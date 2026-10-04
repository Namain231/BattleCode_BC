# Task league_build. Build a ladder-faithful opponent league, then validate it. Output: out/league_report.md (<= 40 lines).

Why: Y9_6 is a poor local opponent (stuck in closed starts, weak vs the ladder). We need local opponents that reproduce top teams' early economy and tactics.

Do:
1. Read ml/v6/README.md, ml/v6/train_v6.py (--team-cond, --only-teams), viper_b19_v6tc and viper_b19_v6tc0 (team-conditioned bots), research_new_meta/y96_analysis.md, out/opening_census.txt and out/sv53_losses.txt.
2. Choose 6-8 league teams from the scouted data (ladder/scout_v6/manifest_new.csv, manifest_all.csv): include tungtung67 if replays exist, the teams that beat us most, and 2 top-rated teams.
3. Train a team-conditioned net per team (or one net with a team one-hot) on that team's winning games (Kaggle GPU if needed: tools/kaggle_train/run_v6.sh). Build one wasm bot per team under league/<team>/ (copy viper_y96qf; only the net weights and team id change; wNN high enough that the bot follows the net, rules stay as fallback).
4. VALIDATE fidelity: for each league bot play 8 games vs Y9_6 on 4 maps and compare its units@r50, units@r100 and first split round with the real team's replays (tools/opening_census.py). Accept a league bot only if its units@r100 median is within 25% of the real team's. Report accepted and rejected.
5. Record how Sv5.3 (out/sv53_pkg) fares against each league bot (20 games each, tools/panel_zig.py) and compare with its real ladder record against that team. The league is faithful if the ranking of opponents (hardest first) matches.

Constraints: data on F: only; at most 3 parallel jobs (RAM); each bot's CPU peak <= 66M points.
Verify: `uv run --python 3.11 --with unswbc python tools/panel_zig.py league/<team> baselines/Y9_6 out/league_chk --maps maze,stripes --seeds 1,2 -j 2` must complete without crashes and print CPU max.
