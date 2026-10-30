#!/usr/bin/env python3
"""RF2 SH1 (2026-10-29): the split-ring electrostatic shield as a KiCad 9 board, then KiCad DRC, KiCad Gerbers and an independent topology check.
37 open copper rings (1.5 mm traces, pitch 2.5 mm from r 12.5 to the edge clearance, skipping the stack-hole band at r 28) on B.Cu (the ground side), every ring split by a 3.0 mm gap on the +x axis; one radial
spine along y = +gap/2 touches each ring at ONE end only, so the copper is a tree (no closed loop around anything: rule 5); one ground pad at the inner
end (single-point ground to the receive board's analog ground). Board 0.4 mm FR4, D228 (the SB1R outline radius), no other copper.
Eddy check (rf2_emi.py estimate): a 1.5 mm trace's own eddies decay with about 0.39 us, gone by the 16.3 us first gate.
Outputs: out/SH1/PF233-RF2-SH1.kicad_pcb, Gerbers, sh1_check.json.  usage (repo root): python3 rf2/head/rf2_shield_pcb.py"""
import os, sys, json, math, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out", "SH1"); os.makedirs(OUT, exist_ok=True)
N, R0, PITCH, W, GAP, R_BOARD, CX, CY = 40, 12.5, 2.5, 1.5, 3.0, 114.0, 150.0, 150.0
ROT = 22.5; HOLES = (22.5, 157.5, 247.5); HOLE_R, HOLE_D, PAD_D = 28.0, 3.4, 5.4    # the SB1R stack holes; 22.5 deg = plated ground pass-through, others NPTH for the pins
R_MAX_RING = R_BOARD - 0.5 - W / 2 - 0.5                                  # board edge clearance 0.5 mm (fab rule) + margin
SKIP = (HOLE_R - PAD_D / 2 - 0.4 - W / 2, HOLE_R + PAD_D / 2 + 0.4 + W / 2)             # no ring may run through the hole band
def rings():
    out = []; k = 0; r = R0
    while r <= R_MAX_RING:                                               # as many rings as fit inside the edge clearance (the hole band costs 3)
        if not (SKIP[0] < r < SKIP[1]):
            d = math.asin((GAP / 2) / r); out.append((r, d))
        r += PITCH
    return out
def build():
    import pcbnew
    b = pcbnew.BOARD(); b.SetCopperLayerCount(2); ds = b.GetDesignSettings(); ds.SetBoardThickness(pcbnew.FromMM(0.4))
    net = pcbnew.NETINFO_ITEM(b, "SHIELD"); b.Add(net)
    def P(x, y):
        c, sn = math.cos(math.radians(ROT)), math.sin(math.radians(ROT)); X, Y = x * c - y * sn, x * sn + y * c       # pattern turned so the spine runs along 22.5 deg
        return pcbnew.VECTOR2I(pcbnew.FromMM(CX + X), pcbnew.FromMM(CY - Y))
    e = pcbnew.PCB_SHAPE(b); e.SetShape(pcbnew.SHAPE_T_CIRCLE); e.SetCenter(P(0, 0)); e.SetEnd(P(R_BOARD, 0)); e.SetLayer(pcbnew.Edge_Cuts); e.SetWidth(pcbnew.FromMM(0.1)); b.Add(e)
    def track(a, c):
        t = pcbnew.PCB_TRACK(b); t.SetStart(a); t.SetEnd(c); t.SetWidth(pcbnew.FromMM(W)); t.SetLayer(pcbnew.B_Cu); t.SetNet(net); b.Add(t)
    def arc(r, a0, a1):
        t = pcbnew.PCB_ARC(b); am = (a0 + a1) / 2
        t.SetStart(P(r * math.cos(a0), r * math.sin(a0))); t.SetMid(P(r * math.cos(am), r * math.sin(am))); t.SetEnd(P(r * math.cos(a1), r * math.sin(a1)))
        t.SetWidth(pcbnew.FromMM(W)); t.SetLayer(pcbnew.B_Cu); t.SetNet(net); b.Add(t)
    for r, d in rings():
        a = d; step = (2 * math.pi - 2 * d) / 4
        for i in range(4): arc(r, a + i * step, a + (i + 1) * step)
    rs = rings(); x0 = rs[0][0] * math.cos(rs[0][1]); x1 = rs[-1][0] * math.cos(rs[-1][1])
    track(P(x0, GAP / 2), P(HOLE_R - PAD_D / 2 + 0.3, GAP / 2)); track(P(HOLE_R + PAD_D / 2 - 0.3, GAP / 2), P(x1, GAP / 2))   # spine in two halves, each ending on the ground pad
    for i, hd in enumerate(HOLES):                                       # plated ground pad on the spine at 22.5 deg; NPTH clearance holes for the two pins
        xh, yh = HOLE_R * math.cos(math.radians(hd - ROT)), HOLE_R * math.sin(math.radians(hd - ROT))
        if i == 0: xh, yh = HOLE_R, GAP / 2                                  # on the spine line (pattern frame)
        fp = pcbnew.FOOTPRINT(b); fp.SetReference(f"H{i+1}"); fp.SetPosition(P(xh, yh)); b.Add(fp); pad = pcbnew.PAD(fp)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE); pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE); pad.SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(HOLE_D), pcbnew.FromMM(HOLE_D)))
        if i == 0:
            pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH); pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(PAD_D), pcbnew.FromMM(PAD_D))); pad.SetLayerSet(pcbnew.PAD.PTHMask()); pad.SetNet(net)
        else:
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(HOLE_D), pcbnew.FromMM(HOLE_D))); pad.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
        pad.SetNumber("1"); pad.SetPosition(P(xh, yh)); fp.Add(pad)
    path = os.path.join(OUT, "PF233-RF2-SH1.kicad_pcb"); pcbnew.SaveBoard(path, b); return path
