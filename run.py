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
          check=jcheck(H + f"out/{b}/{b.lower()}_check.json")) for b in ("TXJ", "TXF", "MP1", "LR1")] + [
    dict(id="field-xcheck", cmd=[H + "rf2_field_xcheck.py"], inputs=[H + "rf2_field_xcheck.py", "rf2/rf2_coil_search.py", H + "rf2_head.py"], deps=[],
         check=jcheck(H + "out/rf2_field_xcheck.json")),
    dict(id="mp1-spice", cmd=[H + "rf2_mp1_spice.py"], inputs=[H + "rf2_mp1_spice.py"], deps=[], timeout=3600,     # MP1 v2 (IXTY08N100D2, Rin2 100 ohm) recovers inside the first gate
         check=jcheck(H + "out/rf2_mp1_spice.json", lambda d: next(r for r in d["v2_real_fets"][next(k for k in d["v2_real_fets"] if k.startswith("IXTP"))]["sweep"]
                                                                if r["Rin2_ohm"] == 100.0)["recovery_us"] < 16.3)),
    dict(id="display-hinge", cmd=[H + "rf2_ledgrid.py"], inputs=[H + "rf2_ledgrid.py"], deps=[], check=jcheck(H + "out/lr1_hinge_check.json")),
    dict(id="ref3", cmd=[H + "rf2_ref3.py"], inputs=[H + "rf2_ref3.py"], deps=[], check=jcheck(H + "out/rf2_ref3.json", lambda d: d["chosen"] is not None)),
    dict(id="ledger", cmd=[H + "rf2_ledger.py"], inputs=[H + "rf2_ledger.py"], deps=["head"], check=jcheck(H + "out/rf2_ledger.json")),
    dict(id="head:B", cmd=[H + "rf2_head.py", "--variant=B"], inputs=[H + "rf2_head.py", H + "rf2_ledgrid.py", H + "rf2_netlist.py"], deps=[], outputs=[H + "out_B/RF2_LID.stl"]),
    dict(id="head-check:B", cmd=[H + "rf2_head_check.py", "--variant=B"], inputs=[H + "rf2_head_check.py"], deps=["head:B"], check=jcheck(H + "out_B/rf2_head_check.json")),
    dict(id="head-section:B", cmd=[H + "rf2_head_section.py", "--variant=B"], inputs=[H + "rf2_head_section.py"], deps=["head:B"], outputs=[H + "out_B/rf2_head_section.png"]),
    dict(id="head:BF", cmd=[H + "rf2_head.py", "--variant=BF"], inputs=[H + "rf2_head.py", H + "rf2_ledgrid.py", H + "rf2_netlist.py"], deps=[], outputs=[H + "out_BF/RF2_LID.stl"]),
    dict(id="head-check:BF", cmd=[H + "rf2_head_check.py", "--variant=BF"], inputs=[H + "rf2_head_check.py"], deps=["head:BF"], check=jcheck(H + "out_BF/rf2_head_check.json")),
    dict(id="head-section:BF", cmd=[H + "rf2_head_section.py", "--variant=BF"], inputs=[H + "rf2_head_section.py"], deps=["head:BF"], outputs=[H + "out_BF/rf2_head_section.png"]),
    dict(id="head-check", cmd=[H + "rf2_head_check.py"], inputs=[H + "rf2_head_check.py"], deps=["head", "ledger", "shield:SH1"], check=jcheck(H + "out/rf2_head_check.json")),
    dict(id="wiring", cmd=[H + "rf2_wiring.py"], inputs=[H + "rf2_wiring.py"], deps=["head", "netlist"], check=jcheck(H + "out/rf2_wiring.json", lambda d: d["checks"]["ok"])),
    dict(id="zonerules", cmd=[H + "rf2_zonerules.py"], inputs=[H + "rf2_zonerules.py", H + "rf2_netlist.py", H + "rf2_head.py"], deps=["board:TXJ", "board:TXF", "board:MP1", "board:LR1", "head:BF"],
         check=jcheck(H + "out/rf2_zonerules.json")),
    dict(id="construct", cmd=[H + "rf2_construct.py"], inputs=[H + "rf2_construct.py", H + "rf2_head.py", H + "rf2_netlist.py"], deps=["head:BF", "board:TXF"],
         check=jcheck(H + "out_BF/construct/construct_check.json"), timeout=3600),
    dict(id="timing-cord", cmd=["rf2/rf2_timing_cord.py"], inputs=["rf2/rf2_timing_cord.py", "rf2/rf2_timing.py"], deps=[], outputs=["rf2/results/rf2_timing_cord.json"], timeout=3600),
    dict(id="slim", cmd=["rf2/rf2_slim.py"], inputs=["rf2/rf2_slim.py", H + "rf2_ref3.py"], deps=["ref3"], check=jcheck("rf2/results/rf2_slim.json", lambda d: all(d["checks"].values()))),
    dict(id="chassis", cmd=["rf2/rf2_chassis.py"], inputs=["rf2/rf2_chassis.py", "rf2/rf2_upper.py", "src/simcache.py", H + "out/rf2_ref3.json"], deps=["head:BF", "ref3", "timing-cord", "slim"],
         check=jcheck("rf2/chassis_out/rf2_chassis_check.json", lambda d: d["ok"]), timeout=1800),
    dict(id="audio", cmd=["rf2/rf2_audio.py"], inputs=["rf2/rf2_audio.py"], deps=[], check=jcheck("rf2/results/rf2_audio.json", lambda d: d["all_pass"])),
    dict(id="system", cmd=["rf2/rf2_system.py"], inputs=["rf2/rf2_system.py", "rf2/rf2_continuous.py", "rf2/rf2_zones.py", "rf2/rf2_audio.py", "rf2/rf2_upper.py", "rf2/rf2_chassis.py"], deps=["audio", "chassis"],
         check=jcheck("rf2/results/rf2_system.json", lambda d: d["all_pass"]), timeout=1800),
    dict(id="ui", cmd=["rf2/rf2_ui.py"], inputs=["rf2/rf2_ui.py", "rf2/rf2_audio.py", H + "rf2_ledgrid.py"], deps=["audio"], check=jcheck(H + "out/rf2_ui.json")),
    dict(id="lightplate", cmd=["rf2/rf2_lightplate.py"], inputs=["rf2/rf2_lightplate.py", H + "rf2_ledgrid.py"], deps=[], check=jcheck(H + "out/rf2_lightplate.json")),
    dict(id="opamp-qualify", cmd=[H + "rf2_opamp_qualify.py"], inputs=[H + "rf2_opamp_qualify.py", "src/simcache.py", "data/spice/LMH6629/*.lib"], deps=[], check=jcheck(H + "out/rf2_opamp_qualify.json")),
    dict(id="study:mp1v2_chain", group="studies", cmd=[H + "rf2_mp1v2_chain.py"], inputs=[H + "rf2_mp1v2_chain.py", H + "spice_compat.py", "src/simcache.py", "data/spice/LMH6629/*.lib"], deps=["opamp-qualify"],
         check=jcheck(H + "out/rf2_mp1v2_chain.json", lambda d: "checks" in d), timeout=3600),
    dict(id="study:hvparts", group="studies", cmd=["rf2/rf2_hvparts.py"], inputs=["rf2/rf2_hvparts.py", "rf2/rf2_continuous.py"],
         check=jcheck("rf2/results/rf2_hvparts.json", lambda d: d["all_pass"]), timeout=120),
    dict(id="study:mp1v2_protect", group="studies", cmd=[H + "rf2_mp1v2_protect.py"], inputs=[H + "rf2_mp1v2_protect.py", H + "rf2_mp1v2_chain.py", "src/simcache.py", "data/spice/LMH6629/*.lib"],
         deps=["study:mp1v2_chain"], check=jcheck(H + "out/rf2_mp1v2_protect.json", lambda d: d["accuracy_check"]["ok"]), timeout=3600),
    dict(id="selftest", cmd=["tests/selftest.py"], inputs=["tests/selftest.py", "src/simcache.py", "run.py", H + "spice_compat.py", H + "rf2_opamp_qualify.py", "data/spice/SHA256SUMS", "data/spice/**/*.lib"], deps=["opamp-qualify"],
         check=jcheck("state/selftest.json")),
    dict(id="display", cmd=["rf2/rf2_display.py"], inputs=["rf2/rf2_display.py", "rf2/rf2_ui.py", H + "rf2_ledgrid.py"], deps=[], check=jcheck(H + "out/rf2_display.json")),
    dict(id="display3", cmd=["rf2/rf2_display3.py"], inputs=["rf2/rf2_display3.py", "rf2/rf2_display.py", "rf2/rf2_ui.py", "rf2/rf2_audio.py", H + "rf2_ledgrid.py"], deps=[], check=jcheck(H + "out/rf2_display3.json")),
    dict(id="icd", cmd=["rf2/rf2_icd.py"], inputs=["rf2/rf2_icd.py", "rf2/rf2_system.py", "docs/DATASHEET_LOG_ARX.md"], deps=["system"], check=jcheck("rf2/results/rf2_icd.json", lambda d: d["ok_except_parts"]), outputs=["docs/ICD.md"]),
    dict(id="topography", cmd=["rf2/rf2_topography.py"], inputs=["rf2/rf2_topography.py", "rf2/chassis_out/rf2_chassis_check.json", "rf2/results/rf2_system.json", "rf2/head/out/rf2_ref3.json"],
         deps=["chassis", "system", "ref3"], outputs=["docs/SYSTEM_TOPOGRAPHY.md"]),
    dict(id="readiness", cmd=["rf2/rf2_readiness.py"], inputs=["rf2/rf2_readiness.py", "state/ledger.json", "rf2/results/rf2_icd.json"], deps=["topography", "icd"], outputs=["docs/PROTOTYPE_ROADMAP.md"]),
    dict(id="router-selftest", cmd=["tests/router_selftest.py"], inputs=["tests/router_selftest.py", "src/pcb/astar_route.py"], deps=["board:MP1"],
         check=jcheck("state/router_selftest.json")),
    dict(id="parity", cmd=[H + "rf2_parity.py"], inputs=[H + "rf2_parity.py"], deps=["netlist", "board:TXJ", "board:MP1", "board:LR1", "shield:SH1", "sb1r-variant"],
         check=jcheck(H + "out/rf2_parity.json")),
    dict(id="render", group="render", cmd=[H + "rf2_render_pv.py"], inputs=[H + "rf2_render_pv.py", H + "rf2_render.py"], deps=["head", "board:TXJ", "board:MP1", "board:LR1"],
         outputs=[H + "out/rf2_cutaway.png", H + "out/rf2_exploded.png"], timeout=3600),
    dict(id="display-figure", group="render", cmd=[H + "rf2_ledgrid.py"], inputs=[H + "rf2_ledgrid.py"], deps=[], outputs=[H + "out/rf2_display.png"]),
] + [dict(id=f"study:{n}", group="studies", cmd=[f"rf2/rf2_{n}.py"], inputs=[f"rf2/rf2_{n}.py"], deps=[], outputs=[f"rf2/results/rf2_{n}.json"], timeout=7200)
     for n in ("coil_search", "receiver_combo", "ground", "ground_dsp", "timing", "pinpoint", "petal_ring", "disk_rx", "emi", "thin", "depth_levers", "taper", "rodin", "wave", "hood", "hood_wide", "hood_size", "zones", "mitigation", "layout", "switch", "qualify", "fluxgate", "decaylib", "continuous", "separation")]


