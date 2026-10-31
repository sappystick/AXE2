#!/usr/bin/env python3
"""AXE2 knowledge base: one SQLite file (FTS5) that indexes every datasheet, document, part row, extracted parameter, result number,
formula, module and run.py step, so the variant engine (rf2_variants.py) and agents can query the whole machine in one place.

  python3 rf2/rf2_kb.py [build]                       rebuild rf2/kb/axe2_kb.sqlite from scratch (+ docs/KNOWLEDGE_BASE.md, rf2/results/rf2_kb.json)
  python3 rf2/rf2_kb.py search "<fts query>" [--kind pdf|md|web|paper|guide] [-n 10]
  python3 rf2/rf2_kb.py part <name>                   parts rows + extracted params + pdf pages that mention it
  python3 rf2/rf2_kb.py param <symbol> [--part X]     e.g. param RDS(on) --part C3M
  python3 rf2/rf2_kb.py fact <key substring>          numbers from the result JSONs
  python3 rf2/rf2_kb.py formula <word>
  python3 rf2/rf2_kb.py deps <file>                   run.py steps that read / write the file, and everything downstream
  python3 rf2/rf2_kb.py gaps                          parts with no PDF on file, PDFs not in DATASHEET_LOG, UNVERIFIED rows
API:  sys.path.insert(0, "rf2"); from rf2_kb import KB; kb = KB(); kb.search(q); kb.part(name); kb.params(symbol, part=None); kb.facts(substr)

Tables (SQLite, rebuilt on every build; nothing in it is hand-edited):
  documents(path, page, kind, text)  FTS5 (porter, unicode61). kind: pdf (data/datasheets), paper (data/papers), guide (data/fab_guides),
             web (data/datasheets/web, tags stripped), md (docs/, rf2/**, concepts/**, root). PDF page = pdftotext -layout page (form feed split);
             md page = '## ' section ordinal (0 = preamble). Downloaded files are UNTRUSTED DATA: only their text is stored, nothing is executed.
  parts(section, part, source, values, use, pdf_path)  every table row of docs/DATASHEET_LOG_ARX.md and rf2/PARTS_RF2.md. Columns are mapped
             from the header words (source|file|url / number|value|figure|read|fact|datasheet / effect|used|role|status|verdict). Tables whose first header is Item or Parameter
             (one part per section) take the part name from the section heading. pdf_path = first file named in the row that exists on disk.
  params(part, pdf_path, page, symbol, name, value, unit, conditions, status)  regex extraction from datasheet PDF text, line by line:
             a known symbol, then 1-3 numbers (min / typ / max, dashes allowed) followed by a unit of that symbol's family on the SAME line.
             Rejected: numbers preceded by '=' '<' '>' (test conditions), symbols followed by '=' (a condition, not a row). Temperature ranges
             'a to b C' near TJ / Tstg / 'temperature'. status is always 'EXTRACTED (unverified)'; ' + MATCHES LOG' is added when all numbers of
             the value (each with >= 2 significant characters or a decimal point) stand alone in that part's DATASHEET_LOG values text.
             Precision over recall: rows whose symbol and number sit on different layout lines are skipped.
  facts(source, key, value, unit)  every JSON in rf2/results, rf2/head/out*/**, rf2/chassis_out, out/**, concepts/out flattened to dotted keys
             (lists as key[i]); files > 5 MB skipped; at most 20000 rows per file. unit = key suffix (_mm, _us, _V, _ohm ...) when present.
  formulas(module, line, text, context)  docstring / comment lines of rf2/, src/, concepts/ *.py that contain '=' and a math marker
             (mu0 sqrt ln exp pi ^ ** / tau I^2 ...), lines inside a 'Model:' / 'Formulas' paragraph, and every top-level def + first docstring
             line of concepts/clib.py. context = enclosing def / class.
  modules(path, summary, imports, inputs, outputs)  docstring (first 300 chars) and imports; inputs / outputs are file-name literals in the
             source (HEURISTIC: a literal on a line with open(..'w') / write / dump / savefig / export counts as output) plus run.py step outputs.
  steps(id, cmd, inputs, outputs, deps, grp)  run.py STEPS parsed with a restricted AST evaluator (dict / list / + / f-strings / H / ROUTER;
             jcheck(path) -> its JSON counted as an output; lambdas ignored). run.py is never executed.
Everything indexed is what the repo already claims (MODELED / UNVERIFIED labels are kept verbatim); the KB adds no engineering facts."""
import os, sys, re, ast, json, glob, html, time, sqlite3, argparse, fnmatch, subprocess, tokenize, io
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
KBDIR = os.path.join(HERE, "kb"); DB = os.path.join(KBDIR, "axe2_kb.sqlite")
MD_OUT = os.path.join(ROOT, "docs", "KNOWLEDGE_BASE.md"); JSON_OUT = os.path.join(HERE, "results", "rf2_kb.json")
DS = "data/datasheets"; LOG_MD = "docs/DATASHEET_LOG_ARX.md"; PARTS_MD = "rf2/PARTS_RF2.md"; HANDOFF = "rf2/HANDOFF_RF2.md"
rel = lambda p: os.path.relpath(p, ROOT)

SCHEMA = """
CREATE VIRTUAL TABLE documents USING fts5(path UNINDEXED, page UNINDEXED, kind UNINDEXED, text, tokenize='porter unicode61');
CREATE TABLE parts(id INTEGER PRIMARY KEY, file TEXT, section TEXT, part TEXT, source TEXT, "values" TEXT, use TEXT, pdf_path TEXT);
CREATE TABLE params(id INTEGER PRIMARY KEY, part TEXT, pdf_path TEXT, page INT, symbol TEXT, name TEXT, value TEXT, unit TEXT, conditions TEXT, status TEXT);
CREATE TABLE facts(source TEXT, key TEXT, value TEXT, unit TEXT);
CREATE TABLE formulas(module TEXT, line INT, text TEXT, context TEXT);
CREATE TABLE modules(path TEXT PRIMARY KEY, summary TEXT, imports TEXT, inputs TEXT, outputs TEXT);
CREATE TABLE steps(id TEXT PRIMARY KEY, cmd TEXT, inputs TEXT, outputs TEXT, deps TEXT, grp TEXT);
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
"""

