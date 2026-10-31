#!/usr/bin/env python3
"""RF2 folding-shaft options that carry an optical data link across every fold (owner 2026-10-31). MODELED; options only, nothing adopted.

Why: the 1 mm POF (Mitsubishi GH-4001-P) needs a 15 mm radius for repeated bending (10 000 cycles +-90 deg, 500 g) and 25 mm static (<= 1 dB per
quarter bend); the telescope's rolling loop inside the 18.6 mm inner bore allows 8.2 mm (rf2_shaftlink_options). A fixed-length shaft that FOLDS
at hinges lets the fibre cross each hinge on a drum coaxial with the hinge axis (radius >= 15 mm), riding on the outside of the fold: a 180 deg
fold pays out pi r of fibre, taken up by the fibre sliding in a PTFE conduit to one slack store at the chassis (loop radius >= 25 mm, static).
The flex crosses each hinge as a clock spring (2 turns on a 34 mm drum, ASSUMED). The existing chassis hinge (rf2_chassis st 790-816) is a
fold too and counts. Same-profile segments (no nesting), so every segment can carry an internal hub and separators.

Model: shaft 980 mm (telescope extended = 430 collapsed + 550 travel, rf2_chassis); cantilever from the chassis hinge with the head + yoke at the tip
and the tubes' own weight; each mid-shaft hinge is a rotational spring k = 300 N m / rad (latched composite hinge, ASSUMED) and 30 g (ASSUMED).
Link budget: AFBR-1624Z PN min -5.5 dBm, AFBR-2624Z PIN min -22 dBm (16.5 dB); fibre 0.17 dB/m; 2 end connectors 1.5 dB each (ASSUMED);
2.0 dB per 180 deg wrap at 15 mm (two quarter bends, ASSUMED from the <= 1 dB quarter-bend figure); 3 dB margin required.
Hinges at s < 375 mm from the head (rf2_system echo distance for TXD-class metal) must be metal-free (PEEK / ceramic pins, no springs).
Writes rf2/results/rf2_fold_options.json.   usage: python3 rf2/rf2_fold_options.py"""
import os, sys, json, math
import numpy as np
from shapely.geometry import Polygon, box as sbox
from shapely import contains_xy
from shapely.affinity import rotate
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "results"); sys.path.insert(0, HERE)
E_CF, RHO_CF = 50e3, 1.55e-3
L_SHAFT, COLLAPSED_TELE, TRAVEL = 980.0, 430.0, 550.0
K_HINGE, M_HINGE_G, KNUCKLE_MM = 300e3, 30.0, 20.0          # N mm / rad, g, axial length added per hinge
POF = dict(r_rep=15.0, r_static=25.0, db_per_m=0.17, cycles=10000)
BUDGET_DB, CONN_DB, WRAP_DB, MARGIN_DB = 16.5, 1.5, 2.0, 3.0
ECHO_S_MM = 375.0

def profile(shape, af, t=1.2, internal="none"):
    rc = af / math.sqrt(3) if shape == "hex" else af / math.sqrt(2)
    n, rot = (6, 0.0) if shape == "hex" else (4, math.pi / 4)
    poly = lambda r: Polygon([(r * math.cos(rot + 2 * math.pi * k / n), r * math.sin(rot + 2 * math.pi * k / n)) for k in range(n)])
    s = poly(rc).difference(poly(rc - t / math.cos(math.pi / n)))
    if internal.startswith("hub"):
        hub = Polygon([(2.5 * math.cos(a), 2.5 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 48)]).difference(Polygon([(2.0 * math.cos(a), 2.0 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 48)]))
        webs = [rotate(sbox(2.3, -0.3, rc - t, 0.3), math.degrees(rot + 2 * math.pi * k / n), origin=(0, 0)) for k in range(n)]
        for w in webs: hub = hub.union(w)
        s = s.union(hub.intersection(poly(rc - 0.5 * t)))
    g = np.linspace(-af, af, 701); X, Y = np.meshgrid(g, g); m = contains_xy(s, X, Y); dA = (g[1] - g[0]) ** 2
    I = min(float(np.sum(Y[m] ** 2) * dA), float(np.sum(X[m] ** 2) * dA))
    cu = 0.0
    if internal == "hub6_cu": cu = 2 * 0.018 * (n * (rc - t - 2.3) + 2 * math.pi * 2.5) * 8.96e-3        # g/mm, 18 um both faces
    return dict(A=s.area, I=I, g_per_mm=RHO_CF * s.area + cu, chambers=n if internal.startswith("hub") else 1)

