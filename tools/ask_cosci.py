"""Talk to a co-scientist in ITS OWN persistent session (it keeps its context across rounds).

    python tools/ask_cosci.py codex ladder/msg.md        # reply -> ladder/cosci/codex_<n>.md (printed too)
    python tools/ask_cosci.py agy   ladder/msg.md

Sessions live in ladder/cosci/sessions.json: {"codex": "<session uuid>", "agy": "<conversation id>"}.
codex: `codex exec resume <id> -` with the message on stdin (model gpt-6-luna, workspace-write sandbox).
agy: `agy -p <msg> --conversation <id> --model claude-opus-4-6-thinking --mode accept-edits` (Gemini quota is out
until ~6 Oct; terminal commands are denied in headless mode, so agy must use file tools only).
"""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / "ladder" / "cosci"
AGY = pathlib.Path(os.environ["LOCALAPPDATA"]) / "agy" / "bin" / "agy.exe"


def main():
    who, msg_file = sys.argv[1], pathlib.Path(sys.argv[2])
    DIR.mkdir(parents=True, exist_ok=True)
    sess = json.loads((DIR / "sessions.json").read_text()) if (DIR / "sessions.json").exists() else {}
    msg = msg_file.read_text(encoding="utf-8")
    n = len(list(DIR.glob(f"{who}_*.md"))) + 1
    out = DIR / f"{who}_{n}.md"
    if who == "codex":
        cmd = ["codex", "exec", "resume", sess["codex"], "-", "-m", "gpt-6-luna", "--skip-git-repo-check",
               "-o", str(out)]
        r = subprocess.run(cmd, input=msg, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=ROOT, shell=True)
        if not out.exists():
            out.write_text(r.stdout[-6000:] + r.stderr[-2000:], encoding="utf-8")
    else:
        cmd = [str(AGY), "-p", msg, "--conversation", sess["agy"], "--model", "claude-opus-4-6-thinking",
               "--mode", "accept-edits", "--output-format", "json"]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        try:
            d = json.loads(r.stdout[r.stdout.index("{"):])
            out.write_text(d.get("response", ""), encoding="utf-8")
        except Exception:
            out.write_text(r.stdout[-6000:] + r.stderr[-2000:], encoding="utf-8")
    print(f"--- {who} -> {out}")
    print(out.read_text(encoding="utf-8")[:4000])


if __name__ == "__main__":
    main()
