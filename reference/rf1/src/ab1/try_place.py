#!/usr/bin/env python3
"""RF1 helper: placement check for a candidate (BOARD, RF1_J2, RF1_RB, RF1_PUT from the environment); prints the errors and the pads of named parts"""
import os, sys, json
import afe_layout as A
print(json.dumps(A.placement_check()))
for r in sys.argv[1:]:
    print(r, A.PLACE.get(r), [(p["num"], round(p["x"], 2), round(p["y"], 2), round(p["w"], 2), round(p["h"], 2)) for p in A.PADS if p["ref"] == r])
