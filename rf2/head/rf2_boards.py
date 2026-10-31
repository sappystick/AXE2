#!/usr/bin/env python3
"""RF2 Phase B boards (2026-10-29): MP1, TXJ, LR1 built from the system netlist (rf2_netlist.py) and taken through the full chain:
  1. KiCad 9 board via pcbnew: outline, holes, pads (SMD on F.Cu with paste and mask; wire holes plated through), nets from the netlist
  2. placement check BEFORE routing: no two parts' courtyards (body and pads + 0.25 mm) overlap; every courtyard inside the board less 0.3 mm
  3. routing with the Freerouting step (src/pcb/freeroute.py --strip): default 0.2 / 0.2 mm, via 0.6 / 0.3; HV nets in a >= 1.0 mm class (rule 6);
     TXJ's coil nets in a 2.5 mm / 1.0 mm class (8 A pulses)
  4. KiCad DRC with board rules (generic 0.2 mm, HV nets >= 1.0 mm to anything, TX nets >= 2.0 mm wide)
  5. independent copper check (shapely, from the routed board): minimum clearance overall and from every HV net to every other net
  6. Gerbers + Excellon drill (kicad-cli); 7. pad-by-pad netlist parity; 8. part placement + body boxes in head coordinates for the render
Outputs: out/<B>/PF233-RF2-<B>.kicad_pcb, gerber/, <b>_check.json; out/rf2_boards.json.  usage (repo root): python3 rf2/head/rf2_boards.py [MP1 TXJ LR1]"""
import os, sys, json, math, subprocess, shutil, tempfile, hashlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "src")); import rf2_netlist as NL
from simcache import memo
OUTB = os.path.join(HERE, "out"); CX, CY = 150.0, 150.0
RULES = "0.2,0.2,0.6,0.3"; EDGE = 0.5; FLOOR = 0.15; STALL_S = 180      # Freerouting stall watchdog (s without a finished pass) before the A* fallback                  # edge: the repo's Gerber edge floor (gerber_edge_check 0.5 mm); floor: FAB_RULES track
def rot(x, y, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg)); return x * c - y * s, x * s + y * c
def pads_abs(p):
    """pads of a part in board coordinates (y up): (num, x, y, w, h, shape, drill, rot)"""
    out = []
    for q in NL.LIB[p["type"]]["pads"]:
        dx, dy = rot(q[1], q[2], p["rot"]); out.append((q[0], p["x"] + dx, p["y"] + dy, q[3], q[4], q[5], q[6] if len(q) > 6 else None, p["rot"]))
    return out
def courtyard(p, m=0.25):
    from shapely.geometry import box as sbox, Point
    from shapely import affinity
    from shapely.ops import unary_union
    bw, bl, _ = NL.LIB[p["type"]]["body"]
    g = [affinity.rotate(sbox(-bw / 2, -bl / 2, bw / 2, bl / 2), p["rot"], origin=(0, 0)).buffer(m).buffer(0)]
    g = [affinity.translate(g[0], p["x"], p["y"])]
    for n, x, y, w, h, sh, dr, r in pads_abs(p):
        g.append(Point(x, y).buffer(w / 2 + m) if sh == "circle" else affinity.translate(affinity.rotate(sbox(-w / 2, -h / 2, w / 2, h / 2), r, origin=(0, 0)), x, y).buffer(m))
    return unary_union(g)
def outline_poly(B):
    from shapely.geometry import box as sbox, Point
    if B["kind"] == "rect": return sbox(-B["w"] / 2, -B["h"] / 2, B["w"] / 2, B["h"] / 2)
    if B["kind"] == "poly":
        import rf2_ledgrid as LG; o = LG.outline()
    else: o = Point(0, 0).buffer(B["r_out"], 256).difference(Point(0, 0).buffer(B["r_in"], 256))
    for r, a, d in B.get("holes", []): o = o.difference(Point(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))).buffer(d / 2 + 0.3, 32))
    return o
def placement_check(B):
    cy = {p["ref"]: courtyard(p) for p in B["parts"]}; inner = outline_poly(B).buffer(-0.3); bad = []
    refs = list(cy)
    for i, a in enumerate(refs):
        if not inner.covers(cy[a].buffer(-0.25)): bad.append(f"{a} outside the board")
        for b in refs[i + 1:]:
            if cy[a].intersects(cy[b]) and cy[a].intersection(cy[b]).area > 1e-6: bad.append(f"{a} x {b}")
    return bad
