"""Local panel on the Zig judge: OURS vs OPP on maps x seeds x both sides, keep replays, summarise.

    python tools/panel_zig.py BOT_DIR OPP_DIR OUTDIR --set live|dev|test|setB [--seeds 1,2] [-j 10]
    python tools/panel_zig.py BOT_DIR OPP_DIR OUTDIR --maps trauma,maps_rm_test/g97_open_0 --seeds 1

Run from the repo root. Needs the Loong Zig judge (LOONG_JUDGE, default ~/toolchains/zig-judge-out/bin/loong-judge)
and the unswbc engine (UNSWBC_ENGINE, default: the installed unswbc package's unswbc_engine.wasm). Bots are built
by tools/buildwasm.py. Replays are named <map>_<seed>_<ourSide>.replay, which rulemine.evalpair understands:
    python -m rulemine.evalpair OUT_CANDIDATE OUT_CONTROL
Map sets: live = the 10 ladder maps; dev = maps_rm_dev (tuning); test = maps_rm_test (held out: final checks
only); setA / setB = the maps listed in ladder/set60.txt / set60b.txt (the gP evaluation sets).
"""
import argparse, os, subprocess, sys, json, re
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from replay_lite import decode_lite  # noqa

CORE = "trauma,autarky,trophy,default,dilemma,devil,slithery_fight,schooltime,portals,queen_of_spades"
import glob as _glob
LIVE = CORE.split(",")


def _dir(d):
    return [os.path.relpath(p[:-4], ROOT).replace("\\", "/") for p in sorted(_glob.glob(os.path.join(ROOT, d, "*.map")))]


def _set60a():
    return _listfile("set60.txt")


def _set60b():
    return _listfile("set60b.txt")


def _listfile(name):
    path = os.path.join(ROOT, "ladder", name)
    if not os.path.exists(path):
        return []
    names = [n for n in open(path).read().replace(",", " ").split() if n]
    return [n[:-4] if n.endswith(".map") else n for n in names]


SETS = {
    "live": lambda: LIVE,
    "dev": lambda: _dir("maps_rm_dev"),
    "test": lambda: _dir("maps_rm_test"),
    "setA": _set60a,
    "setB": _set60b,
}
DEATHS = ["hit wall", "hit self", "hit other body", "head to head", "no valid action"]


JUDGE = os.environ.get("LOONG_JUDGE", os.path.expanduser("~/toolchains/zig-judge-out/bin/loong-judge"))
try:
    import unswbc as _u
    _ENGINE_DEFAULT = os.path.join(os.path.dirname(_u.__file__), "unswbc_engine.wasm")
except Exception:
    _ENGINE_DEFAULT = "unswbc_engine.wasm"
ENGINE = os.environ.get("UNSWBC_ENGINE", _ENGINE_DEFAULT)

# The judge is a Linux (Zig) binary and play() shells out to it with `nice`, which is POSIX-only.
# On native Windows (not already inside WSL/Git Bash), auto-wrap the judge call through WSL -- same
# path-translation and retry-on-flaky-spawn pattern as tools/queen_panel.py -- so this script can be
# run directly from PowerShell without opening a WSL shell and cd-ing in first. Override the distro
# with WSL_DISTRO if it isn't "Ubuntu"; set PANEL_NO_WSL=1 to force a direct call (e.g. already in WSL).
USE_WSL = os.name == "nt" and not os.environ.get("PANEL_NO_WSL")
WSL_DISTRO = os.environ.get("WSL_DISTRO", "Ubuntu")


def _wslpath(p):
    p = os.path.abspath(p).replace("\\", "/")
    return "/mnt/" + p[0].lower() + p[2:]


