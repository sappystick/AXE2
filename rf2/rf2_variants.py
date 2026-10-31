#!/usr/bin/env python3
"""RF2 variant shuffler (owner 2026-10-31): every combination of the concept-derived options, scored the same way as rf2_select, with every
broken rule listed at its location. Nothing is excluded and nothing is adopted.

Axes (each value is computed by its own model, not guessed):
  coil     26 x 1 (today) | 15 x 2 parallel strands with the TX strips doubled on both flex layers           (rf2_lowL_options: L, R, current, PI gate, depth)
  switch   C3M0280090J (today) | NTBG080N120SC1                                                               (rf2_lowL_options: RDS, IDM, Coss, TJ, runtime)
  TXD      s 857 mm (today) | s 400 mm (shorter TX strips; still past the 375 mm echo distance)               (rf2_system echoes)
  RX       mono rim coil (today) | hybrid: rim coil + planar nulled RX on a second channel                     (rf2_lowL_options.hybrid)
  shaft    telescope square (today) | fold x1 / neck+mid / x2 in square31 or hex31 hub6_cu                       (rf2_fold_options: mass, sag, collapsed, hinges)
  data     copper pairs in the flex (today) | optical POF (AFBR-1624Z / 2624Z, 3 links, +0.41-0.60 W)          (rf2_shaftlink_options, rf2_fold_options link budget)
TX-strip length: telescope 1.355 m x s_TXD / 857 (today's routing incl. the rolling loop); fold (s_TXD + 150 mm) + 0.214 m of clock-spring flex per
hinge below the TXD. Flex width rule: telescope 16 mm (bore less 2); fold: the HV group (2 strips + gap + edges) on one inner face.
Score: rf2_select WEIGHTS; each factor normalised so today's machine scores 1.0 (mass system-level, runtime continuous boost, signal = geometric
mean of the three depth ratios, margin = worst rule ratio saturating at 2, attach = added joints / channels / transceivers, footprint = collapsed
length, verify = penalty for ASSUMED-heavy items). Writes rf2/results/rf2_variants.json, docs/VARIANTS.md.   usage: python3 rf2/rf2_variants.py"""
import os, sys, json, math, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); OUT = os.path.join(HERE, "results"); sys.path[:0] = [HERE, os.path.join(HERE, "head")]
import rf2_lowL_options as LO, rf2_cordflex as CFX
from rf2_select import WEIGHTS, M_SAT, M_SYS
DIG_W = 3 * 0.45 + 2 * 0.3
POF_W, POF_G = 0.60, 1.6 * 4.0 + 6 * 2.0                      # worst-case link power; fibre 1.6 m x 4 g/m + 6 transceivers ~2 g each (ASSUMED)
RX_G = 8.0
AX = dict(coil=["26x1", "15x2 TX2L"], switch=["C3M0280090J", "NTBG080N120SC1"], txd=[857, 400], rx=["mono", "hybrid"],
          shaft=["telescope square (today)", "fold x1 square31", "fold x1 hex31 hub6_cu", "fold neck+mid hex31 hub6_cu", "fold x2 square31", "fold x2 hex31 hub6_cu"], data=["copper", "POF"])
FOLD_KEY = {"fold x1": "fold x1 (mid) + chassis hinge", "fold neck+mid": "fold neck + mid + chassis hinge", "fold x2": "fold x2 (thirds) + chassis hinge"}

def shaft_row(fo, name):
    if name.startswith("telescope"): return next(r for r in fo["rows"] if r["mechanism"].startswith("telescope"))
    mech, prof = name.rsplit(" ", 2)[0], " ".join(name.split(" ")[2:]) if name.startswith("fold neck") is False else " ".join(name.split(" ")[2:])
    for k, v in FOLD_KEY.items():
        if name.startswith(k): mech = v; prof = name[len(k) + 1:]
    return next(r for r in fo["rows"] if r["mechanism"] == mech and r["profile"] == prof)

