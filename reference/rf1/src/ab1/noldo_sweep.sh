#!/bin/bash
# RF1 phase 3: AB1A with +3V3D through the hinge (RF1_LDO=0); buffer at the baseline spot or moved; placer margin; one route at a time
export RF1_LDO=0
run() { tag=$1; P=$2; m=$3; ex=$4
  d=nl_${tag}_${m/./}_${ex//,/_}; mkdir -p $d/out_board
  ( cd $d && BOARD=A RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_AP_EXTRA="$ex" PYTHONPATH=../../src/ab1 python3 ../../src/ab1/autoplace_rf1.py $m > late.json 2>err.txt
    LATE=$(python3 -c "import json; print(json.load(open('late.json'))['late'])")
    BOARD=A RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_LATE="$LATE" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1A_layout.json'))['rep']; print('$d', r['placement_errors'][:2], len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1; }
for m in 0.5 0.6; do
  run base "" $m ""
  run base "" $m "UB"
  run moved "UB:6.0:5.4:270;CBD:8.6:7.9" $m ""
done
echo SWEEP DONE
