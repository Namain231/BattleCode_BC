# Opening recipe - completed, failed candidate
viper_y96qo retained after three measured revisions; no submission/promotion. Tested wasm:viper_y96qo-3d978a3f997e4b8a.wasm.
Changed:viper_y96qo/main.cpp,tools/opening_census.py; created critic/runner briefs,out/or_* artifacts; appended insights.md/AGENT_LOG.md. Only main.cpp differs inside copied candidate; qg unchanged; inherited verification files describe old control.
Evidence:18 initial+54 re-dumped traces. Winners leave empty areas toward food,reach4 then commonly split2 next round(some grow5/split3). Stripes S,E x8,N,E,split2 r11,child W immediately. No universal fixed-box exit verified.
Params:38/openingActive:1934: flags ON,length<=6,r0-119; hooks inactive from r120. openingPrepare:1935: visit/eat memory,K=6 hunger,known-cell flood toward food/renewal,discount nearer allies; cycle needs no eat AND no new visit.
openingSplit:1993: workers>=4,child2(flag supports3),known parent/child exits,enemy/budget checks. openingUnwind:2009 uses existing boxed-worker escape evaluator.
Worker selection:2288/2318 follows route in same safety class,pDeath<=.25; first move separates from allies/inferred parent heading(identity heuristic).
Queen food hook:2423 follows original emergency/split/search,same safety class,nonincreasing risk,confirmed depth2 continuation; QBOX/amputation/guard/feeding/sonar code intact.
Portal hook:2366 requires matching unambiguous prior probe/zero echoes; status rays often inhibit after r12; paired portals allowed,legacy PEXPLORE unchanged.
Closed medians units@100/first split; top=winner-only ladder target,not paired expectation.
| Map | Control | R3 candidate | Top | Halfway units |
|---|---:|---:|---:|---:|
| stripes | 6.5/42 | 11.5/11 | 12.5/11 | 9.5 |
| tower_defense | 4/41 | 3/50 | 14.5/47 | 9.25 |
| queen_of_spades | 6.5/14 | 7/12 | 12/13 | 9.25 |
| dilemma | 6/0 | 5.5/0 | 13.5/0 | 9.75 |
Closed wins/CPU:control39/64(60.94%)/64.215M;R1 29/64/63.297M;R2 28/64/64.138M;R3 26/64(40.63%)/64.168M. Halfway R1/R2 0/4,R3 1/4 FAIL.
First split earlier Stripes/Spades,later Tower,Dilemma already r0. Queen deaths<120 control/R3:Stripes7/6,Tower3/1,Spades4/10,Dilemma8/8.
Safety14 games/map; units@100/first split; wins/queen deaths<120 control/candidate.
| Map | Control | Candidate | Top | Wins | Queen deaths |
|---|---:|---:|---:|---:|---:|
| around_unsw | 59/0 | 46/0 | 60.5/0 | 10/7 | 1/2 |
| australia | 33.5/0 | 27.5/0 | 42/0 | 5/4 | 1/5 |
| islands | 42.5/3 | 44/3 | 49/3 | 9/6 | 4/5 |
| maze | 24/0 | 19/0 | 28/0 | 8/8 | 2/1 |
| stripes | 6/67 | 11.5/11 | 12.5/11 | 12/14 | 4/4 |
| tower_defense | 4/41 | 3/61 | 14.5/47 | 6/0 | 3/1 |
| weakhold | 9/0 | 12.5/0 | 13/0 | 9/11 | 5/6 |
Safety59/98(60.20%)->50/98(51.02%),-9.18pp FAIL5pp;CPU64.802M/64.648M PASS<=66M. Population preservation FAIL4/7 maps.
Failed:general recipe regresses outside Stripes;cause unproven. Parent identity/fixed-box exit/ladder unverified. Static review PASS;acceptance critique FAIL.
Commands(PowerShell,sequential guarded -j4,F: data,offline cached unswbc):
uv run --offline --python 3.11 --with unswbc python tools/panel_zig.py viper_y96qg baselines/Y9_6 out/or_ctl --maps stripes,tower_defense,queen_of_spades,dilemma --seeds 1,2,3,4,5,6,7,8 -j 4
uv run --offline --python 3.11 --with unswbc python tools/panel_zig.py viper_y96qo baselines/Y9_6 out/or_chk_r3 --maps stripes,tower_defense,queen_of_spades,dilemma --seeds 1,2,3,4,5,6,7,8 -j 4
R1/R2 same candidate command,OUT out/or_chk/out/or_chk_r2_valid; snapshots out/or_round1/out/or_round2. Aborted out/or_chk_r2 excluded.
uv run --offline --python 3.11 --with unswbc python tools/panel_zig.py viper_y96qg baselines/Y9_6 out/or_safety_ctl --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j 4
uv run --offline --python 3.11 --with unswbc python tools/panel_zig.py viper_y96qo baselines/Y9_6 out/or_safety --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j 4
foreach ($d in 'out/or_ctl','out/or_chk','out/or_chk_r2_valid','out/or_chk_r3','out/or_safety_ctl','out/or_safety') { uv run --offline --python 3.11 --with unswbc python -B tools/opening_census.py --dir $d --quick } # --self-check PASS
uv run --offline --python 3.11 --with unswbc python -B tools/opening_census.py --trace-maps 'Stripes,Tower Defense,Queen Of Spades,Prisoners Dilemma,Portals,Slithery Fight,Schooltime,Around UNSW,Australia' --out out/or_extra_traces.txt
Resume:out/opening_recipe_state.json,out/or_round{1,2,3} source/metrics,atomic per-game caches/summaries. No remote lanes used.
