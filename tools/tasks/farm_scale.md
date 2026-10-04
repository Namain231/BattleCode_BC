# Task farm_scale. Run candidate-vs-league games at scale. Output: out/farm_report.md.

Read farm/README_FARM.md, farm/make_jobs.py, run_shard.sh, summarize.py, farm/kaggle/, farm.yml.move-to-.github-workflows and tools/panel_zig.py.

Goal: >= 2000 games per candidate vs the league (league/*, see out/league_report.md) plus vs baselines/Y9_6, on the 17 live maps and maps_rm_dev, both sides, in shards of about 100 games. Results as TSV with winner, rounds, units@r100, queen death round and CPU max.

Lanes:
- (a) the local WSL box, run overnight (-j 6 when nothing else runs).
- (b) Kaggle CPU kernels (private dataset from farm/pack.sh, one kernel per shard, no internet, respect Kaggle concurrency limits).
- (c) GitHub Actions only if the user approves (repo Namain231/BattleCode_BC); never publish bots to a public repo.

Deliver ONE command `tools/farm_run.sh CANDIDATE_DIR [--games N]` that packs, dispatches, collects and summarises: win rate with 95% CI per opponent and per map family, paired against Sv5.3 on identical seeds. Report throughput (games per hour per lane) and the precision achieved. Keep C: >= 3 GB free and stage on F:.
