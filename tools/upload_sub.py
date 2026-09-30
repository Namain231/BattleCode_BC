"""Upload a candidate WITHOUT leaving it active: new uploads go active as soon as they build, so this waits for the
build and re-activates the champion at once. Prints the new submission id.

    python tools/upload_sub.py cand_y10k Y.7.12.17 --champion 11461
"""
import argparse
import json
import os
import pathlib
import subprocess
import time

BASE = "https://game.battlecode.au/api/v1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
if "UNSWBC_KEY" not in os.environ and (ROOT / "secrets.env").exists():
    for _l in (ROOT / "secrets.env").read_text().splitlines():
        if "=" in _l:
            _k, _v = _l.split("=", 1); os.environ.setdefault(_k.strip(), _v.strip())


def api(path, method=None):
    cmd = ["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"]
    if method:
        cmd += ["-X", method]
    for k in range(6):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            time.sleep(5 + 5 * k)
    return {}


def subs():
    d = api("/submissions")
    return d.get("submissions", d) if isinstance(d, dict) else d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("name")
    ap.add_argument("--champion", type=int, required=True)
    a = ap.parse_args()
    before = {s["id"] for s in subs()}
    subprocess.run(["unswbc", "submit", str(ROOT / a.dir), "-n", a.name, "-d", "maintenance"], capture_output=True)
    new = None
    for _ in range(60):
        cur = [s for s in subs() if s["id"] not in before and s.get("name") == a.name]
        if cur and cur[0].get("status") in ("active", "idle", "ready", "failed", "build failed"):
            new = cur[0]; break
        time.sleep(10)
    api(f"/submissions/{a.champion}/activate", method="POST")
    time.sleep(3)
    act = [s["id"] for s in subs() if s.get("status") == "active"]
    print(json.dumps({"dir": a.dir, "name": a.name, "id": new and new["id"], "status": new and new.get("status"),
                      "active_now": act}))


if __name__ == "__main__":
    main()
