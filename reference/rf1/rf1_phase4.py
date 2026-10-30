#!/usr/bin/env python3
"""RF1 phase 4 (2026-10-29): the head rigid-flex definition. Side experiment, MODELED; nothing ordered.
1. Stackup: every rigid section 6 layers (AB1A, AB1B, CB1D as today; LB1 goes 4 -> 6), the flex core = In2 / In3 of the rigid stack, so the hinge signals
   leave the rigid sections on In2 (a routing layer on AB1 and CB1D today) over a hatched In3 ground; flex finished 0.2 mm (Rigiflex 10-layer page), rigid 1.6 mm.
2. Flattened panel: CB1D disc at the origin, LB1 across its 15.2 mm S-fold hinge, AB1A / AB1B at the ends of their duct hinges (lengths from link_path_check,
   phase 1); HTA stays a separate 4-layer board with a hot-bar flex tail (it sits under the removable roof). Panel extent against the vendor 18 x 24 in.
3. Fold / transition rules (RF1 rule set, ASSUMED until the vendor and IPC-2223 confirm) and a check of the routed RF1 AB1 (build_ab1/out_board) against
   rule F1: no via within 1.0 mm of the rigid-flex transition at the hinge exit.
4. CB1D section part changes for the condensed L5 (rf1_cavity.py): what leaves, what comes in, and a fit of the new parts into the area the old ones free.
usage (repo root, after rf1_cavity.py and the RF1 AB1 route): python3 experiments/RF1_rigidflex/rf1_phase4.py"""
import os, json, math, csv
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "results")
P1 = json.load(open(os.path.join(OUT, "rf1_phase1.json")))

STACK = [  # name, material, thickness mm, rigid-only?
    ("L1 F.Cu", "Cu 1 oz + plating", 0.045, True), ("prepreg (no-flow)", "FR4", 0.20, True), ("L2 In1.Cu GND (hatched)", "Cu 1/2 oz", 0.018, True),
    ("core", "FR4", 0.42, True), ("bond ply", "acrylic-free adhesive", 0.025, True), ("coverlay", "polyimide 25 um + adhesive 25 um", 0.050, False),
    ("L3 In2.Cu signals / hinge traces", "Cu 1/2 oz RA", 0.018, False), ("flex core", "polyimide 50 um (er 4, DF 0.04)", 0.050, False),
    ("L4 In3.Cu hatched GND in the flex", "Cu 1/2 oz RA", 0.018, False), ("coverlay", "polyimide 25 um + adhesive 25 um", 0.050, False),
    ("bond ply", "acrylic-free adhesive", 0.025, True), ("core", "FR4", 0.42, True), ("L5 In4.Cu plane / island", "Cu 1/2 oz", 0.018, True),
    ("prepreg (no-flow)", "FR4", 0.20, True), ("L6 B.Cu", "Cu 1 oz + plating", 0.045, True)]
RULES = [
    ("F1", "no via, plated hole or pad within 1.0 mm of a rigid-flex transition line"),
    ("F2", "traces cross every fold line at 90 deg; no trace corners, neck-downs or width changes inside a bend zone (fold line +- 2 mm)"),
    ("F3", "flex ground = cross-hatch at 45 deg (eddy rule 5, and it bends); no solid copper in the flex"),
    ("F4", "minimum fold radius 2.0 mm (10 x 0.2 mm flex), static folds only (folded once at assembly)"),
    ("F5", "stiffeners FR4 or polyimide only: no stainless or aluminium (closed metal near the coils, rule 5)"),
    ("F6", "no 460 V net on any flex (rule 6): COIL_A / COIL_B stay AWG22 600 V wire into CB1D JCL"),
    ("F7", "the bend region of every hinge stays outside the potting pours (no rigid compound across a fold); the hinge roots may be in gel"),
    ("F8", "signal / ground interleave on the hinge: every analog line (MONO_IN, VCM_OUT, receive tails) has a ground trace on both sides (phase 2 crosstalk model)")]

