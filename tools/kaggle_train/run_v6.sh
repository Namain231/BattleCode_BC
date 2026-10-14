#!/usr/bin/env bash
# Package the v6 code + shards as PRIVATE Kaggle datasets, push the GPU kernel, wait, download results.
# Usage: [TAG=-x] [TEAM_COND=8] [ONLY_TEAMS=a,b,c] [SKIP_UPLOAD=1] tools/kaggle_train/run_v6.sh [SHARD_DIR] [OUT_DIR] [EPOCHS]
#   TAG gives a separate kernel (bc-v6-train$TAG) so runs can go in parallel; SKIP_UPLOAD=1 reuses the already-uploaded datasets.
#   needs KAGGLE_API_TOKEN in the environment (set -a; . ./secrets.env; set +a). Run from the repo root in Git Bash.
set -euo pipefail
uv_retry() {
  local attempt result
  for attempt in 1 2 3; do
    result=$(uv "$@" 2>&1) && { printf '%s\n' "$result"; return 0; }
    printf '%s\n' "$result" >&2
    if ! printf '%s' "$result" | grep -Eq 'Failed to fetch|invalid peer certificate|Request failed after'; then return 1; fi
  done
  return 1
}

: "${KAGGLE_API_TOKEN:?export KAGGLE_API_TOKEN first (never put it in files)}"
SHARDS=${1:-ladder/scout_v6/shards}
OUT=${2:-ladder/scout_v6/train_out/kaggle}
EPOCHS=${3:-8}
OWNER=sohansridutta
STAGE=$(mktemp -d "${TEMP:-/tmp}/bcv6.XXXXXX")
STAGE_PARENT=$(cd -- "${TEMP:-/tmp}" && pwd -P)
cleanup_stage() {
  local resolved
  resolved=$(cd -- "$STAGE" && pwd -P) || return
  case "$resolved" in
    "$STAGE_PARENT"/bcv6.*) rm -rf -- "$resolved" ;;
    *) printf 'Keeping unexpected staging path: %s\n' "$resolved" >&2 ;;
  esac
}
trap cleanup_stage EXIT
mkdir -p "$STAGE/code" "$STAGE/shards" "$STAGE/kernel"
cp ml/train.py ml/build_dataset.py ml/export_cpp.py ml/v6/build_dataset_v6.py ml/v6/train_v6.py ml/v6/policy_nn_v6.hpp ml/v6/parity_main.cpp tools/replay_lite.py tools/replay.py "$STAGE/code/"
[ -n "${INIT:-}" ] && cp "$INIT" "$STAGE/code/init.pt"
[ -n "${VAL_GAMES:-}" ] && cp "$VAL_GAMES" "$STAGE/code/holdout_games.json"
OLD_HASH= NEW_HASH= HOLDOUT_HASH= INIT_HASH=
if [ -n "${OLD_DATASET:-}" ]; then
  cp "${OLD_MANIFEST:?set OLD_MANIFEST for a mixed-data run}" "$STAGE/code/expected_old_manifest.json"
  cp "$SHARDS/manifest.json" "$STAGE/code/expected_new_manifest.json"
  read -r OLD_HASH NEW_HASH HOLDOUT_HASH INIT_HASH < <(uv_retry run --python 3.11 python - "$STAGE/code" <<'PY' | tr -d '\r'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1])
def identity(man):
    return {"schema_version":man["schema_version"],"config":man["config"],"total_samples":man["total_samples"],
            "games":sorted((g["game"],g["team"],g["side"]) for g in man["games"]),
            "shards":sorted((s["file"],s["samples"],s["bytes"]) for s in man["shards"])}
def sig(name):
    m=json.loads((p/name).read_text())
    return hashlib.sha256(json.dumps(identity(m),sort_keys=True,separators=(",",":")).encode()).hexdigest()