def build(name):
    import pcbnew
    B = NL.BOARDS[name]; od = os.path.join(OUTB, name); os.makedirs(od, exist_ok=True)
    b = pcbnew.BOARD(); b.SetCopperLayerCount(B["layers"]); b.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(B["thickness"]))
    vd, vh = (float(x) for x in B.get("rules", RULES).split(",")[2:4]); ds = b.GetDesignSettings()   # board setup minima = the board's own via rule (flex 0.45 / 0.2)
    ds.m_ViasMinSize = min(ds.m_ViasMinSize, pcbnew.FromMM(vd)); ds.m_MinThroughDrill = min(ds.m_MinThroughDrill, pcbnew.FromMM(vh)); ds.m_ViasMinAnnularWidth = min(ds.m_ViasMinAnnularWidth, pcbnew.FromMM((vd - vh) / 2))
    P = lambda x, y: pcbnew.VECTOR2I(pcbnew.FromMM(CX + x), pcbnew.FromMM(CY - y))
    def edge(shape):
        e = pcbnew.PCB_SHAPE(b); e.SetLayer(pcbnew.Edge_Cuts); e.SetWidth(pcbnew.FromMM(0.1)); b.Add(e); return e
    if B["kind"] == "rect":
        w, h = B["w"] / 2, B["h"] / 2; pts = [(-w, -h), (w, -h), (w, h), (-w, h)]
        for i in range(4):
            e = edge(None); e.SetShape(pcbnew.SHAPE_T_SEGMENT); e.SetStart(P(*pts[i])); e.SetEnd(P(*pts[(i + 1) % 4]))
    elif B["kind"] == "poly":                                              # polygon outline (rf2_ledgrid.outline): exterior + interior rings as segments
        import rf2_ledgrid as LG; o = LG.outline()
        for ring in [o.exterior] + list(o.interiors):
            c = list(ring.coords)
            for a, z in zip(c[:-1], c[1:]):
                e = edge(None); e.SetShape(pcbnew.SHAPE_T_SEGMENT); e.SetStart(P(*a)); e.SetEnd(P(*z))
    else:
        for r in (B["r_out"], B["r_in"]):
            e = edge(None); e.SetShape(pcbnew.SHAPE_T_CIRCLE); e.SetCenter(P(0, 0)); e.SetEnd(P(r, 0))
    nets = {}
    for p in B["parts"]:
        for n in p["pins"].values():
            if n not in nets: ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
    for p in B["parts"]:
        fp = pcbnew.FOOTPRINT(b); fp.SetReference(p["ref"]); fp.SetValue(p["value"]); fp.SetFPID(pcbnew.LIB_ID("RF2", p["type"])); fp.SetPosition(P(p["x"], p["y"])); b.Add(fp)
        for q in NL.LIB[p["type"]]["pads"]:                                 # pads in footprint coordinates; the footprint is rotated after (proper KiCad footprints)
            n, lx, ly, w, h, sh = q[:6]; dr = q[6] if len(q) > 6 else None
            pad = pcbnew.PAD(fp); pad.SetNumber(n); pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(w), pcbnew.FromMM(h)))
            pad.SetShape({"circle": pcbnew.PAD_SHAPE_CIRCLE, "rect": pcbnew.PAD_SHAPE_RECT, "roundrect": pcbnew.PAD_SHAPE_ROUNDRECT}[sh])
            if sh == "roundrect": pad.SetRoundRectRadiusRatio(0.25)
            pad.SetPosition(P(p["x"] + lx, p["y"] + ly))
            if dr:
                pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH); pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE); pad.SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(dr), pcbnew.FromMM(dr))); pad.SetLayerSet(pcbnew.PAD.PTHMask())
            else:
                pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD); pad.SetLayerSet(pcbnew.PAD.SMDMask())
            pad.SetNet(nets[p["pins"][n]]); fp.Add(pad)
        fp.SetOrientationDegrees(p["rot"])
    # every pad where the netlist geometry says it is (catches any rotation-convention error)
    want = {(p["ref"], q[0]): (q[1], q[2]) for p in B["parts"] for q in pads_abs(p)}; worst = 0.0
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            k = (fp.GetReference(), pad.GetNumber())
            if k in want:
                x, y = pcbnew.ToMM(pad.GetPosition().x) - CX, CY - pcbnew.ToMM(pad.GetPosition().y); worst = max(worst, math.hypot(x - want[k][0], y - want[k][1]))
    if worst > 1e-3: sys.exit(f"{name}: built pads differ from the netlist geometry by up to {worst:.3f} mm (rotation convention)")
    for k, (r, a, d) in enumerate(B.get("holes", [])):
        fp = pcbnew.FOOTPRINT(b); fp.SetReference(f"MH{k+1}"); fp.SetFPID(pcbnew.LIB_ID("RF2", "MountingHole_2.0mm")); x, y = r * math.cos(math.radians(a)), r * math.sin(math.radians(a)); fp.SetPosition(P(x, y)); b.Add(fp)
        pad = pcbnew.PAD(fp); pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE); pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(d), pcbnew.FromMM(d))); pad.SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(d), pcbnew.FromMM(d))); pad.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
        pad.SetPosition(P(x, y)); pad.SetNumber(""); fp.Add(pad)
    pr = B.get("preroute")
    if pr:                                                                 # locked pre-routes (kept by Freerouting): open bus arcs, radial links, vias
        def trk(net, a, z, layer):
            t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*z)); t.SetWidth(pcbnew.FromMM(pr["width"])); t.SetLayer(layer); t.SetNet(nets[net]); t.SetLocked(True); b.Add(t)
        for net, r, a0, a1 in pr["arcs"]:
            angs = np.linspace(a0, a1, int(abs(a1 - a0) / 2) + 1)
            for u, v in zip(angs[:-1], angs[1:]): trk(net, (r * math.cos(math.radians(u)), r * math.sin(math.radians(u))), (r * math.cos(math.radians(v)), r * math.sin(math.radians(v))), pcbnew.B_Cu)
        for net, a, r0, r1, vr in pr["links"]:
            c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a)); trk(net, (r0 * c, r0 * s_), (r1 * c, r1 * s_), pcbnew.F_Cu)
            for rv in vr:
                v = pcbnew.PCB_VIA(b); v.SetPosition(P(rv * c, rv * s_)); v.SetWidth(pcbnew.FromMM(0.6)); v.SetDrill(pcbnew.FromMM(0.3)); v.SetNet(nets[net]); v.SetLocked(True); b.Add(v)
    for net_, pts_, w_ in B.get("bus", []):                               # straight locked buses (net, [(x, y), ...], width): on F.Cu and B.Cu, both layers carry the pulse current
        for lay_ in (pcbnew.F_Cu, pcbnew.B_Cu):
            for u, v in zip(pts_[:-1], pts_[1:]):
                t = pcbnew.PCB_TRACK(b); t.SetStart(P(*u)); t.SetEnd(P(*v)); t.SetWidth(pcbnew.FromMM(w_)); t.SetLayer(lay_); t.SetNet(nets[net_]); t.SetLocked(True); b.Add(t)
    if B.get("template") in ("led_ring", "led_grid"):                    # deterministic routing, locked like the pre-routes
        if B["template"] == "led_grid":
            import rf2_ledgrid as LG; T, Vs, _ = LG.copper(); RT = LG
        else:
            import rf2_ring_template as RT
            leds = sorted(((int(p["ref"][2:]), round(math.hypot(p["x"], p["y"]), 3), math.degrees(math.atan2(p["y"], p["x"])) % 360) for p in B["parts"] if p["ref"].startswith("LD")))
            T, Vs, _ = RT.route(leds); T2, V2, _ = RT.feeds(); T += T2; Vs += V2
        for net, lay, pts, w in T:
            for a, z in zip(pts[:-1], pts[1:]):
                if math.hypot(z[0] - a[0], z[1] - a[1]) < 1e-6: continue
                t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*z)); t.SetWidth(pcbnew.FromMM(w)); t.SetLayer(pcbnew.F_Cu if lay == "F" else pcbnew.B_Cu)
                t.SetNet(nets[net]); t.SetLocked(True); b.Add(t)
        for net, (x, y) in Vs:
            v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(pcbnew.FromMM(RT.VIA_D)); v.SetDrill(pcbnew.FromMM(RT.VIA_DR)); v.SetNet(nets[net]); v.SetLocked(True); b.Add(v)
    # keep-out bands along every edge (EDGE mm): the router sees them, so no track or via comes closer to the edge than the Gerber edge floor
    def keepout(poly_xy):
        z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(False); z.SetDoNotAllowZoneFills(True) if hasattr(z, "SetDoNotAllowZoneFills") else z.SetDoNotAllowCopperPour(True)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); z.SetLayerSet(ls); o = z.Outline(); o.NewOutline()
        for x, y in poly_xy: o.Append(pcbnew.FromMM(CX + x), pcbnew.FromMM(CY - y))
        b.Add(z)
    from shapely.geometry import Polygon as SPoly
    band = outline_poly(dict(B, holes=[])).difference(outline_poly(dict(B, holes=[])).buffer(-EDGE))
    for hole in [h for h in B.get("holes", [])]:
        r, a, d = hole; from shapely.geometry import Point as SP
        band = band.union(SP(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))).buffer(d / 2 + EDGE, 32))
    geoms = list(band.geoms) if band.geom_type == "MultiPolygon" else [band]
    for g in geoms:                                                       # a band with a hole is split along x into simple polygons (KiCad keep-outs: one outline each)
        for half in (g.intersection(SPoly([(-500, 0), (500, 0), (500, 500), (-500, 500)])), g.intersection(SPoly([(-500, 0), (500, 0), (500, -500), (-500, -500)]))):
            for piece in (list(half.geoms) if half.geom_type == "MultiPolygon" else [half]):
                if piece.area > 1e-3: keepout(list(piece.exterior.coords)[:-1])
    raw = os.path.join(od, f"PF233-RF2-{name}_placed.kicad_pcb"); pcbnew.SaveBoard(raw, b); return raw, od
