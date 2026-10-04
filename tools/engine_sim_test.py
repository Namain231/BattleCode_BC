"""Replay oracle: no pickle cache or rulemine; compares every intermediate update.
Run: python tools/engine_sim_test.py out/sim_oracle --json out/sim_oracle/parity.json
Only round-start spawn and countdown resets are supplied to the simulator.
Expected bodies insert each recorded head, trimming at the recorded tail.
No resynchronisation after mismatch. Ordered events verify all death causes.
"""
import argparse
import json
from pathlib import Path
from time import perf_counter
from engine_sim import Dragon, SpawnInput, load_map, step
from replay_lite import decode_lite

OUTPUTS = {"dragonUpdate", "dragonSplit", "dragonDeath", "tileChange"}
KINDS = OUTPUTS | {"roundStart", "turnStart", "dragonAction", "pearlCountdown"}


def canonical(state):
    return {"dragons": {i: (d.team, tuple(d.body), d.facing, len(d.body))
                        for i, d in state.dragons.items() if d.alive},
            "deaths": {i: d.death for i, d in state.dragons.items() if not d.alive},
            "pearls": state.pearls, "countdowns": state.countdowns}


def replay_update(expected, event, initial=False):
    """Reconstruct from geometry without simulating recorded actions."""
    kind = event["kind"]
    if kind == "tileChange":
        if event["pearl"]:
            expected.pearls.add(event["tile"])
        else:
            expected.pearls.discard(event["tile"])
    elif kind == "pearlCountdown":
        expected.countdowns[event["tile"]] = event["countdown"]
    elif kind == "dragonDeath":
        d = expected.dragons[event["id"]]
        d.alive, d.death = False, event["reason"]
    elif kind == "dragonSplit":
        expected.dragons[event["parent"]].body = event["parentBody"].copy()
        body = event["childBody"].copy()
        child = Dragon(event["child"], event["team"], body,
                       expected.board.facing(body[1], body[0]))
        expected.dragons[child.id] = child
        expected.next_id = max(expected.next_id, child.id + 1)
    elif kind == "dragonUpdate":
        d = expected.dragons[event["id"]]
        if initial:
            assert d.body[0] == event["head"] and d.body[-1] == event["tail"]
        else:
            d.body.insert(0, event["head"])
            del d.body[d.body.index(event["tail"]) + 1:]
        d.facing = event["facing"]


def first_difference(actual, expected):
    a, b = canonical(actual), canonical(expected)
    for key in a:
        if a[key] != b[key]:
            if isinstance(a[key], dict):
                for entity in sorted(a[key].keys() | b[key].keys()):
                    if a[key].get(entity) != b[key].get(entity):
                        return f"{key}[{entity}]: actual={a[key].get(entity)} expected={b[key].get(entity)}"
            return f"{key}: actual={a[key]} expected={b[key]}"
    return None