def wasm(bot):
    return subprocess.run([sys.executable, os.path.join(HERE, "buildwasm.py"), bot], capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout.strip().splitlines()[-1]


def play(ours, opp, mp, seed, side, outdir):
    out = os.path.join(outdir, f"{mp.replace('/', '+')}_{seed}_{side}.replay")
    if os.path.exists(out):
        return out, "cached"
    a, b = (ours, opp) if side == "A" else (opp, ours)
    mpath = os.path.join(ROOT, f"{mp}.map" if "/" in mp else f"maps/{mp}.map")
    if USE_WSL:
        # judge lives in the WSL home, not the Windows one: use a WSL-side path unless LOONG_JUDGE is set
        judge = _wslpath(JUDGE) if os.environ.get("LOONG_JUDGE") else "$HOME/toolchains/zig-judge-out/bin/loong-judge"
        cmd = (f"nice -n 10 {judge} --engine {_wslpath(ENGINE)} --map {_wslpath(mpath)} "
               f"--a {_wslpath(a)} --b {_wslpath(b)} --seed {seed} --replay {_wslpath(out)} --debug 2")
        for attempt in range(3):  # WSL occasionally fails to spawn under load
            r = subprocess.run(["wsl", "-d", WSL_DISTRO, "--", "bash", "-lc", cmd],
                               capture_output=True, text=True, encoding="utf-8", timeout=1800)
            if os.path.exists(out):
                return out, (r.stdout.strip() or "ok")
        return out, f"FAILED after 3 tries: rc={r.returncode} {(r.stdout + r.stderr)[-200:]}"
    r = subprocess.run(["nice", "-n", "10", JUDGE, "--engine", ENGINE, "--map", mpath, "--a", a, "--b", b,
                        "--seed", str(seed), "--replay", out, "--debug", "2"],
                       capture_output=True, text=True, encoding="utf-8", timeout=1800)
    return out, (r.stdout.strip() or r.stderr.strip()[-200:])


def analyse(path):
    rep = decode_lite(path, {"roundStart", "dragonSplit", "dragonDeath", "dragonIndicator"})
    name = os.path.basename(path)
    mp, seed, side = name[:-7].rsplit("_", 2)
    mine = 0 if side == "A" else 1
    res = rep["result"]
    team, nid, lens = {}, 0, {}
    for line in rep["map"].splitlines():
        p = line.split()
        if p and p[0] == "DRAGON":
            team[nid] = int(p[1]); nid += 1
    alive = set(team)
    snaps = {}
    queen = {}  # round -> longest length reported by our indicators that round
    deaths = [[0] * 5, [0] * 5]
    feeds = 0
    rnd = -1
    splits = [0, 0]
    curq = 0
    qids = {}
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            if rnd >= 0:
                queen[rnd] = curq
            curq = 0
            rnd = e["round"]
            if rnd in (50, 100, 200, 300, 400):
                snaps[rnd] = (sum(1 for i in alive if team.get(i) == mine), sum(1 for i in alive if team.get(i) == 1 - mine))
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; alive.add(e["child"]); splits[e["team"]] += 1
        elif k == "dragonDeath":
            alive.discard(e["id"]); deaths[team.get(e["id"], 0)][e["reason"]] += 1
        elif k == "dragonIndicator" and team.get(e["id"]) == mine:
            m = re.match(r"([WQF])(\d+)", e["text"] or "")
            if m:
                curq = max(curq, int(m.group(2)))
                if m.group(1) == "Q":
                    qids.setdefault(e["id"], rnd)
                if "feed" in e["text"]:
                    feeds += 1
    queen[rnd] = curq
    w = res.get("winner")
    return {
        "map": mp, "seed": int(seed), "side": side,
        "win": 1 if w == mine else (0.5 if w not in (0, 1) else 0),
        "rounds": rnd, "end": res.get("endReason"),
        "ours": res["AB"[mine]], "theirs": res["AB"[1 - mine]],
        "snaps": snaps, "longest_ours_by_round": {r: queen.get(r, 0) for r in (100, 200, 300, 400, 450, rnd)},
        "deaths_ours": deaths[mine], "deaths_theirs": deaths[1 - mine], "splits": [splits[mine], splits[1 - mine]],
        "feeds": feeds, "queens": len(qids),
    }


def family(mp):
    base = mp.split("+")[-1]
    if base.startswith("dense_"):
        return "gen:random"
    if base.startswith("g") and base.count("_") >= 2 and base[1].isdigit():
        return "gen:" + base.split("_")[1]
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ours"); ap.add_argument("opp"); ap.add_argument("outdir")
    ap.add_argument("--maps", default=CORE); ap.add_argument("--seeds", default="1,2")
    ap.add_argument("-j", type=int, default=2)
    ap.add_argument("--set", help="named map set: live, dev, test (overrides --maps)")
    a = ap.parse_args()
    if a.set:
        a.maps = ",".join(SETS[a.set]())
    os.makedirs(a.outdir, exist_ok=True)
    wa, wb = wasm(a.ours), wasm(a.opp)
    jobs = [(m, int(s), side) for m in a.maps.split(",") for s in a.seeds.split(",") for side in "AB"]
    with ThreadPoolExecutor(a.j) as ex:
        futs = [ex.submit(play, wa, wb, m, s, side, a.outdir) for m, s, side in jobs]
        for f in futs:
            out, msg = f.result()
            print(os.path.basename(out), msg, flush=True)
    rows = [analyse(os.path.join(a.outdir, f"{m.replace('/', '+')}_{s}_{side}.replay")) for m, s, side in jobs]
    json.dump(rows, open(os.path.join(a.outdir, "summary.json"), "w"))
    tot = sum(r["win"] for r in rows)
    print(f"\n{a.ours} vs {a.opp}: {tot}/{len(rows)} = {100*tot/len(rows):.1f}%")
    permap = {}
    for r in rows:
        permap.setdefault(family(r["map"]), []).append(r)
    for m, rs in permap.items():
        w = sum(r["win"] for r in rs)
        e50 = [r["snaps"].get(50, (0, 0)) for r in rs]
        print(f"  {m:16s} {w}/{len(rs)}  edge@50 {[o - t for o, t in e50]}  "
              f"final longest ours/theirs {[ (r['ours']['longest'], r['theirs']['longest']) for r in rs]}")


if __name__ == "__main__":
    main()