def widen_floor(pcb, FLOOR=FLOOR):
    """Freerouting may neck a track below the fab floor at a fine pin: set such segments to the floor; KiCad DRC then decides whether clearances still hold"""
    import pcbnew
    b = pcbnew.LoadBoard(pcb); n = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < pcbnew.FromMM(FLOOR): t.SetWidth(pcbnew.FromMM(FLOOR)); n += 1
    if n: pcbnew.SaveBoard(pcb, b)
    return n
def dru(B):
    # fab floor from the repo (FAB_RULES / dru_gen GEN: 0.15 mm track); RF2 routes at 0.2 / 0.2 and Freerouting may neck to 0.15 at fine pins
    tw, cl = (float(x) for x in B.get("rules", RULES).split(",")[:2]); fl = B.get("floor", FLOOR)
    hv = B.get("hv_nets", []); r = ['(version 1)', f'(rule "generic" (constraint clearance (min {cl}mm)))', f'(rule "track" (constraint track_width (min {fl}mm)))',
                                    '(rule "edge" (constraint edge_clearance (min 0.5mm)))']
    vd, vh = (float(x) for x in B.get("rules", RULES).split(",")[2:4]); r += [f'(rule "via" (constraint via_diameter (min {vd}mm)) (condition "A.Type == \'Via\'"))', f'(rule "via drill" (constraint hole_size (min {vh}mm)) (condition "A.Type == \'Via\'"))']
    if hv:
        cond = " || ".join(f"A.NetName == '{n}' || B.NetName == '{n}'" for n in hv); r.append(f'(rule "HV rule 6" (constraint clearance (min 1.0mm)) (condition "{cond}"))')
    for n, w in B.get("wide", {}).items(): r.append(f'(rule "wide {n}" (constraint track_width (min {w - 0.5:.1f}mm)) (condition "A.NetName == \'{n}\'"))')
    return "\n".join(r) + "\n"
