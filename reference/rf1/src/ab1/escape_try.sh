#!/bin/bash
# RF1 phase 3: router escape options on the best placements so far (one route at a time)
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90"
PA_fin="$C;CLI:11.2:6.6;UB:6.0:5.4:270;CBD:8.6:7.9;RD1:14.8:4.9;RD2:14.8:6.4"
PB="$C;CLI:13.2:6.5"
try() { B=$1; SRC=$2; P=$3; tag=$4; shift 4
  LATE=$(python3 -c "import json; print(json.load(open('$SRC/late.json'))['late'])"); d=esc_${B}_$tag; mkdir -p $d/out_board; cp $SRC/late.json $d/
  ( cd $d && env BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_LATE="$LATE" "$@" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1$B''_layout.json'))['rep']; print('$d', r['placement_errors'][:2], len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1; }
try B sw3_B_05_free "$PB" fanfirst AFE_FANFIRST=1
try B sw3_B_05_free "$PB" nostub AFE_NOSTUB=SW2.2
try B sw3_B_05_free "$PB" both AFE_FANFIRST=1 AFE_NOSTUB=SW2.2
try A fin_A "$PA_fin" fanfirst AFE_FANFIRST=1
try A fin_A "$PA_fin" nostub AFE_NOSTUB=RISA.2,U1.7
try A fin_A "$PA_fin" both AFE_FANFIRST=1 AFE_NOSTUB=RISA.2,U1.7
