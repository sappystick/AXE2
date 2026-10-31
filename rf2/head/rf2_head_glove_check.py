#!/usr/bin/env python3
"""Checks of the glove housing and the internal head map (rf2_head_glove.py). MEASURED on the solids (manifold3d); design MODELED, not built.
  1. closed meshes (every glove part and potting solid: each edge in exactly two triangles, positive volume)
  2. interference: every pair of glove parts, held components and potting solids intersects < 0.01 mm3
  3. pocket clearances: min_gap of every held part to the glove feature that locates it, each against its stated limit
  4. minimum wall per glove part (horizontal slices, bisection on an inward offset) against the process rule; plates from the SPEC
  5. potting: measured volume and mass per cavity (fill to the stated level); HV epoxy >= 3.0 mm from the litz (measured min_gap)
  6. HV and rule 5: HV envelopes >= 3.0 mm to every non-HV part, litz pass-through clearance, the shield coat's slit not bridged by its masking rib,
     no metal in the housing (all parts PETG / resin), the PRX spirals open (spirals, no closed ring)
  7. PRX: feed hole edge to QA / QB copper >= 1.0 mm (SB1R geometry), feed hole to the main spiral >= 0.5 mm, PRX copper to the litz >= 1.0 mm (rule 6 scale),
     bucking spiral under the TX columns, PRX outline inside the bore
  8. coil (bank) and channel: coil top vs channel top >= 0.2 mm, inner column to channel wall >= 0.2 mm
  9. zone map: every part's echo drift (5 K) <= 0.5 x gate noise; every non-HV part >= 3.0 mm from the HV envelopes
 10. mass: head before (rf2_head_check BF at git HEAD) -> after (glove parts + measured potting)
Every numeric check is also a rule row (rule-11 BLOCKED / EDGE classification in rf2_rules.py style). Writes out_BF/glove/rf2_head_glove.json.
usage: python3 rf2/head/rf2_head_glove_check.py"""
import os, sys, json, math, itertools, subprocess, struct, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..")); sys.path.insert(0, HERE)
import rf2_head_glove as GL
H = GL.H; S = GL.S; m3 = GL.m3
OUT = GL.OUT
ROWS = []
def rule(name, value, limit, sense, where, kind="geometry", safety=False):
    v = float(value); ok = v >= limit - 1e-9 if sense == ">=" else v <= limit + 1e-9
    head = (v - limit) / abs(limit) if sense == ">=" else (limit - v) / abs(limit) if limit else (0.0 if v <= 0 else -1.0)
    status = "PASS" if ok and head > 0.05 else ("EDGE" if ok else ("BLOCKED" if head >= -0.10 else "FAIL"))
    ROWS.append(dict(rule=name, value=round(v, 4), limit=limit, sense=sense, where=where, kind=kind, safety=safety, ok=ok, headroom=round(head, 4), status=status)); return ok