# ------------------------------------------------------------------ documents
def pdf_pages(path):
    try:
        r = subprocess.run(["pdftotext", "-layout", "-q", path, "-"], capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "replace").split("\f")
    except Exception as e:
        return ["(pdftotext failed: %s)" % e]

def strip_html(t):
    t = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", t); t = re.sub(r"(?s)<!--.*?-->", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", t); t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"[ \t]+", " ", html.unescape(t))

def md_sections(text):
    out, cur, n = [], [], 0
    for ln in text.splitlines():
        if ln.startswith("## ") and cur: out.append((n, "\n".join(cur))); cur, n = [], n + 1
        cur.append(ln)
    if cur: out.append((n, "\n".join(cur)))
    return out

def md_files():
    fs = glob.glob(os.path.join(ROOT, "*.md"))
    for d in ("docs", "rf2", "concepts"): fs += glob.glob(os.path.join(ROOT, d, "**", "*.md"), recursive=True)
    return sorted(set(f for f in fs if "/kb/" not in f))

def pdf_files():
    out = []
    for d, kind in ((DS, "pdf"), ("data/papers", "paper"), ("data/fab_guides", "guide")):
        out += [(f, kind) for f in sorted(glob.glob(os.path.join(ROOT, d, "*.pdf")))]
    return out

def build_documents(db):
    pdfs = pdf_files(); texts = {}
    with ThreadPoolExecutor(max_workers=min(8, (os.cpu_count() or 2) * 2)) as ex:
        for (f, kind), pages in zip(pdfs, ex.map(lambda fk: pdf_pages(fk[0]), pdfs)):
            texts[rel(f)] = (kind, pages)
    rows = []
    for p, (kind, pages) in texts.items():
        rows += [(p, i + 1, kind, t) for i, t in enumerate(pages) if t.strip()]
    for f in sorted(glob.glob(os.path.join(ROOT, DS, "web", "*"))):
        if not f.lower().endswith((".txt", ".html", ".htm", ".md")): continue
        t = open(f, encoding="utf-8", errors="replace").read()
        rows.append((rel(f), 1, "web", strip_html(t) if f.lower().endswith((".html", ".htm")) else t))
    for f in md_files():
        rows += [(rel(f), n, "md", t) for n, t in md_sections(open(f, encoding="utf-8", errors="replace").read())]
    db.executemany("INSERT INTO documents(path,page,kind,text) VALUES(?,?,?,?)", rows)
    return texts

# ------------------------------------------------------------------ parts
def cells(line): return [c.strip() for c in line.strip().strip("|").split("|")]
def clean(s): return re.sub(r"\*\*|`", "", s).strip()

def ds_files():
    fs = {}
    for d in (DS, os.path.join(DS, "web"), "data/papers", "data/fab_guides"):
        for f in glob.glob(os.path.join(ROOT, d, "*")):
            if os.path.isfile(f): fs[os.path.basename(f)] = rel(f)
    return fs

def parse_tables(path, files):
    rows, section, hdr = [], "", None
    lines = open(os.path.join(ROOT, path), encoding="utf-8").read().splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("#"): section = clean(ln.lstrip("#").strip()); hdr = None; continue
        if not ln.lstrip().startswith("|"): hdr = None; continue
        c = cells(ln)
        if hdr is None: hdr = [h.lower() for h in c]; continue
        if all(re.fullmatch(r":?-{2,}:?", x or "--") for x in c): continue
        m = {"source": [], "values": [], "use": []}
        for h, v in zip(hdr[1:], c[1:]):
            k = ("source" if re.search(r"source|file|url", h) else "values" if re.search(r"number|value|figure|read|fact|datasheet", h)
                 else "use" if re.search(r"effect|used|role|status|decision|\buse\b|verdict|why|kept", h) else "values")
            m[k].append(v if k != "values" or len(hdr) <= 4 else "%s: %s" % (h, v))
        part = clean(c[0])
        if hdr[0] in ("item", "parameter", "quantity", "property"):
            part = "%s / %s" % (re.split(r":", section)[0].strip(), part)
        pdf = next((files[b] for b in re.findall(r"([\w.+()-]+\.(?:pdf|txt|html?))", ln) if b in files), "")
        if not pdf:   # no file named: a part-number token of the part cell inside exactly one data file name
            for tok in re.findall(r"[A-Za-z0-9-]*\d[A-Za-z0-9-]*", part):
                k = re.sub(r"[^a-z0-9]", "", tok.lower())
                hits = [v for b, v in files.items() if len(k) >= 6 and re.search(r"[a-z]", k) and k in re.sub(r"[^a-z0-9]", "", b.lower())]
                if len(hits) == 1: pdf = hits[0]; break
        rows.append((path, section, part, " ; ".join(m["source"]), " ; ".join(m["values"]), " ; ".join(m["use"]), pdf))
    return rows

def build_parts(db):
    files = ds_files(); rows = []
    for p in (LOG_MD, PARTS_MD):
        if os.path.exists(os.path.join(ROOT, p)): rows += parse_tables(p, files)
    db.executemany('INSERT INTO parts(file,section,part,source,"values",use,pdf_path) VALUES(?,?,?,?,?,?,?)', rows)
    return rows

# ------------------------------------------------------------------ params
U = {"V": r"k?V|mV", "R": r"m?(?:Ω|Ohm|ohm|ohms)|mΩ|kΩ", "A": r"m?A|µA|uA|μA", "C": r"[pnµuμ]F", "Q": r"[pn]C",
     "T": r"[pnµuμ]s|ms", "N": r"nV\s*/\s*(?:√|rt|sqrt|√)?\s*\(?Hz\)?", "F": r"[kMG]Hz", "SR": r"V\s*/\s*(?:µs|us|μs)",
     "M": r"m?g|kg", "P": r"m?W"}