@memo("kicad.drc", files=lambda pcb, B: [pcb], uses=[], tools=["kicad"], key_args=lambda pcb, B: [dru(B), B.get("hv_nets")])
def kicad_drc(pcb, B):
    tmp = tempfile.mkdtemp(); dst = os.path.join(tmp, "b.kicad_pcb"); shutil.copy(pcb, dst)
    open(os.path.join(tmp, "b.kicad_dru"), "w").write(dru(B)); open(os.path.join(tmp, "b.kicad_pro"), "w").write("{}")
    rep = os.path.join(tmp, "drc.json"); subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json", "--units", "mm", "-o", rep, dst], capture_output=True, text=True)
    d = json.load(open(rep)); err = [v for v in d.get("violations", []) if v["severity"] == "error"]
    # control: the HV rule is really loaded (a 50 mm HV clearance must produce violations when there are HV nets)
    ctl = None
    if B.get("hv_nets"):
        open(os.path.join(tmp, "b.kicad_dru"), "w").write(dru(B).replace("(min 1.0mm)", "(min 50mm)"))
        rep2 = os.path.join(tmp, "ctl.json"); subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json", "--units", "mm", "-o", rep2, dst], capture_output=True, text=True)
        ctl = sum(1 for v in json.load(open(rep2)).get("violations", []) if v["type"] == "clearance")
    return dict(errors=len(err), error_types=sorted({v["type"] for v in err}), examples=[v["description"][:100] for v in err[:4]],
                unconnected=len(d.get("unconnected_items", [])), warnings=len([v for v in d.get("violations", []) if v["severity"] == "warning"]), hv_rule_control_violations=ctl)
