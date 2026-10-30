#!/usr/bin/env python3
"""AXE2 smart task runner. Every generator, board and check is a STEP with declared inputs, outputs and a pass test. A ledger
(state/ledger.json, committed) remembers for every step its input fingerprint, pass / fail, time and log tail, so a run does only what is needed:

  python3 run.py              run what is needed: steps that FAILED last time, whose INPUTS CHANGED, whose OUTPUTS are missing, or whose dependency re-ran
  python3 run.py --failed     only the steps that failed last time (and nothing else)
  python3 run.py --plan       show what would run and why; run nothing
  python3 run.py --step board:LR1 parity      run these steps only
  python3 run.py --cold       everything
  python3 run.py --list       the steps, their state and last result
  python3 run.py --with-render / --with-studies   include the slow optional groups

Inside a board step the routing is incremental too (rf2/head/rf2_boards.py): template / pre-routes -> resume the last copper -> Freerouting on the
open connections only, with a stall watchdog -> A* fallback router (src/pcb/astar_route.py) on whatever is still open; every attempt is recorded.
Full logs: state/logs/<step>.log (not committed). STATUS.md is regenerated after each run. Everything is MODELED / tool-checked."""
import os, sys, json, glob, time, hashlib, subprocess, argparse, datetime
ROOT = os.path.dirname(os.path.abspath(__file__)); H = "rf2/head/"; OUT = os.path.join(ROOT, H, "out")
STATE = os.path.join(ROOT, "state"); LEDGER = os.path.join(STATE, "ledger.json"); LOGS = os.path.join(STATE, "logs"); LOCK = os.path.join(STATE, "run.lock")
PY = sys.executable
sys.path.insert(0, os.path.join(ROOT, H))


def files(*patterns):
    out = []
    for p in patterns: out += sorted(glob.glob(os.path.join(ROOT, p), recursive=True))
    return out


def board_key(b):
    import rf2_netlist as NL
    return json.dumps(NL.BOARDS[b], sort_keys=True, default=str)


def jcheck(path, test=lambda d: bool(d.get("ok", True))):
    def f():
        p = os.path.join(ROOT, path)
        if not os.path.exists(p): return False, "no result file"
        d = json.load(open(p)); ok = bool(test(d))
        return ok, "" if ok else json.dumps({k: v for k, v in d.items() if not isinstance(v, (list, dict))})[:300]
    return f


