"""Enrich recent losses with match scores, seed, logs, and download sample replays.
"""
import io
import json
import os
import pathlib
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = "https://game.battlecode.au/api/v1"
with open("secrets.env", "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("UNSWBC_KEY="):
            KEY = line.split("=", 1)[1].strip()

def api_get(path):
    for attempt in range(4):
        r = subprocess.run(
            ["curl", "-s", BASE + path, "-H", f"Authorization: Bearer {KEY}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        try:
            return json.loads(r.stdout)
        except:
            time.sleep(1 + attempt)
    return {}

dataset_path = pathlib.Path("ladder/losses/losses_dataset.json")
with open(dataset_path, "r", encoding="utf-8") as f:
    data = json.load(f)

recent_versions = {'v7.7-viable-buds', 'v7.6-escapable-miners', 'v7.5-miners', 'v7.4-numbers'}
recent_losses = [g for g in data['losses'] if g.get('ourSubName') in recent_versions]
print(f"Recent losses in v7.4-v7.7: {len(recent_losses)}")

# Fetch score details
for idx, g in enumerate(recent_losses):
    gid = g['gameId']
    detail = api_get(f"/battles/{gid}")
    m = detail.get('match', {})
    g['scoresA'] = m.get('scoresA')
    g['scoresB'] = m.get('scoresB')
    g['ourScore'] = m.get('scoresA') if g['ourSide'] == 'A' else m.get('scoresB')
    g['oppScore'] = m.get('scoresB') if g['ourSide'] == 'A' else m.get('scoresA')
    g['seed'] = m.get('seed')
    g['log'] = m.get('log')
    time.sleep(0.2)
    if (idx + 1) % 15 == 0:
        print(f"Fetched {idx + 1}/{len(recent_losses)} games...")

# Save back to file
with open(dataset_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("Updated ladder/losses/losses_dataset.json with scores and logs.")

# Download a few replays for devil, autarky, trophy losses
replays_dir = pathlib.Path("ladder/losses/replays")
replays_dir.mkdir(parents=True, exist_ok=True)

targets = [g for g in recent_losses if g.get('mapName') in {'Devil', 'Autarky', 'Trophy'} and g.get('hasReplay')]
print(f"Downloading sample replays for analysis ({len(targets[:6])} games)...")
for g in targets[:6]:
    gid = g['gameId']
    fn = replays_dir / f"{gid}_{g['mapName']}_{g['oppName'].replace(' ', '_')}.replay"
    if not fn.exists():
        subprocess.run(["curl", "-sL", "-o", str(fn), f"{BASE}/battles/{gid}/replay", "-H", f"Authorization: Bearer {KEY}"])
        print(f"Downloaded {fn.name}")
    time.sleep(0.3)

print("Finished enriching losses.")
