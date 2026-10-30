#!/usr/bin/env python3
"""LR1 dense LED display (owner 2026-10-30: rings from the rim to the centre, tightly packed, a centre cluster, 400+ LEDs; chosen: about 540 on an 8 mm
grid). Single source for the flex's outline, every part, every net and every track / via: rf2_netlist builds LR1 from parts() / nets(), rf2_boards draws
copper() as locked tracks (no autorouter), rf2_head takes outline() / sites() for the envelope. MODELED; routed and checked like every RF2 board.

Layout, in the spine frame (x' along the heel axis HEEL = 178 deg, y' to its left; global = rotate(x', y') by HEEL):
  rings     LED circles r 104, 96, ..., 16 (8 mm apart) and r 8 (the centre cluster); LEDs about 8 mm apart around each ring, SK9822-EC20 + 100 nF 0402
  spine     an LED-free strip along the heel axis (|y'| < 10 for x' >= 10, |y'| < 3 for 1 < x' < 10): the power spokes, the chain feeds and the
            ring-to-ring jumps run here; every bus ends at it (rule 5: no closed loop around the axis)
  buses     B.Cu arcs midway between rings (r 108, 100, ..., 4), alternating GND / +5V_LED: a ring running CCW takes GND from its outer bus and +5V from its
            inner bus; the rings alternate CCW / CW (cells turned 180 deg), so each bus serves the ring on each side
  spokes    B.Cu, one per net (GND on the -y' side, +5V on the +y' side), joined to each bus at one end only: the power net is a tree
  hinge     a flap cut out of the spine above CB1D (x' 20-34, |y'| <= 4.5, slit 0.5 mm), root at x' 34; 12 lands (4 power, 8 signal) at its tip
  chains    4 serial chains (SDI / CKI in, SDO / CKO out), each a serpentine over neighbouring rings: C1 r 32 -> 8, C2 r 40 -> 56, C3 r 64 -> 80, C4 r 88 -> 104
  gland     the flex has a notch (|y'| < 7 for x' > 84.5) around the lid's gland boss (r 92, D12)
  holes     6 mounting holes D2.0 at r 110.8 (lid bosses)
Cell (in the LED's own frame u radial out, s along its ring's chain direction; pads 1 SDO u+0.86 s-0.68 | 2 GND u0 s-0.68 | 3 SDI u-0.86 s-0.68 |
4 CKI u-0.86 s+0.68 | 5 VDD u0 s+0.68 | 6 CKO u+0.86 s+0.68; capacitor at u-2.8, +5V pin s+0.51): data out pad 1 -> u+1.5 -> diagonal to u-0.86 of the
next LED -> pad 3; clock pad 6 -> u+0.86 -> diagonal to u-1.5 -> pad 4 (parallel lanes, no crossing); GND pad 2 and the capacitor's GND -> vias at
s-1.4 -> B.Cu radial to the outer bus (u+4); +5V pad 5 and the capacitor's +5V -> vias at s+1.4 -> B.Cu radial to the inner bus (u-4)."""
import math
HEEL = 178.0
R_OUT, PITCH, RINGS = 113.0, 8.0, [104.0 - 8.0 * k for k in range(12)] + [8.0]
W_SIG, W_PWR, W_BUS, W_FEED, VIA_D, VIA_DR = 0.15, 0.3, 1.0, 0.1, 0.45, 0.2
X1 = 21.2                                                                           # hinge land rows: power x' 21.2, signals 23.2 / 25.2
U_DATA_OUT, U_CLK_OUT, U_DATA_IN, U_CLK_IN, S_LANE, U_CAP, S_PWR, U_BUS = 1.5, 0.86, -0.86, -1.5, 2.6, -2.8, 1.4, 4.0
LED_MARGIN, BUS_MARGIN = 3.5, 0.5
FLAP = dict(x=(20.0, 34.0), half=4.5, slit=0.5)
NOTCH = dict(x0=84.5, half=7.0)
HOLES = [(110.8, 30.0 + 60.0 * k, 2.0) for k in range(6)]
CHAINS = [[32.0, 24.0, 16.0, 8.0], [40.0, 48.0, 56.0], [64.0, 72.0, 80.0], [88.0, 96.0, 104.0]]
# ------------------------------------------------------------------------------------------------ frames
def to_g(xl, yl):
    c, s = math.cos(math.radians(HEEL)), math.sin(math.radians(HEEL)); return (xl * c - yl * s, xl * s + yl * c)
