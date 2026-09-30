"""Train a move network on a Kaggle GPU and export it to a C++ header (no local PyTorch needed).

    python tools/kaggle_train.py launch --data ml/data_open --name open1 [--init ml/models/n4.pt] [--epochs 12]
    python tools/kaggle_train.py fetch --name open1        # -> ml/models/<name>.pt + ml/models/policy_weights_<name>.hpp

Uploads a fresh private dataset (shards + ml/train.py + ml/export_cpp.py + the init checkpoint), pushes a GPU kernel
that runs train.py then export_cpp.py, and fetch downloads the model, the header and the training log.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cloud_test import BATCHES, KUSER, ROOT, kaggle  # noqa: E402


def launch(a):
    batch = f"kt_{a.name}_{time.strftime('%m%d%H%M')}"
    bdir = BATCHES / batch; ds = bdir / "ds"; ds.mkdir(parents=True, exist_ok=True)
    stage = ds / "pkg"; (stage / "data").mkdir(parents=True, exist_ok=True)
    for f in ("train.py", "export_cpp.py"):
        shutil.copy(ROOT / "ml" / f, stage)
    for f in pathlib.Path(ROOT / a.data).glob("*.npz"):
        shutil.copy(f, stage / "data")
    if a.init:
        shutil.copy(ROOT / a.init, stage / "init.pt")
    dataset = f"{KUSER}/{batch.replace('_', '-')}"[:60]
    (ds / "dataset-metadata.json").write_text(json.dumps({"title": batch, "id": dataset, "licenses": [{"name": "CC0-1.0"}]}))
    kaggle("datasets", "create", "-p", "ds", "--dir-mode", "zip", cwd=bdir)
    for _ in range(90):
        try:
            if "ready" in kaggle("datasets", "status", dataset, retries=1): break
        except RuntimeError:
            pass
        time.sleep(10)
    kd = bdir / "k"; kd.mkdir(exist_ok=True)
    slug = f"tr-{a.name}".replace("_", "-")[:50]
    (kd / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{KUSER}/{slug}", "title": slug, "code_file": "run.py", "language": "python", "kernel_type": "script",
        "is_private": True, "enable_gpu": True, "enable_internet": True, "dataset_sources": [dataset]}))
    init = "'--init', '/tmp/pkg/init.pt'," if a.init else ""
    (kd / "run.py").write_text(
        "import glob, os, shutil, subprocess, sys, time, zipfile\n"
        "for _ in range(40):\n"
        "    src = glob.glob('/kaggle/input/**/train.py', recursive=True)\n"
        "    if src: break\n"
        "    time.sleep(30)\n"
        "shutil.copytree(os.path.dirname(src[0]), '/tmp/pkg')\n"
        "for z in glob.glob('/tmp/pkg/**/*.zip', recursive=True):\n"
        "    zipfile.ZipFile(z).extractall(os.path.dirname(z))\n"
        "data = sorted({os.path.dirname(p) for p in glob.glob('/tmp/pkg/**/*.npz', recursive=True)})\n"
        "print('data dirs', data, flush=True)\n"
        f"subprocess.run([sys.executable, '-u', 'train.py', '--data', *data, {init} '--out', '/kaggle/working/{a.name}.pt',"
        f" '--epochs', '{a.epochs}', '--max-samples', '{a.max_samples}', '--scalars', '{a.scalars}'], cwd='/tmp/pkg', check=True)\n"
        f"subprocess.run([sys.executable, '-u', 'export_cpp.py', '/kaggle/working/{a.name}.pt',"
        f" '/kaggle/working/policy_weights_{a.name}.hpp', '--data', data[0]], cwd='/tmp/pkg', check=True)\n")
    msg = kaggle("kernels", "push", "-p", "k", cwd=bdir).strip().splitlines()[-1]
    print(msg)
    (BATCHES / f"last_train_{a.name}.json").write_text(json.dumps({"batch": batch, "kernel": f"{KUSER}/{slug}"}))


def fetch(a):
    rec = json.loads((BATCHES / f"last_train_{a.name}.json").read_text())
    st = kaggle("kernels", "status", rec["kernel"]).strip()
    print(st)
    if "COMPLETE" not in st: return
    out = BATCHES / rec["batch"] / "out"; out.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "kaggle", "kernels", "output", rec["kernel"], "-p", str(out)], cwd=BATCHES)
    for f in out.glob(f"{a.name}.pt"): shutil.copy(f, ROOT / "ml" / "models" / f.name)
    for f in out.glob(f"policy_weights_{a.name}.hpp"): shutil.copy(f, ROOT / "ml" / "models" / f.name)
    print("copied to ml/models:", [p.name for p in (ROOT / "ml" / "models").glob(f"*{a.name}*")])


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("launch"); l.add_argument("--data", required=True); l.add_argument("--name", required=True)
    l.add_argument("--init", default=""); l.add_argument("--epochs", type=int, default=12)
    l.add_argument("--max-samples", type=int, default=1600000)
    l.add_argument("--scalars", type=int, default=3, help="3 = the champion's C++ inputs (length, round, units)")
    f = sub.add_parser("fetch"); f.add_argument("--name", required=True)
    a = ap.parse_args()
    {"launch": launch, "fetch": fetch}[a.cmd](a)


if __name__ == "__main__":
    main()
