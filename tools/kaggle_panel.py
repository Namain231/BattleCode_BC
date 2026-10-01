"""The panel test (tools/panel.py) on Kaggle: one private kernel per candidate plays the frozen panel, all 10 maps, both
sides, no early stop. Frees the laptop: run it for extra candidates while tools/panel.py runs locally.

    python tools/kaggle_panel.py launch cand_y10 cand_y10f [--seeds 2]
    python tools/kaggle_panel.py fetch                       # totals per candidate (same format as panel.py)

Seeds come from ml/cloud_tourney.py (not panel.py's 1000...), so compare Kaggle panel totals only with each other:
always include the base (cand_y10) in a launch. Kaggle runs at most 5 CPU sessions at once (4 CPUs each).
"""
import argparse
import json
import pathlib
import shutil
import sys
import tarfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cloud_test import BATCHES, DATASET, KUSER, PIP, ROOT, build, kaggle  # noqa: E402

PANEL = ["opponents/s475", "opponents/vb17", "viper_nn", "baselines/y7_12_nn1"]


def tag(bot):
    return pathlib.Path(bot).name


def launch(a):
    batch = time.strftime("kp%m%d_%H%M")
    stage = BATCHES / batch / "pkg"
    (stage / "wasm").mkdir(parents=True, exist_ok=True); (stage / "maps").mkdir(exist_ok=True)
    (stage / "maps_gen").mkdir(exist_ok=True)
    shutil.copy(ROOT / "ml" / "cloud_tourney.py", stage)
    for m in (ROOT / "maps").glob("*.map"):
        shutil.copy(m, stage / "maps")
    panel = a.panel.split(",") if a.panel else PANEL
    for b in panel + a.cands:
        shutil.copy(build(b), stage / "wasm" / f"{tag(b)}.wasm")
        print("built", b)
    if a.where == "colab":   # the Colab worker (ml/colab_worker.ipynb) runs jobs from MyDrive/viper_ml/jobs
        import zipfile
        from cloud_test import DRIVE
        shutil.copy(ROOT / "ml" / "panel_run.py", stage)
        zp = DRIVE / f"code_{batch}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in stage.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(stage).as_posix())
        opps = ",".join(tag(o) for o in panel)
        rec = {"batch": batch, "seeds": a.seeds, "seed_base": a.seed_base, "where": {}}
        for c in a.cands:
            job = f"p_{batch}_{tag(c)}{('_' + a.tag) if a.tag else ''}"
            (DRIVE / "jobs" / f"{job}.json").write_text(json.dumps({
                "code": zp.name, "script": "panel_run.py", "pip": PIP,
                "args": f"--cand wasm/{tag(c)}.wasm --opps {opps} --out {{OUT}}/out --maps {a.maps} --seeds {a.seeds}"
                        f" --seed-base {a.seed_base}"}))
            rec["where"][tag(c)] = {"colab": job}
            print("queued Colab job", job)
        (BATCHES / batch / "batch.json").write_text(json.dumps(rec, indent=1))
        (BATCHES / "last_kpanel.json").write_text(json.dumps(rec, indent=1))
        print(f"batch {batch}; fetch with: python tools/kaggle_panel.py fetch --batch {batch}")
        return
    ds = BATCHES / batch / "ds"; ds.mkdir(exist_ok=True)
    with tarfile.open(ds / "pkg.tar", "w") as t:
        t.add(stage, arcname="pkg")
    # A fresh dataset per batch: a new VERSION of a shared dataset is not what kernels mount for many minutes
    # (kp0929_2214 and kp0929_2302 both ran on the previous version: "wasm not found").
    dataset = f"{KUSER}/kpanel-{batch[2:].replace('_', '-')}"
    (ds / "dataset-metadata.json").write_text(json.dumps({"title": f"kpanel {batch}", "id": dataset,
                                                          "licenses": [{"name": "CC0-1.0"}]}))
    bdir = BATCHES / batch
    kaggle("datasets", "create", "-p", "ds", cwd=bdir)
    for _ in range(60):
        try:
            if "ready" in kaggle("datasets", "status", dataset, retries=1):
                break
        except RuntimeError:
            pass
        time.sleep(10)
    rec = {"batch": batch, "seeds": a.seeds, "seed_base": a.seed_base, "where": {}}
    for c in a.cands:
        name = tag(c)
        kd = bdir / f"k_{name}"; kd.mkdir(exist_ok=True)
        slug = f"p-{name.replace('_', '-')}{('-' + a.tag) if a.tag else ''}"[:50]
        (kd / "kernel-metadata.json").write_text(json.dumps({
            "id": f"{KUSER}/{slug}", "title": slug, "code_file": "run.py", "language": "python", "kernel_type": "script",
            "is_private": True, "enable_gpu": False, "enable_internet": True, "dataset_sources": [dataset]}))
        opps = [tag(o) for o in panel]
        (kd / "run.py").write_text(
            "import glob, os, shutil, subprocess, sys\n"
            f"subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *'{PIP}'.split()], check=True)\n"
            "import time\n"
            "for _ in range(40):  # a freshly created dataset can take minutes to mount (kp0930_0550 failed)\n"
            "    src = glob.glob('/kaggle/input/**/cloud_tourney.py', recursive=True)\n"
            "    if src: break\n"
            "    time.sleep(30)\n"
            "shutil.copytree(os.path.dirname(src[0]), '/tmp/pkg')\n"
            f"need = ['{name}'] + {opps!r}\n"
            "missing = [w for w in need if not os.path.exists(f'/tmp/pkg/wasm/{w}.wasm')]\n"
            "assert not missing, f'stale dataset: missing {missing}; have {os.listdir(\"/tmp/pkg/wasm\")}'\n"
            f"for o in {opps!r}:\n"
            f"    subprocess.run([sys.executable, '-u', 'cloud_tourney.py', '--a', 'wasm/{name}.wasm', '--b', f'wasm/{{o}}.wasm',\n"
            f"                    '--out', f'/kaggle/working/{{o}}', '--maps', '{a.maps}', '--gen', '0', '--seeds', '{a.seeds}',\n"
            f"                    '--no-sprt', '--seed-base', '{a.seed_base}'"
            + (", '--tourney-seeds', '--replays', f'/tmp/rep_{o}'" if a.replays else "")
            + "], cwd='/tmp/pkg', check=True)\n")
        msg = kaggle("kernels", "push", "-p", kd.name, cwd=bdir).strip().splitlines()[-1]
        print(name, msg)
        rec["where"][name] = {"kaggle": f"{KUSER}/{slug}", "dir": kd.name, "pushed": "error" not in msg.lower()}
    (bdir / "batch.json").write_text(json.dumps(rec, indent=1))
    (BATCHES / "last_kpanel.json").write_text(json.dumps(rec, indent=1))
    print(f"batch {batch}; fetch with: python tools/kaggle_panel.py fetch")


