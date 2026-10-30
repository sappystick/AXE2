#!/usr/bin/env python3
"""RF1 cavity condensation and potting study (2026-10-29), side experiment: which layers of the vault can shrink once the head electronics are rigid-flex,
which part swaps that needs, and where potting then fills and protects. Coils, formers and printed parts as the baseline unless a layer is shrunk.
Layer budget per layer = what physically has to fit: board + tallest part on each side + clearance, from the baseline part libraries
(src/pcb/afe_design.py LIB bodies for AB1, kit_v19/lib_bodies.json + the CB1D BOM / pick-and-place) with the RF1 part swaps:
  CB1D M5 Murata OKI-78SR (SIP, 10.2 mm body) -> TI LMR36015 (4.2-60 V, 1.5 A, VQFN-HR 2 x 3 mm, 1 mm max height; SNVSB49D Sept 2020, read 2026-10-29)
     + Bourns SRN4018-6R8M (6.8 uH, Isat 1.6 A, Irms 1.5 A, 1.8 mm max; data/seed/datasheets/Bourns_SRN4018.pdf); +5V load 0.70 A (system_live i5)
  CB1D U1 Pico 2 W on pins (8.0 mm) -> chip-down RP2354A (RP2350 with 2 MB flash in package, QFN-60 7 x 7 mm; RP2350 datasheet build 01/10/2026) + 12 MHz
     crystal; no CYW43439 radio (settles OPEN_ITEMS 42 by removal). QFN-60 height is drawn, not tabulated in the datasheet text: 0.9 mm ASSUMED (UNVERIFIED)
  CB1D JA / JB headers (9.0 mm) and AB1 J1 / J2 headers (4.0 mm + 5.0 mm socket) -> rigid-flex hinges (0 mm)
Two options:
  K-top (recommended): every layer that holds coils, magnetic or conductive mass near the receive coils keeps its z (L0-L4: SB1R, gallery, AB1, septum,
     absorber); only L5 (controller) shrinks, so LB1, the roof, the cap and the HTA come down together; the freed L2 headroom is filled by the gel.
  S (full shrink): also shrinks L1 and L2, which moves AB1, the septum and the carbonyl-iron absorber toward the receive coils: changes the receive null
     (absorber permeability next to the lobes) and must be re-simulated (sbq_sim, head_crosscheck, check_v22) before it is considered.
Volumes are envelope estimates (cylinder r 44 minus the board disc and the part boxes), not mesh booleans: phase 5 regenerates the meshes.
MODELED. usage (repo root): python3 experiments/RF1_rigidflex/rf1_cavity.py"""
import os, sys, json, csv, math, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "results")
W = os.path.join(ROOT, "work")
R_BORE, R_TUBE_O, RHO_PETG = 44.0, 49.5, 1.27                       # hub bore and tube outer radius (DESIGN_STATE), PETG g/cc (ASSUMED class)
LAYERS = [("L0", 0.0, 3.2, "base plate + SB1R-QA/QB"), ("L1", 3.2, 9.0, "gallery (RX leads)"), ("floor", 9.0, 9.8, "floor"), ("L2", 9.8, 20.0, "analog cell (AB1A/AB1B)"),
          ("L3", 20.0, 21.9, "septum + cloth"), ("L4", 21.9, 27.0, "absorber (CI)"), ("L5", 27.0, 38.8, "controller (CB1D)"), ("gap", 38.8, 39.2, ""),
          ("L6", 39.2, 40.8, "display (LB1)"), ("gap2", 40.8, 41.3, ""), ("L7", 41.3, 44.5, "roof"), ("L8", 44.5, 47.1, "cap + HTA")]
SWAP_H = {"M5": ("LMR36015 + SRN4018-6R8M", 1.8), "U1": ("RP2354A chip-down (QFN-60) + crystal", 0.9), "JA": ("hinge", 0.0), "JB": ("hinge", 0.0), "JHTA": ("hinge (HTA tail)", 0.0), "JLB": ("hinge (LB1)", 0.0)}
COMP = {"GEL": (0.95, 1.0), "SYN": (0.6, 0.8)}                      # potting_map.py classes (g/cc, ASSUMED)