def cantilever(pr, hinges_s, P_tip_N):
    """tip deflection of a uniform shaft fixed at the chassis hinge (x = 0 at the chassis, the head at x = L); hinges at distance s from the head"""
    x = np.linspace(0, L_SHAFT, 1961); q = pr["g_per_mm"] * 9.81e-3
    M = P_tip_N * (L_SHAFT - x) + q * (L_SHAFT - x) ** 2 / 2; kappa = M / (E_CF * pr["I"])
    th = np.concatenate([[0], np.cumsum((kappa[1:] + kappa[:-1]) / 2 * np.diff(x))])
    for s in hinges_s:                                                     # add the hinge rotation M / k at x_h = L - s
        xh = L_SHAFT - s; Mh = P_tip_N * s + q * s ** 2 / 2; th = th + np.where(x >= xh, Mh / K_HINGE, 0.0)
    w = np.concatenate([[0], np.cumsum((th[1:] + th[:-1]) / 2 * np.diff(x))])
    return float(w[-1])

MECH = {"telescope (today)": dict(hinges=[], fold=False),
        "fold x1 (mid) + chassis hinge": dict(hinges=[490.0], fold=True),
        "fold x2 (thirds) + chassis hinge": dict(hinges=[327.0, 653.0], fold=True),
        "fold neck + mid + chassis hinge": dict(hinges=[60.0, 490.0], fold=True),
        "fold x3 (quarters) + chassis hinge": dict(hinges=[245.0, 490.0, 735.0], fold=True)}
PROFILES = {"square31": ("square", 31.0, "none"), "hex31": ("hex", 31.0, "none"), "hex31 hub6": ("hex", 31.0, "hub6"), "hex31 hub6_cu": ("hex", 31.0, "hub6_cu"),
            "hex26 hub6_cu": ("hex", 26.0, "hub6_cu"), "square26": ("square", 26.0, "none")}

