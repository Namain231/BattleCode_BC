# Ideas backlog

**29 Sept 19:00 IST — new approach (AGENTS §0): rule-core ideas first, judged only by `tools/panel.py`. The ML ideas (#1–#11, #13–#18, #21) are done, neutral or PARKED: do not pick them by default.**
Rule-core ideas to pick next: #12 (public repo tactics), #20 (single-giant detector), #8 (corridor right-of-way), #19 split veto (neutral in sandbox), and new ones from loss analysis.


Sources: AGENTS.md §3–5, loss analysis, research notes in `research_notes/Policy priors and stopping rules/`
(report: `reports/Policy priors and stopping rules.md`). Each idea has a **kill** rule written before testing.
Evaluation rules (from the research): judge only in-bot vs the champion; prefer many `maps_gen` pairs (both sides)
over many seeds; 40 games only detects ≥ ~70% true rates, so a 55% gate passes ~1/3 of null changes: re-test
any sandbox "winner" on fresh maps before the ladder; ≥ 3 properly powered nulls in a direction → park it.

| # | Idea | Why | Test / kill rule | Status |
|---|---|---|---|---|
| 0 | Positive control: `cand_w0` (network off) vs champion | report step 1: can the sandbox see a known ~+300 Elo effect? If w0 isn't clearly worse (≤ 40% within ~200 paired games), the sandbox is too blunt: move testing to a frozen gauntlet of styles | cloud SPRT | **done: w0 7/23 (30%)**: the sandbox sees the network's effect fast |
| 1 | `cand_bp_r1`: network fine-tuned on the full bot's own winning moves (50/50 with replays) | AGENTS §3 step 1 | cloud SPRT vs champion; kill if NOT BETTER | **killed: 13/34 (38%)** |
| 2 | wNN sweep {1, 3, 4} and a log-p floor of 0.02 instead of 1e-3 | `w·log p` = greedy piKL; only w relative to score spread matters; floor stops an overconfident net vetoing a big heuristic edge | local 40 + cloud SPRT; kill each at NOT BETTER | killed: w4 15/40 local, w3 29/63 (46%), floor02 49/99 (49%) cloud. w=2 stays |
| 3 | 1–2 ply lookahead over the 2–3 safe candidate moves (heuristic eval at leaves, prior as PUCT-like bonus) | every competition where ML won had search at play time (Hungry Geese 1st/3rd); we use 25M of 100M | build behind a flag; sandbox + cloud; kill if ≤ 50% after 120 games on maze + gen maps | `cand_look1` built (own 1-ply, enemies static; ~5% of moves change; +0.5–3M CPU): local 19/40; cloud **22/50 (44%) NOT BETTER**: own-move lookahead adds nothing (evaluate() already looks ahead). Next variant: worst case over nearby enemy heads' replies |
| 4 | Masked imitation loss: softmax only over moves passing the C++ safety filter (needs safe-move masks recorded in bot-play data) | causal confusion: the net should not learn safety the C++ already does | offline: accuracy among safe moves; in-bot SPRT; kill if in-bot ≤ v1 | todo |
| 5 | Soft/“improved” targets: π̄ ∝ p·exp(S/λ) over safe moves from the bot's scores (ExIt-style), not the chosen move | ExIt: soft targets +50 Elo at equal accuracy (Hex) | needs the bot to log per-move scores in bot-play; kill if in-bot ≤ v1 | todo |
| 6 | Advantage-weighted instead of winners-only (weight by outcome − value estimate) | winners-only is biased by luck in mirror self-play | as 1 | todo |
| 7 | Enemy-move model: use p_NN on visible enemy heads in the head-on danger logic | Diplomacy uses its BC policy as the opponent model; head-on war r100–300 is 2/3 of losses | CPU: ~18M per enemy evaluated; cap to 1–2 nearest; SPRT | todo |
| 8 | Corridor right-of-way (Devil: two of our drones enter one 1-wide corridor from both ends) | opening DOOMED deaths | sandbox on Devil + gen maps | todo |
| 9 | Late game: bigger queen / single-giant answer, nearest-dragon pearl assignment | ~1/3 of losses are endgame tiebreaks | per AGENTS §5 | todo |
| 10 | Residual RL head (zero-init) on top of `S/λ + log p`, KL to the current bot, critic warm-up | RPL / PIRLNav recipes fix the fine-tuning dip; our PPO was tiny scale | Colab GPU only; kill after 2 runs < 0.5 vs the bot | parked |
| 11 | Opening economy: find where the r0–100 unit gap opens (splits, deaths, pearls) and fix it | numbers war = 73% of logged losses; top teams 25–36 units at r100 vs our ~14 | replay analysis of ladder/losses (9285 games) → 1–3 single-change candidates | analysis stopped at 04:10 (budget); relaunch |
| 12 | From public repo nicked1205/battlecode-unsw-2026 (PRs #1–3): longest-dragon protection (r80+: len ≥ 5 stop voluntary splits, pearls ×2.5); endgame cash-in (r420+: small dragons die 2–4 tiles from a friendly head of len ≥ 6); rich-region pull until r250 | endgame/tiebreak = 17% of losses; copying top ideas is the #1 Battlecode lesson | ladder A/B with the next bot | todo |
| 13 | Network autonomy (Battlesnake winner pattern: the policy picks, search/heuristic only vetoes definite losses): wNN 8 inside the safety class, fresh network | sandbox vs our own champion under-rates this (w3/w4 lost there); needs the ladder | multi-build ladder A/B vs ~10 measurable teams | Y.8b (wNN 5) in A/B batch 1; **Y.8nn (wNN 100: network control, C++ veto only; user's preferred design)** queued as batch 2 |
| 14 | Sample weights by margin: weight each game's samples by how decisive the win was (battle score 9-1 > 6-4; or per-game closeness from final length/units) | user idea; later, only if idle or nothing better | offline NLL then in-bot | n5 (weights 0.5–1.5 by final-mass share): held-out NLL 0.671 vs n4 0.670 → neutral, parked |

| 15 | Conditional clone (Orbit Wars 49th): one net conditioned on teacher one-hot, pin the strongest teacher at play time; style coherence beats blends | our net averages 20 teams' styles | n9 built (pins 6 = Cutlery, 7 = cheji bt) | ladder batch 2 |
| 16 | Include strong teams' LOST games too, and wins vs strong teams (Orbit Wars 2nd filter); then fine-tune on a stricter subset | +1 acc point there | n10 (n4 mix + top teams' 380 lost games) → n10q (fine-tune on wins vs ≥ 1800) | training |
| 17 | Mirror test-time augmentation in C++ (average p over original + mirrored view): +1–2 acc points in Orbit Wars IL; 2× net CPU (~36M) | cheap to stack | in Y.9 (mirror avg over 2 views; peak 56–62M) | ladder batch 2 |
| 18 | Look-ahead planes: roll the known map forward (pearl countdowns / body cells freeing) a few steps as extra input | Orbit Wars 2nd's key feature | needs build_dataset + C++ | todo |
| 19 | Let the network's split probability nudge budding (bud when p(split) is high, hold when low); macro timing learned from replays | StarCraft macro-from-replays; nnProb[4] currently unused | `cand_y8msplit` (veto swarm bud if p(split) < 0.03, maze only); Kaggle maze+gen test | testing |
| 20 | Opponent-style detector for single-giant opponents → switch to the queen/longest-dragon plan earlier | top bots adapt mid-match; endgame tiebreaks = 17% of losses | replay check of giant detection first | parked |
| 21 | Play-time ensemble of two diverse nets (v1 = last week's top teams, n4/n10 = this week's): score += w·mean(log p) or entropy-weighted mixture; needs prefixed weight arrays in C++; if it wins, distil into one net (multi-teacher) | policy ensembles need diversity; ensembles were only judged offline before | built `cand_y8me` (n4 + 25% v1 in log space, off on Autarky: held-out NLL 0.6245 vs 0.6259, v1 hurts Autarky; confidence mix not better); Kaggle vs Y.8m | testing |
| 22 | SPSA tuning of struct Params (Stockfish/fishtest method; Planet Wars bot top 20% via evolved constants): 19 params, θ+ vs θ− on maze + gen maps, local CPU | single-param tests are too noisy; many neutral results today | `tools/spsa.py` (state ladder/spsa_state.json); after 60 iters emit → cloud vs Y.8m (maze) → ladder A/B all maps | running |
| 23 | Stack neutrals: Y.8me (ensemble) + split veto | both neutral in sandbox (51%, 50%) | ladder A/B after Y.8me A/B | todo |
## Done / killed
- `cand_trap1` (no miner excuse for too-deep dead ends): 11/42 — killed (AGENTS §4).
- Cloud b0929_0124: feed radius 14 (61/121), attack margin 1 (22/50) — NOT BETTER.
