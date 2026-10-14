# Search, forward engines and CPU budgeting

This document records search designs, simulator fidelity and measured CPU costs.
It explains why working engines did not establish a useful deployable search layer.
It preserves the evidence needed to revisit search under partial observation.

## Contents

- Rules and evidence
- Search plan and S0 gate
- S1 Python simulator
- S1b C++ forward engine
- S3 served-policy prototype
- Queen-only search
- CPU points and guard thresholds
- CPU audit and fix
- WSL and Zig judge
- Recommendations

## Rules and evidence

**OLD rules, before 2026-10-01:** round-500 scoring used longest living dragon, then total length; x sprint steps cost x−1 length.
**NEW rules, from 2026-10-01:** round 500 compares queen length (IDs 0/1; dead queen = 0), then longest living dragon, then total length.
Free steps = ceil(L/4), fixed from length at move start; eating does not increase that move's quota.
Round index 499 is the 500th round; turns run sequentially in ascending dragon ID, including newborn split children.
Use later dated results or explicit follow-ups where sources disagree: October 2 verification supersedes setup blockers; October 4 settles queen-search eligibility; October 6 updates MLP costs.
Historical opponents below identify experiments, not the current champion.
Engine fidelity, search value, CPU safety and promotion are separate conclusions.

## Search plan and S0 gate

The October 2 plan proposed contact-triggered, net-guided rollouts added to the rule layer.
Existing bot simulate() advanced our dragon against frozen occupancy; replay rebuilders applied events rather than independently executing rules.
The official wasm engine provided whole-match execution without bot-usable snapshot/branching APIs.
The plan's initial “no usable simulator” conclusion was superseded by S1/S1b.

| Component | Proposed design, not a validated improvement |
|---|---|
| Trigger | Enemy reach 3×ceil(enemy length/4)+1 intersects ours, contested pearl, or close top rule scores |
| Roots | At most four rule-legal candidates with net probability ≥5%; retain sprint paths |
| World | Known topology, visible/remembered bodies and pearls, observed countdowns |
| Active set | Dragons whose reach intersects ours; others frozen |
| Horizon | Usually three rounds; proposed five in opening, two with more than eight active dragons |
| Order | Finish requesting-ID suffix, then full rounds including newborns |
| Policy | Greedy initial rollout; sampled later replies; UCB1 allocates further trials |
| Decision | Tactical veto first; ties retain rule choice |
| Leaf | Material, queen death/growth and trap terms; exclude deliberate feeding drones |

Contemporary new-rule corpus: 54% of top-team wins ended by elimination, about 8% were queen-decided.
These corpus-specific observations motivated material emphasis, not a universal scoring prescription.
Proposed queen-death terms −(own length+20) and +(enemy length+10) were untested weights.
The original 9–10 working-day estimate was a plan, not measured delivery time.

| Gate | Requirement | Evidence |
|---|---|---|
| S0 | ≥approximately 15% visible-and-alternative lost length, clearly above top winners | NO-GO |
| S1 | Exact parity on ≥40 local +20 public games | Four-game task gate passed; larger requirement not established |
| Official scenarios | Crafted differential cases against official engine | Simulator assertions exist, not the full official scenario suite |
| S2 hindsight | ≥40% recall; ≤5% false alarms and winner overrides | No completed result in listed sources |
| Cheap rollout policy | ≥90% teacher top-1 agreement; ≤0.3M points/call | Design target, not achieved evidence |
| Wasm search | Maximum <65M over 20-game smoke; no new timeouts | No certified general-search implementation |
| Strength | ≥10pp paired improvement over ≥80 games, then ladder A/B | Not demonstrated |

Six dragons ×three rounds ×three roots require 54 policy calls for one greedy pass.
A ~21M conv call cannot support that; even a hypothetical 5M conv is too expensive.
The plan targeted ≤0.15M rollout calls using sparse MLP inputs, SIMD and caching; ≤0.3M was the acceptance bar.

### S0 addressable-loss audit: October 2 NO-GO

