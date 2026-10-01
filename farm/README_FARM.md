# PROTOTYPE game farm (throwaway)

A self-contained bundle for running many matches in parallel on any x86-64 Linux: your WSL, Kaggle
CPU kernels, GitHub Actions runners. The judge is the Loong Zig judge (built from
github.com/overyonder/the-loong-game, needs only libc), about 3x faster than `unswbc run --sandbox`,
with identical results on the games checked.

Contents: `loong-judge`, `engine.wasm` (unswbc engine), `bots/*.wasm` (bots built with the judge's clang
via `buildwasm.py`), `maps/live` (the 10 ladder maps), `maps/extra` (other official maps), `maps/dev`
(generated tuning maps, all 7 generator styles + random dense), `maps/test` (held-out generated
maps: look at these only for final checks).

## Make jobs
    python3 make_jobs.py --pair proto_rehaul:v712 --pair proto_rehaul:champ --maps live,test --seeds 1-4 --shards 16 --out-dir shards

## Run
- WSL / any Linux box, all cores but a couple:  `sh run_shard.sh shards/jobs_0.tsv 10`
- GitHub Actions: commit this folder as `farm/` plus `.github/workflows/farm.yml`, run the "farm"
  workflow with `shards` = number of shard files. One runner per shard, all in parallel.
- Kaggle: upload this folder as a private dataset, create one script kernel per shard from
  `kaggle/run_shard_kaggle.py` with env SHARD=i (or edit the constant), run them side by side,
  download `results_i.tsv`.

## Read
    python3 summarize.py results*.tsv            # win rate per pairing, 95% CI, per map family

GPUs do not help: games are CPU-bound WebAssembly. What scales is CPU cores across machines.
