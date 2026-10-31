#!/usr/bin/env python3
"""Variant axes registry for rf2/rf2_variants.py (owner 2026-10-31: a permanent tool that grows over time).

HOW TO EXTEND: add an option to an existing axis, or a new axis, here. Each option has an id (short, unique in its axis), a description, the
source of its numbers, `today: True` on the option the machine uses now (exactly one per axis), and `p`: the parameters the engine reads.
A new KIND of parameter needs a few lines in rf2_variants.evaluate_combo() that turn it into metrics and rule rows; everything else
(enumeration, scoring, Pareto front, champions, history, report) is generic. Keep every number sourced (a study JSON, a datasheet in
data/datasheets/ logged in DATASHEET_LOG, or ASSUMED with the reason)."""

AXES = [
    dict(name="coil", help="TX/RX coil wiring in the 30-slot comb (rf2_lowL_options)", options=[
        dict(id="26x1", desc="26 turns, single strand (today)", source="rf2_head comb", today=True, p=dict(N=26, p=1, tx2=False)),
        dict(id="15x2", desc="15 turns x 2 parallel strands, TX strips doubled on both flex layers", source="rf2_lowL_options", p=dict(N=15, p=2, tx2=True)),
        dict(id="10x3", desc="10 turns x 3 parallel strands, TX strips doubled on both flex layers", source="rf2_lowL_options", p=dict(N=10, p=3, tx2=True))]),
    dict(name="switch", help="TX switch (TXD)", options=[
        dict(id="C3M", desc="Wolfspeed C3M0280090J (today)", source="Wolfspeed Rev 04", today=True, p=dict(sw="C3M0280090J")),
        dict(id="NTBG", desc="onsemi NTBG080N120SC1 (80 mohm, 1200 V, IDM 110 A)", source="onsemi datasheet on file", p=dict(sw="NTBG080N120SC1"))]),
    dict(name="txd", help="TXD position along the shaft (s from the head)", options=[
        dict(id="s857", desc="s 857 mm (today)", source="rf2_system", today=True, p=dict(txd_s=857)),
        dict(id="s400", desc="s 400 mm (shorter TX strips; past the 375 mm echo distance)", source="rf2_system echoes", p=dict(txd_s=400))]),
    dict(name="rx", help="receive path", options=[
        dict(id="mono", desc="rim coil receives (today)", source="-", today=True, p=dict(rx="mono")),
        dict(id="hybrid", desc="rim coil + planar nulled RX on a second channel, SNRs combined", source="rf2_lowL_options.hybrid", p=dict(rx="hybrid"))]),
    dict(name="shaft", help="shaft mechanism and profile (rf2_fold_options)", options=[
        dict(id="tele_sq", desc="telescope, keyed square 31/26/21 (today)", source="rf2_chassis", today=True, p=dict(shaft="telescope square (today)")),
        dict(id="f1_sq31", desc="fold x1 (mid) + chassis hinge, square 31", source="rf2_fold_options", p=dict(shaft="fold x1 square31")),
        dict(id="f1_hex31cu", desc="fold x1, hex 31 with hub + 6 Cu-plated separators", source="rf2_fold_options", p=dict(shaft="fold x1 hex31 hub6_cu")),
        dict(id="fnm_hex31cu", desc="fold at neck + mid + chassis hinge, hex 31 hub6_cu", source="rf2_fold_options", p=dict(shaft="fold neck+mid hex31 hub6_cu")),
        dict(id="f2_sq31", desc="fold x2 (thirds), square 31", source="rf2_fold_options", p=dict(shaft="fold x2 square31")),
        dict(id="f2_hex31cu", desc="fold x2 (thirds), hex 31 hub6_cu", source="rf2_fold_options", p=dict(shaft="fold x2 hex31 hub6_cu"))]),
    dict(name="data", help="digital link head <-> chassis", options=[
        dict(id="cu", desc="copper pairs in the cord flex (today)", source="rf2_cordflex", today=True, p=dict(data="copper")),
        dict(id="pof", desc="3 x POF links (AFBR-1624Z / 2624Z, GH-4001-P)", source="Broadcom, Mitsubishi sheets on file", p=dict(data="POF"))]),
    dict(name="pack", help="battery pack (rf2_pack_options keys)", options=[
        dict(id="C2", desc="7S1P Molicel P45B, 2 rows (today)", source="rf2_pack_options", today=True, p=dict(pack="C2")),
        dict(id="B", desc="7S2P Molicel P30B rail pack", source="rf2_pack_options", p=dict(pack="B")),
        dict(id="D2", desc="7S1P LG M50T, 2 rows", source="rf2_pack_options", p=dict(pack="D2")),
        dict(id="E", desc="7S RC LiPo in a hard shell", source="rf2_pack_options", p=dict(pack="E")),
        dict(id="F", desc="small 7S1P P30B (carry a spare)", source="rf2_pack_options", p=dict(pack="F"))]),
    dict(name="wall", help="carbon tube wall (rf2_shaft_options)", options=[
        dict(id="w1.2", desc="1.2 mm (today)", source="owner 2026-10-30", today=True, p=dict(wall=1.2)),
        dict(id="w1.0", desc="1.0 mm", source="rf2_shaft_options", p=dict(wall=1.0)),
        dict(id="w1.5", desc="1.5 mm", source="rf2_shaft_options", p=dict(wall=1.5))]),
    dict(name="clamp", help="flyback energy handling", options=[
        dict(id="regen", desc="regenerative 460 V clamp, 75 % recovery ASSUMED (today's budget)", source="rf2_continuous", today=True, p=dict(clamp="regen")),
        dict(id="dissip", desc="dissipative TVS / zener clamp", source="rf2_continuous", p=dict(clamp="dissip"))]),
    dict(name="flex_cu", help="cord-flex TX strip copper", options=[
        dict(id="2oz", desc="2 oz (today)", source="rf2_cordflex", today=True, p=dict(oz=2)),
        dict(id="3oz", desc="3 oz TX strips (R x 2/3, narrower; thicker stack)", source="IPC-2221 / rf2_cordflex", p=dict(oz=3))]),
]


# ---------------------------------------------------------------- plugins (multi-agent extension point)
# Every module rf2/variant_plugins/<name>.py that defines AXES (same format as above) and evaluate(ctx, P, m) is loaded automatically.
# Optional prepare(ctx) runs once. evaluate() reads the merged parameters P and the core metrics m (m["_e"] = the electrical model output:
# I_scan, I_boost, L_uH, R_coil, fall_us, W_TX_mm, Tj_switch_boost_C, ...), and may adjust m (first_gate_us, depth_cm, runtime_*_h, P_boost_W,
# mass_delta_g, added_parts) and append rule rows to m["rules"]: dict(rule, value, limit, sense ("<=" / ">="), ok, where, kind ("safety" / "target")).
# Extra metrics go in m["extra"][key]. See rf2/variant_plugins/README.md.
def load_plugins():
    import importlib, pkgutil, os, sys
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "variant_plugins"); mods = []
    if not os.path.isdir(d): return mods
    sys.path.insert(0, os.path.dirname(d))
    for m in sorted(pkgutil.iter_modules([d]), key=lambda x: x.name):
        if m.name.startswith("_"): continue
        mod = importlib.import_module(f"variant_plugins.{m.name}")
        if hasattr(mod, "AXES") and hasattr(mod, "evaluate"): mods.append(mod)
    return mods
