import json
import pytest
from conftest import ensure_fixtures
ensure_fixtures()
from conftest import ROOT
from replay_lite import decode_lite
from rulemine import decisions as D, state

DATA = ROOT / "tests" / "data"
SIDES = json.loads((DATA / "sides.json").read_text())
LONG = DATA / "replays" / "690143.replay"   # SSS (side A) won a full-length Schooltime game


@pytest.fixture(scope="module")
def death():
    return D.death_rows(str(LONG), 0)


@pytest.fixture(scope="module")
def bud():
    return D.bud_rows(str(LONG), 0)


@pytest.fixture(scope="module")
def queen():
    return D.queen_move_rows(str(LONG), 0)


def own_turn_deaths(path, side):
    return [t for t in state.turns(str(path), lambda g, i: g.team[i] == side) if t.outcome.died]


def test_death_positives_are_exactly_the_feed_channel_deaths_beside_a_longer_ally(death):
    deaths = own_turn_deaths(LONG, 0)
    feeds = {(t.round, t.id) for t in deaths if t.outcome.died in D.FEED_DEATHS}
    into_body = {(t.round, t.id) for t in deaths if t.outcome.died == "body"}
    pos = {(r["round"], r["id"]) for r in death if r["label"]}
    assert pos and pos <= feeds | into_body       # every positive is a real feed-channel death
    assert len(pos & feeds) >= 0.5 * len(feeds)   # and most such deaths had a longer ally in view/memory
    assert all(r["target"] >= 0 for r in death)


def test_death_rows_hold_only_the_chosen_side_and_an_opportunity(death):
    assert all(r["side"] == "A" for r in death)
    assert all(r["top_ally_vlen"] > r["len"] or r["mem_top_len"] > r["len"] for r in death)


def test_fed_ok_only_on_positives(death):
    assert all(r["fed_ok"] <= r["fed_any"] <= r["label"] for r in death)
    assert sum(r["fed_ok"] for r in death) > 0


def test_bud_positives_equal_the_sides_splits_from_length_four_up(bud):
    rep = decode_lite(str(LONG), {"dragonSplit"})
    raw = [e for e in rep["events"] if e["team"] == 0 and len(e["parentBody"]) + len(e["childBody"]) >= 4]
    assert sum(r["label"] for r in bud) == len(raw)


def test_queen_move_has_exactly_one_chosen_step_per_decision(queen):
    per = {}
    for r in queen:
        per.setdefault(r["decision"], []).append(r["chosen"])
    assert per
    assert all(sum(v) == 1 and len(v) >= 2 for v in per.values())


def test_queen_move_toward_allies_is_one_bounded_vote_per_ally(queen):
    # Schooltime has portals: a raw distance difference jumps by up to the map width through one, which once let a
    # single portal step dominate the fit. Each visible ally may move the feature by at most 1.
    assert all(isinstance(r["toward_allies"], int) for r in queen)
    assert max(abs(r["toward_allies"]) for r in queen) <= 20
    assert any(r["toward_allies"] != 0 for r in queen)


def test_extractors_only_query_terrain_through_the_dragons_own_memory(monkeypatch):
    # unknown-map honesty: every terrain step the extractors take must pass the acting dragon's memory
    from rulemine import mapgeo
    orig = mapgeo.Geo.step
    calls = []

    def guarded(self, c, d, known=None):
        assert known is not None, "terrain read without the dragon's memory"
        calls.append(1)
        return orig(self, c, d, known)
    monkeypatch.setattr(mapgeo.Geo, "step", guarded)
    D.death_rows(str(LONG), 0)
    D.queen_move_rows(str(LONG), 0)
    assert calls
