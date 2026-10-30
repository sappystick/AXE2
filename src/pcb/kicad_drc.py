#!/usr/bin/env python3
"""External DRC with KiCad's own engine (KiCad 9): zones are filled first (pcbnew Python, as a CAM tool would), the filled copy is saved, then `kicad-cli pcb drc` runs on it.
usage: python3 kicad_drc.py board.kicad_pcb out.json BOARD_KEY      BOARD_KEY in dru_gen.py (CB1D LB1 PB1R PM2 HB2 TXJ1) selects the design rules; "-" = KiCad defaults.
Rules are written by dru_gen.py (generic rule first, specific rules last: KiCad lets the last matching rule win) and a project file is created beside the board (kicad-cli
only loads <name>.kicad_dru when <name>.kicad_pro exists). NEGATIVE CONTROL on every run with HV nets: the same board is checked again with a 50 mm HV clearance, which must
produce clearance violations; if it does not, `rules_loaded` is false and the result must not be read as a pass. lib_footprint_issues are counted separately: the generated
footprints are custom (not in a KiCad library). This is the 'KiCad DRC' of OPEN_ITEMS 2; it is not a fabricator's CAM check."""
import sys, json, os, subprocess, collections, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dru_gen
src, out = sys.argv[1], sys.argv[2]; key = sys.argv[3] if len(sys.argv) > 3 else "-"; fill = "--no-fill" not in sys.argv
tmp = tempfile.mkdtemp(); dst = os.path.join(tmp, "b.kicad_pcb"); shutil.copy(src, dst)
def install_rules(rules_text):
    for e in (".kicad_dru", ".kicad_pro"):
        p = os.path.join(tmp, "b" + e)
        if os.path.exists(p): os.remove(p)
    if rules_text is not None:
        open(os.path.join(tmp, "b.kicad_dru"), "w").write(rules_text); open(os.path.join(tmp, "b.kicad_pro"), "w").write("{}")
def fill_zones():
    # the rules are installed BEFORE the fill, so that the planes are carved with the HV clearance exactly as a KiCad user's refill would
    code = f"import pcbnew; b=pcbnew.LoadBoard({dst!r}); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard({dst!r}, b)"
    r = subprocess.run(["/usr/bin/python3", "-c", code], capture_output=True, text=True)
    if r.returncode: print("fill failed", r.stderr[-300:]); sys.exit(2)
    for e in (".kicad_pro", ".kicad_prl"):                       # pcbnew rewrites the project file with defaults: remove it, drc() recreates a minimal one
        p = os.path.join(tmp, "b" + e)
        if os.path.exists(p): os.remove(p)
def drc(rules_text, tag, refill=True):
    install_rules(rules_text)
    if fill and refill: fill_zones(); install_rules(rules_text)
    rep = os.path.join(tmp, f"{tag}.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--all-track-errors", "--format", "json", "--units", "mm", "-o", rep, dst], capture_output=True, text=True)
    return json.load(open(rep))
d = drc(dru_gen.rules(key) if key in dru_gen.BOARDS else None, "main"); V = d.get("violations", [])
cnt = collections.Counter((v["type"], v["severity"]) for v in V)
res = dict(board=os.path.basename(src), board_key=key, kicad=d.get("kicad_version"), zones_filled=fill, violations=len(V), unconnected=len(d.get("unconnected_items", [])),
           errors={a: n for (a, s), n in cnt.items() if s == "error"}, warnings={a: n for (a, s), n in cnt.items() if s == "warning" and a != "lib_footprint_issues"}, lib_footprint_warnings=cnt.get(("lib_footprint_issues", "warning"), 0))
if key in dru_gen.BOARDS and dru_gen.BOARDS[key]["hv"]:
    strict = dict(dru_gen.BOARDS[key], hv_mm=50.0); old = dru_gen.BOARDS[key]; dru_gen.BOARDS[key] = strict
    ctl = drc(dru_gen.rules(key), "control"); dru_gen.BOARDS[key] = old
    nctl = sum(1 for v in ctl["violations"] if v["type"] == "clearance"); res["control_hv50mm_clearance_violations"] = ">100" if nctl > 100 else nctl      # the exact count wobbles by one between KiCad runs: not published
    res["rules_loaded"] = nctl > 0
res["examples"] = [dict(type=v["type"], desc=v["description"], items=[i["description"][:90] for i in v.get("items", [])][:3], pos=v["items"][0]["pos"] if v.get("items") else None) for v in V if v["severity"] == "error"][:8]
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "examples"}))
for e in res["examples"]: print("  ", e["type"], "|", e["desc"][:100], "|", e["items"][:2], e["pos"])
