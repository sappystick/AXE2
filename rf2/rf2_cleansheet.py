#!/usr/bin/env python3
"""RF2 clean-sheet model of the whole detector (owner 2026-10-31). MODELED; a design study, nothing adopted, nothing excluded.

Designs the machine from scratch inside loose envelope bounds, with the repo's own physics, part data and calibration points. One design
evaluation takes a few milliseconds; the full optimisation (Optuna NSGA-II in 4 processes, then a scipy polish) runs in about 1-2 minutes.

Design variables (loose bounds)
  head      diameter D 180-300 mm, height H 15-35 mm
  coil      outer-column inset from the rim 0-60 mm (sets the mean radius), turns N 3-40, parallel strands p 1-6, litz construction (all 100
            Rubadue catalog rows with freq_ok in rf2/results/rf2_wire_options.json: copper area, strands, OD and insulation rating), bundle
            columns 1-10 (rows = ceil(N p / columns), filled row by row as rf2_lowL_options.SLOTS)
  TX        scan pulse current 2-40 A (boost = x sqrt(2.5), as rf2_continuous), flat-top 50-600 us, clamp 100-800 V, switch (every TX-class
            MOSFET / SiC / GaN with a datasheet on file and a DATASHEET_LOG row; see SWITCHES)
  pack      cell (Molicel P30B / P45B, LG M50T: rf2_pack_options.CELLS, datasheets on file), series S 4-12, parallel P 1-3
  shaft     pivot-to-hinge length 0.90-1.40 m, profile square / hex / round, outer across-flats 18-36 mm, wall 0.8-2.0 mm (3-stage telescope,
            each stage 2 x wall + 2.6 mm smaller, today's step), carbon E 50 GPa / 1.55 g/cm3 ASSUMED (rf2_shaft_options)
  receive   mono (rim coil) or hybrid (rim coil + planar nulled RX, a second channel: rf2_lowL_options.hybrid, fast scaled equivalent)
  cord      TX strip width 0.8-6 mm and copper 1 / 2 / 3 oz (IPC-2221 as rf2_cordflex.ipc2221_width_mm)

Physics (each line names the repo model it reuses)
  L         Maxwell coaxial-circle sums over the slots (exact; rf2_lowL_options.coil), self term mu0 r (ln(8r/a) - 7/4) with the litz
            copper-equivalent radius (variant_plugins/coil_winding.a_eq_m). Today's 26 x 1 gives 327.5 uH = rf2_lowL_options.coil(26, 1) and
            FastHenry 327.6 uH (rf2_solver_xcheck).
  R         catalog ohm/m (rf2_wire_options R_coil_20C / 18.27 m) x (slot path + leads x p) / p^2 (rf2_lowL_options.coil).
  C_self    energy method on the turn-to-turn voltage map (variant_plugins/coil_winding.winding_model, row fill), applied as a delta to the
            node C: C_node = 368 pF + cord TX strip pair (rf2_cordflex.cps_c_pf_per_m x length) + switch Coss above the C3M's + dC_self.
  gate      clib.pi_first_sample(L, C_node, I, V_clamp) + one offset fitted so today's machine gives 16.43 us (MP1 v2).
  echo      clib.eddy_echo (mono) / rf2_lowL_options.echo_sep (planar) on the TARGETS of rf2_lowL_options, times a flat-top charging factor
            (1 - e^(-T_flat/tau)) / (1 - e^(-300 us/tau)) (1.0 today; the repo model assumes today's 300 us); noise MP1 v2 2.211 nV/rtHz + coil
            Johnson, 1 MHz, 1000-pulse average, SNR 5 (rf2_lowL_options): absolute depths optimistic, the CHANGE is the result.
  power     rf2_lowL_options.pulse (resistance-limited ramp, flat-top, regenerative clamp 75 % ASSUMED), with the ramp integrals in closed form,
            bus = S x 3.6 V nominal; Rd re-tuned for critical damping (408 ohm x sqrt((L/C)/(L/C)_today)); head electronics 10.62 W
            (rf2_lowL_options.P_HEAD) + 0.35 W for the hybrid's second channel (ASSUMED there); pack usable = S P Wh_cell x 0.90 (rf2_pack_options).
  masses    head items of rf2/head/out_BF/rf2_head_check.json (771 g) scaled: printed parts 75 % with D^2 + 25 % with D H (ASSUMED split), receive
            boards / shield / display flex with D^2, litz from catalog g/m x length, channel epoxy with bundle section x circumference, the rest
            fixed; shaft tubes from the section x 380 mm x L/0.98; pack = rf2_pack_options.pack_mass + rails; chassis items and lever arms from
            rf2/chassis_out/rf2_chassis_check.json (head and shaft levers move with the shaft length); torque about the hand as rf2_pack_options.
  sag       3-stage cantilever with the head + 40 g yoke at the tip and the tubes' own weight (rf2_shaft_options.deflection; today 3.41 mm).
  switch    peak vs 80 % IDM, TJ = 40 C + P_sw x 10 K/W (rf2_lowL_options), clamp vs 0.8 VDS, rule 6 (630 V parts on flyback nets).
Rules: every rule is evaluated for every design and kept (nothing excluded); safety rules are reported, never relaxed. Status PASS / EDGE
(<= 5 % headroom) / BLOCKED (fails by <= 10 %) / FAIL as rf2_rules.

Writes rf2/results/rf2_cleansheet.json, docs/CLEANSHEET.md, rf2/results/cleansheet_top.step, cleansheet_*.stl, cleansheet_view.png.
usage: python3 rf2/rf2_cleansheet.py [--budget SECONDS] [--workers N] [--no-cad]"""
import os, sys, json, math, time, argparse
import numpy as np
from scipy.special import ellipk, ellipe
from scipy.optimize import brentq, minimize
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results")
for _p in (os.path.join(ROOT, "concepts"), os.path.join(HERE, "head"), HERE):
    if _p not in sys.path: sys.path.insert(0, _p)
import clib as K
import rf2_cordflex as CFX
import rf2_lowL_options as LO
import rf2_txd_spice as TS
import rf2_pack_options as PK

MU0, EPS0 = K.MU0, K.EPS0
# ------------------------------------------------------------------ data from the repo (read, never invented)
WIRE = json.load(open(os.path.join(OUT, "rf2_wire_options.json")))
STUDY_LEN_M = WIRE["coil"]["length_m"]                                    # 18.27 m: the length the catalog R and g are for
LITZ = [c for c in WIRE["candidates"] if c["freq_ok"]]                   # 100 rows, every insulation class kept
LITZ_IDX = {c["part"]: i for i, c in enumerate(LITZ)}
TODAY_LITZ = "TXXL66/38FXXX-2(MWXX)"
HEADCHK = json.load(open(os.path.join(HERE, "head", "out_BF", "rf2_head_check.json")))["checks"]["mass_g"]
CHASSIS = json.load(open(os.path.join(HERE, "chassis_out", "rf2_chassis_check.json")))["mass"]
VARIANTS_F = os.path.join(OUT, "rf2_variants.json")

# switches: every TX-class transistor with a DATASHEET_LOG row (python3 rf2/rf2_kb.py part <name>). rds = hot on-resistance used in the
# loss model, idm = pulsed rating (continuous ID where no IDM is given: conservative), vds = rated breakdown, coss_extra = node C above the
# C3M0280090J's at the 26 V tail, e_off = turn-off energy at 7.5 A / 400 V (scaled with I and V as rf2_continuous)
SWITCHES = {
    "C3M0280090J": dict(rds=0.416 * 1.1, idm=22.0, vds=900.0, coss_extra_pF=0.0, e_off=2.4e-6,
                        src="Wolfspeed Rev04 (DATASHEET_LOG RF2-DS-STAGE3): 900 V, IDM 22 A, RDS(on) 416 mohm at 150 C (+10 % as rf2_lowL_options), Coss about 110 pF at 25 V (READ)"),
    "NTBG080N120SC1": dict(rds=0.110 * 1.6, idm=110.0, vds=1200.0, coss_extra_pF=59.0, e_off=2.4e-6 * 1.5,
                           src="onsemi (DATASHEET_LOG RF2-DS-STAGE3): 1200 V, IDM 110 A, RDS(on) 110 mohm max at 25 C (hot x1.6 ASSUMED), Coss 79 pF (rf2_lowL_options)"),
    "GS-065-011-1-L": dict(rds=0.380, idm=19.0, vds=650.0, coss_extra_pF=15.0, e_off=2.4e-6,
                           src="GaN Systems Rev220708 (DATASHEET_LOG RF2-DS-OWNER2): 650 V, 19 A pulse, Coss about 125 pF at 26 V (READ); hot RDS 380 mohm = kb EXTRACTED p3 (UNVERIFIED); Eoff ASSUMED as the C3M"),
    "IPB65R095C7": dict(rds=0.202 * 1.1, idm=100.0, vds=650.0, coss_extra_pF=290.0, e_off=2.4e-6,
                        src="Infineon Rev2.0 (DATASHEET_LOG U-DS-TXDRIVE / RF2-DS-STAGE3): 650 V, ID,pulse 100 A, RDS(on) 202 mohm typ at 150 C (+10 %), Coss about 400 pF at 26 V (READ); Eoff ASSUMED as the C3M"),
    "ARF461": dict(rds=2.0 * 1.8, idm=6.5, vds=1000.0, coss_extra_pF=65.0, e_off=2.4e-6,
                   src="Microsemi ARF461A/B RevD (DATASHEET_LOG RF2-DS-OWNER3): 1000 V, ID 6.5 A (no IDM given: ID used), about 2.0 ohm (hot x1.8 ASSUMED as the log), Coss 175 pF at 50 V; extra C and Eoff ASSUMED"),
    "ARF1510": dict(rds=2.2 * 1.8, idm=8.0, vds=1000.0, coss_extra_pF=20.0, e_off=2.4e-6,
                    src="Microsemi ARF1510 RevF (DATASHEET_LOG RF2-DS-OWNER3): one of its four 1000 V devices, ID 8 A (no IDM: ID used), about 2.2 ohm (hot x1.8 ASSUMED), Coss 100-130 pF at 200 V; BeO ceramic (hazard); extra C and Eoff ASSUMED"),
}
SCREENED_SWITCHES = "depletion-mode limiters on file (IXTY08N100D2, IXTY01N100D, IXTY02N50D, IXTY08N50D2, DN2470: ID(on) <= 0.8 A) and the 40 V BSC007N04LS6 are not TX-switch class: listed, not searched"
# cells (rf2_pack_options.CELLS: Wh typ, g max, d, h, coldest-band continuous A, source) + nominal V (DATASHEET_LOG: P30B / P45B 3.6 V, M50T 3.63 V)
CELLS = {k: dict(Wh=v[0], g=v[1], d=v[2], h=v[3], I_cont=v[4], src=v[5], v_nom={"LG M50T": 3.63}.get(k, 3.6)) for k, v in PK.CELLS.items()}
V_CUTOFF_CELL = 3.0                         # worst-case boost voltage per cell (rf2_pack_options / rf2_txd_spice 21 V at 7S)
Y5B_V = 50.0                                # Panasonic Y5B rated voltage on VIN_H (DATASHEET_LOG RF2 Y5B ratings)
BMS_S = (3, 16)                             # TI BQ76952 3S-16S (DATASHEET_LOG)

