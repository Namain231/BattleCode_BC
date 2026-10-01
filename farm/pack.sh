#!/bin/sh
# Assemble a self-contained game-farm bundle (judge + engine + bots + maps + scripts) for WSL, Kaggle or GitHub Actions.
#   sh farm/pack.sh OUT_DIR BOT_DIR [BOT_DIR ...]        (run from the repo root)
# Bots are compiled with the judge's clang by tools/buildwasm.py and land as OUT_DIR/bots/<dir name>.wasm.
# Needs LOONG_JUDGE (the Zig judge binary; default ~/toolchains/zig-judge-out/bin/loong-judge) and unswbc installed.
set -e
OUT="$1"; shift
JUDGE="${LOONG_JUDGE:-$HOME/toolchains/zig-judge-out/bin/loong-judge}"
ENGINE="$(python3 -c 'import unswbc, os; print(os.path.join(os.path.dirname(unswbc.__file__), "unswbc_engine.wasm"))')"
mkdir -p "$OUT/bots" "$OUT/maps/live" "$OUT/maps/extra" "$OUT/maps/dev" "$OUT/maps/test" "$OUT/shards" "$OUT/kaggle"
cp "$JUDGE" "$OUT/loong-judge"; cp "$ENGINE" "$OUT/engine.wasm"
for m in trauma autarky trophy default dilemma devil slithery_fight schooltime portals queen_of_spades; do cp "maps/$m.map" "$OUT/maps/live/"; done
for m in arena stronghold big_empty Colosseum default_small; do [ -f "maps/$m.map" ] && cp "maps/$m.map" "$OUT/maps/extra/"; done
cp maps_rm_dev/*.map "$OUT/maps/dev/"; cp maps_rm_test/*.map "$OUT/maps/test/"
for b in "$@"; do cp "$(python3 tools/buildwasm.py "$b" | tail -1)" "$OUT/bots/$(basename "$b").wasm"; done
cp farm/make_jobs.py farm/summarize.py farm/run_shard.sh farm/README_FARM.md "$OUT/"; cp farm/kaggle/run_shard_kaggle.py "$OUT/kaggle/"
echo "bundle in $OUT: $(ls "$OUT/bots" | tr '\n' ' ')"
