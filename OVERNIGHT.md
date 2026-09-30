> **29 Sept 19:00 IST: the testing sections below are SUPERSEDED by AGENTS.md §0 (panel tests, rule-core first).** Keep the loop rules (act on own recommendation, park alternatives, idle resources → parked ideas, web research when stuck).

# Overnight loop (29–30 Sept 2026): one checklist per wake-up

Log every tick's outcome as one line in `ladder/overnight_log.md` (IST time, what changed). Keep AGENTS.md §2/§4 and
IDEAS.md current. Use subagents for long investigations or builds to keep the main context small.

1. **ELO bot**: `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` shows `elo_bot`; if dead, restart
   `python -u tools/elo_bot.py --our-sub 9285` (background, output appended to `ladder/elo_bot_stdout.txt`).
   Tail `ladder/elo_log.txt`: note the rating; if the active submission is not 9285 when no A/B test is running,
   re-activate 9285. Read new entries in `ladder/loss_log.txt` and note any new loss pattern.
2. **Kaggle bp-run-1..5**: when COMPLETE, fetch with `bash tools/fetch_kaggle_bp.sh 1 2 3 4 5` (or the loop in
   AGENTS §2) into `ladder/bp_kaggle<i>`. Then Kaggle has free sessions: `python tools/cloud_test.py push`
   (pending: cand_sprint, cand_bud330 of b0929_0124) and use Kaggle for new cloud tests.
3. **Cloud tests**: results in `G:/My Drive/viper_ml/results/t_<batch>_<cand>/worker_log.txt` (Colab) or
   `python tools/cloud_test.py fetch`. Record every verdict in AGENTS §4 and IDEAS.md.
4. **Local CPU** (12 threads; ≤ 10 games in parallel): if no tourney is running, run the next IDEAS.md test.
   Sandbox tests use maze + `maps_gen` maps, both sides.
5. **Build the next idea** when compute is idle (IDEAS.md order; #3 lookahead and #4/#5 better training targets
   are the main bets). A sandbox win must be re-confirmed on fresh maps before the ladder.
6. **Slope collector** alive (`ladder/slope/collect_log.txt`); when ≥ ~3,000 new games: build a dataset from `ladder/slope/index.json` and train a fresh replay prior (v1 recipe), test in-bot.
7. **Ladder** (hourly): leaderboard position and rating; top teams' new submissions (`tools/scout.py`).
   Submit a candidate only after a confirmed sandbox win: `Y.7.12.<n>`, then `tools/ab_test.py`, then re-activate 9285
   unless clearly better.
9. **After 05:40 IST (limit reset)**: relaunch the opening-gap analysis subagent once (IDEAS #11; output `ladder/opening_gap_analysis.md`), one subagent at a time.
8. **Stagnation** (two ticks with no progress, or regressions): web research (several keyword combinations:
   Hungry Geese / Battlesnake / Lux AI writeups, piKL, expert iteration, snake AI search) → add ideas to IDEAS.md.

## Standing instructions (user, 29 Sept 06:40 IST)
- Ladder A/B: upload several builds, launch unranked scrims of each vs the same ~8–10 measurable teams
  (`tools/ab_test.py <subs...> --champion <champ> --teams ...`; pause elo_bot during it), then restore the champion.
- Re-test on the ladder things discarded on sandbox-vs-champion alone: w3, look1, feedr14, v1b, sprint, bud330 (batches of ≤ 4 builds).
- Once a build clearly beats 9285 on the ladder A/B: make it the champion, point elo_bot at it (`--our-sub <id>`), run it aggressively
  (max scrims/ranked challenges within the 60 games/hour quota).
- Compare networks by held-out log-loss on top-team replays, never by accuracy; in-bot results decide.
- (user, 08:10) Log-loss is only a coarse filter: reject a network only if clearly worse (> ~0.01 and consistent across
  eval sets); otherwise it is a candidate. Close candidates go to the ladder as arms of one A/B. Stack ideas into one
  build instead of testing each alone vs the champion; isolate causes only if the stacked build falls.
- (user, 13:15) In loops, take my own recommended option instead of waiting; park the alternatives here.

## Parked alternatives
- (13:15) Finish ladder batch 2 A/B (Y.8nn, Y.9, Y.9c vs champion; 9 of 25 sent) before promoting — parked: Y.8a-n4 promoted on
  sandbox BETTER ×2 + ladder lead; the other arms were already behind. Re-run with `tools/ab_test.py` if the new champion stalls.
- (user, 15:50, all day) Whenever a resource is idle, run a parked idea from IDEAS.md / "Parked alternatives". Aim to combine
  the best parts of everything that tested well. Every few ticks (and whenever stuck or regressing) search online with broad,
  generic keywords (game-AI blogs, competition write-ups, ML articles on our problems: imitation plateau, RL fine-tuning,
  opponent modelling, evaluation); read pages through Chrome when WebFetch can't; log findings in
  research_notes/.../ml_problems_web.md and new ideas in IDEAS.md.