# ------------------------------------------------------------------ today's geometry and repo constants
OD0 = 1.372; CP0, RP0 = 1.77, 1.44                                        # today's comb: column pitch, row pitch (rf2_lowL_options)
TOOTH = CP0 - OD0; ROW_ALLOW = RP0 - OD0                                  # 0.398 mm column tooth, 0.068 mm row allowance (kept, ASSUMED)
FLOOR_Z = 4.49 - OD0 / 2                                                  # channel floor z 3.804 mm
RIM_WALL = 116.5 - 2.4 - OD0 / 2 - 113.4 + 2.4                            # 2.4 mm from the outer column edge to the head rim (today)
STACK_ABOVE = 25.4 - 12.6                                                 # lid + display + boards above the channel top (today, ASSUMED kept)
SHIELD_GAP = 114.45 - 113.4 - OD0 / 2; Z_GND = 3.2                        # coil_winding: shield coat and receive-stack plane
EPS_FEP = 2.1; DIAG_W = 0.5
A_EQ = lambda c: math.sqrt(c["strands"]) * (0.127 * 92 ** ((36 - c["strand_awg"]) / 39.0)) / 2 * 1e-3
F, NAVG, BW, SNR, NOISE_nV = LO.F, LO.NAVG, LO.BW, LO.SNR, LO.NOISE_nV
TARGETS = LO.TARGETS; TNAMES = list(TARGETS)
DEPTHS = LO.DEPTHS
P_HEAD, P_RX2 = LO.P_HEAD, LO.P_RX2_W
BOOST = LO.BOOST
C_FIX = 368e-12                                                           # front end + layout outside the winding (rf2_txd_spice / HANDOFF 19)
TX_C_LEN_M = (TS.C_NODE - C_FIX) / (CFX.cps_c_pf_per_m() * 1e-12)          # cord length that the node C uses (rf2_txd_spice: segments())
USABLE = PK.USABLE
RAIL = PK.RAIL_LATCH_G
E_CF, RHO_CF = 50e3, 1.55e-3                                              # N/mm2, g/mm3 (ASSUMED, rf2_shaft_options)
YOKE_G = 40.0
TODAY = dict(D=233.0, H=25.4, inset=0.0, N=26, p=1, litz=TODAY_LITZ, cols=5, I=8.06, T_flat=300.0, V_cl=460.0, switch="C3M0280090J",
             cell="Molicel P45B", S=7, P=1, L_shaft=0.98, profile="square", af=31.0, wall=1.2, rx="mono", w_tx=CFX.W_TX, oz=2)
BOUNDS = dict(D=(180.0, 300.0), H=(15.0, 35.0), inset=(0.0, 60.0), N=(3, 40), p=(1, 6), cols=(1, 10), I=(2.0, 40.0), T_flat=(50.0, 600.0),
              V_cl=(100.0, 800.0), S=(4, 12), P=(1, 3), L_shaft=(0.90, 1.40), af=(18.0, 36.0), wall=(0.8, 2.0), w_tx=(0.8, 6.0))
CATS = dict(litz=[c["part"] for c in LITZ], switch=list(SWITCHES), cell=list(CELLS), profile=["square", "hex", "round"], rx=["mono", "hybrid"], oz=[1, 2, 3])
INTS = ("N", "p", "cols", "S", "P")
CONT = ("D", "H", "inset", "I", "T_flat", "V_cl", "L_shaft", "af", "wall", "w_tx")
# chassis items (rf2_chassis_check): fixed masses and lever arms about the hand (mm); the drill-rail pack adds a dock + seal and removes the bay (rf2_pack_options)
LEV = {k.split(" (")[0]: v for k, v in CHASSIS["lever_mm"].items()}
ITEMS = {k.split(" (")[0]: v for k, v in CHASSIS["items_g"].items()}
FIXED_ITEMS = [(ITEMS["REF3 rect coils"], LEV["REF3 rect coils"]), (ITEMS["chassis shell + hinge + TXD + PWR + HB2"], LEV["chassis shell + hinge + TXD + PWR + HB2"]),
               (ITEMS["grip + head + screen"], LEV["grip + head + screen"]), (ITEMS["cuff + rails"], LEV["cuff + rails"])]
DOCK_DELTA_G = PK.DOCK_G + PK.GASKET_G - 92.6                             # dock + seal - bay (rf2_pack_options bay_g_from_stl 92.6 g): mass only, as there
LEV_HEAD0, LEV_SHAFT0, LEV_PACK = LEV["head"], LEV["rect profiles"], LEV["battery cartridge"]
CLAMP_G = ITEMS["rect profiles"] - 210.0                                  # yoke + clamps 70 g (ASSUMED there)
HM = {k.split(" (")[0]: v for k, v in HEADCHK["items"].items()}
HEAD_PRINT, HEAD_RX, HEAD_SH, HEAD_LITZ, HEAD_EL, HEAD_EPOXY, HEAD_HW = (HM["printed parts"], HM["receive boards QA + QB"], HM["shield SH1"],
    HM["transmit litz"], HM["electronics islands"], HM["coil channel epoxy"], HM["hardware, cable gland, yoke lug"])
HEAD_POT = HEADCHK["islands_only_potting"]; DISPLAY_FLEX_G = 40.0         # display flex 40 g ASSUMED in rf2_head_check (scales with D^2 here)
REF = dict(L_uH=327.5, L_fasthenry_uH=327.6, R_ohm=0.601, gate_us=16.43, depth=dict(coin_25mm_silver=60.2, gold_1g=30.2, gold_0p1g=15.0), boost_h=2.6, scan_h=5.19,
           head_g=771.0, sag_mm=3.41, tubes_g=210.0, torque_Nm_650g_head=4.19, total_g_650g_head=2415.0, C_self_pF=198.6, Tj_C=89.3, I_boost=12.74, flex_mm=15.7,
           hybrid_depth=dict(coin_25mm_silver=60.6, gold_1g=30.6, gold_0p1g=16.3), hybrid_gate_us=13.58)
REF_SRC = dict(L_uH="rf2_lowL_options.coil(26,1)", L_fasthenry_uH="rf2_solver_xcheck.json", R_ohm="rf2_wire_options / rf2_continuous", gate_us="MP1 v2 first gate (rf2_lowL_options.FIRST_GATE0)",
               depth="rf2_lowL_options.json base", boost_h="rf2_lowL_options.json base", scan_h="rf2_lowL_options.json base", head_g="rf2_head_check total_islands_only",
               sag_mm="rf2_shaft_options / rf2_fold_options (wall 1.2)", tubes_g="rf2_shaft_options", torque_Nm_650g_head="rf2_pack_options C2", total_g_650g_head="rf2_pack_options C2",
               C_self_pF="variant_plugins/coil_winding (rf2_variants extra.C_self_today_pF)", Tj_C="rf2_lowL_options.json base", I_boost="rf2_lowL_options.json base",
               flex_mm="rf2_cordflex.WIDTH", hybrid_depth="rf2_lowL_options.json hybrid 26x1 C3M", hybrid_gate_us="rf2_lowL_options.json hybrid 26x1 C3M")

# ------------------------------------------------------------------ physics kernels
def maxwell(r1, r2, dz):
    k2 = 4 * r1 * r2 / ((r1 + r2) ** 2 + dz ** 2); k2 = np.minimum(k2, 1 - 1e-12); k = np.sqrt(k2)
    return MU0 * np.sqrt(r1 * r2) * ((2 / k - k) * ellipk(k2) - 2 / k * ellipe(k2))