129 physical replays (85 public, 44 local) produced 167 selected-side observations.
Own ladder: 26 games, 18 wins/eight losses; top winners: 67 observations across 12 teams; local vB19: 48 sides.
Eight public games overlap own losses/top wins; local self-play sides are correlated.
Missing out/sw_2 replays were not regenerated; available retained controls were used instead.

| Cohort | Total lost length | Prior-three qualifying length | Share |
|---|---:|---:|---:|
| Own ladder games | 17,015 | 1,616 | 9.50% |
| Own eight losses | 6,137 | 641 | 10.44% |
| Own 18 wins | 10,878 | 975 | 8.96% |
| Local vB19 | 32,606 | 5,475 | 16.79% |
| Top winners | 49,105 | 8,218 | 16.74% |

Denominator: death length plus positive net shrink on successful moves; splitting is redistribution.
Qualification: at t−1, t−2 or t−3, eventual killer head visible within 7×7 and a different legal first step in the same snapshot.
Legal alternatives exclude own tail, kelp, occupied cells and portal exits outside view.
Passive head-on victims count; each death contributes once. This proxy does not prove three-round survival or saved material.

| Sensitivity | Own games | Own losses | Local | Top |
|---|---:|---:|---:|---:|
| Latest three decisions, possibly fatal turn | 11.53% | 13.35% | 20.15% | 18.55% |
| Exclude allied kills at r≥300 from numerator | 8.59% | 9.76% | 15.24% | 15.53% |

Killer head never visible in prior three rounds: 60.25% of own collision-lost length; losses 57.18%, local 50.76%, top 36.97%.
Local clears the absolute bar but ties top winners; excluding late allied feeding removes even that descriptive advantage.
Wall/self deaths with alternative steps fall outside this killer-head metric; alternatives do not establish avoidable traps.
Reconstruction: 167/167 final total-length checks and 2,321,879 successful movement updates, no topology mismatch or unattributed killer.
Only eight own losses and unmatched maps/opponents/builds limit inference; dragons are not independent game samples.
Critic accepted method and NO-GO. This does not prove all forms of search useless.

## S1 Python simulator

tools/engine_sim.py and tools/engine_sim_test.py implement NEW-rule copied-state full-round simulation.
load_map(text, seed) begins at round −1; step(state, actions, spawn_input) returns the next round's new state.
Actions can be mapping/callable; missing action means suicide. Mutable state/RNG copied, immutable topology shared.
Own-tail collision precedes tail advance; head-on kills the other dragon first; affordability checked before paid movement.
Death pearls use current body after any successful sprint steps.

| Official game, seed 1 | Exact rounds | Dragon-turns | Microseconds/copied round |
|---|---:|---:|---:|
| Default A | 388/388 | 16,996 | 719.7 |
| Default B | 500/500 | 19,576 | 761.2 |
| Trauma A | 500/500 | 17,723 | 658.4 |
| Trauma B | 500/500 | 18,078 | 713.1 |
| Total/aggregate | 1,888/1,888 | 72,373 | 712.7 |

Windows Python 3.11: 18.6 microseconds/dragon-turn amortised; copies/ticks/actions/events included, replay decoding excluded.
Ordered events, full bodies, facing, deaths, pearls/countdowns and terminal standings matched without resynchronisation.
Replay countdowns/spawns/resets were exogenous; eating, movement and death drops were simulated.
This did not establish official seeded-spawn parity, sonar/protocol parity or wasm points.
Assertions cover payment/growth, tail/head collision, child order, invalid actions, unit cap, kelp/portals, queen/ties and seeded branching.
The plan's suspicion of missing intermediate sprint cells was corrected: each successful step emits dragonUpdate.
Reproduce: tools/panel_zig.py viper_b19_f1 baselines/vB19 out/sim_oracle --maps trauma,default --seeds 1 -j 2.
Then tools/engine_sim_test.py out/sim_oracle --json out/sim_oracle/parity.json; scenario-only: python tools/engine_sim_test.py.
Generated replays were deleted after compact reports were saved.

