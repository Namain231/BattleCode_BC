# Rule mining for UNSW Battlecode (Loong)

Turn public top-team replays into readable rules for the unknown-map gP build.
Document the specification, implemented pipeline, measured findings, and cycle-1 outcome.
Keep historical evidence separate from validation required under the changed rules.

## Contents

- [Goal and rules boundary](#goal-and-rules-boundary)
- [Why consolidation was selected](#why-consolidation-was-selected)
- [Method and implementation](#method-and-implementation)
- [Learned death rules](#learned-death-rules)
- [Learned queen movement](#learned-queen-movement)
- [Evaluation and outcome](#evaluation-and-outcome)
- [What worked and failed](#what-worked-and-failed)
- [How to rerun](#how-to-rerun)
- [Limits and validation](#limits-and-validation)

## Goal and rules boundary

The 2026-10-01 v2 specification replaced v1: target **gP (S.2)** for unseen-map events, and learn consolidation rather than feed yes/no alone.
The first family couples drone death placement/timing with queen movement toward useful drops.
Each candidate adds one rule to gP behind a knob; separate and combined tests expose interactions.

**OLD rules, before the 2026-10-01 change:** round-500 longest-dragon tiebreak.
All gP win rates and cycle-1 game results below are historical OLD-rules evidence, including work dated Oct 1 before the change.
**NEW rules:** at round 500 compare queen length (dead queen = 0), then longest dragon, then total length; free steps = `ceil(L/4)`.
The historical label “queen” often means the longest dragon; it must not be silently equated with the new designated queen.

Source precedence: the later `insights.md` rules-change banner and cycle summary supersede the Sept 30 research and Oct 1 spec wherever conclusions conflict.
The undated generated reports do not establish their corpus's rules version; new-rules applicability is **(unverified)**.
No supplied source establishes a promoted rule-mining candidate.

## Why consolidation was selected

Historical diagnosis: about **85%** of unseen-map games ended on longest-dragon length at r500.
S.2's ladder test was **3–7**; on Schooltime its largest four were **36/23/20/19**, total **323 vs 97**, yet it lost to one enemy of length **56**.
Drones seldom reached a visible queen; friendly bodies boxed her in; **15–41%** of fed pearls went uneaten.
Every-second-segment drops limited intake to roughly one pearl per two moves.
Top-team queens reached **30–39 at r400**, wasted **3–12%** of feeds, and received nearby drone suicides from about r280.

gP source provenance: submission **13685**, “S.2”, uploaded **2026-09-30 18:40 UTC**, from `viper_y8m_gP/`.
The oddly named `research_new_meta/s2_gQ/README.md` actually documents gP.
It extends Y.8m (`baselines/y8m_active`, submission 11461); changes are in `main.cpp`.
`bot.toml`, `maps_data.hpp`, `policy_nn.hpp`, and `policy_weights.hpp` were byte-identical to Y.8m.

| OLD-rules build/change | Evidence | Decision |
|---|---|---|
| Bed learning only, `viper_y8m_gaps` | Set A 53–67; B 67–53; pooled 50% | Insufficient alone |
| gP: bed learning + unknown-map `protectFrom` 400 → 340 | A 72–47; B 73–47; reported pooled 61% | Historical new-map base |
| gPQ: lower-bound queen election, reports expire after 15 rounds | 44–76 | Dropped |
| gPE: protect from r280 with 30+ dragons | 71–49 | No gain over gP |
| gD: tabu against revisiting without eating | Live 40–20 vs gP 31–29; unseen 66–54 vs gP 73–47 | Even overall |
| gM: late feeding from r430 | Live 30–30; queen +0.9, fewer units | Not kept |
| gJ: gD + merge at `460 - travel to queen` | Unseen 68–52; live 28–32 | Not kept |
| gB: unknown maps use open-map `bigFeed` defaults | 22–98; early economy collapsed | Rejected |

gP set-A final longest was **16.1 vs 15.1** for bed-learning-only.
Paired final margin against Y.8m: **+1.08 ±0.60** vs **−0.45 ±0.59**; r500 units about **23.5 vs 18**.
On ten live maps gP vs Y.8m was **31–29**; peak CPU **61.7M**, control similar, live roughly **49–59M**.
The later summary reports **240 games** pooled; printed A/B gP counts total **239**, so the exact denominator is **(unverified)**.

`learnGap()` runs only when `!KM`: largest observed countdown estimates maximum gap; an upward reset on consecutive observations gives a fresh gap draw (value + 1).
It trusts estimates only after one reset; split children start blank.
Protection already began at r340 on known maze maps; `bigFeed` disables queen protection on known open maps, but their queen head-on danger multiplier moved from ×2 to ×3 earlier.

## Method and implementation

### Corpus and unknown-map reconstruction

The spec began with **184 top-16 replays**, about twelve per team.
Top-team games train the rules; our recent ladder/local gP games are a separate contrast set.
Teacher sonar is mostly hashed, so queen knowledge uses teammates **seen** recently, not decoded messages.
This approximation is explicit; it cannot recover the teacher's private state.

| Module | Responsibility |
|---|---|
| `rulemine/state.py` | Replay events in engine order; bodies, pearls, eats, deaths; per-dragon terrain and teammate memory; final-state check against engine result |
| `rulemine/mapgeo.py` | Toroidal geometry and portal teleports; unseen edges assumed open; portals usable only after both ends were seen |
| `rulemine/features.py` | Shared 19-feature table, mirrored in C++; observed occupancy only |
| `rulemine/decisions.py` | Opportunities, choices, feed outcomes for death, budding, queen movement |
| `rulemine/extract.py` | Scouting `index.json` → CSV; optional bceval context |
| `rulemine/contrast.py` | Situation buckets; rank rate gaps by gap × sqrt(smaller support); queen choice tendencies |
| `rulemine/learn.py` | Game-grouped cross-validation, simple-model bake-off, queen conditional logit |
| `rulemine/codegen.py` | Version-stamped pure C++ functions in `rules_learned.hpp` |
| `rulemine/evalstate.py` | bceval context and fixed-round evaluation |
| `rulemine/evalpair.py` | Matched candidate/control games and mechanism deltas |
| `rulemine/parity.py` | Python/C++ vectors on the same logged dragon-turn |
| `viper_s2_rules/` | gP + `rm_hooks.hpp`, learned header, configurable hooks |

### Features the bot may know

Terrain memory starts at birth; a split child inherits no learned terrain.
Body occupancy is own body plus segments in the 7×7 window.
Map names, full hidden terrain, opponent-specific rules, decoded teacher sonar, and bceval probability are excluded from deployed features.

| Feature group | Names and definitions |
|---|---|
| Own state | `len`, `units` (protocol unit count), `round`, `age`, `since_eat` (observed length growth between turns) |
| Visible heads | `n_ally_vis`, `n_enemy_vis` |
| Largest visible ally | `top_ally_vlen`, `top_ally_ratio`, `top_ally_dist` (BFS with bodies blocking), `top_ally_approach` (torus distance fell since last turn), `allies_near_top` (Chebyshev 3) |
| Remembered largest ally | `mem_top_len`, `mem_top_age`, `mem_top_dist` (torus Manhattan to remembered cell), `i_am_top` |
| Local opportunity | `enemy_threat` (visible head BFS reach ≤ min(visible length − 1, 3)), `room` (reachable tiles capped at 40), `pearls_r3` |

Unknown/unreachable distance is **99**.
`round` and `age` are excluded by default: prefer conditions over clock schedules.
The implemented threat feature's three-step reach is historical and requires review under NEW free-step rules.

### Opportunities and labels

- **Death:** longer ally visible, or longer teammate seen within **15 rounds** whose recorded cell is within **6 torus-Manhattan steps**; enemy-caused deaths are excluded.
- Positive death channels: invalid output, kelp, any own-body hit, or collision with an ally body.
- `fed_ok`: target ally (largest visible, otherwise remembered) ate **at least one** dropped pearl within **5 rounds**; `fed_any`: any teammate did.
- **Bud:** length ≥ **4**, team below unit cap **64**; label is whether it split.
- **Queen move:** side's true longest dragon from **r250**, single-step moves only; one row per legal candidate, chosen step marked.
- Sprints are excluded from the first family because profiling did not identify them as the gap.

The own-neck-only spec became any own-body hit because replays cannot distinguish the intended channel reliably.
“Fed successfully” is not proof all drops were recovered, nor proof the death was intentional.

### Learning, context, and deployment

Yes/no shipping candidates are **L1 logistic** and **depth-3 tree**; GBM is a ceiling check.
The spec's rule-list/depth-4 bake-off is not the implemented set.
Pick the simplest within about **2 AUC points** of the best simple candidate; report ceiling gaps and per-map instability.
Thresholds target the source team's decision rate, at most **1.25×**, rather than maximising balanced accuracy on rare positives.

Queen movement fits conditional logit: `P(step) = softmax(w · x)`.
Its seven terms are `eat`, `straight`, `room_after`, `d_enemy`, `d_ally`, `toward_allies`, `enemy_reach`.
These are candidate-step terms, **not** exposed components of gP's `evaluate()`.
Flag **DO NOT SHIP** unless held-out agreement beats chance and every single-feature baseline.

bceval `p_win` sees both teams and the full map: use only as context/filter (`--min-pwin`) or paired fixed-round metric.
It cannot measure one decision's effect for about **50 rounds**, so it is not a per-action reward.
Without `pycapnp`/bceval the pipeline continues with context unavailable.

Knobs: `rmDeath`, `rmQueen`, `wRmQueen`, `rmQueenFrom`, `rmLog`.
All off gives gP behavior; switch death and queen rules independently, then together.
Never submit `rmLog = 1`: `LOG RMF` exposes feature vectors in public replays.

## Learned death rules

The small reports use 8–12 games; the `lbdeath_*` reports use 22–25 games.
They are different corpora, not controlled before/after performance comparisons.
AUC measures ranking, not game gain. “Fire 0.00%” is reproduced literally; threshold rounding/calibration is **(unverified)**.

| Initial team | Opportunities / positives / games | AUC logistic / tree / GBM | Selected tree threshold | Fire / team rate; precision / recall |
|---|---|---|---|---|
| forgottomention | 59,642 / 310 / 12 | .911 / .927 / .959 | .977 | 0.00% / .52%; .13 / .09 |
| PPP | 36,229 / 367 / 12 | .866 / .889 / .921 | .982 | 1.05% / 1.01%; .33 / .14 |
| SSS | 35,747 / 214 / 8 | .913 / .906 / .880 | .952 | 0.00% / .60%; .34 / .09 |
| Stockfish | 33,421 / 156 / 12 | .802 / .786 / .869 | .956 | 0.00% / .47%; .06 / .06 |

| Expanded team | Opportunities / positives / games | AUC logistic / tree / GBM | Pick; threshold | Fire / team rate; precision / recall | Per-map AUC range |
|---|---|---|---|---|---|
| 3_14159265 | 137,787 / 607 / 25 | .920 / .942 / .961 | Tree; .975 | 0.00% / .44%; .11 / .09 | .85–.99 |
| chejibt | 64,409 / 513 / 25 | .912 / .889 / .952 | Logistic; .979 | 1.00% / .80%; .20 / .24 | .89–.97 |
| Cutlery | 100,123 / 507 / 25 | .887 / .897 / .954 | Tree; .963 | 0.00% / .51%; .00 / .00 | .86–.99 |
| ddabap | 101,444 / 642 / 22 | .921 / .925 / .965 | Tree; .976 | 0.00% / .63%; .25 / .08 | .78–.99 |
| dev_test_1__P | 94,462 / 401 / 25 | .927 / .921 / .968 | Tree; .975 | 0.00% / .42%; .13 / .10 | .84–.94 |
| Sponge_Albert_and_Bob_ | 98,122 / 550 / 24 | .914 / .916 / .962 | Tree; .957 | 0.00% / .56%; .00 / .00 | .87–.97 |
| SSS | 101,600 / 525 / 25 | .932 / .947 / .974 | Tree; .950 | 0.00% / .52%; .11 / .08 | .92–.98 |
| Stockfish | 137,404 / 847 / 25 | .873 / .867 / .947 | Tree; .961 | 0.00% / .62%; .14 / .04 | .85–.91 |
| WeHaveQuizzes | 100,332 / 723 / 25 | .896 / .917 / .957 | Tree; .922 | 0.00% / .72%; .06 / .05 | .89–.95 |
| y | 115,172 / 377 / 25 | .946 / .917 / .980 | Logistic; .994 | .41% / .33%; .11 / .13 | .83–.97 |

Common tree pattern: little room or a substantially longer nearby ally predicts death-channel behavior.
PPP's high leaf: ally distance ≤ **3.5**, length ratio > **1.134**, room ≤ **2.5**, probability **.982**, support **381**.
Sponge's nearby leaf: ratio > **1.094**, distance ≤ **1.5**, probability **.957**, support **2,092**.
Stockfish's expanded high leaf: room ≤ **.5**, since_eat > **2.5**, probability **.961**, support **1,519**.
These are descriptive leaves, not separately validated tactical recommendations.

The chejibt/y logistic models strongly penalise `enemy_threat` (raw weights **−4.9170 / −5.7376**) and remembered ally distance (**−.1010 / −.0928**).
Their own-length signs differ (**−.4480 / +1.1611**): do not transplant coefficients between teams.

Contrast report: top death rate **3.2% over 165,039 opportunities**, ours **1.7% over 121,116**.
Highest-ranked bucket: ratio (0,1.5], distance >98, not approaching, r≤150, p_win (.3,.5]; **13.7% vs 6.4%**, support **1,594 / 1,840**, score **+2.90**.
Another: ratio (1.5,2], distance >98, r250–350, p_win (.5,.7]; **14.3% vs 3.7%**, support **462 / 454**, score **+2.25**.
Distance >98 is the unknown/unreachable sentinel bucket, not evidence of an actual long feed route.
Rates cannot be compared directly with per-team model rates across different corpora/opportunity distributions.

## Learned queen movement

All ten reports beat chance and their strongest single-feature baseline; that establishes offline fit only.
Straight movement is the strongest single-feature baseline in every listed report.
Eating, straightness, and room have positive weights; `toward_allies` and `enemy_reach` have negative weights throughout.
Ally-distance signs differ by team, so there is no universal learned “approach feeders” rule.

| Team | Decisions / games | Held-out / chance / best single (straight) | Gain over best single |
|---|---|---|---|---|
| 3_14159265 | 5,087 / 19 | .642 / .414 / .573 | +6.9 pp |
| cheji_bt | 2,535 / 11 | .639 / .416 / .554 | +8.5 pp |
| Cutlery | 3,714 / 17 | .614 / .421 / .537 | +7.7 pp |
| ddabap | 4,706 / 16 | .559 / .416 / .486 | +7.3 pp |
| dev_test_1__P | 2,111 / 13 | .699 / .424 / .642 | +5.7 pp |
| Sponge_Albert_and_Bob_ | 2,991 / 15 | .712 / .421 / .614 | +9.8 pp |
| SSS | 3,908 / 16 | .586 / .412 / .507 | +7.9 pp |
| Stockfish | 4,119 / 20 | .694 / .427 / .620 | +7.4 pp |
| WeHaveQuizzes | 2,924 / 16 | .651 / .410 / .537 | +11.4 pp |
| y | 5,418 / 18 | .626 / .409 / .597 | +2.9 pp |

Example Stockfish raw weights: eat **+1.5567**, straight **+.9124**, room **+.0641**, enemy distance **+.0580**, ally distance **−.0889**, toward allies **−.1387**, enemy reach **−.6807**.
Sponge raw weights: **+2.6894, +1.0206, +.0930, +.0021, +.1005, −.2162, −1.1614** in the same order.
Raw coefficients depend on feature units; standardised weights in source reports are for interpretation.

## Evaluation and outcome

Screen candidate and gP control against the **same opponent**, identical maps/seeds/sides.
`evalpair` matches replay names `<map>_<seed>_<side>.replay` or farm `<ours>~<opp>~<set+map>~<seed>~<side>.replay`.
It reports win flips/sign test, candidate-minus-control mean final-longest margin with SE, p_win and longest at r250/r400, and feeds/game.
“Queen” in this tool is historical longest; its margin is not the NEW primary win quantity.

| Screen item | Historical acceptance rule / result |
|---|---|
| Unseen maps | Positive paired final margin on set A/B and dev; test held out until final |
| Live maps | No live regression |
| Feed frequency | Reject large unseen-map firing-rate inflation |
| CPU | Report judge peak separately; target ≤65M, hard death limit 100M |
| Ladder | Same-time control; README proposed 25 + 25 games, followed by promotion gate |
| Cycle-1 death outcome | PPP rule regressed gP on both test sets |
| Cycle-1 queen outcome | Five full/partial screens: 47–61%, all within noise of gP |
| Overall decision | No rule cleanly beat gP; no rule-mining promotion established |

Failure example: a death rule fitted on **three fixture games** fed **381 times vs gP's 53** on archipelago; r400 longest **5 vs 16**.
Do not conflate this fixture test with the 12-game PPP report.
Both hooks' CPU check on 2026-10-01: **54.3M vs gP 55.7M** on archipelago; that is one-map evidence.
The later cycle summary records five queen teams without screens and leaderboard-ranks-21–40 data that never reached learning.

Unseen sets: A = `maps_gen/gen_020–049` + `maps_dense/dense_000–029`.
B = `gen_050–079` + `maps_dense/dense_030–039` + `maps_dense2/dense_000–019` (`ladder/set60b.txt`).
`maps_rm_dev/` and `maps_rm_test/`: **20 + 20** maps across seven Loong generator styles plus dense random.
The screen filters candidates; it does not replace local gate or same-time ladder validation.
Current yardstick per Oct 3 correction is `baselines/Y9_6`; before ladder tests read and restore the server's actual active submission.

## What worked and failed

The Sept 30 research notes were based on earlier notes, not remeasurement or bot-source review.
External Ants/Halite/Tron mechanisms informed hypotheses; their centralised control differs from Loong's separate dragon processes.
Claims that top teams are rule-based, or that rules generalise better than networks, remain **(unverified)**.
The durable programme result is tooling and better measurement, not a demonstrated stronger bot.

| OLD-rules evidence | Lesson retained |
|---|---|
| feedDist 3 → 2: feeds within 2 rose 41% → 94%; own recycling 66% → 75%; gate 17/40 (42.5%) | Mechanism improvement alone does not justify shipping |
| queen250c: self-splits ~36 → 6.8; identity churn 65 → 17; Stockfish ~5 self-splits | Election can improve while feeding/eating remains limiting |
| Stable queen ate ~9 over r250–500 vs Stockfish 34 | Feeding volume and queen intake must be measured separately |
| Imitation network: maze ladder 32–37% → 53–65%; same-time 16/20 vs 6/20 | Readable rules were not the only successful approach |
| Flat-parameter attempts 5/5 failed; five isolated transplants failed | Fit and test in the receiving bot |
| Territory made Dilemma 75% → 0% twice; friendCloser eating ~10× worse; time-aware bodies wins 53% → 34% | Crude constraints can encode useful coordination |
| Schedule S.1: gate 20/40; ladder 4/25 vs control 8/25, Fisher p≈.3 | Small samples do not establish improvement or deterioration |

Historical 32-game panels showed **7–9 pp** optimism bias.
Wilson 95% intervals: **20/40 = 35.2–64.8%**, **17/40 = 28.5–57.8%**, **68/125 = 45.7–62.9%**.
Research power estimates for two-arm ladder tests: about **1,560/387/169/93 games per arm** for **5/10/15/20 pp** effects (normal approximation, α=.05, power=.8).
Thus 25 + 25 is a coarse screen, not evidence of a small gain.
Pre-register mechanism, end metric, and falsifier; retain identical backend, paired seeds, and controls.

## How to rerun

These commands reproduce the historical pipeline, not a NEW-rules promotion claim.
Run from repo root; examples use Git Bash line continuations.
Install Python 3.11+, `unswbc`, `scikit-learn`, `scipy`, `pytest`; `pycapnp` enables bceval.
Keep CSV/learning concurrency ≤4 and games ≤6 when other work may compete for memory.

```bash
python -m rulemine extract --index ladder/scout_fresh/index.json --root ladder/scout_fresh \
  --teams SSS,PPP,Stockfish --decision death --out rulemine_data/death_top.csv -j 4
python -m rulemine extract --index ladder/scout_self/index.json --root ladder/scout_self \
  --decision death --out rulemine_data/death_ours.csv -j 4
python -m rulemine contrast --decision death --top rulemine_data/death_top.csv \
  --ours rulemine_data/death_ours.csv --out rulemine_data/contrast_death.md
python -m rulemine learn --decision death --data rulemine_data/death_top.csv --team SSS \
  --out rulemine_data/death_SSS.json
# Optional learning filters: --label fed_ok --min-pwin 0.4
python -m rulemine codegen rulemine_data/death_SSS.json --out viper_cand/rules_learned.hpp
python -m rulemine.parity REPLAY --side A
python tools/panel_zig.py viper_cand baselines/y8m_active runs/cand --set setB -j 6
python tools/panel_zig.py baselines/s2_gP baselines/y8m_active runs/ctrl --set setB -j 6
python -m rulemine.evalpair runs/cand runs/ctrl
python -m pytest -q tests
```

First copy `viper_s2_rules/` to `viper_cand/`; set `rmDeath=1` there.
For parity use a logging copy (`rmLog=1`, Zig `--debug 1`), require **100%** on every consumed feature, and disable logging before submission.
Repeat matched screen pairs with `--set dev` and `--set live`; use `--set test` only for final checks.
For queen training, extract/learn `--decision queen_move` with its own CSV/report and team; inspect chance/baseline checks before enabling `rmQueen`.
`tools/buildwasm.py BOT_DIR` rebuilds on header changes; unswbc sandbox cache historically keyed only on `main.cpp`.

Historical gP benchmark:
```bash
python tools/tourney.py baselines/s2_gP baselines/y8m_active --maps $(cat ladder/set60b.txt) --judge zig -j 6 --keep-replays ladder/x
python tools/local_index.py ladder/x gP y8m ladder/x_idx
python tools/endgame_len.py ladder/x_idx
```

A 120-game replay batch was about **600 MB**, with indexes/`.pkl` caches adding storage.
Check free disk before/after 20+ retained games; delete disposable replays/caches after results are recorded.
Use `tools/mem_guard.sh MIN_MB` before unattended memory-heavy stages; pre-split large CSVs using `tools/split_by_team.py` before team fan-out.
Farm bundle tooling exists (`pack.sh`, `make_jobs.py`, `run_shard.sh`, `summarize.py`); later instructions keep remote lanes OFF.

## Limits and validation

The implementation does not fully satisfy v2:
- No bed-gap learning/local pearl flux in reconstruction, queen intake budget, nearest-visible-ally features, or remembered-queen BFS travel time.
- No budding, queen-protection, or feeding-goal hooks; budding is only extracted/learnable.
- Queen terms are not gP scoring components and have no feature-parity test.
- No own-queen feed-intake or CPU-peak metric inside evalpair.
- Rate matching is distribution-dependent; no swarm-wide runtime death budget.
- Unknown-map honesty test guards `Geo.step`, rather than withholding the map file for a full replay.
- `toward_allies` became one vote per visible ally (+1 closer, −1 farther); raw distance sums could jump by a map width through portals and dominate fitting.

Tests cover state/result consistency, raw-event labels, memory-limited terrain, synthetic rules, generated C++ vs Python to **1e−9**, bceval symmetry, and identical-game evalpair.
`test_parity.py` uses `tests/data/parity_portals_A.replay`; regenerate after feature/hook edits: logging rules build as A vs V7.12, Portals, seed **3**, debug **1**.
Fixture-dependent tests skip without local replay files; two generated-C++ checks skip without `clang++`.
Commands and reported checks here were consolidated, not rerun.

Before a NEW-rules decision, revalidate reconstruction, queen identity/labels, sprint reach, bceval calibration, and queen-first outcome metrics against the changed engine.
Historical longest-margin and offline agreement cannot certify that decision.

Sources consolidated: RULE_BASED_METHODS.md; RULE_MINING_SPEC.md; README_RULEMINE.md; RESEARCH_METHODS.md; research_new_meta/s2_gQ/README.md; insights.md (top banner and cycle summary); rulemine_data/contrast_death.md; rulemine_data/death_forgottomention.md; rulemine_data/death_PPP.md; rulemine_data/death_SSS.md; rulemine_data/death_Stockfish.md; rulemine_data/lbdeath_3_14159265.md; rulemine_data/lbdeath_chejibt.md; rulemine_data/lbdeath_Cutlery.md; rulemine_data/lbdeath_ddabap.md; rulemine_data/lbdeath_dev_test_1__P.md; rulemine_data/lbdeath_Sponge_Albert_and_Bob_.md; rulemine_data/lbdeath_SSS.md; rulemine_data/lbdeath_Stockfish.md; rulemine_data/lbdeath_WeHaveQuizzes.md; rulemine_data/lbdeath_y.md; rulemine_data/lbqueen_3_14159265.md; rulemine_data/lbqueen_cheji_bt.md; rulemine_data/lbqueen_Cutlery.md; rulemine_data/lbqueen_ddabap.md; rulemine_data/lbqueen_dev_test_1__P.md; rulemine_data/lbqueen_Sponge_Albert_and_Bob_.md; rulemine_data/lbqueen_SSS.md; rulemine_data/lbqueen_Stockfish.md; rulemine_data/lbqueen_WeHaveQuizzes.md; rulemine_data/lbqueen_y.md; rulemine/ module docstrings (__init__, __main__, codegen, contrast, decisions, evalpair, evalstate, extract, features, learn, mapgeo, parity, state). Original files remain unchanged.