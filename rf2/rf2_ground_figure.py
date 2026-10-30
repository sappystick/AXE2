#!/usr/bin/env python3
"""RF2 ground figure: modeled 1 g depth vs ground severity per balance method (rf2_ground.json), plus exponent tracking. usage: python3 rf2/rf2_ground_figure.py"""
import os, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(os.path.join(H, "results", "rf2_ground.json")))
lv = list(R["depth_mm"].keys()); fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[2, 1]))
sty = {"D1": ("#bbbbbb", "--"), "D2": ("#6aa0c8", "-"), "D3": ("#2f6f9f", "-"), "D4": ("#d08c3c", "--"), "D5": ("#6aa0c8", ":"), "D6": ("#2f6f9f", ":"), "D7": ("#7a5aa6", "-."), "SD": ("#b03a2e", "-")}
for name in R["depth_mm"][lv[0]]:
    c, ls = sty[name[:2]]; ax[0].plot(range(len(lv)), [R["depth_mm"][g][name]["1.0 g"] for g in lv], color=c, ls=ls, marker="o", ms=3, label=name)
ax[0].set_xticks(range(len(lv))); ax[0].set_xticklabels(lv, fontsize=8); ax[0].set_ylabel("1 g depth, mm (MODELED)"); ax[0].legend(fontsize=6.5, loc="upper right")
ax[0].set_title("ground balance methods vs viscous-ground severity (ASSUMED ground)", fontsize=9, loc="left")
tr = R["exponent_tracking_severe"]; ks = list(tr.keys())
for name, c in (("D3 mono, multi-period (PWM flat-top) balance", "#2f6f9f"), ("SDC 2300-class 8 in mono, multi-period balance", "#b03a2e")):
    ax[1].plot([float(k.split()[-1]) for k in ks], [tr[k][name]["1.0 g"] for k in ks], marker="o", color=c, label=name.split(",")[0])
ax[1].invert_xaxis(); ax[1].set_xlabel("ground-exponent spread the balance must cover", fontsize=8); ax[1].set_title("severe ground: exponent tracking", fontsize=9, loc="left"); ax[1].legend(fontsize=7)
plt.tight_layout(); plt.savefig(os.path.join(H, "results", "rf2_ground.png"), dpi=130); print("results/rf2_ground.png")
