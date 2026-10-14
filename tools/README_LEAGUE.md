# Local opponent league

Run from the repository with the CUDA-enabled Python310 interpreter:

```powershell
& C:/Users/sohan/AppData/Local/Programs/Python/Python310/python.exe tools/league_build.py
```

The supervisor streams one winning replay at a time, trains one small net per team,
and runs at most three WSL games at a time (after GPU training finishes). Each heavy stage waits for at least 3 GB of free
physical memory using tools/mem_guard.sh, and requires 6 GiB free on F:. Its datasets, checkpoints, raw replays, logs and
atomic resume state live in `F:/BattleCode_data/league_build`. Existing scout data
is read through the `ladder/` junction. The `datasets_v2/` files are the active
training inputs; `datasets/` contains disposable output from the initial scan.
Resume with the identical command. Completed games are cached by `panel_zig.py`;
CPU sidecar state is committed atomically after every game; aggregate opening
state is committed after each map/seed evaluation and every replay extraction.

Six teams come from Sv53 losses; missing scout teams are supplemented by their
winning side in cached Sv53 replays, with IDs from the cached leaderboard. Two
teams are the highest peak-rated available winners in the scout manifests.
Only post-rule winning games are used. One entire game per team is held out.
The 16-channel, 32-hidden nets train for eight epochs. Each bot copies
`viper_y96qf`, with a shared `wNN=20` and dimension-aware inference header;
team identity and weights distinguish bots. Rules still choose splits, sprints,
feeding and emergency actions. This is movement imitation, so fidelity must be
measured rather than assumed from classification accuracy.

Fidelity: four replay-covered maps, seed 1, both sides (8 games/team).
Sv53: common Maze, Stripes, Devil, Trophy and Portals, seeds 1 and 2, both sides
(20/team). All opponents use this same map/seed/side schedule for ranking.
Opening metrics use `tools/opening_census.py`'s start-of-round snapshots and
terminal carry; never-split games keep a null first-split round.
`state.json` contains per-map real/local units50, units100, first split and CPU.
Acceptance uses the median of the four map medians: local units100 must be
within 25% of real winning replays, with measured league CPU <=66M. Per-map
differences remain diagnostics. CPU peaks come from Zig judge TSV counters saved in atomic per-game sidecars; absent counters prevent acceptance.
The real ladder sample has different opponents, seeds and map mixes, so ranking
comparisons are descriptive. Ties cannot establish a strict ordering.

Kaggle is an optional future training lane via `tools/kaggle_train/run_v6.sh`, OFF
by default. GitHub Actions and publishing are OFF and require explicit approval.
No remote lane or LLM is called by the supervisor. No submission is activated.

After all panels finish, run the required eight-game `out/league_chk` command
(the output directory must be a junction to F:), then run
`Python310/python.exe tools/league_finalize.py` to write `league/index.json` and
the final <=40-line `out/league_build_report.md`. Accepted entries include CPU
checks across fidelity, Sv53 and verification. Rejected entries remain artifacts
for inspection and must not be used as validated opponents.