def to_l(x, y):
    c, s = math.cos(math.radians(HEEL)), math.sin(math.radians(HEEL)); return (x * c + y * s, -x * s + y * c)
def W(xl): return 3.0 if xl < 10.0 else 10.0
def excl(xl, yl, pad): return xl > 1.0 and abs(yl) < W(xl) + pad
def ring_dir(R): return 1 if round((104.0 - R) / 8.0) % 2 == 0 else -1          # r 104 CCW, r 96 CW, ... (r 8 CCW)
def alpha0(R, pad):
    """first local angle (deg from the heel axis) at radius R outside the spine (excluded region with pad)"""
    a = 0.0
    while a < 180.0:
        xl, yl = R * math.cos(math.radians(a)), R * math.sin(math.radians(a))
        if not excl(xl, yl, pad): return a
        a += 0.01
    return None
def ring_leds(R):
    """local angles of the LEDs on ring R, in chain order"""
    a0 = alpha0(R, LED_MARGIN); span = 360.0 - 2 * a0; n = int(math.floor(math.radians(span) * R / PITCH))
    if R == 8.0: n = 4
    al = [a0 + (i + 0.5) * span / n for i in range(n)]
    return al if ring_dir(R) == 1 else al[::-1]
def cell_xy(R, a_loc, d, u, s):
    """a point of the cell of the LED at ring R, local angle a_loc, chain direction d, in the cell's own frame (u, s) -> global (x, y)"""
    th = math.radians(HEEL + a_loc) + d * s / R; r = R + d * u; return (r * math.cos(th), r * math.sin(th))
def cell_path(R, a_loc, d, pts, per_mm=1.0):
    out = []
    for (u0, s0), (u1, s1) in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil(math.hypot(u1 - u0, s1 - s0) * per_mm))); out += [(u0 + (u1 - u0) * k / n, s0 + (s1 - s0) * k / n) for k in range(n)]
    out.append(pts[-1]); return [cell_xy(R, a_loc, d, u, s) for u, s in out]
def arc_g(r, a0g, a1g, per_mm=1.0):
    n = max(2, int(math.ceil(abs(math.radians(a1g - a0g)) * r * per_mm)) + 1)
    return [(r * math.cos(math.radians(a0g + (a1g - a0g) * k / (n - 1))), r * math.sin(math.radians(a0g + (a1g - a0g) * k / (n - 1)))) for k in range(n)]
def lpath(pts):
    """polyline in the spine frame -> global"""
    return [to_g(x, y) for x, y in pts]
# ------------------------------------------------------------------------------------------------ parts and nets
def layout():
    """LED / capacitor placement and the chain nets. Returns dict(leds=[...], chains=[...])"""
    leds, chains, n = [], [], 0
    for c, rings in enumerate(CHAINS, 1):
        seq = []
        for R in rings:
            d = ring_dir(R)
            for a in ring_leds(R):
                n += 1; x, y = cell_xy(R, a, d, 0, 0); ag = HEEL + a
                cx, cy = cell_xy(R, a, d, U_CAP, 0)
                leds.append(dict(ref=f"LD{n}", cap=f"CD{n}", R=R, a=a, d=d, chain=c, x=x, y=y, rot=(ag + 90.0) if d == 1 else (ag + 270.0),
                                 cx=cx, cy=cy, crot=(ag + 270.0) if d == 1 else (ag + 90.0)))
                seq.append(n)
        chains.append(seq)
    return dict(leds=leds, chains=chains)
