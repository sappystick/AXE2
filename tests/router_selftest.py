#!/usr/bin/env python3
"""Router self-test (AXE2): rip four nets off the routed MP1 board (HV board, rule 6), reroute only those with the A* fallback router, and require
KiCad DRC 0 errors / 0 unconnected, the HV rule control run active, and the independent copper check (clearance, HV >= 1.0 mm, no loop around the axis).
usage: python3 tests/router_selftest.py   (make route-test) -> state/router_selftest.json"""
import os, sys, json, subprocess, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "rf2/head"))
import pcbnew, rf2_boards as R, rf2_netlist as NL
B = NL.BOARDS["MP1"]; src = os.path.join(ROOT, "rf2/head/out/MP1/PF233-RF2-MP1.kicad_pcb"); tmp = tempfile.mkdtemp()
rip = {"INP", "OUT_A", "VBIAS", "PLUS_A"}; b = pcbnew.LoadBoard(src); n = 0
for t in [t for t in b.GetTracks() if t.GetNetname() in rip and not t.IsLocked()]: b.Delete(t); n += 1
ripped = os.path.join(tmp, "ripped.kicad_pcb"); out = os.path.join(tmp, "astar.kicad_pcb"); pcbnew.SaveBoard(ripped, b)
before = R.kicad_drc(ripped, B)["unconnected"]
tw, cl, vd, vh = (float(x) for x in B.get("rules", R.RULES).split(","))
r = subprocess.run([sys.executable, os.path.join(ROOT, "src/pcb/astar_route.py"), ripped, out, "--track", str(tw), "--clear", str(cl), "--via", f"{vd},{vh}",
                    "--edge", str(R.EDGE), "--hv", ",".join(B["hv_nets"]), "--report", os.path.join(tmp, "a.json")], capture_output=True, text=True)
d = R.kicad_drc(out, B); c = R.copper_check(out, B)
res = dict(test="rip 4 MP1 nets, reroute with astar_route.py", ripped_items=n, unconnected_before=before, unconnected_after=d["unconnected"], drc_errors=d["errors"],
           hv_rule_control_violations=d["hv_rule_control_violations"], min_clearance_mm=c["min_clearance_mm"], min_hv_clearance_mm=c["min_hv_clearance_mm"],
           loops_around_axis=c["loops_around_axis"], astar=json.load(open(os.path.join(tmp, "a.json"))).get("seconds"))
res["ok"] = before > 0 and d["unconnected"] == 0 and d["errors"] == 0 and (d["hv_rule_control_violations"] or 0) > 0 and c["ok"]
os.makedirs(os.path.join(ROOT, "state"), exist_ok=True); json.dump(res, open(os.path.join(ROOT, "state/router_selftest.json"), "w"), indent=1); print(json.dumps(res))
sys.exit(0 if res["ok"] else 1)
