#!/bin/bash
# RF1 phase 3: swapped buffer halves, baseline buffer position, LDO south of the island; placer v2 (top side, buffer fixed) x margin x VCM network free / fixed
P="ULD:12.1:1.2:180;CLO:11.4:3.0;CLI:14.6:2.0:90"
for fix in "" "RD1,RD2,CDF,CVM"; do for m in 0.35 0.5 0.6; do
  d=swp_A_${m/./}_${fix:+fixvcm}; mkdir -p $d/out_board
  ( cd $d && BOARD=A RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_AP_FIX="$fix" RF1_AP_NOUB=1 RF1_AP_SIDES=F PYTHONPATH=../../src/ab1 python3 ../../src/ab1/autoplace_rf1_v2.py $m > late.json 2>err.txt
    LATE=$(python3 -c "import json; print(json.load(open('late.json'))['late'])")
    BOARD=A RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_LATE="$LATE" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1A_layout.json'))['rep']; print('$d', r['placement_errors'][:2], len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1
done; done