LANDS_Y = dict(power=[("GND", -1.5), ("GND", -0.5), ("+5V_LED", 0.5), ("+5V_LED", 1.5)])
def nets_and_lands():
    """net per LED pin and the 12 hinge lands (net names follow the feed routing: see feeds())"""
    L = layout(); pins = {}
    for c, seq in enumerate(L["chains"], 1):
        for j, n in enumerate(seq):
            pins[(f"LD{n}", "3")] = f"C{c}_D{j}"; pins[(f"LD{n}", "4")] = f"C{c}_K{j}"
            pins[(f"LD{n}", "1")] = f"C{c}_D{j + 1}"; pins[(f"LD{n}", "6")] = f"C{c}_K{j + 1}"
            pins[(f"LD{n}", "2")] = "GND"; pins[(f"LD{n}", "5")] = "+5V_LED"; pins[(f"CD{n}", "1")] = "+5V_LED"; pins[(f"CD{n}", "2")] = "GND"
    lands = [(f"JH{k + 1}", net, X1, y) for k, (net, y) in enumerate(LANDS_Y["power"])]
    for k, (net, row, y) in enumerate(feeds()[2]): lands.append((f"JH{5 + k}", net, row, y))
    return pins, lands
# ------------------------------------------------------------------------------------------------ outline
def outline():
    """board outline: (exterior ring, [interior rings]) in global mm; holes separate (HOLES)"""
    from shapely.geometry import Point, Polygon, box
    from shapely import affinity
    o = Point(0, 0).buffer(R_OUT, 512)
    notch = affinity.rotate(box(NOTCH["x0"], -NOTCH["half"], R_OUT + 5, NOTCH["half"]), HEEL, origin=(0, 0))
    x0, x1 = FLAP["x"]; h, t = FLAP["half"], FLAP["slit"]
    slit = box(x0 - t, -h - t, x1, h + t).difference(box(x0, -h, x1 + 1, h))
    o = o.difference(notch).difference(affinity.rotate(slit, HEEL, origin=(0, 0)))
    return o
# ------------------------------------------------------------------------------------------------ copper
def ends(R, first):
    """the two lane end points (local spine frame) at the spine side of ring R: incoming (first LED) or outgoing (last LED); returns {net-kind: (x', y')}"""
    al = ring_leds(R); d = ring_dir(R)
    if first: pts = dict(D=cell_xy(R, al[0], d, U_DATA_IN, -S_LANE), K=cell_xy(R, al[0], d, U_CLK_IN, -S_LANE))
    else: pts = dict(D=cell_xy(R, al[-1], d, U_DATA_OUT, S_LANE), K=cell_xy(R, al[-1], d, U_CLK_OUT, S_LANE))
    return {k: to_l(*v) for k, v in pts.items()}