def stack_summary():
    rigid = sum(t for _, _, t, _ in STACK); flex = sum(t for _, _, t, r in STACK if not r)
    return dict(layers=[dict(name=n, material=m, t_mm=t, in_flex=not r) for n, m, t, r in STACK], rigid_mm=round(rigid, 3), flex_mm=round(flex, 3),
                note="rigid sections keep the 6-layer roles of AB1 / CB1D (F, In1 GND, In2, In3, In4 plane, B); LB1 4 -> 6 layers; the vendor builds 6L rigid-flex at 1.6 mm, 1 oz")

def panel():
    lens = P1["ab1_cb1d_hinges"]["rigid-flex hinge from the board edge (RF1)"]["route_length_mm"]; lb = P1["hinges_up"][0]["flex_length_mm"]
    R_CB, R_LB, R_AB, W = 39.0, 39.0, 20.0, 7.0
    sec = {"CB1D": (0.0, 0.0, R_CB), "LB1": (0.0, R_CB + lb + R_LB, R_LB)}
    XA = W / 2 + 1.0 + W / 2 + 1.0                                                          # AB1 hinge roots on the CB1D duct edge, either side of the LB1 hinge (1 mm gaps)
    y_root = math.sqrt(R_CB ** 2 - XA ** 2); yh = R_CB + 3.0 + W / 2                        # strips turn sideways between CB1D and the LB1 disc
    la, lbb = lens["JA-AB1A.J2"], lens["JB-AB1B.J2"]; up = yh - y_root
    sec["AB1A"] = (-(XA + (la - up) + R_AB), yh, R_AB); sec["AB1B"] = (XA + (lbb - up) + R_AB, yh, R_AB)
    STRIPS = [("AB1A", -XA, y_root, yh, sec["AB1A"][0] + R_AB), ("AB1B", XA, y_root, yh, sec["AB1B"][0] - R_AB)]
    xs = [x - r for x, y, r in sec.values()] + [x + r for x, y, r in sec.values()]; ys = [y - r for x, y, r in sec.values()] + [y + r for x, y, r in sec.values()]
    ext = (max(xs) - min(xs), max(ys) - min(ys))
    hinges = [dict(name="CB1D-LB1", length_mm=lb, width_mm=W, from_="CB1D duct edge", to="LB1 duct edge", folds=2),
              dict(name="CB1D-AB1A", length_mm=la, width_mm=W, folds=4, note="duct route: AB1 lane, AB1 comb window, duct, CB1D comb window"),
              dict(name="CB1D-AB1B", length_mm=lbb, width_mm=W, folds=4)]
    def lb1_low(x): return sec["LB1"][1] - math.sqrt(max(R_LB ** 2 - x ** 2, 0.0)) if abs(x) < R_LB else 1e9
    overlap = any(yh + W / 2 > lb1_low(x) for x in [XA + t for t in range(0, 40)] + [-XA - t for t in range(0, 40)]) or XA - W / 2 < W / 2 + 0.5
    fits = ext[0] <= 18 * 25.4 and ext[1] <= 24 * 25.4 or ext[0] <= 24 * 25.4 and ext[1] <= 18 * 25.4
    area = sum(math.pi * r * r for *_, r in sec.values()) + sum(h["length_mm"] * W for h in hinges)
    return dict(sections={k: dict(cx=round(v[0], 1), cy=round(v[1], 1), r=v[2]) for k, v in sec.items()}, hinges=hinges, strips=[dict(to=t, x_root=x0, y_root=round(y0, 2), y_turn=y1, x_end=round(x1, 1)) for t, x0, y0, y1, x1 in STRIPS], extent_mm=[round(e, 1) for e in ext],
                fits_18x24in=fits, hinge_strip_clear_of_LB1=not overlap, copper_area_mm2=round(area), panel_use_pct=round(100 * area / (ext[0] * ext[1]), 1),
                hta="separate 4-layer board, 2-layer flex tail (about 21 mm, phase 1) hot-bar bonded to LB1: keeps the roof removable")

