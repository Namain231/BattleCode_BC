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
