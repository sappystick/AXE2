#!/usr/bin/env python3
"""RF2 step 2 figure: modeled noise-limited depth (1 / 5 / 20 g) per receive architecture in the 1-inch head vs an SDC 2300-class 8 in mono at equal
electronics, with each channel's uniform-ground coupling. Reads results/rf2_receiver_combo.json. usage: python3 rf2/rf2_combo_figure.py"""
import os, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(os.path.join(H, "results", "rf2_receiver_combo.json")))
rx, mq, mo, g = R["receivers"], R["mono_plus_quad"], R["mono"], R["ground_coupling_rel"]
rows = [("QUAD only (built receiver)", rx["QUAD (built quadrupole)"]["depth_mm"], "0 (symmetric)"),
        ("figure-8 only", rx["X8 (figure-8)"]["depth_mm"], "0 (symmetric)"),
        ("concentric nulled (CN)", rx["CN (concentric nulled)"]["depth_mm"], "1.0"),
        ("PROPOSED: rim mono + QUAD, mono channel (15 us gate)", mq["mono_depth_mm_by_gate"]["15 us"], f"{mo['mono, our diameter']['ground_coupling_rel_CN']['h 30 mm']}"),
        ("  same, QUAD channel (bearing / pinpoint)", mq["quad_depth_mm"], "0 (symmetric)"),
        ("SDC 2300-class 8 in mono, equal electronics (10 us)", mo["SDC 2300-class 8 in mono (ASSUMED internals)"]["depth_mm_by_gate"]["10 us"], f"{mo['SDC 2300-class 8 in mono (ASSUMED internals)']['ground_coupling_rel_CN']['h 30 mm']}")]
fig, ax = plt.subplots(figsize=(10.5, 4.8)); cols = {"1.0 g": "#2f6f9f", "5.0 g": "#6aa0c8", "20.0 g": "#b5d0e6"}
for i, (lab, d, gr) in enumerate(rows):
    for j, (k, c) in enumerate(cols.items()):
        v = d[k]; ax.barh(i + (j - 1) * 0.26, v, 0.26, color=c, label=k if i == 0 else None); ax.text(v + 3, i + (j - 1) * 0.26, (">= " if v >= 500 else "") + str(v), va="center", fontsize=7)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([f"{r[0]}\nuniform-ground coupling {r[2]}" for r in rows], fontsize=7.5); ax.invert_yaxis(); ax.set_xlim(0, 560)
ax.set_xlabel("noise-limited depth, mm (MODELED; gold spheres; ground not subtracted; 500 = model limit)", fontsize=8)
ax.set_title("RF2 receive architectures, 1 in head, 10.8 mJ per pulse, vs SDC 2300-class mono (equal electronics)", fontsize=9, loc="left")
ax.legend(fontsize=8, loc="upper right"); plt.tight_layout(); plt.savefig(os.path.join(H, "results", "rf2_receiver_combo.png"), dpi=130); print("results/rf2_receiver_combo.png")