def main():
    hc = json.load(open(os.path.join(HERE, "head", "out_BF", "rf2_head_check.json"))); P = (hc["checks"]["mass_g"]["total_islands_only"] + 40.0) * 9.81e-3
    so = json.load(open(os.path.join(HERE, "results", "rf2_shaft_options.json")))
    tele = next(w for w in so["walls"] if w["wall_mm"] == 1.2)
    rows = []
    for mk, m in MECH.items():
        n_fold = len(m["hinges"]); n_fibre_hinges = n_fold + 1                                   # + the chassis hinge
        for pk, (sh, af, inn) in PROFILES.items():
            if not m["fold"] and pk != "square31": continue
            if m["fold"]:
                pr = profile(sh, af, 1.2, inn); sag = cantilever(pr, m["hinges"], P); sag_rigid = cantilever(pr, [], P)
                hinge_part = sag - sag_rigid; k_need = (K_HINGE * hinge_part / (tele["tip_sag_mm"] - sag_rigid)) if tele["tip_sag_mm"] > sag_rigid else None
                mass = pr["g_per_mm"] * L_SHAFT + n_fold * M_HINGE_G
                segs = np.diff([0.0] + sorted(m["hinges"]) + [L_SHAFT]); collapsed = float(max(segs)) + KNUCKLE_MM * n_fold; stack = (n_fold + 1) * af
            else:
                sag_rigid, k_need = None, None
                pr = dict(chambers=1); sag = tele["tip_sag_mm"]; mass = tele["tubes_g"]; collapsed = COLLAPSED_TELE; stack = 31.0
            loss = POF["db_per_m"] * 1.6 + 2 * CONN_DB + WRAP_DB * n_fibre_hinges
            fibre_ok = m["fold"]
            r = dict(mechanism=mk, profile=pk, hinges_s_mm=m["hinges"], n_fibre_hinges=n_fibre_hinges if m["fold"] else None, tubes_and_hinges_g=round(mass), tip_sag_mm=round(sag, 2), tip_sag_rigid_latch_mm=None if sag_rigid is None else round(sag_rigid, 2),
                     hinge_k_to_match_telescope_Nm_per_rad=None if k_need is None else round(k_need / 1e3),
                     collapsed_mm=round(collapsed), folded_stack_mm=round(stack, 1), chambers=pr["chambers"],
                     fibre=dict(fits=fibre_ok, bend_r_mm=POF["r_rep"] if fibre_ok else 8.2, takeup_mm=round(math.pi * POF["r_rep"] * n_fibre_hinges, 1) if fibre_ok else None,
                                link_loss_dB=round(loss, 2) if fibre_ok else None, margin_dB=round(BUDGET_DB - loss, 2) if fibre_ok else None,
                                cycle_life_years_at_2_folds_per_day=round(POF["cycles"] / (2 * 365), 1) if fibre_ok else None),
                     flex_clock_spring_extra_m=round(n_fibre_hinges * 2 * math.pi * 0.017 * 2, 3) if m["fold"] else 0.0,
                     metal_free_hinges=[s for s in m["hinges"] if s < ECHO_S_MM], tele_ref=dict(tubes_g=tele["tubes_g"], sag_mm=tele["tip_sag_mm"], collapsed_mm=COLLAPSED_TELE))
            r["rule_rows"] = [dict(rule="POF bend radius available vs 15 mm repeated", value=r["fibre"]["bend_r_mm"], limit=15.0, sense=">=", ok=r["fibre"]["bend_r_mm"] >= 15.0),
                              dict(rule="tip sag vs today's telescope", value=r["tip_sag_mm"], limit=tele["tip_sag_mm"], sense="<=", ok=r["tip_sag_mm"] <= tele["tip_sag_mm"]),
                              dict(rule="collapsed length vs today's 430 mm", value=r["collapsed_mm"], limit=COLLAPSED_TELE, sense="<=", ok=r["collapsed_mm"] <= COLLAPSED_TELE)]
            if fibre_ok: r["rule_rows"].append(dict(rule="optical link margin vs 3 dB", value=r["fibre"]["margin_dB"], limit=MARGIN_DB, sense=">=", ok=r["fibre"]["margin_dB"] >= MARGIN_DB))
            rows.append(r)
    res = dict(status="MODELED options study (owner 2026-10-31): hinge stiffness, hinge mass, connector and wrap losses ASSUMED; nothing adopted", rows=rows,
               notes=["a fold lets every segment keep a full internal structure (hub, separators, central bore): nothing slides inside it",
                      "each fold is one more latch to set and one more joint to wear; the telescope stays adjustable in length, a fixed shaft does not (a length adjuster would be a short telescope at the handle, below the last fibre hinge)",
                      "the fibre slides in a PTFE conduit; take-up for all hinges is stored once at the chassis"])
    json.dump(res, open(os.path.join(OUT, "rf2_fold_options.json"), "w"), indent=1, default=float)
    for r in rows: print(r["mechanism"][:34].ljust(34), r["profile"].ljust(14), r["tubes_and_hinges_g"], r["tip_sag_mm"], r["tip_sag_rigid_latch_mm"], r["hinge_k_to_match_telescope_Nm_per_rad"], r["collapsed_mm"], r["fibre"]["margin_dB"], [x["ok"] for x in r["rule_rows"]])
    return res

if __name__ == "__main__":
    main(); sys.exit(0)