def keepout_ab1():
    out = {}
    for B in ("A", "B"):
        p = os.path.join(HERE, "build_ab1", f"final_{B}", "out_board", f"AB1{B}_layout.json")
        if not os.path.exists(p): p = os.path.join(HERE, "build_ab1", "out_board", f"AB1{B}_layout.json")
        if not os.path.exists(p): out[B] = dict(state="not routed yet"); continue
        L = json.load(open(p)); jx, jy = L["PLACE"]["J2"][0], L["PLACE"]["J2"][1]
        # the holes are read from the FINAL board (after Freerouting when it ran): KiCad frame = layout frame + (100, 100) mm, same axis directions (checked on AB1B: 53 of 53 vias match)
        pcb = os.path.join(HERE, "build_ab1", f"final_{B}", "kit_v3", f"PCB_AB1{B}", f"PF233-AB1{B}.kicad_pcb"); src = "layout"
        holes = [(v[0], v[1], "via") for v in L["VIAS"]]
        if os.path.exists(pcb):
            import pcbnew
            bd = pcbnew.LoadBoard(pcb); M = pcbnew.ToMM; src = "final kicad_pcb"
            holes = [(M(t.GetPosition().x) - 100, M(t.GetPosition().y) - 100, "via") for t in bd.GetTracks() if t.GetClass() == "PCB_VIA"]
            holes += [(M(q.GetPosition().x) - 100, M(q.GetPosition().y) - 100, "pth " + q.GetParentFootprint().GetReference()) for q in bd.GetPads()
                      if q.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and q.GetParentFootprint().GetReference() != "J2"]      # the J2 hinge lands sit on the transition by design
        # transition line: the board edge beyond the J2 land row (the hinge leaves the disc there); zone = 1.0 mm band inside the edge over the hinge width
        bad = []
        for x, y, kind in holes:
            r = math.hypot(x, y)
            if abs(y - jy) <= 3.5 + 1.0 and x > jx and r > 20.0 - 1.0 - 0.3: bad.append((round(x, 2), round(y, 2), kind))      # east-edge exit (lands rot 90 at x 15.6)
        rep = L.get("rep", {}); rr = os.path.join(HERE, "results", "rf1_ab1_route.json")
        fin = json.load(open(rr))["boards"].get(B, {}) if os.path.exists(rr) else {}
        out[B] = dict(state="routed", source=src, vias=sum(1 for h in holes if h[2] == "via"), plated_holes=sum(1 for h in holes if h[2] != "via"), vias_in_F1_zone=bad, F1_ok=not bad,
                      open_final=fin.get("open"), router_unrouted=rep.get("unrouted", rep.get("failed")))
    return out