## S1b C++ forward engine

engine_cpp/engine.hpp derives from MIT reference engine, updating free-step/queen rules; retains linked cells, topology, RNG, split queue and sonar.
host.cc supplies native loading and official lockstep C API; bot core uses fixed arrays without native loader.
API: LoadMap, Begin, copied Game, Advance, Act; StartRound/EndRound permit explicit round rollouts.
Map must outlive branches and remain immutable; read observations before Act clears inbox.
Check stale/dead queue entries by both slot and ID; reusable slots are not dragon identities.

| State/bound | Actual size/capacity |
|---|---:|
| Copied Game, RNG and inboxes included | 121,328 bytes |
| Shared immutable Map | 94,224 bytes |
| Geometry / slots / queued turns | 64×64 /128 /512 |
| Inbox messages / action directions | 64 per slot /10,240 |

No heap, exceptions, RTTI or iostream in header. Bounds overflow invalidates checks; callers must supply valid geometry/action lengths.
Actual copy size exceeds the plan's ~25KB estimate.

| WSL three-round benchmark | C++ rounds/s | Python rounds/s | Speedup | C++ move steps/s |
|---|---:|---:|---:|---:|
| Six dragons | 54,535 | 1,247 | 43.72× | 327,208 |
| Sixty dragons | 39,409 | 1,098 | 35.90× | 2,364,528 |

64×64, separated four-segment dragons, no beds, one east step per turn; median of three trials.
Copies/ticks/actions included; Python constructs events, C++ records outcomes. Native throughput is not wasm speed/points.
C++ matched 1,888/1,888 replay rounds; Python independently matched official replay.
Natural spawning matched Python 62/62 rounds without injection, not independent official seeded-spawn proof.
Crafted C++ tests cover scoring/dead-queen slots, sonar clearing/delivery, deterministic branching and movement cases.
Zig bundled Clang compiled C++17 and 36,438-byte wasm32-freestanding probe; separate g++ was not tested.

Official follow-up: **100/100 games, zero differences/skips, 14,264 turns**, ten live maps, seeds 123–222, unswbc 1.2.7.
Compared byte-for-byte observations including sonar/protocol, IDs, end timing, winner/reason, living counts/totals and overflow.
Upstream lockstep does not independently compare terminal queen/longest fields; short games do not prove round-500 scoring.
Old unswbc 1.2.2 gave 90 same/10 different, 13,069 turns; sprint lengths exposed OLD-rule incompatibility.
Correct oracle SHA256: 26e68680e45eb0f221db702aead9eefde776c2ad2ba066f4ddf8c12500c6a546.
Tools: bench.cpp/bench.py, bridge.cpp, seeded_test.py, scenarios.cpp, verify.py, lockstep_maps.txt; commands in engine_cpp/README.md.
Build separate judge with -Dreference-source=<repo>/engine_cpp/host.cc; run --lockstep <repo>/engine_cpp/lockstep_maps.txt --games 100 --seed 123.
Compact JSON retains counts/provenance; original RAM scratch fixtures/logs disappeared externally, so original hashes are unavailable.
Disposable reference judge output was removed after verification; rebuild to repeat lockstep.

## S3 served-policy prototype

This S3 result is a Python served-policy experiment, not completion of the plan's cheap-MLP milestone.
tools/search_proto/serve_search.py, panel.py and check.py use serve judge, official 1.2.7 and tools/engine_sim.py.
Socket framing: GAME, SPAWN, TURN with byte counts, DEATH, END; reply includes PROTOCOL 3 and ENDTURN.
One process merges team observations: communication upper bound relative to isolated shipped dragons.

| Experiment | Result | Meaning |
|---|---|---|
| Trivial served Default B | 152-round loss; 17.435s wall; 0.267ms mean/turn | Framing/lifecycle works |
| Net-only live panel | 4/20 vs cached vB19 | Weak baseline, not full rule bot |
| Untriggered Trauma pilot | Neither finished after 639.8s; 117/123ms mean; 79/81 net calls/turn | Excluded from outcome statistics |
| Triggered depth-three Trauma pilot | 0/2; both 500 rounds; 41/45ms mean | Topic-matched log; no decisive complete full-panel result |

