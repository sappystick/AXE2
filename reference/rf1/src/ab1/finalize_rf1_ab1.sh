#!/bin/bash
# RF1 phase 3: export a routed RF1 AB1 layout to KiCad (the baseline exporter, run on the RF1 generator copies) and run KiCad's DRC and the repo's independent DRC.
# usage (repo root): [FR_RIP=NET,...] experiments/RF1_rigidflex/src/ab1/finalize_rf1_ab1.sh BOARD SCRATCH_DIR "RF1_PUT" ; SCRATCH_DIR holds late.json and out_board/AB1<B>_layout.json
set -e
B=$1; SRC=$(cd "$2" && pwd); P=$3; ROOT=$(pwd); EXP=$ROOT/experiments/RF1_rigidflex; F=$EXP/build_ab1/final_$B
mkdir -p $F/out_board; cp $SRC/out_board/AB1${B}_layout.json $F/out_board/; cp $SRC/late.json $F/
LATE=$(python3 -c "import json; print(json.load(open('$F/late.json'))['late'])")
cd $F
BOARD=$B RF1_J2=15.6,0.0,90 RF1_PUT="$P" RF1_LATE="$LATE" PYTHONPATH=$EXP/src/ab1:$ROOT/work python3 $EXP/src/ab1/afe_export.py > export.log 2>&1 || { tail -5 export.log; exit 1; }
cd $ROOT
PCB=$F/kit_v3/PCB_AB1$B/PF233-AB1$B.kicad_pcb
if [ -n "$FR_RIP" ]; then   # Freerouting step (src/pcb/freeroute.py): the named nets are ripped and Freerouting closes them and anything else left open; the routed board replaces the export
  python3 src/pcb/freeroute.py $PCB $F/fr/PF233-AB1$B.kicad_pcb --rip "$FR_RIP" --passes ${FR_PASSES:-30} --report $F/freeroute.json 2>&1 | grep -v "memory leak" | tail -1 | cut -c1-300
  cp $F/fr/PF233-AB1$B.kicad_pcb $PCB
  # the exporter's own Gerbers and preview predate the Freerouting routes: kept aside, not deleted, so nobody fabricates them by mistake
  python3 -c "import os,shutil,sys; k=sys.argv[1]; d=os.path.join(k,'pre_freerouting'); os.makedirs(d,exist_ok=True); [shutil.move(os.path.join(k,f),os.path.join(d,f)) for f in sorted(os.listdir(k)) if f.endswith(('.gbr','.drl','_layout_preview.png','_board_with_components.stl'))]" $(dirname $PCB)
fi
# fabrication Gerbers and drill written by KiCad from the final board (as the baseline gerber-ab1 step does)
python3 src/pcb/kicad_gerber.py $PCB AB1$B $F/GERBER_AB1$B PF233-AB1$B F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts | head -c 120; echo
python3 src/pcb/kicad_drc.py $PCB $F/kicad_drc.json AB1$B 2>/dev/null | head -c 300; echo
python3 src/pcb/indep_drc.py AB1$B $PCB $F/indep_drc.json | tail -2
( cd $ROOT/work && python3 gerber_edge_check.py $F/gerber_edge.json $F/GERBER_AB1$B PF233-AB1$B | tail -1 | cut -c1-200 )