ROUTER = ["src/pcb/freeroute.py", "src/pcb/astar_route.py", H + "rf2_boards.py", H + "rf2_ledgrid.py", H + "rf2_ring_template.py"]
STEPS = [
    dict(id="netlist", cmd=[H + "rf2_netlist.py"], inputs=[H + "rf2_netlist.py", H + "rf2_ledgrid.py"], deps=[]),
    dict(id="head", cmd=[H + "rf2_head.py"], inputs=[H + "rf2_head.py", H + "rf2_ledgrid.py", H + "rf2_netlist.py"], deps=[], outputs=[H + "out/RF2_LID.stl"]),
    dict(id="shield:SH1", cmd=[H + "rf2_shield_pcb.py"], inputs=[H + "rf2_shield_pcb.py"], deps=[],
         check=jcheck(H + "out/SH1/sh1_check.json", lambda d: d["kicad_drc_errors"] == 0 and d["kicad_unconnected"] == 0 and d["topology"]["loop_free"])),
    dict(id="sb1r-variant", cmd=[H + "rf2_sb1r_variant.py"], inputs=[H + "rf2_sb1r_variant.py", "src/pcb/sbq_export.py", "src/pcb/models3d.py", "data/reference/sbq_geometry.json"],
         deps=[], check=jcheck(H + "out/SB1R_RF2/sb1r_variant_check.json")),
] + [dict(id=f"board:{b}", cmd=[H + "rf2_boards.py", b], inputs=ROUTER, key=lambda b=b: board_key(b), deps=["netlist"], timeout=7200,
          check=jcheck(H + f"out/{b}/{b.lower()}_check.json")) for b in ("TXJ", "MP1", "LR1")] + [
    dict(id="field-xcheck", cmd=[H + "rf2_field_xcheck.py"], inputs=[H + "rf2_field_xcheck.py", "rf2/rf2_coil_search.py", H + "rf2_head.py"], deps=[],
         check=jcheck(H + "out/rf2_field_xcheck.json")),
    dict(id="mp1-spice", cmd=[H + "rf2_mp1_spice.py"], inputs=[H + "rf2_mp1_spice.py"], deps=[], timeout=3600,     # MP1 v2 (IXTY08N100D2, Rin2 100 ohm) recovers inside the first gate
         check=jcheck(H + "out/rf2_mp1_spice.json", lambda d: next(r for r in d["v2_real_fets"][next(k for k in d["v2_real_fets"] if k.startswith("IXTP"))]["sweep"]
                                                                if r["Rin2_ohm"] == 100.0)["recovery_us"] < 16.3)),
    dict(id="display-hinge", cmd=[H + "rf2_ledgrid.py"], inputs=[H + "rf2_ledgrid.py"], deps=[], check=jcheck(H + "out/lr1_hinge_check.json")),
    dict(id="ref3", cmd=[H + "rf2_ref3.py"], inputs=[H + "rf2_ref3.py"], deps=[], check=jcheck(H + "out/rf2_ref3.json", lambda d: d["chosen"] is not None)),
    dict(id="ledger", cmd=[H + "rf2_ledger.py"], inputs=[H + "rf2_ledger.py"], deps=["head"], check=jcheck(H + "out/rf2_ledger.json")),
    dict(id="head-check", cmd=[H + "rf2_head_check.py"], inputs=[H + "rf2_head_check.py"], deps=["head", "ledger", "shield:SH1"], check=jcheck(H + "out/rf2_head_check.json")),
    dict(id="wiring", cmd=[H + "rf2_wiring.py"], inputs=[H + "rf2_wiring.py"], deps=["head", "netlist"], check=jcheck(H + "out/rf2_wiring.json", lambda d: d["checks"]["ok"])),
    dict(id="router-selftest", cmd=["tests/router_selftest.py"], inputs=["tests/router_selftest.py", "src/pcb/astar_route.py"], deps=["board:MP1"],
         check=jcheck("state/router_selftest.json")),
    dict(id="parity", cmd=[H + "rf2_parity.py"], inputs=[H + "rf2_parity.py"], deps=["netlist", "board:TXJ", "board:MP1", "board:LR1", "shield:SH1", "sb1r-variant"],
         check=jcheck(H + "out/rf2_parity.json")),
    dict(id="render", group="render", cmd=[H + "rf2_render_pv.py"], inputs=[H + "rf2_render_pv.py", H + "rf2_render.py"], deps=["head", "board:TXJ", "board:MP1", "board:LR1"],
         outputs=[H + "out/rf2_cutaway.png", H + "out/rf2_exploded.png"], timeout=3600),
    dict(id="display-figure", group="render", cmd=[H + "rf2_ledgrid.py"], inputs=[H + "rf2_ledgrid.py"], deps=[], outputs=[H + "out/rf2_display.png"]),
] + [dict(id=f"study:{n}", group="studies", cmd=[f"rf2/rf2_{n}.py"], inputs=[f"rf2/rf2_{n}.py"], deps=[], outputs=[f"rf2/results/rf2_{n}.json"], timeout=7200)
     for n in ("coil_search", "receiver_combo", "ground", "ground_dsp", "timing", "pinpoint", "petal_ring", "disk_rx", "emi", "thin", "depth_levers", "taper")]


def fingerprint(s):
    h = hashlib.sha256(json.dumps(s["cmd"]).encode())
    for f in files(*s["inputs"]):
        h.update(os.path.relpath(f, ROOT).encode()); h.update(open(f, "rb").read())     # relative: a clone elsewhere keeps the same fingerprints
    if s.get("key"): h.update(s["key"]().encode())
    return h.hexdigest()[:16]


def load():
    return json.load(open(LEDGER)) if os.path.exists(LEDGER) else dict(steps={}, runs=[])


def decide(args, L, ran):
    """(run?, reason) per step, in order"""
    plan = []
    for s in STEPS:
        if s.get("group") == "render" and not (args.with_render or (args.step and s["id"] in args.step)): plan.append((s, False, "optional (--with-render)")); continue
        if s.get("group") == "studies" and not (args.with_studies or (args.step and s["id"] in args.step)): plan.append((s, False, "optional (--with-studies)")); continue
        e = L["steps"].get(s["id"]); fp = fingerprint(s)
        if args.step: r = (s["id"] in args.step, "asked" if s["id"] in args.step else "not asked")
        elif args.cold: r = (True, "cold")
        elif args.failed: r = (bool(e) and e["status"] != "pass", "failed last time" if e and e["status"] != "pass" else "passed / never run")
        elif not e: r = (True, "never run")
        elif e["status"] != "pass": r = (True, "failed last time")
        elif e.get("fingerprint") != fp: r = (True, "inputs changed")
        elif any(not os.path.exists(os.path.join(ROOT, o)) for o in s.get("outputs", [])): r = (True, "outputs missing")
        elif any(d in ran for d in s["deps"]): r = (True, "a dependency re-ran")
        else: r = (False, "up to date")
        plan.append((s, r[0], r[1]))
        if r[0]: ran.add(s["id"])
    return plan


