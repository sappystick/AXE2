#!/usr/bin/env python3
"""RF2 audio path (2026-10-30, owner: 'which way is better, fewer components, least modification, high quality'). MODELED.
DECISION: keep a magnet-free piezo and move the tones into its band, instead of a class-D amplifier and a magnetic speaker (the ARX AU1 board).
  - Fewest parts: the transducer mounts on the pod board (SMD), driven in BRIDGE from the +5 V rail by two SN74AHCT1G125 buffers (already in the BOM for the
    LED data lines; TTL inputs take the 3.3 V MCU PWM) through one resistor per leg. No amplifier, no boost, no inductor, no wires to a speaker.
  - Least modification: no magnet and no audio-frequency current loop in the handle, so nothing reaches the REF3 EMI reference coil 0.3 m away
    (a speaker voice coil would put the detector's own tones into the canceller) or the upper fluxgate; the pod stays sealed (no speaker cone).
  - Quality: tones live where the part is loud and clean, 3.0-7.6 kHz (square-wave harmonics then fall above 9 kHz, where the part rolls off, so tones
    are close to pure); a per-frequency drive-level table flattens the response, so every class is equally loud.
Transducer: Murata PKLCS1212E4001-R1 (12 x 12 x 3 mm SMD, external drive, 4.0 kHz, 84 dB typ at +-1.5 V0-p, 10 cm; +-12.5 V0-p max). Frequency response READ
from its data-sheet graph (square wave, +-1.5 V0-p, 10 cm). Capacitance is not given: 15 nF ASSUMED (checked 5-30 nF). The part is marked 'to be
discontinued' (last order 3/31/2027): any successor needs only a new RESPONSE table (bench: measure it at 10 cm).
Tones (class by pitch family and rhythm; the same functions feed rf2_ui and rf2_display3):
  ferrous 3.0-3.2 kHz, 25 Hz gated ('buzz'); foil 3.5 kHz with soft edges; non-ferrous 3.8-7.6 kHz rising with the decay constant (10-300 us, one octave);
  sonar ping 7.5 kHz tick (a response peak); 'Depth pitch' profile 7.6 kHz (shallow) -> 3.8 kHz (400 mm); 'Field' profile puts every tone on the 3.3-4.3 kHz resonance at full level.
Writes rf2/results/rf2_audio.json; exits 1 if a check fails.   usage: python3 rf2/rf2_audio.py"""
import os, sys, json, math
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "rf2", "results")
PART = "Murata PKLCS1212E4001-R1"
RESPONSE = [(500, 66), (1000, 72), (1300, 76), (1600, 62), (2000, 64), (2500, 70), (2800, 66), (3000, 76), (3300, 82.5), (3600, 80.5), (4000, 83), (4200, 85.5),
            (4600, 79), (5000, 70), (5500, 70), (6000, 72), (6500, 74), (7000, 77), (7500, 80), (8000, 75), (8500, 63), (9000, 65), (10000, 60)]   # Hz, dB SPL (READ)
V_TEST, V_MAX_0P = 1.5, 12.5                                    # graph drive, absolute max (V0-p)
VCC, R_LEG, C_PIEZO, I_GATE_MAX = 5.0, 680.0, 15e-9, 8e-3      # bridge from +5 V; one resistor per leg; piezo C ASSUMED; SN74AHCT1G125 +-8 mA (SCLS378P)
BAND = (3000.0, 7600.0); EAR_M = 0.6                            # band; ear distance from the pod (ASSUMED)
F_FERROUS, F_FOIL, F_NF, F_PING, F_FIELD = (3000.0, 3200.0), 3500.0, (3800.0, 7600.0), 7500.0, (3300.0, 4300.0)
def spl_test(f):                                                # SPL at 10 cm with the data-sheet drive, log-frequency interpolation
    F, S = np.array(RESPONSE, float).T; return float(np.interp(math.log10(f), np.log10(F), S))
def rc_db(f, c=C_PIEZO):                                        # the series resistors and the piezo capacitance round the edges: first-order loss at the fundamental
    w = 2 * math.pi * f * (2 * R_LEG) * c; return -10 * math.log10(1 + w * w)
def spl_full(f, c=C_PIEZO):                                     # full bridge drive (+-VCC across the part)
    return spl_test(f) + 20 * math.log10(VCC / V_TEST) + rc_db(f, c)
FLOOR = min(spl_full(f) for f in np.geomspace(*BAND, 200))      # the level every tone is equalised to at level 1.0
def duty_for(f, level=1.0, c=C_PIEZO):
    """bridge PWM duty that gives FLOOR + 20 log(level) at f: the square wave's fundamental scales with sin(pi d) (d = 0.5 is full)"""
    a = 10 ** ((FLOOR + 20 * math.log10(max(level, 1e-3)) - spl_full(f, c)) / 20); return float(math.asin(min(1.0, a)) / math.pi)
