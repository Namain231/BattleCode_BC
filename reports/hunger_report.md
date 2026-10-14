Hunger experiment — local, unpromoted.
Candidate: viper_nv30h; base/control viper_nv30k (Sv6, 19955); opponent baselines/Y9_6.
Only candidate main.cpp changes; the other four files are copied unchanged.
Mechanism: hunger strengthens unseen/unwalked food priors, penalizes recent head visits, and pulls small drones toward sticky known frontiers.
Portal safety is unchanged; frontier BFS uses ordinary known open edges only, at most once per four turns.
Queen: grace 15/ramp 60, h<=0.6, mild safe-region prior/retrace, no frontier pull; OFF from r100 (conservative base QSAFE window) or enemy within 8.
Nonqueen: grace 8; length cap 6 for frontier; visit window 30; birth/growth/eating/split reset, paid sprint shrink does not.
Verification: judge build PASS; C++ production scorer + engine_sim fixture PASS; metric attribution fixture PASS.
Critic: implementation/tooling PASS before panels; actual CPU and behavior require panel evidence.
Mechanism/sensitivity/safety results PENDING: guarded sequential panels have not completed; no improvement claim yet.
Extra-panel discrepancy: listed four maps × seeds 3,4 × both sides = 16 games, not stated 28; uses explicit map/seed list.
Metrics: our dragons with start-turn L<=6, r0–149; unique/streak averages are lifetime/exposure dependent; retraces exclude same-turn-only visits.
Risk: exploration can dilute good farming or expose workers; queen safe-region filtering is intentionally conservative; local opponent evidence is provisional.
Commands: uv run --python 3.11 --with unswbc python -B tools/buildwasm.py viper_nv30h
Commands: uv run --python 3.11 --with unswbc python -B tools/hunger_unit.py; python -B tools/hunger_metrics_check.py
Resume all panels: uv run --python 3.11 --with unswbc python -B tools/hunger_run.py (sequential guarded -j2; per-game + per-stage checkpoints on F:).
Per panel: python -B tools/hunger_metrics.py DIR; python -B tools/opening_census.py --dir DIR --workers 1; python -B tools/panel_queen.py F:/BC_hunger_20261008/safety_candidate out/nv30k
Created: tools/hunger_{metrics,metrics_check,unit,run,report}.py; tasks/hunger_{critic,runner}.md; out/hunger.patch; this report. Data: F:/BC_hunger_20261008/.
Recommendation: ladder A/B only after acceptable mechanism, early-death and CPU results, and user approval. No submission or active-build change.