def run_step(s):
    os.makedirs(LOGS, exist_ok=True); log = os.path.join(LOGS, s["id"].replace(":", "_") + ".log"); t0 = time.time()
    with open(log, "w") as lf:
        try: rc = subprocess.run([PY] + [os.path.join(ROOT, c) if c.endswith(".py") else c for c in s["cmd"]], cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT,
                                 timeout=s.get("timeout", 1800)).returncode
        except subprocess.TimeoutExpired: rc = "timeout"
    ok, why = (rc == 0, f"rc {rc}")
    if ok and s.get("check"): ok, why = s["check"]()
    if ok and any(not os.path.exists(os.path.join(ROOT, o)) for o in s.get("outputs", [])): ok, why = False, "outputs missing after the run"
    tail = "".join([l for l in open(log, errors="ignore") if "Debug:" not in l][-8:])[-600:]
    return dict(status="pass" if ok else "fail", rc=rc, seconds=round(time.time() - t0, 1), why="" if ok else why, tail="" if ok else tail,
                fingerprint=fingerprint(s), finished=datetime.datetime.now().isoformat(timespec="seconds"), log=os.path.relpath(log, ROOT))


def status_md(L):
    rows = ["# AXE2 status (generated by run.py; MODELED / tool-checked: no fabricator DRC, CAM review or bench)", "",
            f"Last run: {L['runs'][-1]['finished'] if L['runs'] else 'never'}; overall **{'PASS' if all(L['steps'].get(s['id'], {}).get('status') == 'pass' for s in STEPS if not s.get('group')) else 'FAIL'}** (required steps)", "",
            "| Step | Result | s | Last run | Why it failed |", "|---|---|---|---|---|"]
    for s in STEPS:
        e = L["steps"].get(s["id"]); rows.append(f"| {s['id']}{' (optional)' if s.get('group') else ''} | {e['status'].upper() if e else '-'} | {e['seconds'] if e else ''} | "
                                                  f"{e['finished'] if e else 'never'} | {(e or {}).get('why', '')} |")
    open(os.path.join(ROOT, "STATUS.md"), "w").write("\n".join(rows) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--failed", action="store_true"); ap.add_argument("--plan", action="store_true"); ap.add_argument("--cold", action="store_true")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--step", nargs="+"); ap.add_argument("--with-render", action="store_true"); ap.add_argument("--with-studies", action="store_true")
    args = ap.parse_args(); os.makedirs(STATE, exist_ok=True); L = load()
    if args.list:
        for s in STEPS:
            e = L["steps"].get(s["id"], {}); print(f"{s['id']:<22} {e.get('status', '-'):<5} {e.get('seconds', ''):>7} {e.get('finished', 'never')}  {e.get('why', '')}")
        return
    plan = decide(args, L, set()); todo = [(s, why) for s, go, why in plan if go]
    for s, go, why in plan: print(f"{'RUN ' if go else 'skip'} {s['id']:<22} {why}")
    if args.plan or not todo: print(f"{len(todo)} step(s) to run" + (" (plan only)" if args.plan else "")); return
    if os.path.exists(LOCK):
        pid = int(open(LOCK).read().strip() or 0)
        if pid and os.path.exists(f"/proc/{pid}"): sys.exit(f"run.py: another run is active (pid {pid}); wait for it")
    open(LOCK, "w").write(str(os.getpid())); t0 = time.time(); results = {}
    try:
        for i, (s, why) in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {s['id']} ({why}) ...", flush=True)
            e = run_step(s); L["steps"][s["id"]] = e; results[s["id"]] = e["status"]
            json.dump(L, open(LEDGER, "w"), indent=1)                    # saved after every step: an interrupted run keeps what it learned
            print(f"      {e['status'].upper()} {e['seconds']} s {e['why']}", flush=True)
    finally:
        if os.path.exists(LOCK): os.remove(LOCK)
    L["runs"] = (L["runs"] + [dict(finished=datetime.datetime.now().isoformat(timespec="seconds"), seconds=round(time.time() - t0, 1), results=results)])[-50:]
    json.dump(L, open(LEDGER, "w"), indent=1); status_md(L)
    bad = [k for k, v in results.items() if v != "pass"]
    print(f"done in {round(time.time() - t0, 1)} s: {len(results) - len(bad)} pass, {len(bad)} fail" + (f" -> next: python3 run.py --failed  ({', '.join(bad)})" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__": main()
