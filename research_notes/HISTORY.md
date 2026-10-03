# Historical research notes moved from AGENTS.md

## What section 4 taught us (15-line summary)

1. The n4 imitation network was the largest measured win; pure rules alone were much weaker on mazes.
2. Fresh top-team replay data improved held-out log loss more than volume or larger models.
3. More network data, ensembles, TTA, extra inputs, and bigger models did not reliably improve play.
4. PPO and network-only self-imitation regressed; copying composite bot moves can double-count rules.
5. Rule fixes plus n4 produced gains; higher network weights and broad network-on-open changes regressed.
6. Maze-only ladder tests missed open-map costs; evaluate the map classes that a change can affect.
7. Small panels saturated and sometimes disagreed with ladder results; use same-time ladder controls.
8. Opening maze losses tracked contested fountain intake, especially Trophy, Devil, and Trauma.
9. Pocket deaths can be the cost of profitable mining; blanket trap avoidance lost.
10. Wreck scavenging tracked winning rather than causing it; three direct scavenging attempts were negative.
11. More feeding often spread pearls across sinks, reduced mass, or failed to grow the final longest.
12. A stable sink and pearl delivery matter more than raw feed count; open-map feeding differs from maze feeding.
13. Late longest-dragon survival and conversion of dominant games were recurring loss mechanisms.
14. Regional compass showed map-specific effects; queen-of-spades enemy-side targets caused collapses.
15. Mechanism metrics and win totals can disagree; inspect every flipped game and every loss before promoting.

## Archived dated history and tried-idea table (verbatim)

The following sections are copied verbatim from the pre-cleanup AGENTS.md.

## 0-prev. Rules + NN direction (30 Sept 16:30 IST)

**Rules + NN.** Rules-only is abandoned: v7.12 without the network scored 4/22 maze games on the ladder where the champion
won 15/22 on the same teams/maps. Base = champion Y.8m (`viper_nn/`, sub 11461). Explore how rules and the network are mixed:
- `cand_mix_a..g` (Codex): weights, rule veto, network on open maps, and more.
- `cand_dual`: separate open-map network `policy_weights_open.hpp`, trained on Kaggle as `open_ft` (init n4) and `open_sc`
  (from scratch) on `ml/data_open` = 150 top-10 open-map wins. Fetch with `tools/kaggle_train.py fetch --name open_ft`.

Test: outside panel = opponents/nick_{arch4,arch3,farm,commit} on slithery_fight, schooltime, portals and trauma, 3 seeds.
Champion 11/96 there. Runs on Kaggle and Colab (batch kp0930_1623) and on the laptop with `tools/seq_compare.py` (paired
SPRT vs `ladder/out_viper_nn_vs_*`). Rules-only V.13 results (below) are kept for reference only.

## 0a. Rules-only V.13 line (30 Sept 15:00, superseded)

**Base = v7.12 with NO move network** (`baselines/v7_12`, ladder sub 8242). No ML. Candidates: `cand_v13*` =
v7.12 + today's positive changes: V.13 = trap rule on Devil/QoS + contest pearls on mazes + round-bound authenticated
queen gossip (subs 12872 V.13, 12874 V.13t trap-only, 12876 V.13c contest-only); V.13d (6x survival budget: no effect,
the search never hits its budget: spare CPU needs NEW computation, e.g. enemy-reply lookahead). Codex is porting
Nv1.9's sonar (mapping probes on unseen maps, lane echoes) -> cand_v13s, and its fountain-capture opener -> cand_v13f.
Tests (all vs the champion's OWN past ladder games = same teams/maps via seed 930: AB set champion 16/30, top-6 set
0/30): `ladder/run_v13_history.ps1` -> ladder/{v712,V13,V13t,V13c}_vs_{AB,Top6}.txt; Kaggle kp0930_1437 + Colab
kp0930_1438 (all maps vs 6 team bots); laptop `ladder/local_v13.ps1` (maze maps, paired SPRT vs v7.12).
Nv1.9 (teammate) = nn.1 + sonar only (opponents/nv19, downloaded via GET /submissions/:id/download).

