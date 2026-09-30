"""Merge self-play collections from several machines into one indexed folder with unique game ids.

    python ml/merge_selfplay.py --out ladder/selfplay2 SRC [SRC ...] [--maze-only]

Each SRC is a folder holding index.json + <id>.replay files, as written by ml/selfplay_collect.py (Colab, Kaggle,
Lightning or local). Every run numbers its games from 1e9, so ids clash across machines: games are copied as
<out>/<new id>.replay with new ids and the index paths rewritten. Then:
    python ml/build_dataset.py --index <out>/index.json --out ml/data_sp2
"""
import argparse
import json
import pathlib
import shutil

MAZE = {"trophy", "queen_of_spades", "default", "dilemma", "autarky", "devil", "trauma"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("srcs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--maze-only", action="store_true")
    ap.add_argument("--id-base", type=int, default=2 * 10 ** 9, help="first new game id (keep folders disjoint)")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ix_path = out / "index.json"
    index = json.load(open(ix_path)) if ix_path.exists() else []
    have = {g.get("source") for g in index}
    nid = a.id_base + len(index)
    for src in a.srcs:
        src = pathlib.Path(src)
        entries = json.load(open(src / "index.json"))
        added = 0
        for g in entries:
            key = f"{src.resolve()}::{g['game']}"
            if key in have or (a.maze_only and g.get("map") not in MAZE):
                continue
            rp = src / pathlib.Path(g["path"].replace("\\", "/")).name
            if not rp.exists():
                continue
            dst = out / f"{nid}.replay"
            shutil.copyfile(rp, dst)
            index.append({**g, "game": nid, "path": str(dst), "source": key})
            nid += 1; added += 1
        print(f"{src}: +{added} games")
        json.dump(index, open(ix_path, "w"))
    print(f"{len(index)} games in {ix_path}")


if __name__ == "__main__":
    main()
