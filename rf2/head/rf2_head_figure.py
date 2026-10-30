#!/usr/bin/env python3
"""RF2 head v1 layout figure: plan (top) and a radial section through the heel (178 deg) and the toe (0 deg), drawn from rf2_head.SPEC.
usage: python3 rf2/head/rf2_head_figure.py"""
import os, sys, math
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Wedge
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_head as H
S = H.SPEC; fig, (a, b) = plt.subplots(1, 2, figsize=(14, 6.6), gridspec_kw=dict(width_ratios=[1, 1.25]))
R = S["envelope"]["R"]
a.add_patch(Circle((0, 0), R, fc="#f4f4f4", ec="#333", lw=1.2)); a.add_patch(Circle((0, 0), S["shell"]["wall_r"][0], fc="none", ec="#999", lw=0.6))
for r in S["coil"]["columns_r"]: a.add_patch(Circle((0, 0), r, fc="none", ec="#b8620f", lw=1.6))
a.add_patch(Circle((0, 0), S["channel"]["inner_wall_r"][1], fc="none", ec="#555", lw=0.8, ls="--"))
w = S["walls"]
a.add_patch(Wedge((0, 0), 108, *S["sectors"]["hv"], fc="#f6d5d0", ec="none", alpha=0.7)); a.add_patch(Wedge((0, 0), 108, *S["sectors"]["analog"], fc="#d5e6f6", ec="none", alpha=0.7))
for d in w["deg"]:
    t = math.radians(d); a.plot([w["r"][0] * math.cos(t), w["r"][1] * math.cos(t)], [w["r"][0] * math.sin(t), w["r"][1] * math.sin(t)], color="#333", lw=2)
a.add_patch(Circle((0, 0), 40.5, fc="none", ec="#2e7d32", lw=1.0, ls=":")); a.text(0, -46, "CB1D tower", ha="center", fontsize=7)
for d in S["stack_pins"]["holes_deg"]:
    p = H.pol(S["stack_pins"]["r"], d); a.add_patch(Circle(p, 2.2, fc="#333" if d in S["stack_pins"]["deg"] else "#e9a800", ec="#333", zorder=5))
g = S["gland"]; a.add_patch(Circle(g["c"], g["d"] / 2, fc="#ddd", ec="#333", zorder=5)); a.text(g["c"][0] + 2, g["c"][1] - 12, "gland", ha="center", fontsize=7)
for k, v in S["boards_inner"].items():
    if v["kind"] == "disc": a.add_patch(Circle(v["c"], v["r"], fc="#ffffff", ec="#1f5f8f" if k.startswith("AB") else "#2e7d32", lw=1.4)); a.text(*v["c"], k, ha="center", va="center", fontsize=8)
    elif v["kind"] == "box": a.add_patch(Rectangle((v["c"][0] - v["size"][0] / 2, v["c"][1] - v["size"][1] / 2), *v["size"], fc="#fff", ec="#b03a2e", lw=1.4)); a.text(*v["c"], k, ha="center", va="center", fontsize=7)
for p in H.led_positions(): a.add_patch(Circle(p, 1.5, fc="#f2c200", ec="none"))
t = math.radians(178); a.annotate("heel 178 deg: shaft, coil leads, TX cable", (R * math.cos(t), R * math.sin(t)), (-118, -112), fontsize=7.5, arrowprops=dict(arrowstyle="-", lw=0.6))
a.text(-120, -150, "blue: analog sector (gel)\nred: HV sector (epoxy)\ngrey: digital / power (syntactic)\norange: rim mono, 26 turns\nyellow: LED windows; black dots: stack pins;\nyellow dot: shield ground pass-through", fontsize=7)
a.set_xlim(-125, 125); a.set_ylim(-160, 125); a.set_aspect("equal"); a.axis("off"); a.set_title("RF2 head v1, plan (D233, MODELED layout)", fontsize=10, loc="left")
# section: x = radius, y = z; heel side negative
def rect(x0, x1, z0, z1, fc, ec="#333", lw=0.6, lab=None):
    b.add_patch(Rectangle((x0, z0), x1 - x0, z1 - z0, fc=fc, ec=ec, lw=lw))
    if lab: b.text((x0 + x1) / 2, (z0 + z1) / 2, lab, ha="center", va="center", fontsize=6.5)
sh = S["shell"]
rect(-R, R, 0, sh["skid_t"], "#e0e0e0", lab="skid 1.2"); rect(-R, R, *sh["lid_z"], "#e0e0e0", lab="lid 1.5 + LED windows")
for side in (-1, 1):
    rect(side * sh["wall_r"][0], side * sh["wall_r"][1], 0, sh["wall_z"][1], "#e0e0e0")
    ch = S["channel"]; rect(side * ch["inner_wall_r"][0], side * ch["inner_wall_r"][1], *ch["z"], "#cfcfcf")
    for j in range(S["coil"]["turns"]):
        r = S["coil"]["columns_r"][j % 3]; z = S["coil"]["row0_z"] + (j // 3) * S["coil"]["pitch"]; b.add_patch(Circle((side * r, z), 0.6, fc="#b8620f", ec="none"))
for k, c in (("SH1", "#e9c46a"), ("QA", "#8fb8de"), ("QB", "#6a9bc3")):
    bz = S["boards"][k]["z"]; rect(-114, 114, *bz, c, lab=k + (" split-ring shield" if k == "SH1" else " quadrupole board"))
I = S["boards_inner"]; zz = lambda v: (v["z"][0] - v["below"], v["z"][1] + v["above"])
rect(-39, 39, *zz(I["CB1D"]), "#d9eed9", lab="CB1D section (MCU, buck) on the tower")
rect(62, 102, *zz(I["AB1B"]), "#d5e6f6", lab="AB1A/B in cradles")
rect(-89.0, -63.0, *zz(I["MP1"]), "#f6d5d0", lab="MP1 (HV in)"); rect(-104, -95, *zz(I["TXJ"]), "#f6d5d0", lab="TXJ")
rect(-75, -15, *zz(I["LED"]), "#fff2b3", lab="LED ring"); rect(15, 75, *zz(I["LED"]), "#fff2b3", lab="LED ring")
rect(-40.5, -39.3, 3.8, I["CB1D"]["z"][1] + 0.9, "#9e9e9e"); rect(39.3, 40.5, 3.8, I["CB1D"]["z"][1] + 0.9, "#9e9e9e")
b.set_xlim(-122, 122); b.set_ylim(-1, 27); b.set_xlabel("radius, mm (heel side negative)"); b.set_ylabel("z, mm"); b.set_title("radial section (heel left, toe right); vertical scale x 4", fontsize=10, loc="left")
b.set_aspect(4)
plt.tight_layout(); plt.savefig(os.path.join(H.OUT, "rf2_head_layout.png"), dpi=140); print("out/rf2_head_layout.png")
