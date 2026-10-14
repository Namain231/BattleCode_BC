import math
import hashlib
import shutil
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
import argparse, os, subprocess, sys, json, re, time, shlex
from contextlib import contextmanager
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


def save_cpu_stats(replay, stdout):
    # Zig judge figures: A p50/mean/max at field 12, B at field 14.
    # Public and local replays can strip instruction counts; preserve judge output.
    for line in stdout.splitlines():
        fields = line.split("\t")
        if len(fields) >= 16 and fields[0] in ("A", "B", "-"):
            try:
                peaks = {"A": int(fields[12].split("/")[2]) / 1e6,
                         "B": int(fields[14].split("/")[2]) / 1e6}
            except (ValueError, IndexError):
                continue
            target = replay + ".cpu.json"
            with open(target + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(peaks, fh)
            os.replace(target + ".tmp", target)
            return peaks
    return None


def checked_result(out, stdout, stderr, identity):
    with open(out+'.diagnostic.log','w',encoding='utf-8') as fh: fh.write((stdout+stderr)[-8192:])
    cpu=save_cpu_stats(out,stdout)
    if cpu is None or any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in cpu.values()): raise ValueError('Invalid judge CPU result')
    result=decode_lite(out,set()).get('result',{})
    if result.get('endReason') is None or result.get('winner') not in (None,0,1) or any(not isinstance(result.get(t),dict) for t in 'AB'): raise ValueError('Incomplete replay result')
    with open(out+'.success.json','w',encoding='utf-8') as fh: json.dump({'returncode':0,'identity':identity},fh)

def file_hash(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def provenance(ours,opp,mp,seed,side):
    mpath=os.path.join(ROOT,f'{mp}.map' if '/' in mp else f'maps/{mp}.map')
    if USE_WSL:
        judge=_wslpath(JUDGE) if os.environ.get('LOONG_JUDGE') else '$HOME/toolchains/zig-judge-out/bin/loong-judge'
        command='sha256sum '+(shlex.quote(judge) if os.environ.get('LOONG_JUDGE') else '"'+judge+'"')
        digest=subprocess.run(['wsl','-d',WSL_DISTRO,'--','bash','-lc',command],capture_output=True,text=True,check=True).stdout.split()[0]
    else: digest=file_hash(JUDGE)
    return dict(version=2,ours=file_hash(ours),opp=file_hash(opp),map=file_hash(mpath),engine=file_hash(ENGINE),judge=digest,seed=int(seed),side=side)

def resource_check():
    if os.environ.get('KAMIKAZE_GUARDS'):
        for drive,minimum in [('C:/',3),('F:/',6)]:
            if shutil.disk_usage(drive).free<minimum*1024**3: raise RuntimeError(drive+' disk headroom exhausted')


def play(ours, opp, mp, seed, side, outdir, lease=None):
    resource_check()
    identity=provenance(ours,opp,mp,seed,side)
    out = os.path.join(outdir, f"{mp.replace('/', '+')}_{seed}_{side}.replay")
    if os.path.exists(out) and os.path.exists(out + ".cpu.json") and os.path.exists(out + ".success.json"):
        with open(out+'.success.json',encoding='utf-8') as fh: status=json.load(fh)
        with open(out+'.cpu.json',encoding='utf-8') as fh: cpu=json.load(fh)
        result=decode_lite(out,set()).get('result',{})
        if status.get('identity')!=identity:
            status={}  # Unproven or changed builds must execute again.
        if status and (status!={'returncode':0,'identity':identity} or set(cpu)!={'A','B'} or any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in cpu.values()) or result.get('endReason') is None or result.get('winner') not in (None,0,1) or any(not isinstance(result.get(t),dict) for t in 'AB')):
            raise ValueError('Invalid cached judge result')
        if status: return out, "cached"
    lease=lease or out+".lease"
    a, b = (ours, opp) if side == "A" else (opp, ours)
    mpath = os.path.join(ROOT, f"{mp}.map" if "/" in mp else f"maps/{mp}.map")
    if USE_WSL:
        # judge lives in the WSL home, not the Windows one: use a WSL-side path unless LOONG_JUDGE is set
        judge = _wslpath(JUDGE) if os.environ.get("LOONG_JUDGE") else None
        # Quote every translated pathname; only the default HOME expansion is shell syntax.
        judge_arg = shlex.quote(judge) if judge is not None else '"$HOME/toolchains/zig-judge-out/bin/loong-judge"'
        cmd = (f"flock {shlex.quote(_wslpath(lease))} nice -n 10 {judge_arg} "
               + shlex.join(["--engine", _wslpath(ENGINE), "--map", _wslpath(mpath),
                             "--a", _wslpath(a), "--b", _wslpath(b), "--seed", str(seed),
                             "--replay", _wslpath(out), "--debug", "2"]))
        for attempt in range(3):  # WSL occasionally fails to spawn under load
            r = subprocess.run(["wsl", "-d", WSL_DISTRO, "--", "bash", "-lc", cmd],
                               capture_output=True, text=True, encoding="utf-8", timeout=1800)
            if r.returncode == 0 and os.path.exists(out):
                checked_result(out, r.stdout, r.stderr, identity)
                resource_check()
                return out, (r.stdout.strip() or "ok")
        with open(out+'.diagnostic.log','w',encoding='utf-8') as fh: fh.write((r.stdout+r.stderr)[-8192:])
        raise RuntimeError(f"FAILED after 3 tries: rc={r.returncode} {(r.stdout+r.stderr)[-2000:]}")
    r = subprocess.run(["flock", lease, "nice", "-n", "10", JUDGE, "--engine", ENGINE, "--map", mpath, "--a", a, "--b", b,
                        "--seed", str(seed), "--replay", out, "--debug", "2"],
                       capture_output=True, text=True, encoding="utf-8", timeout=1800)
    if r.returncode != 0:
        with open(out+'.diagnostic.log','w',encoding='utf-8') as fh: fh.write((r.stdout+r.stderr)[-8192:])
        raise RuntimeError(f"judge exit {r.returncode}: {(r.stdout+r.stderr)[-2000:]}")
    checked_result(out, r.stdout, r.stderr, identity)
    resource_check()
    return out, (r.stdout.strip() or r.stderr.strip()[-200:])