SYMS = [  # (symbol label, regex for the symbol or its name, unit family)
    ("V(BR)DSS", r"V\s?\(BR\)\s?DSS|BVDSS|VDSS|VDS(?![A-Za-z(])|Drain[- ]Source (?:Breakdown )?Voltage", "V"),
    ("RDS(on)", r"R\s?DS\s?\(on\)|RDS\(ON\)|RDSON|R\s?DS\(on\)|Drain[- ]Source On[- ]?(?:State )?Resistance", "R"),
    ("IDM", r"IDM\b|ID,\s?pulse|ID\(pulse\)|ID,\s?pulsed|Pulsed Drain Current", "A"),
    ("ID", r"(?<![A-Za-z])ID(?![A-Za-z,(])|Continuous Drain Current", "A"),
    ("Ciss", r"Ciss\b|CISS\b|Input Capacitance", "C"), ("Coss", r"Coss\b|COSS\b|Output Capacitance(?! Stored)", "C"),
    ("Crss", r"Crss\b|CRSS\b|Reverse Transfer Capacitance", "C"), ("Qg", r"Q[gG](?:\(tot\)|,?\s?tot)?\b(?!s|d)|Total Gate Charge", "Q"),
    ("Qrr", r"Qrr\b|QRR\b|Reverse Recovery Charge", "Q"),
    ("VGS(th)", r"V\s?GS\s?\(th\)|VGS\(TH\)|Gate Threshold Voltage", "V"),
    ("VRRM", r"VRRM\b|Repetitive Peak Reverse Voltage", "V"), ("IFSM", r"IFSM\b|Surge (?:Forward )?Current", "A"),
    ("IF(AV)", r"IF\(AV\)|IO\(AV\)|(?:^|(?<=\s\s))IO(?=\s+[\d—–-])|I\(AV\)|Average (?:Rectified )?(?:Forward )?Current", "A"),
    ("trr", r"t\s?rr\b|TRR\b|Reverse Recovery Time", "T"), ("Cj", r"C[jJ]\b|C[dD]\b|CT\b|Junction Capacitance|Diode Capacitance", "C"),
    ("VF", r"VF\b|VFM\b|Forward Voltage", "V"),
    ("en", r"\be[nN]\b|Voltage Noise(?: Density)?|Input Noise Voltage(?: Density)?", "N"),
    ("GBW", r"GBW[P]?\b|Gain[- ]Bandwidth(?: Product)?", "F"), ("SR", r"\bSR\b|Slew Rate", "SR"),
    ("IQ", r"\bIQ\b|\bICC\b|\bIDD\b|Quiescent Current|Supply Current", "A"),
    ("Vrated", r"Rated Voltage|Voltage Rating|Working Voltage|\bVWM\b|\bVRWM\b|Rated DC Voltage", "V"),
    ("mass", r"\bWeight\b|\bMass\b", "M"), ("PD", r"\bPD\b|Ptot\b|Power Dissipation", "P"),
]
SYMRE = [(s, re.compile(r"(?:%s)" % r), re.compile(r"(?<![=<>≤≥])\s*((?:[-+±]?\d+(?:\.\d+)?|[—–-])(?:\s*(?:/\s*)?(?:[-+±]?\d+(?:\.\d+)?|[—–-])){0,2})\s*(%s)(?![A-Za-z])" % U[f]))
         for s, r, f in SYMS]
TEMP = re.compile(r"(?:T\s?J|Tstg|T\s?STG|T\s?A\b|[Tt]emperature)[^\n]{0,80}?(-\s?\d+)\s*(?:°\s?C)?\s*(?:to|\.\.|…|~|–)\s*\+?\s?(\d+)\s*°?\s*C\b")
TOL = re.compile(r"[Tt]olerance[^\n]{0,40}?±\s?(\d+(?:\.\d+)?)\s?%")
NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
NORM = str.maketrans({"\u2126": "Ω", "\u03bc": "µ", "\u2212": "-", "\u02da": "°", "\u2009": " ", "\u00a0": " "})
NUMRUN = re.compile(r"\s+((?:[-+±]?\d+(?:\.\d+)?|[—–-])(?:\s+(?:[-+±]?\d+(?:\.\d+)?|[—–-])){0,2})(?=\s{2,}|\s*$)")

def part_from_file(p):
    stem = os.path.splitext(os.path.basename(p))[0]; toks = re.split(r"[_ ]", stem)
    for t in toks[1:] + toks[:1]:
        if re.search(r"\d", t) and re.search(r"[A-Za-z]", t) and not re.fullmatch(r"(?i)rev\w*|v\d.*|\d{4}.*|ds\d+.*", t): return t
    return stem

def line_param(lines, li):
    """first (symbol, name, value, unit, conditions, how) on layout line li, or None"""
    ln = lines[li]
    for (sym, sre, vre), fam in zip(SYMRE, [f for _, _, f in SYMS]):
        for m in sre.finditer(ln):
            if m.start() and ln[m.start() - 1] in "-/_": continue   # USB-PD, I/O ...
            if re.match(r"\s*[=<>≤≥]", ln[m.end():]): continue
            before = ln[:m.start()].strip()[-80:]
            name = (before + " " + m.group(0)).strip() if re.search(r"[a-z]{3}", m.group(0)) else before or m.group(0)
            v = vre.search(ln, m.end())
            if v and NUM.search(v.group(1)) and not re.search(r"[=<>≤≥]\s*$", ln[m.end():v.start(1)]) and v.start(1) - m.end() <= 90:
                return sym, name, v.group(1).strip(), v.group(2), ln[v.end():].strip()[:120], ""
            # column-aligned table: numbers right after the symbol, unit alone in the same column on a line +-2 away
            n = NUMRUN.match(ln, m.end())
            if not n or not NUM.search(n.group(1)): continue
            e = n.end(1)
            if re.match(r"\s{0,8}(?:%%|°|/|(?:%s)(?!\w))" % "|".join(U.values()), ln[e:]): continue   # the row's own unit is another one
            for lj in (li - 1, li + 1, li - 2, li + 2):
                if 0 <= lj < len(lines):
                    u = next((x for x in re.finditer(r"(?<!\S)(%s)(?!\S)" % U[fam], lines[lj]) if e - 2 <= x.start() <= e + 30), None)
                    if u: return sym, name, n.group(1).strip(), u.group(1), ln[e:].strip()[:120], " (unit from adjacent line)"
    return None

