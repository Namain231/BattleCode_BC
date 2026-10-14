# Paired opening farm
Run from Git Bash or WSL at the repository root:
```sh
bash tools/farm_run.sh CANDIDATE_DIR --games 2000
```
Windows/PowerShell equivalent:
```powershell
uv run --python 3.11 --with unswbc python -B tools/farm_scale.py CANDIDATE_DIR --games 2000
```
Local WSL judge is the default and sole automatic dispatch lane. No network or LLM
calls occur inside evaluation loops. Use an installed unswbc environment to avoid
uv package fetching. Default control is out/sv53_pkg (Sv5.3); --control overrides it.
No candidate was named in the task: specify the directory explicitly.
-j defaults to 6; lower it while other jobs run. Physical-memory floor is max(3000, 1500 + 600*workers) MB,
C: floor is 3 GiB, F: floor is 2 GiB, checked before each shard/evaluation.
WSL judge can live at LOONG_JUDGE; engine at UNSWBC_ENGINE.
Stage defaults to F:/BattleCode_data/farm_scale (WSL /mnt/f equivalent).
Bot build helper keeps its existing cache; evaluation files and bundle are on F:.

--games counts games per arm, across all nine sparring opponents, not per opponent.
Odd counts round up to a complete side pair. Default is 2000 candidate + 2000
Sv5.3 games, 40 contiguous shards of 100 evaluations (50 games per arm each).
Maps: 17 live maps plus all maps_rm_dev; no held-out test maps. Opponent/map
schedule rotates opponents first, then maps, then seeds. Both sides and both arms share seeds. Default has 3-4 independent seed clusters per map; opponents receive 222-224 games per arm.
Manifest hashes named recursive bot sources (including .cc), maps, native judge, engine, compiler/toolchain, build code, replay/metric tools and census. The bundle seal hashes actual wasm artifacts and every runtime input. Changes create a fresh run directory; corruption or mixed-version state is rejected.
Rerun the identical command to resume. Every completed evaluation is atomically
saved before its replay is deleted. Failure leaves its replay for resume/diagnosis.
A supervisor lock prevents overlapping local supervisors. A Linux flock shared per evaluation survives supervisor death in the WSL child. Every attempt has a unique replay directory, so surviving children cannot overwrite resumed attempts. Failed scratch is retained for diagnosis; delete it only after the judge exits.
state/*.json is the durable source; results.tsv and farm_report.md are rebuilt.
Full report is also copied to out/farm_report.md after each shard.

Primary metrics reuse opening_census.py: units50/100, total length100, first split,
eats per round (r0..99 / 100), terminal carry and final-body parity. Never-split
games stay NA and are counted separately. Top benchmarks are map medians from
out/opening_census.txt; winner-selection confounding remains.
Paired metric differences use seed-cluster means (sides/opponents clustered),
Student t intervals. Few seed clusters give imprecise results even at many games.
Opening outcomes may depend on opponents; report them as sparring observations.
Win rates per opponent/map family are secondary; Wilson intervals treat draws as
half credit and assume independence. Paired safety CIs are more useful with shared
seeds. An interval spanning zero does not establish non-inferiority.
Queen means the fixed lowest initial friendly ID (0 or 1 under current rules),
resolved from the initial map team order. No observed death is NA. CPU comes from judge stdout.
Generated families use the panel_zig naming convention; each live map is its own
family. Per-map opening comparisons highlight all four requested difficult maps.

## Optional offline Kaggle lane (OFF)
Earlier API access returned 403; local farm never depends on Kaggle.
Prepare a bundle without running games with the same command plus --pack-only.
Only upload the whitelist bundle directory as a PRIVATE dataset; it contains
wasm bots, judge, engine, selected maps, Python tools and shard JSONs, no secrets
or bot sources. Do not upload the repository or farm/pack.sh's arbitrary inputs.
Attach that private dataset to a private CPU script kernel, internet disabled.
One kernel per shard; copy the bundle into /kaggle/working/farm, then:
```sh
cd /kaggle/working/farm
FARM_LANE=kaggle python3 -B farm/worker.py shards/jobs_0000.json -j 2
```
The tools use only Python's standard library and the supplied native judge.
Set concurrency to the limit displayed by YOUR Kaggle account; no fixed account
limit is assumed. Do not launch more kernels than that limit. Export state/ and
manifest.json together, then locally:
```sh
bash tools/farm_run.sh CANDIDATE_DIR --games 2000 --import-results /mnt/f/returned/state --collect-only
bash tools/farm_run.sh CANDIDATE_DIR --games 2000
```
Stop the local supervisor before importing; it resumes only missing evaluations.
Returned manifest, bundle_seal.json and all job identity fields must match. Export bundle_seal.json alongside manifest.json. Every checkpoint is schema/finite-metric validated; extra IDs are rejected. Conflicting results
are rejected. Bundle copying/upload/kernel dispatch/download are manual and
require explicit user approval for publishing. No auto API fallback is attempted.

## GitHub Actions lane (OFF)
No workflow was installed or dispatched. Namain231/BattleCode_BC requires
explicit user approval and confirmed private visibility before any upload.
Never commit a bot bundle to a public repo. The existing move-to-workflows
prototype handles legacy TSV jobs and is not the paired metric worker.
If approved later, use the private bundle and farm/worker.py, cap parallel runners,
and return state/ plus manifest exactly as above. Throughput is unmeasured until
a lane runs; report games/hour from merged evaluation wall-time intervals.

## Precision and acceptance scope (fix round 1)
The one-command acceptance scope is local packing, dispatch, collection and summary.
Remote preparation/import is supported; publishing and remote dispatch remain manual,
OFF, and require explicit approval. No remote throughput is claimed.
Default nominal precision budget: pooled worst-case about +/-2.2 percentage points;
per-opponent about +/-6.6 pp. It does NOT meet +/-1 pp.
For a nominal independent per-opponent +/-1 pp budget:
```sh
bash tools/farm_run.sh CANDIDATE_DIR --games 2000 --precision-pp 1
```
This sizes >=9,604 games/opponent/arm, balanced over maps and sides (>=86,436/arm
with nine opponents), rounded to complete side pairs. It is a sampling budget,
not a precision guarantee: shared seeds, per-family rates and opening metrics
have different variance. Reports give actual Wilson half-widths and seed-cluster
paired intervals. More seeds are needed if those intervals remain too wide.
Memory guard runs before local shards and remote fan-out using /proc/meminfo on
Linux. The 600 MB/worker allowance is conservative planning, not a measured peak;
remote worker enforces a maximum of -j 2 until representative RSS measurements justify changing that cap.
Disk checks happen before evaluations/shards and cannot guarantee the free-space
floor during a running game or against concurrent external disk usage.
Verification (fixtures staged only on F:):
```powershell
uv run --python 3.11 --with unswbc python -B tools/farm_verify.py STAGE
uv run --python 3.11 --with unswbc python -B tools/farm_fix_verify.py STAGE
```
The second test kills a Windows supervisor, checks the surviving WSL lease blocks
resume, and confirms acquisition after child exit. It launches no real games.
## Fix round 2
WSL pathnames are shell-quoted; the default HOME expansion remains double-quoted.
Checkpoint validation reads the manifest once per call. Normal local shard summaries
reuse validated rows; restart/import, failure and final coverage validate disk state.
Summary/TSV computation still grows with completed rows; full-scale timing is unmeasured.
Run after farm_verify.py (no games; fixture output on F:):
`uv run --python 3.11 --with unswbc python -B tools/farm_round2_verify.py STAGE`
