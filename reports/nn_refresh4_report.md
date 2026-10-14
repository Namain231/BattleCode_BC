# nn_refresh4
Stopped safely: [Errno 22] Invalid argument
Locked control: baselines/Nv30. No submission or active-bot change.
Candidate: viper_nv30n (eligible only after export, parity and play checks).
Artifacts: tools/nn_refresh4.py; out/nn_refresh4/; ladder/scout_v6/manifest_new2.csv, shards_new2/, train_out/nn_refresh4/.
New data: {"games": 1448, "teams": 42, "maps": {"Stripes": 83, "Trauma": 85, "Islands": 101, "Maze": 73, "weakhold": 78, "Australia": 75, "Devil": 83, "Queen Of Spades": 83, "Trophy": 81, "Schooltime": 81, "Prisoners Dilemma": 102, "Tower Defense": 89, "Slithery Fight": 89, "Default": 100, "Around UNSW": 79, "Portals": 85, "Autarky": 81}, "dates": ["2026-10-05T01:49:36.942Z", "2026-10-06T23:20:11.270Z"]}
Safeguard verification: Python310 -B tools/nn_refresh4_verify.py (fault-injection checks PASS).
Commands (full argv and successful stages: out/nn_refresh4/state.json):
bash -lc "set -a; . ./secrets.env; set +a; uv run --python 3.11 --with unswbc --with numpy python -B tools/nn_refresh4.py"
Scouting reused out/scout_nn4.done; manifest_sweep rows after line 1858, deduped against manifest_all/new.
Build: ml/v6/build_dataset_v6.py --index ladder/scout_v6/manifest_new2.csv --out ladder/scout_v6/shards_new2 --workers 2
Train: local GTX 1650; remote lanes OFF; k_fullft init; old + recent shards 2x; newest-game holdout; 3 epochs.
Export/parity: ml/export_cpp.py and ml/v6/parity.py; build: tools/buildwasm.py.
Screen: tools/panel_zig.py viper_nv30n baselines/Y9_6 out/nv30n --maps around_unsw,australia,islands,maze,stripes,tower_defense,weakhold --seeds 3,4,5,6,7,8,9 -j 4 (2 if busy).
Queen: tools/panel_queen.py; units@100: tools/opening_census.py --dir.
Local panels are provisional (~5 points); ladder A/B requires user approval.
Unverified: [Errno 22] Invalid argument
