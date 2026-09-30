# Handover (written 30 Sept 2026, ~15:45 IST)

Team Bhole Chature (id 98), UNSW Battlecode 2026. This file summarises the work since the first big Claude session in
this directory and, in detail, the long session of 29–30 Sept. AGENTS.md is the running handoff (state, tools,
pitfalls); `research_notes/LAB.md` is the shared notebook with the co-scientists. Times are IST.

## 1. Where things stand right now

- **Live (active) submission: champion Y.8m = 11461 "Y.7.12.13"** (source `viper_nn/` = `baselines/y8m`). It is V7.12's
  rule core + the frozen move network n4 **on maze maps only** + three maze-only opening fixes (p2Drone 0.15,
  minerGamma 0.90, blind portal step 2.0). Open maps play exactly like Y.7.12-nn.1 (network off there).
- Rating **~1649** (1671 on 29 Sept evening; drift from autoscrims/incoming ranked games, not from our tests — all our
  tests were unranked). Rank ~113 of ~925. Top teams are ~2030–2120.
- **Nothing has beaten the champion convincingly on the ladder.** No promotion was made.
- **Open decision (user):** the user asked (29 and 30 Sept) to **abandon ML and build on v7.12 (no network)**.
  First real-match data: on the champion's own A/B set (6 teams near our rating, same maps via seed 930) v7.12 (no
  network, sub 8242) scored **5/30 (maze 4/22, open 1/8)** vs the champion **16/30 (maze 15/22, open 1/8)** — but the
  champion's games were 13 h earlier. A **same-time champion re-run** was queued to settle it
  (`ladder/champ_now_vs_AB.txt`), then V.13 on the same games (`ladder/V13_vs_AB.txt`). My recommendation (not yet
  accepted): keep the **frozen** network as a fixed component (no more ML training), i.e. use the champion Y.8m (which
  *is* v7.12 + frozen network on mazes) as the base, and put all new rule work on top of it, map-gated.

## 2. History before this session (from AGENTS.md; details there, §4)

- V6/V7 "Viper" C++ bot line (our rules): V7.5, V7.12 (best rules, "late queen").
- **The one big win: imitation learning** — a move network trained on top teams' replays (v1): Y.7.12-nn.1 (sub 9285)
  beat V7.12 clearly (ladder 24/40 vs 6/40 against strong teams). Everything after that was incremental.
- 20+ further ML attempts (fresher/bigger data, ensembles, TTA, distillation, PPO self-play RL, self-imitation, network
  weight sweeps): offline ≤1.4% accuracy gains (ceiling ~72%: dragons act on memory/sonar the network can't see), no
  ladder gain. Fresh data (n4) + opening fixes gave Y.8a-n4 (SPRT better in the cloud) but it lost open maps on the
  ladder → fixes gated to maze maps → **Y.8m, the current champion**.
- Teammates' lines: vB (vB.17/vB.18, "sovereign vacuum" queen/feeding), S (S.4.7.5/S.4.7.6, grower/feeder protocol,
  authenticated gossip), Nv1.9 (see below). On 29 Sept AGENTS.md moved the dev line to **Y.10 = teammates' vB.17 core
  + n4 + our maze fixes**; most of this session's experiments were built on Y.10 (in hindsight the wrong base).

## 3. This session (29 Sept evening → 30 Sept afternoon), in order

### Infrastructure / process
- Fixed a 240 s per-game timeout in `tools/tourney.py` that silently dropped long open-map games (now 900 s).
- Found and fixed ELO-bot problems: the server **refuses map picks for ranked battles** since ~18:54 29 Sept (ranked =
  5 random maps of all 10), so "test on our best maps, then challenge" was broken (tests 70% → ranked 54%). The bot
  now tests on random maps and needs ≥7/10 over two tests. Then the user asked to **keep the ELO bot OFF** unless the
  ladder situation justifies it (it is off).
- Learned that **each game of a series is played by whichever build is active when that game runs** (a teammate
  activating a build mid-series plays our games). New tools verify every game's build from the replay header.
- Disk: ~85 GB of ML shards / self-play data / replay `.pkl` caches cleared by the user; PyTorch uninstalled; caches
  moved to D: (`XDG_CACHE_HOME=D:\battlecode\cache`, `PIP_CACHE_DIR` on D:). Keep everything on D:.
