"""Poll our own ladder battles (continuous autoscrims) and download every finished game.

    python -u tools/our_games.py [--every 2] [--out ladder/ours_nr] [--since 2026-10-01T12:00]

Writes <out>/<map>_<A|B>_<gameId>.replay (our side in the name, so queen_report/cycle tools work) and appends
<out>/index.jsonl: battle, game, map, side, opponent, opponentElo, won, ranked, eloChange, at, submission (active then).
Prints one line per finished battle. The API lists only ~6 recent battles, so keep the poll interval short.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ab_live as A  # noqa: E402

TEAM = 98


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=2); ap.add_argument("--out", default="ladder/ours_nr")
    ap.add_argument("--since", default="2026-10-01T12:00"); ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ixp = out / "index.jsonl"
    seen = set()
    if ixp.exists():
        for l in ixp.read_text(encoding="utf-8").splitlines():
            if l.strip(): seen.add(json.loads(l)["battle"])
    while True:
        try:
            prof = A.api(f"/teams/{TEAM}")
            active = A.active_id()
            for b in prof.get("recent", []):
                if b["id"] in seen or b["at"] < a.since or "pending" in b.get("results", []):
                    continue
                d = A.api(f"/battles/{b['id']}")
                if "games" not in d or any(g.get("status") != "completed" for g in d["games"]):
                    continue
                m = d["match"]; side = "A" if m["teamAId"] == TEAM else "B"
                rows = []
                for g in d["games"]:
                    mp = g["mapName"].replace(" ", "_").lower()
                    path = out / f"{mp}_{side}_{g['id']}.replay"
                    if not path.exists() or path.stat().st_size < 2000:
                        subprocess.run(["curl", "-sL", "-o", str(path), f"{A.BASE}/battles/{g['id']}/replay",
                                        "-H", f"Authorization: Bearer {os.environ['UNSWBC_KEY']}"])
                        time.sleep(0.5)
                    won = (g.get("winner") or "").upper() == side
                    rows.append({"battle": b["id"], "game": g["id"], "map": mp, "side": side, "opponent": b["opponent"],
                                 "opponentElo": b["opponentElo"], "won": won, "ranked": b["ranked"],
                                 "eloChange": b.get("eloChange"), "at": b["at"], "submission": active, "path": str(path)})
                try:   # the build that really played (replay header), not whatever is active now
                    import replay as RP
                    hdr = RP._decode(rows[0]["path"])
                    bot = hdr.get("botA") if side == "A" else hdr.get("botB")
                    if bot:
                        for r in rows: r["played_by"] = str(bot)
                except Exception:
                    pass
                with open(ixp, "a", encoding="utf-8") as f:
                    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
                seen.add(b["id"])
                print(f"[{time.strftime('%H:%M')}] {b['opponent'][:22]:22s} {b['opponentElo']:5} "
                      f"{''.join('W' if r['won'] else 'L' for r in rows)} elo {b.get('eloChange')} played_by {rows[0].get('played_by', '?')} (active {active})", flush=True)
        except Exception as e:  # network hiccups: keep polling
            print("poll error", e, flush=True)
        if a.once: break
        time.sleep(a.every * 60)


if __name__ == "__main__":
    main()
