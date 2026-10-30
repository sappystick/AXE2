#!/usr/bin/env python3
"""RF1 phase 3 placement search: route the RF1 AB1 copy for a list of candidate placements (environment overrides of the generated afe_layout.py copy),
one route at a time, in a scratch folder per candidate; keep the candidate with the fewest open nets (unrouted + failed fan-outs) and copy its layout to
build_ab1/out_board. Baseline files untouched. usage: python3 experiments/RF1_rigidflex/src/ab1/search_rf1_ab1.py A|B"""
import os, sys, json, subprocess, shutil, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); EXP = os.path.abspath(os.path.join(HERE, "..", ".."))
B = sys.argv[1]
J2 = {"A": ["11.0,-12.8", "6.0,-16.8"], "B": ["3.0,-17.4", "-6.0,-16.8"]}[B]
RB = ["8.9,1.2", "6.6,1.2"]
CORE = "ULD:11.8:4.0:90;CLO:9.6:2.8:90;CLI:10.6:6.4"
PUT = {"A": [CORE + ";RISA:12.6:-3.0;UB:6.0:5.4:90;CBD:8.0:7.8;RD1:14.8:4.9;RD2:14.8:6.4",
             CORE + ";RISA:5.2:3.0;UB:6.0:5.4:90;CBD:8.0:7.8;RD1:14.8:4.9;RD2:14.8:6.4",
             CORE + ";RISA:12.6:-3.0;UB:6.0:5.4:90;CBD:8.0:7.8;RD1:14.8:4.9;RD2:14.8:6.4;RISB:15.3:9.6;CVB:16.0:-1.0"],
       "B": [CORE + ";RISA:12.6:-3.0", CORE + ";RISA:6.5:9.0;RISB:13.4:11.4;CVB:4.0:16.4", CORE + ";RISA:12.6:-3.0;CVB:15.6:-1.0"]}[B]
def placement_ok(env, d):
    r = subprocess.run([sys.executable, "-c", "import afe_layout as A; import json; print(json.dumps(A.placement_check()))"], cwd=d, env=env, capture_output=True, text=True, timeout=300)
    try: return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: return ["error: " + r.stderr[-200:]]
best = None; rows = []
for j2, rb, put in itertools.product(J2, RB, PUT):
    d = os.path.join(EXP, "build_ab1", "search", f"{B}_{abs(hash((j2, rb, put))) % 10**8}"); os.makedirs(os.path.join(d, "out_board"), exist_ok=True)
    env = dict(os.environ, BOARD=B, PYTHONPATH=HERE, RF1_J2=j2, RF1_RB=rb, RF1_PUT=put)
    pc = placement_ok(env, d)
    if pc: rows.append(dict(j2=j2, rb=rb, put=put, placement=pc[:3])); print(B, "placement", j2, rb, pc[:2], flush=True); continue
    r = subprocess.run([sys.executable, os.path.join(HERE, "afe_layout.py"), "--route"], cwd=d, env=env, capture_output=True, text=True, timeout=600)
    p = os.path.join(d, "out_board", f"AB1{B}_layout.json")
    if not os.path.exists(p): rows.append(dict(j2=j2, rb=rb, put=put, error=r.stderr[-200:])); continue
    rep = json.load(open(p))["rep"]; n = len(rep.get("unrouted", [])) + len(rep.get("fanout_failed", [])) + (100 if rep.get("placement_errors") else 0)
    row = dict(j2=j2, rb=rb, put=put, open=n, unrouted=rep.get("unrouted"), fanout_failed=rep.get("fanout_failed"), placement=rep.get("placement_errors")[:2], dir=d)
    rows.append(row); print(B, n, j2, rb, put[:30], flush=True)
    if best is None or n < best["open"]: best = row
    if n == 0: break
json.dump(dict(board=B, best=best, rows=rows), open(os.path.join(EXP, "results", f"rf1_ab1_search_{B}.json"), "w"), indent=1)
if best: shutil.copy(os.path.join(best["dir"], "out_board", f"AB1{B}_layout.json"), os.path.join(EXP, "build_ab1", "out_board", f"AB1{B}_layout.json"))
print("best", B, best and {k: best[k] for k in ("open", "j2", "rb", "put", "unrouted", "fanout_failed")})