def cb1d_changes():
    W = os.path.join(ROOT, "work")
    pp = {r["Ref"]: r for r in csv.DictReader(open(os.path.join(W, "kit_v18/CB1D/PF233-CB1D_pickplace.csv")))}
    out_ = [dict(ref="U1", was="Raspberry Pi Pico 2 W module on pins (21 x 51 mm, 8 mm tall, CYW43439 radio)", freed_mm=(51.0, 21.0), at=(float(pp["U1"]["PosX_mm"]), float(pp["U1"]["PosY_mm"]))),
            dict(ref="M5", was="Murata OKI-78SR 5 V module (SIP, 10.2 mm tall)", freed_mm=(11.5, 8.5), at=(float(pp["M5"]["PosX_mm"]), float(pp["M5"]["PosY_mm"]))),
            dict(ref="JA / JB / JLB / JHTA", was="1.27 mm headers and wire pads", freed_mm=None, at=None)]
    new = [  # ref, part, footprint w x h (mm incl. courtyard), source
        ("U1", "RP2354A (RP2350, 2 MB flash in package), QFN-60 7 x 7", (8.0, 8.0), "RP2350 datasheet, build 01/10/2026 (Table 1, 14.1)"),
        ("Y1", "12 MHz crystal 3.2 x 2.5", (4.0, 3.2), "RP2350 datasheet: bootloader expects 12 MHz"),
        ("LV1", "RP2350 core regulator inductor (value per the RP2350 hardware design section: to read)", (3.0, 3.0), "UNVERIFIED value"),
        ("U3V", "TI TLV755P 3.3 V 500 mA LDO, SOT-23-5 (VREG_AVDD / IOVDD 3.3 V from +5V)", (3.6, 3.4), "TI SBVS320D (on disk)"),
        ("C*", "RP2350 decoupling, 14 x 0402 (count to be taken from the hardware design section)", (6.0, 4.0), "UNVERIFIED count"),
        ("U5", "TI LMR36015 4.2-60 V 1.5 A buck, VQFN-HR 2 x 3 (replaces M5)", (3.4, 4.0), "TI SNVSB49D"),
        ("L5", "Bourns SRN4018-6R8M 6.8 uH, Isat 1.6 A", (4.6, 4.6), "Bourns SRN4018 (on disk)"),
        ("C5*", "buck input 2 x 2.2 uF 50 V 1206, output 2 x 22 uF 10 V 1206, boot 0.1 uF", (8.0, 4.0), "values per the LMR36015 design section: to size")]
    a_free_pico = 51.0 * 21.0; a_new_mcu = sum(w * h for r, _, (w, h), _ in new if r in ("U1", "Y1", "LV1", "U3V", "C*"))
    a_free_oki = 11.5 * 8.5; a_new_buck = sum(w * h for r, _, (w, h), _ in new if r in ("U5", "L5", "C5*"))
    return dict(removed=out_, added=[dict(ref=r, part=p, w_h_mm=wh, source=s) for r, p, wh, s in new],
                area_check=dict(pico_freed_mm2=a_free_pico, mcu_cluster_mm2=round(a_new_mcu, 1), oki_freed_mm2=a_free_oki, buck_cluster_mm2=round(a_new_buck, 1),
                                fits=a_new_mcu <= 0.5 * a_free_pico and a_new_buck <= a_free_oki),
                note="placement-level only: CB1D is not re-routed in phase 4 (phase 5); the radio goes (OPEN_ITEMS 42 settled by removal); firmware keeps the RP2350 core")

def cb1d_map():
    """placement-level map of the CB1D rigid section: baseline part boxes (pick-and-place + lib bodies), the removed parts, and the new clusters placed in the
    freed areas; every new box must clear every kept box by 0.3 mm and stay inside r 38.5 (D78 board, 0.5 mm edge keep)"""
    W = os.path.join(ROOT, "work"); LIBJ = json.load(open(os.path.join(W, "kit_v19/lib_bodies.json"))); typ = {}
    for r in list(csv.reader(open(os.path.join(W, "kit_v18/CB1D/PF233-CB1D_BOM.csv"))))[1:]:
        for ref in r[1].split(","): typ[ref.strip()] = r[2]
    gone = {"U1", "M5", "JA", "JB", "JLB", "JHTA"}; keep, rem = [], []
    for r in csv.DictReader(open(os.path.join(W, "kit_v18/CB1D/PF233-CB1D_pickplace.csv"))):
        t = typ.get(r["Ref"]); w, h = (LIBJ[t][0], LIBJ[t][1]) if t in LIBJ else (1.0, 0.5)
        if r["Ref"] == "U1": w, h = 21.0, 51.0                                                   # Pico footprint long along y at rot 0 (pw_design _pico)
        if int(float(r["Rot"])) % 180 == 90: w, h = h, w
        x, y = -float(r["PosX_mm"]), -float(r["PosY_mm"])                                        # pickplace y-up, CB1D mounted rotated 180 deg (hub frame)
        (rem if r["Ref"] in gone else keep).append(dict(ref=r["Ref"], x=x, y=y, w=w, h=h, side=r["Side"]))
    U1 = next(p for p in rem if p["ref"] == "U1"); M5 = next(p for p in rem if p["ref"] == "M5")
    new = [("U1 RP2354A", U1["x"] - 6.0, U1["y"], 8.0, 8.0), ("Y1 12 MHz", U1["x"] + 1.0, U1["y"] + 2.5, 4.0, 3.2), ("LV1 core L", U1["x"] + 1.0, U1["y"] - 2.5, 3.0, 3.0),
           ("U3V TLV755P", U1["x"] + 6.0, U1["y"] + 2.5, 3.6, 3.4), ("C* decoupling", U1["x"] + 6.0, U1["y"] - 2.6, 6.0, 4.0),
           ("U5 LMR36015", M5["x"] - 2.5, M5["y"] + 1.5, 3.4, 4.0), ("L5 SRN4018", M5["x"] + 1.8, M5["y"] + 1.5, 4.6, 4.6), ("C5* buck caps", M5["x"], M5["y"] - 2.6, 8.0, 3.0)]
    def ov(a, b, m=0.3): return abs(a[0] - b[0]) < (a[2] + b[2]) / 2 + m and abs(a[1] - b[1]) < (a[3] + b[3]) / 2 + m
    res = []
    for nm, x, y, w, h in new:
        hits = [k["ref"] for k in keep if k["side"] == "top" and ov((x, y, w, h), (k["x"], k["y"], k["w"], k["h"]))]
        rmax = max(math.hypot(x + sx * w / 2, y + sy * h / 2) for sx in (-1, 1) for sy in (-1, 1))
        res.append(dict(part=nm, x=round(x, 2), y=round(y, 2), w=w, h=h, collides_with=hits, inside_board=rmax <= 38.5))
    return dict(kept=keep, removed=rem, new=res, ok=all(not r["collides_with"] and r["inside_board"] for r in res))

