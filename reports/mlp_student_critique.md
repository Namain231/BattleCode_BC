# mlp_student critique (2026-10-06, current fix round 2)
Required fixes / acceptance blockers:
- out/mlp_student_report.md:19; tools/tasks/mlp_student.md:11: reported safety is 50/98 versus 59/98 (-9.18 pp), beyond the six-point allowance. Keep the candidate dropped; the brief's non-inferiority requirement is unmet.
- tools/panel_zig.py:114-123; ml/v6/resume_mlp_student.py:3-9: cache acceptance binds neither execution-time binaries/engine/maps nor the seed invocation. Original control provenance is unavailable. Any future comparison needs fresh sealed paired arms; do not revive these caches or the retired supervisor.
- ml/v6/bench_mlp_student.py:18: validate n==1600, every fread and fclose before inference. Truncated inputs can leave zero-filled tensors and produce misleadingly cheap successful measurements; malformed counts can cause excessive allocations. Required before reusing this benchmark, not a reason to resume this dropped experiment.
Review and verification:
- Read AGENTS.md, NEXT_STEPS.md, brief/report and guides; inspected all five reported student scripts, candidate main/inference/weights/export/package and relevant tracked documentation/log diffs. git status includes unrelated dirty files; no attribution of those changes to this executor.
- Only intended write is this critique. No AGENT_LOG append, training, game panels, submissions or remote publishing. Small read-only checks used at most two concurrent jobs; C: stayed above 14 GiB. out/ladder/wasm_cache resolve to F:.
- Exact parity/benchmark/census entry points rewrite artifacts. Used read-only equivalents; training and the 98-game panel were not rerun.
- Fresh native executable run through stdout versus fresh Torch on existing input.bin: 1600/1600 argmax agreement, max logit error 0.00067138671875. Exactly reproduces the reported parity numbers.
- Native error cases reproduce exit 2 (missing arguments), 3 (missing input), 7 (unopenable output). Current parity harness checks its I/O; the previous critique's missing-I/O complaint is resolved there.
- Executed current benchmark threshold statements in memory: valid cost passes; >3M, zero, negative, NaN and infinity fail. Previous successful-exit-on-over-budget complaint is resolved.
- CPU sandbox execution was rejected by automatic approval review because possible cache/toolchain writes exceed the critique-only edit scope. CPU-per-call numbers were NOT independently rerun in this review; saved cpu.json says conv 21.137M, MLP 1.659M mean/2.482M sampled max.
- Every exported coefficient matches checkpoint quantization/bias values; all array sizes/values are valid. Checkpoint, export, header and package hashes match. Zip is 3911843 bytes with nine source/config entries, matching current files and no secret files.
- Parent main diff contains only MLP include, nnKind and inference switch; every inherited parent header/config is byte-identical. nnInput6/wNN and seven-logit output semantics are preserved; reserved planes 8/18 are zero and omitted consistently.
- Checked identity against all 246 current shard hashes and trainer hash. Holdout is the newest 60 exported IDs and has zero overlap with the old training manifest; it is globally excluded by batches(). Timestamp-based newest ordering was not independently established.
- Saved epoch-7 checkpoint counts reproduce 68.627761% student / 68.578835% teacher, 582515 validation states and all reported class percentages. Full validation inference and eight-epoch training were not rerun.
- Candidate: independently reconstructed all 98 replay outcomes, queen deaths and full opening census; 50 wins, 91 queen deaths, units100 mean 25.642857 / median 21. No decode/analysis failures; all success sidecars are returncode 0.
- Candidate per-map wins reproduce 7,10,11,9,5,1,7 /14 in report order. CPU sidecars reproduce australia 57.361095M and around_unsw 57.615648M.
- Both replay directories and summaries have exactly the requested 98 unique map/seeds-3-to-9/side keys. Full control reconstruction reproduces 59 wins, 87 queen deaths, units100 mean 25.295918 / median 22; all 196 replays decoded/analyzed without failures.
- Replay-recorded opponent cache files Y9_6-237782e315b0ca3c.wasm and Y9_6-2c39dcb5edd5e18d.wasm are still present and byte-identical (SHA256 7c8c4d6e...196298); this does not recover immutable execution-time identities.
- Census in-memory self-check passes (paid-step eat, corpse source, reversed split, terminal carry and final-body parity).
- Trainer loads one shard at a time and saves identity-bound optimizer/RNG checkpoints atomically at epoch boundaries. Standalone entry has no memory/disk guard; any future launcher must enforce those constraints. Retired supervisor performs no unattended work.
- No LLM, network or credential-writing calls found in reviewed student scripts. The unrelated dirty secrets.env was not read or included in any artifact.
What I would not trust:
- Aggregate imitation accuracy as gameplay equivalence: backward recall is 8.77% versus 43.97%. This is diagnostic, not proof of the safety regression's cause.
- Universal <=3M per-call or <=66M whole-game bounds: only 64 real states from two shards were timed, and two map peaks do not cover unknown maps or dense inputs.
- Historical control bot/engine/map/seed provenance, exact map-text pairing, cached-stage reuse, fresh-seed/ladder strength, or dataset-versus-bot input parity. Matching names and counts do not seal an experiment.
- Farm +/-1-point precision, league fidelity or search promotion: outside this MLP brief, unestablished by 98 games and not grounds for promotion.
VERDICT: FAIL: reported safety misses the six-point allowance; historical control provenance is unsealed
