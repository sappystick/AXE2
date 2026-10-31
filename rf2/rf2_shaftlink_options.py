#!/usr/bin/env python3
"""RF2 shaft options (owner 2026-10-31): an optical data link up the shaft and hexagonal telescope profiles with flex on the inner flats, a central
bore and long flex component boards. MODELED; an options study, nothing adopted.

Optical link: Broadcom AFBR-1624Z / AFBR-2624Z (DC-50 MBd, 650 nm, 1 mm POF; ICC 21-31 mA TX, 20-30 mA RX; delay <= 30 ns; PWD +-3 / +-4 ns;
Versatile Link housing 18.8 x 12.19 x 7.62 mm from the RS listing; data/datasheets/Broadcom_AFBR-1624Z_2624Z_AV02-4369EN.pdf) on Mitsubishi
GH-4001-P POF (2.2 mm jacket, 4 g/m, <= 170 dB/km, quarter-bend radius 25 mm at <= 1 dB, 10 000 bends +-90 deg at 15 mm;
data/datasheets/Mitsubishi_GH4001P_2019.pdf). It would replace the cord flex's three digital pairs (TXCMD, TXSTAT, DATA: rf2_cordflex LANES).
Hex profiles: the three keyed square profiles of rf2_chassis (21 / 26 / 31 mm, wall 1.2) against regular hexagons of the same across-flats and of
equal mass; sections from shapely polygons (second moment exact for straight walls, corner radii ignored); cantilever sag as rf2_shaft_options
(head + yoke at the tip, tubes' own weight, overlaps take the smaller section). E 50 GPa, 1.55 g/cm3 (ASSUMED, as rf2_shaft_options).
Writes rf2/results/rf2_shaftlink_options.json and STL sections rf2/results/shaftlink_*.stl.   usage: python3 rf2/rf2_shaftlink_options.py"""
import os, sys, json, math
import numpy as np
from shapely.geometry import Polygon
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results")
sys.path[:0] = [HERE, os.path.join(HERE, "head"), os.path.join(ROOT, "concepts")]
import rf2_cordflex as CFX
import clib as K
E_CF, RHO_CF = 50e3, 1.55e-3
POF = dict(jacket_mm=2.2, g_per_m=4.0, bend_static_mm=25.0, bend_repeated_mm=15.0, loss_db_km=170.0)
AFBR = dict(icc_tx_mA=(21, 31), icc_rx_mA=(20, 30), v=3.3, delay_ns=30, pwd_ns=4, housing_mm=(18.8, 12.19, 7.62))
DIGITAL = ("TXCMD", "TXSTAT", "DATA")

def hexagon(af, rot=0.0):
    rc = af / math.sqrt(3); return Polygon([(rc * math.cos(rot + k * math.pi / 3), rc * math.sin(rot + k * math.pi / 3)) for k in range(6)])
def square(a): return Polygon([(-a / 2, -a / 2), (a / 2, -a / 2), (a / 2, a / 2), (-a / 2, a / 2)])
def section(kind, af, t):
    outer = hexagon(af) if kind == "hex" else square(af); inner = hexagon(af - 2 * t) if kind == "hex" else square(af - 2 * t); s = outer.difference(inner)
    xs, ys = np.meshgrid(np.linspace(-af, af, 801), np.linspace(-af, af, 801)); dA = (2 * af / 800) ** 2
    from shapely import contains_xy
    m = contains_xy(s, xs, ys); I = float(np.sum((ys[m]) ** 2) * dA); I2 = float(np.sum((xs[m]) ** 2) * dA)
    return dict(A=s.area, I=min(I, I2), flat_in=(af - 2 * t) / math.sqrt(3) if kind == "hex" else af - 2 * t, n_flats=6 if kind == "hex" else 4)

