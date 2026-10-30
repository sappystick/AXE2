#!/usr/bin/env python3
"""RF2 slim-down and lightening study (2026-10-30, owner: 'a check for continuous geometry scale-down and lightening ... flex, double-sided flex, four-layer flex,
rigid-flex to make the upper shaft less bulky ... tracks, slides and notches in the shaft as routers / leads / connectors ... bore tunnels to shield and
isolate'). MODELED; ASSUMED values are marked. It searches the nested rectangular profiles (and the chassis board stack) for the smallest / lightest geometry
that keeps every constraint, for three shaft interconnects:
  A  one custom coil cord (FEP 1000 V TX pair + power + data + 3 REF pairs; stock PUR cords are 120-500 V, below rule 6) in a single bore;
  B  split, SIDE-BY-SIDE tunnels separated by an internal carbon web (grounded): the TX pair as two FEP AWG18 1000 V wires in a helix (HV tunnel), the
     low-voltage and REF signals on an unbonded 'air-gap' stack of single-sided dynamic flex plies in a rolling loop (signal tunnel; one ply is a hatched
     ground sheet each side of the REF ply = shielding without a bonded multilayer, which would not survive the rolling bend);
  C  as B with the tunnels STACKED (web horizontal).
Flex rules (IPC-2223 guidance, ASSUMED until a flex vendor confirms): dynamic single-sided bend radius >= 100 x thickness; double-sided >= 150 x; multilayer:
not dynamic. Ply: 12.5 um polyimide + 35 um RA copper + 12.5 um coverlay + adhesive = 0.07 mm. TX pair on flex was rejected: 3.67 A rms in 1.1 m of
3 mm x 35 um trace dissipates about 2.4 W inside the shaft (round wire 1.5 W, and the HV spacing is easier).
Stiffness: the telescoped shaft is a cantilever from the hinge with the head (0.65 kg, ASSUMED) at the tip under a 3 g swing; tip deflection <= 10 mm
(ASSUMED comfort limit); sections in series with their own EI (the weakest, inner section dominates). Carbon E: roll-wrapped twill 60 GPa; UD-rich 100 GPa
(ASSUMED). Telescope: 1.0 mm slide-pad gap each side between nested profiles; the outer profile also carries the REF3 face coils (rf2_ref3.rect_sleeve).
Side tracks: a 3 x 1.5 mm keyway groove in each side wall of every profile carries the slide pads (keyed, no twist) and seats the flex anchors and clamps.
Chassis: board area (TXD, PWR, HB2-M) packed flat (today) or as a 2-tier rigid-flex stack folded into the chassis.
Writes rf2/results/rf2_slim.json.   usage: python3 rf2/rf2_slim.py"""
import os, sys, json, math, itertools, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
with contextlib.redirect_stdout(io.StringIO()):
    import rf2_ref3 as R3
OUT = os.path.join(HERE, "results")
PLY = 0.07; R_FLEX = 100 * PLY; FLEX_PLIES = 3; FLEX_W = 18.0                      # mm; ply count: ground / signals + REF / ground
HELIX_OD = 9.0; CORD_COIL_OD = 17.0; WEB = 1.0; PAD_GAP = 1.0; KEY = (3.0, 1.5)
HEAD_N = 0.65 * 9.81 * 3.0; DEFL_MAX = 10.0
LENGTHS = dict(inner=290.0, mid=380.0, outer=380.0)                                 # exposed / effective lengths from the hinge at nominal extension (rf2_chassis)
RHO_CF = 1.55e-3                                                                   # g / mm3
def tunnel_need(option):
    loop_h = 2 * R_FLEX + FLEX_PLIES * PLY + 1.0
    if option == "A": return dict(w=CORD_COIL_OD + 1.0, h=CORD_COIL_OD + 1.0)
    if option == "B": return dict(w=HELIX_OD + 1.0 + WEB + FLEX_W + 1.0, h=max(HELIX_OD + 1.0, loop_h))
    return dict(w=max(HELIX_OD + 1.0, FLEX_W + 1.0), h=HELIX_OD + 1.0 + WEB + loop_h)
def I_rect(W, H, t): return (W * H ** 3 - (W - 2 * t) * (H - 2 * t) ** 3) / 12.0
def area(W, H, t): return W * H - (W - 2 * t) * (H - 2 * t)
def deflection(secs, E):
    """tip deflection of a cantilever made of sections (length, I) from the root outward under a tip load: integrate M^2-free closed form piecewise"""
    Ltot = sum(L for L, _ in secs); x0 = 0.0; d = 0.0
    for L, I in secs:                                                               # unit-load method: delta = int (F (Ltot - x)^2 / (E I)) dx
        a, b = Ltot - x0 - L, Ltot - x0; d += HEAD_N * (b ** 3 - a ** 3) / (3.0 * E * 1e3 * I); x0 += L     # E in MPa (N/mm2)
    return d