def topology():
    """independent check with shapely: union of all copper; a closed loop would leave a hole (interior ring) in the union"""
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    geo = []
    for r, d in rings():
        th = np.linspace(d, 2 * math.pi - d, 720); geo.append(LineString(np.c_[r * np.cos(th), r * np.sin(th)]).buffer(W / 2, 16))
    rs = rings(); x0 = rs[0][0] * math.cos(rs[0][1]); x1 = rs[-1][0] * math.cos(rs[-1][1])
    geo.append(LineString([(x0, GAP / 2), (HOLE_R - PAD_D / 2 + 0.3, GAP / 2)]).buffer(W / 2, 16)); geo.append(LineString([(HOLE_R + PAD_D / 2 - 0.3, GAP / 2), (x1, GAP / 2)]).buffer(W / 2, 16)); geo.append(Point(HOLE_R, GAP / 2).buffer(PAD_D / 2, 32).difference(Point(HOLE_R, GAP / 2).buffer(HOLE_D / 2, 32)))
    u = unary_union(geo); parts = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    holes = sum(len(p.interiors) for p in parts)
    # clearance between the free ring ends (-d) and the spine
    free = min(Point(r * math.cos(-d), r * math.sin(-d)).distance(LineString([(x0, GAP / 2), (x1, GAP / 2)])) - W for r, d in rings())
    pins = [Point(HOLE_R * math.cos(math.radians(h - ROT)), HOLE_R * math.sin(math.radians(h - ROT))).buffer(HOLE_D / 2 + 0.4) for h in HOLES[1:]]
    pin_clear = min(u.distance(p.centroid) - HOLE_D / 2 for p in pins)
    holes -= 1                                                          # the plated ground pad's annulus around its drill: the only closed copper path, 5.4 mm, eddy tau about 0.45 us
    return dict(copper_pieces=len(parts), holes_in_copper_excluding_pad_drill=holes, loop_free=holes == 0 and len(parts) == 1, copper_to_pin_holes_mm=round(pin_clear, 2), rings_skipped_band_mm=[round(x, 1) for x in SKIP], min_free_end_to_spine_mm=round(free, 3),
                ring_spacing_mm=round(PITCH - W, 3), copper_area_cm2=round(u.area / 100, 1), eddy_tau_us=round(4e-7 * math.pi * 5.8e7 * 35e-6 * W * 1e-3 / math.pi ** 2 * 1e6, 3))
if __name__ == "__main__":
    pcb = build(); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
    S = os.path.join(OUT, "drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json", "--units", "mm", "-o", S, pcb], capture_output=True, text=True)
    d = json.load(open(S)); err = [v for v in d.get("violations", []) if v["severity"] == "error"]
    g = subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--layers", "F.Cu,B.Cu,F.Mask,B.Mask,Edge.Cuts", "--no-protel-ext", "-o", os.path.join(OUT, "gerber") + "/", pcb], capture_output=True, text=True)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th", "-o", os.path.join(OUT, "gerber") + "/", pcb], capture_output=True, text=True)
    res = dict(board="RF2 SH1 split-ring shield", rings=len(rings()), outer_ring_r_mm=round(rings()[-1][0], 2), trace_mm=W, pitch_mm=PITCH, gap_mm=GAP, kicad_drc_errors=len(err), kicad_drc_error_types=sorted({v["type"] for v in err}),
               kicad_unconnected=len(d.get("unconnected_items", [])), gerber_rc=g.returncode, gerbers=sorted(os.listdir(os.path.join(OUT, "gerber"))) if os.path.isdir(os.path.join(OUT, "gerber")) else [],
               topology=topology())
    json.dump(res, open(os.path.join(OUT, "sh1_check.json"), "w"), indent=1); print(json.dumps(res))
