# Task param_search. Automated search of opening/economy parameters. Output: out/param_search_report.md.

Read out/opening_census.txt, out/sv53_losses.txt, out/farm_report.md and viper_y96qf/main.cpp (struct Params and the opening, split, growth, explore and feed code paths).

Do:
1. Expose 6-12 numeric parameters through a generated header so one build serves many settings (variants = generated params_*.hpp compiled with tools/buildwasm.py). Candidates: first split timing and size, split rules by length and unit count, growth thresholds, PEXPLORE, protectFrom, QFEED/feedFrom, swarm split.
2. Run CMA-ES (or successive halving + SPRT early stopping) using tools/farm_run.sh against the league and Y9_6. Objective = win rate, with units@r100 as a shaping term on closed-start maps. Log every evaluation to out/param_search.tsv. Stop a candidate early at 95% confidence that it is worse than Sv5.3.
3. Promote a final candidate only if it beats Sv5.3 by >= 3 pts with paired seeds on >= 1500 games, CPU peak <= 66M, and the critic passes it.

Never submit. Hand the candidate dir and the report to the user.

## DIRECTOR UPDATE 2026-10-05 00:35 (league fidelity result)
The league is not faithful (see farm_scale.md update). Search objective = closed-start and overall OPENING metrics against the real top-team benchmark (out/opening_census.txt: units@100 per map, first split, eats per round), maximised subject to guards: win rate vs Y9_6 and vs the league not worse than Sv5.3 beyond noise, CPU peak <= 66M. Promotion rule stays: paired seeds, >= 1500 games, critic PASS, and units@100 on the four closed-start maps must move at least halfway to the top-team medians; a win-rate gain is welcome but not required for a candidate to be handed to the user for a ladder test (ladder is the only decisive evidence).
