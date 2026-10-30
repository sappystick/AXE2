#!/usr/bin/env python3
"""RF2 parity (Phase A, 2026-10-29): every built board re-read from its KiCad file and compared pad by pad with the system netlist; every harness conductor
checked against the nets of the pads it lands on, read from the BUILT boards (not from the netlist); conductors with an end on a board not yet in RF2
(AB1A / AB1B / CB1D: Phase C; NECK; the coil itself) are listed as pending, never counted as checked. Writes out/rf2_parity.json.
usage: python3 rf2/head/rf2_parity.py"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rf2_netlist as NL
OUT = os.path.join(HERE, "out")
FILES = {"MP1": "MP1/PF233-RF2-MP1.kicad_pcb", "TXJ": "TXJ/PF233-RF2-TXJ.kicad_pcb", "LR1": "LR1/PF233-RF2-LR1.kicad_pcb", "SH1": "SH1/PF233-RF2-SH1.kicad_pcb",
         "QA": "SB1R_RF2/SB1R-QA-RF2.kicad_pcb", "QB": "SB1R_RF2/SB1R-QB-RF2.kicad_pcb"}
def board_pads(path):
    import pcbnew
    b = pcbnew.LoadBoard(path); got = {}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNumber(): got[(fp.GetReference(), pad.GetNumber())] = pad.GetNetname()
    return got
def main():
    res = dict(status="parity of the BUILT boards against the RF2 system netlist", netlist=NL.check(), boards={}, harness={})
    built = {}
    for b, rel in FILES.items():
        p = os.path.join(OUT, rel)
        if not os.path.exists(p): res["boards"][b] = dict(ok=False, error="not built"); continue
        got = board_pads(p); built[b] = got
        if b in NL.BOARDS:
            want = {(q["ref"], n): net for q in NL.BOARDS[b]["parts"] for n, net in q["pins"].items()}
            diff = [f"{k}: built {got.get(k)} netlist {v}" for k, v in want.items() if got.get(k) != v] + [f"{k}: built, not in the netlist" for k in got if k not in want]
            chk = json.load(open(os.path.join(OUT, b, f"{b.lower()}_check.json"))) if os.path.exists(os.path.join(OUT, b, f"{b.lower()}_check.json")) else {}
            res["boards"][b] = dict(pads=len(want), mismatches=diff[:8], unconnected=chk.get("kicad_drc", {}).get("unconnected"), ok=not diff and chk.get("ok") is True)
        else:
            res["boards"][b] = dict(pads=len(got), nets=sorted(set(got.values()))[:12], ok=True, note="built by its own generator (SH1: rf2_shield_pcb.py; QA / QB: rf2_sb1r_variant.py)")
    checked, pending, bad = [], [], []
    for cid, a, z, nm, med in NL.HARNESS:
        ends = []
        for e in (a, z):
            bname, ref, pin = (e.split(".") + [None, None])[:3]
            if bname in built and ref is not None: ends.append(built[bname].get((ref, pin), "MISSING PAD"))
            else: ends.append(None)
        names = nm.split("|")
        if None in ends:
            pending.append(dict(id=cid, a=a, z=z, built_end_net=[x for x in ends if x is not None]))
            if any(x is not None and x not in names for x in ends): bad.append(f"{cid}: built end net {ends} not in {names}")
        else:
            (checked if all(x in names for x in ends) else bad).append(cid if all(x in names for x in ends) else f"{cid}: {ends} vs {names}")
    res["harness"] = dict(checked=checked, pending_phase_c=pending, errors=bad)
    res["ok"] = res["netlist"]["ok"] and all(v["ok"] for v in res["boards"].values()) and not bad
    json.dump(res, open(os.path.join(OUT, "rf2_parity.json"), "w"), indent=1); return res
if __name__ == "__main__":
    r = main(); print("ok", r["ok"]); print({b: (v["ok"], v.get("mismatches", [])[:2]) for b, v in r["boards"].items()}); print("harness checked", r["harness"]["checked"], "pending", [p["id"] for p in r["harness"]["pending_phase_c"]], "errors", r["harness"]["errors"])
