#!/bin/bash
# RF1 phase 3: AB1A auto-placement with the buffer UB and its neighbours movable (2 mm window), two margins; one route at a time
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90"; PA="$C;CLI:11.2:6.6;UB:6.0:5.4:270;CBD:8.6:7.9;RD1:14.8:4.9;RD2:14.8:6.4"
run() { m=$1; ex=$2
  d=exa_${m/./}_${ex//,/_}; mkdir -p $d/out_board
  ( cd $d && BOARD=A RF1_J2=15.6,0.0,90 RF1_PUT="$PA" RF1_AP_EXTRA="$ex" PYTHONPATH=../../src/ab1 python3 ../../src/ab1/autoplace_rf1.py $m > late.json 2>err.txt
    LATE=$(python3 -c "import json; print(json.load(open('late.json'))['late'])")
    BOARD=A RF1_J2=15.6,0.0,90 RF1_PUT="$PA" RF1_LATE="$LATE" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1A_layout.json'))['rep']; print('$d', r['placement_errors'][:2], len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1; }
for m in 0.6 0.5; do for ex in UB UB,CBD UB,CLO,RB2,CAAF2 UB,CBD,CLO UB,CLO,RB2,CAAF2,RAAF2; do run $m $ex; done; done
echo SWEEP DONE
