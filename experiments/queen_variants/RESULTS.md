# Queen-variant experiments on Y.7.12.49 (2026-10-01)

Base: `baselines/y7_12_49` (sub 14198). Harness: `tools/queen_panel.py` (zig judge in WSL) plus `research_new_meta/analyze.py`
for tiebreak attribution. Maps: the 7 open live maps (default, trophy, queen_of_spades, devil, trauma, portals,
schooltime), both sides. Port scripts rebuild a variant from the base: `port_leash.py NAME LEASH GREED NOSPLIT`,
`port_feed.py NAME SINK FEEDFROM ENDFEED GOSSIP` (they write `viper_s2_NAME/`).

| Variant | What it adds to .49 | vs gP (28) | vs .49 | Verdict |
|---|---|---|---|---|
| E1 | queen leash to her start (radius 5) + 0.2x pearl greed after round 30 | 19 | 10/28 | worse: slower economy |
| R1 | E1 + paid-reach threat (sacrificing strikers) | 20 | 8/28 | worse |
| F1 | feed the true queen (sink) from r300, old timings | n/a | 44/84 (52%) | neutral |
| F2 | F1 with feeding from r200/250 | n/a | 13/28 | worse: economy collapses by r400 |

Lessons:
- Queen survival vs gP was misleading (gP is pre-rules and does not hunt queens). Versus .49 the leash gave no extra
  survival (queens alive at r500 about 8/28 for both sides) and cost wins. Judge by wins against a post-rules bot.
- The queen rule decided 5-6 of 18 round-500 games *against* E1/R1 and 4 for / 3 against F1.
- "no valid action" deaths with action split are deliberate feeding (`SPLIT 1`), not a bug.
- Head-on is still the main queen killer (about 2/3 of deaths). Next idea: a 2-3 round lookahead for the queen only.
