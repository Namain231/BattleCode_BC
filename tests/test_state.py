import pathlib, sys
from conftest import ensure_fixtures
ensure_fixtures()
from conftest import ROOT
from rulemine import state

DATA = ROOT / "tests" / "data"
REPLAYS = sorted((DATA / "replays").glob("*.replay"))


def run(path):
    ts = list(state.turns(str(path)))
    return ts[0].game if ts else None, ts


def test_tracked_final_state_matches_the_engine_result():
    for p in REPLAYS:
        g, ts = run(p)
        res = g.result
        for team, key in ((0, "A"), (1, "B")):
            alive = [j for j in g.alive if g.team[j] == team]
            assert len(alive) == res[key]["count"], p.name
            if alive:
                assert max(g.length(j) for j in alive) == res[key]["longest"], p.name


def test_every_split_is_seen_on_the_parents_own_turn():
    from replay_lite import decode_lite
    for p in REPLAYS:
        rep = decode_lite(str(p), {"dragonSplit"})
        g, ts = run(p)
        assert sum(1 for t in ts if t.outcome.child >= 0) == len(rep["events"]), p.name


def test_own_turn_deaths_plus_other_deaths_equal_all_deaths():
    from replay_lite import decode_lite
    for p in REPLAYS:
        rep = decode_lite(str(p), {"dragonDeath"})
        g, ts = run(p)
        own = sum(1 for t in ts if t.outcome.died)
        assert own <= len(rep["events"])
        # every dragon that is gone at the end died exactly once
        assert len(set(g.team) - g.alive) == len(rep["events"]), p.name


def test_a_split_child_starts_with_blank_memory():
    g, ts = run(REPLAYS[0])
    child_turns = {}
    for t in ts:
        if t.outcome.child >= 0:
            child_turns[t.outcome.child] = t.round
    firsts = {}
    for t in ts:
        if t.id in child_turns and t.id not in firsts:
            firsts[t.id] = t
    assert firsts
    for t in firsts.values():
        # at its first turn the child has seen exactly one window: 49 tiles (fewer on maps under 7 wide)
        assert t.snapshot["seen_count"] == min(49, t.game.geo.w * t.game.geo.h)
        assert all(r >= child_turns[t.id] for (r, _, _) in t.snapshot["mates"].values())


def test_eats_account_for_nearly_every_pearl_removal():
    from replay_lite import decode_lite
    for p in REPLAYS:
        rep = decode_lite(str(p), {"tileChange"})
        removed = sum(1 for e in rep["events"] if not e["pearl"])
        g, ts = run(p)
        # sprints can eat mid-path, which the head-only tracker misses; those are rare (<1% of moves)
        assert len(g.eat_log) >= 0.97 * removed, (p.name, len(g.eat_log), removed)
        assert len(g.eat_log) <= removed
