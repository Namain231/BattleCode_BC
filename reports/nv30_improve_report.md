Nv3.0 improvement ? fix round 1
Status: verification running; incomplete results below. Nv30 locked; no submission or activation.
Diagnosis: <1800: 35 early-deficit, 24 tiebreak, 36 head-on losses; 1800?2099: 9 early-deficit, 5 tiebreak, 6 head-on losses; 2100+: 22 early-deficit, 6 tiebreak, 25 head-on losses. Early economy remains the main gap; queen head-ons dominate queen loss causes. L10 historical losses likewise favor early deficits and head-ons (out/nv31_work/l10_tiers.json; historical audit).
Opening: 188 unique historical map/side matches; Nv30/L10 units50 11.4/12.3, units100 18.8/19.7, eats/r 0.84/0.89. Seeds/time/opponents are confounded; this cannot prove causation.
a: queenAntiRam uses existing enemy reach to avoid threatened queen landings; no queen-ram attack.
b: trapMap caches optimistic terrain, peeled branches and directional Tarjan pocket entry area/cycle bounds; drones get a soft penalty. Dynamic safety outranks static risk; pocket exits remain allowed.
c: wreckExtend allows L<=6 miners and favors present pearls on recently vacated occupied sites; this is a corpse-site proxy, not proven deaths.
Selected to target queen rams, DOOMED traps and early food recovery separately. Other files match Nv30; only main.cpp differs (a +8, b +60, c +10/-1 lines).
Fixes: rebuild validity committed only after success; timeout retries unchanged terrain; all derived caches bind replay/CPU/success bytes, provenance and full producer versions; diagnosis rejects reconstruction errors.
Current-source native/WASM fixtures PASS; hashes bind source, fixtures, compiler, executable and meter. Sampled rebuild peak 1.019M points.
Fixtures: depth5 corridor; area3/L6 pocket; short cycles; both entry/exit edges; unresolved portals; unknown4096 cells; cache/change; forced timeout then same-terrain recovery; unsafe/threatened alternatives and all moves trapped.
Scores compare identical maps/seeds/sides against Y9_6; deltas are versus Nv30 performance, not direct candidate-vs-control matches.

Panel | wins | queen deaths / median round | units100 | eats/r | CPU peak | DOOMED/escape
--- | --- | --- | --- | --- | --- | ---
kz_ctl | 42/98 | 90/98 / 199.0 | 24.1 | 0.92 | 65.251M | 10932
nv31a | 48/98 | 90/98 / 222.5 | 24.5 | 0.92 | 65.269M | 11300
nv31b | 51.5/98 | 92/98 / 207.0 | 24.1 | 0.92 | 65.251M | 10772

Exact screen: uv run --python 3.11 --with unswbc python tools/panel_zig.py DIR baselines/Y9_6 OUT --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j 4
DIR/OUT: baselines/Nv30/out/kz_ctl and viper_nv31a,b,c/out/nv31a,b,c. One panel at a time; use -j2 if other judges run; shared reservation and RAM/disk guards.
Confirmation: same command, --seeds 10,11,12,13,14,15,16; trigger +5 wins or clear target gain without losing wins, CPU<=66M.
Trap targets: same command, --maps slithery_fight,dilemma,stripes,maze,tower_defense --seeds 3,4,5; Nv30 and b, 30 games each.
Metrics: tools/panel_queen.py OUT; tools/opening_census.py --dir OUT. Per-map DOOMED/SHED/ESCAPE-SPLIT and queen rounds: out/nv31_work/trap_targets.json.
Unit/meter: uv run --python 3.11 --with unswbc python -B out/nv31_work/meter.py; native g++ -O1 -std=c++17 out/nv31_work/unit.cpp -o out/nv31_work/unit.exe.
Resume: uv run --python 3.11 --with unswbc python -B out/nv31_work/run.py; atomic state after each evaluation. Created candidates, out/nv31_work scripts/bindings, panels, report; data on F:.
Recommendation withheld until required screens, trap comparison and confirmation finish.
Risks: conservative reach can corner/starve queen; optimistic unseen terrain and budget fallback miss traps; block size is only an upper bound on longest cycle; corpse attribution is approximate.
Unverified: independent other-lane critique, ladder benefit and worst-case CPU. Local results remain provisional; no promotion.
