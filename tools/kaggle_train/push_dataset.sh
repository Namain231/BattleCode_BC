#!/usr/bin/env bash
# Usage: push_dataset.sh DATASET_DIR [create|version [VERSION_NOTES]]
# DATASET_DIR needs dataset-metadata.json. New datasets are PRIVATE.
set -euo pipefail
: "${KAGGLE_API_TOKEN:?Export KAGGLE_API_TOKEN before running; do not put it in files}"
[[ $# -ge 1 && $# -le 3 ]] || { echo "Usage: $0 DATASET_DIR [create|version [VERSION_NOTES]]" >&2; exit 2; }
dir=$(cd -- "$1" && pwd)
mode=${2:-create}
cd -- "$dir"
[[ -f dataset-metadata.json ]] || { echo 'Missing dataset-metadata.json' >&2; exit 2; }
# Using -p . avoids Kaggle 2.2.4's Windows upload-state path bug.
case "$mode" in
  create) uv run --python 3.11 --with kaggle==2.2.4 kaggle datasets create -p . -r skip ;;
  version) uv run --python 3.11 --with kaggle==2.2.4 kaggle datasets version -p . -r skip -m "${3:-Training shards update}" ;;
  *) echo 'Mode must be create or version' >&2; exit 2 ;;
esac
