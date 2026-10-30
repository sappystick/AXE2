#!/bin/bash
# RF1 phase 3: second placer (reference cluster may use the back side, caps anchored to their pins) x corridor margin, then route; one at a time
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90"
declare -A PUT=( [A]="$C;CLI:11.2:6.6" [B]="$C;CLI:13.2:6.5" )
for B in A B; do for m in 0.35 0.5 0.6; do
  d=v2_${B}_${m/./}; mkdir -p $d/out_board
  ( cd $d && BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="${PUT[$B]}" PYTHONPATH=../../src/ab1 python3 ../../src/ab1/autoplace_rf1_v2.py $m > late.json 2>err.txt
    LATE=$(python3 -c "import json; print(json.load(open('late.json'))['late'])")
    BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="${PUT[$B]}" RF1_LATE="$LATE" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1$B''_layout.json'))['rep']; print('$d', r['placement_errors'][:2], len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1
done; done
