# Team Bhole Chature — agent handoff

Stable rules, mechanics, process and tools. **Current state, insights and open threads: [HANDOVER.md](HANDOVER.md) (read it first).** Dated evidence: [research_notes/LAB.md](research_notes/LAB.md); old-rules history: [research_notes/HISTORY.md](research_notes/HISTORY.md).

## 00. New rules and current line

- Engine unswbc 1.2.3. Dragon IDs 0 and 1 are the two queens; which team owns ID 0 depends on map DRAGON order. A team's queen is its first dragon in that order. Bot predicate `isTrueQueen()` is `MY_ID <= 1`.
- At round 500 the longer living queen wins; dead queen counts as length 0. Tie-breaks are longest dragon, then total length. Head-ons kill both.
- Each dragon moves `ceil(L/4)` cells free per turn; each extra step costs one segment. `simulate()` and `buildReaches()` model this. FSPRINT generates 2–3 step free moves.
- Enemy queens die early in nearly all our ladder games; top teams' queens survive to r500 in about 5%. A queen that survives wins. QHIDE (open space, at least 4 from enemy heads, not beside portals) yielded 8–9/24 queen survivals vs 4/24 baseline in sandbox.
- Feed into the longest dragon, not the hiding queen. Never feed at 10 or fewer units: on Schooltime vs Adrak, feeding cut 22 units to 6 and lost by elimination.
- MAPFIX: ladder pearl tables differ from `maps/*.map`; old `viewAgrees()` discarded known maps in about half of Devil/Dilemma/QoS/Slithery games. Identify maps by kelp/portals and learn pearl gaps from observations. Check changes on perturbed `maps_ll/` maps.
- Top teams farm rich fountains early and recycle deaths (e.g. Adrak took 3-5x our pearls in r40-150).
- The active line is the hybrid (rules + n4 network): pure rules lost 22/80 vs 45/80 in the sandbox. Latest code: `bots/y96/` (see HANDOVER.md).
- New-rules top-10 queens survive r500 in about 5% of games; most games still end by elimination or longest-dragon tiebreak. Keep recording queen fate and opening economy.

## Test and review process

- Start with a small, single-change candidate copied from the current base (`bots/y96/` -> `cand_x/`). Review every loss and changed decision; mechanism metrics are diagnostic, not proof of wins. Tune rather than discard on one noisy batch.
- Sandbox: `python tools/tourney.py CAND opponents/vb21 --maps MAP[,maps_new/NAME] --seeds 2 -j 10 --replays OUT` (one opponent per call; Zig judge by default). Use both sides; include `maps_ll/` perturbed pearl tables for map recognition and relevant live maps for mechanics.
- Ladder-like local maps: `maps_ll/`. Inspect paths/CLI with `--help`; map list may contain map files, not just built-in names.
- Ladder: `tools/top_scrims.py --interleave` for candidate and same-time champion on the same teams/maps. Do not infer a paired win from one score: games diverge early; report per-game losses, queen survival, units/mass, opening pearl intake, and per-map outcomes.
- `python tools/our_games.py --help` downloads our autoscrim games; check active submission and current autoscrim state before any ladder action. Never use obsolete even-hour guards blindly.
- Preserve replays and reports locally for analysis. Do not commit secrets, replays, ladder output, `ml/data*`, `ml/models/`, or files over 5 MB. Set `XDG_CACHE_HOME=D:/battlecode/cache` before builds.

## Game knowledge and pitfalls

- 500 rounds; toroidal board. Dragons act in ascending ID; split child gets next ID and acts later that round. Enemy heads do not move during our turn. Vision is 7×7 and does not cross portals; sonar rays pass portals and stop at first body.
- Pearls respawn on per-tile countdowns; mirrored tiles share a timer. Illegal actions kill the dragon and drop pearls. Every second body segment of a death becomes a pearl.
- Team queen survival has absolute endgame value. A hiding queen and the mass-growing longest are different roles; don't send the queen to a rich region or feed into her by default.
- Free sprint turns make 1-step-only option generation incomplete for L≥5. Multi-step collision checks include the tail before it advances. Keep search within CPU guards; sandbox budget is 100M points/turn, normal peak target below ~65M.
- Map-name gating is brittle. Pearl tables vary on ladder; use MAPFIX and verify on `maps_ll/`. Map symmetry/start ownership can vary by map.
- More pearl intake, feeds, wreck share, or network accuracy can move without improving wins. Check both sides and all affected map types; inspect every loss.

## Tool index

| Tool | Use |
|---|---|
| `tools/tourney.py` | paired local sandbox games, both sides, replay output |
| `tools/top_scrims.py --interleave` | same-time ladder A/B |
| `tools/our_games.py` | collect our ladder/autoscrim replays |
| `tools/queen_report.py` | queen survival and fate |
| `tools/friendly_h2h.py` | friendly head-on pairs and portal cases |
| `tools/newrules_scout.py` | new-rules top-team meta |
| `tools/slope_collect.py --since` | collect recent top-team replays |
| `tools/pair_diff.py`, `tools/pair_frames.py` | paired changes and divergence frames |
| `tools/viz.py` | frames, timelines, eatmap |
| `tools/replay_cache.py`, `tools/mech_board.py` | cached parsing and paired mechanic metrics |
| `tools/cycle.py` | candidate sandbox/analyse/screen/ladder cycle |

Keep this file current and short. Update the lab log by appending only; put durable historical context in HISTORY.md.
