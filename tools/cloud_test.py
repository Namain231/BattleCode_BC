"""Test candidate bots against the champion on Kaggle and Colab in parallel (one machine per candidate).

    python tools/cloud_test.py launch cand_a cand_b ... [--where kaggle|colab|both] [--maps all] [--gen 10] [--seeds 4]
    python tools/cloud_test.py fetch  [--batch <name>]        # prints each candidate's summary when done
    python tools/cloud_test.py push   [--batch <name>]        # re-push Kaggle kernels refused by the 5-session limit

launch: builds every candidate and the champion (viper_nn) to .wasm with the judge's clang (cached), packs
ml/cloud_tourney.py + maps + maps_gen + the wasm files, and starts one test per candidate:
  - Kaggle: updates the private dataset kumaryash1134/vtest01 and pushes a private script kernel t-<cand> per candidate
    (4 CPUs each; Kaggle runs several at once);
  - Colab: writes MyDrive/viper_ml/code_<batch>.zip and one job t_<cand>.json per candidate (the worker notebook
    colab_worker_v3 picks them up; 8 CPUs each).
Each test plays the candidate against the champion from both sides and stops early by SPRT (see cloud_tourney.py).
fetch: downloads Kaggle outputs (retrying: this network drops HTTPS) into ladder/cloud_tests/<batch>/<cand>/ and
reads the Colab ones from Drive. The batch record is ladder/cloud_tests/last_batch.json.
Needs ~/.kaggle/access_token (Kaggle) and Google Drive for Desktop at G: (Colab).
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
KUSER = "kumaryash1134"
DATASET = f"{KUSER}/vtest01"
DRIVE = pathlib.Path("G:/My Drive/viper_ml")
BATCHES = ROOT / "ladder" / "cloud_tests"
PIP = "unswbc==1.2.3"  # new queen rules (1 Oct); pin wasmtime only if 1.2.3 needs it


def kaggle(*args, retries=8, cwd=None):
    for k in range(retries):
        r = subprocess.run([sys.executable, "-m", "kaggle", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=cwd or BATCHES)
        if r.returncode == 0:
            return r.stdout
        time.sleep(5 + 5 * k)
    raise RuntimeError(f"kaggle {' '.join(args)} failed: {r.stdout[-300:]} {r.stderr[-300:]}")


def build(bot):
    from unswbc import clangtool
    return pathlib.Path(clangtool.build(ROOT / bot))


def launch(a):
    batch = time.strftime("b%m%d_%H%M")
    stage = BATCHES / batch / "pkg"; stage.mkdir(parents=True, exist_ok=True)
    (stage / "wasm").mkdir(exist_ok=True); (stage / "maps").mkdir(exist_ok=True); (stage / "maps_gen").mkdir(exist_ok=True)
    shutil.copy(ROOT / "ml" / "cloud_tourney.py", stage)
    for m in (ROOT / "maps").glob("*.map"):
        shutil.copy(m, stage / "maps")
    for m in (ROOT / "maps_gen").glob("*.map"):
        shutil.copy(m, stage / "maps_gen")
    shutil.copy(build(a.champion), stage / "wasm" / "champion.wasm")
    for c in a.cands:
        shutil.copy(build(c), stage / "wasm" / f"{pathlib.Path(c).name}.wasm")
        print("built", c)
    args = f"--maps {a.maps} --gen {a.gen} --seeds {a.seeds}"
    record = {"batch": batch, "cands": [pathlib.Path(c).name for c in a.cands], "where": {}, "args": args}
    names = record["cands"]
    kaggle_names = names if a.where in ("kaggle", "both") else []
    colab_names = names if a.where == "colab" else []
    if a.where == "both":   # split: Colab takes every other candidate
        colab_names = names[1::2]; kaggle_names = names[0::2]
    if kaggle_names:
        ds = BATCHES / batch / "ds"; ds.mkdir(exist_ok=True)
        with tarfile.open(ds / "pkg.tar", "w") as t:
            t.add(stage, arcname="pkg")
        (ds / "dataset-metadata.json").write_text(json.dumps({"title": "vtest01", "id": DATASET,
                                                              "licenses": [{"name": "CC0-1.0"}]}))
        bdir = BATCHES / batch   # the CLI breaks on nested -p paths: run it from the batch folder
        exists = subprocess.run([sys.executable, "-m", "kaggle", "datasets", "status", DATASET], capture_output=True,
                                text=True, cwd=BATCHES).returncode == 0
        kaggle(*(["datasets", "version", "-p", "ds", "-m", batch] if exists else ["datasets", "create", "-p", "ds"]), cwd=bdir)
        for _ in range(30):
            if "ready" in kaggle("datasets", "status", DATASET):
                break
            time.sleep(10)
        for c in kaggle_names:
            kd = BATCHES / batch / f"k_{c}"; kd.mkdir(exist_ok=True)
            slug = f"t-{c.replace('_', '-')}"[:50]
            (kd / "kernel-metadata.json").write_text(json.dumps({
                "id": f"{KUSER}/{slug}", "title": slug, "code_file": "run.py", "language": "python",
                "kernel_type": "script", "is_private": True, "enable_gpu": False, "enable_internet": True,
                "dataset_sources": [DATASET]}))
            (kd / "run.py").write_text(
                "import glob, os, shutil, subprocess, sys\n"
                f"subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *'{PIP}'.split()], check=True)\n"
                "src = glob.glob('/kaggle/input/**/cloud_tourney.py', recursive=True)\n"
                "shutil.copytree(os.path.dirname(src[0]), '/tmp/pkg')\n"
                f"subprocess.run([sys.executable, '-u', 'cloud_tourney.py', '--a', 'wasm/{c}.wasm', '--b', "
                f"'wasm/champion.wasm', '--out', '/kaggle/working/out', *'{args}'.split()], cwd='/tmp/pkg', check=True)\n")
            msg = kaggle("kernels", "push", "-p", kd.name, cwd=bdir).strip().splitlines()[-1]
            print(msg)
            # Kaggle runs at most 5 CPU sessions at once; a refused push is retried later with `push`
            record["where"][c] = {"kaggle": f"{KUSER}/{slug}", "pushed": "error" not in msg.lower(), "dir": kd.name}
    if colab_names:
        zp = DRIVE / f"code_{batch}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in stage.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(stage).as_posix())
        for c in colab_names:
            job = {"code": zp.name, "script": "cloud_tourney.py", "pip": PIP,
                   "args": f"--a wasm/{c}.wasm --b wasm/champion.wasm --out {{OUT}}/out {args}"}
            (DRIVE / "jobs" / f"t_{batch}_{c}.json").write_text(json.dumps(job))
            record["where"][c] = {"colab": f"t_{batch}_{c}"}
            print("queued Colab job", f"t_{batch}_{c}")
    (BATCHES / batch / "batch.json").write_text(json.dumps(record, indent=1))
    (BATCHES / "last_batch.json").write_text(json.dumps(record, indent=1))
    print(f"batch {batch}: {len(names)} candidates; fetch with: python tools/cloud_test.py fetch")


def push(a):
    """Push the Kaggle kernels of a batch that were refused (e.g. the 5-session limit)."""
    path = (BATCHES / a.batch / "batch.json") if a.batch else (BATCHES / "last_batch.json")
    rec = json.loads(path.read_text())
    for c, w in rec["where"].items():
        if "kaggle" in w and not w.get("pushed", True):
            msg = kaggle("kernels", "push", "-p", w["dir"], cwd=BATCHES / rec["batch"]).strip().splitlines()[-1]
            print(c, msg)
            w["pushed"] = "error" not in msg.lower()
    for p in (BATCHES / rec["batch"] / "batch.json", BATCHES / "last_batch.json"):
        p.write_text(json.dumps(rec, indent=1))


def fetch(a):
    rec = json.loads(((BATCHES / a.batch / "batch.json") if a.batch else (BATCHES / "last_batch.json")).read_text())
    for c, w in rec["where"].items():
        out = BATCHES / rec["batch"] / c
        summ = None
        if "kaggle" in w:
            st = kaggle("kernels", "status", w["kaggle"]).strip().split("status ")[-1]
            if "COMPLETE" in st:
                out.mkdir(parents=True, exist_ok=True)
                for _ in range(10):
                    subprocess.run([sys.executable, "-m", "kaggle", "kernels", "output", w["kaggle"], "-p", c,
                                    "--file-pattern", "summary|results"], capture_output=True, cwd=BATCHES / rec["batch"])
                    hits = list(out.rglob("summary.json"))
                    if hits:
                        summ = json.loads(hits[0].read_text()); break
                    time.sleep(10)
            where = f"kaggle {st}"
        else:
            p = DRIVE / "results" / w["colab"] / "out" / "summary.json"
            summ = json.loads(p.read_text()) if p.exists() else None
            where = "colab " + ("done" if summ else "running/queued")
        if summ:
            per = " ".join(f"{m[:6]} {s:g}/{g}" for m, (s, g) in sorted(summ["per_map"].items()))
            print(f"{c:22s} {summ['wins']:g}/{summ['games']} = {summ['rate']:.0%}  {summ['verdict']}\n    {per}")
        else:
            print(f"{c:22s} {where}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("launch"); l.add_argument("cands", nargs="+")
    l.add_argument("--where", default="both", choices=["kaggle", "colab", "both"])
    l.add_argument("--champion", default="viper_nn")
    l.add_argument("--maps", default="all"); l.add_argument("--gen", type=int, default=10)
    l.add_argument("--seeds", type=int, default=4)
    f = sub.add_parser("fetch"); f.add_argument("--batch", default="")
    pu = sub.add_parser("push"); pu.add_argument("--batch", default="")
    a = ap.parse_args()
    BATCHES.mkdir(parents=True, exist_ok=True)
    {"launch": launch, "fetch": fetch, "push": push}[a.cmd](a)


if __name__ == "__main__":
    main()
