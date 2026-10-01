"""Mechanics board: one table comparing a candidate with its base on EVERY game mechanic we tune, from paired replays.
Built for speed (shared parse cache, parallel warm-up) and for quick reading by whoever runs the loop.

    python tools/mech_board.py CAND BASE [--maps maze|open|all] [-j 4] [--json OUT]
        CAND/BASE: cycle prefixes (cand_stack2, base_viper_nn -> D:/battlecode/tmp/cycle/<prefix>_*) or replay dirs.
    python tools/mech_board.py --one DIR      # single build profile (no pairing), e.g. a ladder replay folder

Rows (per game means, OUR side unless "theirs"): opening, splitting, sprinting, head-on exchange, races/turn order,
pearl timing, scavenging, feeding/endgame, pockets (DOOMED), unit cap, sonar, conversion. Columns:
  cand | base | delta | delta on SWING games (paired outcome differs) | paired games cand>base / cand<base
A JSON copy goes to ladder/cycle/board_<cand>.json and one summary line is appended to ladder/cycle/board_history.jsonl.
"""
import argparse
import collections
import concurrent.futures as cf
import json
import pathlib
import statistics as st
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay_cache import parsed  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CYCLE = pathlib.Path("D:/battlecode/tmp/cycle")
OPEN = {"Portals", "Slithery Fight", "Schooltime"}

# (group, metric key, label, smaller-is-better)
ROWS = [
    ("opening", "units50", "units at r50", False), ("opening", "units100", "units at r100", False),
    ("opening", "mass100", "mass at r100", False), ("opening", "eat0_100", "pearls eaten r0-100", False),
    ("opening", "their_eat0_100", "THEIR pearls eaten r0-100", True),
    ("opening", "their_units100", "THEIR units at r100", True),
    ("splitting", "splits0_100", "splits r0-100", False), ("splitting", "splits100_300", "splits r100-300", False),
    ("splitting", "splits300", "splits r300+", False),
    ("sprinting", "sprints", "sprints/game", True), ("sprinting", "sprint_segs", "segments spent sprinting", True),
    ("sprinting", "sprint_attack_pct", "% sprints = attack (ATK)", False), ("sprinting", "sprint_escape_pct", "% sprints = escape (pd>=0.5)", True),
    ("head-on", "h2h_ours", "our head-on deaths", True), ("head-on", "h2h_theirs", "THEIR head-on deaths", False),
    ("head-on", "h2h_ratio", "exchange theirs/ours", False),
    ("head-on", "h2h_initiated", "our head-on deaths WE initiated", False),
    ("head-on", "h2h_received", "our head-on deaths THEY initiated", True),
    ("head-on", "h2h_atk", "our deaths after an ATK decision (intent)", False),
    ("races", "contested_ours", "contested eats ours (enemy head <=2)", False),
    ("races", "contested_theirs", "contested eats THEIRS", True), ("races", "contested_share", "% contested eats won", False),
    ("races", "their_eat100_300", "THEIR pearls eaten r100-300", True),
    ("turn order", "race_before_pct", "% our contested eats acting before rivals", False),
    ("turn order", "their_race_before_pct", "% THEIR contested eats acting before us", True),
    ("turn order", "died_birth_round", "our dragons dying in their birth round", True),
    ("pearl timing", "fresh_pct", "% eaten within 1 rd of spawn", False), ("pearl timing", "delay", "mean wait before eaten", True),
    ("scavenging", "wreck_ours_pct", "% wreck pearls eaten by us", False), ("scavenging", "wreck_theirs_pct", "% wreck pearls eaten by THEM", True),
    ("feeding", "feeds300", "deliberate feeds r300+", False), ("feeding", "final_longest", "final longest", False),
    ("feeding", "final_mass", "final mass", False), ("feeding", "final_units", "final units", False),
    ("pockets", "doomed_deaths", "deaths while DOOMED", True), ("pockets", "body_deaths", "hit another dragon", True),
    ("unit cap", "cap_rounds", "rounds near cap (>= 62 units, proxy)", True),
    ("sonar", "sonar_per_turn", "sonar pings / our turn", False),
    ("conversion", "dominant", "dominant at r100 (2:1 units)", False), ("conversion", "thrown", "dominant but LOST", True),
    ("result", "won", "win rate", False), ("result", "won_elim", "wins by elimination", False),
]