def check_game(path):
    rep = decode_lite(path, KINDS)
    actual = load_map(rep["map"])
    expected = actual.copy()
    rounds, initial = [], []
    for event in rep["events"]:
        if event["kind"] == "roundStart":
            rounds.append((event["round"], []))
        elif rounds:
            rounds[-1][1].append(event)
        else:
            initial.append(event)
    for event in initial:
        replay_update(expected, event, initial=True)
    actual = expected.copy()
    matching, seconds, turns, first = 0, 0.0, 0, None
    for round_number, events in rounds:
        prefix = next((i for i, e in enumerate(events) if e["kind"] == "turnStart"), len(events))
        spawn_events, turn_events = events[:prefix], events[prefix:]
        spawn = SpawnInput({e["tile"] for e in spawn_events if e["kind"] == "tileChange" and e["pearl"]},
                           {e["tile"]: e["countdown"] for e in spawn_events if e["kind"] == "pearlCountdown"})
        actions = {e["id"]: e for e in turn_events if e["kind"] == "dragonAction"}
        expected_turns = [e["id"] for e in turn_events if e["kind"] == "turnStart"]
        turns += len(expected_turns)
        observed_turns = []

        def policy(s, i):
            observed_turns.append(i)
            return actions.get(i)

        started = perf_counter()
        actual = step(actual, policy, spawn)
        seconds += perf_counter() - started
        for p, cd in list(expected.countdowns.items()):
            if cd >= 0:
                expected.countdowns[p] = cd - 1
        for event in events:
            replay_update(expected, event)
        expected_outputs = [e for e in turn_events if e["kind"] in OUTPUTS]
        divergence = None
        if actual.round != round_number:
            divergence = "round numbering"
        elif observed_turns != expected_turns:
            divergence = f"turn order: {observed_turns} != {expected_turns}"
        elif actual.events != expected_outputs:
            for i in range(max(len(actual.events), len(expected_outputs))):
                a = actual.events[i] if i < len(actual.events) else None
                b = expected_outputs[i] if i < len(expected_outputs) else None
                if a != b:
                    divergence = f"rule event {i}: actual={a} expected={b}"
                    break
        divergence = divergence or first_difference(actual, expected)
        if divergence is None:
            matching += 1
        elif first is None:
            first = {"round": round_number, "rule": divergence}
        if actual.over and round_number != rounds[-1][0]:
            first = first or {"round": round_number, "rule": "premature terminal state"}
            break
    result = rep.get("result", {})
    if first is None and (actual.winner != result.get("winner") or not actual.over):
        first = {"round": actual.round, "rule": f"terminal winner: {actual.winner} != {result.get('winner')}"}
        matching -= 1

    for team, label in enumerate(("A", "B")):
        living = [len(d.body) for d in actual.dragons.values() if d.alive and d.team == team]
        stats = {"count": len(living), "longest": max(living, default=0), "total": sum(living)}
        if first is None and stats != result.get(label):
            first = {"round": actual.round, "rule": f"terminal standings {label}: {stats} != {result.get(label)}"}
            matching -= 1
    return {"game": str(path), "rounds": len(rounds), "matching": matching,
            "match_rate": matching / len(rounds) if rounds else 0,
            "turns": turns, "seconds": seconds,
            "us_per_round": seconds * 1e6 / len(rounds) if rounds else None,
            "us_per_dragon_turn": seconds * 1e6 / turns if turns else None,
            "first_divergence": first}


