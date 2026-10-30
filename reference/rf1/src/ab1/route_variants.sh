#!/bin/bash
# RF1 phase 3: route a fixed list of placement variants, one at a time, each in its own scratch folder; print the open nets of each
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90;CLI:11.2:6.6"
declare -A PUT=( [A]="$C;RISA:8.3:1.95;UB:6.0:5.4:270;CBD:8.6:7.9;RD1:14.8:4.9;RD2:14.8:6.4" [B]="$C;RISA:12.6:-3.0" )
declare -A J2=( [A]="11.0,-12.8" [B]="3.0,-17.4" )
for B in A B; do for rb in 6.6,1.2 8.9,-1.2; do for pre in "" "CS,VBIAS_O,VCM_O,BLANK"; do
  d=var_${B}_${rb//[,.-]/_}_${pre:+pre}; mkdir -p $d/out_board
  ( cd $d && BOARD=$B RF1_J2=${J2[$B]} RF1_RB=$rb RF1_PUT="${PUT[$B]}" AFE_PRE="$pre" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1$B''_layout.json'))['rep']; print('$d', len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>/dev/null || echo "$d no result"
done; done; done