def analyse(path):
    rep = decode_lite(path, {"roundStart", "dragonSplit", "dragonDeath", "dragonIndicator", "dragonAction"})
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
    cpu = [None, None]
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
        elif k == "dragonAction" and e.get("points", 0) > 0:
            owner = team.get(e["id"])
            if owner in (0, 1): cpu[owner] = max(cpu[owner] or 0, e["points"] / 1e6)
        elif k == "dragonIndicator" and team.get(e["id"]) == mine:
            m = re.match(r"([WQF])(\d+)", e["text"] or "")
            if m:
                curq = max(curq, int(m.group(2)))
                if m.group(1) == "Q":
                    qids.setdefault(e["id"], rnd)
                if "feed" in e["text"]:
                    feeds += 1
    queen[rnd] = curq
    if os.path.exists(path + ".cpu.json"):
        with open(path + ".cpu.json", encoding="utf-8") as fh:
            measured = json.load(fh)
        cpu = [measured["A"], measured["B"]]
    w = res.get("winner")
    return {
        "map": mp, "seed": int(seed), "side": side,
        "win": 1 if w == mine else (0.5 if w not in (0, 1) else 0),
        "rounds": rnd, "end": res.get("endReason"),
        "ours": res["AB"[mine]], "theirs": res["AB"[1 - mine]],
        "snaps": snaps, "longest_ours_by_round": {r: queen.get(r, 0) for r in (100, 200, 300, 400, 450, rnd)},
        "deaths_ours": deaths[mine], "deaths_theirs": deaths[1 - mine], "splits": [splits[mine], splits[1 - mine]],
        "cpu_max_ours_M": cpu[mine], "cpu_max_theirs_M": cpu[1-mine],
        "feeds": feeds, "queens": len(qids),
    }


def family(mp):
    base = mp.split("+")[-1]
    if base.startswith("dense_"):
        return "gen:random"
    if base.startswith("g") and base.count("_") >= 2 and base[1].isdigit():
        return "gen:" + base.split("_")[1]
    return base


@contextmanager
def panel_lock(outdir):
    # Supervisor lock only; play() also takes a Linux judge-side flock.
    os.makedirs(outdir, exist_ok=True)
    if USE_WSL and os.path.basename(outdir)=='.judge_reservation':
        lockpath=_wslpath(os.path.join(outdir,'.panel.lock'))
        command='flock -x '+shlex.quote(lockpath)+" bash -c 'echo LOCKED; cat >/dev/null'"
        holder=subprocess.Popen(['wsl','-d',WSL_DISTRO,'--','bash','-lc',command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        try:
            if holder.stdout.readline().strip()!='LOCKED': raise RuntimeError('Cannot acquire shared WSL worker reservation: '+holder.stderr.read())
            yield
        finally:
            if holder.stdin: holder.stdin.close()
            holder.wait(timeout=30)
        return
    with open(os.path.join(outdir, ".panel.lock"), "a+b") as fh:
        if os.name == "nt":
            import msvcrt
            fh.seek(0, 2)
            if fh.tell() == 0:
                fh.write(b"0"); fh.flush()
            waiting = False
            while True:
                fh.seek(0)
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if not waiting: print("Waiting for the existing panel in", outdir, flush=True)
                    waiting = True; time.sleep(1)
            try:
                yield
            finally:
                fh.seek(0); msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(fh, fcntl.LOCK_UN)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ours"); ap.add_argument("opp"); ap.add_argument("outdir")
    ap.add_argument("--maps", default=CORE); ap.add_argument("--seeds", default="1,2")
    ap.add_argument("-j", type=int, default=2)
    ap.add_argument("--set", help="named map set: live, dev, test (overrides --maps)")
    a = ap.parse_args()
    if a.set:
        a.maps = ",".join(SETS[a.set]())
    with panel_lock(os.path.join(ROOT,'out','.judge_reservation')):
        with panel_lock(a.outdir):
            _execute_panel(a)


def _execute_panel(a):
    if os.environ.get('KAMIKAZE_GUARDS'):
        from kamikaze_run import guard
        a.j=min(a.j,guard())  # Recheck under the shared reservation, after any lock wait.
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
    for label in ("ours", "theirs"):
        peaks = [r[f"cpu_max_{label}_M"] for r in rows if r[f"cpu_max_{label}_M"] is not None]
        print(f"CPU max {label}: {max(peaks):.3f}M" if peaks else f"CPU max {label}: unavailable (replay points absent)")
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