def figure_cb1d(m):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    BLUE, ORANGE, INK, MUTED, GREEN = "#2a78d6", "#eb6834", "#1f2328", "#8a8f98", "#1baf7a"
    fig, ax = plt.subplots(figsize=(7.2, 7.2), dpi=150); ax.add_patch(Circle((0, 0), 39.0, fc="#f3f4f6", ec=INK, lw=0.8))
    for k in m["kept"]: ax.add_patch(Rectangle((k["x"] - k["w"] / 2, k["y"] - k["h"] / 2), k["w"], k["h"], fc=MUTED if k["side"] == "top" else "none", ec=MUTED, lw=0.4, alpha=0.6))
    for k in m["removed"]: ax.add_patch(Rectangle((k["x"] - k["w"] / 2, k["y"] - k["h"] / 2), k["w"], k["h"], fc="none", ec=ORANGE, lw=1.0, ls="--")); ax.text(k["x"], k["y"] + k["h"] / 2 + 0.6, k["ref"] + " (removed)", ha="center", fontsize=6, color=ORANGE)
    for n in m["new"]:
        c = GREEN if not n["collides_with"] and n["inside_board"] else "#d03b3b"
        ax.add_patch(Rectangle((n["x"] - n["w"] / 2, n["y"] - n["h"] / 2), n["w"], n["h"], fc=c, ec=INK, lw=0.4)); ax.text(n["x"], n["y"], n["part"].split(" ")[0], ha="center", va="center", fontsize=5.5, color="white")
    ax.set_aspect("equal"); ax.set_xlim(-41, 41); ax.set_ylim(-41, 41); ax.axis("off")
    ax.set_title("RF1 CB1D section: removed (dashed), kept (grey), new clusters (green) - placement level, MODELED", fontsize=8.5, loc="left", color=INK)
    fig.savefig(os.path.join(OUT, "rf1_cb1d_section.png"))

