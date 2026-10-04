#!/usr/bin/env bash
# Usage: fetch_output.sh OWNER/KERNEL OUTPUT_DIR [MAX_WAIT_SECONDS]
# Poll every 60s; default 40 minutes. Downloads outputs plus the execution log.
set -euo pipefail
: "${KAGGLE_API_TOKEN:?Export KAGGLE_API_TOKEN before running; do not put it in files}"
[[ $# -ge 2 && $# -le 3 ]] || { echo "Usage: $0 OWNER/KERNEL OUTPUT_DIR [MAX_WAIT_SECONDS]" >&2; exit 2; }
kernel=$1
out=$2
max_wait=${3:-2400}
[[ "$max_wait" =~ ^[0-9]+$ ]] || { echo 'MAX_WAIT_SECONDS must be nonnegative' >&2; exit 2; }
mkdir -p -- "$out"
start=$SECONDS
while true; do
  status=$(uv run --python 3.11 --with kaggle==2.2.4 kaggle kernels status "$kernel")
  printf '%s\n' "$status"
  case "$status" in
    *COMPLETE*) break ;;
    *ERROR*|*CANCEL*)
      uv run --python 3.11 --with kaggle==2.2.4 kaggle kernels output "$kernel" -p "$out" || true
      echo 'Kernel failed; inspect downloaded execution log' >&2; exit 1 ;;
    *RUNNING*|*QUEUED*) ;;
    *) echo 'Unrecognized kernel status' >&2; exit 1 ;;
  esac
  if (( SECONDS - start >= max_wait )); then echo 'Timed out waiting for kernel' >&2; exit 124; fi
  sleep 60
done
uv run --python 3.11 --with kaggle==2.2.4 kaggle kernels output "$kernel" -p "$out"
