#!/usr/bin/env python3
"""RF1 side experiment, phase 1 (2026-10-29): could rigid-flex / flex replace the head's wires and headers, with every coil, antenna and printed part unchanged?
ISOLATED: reads the baseline (repo meshes in work/, board layouts, the harness) and never writes outside experiments/RF1_rigidflex/. No pipeline step, no regress row,
no generator is touched; the baseline commit and the sha256 of every input read are recorded in the result, so the study is a copy of the system by reference.
Answers, MODELED / mesh-checked (nothing built, no vendor quote):
  1. interconnect census: every head-internal wire, header pin and hand joint today, and which a flex concept removes
  2. fit on the meshes of the AB1 <-> CB1D hinges: src/mech/link_path_check.one() (imported unchanged) with a third concept, a rigid-flex hinge leaving the
     board edge (no connector, no socket: height 0), flex 0.2 mm thick (Rigiflex 10-layer rigid-flex page: "Finish thickness 0.2mm (flex)"), width 7.0 mm
  3. the CB1D -> LB1 hinge and the CB1D -> HTA tail: vertical rise, minimum fold radius >= 10 x flex thickness (the static-fold rule already used in OPEN_ITEMS 3;
     IPC-2223 and the vendor to confirm) and the free height for an S-fold
  4. receive-coil leads SB1R-QA/QB -> AB1A J1 (4 x AWG36, 60 mm): loop area and capacitance of today's pair vs a broadside flex pair (two traces stacked on a
     50 um polyimide core, Rigiflex flex table: single-sided 0.050 mm, polyimide er 4 / DF 0.04 at 1 MHz)
  5. eddy rule 5: do the hinges close a conductive loop around the head axis? (board graph: a cycle whose path encloses the axis)
  6. vendor fit: board sizes, trace / space, layer counts against the Rigiflex capability pages (owner-supplied PDFs, saved in this folder's ds/)
usage (repo root, after make setup / make signoff): python3 experiments/RF1_rigidflex/rf1_study.py"""
import os, sys, json, csv, math, hashlib, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
READ = {}
def rd(p):
    a = os.path.join(ROOT, p)
    if a not in READ: READ[a] = hashlib.sha256(open(a, "rb").read()).hexdigest()[:16]
    return a

FLEX_T, FLEX_W, BEND_K = 0.2, 7.0, 10.0          # flex thickness (vendor page), hinge width (12 signals + guard grounds on a 0.25 mm pitch + edges), fold radius / thickness
Z = dict(AB1_bot=11.1, AB1_top=12.7, SEPT_bot=20.1, CB1D_bot=27.0, CB1D_top=28.6, LB1_bot=39.2, LB1_top=40.0, HTA_bot=44.5, HTA_top=47.1)   # DESIGN_STATE / link_path_check

def census():
    """head-internal interconnects today, from HARNESS_MASTER_v5 and the AB1 <-> CB1D header link (2 x 12 pins, both ends)"""
    rows = list(csv.DictReader(open(rd("data/seed/harness/HARNESS_MASTER_v5.csv"))))
    head = ("CB1D.JLB", "LB1.", "CB1D.JHTA", "antenna board", "SB1R-Q", "AB1A.J1", "AB1B.J1")
    hw = [r for r in rows if any(k in r["from (board.connector.pin)"] + r["to (board.connector.pin)"] for k in head) and "damping" not in r["signal"]
          and r["from (board.connector.pin)"].split(".")[0] != r["to (board.connector.pin)"].split(".")[0]]
    grp = {}
    for r in hw:
        f, t = r["from (board.connector.pin)"], r["to (board.connector.pin)"]
        k = "CB1D-LB1" if "JLB" in f + t else ("CB1D-HTA" if "JHTA" in f + t else ("SB1R-AB1A" if "SB1R" in f + t else "other"))
        grp.setdefault(k, []).append(r["id"])
    link = dict(conductors=24, ends=48, note="CB1D JA/JB 2 x 6 at 1.27 mm <-> AB1A/AB1B J2: 12 conductors per link, two links")
    wires = sum(len(v) for v in grp.values())
    out = dict(harness_groups={k: dict(ids=v, n=len(v)) for k, v in grp.items()}, header_link=link, wires_today=wires + link["conductors"],
               hand_joints_today=2 * wires + link["ends"])
    # concept C (full head rigid-flex): AB1A, AB1B, CB1D, LB1 one panel; HTA a flex tail; SB1R leads a soldered flex jumper (2 bonded ends per coil board)
    out["concept_C_joints"] = dict(rigid_flex_internal=0, sb1r_jumpers=2 * 2, hta_tail_end=1, total=5)
    # concept B (soldered flex jumpers between separate rigid boards): AB1A-CB1D, AB1B-CB1D, CB1D-LB1, CB1D-HTA, SB1R-QA/QB-AB1A -> 6 jumpers x 2 bonded ends
    out["concept_B_joints"] = dict(jumpers=6, bonded_ends=12, total=12)
    return out

