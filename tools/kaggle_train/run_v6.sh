#!/usr/bin/env bash
# Package the v6 code + shards as PRIVATE Kaggle datasets, push the GPU kernel, wait, download results.
# Usage: [TAG=-x] [TEAM_COND=8] [ONLY_TEAMS=a,b,c] [SKIP_UPLOAD=1] tools/kaggle_train/run_v6.sh [SHARD_DIR] [OUT_DIR] [EPOCHS]
#   TAG gives a separate kernel (bc-v6-train$TAG) so runs can go in parallel; SKIP_UPLOAD=1 reuses the already-uploaded datasets.
#   needs KAGGLE_API_TOKEN in the environment (set -a; . ./secrets.env; set +a). Run from the repo root in Git Bash.
set -euo pipefail
: "${KAGGLE_API_TOKEN:?export KAGGLE_API_TOKEN first (never put it in files)}"
SHARDS=${1:-ladder/scout_v6/shards}
OUT=${2:-ladder/scout_v6/train_out/kaggle}
EPOCHS=${3:-8}
OWNER=sohansridutta
STAGE=$(mktemp -d "${TEMP:-/tmp}/bcv6.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/code" "$STAGE/shards" "$STAGE/kernel"
cp ml/train.py ml/build_dataset.py ml/export_cpp.py ml/v6/build_dataset_v6.py ml/v6/train_v6.py ml/v6/policy_nn_v6.hpp ml/v6/parity_main.cpp tools/replay_lite.py tools/replay.py "$STAGE/code/"
[ -n "${INIT:-}" ] && cp "$INIT" "$STAGE/code/init.pt"
[ "${SKIP_UPLOAD:-}" = 1 ] || [ "${SKIP_SHARDS:-}" = 1 ] || cp "$SHARDS"/shard_*.npz "$SHARDS"/manifest.json "$STAGE/shards/"
printf '{"title":"bc v6 code","id":"%s/bc-v6-code","licenses":[{"name":"CC0-1.0"}],"isPrivate":true}\n' "$OWNER" > "$STAGE/code/dataset-metadata.json"
printf '{"title":"bc v6 shards%s","id":"%s/bc-v6-shards%s","licenses":[{"name":"CC0-1.0"}],"isPrivate":true}
' "${DTAG:-}" "$OWNER" "${DTAG:-}" > "$STAGE/shards/dataset-metadata.json"
cp tools/kaggle_train/train_kernel.py "$STAGE/kernel/"
cat > "$STAGE/kernel/kernel-metadata.json" <<EOF
{"id":"$OWNER/bc-v6-train${TAG:-}","title":"bc v6 train${TAG:-}","code_file":"train_kernel.py","language":"python","kernel_type":"script",
 "is_private":true,"enable_gpu":true,"enable_internet":false,
 "dataset_sources":["$OWNER/bc-v6-code","$OWNER/bc-v6-shards${DTAG:-}"],"competition_sources":[],"kernel_sources":[]}
EOF
( echo "import os; os.environ['EPOCHS']='$EPOCHS'; os.environ['TEAM_COND']='${TEAM_COND:-}'; os.environ['ONLY_TEAMS']='${ONLY_TEAMS:-}'; os.environ['CHANNELS']='${CHANNELS:-32}'; os.environ['INIT_PT']='${INIT:+init.pt}'; os.environ['LR']='${LR:-}'"; cat tools/kaggle_train/train_kernel.py ) > "$STAGE/kernel/train_kernel.py"
for d in code shards; do
  [ "${SKIP_UPLOAD:-}" = 1 ] && continue
  [ "$d" = shards ] && [ "${SKIP_SHARDS:-}" = 1 ] && continue
  tools/kaggle_train/push_dataset.sh "$STAGE/$d" create 2>&1 | tail -2 || true
  tools/kaggle_train/push_dataset.sh "$STAGE/$d" version "update $(date +%F-%H%M)" 2>&1 | tail -2 || true
done
sleep 45   # let Kaggle finish processing the datasets before the kernel mounts them
tools/kaggle_train/push_kernel.sh "$STAGE/kernel" 7200 NvidiaTeslaT4
tools/kaggle_train/fetch_output.sh "$OWNER/bc-v6-train${TAG:-}" "$OUT" 3600
ls -la "$OUT"
