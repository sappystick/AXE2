#!/usr/bin/env python3
"""LR1 LED ring: deterministic template routing (2026-10-30). Freerouting stalls on this board (hundreds of identical fine-pitch cells on a 0.10 mm flex), so the
regular copper is drawn here: one cell per LED, the same in every cell, written in the LED's own polar frame (u radial offset from the LED circle, s arc
length along it, CCW positive) and placed at every LED; every chain link between neighbours on the same circle; every LED and capacitor power stub down
to the open bus arcs (B.Cu); and the four irregular connections (feeds() below: the hinge feeds JH3 / JH4 -> LD1 and the outer-to-inner jump LD36 -> LD37),
which Freerouting could not finish on this board (2026-10-30: no pass completed in 5 min for 4 connections). Nothing is left for an autorouter.
Cell (SK9822-EC20 pads: 1 SDO u+0.86 s-0.68 | 2 GND u0 s-0.68 | 3 SDI u-0.86 s-0.68 | 4 CKI u-0.86 s+0.68 | 5 VDD u0 s+0.68 | 6 CKO u+0.86 s+0.68;
capacitor at u-2.8, +5V pin s+0.51, GND pin s-0.51):
  data   pad 1 -> u+1.5 -> along s past the LED -> diagonal to u-0.86 of the next LED -> pad 3      (outer lane)
  clock  pad 6 -> along s at u+0.86 -> diagonal to u-1.5 of the next LED -> s+0.68 -> pad 4      (inner lane, parallel to data: no crossing)
  GND    pad 2 -> via (0, -1.4); capacitor GND -> via (-2.8, -1.4); B.Cu radial from -2.8 to the GND bus (u+3.5)
  +5V    pad 5 -> via (0, +1.4); capacitor +5V -> via (-2.8, +1.4); B.Cu radial to a via at u+2.8; F.Cu jump over the GND bus to a via on the +5V bus (u+5.5)
A chain link that crosses a radial F.Cu hinge feed (185 / 195 deg) makes its diagonal on B.Cu (two vias each end). Where a bus has its gap (rule 5:
GND 185-195 deg, +5V 175-185 deg) the cell's stub ends are joined to the bus end with a short B.Cu arc, so the buses stay open C shapes.
Geometry rules checked downstream by KiCad DRC, the independent copper check (incl. no loop around the axis) and parity (rf2_boards)."""
import math
W_SIG, W_PWR, VIA_D, VIA_DR = 0.15, 0.3, 0.45, 0.2
U_DATA_OUT, U_CLK_OUT, U_DATA_IN, U_CLK_IN, S_LANE = 1.5, 0.86, -0.86, -1.5, 2.6
U_GND_BUS, U_PWR_BUS, U_JUMP, U_CAP, S_PWR = 3.5, 5.5, 2.8, -2.8, 1.4
def xy(R, a_deg, u, s):
    """point at radial offset u and arc offset s from the LED at radius R, angle a"""
    th = math.radians(a_deg) + s / R; return ((R + u) * math.cos(th), (R + u) * math.sin(th))
def ang(R, a_deg, s): return (a_deg + math.degrees(s / R)) % 360
def path(R, a, pts, n_per_mm=1.0):
    """polyline through (u, s) points, subdivided so each piece follows the circle (chord error < 0.01 mm)"""
    out = []
    for (u0, s0), (u1, s1) in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil(math.hypot(u1 - u0, s1 - s0) * n_per_mm)))
        out += [(u0 + (u1 - u0) * k / n, s0 + (s1 - s0) * k / n) for k in range(n)]
    out.append(pts[-1]); return [xy(R, a, u, s) for u, s in out]