def hinges_ab1():
    sys.path.insert(0, os.path.join(ROOT, "src", "mech")); import link_path_check as L
    cwd = os.getcwd(); os.chdir(os.path.join(ROOT, "work"))
    for p in ("out_board/AB1A_layout.json", "out_board/AB1B_layout.json", "kit_v18/CB1D/PF233-CB1D_pickplace.csv", "kit_v18/CB1D/PF233-CB1D_BOM.csv", "kit_v19/lib_bodies.json",
              "kit_v22/SET/02_CORE_PCB_CYLINDER/CORE_CYLINDER_v5_integrated.stl", "kit_v22/SEPTUM_FRAME_v5.stl", "kit_v22/SPINE_COMB_v5.stl", "kit_v22/ANALOG_TRAY_v5.stl"):
        rd("work/" + p)
    res = {}
    try:
        for name, cp in {"IDC ribbon on the current 1.27 mm headers (baseline)": L.CONCEPTS["IDC ribbon on the current 1.27 mm headers"],
                         "catalog FFC with connectors (B12 decision)": L.CONCEPTS["FFC 0.5 mm with low-profile connectors at the duct-side board edges"],
                         "rigid-flex hinge from the board edge (RF1)": dict(w=FLEX_W, t=FLEX_T, sock=0.0, hdr_ab=0.0, hdr_cb=0.0, lanes=False)}.items():
            L.W_CAB, L.T_CAB, L.SOCKET_H = cp["w"], cp["t"], cp["sock"]
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()): r = L.one(cp)
            res[name] = dict(fails=r["n_fail"], checks=len(r["checks"]), route_length_mm=r["route_length_mm"],
                             failed=[c["check"][:120] + " | " + c["value"] for c in r["checks"] if c["result"] == "FAIL"],
                             height_margin_under_LB1_mm=round(Z["LB1_bot"] - (Z["CB1D_top"] + (9.0 if cp["hdr_cb"] is None else cp["hdr_cb"]) + cp["sock"] + cp["t"]), 2),
                             height_margin_under_septum_mm=round(Z["SEPT_bot"] - (Z["AB1_top"] + cp["hdr_ab"] + cp["sock"] + cp["t"]), 2))
    finally: os.chdir(cwd)
    return res

def hinge_up(name, z_from, z_to):
    """an S-fold from a board edge up to the next board edge: two folds of radius r >= BEND_K * t; needs rise >= 4 r for a full S"""
    r = BEND_K * FLEX_T; rise = z_to - z_from
    return dict(hinge=name, rise_mm=round(rise, 2), min_fold_radius_mm=r, s_fold_needs_mm=4 * r, ok=rise >= 4 * r,
                flex_length_mm=round(rise - 4 * r + 2 * math.pi * r, 1) if rise >= 4 * r else None)

def rx_tail():
    """loop area and capacitance of the receive-coil lead pair, 60 mm: today AWG36 (d 0.127 mm, about 0.02 mm enamel: centre spacing 0.17 mm when touching,
    loose dress up to 1 mm) vs a broadside flex pair (0.10 mm traces stacked on a 0.050 mm polyimide core, er 4)"""
    L_mm, d, eps0 = 60.0, 0.127, 8.854e-12
    wire = {}
    for lab, s, er in (("AWG36 pair touching", 0.17, 2.5), ("AWG36 pair, loose dress 1 mm", 1.0, 1.0)):
        C = math.pi * eps0 * er / math.acosh(s / d) * L_mm * 1e-3
        wire[lab] = dict(loop_area_mm2=round(L_mm * s, 1), C_pF=round(C * 1e12, 2))
    h, w, er = 0.050, 0.10, 4.0
    flex = dict(loop_area_mm2=round(L_mm * h, 1), C_pF=round(eps0 * er * (w * 1e-3) / (h * 1e-3) * L_mm * 1e-3 * 1e12 * 1.3, 2),
                note="parallel-plate x 1.3 for fringing; area fixed by the core, the same on every unit")
    return dict(length_mm=L_mm, wire=wire, flex_broadside=flex,
                area_ratio_vs_touching=round(flex["loop_area_mm2"] / wire["AWG36 pair touching"]["loop_area_mm2"], 2),
                area_ratio_vs_loose=round(flex["loop_area_mm2"] / wire["AWG36 pair, loose dress 1 mm"]["loop_area_mm2"], 3),
                caveat="area only: the leak and pickup need the TX field at the lead path (phase 2: sbq_sim with the tail geometry); a twisted pair cancels by twist, the flex by thinness")

