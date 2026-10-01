"""Summarise loong-judge batch output (one or more results files). Job ids: OURS~OPP~set+map~seed~side.

    python3 summarize.py results*.tsv [--by family|map]
"""
import sys, collections, math

def fam(m):
    s, _, name = m.partition("+")
    if s in ("test", "dev"):
        if name.startswith("rdense"): return s + ":random"
        parts = name.split("_")
        return s + ":" + (parts[1] if len(parts) > 2 else name)
    return s + ":" + name

files = [f for f in sys.argv[1:] if not f.startswith("--")]
by = "family" if "--by" not in sys.argv else sys.argv[sys.argv.index("--by") + 1]
res = collections.defaultdict(lambda: collections.defaultdict(list))
errs = 0
for f in files:
    for line in open(f):
        p = line.rstrip("\n").split("\t")
        if len(p) < 4 or "~" not in p[0]: continue
        ours, opp, m, seed, side = p[0].split("~")
        w = p[1]
        if w not in ("A", "B", "-"): errs += 1; continue
        score = 0.5 if w == "-" else (1.0 if w == side else 0.0)
        key = fam(m) if by == "family" else m
        res[(ours, opp)][key].append(score)
for (ours, opp), per in res.items():
    allv = [v for vs in per.values() for v in vs]
    n = len(allv); p = sum(allv) / n
    lo = p - 1.96 * math.sqrt(p * (1 - p) / n); hi = p + 1.96 * math.sqrt(p * (1 - p) / n)
    print(f"{ours} vs {opp}: {sum(allv):g}/{n} = {100*p:.1f}%  (95% CI {100*lo:.0f}-{100*hi:.0f})")
    for k in sorted(per):
        vs = per[k]; print(f"   {k:28s} {sum(vs):g}/{len(vs)}")
if errs: print("errors:", errs)
