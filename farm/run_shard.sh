#!/bin/sh
# Run one jobs file on every core of this machine (or THREADS). Output: results_<name>.tsv
# usage: sh run_shard.sh jobs.tsv [threads]
cd "$(dirname "$0")"
J="$1"; T="${2:-$(nproc)}"
mkdir -p replays
nice -n 10 ./loong-judge --engine engine.wasm --jobs "$J" --threads "$T" --debug 0 > "results_$(basename "$J" .tsv).tsv"
