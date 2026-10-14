# Task farm_scale. Run candidate-vs-league games at scale. Output: out/farm_report.md.

Read farm/README_FARM.md, farm/make_jobs.py, run_shard.sh, summarize.py, farm/kaggle/, farm.yml.move-to-.github-workflows and tools/panel_zig.py.

Goal: >= 2000 games per candidate vs the league (league/*, see out/league_report.md) plus vs baselines/Y9_6, on the 17 live maps and maps_rm_dev, both sides, in shards of about 100 games. Results as TSV with winner, rounds, units@r100, queen death round and CPU max.

Lanes:
- (a) the local WSL box, run overnight (-j 6 when nothing else runs).
- (b) Kaggle CPU kernels (private dataset from farm/pack.sh, one kernel per shard, no internet, respect Kaggle concurrency limits).
- (c) GitHub Actions only if the user approves (repo Namain231/BattleCode_BC); never publish bots to a public repo.

Deliver ONE command `tools/farm_run.sh CANDIDATE_DIR [--games N]` that packs, dispatches, collects and summarises: win rate with 95% CI per opponent and per map family, paired against Sv5.3 on identical seeds. Report throughput (games per hour per lane) and the precision achieved. Keep C: >= 3 GB free and stage on F:.

## DIRECTOR UPDATE 2026-10-05 00:35 (league fidelity result)
The league nets are NOT faithful so far: Sv5.3 wins 15/20 vs the tungtung67 league bot and 16/20 vs avid coders, while its real ladder record is 0/17 and 6/17; three bots rejected on units@r100. Imitation nets cannot reproduce winners' economy. So: (1) do NOT make league win rate the decision metric. (2) Primary farm metric = SELF-DRIVEN opening metrics vs the real top-team benchmark from out/opening_census.txt: units@50, units@100, length@100, first split round, eats per round on every map (especially Stripes, Tower Defense, Queen Of Spades, Prisoners Dilemma), measured over many seeds against ANY opponent (Y9_6 and the league bots are fine as sparring partners). (3) Win rate vs Y9_6 and vs the league stays a SAFETY guard (no drop beyond noise) and a secondary report. (4) farm_run.sh must output both metric families with paired seeds vs Sv5.3.


Fix-round acceptance: local one-command dispatcher; remote lanes remain manual/OFF.
Default 2,000/arm has nominal pooled +/-2.2 pp, not +/-1 pp. --precision-pp 1
sizes >=9,604/opponent/arm, with achieved intervals reported, not guaranteed.
Exact verification: uv run --python 3.11 --with unswbc python -B tools/farm_verify.py STAGE
and uv run --python 3.11 --with unswbc python -B tools/farm_fix_verify.py STAGE.
