"""Write a jobs.tsv for loong-judge --jobs: every pairing x map x seed x both sides.

    python3 make_jobs.py --pair proto_rehaul:v712 --pair proto_rehaul:champ --maps live,test --seeds 1-4 \
        [--shards 8] [--replays] > jobs.tsv    (or --out-dir DIR with --shards to write one file per shard)
Bots are bots/<name>.wasm, maps are maps/<set>/*.map (live, dev, test) inside the bundle.
"""
import argparse, glob, os, sys

def seeds(s):
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out

ap = argparse.ArgumentParser()
ap.add_argument("--pair", action="append", required=True, help="OURS:OPP")
ap.add_argument("--maps", default="live")
ap.add_argument("--seeds", default="1-2")
ap.add_argument("--shards", type=int, default=1)
ap.add_argument("--out-dir")
ap.add_argument("--replays", action="store_true", help="also write replays/<job>.replay (big with --debug 2)")
a = ap.parse_args()
here = os.path.dirname(os.path.abspath(__file__))
maps = []
for s in a.maps.split(","):
    maps += sorted(os.path.relpath(p, here) for p in glob.glob(os.path.join(here, "maps", s, "*.map")))
jobs = []
for pair in a.pair:
    ours, opp = pair.split(":")
    for m in maps:
        for sd in seeds(a.seeds):
            for side in "AB":
                A, B = (ours, opp) if side == "A" else (opp, ours)
                jid = f"{ours}~{opp}~{m.replace('/', '+')[5:-4]}~{sd}~{side}"
                row = [jid, m, f"bots/{A}.wasm", f"bots/{B}.wasm", str(sd)]
                if a.replays:
                    row.append(f"replays/{jid}.replay")
                jobs.append("\t".join(row))
if a.out_dir:
    os.makedirs(a.out_dir, exist_ok=True)
    for i in range(a.shards):
        open(os.path.join(a.out_dir, f"jobs_{i}.tsv"), "w").write("\n".join(jobs[i::a.shards]) + "\n")
    print(f"{len(jobs)} jobs in {a.shards} shards", file=sys.stderr)
else:
    print("\n".join(jobs))
