"""Kaggle kernel: train the v6 net on the private shards dataset, export it, write results to /kaggle/working.

Inputs (private datasets, any mount layout): bc-v6-code (flat copy of ml/train.py, ml/build_dataset.py, ml/export_cpp.py,
ml/v6/*.py, tools/replay_lite.py) and bc-v6-shards (shard_*.npz + manifest.json). Environment: EPOCHS (default 8), BATCH (2048),
VAL_FRAC (0.1), CHANNELS (32), HIDDEN (64). Outputs: v6.pt, v6.metrics.json, policy_weights_v6.hpp, run.json.
"""
import glob, hashlib, json, os, subprocess, sys, time
def manifest_identity(man):
    return {"schema_version":man["schema_version"],"config":man["config"],
            "total_samples":man["total_samples"],
            "games":sorted((g["game"],g["team"],g["side"]) for g in man["games"]),
            "shards":sorted((s["file"],s["samples"],s["bytes"]) for s in man["shards"])}


t0 = time.time()
code = os.path.dirname(glob.glob("/kaggle/input/**/train_v6.py", recursive=True)[0])
sys.path.insert(0, code)
roots = sorted({os.path.dirname(f) for f in glob.glob("/kaggle/input/**/shard_*.npz", recursive=True)})
shards = next((r for r in roots if os.path.basename(r) == os.environ.get("NEW_DATASET", "")), roots[0])
old_shards = next((r for r in roots if os.path.basename(r) == os.environ.get("OLD_DATASET", "")), None)
audits = {}
if os.environ.get("OLD_DATASET"):
    for label, directory, expected_file in (("old",old_shards,"expected_old_manifest.json"),("new",shards,"expected_new_manifest.json")):
        if not directory: raise RuntimeError(f"{label} dataset missing")
        expected = json.load(open(os.path.join(code,expected_file)))
        actual = json.load(open(os.path.join(directory,"manifest.json")))
        if actual["config"]["terrain"] != "full" or manifest_identity(actual) != manifest_identity(expected):
            raise RuntimeError(f"{label} mounted manifest differs from expected game IDs/config/shards")
        encoded = json.dumps(manifest_identity(expected),sort_keys=True,separators=(",",":")).encode()
        if hashlib.sha256(encoded).hexdigest() != os.environ["EXPECTED_"+label.upper()+"_HASH"]:
            raise RuntimeError(f"{label} expected manifest belongs to another code dataset version")
        for shard in actual["shards"]:
            if os.path.getsize(os.path.join(directory,shard["file"])) != shard["bytes"]:
                raise RuntimeError(f"{label} shard size mismatch")
        audits[label] = {"games":len(actual["games"]),"samples":actual["total_samples"],"identity_hash":hashlib.sha256(encoded).hexdigest()}
    held_path=os.path.join(code,"holdout_games.json")
    if hashlib.sha256(open(held_path,"rb").read()).hexdigest() != os.environ["EXPECTED_HOLDOUT_HASH"]:
        raise RuntimeError("mounted holdout differs from requested newest-game split")
    if os.environ.get("INIT_PT") and hashlib.sha256(open(os.path.join(code,os.environ["INIT_PT"]),"rb").read()).hexdigest() != os.environ["EXPECTED_INIT_HASH"]:
        raise RuntimeError("mounted initialization checkpoint differs from requested current net")

out = "/kaggle/working"
import torch
info = {"torch": torch.__version__, "cuda": torch.cuda.is_available(), "code_dir": code, "shards_dir": shards,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "n_gpu": torch.cuda.device_count(), "manifest_audit": audits}
print(info, flush=True)
env = os.environ.get
sys.argv = ["train_v6.py", "--data", shards, "--out", f"{out}/v6.pt", "--epochs", env("EPOCHS", "8"), "--batch", env("BATCH", "2048"),
            "--val-frac", env("VAL_FRAC", "0.1"), "--channels", env("CHANNELS", "32"), "--hidden", env("HIDDEN", "64"), "--amp"]
if os.environ.get("OLD_DATASET") and not old_shards:
    raise RuntimeError("requested old dataset is not mounted")
if os.environ.get("NEW_DATASET") and os.path.basename(shards) != os.environ["NEW_DATASET"]:
    raise RuntimeError("requested new dataset is not mounted")
if old_shards:
    sys.argv += ["--data", old_shards, "--extra-data", shards, "--extra-data", shards, "--val-data", shards, "--val-games", os.path.join(code, "holdout_games.json")]
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
