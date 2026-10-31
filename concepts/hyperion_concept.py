#!/usr/bin/env python3
"""Project Hyperion conical log-spiral PI head (owner concept, 2026-10-31): isolated evaluation. MODELED.

No AXE2 rule or geometry constrains this study; AXE2 values appear only in the final comparison. Physics from concepts/clib.py (magpylib Biot-Savart,
Neumann inductance, PI tail, eddy echo), self-checked against closed forms.

Studies (each writes its own block of concepts/out/hyperion_concept.json):
  1 reproduce   the concept's own Python, run as written, plus an exact 3D Biot-Savart of the same geometry; what makes its +11.9 %
  2 coils       physical builds in one 300 x 18 mm housing (flat skid at z = 0, every coil above the same floor): conical log spiral (7 deg as
                simulated, 3.5 deg as drawn), flat log spiral, the concept's linear flat reference, a rim bundle, the spiral scaled into the AXE2
                envelope, and the AXE2 coil itself (26 turns, rf2_head comb): L, R, winding C, B per A with depth, local fall-off exponent,
                beam width, B per sqrt(J), first sample, echo of test targets and modelled depth
  3 spin        the 3-phase "spinning vortex": three interleaved spirals (as written) and three 120 deg sector coils (the only build that tilts the field)
  4 ferrite     Fair-Rite 78 segmented backing (image-coil model) and its fit in the 18 mm stack
  5 shields     0.05 mm nanocrystalline sheets below / above the coil; the >85 dB claim
  6 rx          Metatron's Cube micro-coil RX (13 planar nodes, 0.25 / 0.25 mm, 2 oz): coupling, differential nulling, ground with tilt, target depth penalty
  7 parts       IXTY02N100D, BAV199, OPA211, litz 1050/48: what each does in this circuit
  8 claims      every numeric claim in the concept text against the model
  9 axe2        side-by-side with AXE2
Meshes: concepts/out/hyp_*.stl, hyperion_concept.step.   usage: python3 concepts/hyperion_concept.py"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); sys.path.insert(0, HERE); os.makedirs(OUT, exist_ok=True)
import clib as K
import magpylib as magpy

# ---------------- concept values (from the concept text) and ASSUMED values
R_HOUSING, H_STACK, WALL = 0.150, 0.018, 0.002               # 300 mm OD, 18 mm stack; 2 mm skid / wall ASSUMED
N_T, R0, R1, I_C = 20, 0.050, 0.150, 10.0                     # 20 turns, 50-150 mm, 10 A
ALPHA_SIM, RISE_DRAWN = math.radians(7.0), 6.13e-3           # simulated cone angle; "center offset +6.13 mm" in the drawing
LITZ_OD = 2.12e-3; STRAND_D = 0.0315e-3; N_STRAND = 1050      # 1050 / 48 AWG Type 2 litz
A_CU = N_STRAND * math.pi / 4 * STRAND_D ** 2                 # 0.818 mm2
A_EQ = math.sqrt(A_CU / math.pi)                               # equivalent solid-wire radius for the GMD
R_PER_M = 1.72e-8 / A_CU * 1.03                                # +3 % twist (ASSUMED)
LITZ_G_PER_M = A_CU * 1e6 * 8.96 + 2.6                         # copper + serving / insulation 2.6 g/m (ASSUMED)
EPS_SERVE = 2.2                                                # effective eps between served litz turns (ASSUMED)
FLEX_Z = WALL + 0.10e-3                                        # RX / Faraday flex sits on the skid
Z_LOW = WALL + 0.25e-3 + LITZ_OD / 2                          # lowest wire centre above the floor
C_EXT = 60e-12                                                 # switch + clamp + preamp node C for the fast-switch case (ASSUMED)
V_CLAMP_SIC = 460.0                                            # 900 V-class SiC switch, 460 V clamp (same class as the earlier concept study)
SIGMA_AU, SIGMA_AG = 4.1e7, 6.1e7
NOISE_nV, BW_HZ, N_AVG, SNR = 1.1, 1e6, 1000, 5.0              # OPA211 1.1 nV/rtHz; 1 MHz band, 1000-pulse average, SNR 5 (ASSUMED)
V_TH = SNR * NOISE_nV * 1e-9 * math.sqrt(BW_HZ) / math.sqrt(N_AVG)
DEPTHS = np.geomspace(0.02, 1.5, 70)

def logspiral(r0, r1, turns, z_of_r, n=1600, phase=0.0, sign=1):
    th = np.linspace(0, 2 * math.pi * turns, n); b = math.log(r1 / r0) / (2 * math.pi * turns); r = r0 * np.exp(b * th)
    return np.c_[r * np.cos(sign * th + phase), r * np.sin(sign * th + phase), z_of_r(r)]

def cone(alpha, r0=R0, z0=Z_LOW): return lambda r: z0 + (r - r0) * math.tan(alpha)
def flat(z0=Z_LOW): return lambda r: np.full_like(r, z0)

def B(paths, I, pts):
    pts = np.atleast_2d(np.asarray(pts, float)); out = np.zeros((len(pts), 3))
    for p in paths: out += np.atleast_2d(K.polyline_B(p, I, pts))
    return out

def plen(p): return float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))

def winding_C(paths_or_spiral, pitch_fn, n):
    """chain estimate (adjacent-turn coupling only, a lower bound): 1/C = sum 1/C_pair over the N-1 turn pairs"""
    inv = 0.0
    for k in range(n - 1):
        r_k, p = pitch_fn(k); s = max(p, LITZ_OD * 1.001)
        inv += 1.0 / (K.c_parallel_wires(s, LITZ_OD / 2, EPS_SERVE) * 2 * math.pi * r_k)
    return 1.0 / inv

# ---------------------------------------------------------------- 1. reproduce the concept's own simulation
def reproduce():
    mu0 = 4 * np.pi * 1e-7; I = 10.0
    radii_flat = np.linspace(0.05, 0.15, 20); theta = np.linspace(0, 20 * 2 * np.pi, 2000); a = 0.05; b = np.log(0.15 / 0.05) / (20 * 2 * np.pi)
    r_s = a * np.exp(b * theta); z_s = -(0.15 - r_s) * np.tan(np.radians(7.0)); dt = theta[1] - theta[0]
    def flat_bz(ze): return float(sum((mu0 * I * r ** 2) / (2 * (r ** 2 + ze ** 2) ** 1.5) for r in radii_flat))
    def hyp_bz(ze): R = np.sqrt(r_s[:-1] ** 2 + (ze - z_s[:-1]) ** 2); return float(np.sum(mu0 * (I / 20.0) * r_s[:-1] ** 2 * dt / (4 * np.pi * R ** 3)) * 20.0)
    rows = {}
    for lab, ze in (("1 cm", -0.01), ("30 cm", -0.30), ("100 cm", -1.0)):
        rows[lab] = dict(planar_uT=round(flat_bz(ze) * 1e6, 2), hyperion_uT=round(hyp_bz(ze) * 1e6, 2))
    # the same geometry with exact 3D Biot-Savart (magpylib); the concept's sum carries I/20 per element and x20, i.e. 10 A in each of 20 turns
    sp = np.c_[r_s * np.cos(theta), r_s * np.sin(theta), z_s]; fl = [K.circle(r, 0.0, 128) for r in radii_flat]
    exact = {lab: dict(planar_uT=round(float(B(fl, I, [[0, 0, ze]])[0, 2]) * 1e6, 2), hyperion_uT=round(float(B([sp], I, [[0, 0, ze]])[0, 2]) * 1e6, 2))
             for lab, ze in (("1 cm", -0.01), ("30 cm", -0.30), ("100 cm", -1.0))}
    # decomposition at 1 cm: which part of the gain is the log spacing, which is the cone moving the inner turns 12.3 mm closer to the evaluation point
    sp_flat = np.c_[r_s * np.cos(theta), r_s * np.sin(theta), np.zeros_like(r_s)]
    lin_cone = [K.circle(r, -(0.15 - r) * math.tan(math.radians(7.0)), 128) for r in radii_flat]
    dec = {}
    for lab, ze in (("1 cm", -0.01), ("30 cm", -0.30)):
        p0 = float(B(fl, I, [[0, 0, ze]])[0, 2])
        dec[lab] = dict(log_spacing_only_pct=round((float(B([sp_flat], I, [[0, 0, ze]])[0, 2]) / p0 - 1) * 100, 1),
                        cone_only_pct=round((float(B(lin_cone, I, [[0, 0, ze]])[0, 2]) / p0 - 1) * 100, 1),
                        both_pct=round((float(B([sp], I, [[0, 0, ze]])[0, 2]) / p0 - 1) * 100, 1))
    # same floor: in a housing both coils sit on the same skid, so the flat coil goes down to the cone's lowest point (z = -12.3 mm in their frame)
    fl_low = [K.circle(r, -0.10 * math.tan(math.radians(7.0)), 128) for r in radii_flat]
    same_floor = {lab: round((float(B([sp], I, [[0, 0, ze]])[0, 2]) / float(B(fl_low, I, [[0, 0, ze]])[0, 2]) - 1) * 100, 1)
                  for lab, ze in (("1 cm", -0.022), ("30 cm", -0.3123), ("100 cm", -1.0123))}
    claimed = {"1 cm": (1361.40, 1523.31), "30 cm": (40.95, 36.86), "100 cm": (1.34, 1.14)}
    return dict(concept_code_rerun=rows, claimed_log={k: dict(planar_uT=v[0], hyperion_uT=v[1]) for k, v in claimed.items()}, exact_biot_savart=exact,
                gain_decomposition=dec, hyperion_vs_flat_same_floor_pct=same_floor,
                notes=["the concept's own numbers re-run to the printed precision: the code is reproducible",
                       "its evaluation point at '1 cm' (z = -10 mm) lies ABOVE the innermost turns (z = -12.3 mm): the +11.9 % is the inner turns being moved past the probe point",
                       "its flat reference sits at the cone's outer (highest) edge; on a common skid floor the flat coil drops 12.3 mm and the cone loses at every depth",
                       "its own log already shows the cone 10 % weaker at 30 cm and 15 % weaker at 100 cm: there is no focusing at depth"])

# ---------------------------------------------------------------- 2. physical coils in the same housing
def axe2_turns():
    cols = [round(113.4 - 1.77 * k, 2) for k in range(5)]; z0, rp = 4.49, 1.44
    return [K.circle(cols[j % 5] * 1e-3, (z0 + (j // 5) * rp) * 1e-3, 96) for j in range(26)]

def coil_set():
    sims = {}
    sims["HYP_CONE_7deg"] = dict(paths=[logspiral(R0, R1, N_T, cone(ALPHA_SIM))], kind="spiral", note="conical log spiral as simulated (7 deg; outer turns 12.3 mm up)")
    sims["HYP_CONE_drawn_3p5deg"] = dict(paths=[logspiral(R0, R1, N_T, cone(math.atan(RISE_DRAWN / (R1 - R0))))], kind="spiral", note="as drawn (6.13 mm rise over 100 mm = 3.5 deg)")
    sims["LOG_SPIRAL_FLAT"] = dict(paths=[logspiral(R0, R1, N_T, flat())], kind="spiral", note="same log spiral, flat on the skid")
    sims["LINEAR_FLAT_REF"] = dict(paths=[K.circle(r, Z_LOW, 128) for r in np.linspace(R0, R1, N_T)], kind="loops", note="the concept's flat reference (20 loops 50-150 mm), on the skid")
    rim = []
    for j in range(N_T):
        rim.append(K.circle(R_HOUSING - WALL - 0.5e-3 - LITZ_OD / 2 - (j % 4) * LITZ_OD * 1.02, Z_LOW + (j // 4) * LITZ_OD * 1.02, 128))
    sims["RIM_BUNDLE_300"] = dict(paths=rim, kind="loops", note="same wire, same turns, a 4 x 5 bundle at the rim of the same 300 mm housing")
    sims["HYP_CONE_in_233"] = dict(paths=[logspiral(0.038, 0.110, N_T, cone(ALPHA_SIM, 0.038, 4.49e-3))], kind="spiral", note="the conical spiral scaled into the AXE2 233 x 25.4 envelope")
    sims["AXE2_COIL"] = dict(paths=axe2_turns(), kind="loops", note="AXE2 rim mono coil (26 turns, Rubadue TXXL66/38F-2 comb, rf2_head)", a_wire=math.sqrt(66 * math.pi / 4 * (0.101e-3) ** 2 / math.pi),
                             R_ohm=0.601, I_scan=8.06)
    return sims

def coil_metrics(name, c, ref_E=None):
    paths = c["paths"]; a = c.get("a_wire", A_EQ)
    L = K.self_L(paths[0], a, 1) if c["kind"] == "spiral" else K.coil_L(paths, a, 2)
    wire = sum(plen(p) for p in paths); R = c.get("R_ohm", wire * R_PER_M)
    if c["kind"] == "spiral":
        p = paths[0]; r = np.hypot(p[:, 0], p[:, 1]); tpk = len(p) // N_T
        Cw = winding_C(None, lambda k: (r[k * tpk], abs(r[min((k + 1) * tpk, len(p) - 1)] - r[k * tpk])), N_T)
    else:
        rs = [float(np.hypot(*q[0, :2])) for q in paths]; zs = [float(q[0, 2]) for q in paths]
        Cw = winding_C(None, lambda k: (rs[k], math.hypot(rs[k + 1] - rs[k], zs[k + 1] - zs[k])), len(paths))
    if name == "AXE2_COIL": Cw = None
    pts = np.c_[np.zeros_like(DEPTHS), np.zeros_like(DEPTHS), -DEPTHS]
    bz = np.abs(B(paths, 1.0, pts)[:, 2])
    lb, lz = np.log(bz), np.log(DEPTHS); expo = -np.gradient(lb, lz)
    xs = np.linspace(0, 0.6, 61); prof = np.linalg.norm(B(paths, 1.0, np.c_[xs, np.zeros_like(xs), np.full_like(xs, -0.30)]), axis=1) ** 2
    fwhm = 2 * float(np.interp(0.5, prof[::-1] / prof[0], xs[::-1]))
    I = c.get("I_scan", I_C) if ref_E is None else math.sqrt(2 * ref_E / L)
    C_node = (Cw or 0.0) + C_EXT
    fs = K.pi_first_sample(L, C_node, I, V_CLAMP_SIC)
    return dict(L_uH=round(L * 1e6, 1), R_ohm=round(R, 3), wire_m=round(wire, 2), C_wind_pF=None if Cw is None else round(Cw * 1e12, 1), _bz=bz, _expo=expo,
                B_per_A_uT={f"{int(round(d * 1000))} mm": round(float(np.interp(d, DEPTHS, bz)) * 1e6, 3) for d in (0.05, 0.10, 0.30, 0.50, 1.0)},
                falloff_exponent={f"{int(round(d * 1000))} mm": round(float(np.interp(d, DEPTHS, expo)), 2) for d in (0.05, 0.10, 0.30, 0.50, 1.0)},
                beam_FWHM_at_300mm_mm=round(fwhm * 1000), B300_per_sqrtJ_uT=round(float(np.interp(0.3, DEPTHS, bz)) / math.sqrt(0.5 * L) * 1e6, 1),
                B300_sq_per_ohm=round(float(np.interp(0.3, DEPTHS, bz)) ** 2 / R * 1e12, 2), I_A=round(I, 2), E_mJ=round(0.5 * L * I ** 2 * 1e3, 2),
                P_I2R_W_at_10pct_duty=round(I ** 2 * R * 0.10, 2), mass_wire_g=round(wire * (LITZ_G_PER_M if name != "AXE2_COIL" else 6.9)),
                first_sample_us_SiC460=round(fs["first_sample_us"], 2), fall_us=round(fs["fall_us"], 2), _L=L, _I=I)

TARGETS = dict(gold_1g=dict(r=2e-3, w=2e-3, t=2e-3, sigma=SIGMA_AU, area=math.pi * 2e-3 ** 2),
               gold_0p1g_small=dict(r=0.8e-3, w=0.8e-3, t=0.5e-3, sigma=SIGMA_AU, area=math.pi * 1.2e-3 ** 2),
               silver_coin_25mm=dict(r=8e-3, w=8e-3, t=2e-3, sigma=SIGMA_AG, area=math.pi * 12.5e-3 ** 2),
               gold_flake_0p5mm=dict(r=0.125e-3, w=0.125e-3, t=0.05e-3, sigma=SIGMA_AU, area=math.pi * 0.25e-3 ** 2))

def echo(bz_per_A, I, t_s, tg):
    v, tau = K.eddy_echo(bz_per_A * tg["area"], tg["r"], tg["w"], tg["t"], tg["sigma"], I, t_s); return v, tau

def depth_for(m, t_s, tg):
    v = np.array([echo(b, m["_I"], t_s, tg)[0] for b in m["_bz"]])
    if v[0] < V_TH: return 0.0
    return float(np.exp(np.interp(math.log(V_TH), np.log(v[::-1]), np.log(DEPTHS[::-1]))))

# ---------------------------------------------------------------- 3. spin
def spin():
    res = {}
    ph = [logspiral(R0, R1, 7, flat(), 700, phase=2 * math.pi * k / 3) for k in range(3)]
    pts = [[0, 0, -0.10], [0, 0, -0.30], [0.10, 0, -0.30], [0, 0.10, -0.30]]
    Bs = [B([p], 1.0, pts) for p in ph]
    def ang(u, v): return math.degrees(math.acos(max(-1, min(1, float(np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v))))))
    res["interleaved_spirals_as_written"] = dict(max_angle_between_phase_fields_deg={str(pts[i]): round(max(ang(Bs[a][i], Bs[b][i]) for a in range(3) for b in range(3)), 2) for i in range(len(pts))},
                                                 note="three interleaved 120-deg-rotated spirals are three copies of the same axisymmetric source: the field directions agree to a fraction of a degree, so sequencing them spins nothing")
    sect = []
    for k in range(3):
        a0 = 2 * math.pi * k / 3 + math.radians(3); a1 = a0 + math.radians(114); loops = []
        for j in range(7):
            ro, ri = 0.140 - j * 3e-3, 0.025 + j * 3e-3; t1 = np.linspace(a0, a1, 60); t2 = t1[::-1]
            loop = np.r_[np.c_[ri * np.cos(a0), ri * np.sin(a0), Z_LOW], np.c_[ro * np.cos(t1), ro * np.sin(t1), np.full(60, Z_LOW)], np.c_[ri * np.cos(t2), ri * np.sin(t2), np.full(60, Z_LOW)]]
            loops.append(np.r_[loop, loop[:1]])
        sect.append(loops)
    allp = sum(sect, [])
    out = {}
    for d in (0.10, 0.30, 0.50):
        bt = B(allp, 1.0, [[0, 0, -d]])[0]; bi = [B(s, 1.0, [[0, 0, -d]])[0] for s in sect]
        tilt = [round(math.degrees(math.atan2(math.hypot(b[0], b[1]), abs(b[2]))), 1) for b in bi]
        edge = max(abs(b[0]) for b in bi) ** 2 / bt[2] ** 2
        out[f"{int(d * 1000)} mm"] = dict(tilt_each_phase_deg=tilt, edge_on_coin_coupling_vs_flat_coin_all_phases=round(edge, 4),
                                          single_phase_flat_coin_vs_all=round((bi[0][2] / bt[2]) ** 2, 3))
    res["sector_coils_alternative"] = dict(per_depth=out, note="three 120-deg sector coils fired in turn DO tilt the field off the axis: an edge-on coin couples a few % of a flat one at shallow depth, falling with depth; each phase alone has about 1/9 of the full coil's squared field on axis")
    res["timing"] = "the target stores the field present at each turn-off; a 25 kHz 'rotation' during the pulse is not seen by the target. Sequential phases are three separate measurements: 3 x the TX time per reading"
    return res, ph, sect

# ---------------------------------------------------------------- 4. ferrite backing (Fair-Rite 78)
def ferrite(base):
    mu_i, rho = 2300, 2.0                                             # Fair-Rite 78 data: mu_i 2300, rho 200 ohm cm (fair-rite.com, read 2026-10-31)
    f_cov = 0.85; g = 1.0e-3                                          # 85 % ring coverage, 1 mm above the wire (ASSUMED block layout; 9478012002-MOD not a catalogue part)
    p = logspiral(R0, R1, N_T, flat()); z_f = Z_LOW + LITZ_OD / 2 + g
    img = p.copy(); img[:, 2] = 2 * z_f - p[:, 2]; k = f_cov * (mu_i - 1) / (mu_i + 1)
    L0 = K.self_L(p, A_EQ, 1); M = K.mutual(p, img, 1); L1 = L0 + k * M
    b0 = B([p], 1.0, [[0, 0, -0.30]])[0, 2]; b1 = b0 + k * B([img], 1.0, [[0, 0, -0.30]])[0, 2]
    flux = L1 * I_C / N_T; Bf = flux / (2 * math.pi * 0.10 * 3e-3)
    blocks_cm3 = 24 * 4.0 * 2.6 * 0.3
    return dict(L_uH=[round(L0 * 1e6, 1), round(L1 * 1e6, 1)], B300_gain=round(b1 / b0, 3), B300_per_sqrtL_gain=round((b1 / b0) / math.sqrt(L1 / L0), 3),
                echo_gain_equal_energy=round(((b1 / b0) ** 2) / math.sqrt(L1 / L0), 3), ferrite_B_at_10A_T=round(Bf, 3), Bsat_T=0.48,
                mass_g=round(blocks_cm3 * 4.8), first_sample_ratio=round(math.sqrt(L1 / L0), 3),
                fits_18mm_on_7deg_cone=bool(Z_LOW + 0.1 * math.tan(ALPHA_SIM) + LITZ_OD / 2 + g + 3e-3 <= H_STACK - 1.5e-3),
                top_of_ferrite_mm_on_7deg_cone=round((Z_LOW + 0.1 * math.tan(ALPHA_SIM) + LITZ_OD / 2 + g + 3e-3) * 1e3, 2),
                note="a high-mu backing works as a magnetic mirror: more field below for the same current, but L rises with it; per joule the gain is small. MnZn ferrite also carries a slow magnetic after-effect (disaccommodation / viscosity) that shows as a late tail in PI: magnitude UNVERIFIED, must be measured")

# ---------------------------------------------------------------- 5. nanocrystalline sheets
def shields(base_paths):
    mu_r, rho, t, dens = 50000, 1.2e-6, 0.05e-3, 7.3           # FINEMET-class nanocrystalline (ASSUMED: Magnetics 'NC-0050-S' not found)
    sig = 1 / rho; k_sp = 1 / 0.10                               # dominant spatial wavenumber of a 100 mm-radius coil
    T_below = 1 / (1 + mu_r * t * k_sp / 2)                      # thin permeable sheet transmission for the k-component (static)
    tau_mag = K.MU0 * mu_r * sig * t ** 2 / math.pi ** 2
    lo, tau_e = K.eddy_echo(1.0, 0.075, 0.075, t, sig, 1.0, 1e-6)
    S_closed = 1 + mu_r * 2 * t / (2 * R_HOUSING)
    return dict(transmission_below_static=round(T_below, 4), field_loss_dB=round(-20 * math.log10(T_below), 1),
                eddy_tau_us=round(tau_e * 1e6, 2), ferro_relax_tau_us=round(tau_mag * 1e6, 1), closed_shell_shielding_dB=round(20 * math.log10(S_closed), 1),
                mass_g_two_sheets=round(2 * math.pi * 0.148 ** 2 * t * dens * 1e6, 1),
                notes=["a lower sheet sits between the coil and the ground: it shunts the field sideways (about the dB above at DC) and is itself a conducting, ferromagnetic disc inside the coil (eddy and ferromagnetic decay at the taus above)",
                       "even a closed two-layer shell gives the closed-shell figure above at DC; a PI head must be open toward the ground, so >85 dB (17 800 x) from 10 Hz to 500 kHz is not reachable by any sheet that lets the TX out",
                       "an upper sheet only is a known option (shields the electronics side) but it is a ferromagnetic target inside the coil: place it far above the winding or omit it"])

# ---------------------------------------------------------------- 6. Metatron RX
def node_turn_radii(r_out=26e-3, r_in=8e-3, pitch=0.5e-3): return np.arange(r_out, r_in, -pitch)
NODE_C = [(0.0, 0.0)] + [(2 * 27e-3 * math.cos(k * math.pi / 3), 2 * 27e-3 * math.sin(k * math.pi / 3)) for k in range(6)] + \
         [(4 * 27e-3 * math.cos(k * math.pi / 3), 4 * 27e-3 * math.sin(k * math.pi / 3)) for k in range(6)]

def node_flux(src_paths, cx, cy, z, I=1.0, tilt=0.0):
    radii = node_turn_radii(); rr = np.linspace(0, radii[0], 22)[1:]; tt = np.linspace(0, 2 * math.pi, 37)[:-1]
    R_, T_ = np.meshgrid(rr, tt); x = cx + R_ * np.cos(T_); y = cy + R_ * np.sin(T_); zz = np.full_like(x, z) + x * math.tan(tilt)
    Bz = B(src_paths, I, np.c_[x.ravel(), y.ravel(), zz.ravel()])[:, 2].reshape(x.shape)
    n_enc = np.array([np.sum(radii > r) for r in rr]); dA = rr * (rr[1] - rr[0]) * (tt[1] - tt[0])
    return float(np.sum(Bz * n_enc[None, :] * dA[None, :]))

def node_paths(cx, cy, z): return [K.circle(r, z, 48, cx, cy) for r in node_turn_radii()]

def metatron(tx):
    radii = node_turn_radii(); n = len(radii); length = float(np.sum(2 * math.pi * radii)); R = length * 1.72e-8 / (0.25e-3 * 70e-6)
    M = [node_flux([tx], cx, cy, FLEX_Z) for cx, cy in NODE_C]
    Ltx = K.self_L(tx, A_EQ, 1); t_fall = Ltx * I_C / V_CLAMP_SIC
    pair = abs(M[1] - M[4]); d = 0.1e-3
    dMdx = abs(node_flux([tx], NODE_C[1][0] + d, NODE_C[1][1], FLEX_Z) - M[1]) / d
    # target: 25 mm coin as a vertical dipole excited by the TX at depth zt, offset 50 mm in x; reciprocity: flux = m . B_rx_per_A(target)
    out_t = {}
    for zt in (0.10, 0.30, 0.50):
        tp = np.array([[0.05, 0, -zt]]); m_dir = B([tx], 1.0, tp)[0]
        mono = float(np.dot(m_dir, B([tx], 1.0, tp)[0]))
        nb = [float(np.dot(m_dir, B(node_paths(cx, cy, FLEX_Z), 1.0, tp)[0])) for cx, cy in NODE_C]
        out_t[f"{int(zt * 1000)} mm"] = dict(single_node_vs_mono=round(abs(nb[0]) / abs(mono), 4), best_pair_diff_vs_mono=round(max(abs(nb[i] - nb[i + 3]) for i in (1, 2, 3, 7, 8, 9)) / abs(mono), 5))
    # ground: magnetic half-space 20 mm below the skid (image of the TX, weight chi / (2 + chi)), head level and tilted 3 deg
    def ground_pair(tilt):
        h = 0.020; txt = tx.copy(); txt[:, 2] = txt[:, 2] + txt[:, 0] * math.tan(tilt); img = txt.copy(); img[:, 2] = -2 * h - txt[:, 2]
        f = [node_flux([img], cx, cy, FLEX_Z, tilt=tilt) for cx, cy in NODE_C]
        return f, max(abs(f[i] - f[i + 3]) for i in (1, 2, 3, 7, 8, 9)), abs(f[1])
    _, lev, single = ground_pair(0.0); _, til, single_t = ground_pair(math.radians(3))
    return dict(nodes=13, layout="Metatron's Cube: centre, 6 at 54 mm, 6 at 108 mm; node radius 26 mm", turns_per_node=n, trace="0.25 / 0.25 mm, 2 oz (70 um)",
                R_node_ohm=round(R, 2), johnson_nV=round(K.johnson_noise_nV(R), 2), L_node_uH=round(K.coil_L(node_paths(0, 0, 0), 35e-6, 1) * 1e6, 1),
                M_tx_node_uH=[round(m * 1e6, 3) for m in M], V_node_at_turnoff_V=[round(abs(m) * I_C / t_fall, 1) for m in M[:2] + M[7:8]],
                pair_residual_uH=round(pair * 1e6, 4), residual_per_0p1mm_misplacement_uH=round(dMdx * d * 1e6, 4),
                V_pair_residual_per_0p1mm_V=round(dMdx * d * I_C / t_fall, 2), target_coupling=out_t,
                ground_pair_rejection_level=round(lev / single, 5), ground_pair_rejection_tilt3deg=round(til / single_t, 4),
                notes=["planar coils on a flat flex sense only the field normal to the board; '45 / 90 degree vector planes' need folded or vertical coils (an 18 mm stack limits a vertical node to about 14 mm x 50 mm)",
                       "single nodes inside the TX see the full primary: tens to hundreds of volts at turn-off; they are not in a null",
                       "opposite node pairs cancel the TX and a level, uniform ground by symmetry (a gradiometer); the same symmetry cancels a centred target, and a 3 deg tilt breaks the ground balance",
                       "a 26 mm node collects a few % of the mono coil's target flux; differential pairs collect less at depth (gradient falls one power of z faster)"])

# ---------------------------------------------------------------- 7. parts
def parts():
    return dict(
        IXTY02N100D=dict(status="UNVERIFIED: no datasheet found for this part number; the IXTY01N100D family sheet (IXYS 2006) gives 1000 V, ID 100 mA, RDS(on) 90-110 ohm at VGS 0; distributors list 400 mA (Tc) / 80 ohm",
                         finding="a depletion-mode small-signal FET conducts ~0.1-0.4 A class current with ~80-110 ohm on-resistance: it cannot carry a 10 A coil pulse (10 A x 80 ohm = 800 V drop). Normally-on: with no gate bias at power-up it shorts the coil across the supply. Used in PI as a current source or start-up device, not as the TX switch",
                         I_reachable_A_3_parallel=1.2, B_ratio_vs_10A=0.12),
        BAV199=dict(source="NXP/Philips BAV199 datasheet: VR 75 V, VRRM 85 V, IF 160 mA, leakage typ 3 pA, trr 0.8 typ / 3 us max (10 mA / 10 mA), Cd 2 pF",
                    finding="a good low-leakage preamp clamp, but slow: its 0.8-3 us recovery after the flyback alone exceeds the claimed 0.8 us settle. It is not a Schottky and not fast-recovery"),
        OPA211=dict(source="TI SBOS377L: 1.1 nV/rtHz at 1 kHz, GBW 80 MHz (G 100) / 45 MHz (G 1), 27 V/us, +-2.25 to +-18 V, settling 700 ns to 16 bit",
                    finding="a sound PI preamp choice; its settling (0.7 us) and overload recovery also sit at or above the claimed 0.8 us"),
        LITZ_1050_48=dict(source="MWS LITZ-1050-48-T2 sheet not obtained (UNVERIFIED part number); copper area from strand count: 1050 x 48 AWG = %.3f mm2, %.4f ohm/m" % (A_CU * 1e6, R_PER_M),
                          finding="text says silicone-insulated in one place and PU-nylon served in another; 22 m on the BOM vs about 11 m per 20-turn spiral"),
        FERRITE_9478012002=dict(source="not a Fair-Rite catalogue number (-MOD); 78 material data from fair-rite.com: mu_i 2300, Bsat 4800 G at 5 Oe, rho 200 ohm cm, Tc > 200 C", finding="see ferrite block"),
        NC_0050_S=dict(source="not found in Magnetics Inc literature: UNVERIFIED; modelled as FINEMET-class (mu_r 50 000, rho 1.2 uohm m, 7.3 g/cm3, ASSUMED)", finding="see shields block"))

# ---------------------------------------------------------------- main
def main():
    res = dict(status="MODELED; isolated from AXE2 rules; part values from datasheets where named, else UNVERIFIED / ASSUMED", selftest=K.selftest(),
               housing=dict(D_mm=300, stack_mm=18, skid_mm=WALL * 1e3, lowest_wire_centre_mm=round(Z_LOW * 1e3, 2)),
               assumptions=dict(litz_g_per_m=round(LITZ_G_PER_M, 1), eps_serve=EPS_SERVE, C_ext_pF=C_EXT * 1e12, V_clamp_fast_switch=V_CLAMP_SIC,
                                detection_threshold_uV=round(V_TH * 1e6, 3), threshold_basis="OPA211 1.1 nV/rtHz, 1 MHz, 1000-pulse average, SNR 5; no ground or EMI: absolute depths are optimistic, ratios are the result"))
    res["reproduce"] = reproduce(); print("reproduce", json.dumps(res["reproduce"]["concept_code_rerun"]), res["reproduce"]["hyperion_vs_flat_same_floor_pct"])
    sims = coil_set(); M = {}
    for k, c in sims.items(): M[k] = coil_metrics(k, c); print(k, M[k]["L_uH"], M[k]["B_per_A_uT"], M[k]["first_sample_us_SiC460"])
    E_ref = 0.5 * M["HYP_CONE_7deg"]["_L"] * I_C ** 2
    Meq = {k: coil_metrics(k, c, E_ref) for k, c in sims.items()}
    # AXE2 actual first gate (read-only reference from its own pipeline)
    ref = {}
    try:
        hc = json.load(open(os.path.join(HERE, "..", "rf2", "head", "out_BF", "rf2_head_check.json"))); ref["head_mass_g"] = hc["checks"]["mass_g"]["total_islands_only"]
        mc = json.load(open(os.path.join(HERE, "..", "rf2", "head", "out", "rf2_mp1v2_close.json"))); ref["first_sample_us"] = mc["first_gate_us"]
    except Exception as ex: ref["error"] = str(ex)
    ref.update(L_uH_design=333, I_scan_A=8.06, I_boost_A=12.74, envelope="D233 x 25.4 mm", R_coil_ohm=0.601)
    coils = {}
    for k in sims:
        m = M[k]; ts = ref.get("first_sample_us", m["first_sample_us_SiC460"]) * 1e-6 if k == "AXE2_COIL" else m["first_sample_us_SiC460"] * 1e-6
        dep = {t: round(depth_for(m, ts, tg) * 100, 1) for t, tg in TARGETS.items()}
        depE = {t: round(depth_for(Meq[k], ts, tg) * 100, 1) for t, tg in TARGETS.items()}
        coils[k] = {kk: v for kk, v in m.items() if not kk.startswith("_")}
        mc = dict(m, _I=1.2)
        coils[k].update(depth_cm_concept_driver_1p2A={t: round(depth_for(mc, ts, tg) * 100, 1) for t, tg in TARGETS.items()} if k.startswith("HYP") else None)
        coils[k].update(note=sims[k]["note"], depth_cm_at_own_current=dep, depth_cm_equal_energy=depE, I_equal_energy_A=Meq[k]["I_A"],
                        tau_us={t: round(echo(1e-6, 1, 0, tg)[1] * 1e6, 4) for t, tg in TARGETS.items()})
    res["coils"] = coils; res["E_ref_mJ"] = round(E_ref * 1e3, 2)
    # need: signal ratio for the claimed depth jump
    z1, z2 = 0.525, 1.225; mref = M["LINEAR_FLAT_REF"]
    s = lambda m, z: float(np.interp(z, DEPTHS, m["_bz"])) ** 2
    res["depth_claim"] = dict(claimed="45-60 cm -> 110-135 cm (> 100 %)", signal_ratio_needed=round(s(mref, z1) / s(mref, z2), 1),
                              modelled_ratio_cone_vs_flat_at_120cm=round(s(M["HYP_CONE_7deg"], z2) / s(mref, z2), 3),
                              falloff_exponent_signal_at_1m=round(2 * float(np.interp(1.0, DEPTHS, mref["_expo"])), 2))
    res["spin"], ph, sect = spin(); print("spin", res["spin"]["sector_coils_alternative"]["per_depth"]["300 mm"])
    res["ferrite"] = ferrite(None); print("ferrite", res["ferrite"])
    res["shields"] = shields(None); print("shields", res["shields"])
    tx_flat = sims["LOG_SPIRAL_FLAT"]["paths"][0]
    res["rx_metatron"] = metatron(sims["HYP_CONE_7deg"]["paths"][0]); print("rx", {k: v for k, v in res["rx_metatron"].items() if k != "notes"})
    res["parts"] = parts()
    hyp = coils["HYP_CONE_7deg"]; flt = coils["LINEAR_FLAT_REF"]; rim = coils["RIM_BUNDLE_300"]; ax = coils["AXE2_COIL"]
    settle_need_L = 0.8e-6 * V_CLAMP_SIC / I_C
    res["claims"] = [
        dict(claim="+11.89 % near-surface flux concentration", model=f"reproduced only because the probe point sits above the cone's inner turns; on a common floor the cone is {res['reproduce']['hyperion_vs_flat_same_floor_pct']['1 cm']} % at 1 cm, {res['reproduce']['hyperion_vs_flat_same_floor_pct']['30 cm']} % at 30 cm, {res['reproduce']['hyperion_vs_flat_same_floor_pct']['100 cm']} % at 100 cm vs the flat coil", verdict="not supported"),
        dict(claim="field decay shifts from 1/r^3 toward 1/r^2", model=f"local fall-off exponent of B at 0.3 / 0.5 / 1.0 m: cone {hyp['falloff_exponent']['300 mm']} / {hyp['falloff_exponent']['500 mm']} / {hyp['falloff_exponent']['1000 mm']}, flat {flt['falloff_exponent']['300 mm']} / {flt['falloff_exponent']['500 mm']} / {flt['falloff_exponent']['1000 mm']}: any finite loop tends to 3 far away", verdict="not supported"),
        dict(claim="downward-focused 'vortex jet' / parabolic column", model=f"beam FWHM of B^2 at 300 mm: cone {hyp['beam_FWHM_at_300mm_mm']} mm, flat {flt['beam_FWHM_at_300mm_mm']} mm, rim {rim['beam_FWHM_at_300mm_mm']} mm", verdict="not supported (width at depth is set by diameter)"),
        dict(claim="depth 110-135 cm vs 45-60 cm (> 100 %)", model=f"needs {res['depth_claim']['signal_ratio_needed']} x the target signal; the cone gives {res['depth_claim']['modelled_ratio_cone_vs_flat_at_120cm']} x the flat coil's at 120 cm", verdict="not supported"),
        dict(claim="flyback settles in < 0.8 us", model=f"cone coil {hyp['L_uH']} uH at 10 A: fall {hyp['fall_us']} us alone with a 460 V clamp, first sample {hyp['first_sample_us_SiC460']} us; 0.8 us needs L <= {settle_need_L * 1e6:.0f} uH before any settling; BAV199 trr 0.8-3 us", verdict="not supported"),
        dict(claim="3-phase spinning field removes blind spots", model="interleaved spirals: phase fields agree within %.2f deg at 300 mm; sector coils tilt the field %s deg at 300 mm" % (max(res["spin"]["interleaved_spirals_as_written"]["max_angle_between_phase_fields_deg"].values()), res["spin"]["sector_coils_alternative"]["per_depth"]["300 mm"]["tilt_each_phase_deg"]), verdict="not as written; partly with sector coils"),
        dict(claim="Rx in TX nulls (gamma -> 0)", model=f"node coupling {res['rx_metatron']['M_tx_node_uH'][0]} uH (centre), {res['rx_metatron']['V_node_at_turnoff_V'][0]} V at turn-off; pairs cancel by symmetry, residual {res['rx_metatron']['V_pair_residual_per_0p1mm_V']} V per 0.1 mm placement error", verdict="only as differential pairs (a gradiometer)"),
        dict(claim="> 85 dB EMI suppression 10 Hz-500 kHz", model=f"a closed two-layer shell gives {res['shields']['closed_shell_shielding_dB']} dB at DC; a lower sheet costs the TX {res['shields']['field_loss_dB']} dB", verdict="not supported"),
        dict(claim="resolves sub-millimetre targets / sub-grain gold", model=f"0.5 mm flake tau {coils['HYP_CONE_7deg']['tau_us']['gold_flake_0p5mm']} us: gone long before any first sample", verdict="not supported"),
        dict(claim="10 A pulse from IXTY02N100D", model="depletion FET class ~0.1-0.4 A, 80-110 ohm (family data; part UNVERIFIED)", verdict="not supported")]
    res["axe2_compare"] = dict(reference=ref, rows={k: dict(L_uH=coils[k]["L_uH"], R_ohm=coils[k]["R_ohm"], B300_per_A_uT=coils[k]["B_per_A_uT"]["300 mm"], B300_per_sqrtJ_uT=coils[k]["B300_per_sqrtJ_uT"],
                                                         first_sample_us=(ref.get("first_sample_us") if k == "AXE2_COIL" else coils[k]["first_sample_us_SiC460"]),
                                                         depth_coin_cm=coils[k]["depth_cm_at_own_current"]["silver_coin_25mm"], depth_gold_cm=coils[k]["depth_cm_at_own_current"]["gold_1g"], depth_small_gold_cm=coils[k]["depth_cm_at_own_current"]["gold_0p1g_small"],
                                                         depth_coin_equalE_cm=coils[k]["depth_cm_equal_energy"]["silver_coin_25mm"], depth_gold_equalE_cm=coils[k]["depth_cm_equal_energy"]["gold_1g"],
                                                         I_A=coils[k]["I_A"]) for k in coils})
    res["mass"] = dict(housing_g=round((math.pi * R_HOUSING ** 2 * 2 * 2e-3 + 2 * math.pi * R_HOUSING * H_STACK * 2e-3) * 1.15e6), litz_g=coils["HYP_CONE_7deg"]["mass_wire_g"],
                       cone_former_g=round(math.pi * (R1 ** 2 - R0 ** 2) * 0.006 * 0.35 * 1.15e6), ferrite_g=res["ferrite"]["mass_g"], nano_sheets_g=res["shields"]["mass_g_two_sheets"],
                       flex_g=round(math.pi * 0.14 ** 2 * 0.2e-3 * 1.6e6), electronics_g=25, note="ABS-CF 1.15 g/cm3, 2 mm walls, cone former 35 % infill, electronics 25 g (ASSUMED)")
    res["mass"]["total_g"] = round(sum(v for k, v in res["mass"].items() if k.endswith("_g")))
    res["survives"] = [
        "sector / multi-coil TX fired in sequence: a real way to tilt the excitation and see edge-on targets (costs TX time and field per phase)",
        "differential planar RX pairs (gradiometer) for TX and level-ground cancellation: real, and the same principle as AXE2's quadrupole RX boards",
        "OPA211 preamp and a slotted / finger Faraday shield: sound, standard",
        "low-leakage BAV199 clamps: fine for leakage, too slow for a sub-microsecond gate"]
    res["ok"] = bool(res["selftest"]["ok"])
    json.dump(res, open(os.path.join(OUT, "hyperion_concept.json"), "w"), indent=1, default=float)
    np.savez(os.path.join(OUT, "hyperion_profiles.npz"), depths=DEPTHS, **{k: M[k]["_bz"] for k in M}, **{"exp_" + k: M[k]["_expo"] for k in M})
    build_meshes(sims, ph, sect, res)
    plots(res)
    return res

# ---------------------------------------------------------------- meshes
def build_meshes(sims, ph, sect, res):
    import cadquery as cq, pyvista as pv
    mm = 1000.0; P = {}; R = R_HOUSING * mm; H = H_STACK * mm; w = WALL * mm
    P["HOUSING_ABS_CF"] = cq.Workplane("XY").circle(R).circle(R - w).extrude(H).union(cq.Workplane("XY").circle(R).extrude(w))
    P["LID"] = cq.Workplane("XY").circle(R - w).extrude(1.5).translate((0, 0, H - 1.5))
    zc = lambda r: (Z_LOW + (r / mm - R0) * math.tan(ALPHA_SIM)) * mm
    prof = [(R0 * mm - 4, w), (R1 * mm + 2.5, w), (R1 * mm + 2.5, zc(R1 * mm) - LITZ_OD * mm / 2), (R0 * mm - 4, zc(R0 * mm - 4) - LITZ_OD * mm / 2)]
    P["CONE_FORMER"] = cq.Workplane("XZ").polyline(prof).close().revolve(360, (0, 0, 0), (0, 1, 0))
    P["NANO_SHEET_LOWER"] = cq.Workplane("XY").circle(R - w - 0.5).extrude(0.05).translate((0, 0, w))
    P["RX_FLEX_PI"] = cq.Workplane("XY").circle(140.0).circle(45.0).extrude(0.05).translate((0, 0, w + 0.05))
    nodes = []
    for cx, cy in NODE_C:
        for r in node_turn_radii()[::4]:
            nodes.append(cq.Solid.makeCylinder(r * mm, 0.07, cq.Vector(cx * mm, cy * mm, w + 0.10)).cut(cq.Solid.makeCylinder(r * mm - 0.25, 0.07, cq.Vector(cx * mm, cy * mm, w + 0.10))))
    P["RX_METATRON_NODES"] = cq.Workplane("XY").add(cq.Compound.makeCompound(nodes))
    fing = []
    for k in range(96):
        a = 2 * math.pi * k / 96; b = cq.Solid.makeBox(100.0, 1.0, 0.035, cq.Vector(45.0, -0.5, w + 0.18)).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), math.degrees(a)); fing.append(b)
    P["FARADAY_FINGERS"] = cq.Workplane("XY").add(cq.Compound.makeCompound(fing))
    # TX litz: STEP as short cylinders along the 3D log spiral; STL as a swept tube
    p = sims["HYP_CONE_7deg"]["paths"][0] * mm; segs = []
    for a, b in zip(p[:-1:3], p[3::3]):
        d = b - a; segs.append(cq.Solid.makeCylinder(LITZ_OD * mm / 2, float(np.linalg.norm(d)), cq.Vector(*a), cq.Vector(*d)))
    P["TX_LITZ_CONE_SPIRAL"] = cq.Workplane("XY").add(cq.Compound.makeCompound(segs))
    blocks = []
    for k in range(24):
        a = 2 * math.pi * k / 24; rr = 100.0; z = zc(rr) + LITZ_OD * mm / 2 + 1.0
        bl = cq.Solid.makeBox(96.0, 2 * math.pi * rr / 24 - 2.0, 3.0, cq.Vector(R0 * mm, -(2 * math.pi * rr / 24 - 2.0) / 2, 0))
        bl = bl.rotate(cq.Vector(R0 * mm, 0, 0), cq.Vector(R0 * mm, 1, 0), -math.degrees(ALPHA_SIM)).translate(cq.Vector(0, 0, zc(R0 * mm) + LITZ_OD * mm / 2 + 1.0))
        blocks.append(bl.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), math.degrees(a)))
    P["FERRITE_78_x24"] = cq.Workplane("XY").add(cq.Compound.makeCompound(blocks))
    P["NANO_SHEET_UPPER"] = cq.Workplane("XY").circle(R - w - 0.5).extrude(0.05).translate((0, 0, H - 1.55))
    pcb = [cq.Solid.makeBox(60.0, 40.0, 1.6, cq.Vector(-30, -20, w + 1.0))]
    for i in range(3): pcb.append(cq.Solid.makeBox(6.6, 6.1, 2.3, cq.Vector(-26 + 9 * i, 8, w + 2.6)))          # IXTY02N100D TO-252
    for i in range(6): pcb.append(cq.Solid.makeBox(2.9, 1.3, 1.0, cq.Vector(-26 + 4.5 * i, -4, w + 2.6)))       # BAV199 SOT-23
    for i in range(2): pcb.append(cq.Solid.makeBox(4.9, 3.9, 1.75, cq.Vector(6 + 8 * i, -14, w + 2.6)))         # OPA211 SOIC-8
    P["ELECTRONICS_IXTY_BAV199_OPA211"] = cq.Workplane("XY").add(cq.Compound.makeCompound(pcb))
    meta = {}
    for k, wp in P.items():
        cq.exporters.export(wp, os.path.join(OUT, f"hyp_{k}.stl"), tolerance=0.2, angularTolerance=0.3); meta[k] = round(wp.val().Volume() / 1000.0, 3)
    pv.Spline(p, 3000).tube(radius=LITZ_OD * mm / 2, n_sides=10).triangulate().save(os.path.join(OUT, "hyp_TX_LITZ_CONE_SPIRAL.stl"))
    cq.exporters.export(cq.Compound.makeCompound([wp.val() for wp in P.values()]), os.path.join(OUT, "hyperion_concept.step"))
    # measured fit: ferrite and lid / housing interference, wire vs former
    inter = {}
    fer = P["FERRITE_78_x24"].val()
    for k in ("LID", "HOUSING_ABS_CF", "NANO_SHEET_UPPER"):
        try: inter[f"ferrite_x_{k}_mm3"] = round(fer.intersect(P[k].val()).Volume(), 1)
        except Exception as ex: inter[f"ferrite_x_{k}_mm3"] = str(ex)[:60]
    bb = fer.BoundingBox(); inter["ferrite_top_mm"] = round(bb.zmax, 2); inter["stack_mm"] = H
    res["meshes"] = dict(parts_cm3=meta, interference=inter, files=sorted(f for f in os.listdir(OUT) if f.startswith("hyp_")) + ["hyperion_concept.step"])
    json.dump(res, open(os.path.join(OUT, "hyperion_concept.json"), "w"), indent=1, default=float)
    try:
        pv.OFF_SCREEN = True; pl = pv.Plotter(off_screen=True, window_size=(1600, 1000))
        cols = dict(HOUSING_ABS_CF="#777777", CONE_FORMER="#bb9966", TX_LITZ_CONE_SPIRAL="#d07a20", FERRITE_78_x24="#303030", RX_FLEX_PI="#c8a040",
                    RX_METATRON_NODES="#1baf7a", FARADAY_FINGERS="#b87333", ELECTRONICS_IXTY_BAV199_OPA211="#2a6a2a", NANO_SHEET_LOWER="#6250d6")
        for k, c in cols.items():
            m = pv.read(os.path.join(OUT, f"hyp_{k}.stl"))
            if k == "FERRITE_78_x24": m = m.clip(normal="y", origin=(0, 0, 0))
            pl.add_mesh(m, color=c, opacity=0.25 if k in ("HOUSING_ABS_CF", "CONE_FORMER", "RX_FLEX_PI") else 1.0)
        pl.add_text("Hyperion conical log-spiral head, rebuilt (300 x 18 mm; half the ferrite hidden)", font_size=12); pl.view_isometric(); pl.camera.zoom(1.3)
        pl.screenshot(os.path.join(OUT, "hyperion_view.png")); pl.close()
    except Exception as ex: res["meshes"]["render_error"] = str(ex)[:200]

def plots(res):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    d = np.load(os.path.join(OUT, "hyperion_profiles.npz")); z = d["depths"] * 100
    ser = [("HYP_CONE_7deg", "Hyperion cone 7°", "#2a78d6"), ("LINEAR_FLAT_REF", "Concept's flat reference", "#eb6834"), ("RIM_BUNDLE_300", "Rim bundle, same wire", "#1baf7a"), ("AXE2_COIL", "AXE2 coil (233 mm)", "#6250d6")]
    fig, ax = plt.subplots(1, 3, figsize=(17, 5.2), facecolor="#fcfcfb")
    for a in ax: a.set_facecolor("#fcfcfb"); a.grid(color="#e4e3df", lw=0.8); [s.set_color("#c3c2b7") for s in a.spines.values()]; a.tick_params(colors="#52514e")
    for k, lab, c in ser: ax[0].loglog(z, d[k] * 1e6, color=c, lw=2, label=lab)
    ax[0].set_xlabel("Depth below skid (cm)", color="#52514e"); ax[0].set_ylabel("Bz on axis per amp (µT/A)", color="#52514e"); ax[0].set_title("Field per amp vs depth", color="#0b0b0b", loc="left"); ax[0].legend(frameon=False)
    for k, lab, c in ser: ax[1].semilogx(z, d["exp_" + k], color=c, lw=2, label=lab)
    ax[1].axhline(3, color="#52514e", lw=1, ls="--"); ax[1].axhline(2, color="#52514e", lw=1, ls=":"); ax[1].text(2.2, 3.05, "dipole 1/r³", color="#52514e"); ax[1].text(2.2, 2.05, "claimed 1/r²", color="#52514e")
    ax[1].set_xlabel("Depth below skid (cm)", color="#52514e"); ax[1].set_ylabel("Local fall-off exponent  −d ln B / d ln z", color="#52514e"); ax[1].set_title("Fall-off exponent", color="#0b0b0b", loc="left")
    rows = res["axe2_compare"]["rows"]; keys = ["HYP_CONE_7deg", "LINEAR_FLAT_REF", "RIM_BUNDLE_300", "HYP_CONE_in_233", "AXE2_COIL"]
    labs = ["Hyperion\ncone", "Flat\nref", "Rim\n300", "Cone in\n233", "AXE2"]; y = np.arange(len(keys))
    ax[2].barh(y - 0.27, [rows[k]["depth_coin_cm"] for k in keys], 0.25, color="#2a78d6", label="25 mm silver coin")
    ax[2].barh(y, [rows[k]["depth_gold_cm"] for k in keys], 0.25, color="#eda100", label="1 g gold")
    ax[2].barh(y + 0.27, [rows[k]["depth_small_gold_cm"] for k in keys], 0.25, color="#1baf7a", label="0.1 g-class gold (fast)")
    ax[2].set_yticks(y, labs); ax[2].invert_yaxis(); ax[2].set_xlabel("Modelled depth (cm), each coil at its own current and first sample", color="#52514e")
    ax[2].set_title("Modelled depth (ratios matter, absolutes optimistic)", color="#0b0b0b", loc="left"); ax[2].legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "hyperion_fields.png"), dpi=110); plt.close(fig)

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