## 0b. Older process notes (29 Sept evening)

1. **Single line** (superseded by §0): `cand_y10` = teammates' vB.17 rule core + our fixes gated to maze maps + n4.
2. **One test**: `python -u tools/panel.py cand_x` = candidate vs frozen panel (S.4.7.5, vB.17, Y.8m, Y.7.12-nn.1), all 10 maps,
   both sides, ~15 min local. **Never test only vs ourselves.** Log: `ladder/panel_log.jsonl`. Beat Y.10's panel total to advance.
3. **Rule core first**: each change must target a measured loss cause (maze fountains Trauma/Devil, endgame tiebreak vs
   giants, open maps). Networks stay a fixed tie-breaker (wNN 2) until rules plateau.
4. **Ladder only confirms** panel winners: all 10 maps, ELO bot paused during the A/B, then promote + ELO bot on it.
5. Cloud (Kaggle/Colab) = breadth (many candidates at once); laptop = fast panel loop. No self-play SPSA.

## 1. State (29 Sept 2026, 19:00 IST)

- **Active champion: Y.8m** (submission 11461 "Y.7.12.13", source `baselines/y8m` = `viper_nn/`). Rating **1669, rank 113**
  (low 1634 after Y.8a-n4's open-map losses; recovering with the best-map challenge strategy).
  Y.8m = V7.12 rule core + network n4 (`ml/models/n4.pt`, wNN 2, maze maps only) + three opening fixes **on maze maps only**:
  `p2Drone 0.15` (hold ground vs an enemy head at distance 2), `minerGamma 0.90` (keep farming distant fountains),
  blind portal step cost 2.0. Open maps play exactly like Y.7.12-nn.1 (verified identical games).
- **Development line: `cand_y10`** = teammates' vB.17 rule core (fast budding to r220, queen homing r340, full-map feed
  vacuum, protectFrom 280, sonar gossip from r0, n4) + our fixes gated to maze maps. Panel: vs S.4.7.5 12W 5L 3D, vs Y.8m
  10–10. Y.10 and Y.8m are equal; Y.10 is the base because the teammates develop that line.
- **Opponent panel** (`opponents/`, downloaded submissions): `s475` (S.4.7.5, 30–17 on the ladder), `s476`, `vb17` (vB.17),
  `vb18`; plus `viper_nn` (Y.8m) and `baselines/y7_12_nn1`.
- Loss causes (measured): numbers war by r100 is 73% of losses — on maze maps the gap is **pearls eaten** at contested/distant
  fountains (Trophy/Devil centre, Trauma fountain), not splitting (`ladder/opening_gap_analysis.md`); endgame tiebreak vs
  single giants 17%; maze win rates vs teams 20–120 above: Default 44%, Autarky 38%, Trophy 35%, Devil 32%, Trauma 28%.
- Submission names: neutral `Y.7.12.<n>`, bland descriptions (replays and names are public).


---

## 3. Next steps (in order)

0. **Baseline panel Y.10 = 47/80 (59%)** (vs S.4.7.5 15/20, vB.17 11/20, Y.8m 10/20, Y.7.12-nn.1 11/20; weakest maps Trauma 3/8,
   Default 3/8). Earlier panels lost open-map games to the 240 s tourney timeout (now 900 s).
1. Y.10a (adjacentThreat ≤ 2 units on maze + farSight Trauma/Dilemma): panel **46/80 NOT BETTER** (s475 15, vb17 12, Y.8m 9, nn1 10).
   Y.10b (portal landing-cell danger for every dragon, all game): panel **44/80 NOT BETTER** (Portals 3/8 vs Y.10 5/8: too
   broad; retry gated to queen/L ≥ 8 after r300 only). Y.10c panel running (started ~20:00 IST) → `ladder/panel_y10c.txt`:
   `gangSplit()` = length ≥ 5 near an enemy head of length ≥ 4 at distance 2–5 before r340 → keep a 3-long striker at the
   head, the rest leaves as a child; plus findAttack lets length ≤ 3 trade with any enemy ≥ 2 longer. Still checking that
   it fires: 0 GANG-SPLITs in 6 replays (swarm play keeps both sides at length 2–4), so Y.10c effectively tests only the
   findAttack change. Slope collector stopped (ML parked); Colab MCP and Gemini/Codex CLI ideas dropped by the user.