def feeds():
    """hinge feeds as local polylines: (tracks [(net, layer, local pts, width)], vias [(net, local pt)], land assignment [(net, row x', y')])"""
    T, V, lands = [], [], []
    lane = dict(r2a=2.4, r2b=3.4, r3a=2.4, r3b=3.4)                                  # row 2 (x' 25.2) and row 3 (x' 27.2) land y (|y'|)
    X2, X3 = 23.2, 25.2
    L = layout(); start = {c: L["chains"][c - 1][0] for c in range(1, 5)}
    def flap_lane(sig, which):
        """flap lane |y| after row 3: 1.9 (row 2 land 2.4), 2.4 (row 3 land 2.4), 2.9 (row 2 land 3.4), 3.4 (row 3 land 3.4) -> (land x', land |y|, pts)"""
        if which == 1.9: return X2, 2.4, [(X2, 2.4), (X2 + 0.8, 2.4), (X2 + 1.1, 1.95)]
        if which == 2.4: return X3, 2.4, [(X3, 2.4)]
        if which == 2.9: return X2, 3.4, [(X2, 3.4), (X2 + 0.8, 3.4), (X2 + 1.1, 2.9)]
        return X3, 3.4, [(X3, 3.4)]
    def assign(endpts, outer_first_small_x):
        """map the two chain nets to (outer, inner) lane by the no-crossing rule"""
        (ka, pa), (kb, pb) = endpts.items()
        small = ka if pa[0] < pb[0] else kb; big = kb if small == ka else ka
        return (small, big) if outer_first_small_x else (big, small)
    plan = {   # chain: (side, flap lanes (outer, inner), first jog (x' outer, x' inner), pair |y| (outer, inner), heading)
        1: (-1, (2.9, 3.4), (34.95, 34.6), (6.3, 5.95), -1),
        3: (-1, (2.4, 1.9), (35.6, 35.95), (7.0, 6.65), +1),
        2: (+1, (3.4, 2.9), (34.6, 34.95), (7.0, 6.65), +1),
        4: (+1, (2.4, 1.9), (35.6, 35.95), (6.3, 5.95), +1)}
    c2_far = max(p[0] for p in ends(CHAINS[1][0], True).values())
    for c, (sg, fl, jx, py, hd) in plan.items():
        E = ends(CHAINS[c - 1][0], True)
        outer, inner = assign(E, hd == +1)
        for kind, fly, jxx, pyy in ((outer, fl[0], jx[0], py[0]), (inner, fl[1], jx[1], py[1])):
            net = f"C{c}_{kind}0"; ex, ey = E[kind]
            lx, ly, fpts = flap_lane(sg, fly); lands.append((net, lx, sg * ly))
            flane = 1.95 if fly == 1.9 else fly
            pts = [(x, sg * y) for x, y in fpts] + [(jxx, sg * flane), (jxx, sg * pyy)]
            if c == 4:                                                              # second jog after C2 has left, to clear the gland notch (>= 7.5)
                j2 = max(c2_far, 36.5) + (1.0 if kind == outer else 1.35); y2 = 8.75 if kind == outer else 8.4
                pts += [(j2, sg * pyy), (j2, sg * y2), (ex, sg * y2)]
            else: pts += [(ex, sg * pyy)]
            pts += [(ex, ey)]
            T.append((net, "F", pts, W_FEED))
    for net, y in LANDS_Y["power"]:                                                 # power: row 1 -> along the flap -> vias past the feed turns -> B.Cu to the spoke
        sg = 1 if y > 0 else -1
        T.append((net, "F", [(X1, y), (37.5, y)], 0.4)); V.append((net, (37.5, y))); T.append((net, "B", [(37.5, y), (37.5, sg * 7.05)], 0.8))
    return T, V, lands
SPOKE = {+1: [((2.5, 1.5), (13.0, 1.5), 2.0), ((13.0, 1.5), (14.0, 7.05), 2.0), ((14.0, 7.05), (81.0, 7.05), 2.9), ((81.0, 7.05), (82.5, 8.2), 1.2),
              ((82.5, 8.2), (107.0, 8.2), 1.2)],
         -1: [((11.0, -7.05), (81.0, -7.05), 2.9), ((81.0, -7.05), (82.5, -8.2), 1.2), ((82.5, -8.2), (107.0, -8.2), 1.2)]}
