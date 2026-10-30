#!/usr/bin/env python3
"""RF2 flex / photo-etch integrations from the owner's vendor brochures (2026-10-30). MODELED.

Sources (data/datasheets, DATASHEET_LOG RF2-DS-FLEX): Tech Etch long flex circuits (lengths to 40 in preferred / 60 in advanced, lead width / space
0.003 in preferred, 9 um metal layers); Tramonto reverse-bared single-layer flex (3.7-5.4 mil total, 1/4-2 oz copper, -55..150 C, IPC-6013);
FPCexpress flex / rigid-flex (up to 8 layers, crosshatched copper shielding); Tech Etch precision etch & form and precision-engineered parts
(BeCu contact fingers 0.010 in, pitch >= 0.050 in, minimum bend radii by temper, board-level shields 0.007-0.020 in brass / nickel silver / copper /
cold-rolled steel); ProtoShield (0.254 mm nickel silver CDA770 1/2 H sheets, 5 mm depth-etched grid). These are capability brochures: no voltage
ratings, no dielectric constants, no contact forces. Those values are ASSUMED and marked.

  A  coil cord -> long flex (fixes the cord-packing FAIL in rf2_wire_options): split at REF3T: segment 1 head -> REF3T with a rolling loop for the
     telescope travel, segment 2 REF3T -> hinge (static). Width budget with IPC-2221 trace widths and rule-6 spacing, lengths vs the Tech Etch limits,
     the TX-pair capacitance (coplanar strips) vs the 50 pF/m wire assumption, mass vs the coiled cord
  B  board-level shield over the front end / TPS65131 in the coil field: the eddy echo of a closed can vs a slotted (photo-etched comb) lid
  C  photo-etched BeCu contact fingers for the battery dock's BMS signal contacts (replaces the Mill-Max 0906 pins, whose sheet is not obtainable)
Writes rf2/results/rf2_flex_options.json.   usage: python3 rf2/rf2_flex_options.py"""
import os, sys, json, math
import numpy as np
from scipy.special import ellipk
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
EPS0 = 8.854e-12
TE_LEN_PREF, TE_LEN_ADV = 40 * 25.4, 60 * 25.4        # Tech Etch long flex, mm
TE_LINE = 0.003 * 25.4                                 # mm
CH = json.load(open(os.path.join(HERE, "chassis_out", "rf2_chassis_check.json")))

def ipc2221_width_mm(i_a, oz, d_t=10.0, internal=True):
    """IPC-2221 trace width for a temperature rise d_t (k = 0.024 internal / 0.048 external), copper oz (1 oz = 1.378 mil)"""
    k = 0.024 if internal else 0.048; area_mil2 = (i_a / (k * d_t ** 0.44)) ** (1 / 0.725); return area_mil2 / (1.378 * oz) * 0.0254

def cps_c_pf_per_m(w, s, eps_eff):
    """coplanar strips (two strips of width w, gap s): C = eps0 eps_eff K(k')/K(k), k = s / (s + 2 w)"""
    k = s / (s + 2 * w); kp = math.sqrt(1 - k * k); return EPS0 * eps_eff * ellipk(kp ** 2) / ellipk(k ** 2) * 1e12