def in_gap(a, lo, hi): return (a - lo) % 360 < (hi - lo) % 360
def route(leds, feeds=(185.0, 195.0), gnd_gap=(185.0, 195.0), pwr_gap=(175.0, 185.0)):
    """leds: list of (ref index 1.., radius, angle) in chain order; returns (tracks, vias, nets_covered).
    tracks: (net, layer 'F'|'B', [(x, y), ...], width); vias: (net, (x, y))"""
    T, V = [], []
    def seg(net, lay, pts, w): T.append((net, lay, pts, w))
    def via(net, R, a, u, s): V.append((net, xy(R, a, u, s)))
    covered = {"GND", "+5V_LED"}
    by_r = {}
    for i, R, a in leds: by_r.setdefault(R, []).append((i, a))
    for i, R, a in leds:
        # power stubs of the cell
        seg("GND", "F", path(R, a, [(0, -0.68), (0, -S_PWR)]), W_PWR); via("GND", R, a, 0, -S_PWR)
        seg("GND", "F", path(R, a, [(U_CAP, -0.51), (U_CAP, -S_PWR)]), W_PWR); via("GND", R, a, U_CAP, -S_PWR)
        seg("+5V_LED", "F", path(R, a, [(0, 0.68), (0, S_PWR)]), W_PWR); via("+5V_LED", R, a, 0, S_PWR)
        seg("+5V_LED", "F", path(R, a, [(U_CAP, 0.51), (U_CAP, S_PWR)]), W_PWR); via("+5V_LED", R, a, U_CAP, S_PWR)
        seg("GND", "B", path(R, a, [(U_CAP, -S_PWR), (U_GND_BUS, -S_PWR)]), W_PWR)
        seg("+5V_LED", "B", path(R, a, [(U_CAP, S_PWR), (U_JUMP, S_PWR)]), W_PWR); via("+5V_LED", R, a, U_JUMP, S_PWR)
        seg("+5V_LED", "F", path(R, a, [(U_JUMP, S_PWR), (U_PWR_BUS, S_PWR)]), W_PWR); via("+5V_LED", R, a, U_PWR_BUS, S_PWR)
        # bus gaps: join the stub end to the bus end along the bus radius (B.Cu), on the side away from the gap
        for net, u, s, (lo, hi) in (("GND", U_GND_BUS, -S_PWR, gnd_gap), ("+5V_LED", U_PWR_BUS, S_PWR, pwr_gap)):
            at = ang(R, a, s)
            if in_gap(at, lo, hi):
                end = hi if (hi - at) % 360 < (at - lo) % 360 else lo                    # nearer bus end
                ds = math.radians(((end - at + 180) % 360) - 180) * (R + u)
                seg(net, "B", path(R + u, at, [(0, 0), (0, ds)]), W_PWR)
    # chain links between neighbours on the same circle
    order = [i for i, _, _ in leds]; pos = {i: (R, a) for i, R, a in leds}
    for i, j in zip(order[:-1], order[1:]):
        (R, a), (R2, a2) = pos[i], pos[j]
        if R != R2: continue                                                              # the outer -> inner jump is left to the router
        ds = math.radians((a2 - a) % 360) * R; d_net, c_net = f"LED_D{i}", f"LED_C{i}"; covered |= {d_net, c_net}
        cross = any(in_gap(f, ang(R, a, S_LANE), ang(R, a, ds - S_LANE)) for f in feeds)
        # near ends (F.Cu)
        seg(d_net, "F", path(R, a, [(0.86, -0.68), (U_DATA_OUT, -0.68), (U_DATA_OUT, S_LANE)]), W_SIG)
        seg(c_net, "F", path(R, a, [(0.86, 0.68), (U_CLK_OUT, S_LANE)]), W_SIG)
        seg(d_net, "F", path(R, a, [(U_DATA_IN, ds - S_LANE), (-0.86, ds - 0.68)]), W_SIG)
        seg(c_net, "F", path(R, a, [(U_CLK_IN, ds - S_LANE), (U_CLK_IN, ds + 0.68), (-0.86, ds + 0.68)]), W_SIG)
        lay = "B" if cross else "F"
        seg(d_net, lay, path(R, a, [(U_DATA_OUT, S_LANE), (U_DATA_IN, ds - S_LANE)]), W_SIG)
        seg(c_net, lay, path(R, a, [(U_CLK_OUT, S_LANE), (U_CLK_IN, ds - S_LANE)]), W_SIG)
        if cross:
            for net, u0, u1 in ((d_net, U_DATA_OUT, U_DATA_IN), (c_net, U_CLK_OUT, U_CLK_IN)): via(net, R, a, u0, S_LANE); via(net, R, a, u1, ds - S_LANE)
    return T, V, covered

def polar(pts, n_per_mm=1.0):
    """polyline through (r, deg) points: equal radius -> arc along the circle, equal angle -> radial line"""
    out = []
    for (r0, t0), (r1, t1) in zip(pts[:-1], pts[1:]):
        dt = ((t1 - t0 + 180) % 360) - 180; L = math.hypot(r1 - r0, math.radians(dt) * max(r0, r1)); n = max(1, int(math.ceil(L * n_per_mm)))
        out += [(r0 + (r1 - r0) * k / n, t0 + dt * k / n) for k in range(n)]
    out.append(pts[-1]); return [(r * math.cos(math.radians(t)), r * math.sin(math.radians(t))) for r, t in out]
