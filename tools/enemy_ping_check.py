"""Measure received enemy queen sonar warnings; no replay caches are written."""
import argparse
import collections
import json
import random
import sys
from pathlib import Path
sys.dont_write_bytecode = True
from replay_lite import decode_lite

KINDS = {"roundStart", "dragonUpdate", "dragonDeath", "dragonSplit", "sonarPing"}

def read_game(path, meta):
    rep = decode_lite(str(path), KINDS)
    starts = [line.split() for line in rep["map"].splitlines() if line.startswith("DRAGON ")]
    teams = {i: int(parts[1]) for i, parts in enumerate(starts)}
    me = int(meta["me"])
    qid = next(i for i in (0, 1) if teams.get(i) == me)
    records, enemy, friend, payload = {}, collections.Counter(), collections.Counter(), collections.Counter()
    rnd, alive, death = -1, True, None
    unknown = 0
    for event in rep["events"]:
        kind = event["kind"]
        if kind == "roundStart":
            rnd = event["round"]
        elif kind == "dragonSplit":
            teams[event["child"]] = event["team"]
        elif kind == "dragonUpdate" and event["id"] == qid and alive and rnd >= 0:
            records[rnd] = event  # last queen record only
        elif kind == "dragonDeath" and event["id"] == qid:
            alive = False
            death = (rnd, event["reason"])
        elif kind == "sonarPing":
            sender = event["sender"]
            if sender not in teams:
                unknown += 1
                continue
            if teams[sender] != me:
                payload[event["value"]] += 1
            if alive and event["hit"] == qid and rnd >= 0:
                if teams[sender] != me:
                    enemy[rnd] += 1
                elif sender != qid:
                    friend[rnd] += 1
    expected = meta.get("our_queen_death")
    if expected and (death is None or int(expected[0]) != death[0]):
        raise ValueError(f"queen death mismatch: metadata={expected}, replay={death}")
    headon = bool(expected and expected[1] in ("headon", 3))
    if expected and headon != (death[1] == 3):
        raise ValueError(f"head-on cause mismatch: {expected}, {death}")
    return dict(rounds=sorted(records), enemy=enemy, friend=friend,
                death=int(expected[0]) if headon else None, payload=payload, unknown=unknown)

def percentile(values, p):
    values = sorted(values)
    pos = (len(values)-1)*p
    lo = int(pos)
    hi = values[min(lo+1, len(values)-1)]
    if hi == values[lo] or pos == lo:
        return values[lo]
    return values[lo] + (hi-values[lo])*(pos-lo)

