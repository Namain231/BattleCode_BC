"""Queen-survival panel: OURS vs OPP on maps x seeds x both sides, judge run inside WSL, replays kept.

    uv run --python 3.11 --with unswbc python tools/queen_panel.py BOT OPP OUTDIR --maps a,b,maps_rm_dev/x --seeds 1,2 [-j 6]

Reports, per game, when and how OUR queen (dragon id 0 for side A, 1 for side B) died, plus the winner and what
decided it. Bots are built by tools/buildwasm.py. Maps resolve as maps/<name>.map unless the name has a '/'.
"""
import argparse, os, subprocess, sys, json, glob
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from replay_lite import decode_lite  # noqa
import unswbc

ENGINE = os.path.join(os.path.dirname(unswbc.__file__), "unswbc_engine.wasm")
DEATHS = ["wall", "self", "body", "headon", "noaction"]
JUDGE = "~/toolchains/zig-judge-out/bin/loong-judge"


def wsl(p):
    p = os.path.abspath(p).replace("\\", "/")
    return "/mnt/" + p[0].lower() + p[2:]


def wasm(bot):
    return subprocess.run([sys.executable, os.path.join(HERE, "buildwasm.py"), bot], capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout.strip().splitlines()[-1]


def play(a, b, mp, seed, side, outdir):
    out = os.path.join(outdir, f"{mp.replace('/', '+')}_{seed}_{side}.replay")
    if os.path.exists(out):
        return
    x, y = (a, b) if side == "A" else (b, a)
    mpath = os.path.join(ROOT, f"{mp}.map" if "/" in mp else f"maps/{mp}.map")
    cmd = f"{JUDGE} --engine {wsl(ENGINE)} --map {wsl(mpath)} --a {wsl(x)} --b {wsl(y)} --seed {seed} --replay {wsl(out)}"
    for attempt in range(3):  # WSL occasionally fails to spawn under load
        r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-lc", cmd], capture_output=True, text=True, timeout=1800)
        if os.path.exists(out):
            return
        print(f"judge produced no replay ({os.path.basename(out)}, try {attempt + 1}): rc={r.returncode} "
              f"{(r.stdout + r.stderr).replace(chr(0), '')[-200:]}", file=sys.stderr, flush=True)


def analyse(path):
    rep = decode_lite(path, {"roundStart", "dragonDeath"})
    mp, seed, side = os.path.basename(path)[:-7].rsplit("_", 2)
    me = 0 if side == "A" else 1
    # which of dragons 0/1 is ours depends on the map: the first DRAGON line's team owns id 0
    teams = [int(l.split()[1]) for l in rep["map"].splitlines() if l.split()[:1] == ["DRAGON"]][:2]
    mine = teams.index(me) if me in teams else me
    rnd, qd, why = -1, None, None
    for e in rep["events"]:
        if e["kind"] == "roundStart":
            rnd = e["round"]
        elif e["id"] == mine:
            qd, why = rnd, DEATHS[e["reason"]] if e["reason"] < 5 else "?"
    res = rep["result"]
    w = res.get("winner")
    return {"map": mp, "seed": int(seed), "side": side, "qdeath": qd, "why": why, "rounds": rnd,
            "win": 1 if w == me else (0.5 if w not in (0, 1) else 0), "end": res.get("endReason"),
            "ours": res["AB"[me]], "theirs": res["AB"[1 - me]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ours"); ap.add_argument("opp"); ap.add_argument("outdir")
    ap.add_argument("--maps", required=True); ap.add_argument("--seeds", default="1")
    ap.add_argument("-j", type=int, default=6)
    a = ap.parse_args()
    maps = a.maps.split(",")
    if len(maps) == 1 and os.path.isdir(os.path.join(ROOT, maps[0])):
        maps = [os.path.relpath(p[:-4], ROOT).replace("\\", "/") for p in sorted(glob.glob(os.path.join(ROOT, maps[0], "*.map")))]
    os.makedirs(a.outdir, exist_ok=True)
    wa, wb = wasm(a.ours), wasm(a.opp)
    jobs = [(m, int(s), side) for m in maps for s in a.seeds.split(",") for side in "AB"]
    with ThreadPoolExecutor(a.j) as ex:
        list(ex.map(lambda j: play(wa, wb, j[0], j[1], j[2], a.outdir), jobs))
    rows = [analyse(os.path.join(a.outdir, f"{m.replace('/', '+')}_{s}_{side}.replay")) for m, s, side in jobs]
    json.dump(rows, open(os.path.join(a.outdir, "summary.json"), "w"))
    n = len(rows)
    alive = lambda r, t: r["qdeath"] is None or r["qdeath"] > t
    ds = sorted(r["qdeath"] if r["qdeath"] is not None else 999 for r in rows)
    print(f"{a.ours} vs {a.opp}: games {n}, wins {sum(r['win'] for r in rows)}")
    print(f"queen alive @50 {sum(alive(r,50) for r in rows)}/{n}  @100 {sum(alive(r,100) for r in rows)}/{n}  "
          f"@250 {sum(alive(r,250) for r in rows)}/{n}  @500 {sum(r['qdeath'] is None for r in rows)}/{n}  "
          f"median death round {ds[n // 2]}")
    causes = {}
    for r in rows:
        causes[r["why"]] = causes.get(r["why"], 0) + 1
    print("death causes", causes)
    for r in rows:
        print(f"  {r['map'][-22:]:22s} {r['seed']}{r['side']} qdeath {r['qdeath']} {r['why']} rounds {r['rounds']} win {r['win']}")


if __name__ == "__main__":
    main()