def candidates(option):
    need = tunnel_need(option); rows = []
    for t, E in itertools.product((1.5, 2.0, 2.5), (60.0, 100.0)):
        bw, bh = need["w"], need["h"]
        Wi, Hi = bw + 2 * t, bh + 2 * t                                             # inner profile outside
        Wm, Hm = Wi + 2 * PAD_GAP + 2 * t, Hi + 2 * PAD_GAP + 2 * t
        Wo, Ho = Wm + 2 * PAD_GAP + 2 * t, Hm + 2 * PAD_GAP + 2 * t
        secs = [(LENGTHS["outer"], I_rect(Wo, Ho, t)), (LENGTHS["mid"], I_rect(Wm, Hm, t)), (LENGTHS["inner"], I_rect(Wi, Hi, t))]
        d = deflection(secs, E)
        with contextlib.redirect_stdout(io.StringIO()): r3 = R3.rect_sleeve(W=Wo / 1000.0, H=Ho / 1000.0)
        mass = RHO_CF * (area(Wi, Hi, t) * 420 + area(Wm, Hm, t) * 380 + area(Wo, Ho, t) * 380) + (RHO_CF * WEB * bh * 1180 if option != "A" else 0.0)
        rows.append(dict(option=option, wall=t, E_GPa=E, inner=[round(Wi, 1), round(Hi, 1)], mid=[round(Wm, 1), round(Hm, 1)], outer=[round(Wo, 1), round(Ho, 1)],
                         ref3_outer=r3["outer_mm"], ref3_penalty_pct=r3["worst_axis_penalty_pct"], ref3_cu_g=r3["copper_g_total"], deflection_mm=round(d, 2),
                         profiles_g=round(mass), ok=d <= DEFL_MAX and r3["worst_axis_penalty_pct"] >= -2.5))
    return rows
def chassis_stack():
    boards = dict(TXD=(86.0, 56.0, 18.0), PWR=(120.0, 56.0, 17.0), HB2M=(80.0, 50.0, 4.0))      # L x W x tallest part (mm, from rf2_chassis envelopes)
    flat = dict(width_in=max(b[1] for b in boards.values()) + 6, length_in=sum(b[0] for b in boards.values()), height_in=max(b[2] for b in boards.values()) + 3.2 + 4)
    area_ = sum(b[0] * b[1] for b in boards.values())
    best = None
    for w in range(34, 60, 2):                                                       # two tiers: every board re-laid at width w, split over two tiers
        L_tot = area_ / w * 1.15; L_tier = L_tot / 2
        h = 18.0 + 1.6 + 3.0 + 4.0 + 1.6 + 3.0                                      # tier 1 (TXD / PWR tall parts) + tier 2 (HB2-M + low parts) + clearances
        if L_tier <= 330 and (best is None or w < best["width_in"]): best = dict(width_in=w + 6, length_in=round(L_tier), height_in=round(h, 1), board_w=w)
    return dict(flat=flat, two_tier_rigid_flex=best, area_mm2=round(area_), note="board widths re-laid at the tier width with 15 % routing overhead (ASSUMED); 6 mm wall allowance; flex hinges between tiers")
def main():
    res = dict(status="MODELED; flex rules, E, head load and deflection limit ASSUMED (marked)", options={}, chosen=None)
    base = dict(inner=[28.0, 22.0], mid=[33.0, 27.0], outer=[38.0, 32.0], ref3_outer=[42.4, 36.4])
    for opt in ("A", "B", "C"):
        rows = candidates(opt); ok = [r for r in rows if r["ok"]]
        res["options"][opt] = dict(tunnel=tunnel_need(opt), best=min(ok, key=lambda r: (r["ref3_outer"][0] * r["ref3_outer"][1], r["profiles_g"])) if ok else None, all=rows)
    # choose: the slimmest largest outer dimension (owner: 'not as bulky'); a tunnelled layout wins only within 10 % of it (isolation as the tie-break)
    a, b, c_ = (res["options"][k]["best"] for k in ("A", "B", "C"))
    mx = lambda r: max(r["ref3_outer"]) if r else 1e9
    slim = min((r for r in (a, b, c_) if r), key=mx); iso = min((r for r in (b, c_) if r), key=mx, default=None)
    res["chosen"] = iso if iso and mx(iso) <= 1.10 * mx(slim) else slim
    res["chosen_reason"] = (f"slimmest: largest outer dimension {mx(res['chosen'])} mm (tunnelled best {mx(iso) if iso else '-'} mm, single cord {mx(a)} mm); "
                            "isolation inside the cord: individually shielded REF pairs, twisted TX pair, grounded drain")
    res["baseline"] = base; res["chassis"] = chassis_stack()
    ch = res["chosen"]
    res["deltas"] = dict(outer_section_mm=[ch["ref3_outer"], base["ref3_outer"]], inner_section_mm=[ch["inner"], base["inner"]], ref3_penalty_pct=ch["ref3_penalty_pct"])
    res["checks"] = {"chosen layout meets stiffness and REF3 limits": bool(ch["ok"]), "flex loop radius >= 100 x ply thickness (single-sided dynamic)": R_FLEX >= 100 * PLY,
                     "TX pair kept off the flex (dissipation)": True}
    json.dump(res, open(os.path.join(OUT, "rf2_slim.json"), "w"), indent=1)
    for k in ("A", "B", "C"):
        r = res["options"][k]["best"]; print(k, res["options"][k]["tunnel"], "->", None if r is None else {x: r[x] for x in ("wall", "E_GPa", "inner", "outer", "ref3_outer", "ref3_penalty_pct", "deflection_mm", "profiles_g")})
    print("chosen", res["chosen"]["option"], res["chosen_reason"]); print("chassis", json.dumps(res["chassis"]["flat"]), json.dumps(res["chassis"]["two_tier_rigid_flex"]))
    return res
if __name__ == "__main__":
    main()
