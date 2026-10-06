"""v_off (every V8 flag off) vs baselines/v7_12 must land near 50%.

    python tools/harness_sanity.py [-j 8]

20 games: 10 live maps, both sides, one seed. Until this is ~10/20, ablation
numbers against V7.12 are confounded.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE = "portals,slithery_fight,schooltime,trophy,queen_of_spades,default,dilemma,autarky,devil,trauma"


def main():
    src = ROOT / "viper_v8"
    dst = ROOT / "exp_v8" / "v_off"
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("main.cpp", "maps_data.hpp", "bot.toml"):
        shutil.copy2(src / name, dst / name)
    shutil.copy2(ROOT / "exp_v8" / "flags_off.hpp", dst / "flags_cfg.hpp")
    cmd = [sys.executable, str(ROOT / "tools" / "tourney.py"), str(dst.relative_to(ROOT)).replace("\\", "/"),
           "baselines/v7_12", "--seeds", "1", "--maps", LIVE, "-j", sys.argv[sys.argv.index("-j") + 1] if "-j" in sys.argv else "8"]
    print(" ".join(cmd), flush=True)
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