def metrics(g):
    o, t = g["ours"], 1 - g["ours"]
    M = collections.defaultdict(int, {k: v for k, v in g["misc"].items()})
    def snap(r, side, i):
        s = g["snaps"].get(r); return s[side][i] if s else 0
    def dsum(side, pred):
        return sum(v for (tm, ph, cause, tag), v in g["deaths"].items() if tm == side and pred(ph, cause, tag))
    def asum(side, pred):
        return sum(v for (tm, ph, kind), v in g["acts"].items() if tm == side and pred(ph, kind))
    early = ("r0-50", "r50-100"); mid = ("r100-200", "r200-300"); late = ("r300-400", "r400+")
    sp = sum(M[(o, ph, f"sprint_{k}")] for ph in early + mid + late for k in ("attack", "escape", "other"))
    sa = sum(M[(o, ph, "sprint_attack")] for ph in early + mid + late)
    se = sum(M[(o, ph, "sprint_escape")] for ph in early + mid + late)
    h2o = dsum(o, lambda ph, c, tag: c == "head to head"); h2t = dsum(t, lambda ph, c, tag: c == "head to head")
    co, ct = M[(o, "eat_contested")], M[(t, "eat_contested")]
    wm = max(1, M[("all", "wreck_made")])
    last = g["snaps"][max(g["snaps"])] if g["snaps"] else {o: (0, 0, 0), t: (0, 0, 0)}
    dom = snap(100, t, 0) > 0 and snap(100, o, 0) >= 2 * snap(100, t, 0)
    return dict(
        units50=snap(50, o, 0), units100=snap(100, o, 0), mass100=snap(100, o, 1), their_units100=snap(100, t, 0),
        eat0_100=sum(g["eats"].get((o, ph), 0) for ph in early),
        their_eat0_100=sum(g["eats"].get((t, ph), 0) for ph in early),
        their_eat100_300=sum(g["eats"].get((t, ph), 0) for ph in mid),
        splits0_100=asum(o, lambda ph, k: k == "split" and ph in early), splits100_300=asum(o, lambda ph, k: k == "split" and ph in mid),
        splits300=asum(o, lambda ph, k: k == "split" and ph in late),
        sprints=sp, sprint_segs=asum(o, lambda ph, k: k == "sprint_segs"),
        sprint_attack_pct=100 * sa / sp if sp else 0, sprint_escape_pct=100 * se / sp if sp else 0,
        h2h_ours=h2o, h2h_theirs=h2t, h2h_ratio=h2t / h2o if h2o else 0,
        h2h_atk=dsum(o, lambda ph, c, tag: c == "head to head" and tag == "ATK"),
        h2h_initiated=M[(o, "h2h_initiated")], h2h_received=M[(o, "h2h_received")],
        race_before_pct=100 * M[(o, "race_before")] / max(1, M[(o, "race_before")] + M[(o, "race_after")]),
        their_race_before_pct=100 * M[(t, "race_before")] / max(1, M[(t, "race_before")] + M[(t, "race_after")]),
        died_birth_round=M[(o, "died_birth_round")],
        contested_ours=co, contested_theirs=ct, contested_share=100 * co / (co + ct) if co + ct else 0,
        fresh_pct=100 * M[(o, "eat_fresh")] / M[(o, "eat_n")] if M[(o, "eat_n")] else 0,
        delay=M[(o, "eat_delay_sum")] / M[(o, "eat_n")] if M[(o, "eat_n")] else 0,
        wreck_ours_pct=100 * M[(o, "wreck_eaten")] / wm, wreck_theirs_pct=100 * M[(t, "wreck_eaten")] / wm,
        feeds300=dsum(o, lambda ph, c, tag: c == "FEED" and ph in late),
        final_longest=last[o][2], final_mass=last[o][1], final_units=last[o][0],
        doomed_deaths=dsum(o, lambda ph, c, tag: tag == "DOOMED"), body_deaths=dsum(o, lambda ph, c, tag: c == "hit other body"),
        cap_rounds=M[(o, "cap_rounds")], sonar_per_turn=M[(o, "sonar")] / max(1, g["turns"].get(o, 1)),
        dominant=int(dom), thrown=int(dom and not g["won"]), won=int(g["won"]), won_elim=int(g["won"] and g["end"] == "elim"),
        map=g["map"])


def resolve(x):
    m = sorted(CYCLE.glob(x + "_*"))
    if m: return m[-1]
    p = pathlib.Path(x)
    if p.exists() and any(p.rglob("*.replay")): return p
    sys.exit(f"no replay dir for {x}")


def load(paths, j):
    with cf.ProcessPoolExecutor(max_workers=j) as ex:
        return list(ex.map(parsed, paths, chunksize=4))


