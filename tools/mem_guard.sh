#!/bin/bash
# Waits until free physical memory is above a safe floor before letting a caller proceed.
# Usage: bash tools/mem_guard.sh [min_mb]
MIN_MB=${1:-3000}
while true; do
  FREE_KB=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory" 2>/dev/null | tr -d '\r')
  if [ -z "$FREE_KB" ]; then sleep 10; continue; fi
  FREE_MB=$((FREE_KB / 1024))
  if [ "$FREE_MB" -ge "$MIN_MB" ]; then
    echo "mem ok: ${FREE_MB}MB free"
    break
  fi
  echo "mem low (${FREE_MB}MB free, need ${MIN_MB}MB) -- waiting"
  sleep 20
done
