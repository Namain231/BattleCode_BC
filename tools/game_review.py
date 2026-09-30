"""Per-game review of a candidate (small samples, read thoroughly): what happened in each game, did the feature fire,
did its target metric move, what broke. Pairs with a control label on the same team+map when given.

    python tools/game_review.py LABEL [--vs CONTROL_LABEL] [--n 12]        # ladder games from ladder/top_scrims.jsonl
    python tools/game_review.py --dir D:/battlecode/tmp/pairs2/cand_x [--vs-dir .../viper_nn]   # sandbox replays

Per game: result + loss type, units/mass/longest at r100/200/300/400/end (ours v theirs), the round the pair first
diverged (paired mode), pearls eaten r0-100, wreck share, head-on exchange, holders of our longest after r300 and its
fate, and feature activity: giant packets (HUNT/CUTOFF magic 0xD17A), feeds r300+, sprints/splits after r300.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from loss_digest import digest  # noqa: E402
from mechanics import analyse  # noqa: E402
from replay import _decode  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = pathlib.Path("D:/battlecode/tmp/review")
GIANT_MAGIC = 0xD17A


def fetch(game):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{game}.replay"
    if not p.exists():
        subprocess.run(["curl", "-sL", "-o", str(p), f"https://game.battlecode.au/api/v1/battles/{game}/replay",
                        "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"])
    return p


def side_of(path, rep):
    import re
    m = re.search(r"_([AB])_\d+\.replay$", str(path))
    if m: return 0 if m.group(1) == "A" else 1
    return 0 if rep["botA"] and not rep["botB"] else 1


def review(path):
    rep = _decode(str(path)); side = side_of(path, rep)
    d = digest(path); m = analyse(str(path), side); c = m["c"]
    gp = sum(1 for e in rep["events"] if e["kind"] == "sonarPing" and isinstance(e.get("value", e.get("v")), int)
             and (e.get("value", e.get("v")) >> 48) == GIANT_MAGIC)
    wm = max(1, c["wreck_made"])
    return dict(d=d, feat=dict(giant_pkts=gp, feeds300=d["feeds"], sprint300=c["sprint@r300+"], split300=c["split@r300+"]),
                eat100=c["eat@r0-50"] + c["eat@r50-100"], wreck=round(100 * c["scav0"] / wm),
                h2h=(c["h2h_deaths"], c["their_h2h"]))


def line(tag, r):
    d = r["d"]; s = d["snaps"]
    cps = " ".join(f"r{k}:{v[0]}/{v[1]}/L{v[2]}v{v[3]}/{v[4]}/L{v[5]}" for k, v in sorted(s.items()) if k in (100, 200, 300, 400, 499))
    f = r["feat"]
    return (f"  {tag:7s} {'WIN ' if d['won'] else 'LOSS'} {d['kind']:9s} eat r0-100 {r['eat100']:3d}  wreck {r['wreck']:3d}%  "
            f"h2h {r['h2h'][0]}v{r['h2h'][1]}  holders {d['holders']} fate {d['fates']}  giant {f['giant_pkts']} feeds {f['feeds300']}"
            f" spr300 {f['sprint300']} spl300 {f['split300']}\n            {cps}")


def diverge(a, b):
    for k in sorted(a["d"]["snaps"]):
        if k in b["d"]["snaps"] and a["d"]["snaps"][k][:3] != b["d"]["snaps"][k][:3]: return k
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label", nargs="?"); ap.add_argument("--vs", default="")
    ap.add_argument("--dir", default=""); ap.add_argument("--vs-dir", default="")
    ap.add_argument("--n", type=int, default=12)
    a = ap.parse_args()
    pairs = []
    if a.dir:
        base = pathlib.Path(a.dir); ctrl = pathlib.Path(a.vs_dir) if a.vs_dir else None
        for p in sorted(base.glob("*.replay"))[:a.n]:
            q = ctrl / p.name if ctrl and (ctrl / p.name).exists() else None
            pairs.append((p.stem, p, q))
    else:
        rows = [json.loads(l) for l in open(ROOT / "ladder/top_scrims.jsonl", encoding="utf-8")]
        mine = [r for r in rows if r["label"] == a.label and r.get("attributed_ok")]
        ctl = {(r["team"], r["map"]): r for r in rows if a.vs and r["label"] == a.vs and r.get("attributed_ok")}
        for r in mine[:a.n]:
            c = ctl.get((r["team"], r["map"]))
            pairs.append((f"team {r['team']} {r['map']}", fetch(r["game"]), fetch(c["game"]) if c else None))
    for name, p, q in pairs:
        try:
            rc = review(p); rq = review(q) if q else None
        except Exception as ex:   # noqa: BLE001
            print(f"== {name}: skipped ({ex})"); continue
        head = f"== {name}"
        if rq: head += f"   (paired games first differ at r{diverge(rc, rq)})"
        print(head); print(line("CAND", rc))
        if rq: print(line("CONTROL", rq))


if __name__ == "__main__":
    main()