1d. **Live pipeline (22:45 IST 29 Sept)**: local panels one at a time: `ladder/panel_queue.ps1` (f → h → g), then
   `panel_queue2.ps1` (i → j); Kaggle panels (`tools/kaggle_panel.py fetch`, batch kp0929_2214, 2 seeds = 160 games,
   different seeds from local; compare only with its own cand_y10 base). Candidates (all = Y.10 + one idea):
   c 43/80 (short-striker trades: +s475, −others) ✗; e feed any queen ≥ L+2; f e + bud stop r300; g f + stable sink;
   **h = S.4.7.5 endgame protocol on mazes** (feeders ≤ 6, sink = gossiped queen ≥ L+4, stagger 400+id%80, stop 490,
   ≤ 2 feeders near her, die within 2 of her head; bud stop r300 once ≥ 20 units): Trauma vs vB.17 3/3 wins, longest
   13/9/12, mass kept; i fountain yield only to a teammate ≤ 4 from it (S.4.7.5 hotYield); j budding not frozen by
   heads at 2–3 with ≤ 4 units; k macro compass (Codex writing it). Ladder feed report (Y.8m losses, `tools/feed_report.py`):
   6.9 distinct feed targets/game, 21.5% chain feeds, longest-at-r400 died feeding in 21% of games.
   Helpers: agy = Gemini (`ladder/run_agy_*.cmd`, task in `ladder/agy_task_*.md`, read/write files only: headless agy
   can't run commands), Codex (`codex exec -m gpt-6-luna` via cmd stdin; its sandbox has no python: run its tools yourself).
   agy's S.4.7.5 study: `research_notes/s475_vs_y10.md` (verified the feeding part against the source).
   Results (local panel, base Y.10 47/80): f 44 ✗ (QoS/Default 2/8: bud stop regardless of army size hurts);
   **h 49/80** (mixed build: review fixes from agy `research_notes/y10h_review.md` landed mid-panel: feed only with the
   sink visible, a real ≤ 2-step path, full-map homing on mazes) → clean rerun queued (`panel_y10h_final.txt`), then
   **hd = h + d** (`panel_y10hd.txt`). Kaggle: `tools/kaggle_panel.py` now makes a fresh dataset per batch (new
   versions of a shared dataset were not mounted: two batches ran stale). Batches: kp0929_2302 (base cand_y10, valid),
   kp0929_2312 (h, i, j, k): `python tools/kaggle_panel.py fetch --batch <b>` (set PYTHONUTF8=1).
   **Scoreboard 30 Sept 01:05 IST** (local /80 | Kaggle /160): base Y.10 47 | 102 (64%); h 49 | 95/157 (61%);
   i 50 | 91/156 (58%); j 46 | 100/157 (64%); k 50 | running; hi 48 | running (kp0930_0033); c 43, f 44, g 38, hd 39.5
   (Portals 1.5/8: portal avoidance for big dragons cripples them on Portals) ✗. **No candidate beats Y.10 yet**; small
   local edges were luck (i). The panel is built from our/teammate bots and rarely shows the ladder's "3x mass, short
   longest" endgame, so h (the fix for it) goes to a **ladder A/B**: `tools/ab_live.py` (new: keeps the candidate active
   until every game has left the queue, then the champion; verifies each game's build from the replay header).
   Running: Y.10h = submission **12064** "Y.7.12.15" vs champion 11461, teams 522,22,196,534,481,34, 5 random maps
   each (seed 930) → `ladder/ab_live_h.txt`, `ladder/ab_live.jsonl`. New uploads go ACTIVE on build: re-activate the
   champion immediately (done for 12064).
   **Ladder A/B result (01:56 IST, all 60 games verified by replay header): Y.10h 17/30 vs champion 16/30 = tie.
   Open maps 1/8 for BOTH; maze 16/22 vs 15/22.** The panel says open maps are our best (Schooltime 7/8): wrong on
   the ladder. Open-map losses = late collapse with far more mass (Schooltime end 392 mass vs 91, longest 36 vs 40;
   Slithery 223 vs 163, longest 21 vs 45; our r400 longest dies by FEED or crash). → **Y.10h2** (submission 12129
   "Y.7.12.16") = S.4.7.5 feeding on ALL maps (open-map feeders ≤ 10), CPU guards tightened (peak 66M → 60M).
   Its open-maps-only ladder A/B is on hold: a teammate uploaded "Nv1.9" (12130, "probe echo + alt post r300") at
   02:25 and a ranked battle was live, so the champion stays active; don't fight a teammate's test for the account.
   Kaggle hi 91/155 (59%) ✗ (base 64%).
   **Panel is saturated** (all games, 30 Sept 03:00): base 241/400 (60.3%), k 241/392, hk 144/238, h 235/397: equal.
   Only ladder-like tests can guide now. Teammate's "Nv1.9" was active from ~02:56 IST sending RANKED challenges
   (−7, +16, −19, −20); user notified; our ladder tests paused. Local runs stopped by the harness for low memory
   (other apps: Antigravity IDE, 2 Claude sessions, Word, Firefox): don't restart local games without the user's OK.
   Open-map consolidation test moved to Kaggle (`kaggle_panel.py --panel/--maps/--tag`): kp0930_0309 = h2 vs
   cand_y10 + viper_nn, kp0930_0310 = cand_y10 vs viper_nn, portals/slithery/schooltime × 6 seeds (records
   `ladder/cloud_tests/kp_open_*.json`).
   **Result: Y.10h2 ✗✗ on open maps**: vs Y.10 11/36, vs champion 13/36 (control Y.10 vs champion 19/36; Portals
   1–2/12). S.4.7.5's slow staggered feeding (from r400, feeders ≤ 10) is far worse on open maps than our aggressive
   r350 feeding. Keep open-map feeding as is; the ladder's open-map losses need another explanation (e.g. our r400
   longest dying by crash: queen protection). Submissions 12064 (Y.10h) and 12129 (Y.10h2) stay idle; champion 11461.