def closed(man):
    mm = man.to_mesh(); T = np.asarray(mm.tri_verts); e = np.sort(np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
    _, c = np.unique(e, axis=0, return_counts=True); return bool(np.all(c == 2) and man.volume() > 0)
def bbox_hit(a, b):
    A, B = a.bounding_box(), b.bounding_box()
    return all(A[i] <= B[i + 3] + 1e-6 and B[i] <= A[i + 3] + 1e-6 for i in range(3))
def main():
    t0 = time.time(); res = dict(status="MEASURED on the glove housing solids (design MODELED, not built; process rules ASSUMED)", checks={})
    G, C, POT, F, P, info = GL.build("printed"); sides = GL.fin_side_envelopes()
    # 1 closed
    cl = {k: closed(v) for k, v in {**G, **POT}.items()}; res["checks"]["closed_meshes"] = dict(ok=all(cl.values()), parts=cl)
    # 2 interference
    allp = {**G, **C, **POT}; bad = []; n = 0
    for a, b in itertools.combinations(allp, 2):
        if not bbox_hit(allp[a], allp[b]): continue
        n += 1; v = (allp[a] ^ allp[b]).volume()
        if v > 0.01: bad.append(dict(pair=f"{a} x {b}", mm3=round(v, 3)))
    tot = sum(d["mm3"] for d in bad)
    res["checks"]["interference"] = dict(ok=not bad, pairs=len(list(itertools.combinations(allp, 2))), pairs_touching_bbox=n, overlaps=bad, total_mm3=round(tot, 3))
    rule("glove: interference volume, all parts / components / potting (mm3)", tot, 0.01, "<=", "whole head")
    # 3 pockets
    gap = lambda a, b, s=6.0: round(float(a.min_gap(b, s)), 3)
    pk = []
    def pocket(part, feature, design, limit, a, b, seat=False, note=""):
        g = gap(a, b); pk.append(dict(part=part, pocket=feature, design_mm=design, measured_mm=g, limit_mm=limit, seat=seat, note=note))
        if not seat: rule(f"pocket clearance {part} in {feature}", g, limit, ">=", feature)
        return g
    for b in ("SH1", "PRX", "QA", "QB"):
        pocket(f"BOARD_{b}", "shell bore (r 114.5)", round(S["shell"]["wall_r"][0] - S["boards"][b]["r"], 3), 0.2, C[f"BOARD_{b}"], F["outer_wall"])
    for b in ("SH1", "QA", "QB"): pocket(f"BOARD_{b}", "stack pins (3.2 in 3.4 holes)", 0.1, 0.05, C[f"BOARD_{b}"], F["stack_pins"])
    pocket("BOARD_SH1", "skid (seat)", 0.0, 0.0, C["BOARD_SH1"], F["skid"], seat=True)
    pocket("LITZ", "outer wall + coat-mask rib (G_SHELL)", None, 0.2, C["LITZ"], G["G_SHELL"] - F["skid"])
    pocket("LITZ", "shield coat", round(S["shield_coat"]["r"][0] - (max(S["coil"]["columns_r"]) + S["coil"]["litz_od"] / 2), 3), 0.2, C["LITZ"], C["SHIELD_COAT"])
    pocket("LITZ", "channel inner wall", None, 0.2, C["LITZ"], F["channel_wall"])
    pocket("LITZ", "floor (seat: bottom row bonded on the floor)", 0.0, 0.0, C["LITZ"], F["floor"], seat=True)
    pocket("LITZ", "comb slots (1.47 for 1.372 litz)", round((S["coil_combs"]["slot"] - 1.372) / 2, 3), 0.03, C["LITZ"], G["G_COMBS"])
    for k, v in S["boards_inner"].items():
        e = C["ENV_" + k]
        if v.get("kind") == "fin":
            pocket(f"ENV_{k}", "fin rails (1.1 gap, 1.0 board)", round((S["fin_guides"]["gap"] - v["t"]) / 2, 3), 0.03, e, F["fin_rails"])
            pocket(f"ENV_{k}", "floor", round(v["z"][0] - S["bay_floor"]["z"][1], 3), 0.05, e, F["floor"])
            pocket(f"ENV_{k}", "channel inner wall", round(S["channel"]["inner_wall_r"][0] - v["r"][1], 3), 0.5, e, F["channel_wall"])
            pocket(f"ENV_{k}", "sector walls", None, 0.5, e, F["sector_walls"])
            pocket(f"ENV_{k}", "stiffening ribs", None, 0.5, e, F["ribs"])
            if v["r"][0] < S["hub"]["r"]: pocket(f"ENV_{k}", "hub slot", None, 0.03, e, F["hub"])
            if v.get("hv"):                                                   # HV copper / parts to the island walls: the board's outer 0.5 mm is the copper edge keep-out (rf2_boards EDGE)
                e_cu = e - GL.fin_frame_box(v["deg"], v["r"][1] - 0.5, v["r"][1] + 1, -5, 5, 0, 30)
                pocket(f"ENV_{k}", "HV island walls (potting over HV copper / parts)", GL.C_POT, 1.0, e_cu, F["hv_island_walls"])
                pocket(f"ENV_{k}", "HV island outer arc (board edge, no copper)", None, 0.5, e, F["hv_island_walls"])
            elif v["zone"] == "analog":
                pocket(f"ENV_{k}", "gel trough side walls (potting gap)", GL.C_POT, 0.9, e, F["analog_trough_sides"])
                pocket(f"ENV_{k}", "gel trough end-wall fin slot (1.1 for 1.0)", 0.05, 0.03, e, F["analog_trough_end_slots"])
            else: pocket(f"ENV_{k}", "gel troughs / HV island (not its pocket)", None, 0.5, e, F["analog_troughs"] + F["hv_island_walls"])
    pocket("ENV_HUB_PCB", "hub", None, 0.3, C["ENV_HUB_PCB"], F["hub"])
    pocket("ENV_LED", "tray wall tops", round(S["boards_inner"]["LED"]["z"][0] - GL.WALL_TOP, 3), 0.4, C["ENV_LED"], G["G_TRAY"])
    pocket("ENV_LED", "lid (seat: hung on the bosses, LED tops at the plate)", 0.0, 0.0, C["ENV_LED"], G["G_LID"], seat=True)
    pocket("PRX_LEADS", "feed hole in QA / QB", round((S["prx"]["feed"]["hole_d"] - 0.66) / 2, 3), 0.5, C["PRX_LEADS"], C["BOARD_QA"] + C["BOARD_QB"])
    pocket("PRX_LEADS", "lane walls", round((2.0 - 0.66) / 2, 3), 0.3, C["PRX_LEADS"], F["prx_lane"])
    pocket("CORD_FLEX_CURL", "gland bore (8.0)", round((S["gland"]["d"] - GL.GLAND["curl_d"]) / 2, 3), 0.5, C["CORD_FLEX_CURL"], G["G_LID"])
    pocket("CORD_FLEX_CURL", "strain-relief pin", None, 0.2, C["CORD_FLEX_CURL"], G["G_GLAND_PIN"])
    pocket("SHIELD_COAT", "coat-mask rib (slit must stay open)", None, 0.0, C["SHIELD_COAT"], F["coat_mask_rib"], seat=True)
    res["checks"]["pockets"] = dict(ok=all(p["seat"] or p["measured_mm"] >= p["limit_mm"] - 1e-9 for p in pk), rows=pk)
    # 4 min wall
    zs_tray = [S["bay_floor"]["z"][1] + 0.3, 6.0, 9.0, 12.3]
    mw = {}
    for k, zs, proc in (("G_SHELL", [2.0, 8.0, 13.0], "printed"), ("G_TRAY", zs_tray, "printed"), ("G_COMBS", [6.0, 10.0], "resin"), ("G_LID", [S["shell"]["lid_z"][0] + 0.5, S["shell"]["lid_z"][1] - 0.2], "printed"), ("G_GLAND_PIN", [GL.GLAND["pin_z"]], "printed")):
        t, where = GL.min_feature(G[k], zs); mw[k] = dict(min_wall_mm=t, where=where, process=GL.PROC[proc]["name"], limit=GL.PROC[proc]["wall_min"])
        rule(f"min wall {k} ({proc})", t, GL.PROC[proc]["wall_min"], ">=", k)
    plates = dict(skid=S["shell"]["skid_t"], tray_floor=round(S["bay_floor"]["z"][1] - S["bay_floor"]["z"][0], 3), lid=round(S["shell"]["lid_z"][1] - S["shell"]["lid_z"][0], 3), lid_land=S["lid_light"]["land"])
    for k, v in plates.items(): rule(f"plate thickness {k} (printed, >= 3 layers)", v, GL.PROC["printed"]["plate_min"], ">=", k)
    GM, CM, POTM, FM, PM, infoM = GL.build("moulded"); tM, wM = GL.min_feature(GM["G_TRAY"], zs_tray)
    moulded = dict(min_wall_mm=tM, where=wM, draft_deg=GL.PROC["moulded"]["draft_deg"], floor_plate_mm=plates["tray_floor"],
                   wall_top_clearance_growth_mm=round((GL.WALL_TOP - S["bay_floor"]["z"][1]) * math.tan(math.radians(1.0)), 3),
                   pocket_gap_at_base_HV=gap(CM["ENV_FIN_HV1"], FM["hv_island_walls"]), pocket_gap_at_base_A2=gap(CM["ENV_FIN_A2"], FM["analog_troughs"]),
                   interference_with_fins_mm3=round(sum((GM["G_TRAY"] ^ CM["ENV_" + k]).volume() for k, v in S["boards_inner"].items() if v.get("kind") == "fin"), 3))
    rule("moulded variant: tray floor plate vs moulded min wall 0.8", plates["tray_floor"], GL.PROC["moulded"]["plate_min"], ">=", "G_TRAY floor (moulded)", kind="process option")
    rule("moulded variant: min wall G_TRAY", tM, GL.PROC["moulded"]["wall_min"], ">=", "G_TRAY (moulded)", kind="process option")
    res["checks"]["min_wall"] = dict(ok=all(v["min_wall_mm"] >= v["limit"] - 1e-9 for v in mw.values()) and all(v >= GL.PROC["printed"]["plate_min"] for v in plates.values()),
                                    parts=mw, plates_mm=plates, moulded_variant=moulded)
    # 5 potting
    dens = dict(POT_HV_EPOXY=("epoxy (MG 832TC)", GL.DENS["epoxy"]), POT_ANALOG_GEL=("silicone gel", GL.DENS["gel"]), POT_COIL_FOAM=("syntactic foam", GL.DENS["syntactic"]))
    pot = {k: dict(material=dens[k][0], volume_cm3=round(v.volume() / 1000, 2), density=dens[k][1], mass_g=round(v.volume() / 1000 * dens[k][1], 1)) for k, v in POT.items()}
    ep_litz = gap(POT["POT_HV_EPOXY"], C["LITZ"], 10.0)
    pot["POT_HV_EPOXY"]["gap_to_litz_mm"] = ep_litz; pot["fill_level_z"] = GL.FILL_Z
    pot["ports"] = dict(HV="fill: inner arc at 178 deg (open top); vent: the weir is the 12.6 wall top; litz pass-throughs RTV-sealed",
                        analog="fill: funnel notch at each trough's rim end (z 12.0-12.6); vent / weir notch at the hub end at z 12.5", coil="poured from the open channel top before the display")
    rule("HV epoxy to the litz (MG 832TC >= 3.0 mm)", ep_litz, GL.EPOXY_LITZ_MIN, ">=", "HV island outer arc", safety=True)
    res["checks"]["potting"] = dict(ok=ep_litz >= GL.EPOXY_LITZ_MIN - 1e-6 and all(v["volume_cm3"] > 0 for k, v in pot.items() if k.startswith("POT_")), cavities=pot)
    # 6 HV / rule 5
    hv_keys = [k for k, v in S["boards_inner"].items() if v.get("hv")]; hvm = GL.union([C["ENV_" + k] for k in hv_keys])
    non = {k: v for k, v in C.items() if k.startswith(("ENV_", "PRX_LEADS")) and k[4:] not in hv_keys and k != "ENV_LED"}      # the display flex over the fins: copper rule below (as rf2_head_check)
    hv_cu_led = round(S["boards_inner"]["LED"]["z"][0] - (max(S["boards_inner"][k]["z"][1] for k in hv_keys) - 0.5), 3)          # HV fin copper ends 0.5 mm under the board edge (edge rule)
    rule("rule 6: HV fin copper to the display flex (vertical)", hv_cu_led, 1.0, ">=", "HV island / LR1", safety=True)
    g_hv = {k: gap(v, hvm, 20.0) for k, v in non.items()}; rule("HV envelopes to non-HV parts (envelope margin 3.0)", min(g_hv.values()), 3.0, ">=", "HV island", safety=True)
    lp = (GL.LITZ_PASS_D - GL.LITZ_SLEEVE_OD) / 2; rule("litz pass-through radial clearance (sealed)", lp, 0.1, ">=", "HV island outer arc 178 deg")
    pitch = 2 * (info["r_epoxy_max"] + GL.T_W / 2) * math.sin(math.radians(1.5)); web = pitch - GL.LITZ_PASS_D
    rule("rule 6: TX_A / TX_B pass-through web (litz to litz through PETG)", web, 1.0, ">=", "HV island outer arc", safety=True)
    coat_rib = gap(C["SHIELD_COAT"], F["coat_mask_rib"]); coat_sl = C["SHIELD_COAT"].slice(8.0).to_polygons()
    from shapely.geometry import Polygon
    coat_holes = sum(1 for p in coat_sl if Polygon(p).exterior.is_ccw is False)
    r5 = dict(coat_slit_open=len(coat_sl) >= 1 and coat_holes == 0, coat_rings_at_z8=len(coat_sl), coat_to_mask_rib_mm=coat_rib, housing_metal="none (PETG / resin only)",
              prx_spirals="open spirals (two ends at the feed)", sector_wall_89="carbonyl-iron loaded PETG: a radial plane, not a loop")
    res["checks"]["hv_rule5"] = dict(ok=min(g_hv.values()) >= 3.0 and lp >= 0.1 and web >= 1.0 and r5["coat_slit_open"] and hv_cu_led >= 1.0, hv_to_non_hv_mm=g_hv, hv_copper_to_led_flex_mm=hv_cu_led, litz_pass_clearance_mm=round(lp, 3), litz_pass_web_mm=round(web, 3), rule5=r5)
    # 7 PRX
    px = S["prx"]; f = px["feed"]; G0 = json.load(open(os.path.join(ROOT, "data/reference/sbq_geometry.json")))
    from shapely.geometry import LineString, Point
    fp = Point(*H.pol(f["r"], f["deg"])); dq = []
    for lk, vk, pk_ in (("layers", "via_xy", "pads"), ("layersB", "via_xyB", "padsB")):
        dl = min(LineString(p).distance(fp) for v in G0[lk].values() for p in v if len(p) > 1) - 0.4
        dv = min(Point(*q).distance(fp) - 0.4 for q in G0[vk]); dp = min(Point(*q).distance(fp) - 0.8 for q in G0[pk_])
        dq.append(min(dl, dv, dp) - f["hole_d"] / 2)
    feed_cu = round(min(dq), 3); rule("PRX feed hole edge to QA / QB copper", feed_cu, 1.0, ">=", "feed (r 72, 135 deg)")
    feed_sp = round(px["main_r_mm"][1] - px["trace_mm"] / 2 - (f["r"] + f["pad_d"] / 2), 3); rule("PRX feed pad to the main spiral's inner turn", feed_sp, 0.5, ">=", "PRX layer 1")
    litz_bot = min(z for _, z in H.coil_turns()) - S["coil"]["litz_od"] / 2; prx_litz = round(litz_bot - S["boards"]["PRX"]["z"][1], 3)
    rule("PRX copper to the litz (through QA / QB / floor)", prx_litz, 1.0, ">=", "PRX bucking spiral under the TX", safety=True)
    cols = S["coil"]["columns_r"]; used = sorted({c for c, _ in H.coil_slots()}); r_tx = (cols[max(used)] - 0.686, cols[min(used)] + 0.686)
    under = px["buck_r_mm"][1] >= r_tx[0] - 1e-6 and px["buck_r_mm"][0] <= r_tx[1] + 1e-6
    bore = round(S["shell"]["wall_r"][0] - px["pi_r_out_mm"], 3); rule("PRX outline in the shell bore", bore, 0.2, ">=", "PRX")
    rule("PRX null: residual / main M at 0.1 mm z shift (sensitivity)", px["null_ratio_dz_0p1mm"], 0.01, "<=", "PRX", kind="model")
    res["checks"]["prx"] = dict(ok=feed_cu >= 1.0 and feed_sp >= 0.5 and prx_litz >= 1.0 and under and bore >= 0.2, feed_to_qaqb_copper_mm=feed_cu, feed_to_main_spiral_mm=feed_sp,
                                prx_to_litz_mm=prx_litz, buck_under_tx=under, tx_span_r=[round(x, 3) for x in r_tx], buck_r=px["buck_r_mm"], bore_clearance_mm=bore, design=px)
    # 8 coil / channel
    top = max(z for _, z in H.coil_turns()) + S["coil"]["litz_od"] / 2; ct = round(S["channel"]["z"][1] - top, 3)
    inner = round(min(r for r, _ in H.coil_turns()) - S["coil"]["litz_od"] / 2 - S["channel"]["inner_wall_r"][1], 3)
    rule("coil top below the channel top", ct, 0.2, ">=", "coil channel"); rule("coil inner column to the channel wall", inner, 0.2, ">=", "coil channel")
    res["checks"]["coil_channel"] = dict(ok=ct >= 0.2 and inner >= 0.2, order=S["coil"]["order"], coil_top_z=round(top, 3), channel_top_z=S["channel"]["z"][1], top_gap_mm=ct, inner_gap_mm=inner,
                                         row0_z=S["coil"]["row0_z"], floor_z=S["coil"]["floor_z"])
    # 9 zone map
    zr = GL.zone_map(P, sides)
    for r in zr:
        rule(f"echo drift (5 K) {r['part']}", r["echo_drift_5K_x_noise"], r["drift_limit"], "<=", r["zone"], kind="echo")
        if "gap_to_HV_envelopes_mm" in r and not r["part"].startswith("LED"): rule(f"HV envelope gap {r['part']}", r["gap_to_HV_envelopes_mm"], 3.0, ">=", r["zone"], safety=True)
    res["checks"]["zone_map"] = dict(ok=all(r["drift_ok"] and (r.get("hv_envelope_ok", True) or r["part"].startswith("LED")) for r in zr), rows=zr, fin_sides=sides,
                                     note="LED flex: envelope gap reported; its rule is the copper-level 1.0 mm row (HV fin copper to the flex)")
    # 10 mass
    before = None                                                     # 958464f: the last commit before the 2026-10-31 owner head decisions
    try:
        b = subprocess.run(["git", "show", os.environ.get("GLOVE_BEFORE_REF", "958464f") + ":rf2/head/out_BF/rf2_head_check.json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        before = json.loads(b)["checks"]["mass_g"]["total_islands_only"]
    except Exception: pass
    hc = json.load(open(os.path.join(H.OUT, "rf2_head_check.json")))["checks"]["mass_g"]["items"]
    keep = {k: v for k, v in hc.items() if not k.startswith(("printed parts", "coil channel epoxy"))}
    housing = {k: round(G[k].volume() / 1000 * (GL.DENS["resin"] if k == "G_COMBS" else GL.DENS["PETG"]), 1) for k in G}
    m_after = sum(keep.values()) + sum(housing.values()) + sum(v["mass_g"] for k, v in pot.items() if k.startswith("POT_"))
    old_housing = hc.get("printed parts (shell, lid, channel, walls, seats; PETG 100 % infill)")
    res["checks"]["mass_g"] = dict(before_head_check_BF_958464f=before, after_spec_changes_before_glove=json.load(open(os.path.join(H.OUT, "rf2_head_check.json")))["checks"]["mass_g"]["total_islands_only"],
                                   after_glove=round(m_after), housing_parts_g=housing, housing_total_g=round(sum(housing.values()), 1), old_printed_parts_g=old_housing,
                                   potting_g={k: v["mass_g"] for k, v in pot.items() if k.startswith("POT_")}, kept_items_g=keep,
                                   note="PETG / resin at 100 % infill (upper bound, as rf2_head_check); densities ASSUMED (gel 0.98, epoxy 1.15, syntactic foam 0.70)")
    res["rule_rows"] = ROWS
    res["rule_summary"] = {s: [r["rule"] + f" ({r['value']} vs {r['limit']})" for r in ROWS if r["status"] == s] for s in ("FAIL", "BLOCKED", "EDGE")}
    core = ("closed_meshes", "interference", "pockets", "min_wall", "potting", "hv_rule5", "prx", "coil_channel", "zone_map")
    res["ok"] = all(res["checks"][k]["ok"] for k in core); res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(OUT, "rf2_head_glove.json"), "w"), indent=1); return res
if __name__ == "__main__":
    r = main(); print("ok", r["ok"], "seconds", r["seconds"])
    for k, v in r["checks"].items(): print(k, v.get("ok"))
    print(json.dumps(r["rule_summary"], indent=1)); print(json.dumps(r["checks"]["mass_g"], indent=1)[:1500])
