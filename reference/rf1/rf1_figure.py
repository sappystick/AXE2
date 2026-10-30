#!/usr/bin/env python3
"""RF1 phase 1 figure: head side section (hub frame, y = toward the 90 deg spine duct, z up) with the layer bands of DESIGN_STATE, the rigid sections and the flex hinges
of concept C. Reads results/rf1_phase1.json; writes results/rf1_head_concept.png. Drawing, not a mesh: the fit numbers are in the JSON."""
import os, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
H = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(os.path.join(H, "results", "rf1_phase1.json")))
BLUE, ORANGE, GREEN, GOLD, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#1f2328", "#8a8f98"
fig, ax = plt.subplots(figsize=(10, 6.2), dpi=150)
bands = [(0, 3.2, "L0 base"), (3.2, 9.0, "L1 gallery (RX leads)"), (9.8, 20.0, "L2 analog cell"), (20.0, 21.9, "L3 septum + cloth"),
         (21.9, 27.0, "L4 absorber"), (27.0, 38.8, "L5 controller"), (39.2, 40.8, "L6 display"), (41.3, 44.5, "L7 roof (removable)"), (44.5, 47.1, "L8 cap + HTA")]
for z0, z1, t in bands:
    ax.add_patch(Rectangle((-46, z0), 92, z1 - z0, color="#f3f4f6" if bands.index((z0, z1, t)) % 2 else "#e9ebef", lw=0, zorder=0))
    ax.text(-45, (z0 + z1) / 2, t, va="center", fontsize=7, color=MUTED)
def board(x0, x1, z, t, lab, c):
    ax.add_patch(Rectangle((x0, z), x1 - x0, t, color=c, zorder=3)); ax.text((x0 + x1) / 2, z + t + 0.5, lab, ha="center", fontsize=8, color=INK, zorder=5)
board(-44, 40, 1.6, 1.6, "SB1R-QA / QB (unchanged coils, D228)", MUTED)
board(-12, 4, 11.1, 1.6, "AB1A / AB1B rigid (6L)", BLUE)
board(-39, 39, 27.0, 1.6, "CB1D rigid (6L)", BLUE)
board(-39, 39, 39.2, 0.8, "LB1 rigid", BLUE)
board(-30, 30, 45.0, 1.2, "HTA rigid / tail", BLUE)
duct = 42.0
ax.add_patch(Rectangle((duct - 2, 3.2), 4, 41.3, fill=False, ls="--", ec=GOLD, lw=1.2, zorder=2)); ax.text(duct, 45.0, "90° duct", ha="center", fontsize=7, color=GOLD, rotation=90, va="bottom")
def flex(pts, c=ORANGE, lab=None, lx=None):
    xs, zs = zip(*pts); ax.plot(xs, zs, color=c, lw=2.4, zorder=4, solid_capstyle="round")
    if lab: ax.text(lx[0], lx[1], lab, fontsize=7.5, color=c, zorder=6)
flex([(4, 11.9), (duct, 12.6), (duct, 27.8), (39, 27.8)], lab="AB1 → CB1D hinges (2 x 12 signals,\nhatched GND, 0.2 mm, through the duct)", lx=(6, 15.5))
flex([(39, 28.4), (duct - 0.5, 30), (duct - 0.5, 39.6), (39, 39.6)], lab="CB1D → LB1 S-fold", lx=(18, 34.5))
flex([(39, 40.0), (duct + 0.6, 41.5), (duct + 0.6, 45.6), (30, 45.6)], lab="HTA tail (service loop under the roof)", lx=(2, 42.3))
flex([(-20, 3.2), (-16, 6.5), (-6, 11.9)], c=GREEN, lab="SB1R → AB1A soldered flex jumper\n(broadside pair, fixed loop area)", lx=(-40, 7.0))
ax.plot([-44, 40], [3.6, 3.6], color=ORANGE, lw=0.0)
ax.annotate("TX formers, litz and the 460 V taps stay wire (rules 5 / 6)", (-44, -3.2), fontsize=7.5, color=INK, annotation_clip=False)
hb = R["ab1_cb1d_hinges"]; k = "rigid-flex hinge from the board edge (RF1)"; b = "IDC ribbon on the current 1.27 mm headers (baseline)"
txt = (f"mesh fit (link_path_check): baseline ribbon {hb[b]['fails']}/{hb[b]['checks']} FAIL, rigid-flex hinge {hb[k]['fails']}/{hb[k]['checks']} FAIL\n"
       f"headroom under LB1 {hb[b]['height_margin_under_LB1_mm']} → {hb[k]['height_margin_under_LB1_mm']} mm, under the septum {hb[b]['height_margin_under_septum_mm']} → {hb[k]['height_margin_under_septum_mm']} mm\n"
       f"hand joints in the head {R['census']['hand_joints_today']} → {R['census']['concept_C_joints']['total']}; RX lead loop area {R['rx_tail']['wire']['AWG36 pair touching']['loop_area_mm2']}-"
       f"{R['rx_tail']['wire']['AWG36 pair, loose dress 1 mm']['loop_area_mm2']} → {R['rx_tail']['flex_broadside']['loop_area_mm2']} mm² (fixed)")
ax.text(-45, 50.2, txt, fontsize=7.5, color=INK, va="bottom")
ax.set_xlim(-46, 50); ax.set_ylim(-4.5, 56); ax.set_xlabel("y toward the spine duct (mm, hub frame; boards drawn as sections)", fontsize=8); ax.set_ylabel("z (mm)", fontsize=8)
ax.set_title("RF1 concept C: head electronics as one folded rigid-flex (MODELED, side experiment)", fontsize=10, color=INK, loc="left")
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.tick_params(labelsize=7); fig.tight_layout(); fig.savefig(os.path.join(H, "results", "rf1_head_concept.png")); print("written")