def extract_params(texts, parts):
    logvals = {}
    for r in parts:
        if r[6]: logvals.setdefault(r[6], []).append(r[4] + " " + r[3])
    out = []
    for p, (kind, pages) in texts.items():
        if kind != "pdf": continue
        part = part_from_file(p); lv = " ".join(logvals.get(p, []))
        lvnums = set(re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.]*\d)", lv))
        for pg, t in enumerate(pages, 1):
            lines = t.translate(NORM).replace("℃", "°C").splitlines()
            for li, ln in enumerate(lines):
                if len(ln) > 400 or not re.search(r"\d", ln): continue
                h = line_param(lines, li); hits = [h] if h else []
                m = TEMP.search(ln)
                if m: hits.append(("T range", ln[:m.start()].strip()[-60:] or "temperature", "%s to %s" % (m.group(1).replace(" ", ""), m.group(2)), "°C", "", ""))
                m = TOL.search(ln)
                if m: hits.append(("tolerance", "tolerance", "±" + m.group(1), "%", ln[m.end():].strip()[:120], ""))
                for sym, name, val, unit, cond, how in hits:
                    nums = [n.lstrip("+-") for n in NUM.findall(val)]
                    ok = [n for n in nums if len(n.replace(".", "")) >= 2 or "." in n]
                    match = bool(ok) and all(n in lvnums for n in ok)
                    out.append((part, p, pg, sym, re.sub(r"\s+", " ", name), val, unit, re.sub(r"\s+", " ", cond),
                                "EXTRACTED (unverified)" + how + (" + MATCHES LOG" if match else "")))
    return out

# ------------------------------------------------------------------ facts
UNIT = re.compile(r"_(mm|um|nm|cm|m|us|ns|ms|s|h|min|kV|mV|V|kA|mA|uA|A|mohm|kohm|Mohm|ohm|nH|uH|mH|H|pF|nF|uF|g|kg|mW|W|Wh|mAh|uJ|mJ|J|nC|C|K|deg|Hz|kHz|MHz|dB|pct|percent|nV|T|mT|uT)$")

def flatten(o, k="", out=None):
    if out is None: out = []
    if isinstance(o, dict):
        for kk, v in o.items(): flatten(v, "%s.%s" % (k, kk) if k else str(kk), out)
    elif isinstance(o, list):
        for i, v in enumerate(o): flatten(v, "%s[%d]" % (k, i), out)
    else: out.append((k, o))
    return out

def build_facts(db):
    pats = ["rf2/results/**/*.json", "rf2/head/out*/**/*.json", "rf2/chassis_out/**/*.json", "out/**/*.json", "concepts/out/**/*.json"]
    fs = sorted(set(f for p in pats for f in glob.glob(os.path.join(ROOT, p), recursive=True))); n, skipped = 0, []
    for f in fs:
        if os.path.getsize(f) > 5e6: skipped.append(rel(f)); continue
        try: d = json.load(open(f))
        except Exception: skipped.append(rel(f)); continue
        rows = []
        for k, v in flatten(d)[:20000]:
            m = UNIT.search(re.sub(r"\[\d+\]$", "", k))
            rows.append((rel(f), k, json.dumps(v) if not isinstance(v, str) else v[:500], m.group(1) if m else ""))
        db.executemany("INSERT INTO facts VALUES(?,?,?,?)", rows); n += len(rows)
    return len(fs), skipped

# ------------------------------------------------------------------ formulas, modules
MATH = re.compile(r"mu0|μ0|µ0|sqrt|√|\bln\b|\blog\b|\bexp\b|\bpi\b|π|\^|\*\*|\btau\b|τ|I²|I\^2|\bsum\b|Σ|[A-Za-z0-9)\]]\s*/\s*[A-Za-z0-9(]")
FILE_LIT = re.compile(r"""["']([\w./*{}-]+\.(?:json|jsonl|md|csv|pdf|stl|step|png|svg|kicad_pcb|lib|txt|html|cir|net|dxf))["']""")

def py_files():
    return sorted(f for d in ("rf2", "src", "concepts") for f in glob.glob(os.path.join(ROOT, d, "**", "*.py"), recursive=True)
                  if "__pycache__" not in f)

def is_formula(s):
    if "http" in s or len(s) > 300 or not re.search(r"(?<![=<>!])=(?![=>])", s): return False
    t = re.sub(r"\S*/\S*/\S*|\S+\.(?:py|json|md|csv|pdf|png|stl)\b|and/or|\d{4}-\d{2}-\d{2}", " ", s)   # paths, dates
    return bool(MATH.search(t)) and bool(re.search(r"[A-Za-z]", t))

