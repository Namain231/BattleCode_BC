# Kaggle script kernel: runs one shard of the farm on this kernel's CPUs.
# Attach the private dataset built from this folder (see README_FARM.md). Set SHARD below per kernel.
import os, shutil, subprocess, glob
SHARD = int(os.environ.get("SHARD", "0"))
src = glob.glob("/kaggle/input/*/loong-judge")[0].rsplit("/", 1)[0]
dst = "/kaggle/working/farm"
shutil.copytree(src, dst, dirs_exist_ok=True)
os.chmod(f"{dst}/loong-judge", 0o755)
jobs = f"shards/jobs_{SHARD}.tsv"
print("cpus", os.cpu_count(), "jobs", sum(1 for _ in open(f"{dst}/{jobs}")))
subprocess.run(["sh", "run_shard.sh", jobs], cwd=dst, check=True)
shutil.copy(f"{dst}/results_jobs_{SHARD}.tsv", f"/kaggle/working/results_{SHARD}.tsv")
print(open(f"/kaggle/working/results_{SHARD}.tsv").read()[:2000])
