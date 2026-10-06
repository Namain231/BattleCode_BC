"""12 unseen maps x both sides x 1 seed = 24 games of viper_v8 vs V7.12.

    python tools/unseen_panel.py [--bot viper_v8] [-j 8]

Regenerates 12 maps into maps_gen/ if they are missing, then runs tourney.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "maps_gen"
    out.mkdir(exist_ok=True)
    maps = [out / f"gen_{i:03d}.map" for i in range(12)]
    if any(not p.exists() for p in maps):
        print("generating 12 maps into maps_gen/", flush=True)
        r = subprocess.call([sys.executable, str(ROOT / "tools" / "gen_random_maps.py"),
                             "--n", "12", "--out", "maps_gen", "--seed", "1"])
        if r != 0:
            raise SystemExit(r)
    names = ",".join(f"maps_gen/gen_{i:03d}" for i in range(12) if (out / f"gen_{i:03d}.map").exists())
    bot = "viper_v8"
    if "--bot" in sys.argv:
        bot = sys.argv[sys.argv.index("--bot") + 1]
    j = sys.argv[sys.argv.index("-j") + 1] if "-j" in sys.argv else "8"
    cmd = [sys.executable, str(ROOT / "tools" / "tourney.py"), bot, "baselines/v7_12",
           "--seeds", "1", "--maps", names, "-j", j]
    print(" ".join(cmd), flush=True)
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