def tone(cls, tau_us, depth_mm=None, profile="Class tones"):
    """the one tone function (rf2_ui.tone_for and rf2_display3 call it): f_hz, envelope, and the drive duty for level 1"""
    x = min(max((math.log10(max(tau_us, 1.0)) - 1.0) / (math.log10(300.0) - 1.0), 0.0), 1.0)
    if cls == "FERROUS": f, env = F_FERROUS[0] + (F_FERROUS[1] - F_FERROUS[0]) * min(max(math.log10(max(tau_us, 1)) / 2.5, 0), 1), "buzz (25 Hz gate)"
    elif cls == "FOIL": f, env = F_FOIL, "soft (10 ms edges)"
    else: f, env = F_NF[0] * (F_NF[1] / F_NF[0]) ** x, "clear (steady)"
    if profile == "Depth pitch" and depth_mm is not None:
        y = min(max(depth_mm / 400.0, 0.0), 1.0); f = F_NF[1] * (F_NF[0] / F_NF[1]) ** y
    if profile == "Field": f = F_FIELD[0] + (F_FIELD[1] - F_FIELD[0]) * (0.0 if cls == "FERROUS" else 0.5 if cls == "FOIL" else 0.5 + 0.5 * x)
    return dict(f_hz=round(f, 1), timbre=env, duty=round(duty_for(f), 4))
def main():
    res = dict(status="MODELED; response READ from the data-sheet graph; piezo capacitance ASSUMED", part=PART, decision=__doc__.split("DECISION: ")[1].split("\n")[0], checks={})
    taus = (5, 10, 30, 100, 300, 1000)
    tones = {c: [tone(c, t) for t in taus] for c in ("FERROUS", "FOIL", "NONFERROUS")}
    allf = [t["f_hz"] for v in tones.values() for t in v] + [F_PING] + [tone("NONFERROUS", 30, d, "Depth pitch")["f_hz"] for d in (0, 100, 400, 800)] + \
           [tone(c, 30, None, "Field")["f_hz"] for c in ("FERROUS", "FOIL", "NONFERROUS")]
    c = res["checks"]
    c["every tone inside the transducer band"] = all(BAND[0] <= f <= BAND[1] for f in allf)
    c["class families apart (ferrous < foil < non-ferrous, >= 1 semitone)"] = max(t["f_hz"] for t in tones["FERROUS"]) * 2 ** (1 / 12) <= F_FOIL <= min(t["f_hz"] for t in tones["NONFERROUS"]) / 2 ** (1 / 12)
    nf = [t["f_hz"] for t in tones["NONFERROUS"]]; c["non-ferrous pitch rises with decay constant"] = all(a <= b for a, b in zip(nf, nf[1:])) and nf[-1] > nf[0]
    grid = np.geomspace(*BAND, 120); eq = [spl_full(f) + 20 * math.log10(math.sin(math.pi * duty_for(f)) + 1e-12) for f in grid]
    c["equalised to within 0.5 dB over the band"] = max(eq) - min(eq) <= 0.5
    sens = {f"{cc * 1e9:.0f} nF": round(min(spl_full(f, cc) for f in grid), 1) for cc in (5e-9, 15e-9, 30e-9)}
    c["floor >= 78 dB at 10 cm at the nominal 15 nF"] = sens["15 nF"] >= 78.0
    c["floor >= 75 dB at 10 cm (about 60 dB at the ear) for piezo C 5-30 nF"] = min(sens.values()) >= 75.0
    i_pk = 2 * VCC / (2 * R_LEG); c["buffer peak current within SN74AHCT1G125 +-8 mA"] = i_pk <= I_GATE_MAX
    c["drive within the part's +-12.5 V0-p"] = VCC <= V_MAX_0P
    p_drive = C_PIEZO * (2 * VCC) ** 2 * BAND[1]; c["drive power under 20 mW"] = p_drive < 0.02
    res.update(band_hz=BAND, floor_dB_10cm=round(FLOOR, 1), floor_dB_at_ear=round(FLOOR - 20 * math.log10(EAR_M / 0.1), 1), floor_vs_piezo_C=sens,
               buffer_peak_mA=round(i_pk * 1e3, 2), drive_mW_max=round(p_drive * 1e3, 1), tones=tones, ping_hz=F_PING,
               eq_table=[dict(f_hz=round(f), spl_full_dB=round(spl_full(f), 1), duty=round(duty_for(f), 4)) for f in np.geomspace(*BAND, 12)],
               bom=["PKLCS1212E4001-R1 piezo (SMD, on the pod board)", "2 x SN74AHCT1G125 (bridge legs, complementary PWM from one MCU PWM slice)", f"2 x {R_LEG:.0f} ohm 0603"],
               compared=dict(class_D_speaker="ARX AU1: TPA2005D1-class amplifier + magnetic speaker: wider band but about 8-10 more parts, a speaker cone in the sealed pod, "
                                                 "and an audio-frequency magnetic dipole 0.3 m from REF3 (couples the tones into the EMI canceller)",
                             piezo_bridge="3 parts plus the transducer, magnet-free, 7-12 mW; band 3-8 kHz; the 'Stereo' profile is replaced by 'Field' (one transducer)"))
    res["all_pass"] = all(c.values())
    json.dump(res, open(os.path.join(OUT, "rf2_audio.json"), "w"), indent=1)
    print(f"floor {FLOOR:.1f} dB at 10 cm, {res['floor_dB_at_ear']} dB at {EAR_M} m; vs C {sens}; buffer {i_pk*1e3:.2f} mA; drive {p_drive*1e3:.1f} mW")
    for k, v in tones.items(): print(" ", k, [t["f_hz"] for t in v])
    for k, v in c.items(): print(("  PASS " if v else "  FAIL ") + k)
    return res
if __name__ == "__main__":
    sys.exit(0 if main()["all_pass"] else 1)