def finger(s):
    """(fingerprint, {input: short hash}): the map lets the runner say WHICH input changed, not just that something did"""
    h = hashlib.sha256(json.dumps(s["cmd"]).encode()); inputs = {}
    for f in files(*s["inputs"]):
        rel = os.path.relpath(f, ROOT); data = open(f, "rb").read(); h.update(rel.encode()); h.update(data); inputs[rel] = hashlib.sha256(data).hexdigest()[:10]   # relative: a clone elsewhere keeps the same fingerprints
    if s.get("key"):
        k = s["key"](); h.update(k.encode()); inputs["(computed key)"] = hashlib.sha256(k.encode()).hexdigest()[:10]
    return h.hexdigest()[:16], inputs


def fingerprint(s): return finger(s)[0]


def changed_inputs(s, e):
    """names of the inputs that differ from what the ledger entry recorded (None if the entry predates the map)"""
    old = e.get("inputs")
    if old is None: return None
    new = finger(s)[1]; ch = sorted({k for k in set(old) | set(new) if old.get(k) != new.get(k)})
    return ch


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
        elif e.get("fingerprint") != fp:
            ch = changed_inputs(s, e); r = (True, "inputs changed" + (f": {', '.join(ch[:3])}" + (f" (+{len(ch) - 3} more)" if len(ch) > 3 else "") if ch else ""))
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
    fp, inputs = finger(s)
    return dict(status="pass" if ok else "fail", rc=rc, seconds=round(time.time() - t0, 1), why="" if ok else why, tail="" if ok else tail,
                fingerprint=fp, inputs=inputs, finished=datetime.datetime.now().isoformat(timespec="seconds"), log=os.path.relpath(log, ROOT))