1f. **30 Sept 07:00–09:00 IST — early GROWER line** (okbro ~1710 keeps a 25–35-long dragon by r100–200 on open maps;
   ours stay 4–8 until r300). Candidates (Y.10 base, open maps only): CLA3 = cand_claude_3 (12340: consensus queen
   never buds/splits from r30), CDX2 = cand_codex_2 (12345: + feed her from r50 once 8 long), AGY2 = cand_agy_2 (12349:
   CLA3 + r80 adjacent feeding + pearl priority), CDX3 = cand_codex_3 (12468: CLA3 + queen pearl value x1.75 before r300).
   Ladder unranked, open maps: vs okbro+usagi (6 games) CLA3 4, AGY2 4, CDX2 2, Y.10 2; vs 5 teams ~1665–1713 (15
   games, seed 3) CLA3 3, AGY2 5, Y.10 pending, CDX3 queued. Offline (vs team bots) CLA3 NOT BETTER (paired SPRT):
   team bots don't punish the missing giant. CLA3s = cand_claude_3s: CLA3 + **authenticated, encrypted, round-bound
   queen gossip** (16-bit SipHash tag replaces the 0xB0C7 header; plays identically) — use for any promotion.
   Other results: CLA1 (trap avoidance) Kaggle 71/119 vs base 76/120 ✗; Y.10o2 40/72 ✗. Tools added:
   `tools/seq_compare.py` (paired SPRT vs stored base games), `tools/kaggle_panel.py --where colab` (Colab worker jobs
   in G:/My Drive/viper_ml/jobs; worker must run in a browser tab), `tools/lightning_panel.py` (works; the studio was
   stopped manually by the user on 30 Sept, it did not auto-stop), `tools/ask_cosci.py` (persistent Codex session; ids in ladder/cosci/sessions.json). **agy quota is
   exhausted on all models until ~7 Oct**; Codex (gpt-6-luna) remains. Shared notebook: research_notes/LAB.md.
