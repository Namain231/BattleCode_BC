"""Kaggle kernel: train the v6 net on the private shards dataset, export it, write results to /kaggle/working.

Inputs (private datasets, any mount layout): bc-v6-code (flat copy of ml/train.py, ml/build_dataset.py, ml/export_cpp.py,
ml/v6/*.py, tools/replay_lite.py) and bc-v6-shards (shard_*.npz + manifest.json). Environment: EPOCHS (default 8), BATCH (2048),
VAL_FRAC (0.1), CHANNELS (32), HIDDEN (64). Outputs: v6.pt, v6.metrics.json, policy_weights_v6.hpp, run.json.
"""
import glob, json, os, subprocess, sys, time

t0 = time.time()
code = os.path.dirname(glob.glob("/kaggle/input/**/train_v6.py", recursive=True)[0])
sys.path.insert(0, code)
shards = os.path.dirname(sorted(glob.glob("/kaggle/input/**/shard_*.npz", recursive=True))[0])
out = "/kaggle/working"
import torch
info = {"torch": torch.__version__, "cuda": torch.cuda.is_available(), "code_dir": code, "shards_dir": shards,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "n_gpu": torch.cuda.device_count()}
print(info, flush=True)
env = os.environ.get
sys.argv = ["train_v6.py", "--data", shards, "--out", f"{out}/v6.pt", "--epochs", env("EPOCHS", "8"), "--batch", env("BATCH", "2048"),
            "--val-frac", env("VAL_FRAC", "0.1"), "--channels", env("CHANNELS", "32"), "--hidden", env("HIDDEN", "64"), "--amp"]
if env("INIT_PT"): sys.argv += ["--init", os.path.join(code, env("INIT_PT"))]
if env("LR"): sys.argv += ["--lr", env("LR")]
if env("TEAM_COND"): sys.argv += ["--team-cond", env("TEAM_COND")]
if env("ONLY_TEAMS"): sys.argv += ["--only-teams", env("ONLY_TEAMS")]
import train_v6
train_v6.main()
sys.argv = ["export_cpp.py", f"{out}/v6.pt", f"{out}/policy_weights_v6.hpp", "--data", shards]
import export_cpp
export_cpp.main()
info["seconds"] = round(time.time() - t0)
info["outputs"] = sorted(os.listdir(out))
json.dump(info, open(f"{out}/run.json", "w"), indent=1)
print("done", info, flush=True)
