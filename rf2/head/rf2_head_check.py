#!/usr/bin/env python3
"""RF2 head v1 checks (2026-10-29): measured on the solids of rf2_head.py (manifold3d) and on the written STLs. Writes out/rf2_head_check.json.
  1. every STL closed and edge-manifold (each edge in exactly two triangles), positive volume
  2. envelope: every head part inside r <= 116.5 and 0 <= z <= 25.4
  3. no interference: pairwise intersection volume < 0.01 mm3 for every pair of head parts
  4. clearances (manifold min_gap): litz to shell wall and channel wall >= 0.2 mm; islands to bay walls and to each other >= 0.5 mm; HV envelopes
     (TXJ, MP1) to every non-HV island >= 3.0 mm (envelope margin; copper-level HV clearance is the boards' own rule 6 check)
  5. LED display: every LED / capacitor inside the flex outline, LED tops at the clear lid's underside, flex clear of the gland boss
  6. mass from the solids (PETG 1.27, FR4 1.85 g/cm3) + litz (6 g/m) + board copper + island estimates + potting (full fill and islands-only)
  7. potting volume per sector (analog / HV / digital) = sector prism minus islands and walls
usage: python3 rf2/head/rf2_head_check.py"""
import os, sys, json, math, itertools, struct
import numpy as np
import manifold3d as m3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_head as H
S = H.SPEC; OUT = H.OUT
def stl_closed(path):
    b = open(path, "rb").read(); n = struct.unpack("<I", b[80:84])[0]
    T = np.frombuffer(b, dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]), count=n, offset=84)["v"].reshape(-1, 3, 3).astype(np.float64)
    q = np.round(T.reshape(-1, 3) * 1e4).astype(np.int64); _, inv = np.unique(q, axis=0, return_inverse=True); tri = inv.reshape(-1, 3)
    e = np.sort(np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1); _, cnt = np.unique(e, axis=0, return_counts=True)
    v = float(np.sum(np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2]))) / 6)
    return dict(triangles=int(n), edges_not_2=int(np.sum(cnt != 2)), volume_cm3=round(v / 1000, 3), ok=bool(np.all(cnt == 2) and v > 0))
