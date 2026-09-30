#!/bin/bash
# download bp-run-<i> outputs into ladder/bp_kaggle<i> (retries: this network drops HTTPS; present files are skipped)
cd /d/battlecode/BattleCode_BC/ladder
for i in "$@"; do
  for t in 1 2 3 4 5 6 7 8 9 10; do
    if python -m kaggle kernels output kumaryash1134/bp-run-$i -p bp_kaggle$i --page-size 200 > bp_kaggle$i.fetch.log 2>&1; then
      echo "bp-run-$i: $(find bp_kaggle$i -name 'shard_*.npz' | wc -l) shards (try $t)"; break
    fi
    echo "bp-run-$i: retry $t ($(find bp_kaggle$i -name 'shard_*.npz' 2>/dev/null | wc -l) shards so far): $(tail -1 bp_kaggle$i.fetch.log)"
    sleep 20
  done
done
