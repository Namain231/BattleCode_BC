"""How each side sprints (multi-step moves): per game, per phase; how many sprints end in the sprinter's death that turn
(head-on = an attack that landed; other = a costly mistake), and how many were attack-length vs escape.

    python tools/sprint_report.py [GLOB] [--sub 11461] [--n 30]
"""
import argparse, collections, glob, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402

def run(path, sub):
    rep = _decode(path)
    ours = 0 if rep["botA"] and not rep["botB"] else 1 if rep["botB"] and not rep["botA"] else None
    if ours is None or (sub and str(rep["botA"] if ours == 0 else rep["botB"]) != str(sub)): return None
    team = {}; nid = 0
    for l in rep["map"].splitlines():
        p = l.split()
        if p and p[0] == "DRAGON": team[nid] = int(p[1]); nid += 1
    st = {s: collections.Counter() for s in (0, 1)}
    rnd = 0; pending = {}
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]; pending = {}
        elif k == "dragonSplit": team[e["child"]] = e["team"]
        elif k == "dragonAction" and e.get("act") == "move":
            t = team.get(e["id"]); n = len(e.get("dirs", ""))
            if t is None: continue
            side = 0 if t == ours else 1
            ph = "r0-100" if rnd < 100 else "r100-300" if rnd < 300 else "r300+"
            st[side]["moves"] += 1
            if n > 1:
                st[side]["sprints"] += 1; st[side][f"sprint@{ph}"] += 1; st[side]["segs"] += n - 1
                pending[e["id"]] = side
        elif k == "dragonDeath" and e["id"] in pending:
            side = pending.pop(e["id"])
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            st[side]["sprint->H2H" if cause == "head to head" else "sprint->died other"] += 1
    return st, rep["result"].get("winner") == ours

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src", nargs="?", default="ladder/losses/*/*.replay")
    ap.add_argument("--sub", default="11461"); ap.add_argument("--n", type=int, default=30); a = ap.parse_args()
    files = sorted(glob.glob(a.src), key=lambda f: pathlib.Path(f).stat().st_mtime, reverse=True)
    tot = {0: collections.Counter(), 1: collections.Counter()}; g = 0
    for f in files:
        try: r = run(f, a.sub)
        except Exception: continue
        if not r: continue
        for s in (0, 1): tot[s].update(r[0][s])
        g += 1
        if g >= a.n: break
    for s, name in ((0, "ours"), (1, "theirs")):
        c = tot[s]; sp = max(1, c["sprints"])
        print(f"{name:6s} per game: sprints {c['sprints'] / g:.1f} (r0-100 {c['sprint@r0-100'] / g:.1f}, r100-300 {c['sprint@r100-300'] / g:.1f}, "
              f"r300+ {c['sprint@r300+'] / g:.1f}), segments paid {c['segs'] / g:.1f}; sprints ending in head-on "
              f"{100 * c['sprint->H2H'] / sp:.0f}%, in another death {100 * c['sprint->died other'] / sp:.0f}%")
    print(f"({g} games)")

if __name__ == "__main__":
    main()