def part_a():
    import rf2_cordflex as CFX, rf2_chassis as CS                                                          # the adopted cord flex (owner 2026-10-30)
    tel = CH["checks"]["telescope"]; travel = tel["pivot_to_hinge_mm"]["max"] - tel["collapsed_mm"]
    sg = CFX.segments(CS.SPEC["st"], CS.SPEC["extend_max"], travel); seg1, seg2 = sg["seg1_dynamic_mm"], sg["seg2_static_mm"]
    bore = 18.0; rows = []
    for eps_eff in (1.3, 1.6, 2.2):
        c = CFX.cps_c_pf_per_m(eps_eff=eps_eff); rows.append(dict(eps_eff=eps_eff, C_pF_per_m=round(c, 1), C_pF_total=round(c * sg["tx_length_m"], 1)))
    tc = json.load(open(os.path.join(OUT, "rf2_timing_cord.json"))); shift = max(v["shift_fixed_us"] for v in tc["cases"].values())
    pi_g = CFX.WIDTH * 0.075 * (seg1 + seg2) * 1.42e-3
    cu_g = (2 * CFX.W_TX + 2 * CFX.W_PWR + 3 * 0.3 + 3 * 1.2) * 0.070 * (seg1 + seg2) * 8.96e-3
    cord_g = 75.0 * 1.15                                                                                    # the replaced coiled cord, about 75 g/m x 1.15 m (ASSUMED)
    return dict(travel_mm=travel, segments=dict(seg1_dynamic_mm=seg1, seg2_static_mm=seg2), te_limit_mm=dict(preferred=round(TE_LEN_PREF), advanced=round(TE_LEN_ADV)),
                lengths_ok=seg1 <= TE_LEN_PREF and seg2 <= TE_LEN_PREF, one_piece_mm=sg["one_piece_mm"], tx_length_m=sg["tx_length_m"],
                copper_oz=CFX.OZ, tx_trace_mm=round(CFX.W_TX, 2), pwr_trace_mm=round(CFX.W_PWR, 2), lanes=[dict(lane=n, mm=round(w, 2)) for n, w in CFX.LANES], width_mm=round(CFX.WIDTH, 2),
                fits_bore=CFX.WIDTH <= bore - 2.0, bore_mm=bore, rolling_loop_bend_r_mm=CFX.BEND_R, loop_fits=2 * CFX.BEND_R <= bore - 4.0, min_line_mm=round(TE_LINE, 3),
                tx_capacitance=rows, first_gate_shift_us=shift, first_gate_shift_wire_us=0.19, mass_g=dict(flex=round(pi_g + cu_g, 1), coiled_cord=round(cord_g)),
                open=["coverlay / base voltage rating (rule 6): not in the brochures; the vendor must confirm >= 630 V across 1.0 mm and through the coverlay",
                      "rolling-loop carrier inside the two-stage telescope (mock-up)", "polyimide eps and the dynamic flex life at 40 x stack"])

def part_b():
    import rf2_zones as Z
    pts = {"front end near the rim (MP1 fin, r 95 mm, az 170 deg, z 12)": (95 * math.cos(math.radians(170)), 95 * math.sin(math.radians(170)), 12.0),
           "head centre (r 30 mm, z 12)": (30.0, 0.0, 12.0)}
    side, h, t = 12.0, 3.0, 0.254                                                                           # can 12 x 12 x 3 mm, 0.254 mm (ProtoShield / etched shield thickness)
    r_eq = side / math.sqrt(math.pi); out = {}
    for name, P in pts.items():
        b = float(np.linalg.norm(Z.Bc(np.array(P))[0])); phi = b * math.pi * r_eq ** 2 * 1e-6
        worst = None
        for sig in (3.0e6, 1.0e7, 1.6e7, 3.5e7, 5.8e7):                                                     # nickel silver .. copper (conductivities ASSUMED; not in the brochures)
            e_wall, tau_w = Z.loop_echo(phi, r_eq * 1e-3, h * 1e-3, 0, sig, t * 1e-3)
            e_lid, tau_l = Z.loop_echo(phi, r_eq * 0.6e-3, r_eq * 0.5e-3, 0, sig, t * 1e-3)                 # lid as an equivalent ring (first order)
            e = e_wall + e_lid
            if worst is None or e > worst["echo"]: worst = dict(sigma=sig, echo=e, tau_us=round(max(tau_w, tau_l) * 1e6, 3))
        # slotted lid + walls broken at one corner: loops limited to 1 mm fingers (comb etched across the lid)
        wf = 1.0; n_f = int(side / (2 * wf)); phi_f = b * (wf * side) * 1e-6
        e_slot = max(n_f * Z.loop_echo(phi_f, wf / 2 * 1e-3 + 0.0005, t * 1e-3, 0, s, t * 1e-3)[0] for s in (3.0e6, 1.0e7, 1.6e7, 3.5e7, 5.8e7))
        out[name] = dict(B_uT_per_A=round(b * 1e6, 2), closed_can=dict(echo_x_gate_noise=round(worst["echo"] / Z.NOISE_GATE, 3), drift5K_x_noise=round(worst["echo"] * 0.02 / Z.NOISE_GATE, 4),
                         worst_sigma=worst["sigma"], tau_us=worst["tau_us"]), slotted=dict(echo_x_gate_noise=round(e_slot / Z.NOISE_GATE, 4), drift5K_x_noise=round(e_slot * 0.02 / Z.NOISE_GATE, 5)))
        out[name]["closed_ok"] = out[name]["closed_can"]["drift5K_x_noise"] <= 0.5; out[name]["slotted_ok"] = out[name]["slotted"]["drift5K_x_noise"] <= 0.5
    return dict(can_mm=[side, side, h], t_mm=t, criterion="drift for a 5 K step (2 %) <= 0.5 x the gate noise (rf2_system); static echo removed by the offset", places=out,
                note="cold-rolled steel is excluded (ferromagnetic); slotted = photo-etched comb lid and a wall break so no closed loop (eddy rule 5)")

