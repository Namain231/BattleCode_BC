"""Download and analyze replays for any specified bot version's losses.

Usage:
    python tools/pull_75_replays.py [--version v7.5] [--limit 0] [--analyze]
"""
import argparse
import glob
import io
import json
import os
import pathlib
import subprocess
import sys
import time
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TOOLS_DIR)
for p in (TOOLS_DIR, ROOT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from replay import load, DEATHS

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

def parse_args():
    parser = argparse.ArgumentParser(description="Download and analyze replays for any bot version.")
    parser.add_argument("--version", default="v7.5", help="Target bot version (default: 'v7.5')")
    parser.add_argument("--losses-file", default=None, help="Path to losses JSON (if omitted, searches ladder/losses/)")
    parser.add_argument("--out", default=None, help="Directory to save replays (default: ladder/losses/{version}_replays)")
    parser.add_argument("--limit", type=int, default=0, help="Max replays to download (0 = all, default: 0)")
    parser.add_argument("--analyze-only", action="store_true", help="Skip downloading, analyze existing replays")
    return parser.parse_args()

def main():
    args = parse_args()
    clean_ver = args.version.replace(".", "").replace("-", "_").replace(" ", "_")

    if args.losses_file:
        losses_path = pathlib.Path(args.losses_file)
    else:
        # Search for matching losses file
        candidates = list(pathlib.Path("ladder/losses").glob(f"*{clean_ver}*losses.json"))
        if candidates:
            losses_path = candidates[0]
        else:
            losses_path = pathlib.Path(f"ladder/losses/{clean_ver}_losses.json")

    replays_dir = pathlib.Path(args.out) if args.out else pathlib.Path(f"ladder/losses/{clean_ver}_replays")
    replays_dir.mkdir(parents=True, exist_ok=True)

    if not args.analyze_only:
        if not losses_path.exists():
            print(f"Losses file {losses_path} not found. Running pull_v75_losses.py first for version '{args.version}'...")
            subprocess.run([sys.executable, "tools/pull_v75_losses.py", "--version", args.version])
        
        if not losses_path.exists():
            print(f"Error: Could not locate losses file at {losses_path}")
            sys.exit(1)

        with open(losses_path, "r", encoding="utf-8") as f:
            losses = json.load(f)

        print(f"Loaded {len(losses)} losses from {losses_path}")
        dl_list = [l for l in losses if l.get("hasReplay")]
        if args.limit > 0:
            dl_list = dl_list[:args.limit]

        print(f"Downloading {len(dl_list)} replays to {replays_dir}...")
        for idx, g in enumerate(dl_list):
            gid = g["gameId"]
            mname = g.get("mapName", "map").replace(" ", "_")
            opp = g.get("oppName", "opp").replace(" ", "_")
            r_path = replays_dir / f"{gid}_{mname}_{opp}.replay"
            g["replayPath"] = str(r_path)

            if not r_path.exists() or r_path.stat().st_size == 0:
                subprocess.run(["curl", "-sL", "-o", str(r_path), f"{BASE}/battles/{gid}/replay", "-H", f"Authorization: Bearer {KEY}"])
                time.sleep(0.15)

            if (idx + 1) % 20 == 0 or idx == len(dl_list) - 1:
                print(f"  Downloaded {idx + 1}/{len(dl_list)} replays...", flush=True)

    # Analyze replays in directory
    replay_files = sorted(replays_dir.glob("*.replay"))
    if not replay_files:
        print(f"No replays found in {replays_dir}")
        return

    print(f"\n==========================================================================")
    print(f"DEEP REPLAY ANALYSIS: {len(replay_files)} REPLAYS FOR VERSION '{args.version}'")
    print(f"==========================================================================")

    records = []
    for path in replay_files:
        try:
            rep = load(str(path))
        except Exception as e:
            print(f"Error loading {path.name}: {e}")
            continue

        fn = path.name
        lines = rep['map'].splitlines() if rep.get('map') else []
        map_name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), lines[0] if lines else "?")
        res = rep.get('result', {}) or {}

        team = {}
        nid = 0
        for l in lines:
            p = l.split()
            if p and p[0] == "DRAGON":
                team[nid] = int(p[1])
                nid += 1

        deaths = [Counter(), Counter()]
        rounds = 0

        for e in rep.get('events', []):
            k = e['kind']
            if k == 'roundStart':
                rounds = e['round']
            elif k == 'dragonSplit':
                team[e['child']] = e['team']
            elif k == 'dragonDeath':
                i = e['id']
                t = team.get(i)
                r = e['reason']
                r_str = DEATHS[r] if r < len(DEATHS) else str(r)
                if t in (0, 1):
                    deaths[t][r_str] += 1

        # We assume Team A is index 0, Team B is index 1
        stats_a = res.get('A', {}) or {}
        stats_b = res.get('B', {}) or {}
        winner = res.get('winner')
        end_reason = res.get('endReason')

        # Side resolution from filename if possible
        # Default Team 0 = our bot
        our_t = 0
        opp_t = 1

        rec = {
            "file": fn,
            "map": map_name,
            "rounds": rounds,
            "winner": winner,
            "endReason": "elimination" if end_reason == 0 else ("round_limit" if end_reason == 1 else str(end_reason)),
            "ourCount": (stats_a if our_t == 0 else stats_b).get('count', 0),
            "ourLongest": (stats_a if our_t == 0 else stats_b).get('longest', 0),
            "ourTotal": (stats_a if our_t == 0 else stats_b).get('total', 0),
            "oppCount": (stats_b if our_t == 0 else stats_a).get('count', 0),
            "oppLongest": (stats_b if our_t == 0 else stats_a).get('longest', 0),
            "oppTotal": (stats_b if our_t == 0 else stats_a).get('total', 0),
            "ourDeaths": dict(deaths[our_t]),
            "oppDeaths": dict(deaths[opp_t])
        }
        records.append(rec)

    # Print summary table
    print(f"{'Map':<18} {'Rounds':<7} {'End Reason':<13} {'Our Units':<10} {'Opp Units':<10} {'Our Lgst/Tot':<13} {'Opp Lgst/Tot':<13} {'Our Top Death Causes'}")
    print("-" * 130)
    for r in sorted(records, key=lambda x: (x['map'], x['rounds'])):
        our_u = f"{r['ourCount']}"
        opp_u = f"{r['oppCount']}"
        our_lt = f"{r['ourLongest']}/{r['ourTotal']}"
        opp_lt = f"{r['oppLongest']}/{r['oppTotal']}"
        top_d = sorted(r['ourDeaths'].items(), key=lambda x: x[1], reverse=True)[:3]
        deaths_str = ", ".join(f"{k}:{v}" for k, v in top_d)
        print(f"{r['map']:<18} {r['rounds']:<7} {r['endReason']:<13} {our_u:<10} {opp_u:<10} {our_lt:<13} {opp_lt:<13} {deaths_str}")

    eliminated = sum(1 for r in records if r['ourCount'] == 0)
    time_limit = sum(1 for r in records if r['endReason'] == 'round_limit')
    print(f"\nAggregate Replay Metrics ({len(records)} total):")
    print(f"  Team Eliminations (Wiped out): {eliminated} ({eliminated/len(records)*100:.1f}%)")
    print(f"  Round 500 Timeouts:           {time_limit} ({time_limit/len(records)*100:.1f}%)")

    total_our_deaths = Counter()
    total_opp_deaths = Counter()
    for r in records:
        total_our_deaths.update(r['ourDeaths'])
        total_opp_deaths.update(r['oppDeaths'])

    print("\nTotal Death Causes:")
    for k, v in total_our_deaths.most_common():
        opp_v = total_opp_deaths.get(k, 0)
        print(f"  {k:<20}: Ours {v:4d} | Opponent {opp_v:4d}")

if __name__ == "__main__":
    main()