@memo("rf2.copper_check", files=lambda pcb, B: [pcb], uses=[], key_args=lambda pcb, B: [B, RULES, EDGE, FLOOR])
def copper_check(pcb, B):
    """independent: copper per net from the routed board (pads from the netlist geometry, tracks and vias from the board); min clearances"""
    import pcbnew
    from shapely.geometry import LineString, Point, box as sbox
    from shapely import affinity
    from shapely.ops import unary_union
    bd = pcbnew.LoadBoard(pcb); M = pcbnew.ToMM; per = {}
    for p in B["parts"]:
        for n, x, y, w, h, sh, dr, r in pads_abs(p):
            if sh == "circle": g = Point(x, y).buffer(w / 2, 32)
            elif sh == "roundrect":                                      # corner radius 0.25 x the short side (as written to KiCad: SetRoundRectRadiusRatio(0.25))
                rr = 0.25 * min(w, h); g = affinity.translate(affinity.rotate(sbox(-w / 2 + rr, -h / 2 + rr, w / 2 - rr, h / 2 - rr).buffer(rr, 16), r, origin=(0, 0)), x, y)
            else: g = affinity.translate(affinity.rotate(sbox(-w / 2, -h / 2, w / 2, h / 2), r, origin=(0, 0)), x, y)
            per.setdefault((p["pins"][n], "F" if not dr else "T"), []).append(g)
    for t in bd.GetTracks():
        net = t.GetNetname(); lay = "F" if t.GetLayer() == pcbnew.F_Cu else "B"
        if t.GetClass() == "PCB_VIA":
            x, y = M(t.GetPosition().x) - CX, CY - M(t.GetPosition().y); per.setdefault((net, "T"), []).append(Point(x, y).buffer(M(t.GetWidth(pcbnew.F_Cu)) / 2, 24))
        else:
            a = (M(t.GetStart().x) - CX, CY - M(t.GetStart().y)); z = (M(t.GetEnd().x) - CX, CY - M(t.GetEnd().y))
            per.setdefault((net, lay), []).append(LineString([a, z]).buffer(M(t.GetWidth()) / 2, 16) if a != z else Point(a).buffer(M(t.GetWidth()) / 2, 16))
    layer_geo = {}
    for (net, lay), gs in per.items():
        for L in (("F", "B") if lay == "T" else (lay,)): layer_geo.setdefault(L, {}).setdefault(net, []).extend(gs)
    # rule 5: no net's copper (both layers + vias, projected) may enclose the head axis (a closed loop around it)
    from shapely.geometry import Point as SPt
    axis = SPt(-B["head"]["c"][0], -B["head"]["c"][1]); loops = []
    for net in {k[0] for k in per}:
        u = unary_union([g for (n_, L), gs in per.items() if n_ == net for g in gs]); polys = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
        for pg in polys:
            for ring in pg.interiors:
                from shapely.geometry import Polygon as SPg
                if SPg(ring).contains(axis): loops.append(net)
    hv = set(B.get("hv_nets", [])); min_all, min_hv = 1e9, 1e9; worst = None; worst_all = None
    for L, nets in layer_geo.items():
        U = {n: unary_union(g) for n, g in nets.items()}; names = list(U)
        for i, a in enumerate(names):
            for b2 in names[i + 1:]:
                d = U[a].distance(U[b2])
                if d < min_all: min_all, worst_all = d, (L, a, b2)
                if a in hv or b2 in hv:
                    if d < min_hv: min_hv, worst = d, (L, a, b2)
    clr = float(B.get("rules", RULES).split(",")[1])
    return dict(loops_around_axis=sorted(set(loops)), min_clearance_mm=round(min_all, 3), worst_pair=worst_all, min_hv_clearance_mm=round(min_hv, 3) if hv else None, worst_hv_pair=worst, ok=min_all >= clr - 1e-3 and (not hv or min_hv >= 1.0 - 1e-3) and not loops)
def parity(pcb, B):
    import pcbnew
    bd = pcbnew.LoadBoard(pcb); got = {}
    for fp in bd.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNumber(): got[(fp.GetReference(), pad.GetNumber())] = pad.GetNetname()
    want = {(p["ref"], n): net for p in B["parts"] for n, net in p["pins"].items()}
    diff = [f"{k}: board {got.get(k)} netlist {v}" for k, v in want.items() if got.get(k) != v] + [f"{k}: on the board, not in the netlist" for k in got if k not in want]
    return dict(pads_checked=len(want), mismatches=diff[:10], ok=not diff)
