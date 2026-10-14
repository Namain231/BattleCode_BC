"""Offline opening census; at most two decoders, no cache/network dependencies.

Run from the repository: python -B tools/opening_census.py
Snapshots at rN mean start of round N (N completed zero-based rounds).
"""
import sys
sys.dont_write_bytecode = True
import argparse
import collections as C
import csv
import json
import math
import random
import re
import ast
import statistics as S
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / 'tools'))
from replay_lite import decode_lite
from engine_sim import load_map, DEATHS

KINDS = {'roundStart', 'turnStart', 'dragonAction', 'dragonUpdate',
         'dragonSplit', 'dragonDeath', 'tileChange'}
CLOSED = ['Stripes', 'Tower Defense', 'Queen Of Spades']
METRICS = ['units10', 'units25', 'units50', 'units100', 'units200',
           'length50', 'length100', 'first_split', 'splits50', 'eats_rate',
           'corpse_share', 'stuck', 'deaths100', 'paid_steps', 'escape',
           'first_len4', 'lag4_to_split', 'eligible_moves50']


def median(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return S.median(xs) if xs else None


def fmt(x):
    return 'NA' if x is None else f'{x:.2f}'


def sources(cap):
    jobs, skipped, seen = [], C.Counter(), set()
    for label, bot in [('sv52', '16106'), ('sv53', '16651')]:
        folder = Path('ladder') / label
        path = folder / 'games.json'
        if not path.exists():
            skipped[label + '_missing_json'] += 1
            continue
        for row in json.loads(path.read_text(encoding='utf-8')):
            p = folder / f"{row['game']}.replay"
            if (label == 'sv53' and str(row.get('bot')) != bot) or not p.exists():
                skipped[label + '_wrong_bot_or_missing'] += 1
                continue
            if ('ours', str(row['game'])) in seen:
                continue
            seen.add(('ours', str(row['game'])))
            jobs.append(dict(path=p, group='ours', version=label, side=int(row['me']),
                             game=str(row['game']), map=row['map'], team=bot, bot=bot,
                             win=row.get('win'), rating=row.get('oppElo'), battle=str(row['battle'])))
    pool = {}
    for name in ['manifest_all.csv', 'manifest_new.csv']:
        p = Path('ladder/scout_v6') / name
        if not p.exists():
            continue
        with p.open(encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('at', '')[:10] < '2026-10-02' or row.get('group') != 'top':
                    continue
                p = Path('ladder/scout_v6/top') / row['winner_team'] / (row['game'] + '.replay')
                if not p.exists():
                    skipped['top_missing_replay'] += 1
                    continue
                pool[row['game']] = dict(path=p, group='top', version='top',
                                        side={'a': 0, 'b': 1}[row['winner_side'].lower()],
                                        game=row['game'], map=row['map'], team=row['winner_team'],
                                        name=row['winner_name'], rating=float(row['winner_rating']),
                                        date=row['at'], win=True)
    teams = C.defaultdict(lambda: C.defaultdict(list))
    for j in pool.values():
        teams[j['team']][j['map']].append(j)
    rng = random.Random(2504)
    for team, maps in sorted(teams.items()):
        for rows in maps.values():
            rng.shuffle(rows)
        order = sorted(maps)
        rng.shuffle(order)
        n = 0
        while n < cap and any(maps.values()):
            for m in order:
                if maps[m] and n < cap:
                    jobs.append(maps[m].pop())
                    n += 1
    return jobs, skipped, len(pool)


def analyse(job, trace=False, replay=None):
    rep = replay if replay is not None else decode_lite(str(job['path']), KINDS)
    me = job['side']
    if job['group'] == 'ours' and str(rep['botA' if me == 0 else 'botB']) != job['bot']:
        raise ValueError('submission id mismatch')
    if job['group'] == 'top' and rep.get('result', {}).get('winner') != me:
        raise ValueError('manifest winner does not match replay')
    st = load_map(rep['map'], 1)
    board = st.board
    bodies = {i: list(d.body) for i, d in st.dragons.items()}
    teams = {i: d.team for i, d in st.dragons.items()}
    alive = set(bodies)
    starts = [i for i in alive if teams[i] == me]
    # Explicit reproducible proxy; not a claim that every box has radius four.
    region = {bodies[i][0] for i in starts}
    frontier = set(region)
    for _ in range(4):
        nxt = {board.neighbours[p, d] for p in frontier for d in range(4)} - {None} - region
        region |= nxt
        frontier = nxt
    born = {i: 0 for i in starts}
    moves, visited = C.Counter(), {i: {bodies[i][0]} for i in starts}
    pearls, removed, dead_cells = {}, {}, set()
    rnd, actor = -1, None
    eaten, corpses, unknown, splits, paid = 0, 0, 0, 0, 0
    first, escape, first_detail = None, None, None
    first_len4 = 0 if any(len(bodies[i]) >= 4 for i in starts) else None
    eligible_moves50 = 0
    deaths, validation = C.Counter(), C.Counter()
    snapshots, actions, trace_rows, exit_events = {}, {}, [], []
    first_child_move, opening, first_moves = None, C.defaultdict(list), {}
    step_index, free_steps = {}, {}
    last_round = -1

    def snapshot(n):
        own = [i for i in alive if teams[i] == me]
        snapshots[n] = (len(own), sum(len(bodies[i]) for i in own))

    def trace_end():
        if trace and 0 <= rnd < 40:
            text = '; '.join(f"{i}:L{len(bodies[i])}@{bodies[i][0]} action={actions.get(i, 'no turn/dead')}"
                             for i in sorted(alive) if teams[i] == me)
            gone = '; '.join(f'{i}:{a}' for i, a in sorted(actions.items()) if i not in alive)
            trace_rows.append(f'r{rnd:02d} END {text}' + (f'; gone={gone}' if gone else ''))

    for e in rep['events']:
        k = e['kind']
        if k == 'roundStart':
            trace_end()
            rnd = e['round']
            last_round = rnd
            if rnd in (10, 25, 50, 100, 200):
                snapshot(rnd)
            actions = {}
            dead_cells.clear()
            removed.clear()
            actor = None
        elif k == 'turnStart':
            actor = e['id']
            dead_cells.clear()
            removed.clear()
        elif k == 'dragonAction':
            actor = e['id']
            dead_cells.clear()
            removed.clear()
            step_index[actor] = 0
            free_steps[actor] = (len(bodies.get(actor, [])) + 3) // 4
            if teams.get(actor)==me and 0 <= rnd < 50 and e.get('act')=='move' and len(bodies[actor])>=4:
                eligible_moves50 += 1
            if trace and rnd < 40 and teams.get(actor) == me:
                b = bodies[actor]
                act = ('move ' + e.get('dirs', '')) if e.get('act') == 'move' else f"{e.get('act')} size={e.get('size')}"
                actions[actor] = f'PRE L{len(b)}@{b[0]} {act}'
                if actor in starts and rnd < 12:
                    opening[actor].append(f'r{rnd}:{act}')
        elif k == 'dragonDeath':
            i = e['id']
            # Engine death events precede the immediate alternating-cell pearl drops.
            dead_cells.update(bodies.get(i, [])[::2])
            alive.discard(i)
            if teams.get(i) == me and 0 <= rnd < 100:
                deaths[DEATHS[e['reason']] if e['reason'] < len(DEATHS) else str(e['reason'])] += 1
        elif k == 'tileChange':
            p = e['tile']
            if e['pearl']:
                pearls[p] = 'corpse' if p in dead_cells else 'spawn'
                validation['corpse_drop_events' if p in dead_cells else 'spawn_events'] += 1
            else:
                removed[p] = pearls.pop(p, 'unknown')
        elif k == 'dragonSplit':
            i, child = e['parent'], e['child']
            bodies[i], bodies[child] = list(e['parentBody']), list(e['childBody'])
            teams[child] = e['team']
            alive.add(child)
            if e['team'] == me:
                born[child] = rnd
                visited[child] = {bodies[child][0]}
                direction = board.facing(bodies[child][1], bodies[child][0]) if len(bodies[child]) > 1 else -1
                if first is None:
                    first = rnd
                    first_detail = dict(round=rnd, parent=i, child=child, size=len(bodies[child]),
                                        facing='NESW'[direction] if direction >= 0 else '?',
                                        head=bodies[child][0], parent_length=len(bodies[i]),
                                        eats_before_split=eaten)
                if 0 <= rnd < 50:
                    splits += 1
        elif k == 'dragonUpdate':
            i = e['id']
            if i not in bodies or e['head'] is None:
                continue
            b, head = bodies[i], e['head']
            moved = head != b[0]
            if moved:
                # One update per successful sprint step, including portal jumps.
                if head not in [board.neighbours[b[0], d] for d in range(4)]:
                    validation['nonadjacent_update'] += 1
                source = removed.pop(head, None)
                if source is None and head in pearls:
                    source = pearls.pop(head)
                    validation['eat_without_removal'] += 1
                if source is not None and teams[i] == me and 0 <= rnd < 100:
                    eaten += 1
                    corpses += source == 'corpse'
                    unknown += source == 'unknown'
                b.insert(0, head)
                while len(b) > 1 and b[-1] != e['tail']:
                    b.pop()
                if b[-1] != e['tail']:
                    raise ValueError(f'tail reconstruction {i} r{rnd}')
                if teams[i] == me:
                    if first_len4 is None and len(b)>=4:
                        first_len4 = rnd
                    if i not in first_moves:
                        first_moves[i] = dict(round=rnd, head=head, direction='NESW'[e['facing'] % 4])
                    if 0 <= rnd < 50:
                        moves[i] += 1
                        visited.setdefault(i, set()).add(head)
                    if 0 <= rnd < 100 and step_index.get(i, 0) >= free_steps.get(i, 999):
                        paid += 1
                    if head not in region and not any(x['id'] == i for x in exit_events):
                        exit_events.append(dict(id=i, round=rnd, head=head))
                        if escape is None:
                            escape = rnd
                step_index[i] = step_index.get(i, 0) + 1
            else:
                validation['stationary_update'] += 1
    trace_end()
    score = rep.get('result', {}).get('A' if me == 0 else 'B')
    own = [i for i in alive if teams[i] == me]
    if score:
        actual = (len(own), sum(len(bodies[i]) for i in own), max((len(bodies[i]) for i in own), default=0))
        expected = (score['count'], score['total'], score['longest'])
        if actual != expected:
            raise ValueError(f'final body parity: reconstructed={actual}, replay={expected}')
        validation['final_body_parity'] += 1
    # Terminal-state carry forward is explicit, since there are no further actions.
    for n in (10, 25, 50, 100, 200):
        if n not in snapshots:
            snapshot(n)
    result = dict(job)
    result.update({f'units{n}': snapshots[n][0] for n in (10, 25, 50, 100, 200)})
    result.update({f'length{n}': snapshots[n][1] for n in (50, 100)})
    result.update(first_split=first, splits50=splits / len(starts), eats_rate=eaten / 100,
                  corpse_share=corpses / eaten if eaten else None, eats=eaten, corpse_eats=corpses,
                  unknown_eats=unknown, stuck=sum(moves[i] <= 3 for i in born if born[i] < 50),
                  stuck_start=sum(moves[i] <= 3 for i in starts), deaths100=sum(deaths.values()),
                  deaths=dict(deaths), paid_steps=paid, escape=escape, first_detail=first_detail,
                  exits=exit_events, region_size=len(region), trace=trace_rows,
                  validation=dict(validation), end_before200=last_round < 200,
                  first50=splits, initial=len(starts), last_round=last_round,
                  start_bodies={i: list(st.dragons[i].body) for i in starts},
                  opening=dict(opening), first_moves=first_moves, first_len4=first_len4,
                  lag4_to_split=first-first_len4 if first is not None and first_len4 is not None else None,
                  eligible_moves50=eligible_moves50)
    return result


def map_estimate(rows, metric, maps):
    return median([median([r[metric] for r in rows if r['map'] == m]) for m in maps])


def bootstrap(rows, metric, maps, repetitions, rng):
    """Equal-map median; cluster teams for top, battles for ours.

    Top cluster bootstrap resamples teams globally, then games within each map/team;
    missing selected-team maps fall back to that map's observed teams.
    """
    groups = C.defaultdict(lambda: C.defaultdict(list))
    for r in rows:
        if r['map'] in maps and r[metric] is not None:
            groups[r['map']][r['team'] if r['group'] == 'top' else r['battle']].append(r[metric])
    cluster_keys = sorted({t for g in groups.values() for t in g})
    estimates = []
    for _ in range(repetitions):
        draw = rng.choices(cluster_keys, k=len(cluster_keys))
        mm = []
        for m in maps:
            g = groups[m]
            if not g:
                continue
            keys = [t for t in draw if t in g]
            if not keys:
                keys = rng.choices(list(g), k=len(g))
            vals = [x for t in keys for x in rng.choices(g[t], k=len(g[t]))]
            mm.append(median(vals))
        v = median(mm)
        if v is not None:
            estimates.append(v)
    estimates.sort()
    if not estimates:
        return None, None
    return estimates[int(.025 * len(estimates))], estimates[min(len(estimates)-1, int(.975 * len(estimates)))]


def cliffs(a, b):
    a, b = [v for v in a if v is not None], [v for v in b if v is not None]
    if not a or not b:
        return None
    return sum((x > y) - (x < y) for x in a for y in b) / (len(a) * len(b))


def report(rows, skipped, available, reps):
    lines = []
    def emit(s=''):
        lines.append(str(s))
    ours = [r for r in rows if r['group'] == 'ours']
    top = [r for r in rows if r['group'] == 'top']
    maps = sorted({r['map'] for r in ours} & {r['map'] for r in top})
    emit('OPENING CENSUS -- post-2026-10-02, offline, seed 2504, one worker')
    emit(f'Games: ours={len(ours)} ({dict(C.Counter(r["version"] for r in ours))}); top={len(top)}, teams={len(set(r["team"] for r in top))}; eligible unique top replays={available}; skipped={dict(skipped)}')
    emit('rN snapshots are START of round N. Eats/splits/deaths windows: r0..99/r0..49/r0..99. Early terminal states carried forward; eat denominator stays 100.')
    emit('Pearls: tile removal matched to the next successful head update; source marked by immediate death-body alternating-cell drops, including head-on deaths of either team. Paid steps are not mistaken for failed growth.')
    emit('Stuck = <=3 successful movement steps before r50, includes late newborns/dead dragons; stuck_start is starting dragons only. Escape = first head outside graph radius-four union around initial friendly heads, a reproducible proxy, NOT a literal box boundary.')
    emit('Top includes WINNERS ONLY; selection/opponent/rating/side/version confounding remains. Blog post25 numbers are old-rule cross-sectional results, not a new-rule target.')
    emit('\n(1) PER MAP MEDIANS (ours/top); source-specific sample counts')
    emit('map | n ours/top | units50 | units100 | length100 | first split* | eats/round | corpse share')
    for m in sorted({r['map'] for r in rows}):
        a, b = [r for r in ours if r['map'] == m], [r for r in top if r['map'] == m]
        emit(f'{m} | {len(a)}/{len(b)} | ' + ' | '.join(f'{fmt(median([r[k] for r in a]))}/{fmt(median([r[k] for r in b]))}' for k in ['units50','units100','length100','first_split','eats_rate','corpse_share']))
    emit('* First split medians exclude never-split games; no-split counts are given below, not assigned a fictitious round.')
    emit('\n(2) OVERALL: median of per-map medians on shared maps; 95% percentile bootstrap (top team clusters, ours battle clusters), map weights equal')
    emit('Shared maps: ' + ', '.join(maps))
    rng = random.Random(2504)
    for k in METRICS:
        output = []
        for rs in (ours, top):
            lo, hi = bootstrap(rs, k, maps, reps, rng)
            output.append(f'{fmt(map_estimate(rs,k,maps))} [{fmt(lo)}, {fmt(hi)}]')
        emit(f'{k}: ours {output[0]}; top {output[1]}')
    for label, rs in [('ours', ours), ('top', top)]:
        emit(f'{label}: raw pooled median units50={fmt(median([r["units50"] for r in rs]))}, first_split={fmt(median([r["first_split"] for r in rs]))}; no split in entire game={sum(r["first_split"] is None for r in rs)}; pooled eats/round={sum(r["eats"] for r in rs)/max(1,len(rs)*100):.3f}; pooled corpse share={sum(r["corpse_eats"] for r in rs)/max(1,sum(r["eats"] for r in rs)):.3f}; unknown eat sources={sum(r["unknown_eats"] for r in rs)}; early terminal carry={sum(r["end_before200"] for r in rs)}')
    emit('\nVERSION AND MECHANISM BREAKDOWN per map (median units10/25/50/100/200, length50/100, splits50/start, stuck all/start, paid steps100; deaths100 mean by cause)')
    for m in maps:
        for label in ['sv52','sv53','top']:
            rs = [r for r in rows if r['map'] == m and r['version'] == label]
            if not rs:
                continue
            dc = C.Counter()
            for r in rs:
                dc.update(r['deaths'])
            vals = '/'.join(fmt(median([r[k] for r in rs])) for k in ['units10','units25','units50','units100','units200','length50','length100','splits50','stuck','stuck_start','paid_steps'])
            emit(f'{m} {label} n={len(rs)}: {vals}; deaths/100={dict((k,round(v/len(rs),2)) for k,v in dc.items())}')
    gaps = []
    for m in maps:
        for k in ['units50','units100','length100','first_split','eats_rate','corpse_share','splits50','stuck_start','paid_steps']:
            a,b = [r[k] for r in ours if r['map']==m], [r[k] for r in top if r['map']==m]
            if min(sum(v is not None for v in a),sum(v is not None for v in b)) < 3:
                continue
            d = cliffs(b,a)
            gaps.append((abs(d),m,k,d,median(a),median(b)))
    emit('\n(3) TOP FIVE MAP/METRIC GAPS by absolute Cliff delta (top minus ours; ties contribute zero; descriptive, no multiplicity-adjusted inference)')
    for _,m,k,d,a,b in sorted(gaps,reverse=True)[:5]:
        emit(f'{m}: {k} ours={fmt(a)} top={fmt(b)} delta={d:+.3f}')
    emit('\n(4) CLOSED-START TRACES: per round END state and PRE action state. Actual split events, child first move, and proxy exits are listed before each trace.')
    for m in CLOSED:
        for group in ['top','ours']:
            rs = [r for r in rows if r['map']==m and r['group']==group]
            # Representative low/middle/high units100, distinct teams/versions if possible.
            rs.sort(key=lambda r:(r['units100'],r['game']))
            picks = []
            if rs:
                for idx in [0,len(rs)//2,len(rs)-1]:
                    if rs[idx] not in picks:
                        picks.append(rs[idx])
                for r in rs:
                    if len(picks)<3 and r not in picks:
                        picks.append(r)
            if len(picks)<3:
                emit(f'UNVERIFIED coverage: {m} {group} only {len(picks)} trace games available')
            for r in picks:
                tr = analyse(r,True)
                emit(f'GAME {r["game"]} {m} {r["version"]} team={r["team"]} {r.get("name", "")} side={r["side"]} win={r["win"]} units100={r["units100"]}; starts={tr["start_bodies"]}; region size={tr["region_size"]}; first split={tr["first_detail"]}; exits={tr["exits"][:10]}')
                emit('Concrete starting routes: '+str(tr['opening']))
                if tr['first_detail']:
                    ch=tr['first_detail']['child']
                    child_rows=[s for s in tr['trace'] if f'{ch}:L' in s and 'move ' in s.split(f'{ch}:L',1)[1].split(';',1)[0]]
                    emit('First child movement: '+(child_rows[0] if child_rows else 'not observed before r40 (see full replay)'))
                    emit(f'Exact child first successful step: {tr["first_moves"].get(ch)}')
                    d=tr['first_detail']
                    emit(f'Recipe witness: travel the routes above, grow parent {d["parent"]} to length {d["size"]+d["parent_length"]}, then at r{d["round"]} leave length {d["parent_length"]} in the parent and split off length {d["size"]} as child {ch}, facing {d["facing"]}. The child\'s first successful movement is {tr["first_moves"].get(ch)}. First proxy exit r{tr["escape"]}; exit may precede splitting, so splitting is not automatically the escape mechanism.')
                for s in tr['trace']:
                    emit(s)
    emit('\n(5) EVIDENCE AND RANKED TESTABLE HYPOTHESES (observations do not establish causality)')
    for idx,m in enumerate(CLOSED+['Prisoners Dilemma'],1):
        a,b=[r for r in ours if r['map']==m],[r for r in top if r['map']==m]
        emit(f'E{idx} {m}: n={len(a)}/{len(b)}; units100={fmt(median([r["units100"] for r in a]))}/{fmt(median([r["units100"] for r in b]))}; first split={fmt(median([r["first_split"] for r in a]))}/{fmt(median([r["first_split"] for r in b]))}; splits50/start={fmt(median([r["splits50"] for r in a]))}/{fmt(median([r["splits50"] for r in b]))}; eats/round={fmt(median([r["eats_rate"] for r in a]))}/{fmt(median([r["eats_rate"] for r in b]))}; paid steps100={fmt(median([r["paid_steps"] for r in a]))}/{fmt(median([r["paid_steps"] for r in b]))}; proxy escape={fmt(median([r["escape"] for r in a]))}/{fmt(median([r["escape"] for r in b]))}; first length4={fmt(median([r["first_len4"] for r in a]))}/{fmt(median([r["first_len4"] for r in b]))}; length4-to-split lag={fmt(median([r["lag4_to_split"] for r in a]))}/{fmt(median([r["lag4_to_split"] for r in b]))}; move turns at length>=4 before r50={fmt(median([r["eligible_moves50"] for r in a]))}/{fmt(median([r["eligible_moves50"] for r in b]))}')
    emit('H1 [E1-E4]: test opening-only split threshold/child size after inspecting traces; fewer early splits suggests suppressed expansion. Paired 20 seeds/both sides per closed map vs passive opponent; primary units100, secondary splits50/start, eats100, queen survival. Do not assume the earliest split is best.')
    emit('H2 [E1-E3, traces]: give reversed newborns their outward lane; compare child heads and first move in traces to parent direction. Test newborn first-five-turn anti-parent-block rule; units100 and first successful exit/start worker by r40, wall/self deaths as guardrails.')
    emit('H3 [E1-E4, paid-step/death table]: reduce paid exploration sprints in opening if length expenditure dominates reproduction; use free-step quota and splitable-length preservation. Paired passive tests: units100, length100, paid steps/eat and first split; retain escape sprints if necessary.')
    emit('H4 [corpse_share/deaths tables]: corpse recovery may explain food advantage, or may merely reflect winning fights. Test local worker routing toward observed corpse pearls, keeping queen protected; eats100 and units100 vs fixed aggressive opponent, then passive opponent to isolate ordinary farming.')
    emit('H5 [units10/25 and escape tables]: test opening region coverage/pearl renewal routing rather than stationary hoarding. Paired passive tests: unique cells per worker by r50, spawned eats100, units100; reject if queen deaths rise. Radius-four exit proxy cannot alone prove physical chamber escape.')
    emit('\nVALIDATION totals: '+str(dict(sum((C.Counter(r['validation']) for r in rows), C.Counter()))))
    emit('UNVERIFIED: actual box boundaries/strategic intent, causality, random seeds and opportunity denominators, post25 old-rule exact replication, unpublished top code. Bootstrap does not remove winner-only selection or opponent confounding; intervals are descriptive and map fallback is used when sampled teams omit a map.')
    return '\n'.join(lines)+'\n'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true', help='Local panel primary metrics from saved snapshots and split events')
    ap.add_argument('--dir', help='Decode a local panel directory, both bot sides')
    ap.add_argument('--trace-maps', default='', help='Comma-separated display names for extra ladder traces')
    ap.add_argument('--top-cap',type=int,default=25)
    ap.add_argument('--bootstrap',type=int,default=1000)
    ap.add_argument('--out',default='out/opening_census.txt')
    ap.add_argument('--self-check', action='store_true', help='In-memory paid-eat/split/corpse attribution fixture; writes nothing')
    ap.add_argument('--workers',type=int,choices=[1,2],default=1)
    ap.add_argument('--refine-only',action='store_true',help='Refresh evidence-led interpretation from the existing complete report, without decoding again')
    a=ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    if a.dir and a.quick:
        folder=Path(a.dir); summary=folder/'summary.json'
        if not summary.exists(): raise RuntimeError('Incomplete panel: missing summary.json')
        panels=json.loads(summary.read_text(encoding='utf-8')); rows=[]
        for panel in panels:
            path=folder/f"{panel['map']}_{panel['seed']}_{panel['side']}.replay"
            rep=decode_lite(str(path),{'roundStart','dragonSplit','dragonDeath'})
            rnd=-1; first={0:None,1:None}; queen_death={0:None,1:None}
            queen_team={i:d.team for i,d in load_map(rep['map'],1).dragons.items() if i<=1}
            for e in rep['events']:
                if e['kind']=='roundStart': rnd=e['round']
                elif e['kind']=='dragonSplit' and first[e['team']] is None: first[e['team']]=rnd
                elif e['kind']=='dragonDeath' and e['id'] in queen_team: queen_death[queen_team[e['id']]]=rnd
            mine='AB'.index(panel['side']); snap=panel['snaps'].get('100')
            if snap is None and panel['rounds']>=100: raise RuntimeError('Missing r100 snapshot '+str(path))
            for flag,label,side in [(True,'ours',mine),(False,'theirs',1-mine)]:
                rows.append(dict(map=panel['map'],game=path.stem,candidate=flag,units100=snap[0 if flag else 1] if snap is not None else panel[label]['count'],first_split=first[side],queen_death_round=queen_death[side]))
        if not rows: raise RuntimeError('Empty panel')
        result={'rows':rows,'maps':{}}
        for name in sorted({r['map'] for r in rows}):
            result['maps'][name]={}
            for label,flag in [('candidate',True),('opponent',False)]:
                rs=[r for r in rows if r['map']==name and r['candidate']==flag]
                result['maps'][name][label]={k:median([r[k] for r in rs]) for k in ('units100','first_split')}
                result['maps'][name][label].update(n=len(rs),never_split=sum(r['first_split'] is None for r in rs),queen_deaths_before120=sum(r['queen_death_round'] is not None and r['queen_death_round']<120 for r in rs))
        dest=folder/'opening_quick.json';tmp=dest.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(result),encoding='utf-8');tmp.replace(dest)
        print(json.dumps(result['maps'],indent=2));return
    if a.dir:
        rows=[]
        for path in sorted(Path(a.dir).glob('*.replay')):
            match=re.match(r'(.+)_([0-9]+)_([AB])$',path.stem)
            if not match: continue
            rep=decode_lite(str(path),KINDS)
            for side in (0,1):
                row=analyse(dict(path=path,side=side,group='ours',bot=rep['botA' if side==0 else 'botB'],map=match[1],game=path.stem),trace=True,replay=rep)
                row['candidate']=side==('AB'.index(match[3]))
                row['path']=str(path); rows.append(row)
        if not rows: raise RuntimeError('No named panel replays in '+a.dir)
        summary=Path(a.dir)/'summary.json'
        if not summary.exists(): raise RuntimeError('Panel incomplete: missing summary.json')
        expected=json.loads(summary.read_text(encoding='utf-8'))
        expected_names={f"{r['map']}_{r['seed']}_{r['side']}" for r in expected}
        actual_names={r['game'] for r in rows}
        if expected_names != actual_names: raise RuntimeError('Panel replay coverage mismatch')
        result={'rows':rows,'maps':{}}
        for name in sorted({r['map'] for r in rows}):
            result['maps'][name]={}
            for label,flag in [('candidate',True),('opponent',False)]:
                rs=[r for r in rows if r['map']==name and r['candidate']==flag]
                result['maps'][name][label]={k:median([r[k] for r in rs]) for k in METRICS}
                result['maps'][name][label]['n']=len(rs)
                result['maps'][name][label]['never_split']=sum(r['first_split'] is None for r in rs)
        dest=Path(a.dir)/'opening.json'; tmp=dest.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8'); tmp.replace(dest)
        print(json.dumps(result['maps'],indent=2)); return
    if a.trace_maps:
        jobs,_,_=sources(a.top_cap)
        lines=[]
        for name in a.trace_maps.split(','):
            for group in ('ours','top'):
                selected=[j for j in jobs if j['map']==name and j['group']==group][:3]
                for job in selected:
                    row=analyse(job,trace=True)
                    lines.append(f"{name} {group} game={job['game']} units100={row['units100']} split={row['first_detail']} routes={ {i:acts[:12] for i,acts in row['opening'].items() if i in row['start_bodies']} } child_moves={row['first_moves'].get(row['first_detail']['child']) if row['first_detail'] else None}")
        Path(a.out).write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print('Wrote',len(lines),'traces to',a.out); return
    if a.self_check:
        self_check()
        return
    if a.refine_only:
        p=Path(a.out)
        text=refine_text(p.read_text(encoding='utf-8'))
        p.write_text(text,encoding='utf-8')
        print(text,end='')
        return
    jobs,skipped,available=sources(a.top_cap)
    rows=[]
    print(f'Selected {len(jobs)} games; workers={a.workers}',file=sys.stderr,flush=True)
    def consume(results):
        for n,(row,error) in enumerate(results,1):
            if error:
                skipped[error] += 1
            else:
                rows.append(row)
            if n%20==0 or n==len(jobs):
                print(f'Processed {n}/{len(jobs)}; valid={len(rows)}',file=sys.stderr,flush=True)
    if a.workers==1:
        consume(map(safe_analyse,jobs))
    else:
        with ProcessPoolExecutor(max_workers=a.workers) as executor:
            consume(executor.map(safe_analyse,jobs,chunksize=1))
    if not rows or not any(r['group']=='top' for r in rows):
        raise RuntimeError(f'No usable comparison: {skipped}')
    text=refine_text(report(rows,skipped,available,a.bootstrap).replace('one worker',f'{a.workers} worker(s)'))
    p=Path(a.out)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8')
    print(text,end='')


def safe_analyse(job):
    try:
        return analyse(job),None
    except Exception as ex:
        return None,f'game {job["game"]}: {type(ex).__name__}: {ex}'


def refine_text(text):
    """Derive the interpretation from actual printed trace witnesses, not a preset escape story."""
    text=re.sub(r'\nOBSERVED RECIPES AND COVERAGE.*?(?=\n\(5\))','\n',text,flags=re.S)
    text=re.sub(r'\n{3,}','\n\n',text)
    samples=[]
    current=None
    evidence={}
    for line in text.splitlines():
        if re.match(r'E[1-4] ',line):
            name=line.split(':',1)[0].split(' ',1)[1]
            evidence[name]=line
        if line.startswith('GAME '):
            starts=ast.literal_eval(re.search(r'starts=(.*?); region size=',line).group(1))
            current=dict(header=line,group='top' if ' top team=' in line else 'ours',
                         map=next(m for m in CLOSED if m in line),
                         units=int(re.search(r'units100=(\d+)',line).group(1)),
                         cells={int(i):{tuple(body[0])} for i,body in starts.items()},
                         routes={},positions=C.defaultdict(list),recipe='No successful split in this game.')
            samples.append(current)
        elif current and line.startswith('Concrete starting routes: '):
            current['routes']=ast.literal_eval(line.split(': ',1)[1])
        elif current and line.startswith('Recipe witness: '):
            current['recipe']=line.removeprefix('Recipe witness: ')
        elif current and re.match(r'r\d\d END',line):
            for i,length,x,y in re.findall(r'(\d+):L(\d+)@\((\d+), (\d+)\)',line):
                if int(i) in current['cells']:
                    current['cells'][int(i)].add((int(x),int(y)))
                    current['positions'][int(i)].append((int(line[1:3]),int(length),(int(x),int(y))))
    def ev(m,k):
        match=re.search(re.escape(k)+r'=([^;]+)',evidence.get(m,''))
        return match.group(1) if match else 'NA/NA'
    summaries=['OBSERVED RECIPES AND COVERAGE (three selected games per group/map; descriptive witnesses, not population estimates)']
    for n,m in enumerate(CLOSED,1):
        rs=[r for r in samples if r['map']==m]
        counts={g:median([len(c) for r in rs if r['group']==g for c in r['cells'].values()]) for g in ['ours','top']}
        winners=[r for r in rs if r['group']=='top']
        if not winners:
            continue
        best=max(winners,key=lambda r:r['units'])
        routes='; '.join(f'dragon {i} follows '+', '.join(a.split(':',1)[1] for a in acts) for i,acts in best['routes'].items())
        summaries.append(f'R{n} {m}: median distinct starting-dragon head cells through r39, including initial head, ours/top={fmt(counts["ours"])}/{fmt(counts["top"])}. High-expansion winner {best["header"].split()[1]} (units100={best["units"]}) opening: {routes}. Then {best["recipe"]}')
    summaries.append('Interpretation: first-length4-to-split lag (ours/top): '+', '.join(m+'='+ev(m,'length4-to-split lag') for m in CLOSED)+'. Proxy escape: '+', '.join(m+'='+ev(m,'proxy escape') for m in CLOSED)+'. Where split lag matches, delayed food/length acquisition explains later first splits more directly than a split guard. Coverage is similar on Tower/Spades in these witnesses, so visiting more cells alone is not a proven solution. Winners use different paths/split sizes; there is no single verified box-opening script. Successful newborn movement can occur in the split round and can turn away from its initial facing.')
    loop=None
    for r in samples:
        if r['map']!='Stripes' or r['group']!='ours':
            continue
        for i,positions in r['positions'].items():
            for start in range(len(positions)-4):
                block=positions[start:start+5]
                if block[0][2]==block[-1][2] and len({x[2] for x in block})==4 and all(x[1]==2 for x in block) and block[-1][0]-block[0][0]==4:
                    loop=f'R4 specific Stripes loop: ours game {r["header"].split()[1]} dragon {i} visits '+', '.join(str(x[2]) for x in block)+f' in r{block[0][0]}-r{block[-1][0]} and remains length 2. Its first 40 rounds contain {len(r["cells"][i])} distinct head cells including the start. This documents an empty short circuit; recurrence alone does not establish the bot\'s intent, and is different from the <=3-step stuck condition.'
                    break
            if loop:
                break
        if loop:
            break
    if loop:
        summaries.append(loop)
    replacement={
        'H1 ':f'H1 [E1,E2,R1-R4]: prioritize breaking food-starved movement cycles in the opening. Penalize revisiting recently empty cells after repeated no-food circuits, retain loops on sites that actually renew pearls, and continue into alternative lanes. Stripes first length4 (ours/top)={ev("Stripes","first length4")}; split lag={ev("Stripes","length4-to-split lag")}. Test 20 paired seeds/both sides vs a passive opponent: primary units100, then spawned eats100, first length4 and no-food loop duration; queen survival is a guardrail.',
        'H2 ':f'H2 [E2,E3,R2,R3]: test corridor and junction routing toward productive food regions using observed pearl/renewal memory, with the printed winning routes as concrete reference traces. Tower coverage alone is not lower in our samples, but eats/round (ours/top)={ev("Tower Defense","eats/round")} and escape proxy={ev("Tower Defense","proxy escape")}. Test one opening-turn/route preference at a time on Tower and Spades vs passive/any fixed opponent: units100, spawned eats100, first length4; reject variants that only increase distinct cells without food.',
        'H3 ':f'H3 [E3, paid-step/death tables]: preserve early food as length/reproduction by limiting paid sprints to necessary escapes or certain captures. Median paid steps100 (ours/top): Spades={ev("Queen Of Spades","paid steps100")}, Stripes={ev("Stripes","paid steps100")}, Tower={ev("Tower Defense","paid steps100")}; zero paid-step gaps cannot explain a food deficit. Test a Spades-only opening ablation vs passive opponent: units100, length100, paid steps/eat, splits50/start and queen survival.',
        'H4 ':f'H4 [E4, corpse_share/deaths tables]: test better worker food/corpse recovery and safe post-split routes on Prisoners Dilemma; first split (ours/top)={ev("Prisoners Dilemma","first split")}, yet early splits/start={ev("Prisoners Dilemma","splits50/start")} and eats/round={ev("Prisoners Dilemma","eats/round")}. Do not lower an already immediate first-split threshold. Paired fixed aggressive-opponent tests: corpse/spawned eats100 and units100, then repeat vs passive opponent to separate fighting opportunities from ordinary farming; child route/survival mechanism remains unverified.',
        'H5 ':'H5 [overall splits50, E1-E4, R1-R3]: after fixing food acquisition, test newborn outward-lane/reversal handling or early split size as secondary hypotheses. Printed children often move in the split round; no general newborn-stall defect is established. Paired passive tests: units100, child first successful move delay, wall/self deaths and splits50/start; include Schooltime/weakhold controls where population is already comparable.'}
    output=[]
    for line in text.splitlines():
        if line.startswith('(5)'):
            output.extend(summaries)
            output.append('')
        key=next((k for k in replacement if line.startswith(k)),None)
        output.append(replacement[key] if key else line)
    return '\n'.join(output)+'\n'


def self_check():
    from engine_sim import apply_action
    text='MAP 8 8\nDRAGON 0 4 3 3 2 3 1 3 0 3\nDRAGON 1 2 1 1 1 0\n'
    state=load_map(text,1)
    state.pearls={(3,2),(3,1)}
    events=[]
    plans=[{0:{'act':'move','dirs':'NN'},1:{'act':'move','dirs':'E'}},
           {0:{'act':'split','size':2},1:{'act':'suicide'},2:{'act':'move','dirs':'N'}},
           {0:{'act':'move','dirs':'N'},2:{'act':'move','dirs':'E'}},
           {0:{'act':'move','dirs':'N'},2:{'act':'move','dirs':'N'}}]
    for rnd,plan in enumerate(plans):
        events.append({'kind':'roundStart','round':rnd})
        if rnd==0:
            events.extend({'kind':'tileChange','tile':p,'pearl':True} for p in sorted(state.pearls))
        occ={p:i for i,d in state.dragons.items() if d.alive for p in d.body}
        for i,act in plan.items():
            events.extend([{'kind':'turnStart','id':i},dict(kind='dragonAction',id=i,**act)])
            state.events=[]
            apply_action(state,i,act,occ)
            events.extend(state.events)
    own=[d for d in state.dragons.values() if d.alive and d.team==0]
    score={'count':len(own),'total':sum(len(d.body) for d in own),'longest':max(len(d.body) for d in own)}
    rep={'map':text,'botA':'fixture','botB':'enemy','events':events,'result':{'winner':0,'A':score}}
    global decode_lite
    original=decode_lite
    try:
        decode_lite=lambda path,kinds:rep
        row=analyse(dict(path=Path('fixture'),side=0,group='ours',bot='fixture'))
    finally:
        decode_lite=original
    assert row['eats']==3 and row['corpse_eats']==1 and row['unknown_eats']==0,row
    assert row['paid_steps']==1 and row['first_split']==1 and row['splits50']==1,row
    assert row['units100']==2 and row['length100']==6,row
    assert row['validation']['final_body_parity']==1,row
    print('SELF-CHECK PASS: paid-step eat without net growth, spawned/corpse source, reversed split, terminal carry and final body parity')


if __name__=='__main__':
    main()