def bundle(d):
    c = LITZ[LITZ_IDX[d["litz"]]]; od = c["od_mm"]; cp, rp = od + TOOTH, od + ROW_ALLOW
    n = d["N"] * d["p"]; cols = d["cols"]; rows = -(-n // cols)
    r_out = d["D"] / 2 - RIM_WALL - od / 2 - d["inset"]; z0 = FLOOR_Z + od / 2
    j = np.arange(n); col, row = j % cols, j // cols
    r = (r_out - cp * col) * 1e-3; z = (z0 + rp * row) * 1e-3
    return dict(c=c, od=od, cp=cp, rp=rp, n=n, rows=rows, cols=cols, r_out=r_out, z0=z0, r=r, z=z, col=col, row=row,
                top=z0 + rp * (rows - 1) + od / 2, r_in=r_out - cp * (min(cols, n) - 1) - od / 2, width=cp * (min(cols, n) - 1) + od)

def inductance(B, p):
    r, z = B["r"], B["z"]; a = A_EQ(B["c"])
    L = float(np.sum(MU0 * r * (np.log(8 * r / a) - 1.75)))
    if len(r) > 1:
        i, j = np.triu_indices(len(r), 1); L += 2 * float(np.sum(maxwell(r[i], r[j], np.abs(z[i] - z[j]))))
    return L / p ** 2

def c_self(B, N, p):
    """coil_winding.winding_model energy method, row fill: neighbours in the same row / column x 1, diagonals x 0.5; outer column to the
    shield coat, bottom row to the z 3.2 plane; the cold end chosen for the lower C"""
    n, cols = B["n"], B["cols"]; col, row = B["col"], B["row"]; a = B["c"]["core_mm"] / 2 * 1e-3
    turn = np.arange(n) // p; rmm = B["r"] * 1e3
    pairs = []
    for dj, w, pitch in ((1, 1.0, B["cp"]), (cols, 1.0, B["rp"]), (cols + 1, DIAG_W, math.hypot(B["cp"], B["rp"])), (cols - 1, DIAG_W, math.hypot(B["cp"], B["rp"]))):
        if dj <= 0 or (dj == cols - 1 and cols < 2): continue
        i = np.arange(n - dj) if n > dj else np.array([], int); jj = i + dj
        if dj == 1: m = col[i] + 1 == col[jj]
        elif dj == cols: m = np.ones(len(i), bool)
        elif dj == cols + 1: m = (col[jj] == col[i] + 1) & (row[jj] == row[i] + 1)
        else: m = (col[jj] == col[i] - 1) & (row[jj] == row[i] + 1)
        i, jj = i[m], jj[m]
        if len(i) == 0: continue
        if 2 * a >= pitch * 1e-3: pitch = 2 * a * 1e3 * 1.001
        cij = w * math.pi * EPS0 * EPS_FEP / math.acosh(pitch * 1e-3 / (2 * a)) * 2 * math.pi * (rmm[i] + rmm[jj]) / 2 * 1e-3
        pairs.append((cij, np.abs(turn[i] - turn[jj])))
    Cw = sum(float(np.sum(cij * (dt / N) ** 2)) for cij, dt in pairs)
    vmax = max([int(dt.max()) for _, dt in pairs if len(dt)] + [0])
    h_sh = (B["od"] / 2 + SHIELD_GAP) * 1e-3; h_gn = (B["z0"] - Z_GND) * 1e-3
    cg_sh = 2 * math.pi * EPS0 * EPS_FEP / math.acosh(max(h_sh / a, 1.0001)) * 2 * math.pi * B["r"] * (col == 0)
    cg_gn = 2 * math.pi * EPS0 * EPS_FEP / math.acosh(max(h_gn / a, 1.0001)) * 2 * math.pi * B["r"] * (row == 0)
    best = None
    for rev in (False, True):
        frac = ((N - turn - 0.5) if rev else (turn + 0.5)) / N
        C = Cw + float(np.sum((cg_sh + cg_gn) * frac ** 2)); best = C if best is None else min(best, C)
    return best, vmax

def b_axis(r, z, p, depths=DEPTHS):
    return np.sum(MU0 * r[None, :] ** 2 / (2 * (r[None, :] ** 2 + (depths[:, None] + z[None, :]) ** 2) ** 1.5), axis=1) / p

def pulse(L, R, I, vbus, vcl, t_flat, rds, e_off, Rd):
    """rf2_lowL_options.pulse with the ramp integrals in closed form"""
    tau = L / R; imax = vbus / R
    if I >= imax * 0.999: return None
    T1 = -tau * math.log(1 - I / imax); tf = L * I / vcl; e1 = math.exp(-T1 / tau)
    ramp_i2 = imax ** 2 * (T1 - 2 * tau * (1 - e1) + tau / 2 * (1 - e1 ** 2))
    i2 = F * (ramp_i2 + 0.5 * I ** 2 * t_flat + I ** 2 / 3 * tf); sw_i2 = F * (ramp_i2 + 0.5 * I ** 2 * t_flat * 0.30)
    E = 0.5 * L * I ** 2; P_sw = sw_i2 * rds + F * e_off * (I / 7.5) * (vcl / 400.0)
    P_rd = F * (vcl ** 2 / Rd * tf + vbus ** 2 / Rd * (T1 + 0.5 * t_flat))
    P_ohm = F * (ramp_i2 * R + 0.5 * I ** 2 * t_flat * R + 0.5 * t_flat * 0.70 * 1.2 * I)
    return dict(T1_us=T1 * 1e6, fall_us=tf * 1e6, I_rms_coil=math.sqrt(i2), P_sw=P_sw, P_rd=P_rd, P_tx=F * E * 0.25 + P_ohm + P_sw * 0.3 + P_rd * 0.1, E_mJ=E * 1e3)

_S_CACHE = {}
def settle(ratio):
    key = round(math.log(ratio), 3)
    if key not in _S_CACHE: _S_CACHE[key] = brentq(lambda x: (1 + x) * math.exp(-x) - ratio, 1e-6, 200.0)
    return _S_CACHE[key]

TAU_T = {k: (lambda tg: (MU0 * tg["r"] * (math.log(8 * tg["r"] / (0.2235 * (tg["w"] + tg["t"]))) - 2)) / (2 * math.pi * tg["r"] / (tg["sigma"] * tg["w"] * tg["t"])))(tg) for k, tg in TARGETS.items()}
LO_T = {k: MU0 * tg["r"] * (math.log(8 * tg["r"] / (0.2235 * (tg["w"] + tg["t"]))) - 2) for k, tg in TARGETS.items()}

def echo(bt, br, I, t, k, t_flat):
    tg = TARGETS[k]; tau = TAU_T[k]
    chg = (1 - math.exp(-t_flat * 1e-6 / tau)) / (1 - math.exp(-300e-6 / tau))
    return (bt * tg["area"]) * (br * tg["area"]) * I / LO_T[k] / tau * math.exp(-t / tau) * chg

def depth_from(v, vth):
    if v[0] < vth: return 0.0
    if v[-1] >= vth: return float(DEPTHS[-1])
    return float(np.exp(np.interp(math.log(vth), np.log(v[::-1]), np.log(DEPTHS[::-1]))))

# planar nulled RX (rf2_lowL_options.rx_design 40 turns / 0.30 mm / 0.15 mm, scaled with the TX outer radius; null solved per design)
RX_REF = dict(main_r0=88.0, main_n=40, buck_n=16, pitch=0.3, L_uH=525.6, R_ohm=51.63, C_pF=20.5, null_ratio=0.00449, r_tx=113.4)
def planar(B, d, L, Cn, I, fs):
    s = B["r_out"] / RX_REF["r_tx"]; pitch = RX_REF["pitch"] * 1e-3
    r_mo = RX_REF["main_r0"] * s * 1e-3; main = r_mo - pitch * np.arange(RX_REF["main_n"])
    if main[-1] <= 0.005: return None
    zr, zb = LO.RX_Z, LO.RX_Z + 0.1e-3
    m_main = float(np.sum(maxwell(main[:, None], B["r"][None, :], np.abs(B["z"][None, :] - zr)))) / d["p"]
    hi = B["r_out"] * 1e-3 - 0.9e-3; lo = r_mo + 1e-3 + (RX_REF["buck_n"] - 1) * pitch
    if hi <= lo: return None
    grid = np.arange(lo - (RX_REF["buck_n"] - 1) * pitch, hi + 1e-9, 0.1e-3)
    mt = np.sum(maxwell(grid[:, None], B["r"][None, :], np.abs(B["z"][None, :] - zb)), axis=1) / d["p"]
    rb = np.arange(lo, hi + 1e-9, 0.1e-3)
    fb = sum(np.interp(rb - k * pitch, grid, mt) for k in range(RX_REF["buck_n"])) - m_main
    sg = np.where(np.sign(fb[:-1]) != np.sign(fb[1:]))[0]
    if len(sg) == 0: return None
    q = sg[0]; r_b = rb[q] - fb[q] * (rb[q + 1] - rb[q]) / (fb[q + 1] - fb[q]); buck = r_b - pitch * np.arange(RX_REF["buck_n"])
    rr = np.concatenate([main, buck]); zz = np.concatenate([np.full(len(main), zr), np.full(len(buck), zb)]); sgn = np.concatenate([np.ones(len(main)), -np.ones(len(buck))])
    br = np.abs(np.sum(sgn[None, :] * MU0 * rr[None, :] ** 2 / (2 * (rr[None, :] ** 2 + (DEPTHS[:, None] + zz[None, :]) ** 2) ** 1.5), axis=1))
    Lrx = RX_REF["L_uH"] * 1e-6 * (r_mo / (RX_REF["main_r0"] * 1e-3)); Rrx = RX_REF["R_ohm"] * (r_mo / (RX_REF["main_r0"] * 1e-3))
    tau_rx = math.sqrt(Lrx * RX_REF["C_pF"] * 1e-12)
    v_res = RX_REF["null_ratio"] * m_main * d["V_cl"] / L
    sx = settle(1e-6 / max(v_res, 1.01e-6))
    gate = max(fs["fall_us"] + fs["tau_us"] * sx + tau_rx * 1e6 * sx, fs["fall_us"] + 0.5)
    return dict(br=br, gate_us=gate, noise_nV=math.hypot(NOISE_nV, K.johnson_noise_nV(Rrx)), main_r_mm=(round(main[0] * 1e3, 2), round(main[-1] * 1e3, 2)),
                buck_r_mm=(round(r_b * 1e3, 2), round(buck[-1] * 1e3, 2)), M_main_uH=m_main * 1e6, v_res=v_res)

def section(profile, af, t):
    b = af - 2 * t
    if b <= 0: return 1e-9, 1e-9, 0.0
    if profile == "square": return (af ** 4 - b ** 4) / 12.0, af ** 2 - b ** 2, b
    if profile == "hex":
        so, si = af / math.sqrt(3), b / math.sqrt(3); return 5 * math.sqrt(3) / 16 * (so ** 4 - si ** 4), 1.5 * math.sqrt(3) * (so ** 2 - si ** 2), b
    return math.pi * (af ** 4 - b ** 4) / 64.0, math.pi / 4 * (af ** 2 - b ** 2), b

XS = np.linspace(0.0, 1.0, 401)
def shaft(d, P_tip_N):
    """rf2_shaft_options.deflection: three nested stages (outer at the hinge), 100 mm overlaps (the smaller section), head at the tip"""
    L = d["L_shaft"] * 1000.0; ov = 100.0; step = 2 * d["wall"] + 2.6
    afs = [d["af"], d["af"] - step, d["af"] - 2 * step]; secs = [section(d["profile"], a, d["wall"]) for a in afs]
    seg = (L + 2 * ov) / 3.0; x = XS * L
    idx = np.minimum((x // (seg - ov)).astype(int), 2)
    EI = E_CF * np.array([s[0] for s in secs])[idx]; q = RHO_CF * np.array([s[1] for s in secs])[idx] * 9.81e-3
    dx = np.diff(x)
    def tail(f): c = np.concatenate([[0], np.cumsum((f[1:] + f[:-1]) / 2 * dx)]); return c[-1] - c
    shear = tail(q) + P_tip_N; M = tail(shear); kap = M / EI
    th = np.concatenate([[0], np.cumsum((kap[1:] + kap[:-1]) / 2 * dx)]); w = np.concatenate([[0], np.cumsum((th[1:] + th[:-1]) / 2 * dx)])
    tube_len = 380.0 * L / 980.0
    mass = sum(RHO_CF * s[1] * tube_len for s in secs)
    bore = secs[2][2]
    chord = bore * (2 / math.sqrt(3) if d["profile"] == "hex" else 1.0)          # a flat strip across a hex lies corner to corner (ASSUMED)
    return dict(sag_mm=float(w[-1]), tubes_g=float(mass), afs=afs, bore_mm=bore, chord_mm=chord, collapsed_mm=tube_len + 50.0)

def ipc_b4_mm(v):
    """IPC-2221B table 6-1 B4 (external, coated) as commonly tabulated (UNVERIFIED: the standard is not on file)"""
    return 0.8 + 0.00305 * (v - 500.0) if v > 500 else (0.4 if v > 300 else 0.25 if v > 150 else 0.13)

# ------------------------------------------------------------------ rules
BLOCK, EDGE = 0.10, 0.05
def rule(name, value, limit, sense, where, kind, binary=False):
    den = abs(limit) if limit else 1.0
    m = (limit - value) / den if sense == "<=" else (value - limit) / den
    ok = m >= -1e-9
    st = ("EDGE" if (m <= EDGE and not binary) else "PASS") if ok else ("BLOCKED" if (-m <= BLOCK and not binary) else "FAIL")
    return dict(rule=name, value=round(float(value), 4), limit=round(float(limit), 4), sense=sense, where=where, kind=kind, ok=bool(ok), margin=round(float(m), 4), status=st)

# ------------------------------------------------------------------ one design
_CAL = {}
def evaluate(d, detail=False):
    d = dict(d); sw = SWITCHES[d["switch"]]; cell = CELLS[d["cell"]]
    B = bundle(d); N, p = d["N"], d["p"]
    L = inductance(B, p)
    length = float(np.sum(2 * math.pi * B["r"])) + LO.LEAD_M * p
    R = B["c"]["R_coil_20C"] / STUDY_LEN_M * length / p ** 2
    Cs, dt_max = c_self(B, N, p)
    tx_len = CFX.TX_LEN_M * d["L_shaft"] / 0.98; c_len = TX_C_LEN_M * d["L_shaft"] / 0.98
    t_cu = 0.0014 * 25.4 * d["oz"]
    r_flex = 2 * 0.017241 * tx_len / (d["w_tx"] * t_cu)
    Cn = C_FIX + CFX.cps_c_pf_per_m(d["w_tx"], CFX.HV_GAP) * 1e-12 * c_len + sw["coss_extra_pF"] * 1e-12 + (Cs - _CAL.get("C_self", Cs))
    Rd = 408.0 * math.sqrt((L / Cn) / _CAL.get("LC", 333e-6 / Cn))
    vbus = d["S"] * cell["v_nom"]; vcut = d["S"] * V_CUTOFF_CELL
    R_loop = R + r_flex + sw["rds"] + 0.010
    I, Ib = d["I"], d["I"] * BOOST
    ps = pulse(L, R_loop, I, vbus, d["V_cl"], d["T_flat"] * 1e-6, sw["rds"], sw["e_off"], Rd)
    pb = pulse(L, R_loop, Ib, vbus, d["V_cl"], d["T_flat"] * 1e-6, sw["rds"], sw["e_off"], Rd)
    ratio = 1e-6 / d["V_cl"]; tau = math.sqrt(L * Cn); sx = settle(ratio)
    fs = dict(fall_us=L * I / d["V_cl"] * 1e6, tau_us=tau * 1e6, first_us=(L * I / d["V_cl"] + tau * sx) * 1e6)
    gate = fs["first_us"] + _CAL.get("gate_off", 0.0)
    bt = b_axis(B["r"], B["z"], p)
    vn = math.hypot(NOISE_nV, K.johnson_noise_nV(R + r_flex))
    sig = vn * 1e-9 * math.sqrt(BW) / math.sqrt(NAVG); vth = SNR * sig
    dep = {k: depth_from(echo(bt, bt, I, gate * 1e-6, k, d["T_flat"]), vth) * 100 for k in TNAMES}
    pl = None; dep_mono = dict(dep)
    if d["rx"] == "hybrid":
        pl = planar(B, d, L, Cn, I, fs)
        if pl:
            sr = pl["noise_nV"] * 1e-9 * math.sqrt(BW) / math.sqrt(NAVG)
            dep = {k: depth_from(np.hypot(echo(bt, bt, I, gate * 1e-6, k, d["T_flat"]) / sig, echo(bt, pl["br"], I, pl["gate_us"] * 1e-6, k, d["T_flat"]) / sr), SNR) * 100 for k in TNAMES}
    p_extra = P_RX2 if (d["rx"] == "hybrid" and pl) else 0.0
    wh = d["S"] * d["P"] * cell["Wh"] * USABLE
    # flex strip: IPC-2221 width at the boost rms, scaled from rf2_cordflex's 3.67 A by this design's coil rms against today's
    i_tx = CFX.I_TX * ((pb["I_rms_coil"] if pb else Ib / 2) / _CAL.get("Irms_b", (pb["I_rms_coil"] if pb else 1.0)))
    w_need = CFX.ipc2221_width_mm(i_tx, oz=d["oz"])
    flex_w = CFX.WIDTH + 2 * (d["w_tx"] - CFX.W_TX)
    stack = CFX.STACK_MM + (d["oz"] - CFX.OZ) * 0.0014 * 25.4
    # masses
    D, H = d["D"], d["H"]; a2 = (D / 233.0) ** 2; dh = D * H / (233.0 * 25.4)
    litz_g = B["c"]["coil_wire_g"] / STUDY_LEN_M * float(np.sum(2 * math.pi * B["r"]))
    ep = B["width"] * (B["rows"] * B["rp"]) * (B["r_out"] - B["width"] / 2); epoxy = HEAD_EPOXY * ep / _CAL.get("epoxy", ep)
    head_g = (HEAD_PRINT * (0.75 * a2 + 0.25 * dh) + (HEAD_RX + HEAD_SH + DISPLAY_FLEX_G) * a2 + (HEAD_EL - DISPLAY_FLEX_G) + litz_g + epoxy + HEAD_HW + HEAD_POT)
    sh = shaft(d, (head_g + YOKE_G) * 9.81e-3)
    n_cells = d["S"] * d["P"]
    pack_g = n_cells * cell["g"] + PK.OVERHEAD_2P * (0.55 + 0.45 * n_cells / 14.0) + RAIL
    dL = (d["L_shaft"] - 0.98) * 1000.0
    parts = [(head_g, LEV_HEAD0 + dL), (sh["tubes_g"] + CLAMP_G, LEV_SHAFT0 + dL / 2), (pack_g, LEV_PACK)] + FIXED_ITEMS
    total_g = sum(m for m, _ in parts) + DOCK_DELTA_G
    torque = sum(m * 9.81e-3 * x * 1e-3 for m, x in parts)
    inertia = sum(m * 1e-3 * (x * 1e-3) ** 2 for m, x in parts)
    P_b = (pb["P_tx"] if pb else float("nan")) + P_HEAD + p_extra; P_s = (ps["P_tx"] if ps else float("nan")) + P_HEAD + p_extra
    tj = 40.0 + (pb["P_sw"] if pb else 0.0) * (2.5 + 0.5 + 7.0)
    i_cell = P_b / vcut / d["P"] if pb else float("nan")
    gm = (max(dep["coin_25mm_silver"], 1e-3) * max(dep["gold_1g"], 1e-3) * max(dep["gold_0p1g"], 1e-3)) ** (1 / 3)
    swn = d["switch"]; lz = B["c"]["part"]
    rules = [
        rule("TX switch peak (boost) vs 80 % IDM", Ib, 0.8 * sw["idm"], "<=", f"TXD switch {swn}", "safety"),
        rule("clamp voltage vs 0.8 x switch VDS", d["V_cl"], 0.8 * sw["vds"], "<=", f"TXD switch {swn}", "safety"),
        rule("rule 6: switch VDS rating vs 630 V (flyback net)", sw["vds"], 630.0, ">=", f"TXD switch {swn}", "safety"),
        rule("rule 6: coil litz insulation rating vs 630 V (flyback net)", B["c"]["v_rating"], 630.0, ">=", f"coil litz {lz}", "safety"),
        rule("coil litz insulation rating vs the clamp voltage", B["c"]["v_rating"], d["V_cl"], ">=", f"coil litz {lz}", "safety"),
        rule("coil max turn-to-turn voltage at the clamp vs litz rating", d["V_cl"] * dt_max / N, B["c"]["v_rating"], "<=", f"coil bundle {B['rows']}x{B['cols']}", "safety"),
        rule("IPC-2221 B4 clearance at the clamp voltage vs the rule-6 1.0 mm gap (UNVERIFIED table)", ipc_b4_mm(d["V_cl"]), CFX.HV_GAP, "<=", "cord flex / TXD HV lanes", "safety"),
        rule("TX switch TJ in boost vs 125 C", tj, 125.0, "<=", f"TXD switch {swn}", "safety"),
        rule("boost current reachable at the cut-off bus (S x 3.0 V / R_loop)", Ib, 0.98 * vcut / R_loop, "<=", "TXD / pack", "target"),
        rule("pack full-charge voltage vs Y5B 50 V (VIN_H)", d["S"] * 4.2, Y5B_V, "<=", "head gland Y5B (VIN_H)", "safety"),
        rule("pack series count vs BQ76952 3S-16S", d["S"], BMS_S[1], "<=", "battery BMS", "safety"),
        rule("pack cell current in boost vs coldest-band rating", i_cell if pb else 99.0, cell["I_cont"], "<=", f"battery {d['cell']} {d['S']}S{d['P']}P", "safety"),
        rule("coil bundle top vs head height less today's 12.8 mm stack", B["top"], H - STACK_ABOVE, "<=", "coil channel", "target"),
        rule("coil inner edge radius vs 40 mm (centre electronics, ASSUMED)", B["r_in"], 40.0, ">=", "coil channel", "target"),
        rule("coil channel width vs 16 mm (ASSUMED)", B["width"], 16.0, "<=", "coil channel", "target"),
        rule("cord TX strip width vs IPC-2221 width at the boost rms (10 K)", d["w_tx"], w_need, ">=", f"cord flex TX strips {d['oz']} oz", "target"),
        rule("cord-flex width vs bore chord less 2", flex_w, sh["chord_mm"] - 2.0, "<=", f"telescope inner bore ({d['profile']})", "target"),
        rule("rolling loop: 2 x 40 x stack vs bore less 4", 2 * 40 * stack, sh["bore_mm"] - 4.0, "<=", "telescope rolling loop", "target"),
        rule("tip sag vs today's telescope 3.41 mm", sh["sag_mm"], REF["sag_mm"], "<=", f"shaft ({d['profile']} {d['af']:.1f}/{d['wall']:.2f})", "target"),
        rule("hand-to-head lever vs 95 % of today's 706 mm (operator stance, ASSUMED)", LEV_HEAD0 + dL, 0.95 * LEV_HEAD0, ">=", "shaft length", "target"),
        rule("collapsed length vs today's 430 mm", sh["collapsed_mm"], 430.0, "<=", "shaft (telescope)", "target"),
        rule("torque about the hand >= 0 (not tail-heavy, ASSUMED)", torque, 0.0, ">=", "balance about the grip", "target"),
    ]
    if d["rx"] == "hybrid": rules.append(rule("planar RX null found inside the TX", 1.0 if pl else 0.0, 1.0, ">=", "planar RX (hybrid)", "target", binary=True))
    if not ps: rules.append(rule("scan current reachable at the nominal bus", I, 0.999 * vbus / R_loop, "<=", "TXD / pack", "target"))
    if not pb: rules.append(rule("boost current reachable at the nominal bus", Ib, 0.999 * vbus / R_loop, "<=", "TXD / pack", "target"))
    ok_power = bool(ps and pb)
    m = dict(L_uH=L * 1e6, R_coil=R, C_self_pF=Cs * 1e12, C_node_pF=Cn * 1e12, Rd_ohm=Rd, R_flex=r_flex, R_loop=R_loop, I_boost=Ib, rows=B["rows"], bundle_top_mm=B["top"],
             r_out_mm=B["r_out"], r_mean_mm=B["r_out"] - B["width"] / 2 + B["od"] / 2, bundle_w_mm=B["width"], b300_uT_per_A=float(b_axis(B["r"], B["z"], p, np.array([0.3]))[0]) * 1e6,
             gate_us=gate, gate_planar_us=(pl["gate_us"] if pl else None), fall_us=fs["fall_us"], depth_cm=dep, depth_mono_cm=dep_mono, depth_gm_cm=gm,
             P_tx_boost_W=(pb["P_tx"] if pb else None), P_boost_W=P_b, P_scan_W=P_s, Wh_usable=wh, boost_h=(wh / P_b if ok_power else 0.0), scan_h=(wh / P_s if ok_power else 0.0),
             Tj_C=tj, E_pulse_mJ=(ps["E_mJ"] if ps else None), I_rms_boost=(pb["I_rms_coil"] if pb else None), P_coil_boost_W=((pb["I_rms_coil"] ** 2 * R) if pb else None),
             flex_w_mm=flex_w, w_tx_need_mm=w_need, head_g=head_g, litz_g=litz_g, pack_g=pack_g, tubes_g=sh["tubes_g"], total_g=total_g, torque_Nm=torque, inertia_kgm2=inertia,
             sag_mm=sh["sag_mm"], bore_mm=sh["bore_mm"], collapsed_mm=sh["collapsed_mm"], vbus=vbus, i_cell_A=i_cell, dt_max_turns=dt_max)
    if pl: m.update(planar_main_r_mm=pl["main_r_mm"], planar_buck_r_mm=pl["buck_r_mm"])
    out = dict(x=d, m=m, rules=rules, feasible=all(r["ok"] for r in rules), viol=[max(0.0, -r["margin"]) for r in rules],
               viol_kind=(sum(max(0.0, -r["margin"]) for r in rules if r["kind"] == "safety"), sum(max(0.0, -r["margin"]) for r in rules if r["kind"] != "safety")))
    if detail: out["internals"] = dict(Irms_b=(pb["I_rms_coil"] if pb else None), first_raw_us=fs["first_us"], LC=L / Cn)
    return out

def calibrate():
    """fit the gate offset and the deltas' references to today's machine, then report today against the repo's numbers"""
    _CAL.clear()
    e = evaluate(TODAY, detail=True)
    B = bundle(TODAY); Cs, _ = c_self(B, TODAY["N"], TODAY["p"])
    _CAL.update(C_self=Cs, gate_off=REF["gate_us"] - e["internals"]["first_raw_us"], epoxy=B["width"] * (B["rows"] * B["rp"]) * (B["r_out"] - B["width"] / 2))
    e = evaluate(TODAY, detail=True)
    _CAL.update(LC=e["internals"]["LC"], Irms_b=e["internals"]["Irms_b"])
    t = evaluate(TODAY); m = t["m"]
    hy = evaluate(dict(TODAY, rx="hybrid"))["m"]
    # torque / mass on rf2_pack_options' basis (chassis' 650 g head)
    dh = 650.0 - m["head_g"]; tq650 = m["torque_Nm"] + dh * 9.81e-3 * LEV_HEAD0 * 1e-3; tot650 = m["total_g"] + dh
    rows = [("coil L (uH)", m["L_uH"], REF["L_uH"], REF_SRC["L_uH"]), ("coil L vs FastHenry (uH)", m["L_uH"], REF["L_fasthenry_uH"], REF_SRC["L_fasthenry_uH"]),
            ("coil R (ohm)", m["R_coil"], REF["R_ohm"], REF_SRC["R_ohm"]), ("winding C_self (pF)", m["C_self_pF"], REF["C_self_pF"], REF_SRC["C_self_pF"]),
            ("first gate (us) [offset fitted here]", m["gate_us"], REF["gate_us"], REF_SRC["gate_us"]),
            ("depth 25 mm silver coin (cm)", m["depth_cm"]["coin_25mm_silver"], REF["depth"]["coin_25mm_silver"], REF_SRC["depth"]),
            ("depth 1 g gold (cm)", m["depth_cm"]["gold_1g"], REF["depth"]["gold_1g"], REF_SRC["depth"]),
            ("depth 0.1 g gold (cm)", m["depth_cm"]["gold_0p1g"], REF["depth"]["gold_0p1g"], REF_SRC["depth"]),
            ("boost runtime (h)", m["boost_h"], REF["boost_h"], REF_SRC["boost_h"]), ("scan runtime (h)", m["scan_h"], REF["scan_h"], REF_SRC["scan_h"]),
            ("boost current (A)", m["I_boost"], REF["I_boost"], REF_SRC["I_boost"]), ("switch TJ in boost (C)", m["Tj_C"], REF["Tj_C"], REF_SRC["Tj_C"]),
            ("cord-flex width (mm)", m["flex_w_mm"], REF["flex_mm"], REF_SRC["flex_mm"]),
            ("head mass (g)", m["head_g"], REF["head_g"], REF_SRC["head_g"]), ("shaft tip sag (mm)", m["sag_mm"], REF["sag_mm"], REF_SRC["sag_mm"]),
            ("shaft tubes (g)", m["tubes_g"], REF["tubes_g"], REF_SRC["tubes_g"]),
            ("torque about the hand, 650 g head basis (Nm)", tq650, REF["torque_Nm_650g_head"], REF_SRC["torque_Nm_650g_head"]),
            ("system mass, 650 g head basis (g)", tot650, REF["total_g_650g_head"], REF_SRC["total_g_650g_head"]),
            ("hybrid depth coin (cm)", hy["depth_cm"]["coin_25mm_silver"], REF["hybrid_depth"]["coin_25mm_silver"], REF_SRC["hybrid_depth"]),
            ("hybrid depth 1 g (cm)", hy["depth_cm"]["gold_1g"], REF["hybrid_depth"]["gold_1g"], REF_SRC["hybrid_depth"]),
            ("hybrid depth 0.1 g (cm)", hy["depth_cm"]["gold_0p1g"], REF["hybrid_depth"]["gold_0p1g"], REF_SRC["hybrid_depth"]),
            ("hybrid planar first gate (us)", hy["gate_planar_us"] or 0.0, REF["hybrid_gate_us"], REF_SRC["hybrid_gate_us"])]
    tab = [dict(quantity=q, model=round(v, 3), repo=r, err_pct=round(100 * (v / r - 1), 2), source=s, ok=bool(abs(v / r - 1) <= 0.03)) for q, v, r, s in rows]
    return dict(rows=tab, gate_offset_us=round(_CAL["gate_off"], 3), ok=all(r["ok"] for r in tab), today=t)

# ------------------------------------------------------------------ optimisation
OBJ = ("depth_gm_cm", "gold_0p1g", "boost_h", "total_g")
def objectives(e):
    m = e["m"]; return (m["depth_gm_cm"], m["depth_cm"]["gold_0p1g"], m["boost_h"], m["total_g"])

def suggest(trial):
    d = {}
    for k in CONT: d[k] = trial.suggest_float(k, *BOUNDS[k])
    for k in INTS: d[k] = trial.suggest_int(k, *BOUNDS[k])
    for k, v in CATS.items(): d[k] = trial.suggest_categorical(k, v)
    return d

def compact(e):
    return dict(x=e["x"], obj=objectives(e), feasible=e["feasible"], viol=float(sum(e["viol"])), broken=[(r["rule"], r["where"], r["kind"]) for r in e["rules"] if not r["ok"]])

def _worker(args):
    seed, budget, cal = args
    import optuna
    optuna.logging.set_verbosity(optuna.logging.ERROR)
    _CAL.update(cal)
    recs = []
    def obj(trial):
        e = evaluate(suggest(trial)); trial.set_constraint("safety", e["viol_kind"][0]); trial.set_constraint("target", e["viol_kind"][1])
        recs.append(compact(e)); return objectives(e)
    sampler = optuna.samplers.NSGAIISampler(population_size=60, seed=seed)
    st = optuna.create_study(directions=["maximize", "maximize", "maximize", "minimize"], sampler=sampler)
    st.enqueue_trial(dict(TODAY))
    t0 = time.time(); st.optimize(obj, timeout=budget, gc_after_trial=False)
    return recs, time.time() - t0

def pareto(F):
    """non-dominated rows of F (all objectives 'larger is better'): sweep in descending order of the normalised sum (a later row can
    never dominate an earlier one), each row tested against the front found so far"""
    if len(F) == 0: return np.array([], int)
    Z = (F - F.min(0)) / np.maximum(F.max(0) - F.min(0), 1e-12); order = np.argsort(-Z.sum(1))
    front = []; P = np.empty((0, F.shape[1]))
    for i in order:
        f = F[i]
        if len(P) and np.any(np.all(P >= f, axis=1) & np.any(P > f, axis=1)): continue
        front.append(i); P = np.vstack([P, f])
    return np.array(sorted(front))

CAP = 3.0
def score(m, t):
    """balanced score: geometric mean of five ratios vs today, each capped at 3 (diminishing returns): depth gm, 0.1 g gold, boost h,
    1 / total mass, 1 / |torque about the hand| (|torque| floored at 1 Nm)"""
    r = [m["depth_gm_cm"] / t["depth_gm_cm"], max(m["depth_cm"]["gold_0p1g"], 1e-3) / t["depth_cm"]["gold_0p1g"], max(m["boost_h"], 1e-3) / t["boost_h"],
         t["total_g"] / m["total_g"], max(abs(t["torque_Nm"]), 1.0) / max(abs(m["torque_Nm"]), 1.0)]
    return float(np.prod(np.minimum(np.maximum(r, 1e-6), CAP)) ** 0.2)

def dominates_today(m, t):
    """no worse than today on every objective: depth gm, 0.1 g, boost h, total mass, torque about the hand"""
    return (m["depth_gm_cm"] >= t["depth_gm_cm"] and m["depth_cm"]["gold_0p1g"] >= t["depth_cm"]["gold_0p1g"] and m["boost_h"] >= t["boost_h"]
            and m["total_g"] <= t["total_g"] and abs(m["torque_Nm"]) <= abs(t["torque_Nm"]))

def balanced(m, t):
    """the balanced rank: designs that dominate today first, ranked by detection (depth gm x 0.1 g ratios); the rest by score - 10"""
    det = (m["depth_gm_cm"] / t["depth_gm_cm"]) * (max(m["depth_cm"]["gold_0p1g"], 1e-3) / t["depth_cm"]["gold_0p1g"])
    return det if dominates_today(m, t) else score(m, t) - 10.0

def polish(x0, key, tm):
    """scipy Powell over the continuous variables (normalised), integers and categories held; penalty 10 x total violation"""
    x0 = dict(x0); lo = np.array([BOUNDS[k][0] for k in CONT]); hi = np.array([BOUNDS[k][1] for k in CONT])
    hi = np.where(hi > lo, hi, lo + 1e-9)                                  # a variable fixed with --fix has lo == hi
    u0 = (np.array([x0[k] for k in CONT]) - lo) / (hi - lo)
    def val(e):
        m = e["m"]
        if key == "balanced": v = balanced(m, tm)
        elif key == "total_g": v = -m["total_g"]
        elif key == "gold_0p1g": v = m["depth_cm"]["gold_0p1g"]
        else: v = m[key]
        return v
    def f(u):
        u = np.clip(u, 0, 1); d = dict(x0, **{k: float(lo[i] + u[i] * (hi[i] - lo[i])) for i, k in enumerate(CONT)}); e = evaluate(d)
        return -val(e) / v0 + 10.0 * sum(e["viol"])
    v0 = max(abs(val(evaluate(x0))), 1e-9)
    r = minimize(f, u0, method="Powell", bounds=[(0, 1)] * len(CONT), options=dict(maxfev=400, xtol=1e-3, ftol=1e-5))
    u = np.clip(r.x, 0, 1); d = dict(x0, **{k: float(lo[i] + u[i] * (hi[i] - lo[i])) for i, k in enumerate(CONT)})
    e = evaluate(d)
    return e if (e["feasible"] and val(e) >= val(evaluate(x0))) else evaluate(x0)

def sensitivity(x, tm):
    """one-at-a-time: continuous +-5 % of the variable's range (inside the bounds), integers +-1, categories: every other option (litz: the 4
    nearest catalog rows); change of each metric"""
    base = evaluate(x); bm = base["m"]; rows = []
    def met(m): return dict(depth_gm_cm=m["depth_gm_cm"], gold_0p1g=m["depth_cm"]["gold_0p1g"], boost_h=m["boost_h"], torque_Nm=m["torque_Nm"], total_g=m["total_g"])
    b0 = met(bm)
    def add(var, label, d):
        e = evaluate(d); mm = met(e["m"])
        rows.append(dict(var=var, change=label, **{f"d_{k}_pct": round(100 * (mm[k] / b0[k] - 1), 2) if b0[k] else None for k in b0}, feasible=e["feasible"],
                         newly_broken=[f"{r['rule']} @ {r['where']}" for r in e["rules"] if not r["ok"] and not any(q["rule"] == r["rule"] and not q["ok"] for q in base["rules"])]))
    for k in CONT:
        for s in (-1, 1):
            v = min(max(x[k] + 0.05 * s * (BOUNDS[k][1] - BOUNDS[k][0]), BOUNDS[k][0]), BOUNDS[k][1])
            if abs(v - x[k]) > 1e-9: add(k, f"{x[k]:.4g} -> {v:.4g}", dict(x, **{k: v}))
    for k in INTS:
        for s in (-1, 1):
            v = x[k] + s
            if BOUNDS[k][0] <= v <= BOUNDS[k][1]: add(k, f"{x[k]} -> {v}", dict(x, **{k: v}))
    for k in ("switch", "cell", "profile", "rx", "oz"):
        for v in CATS[k]:
            if v != x[k]: add(k, f"{x[k]} -> {v}", dict(x, **{k: v}))
    i0 = LITZ_IDX[x["litz"]]; c0 = LITZ[i0]
    near = sorted([c for c in LITZ if c["part"] != x["litz"]], key=lambda c: abs(c["cu_mm2"] - c0["cu_mm2"]) + abs(c["od_mm"] - c0["od_mm"]))[:4]
    for c in near: add("litz", f"{x['litz']} -> {c['part']}", dict(x, litz=c["part"]))
    return rows

def summary(e, tm=None):
    x, m = e["x"], e["m"]; c = LITZ[LITZ_IDX[x["litz"]]]
    s = dict(D_mm=round(x["D"], 1), H_mm=round(x["H"], 1), inset_mm=round(x["inset"], 1), r_mean_mm=round(m["r_mean_mm"], 1), N=x["N"], p=x["p"], bundle=f"{m['rows']}x{x['cols']}",
             litz=f"{c['part']} ({c['ins']} {c['v_rating']:.0f} V, {c['cu_mm2']:.3f} mm2, OD {c['od_mm']})", I_scan_A=round(x["I"], 2), I_boost_A=round(m["I_boost"], 2), T_flat_us=round(x["T_flat"]),
             V_clamp=round(x["V_cl"]), switch=x["switch"], pack=f"{x['cell']} {x['S']}S{x['P']}P", shaft=f"{x['profile']} {x['af']:.1f} mm / {x['wall']:.2f} wall, {x['L_shaft']:.3f} m", rx=x["rx"],
             cord=f"{x['w_tx']:.2f} mm {x['oz']} oz", L_uH=round(m["L_uH"], 1), R_coil=round(m["R_coil"], 3), gate_us=round(m["gate_us"], 2),
             gate_planar_us=(round(m["gate_planar_us"], 2) if m["gate_planar_us"] else None), depth_cm={k: round(v, 1) for k, v in m["depth_cm"].items()},
             depth_gm_cm=round(m["depth_gm_cm"], 2), boost_h=round(m["boost_h"], 2), scan_h=round(m["scan_h"], 2), P_boost_W=round(m["P_boost_W"], 2), Tj_C=round(m["Tj_C"], 1),
             head_g=round(m["head_g"]), pack_g=round(m["pack_g"]), tubes_g=round(m["tubes_g"]), total_g=round(m["total_g"]), torque_Nm=round(m["torque_Nm"], 3),
             inertia_kgm2=round(m["inertia_kgm2"], 4), sag_mm=round(m["sag_mm"], 2), flex_w_mm=round(m["flex_w_mm"], 2), feasible=e["feasible"],
             edge=[f"{r['rule']} @ {r['where']} ({r['value']} vs {r['limit']})" for r in e["rules"] if r["status"] == "EDGE"],
             broken=[f"{r['status']}: {r['rule']} @ {r['where']} ({r['value']} vs {r['limit']}, {r['kind']})" for r in e["rules"] if not r["ok"]])
    if tm: s["score_vs_today"] = round(score(m, tm), 4); s["no_worse_than_today"] = dominates_today(m, tm)
    return s

# ------------------------------------------------------------------ CAD
def build_cad(e):
    import cadquery as cq
    x, m = e["x"], e["m"]; B = bundle(x); files = []
    D, H = x["D"], x["H"]; wall = 2.0
    shell = cq.Workplane("XY").circle(D / 2).extrude(H).cut(cq.Workplane("XY").circle(D / 2 - wall).extrude(H - wall).translate((0, 0, wall)))
    r_in, r_o = B["r_out"] - B["width"] + B["od"] / 2, B["r_out"] + B["od"] / 2; z_lo, z_hi = FLOOR_Z, B["top"]
    coil = cq.Workplane("XZ").center((r_in + r_o) / 2, (z_lo + z_hi) / 2).rect(r_o - r_in, z_hi - z_lo).revolve(360, (-(r_in + r_o) / 2, 0, 0), (-(r_in + r_o) / 2, 1, 0))
    sh = shaft(x, 1.0); L = x["L_shaft"] * 1000.0; ang = math.radians(30.0)
    def prof(af, t, length):
        if x["profile"] == "square": w = cq.Workplane("YZ").rect(af, af).extrude(length).cut(cq.Workplane("YZ").rect(af - 2 * t, af - 2 * t).extrude(length))
        elif x["profile"] == "hex": w = cq.Workplane("YZ").polygon(6, 2 * af / math.sqrt(3)).extrude(length).cut(cq.Workplane("YZ").polygon(6, 2 * (af - 2 * t) / math.sqrt(3)).extrude(length))
        else: w = cq.Workplane("YZ").circle(af / 2).extrude(length).cut(cq.Workplane("YZ").circle(af / 2 - t).extrude(length))
        return w
    seg = (L + 200.0) / 3.0; tubes = None
    for i, af in enumerate(sh["afs"][::-1]):                   # inner (at the head) to outer (at the hinge)
        t = prof(af, x["wall"], seg).translate((i * (seg - 100.0), 0, 0)); tubes = t if tubes is None else tubes.union(t)
    x0, z0 = -D / 2 - 10.0, H + 10.0
    shaftw = tubes.rotate((0, 0, 0), (0, 1, 0), -30).mirror("YZ").translate((x0, 0, z0))
    cell = CELLS[x["cell"]]; per_row = math.ceil(x["S"] * x["P"] / 2)
    box = (per_row * cell["d"] + 6.0, cell["h"] + 6.0, 2 * cell["d"] + 10.0)
    hand = LEV_HEAD0 + (x["L_shaft"] - 0.98) * 1000.0; s_pack = hand - LEV_PACK
    px, pz = x0 - s_pack * math.cos(ang), z0 + s_pack * math.sin(ang) - 60.0
    pack = cq.Workplane("XY").box(*box).rotate((0, 0, 0), (0, 1, 0), 30).translate((px, 0, pz))
    parts = dict(head_shell=shell, coil_bundle=coil, shaft=shaftw, pack=pack)
    for k, w in parts.items():
        f = os.path.join(OUT, f"cleansheet_{k}.stl"); cq.exporters.export(w, f, tolerance=0.2); files.append(os.path.basename(f))
    cq.exporters.export(cq.Compound.makeCompound([w.val() for w in parts.values()]), os.path.join(OUT, "cleansheet_top.step")); files.append("cleansheet_top.step")
    try:
        import pyvista as pv
        pv.OFF_SCREEN = True
        pl = pv.Plotter(off_screen=True, window_size=(1400, 800))
        colors = dict(head_shell="#9fb7c9", coil_bundle="#c8742a", shaft="#333333", pack="#3d7a3d")
        for k in parts: pl.add_mesh(pv.read(os.path.join(OUT, f"cleansheet_{k}.stl")), color=colors[k], opacity=0.45 if k == "head_shell" else 1.0, smooth_shading=True)
        pl.add_text(f"clean-sheet top design: D {x['D']:.0f} x H {x['H']:.1f} mm, {x['N']}x{x['p']} turns, {x['switch']}, {x['cell']} {x['S']}S{x['P']}P, {x['profile']} {x['af']:.0f} mm shaft (MODELED)", font_size=10)
        pl.camera_position = "iso"; pl.camera.azimuth = 200; pl.camera.elevation = 10; pl.reset_camera(); pl.camera.zoom(1.25)
        pl.screenshot(os.path.join(OUT, "cleansheet_view.png")); pl.close(); files.append("cleansheet_view.png")
    except Exception as ex:                                       # noqa: BLE001 (no display: the STEP / STL stay)
        files.append(f"PNG not rendered: {ex}")
    return files

# ------------------------------------------------------------------ report
def variant_best():
    if not os.path.exists(VARIANTS_F): return None
    v = json.load(open(VARIANTS_F)); rows = {r["id"]: r for r in v.get("rows_kept", [])}; out = {}
    for key in ("score", "small_gold", "runtime", "lightest"):
        cid = v["champions"].get(key, {}).get("no_break"); r = rows.get(cid)
        if r: out[key] = dict(id=cid, depth_cm=r["depth_cm"], runtime_boost_h=r["runtime_boost_h"], torque_about_hand_Nm=r["torque_about_hand_Nm"], first_gate_us=r["first_gate_us"],
                              mass_delta_g=r.get("mass_delta_g"), tip_sag_mm=r.get("tip_sag_mm"))
    return out

def write_md(res, path):
    t = res["today"]; L = ["# AXE2 clean-sheet model (generated by rf2/rf2_cleansheet.py; MODELED, nothing adopted)", "",
         f"Status: {res['status']}", "",
         f"Run: {res['run_s']['total']:.1f} s in all ({res['run_s']['optimise']:.1f} s NSGA-II in {res['workers']} processes, {res['n_evaluated']} designs evaluated, "
         f"{res['n_feasible']} with no broken rule; {res['run_s']['polish']:.1f} s polish; {res['run_s'].get('cad', 0):.1f} s CAD). One evaluation: {res['ms_per_eval']:.2f} ms.", "",
         "## 1. Calibration: today's AXE2 through the clean-sheet model", "",
         "| Quantity | Model | Repo | Error % | Source | Within 3 % |", "|---|---|---|---|---|---|"]
    L += [f"| {r['quantity']} | {r['model']} | {r['repo']} | {r['err_pct']:+.2f} | {r['source']} | {'yes' if r['ok'] else '**no**'} |" for r in res["calibration"]["rows"]]
    L += ["", f"The first-gate offset fitted to today's 16.43 us is {res['calibration']['gate_offset_us']:+.3f} us (rf2_lowL_options' own base row reads 16.26 us because its offset is fitted at "
          "333 uH, not the modeled 327.5 uH; its depths were computed at 16.26 us, so the depths here sit about 1 % under them). Torque and system mass are compared on rf2_pack_options' basis "
          "(the chassis model's 650 g head); the clean-sheet itself uses the modeled 771 g head, so today's machine reads "
          f"{t['total_g']} g and {t['torque_Nm']} Nm below.", "",
         "## 2. Today vs the champions", "",
         "| Design | D x H mm | N x p, bundle | litz | I scan A / clamp V / T_flat us | switch | pack | shaft | RX | gate us | coin / 1 g / 0.1 g cm | boost h | head g | total g | torque Nm | sag mm | score |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    def row(name, s):
        dc = s["depth_cm"]
        return (f"| {name} | {s['D_mm']} x {s['H_mm']} | {s['N']} x {s['p']}, {s['bundle']} | {s['litz'].split(' (')[0]} | {s['I_scan_A']} / {s['V_clamp']} / {s['T_flat_us']} | {s['switch']} | {s['pack']} | "
                f"{s['shaft']} | {s['rx']} | {s['gate_us']} | {dc['coin_25mm_silver']} / {dc['gold_1g']} / {dc['gold_0p1g']} | {s['boost_h']} | {s['head_g']} | {s['total_g']} | {s['torque_Nm']} | {s['sag_mm']} | {s.get('score_vs_today', 1.0)} |")
    L.append(row("today (AXE2)", t))
    for k, s in res["champions"].items(): L.append(row(f"best {k}", s))
    L += ["", "### Top 5 feasible designs (balanced rank: no worse than today on depth gm, 0.1 g, boost h, total mass and |torque|, then the deepest by depth-gm x 0.1 g; "
          "score = geometric mean of the five ratios vs today, each capped at 3)", "",
          "| # | D x H mm | N x p, bundle | litz | I / clamp / T_flat | switch | pack | shaft | RX | cord | coin / 1 g / 0.1 g cm | boost h | total g | torque Nm | score |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(res["top5"], 1):
        dc = s["depth_cm"]
        L.append(f"| {i} | {s['D_mm']} x {s['H_mm']} | {s['N']} x {s['p']}, {s['bundle']} | {s['litz']} | {s['I_scan_A']} A / {s['V_clamp']} V / {s['T_flat_us']} us | {s['switch']} | {s['pack']} | {s['shaft']} | {s['rx']} | {s['cord']} | "
                 f"{dc['coin_25mm_silver']} / {dc['gold_1g']} / {dc['gold_0p1g']} | {s['boost_h']} | {s['total_g']} | {s['torque_Nm']} | {s['score_vs_today']} |")
    vb = res.get("variant_engine_best")
    if vb:
        L += ["", "### The variant engine's best (rf2/results/rf2_variants.json, no broken rule; its torque uses the chassis model's 650 g head)", "",
              "| Champion | coin / 1 g / 0.1 g cm | boost h | torque Nm | gate us | id |", "|---|---|---|---|---|---|"]
        for k, r in vb.items():
            dc = r["depth_cm"]; L.append(f"| {k} | {dc['coin_25mm_silver']} / {dc['gold_1g']} / {dc['gold_0p1g']} | {r['runtime_boost_h']} | {r['torque_about_hand_Nm']} | {r['first_gate_us']} | `{r['id']}` |")
    L += ["", "## 3. What the free design changes, and why", ""] + [f"- {f}" for f in res["findings"]]
    L += ["", "## 4. Rules: every broken or EDGE row of the champions and the top 5, at its location", ""]
    for name, s in [("today", t)] + [(f"best {k}", s) for k, s in res["champions"].items()] + [(f"top {i}", s) for i, s in enumerate(res["top5"], 1)]:
        rows = s["broken"] + [f"EDGE: {x}" for x in s["edge"]]
        L.append(f"- **{name}:** " + ("; ".join(rows) if rows else "no broken or EDGE row"))
    L += ["", "Rule counts over every evaluated design (a design can break several):", "", "| Rule @ location class | kind | designs breaking it |", "|---|---|---|"]
    L += [f"| {r['rule']} | {r['kind']} | {r['n']} |" for r in res["rule_tally"]]
    L += ["", "## 5. Sensitivity of the balanced champion (one variable at a time: continuous +-5 % of the range, integers +-1, every other category)", "", "| Variable | Change | depth gm % | 0.1 g % | boost h % | torque % | mass % | feasible | newly broken |", "|---|---|---|---|---|---|---|---|---|"]
    for r in res["sensitivity"]:
        L.append(f"| {r['var']} | {r['change']} | {r['d_depth_gm_cm_pct']} | {r['d_gold_0p1g_pct']} | {r['d_boost_h_pct']} | {r['d_torque_Nm_pct']} | {r['d_total_g_pct']} | {r['feasible']} | {'; '.join(r['newly_broken'])} |")
    L += ["", "## 6. Assumptions", ""] + [f"- {a}" for a in res["assumptions"]] + ["", "## 7. Limitations", ""] + [f"- {a}" for a in res["limitations"]]
    L += ["", "## 8. Files", ""] + [f"- `{f}`" for f in res["files"]] + [""]
    open(path, "w").write("\n".join(L))

ASSUMPTIONS = [
    "Every performance number is MODELED with the repo's models (named per line in the module docstring); no bench test, no fabricator review.",
    "Depth: target echo of a small eddy loop, MP1 v2 2.211 nV/rtHz + coil and cord Johnson noise, 1 MHz, 1000-pulse average, SNR 5 (rf2_lowL_options): absolute depths optimistic, the change is the result; ground, EMI and motion noise not modeled.",
    "Flat-top charging factor (1 - e^(-T/tau)) relative to today's 300 us (the repo model is calibrated at 300 us).",
    "Regenerative clamp 75 % (ASSUMED, rf2_continuous); pulse rate 400 Hz and the boost factor sqrt(2.5) fixed as today; head electronics 10.62 W at any bus voltage; hybrid second channel 0.35 W (ASSUMED there).",
    "Switch thermal path 10 K/W junction to 40 C ambient for every switch (rf2_lowL_options); hot RDS factors and Eoff of the parts without a logged hot value ASSUMED (see SWITCHES).",
    "Planar RX: rf2_lowL_options' 40-turn / 0.30 mm design scaled with the TX outer radius; the bucking radius is re-solved for an exact null per design; residual coupling = 0.449 % of M_main (rf2_lowL_options' 0.1 mm tolerance); RX L and R scale with radius, C 20.5 pF.",
    "Head shell: printed mass 75 % with D^2 and 25 % with D x H (ASSUMED split of 252 g); receive boards, shield and the 40 g display flex with D^2; 12.8 mm of lid / display / boards above the coil channel kept from today.",
    "Comb: column tooth 0.398 mm and row allowance 0.068 mm kept from today for every litz; outer column 2.4 mm inside the rim; channel width <= 16 mm and coil inner edge >= 40 mm ASSUMED.",
    "Shaft: 3 nested stages, each 2 x wall + 2.6 mm smaller (today's step), 100 mm overlaps, tubes 380 mm x L/0.98; carbon E 50 GPa, 1.55 g/cm3 (ASSUMED, rf2_shaft_options); corner radii ignored; a flat cord strip lies corner to corner in a hex bore.",
    "Cord: TX strips 1.355 m x L/0.98 out and back; IPC-2221 internal 10 K width at the boost rms (rf2_cordflex's 3.67 A scaled by the modeled coil rms); flex stack 0.15 mm + 0.036 mm per extra oz.",
    "Masses and lever arms of the chassis items from rf2_chassis_check (their own ASSUMED masses); the pack's lever arm fixed at -161.3 mm; the head and shaft levers move with the shaft length.",
    "Operator stance: hand-to-head lever >= 95 % of today's 706 mm (ASSUMED, so the optimiser cannot buy torque by shortening the reach).",
]
LIMITATIONS = [
    "Quasi-static models only: no transient FEM of the head, no proximity loss inside the litz bundle, no thermal model of the potted channel.",
    "Ground response, soil viscosity, EMI pickup, motion and the quadrupole bearing boards are outside the objectives (the boards are carried as mass only).",
    "The planar RX is a scaled equivalent of the repo design, not re-optimised per design; its gate depends on the 0.1 mm build tolerance assumed there.",
    "The IPC-2221 B4 clearance table is not on file (UNVERIFIED); rule 6 itself (630 V parts, >= 1.0 mm) is applied as the repo states it.",
    "Cell data from the datasheets on file (the LG M50T from a 2018 rev 0 draft); the RC LiPo option of rf2_pack_options is not a cell and is not searched.",
    "Optuna NSGA-II is stochastic: the front is a sample; the run seeds are recorded so a run can be repeated (time-limited workers, so the trial count varies with the machine).",
    "Head height costs only mass here (no drag, ground clearance or internal stack design), so it runs to the 35 mm bound whenever the coil wants rows; the shaft runs to the 95 % reach floor for the same reason (no ergonomics beyond that rule).",
    "The variant engine's torque figures use the chassis model's 650 g head; the clean-sheet uses the modeled 771 g head (today 5.02 Nm here vs 4.19 Nm there).",
]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--budget", type=float, default=70.0); ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1)); ap.add_argument("--no-cad", action="store_true")
    ap.add_argument("--fix", nargs="*", default=[], help="hold variables: e.g. D=233 H=25.4 cell='Molicel P45B' S=7 P=1 profile=square af=31 wall=1.2 L_shaft=0.98")
    ap.add_argument("--tag", default="", help="write rf2_cleansheet_<tag>.json and docs/CLEANSHEET_<tag>.md (no CAD) instead of the main outputs")
    a = ap.parse_args(); T0 = time.time()
    for kv in a.fix:                                                       # 2026-10-31: constrained runs (e.g. today's head envelope)
        k, v = kv.split("=", 1)
        if k in CATS: CATS[k] = [type(CATS[k][0])(v) if not isinstance(CATS[k][0], str) else v]
        elif k in BOUNDS: x = float(v); BOUNDS[k] = (int(x), int(x)) if k in INTS else (x, x)
        else: raise SystemExit(f"--fix: unknown variable {k}")
    if a.tag: a.no_cad = True
    cal = calibrate(); today = cal["today"]; tm = today["m"]
    t1 = time.time(); [evaluate(dict(TODAY, N=n)) for n in range(10, 40)]; ms = (time.time() - t1) / 30 * 1e3
    print("calibration:"); [print(f"  {r['quantity']:<48} model {r['model']:>10}  repo {r['repo']:>8}  {r['err_pct']:+6.2f} %") for r in cal["rows"]]
    print(f"one evaluation {ms:.2f} ms; optimising {a.budget:.0f} s x {a.workers} processes")
    import multiprocessing as mp
    t2 = time.time(); seeds = [11 + 7 * k for k in range(a.workers)]
    with mp.get_context("fork").Pool(a.workers) as pool: res_w = pool.map(_worker, [(s, a.budget, dict(_CAL)) for s in seeds])
    recs = [r for rr, _ in res_w for r in rr]; t_opt = time.time() - t2; print("worker times", [round(t, 1) for _, t in res_w])
    feas = [r for r in recs if r["feasible"]]
    print(f"evaluated {len(recs)} designs, {len(feas)} feasible, in {t_opt:.1f} s")
    # rule tally
    tally = {}
    for r in recs:
        for name, where, kind in r["broken"]:
            k = (name, kind); tally[k] = tally.get(k, 0) + 1
    rule_tally = [dict(rule=k[0], kind=k[1], n=v) for k, v in sorted(tally.items(), key=lambda kv: -kv[1])]
    # Pareto of feasible designs
    Fm = np.array([[o[0], o[1], o[2], -o[3]] for o in (r["obj"] for r in feas)]) if feas else np.zeros((0, 4))
    _, uniq = np.unique(np.round(Fm, 4), axis=0, return_index=True); feas = [feas[i] for i in sorted(uniq)]; Fm = Fm[sorted(uniq)]
    tp = time.time(); front_i = pareto(Fm) if len(Fm) else []
    front = [evaluate(feas[i]["x"]) for i in front_i]; print(f"pareto {len(front)} in {time.time() - tp:.1f} s")
    # polish: best per objective + balanced, from the feasible set
    t3 = time.time(); champs = {}
    keys = dict(depth_gm_cm=lambda e: e["m"]["depth_gm_cm"], gold_0p1g=lambda e: e["m"]["depth_cm"]["gold_0p1g"], boost_h=lambda e: e["m"]["boost_h"],
                total_g=lambda e: -e["m"]["total_g"], balanced=lambda e: balanced(e["m"], tm))
    pool_e = front if front else [today]; polished = []
    for k, fn in keys.items():
        for best in sorted(pool_e, key=fn, reverse=True)[:3]: polished.append(polish(best["x"], k, tm))
    cand = [e for e in pool_e + polished if e["feasible"]] or [today]
    for k, fn in keys.items(): champs[k] = max(cand, key=fn)
    t_pol = time.time() - t3
    allf = front + [e for e in polished if e["feasible"]]
    allf_u = {}
    for e in allf: allf_u[json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in e["x"].items()}, sort_keys=True)] = e
    ranked = sorted(allf_u.values(), key=lambda e: -balanced(e["m"], tm))
    top5 = ranked[:5]
    t5 = time.time(); sens = sensitivity(champs["balanced"]["x"], tm); print(f"sensitivity {time.time() - t5:.1f} s")
    ts = summary(today, tm)
    cs = {k: summary(e, tm) for k, e in champs.items()}
    # findings
    bal = cs["balanced"]; g = cs["gold_0p1g"]; dg = cs["depth_gm_cm"]; rt = cs["boost_h"]; tq = cs["total_g"]
    def pct(a_, b_): return f"{100 * (a_ / b_ - 1):+.0f} %"
    findings = [
        f"balanced champion: D {bal['D_mm']} x H {bal['H_mm']} mm, {bal['N']} x {bal['p']} turns of {bal['litz'].split(' (')[0]} ({bal['bundle']}), {bal['I_scan_A']} A at a {bal['V_clamp']} V clamp on {bal['switch']}, "
        f"{bal['pack']}, {bal['shaft']}, {bal['rx']}: depth gm {bal['depth_gm_cm']} cm ({pct(bal['depth_gm_cm'], ts['depth_gm_cm'])}), 0.1 g {bal['depth_cm']['gold_0p1g']} cm ({pct(bal['depth_cm']['gold_0p1g'], ts['depth_cm']['gold_0p1g'])}), "
        f"boost {bal['boost_h']} h ({pct(bal['boost_h'], ts['boost_h'])}), torque {bal['torque_Nm']} Nm ({pct(bal['torque_Nm'], ts['torque_Nm'])}), mass {bal['total_g']} g ({pct(bal['total_g'], ts['total_g'])}).",
        f"lower inductance wins the small targets: the 0.1 g champion runs {g['L_uH']} uH ({g['N']} x {g['p']}) and a {g['V_clamp']} V clamp, first gate {g['gate_us']} us vs today's {ts['gate_us']} us; the short-tau gold echo grows faster than the field per amp falls.",
        f"coin / geometric-mean depth wants a big head and amp-turns: the depth champion is D {dg['D_mm']} mm, {dg['N']} x {dg['p']}, {dg['I_scan_A']} A, depth gm {dg['depth_gm_cm']} cm, but costs {dg['torque_Nm']} Nm and {dg['boost_h']} h.",
        f"runtime is bought with pack cells, low loop resistance and a short flat-top: the runtime champion {rt['pack']}, R_coil {rt['R_coil']} ohm, T_flat {rt['T_flat_us']} us gives {rt['boost_h']} h.",
        f"the lightest machine: {tq['total_g']} g ({pct(tq['total_g'], ts['total_g'])}) with D {tq['D_mm']} mm, {tq['pack']}, {tq['shaft']}; torque {tq['torque_Nm']} Nm (a pack behind the hand counterbalances the head, so a heavier pack lowers the torque: mass and torque pull in opposite directions).",
        f"clamp voltage is the strongest free lever on the first gate (fall = L I / V_clamp); it is held by 0.8 x VDS of the switch and by the litz rating, and above 500 V the IPC-2221 B4 clearance exceeds rule 6's 1.0 mm (reported as a safety row, never relaxed).",
        f"{len(feas)} unique feasible designs out of {len(recs)}; the most-broken rules: " + "; ".join(f"{r['rule']} ({r['n']})" for r in rule_tally[:5]) + ".",
    ]
    status = "MODELED clean-sheet study (owner 2026-10-31): nothing adopted, nothing excluded (every evaluated design's broken rules are counted; safety rules reported, never relaxed)"
    res = dict(status=status, calibration=dict(rows=cal["rows"], gate_offset_us=cal["gate_offset_us"], ok=cal["ok"]), today=ts, variables=dict(bounds=BOUNDS, categories={k: v for k, v in CATS.items() if k != "litz"},
               litz_rows=len(CATS["litz"]), today=TODAY), switches={k: v["src"] for k, v in SWITCHES.items()}, screened_switches=SCREENED_SWITCHES,
               cells={k: v["src"] for k, v in CELLS.items()}, objectives=["max depth geometric mean (coin, 1 g, 0.1 g)", "max 0.1 g gold depth", "max continuous-boost runtime", "min total carried mass"],
               objective_note="torque about the hand is not minimised directly (a heavy pack behind the hand drives it to zero or negative): it is reported, kept >= 0 by a target rule, and enters the balanced rank (no worse than today)",
               balanced_rank="designs no worse than today on depth gm, 0.1 g, boost h, total mass and |torque|, ranked by the depth-gm x 0.1 g ratio product; others by the capped 5-ratio score - 10",
               workers=a.workers, seeds=seeds, n_evaluated=len(recs), n_feasible=len(feas), ms_per_eval=ms,
               pareto_front=[summary(e, tm) for e in sorted(front, key=lambda e: -score(e["m"], tm))][:300], n_pareto=len(front),
               pareto_full_x=[e["x"] for e in front], champions=cs, top5=[summary(e, tm) for e in top5],
               champion_rules={k: e["rules"] for k, e in champs.items()}, today_rules=today["rules"], rule_tally=rule_tally,
               sensitivity=sens, variant_engine_best=variant_best(), findings=findings, assumptions=ASSUMPTIONS, limitations=LIMITATIONS)
    res["run_s"] = dict(optimise=round(t_opt, 1), polish=round(t_pol, 1))
    files = ["rf2/rf2_cleansheet.py", "rf2/results/rf2_cleansheet.json", "docs/CLEANSHEET.md"]
    if not a.no_cad:
        t4 = time.time(); files += ["rf2/results/" + f for f in build_cad(champs["balanced"] if champs["balanced"]["feasible"] else top5[0])]; res["run_s"]["cad"] = round(time.time() - t4, 1)
    res["run_s"]["total"] = round(time.time() - T0, 1); res["files"] = files
    res["ok"] = bool(cal["ok"])
    res["fixed"] = a.fix; sfx = f"_{a.tag}" if a.tag else ""
    json.dump(res, open(os.path.join(OUT, f"rf2_cleansheet{sfx}.json"), "w"), indent=1, default=float)
    write_md(res, os.path.join(ROOT, "docs", f"CLEANSHEET{sfx}.md"))
    print("champions:"); [print(f"  {k:<12} gm {s['depth_gm_cm']} 0.1g {s['depth_cm']['gold_0p1g']} boost {s['boost_h']} torque {s['torque_Nm']} feasible {s['feasible']}") for k, s in cs.items()]
    print("run s:", res["run_s"])
    return res

if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
