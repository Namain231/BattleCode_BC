#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
  exec uv run --python 3.11 --with unswbc python -B tools/farm_scale.py "$@"
fi
if command -v uv.exe >/dev/null 2>&1; then
  exec uv.exe run --python 3.11 --with unswbc python -B tools/farm_scale.py "$@"
fi
if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
  for farm_uv in /mnt/c/Users/*/.local/bin/uv.exe; do
    if [[ -x "$farm_uv" ]]; then
      exec "$farm_uv" run --python 3.11 --with unswbc python -B tools/farm_scale.py "$@"
    fi
  done
fi
exec python3 -B tools/farm_scale.py "$@"