def fetch_replays(kernel, dest):
    """Download a kernel's replays.tgz files and unpack them into dest/<opp>/ (tools/cycle.py layout). True if found."""
    import subprocess, tarfile, tempfile
    tmp = pathlib.Path(tempfile.mkdtemp(dir="D:/battlecode/tmp"))
    subprocess.run([sys.executable, "-m", "kaggle", "kernels", "output", kernel, "-p", str(tmp), "--file-pattern", "replays"],
                   capture_output=True)
    found = False
    for tgz in tmp.rglob("replays.tgz"):
        od = pathlib.Path(dest) / tgz.parent.name
        od.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tgz) as t:
            t.extractall(od)
        found = True
    return found


def fetch(a):
    import subprocess
    rec = json.loads(((BATCHES / a.batch / "batch.json") if a.batch else (BATCHES / "last_kpanel.json")).read_text())
    bdir = BATCHES / rec["batch"]
    for name, w in rec["where"].items():
        if "colab" in w:
            from cloud_test import DRIVE
            res = DRIVE / "results" / w["colab"] / "out"
            summ = {p.parent.name: json.loads(p.read_text()) for p in res.glob("*/summary.json")} if res.exists() else {}
            if not summ:
                print(f"{name:14s} colab running/queued"); continue
            tot = sum(s["wins"] for s in summ.values()); n = sum(s["games"] for s in summ.values())
            print(f"{name:14s} TOTAL {tot:g}/{n} = {tot / max(1, n):.0%}   " +
                  "  ".join(f"{o} {s['wins']:g}/{s['games']}" for o, s in sorted(summ.items())) + "  (colab)")
            continue
        st = kaggle("kernels", "status", w["kaggle"]).strip().split("status ")[-1]
        out = bdir / name
        if "COMPLETE" in st:
            out.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "kaggle", "kernels", "output", w["kaggle"], "-p", name,
                            "--file-pattern", "summary"], capture_output=True, cwd=bdir)
        summ = {p.parent.name: json.loads(p.read_text()) for p in out.rglob("summary.json")} if out.exists() else {}
        if not summ:
            print(f"{name:14s} kaggle {st}")
            continue
        tot = sum(s["wins"] for s in summ.values()); n = sum(s["games"] for s in summ.values())
        per = "  ".join(f"{o} {s['wins']:g}/{s['games']}" for o, s in sorted(summ.items()))
        print(f"{name:14s} TOTAL {tot:g}/{n} = {tot / max(1, n):.0%}   {per}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("launch"); l.add_argument("cands", nargs="+"); l.add_argument("--seeds", type=int, default=1); l.add_argument("--seed-base", type=int, default=0)
    l.add_argument("--panel", default="", help="opponents (default: the frozen panel)"); l.add_argument("--maps", default="all")
    l.add_argument("--tag", default="", help="suffix for kernel names, so one candidate can run in several batches")
    l.add_argument("--where", default="kaggle", choices=["kaggle", "colab"])
    l.add_argument("--replays", action="store_true", help="keep replays (tourney.py seeds) as <opp>/replays.tgz for tools/cycle.py")
    f = sub.add_parser("fetch"); f.add_argument("--batch", default="")
    a = ap.parse_args()
    {"launch": launch, "fetch": fetch}[a.cmd](a)


if __name__ == "__main__":
    main()
