"""Download our challenge games and index BOTH sides (us and the opponent), scout-style, so the
profilers can compare the two teams in the very same games.

    uv run --python 3.11 python tools/fetch_challenges.py OUT_DIR BATTLE_ID [BATTLE_ID ...]
"""
import json, os, pathlib, subprocess, sys
BASE = "https://game.battlecode.au/api/v1"
OUR = 98


def get(path):
    r = subprocess.run(["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(r.stdout)


def main():
    out = pathlib.Path(sys.argv[1])
    idx_path = out / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    have = {(e["teamId"], str(e["game"])) for e in index}
    for bid in sys.argv[2:]:
        d = get(f"/battles/{bid}")
        m = d["match"]
        us_side = "A" if m["teamAId"] == OUR else "B"
        opp_id = m["teamBId"] if us_side == "A" else m["teamAId"]
        opp_name = d["teamBName"] if us_side == "A" else d["teamAName"]
        for g in d.get("games", []):
            if g.get("status") != "completed":
                print(f"  {g['id']} not finished, skipped"); continue
            win = (g.get("winner") or "").upper()
            for tid, name, side, opp in (("ours", "ours", us_side, opp_name),
                                          (str(opp_id), opp_name, "B" if us_side == "A" else "A", "ours")):
                (out / tid).mkdir(parents=True, exist_ok=True)
                dst = out / tid / f"{g['id']}.replay"
                if not dst.exists():
                    subprocess.run(["curl", "-sL", "-o", str(dst), f"{BASE}/battles/{g['id']}/replay",
                                    "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"])
                if (tid, str(g["id"])) not in have:
                    index.append({"teamId": tid, "team": name, "rank": None, "elo": 0, "game": g["id"],
                                  "map": g.get("mapName", d.get("mapName", "")), "side": side,
                                  "opponent": opp, "opponentElo": 0, "winner": win})
                    have.add((tid, str(g["id"])))
            print(f"  {g['id']} {g.get('mapName', d.get('mapName'))} vs {opp_name}: winner {win} (we are {us_side})")
    idx_path.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(index)} index entries in {out}")


if __name__ == "__main__":
    main()