- New tools (all in `tools/`): `ab_live.py` (ladder A/B; keeps a build active until its games leave the queue),
  `top_scrims.py` (several builds vs the same teams/maps; quota- and autoscrim-draw-safe; replay-verified),
  `ladder_ab_loop.py` (continuous paired ladder A/B with SPRT), `upload_sub.py` (upload without leaving it active),
  `kaggle_panel.py` (panels on Kaggle, or `--where colab` via the Drive job worker; fresh dataset per batch; seeds via
  `--seed-base`), `lightning_panel.py` (Lightning studio; the free studio auto-stops → unreliable), `seq_compare.py`
  (paired SPRT vs stored base games), `giant_profile.py`, `queen_traffic.py`, `feed_delivery.py`, `trap_compare.py`
  (by Codex), `forensics.py` (by Codex; its ally/enemy head-on split is unreliable), `param_mine.py` (by Codex),
  `feed_report.py` (by Codex), `ask_cosci.py` (persistent co-scientist sessions), `build_record.py` (now per map).
- Co-scientists: **Codex** (`codex exec`, model gpt-6-luna; persistent session id in `ladder/cosci/sessions.json`)
  and **agy** (Gemini 3.1 Pro, then Claude Opus 4.6 via agy). agy's quota is **exhausted on all models until ~7 Oct**.
  agy headless needs file-permission allow-rules (set in `~/.gemini/antigravity-cli/settings.json`, project-only).
- Colab worker: `G:/My Drive/viper_ml/colab_worker.ipynb` must be running in a browser tab; jobs in `viper_ml/jobs/`.

### Findings (measured)
1. **Offline panels vs our own/teammates' bots are saturated and misleading** (all candidates 59–62% over ~400 games;
   open maps look like our best there but we lose them on the ladder). Judge only on the real ladder (unranked scrims
   are free; 60 games/hour/team), ideally against the champion's own past games (same teams + maps via seed 930).
