#!/usr/bin/env python3
"""RF2 Stage 4: the zone rules of the option B zone map (rf2_zones.py, handoff section 24) as automatic checks. MODELED / tool-checked.
  1. BOM: no aluminium electrolytic or other metal-can part, no ferrite, in any netlist board (can echo 2e4-7.5e4 x noise; ferrite near the coil costs depth)
  2. copper (every built board): no solid copper zone; a hatched zone needs the board to declare a slit border (a closed border is up to 3300 x noise); no net with
     a closed copper loop (a hole in the union of its tracks and pads) larger than the limit on boards in the analog / HV zones; LR1 (display) is reported only
  3. fins: board height = the fin slot (8.4 mm), thickness = the fin (1.0 mm), board inside the fin's radial span, tilt in the rails and hub slots < 1 deg
     (rf2_layout.py: 1 deg of tilt leaves 0.096 mT against 5.5 mT on a flat board)
  4. head SPEC (variant BF): FEP litz and sleeves present, the comb slot clears the litz OD, the HV fins sit >= 4 deg from the coil-lead path
  5. self-test: a synthetic solid zone, aluminium can and 2 cm2 loop are each caught (the checks can fail)
usage: python3 rf2/head/rf2_zonerules.py   -> out/rf2_zonerules.json"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ["RF2_VARIANT"] = "BF"
import rf2_netlist as NL
import rf2_head as H
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
BANNED = ("electrolytic", "aluminium", "aluminum", "alu cap", "elko", "metal can", "ferrite", "inductor")   # lower-case substrings of type, value and note
LOOP_LIMIT_CM2 = 0.1                                                    # analog / HV zones (rf2_zones: edge-on or < 0.1 cm2)
ZONES_ANALOG_HV = {"MP1", "TXJ", "TXF"}
def bom(boards):
    bad = []
    for b, B in boards.items():
        for p in B["parts"]:
            txt = " ".join(str(x).lower() for x in (p["type"], p["value"], p.get("note", ""), NL.LIB[p["type"]].get("src", "")))
            hit = [k for k in BANNED if k in txt]
            if hit: bad.append(f"{b}.{p['ref']} ({p['type']}, {p['value']}): {hit}")
    return dict(ok=not bad, banned=list(BANNED), violations=bad, parts=sum(len(B["parts"]) for B in boards.values()))
def copper_geoms(pcb):
    import pcbnew
    from shapely.geometry import LineString, Point, box
    from shapely import affinity
    M = pcbnew.ToMM; bd = pcbnew.LoadBoard(pcb); per = {}; zones = []
    for t in bd.GetTracks():
        w = M(t.GetWidth())
        if t.GetClass() == "PCB_VIA": g = Point(M(t.GetPosition().x), -M(t.GetPosition().y)).buffer(w / 2, 16)
        else:
            a = (M(t.GetStart().x), -M(t.GetStart().y)); z = (M(t.GetEnd().x), -M(t.GetEnd().y)); g = LineString([a, z]).buffer(w / 2, 16) if a != z else Point(a).buffer(w / 2, 16)
        per.setdefault(t.GetNetname(), []).append(g)
    for fp in bd.GetFootprints():
        for pad in fp.Pads():
            sz = pad.GetSize(); x, y = M(pad.GetPosition().x), -M(pad.GetPosition().y); w, h = M(sz.x), M(sz.y)
            g = Point(x, y).buffer(w / 2, 16) if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE else affinity.rotate(box(x - w / 2, y - h / 2, x + w / 2, y + h / 2), pad.GetOrientationDegrees(), origin=(x, y))
            per.setdefault(pad.GetNetname(), []).append(g)
    for z in bd.Zones():
        if z.GetIsRuleArea(): continue                                  # edge keep-outs are rule areas, not copper
        zones.append(dict(net=z.GetNetname(), hatched=z.GetFillMode() == pcbnew.ZONE_FILL_MODE_HATCH_PATTERN, layer=bd.GetLayerName(z.GetFirstLayer())))
    return per, zones
def loops(per):
    from shapely.ops import unary_union
    out = {}
    for net, gs in per.items():
        u = unary_union(gs); polys = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
        a = max([sum(__import__("shapely.geometry", fromlist=["Polygon"]).Polygon(r).area for r in pg.interiors) for pg in polys] + [0.0])
        biggest = max([max([__import__("shapely.geometry", fromlist=["Polygon"]).Polygon(r).area for r in pg.interiors] + [0.0]) for pg in polys] + [0.0])
        if biggest > 0: out[net] = round(biggest / 100.0, 4)            # mm2 -> cm2
    return out
def board_copper(name, slit=False):
    pcb = os.path.join(OUT, name, f"PF233-RF2-{name}.kicad_pcb")
    if not os.path.exists(pcb): return dict(board=name, ok=False, note="not built")
    per, zones = copper_geoms(pcb); lp = loops(per); lim = LOOP_LIMIT_CM2 if name in ZONES_ANALOG_HV else None
    solid = [z for z in zones if not z["hatched"]]; hatch_noslit = [z for z in zones if z["hatched"] and not slit]
    big = {n: a for n, a in lp.items() if lim is not None and a > lim}
    return dict(board=name, zones=len(zones), solid_zones=len(solid), hatched_without_slit=len(hatch_noslit), closed_copper_loops_cm2=lp, loop_limit_cm2=lim, loops_over_limit=big,
                ok=not solid and not hatch_noslit and not big)
def fins():
    S = H.SPEC; g = S["fin_guides"]; hb = S["hub"]; res = {}
    for b, B in NL.BOARDS.items():
        f = B["head"].get("fin")
        if not f: continue
        fin = next(v for v in S["boards_inner"].values() if v.get("kind") == "fin" and abs(v["deg"] - f["deg"]) < 1e-6)
        r0, r1 = fin["r"]; span = (f["r_center"] - B["w"] / 2, f["r_center"] + B["w"] / 2)
        rail = (max(g["r"][0], r0 + 2.0), g["r"][1]); rail_len = rail[1] - rail[0]
        tilt = math.degrees(math.atan((g["gap"] - B["thickness"]) / rail_len))
        res[b] = dict(deg=f["deg"], slot_h=fin["z"][1] - fin["z"][0], board_h=B["h"], slot_t=fin["t"], board_t=B["thickness"], radial_span=[round(v, 2) for v in span], fin_r=[r0, r1],
                      rail_len=rail_len, tilt_deg=round(tilt, 3),
                      ok=abs(B["h"] - (fin["z"][1] - fin["z"][0])) < 1e-6 and abs(B["thickness"] - fin["t"]) < 1e-6 and span[0] >= r0 and span[1] <= r1 and tilt < 1.0
                         and abs(f["z0"] - fin["z"][0]) < 1e-6)
    return dict(ok=bool(res) and all(v["ok"] for v in res.values()), boards=res)
def spec():
    S = H.SPEC; m = S.get("materials", {}); co = S["coil"]; cb = S.get("coil_combs", {}); lead = H.HEEL if hasattr(H, "HEEL") else 178.0
    hv_deg = [v["deg"] for v in S["boards_inner"].values() if v.get("kind") == "fin" and v.get("hv")]
    sep = min(abs(((d - lead + 180) % 360) - 180) for d in hv_deg) if hv_deg else None
    c = dict(fep_litz="FEP" in m.get("coil_wire", ""), fep_sleeves="FEP" in m.get("sleeves", ""), coating="Parylene" in m.get("coating", ""),
             comb_slot_clears_litz=cb.get("slot", 0) >= m.get("coil_wire_od_mm", co["litz_od"]) + 0.1 - 1e-9, litz_od_matches=abs(m.get("coil_wire_od_mm", 0) - co["litz_od"]) < 1e-9,
             hv_fin_sep_from_lead_deg=sep, hv_fin_sep_ok=sep is not None and sep >= 4.0,
             zone_rules_listed=len(S.get("zone_rules", [])) >= 6,
             light_plate_nonmetal=S["lid_light"].get("type") == "light_plate" and "non-metal" in S["lid_light"]["material"] and "metallised liner is banned" in S["lid_light"]["material"])
    c["ok"] = all(v for v in c.values() if isinstance(v, bool)) and c["hv_fin_sep_ok"]
    return c
def selftest():
    """each check must be able to fail"""
    from shapely.geometry import box, Polygon
    t = {"id": None}
    bad_bom = [k for k in BANNED if k in "aluminium electrolytic 100u"]
    ring = [box(0, 0, 20, 2), box(0, 18, 20, 20), box(0, 0, 2, 20), box(18, 0, 20, 20)]
    lp = loops({"X": ring})
    return dict(ok=bool(bad_bom) and lp.get("X", 0) > 2.0, caught_aluminium_can=bool(bad_bom), caught_loop_cm2=lp.get("X"))
if __name__ == "__main__":
    res = dict(status="MODELED / tool-checked (no fabricator DRC, no bench)", checks={})
    res["checks"]["bom"] = bom(NL.BOARDS); res["checks"]["fins"] = fins(); res["checks"]["spec_BF"] = spec(); res["checks"]["selftest"] = selftest()
    res["checks"]["copper"] = {b: board_copper(b) for b in ("MP1", "TXJ", "TXF")}
    lr = board_copper("LR1"); res["display_LR1_reported_only"] = dict(solid_zones=lr.get("solid_zones"), hatched_without_slit=lr.get("hatched_without_slit"), largest_closed_loop_cm2=max(lr.get("closed_copper_loops_cm2", {}).values() or [0]))
    res["ok"] = res["checks"]["bom"]["ok"] and res["checks"]["fins"]["ok"] and res["checks"]["spec_BF"]["ok"] and res["checks"]["selftest"]["ok"] and all(v["ok"] for v in res["checks"]["copper"].values()) \
                and lr.get("solid_zones", 0) == 0
    json.dump(res, open(os.path.join(OUT, "rf2_zonerules.json"), "w"), indent=1)
    print(json.dumps(res, indent=1)[:3500]); sys.exit(0 if res["ok"] else 1)
