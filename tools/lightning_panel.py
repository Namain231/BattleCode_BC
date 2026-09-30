"""Run a candidate's panel on the Lightning AI studio (free CPU machine), in the background.

    python tools/lightning_panel.py launch cand_x [--panel a,b] [--maps m1,m2] [--seeds 2] [--seed-base 0]
    python tools/lightning_panel.py fetch            # prints totals when summaries exist
    python tools/lightning_panel.py stop             # stops the studio (saves credits)

Uses the studio "sp1" in teamspace "default-project" (user from ~/.lightning/credentials.json). Stages the same
package as tools/kaggle_panel.py (cloud_tourney.py + panel_run.py + maps + wasm), uploads it as a zip, installs
unswbc/wasmtime there and runs panel_run.py with nohup; results land in ~/lp/<batch>/out/<opponent>/summary.json.
"""
import argparse
import json
import os
import pathlib
import shutil
import sys
import time
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cloud_test import BATCHES, PIP, ROOT, build  # noqa: E402

PANEL = ["opponents/s475", "opponents/s476", "opponents/vb17", "opponents/vb18", "viper_nn", "baselines/y7_12_nn1"]
REC = BATCHES / "last_lightning.json"


def studio():
    d = json.load(open(os.path.expanduser("~/.lightning/credentials.json")))
    os.environ["LIGHTNING_USER_ID"] = d["user_id"]; os.environ["LIGHTNING_API_KEY"] = d["api_key"]
    from lightning_sdk import Studio
    return Studio(name="sp1", teamspace="default-project", user="f20231134")


def tag(b):
    return pathlib.Path(b).name


def launch(a):
    from lightning_sdk import Machine
    batch = time.strftime("lp%m%d_%H%M")
    stage = BATCHES / batch / "pkg"; (stage / "wasm").mkdir(parents=True, exist_ok=True); (stage / "maps").mkdir(exist_ok=True)
    (stage / "maps_gen").mkdir(exist_ok=True)
    shutil.copy(ROOT / "ml" / "cloud_tourney.py", stage); shutil.copy(ROOT / "ml" / "panel_run.py", stage)
    for m in (ROOT / "maps").glob("*.map"):
        shutil.copy(m, stage / "maps")
    panel = a.panel.split(",") if a.panel else PANEL
    for b in panel + [a.cand]:
        shutil.copy(build(b), stage / "wasm" / f"{tag(b)}.wasm")
    zp = BATCHES / batch / "pkg.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in stage.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(stage).as_posix())
    s = studio()
    if str(s.status).lower().find("running") < 0:
        print("starting studio sp1 (CPU)..."); s.start(Machine.CPU)
    s.upload_file(str(zp), f"{batch}.zip")   # no sub-directory: the Windows SDK turns "lp/x" into a file named "lp\x"
    opps = ",".join(tag(o) for o in panel)
    cmd = (f"cd ~ && rm -f 'lp\\'*.zip; mkdir -p lp/{batch} && cd lp/{batch} && unzip -oq ~/{batch}.zip && pip install -q {PIP} && "
           f"nohup python panel_run.py --cand wasm/{tag(a.cand)}.wasm --opps {opps} --out out --maps {a.maps} "
           f"--seeds {a.seeds} --seed-base {a.seed_base} > run.log 2>&1 &")
    print(s.run(cmd)[-500:])
    REC.write_text(json.dumps({"batch": batch, "cand": tag(a.cand), "opps": opps}))
    print("launched", batch)


def fetch(a):
    rec = json.loads(REC.read_text()); s = studio()
    out = s.run(f"cd ~/lp/{rec['batch']} && bash -c 'for f in out/*/summary.json; do [ -f $f ] && echo $f && cat $f && echo; done; tail -2 run.log'")
    tot = n = 0; per = []
    for block in out.split("out/")[1:]:
        try:
            name, js = block.split("/summary.json", 1)
            d = json.loads(js[js.index("{"):js.rindex("}") + 1])
            tot += d["wins"]; n += d["games"]; per.append(f"{name} {d['wins']:g}/{d['games']}")
        except Exception:
            pass
    print(f"{rec['cand']}: TOTAL {tot:g}/{n}  " + "  ".join(per) if n else out[-600:])


def stop(a):
    studio().stop(); print("stopped")


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("launch"); l.add_argument("cand"); l.add_argument("--panel", default="")
    l.add_argument("--maps", default="all"); l.add_argument("--seeds", type=int, default=1); l.add_argument("--seed-base", type=int, default=0)
    sub.add_parser("fetch"); sub.add_parser("stop")
    a = ap.parse_args()
    {"launch": launch, "fetch": fetch, "stop": stop}[a.cmd](a)


if __name__ == "__main__":
    main()