def median_s(L, sid):
    h = L["steps"].get(sid, {}).get("history") or ([L["steps"][sid]["seconds"]] if sid in L["steps"] and L["steps"][sid].get("status") == "pass" else [])
    h = sorted(h); return h[len(h) // 2] if h else None


def est(s, L, go):
    m = median_s(L, s["id"]); return f"~{m:>5.0f} s  " if go and m is not None else ("            " if go else "")


def why(sid, L):
    s = next((x for x in STEPS if x["id"] == sid), None)
    if not s: sys.exit(f"no step {sid}; python3 run.py --list")
    e = L["steps"].get(sid); fp, inputs = finger(s)
    print(f"{sid}: cmd {' '.join(s['cmd'])}; deps {s['deps'] or '-'}; group {s.get('group', 'required')}")
    print(f"  inputs ({len(inputs)}): " + ", ".join(sorted(inputs)[:8]) + (" ..." if len(inputs) > 8 else ""))
    if not e: print("  never run"); return
    print(f"  last: {e['status']} in {e['seconds']} s at {e['finished']}; history {e.get('history', [])} s")
    ch = changed_inputs(s, e)
    print("  fingerprint: " + ("unchanged" if e.get("fingerprint") == fp else f"CHANGED: {', '.join(ch) if ch else '(this entry has no per-input record)'}"))
    miss = [o for o in s.get("outputs", []) if not os.path.exists(os.path.join(ROOT, o))]
    if miss: print("  outputs missing: " + ", ".join(miss))
    if e["status"] != "pass": print(f"  failed: {e.get('why')}\n{e.get('tail', '')}")


def timing(L):
    rows = [(s["id"], L["steps"][s["id"]]["seconds"], median_s(L, s["id"])) for s in STEPS if s["id"] in L["steps"] and not s.get("group")]
    for sid, last, med in sorted(rows, key=lambda r: -r[1]): print(f"{sid:<22} last {last:>7.1f} s   median {med:>7.1f} s")
    print(f"required steps, sum of last times: {sum(r[1] for r in rows):.0f} s")
    print("result cache inside the steps: python3 src/simcache.py --stats")


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
    ap.add_argument("--why", metavar="STEP", help="explain one step: its inputs, what changed since it last ran, its time history"); ap.add_argument("--timing", action="store_true", help="time per step (last and median of the history) and the cache")
    args = ap.parse_args(); os.makedirs(STATE, exist_ok=True); L = load()
    if args.list:
        for s in STEPS:
            e = L["steps"].get(s["id"], {}); print(f"{s['id']:<22} {e.get('status', '-'):<5} {e.get('seconds', ''):>7} {e.get('finished', 'never')}  {e.get('why', '')}")
        return
    if args.why: return why(args.why, L)
    if args.timing: return timing(L)
    plan = decide(args, L, set()); todo = [(s, why) for s, go, why in plan if go]
    for s, go, why in plan: print(f"{'RUN ' if go else 'skip'} {s['id']:<22} {est(s, L, go)}{why}")
    est_total = sum(median_s(L, s["id"]) or 0 for s, _ in todo)
    if args.plan or not todo: print(f"{len(todo)} step(s) to run" + (f", about {est_total:.0f} s by their history (a cache hit inside a step makes it faster)" if todo else "") + (" (plan only)" if args.plan else "")); return
    if os.path.exists(LOCK):
        pid = int(open(LOCK).read().strip() or 0)
        if pid and os.path.exists(f"/proc/{pid}"): sys.exit(f"run.py: another run is active (pid {pid}); wait for it")
    open(LOCK, "w").write(str(os.getpid())); t0 = time.time(); results = {}
    try:
        for i, (s, why) in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {s['id']} ({why}) ...", flush=True)
            e = run_step(s); e["history"] = (L["steps"].get(s["id"], {}).get("history", []) + ([e["seconds"]] if e["status"] == "pass" else []))[-8:]
            L["steps"][s["id"]] = e; results[s["id"]] = e["status"]
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
