# opening_fix runtime critic (read-only)
Read tools/tasks/opening_fix.md, out/opening_fix_report.md, tools/opening_fix.py, and final viper_y96qo2/main.cpp.
Do not change bot code, original/control directories, baselines, or evaluations.
Critique final source and selection against measured per-part open/closed ablations in out/opening_fix/state.json.
Check independent switches, stagnation/exit/risk guards, true-queen QBOX/amputation ordering, and r120 handoff.
Exact verification (root/runner execute, critic assesses coverage/hashes/results):
uv run --offline --python 3.11 --with unswbc python -B tools/panel_zig.py viper_y96qo2 baselines/Y9_6 out/opening_fix/v2_final_closed --maps stripes,tower_defense,queen_of_spades,dilemma --seeds 1,2,3,4,5,6,7,8 -j 4
uv run --offline --python 3.11 --with unswbc python -B tools/panel_zig.py viper_y96qo2 baselines/Y9_6 out/opening_fix/v2_final_safety --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j 2
Accept only safety>=56/98, closed win gains on>=2maps and units100 gains on>=3maps, CPU<=66M.
Return<=10lines: correct/risky/missing, source lines, verdict; do not treat local static review as external Antigravity review.