def main():
    P = H.parts(); head = {k: v for k, v in P.items() if k != "REF3_FORMER"}; res = dict(status="MEASURED on the RF2 head v1 solids (design MODELED, not built)", checks={})
    # 1
    closed = {k: stl_closed(os.path.join(OUT, f"RF2_{k}.stl")) for k in P}; res["checks"]["closed_meshes"] = dict(ok=all(c["ok"] for c in closed.values()), parts=closed)
    # 2
    env = {}
    for k, v in head.items():
        Vt = np.asarray(v.to_mesh().vert_properties)[:, :3]; env[k] = dict(r_max=round(float(np.max(np.hypot(Vt[:, 0], Vt[:, 1]))), 3), z=[round(float(Vt[:, 2].min()), 3), round(float(Vt[:, 2].max()), 3)])
    res["checks"]["envelope"] = dict(ok=all(e["r_max"] <= S["envelope"]["R"] + 1e-6 and e["z"][0] >= -1e-6 and e["z"][1] <= S["envelope"]["H"] + 1e-6 for e in env.values()), parts=env)
    # 3
    bad = []
    for a, b in itertools.combinations(head, 2):
        v = (head[a] ^ head[b]).volume()
        if v > 0.01: bad.append(dict(pair=f"{a} x {b}", mm3=round(v, 3)))
    res["checks"]["no_interference"] = dict(ok=not bad, pairs_checked=len(list(itertools.combinations(head, 2))), overlaps=bad)
    # 4
    gap = lambda a, b, s=10.0: round(float(head[a].min_gap(head[b], s)), 3)
    isl = [k for k in head if k.startswith("ENV_") and k != "ENV_LED"]; hv = [f"ENV_{k}" for k, v in S["boards_inner"].items() if v.get("hv") or k in ("MP1", "TXJ")]
    seats = {k: gap(k, "ENV_" + k.split("_", 1)[1]) for k in head if k.startswith(("CRADLE_", "TRAY_"))}; 
    if "CB1D_TOWER" in head: seats["CB1D_TOWER"] = gap("CB1D_TOWER", "ENV_CB1D")
    fin_env = [k for k in isl if S["boards_inner"][k[4:]].get("kind") == "fin"]
    for k in ("HUB", "FIN_RAILS"):
        if k in head: seats[k] = min(gap(k, f) for f in fin_env)
    seat_ok = all(v >= -1e-6 for v in seats.values())                       # seats touch their board at the ledge (0) and nowhere intersect (interference check)
    co = S["coil"]; inner_wall_gap = round(min(co["columns_r"]) - co["litz_od"] / 2 - S["channel"]["inner_wall_r"][1], 3)
    seated = round(co["row0_z"] - co["litz_od"] / 2 - co["floor_z"][1], 3)                 # bottom row rests on the printed floor (bonded seat): 0 by design
    g_litz = dict(shell=gap("LITZ", "SHELL_LOWER"), channel_inner_wall=inner_wall_gap, top_row_below_channel_top=round(S["channel"]["z"][1] - (max(z for _, z in H.coil_turns()) + co["litz_od"] / 2), 3))
    turns = H.coil_turns(); slots = H.coil_slots()
    res["checks"]["coil_order"] = dict(order=co.get("order", "row"), slots=[list(x) for x in slots], coil_top_z=round(max(z for _, z in turns) + co["litz_od"] / 2, 3),
                                       inner_turn_r=round(min(r for r, _ in turns), 3), turns=len(turns), distinct_slots=len(set(slots)),
                                       ok=len(turns) == co["turns"] and len(set(slots)) == len(slots) and (co.get("order", "row") != "bank" or all(
                                           slots[i + 1][0] > slots[i][0] or (slots[i + 1][0] == slots[i][0] and slots[i + 1][1] == slots[i][1] + 1) for i in range(len(slots) - 1))))
    litz_seat = dict(floor_contact_mm=seated, channel_min_gap=gap("LITZ", "COIL_CHANNEL"), note="the bottom row is seated on the floor (0 by design); nothing else touches")
    g_walls = {k: gap(k, "BAY_WALLS") for k in isl}
    g_seat_walls = {k: gap(k, "BAY_WALLS") for k in head if k.startswith(("CRADLE_", "TRAY_", "CB1D_TOWER", "FIN_RAILS"))}
    g_isl = {f"{a} - {b}": gap(a, b) for a, b in itertools.combinations(isl, 2)}
    g_hv = {f"{h} - {k}": gap(h, k, 20.0) for h in hv for k in isl if k not in hv}
    res["checks"]["seats"] = dict(ok=seat_ok, seat_to_its_board_mm=seats, seats_to_walls_mm=g_seat_walls)
    res["checks"]["clearances_mm"] = dict(ok=min(g_litz.values()) >= 0.2 and min(g_walls.values()) >= 0.5 and min(g_isl.values()) >= 0.5 and min(g_hv.values()) >= 3.0 and min(g_seat_walls.values()) >= 0.5,
                                         litz=g_litz, litz_seat=litz_seat, islands_to_walls=g_walls, islands=g_isl, hv_to_others=g_hv)
    # 5 LED display: every LED / capacitor site inside the flex outline (1.0 mm from its edges, incl. the gland notch and the hinge slit); LEDs end at
    #   the clear lid's underside; the flex clears the gland boss; the flex hangs on the bosses (pins through the board holes)
    import rf2_ledgrid as LG
    from shapely.geometry import Point
    led = S["boards_inner"]["LED"]; pos = H.led_positions(); o = LG.outline().buffer(-1.0); top = led["z"][1] + led["above"]
    inside = all(o.contains(Point(x, y)) for x, y, *_ in H.led_sites())
    gb = S["gland"]; gland_gap = LG.outline().distance(Point(*gb["c"]).buffer(gb["boss_d"] / 2, 64))
    res["checks"]["led_display"] = dict(ok=abs(top - S["shell"]["lid_z"][0]) < 1e-9 and inside and gland_gap >= 0.5, leds=len(pos), sites_inside_outline=inside,
                                        led_top_z=top, lid_underside_z=S["shell"]["lid_z"][0], flex_to_gland_boss_mm=round(gland_gap, 3),
                                        led_seat_gap_to_lid=round(gap("ENV_LED", "LID"), 3), lid=S["lid_light"]["material"])
    ll = S["lid_light"]
    if ll.get("type") == "light_plate":                                                        # every LED has a conical well, centred, with printable webs between them
        from shapely.geometry import Polygon
        from shapely.strtree import STRtree
        zm = S["shell"]["lid_z"][1] - 0.02; polys = H.parts()["LID"].slice(zm).to_polygons()
        holes = [Polygon(r) for pg in polys[1:] for r in [pg]] if len(polys) > 1 else []
        holes = [Polygon(p_) for p_ in polys if Polygon(p_).exterior.is_ccw is False] if not holes else holes
        rings = [Polygon(p_) for p_ in polys]; areas = sorted(rings, key=lambda g: -g.area); wells = [g for g in rings if g.area < 40.0 and g.area > 5.0]
        cen = np.array([(g.centroid.x, g.centroid.y) for g in wells]); led = np.array(pos)
        off = [float(np.min(np.hypot(*(cen - q).T))) if len(cen) else 9e9 for q in led]
        tree = STRtree(wells); web = min((g.distance(wells[j]) for i, g in enumerate(wells) for j in tree.query(g.buffer(3.0)) if j != i), default=9e9)
        res["checks"]["light_plate"] = dict(ok=len(wells) == len(pos) and max(off) < 0.05 and web >= ll["web_min_mm"], leds=len(pos), wells=len(wells), max_centre_offset_mm=round(max(off), 4),
                                            min_web_mm=round(web, 3), d_bottom=ll["d_bottom"], d_top=ll["d_top"], material=ll["material"][:120])
    # 7 potting per sector
    bz = S["bay"]["z"]; bay = H.cyl(S["bay"]["r_max"], *bz)                                   # the whole bay disc
    def sector(d0, d1):
        pts = [(0, 0)] + [(200 * math.cos(math.radians(a)), 200 * math.sin(math.radians(a))) for a in np.linspace(d0, d1, 64)]
        return m3.CrossSection([pts]).extrude(bz[1] - bz[0]).translate([0, 0, bz[0]])
    solids = None
    for k in isl + ["BAY_WALLS"] + [k for k in head if k.startswith(("CRADLE_", "TRAY_", "CB1D_TOWER", "HUB", "FIN_RAILS", "BAY_FLOOR", "BOARD_HUB"))]: solids = head[k] if solids is None else solids + head[k]
    free = bay - solids
    secs = dict(analog=sector(*S["sectors"]["analog"]), hv=sector(*S["sectors"]["hv"]))
    secs["digital"] = H.cyl(300, bz[0], bz[1]) - secs["analog"] - secs["hv"]
    pv = {k: round((free ^ v).volume() / 1000, 1) for k, v in secs.items()}
    res["checks"]["potting_cm3_full_fill"] = pv
    # 6 mass
    shp = os.path.join(OUT, "SH1", "sh1_check.json"); SH1_CU = json.load(open(shp))["topology"]["copper_area_cm2"] if os.path.exists(shp) else 230.0
    PETG, FR4 = 1.27, 1.85; dens = dict(analog=0.98, hv=1.15, digital=0.65)        # gel / epoxy / syntactic: ASSUMED densities
    vol = lambda k: P[k].volume() / 1000
    printed = ["SHELL_LOWER", "LID", "COIL_CHANNEL", "BAY_WALLS"] + [k for k in ("CB1D_TOWER", "COIL_COMBS", "HUB", "FIN_RAILS", "BAY_FLOOR") if k in P] + [k for k in P if k.startswith(("CRADLE_", "TRAY_"))]
    cu_rx = S["boards"]["QA"].get("copper_um", 35) / 1000.0
    m = {"printed parts (shell, lid, channel, walls, seats; PETG 100 % infill)": sum(vol(k) for k in printed) * PETG,
         "receive boards QA + QB (FR4) + copper (16.9 m x 0.8 mm x %d um each)" % round(cu_rx * 1000): (vol("BOARD_QA") + vol("BOARD_QB")) * FR4 + 2 * 16.9e3 * 0.8 * cu_rx / 1000 * 8.96,
         "shield SH1 (FR4) + its copper (area from sh1_check.json) x 35 um": vol("BOARD_SH1") * FR4 + SH1_CU * 0.0035 * 8.96,
         "transmit litz (26 turns, %.1f g/m)" % S.get("materials", {}).get("litz_g_per_m", 6.0): sum(2 * math.pi * r for r, _ in turns) / 1000 * S.get("materials", {}).get("litz_g_per_m", 6.0),
         "electronics islands (ASSUMED: AB1A/B 10 g each, CB1D 40 g, MP1 8 g, TXJ 10 g; LED display flex 40 g ASSUMED: 0.4 mm flex+stiffener D226 about 30 g + 522 LEDs / caps)": 10 + 10 + 40 + 8 + 10 + 40,
         "coil channel epoxy (fill around the litz, 1.15 g/cm3 ASSUMED)": max(0.0, (H.ring(S["channel"]["inner_wall_r"][1], S["shell"]["wall_r"][0], S["coil"]["floor_z"][1], S["coil"]["row0_z"] + S["coil"]["rows"] * S["coil"]["pitch"]).volume() - vol("LITZ") * 1000) / 1000 * 1.15),
         "hardware, cable gland, yoke lug (ASSUMED)": 40.0}
    if "PRX" in S["boards"]:                                                   # hybrid receive (owner 2026-10-31): PRX layer + the MP2 board (as MP1, ASSUMED)
        px = S["prx"]; pi_cm2 = vol("BOARD_PRX") / 0.01                        # area from the solid (0.1 mm slot)
        m["PRX layer (25 um PI 1.42 g/cm3 + %.1f m x %.2f mm x %d um Cu spirals)" % (px["length_m"], px["trace_mm"], px["copper_um"])] = pi_cm2 * 0.0025 * 1.42 + px["length_m"] * 100 * px["trace_mm"] / 10 * px["copper_um"] * 1e-4 * 8.96
        m["MP2 second receive channel (ASSUMED as MP1, 8 g)"] = 8.0
    base = sum(m.values()); pot_full = sum(pv[k] * dens[k] for k in pv); pot_isl = 0.5 * sum(vol(k) for k in isl) * 0.9
    lp = os.path.join(OUT, "rf2_ledger.json")
    if os.path.exists(lp):                                                 # the ledger's stated fill levels replace the islands-only estimate (coil epoxy is counted there too)
        led = json.load(open(lp)); pot_isl = led["potting_g"] - next(r["fill_g"] for r in led["regions"] if r["region"] == "coil channel"); m.pop("coil channel epoxy (fill around the litz, 1.15 g/cm3 ASSUMED)", None); base = sum(m.values()) + next(r["fill_g"] for r in led["regions"] if r["region"] == "coil channel")
    res["checks"]["mass_g"] = dict(items={k: round(v, 1) for k, v in m.items()}, without_bay_potting=round(base), bay_full_fill_potting=round(pot_full), islands_only_potting=round(pot_isl),
                                   potting_source="rf2_ledger.json stated fill levels" if os.path.exists(lp) else "islands-only estimate", total_islands_only=round(base + pot_isl), total_full_fill=round(base + pot_full), earlier_estimate=529,
                                   note="100 % infill PETG is an upper bound for the printed parts; the earlier 529 g estimate assumed a single 0.4 mm receive board, not the two 0.8 mm SB1R boards")
    res["ok"] = all(c.get("ok", True) for c in res["checks"].values() if isinstance(c, dict))
    res["vertical_budget_mm"] = dict(total=S["envelope"]["H"], bay=S["bay"]["z"], bay_height=round(S["bay"]["z"][1] - S["bay"]["z"][0], 1),
                                    stack={k: [round(v["z"][0] - v["below"], 2), round(v["z"][1] + v["above"], 2)] for k, v in S["boards_inner"].items()}, baseline_head=47.1)
    res["model_deviation"] = "coil rows sit at z 4.4-17.2 mm (a 0.6 mm printed floor on QB) against z 3.2-16.0 in the RF2 models: 1.2 mm higher; re-run rf2_receiver_combo with the built z before any number is quoted for this layout"
    json.dump(res, open(os.path.join(OUT, "rf2_head_check.json"), "w"), indent=1); return res
if __name__ == "__main__":
    r = main(); print("ok", r["ok"]); [print(k, json.dumps({kk: vv for kk, vv in v.items() if kk not in ("parts",)})[:400]) for k, v in r["checks"].items()]
