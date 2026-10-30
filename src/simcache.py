#!/usr/bin/env python3
"""AXE2 result cache (2026-10-30): memoize expensive, DETERMINISTIC computations whose result is a small JSON value (an ngspice bench reduced to numbers, a KiCad DRC verdict,
a copper check), so the same question is never answered twice. The runner (run.py) already skips whole steps whose inputs did not change; this cache works INSIDE a step, so
editing one thing re-computes only the questions that depend on it (adding one point to a sweep runs one point; re-routing a board whose copper did not change skips its DRC).

  from simcache import memo
  @memo("spice.chain.transient", files=[MODEL_FILE], uses=[netlist, leg, MODEL], tools=["ngspice"])
  def transient(rin2, rf, rg): ...

The key is the SHA-256 of: the kind, the function's own source, every `uses` item (a function contributes its source, anything else its repr), the CONTENT of every file in `files`
(a list, or a callable taking the call's arguments and returning paths), the versions of the named `tools`, and the call's arguments (`key_args` can narrow them, e.g. to drop a
file path whose content is already hashed). Change any of those and the old entry is simply not found. Results are stored as state/simcache/<kind>/<key>.json (committed: they are
small, and a new container then starts warm). A hit and a miss return the same value (the miss path is passed through JSON too).
Environment: SIMCACHE=0 bypasses the cache completely; SIMCACHE=refresh recomputes and overwrites. An unreadable or mismatching entry is treated as a miss.
CLI: python3 src/simcache.py --stats | --kinds | --verify    (verify re-reads every entry and checks its key field and JSON; it deletes nothing)"""
import os, sys, json, hashlib, inspect, subprocess, functools, time, atexit
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CACHE = os.environ.get("SIMCACHE_DIR") or os.path.join(ROOT, "state", "simcache")
MODE = os.environ.get("SIMCACHE", "1")
_STATS = dict(hits=0, misses=0, saved_s=0.0, spent_s=0.0, bypass=0); _FH = {}; _TV = {}
def _toplevel_blocks(t):
    """the depth-1 children of the outer (kicad_pcb ...) form, as strings (parentheses inside quoted text do not count)"""
    out = []; depth = 0; start = None; q = False; i = 0; n = len(t)
    while i < n:
        c = t[i]
        if q:
            if c == "\\": i += 1
            elif c == '"': q = False
        elif c == '"': q = True
        elif c == "(":
            depth += 1
            if depth == 2: start = i
        elif c == ")":
            if depth == 2 and start is not None: out.append(t[start:i + 1]); start = None
            depth -= 1
        i += 1
    return out
def _canonical(path, data):
    """bytes to hash: a KiCad board is hashed WITHOUT its uuids and timestamps and with its top-level items SORTED (KiCad writes fresh uuids and may order tracks differently on every
    build, so the raw bytes never match twice although the copper and the pads are identical); everything else is hashed as it is"""
    if path.endswith((".kicad_pcb", ".kicad_dru")):
        import re
        t = data.decode("utf-8", "replace"); t = re.sub(r'\(uuid\s+"?[0-9a-fA-F-]+"?\)', "", t); t = re.sub(r'\(tstamp\s+[0-9a-fA-F-]+\)', "", t)
        t = re.sub(r'\(generator_version\s+"[^"]*"\)', "", t); blocks = _toplevel_blocks(t)
        return ("\n".join(sorted(re.sub(r"\s+", " ", b) for b in blocks))).encode() if blocks else t.encode()
    return data
def file_hash(path):
    p = os.path.abspath(path); st = os.stat(p); k = (p, st.st_mtime_ns, st.st_size)
    if k not in _FH: _FH[k] = hashlib.sha256(_canonical(p, open(p, "rb").read())).hexdigest()
    return _FH[k]
