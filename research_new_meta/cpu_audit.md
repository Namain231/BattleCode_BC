# vB19 CPU audit - 2026-10-02

Analysis only. No bot edits, new games, generated replays, or pickle caches.

The measured peak is **76,876,136 points**, leaving **23,123,864** below the 100M kill limit. It is on Schooltime, where the normal policy network is disabled. The difference from the reported roughly 59M self-play peak cannot be attributed to adding an 18M network call. The strongest structural suspects are repeated full-board option evaluation and enemy reach construction with linear membership checks. These are hypotheses, not a measured function breakdown.

## Evidence and the missing top-turn identities

Sources: `out/yard_vB19.log`, its 20 retained replays, `tools/panel_zig.py`, `tools/replay_lite.py:58`, `docs/timeouts.md`, and frozen `baselines/vB19/main.cpp`. The panel judge prints winner, round, end reason, team counts/totals/deaths/errors, then A turns and A p50/mean/max points, B turns and B p50/mean/max points, and wall time. Select the CPU column by the candidate's side in the filename, not by winner or by taking the larger team maximum.

**Exact worst dragon/round/length/unit count cannot be recovered from these artifacts.** The panel log retains aggregate CPU statistics only. The replay decoder expects instruction statistics at dragonAction pointer 1. A raw Cap'n Proto check of all 29,247 Schooltime A actions and all 33,862 Schooltime B actions found that pointer null in every action, rather than a populated statistics struct containing zero points. Decoding all 20 games likewise returned no nonzero action points. Do not interpret absent statistics as cheap turns or sort them to claim a round-0 maximum. The fresh insights banner also warns that replays strip CPU points.

The following is therefore a table of the **games containing the top turns**, not an invented turn-level ranking. All rows use seed 1 and candidate side shown. Dragon/round/length/units are unavailable for the peak itself.

| Rank | Map / side | vB19 max points | Median / mean (M) | vB19 turns | Normal net on map? |
|---|---|---:|---:|---:|---|
| 1 | schooltime A | 76,876,136 | 7.631 / 9.242 | 20,912 | No |
| 2 | schooltime B | 71,803,255 | 7.809 / 8.954 | 13,947 | No |
| 3 | slithery_fight A | 61,442,325 | 6.278 / 6.594 | 27,890 | No |
| 4 | slithery_fight B | 57,868,667 | 6.197 / 6.429 | 28,822 | No |
| 5 | autarky A | 52,958,332 | 22.927 / 23.047 | 10,964 | Eligible |
| 6 | default A | 47,794,169 | 23.578 / 23.620 | 4,451 | Eligible |
| 7 | queen_of_spades A | 44,841,708 | 22.418 / 22.439 | 2,335 | Eligible |
| 8 | trophy A | 44,324,104 | 22.936 / 22.995 | 4,464 | Eligible |
| 9 | devil A | 42,858,866 | 22.044 / 22.073 | 4,644 | Eligible |
| 10 | dilemma A | 42,274,863 | 21.705 / 21.749 | 3,617 | Eligible |

No bot-failure counts were reported in the 20 panel log rows. The spike-heavy open maps have much lower medians than maze maps; the expensive tail is not their routine network cost. The supplied self-play peak (~59M) is contextual, not independently re-measured here.

## Replay characterisation: examples, not identified CPU maxima

Indicators precede dragonAction in these replays. They must be associated within the same turnStart, rather than attached to the preceding action. Counts below are live units at action time, reconstructed from initial DRAGON records, splits and deaths; they are game-state counts, not necessarily the exact instant used by the bot's UNITS input.

| Replay | Round / dragon | Indicated input length | Friendly / enemy units | Indicator evidence / action | What it establishes |
|---|---|---:|---:|---|---|
| schooltime_1_A | 237 / 8 | 66 | 60 / 27 | `L66 s3.4 sp2061 rm152 ... pd0.00 K`; WNN | Very long dragon, near-full-board field, up to three-step enumeration |
| schooltime_1_A | 236 / 8 | 66 | 60 / 27 | `L66 s3.2 sp2060 rm152 ... pd0.00 K`; NNN | Repeated long-body, broad-field turns |
| schooltime_1_A | 235 / 8 | 65 | 60 / 26 | `L65 s1.3 sp2061 rm134 ... pd0.00 K`; N | Even a chosen single step comes after enumerating longer options |
| schooltime_1_B | 499 / 504 | 36 | 17 / 11 | `L36 ... sp1 rm1 ... pd0.00 K`; W | Long length alone does not imply expensive endgame search: remaining horizon is tiny |
| slithery_fight_1_A | 487 / 1485 | 26 | 60 / 5 | `L26 ... sp557 rm13 ... pd0.00 K`; WW | Large swarm and long dragon; shortened remaining horizon |
| autarky_1_A | 0 / 0 | 14 | 6 / 6 | `L14 ... sp2 rm2 ... pd0.97 K`; N | A cramped queen turn; deep survival and emergency paths are eligible |

