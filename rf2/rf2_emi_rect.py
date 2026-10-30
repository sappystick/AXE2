#!/usr/bin/env python3
"""RF2 EMI canceller with the rectangular REF3 (2026-10-30; roadmap P0.4). Runs rf2_emi.py unchanged except its two REF constants, which come from
rf2_ref3 'rect_sleeve': EN_REF = the worst axis' e_ref per gain (the canceller weights REF by 1 / gain, so e_ref / gain is what enters the mono), expressed
as an equivalent (e_ref, gain) pair. The original study assumed e_ref 1.9 nV/rtHz at gain 3.
Writes rf2/results/rf2_emi_rect.json.   usage: python3 rf2/rf2_emi_rect.py"""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__))
r = json.load(open(os.path.join(HERE, "head", "out", "rf2_ref3.json")))["rect_sleeve"]
worst = max(("X", "Y", "Z"), key=lambda a: r[a]["e_ref_nV"] / r[a]["gain"]); e, g = r[worst]["e_ref_nV"] * 1e-9, r[worst]["gain"]
src = open(os.path.join(HERE, "rf2_emi.py")).read()
assert "EN_REF = 1.9e-9; REF_GAIN = 3.0" in src and '"rf2_emi.json"' in src
src = src.replace("EN_REF = 1.9e-9; REF_GAIN = 3.0", f"EN_REF = {e!r}; REF_GAIN = {g!r}").replace('"rf2_emi.json"', '"rf2_emi_rect.json"')
g_ = {"__name__": "__main__", "__file__": os.path.join(HERE, "rf2_emi.py")}
exec(compile(src, os.path.join(HERE, "rf2_emi.py"), "exec"), g_)
out = os.path.join(HERE, "results", "rf2_emi_rect.json"); d = json.load(open(out)); d["ref3_layout"] = dict(source="rf2_ref3 rect_sleeve", worst_axis=worst, e_ref_nV=round(e * 1e9, 2), gain=g)
json.dump(d, open(out, "w"), indent=1); print("REF3 rect:", d["ref3_layout"])
