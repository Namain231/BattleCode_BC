#!/bin/bash
# usage: run_games.sh JOBFILE OUTTSV ; job line: tag engine map A B seed
J=/home/claude/the-loong-game/harness/zig_judge/zig-out/bin/loong-judge
OUT=$2
run() { read tag eng map a b seed <<<"$1"; d=$(dirname $OUT)/replays; mkdir -p $d
  r=$d/$tag.replay
  line=$(nice -n 10 $J --engine $eng --map $map --a $a --b $b --seed $seed --replay $r 2>/dev/null | tail -1)
  echo -e "$tag\t$(basename $map .map)\t$(basename $a .wasm)\t$(basename $b .wasm)\t$seed\t$line" >> $OUT; }
export -f run; export J OUT
grep -v '^#' $1 | xargs -P2 -I{} bash -c 'run "{}"'
