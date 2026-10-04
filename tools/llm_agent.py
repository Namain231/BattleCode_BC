"""Minimal tool-using agent loop for OpenAI-compatible providers (Groq, Cloudflare, OpenRouter).

    uv run --python 3.11 python tools/llm_agent.py PROVIDER [--model M] [--steps N] [--readonly] < prompt.txt
    uv run --python 3.11 python tools/llm_agent.py groq "task text"

Why: opencode sends big system prompts and echoes reasoning fields, which Groq rejects. This loop sends a tiny
system prompt, strips reasoning fields, and gives the model four tools: read_file, write_file, list_dir, run
(shell, cwd = repo root, 120 s timeout). It never reads secrets.env and never prints keys.
Secrets are read from the environment (delegate.sh loads secrets.env first).
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", "openai/gpt-oss-120b"),
    "cf": ("https://api.cloudflare.com/client/v4/accounts/%s/ai/v1/chat/completions" % os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
           "CLOUDFLARE_API_TOKEN", "@cf/openai/gpt-oss-120b"),
    "or": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "nvidia/nemotron-3-super-120b-a12b:free"),
}
SYSTEM = ("You are a careful software engineering agent working in the repo at the current directory. Use the tools to read and "
          "edit files and run commands. Make the smallest correct change, verify it by running commands, and finish with a "
          "short plain-text report of what you did and what you could not verify. Never print or write secrets. "
          "Do not read secrets.env.")
TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a text file (optionally a line range).",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create or overwrite a text file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "List a directory.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "run", "description": "Run a bash command in the repo root (120 s timeout); returns exit code and the last 6000 chars of output.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]


def safe(path):
    full = os.path.abspath(os.path.join(ROOT, path))
    if os.path.basename(full).lower() == "secrets.env":
        raise PermissionError("secrets.env is off limits")
    return full


def call_tool(name, a, readonly):
    try:
        if name == "read_file":
            lines = open(safe(a["path"]), encoding="utf-8", errors="replace").read().splitlines()
            s, e = a.get("start") or 1, a.get("end") or min(len(lines), (a.get("start") or 1) + 399)
            return "\n".join(f"{i+1}\t{l}" for i, l in enumerate(lines[s - 1:e], start=s - 1))[:12000]
        if name == "list_dir":
            return "\n".join(sorted(os.listdir(safe(a["path"]))))[:4000]
        if name == "write_file":
            if readonly:
                return "ERROR: read-only run"
            full = safe(a["path"]); os.makedirs(os.path.dirname(full), exist_ok=True)
            open(full, "w", encoding="utf-8", newline="\n").write(a["content"]); return f"wrote {len(a['content'])} chars"
        if name == "run":
            if readonly and any(w in a["command"] for w in (">", "rm ", "mv ", "sed -i", "tee ")):
                return "ERROR: read-only run"
            r = subprocess.run(["bash", "-lc", a["command"]], cwd=ROOT, capture_output=True, text=True, timeout=120,
                               encoding="utf-8", errors="replace")
            return f"exit={r.returncode}\n" + (r.stdout + r.stderr)[-6000:]
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    return "ERROR: unknown tool"


def chat(url, key, model, messages):
    body = json.dumps({"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto",
                       "max_tokens": 4000, "temperature": 0.2}).encode()
    req = urllib.request.Request(url, body, {"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "llm_agent/1.0"})
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))
        except urllib.error.HTTPError as e:
            txt = e.read()[:300].decode("utf8", "replace")
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(10 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {txt}")


def main():
    args = sys.argv[1:]
    provider = args.pop(0)
    model = None; steps = 25; readonly = False
    while args and args[0].startswith("--"):
        o = args.pop(0)
        if o == "--model": model = args.pop(0)
        elif o == "--steps": steps = int(args.pop(0))
        elif o == "--readonly": readonly = True
    prompt = args[0] if args else sys.stdin.read()
    url, keyenv, dmodel = PROVIDERS[provider]
    key = os.environ.get(keyenv, "")
    if not key:
        print(f"ERROR: {keyenv} not set", flush=True); sys.exit(2)
    model = model or dmodel
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    for step in range(steps):
        r = chat(url, key, model, msgs)
        m = r["choices"][0]["message"]
        clean = {"role": "assistant", "content": m.get("content") or ""}
        if m.get("tool_calls"):
            clean["tool_calls"] = [{"id": t["id"], "type": "function", "function": {"name": t["function"]["name"], "arguments": t["function"]["arguments"]}} for t in m["tool_calls"]]
        msgs.append(clean)
        if not m.get("tool_calls"):
            print(clean["content"], flush=True); return
        for t in m["tool_calls"]:
            try:
                a = json.loads(t["function"]["arguments"] or "{}")
            except Exception:
                a = {}
            out = call_tool(t["function"]["name"], a, readonly)
            print(f"[tool {t['function']['name']}] {str(a)[:100]} -> {out[:120]!r}", flush=True)
            msgs.append({"role": "tool", "tool_call_id": t["id"], "content": out})
    print("ERROR: step limit reached without a final answer", flush=True); sys.exit(3)


if __name__ == "__main__":
    main()