2. **vs the top-6 teams: champion 0/30, Nv1.9 3/35.** We are far below the top.
3. **Maze maps are decided in the first 100 rounds by pearl collection** (our lost maze games: 9 units at r100 vs 27
   in wins; top teams' losses look the same). Our army shrinks after r100 on Devil, Queen of Spades, Dilemma.
4. **Open maps are a growth race:** top teams swarm to ~60 units by r300, then consolidate to one giant (units
   60→35→18→7 at r300/350/400/500, longest 7→11→25→48); the giant grows mostly by eating piles dropped elsewhere
   (only ~4 of 78 late feeds are next to it). A team at our level (okbro) keeps a 25–35-long grower from r100–200.
5. **Traps:** on Devil we lose ~12 dragons/game to self-trapping in r0–100; a trap rule (no risk excuse for dead ends
   too deep to bud out of) **halves trap deaths on Devil/QoS** (wall 139→76, self 192→98) but hurts Dilemma/Autarky
   → only useful map-gated.
6. **Deliberate even head-on trades are valuable** (removing them: 52% vs 63%).
7. **Nv1.9 (teammate) = Y.7.12-nn.1 + sonar changes only** (source downloaded to `opponents/nv19` via
   `GET /submissions/:id/download`): mapping probes on unseen maps, lane echoes, weak (not round-bound) signing.
8. **Sonar security:** champion/Y.10/nn.1/vB.17 send plaintext queen gossip (readable/forgeable from public replays);
   S.4.7.5 authenticates. We wrote round-bound authenticated gossip (16-bit SipHash tag + keyed stream).
9. Falsified: "our queen suffocates in her own traffic" (replays: less allied crowding than top teams).

### Candidates tried (all measured; ✗ = not better)
- On Y.10 (vB.17 core + n4): a–k (feed thresholds, S.4.7.5 feed protocol h, fountain sharing i, budding j, compass k,
  portal safety b/d, short-striker c) ✗; h ladder A/B 17 vs 16 (tie); o/o2/o3 top-team consolidation schedule ✗;
  x exploration, s spawn-blocking ✗(neutral); CLA1 trap rule all maps ✗, **CLA1d trap rule Devil/QoS only: ladder
  paired 28 vs 26 of 39 (small edge, undecided)**; CLA2 no even trades ✗✗; CLA3/AGY2/CDX2/CDX3/CDX4 early grower
  (ladder open maps within noise of control); CDX5 maze target patience ✗; **CLA5 contest pearls on mazes: Kaggle maze
  68% vs 62% (gain mostly vs the champion)**; Y.11 = CLA5 + CLA1d + authenticated gossip (never got ladder games).
- On v7.12 (no network), per the user: **V.13** (trap rule Devil/QoS + contest pearls on mazes + authenticated gossip,
  sub 12872), V.13t (12874, trap only), V.13c (12876, contest only): offline maze vs 6 team bots NOT BETTER than v7.12
  (paired 19 vs 24 of 56; v7.12 itself only 28/84 there). V.13d (6x survival-search budget): no effect (search never
  hits its budget). **V.13s** (Codex port of Nv1.9 sonar onto V.13): 10–10 vs V.13 on unseen maps. **V.13f** (Codex's
  coordinated fountain-capture opener on V.13): on Kaggle. **V.13x** (Codex: spare-CPU lookahead): being written.

## 4. Running / queued jobs at handover (check before starting anything; stop what you don't need)

- Ladder: `ladder/run_champ_now.ps1` → champion re-run on the AB set, then V.13 on the AB set
  (`ladder/champ_now_vs_AB.txt`, `ladder/V13_vs_AB.txt`; per-game results in `ladder/top_scrims.jsonl`).
- Kaggle: batch kp0930_1437 (v7.12, V.13, V.13t, V.13c; all maps vs 6 team bots, seed-base 30) and kp0930_1452
  (V.13f): `python tools/kaggle_panel.py fetch --batch <b>` (set PYTHONUTF8=1).
- Colab: batch kp0930_1438 (same four builds, seed-base 40) — only runs while the worker tab is open.
- Codex: writing cand_v13x (spare-CPU lookahead); reply lands in `ladder/cosci/codex_*.md`.
- Stop everything: stop python processes matching `top_scrims|ladder_ab_loop|tourney|seq_compare|ask_cosci` and
  powershell processes running `ladder\run_*.ps1` / `ladder\*queue*.ps1`; then `python -c "import sys;
  sys.path.insert(0,'tools');import ab_live as A;A.activate(11461)"` to make sure the champion is active.
- Idle uploaded test builds (never activate for ranked): 12064 Y.10h, 12129 Y.10h2 (rejected), 12235 Y.10,
  12236–12240, 12261 Y.10o, 12340 CLA3, 12345 CDX2, 12349 AGY2, 12468 CDX3, 12483 CDX4, 12703 CLA1d, 12860 Y.11,
  12872/12874/12876 V.13/V.13t/V.13c. Teammate builds: 12130 Nv1.9, 11445 vB18, 11411 vB.17, 11262 S.4.7.5.

## 5. Recommended next steps

1. Read `ladder/champ_now_vs_AB.txt` (same-time control). If the champion still clearly beats v7.12 on maze maps,
   keep the frozen network (base = Y.8m) and stop ML *training*; otherwise go network-free (base v7.12).
2. Put the map-gated pieces (trap rule on Devil/QoS, contest pearls on mazes, authenticated gossip) and Codex's two
   bigger ideas (fountain-capture opener, spare-CPU lookahead) on the chosen base; test each on the ladder against the
   champion's own past games (`top_scrims.py --teams <same> --seed 930`), not against our own bots.
3. Fewer, bigger bets aimed at the two measured decision points: maze pearls in r0–100; open-map giant in r300–500.
4. Before any promotion: include authenticated gossip; check CPU peak (< ~65M); never leave a test build active.

## 5b. Proposed: learn from loss replays and tune the champion (user's question at handover)
1. Mine losses automatically (`ladder/losses/`, 1,250+ replays + `ladder/loss_log.txt`): per loss find the turning
   point (round where the unit / mass / longest gap opens) and classify our dragons' actions in the ~20 rounds before
   (feed, trap, head-on, out-harvested at a fountain). Existing pieces: loss_report.py, forensics.py, trap_compare.py,
   giant_profile.py.
2. Label AVOIDABLE deaths from the true board (replays show everything): did a safe move exist 1–3 turns before the
   death? Group by map and situation (dead-end pocket, head-on at distance 2, blind portal) -> the parameters involved
   (p1/p2/p2Drone head-on weights, miner risk excuse, deathExtra, minerGamma, enemyCloser...).
3. Tune those parameters per map (map-gated slot in activateMap), 2–3 values each, judged ONLY on the ladder against
   the champion's own past games (`tools/top_scrims.py --teams <same> --seed 930`); keep a value only if it beats the
   champion's result on those games. One parameter per map at a time.
4. Repeat daily as new losses arrive (the ELO bot's loss reports feed step 1).

## 6. Lessons / pitfalls learned this session
- Offline panels vs our own lineage don't predict the ladder; 15-game ladder samples swing ±12 points.
- New uploads go ACTIVE on build: use `tools/upload_sub.py` (re-activates the champion).
- Kaggle: a new version of a shared dataset isn't mounted for many minutes → one fresh dataset per batch; kernels wait
  for the mount.
- `tail -F` monitors leave orphan processes that deadlock "wait until no process matches X" chains; poll files instead.
- PowerShell `*>`/`Out-File` write UTF-16; `Stop-Process` by command-line pattern can kill your own shell.
- A teammate activating builds or sending ranked challenges on the shared account corrupts tests and costs rating;
  coordinate.