1e. **30 Sept 05:00–05:45 IST (user: test vs real opponents and many team bots, not the 4-bot panel; see memory
   testing-approach-sep30)**. Someone activated 12129 (Y.10h2, rejected) ~04:00–05:00 IST: re-activated champion.
   **vs the top-6 teams (unranked, same maps): champion 0/30, Nv1.9 2/25** (`tools/top_scrims.py`, results in
   `ladder/top_scrims.jsonl`). **Top teams' open-map playbook** (`tools/giant_profile.py`, 60 of their wins): swarm to
   ~60 units by r300 (longest ~7!), then consolidate: 35 units r350, 18 r400, 7 r500; longest 11 → 25 → 37 → 48
   (20 at r375, 30 at r429, 40 at r472). We end open-map losses with ~34 units, longest 19 vs 33 (median, 225 losses);
   our r400-longest dies by feeding 46, head-on 46, trapped 33, crash 17. Champion code: protectedQueen() is OFF on
   open maps, feedRadius 10. **Per-map ladder history** (`tools/build_record.py` → `ladder/build_permap.csv`): Slithery
   is our worst map for every build (champion 7/46, nn.1 1/12) while S.4.7.5 is 4/5 there; nn.1 better on Trophy
   (24/41) than the champion (6/21). → **Y.10o** (12261 "Y.7.12.21"): open maps consolidate like top teams (bud stop
   r290, feed/home from r300, whole-map radius). Running: `ladder/open_compare.ps1` (Y.10o and Y.10 vs s475, s476,
   vb17, vb18, viper_nn, y7_12_nn1 on open maps → `ladder/open_cand_y10*_vs_*.txt`); quick scrims 11 builds × 5 maps vs
   Computers (112) → `ladder/quick_vs_computers.txt`. Helpers: Codex critique `research_notes/codex_critique.md`
   (optimise P(longest survives), open-map survival mode, opponent-giant detection), Codex + agy portfolio designs and
   open-map interpretations → `research_notes/portfolio_design_*.md`, `research_notes/openmaps_*.md`.
   All downloads/caches on D: (`XDG_CACHE_HOME=D:\battlecode\cache` set for the user).
1a. **ELO bot OFF (user, 29 Sept 22:00 IST): don't start it without checking the ladder first.** Random-map tests vs
   teams 1700–1720 went mostly 1–4/2–3 (19:10–20:01): we're rated about right, so upward challenges lose Elo and leak replays.
   Only a stronger bot moves the rating.
1c. **Late-collapse root cause (Y.10e/f, panels queued via `ladder/panel_queue.ps1`)**: ladder loss reports: "LATE COLLAPSE /
   TIEBREAK" ≈ 20% of lost games, e.g. Trauma r400 38 units/95 mass/longest 6 vs 2/30/24; our longest often dies by FEED.
   Causes: `tryFeed` needed queen ≥ 10 (mazes) and homing queen ≥ 8, so with everyone at 2–6 nothing merges; budding runs
   to r400 while UNITS < 45; `endFeedFrom` is unused. Y.10e = feed/home into any queen ≥ MY_LEN+2 (≥ 4). Y.10f = Y.10e +
   budding stops at r300. Trauma check (vs vB.17): Y.10e 22 feeds into **nine different queens** with chains (mass 89 → 49,
   longest 9 → 13): feeding needs a stable sink; next: feed only into ≥ MY_LEN+3, never from a dragon being fed.
1b. **Bug found (next candidate `cand_y10b`): friendly head-ons through portals.** Default vs S.4.7.5 (seed 1000, we are A): at
   r350 we had 45 units/127 mass vs their 3/8 and still lost the tiebreak (longest 8 vs 14). After r400 nearly every head-on
   death was us vs us; our L14 queen (id 176) died at r480 when our drone 209 stepped through a portal 20 columns away and
   came out on the queen's head (vision doesn't cross portals; `zoneF` only covers seen adjacent friendly heads). Fix idea:
   no portal step whose exit is within 1 of the gossiped queen cell; queen/big dragons avoid parking with a portal edge at
   the head. Also: when the enemy is down to ≤ 5 units and we lead massively, hunt them (elimination wins outright).
   Measure friendly head-on pairs on a few replays first (NOT a scan of all 1,258 loss replays: that crashed memory).
