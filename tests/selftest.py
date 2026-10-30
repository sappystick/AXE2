#!/usr/bin/env python3
"""AXE2 self-test (2026-10-30): tests of the TOOLS that the design checks rely on, so a broken tool cannot silently pass a design. Every test must be able to fail:
  simcache    hit / miss, invalidation by source, by a `uses` value, by file content; key_args; JSON round trip (hit == miss); corrupt entry recovery; bypass
  spice       the PSpice -> ngspice converter (VSWITCH, IF, | and &, noiseless resistors); the TI models in data/spice are byte-identical to their recorded SHA-256
  qualify     the op-amp bench PASSES the TI LMH6629 model and FAILS a wrong model (a behavioral 80 MHz op-amp): it has discriminating power
  runner      run.py names the input that changed, notices a missing output and a re-run dependency, and skips an unchanged step
Writes state/selftest.json.   usage: python3 tests/selftest.py   (make test)"""
import os, sys, json, time, shutil, tempfile, hashlib, types, traceback
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TMP = tempfile.mkdtemp(prefix="axe2_selftest_"); os.environ["SIMCACHE_DIR"] = os.path.join(TMP, "cache")
sys.path[:0] = [os.path.join(ROOT, "src"), os.path.join(ROOT, "rf2", "head"), ROOT]
import simcache
RESULTS = []
def test(name):
    def deco(fn):
        t0 = time.time()
        try: detail = fn() or ""; ok = True
        except Exception as e: detail = "".join(traceback.format_exception_only(type(e), e)).strip()[:300]; ok = False
        RESULTS.append(dict(name=name, ok=ok, seconds=round(time.time() - t0, 2), detail=detail)); print(("PASS " if ok else "FAIL "), name, detail if not ok else "")
        return fn
    return deco
# ------------------------------------------------------------------------------------------------ simcache
def counter(kind, **kw):
    calls = []
    @simcache.memo(kind, **kw)
    def f(x, y=0): calls.append((x, y)); return dict(x=x, y=y, t=(x, y))
    return f, calls
@test("simcache: second call is a hit, the first a miss")
def _():
    f, calls = counter("t.hit"); a = f(1); b = f(1)
    assert a == b and len(calls) == 1, calls
@test("simcache: different arguments miss")
def _():
    f, calls = counter("t.args"); f(1); f(2); f(1, y=3); assert len(calls) == 3, calls
@test("simcache: hit and miss return the same value (tuple -> list through JSON)")
def _():
    f, calls = counter("t.rt"); a = f(4, 5); b = f(4, 5); assert a == b and a["t"] == [4, 5]
@test("simcache: a changed `uses` value invalidates")
def _():
    f1, c1 = counter("t.uses", uses=["model-v1"]); f1(1)
    f2, c2 = counter("t.uses", uses=["model-v2"]); f2(1); assert len(c2) == 1
    f3, c3 = counter("t.uses", uses=["model-v1"]); f3(1); assert len(c3) == 0           # the v1 entry is still there
@test("simcache: file CONTENT (not name, not time) keys the entry")
def _():
    p = os.path.join(TMP, "model.txt"); open(p, "w").write("A"); f, c = counter("t.file", files=lambda *a, **k: [p]); f(1); f(1)
    open(p, "w").write("B"); f(1); open(p, "w").write("A"); f(1)
    assert len(c) == 2, c                                                                # A (miss), A (hit), B (miss), A again (hit)
@test("simcache: a KiCad board is keyed without its uuids, timestamps and item order, but a copper change still changes the key")
def _():
    a = os.path.join(TMP, "a.kicad_pcb"); b = os.path.join(TMP, "b.kicad_pcb"); c = os.path.join(TMP, "c.kicad_pcb")
    body = '(kicad_pcb (version 20240108) (segment (start 1 2) (end 3 4) (width 0.2) (layer "F.Cu") (net 1) (uuid "{u}")) (footprint "R" (tstamp 1234abcd-00) (uuid "{u}")))'
    open(a, "w").write(body.format(u="aaaaaaaa-1111")); open(b, "w").write(body.format(u="bbbbbbbb-2222")); open(c, "w").write(body.format(u="aaaaaaaa-1111").replace("(end 3 4)", "(end 3 5)"))
    d = os.path.join(TMP, "d.kicad_pcb")
    open(d, "w").write('(kicad_pcb (version 20240108) (footprint "R" (tstamp 1234abcd-00) (uuid "ab12")) (segment (start 1 2) (end 3 4) (width 0.2) (layer "F.Cu") (net 1) (uuid "cd34")))')       # the same items in the other order
    assert simcache.file_hash(a) == simcache.file_hash(b) == simcache.file_hash(d) and simcache.file_hash(a) != simcache.file_hash(c)