def bus_net(m): return "GND" if round((108.0 - m) / 8.0) % 2 == 0 else "+5V_LED"     # r 108 GND, r 100 +5V, ...
def copper():
    """every track and via of LR1: (tracks [(net, 'F'|'B', [(x, y) global], width)], vias [(net, (x, y))], nets covered)"""
    from shapely.geometry import LineString, Point
    from shapely.ops import nearest_points
    T, V = [], []
    def seg(net, lay, pts, w): T.append((net, lay, pts, w))
    def via(net, p): V.append((net, p))
    L = layout(); pins, _ = nets_and_lands(); covered = set(pins.values())
    by_ring = {}
    for e in L["leds"]: by_ring.setdefault(e["R"], []).append(e)
    for R, es in by_ring.items():
        for e in es:                                                                # the cell's power stubs
            a, d = e["a"], e["d"]
            seg("GND", "F", cell_path(R, a, d, [(0, -0.68), (0, -S_PWR)]), W_PWR); via("GND", cell_xy(R, a, d, 0, -S_PWR))
            seg("GND", "F", cell_path(R, a, d, [(U_CAP, -0.51), (U_CAP, -S_PWR)]), W_PWR); via("GND", cell_xy(R, a, d, U_CAP, -S_PWR))
            seg("+5V_LED", "F", cell_path(R, a, d, [(0, 0.68), (0, S_PWR)]), W_PWR); via("+5V_LED", cell_xy(R, a, d, 0, S_PWR))
            seg("+5V_LED", "F", cell_path(R, a, d, [(U_CAP, 0.51), (U_CAP, S_PWR)]), W_PWR); via("+5V_LED", cell_xy(R, a, d, U_CAP, S_PWR))
            seg("GND", "B", cell_path(R, a, d, [(U_CAP, -S_PWR), (U_BUS, -S_PWR)]), W_PWR)
            seg("+5V_LED", "B", cell_path(R, a, d, [(0, S_PWR), (-U_BUS, S_PWR)]), W_PWR)
        for e0, e1 in zip(es[:-1], es[1:]):                                         # links inside the ring
            d = e0["d"]; ds = math.radians(abs(e1["a"] - e0["a"])) * R; dn, kn = pins[(e0["ref"], "1")], pins[(e0["ref"], "6")]
            seg(dn, "F", cell_path(R, e0["a"], d, [(0.86, -0.68), (U_DATA_OUT, -0.68), (U_DATA_OUT, S_LANE), (U_DATA_IN, ds - S_LANE), (-0.86, ds - 0.68)]), W_SIG)
            seg(kn, "F", cell_path(R, e0["a"], d, [(0.86, 0.68), (U_CLK_OUT, S_LANE), (U_CLK_IN, ds - S_LANE), (U_CLK_IN, ds + 0.68), (-0.86, ds + 0.68)]), W_SIG)
    # ring-end stubs: incoming lanes of every first LED, outgoing lanes of every last LED that has a successor
    for c, rings in enumerate(CHAINS, 1):
        for i, R in enumerate(rings):
            es = by_ring[R]; f, l = es[0], es[-1]
            seg(pins[(f["ref"], "3")], "F", cell_path(R, f["a"], f["d"], [(U_DATA_IN, -S_LANE), (-0.86, -0.68)]), W_SIG)
            seg(pins[(f["ref"], "4")], "F", cell_path(R, f["a"], f["d"], [(U_CLK_IN, -S_LANE), (U_CLK_IN, 0.68), (-0.86, 0.68)]), W_SIG)
            if i + 1 < len(rings):
                seg(pins[(l["ref"], "1")], "F", cell_path(R, l["a"], l["d"], [(0.86, -0.68), (U_DATA_OUT, -0.68), (U_DATA_OUT, S_LANE)]), W_SIG)
                seg(pins[(l["ref"], "6")], "F", cell_path(R, l["a"], l["d"], [(0.86, 0.68), (U_CLK_OUT, S_LANE)]), W_SIG)
                # jump to the next ring: a polar U-turn through the spine side (no crossing). Each lane follows its own ring's lane radius towards
                # the axis, turns radially, and comes back along the next ring's lane radius; the exterior lane turns nearer the axis.
                P, Q = ends(R, False), ends(rings[i + 1], True)
                pol = lambda p: (math.hypot(*p), abs(math.degrees(math.atan2(p[1], p[0]))))
                sg = 1 if P["D"][1] > 0 else -1; inward = pol(Q["D"])[0] < pol(P["D"])[0]
                rmin = min(pol(p)[0] for p in (P["D"], P["K"], Q["D"], Q["K"]))
                bint = min(pol(p)[1] for p in (P["D"], P["K"], Q["D"], Q["K"])) - math.degrees(0.6 / rmin)
                bext = bint - math.degrees(0.45 / rmin)
                ext = max(("D", "K"), key=lambda k: pol(P[k])[0]) if inward else min(("D", "K"), key=lambda k: pol(P[k])[0])
                for k in ("D", "K"):
                    (rp, bp), (rq, bq) = pol(P[k]), pol(Q[k]); bs = bext if k == ext else bint; net = pins[(l["ref"], "1" if k == "D" else "6")]
                    ga = lambda b: HEEL + sg * b
                    pts = arc_g(rp, ga(bp), ga(bs)) + arc_g(rq, ga(bs), ga(bq))
                    seg(net, "F", [to_g(*P[k])] + pts + [to_g(*Q[k])], W_SIG)
    # hinge feeds and power taps
    FT, FV, _ = feeds()
    for net, lay, pts, w in FT: seg(net, lay, lpath(pts), w)
    for net, p in FV: via(net, to_g(*p))
    # spokes (B.Cu) and buses (B.Cu arcs between the rings, open at the spine; the spoke-side end is extended to the spoke)
    sp_line = {}
    for sg, segs in SPOKE.items():
        net = "+5V_LED" if sg > 0 else "GND"
        for p0, p1, w in segs: seg(net, "B", lpath([p0, p1]), w)
        sp_line[sg] = LineString([to_g(*p0) for p0, _, _ in segs] + [to_g(*segs[-1][1])])
    for m in [108.0 - 8.0 * k for k in range(14)]:
        net = bus_net(m); a0 = alpha0(m, BUS_MARGIN)
        seg(net, "B", arc_g(m, HEEL + a0, HEEL + 360.0 - a0), W_BUS)
        sg = 1 if net == "+5V_LED" else -1; eg = (m * math.cos(math.radians(HEEL + sg * a0)), m * math.sin(math.radians(HEEL + sg * a0)))
        _, q = nearest_points(Point(eg), sp_line[sg]); seg(net, "B", [eg, (q.x, q.y)], W_BUS)
    return T, V, covered
