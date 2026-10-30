#!/usr/bin/env python3
"""RF1 summary (2026-10-29): one table of every RF1 result, read from results/*.json (no number typed by hand). Writes results/RF1_SUMMARY.md.
usage: python3 experiments/RF1_rigidflex/rf1_summary.py"""
import os, json
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(H, "results")
J = lambda n: json.load(open(os.path.join(R, n))) if os.path.exists(os.path.join(R, n)) else None
p1, p2, cav, fe, p4, ab = J("rf1_phase1.json"), J("rf1_phase2.json"), J("rf1_cavity.json"), J("rf1_frontend_check.json"), J("rf1_phase4.json"), J("rf1_ab1_route.json")
L = ["# RF1 side experiment: results (MODELED, not part of the sign-off)", "", "| Area | Baseline | RF1 | Source |", "|---|---|---|---|"]
h = p1["ab1_cb1d_hinges"]; b = h["IDC ribbon on the current 1.27 mm headers (baseline)"]; r = h["rigid-flex hinge from the board edge (RF1)"]
L.append(f"| AB1-CB1D link fit on the meshes | {b['fails']} / {b['checks']} FAIL | {r['fails']} / {r['checks']} FAIL | rf1_phase1.json |")
L.append(f"| Headroom under LB1 / septum (mm) | {b['height_margin_under_LB1_mm']} / {b['height_margin_under_septum_mm']} | {r['height_margin_under_LB1_mm']} / {r['height_margin_under_septum_mm']} | rf1_phase1.json |")
L.append(f"| Hand joints in the head | {p1['census']['hand_joints_today']} | {p1['census']['concept_C_joints']['total']} | rf1_phase1.json |")
q = p2["lead_pickup"]["boards"]["QA"]
L.append(f"| RX lead pickup spread, QA (sigma, mV) | untwisted {q['AWG36 untwisted']['std_mV']}, twisted {q['AWG36 twisted']['std_mV']} | flex {q['flex broadside (RF1)']['std_mV']} | rf1_phase2.json |")
x = p2["crosstalk"]
L.append(f"| Worst crosstalk into MONO_IN / VCM_OUT (mV, bound) | {x['MONO_IN_worst_mV']['ribbon']} / {x['VCM_OUT_worst_mV']['ribbon']} | {x['MONO_IN_worst_mV']['hinge']} / {x['VCM_OUT_worst_mV']['hinge']} | rf1_phase2.json |")
k = cav["option_K_top"]
L.append(f"| Head height (mm), K-top | 47.1 | {k['head_height_mm']} | rf1_cavity.json |")
L.append(f"| L5 controller layer | coat only | potted SYN {k['l5_pour_cm3']} cm3, net head mass {k['net_head_g'][0]} to {k['net_head_g'][1]} g | rf1_cavity.json |")
L.append(f"| OPA2211 input bias vs range (V) | {fe['baseline']['opa_input_dc_V']} vs {fe['baseline']['opa_input_range_V']}: {'PASS' if fe['baseline']['ok'] else 'FAIL'} | {fe['rf1']['opa_input_dc_V']}: {'PASS' if fe['rf1']['ok'] else 'FAIL'} | rf1_frontend_check.json |")
L.append(f"| Stackup rigid / flex (mm) | - | {p4['stackup']['rigid_mm']} / {p4['stackup']['flex_mm']} | rf1_phase4.json |")
L.append(f"| Flattened panel (mm) | - | {p4['panel']['extent_mm'][0]} x {p4['panel']['extent_mm'][1]} (fits 18 x 24 in: {p4['panel']['fits_18x24in']}) | rf1_phase4.json |")
L.append(f"| CB1D section swaps placed | - | {'no collision' if p4['cb1d_map']['ok'] else 'COLLISION'} ({len(p4['cb1d_map']['new'])} clusters) | rf1_phase4.json |")
if ab:
    for B, v in ab["boards"].items():
        L.append(f"| RF1 AB1{B} route | 0 open (baseline) | {v['open']} open; KiCad DRC errors {v.get('kicad_errors')}, unconnected {v.get('kicad_unconnected')}; independent DRC {v.get('indep')} | rf1_ab1_route.json |")
open(os.path.join(R, "RF1_SUMMARY.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
