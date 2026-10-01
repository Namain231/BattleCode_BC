"""Continuous improvement loop: fight + analyse every queued candidate against the current base, write a report and a
ledger entry, and print one CYCLE line per candidate so a watcher (Claude) can review, audit and decide.

    python -u tools/cycle.py [--queue ladder/cycle/queue.txt] [--state ladder/cycle/state.json]

Queue file: one candidate per line, `<dir> | <target metric> | <note>`; lines are consumed in order (a processed line
is marked done in ladder/cycle/done.txt). The base is state.json["base"] (default viper_nn); promote by editing it
(`python tools/cycle.py promote cand_x`), which also records the stack in the ledger.

Fight: paired sandbox games (same maps, seeds, sides) on PANEL_MAPS x PANEL_OPPS, replays kept; base games are cached
per base content hash. Analyse: per game, from the replays: result + loss type, units/mass at r100, pearls eaten r0-100,
deliberate feeds r350+, final longest, final mass; plus paired flips (games the candidate won and the base lost, and
vice versa). Screen (advice only, Claude decides): target metric moved in the intended direction and paired flips >= 0.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import statistics as st
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parents[1]
CYC = ROOT / "ladder" / "cycle"
REPLAYS = pathlib.Path("D:/battlecode/tmp/cycle")
PANEL_MAPS = ["trophy", "queen_of_spades", "default", "dilemma", "autarky", "devil", "trauma",
              "slithery_fight", "schooltime", "portals"]
PANEL_OPPS = ["opponents/nick_farm", "opponents/nick_arch4"]
SEEDS = 2          # screen: stage 1 plays seed index 0, stage 2 (only if promising) seed index 1
DOWN_IS_GOOD = {"sprint_segs", "sprints", "h2h_ours", "hit_other_body", "throws", "friendly_h2h"}   # targets where smaller is better


def judge():
    """zig (WSL loong-judge, ~2.5x faster, identical results) when installed, else the standard sandbox."""
    import os
    j = os.environ.get("BC_ZIG_JUDGE", "")
    if not j:
        return "sandbox"
    r = subprocess.run(["wsl", "-d", os.environ.get("BC_WSL_DISTRO", "Ubuntu"), "--", "test", "-x", j], capture_output=True)
    return "zig" if r.returncode == 0 else "sandbox"


def dir_hash(d):
    h = hashlib.sha1()
    for p in sorted((ROOT / d).glob("*.*pp")):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()[:10]


def fight(bot, tag, seed_idx):
    """Play one seed of the panel with replays into REPLAYS/<tag>/s<seed_idx>/<opp>/ (skipped if already complete)."""
    out = REPLAYS / tag / f"s{seed_idx}"
    jd = judge()
    for opp in PANEL_OPPS:
        od = out / pathlib.Path(opp).name
        want = len(PANEL_MAPS) * 2
        if od.exists() and len(list(od.glob("*.replay"))) >= want:
            continue
        od.mkdir(parents=True, exist_ok=True)
        log = CYC / f"fight_{tag}_s{seed_idx}_{pathlib.Path(opp).name}.txt"
        with open(log, "w", encoding="utf-8") as f:
            subprocess.run([sys.executable, "-u", "tools/tourney.py", bot, opp, "--maps", ",".join(PANEL_MAPS),
                            "--seeds", "1", "--seed-base", str(seed_idx), "-j", "10", "--judge", jd,
                            "--replays", str(od)], cwd=ROOT, stdout=f,
                           stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    return out


KAGGLE_MAX = 3   # later approved candidates sent to Kaggle (stage 1, replays) while the laptop fights the first


def kaggle_offload(todo):
    """Launch Kaggle stage-1 fights for up to KAGGLE_MAX queued approved candidates (not the one fighting locally)."""
    rec_p = CYC / "kaggle.json"
    rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}
    live = [c for c, r in rec.items() if r.get("state") == "launched"]
    for line in todo[1:]:
        cand = line.split("|")[0].strip()
        if (cand in rec and rec[cand].get("state") != "failed") or len(live) >= KAGGLE_MAX:
            continue   # a failed launch (e.g. Kaggle's 5-session limit) is retried on the next pass
        r = subprocess.run([sys.executable, "tools/kaggle_panel.py", "launch", cand, "--seeds", "1", "--seed-base", "0",
                            "--panel", ",".join(PANEL_OPPS), "--maps", ",".join(PANEL_MAPS), "--tag", "cyc", "--replays"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = "successfully pushed" in r.stdout
        rec[cand] = {"state": "launched" if ok else "failed", "kernel": f"kumaryash1134/p-{cand.replace('_', '-')}-cyc",
                     "hash": dir_hash(cand), "at": time.strftime("%H:%M")}
        if ok:
            live.append(cand)
        print(f"[{time.strftime('%H:%M')}] KAGGLE {'launched' if ok else 'launch failed'} {cand}", flush=True)
    rec_p.write_text(json.dumps(rec, indent=1))


def kaggle_collect(cand, ctag):
    """If cand's Kaggle stage-1 run finished (same code hash), unpack its replays into REPLAYS/<ctag>/s0/. True if used."""
    rec_p = CYC / "kaggle.json"
    rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}
    r = rec.get(cand)
    if not r or r.get("state") != "launched" or r.get("hash") != dir_hash(cand):
        return False
    st = subprocess.run([sys.executable, "-m", "kaggle", "kernels", "status", r["kernel"]], capture_output=True, text=True,
                        cwd=ROOT / "ladder" / "cloud_tests").stdout
    if "COMPLETE" not in st:
        return False
    from kaggle_panel import fetch_replays
    ok = fetch_replays(r["kernel"], REPLAYS / ctag / "s0")
    r["state"] = "used" if ok else "no-replays"; rec_p.write_text(json.dumps(rec, indent=1))
    return ok


