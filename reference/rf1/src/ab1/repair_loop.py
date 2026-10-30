#!/usr/bin/env python3
"""RF1 phase 3: placement repair loop. From a routed RF1 AB1 layout with open nets: find the parts with a pad within RADIUS of each stuck pad, let
autoplace_rf1.py re-place only those (RF1_AP_ONLY, 2 mm window, starting from the current positions), route again, keep the result if fewer nets are open.
usage (cwd: build_ab1): python3 ../src/ab1/repair_loop.py BOARD START_DIR "RF1_PUT" MARGIN ITERATIONS"""
import os, sys, json, math, subprocess, shutil
B, START, PUT, MARGIN, IT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
HERE = os.path.dirname(os.path.abspath(__file__)); SCHED = [(2.5, MARGIN), (3.5, MARGIN), (2.5, "0.35"), (4.5, "0.35"), (3.5, "0.6"), (5.5, "0.5")]
def env(late, extra=None):
    e = dict(os.environ, BOARD=B, RF1_J2="15.6,0.0,90", RF1_PUT=PUT, RF1_LATE=late, PYTHONPATH=HERE)
    if extra: e.update(RF1_AP_EXTRA=extra, RF1_AP_ONLY="1")
    return e
def opens(d):
    r = json.load(open(os.path.join(d, "out_board", f"AB1{B}_layout.json")))["rep"]; return r["unrouted"] + r["fanout_failed"], r
def merge(late, new):
    D = {e.split(":")[0]: e for e in late.split(";") if e}
    for e in new.split(";"):
        if e: D[e.split(":")[0]] = e
    return ";".join(D.values())
best_dir = START; best_late = json.load(open(os.path.join(START, "late.json")))["late"]; best_open, _ = opens(START)
print("start", len(best_open), best_open, flush=True)
tried = set()
for it in range(IT):
    if not best_open: break
    RADIUS, MG = SCHED[it % len(SCHED)]
    # pads of the stuck connections and the parts near them
    q = subprocess.run([sys.executable, "-c", "import afe_layout as A, json; print(json.dumps([dict(ref=p['ref'], num=p['num'], x=p['x'], y=p['y'], net=A.owner.get((p['ref'], p['num']))) for p in A.PADS]))"], cwd=best_dir, env=env(best_late), capture_output=True, text=True)
    pads = json.loads(q.stdout.strip().splitlines()[-1])
    stuck = []
    for o in best_open:
        ref_pad = o.split(": ")[-1] if ": " in o else o
        r_, n_ = ref_pad.split(".")[0], ref_pad.split(".")[1]; stuck += [p for p in pads if p["ref"] == r_ and p["num"] == n_]
    BIG = ("UA", "J", "U1", "U2")
    near = {p["ref"] for s in stuck for p in pads if math.hypot(p["x"] - s["x"], p["y"] - s["y"]) <= RADIUS and not p["ref"].startswith(BIG)}
    nets = {s["net"] for s in stuck if s["net"] and s["net"] not in ("GND", "+5VA")}
    near |= {p["ref"] for p in pads if p["net"] in nets and not p["ref"].startswith(BIG)}            # the small parts on the stuck net are the route's other ends
    near = sorted(near)
    extra = ",".join(near)
    if (extra, MG) in tried: print("skip repeated move set", extra, MG, flush=True); continue
    tried.add((extra, MG))
    d = f"rep_{B}_{os.path.basename(START.rstrip('/'))}_{it}"; os.makedirs(os.path.join(d, "out_board"), exist_ok=True)
    a = subprocess.run([sys.executable, os.path.join(HERE, "autoplace_rf1.py"), MG], cwd=d, env=env(best_late, extra), capture_output=True, text=True)
    try: new = json.loads(a.stdout.strip().splitlines()[-1])["late"]
    except Exception: print("placer failed", a.stderr[-300:], flush=True); continue
    late = merge(best_late, new); json.dump(dict(late=late), open(os.path.join(d, "late.json"), "w"))
    subprocess.run([sys.executable, os.path.join(HERE, "afe_layout.py"), "--route"], cwd=d, env=env(late), capture_output=True, text=True, timeout=900)
    o, rep = opens(d); print(f"iter {it} (r {RADIUS}, margin {MG}): moved {extra} -> {len(o)} open {o} placement {rep['placement_errors'][:2]}", flush=True)
    if not rep["placement_errors"] and len(o) < len(best_open): best_dir, best_late, best_open = d, late, o
print("BEST", best_dir, len(best_open), best_open, flush=True)
