Hunger critique (2026-10-08): implementation exists; experiment acceptance is incomplete.
Required fixes:
1. tools/hunger_run.py:81-85 and tools/hunger_metrics.py:103-110: validate the reused safety control against the current control/opponent wasm, map, engine and judge hashes; require exactly the expected 98 map/seed/side keys and equality with candidate keys. Hashing success-file bytes is not validating its contents. Reject stale, extra, missing or failed games before aggregation.
2. tools/hunger_run.py:60-69: persist the seal atomically BEFORE starting the first panel. Currently state.json is absent during the first panel; a crash then permits changed control/workflow inputs to become the new seal and mixes the run history. Seal panel/build/guard dependencies too; serialize the entire workflow to prevent two supervisors rewriting variants/state.
3. tools/hunger_run.py:81-88: complete the requested mechanism, sensitivity, paired safety, queen/death and CPU evidence before acceptance. DONE currently has no check for candidate CPU <=66M, pairing, finite metrics or acceptable safety. Distinguish workflow completion from acceptance explicitly.
4. tools/hunger_unit.py:25-34: the fixture selects using hungerMoveScore alone and applies a hard-coded E action once. Add a multi-turn production-decision fixture proving departure from a foodless patch and reduced retracing; current test does not establish the brief's behavioral premise or full flag-off parity.
5. tools/hunger_report.py:18-19,59-60 and tools/hunger_run.py:88: do not hard-code verification/critic PASS independent of evidence. Generate the final report from validated results at workflow completion; the runner never invokes hunger_report.py, leaving the delivered report stale.
6. tools/hunger_report.py:52: use the stipulated Python 3.11/unswbc environment for the metric-check command; bare python fails silently on this machine.
Checks reproduced:
- uv run --python 3.11 --with unswbc python -B tools/buildwasm.py viper_nv30h: PASS (cached wasm returned).
- uv run --python 3.11 --with unswbc python -B tools/hunger_unit.py: PASS; unvisited E chosen, guard assertions pass, one engine move survives.
- python -B tools/hunger_metrics_check.py: exit 1, no output; same command through uv/Python 3.11: PASS (2 turns, 5 moves, 1 retrace, 1 eat, 4 unique cells, streak 1).
- All four required non-main candidate files match control byte-for-byte; inspected the main changes and saved patch, five hunger scripts, both role briefs, git status and tracked build/panel diffs. Hunger files/candidate are untracked, so git diff alone does not show them.
What I would not trust:
- No completed mechanism/sensitivity/safety comparison is supplied. One mild game had a success marker at inspection; full panels were intentionally not started or resumed by this critique.
- 98 existing control replays have success markers; CPU sidecars show peak 65.248604M. This does not prove current provenance or candidate CPU safety.
- Queen hunger is conservatively disabled at r100 rather than the brief's allowed pre-r150 window; disclosed, but actual queen behavior still needs evidence. Hunger scoring leaves survival classification unchanged; queen bonuses require ordinary safe paths and corridorRisk==0.
- Unique coverage and longest streak averages depend on exposure/survival; pooled raw death counts also depend on units/turns. Do not interpret these alone as better exploration or lower risk; report paired per-game changes and death rates per exposed turn.
- Frontier distance maps may be four turns old; target selection blocks occupied cells but reverse distance propagation does not (main.cpp:1087,1100). Validate that the attraction does not repeatedly favor blocked shortcuts despite the unchanged survival veto.
- C: remained about 13.4 GiB free; out/ and ladder/ are F: junctions. Sequential -j2 panels and disk/RAM guards exist; replay decoding still loads one whole replay at a time. No LLM calls, remote submissions or secret writes found in the hunger code.
- Farm precision, league fidelity and search promotion criteria are not applicable to this hunger brief. No promotion is authorized; local percentages remain provisional and do not establish ladder strength.
VERDICT: FAIL: required behavioral and safety evidence is pending; control provenance and first-panel resume sealing are insufficient
