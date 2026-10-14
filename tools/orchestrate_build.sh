#!/bin/bash
# Unattended executor -> critic -> fix loop for the league / farm / param-search build (no LLM inside the loops being built).
# Usage: nohup bash tools/orchestrate_build.sh > out/orch.log 2>&1 &
# Each step: executor (codex exec) writes out/<name>_report.md; critic (codex exec) writes out/<name>_critique.md ending in VERDICT;
# on FAIL the executor gets the critique and fixes (max 2 fix rounds). Markers: out/<name>.stepdone, out/orch.done.
cd /c/Users/sohan/Downloads/BattleCode_BC || exit 1
export PATH="$HOME/.bun/bin:$PATH" UV_CACHE_DIR='F:\uv-cache' PYTHONIOENCODING=utf-8
mkdir -p out
EXTRA="
ADDENDUM (director, 2026-10-04): Kaggle API returned 403 earlier, so do NOT depend on Kaggle for training: train small nets locally (Python310 CUDA torch, see ml/v6/README.md; the GTX 1650 does ~15k samples/s). The farm's primary lane is the local WSL box; make Kaggle and GitHub Actions lanes optional, documented, and OFF by default (GitHub Actions and any publishing need explicit user approval). Never use an LLM inside any loop you build. Write crash-resume state to disk after every evaluation. Write your final report to out/__NAME___report.md (<= 40 lines: files changed/created, exact commands, verification numbers, what is unverified)."

run_codex() { # $1 prompt-file $2 log
  for attempt in 1 2 3 4 5; do
    codex exec --approve-for-me "$(cat "$1")" > "$2" 2>&1
    if ! grep -qE "^ERROR:.*(capacity|usage limit)|hit your usage limit" "$2"; then return 0; fi
    echo "[$(date +%H:%M)] codex capacity/limit, retry $attempt"; sleep 180
  done
  return 1
}

for NAME in ${STEPS:-league_build farm_scale param_search}; do
  [ -f out/$NAME.stepdone ] && continue
  echo "[$(date +%H:%M)] START $NAME"
  { cat tools/tasks/$NAME.md; echo "$EXTRA" | sed "s/__NAME__/$NAME/g"; } > out/${NAME}_exec_prompt.md
  sed "s/__NAME__/$NAME/g" tools/tasks/critic_generic.md > out/${NAME}_critic_prompt.md
  run_codex out/${NAME}_exec_prompt.md out/${NAME}.exec.codex.log
  for round in 1 2 3; do
    run_codex out/${NAME}_critic_prompt.md out/${NAME}.critic$round.codex.log
    if tail -n 3 out/${NAME}_critique.md 2>/dev/null | grep -q "VERDICT: PASS"; then echo "[$(date +%H:%M)] $NAME critic PASS (round $round)"; break; fi
    echo "[$(date +%H:%M)] $NAME critic FAIL/none (round $round)"
    [ $round -eq 3 ] && break
    { cat out/${NAME}_exec_prompt.md; echo; echo "FIX ROUND $round: the critic's findings are in out/${NAME}_critique.md. Fix every required item, re-verify, and rewrite out/${NAME}_report.md."; } > out/${NAME}_fix_prompt.md
    run_codex out/${NAME}_fix_prompt.md out/${NAME}.fix$round.codex.log
  done
  touch out/$NAME.stepdone
  printf '%s\n' "- [$(date +%F)] [director] [orchestrate_build] step $NAME finished (see out/${NAME}_report.md and out/${NAME}_critique.md)" >> AGENT_LOG.md
done
touch out/orch.done
echo "[$(date +%H:%M)] ALL DONE"
