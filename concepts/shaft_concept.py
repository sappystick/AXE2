#!/usr/bin/env python3
"""Owner concept boards 1 + 2 (2026-10-31): 'Project Axis' 1 in (25.4 mm) shafts, tested in ISOLATION from the AXE2 design. MODELED (concepts/clib.py).
  A (REV A / REV 05): carbon shell 25.4 x 0.5 mm, 6 PEEK radial fins, central Mu-metal conduit 3 mm ID x 0.5 mm wall carrying three twin-axial cables
    (TX, RX1, RX2; RG316-DS named in the BOM), 6-layer rigid-flex accordion (0.5 mm FR4 rigid segments, 5 mil polyimide flex) in the hexagonal chambers.
  B (REV 04): PEEK / GFRP shell 0.1 mm (E = 30 GPa per its own table), helical-hex wrapped 6-layer HDI flex, 0.05 mm microfluidic channels, 0.01 mm optical
    core, 'metamaterial core mu_r = 0.01, negative index', aerogel barrier, vacuum-insulated EM waveguide tube, twin-axial TX / RX lines.
Sources: MuMETAL foil / sheet data (Magnetic Shield Corp, on file): rho 60 uOhm cm, mu_i 50 000 DC, Bs 0.74 T, 8.7 g/cm3; RG316-DS 95 pF/m and OD 0.114 in
(2.9 mm) from vendor listings (UNVERIFIED: no datasheet on file); Minco design guide (on file): multilayer bend >= 24 x thickness, double 12 x, about 0.15 mm
per layer, single layer for dynamic flexing. ASSUMED: carbon E 50 GPa / 1.55 g/cm3, PEEK 1.30, FR4 1.85, polyimide 1.42 g/cm3; concept head 931 g
(concepts/head_concept.json); aerogel k 0.014 W/mK (the concept's figure, UNVERIFIED); cable 0.07 ohm/m.
Writes concepts/out/shaft_concept.json, STL / STEP parts.   usage: python3 concepts/shaft_concept.py"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); sys.path.insert(0, HERE); os.makedirs(OUT, exist_ok=True)
import clib as K
E_CF, RHO_CF, RHO_PEEK, RHO_MU, RHO_FR4, RHO_PI = 50e9, 1550.0, 1300.0, 8700.0, 1850.0, 1420.0
OD, WALL, L_SHAFT = 25.4e-3, 0.5e-3, 1.0
COND_ID, COND_T = 3.0e-3, 0.5e-3; CABLE_OD = 2.9e-3; MU_I, RHO_MU_E = 50000, 60e-8

def head_mass():
    try: return json.load(open(os.path.join(OUT, "head_concept.json")))["mass"]["total_g"] / 1000.0
    except Exception: return 0.931

def concept_a():
    r = {}
    # cables in the conduit
    d_max3 = COND_ID / (1 + 2 / math.sqrt(3))
    r["cables"] = dict(conduit_id_mm=COND_ID * 1e3, cables=3, rg316ds_od_mm=CABLE_OD * 1e3, fill_pct=round(100 * 3 * CABLE_OD ** 2 / COND_ID ** 2, 0), fits=3 * CABLE_OD ** 2 <= COND_ID ** 2 and CABLE_OD <= d_max3,
                       max_od_for_3_mm=round(d_max3 * 1e3, 2), conduit_id_for_3_rg316ds_mm=round(CABLE_OD * (1 + 2 / math.sqrt(3)) * 1e3, 2))
    # structure and mass per metre
    I = K.I_round(OD, OD - 2 * WALL); m_shell = math.pi / 4 * (OD ** 2 - (OD - 2 * WALL) ** 2) * RHO_CF
    m_fins = 6 * (OD / 2 - WALL - (COND_ID / 2 + COND_T)) * 0.5e-3 * RHO_PEEK; m_cond = math.pi / 4 * ((COND_ID + 2 * COND_T) ** 2 - COND_ID ** 2) * RHO_MU
    m_flex = 6 * 2 * 8e-3 * 1.0e-3 * RHO_FR4                                                # two 8 mm x 1.0 mm rigid-flex panels per chamber along the whole metre (ASSUMED full fill: an upper bound)
    m_cab = 3 * 30e-3                                                                       # about 30 g/m per RG316-class cable (ASSUMED)
    q = (m_shell + m_fins + m_cond + m_flex + m_cab) * 9.81; P = head_mass() * 9.81
    r["structure"] = dict(I_mm4=round(I * 1e12), mass_g_per_m=dict(shell=round(m_shell * 1e3), fins=round(m_fins * 1e3), mumetal_conduit=round(m_cond * 1e3), rigid_flex=round(m_flex * 1e3), cables=round(m_cab * 1e3)),
                          total_g_per_m=round((m_shell + m_fins + m_cond + m_flex + m_cab) * 1e3), tip_sag_mm_1m=round(K.sag(P, q, L_SHAFT, E_CF, I) * 1e3, 2),
                          bending_stress_MPa=round(P * L_SHAFT * (OD / 2) / I / 1e6, 1), buckling_MPa=round(K.buckling_stress(E_CF, WALL, OD / 2) / 1e6))
    # shielding: what the conduit sees and does
    S_dc = 1 + MU_I * COND_T / (COND_ID + COND_T)
    f = 50e3; delta = K.skin_depth(RHO_MU_E, f, MU_I)
    I_pk, s_pair, r_flex, t_di = 50.0, 2.0e-3, 11e-3, 3e-6
    B_pair = K.MU0 * I_pk * s_pair / (2 * math.pi * r_flex ** 2); V_trace = B_pair / t_di * (0.3e-3 * 1.0)
    r["shielding"] = dict(static_transverse_factor=round(S_dc), skin_depth_50kHz_mm=round(delta * 1e3, 3), wall_mm=COND_T * 1e3,
                          twin_lead_50A_B_at_flex_uT=round(B_pair * 1e6, 2), emf_in_a_1m_trace_pair_mV_unshielded=round(V_trace * 1e3, 2),
                          coax_external_field="about 0 for an ideal coax (equal and opposite currents): a magnetic conduit adds nothing for coax lines",
                          note="the conduit matters only for twin-lead; a grounded copper braid / foil already handles the electric coupling")
    # the Mu-metal conduit as a PI target: axial along the head axis from 30 mm above the coil plane, against a 1 g gold at 150 mm (concept 8-turn hex coil)
    tx = [K.hexagon(0.100, k * 1.4e-3, 0.0, n_side=10) for k in range(8)]
    zs = np.linspace(0.03, 0.60, 58); pts = [[0, 0, z] for z in zs]
    B = sum(np.atleast_2d(K.polyline_B(t, 1.0, pts)) for t in tx); H = np.linalg.norm(B, axis=1) / K.MU0
    A_wall = math.pi / 4 * ((COND_ID + 2 * COND_T) ** 2 - COND_ID ** 2); dz = zs[1] - zs[0]; chi = 1000.0
    tau = K.MU0 * MU_I * (1 / RHO_MU_E) * COND_T ** 2 / math.pi ** 2; I0, ts = 50.0, 10e-6
    cond = K.MU0 * chi * float(np.sum(A_wall * dz * H ** 2)) * I0 / tau * math.exp(-ts / tau)
    Bg = sum(np.atleast_2d(K.polyline_B(t, 1.0, [[0, 0, -0.15]]))[0] for t in tx); gold, tau_g = K.eddy_echo(abs(Bg[2]) * math.pi * 0.002 ** 2, 0.002, 0.002, 0.002, 4.1e7, I0, ts)
    r["conduit_as_target"] = dict(chi_eff=chi, tau_ms=round(tau * 1e3, 2), ratio_to_1g_gold_150mm=round(cond / gold), note="chi_eff capped at 1000 (demagnetisation, ASSUMED low); the conduit is a soft-ferrous target 30 mm above the coil with a millisecond relaxation")
    # 6-layer accordion in the chambers
    t6, t2, t1 = 6 * 0.15e-3, 2 * 0.15e-3, 0.15e-3; chamber_w = 2 * math.pi * (OD / 2 - WALL) / 6 * 0.6; avail = chamber_w / 4
    r["accordion"] = dict(six_layer_bend_min_mm=round(24 * t6 * 1e3, 1), two_layer_hinge_bend_min_mm=round(12 * t2 * 1e3, 1), single_layer_hinge_bend_min_mm=round(6 * t1 * 1e3, 1),
                          fold_radius_available_mm=round(avail * 1e3, 1), six_layer_ok=24 * t6 <= avail, two_layer_hinge_ok=12 * t2 <= avail, single_layer_hinge_ok=6 * t1 <= avail,
                          note="a 6-layer flex cannot fold inside a 25 mm tube; only single-layer flex hinges between rigid panels fold in the space; 0.5 mm boards in 0.5 mm tracks have no fit clearance")
    return r

def concept_b():
    r = {}; t, E, P = 0.1e-3, 30e9, head_mass() * 9.81
    I = K.I_round(OD, OD - 2 * t); m = math.pi / 4 * (OD ** 2 - (OD - 2 * t) ** 2) * RHO_PEEK
    sigma = P * L_SHAFT * (OD / 2) / I; scr = K.buckling_stress(E, t, OD / 2)
    r["shell"] = dict(wall_mm=0.1, E_GPa=30, I_mm4=round(I * 1e12), mass_g_per_m=round(m * 1e3), bending_stress_MPa=round(sigma / 1e6), local_buckling_MPa=round(scr / 1e6),
                      buckles=sigma > scr, tip_sag_mm_shell_only=round(K.sag(P, m * 9.81, L_SHAFT, E, I) * 1e3, 1),
                      note="the 0.1 mm shell alone buckles under the head's moment; the inner layers would have to carry the load (not specified)")
    # heat: TX cable I^2R per metre vs a 25.4 mm tube in still air, with / without the aerogel barrier
    I_rms = 50.0 * math.sqrt(0.1 / 3); p = I_rms ** 2 * 0.07 * 2
    h_out = 8.0 * math.pi * OD; dT_bare = p / h_out
    R_aero = math.log(10e-3 / 9.5e-3) / (2 * math.pi * 0.014); dT_aero = p * R_aero + dT_bare
    r["heat"] = dict(I_rms_A=round(I_rms, 1), W_per_m=round(p, 2), dT_bare_K=round(dT_bare, 1), dT_with_aerogel_inner_K=round(dT_aero, 1),
                     note="a 25 mm tube sheds the cable loss by natural convection; the aerogel barrier traps it inside; a closed microfluidic loop with no radiator only moves heat around")
    # 'metamaterial mu_r 0.01': the physical analogue is an eddy-current sleeve (copper) whose transverse effective permeability falls above its cut-off
    sig_cu, tcu, Rs = 5.8e7, 0.1e-3, 7e-3; fc = 1 / (math.pi * K.MU0 * sig_cu * tcu * Rs)
    r["metamaterial_core"] = dict(claim="mu_r = 0.01, negative index, Z0 = 377 ohm", physical_analogue=f"0.1 mm copper sleeve at r 7 mm: transverse cut-off {fc / 1e3:.1f} kHz, above it the inside field falls like a low effective mu",
                                  shield_at_50kHz=round(K.tube_shield_transverse(50e3, sig_cu, tcu, Rs), 3), note="no passive kHz-MHz material with mu_r = 0.01 exists outside superconductors; a copper sleeve near the head is itself an eddy target")
    r["waveguides"] = dict(optical="a 10 um core is single-mode (laser + precise coupling); a 1 mm plastic optical fibre is the practical EMI-immune data link (real option, no datasheet on file)",
                           em_waveguide="a metal tube of about 5 mm passes nothing below about 35 GHz: no role at PI frequencies")
    return r

def build_meshes(res):
    import cadquery as cq
    L = 300.0; P = {}; Ro = OD / 2 * 1e3
    P["A_SHELL_CF"] = cq.Workplane("XY").circle(Ro).circle(Ro - 0.5).extrude(L)
    rc_o = (COND_ID / 2 + COND_T) * 1e3
    P["A_CONDUIT_MUMETAL"] = cq.Workplane("XY").circle(rc_o).circle(COND_ID / 2 * 1e3).extrude(L)
    fins = []
    for k in range(6):
        fins.append(cq.Workplane("XY").box(Ro - 0.5 - rc_o, 0.5, L).translate(((Ro - 0.5 + rc_o) / 2, 0, L / 2)).rotate((0, 0, 0), (0, 0, 1), k * 60).val())
    P["A_FINS_PEEK"] = cq.Workplane("XY").add(cq.Compound.makeCompound(fins))
    cab = []
    for k in range(3):
        a = 2 * math.pi * k / 3; rr = (COND_ID / 2 * 1e3) * 0.45
        cab.append(cq.Workplane("XY").circle(CABLE_OD / 2 * 1e3).extrude(L).translate((rr * math.cos(a), rr * math.sin(a), 0)).val())
    P["A_CABLES_RG316DS"] = cq.Workplane("XY").add(cq.Compound.makeCompound(cab))
    panels = []
    for j in range(8):
        y = 4.0 + j * 1.0; ang = 25 if j % 2 else -25
        panels.append(cq.Workplane("XY").box(5.0, 0.5, 30.0).rotate((0, 0, 0), (0, 0, 1), ang).translate((7.5, y - 6.0, 15.0 + j * 32.0)).rotate((0, 0, 0), (0, 0, 1), 30).val())
    P["A_RIGIDFLEX_ACCORDION"] = cq.Workplane("XY").add(cq.Compound.makeCompound(panels))
    # interference: cables vs conduit bore (cables overlapping each other / the wall)
    inter = sum(a.intersect(b).Volume() for i, a in enumerate(cab) for b in cab[i + 1:])
    wall_hit = sum(c.intersect(P["A_CONDUIT_MUMETAL"].val()).Volume() for c in cab)
    res["A"]["mesh_interference_mm3"] = dict(cable_cable=round(inter, 1), cable_conduit_wall=round(wall_hit, 1))
    # B
    P["B_SHELL_PEEK_0p1"] = cq.Workplane("XY").circle(Ro).circle(Ro - 0.1).extrude(L)
    helix = cq.Wire.makeHelix(pitch=40.0, height=L, radius=Ro - 1.0)
    rib = cq.Workplane("XZ").center(Ro - 1.0, 0).rect(0.15, 10.0).sweep(cq.Workplane().add(helix), isFrenet=True)
    P["B_FLEX_HELICAL"] = rib
    core = cq.Workplane("XY").circle(9.0).circle(7.0).extrude(L)
    wins = [cq.Workplane("XZ").rect(3.0, 3.0).extrude(10.0, both=True).translate((0, 0, z)).rotate((0, 0, 0), (0, 0, 1), a).val() for z in np.arange(6.0, L - 6.0, 6.0) for a in range(0, 180, 45)]
    P["B_CORE_GRID"] = core.cut(cq.Workplane("XY").add(cq.Compound.makeCompound(wins)))
    P["B_WAVEGUIDE_TUBE"] = cq.Workplane("XY").circle(4.0).circle(3.5).extrude(L)
    P["B_TWINAX"] = cq.Workplane("XY").add(cq.Compound.makeCompound([cq.Workplane("XY").circle(1.45).extrude(L).translate((x, 0, 0)).val() for x in (-1.6, 1.6)]))
    meta = {}
    for k, w in P.items():
        cq.exporters.export(w, os.path.join(OUT, f"shaft_{k}.stl")); meta[k] = round(w.val().Volume() / 1000.0, 3)
    cq.exporters.export(cq.Compound.makeCompound([w.val() for k, w in P.items() if k.startswith("A_")]), os.path.join(OUT, "shaft_A_concept.step"))
    cq.exporters.export(cq.Compound.makeCompound([w.val() for k, w in P.items() if k.startswith("B_")]), os.path.join(OUT, "shaft_B_concept.step"))
    res["meshes"] = dict(section_mm=L, parts_cm3=meta)

def main():
    res = dict(status=__doc__.split("\n")[1], selftest=K.selftest(), A=concept_a(), B=concept_b())
    try:
        so = json.load(open(os.path.join(HERE, "..", "rf2", "results", "rf2_shaft_options.json"))); res["reference"] = dict(garrett_two_piece_g_per_m=so["benchmark"]["garrett_g_per_m"], AXE2_nested_g_per_m=so["benchmark"]["ours_g_per_m"])
    except Exception as ex: res["reference"] = dict(error=str(ex))
    build_meshes(res)
    a, b = res["A"], res["B"]
    res["findings"] = [
        f"A cables: three RG316-DS (2.9 mm) in a 3 mm conduit fill {a['cables']['fill_pct']:.0f} %: they do not fit (max {a['cables']['max_od_for_3_mm']} mm each; three RG316-DS need a {a['cables']['conduit_id_for_3_rg316ds_mm']} mm bore); mesh overlap {a['mesh_interference_mm3']}",
        f"A structure: {a['structure']['total_g_per_m']} g/m (Garrett two-piece 155 g/m); 1 m tip sag {a['structure']['tip_sag_mm_1m']} mm under a {head_mass() * 1000:.0f} g head; bending {a['structure']['bending_stress_MPa']} MPa vs buckling {a['structure']['buckling_MPa']} MPa",
        f"A conduit: static shielding x{a['shielding']['static_transverse_factor']}, but coax has no external field to shield; as a ferrous target 30 mm above the coil it reads about {a['conduit_as_target']['ratio_to_1g_gold_150mm']:,} x a 1 g gold at 150 mm, relaxing over {a['conduit_as_target']['tau_ms']} ms",
        f"A accordion: a 6-layer flex needs a {a['accordion']['six_layer_bend_min_mm']} mm bend radius and a 2-layer hinge {a['accordion']['two_layer_hinge_bend_min_mm']} mm; about {a['accordion']['fold_radius_available_mm']} mm is available: only single-layer hinges ({a['accordion']['single_layer_hinge_bend_min_mm']} mm) fold",
        f"B shell: 0.1 mm at 30 GPa: bending {b['shell']['bending_stress_MPa']} MPa vs local buckling {b['shell']['local_buckling_MPa']} MPa -> buckles; the cable loss is {b['heat']['W_per_m']} W/m ({b['heat']['dT_bare_K']} K rise in still air, {b['heat']['dT_with_aerogel_inner_K']} K inside the aerogel): convection handles it without a liquid loop; the aerogel makes it worse",
        "B 'metamaterial' and the EM waveguide have no physical role at PI frequencies; the optical data link is the one real idea (a 1 mm POF)"]
    res["ok"] = bool(res["selftest"]["ok"])
    json.dump(res, open(os.path.join(OUT, "shaft_concept.json"), "w"), indent=1, default=float)
    for f in res["findings"]: print("-", f)
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
