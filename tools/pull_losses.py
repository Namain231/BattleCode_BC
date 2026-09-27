"""Pull and analyze all historical loss data against opponents from the API.

Usage:
    python tools/pull_losses.py [--download-recent-replays] [--out ladder/losses]
"""
import argparse
import collections
import json
import os
import pathlib
import subprocess
import sys
import time

BASE = "https://game.battlecode.au/api/v1"

def get_key():
    if "UNSWBC_KEY" in os.environ:
        return os.environ["UNSWBC_KEY"]
    if os.path.exists("secrets.env"):
        with open("secrets.env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("UNSWBC_KEY="):
                    return line.split("=", 1)[1].strip()
    raise RuntimeError("No UNSWBC_KEY found in environment or secrets.env")

KEY = get_key()

def api_get(path):
    for attempt in range(5):
        r = subprocess.run(
            ["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {KEY}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if not r.stdout.strip():
            time.sleep(2 + 2 * attempt)
            continue
        try:
            data = json.loads(r.stdout)
            if isinstance(data, dict) and "error" in data:
                print(f"API Error for {path}: {data['error']}", file=sys.stderr)
            return data
        except json.JSONDecodeError:
            time.sleep(2 + 2 * attempt)
    raise RuntimeError(f"Failed to get valid JSON from {path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="ladder/losses", help="Output directory")
    parser.add_argument("--fetch-game-details", action="store_true", help="Fetch detailed match info for each lost game")
    parser.add_argument("--download-replays", type=int, default=0, help="Download N most recent lost game replays")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch team info and submissions
    print("Fetching /me and /team...", flush=True)
    me = api_get("/me")
    our_team_id = me["team"]["id"]
    our_team_name = me["team"]["name"]
    print(f"Authenticated as Team #{our_team_id}: {our_team_name}")

    print("Fetching submissions...", flush=True)
    subs_list = api_get("/submissions")
    subs_map = {s["id"]: s for s in subs_list}
    print(f"Loaded {len(subs_map)} submissions.")

    # 2. Fetch battles
    print("Fetching battles list...", flush=True)
    battles_summary = api_get("/battles?limit=200")
    print(f"Found {len(battles_summary)} battles.")

    # 3. Fetch each battle's full details
    all_losses = []
    all_games = []
    all_battles_detailed = []

    print("Fetching detailed battle info (with rate pacing)...", flush=True)
    for idx, b in enumerate(battles_summary):
        bid = b["id"]
        detail = api_get(f"/battles/{bid}")
        all_battles_detailed.append(detail)
        time.sleep(0.3)  # stay well within 120 req/min

        match = detail.get("match", {})
        team_a_name = detail.get("teamAName", "")
        team_b_name = detail.get("teamBName", "")
        team_a_id = match.get("teamAId")
        team_b_id = match.get("teamBId")
        team_a_elo = detail.get("teamAElo")
        team_b_elo = detail.get("teamBElo")
        sub_a_id = match.get("submissionAId")
        sub_b_id = match.get("submissionBId")
        is_ranked = match.get("ranked", b.get("ranked", False))
        created_at = match.get("requestedAt") or b.get("at")

        our_side = "a" if team_a_id == our_team_id or team_a_name == our_team_name else ("b" if team_b_id == our_team_id or team_b_name == our_team_name else None)
        if not our_side:
            continue

        opp_side = "b" if our_side == "a" else "a"
        opp_name = team_b_name if our_side == "a" else team_a_name
        opp_id = team_b_id if our_side == "a" else team_a_id
        opp_elo = team_b_elo if our_side == "a" else team_a_elo
        our_sub_id = sub_a_id if our_side == "a" else sub_b_id
        opp_sub_id = sub_b_id if our_side == "a" else sub_a_id
        our_sub_name = subs_map.get(our_sub_id, {}).get("name", f"sub_{our_sub_id}")

        games = detail.get("games", [])
        for g in games:
            gid = g["id"]
            map_name = g.get("mapName", "")
            winner = (g.get("winner") or "").lower()
            status = g.get("status")
            has_replay = g.get("hasReplay", False)

            is_win = (winner == our_side)
            is_loss = (winner == opp_side)
            is_draw = (winner == "draw" or (status == "completed" and not is_win and not is_loss))

            game_rec = {
                "battleId": bid,
                "gameId": gid,
                "createdAt": created_at,
                "ranked": is_ranked,
                "mapName": map_name,
                "ourSide": our_side.upper(),
                "ourSubId": our_sub_id,
                "ourSubName": our_sub_name,
                "oppId": opp_id,
                "oppName": opp_name,
                "oppElo": opp_elo,
                "oppSubId": opp_sub_id,
                "winner": winner.upper(),
                "outcome": "win" if is_win else ("loss" if is_loss else "draw"),
                "hasReplay": has_replay
            }
            all_games.append(game_rec)
            if is_loss:
                all_losses.append(game_rec)

        if (idx + 1) % 10 == 0 or idx == len(battles_summary) - 1:
            print(f"Processed {idx + 1}/{len(battles_summary)} battles. Losses found so far: {len(all_losses)}", flush=True)

    print(f"\nTotal games: {len(all_games)}, Total losses: {len(all_losses)}")

    # 4. Optional: fetch specific game details for losses (scores, seeds, logs)
    if args.fetch_game_details:
        print(f"Fetching game details for {len(all_losses)} losses...", flush=True)
        for i, l in enumerate(all_losses):
            gid = l["gameId"]
            g_detail = api_get(f"/battles/{gid}")
            g_match = g_detail.get("match", {})
            l["scoresA"] = g_match.get("scoresA")
            l["scoresB"] = g_match.get("scoresB")
            l["ourScore"] = g_match.get("scoresA") if l["ourSide"] == "A" else g_match.get("scoresB")
            l["oppScore"] = g_match.get("scoresB") if l["ourSide"] == "A" else g_match.get("scoresA")
            l["seed"] = g_match.get("seed")
            l["log"] = g_match.get("log")
            time.sleep(0.3)
            if (i + 1) % 20 == 0:
                print(f"Fetched details for {i + 1}/{len(all_losses)} loss games...", flush=True)

    # 5. Optional: download replays for recent losses
    if args.download_replays > 0:
        replays_dir = out_dir / "replays"
        replays_dir.mkdir(parents=True, exist_ok=True)
        to_dl = [l for l in all_losses if l.get("hasReplay")][:args.download_replays]
        print(f"Downloading {len(to_dl)} replays...", flush=True)
        for l in to_dl:
            gid = l["gameId"]
            r_path = replays_dir / f"{gid}_{l['mapName'].replace(' ', '_')}_{l['oppName'].replace(' ', '_')}.replay"
            l["replayPath"] = str(r_path)
            if not r_path.exists():
                subprocess.run(["curl", "-sL", "-o", str(r_path), f"{BASE}/battles/{gid}/replay",
                                "-H", f"Authorization: Bearer {KEY}"])
            time.sleep(0.3)

    # 6. Save raw structured dataset
    data_out = {
        "team": {"id": our_team_id, "name": our_team_name},
        "extractedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "totalBattles": len(all_battles_detailed),
            "totalGames": len(all_games),
            "totalWins": len([g for g in all_games if g["outcome"] == "win"]),
            "totalLosses": len(all_losses),
            "totalDraws": len([g for g in all_games if g["outcome"] == "draw"])
        },
        "losses": all_losses,
        "allGames": all_games,
        "submissions": subs_map
    }
    raw_path = out_dir / "losses_dataset.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data_out, f, indent=2, ensure_ascii=False)
    print(f"Saved dataset to {raw_path}")

if __name__ == "__main__":
    main()
