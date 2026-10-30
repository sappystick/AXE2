#!/bin/bash
# RF1 phase 3: the AB1 router's net order depends on Python's hash seed; route one placement with fixed PYTHONHASHSEED values (reproducible), one at a time
B=$1; SRC=$2; P=$3; N=${4:-16}
LATE=$(python3 -c "import json; print(json.load(open('$SRC/late.json'))['late'])")
for s in $(seq 0 $((N-1))); do
  d=seed_${B}_$(basename $SRC)_$s; mkdir -p $d/out_board; cp $SRC/late.json $d/
  ( cd $d && PYTHONHASHSEED=$s BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_LATE="$LATE" PYTHONPATH=../../src/ab1 timeout 900 python3 ../../src/ab1/afe_layout.py --route >/dev/null 2>&1 )
  python3 -c "
import json; r=json.load(open('$d/out_board/AB1$B''_layout.json'))['rep']; print('$d', len(r['unrouted'])+len(r['fanout_failed']), r['unrouted'], r['fanout_failed'])" 2>&1 | tail -1
done
echo SEEDS DONE