@test("simcache: key_args drops an argument that is already covered by a file hash")
def _():
    p = os.path.join(TMP, "m2.txt"); open(p, "w").write("x"); calls = []
    @simcache.memo("t.keyargs", files=lambda path: [path], key_args=lambda path: [])
    def g(path): calls.append(path); return 1
    q = os.path.join(TMP, "m3.txt"); shutil.copy(p, q); g(p); g(q); assert len(calls) == 1
@test("simcache: a source edit of the function invalidates")
def _():
    import importlib.util; counts = []
    for n, body in enumerate(("return x + 1", "return x + 1", "return x + 2")):                 # the same function, then the same again, then edited
        path = os.path.join(TMP, f"edit_mod{n if n != 1 else 0}.py"); open(path, "w").write(f"import simcache\n@simcache.memo('t.src')\ndef h(x):\n    {body}\n")
        spec = importlib.util.spec_from_file_location(f"edit_mod_{n}", path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        before = sum(1 for _ in simcache.entries()); m.h(1); counts.append(sum(1 for _ in simcache.entries()) - before)    # 1 = a new entry was written (a miss)
    assert counts == [1, 0, 1], counts
@test("simcache: a corrupt entry is recomputed and repaired")
def _():
    f, c = counter("t.corrupt"); f(7); path = next(p for p in simcache.entries() if "t.corrupt" in p); open(path, "w").write("{not json")
    f(7); assert len(c) == 2; f(7); assert len(c) == 2
@test("simcache: SIMCACHE=0 bypasses (no read, no write)")
def _():
    f, c = counter("t.bypass"); old = simcache.MODE; simcache.MODE = "0"
    try: f(1); f(1)
    finally: simcache.MODE = old
    assert len(c) == 2 and not any("t.bypass" in p for p in simcache.entries())
# ------------------------------------------------------------------------------------------------ spice
import spice_compat
@test("spice_compat: VSWITCH -> SW (vt, vh)")
def _():
    p = os.path.join(TMP, "a.lib"); open(p, "w").write(".MODEL S1 VSWITCH(RON=50 ROFF=1E12 VON=500E-3 VOFF=100E-3)\n"); out, notes = spice_compat.compat(p)
    t = open(out).read().lower(); assert "sw(vt=0.3 vh=0.2 ron=50" in t, t
@test("spice_compat: nested IF, | and &, TEMP, noiseless resistors")
def _():
    p = os.path.join(TMP, "b.lib"); open(p, "w").write("G1 a b VALUE={IF(V(x)>1 | V(y)<0,IF(V(z)>2,1,2),0)}\nE1 p n VALUE={DC+K*(TEMP-27)}\n.MODEL R_NOISELESS RES (T_ABS=-273.15)\nR1 a b R_NOISELESS 5\n")
    out, _ = spice_compat.compat(p); t = open(out).read()
    assert "ternary_fcn(V(x)>1 || V(y)<0,ternary_fcn(V(z)>2,1,2),0)" in t.replace(" ", "") or "ternary_fcn(" in t and t.count("ternary_fcn(") == 2, t
    assert "||" in t and "temper" in t and "noisy=0" in t and ".model R_NOISELESS R()" in t, t
@test("spice models: byte-identical to data/spice/SHA256SUMS (the converter never edits them)")
def _():
    bad = []
    for ln in open(os.path.join(ROOT, "data", "spice", "SHA256SUMS")):
        h, rel = ln.split(None, 1); rel = rel.strip()
        if hashlib.sha256(open(os.path.join(ROOT, "data", "spice", rel), "rb").read()).hexdigest() != h: bad.append(rel)
    assert not bad, bad
# ------------------------------------------------------------------------------------------------ qualify
import rf2_opamp_qualify as Q
@test("qualify bench: PASSES the TI LMH6629 model")
def _():
    r = Q.evaluate(); assert r["ok"], [x["name"] for x in r["rows"] if not x["ok"]]
@test("qualify bench: FAILS a wrong model (80 MHz behavioral op-amp in the LMH6629's place)")
def _():
    lib = os.path.join(TMP, "wrong.lib")
    open(lib, "w").write(".SUBCKT BOPA INP INM VCC VEE OUT\nEd d 0 INP INM 1e5\nRp d p 1k\nCp p 0 199n\nBo OUT 0 v = max(v(VEE) + 0.2, min(v(VCC) - 0.2, v(p)))\n.ENDS\n"
                         ".SUBCKT LMH6629 4 3 8 5 7 6\nXb 4 3 8 5 7 BOPA\n.ENDS\n")
    old = Q.LIB; Q.LIB = lib
    try: r = Q.evaluate()
    finally: Q.LIB = old
    bad = [x["name"] for x in r["rows"] if not x["ok"]]
    assert not r["ok"] and len(bad) >= 3, bad
    return f"{len(bad)} rows fail: {', '.join(bad[:5])}"
# ------------------------------------------------------------------------------------------------ runner
import run as R
@test("runner: skips an unchanged step, names the changed input, sees a missing output and a re-run dependency")
def _():
    root = os.path.join(TMP, "proj"); os.makedirs(os.path.join(root, "state"))
    open(os.path.join(root, "a.py"), "w").write("import sys\nopen('out.txt','w').write('x')\n"); open(os.path.join(root, "data.txt"), "w").write("1")
    old = (R.ROOT, R.STEPS, R.LOGS, R.LEDGER); R.ROOT, R.LOGS, R.LEDGER = root, os.path.join(root, "state", "logs"), os.path.join(root, "state", "ledger.json")
    try:
        R.STEPS = [dict(id="s1", cmd=["a.py"], inputs=["a.py", "data.txt"], deps=[], outputs=["out.txt"]), dict(id="s2", cmd=["a.py"], inputs=["a.py"], deps=["s1"], outputs=["out.txt"])]
        L = dict(steps={}, runs=[]); ns = types.SimpleNamespace(with_render=False, with_studies=False, step=None, cold=False, failed=False)
        for s in R.STEPS: L["steps"][s["id"]] = R.run_step(s)
        assert L["steps"]["s1"]["status"] == "pass", L["steps"]["s1"]
        plan = {s["id"]: why for s, go, why in R.decide(ns, L, set())}; assert plan["s1"] == "up to date" and plan["s2"] == "up to date", plan
        open(os.path.join(root, "data.txt"), "w").write("2"); plan = {s["id"]: why for s, go, why in R.decide(ns, L, set())}
        assert plan["s1"].startswith("inputs changed") and "data.txt" in plan["s1"], plan; assert plan["s2"] == "a dependency re-ran", plan
        for s in R.STEPS: L["steps"][s["id"]] = R.run_step(s)
        os.remove(os.path.join(root, "out.txt")); plan = {s["id"]: why for s, go, why in R.decide(ns, L, set())}; assert plan["s1"] == "outputs missing", plan
    finally: R.ROOT, R.STEPS, R.LOGS, R.LEDGER = old
res = dict(ok=all(r["ok"] for r in RESULTS), tests=RESULTS, passed=sum(r["ok"] for r in RESULTS), total=len(RESULTS))
os.makedirs(os.path.join(ROOT, "state"), exist_ok=True); json.dump(res, open(os.path.join(ROOT, "state", "selftest.json"), "w"), indent=1)
for d, ds, fs in os.walk(TMP, topdown=False):                                         # remove only what this run created, file by file
    for f in fs: os.remove(os.path.join(d, f))
    os.rmdir(d)
print(f"selftest: {res['passed']}/{res['total']} passed"); sys.exit(0 if res["ok"] else 1)
