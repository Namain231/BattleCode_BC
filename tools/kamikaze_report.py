"""Short report from checkpointed opportunity and panel artifacts."""
import sys
sys.dont_write_bytecode=True
import json, statistics, collections, math, hashlib
from pathlib import Path

def quant(values):
    if not values: return 'n/a'
    values=sorted(values)
    return '/'.join(str(values[round((len(values)-1)*p)]) for p in (.5,.9,.99))

MAPS='around_unsw,australia,islands,maze,stripes,tower_defense,weakhold'
def validate_panel(out):
    dest=Path(out)
    smoke='smoke' in out
    expected={(m,n,side) for m in (['maze'] if smoke else MAPS.split(',')) for n in ([3] if smoke else range(3,10)) for side in 'AB'}
    rows=json.loads((dest/'summary.json').read_text())
    keys=[(r['map'],r['seed'],r['side']) for r in rows]
    if len(keys)!=len(expected) or set(keys)!=expected: raise ValueError('Incorrect panel coverage: '+out)
    audits=json.loads((dest/'audit.json').read_text())
    identities=json.loads((dest/'audit.identity.json').read_text())
    version=hashlib.sha256(Path('tools/kamikaze_measure.py').read_bytes()+Path('tools/replay_lite.py').read_bytes()+Path('tools/engine_sim.py').read_bytes()).hexdigest()
    valid=[]
    for r in rows:
        cpu=r['cpu_max_ours_M']
        if not isinstance(cpu,(int,float)) or not math.isfinite(cpu) or not 0<=cpu<=66: raise ValueError('CPU limit: '+out)
        replay=dest/f"{r['map']}_{r['seed']}_{r['side']}.replay"
        key=str(replay)
        audit=audits.get(key)
        identity=identities.get(key,{})
        digest=hashlib.sha256(replay.read_bytes()).hexdigest()
        if not audit or audit.get('validation') or not audit.get('ordered') or identity.get('version')!=version or identity.get('replay')!=digest or identity.get('me')!=int(r['side']=='B') or identity.get('want') is not None or identity.get('opportunities') is not False: raise ValueError('Invalid replay audit: '+key)
        status=json.loads(Path(str(replay)+'.success.json').read_text())
        from panel_zig import provenance,wasm
        # Build hashes are checked once below; replay completion is checked for every key.
        if status.get('returncode')!=0 or not status.get('identity'): raise ValueError('Unproven completion: '+key)
        valid.append(audit)
    from panel_zig import provenance,wasm
    bot='baselines/Nv30' if out.endswith('kz_ctl') else 'viper_y96nk'
    wa,wb=wasm(bot),wasm('baselines/Y9_6')
    for r in rows:
        replay=dest/f"{r['map']}_{r['seed']}_{r['side']}.replay"
        status=json.loads(Path(str(replay)+'.success.json').read_text())
        if status['identity']!=provenance(wa,wb,r['map'],r['seed'],r['side']): raise ValueError('Build identity mismatch: '+str(replay))
    if len(audits)!=len(expected): raise ValueError('Unexpected audit rows: '+out)
    return rows,valid