def promising(s):
    """Stage-1 gate for spending the second seed: paired flips not negative, or the target moved the intended way."""
    if s["flips_for"] >= s["flips_against"]:
        return True
    t = ((s["throws"]["cand"], s["throws"]["base"]) if s.get("target") == "throws" else
         (s["queen_alive"]["cand"], s["queen_alive"]["base"]) if s.get("target") == "queen_alive" else s["median"].get(s.get("target")))
    if not t or t[0] is None or t[1] is None:
        return False
    return (t[0] < t[1]) if s["target"] in DOWN_IS_GOOD else (t[0] > t[1])


def friendly_h2h(path, side):
    """Head-on pairs between two of OUR dragons (the engine logs both deaths of a head-on consecutively in one round)."""
    from replay import _decode, DEATHS
    rep = _decode(str(path)); team = {}; nid = 0
    for l in rep["map"].splitlines():
        q = l.split()
        if q and q[0] == "DRAGON": team[nid] = int(q[1]); nid += 1
    rnd = 0; dead = []
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart": rnd = e["round"]
        elif k == "dragonSplit": team[e["child"]] = e["team"]
        elif k == "dragonDeath" and isinstance(e["reason"], int) and e["reason"] < len(DEATHS) and DEATHS[e["reason"]] == "head to head":
            dead.append((rnd, e["id"]))
    i = f = 0
    while i + 1 < len(dead):
        if dead[i][0] == dead[i + 1][0]:
            f += team.get(dead[i][1]) == side and team.get(dead[i + 1][1]) == side; i += 2
        else:
            i += 1
    return f


def game_metrics(path):
    from queen_report import analyse as queen_analyse
    qa = queen_analyse(path)
    base = _game_metrics(path)
    base.update(our_queen_end=qa["q_end"][0] or 0, their_queen_end=qa["q_end"][1] or 0,
                our_queen_alive=qa["ours"]["death"] is None, their_queen_alive=qa["theirs"]["death"] is None,
                our_queen_death=qa["ours"]["death"] if qa["ours"]["death"] is not None else 500,
                their_queen_death=qa["theirs"]["death"] if qa["theirs"]["death"] is not None else 500,
                decided_by=qa["how"])
    return base


def _game_metrics(path):
    from loss_digest import digest
    from mechanics import analyse
    from feed_count import one as feeds_of
    d = digest(path)
    m = re.search(r"_([AB])_\d+\.replay$", str(path)); side = 0 if m.group(1) == "A" else 1
    c = analyse(str(path), side)["c"]
    s100 = d["snaps"].get(100, (0, 0, 0, 0, 0, 0))
    last = d["snaps"][max(d["snaps"])] if d["snaps"] else (0,) * 6
    f, longest, total, won = feeds_of(path, 350, False)
    dominant = s100[3] > 0 and s100[0] >= 2 * s100[3]   # we led 2:1 in units at r100
    return dict(won=won, kind=d["kind"], units100=s100[0], mass100=s100[1], dominant=dominant, throw=dominant and not won, eat100=c["eat@r0-50"] + c["eat@r50-100"],
                feeds=f, final_longest=last[2], final_mass=last[1], map=d["map"],
                sprint_segs=c["segs"], sprints=c["sprints"], attack_sprints=c["purpose:ATTACK"],
                h2h_ours=c["h2h_deaths"], h2h_theirs=c["their_h2h"],
                friendly_h2h=friendly_h2h(path, side),
                hit_other_body=sum(n for (cause, _ph), n in d["deaths"].items() if cause == "hit other body"))


