"""Turn a local tourney.py replay batch into a scout-style dir, so behaviour_profile.py,
death_context.py, sonar_profile.py and profile_style.py can profile BOTH bots of a local A/B from the
very same games (a paired comparison, which is far less noisy than two separate batches).

    uv run --python 3.11 python tools/local_index.py ladder/late1_vs_champ late1 champion ladder/late1_prof

tourney.py names replays <map>_<seed>_<side>.replay, where side A means the FIRST bot on its command
line played team A, and logs "[WIN ] <map> as A seed 1000: ..." from the first bot's point of view.
Writes <out>/<label>/<stem>.replay (hard links, else copies) and <out>/index.json.
"""
import json
import os
import pathlib
import re
import shutil
import sys

LINE = re.compile(r"\[(WIN |LOSS|DRAW|ERR[A-Z ]*)\]\s+(\S+)\s+as ([AB]) seed (\d+)")


def main():
    src, first, second, out = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], pathlib.Path(sys.argv[4])
    res = {}
    log = src / "t.log"
    if log.exists():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LINE.search(line)
            if m:
                res[(m.group(2).replace("/", "_").replace("\\", "_"), m.group(4), m.group(3))] = m.group(1).strip()
    index = []
    for label in (first, second):
        (out / label).mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.replay")):
        stem = f.stem
        mp, seed, side = stem.rsplit("_", 2)
        r = res.get((mp, seed, side))
        # winner as a game side letter: the first bot played `side`
        if r == "WIN":
            winner = side
        elif r == "LOSS":
            winner = "B" if side == "A" else "A"
        else:
            winner = ""
        other = "B" if side == "A" else "A"
        for label, s in ((first, side), (second, other)):
            dst = out / label / f.name
            if not dst.exists():
                try:
                    os.link(f, dst)
                except OSError:
                    shutil.copy2(f, dst)
            index.append({"teamId": label, "team": label, "rank": None, "elo": 0, "game": stem,
                          "map": mp, "side": s, "opponent": second if label == first else first,
                          "opponentElo": 0, "winner": winner})
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    known = sum(1 for e in index if e["winner"]) // 2
    print(f"{len(index) // 2} games -> {out} ({known} with a known result)")


if __name__ == "__main__":
    main()
