# farm_scale critique (2026-10-05)
Required fixes:
- tools/farm_round2_verify.py:43 calls summarize() with the repository ROOT still active; tools/farm_scale.py:240 consequently overwrites out/farm_report.md with synthetic wins/opening metrics and invented throughput. Isolate ROOT/output publication as farm_verify.py does, or explicitly disable shared publication for fixtures; assert the shared report remains byte-identical.
- out/farm_report.md:3 now says eight evaluations/four pairs after this verification rerun, although the sealed production bundle has zero evaluations. Regenerate it from the intended sealed run after fixing fixture isolation; synthetic results must never masquerade as farm evidence.

Independent verification:
- Read AGENTS.md protocol, NEXT_STEPS.md, task/update, executor report, reported source/docs changes, git status and scoped tracked diffs; unrelated dirty files/secrets were not reviewed or changed.
- farm_verify.py: PASS; 4,000 evaluations, 40 x 100 shards, nine opponents, 17 live + 20 dev maps, candidate/control seed/map/side pairing; >=3 seed clusters/map.
- Opening/census/TSV/NA/cached-resume fixtures and swapped queen ownership/death/safety checks reproduced.
- farm_round2_verify.py: PASS for explicit/default WSL pathname tokenization, one manifest read per scan, supplied-row summary avoiding rescan.
- 100 synthetic 371k+ manifest validations: 0.033s versus reported 0.032s; exactly 100 parses. This is not game throughput.
- farm_fix_verify.py: PASS; all 13 rejection cases; killed supervisor left WSL child holding lease, and resume waited for child exit.
- Six Python files parsed; WSL bash -n passed; opening_census --self-check passed.
- Exact --games 2 --pack-only reproduced sealed sv53_pkg-e807ea5f04cf; no games launched.
- --games 2 --collect-only reproduced (0, 0); its shared-report write was redirected to an F: fixture during this check.
- Sequential verification only, no game fan-out; C: remained approximately 13.8 GiB free. Confirmed out/ and ladder/ junctions target F:.

What I would not trust:
- Current shared farm_report.md is fixture-contaminated; the executor's zero-evaluation statement remains true for the sealed empty bundle, not that shared file.
- No measured current-code candidate performance, achieved precision, sustained throughput, peak RSS, CPU safety, or real-game crash/restart evidence exists.
- Default 2,000/arm gives nominal +/-2.2 pp pooled, about +/-6.6 pp/opponent and only 3-4 seed clusters/map; it cannot substantiate +/-1 pp. Revised acceptance explicitly permits this; --precision-pp 1 budgets >=9,604/opponent/arm without guaranteeing clustered precision.
- Wilson intervals assume independent half-credit outcomes; use paired clustered intervals for decisions, and require more seeds when wide. An interval spanning zero is not proof of safety.
- Rejected league bots are sparring partners only, not faithful reproductions of real teams; census benchmarks are observational winners-only comparisons.
- No search/promotion logic is delivered here; paired >=3 pp improvement and CPU <=66M must be enforced by the later search gate, not inferred from farm completion.
- Shell quoting, durable checkpoints, failed-judge rejection and side handling look sound in inspected paths; failures are raised rather than scored as losses. No LLM calls in evaluation loops or secrets in the explicit packing whitelist found.
- Remote lanes remain manual/OFF; no remote throughput or end-to-end remote recovery is validated. Disk checks before games cannot preserve floors against running/concurrent workloads; failed scratch can accumulate.
VERDICT: FAIL: verification publishes synthetic fixture results into the shared farm report