METRICS_VERSION = 3   # bump when game_metrics changes: stale cache entries are recomputed (v3: queen rules)
METRICS_CACHE = CYC / "metrics_cache.json"   # per-replay metrics keyed by path + mtime: base games are analysed once


def analyse_dir(tag):
    cache = json.loads(METRICS_CACHE.read_text()) if METRICS_CACHE.exists() else {}
    res, dirty = {}, False
    for p in sorted((REPLAYS / tag).rglob("*.replay")):
        key = f"{p.parent.parent.name}/{p.parent.name}/{p.name}"
        ck = f"v{METRICS_VERSION}|{p}|{p.stat().st_mtime_ns}"
        if ck not in cache:
            try:
                cache[ck] = game_metrics(p)
            except Exception as ex:   # noqa: BLE001
                cache[ck] = {"error": str(ex)}
            dirty = True
        res[key] = cache[ck]
    if dirty:
        METRICS_CACHE.write_text(json.dumps(cache))
    return res


def summarise(cand, base):
    keys = sorted(set(cand) & set(base))
    ok = [k for k in keys if "error" not in cand[k] and "error" not in base[k]]
    flips_for = sum(1 for k in ok if cand[k]["won"] and not base[k]["won"])
    flips_against = sum(1 for k in ok if base[k]["won"] and not cand[k]["won"])
    def med(res, f): return st.median(res[k][f] for k in ok if f in res[k]) if ok else None
    metrics = ["units100", "mass100", "eat100", "feeds", "final_longest", "final_mass",
               "sprint_segs", "sprints", "attack_sprints", "h2h_ours", "h2h_theirs", "hit_other_body", "friendly_h2h",
               "our_queen_end", "their_queen_end", "our_queen_death", "their_queen_death"]
    out = dict(games=len(ok), wins_cand=sum(cand[k]["won"] for k in ok), wins_base=sum(base[k]["won"] for k in ok),
               flips_for=flips_for, flips_against=flips_against,
               median={f: (med(cand, f), med(base, f)) for f in metrics})
    permap = {}
    for k in ok:
        mp = cand[k]["map"]; e = permap.setdefault(mp, [0, 0, 0]); e[0] += 1; e[1] += cand[k]["won"]; e[2] += base[k]["won"]
    out["per_map"] = permap
    kinds = {"cand": {}, "base": {}}
    for k in ok:
        for who, r in (("cand", cand), ("base", base)):
            kinds[who][r[k]["kind"]] = kinds[who].get(r[k]["kind"], 0) + 1
    out["kinds"] = kinds
    # throws: we led 2:1 in units at r100 and still lost (the "start strong, maintain, then throw" pattern)
    out["queen_alive"] = {w: sum(1 for k in ok if r[k].get("our_queen_alive")) for w, r in (("cand", cand), ("base", base))}
    out["enemy_queen_alive"] = {w: sum(1 for k in ok if r[k].get("their_queen_alive")) for w, r in (("cand", cand), ("base", base))}
    out["decided_by"] = {w: dict(collections.Counter(r[k].get("decided_by") for k in ok)) for w, r in (("cand", cand), ("base", base))}
    out["throws"] = {w: sum(1 for k in ok if r[k].get("throw")) for w, r in (("cand", cand), ("base", base))}
    out["dominant"] = {w: sum(1 for k in ok if r[k].get("dominant")) for w, r in (("cand", cand), ("base", base))}
    return out


