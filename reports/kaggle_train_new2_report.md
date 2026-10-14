# kaggle_train_new2
Status: blocked at the required shard-completeness gate; no upload or kernel launched.
New2 CSV: 1,448 games; committed manifest: 1,430 games.
All 18 missing games involve our team (98), intentionally excluded by nn_refresh4.
No build_dataset_v6.py Python process was running during preflight.
The local supervisor validates eligible games, not every CSV game (tools/nn_refresh4.py:257).
Requested all-game completeness cannot be achieved by waiting on this builder.
Pending scope clarification: use the 1,430 eligible games or require all 1,448.
C: free at preflight: 8.77 GiB; F: free: 112.77 GiB.
Local nn_refresh4, its shards/state, shared trainer, and baselines were read only.
Existing trainer supports repeated extra-data, global explicit holdout exclusion,
AMP, epoch checkpoints, best.pt, last.pt, and move-class holdout metrics.
Existing Kaggle kernel only handles one new shard root and needs staged adaptation.
Existing run_v6.sh also omits shard_manifest.py from its code package.
Plan: isolated F: staging; old dataset reused; both new roots sampled twice;
newest-game holdout; k_fullft initialization; four epochs on a private T4 kernel.
No Kaggle API call yet; availability and GPU concurrency unverified.
Old/new holdout accuracy: unverified (training not started).
Parity, plane-8 audit, wasm build, and CPU peak: unverified.
Candidate viper_nv30k has not been created; no placeholder candidate exported.
No large panel, submission, champion change, or local fallback training started.
Files created: out/kaggle_train_new2_report.md.