def feeds(R_out=62.5, a_first=0.0, a_last=350.0, R_in=22.0, a_in=30.0, jh_clk=(17.0, 205.0), jh_dat=(17.0, 215.0)):
    """the four irregular links, as (tracks, vias, nets). Lane order is kept on each layer (no crossing): planned turn by turn, see the module notes.
    Hinge feeds: JH -> F stub -> via -> B.Cu arc inside the inner ring -> B.Cu radial under the inner chain -> via (inside the inner buses) -> F.Cu radial
    -> F.Cu arc at r 57 / 57.6 (inside the outer cells) -> up into LD1's incoming lanes. Jump LD36 -> LD37: LD36's outgoing lanes -> F.Cu drop, with a
    B.Cu section where it crosses the feed arcs -> F.Cu arc at r 30.3 / 31 -> down into LD37's incoming lanes."""
    T, V = [], []
    def seg(net, lay, pts, w=W_SIG): T.append((net, lay, pts, w))
    d, c = "LED_D0", "LED_C0"
    # hinge feeds
    rc, tc = jh_clk; rd, td = jh_dat; vc, vd = tc + 4.7, td + 4.7
    seg(c, "F", polar([(rc, tc), (rc, vc)])); V.append((c, polar([(rc, vc)])[0])); seg(d, "F", polar([(rd, td), (rd, vd)])); V.append((d, polar([(rd, vd)])[0]))
    seg(c, "B", polar([(rc, vc), (16.2, vc), (16.2, 233.5), (24.6, 233.5)])); seg(d, "B", polar([(rd, vd), (17.0, 231.5), (24.6, 231.5)]))
    V += [(c, polar([(24.6, 233.5)])[0]), (d, polar([(24.6, 231.5)])[0])]
    a_in_d = a_first + math.degrees(-S_LANE / R_out)                                 # LD1 incoming lanes start (s = -2.6)
    seg(c, "F", polar([(24.6, 233.5), (57.0, 233.5), (57.0, 356.8), (R_out + U_CLK_IN, 356.8), (R_out + U_CLK_IN, a_in_d)]))
    seg(d, "F", polar([(24.6, 231.5), (57.6, 231.5), (57.6, 355.6), (R_out + U_DATA_IN, 355.6), (R_out + U_DATA_IN, a_in_d)]))
    seg(d, "F", path(R_out, a_first, [(U_DATA_IN, -S_LANE), (-0.86, -0.68)])); seg(c, "F", path(R_out, a_first, [(U_CLK_IN, -S_LANE), (U_CLK_IN, 0.68), (-0.86, 0.68)]))
    # jump LD36 -> LD37
    d, c = "LED_D36", "LED_C36"
    seg(d, "F", path(R_out, a_last, [(0.86, -0.68), (U_DATA_OUT, -0.68), (U_DATA_OUT, S_LANE)])); seg(c, "F", path(R_out, a_last, [(0.86, 0.68), (U_CLK_OUT, S_LANE)]))
    a0 = ang(R_out, a_last, S_LANE); td_, tc_ = 354.6, 353.0
    seg(d, "F", polar([(R_out + U_DATA_OUT, a0), (R_out + U_DATA_OUT, td_), (58.6, td_)])); seg(c, "F", polar([(R_out + U_CLK_OUT, a0), (R_out + U_CLK_OUT, tc_), (58.6, tc_)]))
    for net, t in ((d, td_), (c, tc_)):
        seg(net, "B", polar([(58.6, t), (55.9, t)])); V += [(net, polar([(58.6, t)])[0]), (net, polar([(55.9, t)])[0])]
    seg(d, "F", polar([(55.9, td_), (31.0, td_), (31.0, 19.6), (R_in + U_DATA_IN, 19.6)])); seg(c, "F", polar([(55.9, tc_), (30.3, tc_), (30.3, 18.0), (R_in + U_CLK_IN, 18.0)]))
    s_d = math.radians(19.6 - a_in) * R_in; s_c = math.radians(18.0 - a_in) * R_in
    seg(d, "F", path(R_in, a_in, [(U_DATA_IN, s_d), (-0.86, -0.68)])); seg(c, "F", path(R_in, a_in, [(U_CLK_IN, s_c), (U_CLK_IN, 0.68), (-0.86, 0.68)]))
    return T, V, {"LED_D0", "LED_C0", "LED_D36", "LED_C36"}
