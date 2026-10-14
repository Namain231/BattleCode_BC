"""Resolve committed shards only; validate hashes, sample counts and game ownership."""
import hashlib
import json
from pathlib import Path
import numpy as np


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def owned_shards(directory, audit=None):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    games = {int(g['game']) for g in manifest['games']}
    if 'exported_game_ids' in manifest:
        assert set(map(int, manifest['exported_game_ids'])) == games, 'incomplete export'
    previous = json.loads(Path(audit).read_text()) if audit and Path(audit).exists() else None
    identity = {'manifest': sha256(directory / 'manifest.json'), 'shards': {}, 'game_ids': sorted(games)}
    files = []; observed = set(); samples = 0
    for info in manifest['shards']:
        p = directory / info['file']
        assert p.parent.resolve() == directory.resolve(), 'invalid shard path'
        digest = sha256(p)
        if info.get('sha256'):
            assert digest == info['sha256'], 'shard hash mismatch'
        identity['shards'][info['file']] = digest
        with np.load(p) as z:
            ids = set(map(int, np.unique(z['game'])))
            n = len(z['game'])
            assert n == info['samples'] and len(z['labels']) == n, 'sample count mismatch'
            assert ids <= games, 'unowned games in shard'
            observed.update(ids); samples += n
        files.append(str(p))
    assert files and samples == manifest['total_samples'], 'incomplete shard generation'
    # Team capping can remove whole games; explicitly record that coverage.
    identity['represented_games'] = sorted(observed)
    identity['capped_out_games'] = sorted(games - observed)
    if previous is not None:
        assert previous == identity, 'committed shard identity changed'
    elif audit:
        target = Path(audit); target.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(target) + '.tmp')
        tmp.write_text(json.dumps(identity, indent=2), encoding='utf-8'); tmp.replace(target)
    return files