def keep(g, which):
    return which == "all" or (which == "open") == (g["map"] in OPEN)


def fmt(v):
    if isinstance(v, float): return f"{v:7.2f}" if abs(v) < 2 else f"{v:7.1f}"
    return f"{v:7d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand", nargs="?"); ap.add_argument("base", nargs="?")
    ap.add_argument("--one", default=""); ap.add_argument("--maps", default="all", choices=["all", "maze", "open"])
    ap.add_argument("-j", type=int, default=4); ap.add_argument("--json", default="")
    a = ap.parse_args()
    t0 = time.time()
    if a.one:
        d = resolve(a.one); P = sorted(d.rglob("*.replay"))
        G = [g for g in load(P, a.j) if keep(g, a.maps)]
        ms = [metrics(g) for g in G]
        print(f"{d.name}: {len(ms)} games ({a.maps}) in {time.time() - t0:.0f}s")
        grp = None
        for group, key, label, _ in ROWS:
            if group != grp: print(f"-- {group}"); grp = group
            print(f"   {label:38s} {fmt(st.mean(m[key] for m in ms))}")
        return
    cd, bd = resolve(a.cand), resolve(a.base)
    c = {str(p.relative_to(cd)): p for p in cd.rglob("*.replay")}; b = {str(p.relative_to(bd)): p for p in bd.rglob("*.replay")}
    keys = sorted(set(c) & set(b))
    GC = load([c[k] for k in keys], a.j); GB = load([b[k] for k in keys], a.j)
    pairs = [(k, metrics(x), metrics(y)) for k, x, y in zip(keys, GC, GB) if keep(x, a.maps)]
    swing = [p for p in pairs if p[1]["won"] != p[2]["won"]]
    print(f"{cd.name} vs {bd.name}: {len(pairs)} paired games ({a.maps}), {len(swing)} swing; wins {sum(p[1]['won'] for p in pairs)} v "
          f"{sum(p[2]['won'] for p in pairs)} (+{sum(1 for p in swing if p[1]['won'])}/-{sum(1 for p in swing if p[2]['won'])})  [{time.time() - t0:.0f}s]")
    print(f"{'':52s} {'cand':>7s} {'base':>7s} {'delta':>7s} {'swingD':>7s}  c>b/c<b")
    out = {"cand": cd.name, "base": bd.name, "maps": a.maps, "games": len(pairs), "swing": len(swing), "rows": []}
    grp = None
    for group, key, label, down in ROWS:
        if group != grp: print(f"-- {group}"); grp = group
        cv = st.mean(p[1][key] for p in pairs); bv = st.mean(p[2][key] for p in pairs)
        sd = st.mean(p[1][key] - p[2][key] for p in swing) if swing else 0.0
        gt = sum(1 for p in pairs if p[1][key] > p[2][key]); lt = sum(1 for p in pairs if p[1][key] < p[2][key])
        better = (cv < bv) if down else (cv > bv)
        flag = "" if abs(cv - bv) < 1e-9 else (" +" if better else " -")
        print(f"   {label:48s} {fmt(float(cv))} {fmt(float(bv))} {fmt(float(cv - bv))} {fmt(float(sd))}  {gt:3d}/{lt:<3d}{flag}")
        out["rows"].append(dict(group=group, metric=key, label=label, cand=cv, base=bv, delta=cv - bv, swing_delta=sd, gt=gt, lt=lt,
                                better=bool(better) if flag else None))
    permap = collections.defaultdict(lambda: [0, 0, 0])
    for k, x, y in pairs: e = permap[x["map"]]; e[0] += 1; e[1] += x["won"]; e[2] += y["won"]
    print("-- per map (games, cand wins, base wins): " + ", ".join(f"{m} {v[1]}v{v[2]}/{v[0]}" for m, v in sorted(permap.items())))
    out["per_map"] = dict(permap)
    jp = pathlib.Path(a.json) if a.json else ROOT / "ladder" / "cycle" / f"board_{a.cand}.json"
    jp.parent.mkdir(parents=True, exist_ok=True); jp.write_text(json.dumps(out, indent=1))
    with open(ROOT / "ladder" / "cycle" / "board_history.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "cand": a.cand, "base": a.base, "maps": a.maps,
                            "games": len(pairs), "swing": len(swing), "deltas": {r["metric"]: round(r["delta"], 2) for r in out["rows"]}}) + "\n")


if __name__ == "__main__":
    main()
