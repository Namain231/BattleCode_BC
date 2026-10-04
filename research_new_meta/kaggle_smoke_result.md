# Kaggle command-line GPU smoke test (2026-10-02)

Outcome: private dataset upload, script execution, dataset attachment/read, status polling and output download worked. **GPU training was not proved:** all three versions ran without a usable GPU. Do not start the real training job on the strength of this test.

## Measured execution

Account: `sohansridutta`; Kaggle CLI 2.2.4 via `uv run --python 3.11 --with kaggle`. Used only the already-exported `KAGGLE_API_TOKEN`; did not read secrets.env or put credentials in files.

| Attempt | Requested settings | Result |
|---|---|---|
| v1 | private, enable_gpu=true, internet=true, timeout=300s | Push accepted. ERROR: nvidia-smi executable missing; original diagnostic aborted before result file. |
| v2 | private, enable_gpu=true, machine_shape=NvidiaTeslaT4, internet=true, timeout=300s | COMPLETE, result.json downloaded. PyTorch 2.10.0+cpu, CUDA false, nvidia-smi missing. No GPU training. |
| v3 | private, enable_gpu=true, --accelerator NvidiaTeslaP100, internet=false, timeout=300s | COMPLETE, result.json downloaded. Same CPU-only runtime. No GPU training. |

The v1 pulled metadata reported `is_private: true`, `enable_gpu: true`, `enable_internet: true`, `machine_shape: NvidiaTeslaT4`. Final metadata reported `is_private: true`, `enable_gpu: true`, `enable_internet: false`, `machine_shape: Gpu`. These are settings, **not evidence of a granted GPU**. Actual GPU type granted: none detected. CUDA training throughput, VRAM, weights and 20-second GPU-loop timing: unavailable because the CUDA prerequisite failed; there was no CPU fallback disguised as success.

v2 log finished around 42.2 seconds after script execution began. The final API session status was COMPLETE with `failureMessage: null`, despite our result file recording the failed CUDA prerequisite. No push response/error required phone verification or an internet-toggle change. Consequently this test cannot establish verification status or the root cause of the CPU/offline runtime. Phone verification, resource provisioning or account restrictions need separate confirmation; no specific one was proved here.

Internet HTTPS GET to https://www.google.com failed with `<urlopen error [Errno -3] Temporary failure in name resolution>` both with internet requested ON and OFF. No outbound connectivity was proved.

Dataset was mounted at `/kaggle/input/datasets/sohansridutta/bc-private-gpu-smoke-20261002/tiny_data.npz`: 1,040,262 bytes, array `data` shape [130000]. npz load took 0.02329 seconds (v2), 0.04782 seconds (v3). Working filesystem: 20,957,446,144 bytes total, 20,940,550,144 bytes free (~19.5 GiB).

## Quota and documented limits

`kaggle quota --format json` reported GPU 0.00h used / 30.00h remaining, TPU 0.00h used / 20.00h remaining; refreshAt `2026-10-03T00:00:00`. A direct authenticated `KaggleApi.quota_view()` call instead reported GPU `totalTimeAllowed: 21600s` (6h), `timeUsed: 0s`, `timeReserved: 0s`, `hasEverRun: false`; TPU 72000s. A subsequent CLI quota call again said 30h. **Quota responses disagree; exact usable GPU quota is unresolved.** Direct API refresh timestamp was `2026-10-03T00:00:00.000Z`.

