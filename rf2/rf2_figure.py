#!/usr/bin/env python3
"""RF2 figure: modeled noise-limited depth per transmit formation (same energy per pulse), plus the quadrant X mode and the receiver comparison from
sim_head1 (figure-8 vs RX-Q, built coil). Reads results/rf2_coil_search.json and data/results/sim_head1.json. usage: python3 rf2/rf2_figure.py"""
import os, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(os.path.join(H, "results", "rf2_coil_search.json")))
S = json.load(open(os.path.join(H, "..", "data", "reference", "sim_head1.json")))["gold_nugget_depth_noise_limited"]
lab, d1, d01 = [], [], []
short = lambda n: n.replace("1in window ", "1 in: ").replace(" (quadrant-ready if 4)", "").replace("z 3.2-21.9, ", "").replace(" + ideal ferrite plane (BOUND)", " + ferrite (bound)").replace("BASELINE built coil (6 layers parallel, 25.6 mm tall: does not fit 1 in)", "built coil, 25.6 mm tall")
for r in R["rows"]: lab.append(short(r["name"])); d1.append(r["depth_mm"]["1.0 g"]); d01.append(r["depth_mm"]["0.1 g"])
x = R["signature"]["quadrant_X_mode_depth_mm"]; lab.append("1 in: quadrant X mode (shape probe)"); d1.append(x["1.0 g"]); d01.append(x["0.1 g"])
c = "100 nF C0G/film | X8 | "; lab.append("built coil, figure-8 receiver (sim_head1)"); d1.append(S[c + "1.0 g"]["detect_depth_mm"]); d01.append(S[c + "0.1 g"]["detect_depth_mm"])
fig, ax = plt.subplots(figsize=(10, 5.2)); y = range(len(lab))
ax.barh([i + 0.2 for i in y], d1, 0.4, color="#2f6f9f", label="1 g gold sphere"); ax.barh([i - 0.2 for i in y], d01, 0.4, color="#9fc3df", label="0.1 g")
for i, (a, b) in enumerate(zip(d1, d01)): ax.text(a + 1, i + 0.2, str(a), va="center", fontsize=8); ax.text(b + 1, i - 0.2, str(b), va="center", fontsize=8)
ax.set_yticks(list(y)); ax.set_yticklabels(lab, fontsize=8); ax.invert_yaxis(); ax.set_xlabel("noise-limited detection depth, mm (MODELED, no ground)")
ax.set_title("RF2: transmit formation inside a 1 in head, same energy per pulse (10.8 mJ); receiver RX-Q unless noted", fontsize=9, loc="left"); ax.legend(fontsize=8, loc="lower right"); ax.set_xlim(0, 185)
plt.tight_layout(); plt.savefig(os.path.join(H, "results", "rf2_coil_search.png"), dpi=130); print("results/rf2_coil_search.png")
