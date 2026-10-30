#!/bin/bash
# RF1 phase 3: rip-up rounds (the repo's afe_ripup strategy, RF1 copy) on the recorded RF1 placement of each board; one board at a time
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90;CLI:11.2:6.6"
declare -A PUT=( [A]="$C;RISA:8.3:1.95;UB:6.0:5.4:270;CBD:8.6:7.9;RD1:14.8:4.9;RD2:14.8:6.4;RISB:6.8:8.85" [B]="$C;RISA:1.6:10.4;RISB:7.6:11.6:90" )
declare -A J2=( [A]="11.0,-12.8" [B]="3.0,-17.4" )
for B in A B; do
  d=ripup_$B; mkdir -p $d/out_board
  ( cd $d && BOARD=$B RF1_J2=${J2[$B]} RF1_RB=8.9,-1.2 RF1_PUT="${PUT[$B]}" PYTHONPATH=../../src/ab1 timeout 5400 python3 ../../src/ab1/afe_ripup.py $B 6 )
done