def build_code(db, steps):
    frows, mrows = [], []
    step_out = {}
    for s in steps:
        if s["cmd"]: step_out.setdefault(s["cmd"][0], []).extend(s["outputs"])
    for f in py_files():
        if os.path.abspath(f) == os.path.abspath(__file__): continue   # not this indexer
        src = open(f, encoding="utf-8", errors="replace").read(); p = rel(f)
        try: tree = ast.parse(src)
        except SyntaxError: mrows.append((p, "(syntax error)", "", "", "")); continue
        ctx = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                    if ln not in ctx or node.lineno > ctx[ln][1]: ctx[ln] = (node.name, node.lineno)
        lines = []  # (line, text) from docstrings and comments
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body \
                    and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant) \
                    and isinstance(node.body[0].value.value, str):
                for i, t in enumerate(node.body[0].value.value.splitlines()): lines.append((node.body[0].lineno + i, t.strip(), True))
        try:
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.COMMENT: lines.append((tok.start[0], tok.string.lstrip("#").strip(), False))
        except (tokenize.TokenError, IndentationError): pass
        lines.sort(); block = False
        for ln, t, isdoc in lines:
            if re.match(r"(?i)(model|models|formulas?|physics|equations?)\s*[:(]", t): block = True
            elif not t: block = False
            if t and (is_formula(t) or (block and isdoc and re.search(r"[=∝≈~]", t))):
                frows.append((p, ln, t[:300], ctx.get(ln, ("<module>", 0))[0]))
        if p == "concepts/clib.py":
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    doc = (ast.get_docstring(node) or "").strip().splitlines()
                    frows.append((p, node.lineno, "def %s(%s)%s" % (node.name, ast.unparse(node.args), (": " + doc[0]) if doc else ""), node.name))
        doc = (ast.get_docstring(tree) or "").strip()
        imps = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imps += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module: imps.append(node.module)
        ins, outs = set(), set(step_out.get(p, []))
        for line in src.splitlines():
            for lit in FILE_LIT.findall(line):
                (outs if re.search(r"""open\([^)]*['"][wa]b?['"]|\.write|dump\(|savefig|export|to_csv|\.save\(""", line) else ins).add(lit)
        mrows.append((p, re.sub(r"\s+", " ", doc)[:300], ", ".join(sorted(set(imps))), ", ".join(sorted(ins - outs)), ", ".join(sorted(outs))))
    db.executemany("INSERT INTO formulas VALUES(?,?,?,?)", frows)
    db.executemany("INSERT OR REPLACE INTO modules VALUES(?,?,?,?,?)", mrows)

# ------------------------------------------------------------------ run.py steps (restricted AST evaluation, never executed)
class _Skip(Exception): pass

def _ev(n, env):
    if isinstance(n, ast.Constant): return n.value
    if isinstance(n, ast.Name):
        if n.id in env: return env[n.id]
        raise _Skip(n.id)
    if isinstance(n, (ast.List, ast.Tuple)): return [_ev(e, env) for e in n.elts]
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add): return _ev(n.left, env) + _ev(n.right, env)
    if isinstance(n, ast.JoinedStr):
        s = ""
        for v in n.values:
            if isinstance(v, ast.Constant): s += str(v.value)
            else:
                x = _ev(v.value, env) if not isinstance(v.value, ast.Call) else _call(v.value, env)
                s += str(x)
        return s
    if isinstance(n, ast.Call): return _call(n, env)
    if isinstance(n, ast.ListComp) and len(n.generators) == 1 and isinstance(n.generators[0].target, ast.Name):
        g = n.generators[0]; return [_ev(n.elt, {**env, g.target.id: x}) for x in _ev(g.iter, env)]
    raise _Skip(type(n).__name__)

def _call(n, env):
    fn = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
    if fn == "dict":
        d = {}
        for k in n.keywords:
            try: d[k.arg] = _ev(k.value, env)
            except _Skip: d[k.arg] = None
        return d
    if fn == "jcheck": return {"check_file": _ev(n.args[0], env)}
    if fn == "lower": return _ev(n.func.value, env).lower()
    raise _Skip(str(fn))

def parse_steps():
    tree = ast.parse(open(os.path.join(ROOT, "run.py"), encoding="utf-8").read()); env, steps = {}, []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("H", "ROUTER"):
                try: env[name] = _ev(node.value, env)
                except _Skip: pass
            elif name == "STEPS":
                for d in _ev(node.value, env):
                    outs = list(d.get("outputs") or [])
                    if isinstance(d.get("check"), dict): outs.append(d["check"]["check_file"])
                    steps.append(dict(id=d["id"], cmd=list(d.get("cmd") or []), inputs=list(d.get("inputs") or []), outputs=outs,
                                      deps=list(d.get("deps") or []), grp=d.get("group") or ""))
    return steps

# ------------------------------------------------------------------ gaps
PARTNO = re.compile(r"(?<![\w/.-])([A-Z][A-Z0-9]*(?:[-.][A-Z0-9]+)*)(?![\w/-])")
NOT_PART = re.compile(r"^(RF2|ARX|PHI|AXE|U-DS|OPEN|ITEMS|D233|SH\d|MP\d|LR\d|TX[JF]\d*|AB\d|CB\d|PB\d|PM\d|HB\d|AU\d|LB\d|SB\d|B\d+|P\d|RX\d|TX\d|"
                      r"IEC|ISO|IPC|UL\d|JEDEC|AWG|AEC|ANSI|MIL|EN\d|USB|SOT|SOIC|SOD|SMA|SMB|SMC|TO\d|DO\d|QFN|DFN|MSOP|TSSOP|LFCSP|WCSP|PDFN|SON|VSON|LGA|BGA|"
                      r"SHA|FR\d|X\dR|C0G|NP0|PCB|LED|ADC|DAC|SPI|I2C|GPIO|MCU|PWM|ESR|SOC|SOA|PI\d|DRC|CAM|STL|STEP|FEP|PTFE|PFA|ETFE|PEEK|PET|PEN|PI|CF\d)")

def part_tokens(text):
    out = {}
    for t in PARTNO.findall(text):
        t = t.strip(".-")
        if len(t) < 6 or len(t) > 24 or NOT_PART.match(t): continue
        if len(re.findall(r"\d", t)) < 2 or len(re.findall(r"[A-Z]", t)) < 2: continue
        if re.fullmatch(r"[A-Z]{1,3}\d{1,3}[A-Z]?", t) or re.fullmatch(r"\d.*", t): continue
        if re.search(r"\d{4}-\d{2}", t) or re.fullmatch(r"[A-Z]+\d+-[A-Z]+\d+", t): continue   # dates, ranges C01-C12
        out[t] = out.get(t, 0) + 1
    return out

