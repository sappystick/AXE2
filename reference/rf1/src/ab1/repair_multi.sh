#!/bin/bash
# RF1 phase 3: repair loop from several 2-open AB1A starting layouts (each with the RF1_PUT it was made with); one at a time
C="ULD:11.8:4.0:90;CLO:9.6:2.8:90"; PA="$C;CLI:11.2:6.6;UB:6.0:5.4:270;CBD:8.6:7.9;RD1:14.8:4.9;RD2:14.8:6.4"
for s in sw3_A_06_free fin_A a3_06_; do echo "== $s"; python3 ../src/ab1/repair_loop.py A $s "$PA" 0.5 6 2>&1 | sed "s/^/$s /"; mkdir -p keep_$s; done
echo REPAIR DONE