≤4 roots above 5% legal net mass; two stochastic opponent trajectories; UCB1 allocation, raw mean final scoring.
Trigger on reach overlap/close prior; always search fixed queen with ≥2 roots; skip single-root decisions.
Seed 123+round×4096+id prevents skipped earlier decisions changing later samples.
Depth three = current suffix plus two full rounds; stop at r499.
Only observed positive countdowns predict spawns; no hidden initial dragons/countdowns; head sightings expire after one round.
Known live topology permitted; unknown queens receive no invented death reward.
Lifecycle checks cover logits, countdown expiry, child IDs, suicide framing and terminal depth.
Limits: truncated bodies/lengths, omitted tail-only rollout blockers, no hidden-team elimination inference, fixed split size two, net-only opponent model.
Zero metered served points do not prove wasm feasibility. No decisive gain over full rule layer was established.

## Queen-only search

October 4: viper_y96qh with Params::qSearch and OFF arm viper_y96qh_off, derived from viper_y96qg.
True-queen depth-two adversarial lookahead: rule root plus two alternatives, full sprint paths, at most two nearest threatening heads.
Trigger: rule pDeath≥0.05, enemy head within Chebyshev five, or enemy ping/threat flag.
Override only when an alternative survives a worst-case reply that kills the rule winner.
Unknown geometry/bodies force fallback; paid/blocking reply modelling hardened after critique.

| Check | Result |
|---|---|
| OFF parity | 4/4 summaries; 504,664 gameplay events identical |
| Initial smoke | Peak 64,464,114 points; zero overrides |
| Initial metered selfchecks | 3/3; mean 0.973ms, maximum 1.208ms |
| Later corrected differential checks | 240 random +10 hand cases passed; maximum call 0.26ms |
| 20 dev maps ×2 seeds ×2 sides vs Y9_6 | ON 45/80 = OFF 45/80; identical per map |
| Queen deaths / overrides | 77/80 both arms /zero |
| Australia diagnostics | 127 triggers per 397 calls; **zero eligible searches** |

Every trigger rejected for unknown geometry/unseen actors: the 7×7 view did not supply the complete state required.
Identical outcomes establish a no-op, not neutral value from executed search.
Decision: park unless redesigned with a belief over unseen enemies.
Queen-search reports are absent; outcomes come from topic-matched October 4 AGENT_LOG.md entries.

## CPU points and guard thresholds

| Cost/limit | Points | Qualification |
|---|---:|---|
| Each stdout/stderr write | 2.5M +4,000 per byte | Official local timeout documentation |
| Conv call | About 21M; 21,136,975 measured | Later benchmark supersedes old ~18M |
| Early MLP student call | About 1.25M | October 6 initial trial, matched log |
| Later MLP student call | Mean 1,658,790; sampled max 2,482,105 | Newer fix-round-two report takes precedence |
| Typical later tested bot peaks, including 64×64 tests | Approximately 63–66M | Queen smoke 64.464M; tight-guard variant 64.9M; qf 65.2M; L10 66.083M |
| Desired complete-turn maximum | ≤65M | Repository target, not universal achieved bound |
| Per-dragon per-turn kill limit | 100M | Exhaustion stops reply and kills dragon |

63–66M is representative of tested builds, not all maps/builds: original vB19 reached 76.876M.
Later MLP: 1,600/1,600 argmax parity, holdout 68.628% vs conv 68.579%, but safety FAILED 50/98 vs 59/98 (−9.18pp).
Initial MLP also failed 47/98. Cheaper inference neither justifies promotion nor meets ≤0.3M rollout target.
elapsedMs measures metered clock, approximately one million points/ms; admission thresholds are not total-turn guarantees.