def main():
    data=json.loads(Path('out/kz_measure.json').read_text(encoding='utf-8'))
    meta=json.loads(Path('out/kz_measure.identity.json').read_text())
    version=hashlib.sha256(Path('tools/kamikaze_measure.py').read_bytes()+Path('tools/replay_lite.py').read_bytes()+Path('tools/engine_sim.py').read_bytes()).hexdigest()
    if set(meta)!=set(data) or any(m.get('version')!=version for m in meta.values()): raise ValueError('Offline refresh incomplete; do not publish stale counts')
    from panel_zig import file_hash
    if any(m.get('replay')!=(file_hash(p) if Path(p).exists() else None) for p,m in meta.items()): raise ValueError('Offline replay identity changed')
    rows=[r for r in data.values() if r]
    if any(r.get('validation') for r in rows): raise ValueError('Offline reconstruction errors')
    lines=['# Kamikaze experiment (2026-10-07)',
           'Candidate: viper_y96nk, copied from baselines/Nv30; no submission or baseline edits.',
           'Files: candidate main.cpp; tools/panel_zig.py, kamikaze_{measure,unit,run,report}.py; out/kz_work/unit.cpp; AGENTS.md, insights.md, runner/critic task briefs.',
           'Offline audit uses replay-verified submission IDs 17124 / 16651 / 16106 and exact turn states; opportunities are upper bounds before candidate policy guards.',
           'Paths model wrap, portals, kelp, current occupancy, own-body movement, pearls, and up to two affordable paid steps.']
    for label in ('l10','sv53','sv52'):
        rs=[r for p,r in data.items() if r and ('\\'+label+'\\') in p]
        if not rs: continue
        lengths=[n for r in rs for n in r['lengths']]; opportunities=[r for r in rs if r['rounds']]
        lines.append(f'{label}: {len(opportunities)}/{len(rs)} games ({100*len(opportunities)/len(rs):.1f}%) have a chance; fully visible routes in {sum(r["visible_rounds"]>0 for r in rs)} games.')
        lines.append(f'Opportunity rounds/game p50/p90/p99={quant([r["rounds"] for r in rs])}; scout lengths={quant(lengths)}; own queen later dies in {sum(r["later_queen_death"] for r in rs)}/{len(opportunities)} opportunity games.')
    reverse=[x for r in rows for x in r['reverse']]
    lines.append(f'Reverse (enemy-initiated): L<=4 dragons ram our queen in {sum(bool(r["reverse"]) for r in rows)}/{len(rows)} games; lengths p50/p90/p99={quant([x["length"] for x in reverse])}, remaining steps={quant([x["steps"] for x in reverse])}; {sum(x["portal"] for x in reverse)} portal routes.')
    validation=sum((collections.Counter(r['validation']) for r in rows),collections.Counter())
    lines.append(f'Existing tagged attacks already killed the enemy queen head-on in {sum(r["ramkills"] for r in rows)} corpus games; raw opportunities are not all new chances.')
    lines.append(f'Reconstruction errors: {dict(validation)}; excluded missing/identity rows: {sum(r is None for r in data.values())}. No replay pickle caches.')
    lines += ['Rule ON; paid cap L12; early trades L<=4 unless visible enemy length >=2x scout; with current proof our queen lives, any length from r150.',
              'Critical limit: input has no global queen-life/longest census. Require current ally queen segment; otherwise trade only with every ally fully visible and enemy visible length > their longest.',
              'Unknown own body or intermediate occupancy rejects the ram; search capped at 2048 nodes / 40ms. This misses some true opportunities.',
              'Legacy queen attacks use the same guard while ON. Turning OFF restores Nv30 attack behavior. Chase flag OFF; approach efficacy unmeasured.',
              'Unit: uv run --python 3.11 python -B tools/kamikaze_unit.py (actual C++ decision + engine_sim; ram and four rejection cases PASS).',
              'Measure: uv run --python 3.11 python -B tools/kamikaze_measure.py',
              'Panels: uv run --python 3.11 --with unswbc python -B tools/kamikaze_run.py',
              'Smoke subcommand: tools/panel_zig.py viper_y96nk baselines/Y9_6 out/kz_smoke_current --maps maze --seeds 3 -j 1',
              '98-game subcommands: tools/panel_zig.py BOT baselines/Y9_6 OUT --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j J',
              'BOT/OUT: viper_y96nk/out/kz_panel; baselines/Nv30/out/kz_ctl. Zero-other-judge, C:>=3GiB, RAM>=1800MB; J=1 or 2 (2 requires2500MB), reduced from requested4; exact commands saved in each command.json.']
    complete=True; panel_results=[]
    for out in ('out/kz_smoke_current','out/kz_panel','out/kz_ctl'):
        dest=Path(out)
        if not (dest/'DONE').exists(): lines.append(out+': pending; no final result claimed.'); complete=False; continue
        try: rs,audit=validate_panel(out)
        except (ValueError,OSError,KeyError) as e:
            lines.append(out+': invalid/incomplete verification: '+str(e)); complete=False; continue
        wins=sum(r['win'] for r in rs); rams=sum(r.get('queen_rams',r['rams']) for r in audit); kills=sum(r['ramkills'] for r in audit)
        lines.append(f'{out}: {wins}/{len(rs)} wins ({100*wins/len(rs):.1f}%); CPU peak {max(r["cpu_max_ours_M"] for r in rs):.3f}M; rams {rams}, enemy queen ram-kills {kills}, own queen deaths {sum(r["queen_dead"] for r in audit)}/{len(audit)}.')
        panel_results.append((out,wins,rams,kills,len(rs)))
    lines.append('Fix checks: invalid-build cache, cached-None replay/version invalidation, missing coverage and CPU>66M rejection PASS; shared WSL reservation PASS; independent tooling critique PASS.')
    lines.append('98-game rates are provisional: about +/-5 points standard error, approximately +/-10 points at 95%; local fixed-opponent results do not establish ladder strength.')
    lines.append('Ram counts use K1 (candidate) and ATK queen-id (Nv30 control); actual same-turn head-on deaths verify kills. Risks: growth/last-longest, hidden state, incomplete routes; current queen IDs/head occupancy prevent decoys/stale targets.')
    candidate=next((r for r in panel_results if r[0]=='out/kz_panel'),None)
    control=next((r for r in panel_results if r[0]=='out/kz_ctl'),None)
    if candidate and control: lines.append(f'Candidate minus Nv30: {(candidate[1]-control[1])*100/candidate[4]:+.1f} win-rate points on matched seeds/sides; provisional.')
    if not complete: recommendation='Wait for verification; no ladder test yet.'
    elif candidate[2]==0: recommendation='Drop: no rams fired in 98 games; opportunity too rare under these conservative guards. Do not tune.'
    elif candidate[1]>control[1]: recommendation='Consider a same-time ladder test after the promotion gate; local improvement remains provisional.'
    else: recommendation='Drop: no local win-rate gain over Nv30; sacrificing growth is not justified by this panel.'
    lines.append('Recommendation: '+recommendation)
    lines.append('Unverified: ladder effect, chase benefit, exact hidden global queen state, and CPU worst case beyond sampled games.')
    assert len(lines)<=35,len(lines)
    Path('out/kamikaze_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__': main()
