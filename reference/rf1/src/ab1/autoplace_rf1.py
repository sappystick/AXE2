#!/usr/bin/env python3
"""RF1 phase 3: greedy auto-placement of the parts RF1 adds to AB1 (divider RB / RAN / RBN, CAN, RISA, CVB), on top of the baseline placement and the
fixed RF1 parts. For each part, largest first: every position on a 0.25 mm grid within 6 mm of the pads it connects to (signal nets only: GND and +5VA
reach their planes through vias), rotations 0 / 90, keeping CLEAR + MARGIN from every other-net pad on its layer and inside the edge keep; cost = summed
distance from each pad to the nearest pad of its net on another part. MARGIN (0.35 mm) leaves a corridor for one track between neighbours.
Prints the RF1_LATE string for afe_layout.py (the RF1 copy). usage (cwd: a scratch folder; env BOARD, RF1_J2, RF1_PUT as for the route):
  python3 autoplace_rf1.py [MARGIN]"""
import os, sys, math, json
import afe_layout as A
D = A.D; MARGIN = float(sys.argv[1]) if len(sys.argv) > 1 else 0.35
PLANE = {"GND", "+5VA"}
CH = len([p for p in D.PARTS if p["ref"].startswith("RAAF")])
MOV = [f"CAN{k}" for k in range(1, CH + 1)] + ["CVB"] + [r for k in range(1, CH + 1) for r in (f"RB{k}", f"RAN{k}", f"RBN{k}")] + ["RISA", "RISB", "RD1", "RD2", "CDF", "CVM"]
EXTRA = [r for r in os.environ.get("RF1_AP_EXTRA", "").split(",") if r]                       # baseline parts the placer may also move (tight window): the ones walling a stuck pin in
EXTRA_WIN = float(os.environ.get("RF1_AP_EXTRA_WIN", "2.0"))
MOV = EXTRA + ([] if os.environ.get("RF1_AP_ONLY") else [r for r in MOV if r in D.BYREF and r not in os.environ.get("RF1_AP_FIX", "").split(",") and r not in EXTRA])   # RF1_AP_ONLY: move the EXTRA parts only (repair loop)          # RF1_AP_FIX: parts the placer must not move

def pads(ref):
    out = A.pads_of(ref)
    for pd in out: pd["net"] = A.owner.get((pd["ref"], pd["num"]))
    return out
def gap(a, b):
    gx = abs(a["x"] - b["x"]) - (a["w"] + b["w"]) / 2; gy = abs(a["y"] - b["y"]) - (a["h"] + b["h"]) / 2
    return math.hypot(max(gx, 0), max(gy, 0)) if (gx > 0 and gy > 0) else max(gx, gy)
def body(ref):
    """body rectangle (x0, x1, y0, y1, side) from the library body (w, h) rotated with the part; a part without a body uses its pad hull"""
    x, y, rot, side = A.PLACE[ref]; lib = D.LIB[D.BYREF[ref]["type"]]; w, h = lib.get("body", (0, 0, 0))[:2]
    if not w or not h:
        ps = pads(ref); return (min(p["x"] - p["w"] / 2 for p in ps), max(p["x"] + p["w"] / 2 for p in ps), min(p["y"] - p["h"] / 2 for p in ps), max(p["y"] + p["h"] / 2 for p in ps), side)
    if rot % 180 == 90: w, h = h, w
    return (x - w / 2, x + w / 2, y - h / 2, y + h / 2, side)
def body_hit(ref, m=0.1):
    a = body(ref)
    for r in list(fixed) + list(placed):
        if r == ref: continue
        b = body(r)
        if a[4] == b[4] and a[0] < b[1] + m and b[0] < a[1] + m and a[2] < b[3] + m and b[2] < a[3] + m: return r
    return None
W_OUT = {"VBIAS_O": 10.0, "VCM_O": 10.0}                                           # buffer outputs: keep the isolation resistor at the pin
fixed = {r: pads(r) for r in [p["ref"] for p in D.PARTS] if r not in MOV}
placed = {r: pads(r) for r in MOV} if os.environ.get("RF1_AP_ONLY") else {}            # repair mode: parts waiting their turn are obstacles at their current spot
def others(ref):
    for r, ps in list(fixed.items()) + list(placed.items()):
        if r != ref: yield from ps
def feasible(ps):
    for a in ps:
        if math.hypot(abs(a["x"]) + a["w"] / 2, abs(a["y"]) + a["h"] / 2) > A.R_BOARD - A.EDGE_KEEP - 0.2: return False
        for b in others(a["ref"]):
            if a["layer"] != b["layer"] and "ALL" not in (a["layer"], b["layer"]): continue
            g = gap(a, b)
            if g < A.CLEAR + (MARGIN if a["net"] != b["net"] else 0.0) and not (a["net"] and a["net"] == b["net"] and g >= 0): return False
    return True
def cost(ps):
    c = 0.0
    for a in ps:
        if not a["net"] or a["net"] in PLANE: continue
        ds = [math.hypot(a["x"] - b["x"], a["y"] - b["y"]) for b in others(a["ref"]) if b["net"] == a["net"]]
        c += (min(ds) if ds else 0.0) * W_OUT.get(a["net"], 1.0)
    return c
res = {}
for ref in MOV:
    x0, y0, rot0, side = A.PLACE[ref]
    nets = {pd["net"] for pd in pads(ref) if pd["net"] and pd["net"] not in PLANE}
    anchors = [b for b in others(ref) if b["net"] in nets]
    cx = sum(b["x"] for b in anchors) / len(anchors) if anchors else x0; cy = sum(b["y"] for b in anchors) / len(anchors) if anchors else y0
    best = None
    if ref in EXTRA: cx, cy = x0, y0                                                    # extra parts stay near their baseline spot
    WIN = EXTRA_WIN if ref in EXTRA else 6.0; n = int(WIN / 0.25)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = cx + 0.25 * i, cy + 0.25 * j
            if math.hypot(x - cx, y - cy) > WIN: continue
            for rot in (0, 90):
                A.PLACE[ref] = (round(x, 3), round(y, 3), rot, side); ps = pads(ref)
                if not feasible(ps) or body_hit(ref): continue
                c = cost(ps)
                if best is None or c < best[0]: best = (c, x, y, rot)
    if best is None: A.PLACE[ref] = (x0, y0, rot0, side); placed[ref] = pads(ref); res[ref] = None; print("no place", ref, file=sys.stderr); continue   # keeps its old spot and stays an obstacle
    _, x, y, rot = best; A.PLACE[ref] = (round(x, 3), round(y, 3), rot, side); placed[ref] = pads(ref); res[ref] = (round(x, 3), round(y, 3), rot, side)
late = ";".join(f"{r}:{v[0]}:{v[1]}:{v[2]}:{v[3]}" for r, v in res.items() if v)
refs = [p["ref"] for p in D.PARTS]; overl = []
for i, r1 in enumerate(refs):
    a = body(r1)
    for r2 in refs[i + 1:]:
        b = body(r2)
        if a[4] == b[4] and a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]: overl.append(f"{r1}-{r2}")
print(json.dumps(dict(late=late, unplaced=[r for r, v in res.items() if v is None], body_overlaps=overl)))
