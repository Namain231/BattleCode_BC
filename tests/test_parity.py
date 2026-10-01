"""Seam 2: the bot's C++ features (logged by a Params::rmLog=1 build of viper_s2_rules) equal the extractor's.

The fixture replay was produced by: viper_s2_rules with rmLog=1 as side A vs v7.12, Portals, seed 3,
zig judge --debug 1. Regenerate it whenever rm_hooks.hpp or features.py changes (see README_RULEMINE.md).
"""
from conftest import ROOT
from rulemine import parity

FIXTURE = ROOT / "tests" / "data" / "parity_portals_A.replay"


def test_every_feature_matches_the_bot_exactly():
    stats, examples, n = parity.compare(str(FIXTURE), 0)
    assert n > 1000
    bad = {k: v for k, v in stats.items() if v[0] != v[1]}
    assert not bad, (bad, examples)
