#!/bin/bash
# Director -> Executor -> Critic pipeline (Claude is the director; this script runs the other two roles).
#
# Usage: tools/delegate.sh TASK_FILE.md [VERIFY_CMD]
#   TASK_FILE.md  standalone brief (the agents have no memory of the conversation).
#   VERIFY_CMD    optional shell command run after the executor; its output goes to the critic.
#
# Back-ends (set EXECUTOR_CHAIN / CRITIC). The executor chain tries each in order and falls through on
# usage-limit / auth / empty-output failures:
#   codex    Codex CLI (ChatGPT plan; best quality; has a usage limit)
#   gq       own tool loop + Groq gpt-oss-120b (tools/llm_agent.py): free, fast, works multi-step  <- default first
#   gcf/gor  same loop on Cloudflare / OpenRouter free
#   cf       opencode + Cloudflare Workers AI gpt-oss-120b      (free plan; works with tools)
#   cfcode   opencode + Cloudflare qwen2.5-coder-32b            (free plan)
#   or       opencode + OpenRouter free Nemotron-3-super-120b   (free; rate limited)
#   longcat  opencode + OpenRouter LongCat                      (needs OpenRouter credit)
#   groq     opencode + Groq (BROKEN in opencode: reasoning_content + size limits; use gq instead)
#   kimi     Kimi CLI (needs a paid Kimi Code plan; currently 403)
#   OPENCODE_MODEL=provider/model overrides the model for any opencode back-end.
# Env: EXECUTOR_CHAIN="gq gcf cf or codex"   CRITIC=gq   (CRITIC may be any name above; codex runs read-only)
# Secrets come from secrets.env (loaded here; never echoed).

set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.bun/bin:$HOME/.kimi-code/bin:$PATH"
set -a; [ -f secrets.env ] && . ./secrets.env; set +a

TASK_FILE="${1:?usage: delegate.sh TASK_FILE.md [VERIFY_CMD]}"
VERIFY_CMD="${2:-}"
EXECUTOR_CHAIN="${EXECUTOR_CHAIN:-${EXECUTOR:-gq gcf cf or}}"   # free executors only; if all fail the DIRECTOR does the work
CRITIC="${CRITIC:-codex}"   # Codex is the critic (give it the diff in the prompt)
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$(dirname "$TASK_FILE")/$(basename "$TASK_FILE" .md).$STAMP"

oc_model() {  # name -> opencode model id
  case "$1" in
    groq)    echo "groq/openai/gpt-oss-120b" ;;
    cf)      echo "cloudflare/@cf/openai/gpt-oss-120b" ;;
    cfcode)  echo "cloudflare/@cf/qwen/qwen2.5-coder-32b-instruct" ;;
    or)      echo "openrouter/nvidia/nemotron-3-super-120b-a12b:free" ;;
    longcat) echo "openrouter/${LONGCAT_MODEL:-meituan/longcat-2.0}" ;;
  esac
}

# run_agent NAME MODE(write|read) PROMPT LOGFILE ; returns 0 on a usable run
run_agent() {
  local name="$1" mode="$2" prompt="$3" log="$4" model
  case "$name" in
    codex)
      if [ "$mode" = write ]; then codex exec --approve-for-me "$prompt" < /dev/null > "$log" 2>&1
      else codex exec -s read-only "$prompt" < /dev/null > "$log" 2>&1; fi ;;
    gq|gcf|gor)   # own tool loop (tools/llm_agent.py): Groq / Cloudflare / OpenRouter-free, tiny prompt, no opencode
      local ro=""; [ "$mode" = read ] && ro="--readonly"
      uv run --python 3.11 python tools/llm_agent.py "$(case "$name" in gq) echo groq;; gcf) echo cf;; gor) echo or;; esac)" $ro "$prompt" < /dev/null > "$log" 2>&1 ;;
    kimi)
      "$HOME/.kimi-code/bin/kimi.exe" --auto -p "$prompt" < /dev/null > "$log" 2>&1 ;;
    groq|cf|cfcode|or|longcat)
      model="${OPENCODE_MODEL:-$(oc_model "$name")}"
      opencode run --model "$model" "$prompt" < /dev/null > "$log" 2>&1 ;;
    *) echo "unknown back-end $name" > "$log"; return 2 ;;
  esac
  # failure signatures: usage limits, auth errors, empty output
  if grep -qiE "usage limit|rate.?limited|Too Many Requests|daily free allocation|requires more credits|not available on the Workers|No model configured|UnknownFlag|reasoning_content|HTTP 40[13]|status.?(code)?[: ]+40[13]" "$log" \
     || [ "$(wc -c < "$log")" -lt 40 ]; then return 1; fi
  return 0
}

SNAP="$OUT.snap"
uv run --python 3.11 python tools/scoped_diff.py snap "$SNAP"   # remember pre-executor state

used=""
for b in $EXECUTOR_CHAIN; do
  echo "== executor: $b =="
  if run_agent "$b" write "$(cat "$TASK_FILE")" "$OUT.exec.log"; then used="$b"; break; fi
  echo "   $b failed or was limited (see $OUT.exec.$b.failed.log); trying next"
  mv "$OUT.exec.log" "$OUT.exec.$b.failed.log" 2>/dev/null
done
[ -z "$used" ] && echo "!! every executor back-end failed" && used="none"
echo "executor used: $used" > "$OUT.backend.txt"

uv run --python 3.11 python tools/scoped_diff.py diff "$SNAP" > "$OUT.diff" 2>&1 || true   # only what the executor changed
rm -rf "$SNAP"

VERIFY_OUT="(no verify command given)"
if [ -n "$VERIFY_CMD" ]; then
  echo "== verify: $VERIFY_CMD =="
  bash -c "$VERIFY_CMD" > "$OUT.verify.log" 2>&1; VERIFY_OUT="exit=$?; $(tail -c 6000 "$OUT.verify.log")"
fi

echo "== critic: $CRITIC =="
CRITIQUE_PROMPT="Review the following diff against this task. Do not make further edits.
Report: (1) does it actually do what the task asked, (2) anything wrong or risky,
(3) anything the task asked for that is missing. Be specific, cite lines. End with one line:
VERDICT: PASS  or  VERDICT: FAIL: <reason>.

TASK:
$(cat "$TASK_FILE")

DIFF (only what the executor changed):
$(cat "$OUT.diff")

VERIFY OUTPUT:
$VERIFY_OUT"
run_agent "$CRITIC" read "$CRITIQUE_PROMPT" "$OUT.critique.log" || echo "   critic $CRITIC failed or was limited (see $OUT.critique.log)"
echo "  -> $OUT.critique.log"

echo
echo "Done. Executor: $used. Read $OUT.critique.log before trusting $OUT.diff; this script does not act on the critique."
