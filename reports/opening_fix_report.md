IN PROGRESS: opening_fix; resumed 2026-10-07, no accepted fix or ladder recommendation.
Candidate copy viper_y96qo2; viper_y96qo/viper_y96qg/baselines remain read-only.
Saved diagnosis reused; not rerun. Source/checkpoints/manifests: out/opening_fix/.
Original/control closed:26/64 vs39/64; safety50/98 vs59/98 (fresh control reproduced59).
Safety original/control wins:around7/10,australia4/5,islands6/9,maze8/8,stripes14/12,tower0/6,weakhold11/9.
Tower economy/routing loss; Australia/Islands increased wall/self deaths; causal attribution remains unproven.
Open panel is16 games (specified4maps x2seeds x2sides), not28; original7/16,control9/16.
Open units100 map order:around_unsw,australia,islands,maze; original51,21,43.5,17.5;control55,37.5,40,21.5.
| Disabled | Open wins (swing vs original) | Open units100 | CPU M | Closed |
|---|---:|---|---:|---|
| cycle |9/16 (+2)|42,22,49,19.5|64.530|not run|
| queen food |6/16 (-1)|49,21,45.5,20|64.455|planned priority|
| split |7/16 (0)|51,21,43.5,17.5|64.507|not run|
| first-turn separation |8/16 (+1)|40,23,47.5,17|64.435|not run|
| portal |8/16 (+1)|45,22,33,18|64.440|not run|
| unwind |pending|pending|pending|not run|
Six Params switches independently verified by static critic; QBOX/amputation ordering preserved.
Prepared composition: hunger+new-cell stagnation routing (workers/queens), observed split exits, original-option risk/survival fallback.
Composition assertions/syntax PASS; composition build/CPU/game behavior UNVERIFIED.
Commands:uv run --offline --python 3.11 --with unswbc python -B tools/opening_fix.py
Each exact panel command/source/map/opponent hash is persisted in out/opening_fix/state.json and inputs.json.
RAM start guard2200MiB; -j4 idle/-j2 competing judge; low-memory monitoring; disposable WSL cache reclaimed once.
Updated plan: allsixopen (-j2 after sustained<1GiB), allsixclosed (-j4 monitored), then composedclosed64+safety98.
Saved closed64 replay spans6-7min, restoring time for full ablations; safety98 historical50-51min (old jobs unverified).
Final acceptance: safety>=56/98; closed win gains>=2maps and units100 gains>=3maps;CPU<=66M.
Safety looks: historical original98 used for diagnosis; zero new final98 looks. No safety tuning.
No submission/activation/training/remote publishing. Local results provisional (~+-5pp at98 games).
