#!/usr/bin/env python3
"""Freerouting as a scripted pipeline step (2026-10-29): KiCad board -> Specctra DSN -> Freerouting (headless, pinned jar) -> SES -> KiCad board.
The routes are produced by this script from the input board and the rules below, so the step is rerunnable like every other generator; the output
board is then checked by kicad_drc.py and indep_drc.py exactly as a board from the repo's own router.

Rules are written into the board's net classes before the DSN export (Freerouting reads them from the DSN):
  Default class: track / clearance / via diameter / via drill from --rules (mm).
  HV class (--hv NET,NET,...): clearance --hv-clear (default 1.0 mm, rule 6), so the flyback nets keep their spacing while they are routed.
Existing tracks and vias are kept (Freerouting routes only what is open) unless --strip (all) or --rip NET,... (those nets).
Jar: tools/freerouting/freerouting-<ver>.jar, fetched by scripts/fetch_freerouting.sh (SHA-256 pinned); Java 25+ (env JAVA, else java-25 in /usr/lib/jvm).
usage: python3 src/pcb/freeroute.py IN.kicad_pcb OUT.kicad_pcb [--rules 0.15,0.16,0.508,0.254] [--hv NETS] [--hv-clear 1.0] [--passes 100] [--strip | --rip NETS]
       [--report OUT.json]"""
import os, sys, json, glob, shutil, argparse, subprocess, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
VERSION = "2.4.1"
JAR = os.path.join(ROOT, "tools", "freerouting", f"freerouting-{VERSION}.jar")
# headless, no network: the jar's GUI, API server, update check and analytics are all switched off
FR_FLAGS = ["--gui.enabled=false", "--api_server.enabled=false", "--feature_flags.save_jobs=false",
            "--usage_and_diagnostic_data.disable_analytics=true", "--update_check.enabled=false"]

def java():
    if os.environ.get("JAVA"): return os.environ["JAVA"]
    for j in sorted(glob.glob("/usr/lib/jvm/java-2[5-9]-openjdk*/bin/java")) + sorted(glob.glob("/usr/lib/jvm/*/bin/java")):
        try:
            v = subprocess.run([j, "-version"], capture_output=True, text=True).stderr
            if any(f'version "{n}' in v for n in range(25, 40)): return j
        except OSError: pass
    sys.exit("freeroute: Java 25+ not found (apt-get install openjdk-25-jre-headless, or set JAVA)")

def set_rules(b, rules, hv, hv_clear, classes=()):
    import pcbnew
    tw, cl, vd, vdr = rules; ns = b.GetDesignSettings().m_NetSettings; d = ns.GetDefaultNetclass()
    d.SetTrackWidth(pcbnew.FromMM(tw)); d.SetClearance(pcbnew.FromMM(cl)); d.SetViaDiameter(pcbnew.FromMM(vd)); d.SetViaDrill(pcbnew.FromMM(vdr))
    for name, cw, cc, nets in classes:                                   # --class NAME:track:clearance:NET,NET (e.g. wide pulse-current nets); an HV net keeps >= hv_clear
        if any(n in hv for n in nets) and cc < hv_clear: sys.exit(f"freeroute: class {name} holds HV nets: clearance must be >= {hv_clear} mm")
        c = pcbnew.NETCLASS(name); c.SetTrackWidth(pcbnew.FromMM(cw)); c.SetClearance(pcbnew.FromMM(cc)); c.SetViaDiameter(pcbnew.FromMM(max(vd, cw * 0.8)))
        c.SetViaDrill(pcbnew.FromMM(max(vdr, cw * 0.4))); ns.SetNetclass(name, c)
        for n in nets: ns.SetNetclassPatternAssignment(n, name)
    hv = [n for n in hv if not any(n in cn for _, _, _, cn in classes)]
    if classes and not hv: b.SynchronizeNetsAndNetClasses(True)
    if hv:
        c = pcbnew.NETCLASS("HV"); c.SetTrackWidth(pcbnew.FromMM(max(tw, 0.25))); c.SetClearance(pcbnew.FromMM(hv_clear))
        c.SetViaDiameter(pcbnew.FromMM(vd)); c.SetViaDrill(pcbnew.FromMM(vdr)); ns.SetNetclass("HV", c)
        names = set(b.GetNetsByName().keys()) if hasattr(b, "GetNetsByName") else None
        for n in hv:
            ns.SetNetclassPatternAssignment(n, "HV")
        b.SynchronizeNetsAndNetClasses(True)
        missing = [n for n in hv if names is not None and n not in {str(k) for k in names}]
        if missing: sys.exit(f"freeroute: --hv nets not on the board: {missing}")