def cb1d_parts():
    LIBJ = json.load(open(os.path.join(W, "kit_v19/lib_bodies.json"))); typ = {}
    for r in list(csv.reader(open(os.path.join(W, "kit_v18/CB1D/PF233-CB1D_BOM.csv"))))[1:]:
        for ref in r[1].split(","): typ[ref.strip()] = r[2]
    rows = []
    for r in csv.DictReader(open(os.path.join(W, "kit_v18/CB1D/PF233-CB1D_pickplace.csv"))):
        t = typ.get(r["Ref"])
        if t not in LIBJ: continue
        bw, bh, bz = LIBJ[t]
        if r["Ref"] in SWAP_H:
            new, bz = SWAP_H[r["Ref"]]
            if r["Ref"] == "U1": bw, bh = 7.0, 7.0
            if r["Ref"] == "M5": bw, bh = 4.0, 7.0                     # converter 2 x 3 + inductor 4 x 4 side by side
            if r["Ref"] in ("JA", "JB", "JHTA", "JLB"): continue
        rows.append(dict(ref=r["Ref"], side=r["Side"], w=bw, h=bh, z=bz))
    return rows

def ab1_parts():
    sys.path.insert(0, os.path.join(ROOT, "src", "pcb")); out = {}
    cwd = os.getcwd(); os.chdir(W)
    try:
        for B in ("A", "B"):
            os.environ["BOARD"] = B; sys.modules.pop("afe_design", None)
            with contextlib.redirect_stdout(io.StringIO()): import afe_design as A
            P = json.load(open(f"out_board/AB1{B}_layout.json"))["PLACE"]; T = {p["ref"]: p for p in A.PARTS}
            rows = []
            for r, v in P.items():
                if r not in T or r in ("J1", "J2"): continue
                b = A.LIB[T[r]["type"]].get("body", (0, 0, 0)); rows.append(dict(ref=r, side=v[3], w=b[0], h=b[1], z=b[2]))
            out[B] = rows
    finally: os.chdir(cwd)
    return out

def budget():
    cb = cb1d_parts(); ab = ab1_parts()
    top_cb = max(p["z"] for p in cb if p["side"] == "top"); bot_cb = max([p["z"] for p in cb if p["side"] != "top"] + [0.0])
    top_ab = max(p["z"] for B in ab.values() for p in B if p["side"] == "F"); bot_ab = max([p["z"] for B in ab.values() for p in B if p["side"] != "F"] + [0.55])
    CLR = 1.0                                                                                # pour cover / clearance above the tallest part
    need = dict(L1=0.2 + 2 * CLR, L2=bot_ab + 1.6 + top_ab + 2 * CLR + 0.3, L5=bot_cb + 1.6 + top_cb + CLR)
    base = {n: z1 - z0 for n, z0, z1, _ in LAYERS}
    return dict(cb1d_tallest_top_mm=top_cb, cb1d_tallest_bottom_mm=bot_cb, ab1_tallest_top_mm=top_ab, ab1_tallest_bottom_mm=bot_ab,
                cb1d_top5=sorted(((p["z"], p["ref"]) for p in cb if p["side"] == "top"), reverse=True)[:5], need_mm={k: round(v, 2) for k, v in need.items()},
                baseline_mm={k: round(base[k], 2) for k in ("L1", "L2", "L5")}, saving_mm={k: round(base[k] - need[k], 2) for k in need}), cb, ab

