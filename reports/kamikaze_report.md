# Kamikaze experiment (2026-10-07)
Candidate: viper_y96nk, copied from baselines/Nv30; no submission or baseline edits.
Files: candidate main.cpp; tools/panel_zig.py, kamikaze_{measure,unit,run,report}.py; out/kz_work/unit.cpp; AGENTS.md, insights.md, runner/critic task briefs.
Offline audit uses replay-verified submission IDs 17124 / 16651 / 16106 and exact turn states; opportunities are upper bounds before candidate policy guards.
Paths model wrap, portals, kelp, current occupancy, own-body movement, pearls, and up to two affordable paid steps.
l10: 294/752 games (39.1%) have a chance; fully visible routes in 286 games.
Opportunity rounds/game p50/p90/p99=0/1/5; scout lengths=3/16/26; own queen later dies in 126/294 opportunity games.
sv53: 62/147 games (42.2%) have a chance; fully visible routes in 61 games.
Opportunity rounds/game p50/p90/p99=0/2/5; scout lengths=3/20/25; own queen later dies in 27/62 opportunity games.
sv52: 33/77 games (42.9%) have a chance; fully visible routes in 32 games.
Opportunity rounds/game p50/p90/p99=0/2/3; scout lengths=3/7/20; own queen later dies in 18/33 opportunity games.
Reverse (enemy-initiated): L<=4 dragons ram our queen in 414/976 games; lengths p50/p90/p99=3/3/4, remaining steps=1/1/1; 3 portal routes.
Existing tagged attacks already killed the enemy queen head-on in 367 corpus games; raw opportunities are not all new chances.
Reconstruction errors: {}; excluded missing/identity rows: 3. No replay pickle caches.
Rule ON; paid cap L12; early trades L<=4 unless visible enemy length >=2x scout; with current proof our queen lives, any length from r150.
Critical limit: input has no global queen-life/longest census. Require current ally queen segment; otherwise trade only with every ally fully visible and enemy visible length > their longest.
Unknown own body or intermediate occupancy rejects the ram; search capped at 2048 nodes / 40ms. This misses some true opportunities.
Legacy queen attacks use the same guard while ON. Turning OFF restores Nv30 attack behavior. Chase flag OFF; approach efficacy unmeasured.
Unit: uv run --python 3.11 python -B tools/kamikaze_unit.py (actual C++ decision + engine_sim; ram and four rejection cases PASS).
Measure: uv run --python 3.11 python -B tools/kamikaze_measure.py
Panels: uv run --python 3.11 --with unswbc python -B tools/kamikaze_run.py
Smoke subcommand: tools/panel_zig.py viper_y96nk baselines/Y9_6 out/kz_smoke_current --maps maze --seeds 3 -j 1
98-game subcommands: tools/panel_zig.py BOT baselines/Y9_6 OUT --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j J
BOT/OUT: viper_y96nk/out/kz_panel; baselines/Nv30/out/kz_ctl. Zero-other-judge, C:>=3GiB, RAM>=1800MB; J=1 or 2 (2 requires2500MB), reduced from requested4; exact commands saved in each command.json.
out/kz_smoke_current: 1/2 wins (50.0%); CPU peak 63.741M; rams 0, enemy queen ram-kills 0, own queen deaths 2/2.
out/kz_panel: 36/98 wins (36.7%); CPU peak 65.199M; rams 8, enemy queen ram-kills 8, own queen deaths 90/98.
out/kz_ctl: 42/98 wins (42.9%); CPU peak 65.251M; rams 64, enemy queen ram-kills 64, own queen deaths 90/98.
Fix checks: invalid-build cache, cached-None replay/version invalidation, missing coverage and CPU>66M rejection PASS; shared WSL reservation PASS; independent tooling critique PASS.
98-game rates are provisional: about +/-5 points standard error, approximately +/-10 points at 95%; local fixed-opponent results do not establish ladder strength.
Ram counts use K1 (candidate) and ATK queen-id (Nv30 control); actual same-turn head-on deaths verify kills. Risks: growth/last-longest, hidden state, incomplete routes; current queen IDs/head occupancy prevent decoys/stale targets.
Candidate minus Nv30: -6.1 win-rate points on matched seeds/sides; provisional.
Recommendation: Drop: no local win-rate gain over Nv30; sacrificing growth is not justified by this panel.
Unverified: ladder effect, chase benefit, exact hidden global queen state, and CPU worst case beyond sampled games.
