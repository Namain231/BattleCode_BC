#!/usr/bin/env bash
# Usage: push_kernel.sh KERNEL_DIR [TIMEOUT_SECONDS [ACCELERATOR]]
# Metadata supplies id, title, code_file, dataset_sources and enable_internet.
set -euo pipefail
: "${KAGGLE_API_TOKEN:?Export KAGGLE_API_TOKEN before running; do not put it in files}"
[[ $# -ge 1 && $# -le 3 ]] || { echo "Usage: $0 KERNEL_DIR [TIMEOUT_SECONDS [ACCELERATOR]]" >&2; exit 2; }
dir=$(cd -- "$1" && pwd)
timeout=${2:-43200}
accelerator=${3:-NvidiaTeslaT4}
[[ "$timeout" =~ ^[0-9]+$ && "$timeout" -gt 0 && "$timeout" -le 43200 ]] || { echo 'Timeout must be 1..43200 seconds' >&2; exit 2; }
cd -- "$dir"
# Enforce a private GPU kernel before upload; token stays only in the environment.
uv run --python 3.11 python - <<'PY'
import json, pathlib
p = pathlib.Path('kernel-metadata.json')
d = json.loads(p.read_text(encoding='utf-8-sig'))
d['is_private'] = True
d['enable_gpu'] = True
d['enable_tpu'] = False
p.write_text(json.dumps(d, indent=2) + '\n', encoding='utf-8')
PY
uv run --python 3.11 --with kaggle==2.2.4 kaggle kernels push -p . -t "$timeout" --accelerator "$accelerator"
