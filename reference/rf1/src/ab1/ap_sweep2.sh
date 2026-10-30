#!/bin/bash
# RF1 phase 3 sweep 2: corridor margin x (A: VCM network free / fixed with RD1, RD2 moved clear of the LDO)
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90"
run() { B=$1; m=$2; P=$3; FIX=$4; tag=$5
  d=sw3_${B}_${m/./}_$tag; mkdir -p $d/out_board
  ( cd $d && BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_AP_FIX="$FIX" PYTHONPATH=../../src/ab1 python3 ../../src/ab1/autoplace_rf1.py $m > late.json 2>err.txt
    LATE=$(python3 -c "import json; print(json.load(open('late.json'))['late'])")
    BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_LATE="$LATE" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1$B''_layout.json'))['rep']; print('$d', r['placement_errors'][:2], len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1; }
PA="$C;CLI:11.2:6.6;UB:6.0:5.4:270;CBD:8.6:7.9;RD1:14.8:4.9;RD2:14.8:6.4"
for m in 0.4 0.5 0.6; do run A $m "$PA" "RD1,RD2,CDF,CVM" fixvcm; run A $m "$PA" "" free; done
for m in 0.4 0.5 0.6; do run B $m "$C;CLI:13.2:6.5" "" free; done
