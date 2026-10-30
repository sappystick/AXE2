#!/usr/bin/env python3
"""Self-test of the Freerouting step (src/pcb/freeroute.py), fast (no routing run): the pinned jar is present with its SHA-256, Java 25+ answers, the DSN that
Freerouting reads carries the repo's rules (default class 0.15 mm track / 0.16 mm clearance / 0.508-0.254 mm via) and an HV class at >= 1.0 mm (rule 6),
and an HV clearance below 1.0 mm is refused. Test board: the committed RF1 AB1A (experiments/RF1_rigidflex/build_ab1/final_A).
Writes data/results/freeroute_selftest.json. usage (repo root): python3 tests/freeroute_selftest.py"""
import os, re, sys, json, subprocess, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "pcb")); import freeroute as FR
BOARD = os.path.join(ROOT, "experiments/RF1_rigidflex/build_ab1/final_A/kit_v3/PCB_AB1A/PF233-AB1A.kicad_pcb")
PIN = re.search(r"SHA=([0-9a-f]{64})", open(os.path.join(ROOT, "scripts/fetch_freerouting.sh")).read()).group(1)
res = dict(version=FR.VERSION, pinned_sha256=PIN)
res["jar_present"] = os.path.exists(FR.JAR); res["jar_sha_ok"] = res["jar_present"] and FR.jar_sha() == PIN
try:
    v = subprocess.run([FR.java(), "-version"], capture_output=True, text=True).stderr; res["java"] = v.splitlines()[[i for i, l in enumerate(v.splitlines()) if "version" in l][0]].strip()
except SystemExit as e: res["java"] = None
tmp = tempfile.mkdtemp(); run = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, "src/pcb/freeroute.py"), BOARD, os.path.join(tmp, "t.kicad_pcb"), "--dsn-only", *a], capture_output=True, text=True)
r = run("--hv", "OUT_GY,IN_GX"); dsn = os.path.join(tmp, "t_fr", "board.dsn"); txt = open(dsn).read() if os.path.exists(dsn) else ""
def cls(name):
    m = re.search(r"\(class " + name + r"\b(.*?)\(rule\s*\(width (\d+)\)\s*\(clearance (\d+)\)", txt, re.S)
    return None if not m else dict(nets=m.group(1).split("(circuit")[0].split(), width_um=int(m.group(2)), clearance_um=int(m.group(3)), via="508:254_um" in m.group(1))
d, h = cls("kicad_default"), cls("HV")
res["default_class"] = d and {k: d[k] for k in ("width_um", "clearance_um", "via")}; res["hv_class"] = h and dict(nets=h["nets"], width_um=h["width_um"], clearance_um=h["clearance_um"])
res["hv_low_refused"] = run("--hv", "OUT_GY", "--hv-clear", "0.5").returncode != 0
res["ok"] = bool(res["jar_sha_ok"] and res["java"] and d and d["width_um"] == 150 and d["clearance_um"] == 160 and d["via"]
                 and h and h["clearance_um"] >= 1000 and sorted(h["nets"]) == ["IN_GX", "OUT_GY"] and res["hv_low_refused"])
os.makedirs(os.path.join(ROOT, "data/results"), exist_ok=True)
json.dump(res, open(os.path.join(ROOT, "data/results/freeroute_selftest.json"), "w"), indent=1); print(json.dumps(res))
sys.exit(0 if res["ok"] else 1)
