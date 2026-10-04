# Run from the repo root after the requested panels.
import hashlib
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, 'tools')
from replay_lite import decode_lite

candidate = Path(__file__).parent
judge_cpu = {}
for line in (candidate/'cpu_smoke.txt').read_text().splitlines():
    game = line.split()[0]
    triples = re.findall(r'(\d+)/(\d+)/(\d+)', line)
    assert len(triples)==2
    judge_cpu[game] = int(triples[0 if game.endswith('_A.replay') else 1][2])
assert len(judge_cpu)==4
source=(candidate/'main.cpp').read_text()
expected_off=source.replace('int qposFrom = 12;', 'int qposFrom = 0;').replace('encryptPayload = true, statusRay = true, guardZone = true','encryptPayload = false, statusRay = false, guardZone = false').replace('guardIntercept = true, laneEcho = true, enemyPing = true','guardIntercept = false, laneEcho = false, enemyPing = false')
assert Path('viper_y96qg_off/main.cpp').read_text()==expected_off

off = json.loads(Path('out/qg_off_chk/summary.json').read_text())
control = json.loads(Path('out/qf_chk/summary.json').read_text())
assert off == control, 'Final-source summary divergence'
kinds = {'roundStart', 'turnStart', 'dragonAction', 'sonarPing', 'dragonUpdate',
         'dragonSplit', 'dragonDeath', 'dragonIndicator', 'dragonLog',
         'engineLog', 'tileChange'}
parity = []
for row in off:
    name = f"{row['map']}_{row['seed']}_{row['side']}.replay"
    left = decode_lite('out/qg_off_chk/' + name, kinds)
    right = decode_lite('out/qf_chk/' + name, kinds)
    for replay in (left, right):
        for event in replay['events']:
            event.pop('points', None)
    assert left['events'] == right['events'], name + ': gameplay/sonar divergence'
    parity.append({'game': name, 'identical_events': len(left['events'])})
    del left, right
cpu = []
for replay in sorted(Path('out/qg_cpu').glob('*.replay')):
    data = decode_lite(str(replay), {'dragonAction', 'dragonSplit'})
    teams = {}
    for line in data['map'].splitlines():
        fields = line.split()
        if fields and fields[0] == 'DRAGON':
            teams[len(teams)] = int(fields[1])
    ours = 0 if replay.stem.endswith('_A') else 1
    peak = 0
    for event in data['events']:
        if event['kind'] == 'dragonSplit':
            teams[event['child']] = event['team']
        elif teams.get(event['id']) == ours:
            peak = max(peak, event.get('points', 0))
    if peak:
        assert peak==judge_cpu[replay.name]
    peak=judge_cpu[replay.name]  # local replays strip instruction counters
    cpu.append({'game': replay.name, 'candidate_cpu_max': peak})
    del data
assert len(cpu) == 4
peak = max(row['candidate_cpu_max'] for row in cpu)
if peak:
    assert peak <= 66_000_000, peak
result = {'parity_games': len(parity), 'summaries_identical': True,
          'gameplay_events_identical_excluding_cpu': parity, 'cpu_games': cpu,
          'candidate_cpu_max': peak, 'cpu_source': 'judge stdout; replay counters stripped',
          'main_sha256': hashlib.sha256((candidate/'main.cpp').read_bytes()).hexdigest()}
(candidate/'verification.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, indent=2))