def summary():
    L = layout(); per = {R: len(ring_leds(R)) for R in RINGS}
    ch = [len(s) for s in L["chains"]]
    return dict(leds=len(L["leds"]), per_ring=per, chain_lengths=ch, holes=HOLES)
def figure(path):
    """plan view of the display flex: outline, F.Cu (red), B.Cu (blue), vias, LED sites; one figure for the layout decision"""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    T, V, _ = copper(); o = outline(); sm = summary()
    fig, ax = plt.subplots(figsize=(12, 12))
    for ring in [o.exterior] + list(o.interiors): x, y = ring.xy; ax.plot(x, y, "k", lw=0.5)
    for r, a, d in HOLES: ax.add_patch(plt.Circle((r * math.cos(math.radians(a)), r * math.sin(math.radians(a))), d / 2, fill=False, lw=0.5))
    for net, lay, pts, w in T:
        xs, ys = zip(*pts); ax.plot(xs, ys, color="#c0392b" if lay == "F" else "#2471a3", lw=max(0.25, w * 1.1), alpha=0.85 if lay == "F" else 0.45, solid_capstyle="round")
    L = layout()
    ax.scatter([e["x"] for e in L["leds"]], [e["y"] for e in L["leds"]], s=6, marker="s", c="#f4d03f", edgecolors="k", linewidths=0.2, zorder=3)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"RF2 LR1 display flex (MODELED, template-routed): {sm['leds']} SK9822-EC20 in {len(RINGS)} rings, chains {sm['chain_lengths']}; "
                 "F.Cu red, B.Cu blue (open buses + spokes)", loc="left", fontsize=9)
    fig.savefig(path, dpi=130, bbox_inches="tight"); plt.close(fig)
if __name__ == "__main__":
    import json, os; print(json.dumps(summary(), indent=1))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(out, exist_ok=True); figure(os.path.join(out, "rf2_display.png"))