Schooltime A had 47 ESCAPE-SPLIT and 2 DANGER-ESCAPE-SPLIT actions; Schooltime B had 46 and 10. Slithery A had 571 and 5, respectively. These show escape search is a real path, but do not measure its points. `sp` is selected-option flood-fill space; `rm` is static room; `pd` is estimated death probability. None of these indicators logs elapsed points, nnReady, number of options, or DFS node counts. Exact survival execution and per-turn net eligibility cannot generally be read from the strings.

## Code-level cost explanation

1. **Enemy reach construction is unguarded and can be quadratic.** `buildReaches()` (`main.cpp:780`) explores up to `3 * ceil(enemyLength/4)` tiles of depth per visible enemy head. Every neighbour uses `find(seen.begin(), seen.end(), n)` on a growing vector. Large enemy dragons can cover much of a 2,400-cell Schooltime board. With V reached cells this has O(V^2) membership work per visible head. `think():1578` calls it before the option/search guards. It can explain opponent-dependent peaks without any network call. Enemy sizes/visibility at the actual peak are unavailable.

2. **Free-path enumeration creates work that its guard does not bound.** `main.cpp:1697-1712` generates 16 two-step and 64 three-step direction codes. Excluding immediate reversals leaves at most 12 and 36 paths, plus four singles (52 before collisions). Input lengths 5+ unlock two steps and 9+ unlock three. The 60ms check bounds simulation, then `for (auto& o : opts) o.ev = evaluate(o.sim, true)` evaluates the entire queued list without a cumulative stop. A long dragon may therefore receive roughly 52 evaluations plus current-state and stay evaluations. Tightening only enumeration's 60ms guard will often save nothing, because simulation finishes cheaply before evaluation begins.

3. **Each evaluation repeats a large field computation.** `main.cpp:954-1005` clears N distance entries, traverses reachable cells to depth max(90, 2L+12), computes pearl probabilities/farm bonuses, and then runs staticSpace. Schooltime examples report space ~2,061; 50 such options can revisit roughly 100,000 cells, plus edges and probability math. `pearlProb():481` contains repeated exp calls. `deepAllowed = false` after 70ms disables DFS only; it does not stop this field computation. Additional stay/parent/child evaluations occur at `1798` and `trySplit():1400`.

4. **DFS budgets are per search, not per turn.** `main.cpp:1017-1026` permits 12,000 nodes below 35ms, 1,500 from 35-55ms, then zero. An option may run both pessimistic and optimistic searches, each with that budget. The optimistic pass uses the budget computed before the pessimistic pass. Recursive `dfs():833` checks nodes but no elapsed deadline. One option can overshoot a threshold before the next option notices. `doomedSplit():1297` also checks its 55ms deadline only before another child evaluation.

5. **Network cost is a separate maze-map component.** `nnRun():1558` exits on bigFeed (Schooltime/Slithery/Portals, `369`) or if elapsed >40ms; eligible calls cost approximately the supplied 18M. Since it runs after primary option evaluations, it cannot normally be added to a 59M search turn: such a turn already misses the admission guard. There is a separate unconditional round-0/id-0 self-test (`1735`), if execution reaches it; it may run even on an open map. The Schooltime A opening queen indicator BUD shows it reached the ordinary decision path, where this self-test is called. Its cost is confined to that opening turn and is not proven to be the 76.88M peak.

6. **The clock omits part of the charged turn.** T0 resets after `readTurn()` (`1910`), leaving input parsing and first-turn initialization outside elapsedMs accounting. Sonar, indicator text, protocol output and the final flush occur after think. A write costs 2.5M + 4,000 points/byte. Existing buffering produces one flush, but four sonar lines and a ~90-byte indicator can still add roughly 3.4-3.6M total output cost. The 70ms guard is not a 70M whole-turn ceiling.

## Profiling feasibility