def sag(kind, afs, t, P_tip_N, L=980.0, ov=100.0):
    secs = [section(kind, a, t) for a in afs]; seg = (L + 2 * ov) / 3.0; x = np.linspace(0, L, 1201)
    idx = np.array([min(int(v // (seg - ov)), 2) for v in x])
    EI = E_CF * np.array([secs[i]["I"] for i in idx]); q = RHO_CF * np.array([secs[i]["A"] for i in idx]) * 9.81e-3
    shear = np.array([np.trapezoid(q[i:], x[i:]) for i in range(len(x))]) + P_tip_N
    M = np.array([np.trapezoid(shear[i:], x[i:]) for i in range(len(x))]); kappa = M / EI
    th = np.concatenate([[0], np.cumsum((kappa[1:] + kappa[:-1]) / 2 * np.diff(x))]); w = np.concatenate([[0], np.cumsum((th[1:] + th[:-1]) / 2 * np.diff(x))])
    mass = sum(RHO_CF * s["A"] * 380.0 for s in secs)
    return float(w[-1]), float(mass), secs

def lane_groups():
    g = {"HV (TX strips)": 0.0, "power": 0.0, "digital": 0.0, "REF": 0.0}; pos = 0.0; first_ref = None; tx_end = None
    for n, w in CFX.LANES:
        if n.startswith("TX"): g["HV (TX strips)"] += w
        elif n.startswith(("VIN", "GND")): g["power"] += w
        elif any(n.startswith(d) for d in DIGITAL): g["digital"] += w
        elif n.startswith("REF"): g["REF"] += w
        if n == "TX_B": tx_end = pos + w
        if n.startswith("REF") and first_ref is None: first_ref = pos
        pos += w
    return g, (first_ref - tx_end) if first_ref is not None and tx_end is not None else None

def main():
    import rf2_chassis as CS
    tubes = CS.SPEC["tubes"]; t = CS.SPEC["wall"]; afs = [tubes["outer"][0], tubes["mid"][0], tubes["inner"][0]]
    hc = json.load(open(os.path.join(HERE, "head", "out_BF", "rf2_head_check.json"))); P = (hc["checks"]["mass_g"]["total_islands_only"] + 40.0) * 9.81e-3
    bore = min(tubes["inner"]) - 2 * t; res = dict(status="MODELED options study (owner 2026-10-31): nothing adopted")
    # ---------------- A. optical link
    g, gap_tx_ref = lane_groups()
    dig_w = sum(w for n, w in CFX.LANES if any(n.startswith(d) for d in DIGITAL)) + 2 * 0.3
    loop_r_avail = (bore - POF["jacket_mm"]) / 2
    P_links = [3 * (a + b) * AFBR["v"] / 1000 for a, b in zip(AFBR["icc_tx_mA"], AFBR["icc_rx_mA"])]
    P_sys = 19.72; Wh = 102.1
    c_dig_ref = CFX.cps_c_pf_per_m(0.15, 0.3 + 0.3, CFX.EPS_EFF)
    res["optical"] = dict(links=3, replaces=list(DIGITAL), flex_width_mm=[round(CFX.WIDTH, 2), round(CFX.WIDTH - dig_w, 2)], conductors_removed=6,
                          power_W=[round(x, 2) for x in P_links], runtime_scan_h=[round(Wh / P_sys, 2), round(Wh / (P_sys + P_links[0]), 2), round(Wh / (P_sys + P_links[1]), 2)],
                          timing=f"delay <= {AFBR['delay_ns']} ns, pulse-width distortion <= +-{AFBR['pwd_ns']} ns: negligible against microsecond gates",
                          fibre_loss_dB_1p5m=round(POF["loss_db_km"] * 1.5e-3, 2), rolling_loop_radius_available_mm=round(loop_r_avail, 2),
                          fibre_bend_needed_mm=dict(repeated=POF["bend_repeated_mm"], static=POF["bend_static_mm"]), bore_needed_mm=round(2 * POF["bend_repeated_mm"] + POF["jacket_mm"], 1),
                          housings=f"6 Versatile Link housings {AFBR['housing_mm']} mm: at the neck and at the hinge / handle, not in the 18 mm bore",
                          coupling_removed_pF_per_m=round(c_dig_ref, 1),
                          findings=[f"the fibre would follow the cord flex's rolling loop inside an {bore:.1f} mm bore: at most {loop_r_avail:.1f} mm loop radius against {POF['bend_repeated_mm']:.0f} mm for repeated bending (25 mm static): it does not fit the telescope ({2 * POF['bend_repeated_mm'] + POF['jacket_mm']:.0f} mm bore needed)",
                                    f"gain if it did: flex {CFX.WIDTH:.1f} -> {CFX.WIDTH - dig_w:.1f} mm, 6 conductors and the digital-edge coupling into the REF pairs removed; cost {P_links[0]:.2f}-{P_links[1]:.2f} W (scan runtime {Wh / P_sys:.2f} -> {Wh / (P_sys + P_links[1]):.2f} h)",
                                    "galvanic isolation is only partial: power, TX strips and REF pairs stay copper",
                                    "where it fits: a straight, static run (e.g. handle to a hinge-mounted board) or a free-space IR link down a clear tube (not modeled)"])
    # ---------------- B. hex profiles
    sq_d, sq_m, sq_s = sag("square", afs, t, P)
    hx_d, hx_m, hx_s = sag("hex", afs, t, P)
    # equal mass hex: scale across-flats so the mass matches the square set
    lo, hi = 1.0, 1.4
    for _ in range(40):
        k = (lo + hi) / 2; d, m, _ = sag("hex", [a * k for a in afs], t, P)
        lo, hi = (k, hi) if m < sq_m else (lo, k)
    he_d, he_m, he_s = sag("hex", [a * k for a in afs], t, P)
    flat = hx_s[2]["flat_in"]
    fits = {name: dict(width_mm=round(w + 1.5, 2), fits_hex_flat=bool(w + 1.5 <= flat), fits_square_flat=bool(w + 1.5 <= sq_s[2]["flat_in"])) for name, w in g.items()}
    c_coplanar = K.c_parallel_wires(max(gap_tx_ref, 1.0) * 1e-3 + CFX.W_TX * 1e-3, CFX.W_TX * 1e-3 / 4, 1.0 + (CFX.EPS_EFF - 1)) * 1e12
    c_opposite = K.c_parallel_wires((min(tubes["inner"]) - 2 * t) * 1e-3, CFX.W_TX * 1e-3 / 4, 1.0) * 1e12
    clear = (afs[1] - 2 * t - afs[2]) / 2
    res["hex"] = dict(square=dict(across_flats_mm=afs, tubes_g=round(sq_m), tip_sag_mm=round(sq_d, 2), inner_flat_mm=round(sq_s[2]["flat_in"], 2), n_flats=4),
                      hex_same_af=dict(across_flats_mm=afs, tubes_g=round(hx_m), tip_sag_mm=round(hx_d, 2), inner_flat_mm=round(flat, 2), n_flats=6),
                      hex_equal_mass=dict(across_flats_mm=[round(a * k, 1) for a in afs], tubes_g=round(he_m), tip_sag_mm=round(he_d, 2), inner_flat_mm=round(he_s[2]["flat_in"], 2), n_flats=6),
                      lane_groups_on_faces=fits, tx_ref_gap_coplanar_mm=round(gap_tx_ref, 2),
                      C_tx_to_ref_pF_per_m=dict(coplanar_flex=round(c_coplanar, 2), opposite_hex_faces=round(c_opposite, 2)),
                      sliding_clearance_mm=round(clear, 2),
                      central_bore=dict(feasible_in="the innermost (lowest) tube only: every other tube's bore must stay clear for the tube that slides in it",
                                        hub=dict(od_mm=5.0, id_mm=4.0, webs=6, web_t_mm=0.6), added_g_per_380mm=round(RHO_CF * (math.pi / 4 * (5 ** 2 - 4 ** 2) + 6 * 0.6 * ((afs[2] - 2 * t) / 2 - 2.5)) * 380.0, 1)),
                      long_flex_boards=dict(outer_tube_outside_flats=dict(n=6, width_mm=round(hexagon(afs[0]).length / 6, 1), length_mm=380.0, area_cm2=round(6 * hexagon(afs[0]).length / 6 * 380.0 / 100, 1)),
                                            square_outside_faces_area_cm2=round(4 * afs[0] * 380.0 / 100, 1),
                                            echo_rule="metal boards at s >= 375 mm from the head stay below 0.5 x gate noise for a 5 K step (rf2_system echoes, TXD-class metal); the outer tube spans s 410-790 mm",
                                            inside_flats="the inner flats of the outer and middle tubes are swept by the sliding tube (clearance %.1f mm): only flex with parts under about 1 mm would fit, at wear risk" % clear))
    res["hex"]["findings"] = [
        f"same across-flats: hex tubes {hx_m:.0f} g vs square {sq_m:.0f} g, tip sag {hx_d:.2f} vs {sq_d:.2f} mm (hex is lighter and slightly softer: less material in the corners)",
        f"equal mass: hex across-flats x{k:.3f} ({', '.join(str(round(a * k, 1)) for a in afs)} mm), sag {he_d:.2f} mm vs square {sq_d:.2f} mm",
        f"inner flats: hex 6 x {flat:.1f} mm vs square 4 x {sq_s[2]['flat_in']:.1f} mm; the whole 15.7 mm cord flex fits one square face, not one hex face: on a hex it splits by group onto separate faces",
        f"TX strips and REF pairs on opposite hex faces: {c_opposite:.2f} pF/m vs {c_coplanar:.2f} pF/m side by side on the flex (gap {gap_tx_ref:.1f} mm)",
        "a central bore with webs works only in the innermost tube; it would carry a fibre or a coax, but the fibre still cannot cross the rolling loop",
        f"long flex boards: the outside flats of the upper tube give {6 * hexagon(afs[0]).length / 6 * 380.0 / 100:.0f} cm2 (square {4 * afs[0] * 380.0 / 100:.0f} cm2) at s 410-790 mm, past the 375 mm echo distance: room for the TXD as a long board under a cover",
        "the flex groups bonded to the inner tube's faces move with it; the slack for the 550 mm travel still needs the rolling loop (or a coil cord) in the upper tubes"]
    res["rule_rows"] = [dict(rule="POF repeated-bend radius vs the rolling-loop radius available in the inner bore", value=round(loop_r_avail, 2), limit=POF["bend_repeated_mm"], sense=">=", ok=loop_r_avail >= POF["bend_repeated_mm"]),
                        dict(rule="hex (same AF) tip sag vs the square profiles' sag", value=round(hx_d, 2), limit=round(sq_d, 2), sense="<=", ok=hx_d <= sq_d),
                        dict(rule="HV lane group (TX strips + edges) vs one hex inner flat", value=fits["HV (TX strips)"]["width_mm"], limit=round(flat, 2), sense="<=", ok=fits["HV (TX strips)"]["fits_hex_flat"])]
    res["ok"] = True
    json.dump(res, open(os.path.join(OUT, "rf2_shaftlink_options.json"), "w"), indent=1, default=float)
    build_stl(afs, t, res)
    print(json.dumps(res["optical"]["findings"], indent=0)); print(json.dumps(res["hex"]["findings"], indent=0)); print(res["rule_rows"])
    return res

def build_stl(afs, t, res):
    import cadquery as cq
    L = 200.0; P = {}
    def hx(af, tt): return cq.Workplane("XY").polygon(6, 2 * af / math.sqrt(3)).polygon(6, 2 * (af - 2 * tt) / math.sqrt(3)).extrude(L)
    P["HEX_OUTER"] = hx(afs[0], t).translate((0, 0, 2 * L + 20)); P["HEX_MID"] = hx(afs[1], t).translate((0, 0, L + 10)); P["HEX_INNER"] = hx(afs[2], t)
    ri = (afs[2] - 2 * t) / 2; hub = cq.Workplane("XY").circle(2.5).circle(2.0).extrude(L)
    for k in range(6):
        a = math.degrees(k * math.pi / 3); hub = hub.union(cq.Workplane("XY").box(ri / math.cos(math.pi / 6) - 2.4, 0.6, L).translate(((ri / math.cos(math.pi / 6) + 2.4) / 2 + 0.05, 0, L / 2)).rotate((0, 0, 0), (0, 0, 1), a))
    P["CENTRAL_BORE_HUB"] = hub
    P["POF_IN_BORE"] = cq.Workplane("XY").circle(1.1).extrude(L)
    strips = []
    fw = (afs[2] - 2 * t) / math.sqrt(3) - 0.6
    for k, (name, col) in enumerate((("HV", 0), ("PWR", 2), ("REF", 4))):
        a = (2 * k * math.pi / 3) + math.pi / 6; d = ri - 0.08
        strips.append(cq.Workplane("XY").box(0.15, fw, L).translate((d, 0, L / 2)).rotate((0, 0, 0), (0, 0, 1), math.degrees(a)).val())
    P["FLEX_ON_FLATS"] = cq.Workplane("XY").add(cq.Compound.makeCompound(strips))
    ro = afs[0] / 2; brd = []
    for k in range(6):
        a = math.degrees(k * math.pi / 3 + math.pi / 6)
        b = cq.Workplane("XY").box(0.2, hexagon(afs[0]).length / 6 - 2, L - 20).translate((ro + 0.1, 0, 2 * L + 30 + (L - 20) / 2)).rotate((0, 0, 0), (0, 0, 1), a)
        brd.append(b.val())
    P["LONG_FLEX_BOARDS_OUTSIDE"] = cq.Workplane("XY").add(cq.Compound.makeCompound(brd))
    files = []
    for k, w in P.items():
        f = os.path.join(OUT, f"shaftlink_{k}.stl"); cq.exporters.export(w, f, tolerance=0.1); files.append(os.path.basename(f))
    cq.exporters.export(cq.Compound.makeCompound([w.val() for w in P.values()]), os.path.join(OUT, "shaftlink_hex.step"))
    res["stl"] = files + ["shaftlink_hex.step"]; json.dump(res, open(os.path.join(OUT, "rf2_shaftlink_options.json"), "w"), indent=1, default=float)

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
