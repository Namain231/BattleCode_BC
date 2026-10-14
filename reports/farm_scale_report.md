# farm_scale fix round 2 - 2026-10-05
Both required critique items fixed; no candidate games launched.
Changed: tools/panel_zig.py, tools/farm_scale.py, farm/README_SCALE.md.
Created: tools/farm_round2_verify.py; audit appended to insights.md and AGENT_LOG.md.
WSL judge, lease, engine, map, bot and replay paths shell-quoted.
Default WSL HOME expansion double-quoted; explicit judge path uses shlex.quote.
checkpoints() reads manifest once, outside its row loop.
Normal local shard summaries reuse validated rows.
Restart/import, failure and final coverage still validate durable disk state.
Summary/TSV computation still scales with completed rows; full-scale timing unmeasured.
One command from repository root:
`bash tools/farm_run.sh CANDIDATE_DIR --games 2000`
Primary: paired opening metrics versus Sv5.3 and observational census benchmarks.
Wins versus Y9_6/league remain secondary safety evidence; remote lanes OFF.
Verification commands (PowerShell, repo root; STAGE below):
`uv run --python 3.11 --with unswbc python -B tools/farm_verify.py STAGE`
`uv run --python 3.11 --with unswbc python -B tools/farm_round2_verify.py STAGE`
`uv run --python 3.11 --with unswbc python -B tools/farm_fix_verify.py STAGE`
STAGE = F:/BattleCode_data/farm_scale/sv53_pkg-3121a4a0fbfa
PASS: 4,000 evaluations planned, 40 shards, nine opponents, 17 live + 20 dev maps, paired seeds/sides.
PASS: opening/census/TSV/queen ordering/death/safety/cached-resume fixtures.
PASS: explicit/default mocked WSL judge with spaces, apostrophes and shell metacharacters.
PASS: eight checkpoints read manifest once; supplied-row summary avoids checkpoint rescan.
Synthetic 371k+ manifest: 100 validations in 0.032s, exactly 100 parses; not farm throughput.
PASS: 13 malformed/extra/mixed-version/nonzero-exit rejection checks.
PASS: killed supervisor; WSL child retained lease; resume waited until child exited.
PASS: six Python files parse; WSL bash -n tools/farm_run.sh.
`uv run --python 3.11 --with unswbc python -B tools/farm_scale.py out/sv53_pkg --games 2 --pack-only`
`uv run --python 3.11 --with unswbc python -B tools/farm_scale.py out/sv53_pkg --games 2 --collect-only`
PASS: sealed bundle F:/BattleCode_data/farm_scale/sv53_pkg-e807ea5f04cf; zero evaluations.
out/farm_report.md regenerated from empty bundle; no achieved precision/throughput claimed.
Default nominal widths: +/-2.2 pp pooled, +/-6.6 pp/opponent; clustered CIs require games.
Resource check: C: 13.82 GiB free; F: 121.71 GiB free; staging/fixtures on F:.
Unverified: candidate performance, current-code game throughput/CPU/RSS, real-game crash recovery.
No independent Antigravity review this round; automated checks and direct review only.
No promotion, ladder changes, publishing, remote dispatch or LLM evaluation loop.
