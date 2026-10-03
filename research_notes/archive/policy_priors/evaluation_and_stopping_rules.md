# Evaluation methodology for game-playing bots, and stopping rules for research directions

Context: UNSW Battlecode 2026 team; candidate vs champion in a sandbox (40–120 games, maps × both sides), Bernoulli SPRT, then same-time ladder A/B (e.g. 16/30 vs 17/30). Draws are essentially absent in this game (the tiebreak is longest dragon, then total length), which simplifies the chess formulas: with draw ratio d = 0, normalized Elo = logistic Elo and the per-game SD of the score is 0.5.

Numbers marked "(derived)" are computed from the cited formulas and are not quoted from a source.

## 1. Fishtest/SPRT methodology: bounds, normalized Elo, pentanomial pairs, expected games, two-stage testing

### Takeaway
Fishtest uses a GSPRT in *normalized Elo* (nElo). Nearly all its game-count formulas reduce to one rule: **expected games ≈ 1,000,000 / (nElo1 − nElo0)² in the worst case, with α = β = 0.05.** With no draws, nElo = logistic Elo. Stockfish-scale bounds ([0, 2] nElo, ~260k games) do not fit a team that can afford 100–400 games. That budget only resolves effects of roughly 50–100 Elo (a 57–64% win rate). Pairing each map across both sides (the pentanomial model) is the cheapest variance reduction on offer, provided the pair is analysed as a unit.

