#!/bin/bash
# RF1 phase 3: AB1B best placement (sw3_B_05: one open, VBIAS at SW2.2) with small SW2 / CSW2 nudges; one route at a time
P="ULD:11.8:4.0:90;CLO:9.6:2.8:90;CLI:13.2:6.5"; LATE=$(python3 -c "import json; print(json.load(open('sw3_B_05_free/late.json'))['late'])")
for n in "SW2:0.3:0" "SW2:-0.3:0" "SW2:0:0.3" "SW2:0:-0.3" "CSW2:0.4:0" "CSW2:-0.4:0"; do
  d=bn_${n//[:.-]/_}; mkdir -p $d/out_board; cp sw3_B_05_free/late.json $d/
  ( cd $d && BOARD=B RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_LATE="$LATE" AFE_NUDGE="RD2:0.4:0,CRF:0:-0.3,$n" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1B_layout.json'))['rep']; print('$d', r['placement_errors'][:2], len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1
done