def main():
    fo = json.load(open(os.path.join(OUT, "rf2_fold_options.json"))); cache = {}
    face = {"square31": 31 - 2.4 - 0.6, "hex31 hub6_cu": (31 - 2.4) / math.sqrt(3) - 0.6}
    rows = []
    for coil, sw, txd, rx, shaft, data in itertools.product(*AX.values()):
        N, p, tx2 = (26, 1, False) if coil == "26x1" else (15, 2, True)
        sr = shaft_row(fo, shaft); fold = not shaft.startswith("telescope")
        if fold: L_tx = (txd + 150.0) / 1000 + 0.214 * sum(1 for s in sr["hinges_s_mm"] if s < txd)
        else: L_tx = CFX.TX_LEN_M * txd / 857.0
        scale = round(L_tx / CFX.TX_LEN_M, 4)
        key = (N, p, sw, rx, tx2, scale)
        if key not in cache:
            if rx == "mono":
                o, _ = LO.evaluate(N, p, sw, False, False, tx2=tx2, flex_scale=scale); cache[key] = dict(o, gate=o.get("first_gate_us"))
            else:
                h = LO.hybrid(N, p, sw, False, tx2, flex_scale=scale); cache[key] = dict(h, gate=h.get("gate_planar_us"))
        e = cache[key]
        if "depth_cm" not in e: continue
        rt_b = e["runtime_boost_h"]; rt_s = e["runtime_scan_h"]
        if data == "POF": rt_b = round(LO.WH / (LO.WH / rt_b + POF_W), 2); rt_s = round(LO.WH / (LO.WH / rt_s + POF_W), 2)
        fw = e["flex_width_mm"] - (DIG_W if data == "POF" else 0.0)
        w_tx = (e.get("W_TX_mm") or cache.get((N, p, sw, "mono", tx2, scale), {}).get("W_TX_mm") or CFX.W_TX)
        hv = 1.5 + 2 * (w_tx / 2 if tx2 else w_tx) + 1.0
        rules = [dict(rule=r["rule"], value=r["value"], limit=r["limit"], ok=r["ok"], where="TXD (switch)" if "switch" in r["rule"] or "TJ" in r["rule"] else "cord flex") for r in e.get("rule_rows", []) if "cord-flex width" not in r["rule"]]
        if fold:
            prof = shaft.split(" ", 2)[-1] if not shaft.startswith("fold neck") else shaft.split(" ", 2)[-1]
            fwid = face.get(prof, 15.9)
            rules.append(dict(rule="HV lane group on one inner face", value=round(hv, 2), limit=round(fwid, 2), ok=hv <= fwid, where=f"shaft inner face ({prof})"))
        else:
            rules.append(dict(rule="cord-flex width vs 16 mm (18 mm bore less 2)", value=round(fw, 2), limit=16.0, ok=fw <= 16.0, where="telescope inner bore"))
        for r in sr["rule_rows"]:
            if "POF" in r["rule"] and data != "POF": continue
            if "optical" in r["rule"] and data != "POF": continue
            rules.append(dict(rule=r["rule"], value=r["value"], limit=r["limit"], ok=r["ok"], where=f"shaft ({sr['mechanism']})"))
        added = (1 if rx == "hybrid" else 0) + (len(sr["hinges_s_mm"]) if fold else 0) + (6 if data == "POF" else 0) + (1 if tx2 else 0)
        mass_d = (sr["tubes_and_hinges_g"] - 210) + (RX_G if rx == "hybrid" else 0) + (POF_G if data == "POF" else 0)
        rows.append(dict(coil=coil, switch=sw, txd_s_mm=txd, rx=rx, shaft=shaft, data=data, L_tx_m=round(L_tx, 3), first_gate_us=e["gate"], depth_cm=e["depth_cm"],
                         runtime_boost_h=rt_b, runtime_scan_h=rt_s, flex_width_mm=round(fw, 2), shaft_g=sr["tubes_and_hinges_g"], tip_sag_mm=sr["tip_sag_mm"], collapsed_mm=sr["collapsed_mm"],
                         added_parts=added, mass_delta_g=round(mass_d), rules=rules, breaks=[r for r in rules if not r["ok"]]))
    base = next(r for r in rows if r["coil"] == "26x1" and r["switch"] == "C3M0280090J" and r["txd_s_mm"] == 857 and r["rx"] == "mono" and r["shaft"].startswith("telescope") and r["data"] == "copper")
    def margin(r):
        vals = []
        for x in r["rules"]:
            v, l = float(x["value"]), float(x["limit"])
            if v <= 0 or l <= 0: continue
            ratio = (l / v) if any(k in x["rule"] for k in ("vs 80 %", "TJ", "width", "group", "sag", "collapsed")) else (v / l)
            vals.append(min(ratio, M_SAT))
        return min(vals) if vals else M_SAT
    m0 = margin(base)
    for r in rows:
        sig = math.prod(r["depth_cm"][k] / base["depth_cm"][k] for k in base["depth_cm"]) ** (1 / 3)
        f = dict(mass_g=(M_SYS) / (M_SYS + r["mass_delta_g"]), runtime_h=r["runtime_boost_h"] / base["runtime_boost_h"], signal=sig,
                 margin=margin(r) / m0, attach=1.0 / (1 + 0.1 * r["added_parts"]), footprint=base["collapsed_mm"] / r["collapsed_mm"],
                 verify=1.0 - 0.1 * ((r["rx"] == "hybrid") + (r["data"] == "POF") + (not r["shaft"].startswith("telescope")) + (r["coil"] != "26x1")))
        r["factors"] = {k: round(v, 3) for k, v in f.items()}; r["score"] = round(sum(WEIGHTS[k] * f[k] for k in WEIGHTS), 4)
        r["status"] = "OK" if not r["breaks"] else "BREAKS " + "; ".join(f"{b['rule']} ({b['value']} vs {b['limit']}) at {b['where']}" for b in r["breaks"])
    rows.sort(key=lambda r: -r["score"])
    def dominated(a, b):     # b dominates a on runtime, the three depths, shaft mass, collapsed length, sag
        ka = [a["runtime_boost_h"], *a["depth_cm"].values(), -a["shaft_g"], -a["collapsed_mm"], -a["tip_sag_mm"]]; kb = [b["runtime_boost_h"], *b["depth_cm"].values(), -b["shaft_g"], -b["collapsed_mm"], -b["tip_sag_mm"]]
        return all(y >= x for x, y in zip(ka, kb)) and any(y > x for x, y in zip(ka, kb))
    for r in rows: r["pareto"] = not any(dominated(r, o) for o in rows if o is not r)
    res = dict(status="MODELED variant shuffle (owner 2026-10-31): nothing adopted; nothing excluded; broken rules named at their location", axes=AX, weights=WEIGHTS, n=len(rows),
               baseline=dict(score=base["score"], depth_cm=base["depth_cm"], runtime_boost_h=base["runtime_boost_h"]), rows=rows)
    json.dump(res, open(os.path.join(OUT, "rf2_variants.json"), "w"), indent=1, default=float)
    L = ["# Variant shuffle (generated by rf2/rf2_variants.py; MODELED)", "", res["status"] + ".", f"{len(rows)} combinations of: " + "; ".join(f"{k} = {' | '.join(map(str, v))}" for k, v in AX.items()) + ".",
         f"Score = rf2_select weights {WEIGHTS}, today's machine = {base['score']}. P = on the Pareto front (runtime, three depths, shaft mass, collapsed length, sag).", "",
         "## Top 25 by score (all statuses)", "", "| # | Score | P | Coil | Switch | TXD s | RX | Shaft | Data | Gate us | Coin / 1 g / 0.1 g cm | Boost h | Shaft g | Sag mm | Collapsed mm | Status |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    def line(i, r):
        d = r["depth_cm"]; return f"| {i} | {r['score']} | {'P' if r['pareto'] else ''} | {r['coil']} | {r['switch'][:4]} | {r['txd_s_mm']} | {r['rx']} | {r['shaft']} | {r['data']} | {r['first_gate_us']} | {d['coin_25mm_silver']} / {d['gold_1g']} / {d['gold_0p1g']} | {r['runtime_boost_h']} | {r['shaft_g']} | {r['tip_sag_mm']} | {r['collapsed_mm']} | {r['status']} |"
    L += [line(i + 1, r) for i, r in enumerate(rows[:25])]
    ok = [r for r in rows if not r["breaks"]]
    L += ["", f"## Best {min(15, len(ok))} that break no rule", "", "| # | Score | P | Coil | Switch | TXD s | RX | Shaft | Data | Gate us | Coin / 1 g / 0.1 g cm | Boost h | Shaft g | Sag mm | Collapsed mm | Status |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    L += [line(i + 1, r) for i, r in enumerate(ok[:15])]
    L += ["", "## Today's machine", "", line(rows.index(base) + 1, base), "", "Every combination with its factors and rule rows: rf2/results/rf2_variants.json."]
    open(os.path.join(ROOT, "docs", "VARIANTS.md"), "w").write("\n".join(L) + "\n")
    print(len(rows), "variants; baseline score", base["score"], "rank", rows.index(base) + 1)
    for r in rows[:12]: print(r["score"], r["coil"], r["switch"][:4], r["txd_s_mm"], r["rx"], r["shaft"], r["data"], r["first_gate_us"], r["depth_cm"], r["runtime_boost_h"], r["collapsed_mm"], r["status"][:80])
    print("no-break best:"); [print(r["score"], r["coil"], r["switch"][:4], r["txd_s_mm"], r["rx"], r["shaft"], r["data"], r["depth_cm"], r["runtime_boost_h"]) for r in ok[:6]]
    return res

if __name__ == "__main__":
    main(); sys.exit(0)
