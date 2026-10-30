#!/bin/bash
# RF1 phase 3: positions of the AIN- divider (RAN, CAN, RBN) per row: placement check first, then route; one at a time
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90"
declare -A PUT=( [A]="$C;CLI:11.2:6.6;RISA:6.4:1.9;UB:6.0:5.4:270;CBD:8.6:7.9;CVB:13.0:-3.2" [B]="$C;CLI:13.2:6.5;RISA:1.6:10.4" )
for B in A B; do for an in "6.6,1.25,8.9,1.35,10.9,-1.2" "6.6,-1.2,10.9,0.0,10.9,1.3" "6.6,1.25,10.9,0.0,10.9,-1.3" "6.6,-1.2,8.9,1.35,10.9,-1.2"; do
  pc=$(BOARD=$B RF1_J2=15.6,0.0,90 RF1_AN=$an RF1_PUT="${PUT[$B]}" PYTHONPATH=../src/ab1 python3 ../src/ab1/try_place.py 2>&1 | tail -1)
  if [ "$pc" != "[]" ]; then echo "$B $an placement $pc"; continue; fi
  d=an_${B}_${an//[,.-]/_}; mkdir -p $d/out_board
  ( cd $d && BOARD=$B RF1_J2=15.6,0.0,90 RF1_AN=$an RF1_PUT="${PUT[$B]}" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1$B''_layout.json'))['rep']; print('$B $an', len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])"
done; done