def pad_signature(pcb):
    """placement fingerprint: every pad (ref, number, net, position) and the board outline box"""
    import pcbnew
    bd = pcbnew.LoadBoard(pcb); M = pcbnew.ToMM; bb = bd.GetBoardEdgesBoundingBox()
    pads = {(fp.GetReference(), p.GetNumber()): (p.GetNetname(), M(p.GetPosition().x), M(p.GetPosition().y)) for fp in bd.GetFootprints() for p in fp.Pads()}
    return pads, [M(v) for v in (bb.GetX(), bb.GetY(), bb.GetWidth(), bb.GetHeight())]
def changed_pads(old, new, tol=0.005):
    """pads whose net or position differ (>= 5 um; pcbnew save / load of rotated pads moves them by up to 1 um), as (net, old x, old y);
    None = outline or pad set changed"""
    (pa, ba), (pb, bb) = pad_signature(old), pad_signature(new)
    if pa.keys() != pb.keys() or any(abs(x - y) >= tol for x, y in zip(ba, bb)): return None
    return [pa[k] for k in pa if pa[k][0] != pb[k][0] or abs(pa[k][1] - pb[k][1]) >= tol or abs(pa[k][2] - pb[k][2]) >= tol] + \
           [pb[k] for k in pa if pa[k][0] != pb[k][0]]
def drc_bad_uuids(pcb, B):
    """uuids of the items KiCad DRC flags as errors (same rules as kicad_drc)"""
    tmp = tempfile.mkdtemp(); dst = os.path.join(tmp, "b.kicad_pcb"); shutil.copy(pcb, dst)
    open(os.path.join(tmp, "b.kicad_dru"), "w").write(dru(B)); open(os.path.join(tmp, "b.kicad_pro"), "w").write("{}")
    rep = os.path.join(tmp, "drc.json"); subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json", "--units", "mm", "-o", rep, dst], capture_output=True, text=True)
    return {it["uuid"] for v in json.load(open(rep)).get("violations", []) if v["severity"] == "error" for it in v.get("items", []) if "uuid" in it}
def resume_input(name, raw, pcb, B, od):
    """incremental route (owner 2026-10-30: route only what is still open, never re-run a whole board for a few open nets): the unlocked tracks and vias
    of the last routed board are copied onto the new build; KiCad DRC then runs on that board and the unlocked
    items it flags are deleted; Freerouting gets it without --strip, so it routes only the open connections. RF2_FULL=1 forces a full route.
    Of a net whose pads moved, only the copper within 2 mm of a moved pad is dropped. Returns (input board, report) or (None, reason)."""
    import pcbnew
    if os.environ.get("RF2_FULL") == "1": return None, "RF2_FULL=1"
    if not os.path.exists(pcb): return None, "no earlier route"
    ch = changed_pads(pcb, raw)
    if ch is None: return None, "outline or pad set changed"
    def near_moved(t):                                       # copper of a changed pad's net within 2 mm of that pad's old position
        M = pcbnew.ToMM; pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
        return any(t.GetNetname() == n and math.hypot(M(q.x) - x, M(q.y) - y) < 2.0 for n, x, y in ch for q in pts)
    covered = set()
    if B.get("template") == "led_grid":
        import rf2_ledgrid as LG; covered = LG.copper()[2]
    if B.get("template") == "led_ring":
        import rf2_ring_template as RT
        leds = sorted(((int(p["ref"][2:]), round(math.hypot(p["x"], p["y"]), 3), math.degrees(math.atan2(p["y"], p["x"])) % 360) for p in B["parts"] if p["ref"].startswith("LD")))
        covered = RT.route(leds)[2] | RT.feeds()[2]
    old = pcbnew.LoadBoard(pcb); new = pcbnew.LoadBoard(raw); copied = 0
    for t in old.GetTracks():
        if t.IsLocked() or near_moved(t) or t.GetNetname() in covered: continue
        net = new.FindNet(t.GetNetname())
        if t.GetClass() == "PCB_VIA":
            v = pcbnew.PCB_VIA(new); v.SetPosition(t.GetPosition()); v.SetDrill(t.GetDrill()); v.SetWidth(t.GetWidth(pcbnew.F_Cu)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); n = v
        else:
            n = pcbnew.PCB_TRACK(new); n.SetStart(t.GetStart()); n.SetEnd(t.GetEnd()); n.SetWidth(t.GetWidth()); n.SetLayer(t.GetLayer())
        n.SetNet(net); new.Add(n); copied += 1
    inp = os.path.join(od, f"PF233-RF2-{name}_resume.kicad_pcb"); new.Save(inp)
    widen_floor(inp, B.get("floor", FLOOR)); bad = drc_bad_uuids(inp, B)
    bd = pcbnew.LoadBoard(inp); deleted = 0
    for t in list(bd.GetTracks()):
        if t.m_Uuid.AsString() in bad and not t.IsLocked(): bd.Delete(t); deleted += 1
    bd.Save(inp)
    return inp, dict(copied_items=copied, changed_pads=len(ch), changed_nets=sorted({c[0] for c in ch}), deleted_drc_items=deleted)