### Cited Findings
- **Parameters.** SPRT has four: Elo0 (H0), Elo1 (H1), α (Type I) and β (Type II). The test runs until the log-likelihood ratio (LLR) crosses a bound set by α and β. — [Chessprogramming wiki: SPRT](https://www.chessprogramming.org/Sequential_Probability_Ratio_Test)
- **Recommended bounds by engine strength** (gainer / non-regression): Stockfish LTC [0.5, 2.5] / [−1.75, 0.25]; Stockfish STC [0, 2] / [−1.75, 0.25]; top-30 engines [0, 3] / [−3, 1]; top-200 engines [0, 5] / [−5, 0]; other engines [0, 10] / [−10, 0]. Weaker engines use wider bounds because real gains are larger. — [Chessprogramming wiki: SPRT](https://www.chessprogramming.org/Sequential_Probability_Ratio_Test)
- **Fishtest two-stage process.** STC runs at 10+0.1 s and LTC at 60+0.6 s. LTC is run "only if STC passes", which saves expensive games on patches that fail cheap screening. Simplifications get the relaxed non-regression bounds SPRT(−1.75, 0.25) because "the code under test is simpler/smaller than the original". The same page mentions SPRT(0, 3.5) for functional changes. Bounds have changed over time, and the chessprogramming table gives [0, 2] for STC. — [Fishtest wiki: Creating my first test](https://github.com/official-stockfish/fishtest/wiki/Creating-my-first-test)
- **Normalized t-value and normalized Elo (Van den Bergh).**
  - t_n := (μ − 1/2) / σ_pg, where μ is the expected score and σ_pg is the SD of the score per game.
  - In the pentanomial case, σ_pg is the SD of the pair-outcome distribution (pairs scored 0, 1/4, 2/4, 3/4, 1) multiplied by √2.
  - The observed t̂_n ~ N(t_n, 1/N) for N games.
  - Normalized Elo is e_n := C·t_n, where C = 800/ln 10 ≈ 347.43.
  - With a balanced book, e_n ≈ e_logistic / √(1 − d), where d is the draw ratio. At d = 0, "normalized Elo and logistic Elo coincide". A normalized Elo of 5 equals logistic Elo 4.18 at 30% draws and 3.54 at 50% draws.
  - Source: [Van den Bergh, Comments on Normalized Elo (PDF)](https://cantate.be/Fishtest/normalized_elo_practical.pdf)
- **Expected SPRT duration** (α = β = 0.05, worst case, true Elo midway between H0 and H1):
  - T = D / (e_n1 − e_n0)², with D = C²·ln(19)² ≈ 1,046,535 ("close to 1000000 … sufficiently accurate for back of the envelope calculations").
  - Table: width 1 → 1,046,535 games; 2 → 261,634; 3 → 116,282; 4 → 65,408; 5 → 41,861; 6 → 29,070.
  - If the true value equals H0 or H1, the numerator is D′ = 9C²·ln(19)/5 ≈ 639,770.
  - General form: T = T(h)/w², with w = t_n1 − t_n0, b = ln((1 − α)/α) and T(0) = b².
  - Source: [Van den Bergh (PDF)](https://cantate.be/Fishtest/normalized_elo_practical.pdf)
- **Usable LLR approximation, valid for both the trinomial and pentanomial models:** LLR ≈ (N/2)·ln[(1 + (t̂_n − t_n0)²) / (1 + (t̂_n − t_n1)²)], or roughly (N/2)(t_n1 − t_n0)(2t̂_n − t_n0 − t_n1).
  - Early in a test σ̂ ≈ 0, so the LLR must be regularised. Clamp LLR/N to ±(t_n1 − t_n0)/2.
  - What Fishtest calls an SPRT "is strictly speaking a GSPRT": unknown nuisance parameters are replaced by their maximum-likelihood estimates.
  - Source: [Van den Bergh (PDF)](https://cantate.be/Fishtest/normalized_elo_practical.pdf)
- **Pentanomial model.** It scores pairs of games from the same opening with colours reversed, giving 5 outcomes (LL, LD, DD/WL, WD, WW). This "leads to a substantial saving of testing resources compared to the trinomial model". — [Fishtest Mathematics](https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-Mathematics.html)
- **Evidence for pairing.** Across ~150 LTC tests, the white and black scores within a pair had correlation ≈ −0.15, which is statistically significant. So "the correct pentanomial variance is about 15% smaller than the naive trinomial variance … we could use 15% fewer games". — [fishtest issue #348](https://github.com/official-stockfish/fishtest/issues/348)
- **Unbalanced openings.** With highly correlated pairs, unbalanced openings become efficient under pentanomial variance at draw rates above ~60%. The trinomial–pentanomial gap also estimates the RMS bias of the opening book. — [TalkChess: Fixed nodes games and the pentanomial model](https://www.talkchess.com/forum3/viewtopic.php?t=69407) (search-snippet level; thread not read in full)
- **Classical match statistics.**
  - Score to Elo: E = 1/(1 + 10^(−Δ/400)), so Δ = 400·log10(E/(1 − E)).
  - Likelihood of superiority: LOS = Φ((W − L)/√(W + L)). Draws do not enter LOS.
  - The pentanomial model with probabilities (p0, p½, p1, p3/2, p2) handles unbalanced openings and within-pair correlation.
  - Source: [Chessprogramming: Match Statistics](https://www.chessprogramming.org/Match_Statistics)
- **Tools.** OpenBench, cutechess-cli and fast-chess implement SPRT. fast-chess supports pentanomial statistics "for faster completion". There is also an SPRT calculator at tests.stockfishchess.org/sprt_calc. — [Chessprogramming: SPRT](https://www.chessprogramming.org/Sequential_Probability_Ratio_Test)
- **Accepting H0 is weaker than it sounds.** It "only means the SPRT failed to demonstrate the expected gain". A genuinely neutral patch accepts H0 as reliably as a regression does. — [coeusyk/chess-engine issue #231](https://github.com/coeusyk/chess-engine/issues/231)
- **True effect between the bounds.** With Elo0 = 0 and Elo1 = 10 but a true difference of 4, the test runs long and accepts H0 in more than half of cases. — search summary of [Chessprogramming SPRT](https://chessprogramming.org/Sequential_Probability_Ratio_Test) / [OpenChess "How (not) to use SPRT"](http://www.open-chess.org/viewtopic.php?f=5&t=2477) (not verified verbatim)

### Inferences
- **Translate SPRT bounds into this game (derived; d = 0, σ_pg = 0.5, α = β = 0.05).** Win-rate targets: 52.5% ≈ 17 Elo, 55% ≈ 35 Elo, 60% ≈ 70 Elo, 65% ≈ 108 Elo.

  | Bounds (logistic Elo) | Win-rate target | Worst-case games | Games if truth = H0 or H1 |
  |---|---|---|---|
  | [0, 35] | 50% → 55% | ≈ 850 | ≈ 520 |
  | [0, 70] | 50% → 60% | ≈ 215 | ≈ 130 |
  | [0, 100] | 50% → 64% | ≈ 105 | ≈ 65 |

  - Cross-check: w = 0.1/0.5 = 0.2 and b² = ln(19)² ≈ 8.67, so T = 8.67/0.04 ≈ 217. At Elo differences this large the small-Elo linearisation is only approximate.
  - Relaxing to α = β = 0.1 (b = ln 9) cuts every figure to about 56% of these values: [0, 70] then needs ≈ 120 games worst case.
- **Two-stage testing for this team (analog of Fishtest STC → LTC).**
  - Stage 1: a cheap local screen of ~40–60 games with wide bounds, e.g. [0, 100] Elo, or α = β = 0.1–0.2. Its job is to kill obvious losers fast.
  - Stage 2: a cloud SPRT with [0, 50–70] Elo on ≥ 200 games, including unseen `maps_gen` maps.
  - Stage 3: the ladder A/B.
  - Treat stage-2 H0 acceptance as "not proven", not "harmful". For simplifications or cheaper code, use non-regression bounds such as [−50, 0].
- **Pairing in this game.**
  - Define the pair unit as (map, seed) played with sides swapped. Without draws, pair outcomes are 0, ½ or 1 (LL, split, WW). σ_pg,pair = √2 × SD(pair score), and Var(pair sum) = 2σ²(1 + ρ).
  - Strong map and side effects make split pairs common. That pushes ρ negative and cuts variance, possibly by much more than chess's 15%.
  - If the candidate systematically wins or loses a whole map from both sides (a map × bot interaction), ρ is positive. The naive Bernoulli SPRT then *understates* variance and over-accepts.
  - The team can measure ρ directly from existing tourney logs. It should run the SPRT on pair scores, i.e. Van den Bergh's formula (4.14) with pentanomial σ.
- **Map sampling.** With few maps, "is A better?" is really "is A better on these 10 maps?" The effective sample size for generalising to *new* maps is closer to the number of maps than the number of games. Many random maps (`maps_gen`), each played as one pair, generalise better than many seeds on few maps.
- **Repeated seeds.** If games are deterministic, repeating a seed adds zero information. Vary seeds or maps.

### Gaps
- No OpenBench- or Lc0-specific documentation was retrieved. That Lc0 uses cutechess-cli SPRT with similar bounds is unverified here.
- The bias of the Elo *estimate* after an SPRT stops early is not covered (Fishtest reports a bias-corrected estimate, but no source was retrieved). The effect is that estimates from runs that stopped early by passing are inflated.

## 2. Detectable effect sizes at 40, 100 and 400 games; α/β choices; early stopping; multiple comparisons

### Takeaway
The team's "±8% at 40 games" is **one standard error**. The 95% interval is about ±16%. At 40 games only a real win rate of about 70% or more is reliably detectable, so "noise level" is the expected verdict for most honest tweaks. Testing many tweaks at small N and promoting the best guarantees winner's-curse regressions.

### Cited Findings
- **Standard error scaling.** t̂_n ~ N(t_n, 1/N), so the resolution in the score scales as σ_pg/√N, with σ_pg = ½√(1 − d). — [Van den Bergh (PDF)](https://cantate.be/Fishtest/normalized_elo_practical.pdf)
- **Continuous monitoring.** Peeking at a fixed-N test and stopping when it looks significant is result-dependent multiple testing that inflates Type I error. The SPRT and Bayesian sequential designs are built for continuous monitoring. — [Deng et al., Continuous Monitoring of A/B Tests without Pain (arXiv 1602.05549)](https://arxiv.org/pdf/1602.05549)
- **Testing in Fishtest's own words.** "SPRT will automatically run as many games as needed until the test reaches a statistically definitive result." — [Fishtest wiki: Creating my first test](https://github.com/official-stockfish/fishtest/wiki/Creating-my-first-test)
- **Overfitting a reused validation set.** Kaggle grandmasters note that even a good cross-validation (CV) setup overfits if "you use it a lot with same splits over and over again". Tuning to the public leaderboard leads to a private-leaderboard "shake". — [NVIDIA: Kaggle Grandmasters Unveil Winning Strategies](https://developer.nvidia.com/blog/kaggle-grandmasters-unveil-winning-strategies-for-data-science-superpowers/); [Towards Data Science: How to become a Kaggle Competitions Grandmaster](https://towardsdatascience.com/how-to-become-a-kaggle-competitions-grandmaster-9d77431c5b7d/) (search-snippet level)

### Inferences (all derived; d = 0)
- **Resolution by N.** SE = 0.5/√N.

  | Games N | 1 SE | 95% half-width | Detectable at 80% power, two-sided α = 0.05 | Same, one-sided α = 0.05 |
  |---|---|---|---|---|
  | 40 | 7.9% | 15.5% | ≥ 72% (~165 Elo) | ~69.6% |
  | 100 | 5.0% | 9.8% | ≥ 64% (~100 Elo) | ~62.4% |
  | 400 | 2.5% | 4.9% | ≥ 57% (~49 Elo) | ~56.2% |

  - Minimum detectable effect ≈ (z_α + z_β)·0.5/√N; two-sided at 80% power gives 1.4/√N.
  - The one-sided column uses 1.24/√N.
  - Detecting 55% vs 50% needs ≈ 620 games (80% power, one-sided) or ≈ 850 (SPRT worst case).
- **Reading the team's results.** 20/40, 17/40 and 21/40 are all within 1 SE of 50%. They cannot rule out a true effect of ±10–15%. "Noise level" means *not measured*, not *no effect*.
- **Recommended α and β.**
  - Screening stage: α ≈ 0.1–0.2 with β ≈ 0.1 is acceptable, because false positives are caught later.
  - Promotion gate: α ≤ 0.05 (Fishtest uses 0.05/0.05), because a false promotion costs ladder rating.
  - Asymmetric costs favour a higher α early and a lower α late.
- **Multiple comparisons.**
  - With k null tweaks each tested at α = 0.05, P(≥ 1 false pass) = 1 − 0.95^k: 40% at k = 10, 64% at k = 20.
  - Winner's curse: the best of k null tweaks shows an expected excess of about E[max of k N(0,1)] × SE. At k = 10 that is ≈ 1.54 × 7.9% ≈ +12%, so the best of 10 neutral 40-game tests looks like ~62%.
  - The fix is to **re-test the winner on fresh games** (regression to the mean shows up immediately), use sequential tests, and count every variant tried.
- **The "gate at ≥ 55% over 40 games" rule.** Under the null (p = 0.5), P(≥ 22/40) ≈ 32%. It admits about one in three neutral changes, so it is a screen, not a gate.

### Gaps
- No source was found that gives an explicit false-positive audit of Fishtest (e.g. the fraction of STC passes that fail LTC). Such data would calibrate the value of two-stage testing.

## 3. Self-play overfitting and non-transitivity: why sandbox gains fail to transfer, and fixes

### Takeaway
Strength in real games has a large cyclic (rock-paper-scissors) component alongside the transitive one. A gain against your own previous version can be an exploit of that version and need not be general strength. Evaluate against a **diverse, weighted pool**: past champions, teammates' styles, and imitations of ladder opponents. Where the pool is redundant, weight opponents with Nash-style weights and not a plain average.

### Cited Findings
- **"Spinning tops".** Real games (Tic-Tac-Toe, Go, StarCraft II among 9 studied) share this geometry. The vertical axis is transitive strength. The radial axis is cyclic, non-transitive structure, largest at medium skill. "Populations of strategies are necessary for training of agents", and the population size needed depends on the game's structure. — [Czarnecki et al. 2020, Real World Games Look Like Spinning Tops (arXiv 2004.09468)](https://arxiv.org/abs/2004.09468)
- **Elo under non-transitivity.** Elo is problematic when A > B > C > A, and evaluation is biased by redundant easy tasks or weak agents. Nash averaging "automatically adapts to redundancies in evaluation data, so that results are not biased by the incorporation of easy tasks or weak agents", which enables "maximally inclusive evaluation". — [Balduzzi et al. 2018, Re-evaluating Evaluation (arXiv 1806.02643)](https://arxiv.org/abs/1806.02643)
- **AlphaStar on self-play.**
  - "An agent playing against itself may keep improving, but it also may forget how to win against a previous version of itself."
  - Strategies cycle rock → paper → scissors → rock.
  - The fix was a league of main agents plus exploiters that "focus on helping the main agent grow stronger by exposing its flaws".
  - Source: [DeepMind blog: AlphaStar Grandmaster level](https://deepmind.google/blog/article/AlphaStar-Grandmaster-level-in-StarCraft-II-using-multi-agent-reinforcement-learning)
- **AlphaStar league mechanics.**
  - Main agents train with prioritized fictitious self-play (PFSP) against past versions, sampled in proportion to how hard they are.
  - Main exploiters train only against the current main agent.
  - League exploiters best-respond to the whole league.
  - Source: [Vinyals et al. 2019 notes (spinningup-workspace)](https://github.com/RobertTLange/spinningup-workspace/blob/master/08_Scaling_RL/02_2019_Vinyals.md); secondary source.
- **Head-to-head vs gauntlet.** For normalized-Elo resolution, "in testing against a third party engine, it is common wisdom that one needs 4 times the number of games to attain the same resolution". — TalkChess thread on opening-suite efficiency, surfaced by search: [TalkChess t=64358](https://talkchess.com/viewtopic.php?t=64358). Attribution is from a search snippet and not verified in the thread.

### Inferences
- **The team's own data fit this picture.** In the bot, network-only self-imitation scored 16/42 while network vs network was even. Self-play gains "often don't transfer". Both match the cyclic component: the sandbox measures A vs one point (the champion) on the top, while the ladder is a mixture over many opponents.
- **Practical fixes, in order of cost.**
  1. A fixed **gauntlet panel**: the champion plus 3–6 frozen styles (older V7.x, teammates' vB/S.2 builds, a swarm/early-aggression bot, a single-giant bot like Trauma), weighted by how often each style appears on the ladder.
  2. Report per-opponent and per-map results next to the pooled result. A gain concentrated on one opponent is a red flag.
  3. Weight by Nash averaging or by the ladder's opponent mix. This stops redundant weak opponents from inflating the score.
  4. Use unseen random maps, because the next phase uses new maps.
- **Budget cost.** Gauntlets need about 4× the games for the same resolution on a head-to-head-equivalent effect. Reserve the panel for stage 2/3 and use head-to-head vs the champion as the cheap stage-1 screen.

### Gaps
- No quantitative measure of Battlecode-specific non-transitivity was found. The team could estimate it from its own cross-table of builds (for example, with a Nash-clustering-style analysis).

## 4. Elo ladder dynamics: K-factor, confirming a real improvement, live A/B design

### Takeaway
A single ladder A/B of 30 vs 30 battles has a standard error of about 13 percentage points on the difference. It can confirm only very large gains (≥ 25–30 pp). Ladder rating itself drifts by tens of Elo from noise at K = 24. Treat the ladder as a final sanity or regression check, powered with paired designs. It is not a place to discover 5% edges.

### Cited Findings
- **Score–Elo relation.** E = 1/(1 + 10^(−Δ/400)). — [Chessprogramming: Match Statistics](https://www.chessprogramming.org/Match_Statistics)
- **Update rule on this ladder** (from the team's documentation, AGENTS.md §5): change = K·(score − expected). K starts at 96 for new code and falls by 7.2 per ranked battle to 24. — internal project doc, no URL.

### Inferences (derived)
- **Rating noise at a fixed true strength.**
  - Linearise E around the true rating: slope c = ln10/1600 ≈ 0.00144 per Elo. The update is then an AR(1) process with stationary variance ≈ K·Var(S)/(2c).
  - For single-game battles (Var(S) = 0.25) at K = 24, that gives an SD of about 46 Elo.
  - If a battle averages about 10 games (Var(S) ≈ 0.025), the SD is about 15 Elo.
  - So a rating move from 1664 to 1711 over two days is within noise unless battles are multi-game. The per-build win rate (build_record) is a better metric than rating.
  - The high initial K (96) makes early rating after a resubmission very noisy.
- **Two independent arms of n battles.** SE of the difference = √(2·0.25/n): 12.9 pp at n = 30. Detecting a 10 pp difference (80% power, α = 0.05) needs ≈ 390 battles per arm.
- **Paired A/B.** Same opponent, same maps, same time, both builds. Analyse with a paired or McNemar-style test: only discordant pairs (A wins and B loses, or vice versa) carry information. If most pairs are concordant, variance drops sharply. `ab_test.py` already pairs opponents and maps, so it should report the discordant counts and an exact binomial p-value on them.
- **Decision rule for the ladder.**
  - Promote only if (a) the sandbox SPRT and panel pass and (b) the ladder paired test is not significantly worse, i.e. a non-regression check.
  - Do not require the ladder to prove superiority; at these sample sizes it cannot.
  - Keep the champion active before autoscrims, as already done.

### Gaps
- No public documentation of the UNSW ladder's matchmaking or battle scoring (games per battle, how scores aggregate) was found. The noise estimate above depends on it.

## 5. Stopping and continuation rules for research directions under a compute/time budget

### Takeaway
Treat each research direction as a sequential test at the portfolio level:
- Pre-register a kill criterion and a time-box, e.g. "two full-power tests with no stage-2 pass, or 3 days".
- Rank directions by (P(success) × expected Elo gain) / hours.
- Ignore sunk cost.
- Keep a small exploration share for high-variance ideas.
- Near the deadline, shift from exploration to low-risk robustness and regression checks.

### Cited Findings
- **Hamming.** "It's not the consequence that makes a problem important, it is that you have a reasonable attack." He also reserved about 10% of his time ("Great Thoughts Time", Friday afternoons) for strategic reflection on what matters. — [Hamming, You and Your Research](https://www.cs.virginia.edu/~robins/YouAndYourResearch.html)
- **Schulman.** Recommends *goal-driven* over idea-driven research for most people. Idea-driven work risks spending "months on a 10% tweak with no larger target of value", and breakthroughs from it need "an exceptionally deep understanding … and a perspective that diverges from the rest of the community". — [Schulman, An Opinionated Guide to ML Research](http://joschu.net/blog/opinionated-guide-ml-research.html) (page fetch failed; quotes via [hardmaru on X](https://twitter.com/hardmaru/status/1223057947237875712?lang=en-gb) and [braindump summary](https://braindump.jethro.dev/posts/an_opinionated_guide_to_ml_research/))
- **Kaggle grandmasters.**
  - "The biggest lever in any competition is the number of high-quality experiments you can run." Plan experiments and make iteration faster through sampling or better resource allocation.
  - Replicate the validation setup "as closely as possible to the leaderboard setup", so that many experiments can be run without overfitting the leaderboard.
  - Sources: [NVIDIA: Kaggle Grandmasters Unveil Winning Strategies](https://developer.nvidia.com/blog/kaggle-grandmasters-unveil-winning-strategies-for-data-science-superpowers/); [NVIDIA: Kaggle Grandmasters Playbook](https://developer.nvidia.com/blog/the-kaggle-grandmasters-playbook-7-battle-tested-modeling-techniques-for-tabular-data)
- **Fishtest's staged process** (cheap STC before expensive LTC) is itself a resource-allocation rule: most patches die cheaply. — [Fishtest wiki](https://github.com/official-stockfish/fishtest/wiki/Creating-my-first-test)

### Inferences (reasoned frameworks; not sourced to a specific study)
- **Expected value per hour.** Score each direction as EV/h = P(pass stage 2) × expected Elo if it passes × P(it transfers to the ladder) / hours to a decisive test. Update P after each test in a Bayesian way; a Beta prior on "this family of ideas works" is enough. Applied to the team's record:
  - Imitation learning produced the one big win.
  - Six PPO runs and more than 10 network variants were all ≤ neutral.
  - Most single-parameter tweaks were noise.
  - The posterior for "another NN variant" and "another parameter tweak" is now low. Game-logic fixes aimed at the diagnosed loss causes (trapped drones in the opening, the r100–r300 numbers war, the single-giant endgame) have direct evidence behind them.
- **Bandit framing.** Directions are arms and each full test is a pull.
  - Thompson sampling or UCB favours arms with high uncertainty *and* plausible upside. Once an arm has 3+ full-power null results, its upper bound falls below alternatives, so stop pulling it.
  - Arms whose outcomes are mostly unmeasured (40-game "noise" tests) have not really been pulled. Either power them properly or drop them; do not count them as evidence either way.
- **Pre-registered kill criteria.** Before starting, write down:
  - the hypothesis;
  - the metric (stage-2 SPRT result or panel win rate);
  - the budget (games, GPU-hours, calendar days);
  - the kill rule, e.g. "stop if SPRT [0, 70] accepts H0 twice for the best variant, or if offline accuracy gains are below 1% after N experiments";
  - the continue rule, e.g. "continue only if a stage-2 pass occurs".

  This prevents sunk-cost drift and garden-of-forking-paths re-analysis.
- **Time-boxing.** A direction gets a fixed slice (for example, 2–3 days or a fixed number of cloud sessions). A direction that has not produced a decisive positive test by the end of its box is parked with notes and not extended.
- **Rigor vs speed near a deadline.**
  - Early: run many cheap, wide-bound screens and accept some false positives.
  - Late: freeze the exploration share, and require non-regression on the panel and unseen maps for any change.
  - A false promotion just before the deadline cannot be corrected, so α should fall as the deadline nears, while β (missing a small gain) can rise.
  - Resubmitting the champion is always a valid fallback.

### Gaps
- No empirical study was found that quantifies research-direction stopping rules (e.g. the optimal time-box length) for competition teams. The frameworks above are standard decision-analysis reasoning, not measured results.
- Karpathy's "Recipe for Training Neural Networks" was not retrieved in this session.
- Specific Kaggle-winner interviews on "when to abandon ML for heuristics" were not found.
