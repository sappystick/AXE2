#!/usr/bin/env python3
"""KiCad custom design rules (.kicad_dru) per board, in the order KiCad evaluates them: the LAST matching rule wins, so the generic rule comes first and the specific
rules (HV clearance, power track width) after it. The earlier shipped files (mfg_v19.py) ended with an unconditional 0.127 mm rule that overrode both specific rules,
so KiCad never enforced the 1.0 mm high-voltage clearance (negative control in kicad_drc.py history: a 5 mm HV rule produced no violations).
usage: dru_gen.py BOARD OUT.kicad_dru      boards: CB1D LB1 PB1R PM2 HB2 TXJ1 HTA SB1R-QA SB1R-QB   (CLAUDE.md rule 6: coil flyback nets need >= 1.0 mm)"""
import sys
# Fabrication floor for Advanced Circuits (AdvancedPCB) or TTM, designed to the stricter of the two (owner decision 2026-10-24). Vendor numbers, URLs and the
# facility table: docs/design/FAB_RULES_VERIFIED.md (Step 5a, read 2026-10-25). Tightened where a vendor was stricter, kept where the floor was already stricter:
#   clearance 0.16 (AdvancedPCB Orange County standard outer space 1 oz 0.006" = 0.152), track 0.15 (worst standard outer width 0.0055" = 0.140),
#   drill 0.30 (TTM standard through-hole drill 10 mil = 0.254), via annular 0.15 (0.005" = 0.127 both vendors), component-PTH annular 0.18 (AdvancedPCB 0.007" = 0.178)
#   and finished hole 0.46 (smallest standard component PTH 0.018" = 0.457), drill to copper 0.26 (standard 0.010" = 0.254), drill to drill 0.41 (TTM 16 mil same-net
#   guideline = 0.406), copper to edge 0.5 (inner 0.015" = 0.381 required, 0.020" = 0.508 preferred).
# Every rule carries (severity error): kicad_drc.py and the sign-off count errors only, and KiCad reports hole_to_hole as a warning by default.
# The router still designs to 0.2 mm clearance; this file is the floor a fabricator would reject below.
GEN = dict(clearance=0.16, track=0.15, drill=0.3, annular=0.15, edge=0.5, hole_clearance=0.26, hole_to_hole=0.41, pth_annular=0.18, pth_drill=0.46)
BOARDS = {
    # CB1D-B: the MONO_IN coupling tap was removed (it carried the flyback pulse onto a 1.27 mm header and could not meet 1.0 mm)
    "CB1D": dict(hv=["COIL_A", "COIL_B", "DM1", "DM2"], hv_mm=1.0, power={"VBUS_IN": 0.8, "+5V": 0.6, "+5VA": 0.5}),
    "LB1": dict(hv=[], hv_mm=1.0, power={"+5V": 0.4, "GND": 0.4}),
    "PB1R": dict(hv=["DRAIN1", "CLAMP1"], hv_mm=1.0, power={"DRAIN1": 1.5}),
    "PM2": dict(hv=[], hv_mm=1.0, power={"BAT_P": 1.5, "BAT_F": 1.5, "VBUS": 1.0, "GND": 1.0}),      # = the router widths (route_run.py)
    "SB1R-QA": dict(hv=[], hv_mm=1.0, power={}),
    "SB1R-QB": dict(hv=[], hv_mm=1.0, power={}),
    "HB2": dict(hv=[], hv_mm=1.0, power={"P3V3": 0.3}),
    "AU1": dict(hv=[], hv_mm=1.0, power={"VBUS_AU": 0.5, "SW_AU": 0.6, "SPK_P": 0.5, "SPK_N": 0.5}),      # = the router widths (route_run.py)
    "HTA": dict(hv=[], hv_mm=1.0, power={}),
    "TXJ1": dict(hv=["TX_A", "TX_B"], hv_mm=1.0, power={"TX_A": 3.0, "TX_B": 3.0}),
    # Step 12: receive analog boards (low voltage). Router designs to the floor itself for clearance (0.16 mm) and, only here, to the vendors' documented Standard via:
    # drill 0.254 mm (TTM [T-HDI] H, through hole Standard, 10 mil) with a 0.127 mm ring (TTM [T-HDI] I, 10 mil pad over drill; AdvancedPCB [A-TOL] ring >= 0.005"): via 0.508 mm.
    # The other boards keep the conservative 0.30 / 0.15 (0.60 mm). WATCH (docs/design/FAB_RULES_VERIFIED.md): three AdvancedPCB facilities list a 0.216 mm no-breakout ring: settle with U-FAB-DRC.
    "AB1A": dict(hv=[], hv_mm=1.0, power={}, via_drill=0.254, via_annular=0.127),
    "AB1B": dict(hv=[], hv_mm=1.0, power={}, via_drill=0.254, via_annular=0.127),
}
def rules(board):
    b = BOARDS[board]; q = lambda ns: " || ".join(f"A.NetName == '{n}'" for n in ns)
    s = ["(version 1)", f'(rule "general {GEN["clearance"]} mm / {GEN["track"]} mm"', "  (severity error)", f'  (constraint clearance (min {GEN["clearance"]}mm))', f'  (constraint track_width (min {GEN["track"]}mm))', f'  (constraint hole_size (min {b.get("via_drill", GEN["drill"])}mm))', f'  (constraint annular_width (min {b.get("via_annular", GEN["annular"])}mm))', f'  (constraint edge_clearance (min {GEN["edge"]}mm))',
         f'  (constraint hole_clearance (min {GEN["hole_clearance"]}mm))', f'  (constraint hole_to_hole (min {GEN["hole_to_hole"]}mm)))',
         f'(rule "component PTH annular {GEN["pth_annular"]} mm, hole {GEN["pth_drill"]} mm"', "  (severity error)", "  (condition \"A.Pad_Type == 'Through-hole'\")", f'  (constraint annular_width (min {GEN["pth_annular"]}mm))', f'  (constraint hole_size (min {GEN["pth_drill"]}mm)))']
    for n, w in b["power"].items(): s += [f'(rule "power width {n}"', f'  (condition "A.NetName == \'{n}\'")', f'  (constraint track_width (min {w}mm)))']
    if b["hv"]: s += [f'(rule "HV flyback nets {b["hv_mm"]} mm"', f'  (condition "{q(b["hv"])}")', f'  (constraint clearance (min {b["hv_mm"]}mm)))']
    return "\n".join(s) + "\n"
if __name__ == "__main__":
    open(sys.argv[2], "w").write(rules(sys.argv[1])); print("wrote", sys.argv[2])