def loops():
    """board graph of the head concept: an edge per hinge / jumper; a cycle that encloses the axis would be a closed conductive loop (eddy rule 5)"""
    pos = {"AB1A": (-20.3, 0.0), "AB1B": (20.3, 0.0), "CB1D": (0.0, 0.0), "LB1": (0.0, 0.0), "HTA": (0.0, 0.0), "SB1R-QA": (0.0, 0.0), "SB1R-QB": (0.0, 0.0)}
    E = [("AB1A", "CB1D"), ("AB1B", "CB1D"), ("CB1D", "LB1"), ("CB1D", "HTA"), ("SB1R-QA", "AB1A"), ("SB1R-QB", "AB1A")]
    par = {n: n for n in pos}
    def f(a):
        while par[a] != a: a = par[a]
        return a
    cyc = []
    for a, b in E:
        ra, rb = f(a), f(b)
        if ra == rb: cyc.append((a, b))
        else: par[ra] = rb
    return dict(edges=E, cycles=cyc, tree=not cyc, hinges_share_the_90deg_duct=True,
                note="a tree has no closed loop; the receive grounds (VCM) reach AB1A only, AB1B joins through CB1D. Planes inside each hinge are hatched (rule 5); "
                     "no stainless or aluminium stiffeners (the vendor offers both): FR4 or polyimide stiffeners only")

def vendor():
    return dict(source="Rigiflex Technology product / capability pages, owner-supplied PDFs (2026-10-29), copies in experiments/RF1_rigidflex/ds/; marketing pages, not part datasheets",
                facts=dict(rigid_flex_6L=dict(thickness_mm=1.6, copper_oz=1, min_hole_mil=4, width_gap_mil="4/5", laser_hole_mil="5, 6"),
                           rigid_flex_10L_4flex=dict(flex_thickness_mm=0.2, total_mm=1.6, width_space_mil="4/4", dielectric_strength="5 kV (thickness not stated)", insulation_Mohm=1000),
                           polyimide_flex=dict(er_1MHz=4, df_1MHz=0.04, single_sided_mm=0.050, double_sided_mm=0.075, min_conductor_mm=0.025, water_absorption_pct=2.9),
                           panel_max_in="18 x 24", rigid_min_board_mm="30 x 50", layers="1-20 (flex / rigid-flex page), 1-30 rigid", stiffeners="stainless steel, aluminium, FR4, polyimide"),
                fit=[dict(item="SB1R-QA/QB D228 receive boards", vs="panel 18 x 24 in (457 x 610 mm)", ok=True),
                     dict(item="our finest trace / space (AB1 0.15 neck-down, 0.125 grid)", vs="4/4 mil = 0.10 / 0.10 mm", ok=True),
                     dict(item="CB1D and AB1 are 6 layers, LB1 4, HTA 4", vs="one stackup for every rigid section: 6L rigid with a 2L flex core (the 6L 1.6 mm page)", ok=True,
                          note="LB1 and HTA become 6-layer rigid sections or stay separate boards"),
                     dict(item="460 V coil taps on CB1D (COIL_A / COIL_B)", vs="rule 6: >= 1.0 mm, keep them off every hinge (they stay AWG22 600 V wire from TXJ1)", ok=True),
                     dict(item="stiffeners", vs="stainless / aluminium are closed metal near the coils (rule 5)", ok=False, note="specify FR4 or polyimide stiffeners only")])

def baseline():
    try: h = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception: h = None
    return dict(commit=h, rule="the baseline is read, never written; phase 2 copies any generator it changes into experiments/RF1_rigidflex/src/")

if __name__ == "__main__":
    out = dict(status="MODELED / mesh-checked side experiment (RF1, phase 1); not part of the sign-off", baseline=baseline())
    out["census"] = census(); out["ab1_cb1d_hinges"] = hinges_ab1()
    out["hinges_up"] = [hinge_up("CB1D -> LB1 (S-fold in the duct window at the LB1 level)", Z["CB1D_top"], Z["LB1_bot"]),
                        hinge_up("CB1D -> HTA tail (through the LB1 level to the cap)", Z["CB1D_top"], Z["HTA_bot"])]
    out["rx_tail"] = rx_tail(); out["eddy_loops"] = loops(); out["vendor"] = vendor()
    out["inputs_read_sha256_16"] = {os.path.relpath(k, ROOT): v for k, v in sorted(READ.items())}
    json.dump(out, open(os.path.join(OUT, "rf1_phase1.json"), "w"), indent=1)
    c = out["census"]; print("census: wires today", c["wires_today"], "hand joints", c["hand_joints_today"], "-> concept B", c["concept_B_joints"]["total"], "concept C", c["concept_C_joints"]["total"])
    for k, v in out["ab1_cb1d_hinges"].items(): print(f"hinge {k}: {v['fails']}/{v['checks']} FAIL, LB1 margin {v['height_margin_under_LB1_mm']} mm, septum margin {v['height_margin_under_septum_mm']} mm, length {v['route_length_mm']}")
    for h in out["hinges_up"]: print("up", h)
    print("rx tail", out["rx_tail"]["wire"], out["rx_tail"]["flex_broadside"]); print("loops", out["eddy_loops"]["cycles"], "tree", out["eddy_loops"]["tree"])