WSL checkout exists at `/home/sohan/the-loong-game`. Both requested commands attempted from `examples/tooling` failed immediately: `just: command not found`. Neither Nim nor clang/gcc was found on PATH. Zig is available by explicit path (`~/toolchains/zig-linux/zig`, version 0.16.0), and Wasmtime headers exist; this is not a claim that every build dependency is missing. The installed `~/toolchains/zig-judge-out/bin/loong-judge` is a Sep 29 binary with the old `--engine --map --a --b --seed --debug` interface, not the checkout's `run --sandbox --profile` interface. Expected `~/the-loong-game/build/bin/loong-profile` / registered compiler sidecars are not established by this installation.

`just/inspection.just:184` runs the newer judge and writes a function/operator-class profile. `harness/profiling/README.md` describes a team-wide game profile, not a per-turn profile, so even restoring it requires a turn observer/window to attribute the worst turn specifically. No system packages were installed. No build attempted: C: actually had ~150MB free (not ~6GB), and WSL storage shares that physical disk. Building the new judge and tooling would consume scarce disk and still require absent command tooling. The per-function analysis above is therefore structural, with no fabricated percentages.

## Concrete reductions, ordered by confidence

Savings are estimates unless explicitly described as arithmetic; they are not additive and require paired validation, especially queen survival.

| Change | Expected saving | Safety constraints |
|---|---|---|
| Replace buildReaches linear seen-vector lookup with an N-cell stamped visited array; retain identical depth/order | Membership work changes O(V^2) to O(V). Potential multi-million-point saving for wide enemy reach; absolute M unknown without profile | Best first change: preserve reached cells, turn-distance labels and traversal order exactly; no threat truncation |
| Cache pearlProb by (cell, arrival depth) for the current turn; precompute farmBonus on map activation | Avoid repeated exp/farm calculations across dozens of evaluations. Several-M plausible on broad Schooltime turns; unmeasured | Cache must reset each turn and preserve all probability inputs. Do not cache whole evaluations across different simulated bodies |
| Evaluate all legal singles first; admit optional paths only while elapsed <=45-50ms, cap total evaluated options at e.g. 16 | Max primary option evaluations 52 ->16 (69% fewer in open long-body cases). Tentative 10-25M tail reduction if field evaluation dominates | Reserve emergency escape work; preserve candidate safety ordering and queen regression checks. This changes move quality and is not behavior-neutral |
| Add a shared DFS turn budget and check elapsed in recursion every 64-128 nodes; re-check before optimistic pass | Limits one-call overshoot and repeated 12k-node searches. Saving equals work currently past the deadline; absolute M unknown | Unfinished searches remain unproven; never promote a partial search to safeClass 2. Keep exact state rollback on unwind |
| Apply one cumulative optional-work deadline to evaluation, emergency candidates and split probes; target <=50-55ms measured work | Measured peak must drop >=11.88M to reach 65M. A correctly enforced deadline could recover 10-20M from overruns; existing guards alone cannot guarantee it | Stop optional work only after retaining a usable single-step fallback; reserve input/output allowance and do not skip mandatory collision/threat construction |
| Admit maze net only below 30ms rather than 40ms, or skip it on non-queen drones at UNITS>=40 | About 18M per skipped call; **zero saving on the Schooltime/Slithery peak games** | Already reranks inside safety classes, so collision legality remains. Strategic benefit is unproven; prefer elapsed admission over arbitrary global unit count |
| Strip final indicator diagnostics while retaining buffered single flush | ~0.36M for a 90-byte indicator; not another 2.5M because it shares the existing write | Low-impact tournament cleanup; preserve sonar/protocol. Do not claim it fixes a 12M overrun |

Aim for **<=65M maximum complete-turn cost**, matching the repository's CPU guidance, leaving >=35M headroom. Current maximum leaves 23.12M; reaching 65M needs at least 11.88M reduction. Budget optional think work to approximately 50-55M, then measure actual parsing, initialization and output reserve rather than assuming elapsedMs includes them. In particular, guard unbounded buildReaches membership work through an exact data-structure improvement before relying on optional-search deadlines.

For later validation, retain per-turn `(team, dragon, round, points, failure)` outside the sanitized replay using the current checkout's `game.zig` TurnObserver/recordTurn hooks, verify aggregate maxima match panel output, and profile the matching build with name sidecars. Compare candidate/control on the same maps/seeds at -j 2, log the top turns and queen regressions, then remove only audit-generated replays. This audit generated none; the pre-existing yardstick replays were retained. Only this note and one append to AGENT_LOG.md are intended changes.