2. Rule-core candidates, one measured loss cause each, all judged by `tools/panel.py` vs Y.10's total:
   - Trauma/Devil/Trophy fountain control (keep a dragon on the fountain; contest the centre).
   - Endgame vs single giants: detect a giant opponent early, switch to the longest-dragon plan (IDEAS #20).
   - Open maps: panel shows Slithery/Default losses vs S.4.7.5; study S.4.7.5's code (`opponents/s475/`) for what it does there.
   - Ideas from other teams' public repo (IDEAS #12): longest-dragon protection, endgame cash-in, rich-region pull.
3. ML is parked (IDEAS 1–21 are mostly done/neutral): keep n4 as a fixed tie-breaker; don't retrain unless rules plateau.

## 4. What has been tried (all measured)

| Idea | Result |
|---|---|
| Imitation network on top teams' replays (v1) | **the win**: ladder 24/40 vs 8 strong teams (V7.12 6/40), same-time 16/20 vs 6/20 |
| More/fresher data (v1b–v5), bigger nets, ensembles, TTA, distillation, memory plane, prev-turn input, AWR, Q, joint value | offline ≤ +1.4% accuracy (ceiling ~72%: dragons act on memory/sonar we can't see); in play: v1b 19/42 vs champion |
| Team-style networks (Vibing++), pearl gossip, sonar jamming, lane sonar, giant hunt, soft safety | neutral on the ladder A/B (16/30 vs 17/30, 16/30 vs 15/30, 5/30 vs 4/30) |
| PPO self-play RL (6 runs; team-standing reward; KL 0.2–1.0) | worse than imitation: 0.25–0.45 greedy; fine-tuning dips first (PIRLNav) — `--critic-warmup` added, untested |
| Network-only self-imitation (winners' moves, 3,800 games on Colab/Kaggle/Lightning) | network-vs-network even (29/56); **in the bot worse: 16/42** — it learns moves that stand in for the missing C++ safety logic |
| Sprint discipline / feed from 400 / feed radius 14 (sandbox, 40 games each) | 20/40, 17/40, 21/40: noise level |
| Cloud SPRT b0929_0124: feed radius 14 / attack margin 1 | 61/121 (50%), 22/50 (44%): NOT BETTER |
| Network fine-tuned on the full bot's own winning moves (`cand_bp_r1`, 2,100 real-bot games from Colab + Lightning, 50/50 with replays, val acc 76%) | cloud **13/34 (38%) NOT BETTER**: as the research predicted, imitating the composite bot double-counts the heuristic. Kaggle's 2,000 games unused so far. Next: masked/soft targets (IDEAS.md) |
| wNN 3 / 4, log-p floor 0.02; positive control wNN 0 | 29/63, 15/40 (local), 49/99: NOT BETTER; w0 7/23 = sandbox detects big effects |
| 1-ply own-move lookahead over top-3 options, enemies static (`cand_look1`) | local 19/40, cloud 22/50: NOT BETTER; next: enemy replies |
| Fresh top-team networks (held-out log-loss on 451 new games): v1 0.690, n2a (slope data) 0.676, n3 (+upset winners +winners vs us) 0.674, n4 (+v1-era data) **0.670**, n5 (win-margin weights) 0.671, n6 (maze-only) worse | freshness gave most of the gain; volume/variety > filtering |
| Opening fixes alone, cloud vs champion: minerGamma 0.9 (open2) 32/68, blind portal step 2.0 (open3) 16/39 | NOT BETTER in the sandbox; ladder A/B of Y.8 decides |
| **Y.8a-n4** (n4 + p2Drone 0.15 + minerGamma 0.9 + blind portal 2.0) | cloud **31/46 (67%) SPRT BETTER** vs champion; n4 network alone 65/128 (51%) neutral; p2Drone 0.15 alone 92/160 (57%, no decision) — the fixes carry it, with a fresh network. Ladder batch 2 + fresh-map confirm running |
| **Ladder A/B batch 1** (6 measurable teams × 5 maze maps, same time) | **Y.8a (n3 + fixes) 16/30**, sil_r2 13/30, champion 12/30, Y.8b (+wNN 5, adj ≤ 2) 12/30, bp_r1 8/30. Y.8a-n10 cloud SPRT BETTER 80/135 |
| Y.8a-n4 re-confirm on 30 fresh `maps_gen` maps | **47/75 (63%) SPRT BETTER** → champion candidate (submission 11041) |
| Y.9 full stack (n8 + mirror TTA + wNN 100 + fixes + adj ≤ 2) | cloud 11/30 NOT BETTER; isolating: Y.8s (= Y.8a-n10 + adj ≤ 2) on Kaggle, Y.8nn (wNN 100) on ladder batch 2 |
| Y.8s (= Y.8a-n10 + adjacentThreat only with ≤ 2 units) | cloud **88/150 (59%) SPRT BETTER** → adj ≤ 2 is not what sank Y.9; high network weight is the suspect (Y.8b wNN 5 ladder 12/30 vs Y.8a 16/30; batch 2 interim Y.8nn 2/10, Y.9 3/10 vs Y.8a-n4 5/10) |
| **Lesson**: a ladder A/B on maze maps only missed a global change's open-map cost (Y.8a-n4 ranked 21/55, open maps 4/16). Always include open maps (Portals 20, Slithery 21, Schooltime 9) in A/Bs, or gate changes by map type |
| Vs Y.8m (new baseline): Y.8m2 (n10 + adj ≤ 2 on maze) and Y.8m3 (+ farSight Trauma) | cloud 14/36 each: NOT BETTER; isolating n10 alone |
| Vs Y.8m: mirror TTA (Y.8mt), n10 network alone (Y.8m-n10) | 15/38 each, maze+gen only 12/32: NOT BETTER. Y.8m is a local optimum for network swaps/TTA/adj/farSight |
| (process) Maze-only changes must be cloud-tested with `--maps` = maze maps (+ gen): open maps play identically and lock 50% |
| Ensemble Y.8me (n4 + 25% v1, off on Autarky) vs Y.8m | cloud 72/141 (51%), maze+gen 60/117: neutral → ladder A/B on all 10 maps (4 teams) |
| (process) Colab workers can both claim one job (duplicate result folders `… (1)`): results are copies, not replicates | |
| No miner excuse for dead ends too deep to bud out of (`cand_trap1`; ~19 opening DOOMED deaths per lost Autarky game come from one fountain-baited 1-wide dead end, T18,17/T19,0) | sandbox **11/42**, worse on every maze map: the pocket deaths are the price of mining that pays. Devil's DOOMED deaths are mixed: e.g. two of our drones enter one 1-wide corridor from both ends, unseen (corridor longer than vision), both die; idea: corridor right-of-way via sonar/gossip (untested) |
| Earlier V7 logic (late cull everywhere, mass feed from 350 on mazes, stricter mining, stop budding r300 on Autarky, fountain rush) | all worse on the ladder |
| Teammates' vB/v8/vS/S4 builds | regressions (vB.4 35% maze, vB.10 18%); good parts: S.2 sprints 3–10/game vs our 30–56 and a bigger late queen (+21 after r300 vs our +12); vB.4 29 units at r100 vs our 14 |

Why we lose (loss reports, `tools/loss_report.py`): **numbers war by round 300 in ~2/3 of losses** (trapped
drones decide the opening; head-on war rounds 100–300; 6+ units ahead at r100 wins 82%); ~1/3 endgame vs
single-giant opponents (we out-mass them and lose the longest-dragon tiebreak; most feeding pearls never
reach our queen). Win predictor: game state predicts the winner 72% at r50, 79% at r200.