def load_state(p):
    return json.loads(p.read_text()) if p.exists() else {"base": "viper_nn", "stack": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "promote"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--queue", default=str(CYC / "queue.txt")); ap.add_argument("--state", default=str(CYC / "state.json"))
    a = ap.parse_args()
    CYC.mkdir(parents=True, exist_ok=True); REPLAYS.mkdir(parents=True, exist_ok=True)
    state_p = pathlib.Path(a.state); state = load_state(state_p)
    if a.cmd == "promote":
        state["stack"].append({"from": state["base"], "to": a.arg, "at": time.strftime("%Y-%m-%d %H:%M")})
        state["base"] = a.arg; state_p.write_text(json.dumps(state, indent=1))
        with open(CYC / "ledger.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "promote", "base": a.arg, "at": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
        print(f"base is now {a.arg}"); return
    done_p = CYC / "done.txt"; qp = pathlib.Path(a.queue); qp.touch()
    print(f"[{time.strftime('%H:%M')}] cycle running; base {state['base']}", flush=True)
    while True:
        state = load_state(state_p)
        done = set(done_p.read_text(encoding="utf-8").splitlines()) if done_p.exists() else set()
        ap_p = CYC / "approved.txt"   # review gate: only candidates whose diff Claude reviewed (one dir per line)
        approved = set(x.strip() for x in ap_p.read_text(encoding="utf-8").splitlines()) if ap_p.exists() else set()
        todo = [l for l in qp.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#") and l not in done
                and l.split("|")[0].strip() in approved]
        if not todo:
            time.sleep(60); continue
        line = todo[0]
        cand, target, note = [x.strip() for x in (line.split("|") + ["", ""])[:3]]
        base = state["base"]
        btag = f"base_{base}_{dir_hash(base)}"; ctag = f"{cand}_{dir_hash(cand)}"
        print(f"[{time.strftime('%H:%M')}] CYCLE start {cand} (target: {target}) vs base {base}", flush=True)
        try:
            b = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, 'tools'); from tourney import prepare; prepare({cand!r})"],
                               cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if b.returncode != 0:   # review gate part 2: never fight (or report 0 games for) a candidate that doesn't build
                err = [l for l in b.stderr.splitlines() if "error" in l][:3]
                raise RuntimeError("BUILD FAILED: " + " | ".join(err))
            kaggle_offload(todo)
            fight(base, btag, 0)
            if kaggle_collect(cand, ctag):
                print(f"[{time.strftime('%H:%M')}] {cand}: stage 1 from Kaggle replays", flush=True)
            else:
                fight(cand, ctag, 0)
            s = summarise(analyse_dir(ctag), analyse_dir(btag)); s["target"] = target
            stage = 1
            if promising(s):
                fight(base, btag, 1); fight(cand, ctag, 1)
                s = summarise(analyse_dir(ctag), analyse_dir(btag)); s["target"] = target; stage = 2
                # stacked candidates: effects are small and only ~16 of 80 games swing, so spend a third seed
                if (cand.startswith("cand_stack") or cand == "cand_dev") and promising(s):
                    fight(base, btag, 2); fight(cand, ctag, 2)
                    s = summarise(analyse_dir(ctag), analyse_dir(btag)); s["target"] = target; stage = 3
            s.update(cand=cand, base=base, target=target, note=note, stage=stage, judge=judge(),
                     at=time.strftime("%Y-%m-%d %H:%M"))
            (CYC / f"report_{cand}.json").write_text(json.dumps(s, indent=1))
            with open(CYC / "ledger.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"event": "screen", **{k: s[k] for k in ("cand", "base", "target", "games", "wins_cand",
                                                                           "wins_base", "flips_for", "flips_against")}}) + "\n")
            if s["games"] == 0:
                raise RuntimeError("0 paired games (fights produced no replays): check ladder/cycle/fight_*.txt")
            tm = s["median"].get(target)
            if target == "queen_alive":
                tm = (s["queen_alive"]["cand"], s["queen_alive"]["base"])
            if target == "throws":
                tm = (s["throws"]["cand"], s["throws"]["base"])
            print(f"[{time.strftime('%H:%M')}] CYCLE done {cand} (stage {stage}, {s['judge']}): wins {s['wins_cand']} v {s['wins_base']} of {s['games']}, "
                  f"flips +{s['flips_for']}/-{s['flips_against']}, target {target} {tm}", flush=True)
        except Exception as ex:   # noqa: BLE001
            print(f"[{time.strftime('%H:%M')}] CYCLE error {cand}: {ex}", flush=True)
        with open(done_p, "a", encoding="utf-8") as f:
            f.write(line + "\n")


if __name__ == "__main__":
    main()
