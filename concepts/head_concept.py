#!/usr/bin/env python3
"""Owner concept boards 3 + 4 (2026-10-31): 'Project Hyperion' 9 in (229 mm) PI search head, REV 03 / 05 / 06 synthesis. Tested in ISOLATION from the
AXE2 design (its rules do not constrain this study; AXE2 numbers appear only as a reference column). MODELED with concepts/clib.py (self-checked).

Concept claims tested: helical-hex TX, 3-D honeycomb lattice former 'driving inter-winding capacitance to zero', sub-2 us decay, 50 A Stage-2 pulse
switched by Infineon BSC007N04LS6 (OptiMOS 6, 40 V), nested-hex planar fractal RX on 5 mil polyimide 'not blinded by the TX', graphene / Mu-metal
fins (radial phase-damping fins + concentric shielding fins under the LEDs), 360 WS2812B-Mini radar LEDs, TI ADS1282 digitiser + IGLOO2 FPGA in the head,
optically clear PU vacuum potting, noise floor < 1 nV/rtHz. 'Quantum resonance' has no physical content to test and is not modelled.
Datasheet facts (data/datasheets, DATASHEET_LOG RF2-DS-CONCEPTS): BSC007N04LS6 VDS 40 V, RDS(on) 0.7 mohm max, Coss 2100 typ / 2700 max pF at 20 V,
EAS 674 mJ single pulse; ADS1282 data rate 250-4000 SPS (FIR), sinc mode to 128 kSPS, PGA 5 nV/rtHz; WS2812B 800 kbit/s, 1.25 us per bit, reset > 50 us;
SK6812MINI (3535 class) 3.5 x 3.7 x 0.95 mm, 0.2 W per LED; MuMETAL rho 60 uOhm cm, mu_i 50 000 (DC) / 100 000 (60 Hz), Bs 0.74 T, 8.7 g/cm3.
ASSUMED (no source): graphene film 1e6 S/m and 25 um; PU potting eps_r 3.5 and 1.10 g/cm3; PEEK-CF 1.40 g/cm3; litz 1.2 mm; LED drive 5 V.
Writes concepts/out/head_concept.json, STL / STEP parts and a view.   usage: python3 concepts/head_concept.py"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); sys.path.insert(0, HERE); os.makedirs(OUT, exist_ok=True)
import clib as K
D_HEAD, H_HEAD = 0.229, 0.0215; R_TX = 0.100; A_WIRE = 0.6e-3; PITCH_TIGHT = 1.4e-3; PITCH_CELL = 3.0e-3
EPS_PU = 3.5; I_CONCEPT = 50.0; V_CLAMP_40V = 36.0; COSS_OPTIMOS = 2100e-12; C_EXT = 50e-12
SIGMA_MU = 1 / 60e-8; MU_I = 50000; SIGMA_GOLD = 4.1e7
DEPTHS = (0.10, 0.20, 0.30)

def turns(kind, n, pitch, rows=12):
    out = []
    for k in range(n):
        r = R_TX - (k // rows) * pitch; z = (k % rows) * pitch
        out.append(K.circle(r, z, 64) if kind == "circle" else (K.hexagon(r, z, 0.0, n_side=10) if kind == "hex" else K.zigzag_ring(r, 2.0e-3, 30, z, 3)))
    return out

def tx_eval(kind, n, pitch, eps_r, coss, v_clamp, I):
    T = turns(kind, n, pitch); L = K.coil_L(T, A_WIRE, 2 if kind != "zigzag" else 1)
    pts = [[0, 0, -d] for d in DEPTHS]; B = sum(np.atleast_2d(K.polyline_B(t, 1.0, pts))[:, 2] for t in T)
    perim = sum(float(np.sum(np.linalg.norm(np.diff(t, axis=0), axis=1))) for t in T)
    c_pair = (perim / max(n, 1)) * K.c_parallel_wires(pitch, A_WIRE, eps_r) if n > 1 else 0.0
    c_self = c_pair / (n - 1) if n > 1 else 0.0; C_node = c_self + coss + C_EXT
    ps = K.pi_first_sample(L, C_node, I, v_clamp)
    area = abs(0.5 * float(np.sum(T[0][:-1, 0] * T[0][1:, 1] - T[0][1:, 0] * T[0][:-1, 1])))
    return dict(kind=kind, turns=n, L_uH=round(L * 1e6, 2), B_uT_per_A={f"{int(d*1000)} mm": round(float(b) * 1e6, 4) for d, b in zip(DEPTHS, B)},
                B200_per_sqrtJ_uT=round(float(B[1]) * math.sqrt(2 / L) * 1e6, 2), wire_m=round(perim, 2), turn_area_cm2=round(area * 1e4, 1),
                C_self_pF=round(c_self * 1e12, 1), C_node_pF=round(C_node * 1e12, 1), E_pulse_mJ=round(0.5 * L * I ** 2 * 1e3, 1), P_400Hz_W_if_dumped=round(0.5 * L * I ** 2 * 400, 1), **ps)

def main():
    res = dict(status=__doc__.split("\n")[1], selftest=K.selftest())
    # ---- 1. TX geometry: circle vs helical hex vs honeycomb-woven (zigzag), same rim, 1.4 mm (tight) pitch, concept switch (40 V, 2.1 nF)
    sweep = []
    for kind in ("circle", "hex", "zigzag"):
        for n in (1, 2, 4, 8, 16, 26):
            if kind == "zigzag" and n > 8: continue
            sweep.append(tx_eval(kind, n, PITCH_TIGHT, EPS_PU, COSS_OPTIMOS, V_CLAMP_40V, I_CONCEPT))
    res["tx_sweep_concept_switch"] = sweep
    # ---- 2. 'zero capacitance' honeycomb: tight potted vs 3 mm air cells vs 3 mm cells potted, 8 turns hex, with the concept switch and a 900 V SiC-class switch
    cap = []
    for label, pitch, eps in (("tight litz, PU potted", PITCH_TIGHT, EPS_PU), ("honeycomb 3 mm cells, air", PITCH_CELL, 1.0), ("honeycomb 3 mm cells, PU potted (as the concept pots it)", PITCH_CELL, EPS_PU)):
        for sw, coss, vcl in (("BSC007N04LS6 40 V (concept)", COSS_OPTIMOS, V_CLAMP_40V), ("900 V SiC class, Coss 110 pF, 460 V clamp", 110e-12, 460.0)):
            r = tx_eval("hex", 8, pitch, eps, coss, vcl, I_CONCEPT); cap.append(dict(case=label, switch=sw, **{k: r[k] for k in ("L_uH", "C_self_pF", "C_node_pF", "fall_us", "settle_us", "first_sample_us")}))
    res["capacitance_cases_8turn_hex_50A"] = cap
    # what would a 2 us first sample need? (best case: no winding C, node = 50 pF external only)
    need = []
    for L_uH in (1, 3, 10, 30, 100):
        for vcl in (36.0, 460.0):
            p = K.pi_first_sample(L_uH * 1e-6, 50e-12 + 110e-12, I_CONCEPT, vcl); need.append(dict(L_uH=L_uH, v_clamp=vcl, first_sample_us=round(p["first_sample_us"], 2)))
    res["sub_2us_requirement"] = need
    # ---- 3. RX nested-hex planar array on 5 mil polyimide: R, noise, coupling to the TX, voltage at turn-off
    rx_turns = [K.hexagon(r, PITCH_TIGHT * 12 + 1e-3, 0.0, n_side=8) for r in np.linspace(0.090, 0.030, 20)]
    rx_len = sum(float(np.sum(np.linalg.norm(np.diff(t, axis=0), axis=1))) for t in rx_turns)
    w_tr, t_cu = 0.15e-3, 18e-6; R_rx = 1.72e-8 * rx_len / (w_tr * t_cu)
    tx8 = turns("hex", 8, PITCH_TIGHT); L_rx = K.coil_L(rx_turns, 0.5 * math.sqrt(w_tr * t_cu), 1)
    M = sum(K.mutual(a, b, 1) for a in tx8 for b in rx_turns)
    tx8_L = K.coil_L(tx8, A_WIRE, 2); t_fall = tx8_L * I_CONCEPT / V_CLAMP_40V
    res["rx_planar"] = dict(turns=20, trace_mm=0.15, copper_um=18, length_m=round(rx_len, 2), R_ohm=round(R_rx, 1), johnson_nV=round(K.johnson_noise_nV(R_rx), 2),
                            L_uH=round(L_rx * 1e6, 1), M_tx_rx_uH=round(M * 1e6, 2), k=round(M / math.sqrt(L_rx * tx8_L), 3),
                            V_rx_at_turnoff_V=round(M * I_CONCEPT / t_fall, 1), V_rx_at_turnoff_SiC_460V_V=round(M * I_CONCEPT / (tx8_L * I_CONCEPT / 460.0), 1), note="coplanar concentric RX: the coupling is geometric; 'non-parallel' tracks do not null it (only bucking / DD / quadrupole geometry does)")
    # ---- 4. fins and shields inside the head vs a 1 g gold reference at 150 mm (same coil, same formula), sample 10 us after turn-off
    T8 = tx8; h_at = lambda P: sum(np.atleast_2d(K.polyline_B(t, 1.0, [P]))[0] for t in T8)
    I0, ts = I_CONCEPT, 10e-6
    Bg = h_at([0, 0, -0.150]); phi_g = abs(Bg[2]) * math.pi * 0.002 ** 2
    gold, tau_g = K.eddy_echo(phi_g, 0.002, 0.002, 0.002, SIGMA_GOLD, I0, ts)
    Bring = h_at([0.060, 0, 0.018]); phi_r = abs(Bring[2]) * math.pi * 0.060 ** 2
    ring, tau_r = K.eddy_echo(phi_r, 0.060, 0.010, 25e-6, 1e6, I0, ts)
    # radial Mu-metal fin (in the r-z plane): no azimuthal field -> no eddy flux; its ferromagnetic polarisation (in-plane field) relaxes with the sheet's eddy time
    Bfin = h_at([0.060, 0, 0.008]); H_in = math.hypot(Bfin[0], Bfin[2]) / K.MU0; t_fin = 0.1e-3; V_fin = 0.075 * 0.015 * t_fin
    chi = 0.015 / t_fin                                                            # demagnetisation-limited in-plane susceptibility (N about t / h)
    tau_f = K.MU0 * MU_I * SIGMA_MU * t_fin ** 2 / math.pi ** 2
    fin = K.MU0 * chi * V_fin * H_in ** 2 * I0 / tau_f * math.exp(-ts / tau_f) * 6
    res["head_metal"] = dict(sample_us=ts * 1e6, gold_1g_150mm=dict(echo=gold, tau_us=round(tau_g * 1e6, 2)),
                             concentric_graphene_ring=dict(ratio_to_gold=round(ring / gold, 1), tau_us=round(tau_r * 1e6, 3), note="a closed ring round the axis: full eddy coupling"),
                             radial_mumetal_fins_x6=dict(ratio_to_gold=round(fin / gold, 1), tau_us=round(tau_f * 1e6, 1), chi_eff=round(chi), note="ferromagnetic response of the fins (eddy part zero for exact radial planes)"))
    # ---- 5. LEDs, digitiser, switch, potting, mass
    n_led = 360; frame_ms = n_led * 24 * 1.25e-3 + 0.05
    res["leds"] = dict(n=n_led, power_full_W=n_led * 0.2, current_5V_A=round(n_led * 0.2 / 5, 1), frame_ms=round(frame_ms, 2), pi_period_ms_400Hz=2.5,
                       note="one WS2812 chain cannot finish a frame inside one PI period; its 800 kbit/s data and 14 A of LED PWM switch inside the RX windows")
    res["digitiser"] = dict(ads1282_max_SPS_fir=4000, ads1282_max_SPS_sinc=128000, min_sample_spacing_us=round(1e6 / 128000, 2), needed_spacing_us=0.5,
                            note="a PI decay is read at microsecond spacing (>= 1-2 MSPS); the ADS1282 is a seismic converter: 15x too slow even in sinc mode, 500x in FIR mode")
    e = tx_eval("hex", 8, PITCH_TIGHT, EPS_PU, COSS_OPTIMOS, V_CLAMP_40V, I_CONCEPT)
    res["switch"] = dict(part="BSC007N04LS6", vds_V=40, coss_pF=2100, eas_single_mJ=674, E_pulse_mJ_8turn=e["E_pulse_mJ"],
                         avalanche_W_400Hz=e["P_400Hz_W_if_dumped"], note="a 40 V switch must clamp below 40 V: fall = L I / 36 V; the pulse energy has to be dumped every pulse (no repetitive avalanche rating given)")
    r_in = D_HEAD / 2 - 0.004; vol_in = math.pi * r_in ** 2 * (H_HEAD - 0.003)
    res["mass"] = dict(potting_g=round(vol_in * 0.80 * 1.10e6), frame_shell_g=round((math.pi * (D_HEAD / 2) ** 2 * 0.003 + 2 * math.pi * D_HEAD / 2 * H_HEAD * 0.004) * 1.40e6),
                       tx_litz_g=round(e["wire_m"] * 6.0), leds_g=round(n_led * 0.05), note="potting fills 80 % of the interior (ASSUMED); PU 1.10, PEEK-CF 1.40 g/cm3 ASSUMED")
    res["mass"]["total_g"] = sum(v for k, v in res["mass"].items() if k.endswith("_g"))
    # ---- 6. AXE2 reference (read only)
    ref = {}
    try:
        hc = json.load(open(os.path.join(HERE, "..", "rf2", "head", "out_BF", "rf2_head_check.json"))); ref["AXE2_head_mass_g"] = hc["checks"]["mass_g"]["total_islands_only"]
        mc = json.load(open(os.path.join(HERE, "..", "rf2", "head", "out", "rf2_mp1v2_close.json"))); ref["AXE2_first_sample_us"] = mc["first_gate_us"]
    except Exception as ex: ref["error"] = str(ex)
    res["reference_AXE2"] = ref
    best = max([s for s in sweep if s["first_sample_us"] < 50], key=lambda s: s["B200_per_sqrtJ_uT"], default=None)
    res["findings"] = [
        f"geometry: a hexagon inscribed in the rim loses {100 * (1 - next(s for s in sweep if s['kind']=='hex' and s['turns']==8)['turn_area_cm2'] / next(s for s in sweep if s['kind']=='circle' and s['turns']==8)['turn_area_cm2']):.0f} % of the loop area; the honeycomb zigzag adds wire with no field gain",
        "capacitance: 3 mm air cells cut the winding capacitance, but the PU potting the concept calls for puts eps_r back; with the BSC007N04LS6's 2.1 nF on the node the winding C does not matter",
        f"sub-2 us needs a coil of about 10 uH or less with a 460 V clamp ({next(x for x in need if x['L_uH']==10 and x['v_clamp']==460.0)['first_sample_us']} us), or about 1 uH at a 36 V clamp ({next(x for x in need if x['L_uH']==1 and x['v_clamp']==36.0)['first_sample_us']} us): 1-3 turns. The concept's 8-turn coil at 50 A falls in {e['fall_us']:.0f} us on the 40 V switch; with a 900 V SiC-class switch the same coil reads at about 4-5 us",
        f"planar RX: low noise ({res['rx_planar']['johnson_nV']} nV/rtHz) but k = {res['rx_planar']['k']} to the TX: {res['rx_planar']['V_rx_at_turnoff_V']} V induced at turn-off on the 40 V switch, {res['rx_planar']['V_rx_at_turnoff_SiC_460V_V']} V with a fast switch: blinded without geometric nulling",
        f"metal in the head vs a 1 g gold at 150 mm (10 us): Mu-metal fins {res['head_metal']['radial_mumetal_fins_x6']['ratio_to_gold']:.0f} x (a ferrous target with a {res['head_metal']['radial_mumetal_fins_x6']['tau_us']} us relaxation inside the coil); the concentric graphene ring decays in {res['head_metal']['concentric_graphene_ring']['tau_us']} us (gone by the first sample, but it is a closed loop that absorbs TX energy)",
        f"LEDs: {n_led * 0.2:.0f} W full white, frame {frame_ms:.1f} ms vs a 2.5 ms PI period; ADS1282 is 15-500 x too slow for a PI decay"]
    res["ok"] = bool(res["selftest"]["ok"])
    json.dump(res, open(os.path.join(OUT, "head_concept.json"), "w"), indent=1, default=float)
    build_meshes(res)
    for f in res["findings"]: print("-", f)
    return res

def build_meshes(res):
    """concept geometry as solids: shell, honeycomb lattice band, 8-turn helical-hex TX, nested-hex RX on 5 mil PI, radial fins, concentric ring,
    360 LEDs (SK6812MINI / WS2812B-Mini 3535 class), electronics module with real package outlines (ADS1282 TSSOP-28 9.7 x 4.4, IGLOO2 VF400 17 x 17,
    4 x BSC007N04LS6 TDSON-8 5.15 x 6.15), RG316-DS exit (2.9 mm)."""
    import cadquery as cq
    mm = 1000.0; R = D_HEAD / 2 * mm; H = H_HEAD * mm; P = {}
    P["SHELL"] = cq.Workplane("XY").circle(R).circle(R - 2.0).extrude(H).union(cq.Workplane("XY").circle(R).extrude(1.5))
    band = cq.Workplane("XY").circle(R - 2.0).circle(R - 9.0).extrude(H - 3.0).translate((0, 0, 1.5))
    cells = None
    for row in range(2):
        for k in range(36):
            a = 2 * math.pi * (k + 0.5 * row) / 36; z = 6.0 + row * 8.0
            c = cq.Workplane("YZ").polygon(6, 6.5).extrude(12.0).translate((R - 12.0, 0, z)).rotate((0, 0, 0), (0, 0, 1), math.degrees(a)).val()
            cells = [c] if cells is None else cells + [c]
    P["LATTICE_BAND"] = band.cut(cq.Workplane("XY").add(cq.Compound.makeCompound(cells)))
    tx = None
    for k in range(8):
        r = (R_TX - 0.0) * mm; z = 2.5 + k * 1.4; v = [(r * math.cos(j * math.pi / 3), r * math.sin(j * math.pi / 3), z) for j in range(7)]
        for (x1, y1, z1), (x2, y2, z2) in zip(v[:-1], v[1:]):
            ln = math.hypot(x2 - x1, y2 - y1); ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
            cyl = cq.Workplane("YZ").circle(0.6).extrude(ln).rotate((0, 0, 0), (0, 0, 1), ang).translate((x1, y1, z1))
            tx = cyl if tx is None else tx.union(cyl)
            tx = tx.union(cq.Workplane("XY").sphere(0.6).translate((x2, y2, z2)))
    P["TX_HEX_8T"] = tx
    zr = 2.5 + 12 * 1.4; P["RX_POLYIMIDE"] = cq.Workplane("XY").circle(93.0).extrude(0.127).translate((0, 0, zr))
    rx = None
    for r in np.linspace(90.0, 30.0, 20):
        ring = cq.Workplane("XY").polygon(6, 2 * r).polygon(6, 2 * (r - 0.15)).extrude(0.018).translate((0, 0, zr + 0.127))
        rx = ring if rx is None else rx.union(ring)
    P["RX_NESTED_HEX"] = rx
    fins = None
    for k in range(6):
        f = cq.Workplane("XY").box(75.0, 0.1, 15.0).translate((57.5, 0, 9.0)).rotate((0, 0, 0), (0, 0, 1), k * 60 + 30)
        fins = f if fins is None else fins.union(f)
    P["FINS_MUMETAL_RADIAL"] = fins
    P["RING_GRAPHENE_CONCENTRIC"] = cq.Workplane("XY").circle(65.0).circle(55.0).extrude(0.025).translate((0, 0, 18.0))
    P["LED_BOARD"] = cq.Workplane("XY").circle(100.0).extrude(0.8).translate((0, 0, 18.3))
    leds = None; n_left = 360; rings = np.linspace(14.0, 96.0, 12); per = np.round(360 * rings / rings.sum()).astype(int); per[-1] += 360 - per.sum()
    for rr, n in zip(rings, per):
        for j in range(int(n)):
            a = 2 * math.pi * j / n; b = cq.Workplane("XY").box(3.5, 3.7, 0.95).rotate((0, 0, 0), (0, 0, 1), math.degrees(a)).translate((rr * math.cos(a), rr * math.sin(a), 19.1 + 0.475)).val()
            leds = [b] if leds is None else leds + [b]
    P["LEDS_360_3535"] = cq.Workplane("XY").add(cq.Compound.makeCompound(leds))
    pcb = cq.Workplane("XY").box(45.0, 35.0, 1.6).translate((-55.0, 0, 5.0))
    parts = [((9.7, 4.4, 1.2), (-62, 8, 6.4)), ((17.0, 17.0, 1.5), (-50, -6, 6.55))] + [((5.15, 6.15, 1.0), (-70 + 6.5 * i, -14, 6.3)) for i in range(4)]
    for (sx, sy, sz), (x, y, z) in parts: pcb = pcb.union(cq.Workplane("XY").box(sx, sy, sz).translate((x, y, z)))
    P["SOC_MODULE_ADS1282_IGLOO2_4xBSC007"] = pcb
    P["RG316DS_EXIT"] = cq.Workplane("YZ").circle(1.45).extrude(40.0).translate((-R - 20.0, 0, 8.0))
    meta = {}
    for k, w in P.items():
        cq.exporters.export(w, os.path.join(OUT, f"head_{k}.stl")); meta[k] = round(w.val().Volume() / 1000.0, 3)
    cq.exporters.export(cq.Compound.makeCompound([w.val() for w in P.values()]), os.path.join(OUT, "head_concept.step"))
    res["meshes"] = dict(parts_cm3=meta, files=sorted(f for f in os.listdir(OUT) if f.startswith("head_")))
    json.dump(res, open(os.path.join(OUT, "head_concept.json"), "w"), indent=1, default=float)

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