def compute_gaps(db):
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    names = [norm(os.path.basename(p)) for (p,) in db.execute("SELECT DISTINCT path FROM documents WHERE kind IN ('pdf','web','guide','paper')")]
    ds_text = norm(" ".join(t for (t,) in db.execute("SELECT text FROM documents WHERE kind IN ('pdf','web') AND page<=3")))
    toks = {}
    for f in (PARTS_MD, HANDOFF):
        if os.path.exists(os.path.join(ROOT, f)):
            for t, c in part_tokens(open(os.path.join(ROOT, f), encoding="utf-8").read()).items(): toks[t] = toks.get(t, 0) + c
    no_pdf = []
    for t, c in sorted(toks.items(), key=lambda x: -x[1]):
        k = norm(t)
        if any(k in n for n in names) or k in ds_text: continue
        no_pdf.append({"part": t, "mentions": c})
    log = open(os.path.join(ROOT, LOG_MD), encoding="utf-8").read()
    unref = [p for (p,) in db.execute("SELECT DISTINCT path FROM documents WHERE kind IN ('pdf','web') ORDER BY path")
             if os.path.basename(p) not in log and os.path.splitext(os.path.basename(p))[0] not in log]
    unver = [{"file": f, "section": s, "part": p} for f, s, p in
             db.execute("SELECT file, section, part FROM parts WHERE part||source||\"values\"||use GLOB '*UNVERIFIED*' ORDER BY file, id")]
    nolink = [p for (p,) in db.execute("SELECT DISTINCT part FROM parts WHERE file=? AND (pdf_path='' OR pdf_path IS NULL) AND section LIKE 'RF2-%'", (LOG_MD,))]
    return {"parts_without_pdf": no_pdf, "pdfs_not_in_datasheet_log": unref, "unverified_rows": unver, "rf2_log_rows_without_pdf_link": nolink}

# ------------------------------------------------------------------ build
def build(quiet=False):
    t0 = time.time(); os.makedirs(KBDIR, exist_ok=True)
    gi = os.path.join(KBDIR, ".gitignore")
    if not os.path.exists(gi): open(gi, "w").write("*.sqlite\n*.sqlite-journal\n*.sqlite.tmp\n")
    tmp = DB + ".tmp"
    if os.path.exists(tmp): os.remove(tmp)
    db = sqlite3.connect(tmp); db.executescript(SCHEMA)
    texts = build_documents(db); t_docs = time.time() - t0
    parts = build_parts(db)
    db.executemany("INSERT INTO params(part,pdf_path,page,symbol,name,value,unit,conditions,status) VALUES(?,?,?,?,?,?,?,?,?)", extract_params(texts, parts))
    nfact_files, skipped = build_facts(db)
    steps = parse_steps()
    db.executemany("INSERT INTO steps VALUES(?,?,?,?,?,?)", [(s["id"], " ".join(s["cmd"]), json.dumps(s["inputs"]), json.dumps(s["outputs"]),
                                                              json.dumps(s["deps"]), s["grp"]) for s in steps])
    build_code(db, steps)
    for ix in ("parts(part)", "params(symbol)", "params(part)", "facts(key)", "formulas(module)"):
        db.execute("CREATE INDEX IF NOT EXISTS ix_%s ON %s" % (re.sub(r"\W", "_", ix), ix))
    gaps = compute_gaps(db)
    counts = {t: db.execute("SELECT count(*) FROM %s" % t).fetchone()[0] for t in ("documents", "parts", "params", "facts", "formulas", "modules", "steps")}
    sub = {"pdf_files": len([1 for k, _ in texts.values() if k == "pdf"]), "pdf_pages": sum(len(p) for k, p in texts.values() if k == "pdf"),
           "params_matching_log": db.execute("SELECT count(*) FROM params WHERE status LIKE '%MATCHES LOG%'").fetchone()[0],
           "parts_with_pdf_link": db.execute("SELECT count(*) FROM parts WHERE pdf_path<>''").fetchone()[0],
           "fact_files": nfact_files, "fact_files_skipped": skipped}
    dt = time.time() - t0
    db.executemany("INSERT INTO meta VALUES(?,?)", [("built", time.strftime("%Y-%m-%d %H:%M:%S")), ("build_s", "%.1f" % dt), ("counts", json.dumps(counts))])
    db.commit(); db.close(); os.replace(tmp, DB)
    res = {"ok": True, "build_s": round(dt, 1), "documents_s": round(t_docs, 1), "db": rel(DB), "counts": counts, "detail": sub,
           "gaps": {k: len(v) for k, v in gaps.items()}, "gap_lists": {k: v[:60] for k, v in gaps.items()}}
    os.makedirs(os.path.dirname(JSON_OUT), exist_ok=True); json.dump(res, open(JSON_OUT, "w"), indent=1)
    write_md(res, gaps)
    if not quiet: print(json.dumps({k: res[k] for k in ("build_s", "counts", "detail", "gaps")}, indent=1))
    return res