def part_c():
    T = 0.010 * 25.4; L, w, defl = 10.0, 1.5, 0.8                                                           # finger 10 mm free length, 1.5 mm wide, 0.8 mm deflection at mating (ASSUMED)
    E, sy = 128e3, 1000.0                                                                                   # MPa: BeCu C172 heat-treated (ASSUMED typical values; not in the brochures)
    I = w * T ** 3 / 12; F = 3 * E * I * defl / L ** 3; sig = 6 * F * L / (w * T ** 2)
    rules = dict(min_finger_w_ge_T=w >= T, pitch_ge_0p050in=2.54 >= 0.050 * 25.4, bend_r_mm=round(0.7 * T, 3), bend_rule="C172 1/2 H: 0.5 T across, 0.7 T at 45 deg, 1.1 T with the grain (Tech Etch table 5)")
    return dict(material="BeCu C172 1/2 H, 0.254 mm, gold-plated contact area (Tech Etch finishing)", n=4, pitch_mm=2.54, free_len_mm=L, width_mm=w, deflection_mm=defl,
                force_N=round(F, 2), stress_MPa=round(sig), stress_frac_of_yield=round(sig / sy, 2), rules=rules, ok=bool(all(v for k, v in rules.items() if isinstance(v, bool)) and sig < 0.6 * sy),
                use="BMS signal contacts (SDA, SCL, TS2 wake, sense) on the drill-style dock; power stays on the MT60", note="E and yield ASSUMED (typical BeCu); contact resistance and cycle life: vendor test")

def main():
    res = dict(status="MODELED: vendor capability brochures; voltage ratings, dielectric constants, conductivities, spring constants ASSUMED where marked", A_cord_to_flex=part_a(), B_shield_can=part_b(), C_becu_fingers=part_c())
    a = res["A_cord_to_flex"]; b = res["B_shield_can"]["places"]; c = res["C_becu_fingers"]
    res["findings"] = [
        f"A: the cord as a {a['width_mm']} mm single-layer 2 oz flex (TX traces {a['tx_trace_mm']} mm, 1.0 mm rule-6 gaps) fits the {a['bore_mm']} mm bore; split at REF3T the pieces are "
        f"{a['segments']['seg1_dynamic_mm']} mm (rolling loop for {a['travel_mm']} mm travel) and {a['segments']['seg2_static_mm']} mm, inside Tech Etch's {a['te_limit_mm']['preferred']} mm preferred length; "
        f"TX strips {a['tx_capacitance'][1]['C_pF_per_m']} pF/m over {a['tx_length_m']} m (eps_eff 1.6 ASSUMED) -> first gate +{a['first_gate_shift_us']} us (rf2_timing_cord; the wire pair gave +{a['first_gate_shift_wire_us']} us); "
        f"mass {a['mass_g']['flex']} g vs about {a['mass_g']['coiled_cord']} g",
        "B: " + "; ".join(f"{k}: closed can drift {v['closed_can']['drift5K_x_noise']} x noise ({'ok' if v['closed_ok'] else 'FAILS'}), slotted {v['slotted']['drift5K_x_noise']}" for k, v in b.items()),
        f"C: 0.254 mm BeCu fingers 10 x 1.5 mm give {c['force_N']} N at 0.8 mm at {int(100 * c['stress_frac_of_yield'])} % of an ASSUMED 1000 MPa yield; Tech Etch geometry rules met: {c['ok']}"]
    res["ok"] = bool(a["fits_bore"] and a["lengths_ok"])
    json.dump(res, open(os.path.join(OUT, "rf2_flex_options.json"), "w"), indent=1, default=float)
    for f in res["findings"]: print("-", f)
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
