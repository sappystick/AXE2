#!/usr/bin/env python3
"""PSpice / TINA-TI macro-model -> ngspice compatibility copies (2026-10-30). The TI models in data/spice are never edited: a converted copy is written to
rf2/head/out/spice_compat/ and that is what ngspice includes. Conversions (each is logged in the returned list):
  .MODEL x VSWITCH(RON ROFF VON VOFF)  ->  .model x SW(vt=(VON+VOFF)/2 vh=(VON-VOFF)/2 ron roff)     (ngspice's switch has no VON / VOFF)
  TEMP inside an expression            ->  temper
  IF(cond, a, b) in VALUE expressions  ->  ternary_fcn(cond, a, b)      (ngspice has no IF function; single | and & become || and &&)
  R_NOISELESS resistors (T_ABS = -273.15 in PSpice: no thermal noise)  ->  instance noisy=0 and an empty model (ngspice ignores T_ABS and would add thermal noise)
usage: from spice_compat import compat; path, notes = compat(lib_path)"""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out", "spice_compat")
def num(s):
    s = s.strip().upper().rstrip("V"); m = re.match(r"^([-+]?[0-9.]+(?:E[-+]?\d+)?)(MEG|K|M|U|N|P|F)?$", s)
    if not m: raise ValueError(s)
    return float(m.group(1)) * {"MEG": 1e6, "K": 1e3, "M": 1e-3, "U": 1e-6, "N": 1e-9, "P": 1e-12, "F": 1e-15, None: 1.0}[m.group(2)]
def _ifs(t):
    """rewrite every IF( ... ) call (case-insensitive, balanced parentheses, nested) as ternary_fcn( ... )"""
    out = []; i = 0
    while i < len(t):
        m = re.match(r"IF\s*\(", t[i:], re.I)
        if m and (i == 0 or not (t[i - 1].isalnum() or t[i - 1] == "_")): out.append("ternary_fcn("); i += m.end()
        else: out.append(t[i]); i += 1
    return "".join(out)
def compat(path):
    os.makedirs(OUT, exist_ok=True); notes = []; out = []
    for ln in open(path, encoding="latin-1").read().splitlines():
        m = re.match(r"^\s*\.MODEL\s+(\S+)\s+VSWITCH\s*\(?(.*?)\)?\s*$", ln, re.I)
        if m:
            kv = dict((k.upper(), v) for k, v in re.findall(r"(\w+)\s*=\s*([^\s)]+)", m.group(2))); von, voff = num(kv["VON"]), num(kv["VOFF"])
            new = f".model {m.group(1)} SW(vt={(von + voff) / 2:g} vh={(von - voff) / 2:g} ron={num(kv['RON']):g} roff={num(kv['ROFF']):g})"; notes.append(f"{ln.strip()}  ->  {new}"); out.append(new); continue
        if re.match(r"^\s*\.MODEL\s+R_NOISELESS", ln, re.I): new = ".model R_NOISELESS R()"; notes.append(f"{ln.strip()}  ->  {new}"); out.append(new); continue
        if re.match(r"^\s*R\S*\s+\S+\s+\S+\s+R_NOISELESS\s", ln, re.I): out.append(ln.rstrip() + " noisy=0"); continue
        if re.search(r"\bIF\s*\(", ln, re.I) and "VALUE" in ln.upper(): new = re.sub(r"(?<![&])&(?![&])", "&&", re.sub(r"(?<![|])\|(?![|])", "||", _ifs(ln))); notes.append(f"{ln.strip()}  ->  {new.strip()}"); out.append(new); continue
        if re.search(r"\bTEMP\b", ln, re.I) and ln.lstrip().upper().startswith("E") and "VALUE" in ln.upper():
            new = re.sub(r"\bTEMP\b", "temper", ln, flags=re.I); notes.append(f"{ln.strip()}  ->  {new.strip()}"); out.append(new); continue
        out.append(ln)
    dst = os.path.join(OUT, os.path.basename(path)); open(dst, "w", encoding="latin-1").write("\n".join(out) + "\n"); return dst, notes
