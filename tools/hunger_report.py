"""Write <=40-line plain local hunger report; never submits or activates a build."""
import sys
sys.dont_write_bytecode=True
import json, statistics
from pathlib import Path

DATA=Path('F:/BC_hunger_20261008')
def main():
    state_path=DATA/'state.json'
    s=json.loads(state_path.read_text()) if state_path.exists() else {}
    lines=['Hunger experiment — local, unpromoted.',
        'Candidate: viper_nv30h; base/control viper_nv30k (Sv6, 19955); opponent baselines/Y9_6.',
        'Only candidate main.cpp changes; the other four files are copied unchanged.',
        'Mechanism: hunger strengthens unseen/unwalked food priors, penalizes recent head visits, and pulls small drones toward sticky known frontiers.',
        'Portal safety is unchanged; frontier BFS uses ordinary known open edges only, at most once per four turns.',
        'Queen: grace 15/ramp 60, h<=0.6, mild safe-region prior/retrace, no frontier pull; OFF from r100 (conservative base QSAFE window) or enemy within 8.',
        'Nonqueen: grace 8; length cap 6 for frontier; visit window 30; birth/growth/eating/split reset, paid sprint shrink does not.',
        'Verification: judge build PASS; C++ production scorer + engine_sim fixture PASS; metric attribution fixture PASS.',
        'Critic: implementation/tooling PASS before panels; actual CPU and behavior require panel evidence.']
    details=lines[2:];lines=lines[:2]
    chosen=s.get('chosen')
    if chosen:
        params={'mild':'60/1.0/0.35/0.3','medium':'40/2.0/0.7/0.6','strong':'25/3.0/1.0/0.9'}
        lines.append('Selected '+chosen+' (nonqueen ramp/expl/revisit/frontier='+params[chosen]+'); mechanism food efficiency first, then retrace/coverage; safety is not used to tune.')
    def metric(label,ctl,cand):
        lines.append(f'{label} (control -> candidate): unique cells/dragon {ctl["unique_cells_per_dragon"]:.2f} -> {cand["unique_cells_per_dragon"]:.2f}; retraces {100*ctl["retrace_rate"]:.1f}% -> {100*cand["retrace_rate"]:.1f}%.')
        lines.append(f'Eats/dragon-turn {ctl["eats_per_dragon_turn"]:.4f} -> {cand["eats_per_dragon_turn"]:.4f}; mean longest foodless streak {ctl["longest_streak_mean"]:.1f} -> {cand["longest_streak_mean"]:.1f} (censored at L>6/death/window).')
        lines.append(f'Mean units@50/@100 {ctl["units50"]:.1f}/{ctl["units100"]:.1f} -> {cand["units50"]:.1f}/{cand["units100"]:.1f}.')
    if chosen and 'control_mech' in s:metric('64-game mechanism',s['control_mech'],s[chosen])
    if 'extra_control' in s and 'extra_candidate' in s:metric('16-game extra mechanism',s['extra_control'],s['extra_candidate'])
    for setting in ('mild','medium','strong'):
        if setting in s:
            r=s[setting];lines.append(f'Sensitivity {setting}: {r["eats_per_dragon_turn"]:.4f} eats/turn, {100*r["retrace_rate"]:.1f}% retraces, {r["unique_cells_per_dragon"]:.2f} unique; {r["wins"]}/{r["games"]} wins (secondary).')
    if 'safety_candidate' in s and 'safety_control' in s:
        c,n=s['safety_control'],s['safety_candidate']
        lines.extend([f'Safety wins: {c["wins"]}/{c["games"]} -> {n["wins"]}/{n["games"]}; local win rates provisional (small differences around ±5 points are inconclusive).',
            f'Queen deaths: {c["queen_deaths"]}/{c["games"]} -> {n["queen_deaths"]}/{n["games"]}; median death round {c["queen_death_median"]} -> {n["queen_death_median"]}.',
            'Nonqueen r0–149 deaths (control -> candidate): '+', '.join(f'{k} {c["deaths"].get(k,0)} -> {n["deaths"].get(k,0)}' for k in sorted(set(c['deaths'])|set(n['deaths']))),
            f'CPU peak: {c["cpu_peak"]:.3f}M -> {n["cpu_peak"]:.3f}M; required candidate ceiling 66M.'])
    else:lines.append('Mechanism/sensitivity/safety results PENDING: guarded sequential panels have not completed; no improvement claim yet.')
    if chosen:
        for name in ('control_mech',chosen,'extra_control','extra_candidate'):
            p=DATA/name/'opening.json'
            if p.exists():
                rows=[r for r in json.loads(p.read_text())['rows'] if r['candidate']]
                lines.append(f'Census {name}: eats/round r0–99 {sum(r["eats"] for r in rows)/max(1,len(rows)*100):.3f}; units50/100 medians {statistics.median(r["units50"] for r in rows):.1f}/{statistics.median(r["units100"] for r in rows):.1f}.')
    lines.extend(details)
    lines.extend(['Extra-panel discrepancy: listed four maps × seeds 3,4 × both sides = 16 games, not stated 28; uses explicit map/seed list.',
        'Metrics: our dragons with start-turn L<=6, r0–149; unique/streak averages are lifetime/exposure dependent; retraces exclude same-turn-only visits.',
        'Risk: exploration can dilute good farming or expose workers; queen safe-region filtering is intentionally conservative; local opponent evidence is provisional.',
        'Commands: uv run --python 3.11 --with unswbc python -B tools/buildwasm.py viper_nv30h',
        'Commands: uv run --python 3.11 --with unswbc python -B tools/hunger_unit.py; python -B tools/hunger_metrics_check.py',
        'Resume all panels: uv run --python 3.11 --with unswbc python -B tools/hunger_run.py (sequential guarded -j2; per-game + per-stage checkpoints on F:).',
        'Mechanism: python -B tools/panel_zig.py BOT baselines/Y9_6 OUT --maps stripes,tower_defense,queen_of_spades,dilemma --seeds 1,2,3,4,5,6,7,8 -j 2',
        'Safety (once): python -B tools/panel_zig.py viper_nv30h baselines/Y9_6 F:/BC_hunger_20261008/safety_candidate --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j 2',
        'Per panel: python -B tools/hunger_metrics.py DIR; python -B tools/opening_census.py --dir DIR --workers 1; python -B tools/panel_queen.py F:/BC_hunger_20261008/safety_candidate out/nv30k',
        'Created: tools/hunger_{metrics,metrics_check,unit,run,report}.py; tasks/hunger_{critic,runner}.md; out/hunger.patch; this report. Data: F:/BC_hunger_20261008/.',
        'Recommendation: ladder A/B only after acceptable mechanism, early-death and CPU results, and user approval. No submission or active-build change.'])
    assert len(lines)<=40,len(lines)
    Path('out/hunger_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Wrote out/hunger_report.md:',len(lines),'lines')

if __name__=='__main__':main()
