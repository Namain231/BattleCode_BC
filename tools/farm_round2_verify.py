"""Round-2 regression checks: no judge/game launch; fixture writes only on F:."""
import json, os, shlex, sys, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).absolute().parent))
import farm_scale as f
stage = Path(sys.argv[1])
fixture = stage / 'verification'
p = f.panel
class Captured(Exception): pass
calls = []
def capture(args, **kwargs):
    calls.append(args)
    raise Captured
# Includes spaces, apostrophes, command substitution, semicolons and dollar signs.
paths = ["F:/farm stage/a';$(touch BAD);$x.wasm", "F:/farm stage/b bot.wasm",
         "F:/farm stage/engine';$x.wasm", "F:/farm stage/judge';$x",
         "F:/farm stage/lease';$(touch BAD)"]
for explicit in (True, False):
    with patch.object(p, 'USE_WSL', True), patch.object(p, 'JUDGE', paths[3]), \
         patch.object(p, 'ENGINE', paths[2]), patch.object(p, '_wslpath', lambda x: '/mnt/f/' + str(x)), \
         patch.object(p.subprocess, 'run', capture), \
         patch.dict(os.environ, {'LOONG_JUDGE': paths[3]} if explicit else {}, clear=True):
        try: p.play(paths[0], paths[1], 'stripes', 123, 'A', str(stage / "space ';$x"), lease=paths[4])
        except Captured: pass
        else: raise AssertionError('mock not reached')
        tokens = shlex.split(calls[-1][-1])
        assert tokens[:4] == ['flock', '/mnt/f/' + paths[4], 'nice', '-n']
        assert tokens[5] == ('/mnt/f/' + paths[3] if explicit else '$HOME/toolchains/zig-judge-out/bin/loong-judge')
        for flag, value in [('--a', paths[0]), ('--b', paths[1]), ('--engine', paths[2])]:
            assert tokens[tokens.index(flag) + 1] == '/mnt/f/' + value
        assert len(tokens) == 20, tokens
print('PASS: explicit/default WSL judge, every pathname remains one shell argument')
original = Path.read_text
reads = {}
def counted(path, *args, **kwargs):
    reads[path.name] = reads.get(path.name, 0) + 1
    return original(path, *args, **kwargs)
with patch.object(Path, 'read_text', counted): rows = f.checkpoints(fixture)
assert reads['manifest.json'] == reads['jobs.json'] == 1
assert len(rows) == 8
with patch.object(f, 'checkpoints', side_effect=AssertionError('unexpected full state rescan')):
    f.summarize(fixture, rows)
print('PASS: eight checkpoints, one manifest parse; supplied rows summary avoids state rescan')
# Large-plan parse cost: repeat an entire checkpoint validation 100 times with the
# production-size manifest, but mock checkpoint files/rows to avoid 172k disk writes.
manifest = json.loads((fixture/'manifest.json').read_text())
manifest['padding'] = 'x' * 371544
job = json.loads((fixture/'jobs.json').read_text())[0]
row = rows[0]
blob = json.dumps(manifest)
read_counts = {'manifest': 0}
def synthetic_read(path, *args, **kwargs):
    if path.name == 'manifest.json':
        read_counts['manifest'] += 1
        return blob
    if path.name == 'jobs.json': return json.dumps([job])
    return json.dumps(row)
started = time.perf_counter()
with patch.object(Path, 'read_text', synthetic_read), patch.object(Path, 'glob', return_value=[Path(job['id']+'.json')]):
    for _ in range(100): assert len(f.checkpoints(fixture)) == 1
assert read_counts['manifest'] == 100
print(f'PASS: 100 validations of 371k+ manifest: {time.perf_counter()-started:.3f}s; exactly 100 parses')