| Threshold | Inspected viper_y96qg/main.cpp use |
|---|---|
| 40ms | Network, compass preparation/reranking, optional deep evaluation |
| 48ms | DFS every 64 nodes; deep/free-path/split stops |
| 52ms | Attack/intercept enumeration; optional evaluation after retaining ≥2 roots |
| 55ms | Doomed-split admission and some sonar/echo work |
| 62ms | Emergency true-queen amputation admission |

CPU1 initially admitted net below 30ms; later qg uses 40ms: distinct variants.
Queen-search task separately required entry ≤50ms, four-ms abort and 5M call budget; requirements are not universal guarantees.
Unsandboxed games cannot certify points safety; use --sandbox -v or complete-turn judge statistics.
Official limits: 48MB memory, one thread; first-turn setup charged. Post-end_turn work charges next turn.
Arithmetic/comparisons mostly one point; loads/stores/SIMD two; division/remainder three; direct call four; indirect call six.
Bulk memory ten plus one/eight bytes; reads six/byte; random draws 40,000+three/byte; file open/path lookup 40,000.
Use one buffered flush: each extra write costs 2.5M; stderr same price. A 90-byte indicator adds ~0.36M when sharing flush.

## CPU audit and fix

October 2 vB19 peak: **76,876,136**, Schooltime A; remaining headroom 23,123,864. Schooltime B: 71,803,255.
Ordinary net disabled there: spike was not an extra network call.
Schooltime A median/mean only 7.631/9.242M; B 7.809/8.954M: expensive tails.
Replay action statistics absent; peak dragon/round/length cannot be reconstructed.

Structural suspects, not measured function percentages:
- Reach BFS linear vector membership could be O(V²), before guards.
- Up to 52 paths queued before collision filtering; full evaluations continued past enumeration guards.
- Repeated wide distance/space fields and pearl probability math; example space ~2,061 cells.
- Per-search DFS budgets, stale optimistic admission and no recursive elapsed checks.
- Clock reset after parsing; initialization/output outside think accounting.

viper_b19_cpu copied F1, changing only main.cpp and preserving map/net/auth headers.
Fix: exact N-cell arrival lookup preserving BFS order/reach; shared 48ms optional deadline.
DFS checks every 64 nodes, restores state, returns attained depth only; recheck optimistic and parent/child passes.
Attack reserve 52ms, checks every 16 codes; include parsing in clock; net admission 30ms.
One field can overrun admission; initialization/output still extra. No hard complete-turn cap proved.

| Map/seed/seat | F1 before max | CPU1 after max |
|---|---:|---:|
| Schooltime 1 A | 76,870,551 | 51,868,602 |
| Schooltime 1 B | 63,257,872 | 51,465,973 |
| Schooltime 2 A/B | unavailable | 51,958,038 /51,780,516 |
| Devil 1 A/B | unavailable | 42,875,350 /29,120,685 |
| Devil 2 A | 56,235,797 | 44,980,551 |
| Devil 2 B | 43,058,418 | 43,448,533 |

Later fresh eight-game panel: all <65M, peak 51,958,038; 32.4% below largest before peak, from different games.
Historical live gate vs y7_12_nn1: **12/20 PASS**, zero asymmetric queen deaths before r50; own queen deaths 14/20 vs 20/20.
Wins/2: Autarky2, Default2, Devil0, Dilemma1, Portals2, QoS1, Schooltime2, Slithery0, Trauma1, Trophy1.
Gate reused completed 20 replays; only eight CPU games reran fresh after cache hits lacked CPU stdout.
F1 pairing: all 509 actions through r20 matched; Devil seed1 complete action sequences identical.
Schooltime first divergences: r222/458/269/407. Seed2 A queen died r409 vs F1 r454: **45 rounds earlier**, unresolved.
Partial paired subset 4/6 each; old 10/20 yardstick belongs to vB19, not verified F1.
At n=20, ~11pp standard error near 50%; gate does not establish strength/promotion; eight games do not prove universal CPU cap.
Select CPU by candidate seat: stdout A index 12/B index 14 (zero-based), third p50/mean/max component.
Use tools/buildwasm.py for header-aware caching.
Evidence: out/cpu_after/fresh/panel.log and summary.json; out/cpu_gate/gate_report.json and paired_queens.json; candidate pairing scripts.

