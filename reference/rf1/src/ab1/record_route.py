#!/usr/bin/env python3
"""RF1 phase 3: collect the final AB1 route results (layout report, KiCad DRC, independent DRC, the placement that produced it) into results/rf1_ab1_route.json"""
import os, json
EXP = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")); out = {"status": "MODELED / tool-checked (KiCad 9 DRC + independent DRC); RF1 side experiment", "boards": {}}
for B in ("A", "B"):
    F = os.path.join(EXP, "build_ab1", f"final_{B}")
    if not os.path.exists(os.path.join(F, "out_board", f"AB1{B}_layout.json")): continue
    rep = json.load(open(os.path.join(F, "out_board", f"AB1{B}_layout.json")))["rep"]; kd = json.load(open(os.path.join(F, "kicad_drc.json"))); ind = json.load(open(os.path.join(F, "indep_drc.json")))
    frp = os.path.join(F, "freeroute.json"); fr = json.load(open(frp)) if os.path.exists(frp) and os.path.getmtime(frp) >= os.path.getmtime(os.path.join(F, "export.log")) else None
    ge = os.path.join(F, "gerber_edge.json")
    # "open" is the final board's: KiCad's unconnected count after the last routing step (the repo router, then Freerouting when it ran)
    out["boards"][B] = dict(open=kd.get("unconnected"), router_open=len(rep["unrouted"]) + len(rep["fanout_failed"]), unrouted=rep["unrouted"], fanout_failed=rep["fanout_failed"], tracks=rep["tracks"], vias=rep["vias"],
                            freerouting=None if fr is None else {k: fr[k] for k in ("version", "jar_sha256", "rules_mm", "ripped", "passes", "unconnected_before", "unconnected_after", "tracks", "vias")},
                            gerber_edge=json.load(open(ge)) if os.path.exists(ge) else None,
                            kicad_errors=kd.get("errors"), kicad_unconnected=kd.get("unconnected"), kicad_warnings=kd.get("warnings"),
                            indep=ind.get("fails") if "fails" in ind else ind.get("summary", "see indep_drc.json"), placement=json.load(open(os.path.join(F, "late.json")))["late"])
json.dump(out, open(os.path.join(EXP, "results", "rf1_ab1_route.json"), "w"), indent=1); print(json.dumps({k: {kk: v[kk] for kk in ("open", "router_open", "kicad_errors", "kicad_unconnected", "indep")} for k, v in out["boards"].items()}))