def figure(pn, st):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    BLUE, ORANGE, INK, MUTED, GOLD = "#2a78d6", "#eb6834", "#1f2328", "#8a8f98", "#eda100"
    fig = plt.figure(figsize=(11, 6.6), dpi=150); ax = fig.add_axes([0.04, 0.08, 0.6, 0.84]); ax2 = fig.add_axes([0.68, 0.08, 0.3, 0.84])
    S = pn["sections"]
    for k, v in S.items():
        ax.add_patch(Circle((v["cx"], v["cy"]), v["r"], fc=BLUE, ec=INK, lw=0.6, alpha=0.85)); ax.text(v["cx"], v["cy"], k, ha="center", va="center", color="white", fontsize=9)
    W = 7.0
    for st_ in pn["strips"]:
        x0, y0, y1, x1 = st_["x_root"], st_["y_root"], st_["y_turn"], st_["x_end"]
        ax.add_patch(Rectangle((x0 - W / 2, y0 - 0.5), W, y1 - y0 + W / 2 + 0.5, fc=ORANGE, ec="none"))
        ax.add_patch(Rectangle((min(x0, x1), y1 - W / 2), abs(x1 - x0), W, fc=ORANGE, ec="none"))
        ax.plot([x1, x1], [y1 - 6, y1 + 6], color=GOLD, ls="--", lw=1); ax.plot([x0 - 5, x0 + 5], [y0, y0], color=GOLD, ls="--", lw=1)
    ax.add_patch(Rectangle((-W / 2, S["CB1D"]["r"] - 0.5), W, S["LB1"]["cy"] - S["LB1"]["r"] - S["CB1D"]["r"] + 1.0, fc=ORANGE, ec="none"))
    for y in (S["CB1D"]["r"], S["LB1"]["cy"] - S["LB1"]["r"]): ax.plot([-8, 8], [y, y], color=GOLD, ls="--", lw=1)
    ax.text(0, -S["CB1D"]["r"] - 3, f"flattened panel {pn['extent_mm'][0]} x {pn['extent_mm'][1]} mm (vendor 457 x 610): fits; copper {pn['panel_use_pct']} % of the box\n"
            "orange = 2-layer flex hinges (0.2 mm), dashed = rigid-flex transitions (rule F1: no via within 1 mm)", ha="center", va="top", fontsize=7.5, color=INK)
    ax.set_aspect("equal"); ax.autoscale_view(); ax.set_xlim(min(v["cx"] - v["r"] for v in S.values()) - 5, max(v["cx"] + v["r"] for v in S.values()) + 5)
    ax.set_ylim(-S["CB1D"]["r"] - 18, S["LB1"]["cy"] + S["LB1"]["r"] + 5); ax.axis("off"); ax.set_title("RF1 head rigid-flex, flattened (MODELED)", fontsize=10, loc="left", color=INK)
    y = 0.0
    for L in reversed(st["layers"]):
        t = L["t_mm"]; c = ORANGE if L["in_flex"] and "Cu" in L["name"] else (BLUE if "Cu" in L["name"] else ("#f2c9a8" if L["in_flex"] else "#d9dde3"))
        ax2.add_patch(Rectangle((0, y), 1, t, fc=c, ec="white", lw=0.3)); ax2.text(1.05, y + t / 2, f"{L['name']} · {L['t_mm']} mm", va="center", fontsize=6.5, color=INK); y += t
    ax2.set_xlim(0, 3.2); ax2.set_ylim(-0.05, y + 0.05); ax2.axis("off")
    ax2.set_title(f"stackup: rigid {st['rigid_mm']} mm, flex {st['flex_mm']} mm\n(orange rows continue into the hinges)", fontsize=8.5, loc="left", color=INK)
    fig.savefig(os.path.join(OUT, "rf1_rigidflex_panel.png"))

if __name__ == "__main__":
    st = stack_summary(); pn = panel(); ko = keepout_ab1(); cb = cb1d_changes(); cm = cb1d_map(); figure_cb1d(cm)
    out = dict(status="MODELED (RF1 phase 4, side experiment)", stackup=st, panel=pn, rules=[dict(id=i, rule=r) for i, r in RULES], ab1_F1_check=ko, cb1d_section=cb, cb1d_map=dict(new=cm["new"], ok=cm["ok"], removed=[r["ref"] for r in cm["removed"]]))
    json.dump(out, open(os.path.join(OUT, "rf1_phase4.json"), "w"), indent=1); figure(pn, st)
    print("stack", st["rigid_mm"], st["flex_mm"]); print("panel", pn["extent_mm"], pn["fits_18x24in"], pn["hinge_strip_clear_of_LB1"], pn["panel_use_pct"])
    print("F1", ko); print("cb1d area", cb["area_check"]); print("cb1d map ok", cm["ok"], [(n["part"], n["collides_with"], n["inside_board"]) for n in cm["new"]])
