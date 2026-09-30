"""Report deliberate feed deaths and subsequent target growth in recent losses.

Usage: python tools/feed_report.py [--count 40] [--out ladder/feed_report.txt]
"""
import argparse
import builtins
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from replay import load  # noqa: E402


def load_without_cache(path):
    """Use replay.load while preventing it from writing sidecar .pkl files."""
    real_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        if str(file).endswith(".replay.pkl"):
            raise OSError("sidecar cache disabled")
        return real_open(file, *args, **kwargs)

    builtins.open = guarded_open
    try:
        return load(path)
    finally:
        builtins.open = real_open


def analyse(path):
    rep = load_without_cache(path)
    ours = 0 if rep.get("botA") else 1 if rep.get("botB") else None
    lines = rep.get("map", "").splitlines()
    map_name = next((line.split(" ", 1)[1] for line in lines if line.startswith("MAP_NAME ")), lines[0] if lines else "?")
    teams, bodies = {}, {}
    next_id = 0
    for line in lines:
        p = line.split()
        if p and p[0] == "DRAGON":
            team, n = int(p[1]), int(p[2])
            coords = [int(v) for v in p[3:3 + 2 * n]]
            teams[next_id] = team
            bodies[next_id] = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
            next_id += 1

    alive = set(teams)
    round_no = 0
    indicators = {}
    length_at_400 = None
    our_feed_deaths = []
    feed_events = []
    longest_400_id = None
    growth_samples = []
    growth_results = []

    def longest(team):
        candidates = [(len(bodies[i]), i) for i in alive if teams.get(i) == team]
        return max(candidates, default=(0, None))

    for event in rep.get("events", []):
        kind = event["kind"]
        if kind == "roundStart":
            round_no = event["round"]
            for target, fed_round, baseline in growth_samples[:]:
                if round_no >= fed_round + 15:
                    growth_results.append((target, fed_round, max(0, len(bodies.get(target, [])) - baseline)))
                    growth_samples.remove((target, fed_round, baseline))
            if round_no == 400 and ours is not None:
                length_at_400, longest_400_id = longest(ours)
        elif kind == "dragonIndicator":
            indicators[event["id"]] = event.get("text", "")
        elif kind == "dragonUpdate":
            i = event["id"]
            body = bodies.get(i)
            if body is None or event.get("head") is None:
                continue
            if body[0] != event["head"]:
                body.insert(0, event["head"])
            while len(body) > 1 and body[-1] != event.get("tail"):
                body.pop()
        elif kind == "dragonSplit":
            teams[event["child"]] = event["team"]
            bodies[event["child"]] = event["childBody"]
            bodies[event["parent"]] = event["parentBody"]
            alive.add(event["child"])
        elif kind == "dragonDeath":
            i = event["id"]
            ln = len(bodies.get(i, []))
            indicator = indicators.get(i, "")
            target = None
            if ours is not None and teams.get(i) == ours and 300 <= round_no <= 500:
                import re
                match = re.search(r"\bFEED\s+(\d+)\b", indicator)
                if match:
                    target = int(match.group(1))
                    feed_events.append({"round": round_no, "feeder": i, "length": ln,
                                        "mass": (ln + 1) // 2, "target": target})
                    our_feed_deaths.append(i)
                    growth_samples.append((target, round_no, len(bodies.get(target, []))))
            alive.discard(i)

    if ours is None:
        our_feed_deaths = []
        feed_events = []
    target_ids = {f["target"] for f in feed_events}
    growths = [(target, fed_round, growth) for target, fed_round, growth in growth_results]
    chains = {f["feeder"] for f in feed_events} & target_ids
    res = rep.get("result", {})
    return {"path": path, "map": map_name, "ours": ours, "result": res,
            "feeds": feed_events, "targets": len(target_ids), "growths": growths,
            "chains": chains,
            "longest400": length_at_400, "longest400id": longest_400_id,
            "our_end": longest(ours)[0] if ours is not None else 0,
            "their_end": longest(1 - ours)[0] if ours is not None else 0,
            "our_deaths": our_feed_deaths}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--out", default="ladder/feed_report.txt")
    args = ap.parse_args()
    root = os.path.join(os.path.dirname(HERE), "ladder", "losses")
    paths = []
    for directory, _, files in os.walk(root):
        for name in files:
            if name.endswith(".replay"):
                path = os.path.join(directory, name)
                paths.append((os.path.getmtime(path), path))
    selected = [p for _, p in sorted(paths, reverse=True)[:args.count]]
    reports = [analyse(path) for path in selected]
    lines = []
    for r in reports:
        winner = r["result"].get("winner")
        verdict = "unknown" if winner is None or r["ours"] is None else ("us" if winner == r["ours"] else "them")
        lines.append(f"{r['path']} | {r['map']} | result={verdict} winner={winner}")
        lines.append(f"  feeds={len(r['feeds'])} fed_length={sum(f['length'] for f in r['feeds'])} fed_mass={sum(f['mass'] for f in r['feeds'])} distinct_targets={r['targets']}")
        lines.append(f"  feed events: " + (", ".join(f"r{f['round']} #{f['feeder']} len{f['length']} -> #{f['target']}" for f in r["feeds"]) or "none"))
        lines.append("  target growth (+15 rounds): " + (", ".join(f"#{i} fed r{rnd}: +{gain}" for i, rnd, gain in r["growths"]) or "not observed"))
        lines.append(f"  longest ours r400={r['longest400']} (#{r['longest400id']}) end={r['our_end']}; theirs end={r['their_end']}")
    total_feeds = sum(len(r["feeds"]) for r in reports)
    total_mass = sum(f["mass"] for r in reports for f in r["feeds"])
    chain_feeds = sum(len(r["chains"]) for r in reports)
    growth_mass = sum(gain for r in reports for _, _, gain in r["growths"])
    r400_feed = sum(1 for r in reports if r["longest400id"] in r["our_deaths"] and r["longest400id"] is not None)
    r400_count = sum(1 for r in reports if r["longest400id"] is not None)
    lines.append("\nAGGREGATE")
    lines.append(f"replays={len(reports)} mean_distinct_targets={sum(r['targets'] for r in reports) / max(1, len(reports)):.3f}")
    lines.append(f"fed_mass={total_mass} observed_target_growth={growth_mass} ({100*growth_mass/max(1,total_mass):.1f}% of fed mass)")
    lines.append(f"chain feeds={chain_feeds}/{total_feeds} ({100*chain_feeds/max(1,total_feeds):.1f}% of feed deaths)")
    lines.append(f"longest-at-r400 later died by feeding={r400_feed}/{r400_count} ({100*r400_feed/max(1,r400_count):.1f}%)")
    output = "\n".join(lines) + "\n"
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(output)
    print("\n".join(lines[-5:]))


if __name__ == "__main__":
    main()
