"""Pull battle and loss data for any specified bot version from the API.

Usage:
    python tools/pull_v75_losses.py [--version v7.5] [--sub-id 7793] [--out ladder/losses] [--fetch-details]
"""
import argparse
import io
import json
import os
import pathlib
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

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
            time.sleep(1 + attempt)
            continue
        try:
            data = json.loads(r.stdout)
            if isinstance(data, dict) and "error" in data:
                print(f"API Error for {path}: {data['error']}", file=sys.stderr)
            return data
        except json.JSONDecodeError:
            time.sleep(1 + attempt)
    raise RuntimeError(f"Failed to get valid JSON from {path}")

def parse_args():
    parser = argparse.ArgumentParser(description="Pull losses and match data for any bot version.")
    parser.add_argument("--version", default="v7.5", help="Bot version name, alias, or substring (default: 'v7.5'). Use 'all' for all versions.")
    parser.add_argument("--sub-id", type=int, default=None, help="Explicit submission ID (e.g. 7793)")
    parser.add_argument("--out", default="ladder/losses", help="Output directory (default: ladder/losses)")
    parser.add_argument("--fetch-details", action="store_true", default=True, help="Fetch scores, seeds, and logs for losses")
    return parser.parse_args()

def main():
    args = parse_args()
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to UNSW Battlecode API...")
    me = api_get("/me")
    our_team_id = me["team"]["id"]
    our_team_name = me["team"]["name"]
    print(f"Authenticated as Team #{our_team_id}: {our_team_name}")

    print("Fetching submissions...")
    subs_list = api_get("/submissions")
    subs_map = {s["id"]: s for s in subs_list}

    target_sub_ids = set()
    target_label = args.version

    if args.sub_id is not None:
        target_sub_ids.add(args.sub_id)
        sub_info = subs_map.get(args.sub_id, {})
        target_label = sub_info.get("name", f"sub_{args.sub_id}")
    elif args.version.lower() == "all":
        target_sub_ids = set(subs_map.keys())
        target_label = "all"
    else:
        q = args.version.lower()
        for sid, s in subs_map.items():
            name = s.get("name", "").lower()
            if q == str(sid) or q in name or name.startswith(q) or q in name.replace("-", "").replace(".", ""):
                target_sub_ids.add(sid)
        if not target_sub_ids:
            print(f"Warning: No submission found matching '{args.version}'. Available submissions:")
            for sid in sorted(subs_map.keys(), reverse=True):
                print(f"  ID {sid}: {subs_map[sid].get('name')}")
            sys.exit(1)

    print(f"Target version: '{target_label}' -> Matching submission IDs: {sorted(target_sub_ids)}")

    print("Fetching battles from /battles?limit=200...")
    battles_summary = api_get("/battles?limit=200")
    print(f"Found {len(battles_summary)} battles.")

    version_games = []
    version_losses = []

    print("Retrieving battle details (rate paced)...")
    for idx, b in enumerate(battles_summary):
        bid = b["id"]
        detail = api_get(f"/battles/{bid}")
        time.sleep(0.15)  # rate pacing

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

        if our_sub_id not in target_sub_ids:
            continue

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
            version_games.append(game_rec)
            if is_loss:
                version_losses.append(game_rec)

        if (idx + 1) % 25 == 0 or idx == len(battles_summary) - 1:
            print(f"Processed {idx + 1}/{len(battles_summary)} battles. Target games: {len(version_games)} (Losses: {len(version_losses)})", flush=True)

    wins_count = len([g for g in version_games if g["outcome"] == "win"])
    losses_count = len(version_losses)
    draws_count = len([g for g in version_games if g["outcome"] == "draw"])
    print(f"\nSummary for {target_label}:")
    print(f"  Total Games: {len(version_games)}")
    print(f"  Wins:        {wins_count}")
    print(f"  Losses:      {losses_count}")
    print(f"  Draws:       {draws_count}")

    if args.fetch_details and version_losses:
        print(f"\nFetching match details (scores, seed, log) for {len(version_losses)} loss games...")
        for i, l in enumerate(version_losses):
            gid = l["gameId"]
            g_detail = api_get(f"/battles/{gid}")
            g_match = g_detail.get("match", {})
            l["scoresA"] = g_match.get("scoresA")
            l["scoresB"] = g_match.get("scoresB")
            l["ourScore"] = g_match.get("scoresA") if l["ourSide"] == "A" else g_match.get("scoresB")
            l["oppScore"] = g_match.get("scoresB") if l["ourSide"] == "A" else g_match.get("scoresA")
            l["seed"] = g_match.get("seed")
            l["log"] = g_match.get("log")
            time.sleep(0.15)
            if (i + 1) % 25 == 0 or i == len(version_losses) - 1:
                print(f"  Fetched details for {i + 1}/{len(version_losses)} loss games...", flush=True)

    # Save output JSON
    clean_tag = target_label.replace(".", "").replace("-", "_").replace(" ", "_")
    losses_file = out_dir / f"{clean_tag}_losses.json"
    games_file = out_dir / f"{clean_tag}_games.json"

    with open(losses_file, "w", encoding="utf-8") as f:
        json.dump(version_losses, f, indent=2, ensure_ascii=False)
    with open(games_file, "w", encoding="utf-8") as f:
        json.dump(version_games, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(version_losses)} losses to {losses_file}")
    print(f"Saved {len(version_games)} games to {games_file}")

if __name__ == "__main__":
    main()