def write_md(res, gaps):
    c, d = res["counts"], res["detail"]
    L = ["# AXE2 knowledge base", "", "Generated by `python3 rf2/rf2_kb.py build` (do not edit by hand). Database: `rf2/kb/axe2_kb.sqlite` (git-ignored,",
         "rebuilt from scratch in %.0f s). It indexes what the repo already states; extracted datasheet parameters are **EXTRACTED (unverified)**" % res["build_s"],
         "regex reads of the PDF text, and every performance number in `facts` stays MODELED with the assumptions of the study that wrote it.", "",
         "## Tables", "", "| Table | Rows | Content |", "|---|---|---|",
         "| documents (FTS5) | %d | %d datasheet PDFs (%d pages) + papers, fab guides, web pages and every .md, one row per PDF page / md section |" % (c["documents"], d["pdf_files"], d["pdf_pages"]),
         "| parts | %d | table rows of DATASHEET_LOG_ARX.md and PARTS_RF2.md; %d linked to a file in data/ |" % (c["parts"], d["parts_with_pdf_link"]),
         "| params | %d | symbol + value + unit lines from datasheet PDFs; %d have all their numbers in the linked DATASHEET_LOG row (MATCHES LOG) |" % (c["params"], d["params_matching_log"]),
         "| facts | %d | scalars from %d result JSONs (dotted keys); skipped (> 5 MB or unreadable): %s |" % (c["facts"], d["fact_files"], ", ".join(d["fact_files_skipped"]) or "none"),
         "| formulas | %d | formula lines in docstrings / comments of rf2, src, concepts; concepts/clib.py signatures |" % c["formulas"],
         "| modules | %d | every .py: docstring head, imports, file literals (inputs / outputs, heuristic) |" % c["modules"],
         "| steps | %d | run.py STEPS (cmd, inputs, outputs incl. check JSON, deps, group) |" % c["steps"], "",
         "## Coverage gaps", "",
         "- Part numbers named in PARTS_RF2.md / HANDOFF_RF2.md with no file in data/ whose name or first pages contain them: **%d**" % len(gaps["parts_without_pdf"]),
         "  (token heuristic: some are drawing names or order codes, read the list): " + ", ".join("%s (%d)" % (g["part"], g["mentions"]) for g in gaps["parts_without_pdf"][:40]),
         "- Datasheet files on disk not named in DATASHEET_LOG_ARX.md: **%d**: %s" % (len(gaps["pdfs_not_in_datasheet_log"]), ", ".join("`%s`" % os.path.basename(p) for p in gaps["pdfs_not_in_datasheet_log"])),
         "- Table rows marked UNVERIFIED: **%d** (`python3 rf2/rf2_kb.py gaps` lists them)" % len(gaps["unverified_rows"]),
         "- RF2-* DATASHEET_LOG rows that name no file on disk: **%d**" % len(gaps["rf2_log_rows_without_pdf_link"]), "",
         "## How to query", "", "```",
         "python3 rf2/rf2_kb.py search \"reverse recovery\" --kind pdf -n 5   # FTS5 syntax: AND OR NOT \"phrase\" prefix*",
         "python3 rf2/rf2_kb.py part C3M0280090J", "python3 rf2/rf2_kb.py param RDS --part C3M", "python3 rf2/rf2_kb.py fact first_gate",
         "python3 rf2/rf2_kb.py formula mu0", "python3 rf2/rf2_kb.py deps rf2/rf2_cordflex.py", "python3 rf2/rf2_kb.py gaps",
         "sqlite3 rf2/kb/axe2_kb.sqlite \"SELECT path,page FROM documents WHERE documents MATCH 'Coss' LIMIT 5\"", "```", "",
         "Python: `sys.path.insert(0, 'rf2'); from rf2_kb import KB; kb = KB(); kb.search('litz'); kb.part('LMH6629'); kb.params('Coss'); kb.facts('runtime')`.", "",
         "## Limitations", "",
         "- params: precision over recall. Rows whose symbol, number and unit are on different layout lines (common in pdftotext output, e.g. most",
         "  TI electrical-characteristics tables) are missed; a unit is taken from an adjacent line only when it sits in the same column.",
         "  values taken from curves, notes or drawings are not extracted. Treat every params row as a pointer to the page, not as a datasheet fact.",
         "- parts: one row per table row; tables with other layouts (e.g. topology comparisons in PARTS_RF2.md) are indexed as rows too.",
         "- modules inputs / outputs are file-name literals in the source, classified by a line heuristic; run.py step outputs are authoritative.",
         "- Scanned PDFs without a text layer give empty pages (no OCR)."]
    open(MD_OUT, "w").write("\n".join(L) + "\n")

# ------------------------------------------------------------------ API
class KB:
    def __init__(s, path=DB, build_if_missing=True):
        if not os.path.exists(path) and build_if_missing: build(quiet=True)
        s.db = sqlite3.connect(path); s.db.row_factory = sqlite3.Row
    def _q(s, sql, a=()): return [dict(r) for r in s.db.execute(sql, a)]
    def search(s, q, kind=None, n=10):
        sql = ("SELECT path, page, kind, snippet(documents, 3, '[', ']', ' … ', 14) AS snip FROM documents WHERE documents MATCH ?"
               + (" AND kind=?" if kind else "") + " ORDER BY bm25(documents) LIMIT ?")
        a = lambda qq: (qq, kind, n) if kind else (qq, n)
        try: return s._q(sql, a(q))
        except sqlite3.OperationalError: return s._q(sql, a(" ".join('"%s"' % w.replace('"', "") for w in q.split())))
    def part(s, name):
        like = "%" + name + "%"
        rows = s._q('SELECT file, section, part, source, "values", use, pdf_path FROM parts WHERE part LIKE ? OR pdf_path LIKE ?', (like, like))
        pdfs = sorted({r["pdf_path"] for r in rows if r["pdf_path"]})
        params = s._q("SELECT * FROM params WHERE part LIKE ? OR pdf_path LIKE ?" + "".join(" OR pdf_path=?" for _ in pdfs), (like, like, *pdfs))
        pages = s.search('"%s"' % name.replace('"', ""), kind="pdf", n=15)
        return {"parts": rows, "params": params, "pdf_pages": pages}
    def params(s, symbol, part=None):
        """symbol prefix (case-insensitive; '*' = all); names are searched too when the query has >= 4 characters"""
        sym = "" if symbol in ("*", "all") else symbol
        sql = "SELECT * FROM params WHERE (symbol LIKE ?" + (" OR name LIKE ?" if len(sym) >= 4 else "") + ")" \
              + (" AND (part LIKE ? OR pdf_path LIKE ?)" if part else "") + " ORDER BY part, page"
        a = (sym + "%",) + (("%" + sym + "%",) if len(sym) >= 4 else ()) + (("%" + part + "%",) * 2 if part else ())
        return s._q(sql, a)
    def facts(s, substr, n=200): return s._q("SELECT * FROM facts WHERE key LIKE ? LIMIT ?", ("%" + substr + "%", n))
    def formulas(s, word, n=100): return s._q("SELECT * FROM formulas WHERE text LIKE ? OR context LIKE ? LIMIT ?", ("%" + word + "%",) * 2 + (n,))
    def steps(s):
        return [dict(r, cmd=r["cmd"].split(), inputs=json.loads(r["inputs"]), outputs=json.loads(r["outputs"]), deps=json.loads(r["deps"]))
                for r in s._q("SELECT * FROM steps")]
    def deps(s, f):
        f = os.path.relpath(os.path.abspath(f), ROOT) if os.path.exists(f) else f.lstrip("./")
        st = s.steps(); hit = lambda pats: any(fnmatch.fnmatch(f, p) or p == f for p in pats)
        readers = [x["id"] for x in st if hit(x["inputs"]) or (x["cmd"] and x["cmd"][0] == f)]
        writers = [x["id"] for x in st if hit(x["outputs"])]
        down, frontier = {}, set(readers) | set(writers)
        while frontier:
            nxt = set()
            for x in st:
                if x["id"] in down or x["id"] in readers or x["id"] in writers: continue
                why = [d for d in x["deps"] if d in frontier]
                outs = [o for y in st if y["id"] in frontier for o in y["outputs"]]
                why += ["reads " + o for o in outs if hit_any(o, x["inputs"])]
                if why: down[x["id"]] = why; nxt.add(x["id"])
            frontier = nxt
        return {"file": f, "read_by": readers, "written_by": writers, "downstream": down}
    def gaps(s): return compute_gaps(s.db)

