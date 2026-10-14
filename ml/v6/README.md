# v6 imitation pipeline (new rules; plane 8 = zero)

Build shards (resumable, streaming; ~2 min for 22 games / 287k samples, ~120 bytes/sample):
    uv run --python 3.11 --with unswbc --with numpy python ml/v6/build_dataset_v6.py --workers 2 --out ladder/scout_v6/shards
Check them:
    uv run --python 3.11 --with numpy python ml/v6/test_builder.py ladder/scout_v6/shards
Train (streams shards, hold-out by game; use Python310 with CUDA torch locally, ~15k samples/s on a GTX 1650):
    PY310 ml/v6/train_v6.py --data ladder/scout_v6/shards --out ladder/scout_v6/train_out/v6.pt --epochs 8 --val-frac 0.1 --amp
Export + parity (C++ forward vs torch; plane-8 weight audit; compiles with g++ or `zig c++` in WSL):
    PY310 ml/export_cpp.py v6.pt OUTDIR/policy_weights_v6.hpp --data ladder/scout_v6/shards
    PY310 ml/v6/parity.py v6.pt ladder/scout_v6/shards OUTDIR
C++ inference: `ml/v6/policy_nn_v6.hpp` (19 planes + 6 scalars -> 7 logits).
The reconstruction of bodies applies each recorded dragonUpdate step exactly (growth / tail pops decided by head+tail).
Known gaps: byte-identical bot-vs-builder input parity is NOT yet verified (next job); only 22 games so far.

Recent-game refresh:
    --extra-data DIR can be repeated to visit new shards twice per epoch.
    --val-data NEW_DIR --val-games holdout_games.json freezes explicit newest-game IDs;
    these IDs are excluded globally from all training directories.
Kaggle: DTAG=-new OLD_DATASET=bc-v6-shards VAL_GAMES=... INIT=... CREATE_SHARDS=1
mounts existing old shards plus the new private dataset. Use SKIP_UPLOAD=1 for a second
kernel on those same mounts. FETCH_TIMEOUT / KERNEL_TIMEOUT override long-run limits.
The refresh supervisor and report are under ladder/scout_v6/ (F: junction), not C:.