def report(games, failures):
    lines = []
    def say(s=""): lines.append(s)
    say(f"Games analyzed: {len(games)}; failures: {len(failures)}")
    say("Unit: last alive queen dragonUpdate per round; pings counted over its entire round.")
    say("Prediction excludes current-round deaths: 1 <= death-round <= 5.")
    say("Last 2 rounds means current round and preceding round; missing rounds have zero pings.")
    say("Payload distributions include ALL enemy sonar events, not only rays hitting queen.")
    say(f"Unknown sender events: {sum(g['unknown'] for g in games)}")
    for label, pred in [("overall", lambda r: True), ("<100", lambda r: r<100),
                        ("100-299", lambda r: 100<=r<300), (">=300", lambda r: r>=300)]:
        for channel in ("enemy", "friend"):
            counts = [g[channel][r] for g in games for r in g["rounds"] if pred(r)]
            n, hits = len(counts), sum(c>0 for c in counts)
            say(f"{label} {channel}: {hits}/{n} = {hits/n if n else 0:.4%}; mean count={sum(counts)/n if n else 0:.6f}")
    for window in (1, 2):
        bins = {False: [0,0], True: [0,0]}
        for g in games:
            for r in g["rounds"]:
                alarm = any(g["enemy"][r-i] for i in range(window))
                bins[alarm][1] += 1
                bins[alarm][0] += int(g["death"] is not None and 1<=g["death"]-r<=5)
        for alarm, (hits,n) in bins.items():
            say(f"Head-on within next 5, {'this round' if window==1 else 'any in last 2'}, alarm={alarm}: {hits}/{n} = {hits/n if n else 0:.4%}")
    dead = [g for g in games if g["death"] is not None]
    eligible = []
    covered = 0
    for g in dead:
        rounds = g["rounds"]
        alarm = [bool(g["enemy"][r]) for r in rounds]
        before = [i for i,r in enumerate(rounds) if 1<=g["death"]-r<=5]
        observed = any(alarm[i] for i in before)
        covered += observed
        # Both directions must be >=20 actual rounds, including across wrap.
        span = rounds[-1]-rounds[0]+1 if rounds else 0
        shifts = [s for s in range(1,len(rounds)) if
                  all(20<=((rounds[(i+s)%len(rounds)]-r)%span)<=span-20
                      for i,r in enumerate(rounds))]
        if shifts:
            eligible.append((alarm, before, shifts, observed))
    rng = random.Random(20261004)
    null = []
    for _ in range(200):
        count = 0
        for alarm,before,shifts,_ in eligible:
            shift = rng.choice(shifts)
            count += any(alarm[(i+shift)%len(alarm)] for i in before)
        null.append(count)
    obs = sum(x[3] for x in eligible)
    mean = sum(null)/200
    say(f"Death coverage: {covered}/{len(dead)} head-on deaths warned in preceding 5 rounds.")
    say(f"Circular null: {len(eligible)} eligible deaths; excluded {len(dead)-len(eligible)} (no valid >=20-round shift).")
    say(f"Matched observed={obs}; null mean={mean:.3f}; empirical 95% null count interval=[{percentile(null,.025):.3f}, {percentile(null,.975):.3f}]")
    if mean:
        lifts = [obs/n if n else float("inf") for n in null]
        say(f"Lift={obs/mean:.3f}; empirical 95% lift interval=[{percentile(lifts,.025):.3f}, {percentile(lifts,.975):.3f}]")
    else:
        say("Lift undefined: null mean is zero.")
    say("Interval describes shuffle variability, not sampling uncertainty; circular shifts preserve each game's alarm rate.")
    team_games = collections.Counter(g["opp"] for g in games)
    for team,n in team_games.most_common(5):
        values = collections.Counter()
        for g in games:
            if g["opp"] == team: values.update(g["payload"])
        high = collections.Counter()
        for value,count in values.items(): high[value>>48] += count
        say(f"Opponent {team!r}: games={n}; enemy pings={sum(values.values())}")
        say(f"  high bits value>>48 (value,count): {high.most_common()}")
        say(f"  top 10 raw (decimal,hex,count): {[(v,hex(v),c) for v,c in values.most_common(10)]}")
    for failure in failures: say("FAILURE: "+failure)
    return "\n".join(lines)+"\n"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="+", type=Path)
    parser.add_argument("--max-games", type=int)
    parser.add_argument("--output", type=Path, default=Path("out/enemy_ping_check.txt"))
    args = parser.parse_args()
    games, failures, seen = [], [], set()
    attempted = 0
    for root in args.directories:
        metadata = root/"games.json"
        if not metadata.exists():
            failures.append(f"{metadata}: missing")
            continue
        for meta in json.loads(metadata.read_text(encoding="utf-8")):
            gid = meta["game"]
            if gid in seen: continue
            if args.max_games is not None and attempted>=args.max_games: break
            seen.add(gid)
            attempted += 1
            try:
                g = read_game(root/f"{gid}.replay", meta)
                g["opp"] = meta["opp"]
                games.append(g)
            except Exception as exc:
                failures.append(f"{root}/{gid}: {type(exc).__name__}: {exc}")
    result = report(games, failures)
    print(result, end="")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
