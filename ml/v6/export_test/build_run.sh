#!/bin/bash
if which g++ >/dev/null 2>&1; then CXX=g++; else CXX="$HOME/toolchains/zig-linux/zig c++"; fi
$CXX -O2 -std=c++17 -I/mnt/c/Users/sohan/Downloads/BattleCode_BC/ml/v6/export_test -I/mnt/c/Users/sohan/Downloads/BattleCode_BC/ml/v6 /mnt/c/Users/sohan/Downloads/BattleCode_BC/ml/v6/parity_main.cpp -o /mnt/c/Users/sohan/Downloads/BattleCode_BC/ml/v6/export_test/parity.out && /mnt/c/Users/sohan/Downloads/BattleCode_BC/ml/v6/export_test/parity.out /mnt/c/Users/sohan/Downloads/BattleCode_BC/ml/v6/export_test/in.bin /mnt/c/Users/sohan/Downloads/BattleCode_BC/ml/v6/export_test/out.bin