## WSL and Zig judge

October 2 setup resolved missing just/Nim and old judge's UnknownFlag serve blocker.
just 1.43.0, Nim 2.2.6, Zig 0.16.0, Wasmtime C API 49.0.1; v27 preserved.
Recipes: ~/the-loong-game/examples/tooling, not checkout root.
User gcc wrapper invokes zig cc; user links supply zlib/SQLite; no sudo/apt.
WASMTIME_INCLUDE/WASMTIME_LIB select v49 in ~/.profile.
Commands: just tools-build; just zig-judge-build -j2 --prefix "$HOME/toolchains/zig-judge-out-serve".
Seven binaries, 19MB: loong-gamedata/report/sample-replays/recover/profile/map-variants/regenerate.
New judge: /home/sohan/toolchains/zig-judge-out-serve/bin/loong-judge; old zig-judge-out preserved.
Checkout 19f56e181fd290eee24e9a0b1817d56b2eb8c6e2; local help handler exposes serve/lockstep, gameplay unchanged.
Setup smoke: v7.5 self-play 500 rounds, A total 135 vs 7, zero failures, 9.790s wall; peaks 14,773,016/7,822,227.
Smoke used OLD-rule ~/venv unswbc 1.2.2; build readiness was not NEW-rule fidelity. Use checked 1.2.7 oracle.
PowerShell: direct arguments through wsl -d Ubuntu --; piped script once inserted CR into seed and failed before play.
Git Bash: MSYS_NO_PATHCONV=1 for /mnt paths. Bind build/map/engine/judge/seed/side in comparisons.
WSL virtual free space is not C: headroom; historical work used 1.5GB physical floor and at most two games/build jobs.
Function profiling is team-wide unless augmented with turn observer; aggregate maxima/sanitized replays cannot identify peak turn.

## Recommendations

- Revisit only with a **belief over unseen enemies**, modelling reach outside 7×7 and uncertain bodies/topology; complete-state eligibility rejected every contact.
- Track aged observations and uncertain spawns; compare sampled/conservative hypotheses without presenting guesses as verified safety.
- Measure triggers, eligible searches, aborts and overrides before a large panel.
- Re-establish tactical value on matched NEW-rule losses; separate deliberate trades/feeding and wall/self traps.
- Compare against full rule layer on paired seeds/sides/opponents; served net-only/shared-observation evidence is insufficient.
- Use simulator-computable inputs for every modeled dragon; root memory features are not automatically available.
- Meter branches/input building/policy in wasm; native 43× speedup and 1–2.5M MLP calls do not meet original rollout budget.
- Retain legal fallback, rollback interrupted work, never classify incomplete survival as safe; check queen regressions separately.
- Capture per-turn team/dragon/round/points/failure outside sanitized replays; test dense 64×64, long bodies and high unit counts.
- Use fresh sealed controls/current promotion yardstick; engine PASS or historical CPU gate does not approve a candidate.

Sources consolidated: tools/tasks/docs_merge/COMMON.md; research_new_meta/search_layer_plan.md; research_new_meta/search_s0_result.md; research_new_meta/search_s3_result.md; research_new_meta/engine_sim_status.md; research_new_meta/engine_cpp_status.md; research_new_meta/cpu_audit.md; research_new_meta/cpu_fix_result.md; research_new_meta/cpu_fix_verify.md; research_new_meta/wsl_setup_result.md; engine_cpp/README.md; docs/timeouts.md (CPU summary only); reports/param_search_report.md and reports/param_search_critique.md (read; parameter farm, separate topic); reports/mlp_student_report.md (newer CPU evidence); tools/tasks/queen_search.md; viper_y96qg/main.cpp (guards); topic-matched October 2/4/6/7 AGENT_LOG.md entries (missing search reports/later CPU). Original files remain; no reports/queen_search*.md or reports/search*.md existed.