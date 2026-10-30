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
fig, axs = plt.subplots(2, 1, figsize=(15, 6.5), gridspec_kw=dict(height_ratios=[1, 1]))
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
axs[1].set_title("zoom: coil channel with combs, TXJ, MP1 (HV sector)", fontsize=8)
fig.savefig(os.path.join(H.OUT, "rf2_head_section.png"), dpi=150, bbox_inches="tight"); print("written")
