#!/usr/bin/env python3
"""Cross-section of a head variant through the heel axis (the x-z plane, y = 0): every printed part, board envelope, the litz and the combs, cut from
the written STLs (trimesh). usage: python3 rf2/head/rf2_head_section.py [--variant=B] -> out[_B]/rf2_head_section.png"""
import os, sys, json
import numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_head as H
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
COL = dict(SHELL_LOWER="#9e9e9e", LID="#b3e5fc", COIL_CHANNEL="#8d6e63", COIL_COMBS="#5d4037", LITZ="#e67e22", BAY_WALLS="#7e57c2", SHIELD_COAT="#212121",
           BOARD_SH1="#c9a227", BOARD_QA="#2e7d32", BOARD_QB="#43a047")
fig = plt.figure(figsize=(15, 13)); gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 3.2]); axs = [fig.add_subplot(gs[0]), fig.add_subplot(gs[1])]; axp = fig.add_subplot(gs[2])
for ax, xlim in zip(axs, ((-118, 118), (-118, -40))):
    for f in sorted(os.listdir(H.OUT)):
        if not (f.startswith("RF2_") and f.endswith(".stl")) or "REF3" in f: continue
        k = f[4:-4]; m = trimesh.load(os.path.join(H.OUT, f)); s = m.section(plane_origin=[0, 0.0, 0], plane_normal=[0, 1, 0])
        if s is None: continue
        c = COL.get(k, "#26a69a" if k.startswith("ENV_") else "#90a4ae")
        for e in s.discrete:
            ax.fill(e[:, 0], e[:, 2], color=c, alpha=0.35 if k.startswith("ENV_") else 0.85, lw=0.3, ec="k")
        if k.startswith("ENV_") or k in ("LITZ", "LID"):
            b = s.bounds
            if b[0][0] < xlim[1] and b[1][0] > xlim[0]: ax.text(max(b[0][0], xlim[0]) + 0.5, b[1][2] + 0.2, k.replace("ENV_", ""), fontsize=6)
    ax.set_xlim(*xlim); ax.set_ylim(-0.5, H.SPEC["envelope"]["H"] + 1.5); ax.set_aspect("equal"); ax.set_xlabel("x (mm), heel at -x"); ax.set_ylabel("z (mm)")
axs[0].set_title(f"RF2 head variant {H.VARIANT}: section through the heel axis (y = 0), H {H.SPEC['envelope']['H']} mm (MODELED geometry)", fontsize=9)
axs[1].set_title("zoom: heel side (coil channel, HV sector)", fontsize=8)
for f in sorted(os.listdir(H.OUT)):                                                         # plan view: horizontal cut at mid board height
    if not (f.startswith("RF2_") and f.endswith(".stl")) or "REF3" in f or f[4:-4] in ("LID", "BOARD_SH1", "BOARD_QA", "BOARD_QB", "ENV_LED"): continue
    k = f[4:-4]; m = trimesh.load(os.path.join(H.OUT, f)); s = m.section(plane_origin=[0, 0, 8.0], plane_normal=[0, 0, 1])
    if s is None: continue
    c = COL.get(k, ("#c62828" if H.SPEC["boards_inner"].get(k[4:], {}).get("hv") else "#26a69a") if k.startswith("ENV_") else "#90a4ae")
    for e in s.discrete:
        if k.startswith("ENV_"): axp.fill(e[:, 0], e[:, 1], color=c, alpha=0.7, lw=0.3, ec="k")
        else: axp.plot(e[:, 0], e[:, 1], color=COL.get(k, "#546e7a"), lw=0.6)                     # printed parts as outlines (rings would fill the disc)
    if k.startswith("ENV_"):
        v = H.SPEC["boards_inner"][k[4:]]
        if v.get("kind") == "fin":
            import math; r = 70.0; axp.text(r * math.cos(math.radians(v["deg"])), r * math.sin(math.radians(v["deg"])), k[8:], fontsize=7, ha="center", rotation=v["deg"] if abs(v["deg"] - 180) > 90 else v["deg"] - 180)
for d in H.SPEC["walls"]["deg"]:
    import math; axp.text(108 * math.cos(math.radians(d)), 108 * math.sin(math.radians(d)), f"{d:.0f}", fontsize=6, color="#7e57c2", ha="center")
axp.set_aspect("equal"); axp.set_xlim(-120, 120); axp.set_ylim(-120, 120); axp.set_title(f"plan view, cut at z 8.0 (red = HV boards, teal = LV boards, purple numbers = sector walls)", fontsize=8)
fig.savefig(os.path.join(H.OUT, "rf2_head_section.png"), dpi=150, bbox_inches="tight"); print("written")
