#!/bin/bash
# RF1 phase 3: auto-placement that may also move the baseline parts around the stuck pins (2 mm window), then route; one at a time
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90"
PA="$C;CLI:11.2:6.6;UB:6.0:5.4:270;CBD:8.6:7.9;RD1:14.8:4.9;RD2:14.8:6.4"; PB="$C;CLI:13.2:6.5"
run() { B=$1; P=$2; m=$3; ex=$4
  d=ex_${B}_${m/./}_${ex//,/_}; mkdir -p $d/out_board
  ( cd $d && BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_AP_EXTRA="$ex" PYTHONPATH=../../src/ab1 python3 ../../src/ab1/autoplace_rf1.py $m > late.json 2>err.txt
    LATE=$(python3 -c "import json; print(json.load(open('late.json'))['late'])")
    BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_LATE="$LATE" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1$B''_layout.json'))['rep']; print('$d', r['placement_errors'][:2], len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1; }
for ex in D2 D2,D1 D2,RF1,CF1 D2,SW2,RS2; do run B "$PB" 0.5 $ex; done
for ex in CLO CLO,RB2 CLO,RB2,CAAF2 CLO,CBD,RAAF2; do run A "$PA" 0.6 $ex; done
echo SWEEP DONE
