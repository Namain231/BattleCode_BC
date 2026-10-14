# League build report

Outcome: 0/8 accepted; 8/8 rejected. Ranking FAILS (2/12 discordant strict pairs, 4 collapsed ties).
Accepted: none.
Rejected: tungtung67, avid coders, Just Keep Swimming, code matters, Jingling Munmin, hm, SSS, forgot to mention.
Built 8 wasm bots; completed 64 fidelity + 160 Sv53 + 8 verification games; no judge/build failures in the final run.
Data, checkpoints, CPU state and replays: F:/BattleCode_data/league_build; decisions: league/index.json.
Shared viper_y96qf rules; wNN=20; per-team 16-channel/32-hidden net (33,649 parameters), 8 CUDA epochs, whole-game holdout.
Six Sv53 loss opponents + two highest peak-rated scout winners; missing scout teams use cached Sv53 opponent wins.

Team | samples / val% | units50 real/local | units100 real/local | first split real/local | Sv53 local / real W/N | CPU M | decision
|---|---|---|---|---|---|---|---|
tungtung67 (566) | 178010 / 63.9 | 12/7.75 | 27/5.5 | 10.5/11.5 | 15/20 / 0/17 | 55.1835 | rejected
avid coders (187) | 147381 / 57.9 | 11/4 | 20/2.5 | 5.5/0 | 16/20 / 6/17 | 55.8162 | rejected
Just Keep Swimming (7) | 130662 / 51.7 | 13/3.75 | 28.5/2.5 | 3/16.5 | 16/20 / 7/17 | 55.4588 | rejected
code matters (844) | 98575 / 54.9 | 11/2.5 | 26/2.5 | 4/25 | 17/20 / 9/17 | 53.7971 | rejected
Jingling Munmin (133) | 89936 / 44.6 | 12.5/8 | 26.5/15 | 0/0 | 16/20 / 0/5 | 56.0565 | rejected
hm (221) | 106599 / 54.5 | 19/10.25 | 40/19 | 0/0 | 17/20 / 0/5 | 57.5938 | rejected
SSS (91) | 122400 / 61.5 | 14.25/4 | 28.5/2.5 | 5.5/27.5 | 15/20 / NA | 55.0939 | rejected
forgot to mention (264) | 112081 / 50.6 | 16/4.75 | 32.5/4 | 5.25/11 | 17/20 / NA | 55.6592 | rejected
Sv53 uses the same Maze/Stripes/Devil/Trophy/Portals schedule for all teams, seeds 1,2, both sides.
Metrics are medians of four map medians; first split excludes never-split games. Per-map counts/values are in state.json.
Acceptance: units100 local/real within [0.75,1.25], with measured league CPU <=66M across every tested game.
Hardest first, local: tungtung67 (75%) < avid coders / Just Keep Swimming / Jingling Munmin (80%) < code matters / hm (85%)
Hardest first, real: tungtung67 / Jingling Munmin / hm (0%) < avid coders (35%) < Just Keep Swimming (41%) < code matters (53%)
Files: tools/league_build.py, league_parity.py, league_finalize.py, README_LEAGUE.md; tools/panel_zig.py CPU capture; league/<team> sources/wasm/index.
Commands (repo cwd): `& C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe tools/league_build.py`
`& C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe tools/league_parity.py 566` (supervisor runs all teams)
`uv run --python 3.11 --with unswbc python tools/panel_zig.py league/team_566 baselines/Y9_6 out/league_chk --maps maze,stripes --seeds 1,2 -j 2`
Verification: 1/8 wins; CPU max league 55.183M; command completed and printed CPU max.
All eight exports passed C++/PyTorch numerical parity and plane-8 audit; individual results: F: league_build/parity/<id>/result.json.
Crash resume: atomic CPU state after every game; atomic aggregate state after map/seed evaluation; streaming replay extraction; max 3 jobs, 3GB RAM/6GiB disk guard.
Remote lanes OFF: Kaggle optional via tools/kaggle_train/run_v6.sh; GitHub Actions/publishing require explicit approval. No LLM in loops.
Limitations: movement-only nets cannot choose splits/feeding/actions; input-builder vs runtime feature parity remains unverified.
Real records use different maps/seeds/opponents and winner-only sampling; 8 fidelity games/team are noisy. Top two have no real Sv53 record.
No submission/activation/promotion. Rejected proxies must not be treated as faithful opponents.