print(sig("expected_old_manifest.json"),sig("expected_new_manifest.json"),hashlib.sha256((p/"holdout_games.json").read_bytes()).hexdigest(),hashlib.sha256((p/"init.pt").read_bytes()).hexdigest() if (p/"init.pt").exists() else "-")
PY
)
fi
[ "${SKIP_UPLOAD:-}" = 1 ] || [ "${SKIP_SHARDS:-}" = 1 ] || cp "$SHARDS"/shard_*.npz "$SHARDS"/manifest.json "$STAGE/shards/"
printf '{"title":"bc v6 code","id":"%s/bc-v6-code","licenses":[{"name":"CC0-1.0"}],"isPrivate":true}\n' "$OWNER" > "$STAGE/code/dataset-metadata.json"
printf '{"title":"bc v6 shards%s","id":"%s/bc-v6-shards%s","licenses":[{"name":"CC0-1.0"}],"isPrivate":true}
' "${DTAG:-}" "$OWNER" "${DTAG:-}" > "$STAGE/shards/dataset-metadata.json"
cp tools/kaggle_train/train_kernel.py "$STAGE/kernel/"
cat > "$STAGE/kernel/kernel-metadata.json" <<EOF
{"id":"$OWNER/bc-v6-train${TAG:-}","title":"bc v6 train${TAG:-}","code_file":"train_kernel.py","language":"python","kernel_type":"script",
 "is_private":true,"enable_gpu":true,"enable_internet":false,
 "dataset_sources":["$OWNER/bc-v6-code","$OWNER/bc-v6-shards${DTAG:-}"${OLD_DATASET:+,\"$OWNER/$OLD_DATASET\"}],"competition_sources":[],"kernel_sources":[]}
EOF
( echo "import os; os.environ['EPOCHS']='$EPOCHS'; os.environ['TEAM_COND']='${TEAM_COND:-}'; os.environ['ONLY_TEAMS']='${ONLY_TEAMS:-}'; os.environ['CHANNELS']='${CHANNELS:-32}'; os.environ['INIT_PT']='${INIT:+init.pt}'; os.environ['LR']='${LR:-}'; os.environ['NEW_DATASET']='bc-v6-shards${DTAG:-}'; os.environ['OLD_DATASET']='${OLD_DATASET:-}'; os.environ['EXPECTED_OLD_HASH']='$OLD_HASH'; os.environ['EXPECTED_NEW_HASH']='$NEW_HASH'; os.environ['EXPECTED_HOLDOUT_HASH']='$HOLDOUT_HASH'; os.environ['EXPECTED_INIT_HASH']='$INIT_HASH'"; cat tools/kaggle_train/train_kernel.py ) > "$STAGE/kernel/train_kernel.py"
for d in code shards; do
  [ "${SKIP_UPLOAD:-}" = 1 ] && continue
  [ "$d" = shards ] && [ "${SKIP_SHARDS:-}" = 1 ] && continue
  if [ "$d" = shards ] && [ "${CREATE_SHARDS:-}" = 1 ]; then
    tools/kaggle_train/push_dataset.sh "$STAGE/$d" upsert
  else
    tools/kaggle_train/push_dataset.sh "$STAGE/$d" upsert "update $(date +%F-%H%M)"
  fi
done
sleep 45   # let Kaggle finish processing the datasets before the kernel mounts them
for dataset in bc-v6-code "bc-v6-shards${DTAG:-}" ${OLD_DATASET:-}; do
  ready_deadline=$((SECONDS + 1800))
  while true; do
    dataset_status=
    for attempt in 1 2 3; do
      if dataset_status=$(uv_retry run --python 3.11 --with kaggle==2.2.4 kaggle datasets status "$OWNER/$dataset" --format json 2>&1); then break; fi
      if ! printf '%s' "$dataset_status" | grep -Eq 'Failed to fetch|invalid peer certificate|Request failed after'; then printf '%s\n' "$dataset_status" >&2; exit 1; fi
    done
    if printf '%s' "$dataset_status" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ready"'; then break; fi
    if (( SECONDS >= ready_deadline )); then printf 'Dataset readiness timeout: %s\n' "$dataset" >&2; exit 124; fi
    sleep 20
  done
done
if [ -n "${READY_MARKER:-}" ] && [ "${SKIP_UPLOAD:-}" != 1 ]; then
  uv_retry run --python 3.11 python - "${READY_MARKER}" "$SHARDS/manifest.json" "$VAL_GAMES" <<'PY'
import hashlib,json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({"new_manifest_sha":hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).hexdigest(),"holdout_sha":hashlib.sha256(pathlib.Path(sys.argv[3]).read_bytes()).hexdigest()}))
PY
fi
tools/kaggle_train/push_kernel.sh "$STAGE/kernel" "${KERNEL_TIMEOUT:-7200}" NvidiaTeslaT4
tools/kaggle_train/fetch_output.sh "$OWNER/bc-v6-train${TAG:-}" "$OUT" "${FETCH_TIMEOUT:-10800}"
ls -la "$OUT"