def open_count(b):
    import pcbnew
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity(); return b.GetConnectivity().GetUnconnectedCount(True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--rules", default="0.15,0.16,0.508,0.254"); ap.add_argument("--hv", default=""); ap.add_argument("--hv-clear", type=float, default=1.0)
    ap.add_argument("--passes", type=int, default=100); ap.add_argument("--threads", type=int, default=1); ap.add_argument("--strip", action="store_true")
    ap.add_argument("--rip", default="", help="nets whose existing tracks and vias are removed first, so Freerouting reroutes them")
    ap.add_argument("--dsn-only", action="store_true", help="write the DSN (rules and classes as Freerouting will see them) and stop; for checks")
    ap.add_argument("--no-neckdown", action="store_true", help="forbid Freerouting's automatic neck-down at pins (tracks keep their class width)")
    ap.add_argument("--no-fanout", action="store_true", help="skip Freerouting's fan-out stage (for a resume on a mostly routed board: only the open connections are routed)")
    ap.add_argument("--class", dest="classes", action="append", default=[], help="NAME:track_mm:clearance_mm:NET,NET (repeatable)")
    ap.add_argument("--report", default=""); ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--stall", type=int, default=0, help="stop Freerouting when its log shows no progress (a finished pass or stage) for this many seconds; "
                    "the report then says stalled and the caller falls back (rf2_boards: A* router). 0 = off")
    a = ap.parse_args()
    if not os.path.exists(JAR): sys.exit(f"freeroute: {JAR} missing: run scripts/fetch_freerouting.sh")
    import pcbnew
    rules = [float(x) for x in a.rules.split(",")]; hv = [n for n in a.hv.split(",") if n]
    if hv and a.hv_clear < 1.0: sys.exit("freeroute: rule 6 needs --hv-clear >= 1.0 mm")
    b = pcbnew.LoadBoard(a.inp)
    classes = [(c.split(":")[0], float(c.split(":")[1]), float(c.split(":")[2]), c.split(":")[3].split(",")) for c in a.classes]
    set_rules(b, rules, hv, a.hv_clear, classes)
    rip = {x for x in a.rip.split(",") if x}
    if a.strip or rip:
        for t in [t for t in b.GetTracks() if a.strip or t.GetNetname() in rip]: b.Delete(t)      # Delete, not Remove: a removed track freed by Python's GC crashed pcbnew later
    open_in = open_count(b)
    work = os.path.abspath(os.path.splitext(a.out)[0] + "_fr"); os.makedirs(work, exist_ok=True)
    dsn, ses, log = (os.path.join(work, "board." + e) for e in ("dsn", "ses", "log"))
    if not pcbnew.ExportSpecctraDSN(b, dsn): sys.exit("freeroute: DSN export failed")
    if a.dsn_only: print(dsn); return
    cmd = [java(), "-jar", JAR, "-de", dsn, "-do", ses, "-mp", str(a.passes), "-mt", str(a.threads)] + FR_FLAGS + (["--router.automatic_neckdown=false"] if a.no_neckdown else []) + (["--router.fanout.enabled=false"] if a.no_fanout else [])
    t0 = time.time()
    import re
    PROGRESS = re.compile(r"pass #\d+ .*completed|stage (started|completed)|Saving output")
    stalled = False
    with open(log, "w") as lf:
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=work); last, seen = time.time(), 0
        while p.poll() is None:                                           # watchdog: progress = a new finished pass / stage line in the log
            time.sleep(2.0)
            try: n = sum(1 for l in open(log, errors="ignore") if PROGRESS.search(l))
            except OSError: n = seen
            if n > seen: seen, last = n, time.time()
            if (a.stall and time.time() - last > a.stall) or time.time() - t0 > a.timeout:
                stalled = True; p.kill(); p.wait(); break                 # our own child process only
    if stalled or p.returncode != 0 or not os.path.exists(ses):
        why = f"no progress for {a.stall} s" if stalled and a.stall and time.time() - t0 <= a.timeout else ("timeout" if stalled else f"rc {p.returncode}")
        if a.report: json.dump(dict(tool="freerouting", version=VERSION, stalled=stalled, reason=why, unconnected_before=open_in, unconnected_after=open_in,
                                    seconds=round(time.time() - t0, 1), progress_lines=seen), open(a.report, "w"), indent=1)
        sys.exit(f"freeroute: Freerouting stopped ({why}); see {log}")
    if not pcbnew.ImportSpecctraSES(b, ses): sys.exit("freeroute: SES import failed")
    filler = pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
    open_out = open_count(b)
    pcbnew.SaveBoard(a.out, b)
    rep = dict(tool="freerouting", version=VERSION, jar_sha256=jar_sha(), input=os.path.relpath(a.inp, ROOT) if a.inp.startswith(ROOT) else a.inp,
               output=os.path.relpath(os.path.abspath(a.out), ROOT), rules_mm=dict(track=rules[0], clearance=rules[1], via=rules[2], drill=rules[3]),
               hv_nets=hv, hv_clear_mm=a.hv_clear if hv else None, passes=a.passes, threads=a.threads, classes=a.classes, neckdown=not a.no_neckdown, fanout=not a.no_fanout, stripped=a.strip, ripped=sorted(rip),
               unconnected_before=open_in, unconnected_after=open_out, seconds=round(time.time() - t0, 1), stalled=False,
               tracks=sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"), vias=sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_VIA"))
    if a.report: json.dump(rep, open(a.report, "w"), indent=1)
    print(json.dumps(rep))

def jar_sha():
    import hashlib; h = hashlib.sha256()
    with open(JAR, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""): h.update(blk)
    return h.hexdigest()

if __name__ == "__main__": main()