def tool_version(name):
    if name not in _TV:
        cmd = dict(ngspice=["ngspice", "--version"], kicad=["kicad-cli", "version"], python=[sys.executable, "--version"]).get(name, [name, "--version"])
        try: out = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=30); _TV[name] = (out.stdout + out.stderr).strip().splitlines()[0:2]
        except Exception as e: _TV[name] = [f"unavailable: {type(e).__name__}"]
    return _TV[name]
def _src(o):
    if callable(o):
        try: return inspect.getsource(o)
        except (OSError, TypeError): return repr(o)
    return repr(o)
def _canon(o): return json.dumps(o, sort_keys=True, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))
def make_key(kind, fn, args, kwargs, files, uses, tools, key_args):
    h = hashlib.sha256(); h.update(kind.encode()); h.update(_src(fn).encode())
    for u in uses: h.update(b"\x00use\x00"); h.update(_src(u).encode())
    fl = files(*args, **kwargs) if callable(files) else files
    for f in fl: h.update(b"\x00file\x00"); h.update(os.path.relpath(os.path.abspath(f), ROOT).encode() if os.path.abspath(f).startswith(ROOT) else b"ext"); h.update(file_hash(f).encode())
    for t in tools: h.update(b"\x00tool\x00"); h.update(_canon([t, tool_version(t)]).encode())
    h.update(b"\x00args\x00"); h.update(_canon(key_args(*args, **kwargs) if key_args else [args, kwargs]).encode())
    return h.hexdigest()
def _path(kind, key): return os.path.join(CACHE, kind, key[:2], key + ".json")
def memo(kind, files=(), uses=(), tools=(), key_args=None):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if MODE == "0": _STATS["bypass"] += 1; return json.loads(_canon(fn(*args, **kwargs)))
            key = make_key(kind, fn, args, kwargs, files, uses, tools, key_args); p = _path(kind, key)
            if MODE != "refresh" and os.path.exists(p):
                try:
                    e = json.load(open(p))
                    if e.get("key") == key: _STATS["hits"] += 1; _STATS["saved_s"] += float(e.get("seconds", 0)); return e["value"]
                except (OSError, ValueError): pass                                          # unreadable entry: recompute and overwrite
            t0 = time.time(); v = json.loads(_canon(fn(*args, **kwargs))); dt = time.time() - t0
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + f".{os.getpid()}.tmp"; json.dump(dict(key=key, kind=kind, seconds=round(dt, 3), created=time.strftime("%Y-%m-%dT%H:%M:%S"), value=v), open(tmp, "w")); os.replace(tmp, p)
            _STATS["misses"] += 1; _STATS["spent_s"] += dt; return v
        wrapper.cache_kind = kind; return wrapper
    return deco
def stats(): return dict(_STATS)
def _report():
    if _STATS["hits"] or _STATS["misses"]: print(f"simcache: {_STATS['hits']} hit(s) saved about {_STATS['saved_s']:.0f} s, {_STATS['misses']} miss(es) took {_STATS['spent_s']:.0f} s", file=sys.stderr)
atexit.register(_report)
def entries():
    for d, _, fs in os.walk(CACHE):
        for f in fs:
            if f.endswith(".json"): yield os.path.join(d, f)
def main():
    if "--verify" in sys.argv:
        bad = []
        for p in entries():
            try:
                e = json.load(open(p))
                if e.get("key") != os.path.basename(p)[:-5] or "value" not in e: bad.append(p)
            except Exception: bad.append(p)
        print(json.dumps(dict(entries=sum(1 for _ in entries()), bad=bad), indent=1)); return 1 if bad else 0
    kinds = {}
    for p in entries():
        k = os.path.relpath(p, CACHE).split(os.sep)[0]
        try: s = float(json.load(open(p)).get("seconds", 0))
        except Exception: s = 0.0
        kinds.setdefault(k, [0, 0.0]); kinds[k][0] += 1; kinds[k][1] += s
    print(json.dumps({k: dict(entries=v[0], compute_seconds_saved_per_reuse=round(v[1], 1)) for k, v in sorted(kinds.items())}, indent=1)); return 0
if __name__ == "__main__": sys.exit(main())