def options(B, cb):
    s5 = max(0.0, B["saving_mm"]["L5"]); s1 = max(0.0, B["saving_mm"]["L1"]); s2 = max(0.0, B["saving_mm"]["L2"])
    ring = math.pi * (R_TUBE_O ** 2 - R_BORE ** 2)                                           # mm2, tube wall (upper bound: lanes and tracks are solid here)
    def tube_g(dz): return round(ring * dz / 1000 * RHO_PETG, 1)
    l5_h = B["need_mm"]["L5"]; board = math.pi * 39.0 ** 2 * 1.6
    parts = sum(p["w"] * p["h"] * p["z"] for p in cb)
    l5_free = (math.pi * R_BORE ** 2 * l5_h - board - parts) / 1000                          # cm3, envelope estimate
    pot = {k: [round(l5_free * v[0], 1), round(l5_free * v[1], 1)] for k, v in COMP.items()}
    lever = 0.97                                                                             # head horizontal reach, m (upper_check balance)
    K = dict(name="K-top (recommended)", shrink_mm=round(s5, 1), head_height_mm=round(47.1 - s5, 1), tube_saving_g=tube_g(s5),
             l5_pour_cm3=round(l5_free, 1), l5_pour_g=pot, net_head_g=[round(pot["SYN"][0] - tube_g(s5), 1), round(pot["SYN"][1] - tube_g(s5), 1)],
             net_torque_kg_m=[round((pot["SYN"][0] - tube_g(s5)) / 1000 * lever, 4), round((pot["SYN"][1] - tube_g(s5)) / 1000 * lever, 4)],
             moves="LB1, roof, cap and HTA come down by the L5 saving; nothing below z 27 moves",
             rerun=["head_crosscheck (HTA and LB1 positions)", "the HTA timing antenna coupling (it moves toward the formers)", "head thermal with SYN in L5"])
    S = dict(name="S (full shrink, not recommended before simulation)", shrink_mm=round(s5 + s1 + s2, 1), head_height_mm=round(47.1 - s5 - s1 - s2, 1), tube_saving_g=tube_g(s5 + s1 + s2),
             moves=f"AB1 down {s1:.1f} mm, septum + absorber down {s1 + s2:.1f} mm toward the receive coils",
             rerun=["sbq_sim leak null with the absorber lower", "check_v22 (47 geometry checks)", "head_crosscheck", "former / bridge clearances"])
    return K, S

def potting():
    return [dict(zone="L1 gallery", baseline="GEL (34.8 cm3)", rf1="GEL, full: the flex jumper is fixed, nothing to service", why="locks the lead jumper; er 2.7-3.0 next to the receive leads"),
            dict(zone="L2 analog cell", baseline="GEL (52.3 cm3)", rf1="GEL, the headroom freed by the headers is filled too", why="no connector voids or ribbon fold left; the hinge root is wetted (strain relief)"),
            dict(zone="L4 absorber", baseline="CI", rf1="CI unchanged", why="magnetic function"),
            dict(zone="L5 controller (new)", baseline="conformal coat only (Pico W antenna, serviceable pads)", rf1="SYN (syntactic silicone) up to 1 mm over the tallest part, below the hinge bend",
                 why="no radio left, no connector to service: the board can be potted; locks parts (microphonics), seals moisture, conducts better than the still air it replaces"),
            dict(zone="hinges / folds", baseline="-", rf1="no rigid epoxy across a fold; the bend region stays outside every pour (duct), the roots are in gel",
                 why="a rigid pour on a fold cracks the copper under thermal cycling"),
            dict(zone="L6 display", baseline="conformal coat", rf1="conformal coat (LED light path)", why="the pixel holes need the LEDs clear"),
            dict(zone="L8 HTA", baseline="conformal coat", rf1="conformal coat; flex tail service loop free under the removable roof", why="the roof stays removable")]

if __name__ == "__main__":
    B, cb, ab = budget(); K, S = options(B, cb)
    out = dict(status="MODELED (RF1 cavity study, side experiment); envelope estimates, not mesh booleans", budget=B, option_K_top=K, option_S=S, potting=potting(),
               swaps={k: v[0] for k, v in SWAP_H.items()}, unverified=["RP2354A QFN-60 package height (drawn only): 0.9 mm ASSUMED"])
    json.dump(out, open(os.path.join(OUT, "rf1_cavity.json"), "w"), indent=1)
    print("budget", B); print("K-top", K); print("S", S)
