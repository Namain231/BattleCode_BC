"""Summarise one Kaggle panel kernel's output by kernel slug (batch records can be overwritten by retries).

    python tools/kernel_result.py p-cand-dijk-out [more slugs]
"""
import json, pathlib, subprocess, sys, tempfile
for slug in sys.argv[1:]:
    d = pathlib.Path(tempfile.mkdtemp(dir="D:/battlecode/tmp"))
    subprocess.run([sys.executable, "-m", "kaggle", "kernels", "output", f"kumaryash1134/{slug}", "-p", str(d),
                    "--file-pattern", "summary"], capture_output=True)
    tot = n = 0; per = []
    for p in sorted(d.rglob("summary.json")):
        s = json.loads(p.read_text()); w = s.get("wins", s.get("W", 0)); g = s.get("games", s.get("n", 0))
        tot += w; n += g; per.append(f"{p.parent.name.split('_vs_')[-1]} {w}/{g}")
    print(f"{slug:24s} TOTAL {tot}/{n}   " + "  ".join(per))
