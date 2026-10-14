#!/usr/bin/env bash
# Usage: push_dataset.sh DATASET_DIR [create|version [VERSION_NOTES]]
# DATASET_DIR needs dataset-metadata.json. New datasets are PRIVATE.
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

: "${KAGGLE_API_TOKEN:?Export KAGGLE_API_TOKEN before running; do not put it in files}"
[[ $# -ge 1 && $# -le 3 ]] || { echo "Usage: $0 DATASET_DIR [create|version [VERSION_NOTES]]" >&2; exit 2; }
dir=$(cd -- "$1" && pwd)
mode=${2:-create}
cd -- "$dir"
[[ -f dataset-metadata.json ]] || { echo 'Missing dataset-metadata.json' >&2; exit 2; }
# Using -p . avoids Kaggle 2.2.4's Windows upload-state path bug.
if [ "$mode" = upsert ]; then
  dataset_id=$(uv_retry run --python 3.11 python -c 'import json; print(json.load(open("dataset-metadata.json", encoding="utf-8"))["id"])')
  if dataset_status=$(uv_retry run --python 3.11 --with kaggle==2.2.4 kaggle datasets status "$dataset_id" --format json 2>&1); then
    mode=version
  elif printf '%s' "$dataset_status" | grep -Eiq '404|not found|does not exist'; then
    mode=create
  else
    printf '%s\n' "$dataset_status" >&2
    exit 1
  fi
fi
case "$mode" in
  create) uv_retry run --python 3.11 --with kaggle==2.2.4 kaggle datasets create -p . -r skip ;;
  version) uv_retry run --python 3.11 --with kaggle==2.2.4 kaggle datasets version -p . -r skip -m "${3:-Training shards update}" ;;
  *) echo 'Mode must be create, version or upsert' >&2; exit 2 ;;
esac