def scenarios():
    """Rare-rule assertions with independently specified outcomes."""
    text = "MAP 12 12\nDRAGON 0 4 3 3 2 3 1 3 0 3\nDRAGON 1 4 8 8 9 8 10 8 11 8\n"
    base = load_map(text)
    branch = step(base, {0: {"act": "move", "dirs": "EEE"}, 1: {"act": "move", "dirs": "W"}})
    assert len(branch.dragons[0].body) == 2 and branch.dragons[0].body[0] == (6, 3)
    assert base.round == -1 and base.dragons[0].body[0] == (3, 3)
    dead = step(base, {0: {"act": "move", "dirs": "EEEE"}, 1: {"act": "move", "dirs": "W"}})
    assert dead.dragons[0].death == 4 and dead.dragons[0].body == [(6, 3), (5, 3)]
    assert (6, 3) in dead.pearls
    tail = load_map("MAP 12 12\nDRAGON 0 4 3 3 3 4 2 4 2 3\nDRAGON 1 2 8 8 9 8\n")
    tail = step(tail, {0: {"act": "move", "dirs": "W"}, 1: {"act": "move", "dirs": "W"}})
    assert tail.dragons[0].death == 1
    head = load_map("MAP 12 12\nDRAGON 0 2 3 3 2 3\nDRAGON 1 2 4 3 5 3\n")
    head = step(head, {0: {"act": "move", "dirs": "E"}})
    assert [(e["id"], e["reason"]) for e in head.events if e["kind"] == "dragonDeath"] == [(1, 3), (0, 3)]
    split = step(base, {0: {"act": "split", "size": 2}, 1: {"act": "move", "dirs": "W"},
                        2: {"act": "move", "dirs": "W"}})
    assert split.dragons[2].body == [(11, 3), (0, 3)]
    invalid = step(base, {0: {"act": "split", "size": 1}})
    assert invalid.dragons[0].death == invalid.dragons[1].death == 4
    growth = base.copy()
    growth.pearls.add((4, 3))
    growth = step(growth, {0: {"act": "move", "dirs": "EE"}, 1: {"act": "move", "dirs": "W"}})
    assert len(growth.dragons[0].body) == 4
    queen = base.copy()
    queen.round = 498
    queen.dragons[2] = Dragon(2, 0, [(x, 5) for x in range(8)], 1)
    queen.next_id = 3
    queen = step(queen, {0: {"act": "move", "dirs": "E"}, 1: {"act": "move", "dirs": "W"},
                        2: {"act": "move", "dirs": "N"}})
    assert queen.over and queen.winner == 0

    # A longer enemy queen outranks our longer non-queen.
    queen = base.copy()
    queen.round = 498
    queen.dragons[1].body.append((0, 8))
    queen.dragons[2] = Dragon(2, 0, [(x, 5) for x in range(8)], 1)
    queen.next_id = 3
    queen = step(queen, {0: {"act": "move", "dirs": "E"}, 1: {"act": "move", "dirs": "W"},
                        2: {"act": "move", "dirs": "N"}})
    assert queen.over and queen.winner == 1
    # Length five receives two free steps; pearl growth cannot enlarge allowance.
    free = load_map("MAP 12 12\nDRAGON 0 5 4 3 3 3 2 3 1 3 0 3\nDRAGON 1 2 8 8 9 8\n")
    free = step(free, {0: {"act": "move", "dirs": "EE"}, 1: {"act": "move", "dirs": "W"}})
    assert len(free.dragons[0].body) == 5
    cap = load_map(text + "UNIT_LIMIT 1\n")
    cap = step(cap, {0: {"act": "split", "size": 2}, 1: {"act": "move", "dirs": "W"}})
    assert cap.dragons[0].death == 4
    # West edge of (4,3) is kelp: east from (3,3) collides with it.
    wall = load_map(text + "EDGE 95 1 -1\n")
    wall = step(wall, {0: {"act": "move", "dirs": "E"}, 1: {"act": "move", "dirs": "W"}})
    assert wall.dragons[0].death == 0
    # Paired vertical portals: entering left side preserves east direction.
    portal = load_map(text + "EDGE 95 2 7\nEDGE 151 2 7\n")
    portal = step(portal, {0: {"act": "move", "dirs": "EE"}, 1: {"act": "move", "dirs": "W"}})
    assert portal.dragons[0].body == [(9, 5), (8, 5), (3, 3)]
    # Collision with a non-head segment kills only the moving dragon.
    body = load_map("MAP 12 12\nDRAGON 0 2 3 3 2 3\nDRAGON 1 3 4 2 4 3 4 4\n")
    body = step(body, {0: {"act": "move", "dirs": "E"}, 1: {"act": "move", "dirs": "N"}})
    assert body.dragons[0].death == 2 and body.dragons[1].alive
    # Fixed-rate symmetric bed: blocked attempt still resets, mirror can spawn.
    beds = load_map(text + "SYMMETRY xy\nTILE 3 3 1 1\nTILE 8 8 1 1\n")
    beds = step(beds, {0: {"act": "move", "dirs": "E"}, 1: {"act": "move", "dirs": "W"}})
    assert beds.countdowns[3, 3] == beds.countdowns[8, 8] == 1 and not beds.pearls
    # Seeded branching must reproduce random respawns with independent RNG state.
    beds = load_map(text + "TILE 6 6 1 3\n", seed=9)
    a = step(beds, {0: {"act": "move", "dirs": "E"}, 1: {"act": "move", "dirs": "W"}})
    b = step(beds, {0: {"act": "move", "dirs": "E"}, 1: {"act": "move", "dirs": "W"}})
    assert canonical(a) == canonical(b) and a.rng.words == b.rng.words


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    scenarios()
    paths = []
    for value in args.paths:
        p = Path(value)
        paths.extend(sorted(p.glob("*.replay")) if p.is_dir() else [p])
    reports = [check_game(path) for path in paths]
    for report in reports:
        print(json.dumps(report))
    total = sum(r["rounds"] for r in reports)
    matched = sum(r["matching"] for r in reports)
    summary = {"rounds": total, "matching": matched, "match_rate": matched / total if total else None,
               "games": reports, "scenario_tests": "passed"}
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Total: {matched}/{total} exact rounds; scenarios passed")
    return 0 if not reports or matched >= .99 * total else 1


if __name__ == "__main__":
    raise SystemExit(main())