def run(name):
    B = NL.BOARDS[name]; res = dict(board=name)
    bad = placement_check(B); res["placement"] = dict(overlaps_or_outside=bad, ok=not bad)
    if bad: return res
    raw, od = build(name); pcb = os.path.join(od, f"PF233-RF2-{name}.kicad_pcb")
    open(os.path.join(od, f"PF233-RF2-{name}.kicad_dru"), "w").write(dru(B))          # the same rules for KiCad's GUI / CAM review as for the DRC here
    inp, why = resume_input(name, raw, pcb, B, od); mode = "resume" if inp else "full"
    cmd = [sys.executable, os.path.join(ROOT, "src/pcb/freeroute.py"), inp or raw, pcb] + ([] if (inp or B.get("preroute")) else ["--strip"]) + (["--no-fanout"] if inp else []) + ["--no-neckdown", "--rules", B.get("rules", RULES), "--passes", "150", "--report", os.path.join(od, "freeroute.json")]
    hv = [n for n in B.get("hv_nets", []) if n not in B.get("wide", {})]
    if hv: cmd += ["--hv", ",".join(hv)] + (["--hv-clear", str(B["hv_route_clear"])] if B.get("hv_route_clear") else [])   # router-side margin (Freerouting grid rounding: 0.998 vs 1.0); DRC keeps 1.0
    if B.get("wide"): cmd += ["--class", "PULSE:2.5:1.0:" + ",".join(B["wide"])]
    done = False
    pre = kicad_drc(inp or raw, B)                                         # nothing open after the pre-routes / template / resumed copper: no autorouter run at all
    if pre["unconnected"] == 0 and pre["errors"] == 0:
        import pcbnew
        shutil.copy(inp or raw, pcb); bd = pcbnew.LoadBoard(pcb); tr = list(bd.GetTracks())
        json.dump(dict(unconnected_after=0, tracks=sum(t.GetClass() == "PCB_TRACK" for t in tr), vias=sum(t.GetClass() == "PCB_VIA" for t in tr), skipped="nothing open: template / pre-routes complete"),
                  open(os.path.join(od, "freeroute.json"), "w"), indent=1); mode = (mode + ", complete: no autorouter") if inp else "template (no autorouter)"
        if inp: os.remove(inp); inp = None
        r = None; done = True
    strategies = [dict(name="template / pre-routes / resumed copper", open=pre["unconnected"], drc_errors=pre["errors"], used=done)]
    if not done:
        # strategy chain (AXE2): Freerouting with a stall watchdog, then the A* fallback router on whatever is still open
        stall = int(B.get("stall_s", STALL_S)); fr_json = os.path.join(od, "freeroute.json")
        if os.path.exists(fr_json): os.remove(fr_json)
        r = subprocess.run(cmd + ["--stall", str(stall)], capture_output=True, text=True, timeout=2400)
        frr = json.load(open(fr_json)) if os.path.exists(fr_json) else dict(stalled=True, reason=(r.stderr or r.stdout)[-200:])
        strategies.append(dict(name="freerouting", stalled=bool(frr.get("stalled")), reason=frr.get("reason"), open=frr.get("unconnected_after"), seconds=frr.get("seconds")))
        if not os.path.exists(pcb) or frr.get("stalled") or frr.get("unconnected_after", 1) > 0:
            base = pcb if os.path.exists(pcb) and not frr.get("stalled") else (inp or raw)
            tw, cl, vd, vh = (float(x) for x in B.get("rules", RULES).split(","))
            acmd = [sys.executable, os.path.join(ROOT, "src/pcb/astar_route.py"), base, pcb, "--track", str(tw), "--clear", str(cl), "--via", f"{vd},{vh}",
                    "--edge", str(EDGE), "--report", os.path.join(od, "astar.json")] + (["--hv", ",".join(B.get("hv_nets", []))] if B.get("hv_nets") else []) + (["--hv-clear", str(B["hv_route_clear"])] if B.get("hv_nets") and B.get("hv_route_clear") else [])
            ra = subprocess.run(acmd, capture_output=True, text=True, timeout=3600)
            ar = json.load(open(os.path.join(od, "astar.json"))) if os.path.exists(os.path.join(od, "astar.json")) else dict(open_after=["?"], err=ra.stderr[-200:])
            strategies.append(dict(name="astar fallback", open_after=ar.get("open_after"), connections=len(ar.get("connections", [])), seconds=ar.get("seconds")))
            import pcbnew
            bd = pcbnew.LoadBoard(pcb); tr = list(bd.GetTracks())
            json.dump(dict(unconnected_after=len(ar.get("open_after", ["?"])), tracks=sum(t.GetClass() == "PCB_TRACK" for t in tr), vias=sum(t.GetClass() == "PCB_VIA" for t in tr),
                           via="astar fallback"), open(fr_json, "w"), indent=1); mode += " + astar"
    if not os.path.exists(pcb): res["route"] = dict(ok=False, err=(r.stdout[-300:] + r.stderr[-300:]) if r else "no board", strategies=strategies); return res
    widened = widen_floor(pcb, B.get("floor", FLOOR))
    fr = json.load(open(os.path.join(od, "freeroute.json"))); res["route"] = dict(unconnected_after=fr["unconnected_after"], tracks=fr["tracks"], vias=fr["vias"], widened_to_floor=widened, mode=mode, resume=why,
                                                                               strategies=strategies, ok=fr["unconnected_after"] == 0)
    res["kicad_drc"] = kicad_drc(pcb, B); res["kicad_drc"]["ok"] = res["kicad_drc"]["errors"] == 0 and res["kicad_drc"]["unconnected"] == 0 and (res["kicad_drc"]["hv_rule_control_violations"] in (None,) or res["kicad_drc"]["hv_rule_control_violations"] > 0)
    res["copper"] = copper_check(pcb, B); res["parity"] = parity(pcb, B)
    g = os.path.join(od, "gerber"); os.makedirs(g, exist_ok=True)
    lay = "F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,Edge.Cuts" if B["layers"] == 2 else "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,Edge.Cuts"
    a = subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--layers", lay, "--no-protel-ext", "-o", g + "/", pcb], capture_output=True, text=True)
    dd = subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th", "-o", g + "/", pcb], capture_output=True, text=True)
    res["gerbers"] = dict(files=sorted(os.listdir(g)), ok=a.returncode == 0 and dd.returncode == 0)
    hd = B["head"]; t = B["thickness"]
    if hd.get("fin"):                                                      # fin board: x along the radius at azimuth deg, y up from z0 + h / 2, thickness across the fin
        f = hd["fin"]; ca, sa = math.cos(math.radians(f["deg"])), math.sin(math.radians(f["deg"]))
        res["placement_in_head"] = [dict(ref=p["ref"], type=p["type"], x=round((f["r_center"] + p["x"]) * ca, 3), y=round((f["r_center"] + p["x"]) * sa, 3), rot=p["rot"],
                                         z=round(f["z0"] + B["h"] / 2 + p["y"], 3), body=NL.LIB[p["type"]]["body"], fin_deg=f["deg"]) for p in B["parts"]]
    else: res["placement_in_head"] = [dict(ref=p["ref"], type=p["type"], x=round(hd["c"][0] + p["x"], 3), y=round(hd["c"][1] + p["y"], 3), rot=p["rot"],
                                     z=round(hd["z_bottom"] + t, 3), body=NL.LIB[p["type"]]["body"]) for p in B["parts"]]
    res["ok"] = all(res[k]["ok"] for k in ("placement", "route", "kicad_drc", "copper", "parity", "gerbers"))
    os.remove(raw)
    if inp: os.remove(inp)
    json.dump(res, open(os.path.join(od, f"{name.lower()}_check.json"), "w"), indent=1); return res
if __name__ == "__main__":
    names = sys.argv[1:] or ["TXJ", "MP1", "LR1"]; allres = {}
    p = os.path.join(OUTB, "rf2_boards.json")
    if os.path.exists(p): allres = json.load(open(p))
    for n in names:
        r = run(n); allres[n] = r
        print(n, json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk in ("ok", "mode", "resume", "errors", "unconnected", "unconnected_after", "min_clearance_mm", "min_hv_clearance_mm", "overlaps_or_outside", "mismatches", "error_types", "hv_rule_control_violations", "examples", "err")}) for k, v in r.items() if k != "placement_in_head"})[:1500], flush=True)
    json.dump(allres, open(p, "w"), indent=1)