def hit_any(f, pats): return any(fnmatch.fnmatch(f, p) or p == f for p in pats)

# ------------------------------------------------------------------ CLI
def main():
    import signal
    if hasattr(signal, "SIGPIPE"): signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=["build", "search", "part", "param", "fact", "formula", "deps", "gaps"])
    ap.add_argument("arg", nargs="?"); ap.add_argument("--kind"); ap.add_argument("--part"); ap.add_argument("-n", type=int, default=10)
    a = ap.parse_args()
    if a.cmd == "build": build(); return
    if a.cmd != "gaps" and not a.arg: ap.error("%s needs an argument" % a.cmd)
    kb = KB(); one = lambda s, w=160: re.sub(r"\s+", " ", str(s))[:w]
    if a.cmd == "search":
        for r in kb.search(a.arg, a.kind, a.n): print("%s:%s [%s]  %s" % (r["path"], r["page"], r["kind"], one(r["snip"], 220)))
    elif a.cmd == "part":
        r = kb.part(a.arg)
        print("== parts rows (%d)" % len(r["parts"]))
        for p in r["parts"]: print("- [%s | %s] %s\n    values: %s\n    use: %s\n    pdf: %s" % (p["file"], one(p["section"], 50), one(p["part"], 90), one(p["values"], 300), one(p["use"], 200), p["pdf_path"] or "-"))
        print("== extracted params (%d, all EXTRACTED (unverified))" % len(r["params"]))
        for p in r["params"][:a.n * 4]: print("  p%-3s %-9s %-10s %s  (%s) %s" % (p["page"], p["symbol"], one(p["value"], 22) + " " + p["unit"], one(p["name"], 40), one(p["conditions"], 60), "MATCHES LOG" if "MATCHES" in p["status"] else ""))
        print("== pdf pages mentioning it (%d)" % len(r["pdf_pages"]))
        for p in r["pdf_pages"]: print("  %s:%s  %s" % (p["path"], p["page"], one(p["snip"], 120)))
    elif a.cmd == "param":
        rows = kb.params(a.arg, a.part)
        for p in rows[:a.n * 5]: print("%-22s p%-3s %-9s %-14s %s | %s | %s" % (one(p["part"], 22), p["page"], p["symbol"], one(p["value"], 18) + " " + p["unit"], one(p["name"], 36), one(p["conditions"], 50), p["status"]))
        print("(%d rows)" % len(rows))
    elif a.cmd == "fact":
        rows = kb.facts(a.arg, a.n * 10)
        for r in rows: print("%s :: %s = %s %s" % (r["source"], r["key"], one(r["value"], 80), r["unit"]))
        print("(%d rows shown)" % len(rows))
    elif a.cmd == "formula":
        for r in kb.formulas(a.arg, a.n * 5): print("%s:%s [%s] %s" % (r["module"], r["line"], r["context"], one(r["text"], 200)))
    elif a.cmd == "deps":
        r = kb.deps(a.arg)
        print("file: %s\nread by: %s\nwritten by: %s\ndownstream (%d):" % (r["file"], ", ".join(r["read_by"]) or "-", ", ".join(r["written_by"]) or "-", len(r["downstream"])))
        for k, v in r["downstream"].items(): print("  %s  <- %s" % (k, "; ".join(v)))
    elif a.cmd == "gaps":
        g = kb.gaps()
        print("== part numbers in PARTS_RF2 / HANDOFF with no file on disk (%d; token heuristic)" % len(g["parts_without_pdf"]))
        print("  " + ", ".join("%s(%d)" % (x["part"], x["mentions"]) for x in g["parts_without_pdf"]))
        print("== datasheet files not named in DATASHEET_LOG (%d)" % len(g["pdfs_not_in_datasheet_log"]))
        for p in g["pdfs_not_in_datasheet_log"]: print("  " + p)
        print("== UNVERIFIED rows (%d)" % len(g["unverified_rows"]))
        for x in g["unverified_rows"]: print("  [%s | %s] %s" % (x["file"], one(x["section"], 40), one(x["part"], 90)))
        print("== RF2-* log rows naming no file on disk (%d)" % len(g["rf2_log_rows_without_pdf_link"]))
        for x in g["rf2_log_rows_without_pdf_link"]: print("  " + one(x, 110))

if __name__ == "__main__":
    main()