Each smoke push requested a 300-second session limit; no response exposed an independently granted session cap. [Official notebook specifications](https://www.kaggle.com/docs/notebooks) state 12 hours for CPU/GPU, 9 hours for TPU, 20 GB saved working storage, and list P100 / T4 x2 configurations. [Official GPU guidance](https://www.kaggle.com/docs/efficient-gpu-usage) describes a weekly quota of 30 hours or sometimes higher. Those documented defaults are not measured hardware or guarantees for this account.

[Official dataset specifications](https://www.kaggle.com/docs/datasets#technical-specifications) currently state 200 GB per dataset, 200 GB across private datasets, and at most 50 top-level files (use directories/archives beyond that). Uploaded archives are unpacked. [Kaggle's announcement](https://www.kaggle.com/discussions/product-announcements/512322) confirms the 200 GB private quota. No separate smaller per-file limit was found in current official specifications; do not assume a separately verified maximum single-file size. The [official CLI changelog](https://github.com/Kaggle/kaggle-cli/blob/main/CHANGELOG.md) records removal of a client file-size restriction, but does not establish a current server per-file limit. Only the ~1 MB file was tested. A ~1 GB compressed shard dataset fits the published overall cap, subject to unused private storage and archive expansion; a 1 GB upload was deliberately not attempted.

## Transfer speed and local footprint

- Successful upload: 1,040,262 bytes; CLI progress reported ~421 kB/s transfer, ~2 seconds. Full CLI dataset creation wall time 10.822s, ~96 kB/s including authentication/processing.
- Output-only download: result.json 917 bytes + execution log 3426 bytes = 4343 bytes in 3.435s (~1.26 kB/s end-to-end). This tiny latency-dominated transfer does **not** estimate bulk download bandwidth. Fetch-with-status took 6.685s for v2, 7.352s for v3.
- Final measured scratch directory size: 2,105,147 bytes (~2.01 MiB). C: free was ~4.04 GiB initially and ~3.97 GiB before cleanup; observed net free-space reduction ~75 MB including uv activity and unrelated concurrent writes, below 300 MB. No real shards or local torch install were downloaded.

## Setup failures fixed

1. `kaggle datasets create -p kaggle_smoke/dataset` failed on Windows with missing upload-state file under `Temp/.kaggle/uploads/kaggle_smoke/dataset_tiny_data.npz.json`. Changing into the dataset directory and using `-p .` worked. The CLI printed an error but the enclosing command did not yield a trustworthy failure code.
2. First kernel push returned HTTP 409. The server body said the requested title was already used by a dataset. Giving the kernel a distinct title/slug worked. This was a naming conflict, not a verification error.

## Reusable scripts and validation

Written under `tools/kaggle_train/`, LF UTF-8; all pass Git Bash `bash -n`:

```bash
# Token must already be exported; none of these scripts sources secrets.env.
bash tools/kaggle_train/push_dataset.sh DATASET_DIR
bash tools/kaggle_train/push_dataset.sh DATASET_DIR version 'Updated shards'
bash tools/kaggle_train/push_kernel.sh KERNEL_DIR 43200 NvidiaTeslaT4
bash tools/kaggle_train/fetch_output.sh sohansridutta/KERNEL OUTPUT_DIR 2400
```

Dataset metadata must exist. Create omits --public (private by default). Dataset version mode preserves the existing dataset's visibility: use it only on a private dataset. Upload uses `-r skip`, for top-level shard files; nested folders need deliberate archive handling first. Kernel script enforces private + GPU metadata and an explicit accelerator; internet setting is supplied by metadata. Fetch polls every 60 seconds, default timeout 40 minutes, downloads execution logs on ERROR, and returns nonzero for ERROR/cancellation/timeout. Always inspect training result/checkpoint as well as COMPLETE: this smoke demonstrated that a kernel can finish successfully without meeting its GPU training prerequisite.

The push-kernel script was used to push v2; fetch-output was used for v1/v2/v3, including its ERROR and COMPLETE branches. Dataset-create and explicit P100 push were additionally exercised directly through the CLI. Dataset version mode was syntax-checked only. Final accelerator argument addition was syntax-checked; the same explicit accelerator CLI flag was exercised for v3.

## Real-training implication

Read `research_new_meta/dataset_v6_and_bceval.md`, `research_new_meta/nn_plan.md`, and `ml/train.py`. v6 expects ~19 planes, 6 scalars, 7-way actions and compressed shards around 1-1.6 GB. Its trainer requirement is streaming with <=1 GB host RAM for data. Current `ml/train.py` preallocates the whole dataset and concatenates parts; it is not ready for the full v6 data. Do not upload/retrain real data until GPU provisioning is confirmed and a streaming trainer exists. This task changed no trainer or bot.

## Cleanup

- Deleted earlier PUBLIC `sohansridutta/tiny-smoke-dataset` first; CLI confirmed success.
- Deleted private kernel `sohansridutta/bc-private-gpu-kernel-20261002`; CLI confirmed success.
- Deleted private dataset `sohansridutta/bc-private-gpu-smoke-20261002`; CLI confirmed success.
- Deleted local `kaggle_smoke/` after recording diagnostics here. No smoke dataset/kernel remains knowingly retained. Pre-existing root `tiny_data.npz` and `dataset-metadata.json` were left untouched.

Final v3 diagnostic (preserved before scratch cleanup):

```json
{
  "torch_version": "2.10.0+cpu",
  "cuda_available": false,
  "disk": {
    "total": 20957446144,
    "used": 118784,
    "free": 20940550144
  },
  "nvidia_smi": {
    "error": "[Errno 2] No such file or directory: 'nvidia-smi'"
  },
  "internet": {
    "error": "<urlopen error [Errno -3] Temporary failure in name resolution>"
  },
  "dataset": {
    "path": "/kaggle/input/datasets/sohansridutta/bc-private-gpu-smoke-20261002/tiny_data.npz",
    "bytes": 1040262,
    "arrays": {
      "data": [
        130000
      ]
    },
    "read_seconds": 0.04781907399998886
  },
  "error": "Traceback (most recent call last):\n  File \"/kaggle/src/script.py\", line 22, in <module>\n    if not torch.cuda.is_available(): raise RuntimeError('GPU required for smoke training')\n                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\nRuntimeError: GPU required for smoke training\n"
}
```
