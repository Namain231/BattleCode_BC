# Task param_search. Automated search of opening/economy parameters. Output: out/param_search_report.md.

Read out/opening_census.txt, out/sv53_losses.txt, out/farm_report.md and viper_y96qf/main.cpp (struct Params and the opening, split, growth, explore and feed code paths).

Do:
1. Expose 6-12 numeric parameters through a generated header so one build serves many settings (variants = generated params_*.hpp compiled with tools/buildwasm.py). Candidates: first split timing and size, split rules by length and unit count, growth thresholds, PEXPLORE, protectFrom, QFEED/feedFrom, swarm split.
2. Run CMA-ES (or successive halving + SPRT early stopping) using tools/farm_run.sh against the league and Y9_6. Objective = win rate, with units@r100 as a shaping term on closed-start maps. Log every evaluation to out/param_search.tsv. Stop a candidate early at 95% confidence that it is worse than Sv5.3.
3. Promote a final candidate only if it beats Sv5.3 by >= 3 pts with paired seeds on >= 1500 games, CPU peak <= 66M, and the critic passes it.

Never submit. Hand the candidate dir and the report to the user.
