#!/usr/bin/env python3
"""RF2 user interface model (2026-10-30): how a detected signature becomes light and sound, the 3-position mode selector and the trigger. MODELED: a specification with
checks, not a measurement of what a person sees or hears. The detection fields come from the pipeline of rf2_decaylib.py (decay-curve classes) and the quadrupole
bearing boards (position); nothing here is bench data.
Mode selector (3 positions, left to right): AUDIO | LED | BOTH (coupled). Trigger: HOLD = pinpoint / enhanced projection; DOUBLE-PRESS = set signature.
Audio is silent until a signature is detected (a detection above the confidence threshold); with no detection the display is dark too.
Coding (redundant, so colour is never the only channel):
  class      -> hue (display) and timbre + pitch family (audio);  size (mass-equivalent) -> brightness and loudness;  depth -> ripple speed and beep rate (shallow = fast)
  FERROUS red 0 deg, buzz 3.0-3.2 kHz (25 Hz gate);  FOIL / thin ring violet 280 deg, soft 3.5 kHz;  NONFERROUS hue by decay time tau: 10 us gold-yellow 50 deg -> 100 us green
  about 150 deg -> 300 us cyan-blue 200 deg, pitch 3.8 -> 7.6 kHz with tau (tones in the piezo band since 2026-10-30, rf2_audio.py; were 150-1200 Hz) (the decay class, not the metal: conductivity x size^2 is ambiguous, rf2_decaylib / DECAY_LIBRARY.md)
Reactive wave map: a ripple spreads from the target's position over the 522 LEDs (13 rings); when the head is centred over it the ripple collapses to the centre ring (bullseye).
LEDs are written only in the quiet slot after the last gate and are dark in receive windows (rf2_timing / HANDOFF); this model gives the frame content, not the timing.
Writes out/rf2_ui.json, out/rf2_ui_wavemap.png, out/audio_*.wav.   usage: python3 rf2/rf2_ui.py"""
import os, sys, json, math, wave, struct
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "rf2", "head")); sys.path.insert(0, os.path.join(ROOT, "rf2"))
import rf2_audio as AU
OUT = os.path.join(ROOT, "rf2", "head", "out"); os.makedirs(OUT, exist_ok=True)
MODES = ("AUDIO", "LED", "BOTH")
CONF_MIN = 0.5                      # detections below this confidence stay silent and dark (ASSUMED; set from the bench false-alarm rate)
BULLSEYE_MM = 12.0                  # target within this distance of the head centre: the ripple collapses to the centre ring (ASSUMED, a quarter of a 48 mm ring step)
def hue_for(cls, tau_us):
    if cls == "FERROUS": return 0.0
    if cls == "FOIL": return 280.0
    x = (math.log10(max(tau_us, 1.0)) - 1.0) / (math.log10(300.0) - 1.0)                                  # 10 us -> 0, 300 us -> 1
    x = min(max(x, 0.0), 1.0); return 50.0 + 150.0 * x if x > 0 else 50.0                                  # 50 gold-yellow -> 200 cyan-blue (passes green at about x = 0.5)
def brightness_for(mass_g): return min(max(0.25 + 0.75 * math.log10(max(mass_g, 0.1) / 0.1) / math.log10(200.0), 0.25), 1.0)       # 0.1 g -> 0.25, 20 g -> 0.25 + 0.75 x 0.77 .. 200 g -> 1.0
def speed_for(depth_mm): return max(1.5, 12.0 * math.exp(-depth_mm / 200.0))                              # ripple speed, rings per second: 12 at the surface, 1.5 floor
def beep_rate_for(depth_mm): return 2.0 + 14.0 * math.exp(-depth_mm / 180.0)                              # beeps per second: shallow = fast
def tone_for(cls, tau_us):
    """the tones live in the piezo's band (rf2_audio.py, 2026-10-30: magnet-free piezo in bridge drive, 3.0-7.6 kHz, equalised); this delegates to it"""
    return AU.tone(cls, tau_us)
def hsv(h, s, v):
    import colorsys; return colorsys.hsv_to_rgb((h % 360) / 360.0, s, v)
class Det:
    def __init__(self, cls, depth_mm, mass_g, tau_us, az_deg, off_mm, conf=0.9): self.cls, self.depth, self.mass, self.tau, self.az, self.off, self.conf = cls, depth_mm, mass_g, tau_us, az_deg, off_mm, conf
def state(det, mode, trigger_hold=False, accept=None):
    """-> dict of what the display and the sounder do. accept: stored signature (cls, tau_us, tol) set by the double-press; a non-matching target is toned down"""
    assert mode in MODES
    if det is None or det.conf < CONF_MIN: return dict(detected=False, audio=None, led=None)
    match = None
    if accept is not None: match = det.cls == accept[0] and abs(math.log10(det.tau / accept[1])) <= accept[2]
    dim = 0.35 if (accept is not None and not match) else 1.0
    st = dict(detected=True, match=match, pinpoint=trigger_hold)
    st["led"] = None if mode == "AUDIO" else dict(hue=hue_for(det.cls, det.tau), value=brightness_for(det.mass) * dim, speed_rings_s=speed_for(det.depth) * (1.5 if trigger_hold else 1.0),
                                                   bullseye=det.off <= BULLSEYE_MM, centre_mm=(det.off * math.cos(math.radians(det.az)), det.off * math.sin(math.radians(det.az))))
    t = tone_for(det.cls, det.tau)
    st["audio"] = None if mode == "LED" else dict(f_hz=t["f_hz"], timbre=t["timbre"], level=(0.2 + 0.8 * (brightness_for(det.mass) - 0.25) / 0.75) * dim, beeps_per_s=beep_rate_for(det.depth), phase_locked_to_led=(mode == "BOTH"))
    return st
def wave_frame(st, led_xy, ring_r, t):
    """RGB for every LED at time t (s): a ripple from the target; ring step 8 mm; wavelength 24 mm (3 rings), width 6 mm; bullseye collapses to the centre."""
    rgb = np.zeros((len(led_xy), 3))
    if not st["detected"] or st["led"] is None: return rgb
    L = st["led"]; cx, cy = L["centre_mm"]; rho = np.hypot(led_xy[:, 0] - cx, led_xy[:, 1] - cy); lam, w = 24.0, 6.0; v_mm = L["speed_rings_s"] * 8.0
    ph = (rho + v_mm * t) % lam if L["bullseye"] else (rho - v_mm * t) % lam              # bullseye: the ripple moves inward
    amp = np.exp(-(np.minimum(ph, lam - ph) / w) ** 2) * np.exp(-rho / 90.0)
    core = np.exp(-(rho / 5.0) ** 2) * (1.0 if L["bullseye"] else 0.6)                       # the target itself stays lit; solid + white-ish at the bullseye
    I = np.clip(0.75 * amp + core, 0, 1) * L["value"]
    base = np.array(hsv(L["hue"], 1.0, 1.0)); rgb = I[:, None] * base[None, :]
    if L["bullseye"]: rgb = rgb + (np.exp(-(rho / 5.0) ** 2) * 0.35 * L["value"])[:, None]
    return np.clip(rgb, 0, 1)
def synth(st, secs=1.2, sr=48000, seed=0):
    a = st["audio"]; n = int(secs * sr); t = np.arange(n) / sr; y = np.zeros(n)
    if a is None: return y
    period = 1.0 / a["beeps_per_s"]; env = np.zeros(n)
    for k in range(int(secs / period) + 1):
        t0 = k * period; m = (t >= t0) & (t < t0 + min(0.07, period * 0.6)); x = (t[m] - t0) / 0.07
        env[m] = np.sin(np.pi * np.clip(x, 0, 1)) ** 0.7
    f = a["f_hz"]; d = AU.duty_for(f, 1.0)                                           # what the bridge drives: a square wave at f with the equalising duty
    s = np.where(((t * f) % 1.0) < d, 1.0, 0.0) - np.where((((t * f) + 0.5) % 1.0) < d, 1.0, 0.0)
    if a["timbre"].startswith("buzz"): s = s * (((t * 25.0) % 1.0) < 0.5)               # 25 Hz gate
    elif a["timbre"].startswith("soft"): env = np.convolve(env, np.ones(int(0.01 * sr)) / int(0.01 * sr), mode="same")   # 10 ms edges
    return 0.8 * a["level"] * env * s
def write_wav(path, y, sr=48000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32000)) for v in y))
CASES = {
    "deep iron nail": Det("FERROUS", 350, 3, 40, 40, 70),
    "small gold, shallow": Det("NONFERROUS", 80, 0.5, 14, 200, 55),
    "large silver, mid": Det("NONFERROUS", 250, 20, 150, 300, 40),
    "big copper, deep": Det("NONFERROUS", 420, 100, 280, 120, 60),
    "foil / thin ring": Det("FOIL", 120, 1, 30, 250, 30),
    "gold, head centred": Det("NONFERROUS", 90, 2, 20, 0, 6),
}
def main():
    import rf2_ledgrid as LG
    lay = LG.layout()["leds"]; xy = np.array([(e["x"], e["y"]) for e in lay]); res = dict(status="MODELED specification (no human-factors or bench data)", checks={}, coding={})
    # --- checks of the mapping
    c = {}
    c["silent_without_detection"] = state(None, "BOTH")["audio"] is None and state(None, "BOTH")["led"] is None and state(Det("FERROUS", 100, 1, 30, 0, 50, conf=0.2), "BOTH")["audio"] is None
    c["audio_mode_has_no_light"] = state(CASES["small gold, shallow"], "AUDIO")["led"] is None and state(CASES["small gold, shallow"], "AUDIO")["audio"] is not None
    c["led_mode_has_no_sound"] = state(CASES["small gold, shallow"], "LED")["audio"] is None and state(CASES["small gold, shallow"], "LED")["led"] is not None
    sb = state(CASES["small gold, shallow"], "BOTH"); c["both_is_phase_locked"] = sb["audio"]["phase_locked_to_led"] and sb["led"] is not None
    ds = [30, 100, 200, 400]; c["depth_monotonic"] = all(speed_for(a) > speed_for(b) and beep_rate_for(a) > beep_rate_for(b) for a, b in zip(ds[:-1], ds[1:]))
    ms = [0.1, 1, 10, 100]; c["size_monotonic"] = all(brightness_for(a) < brightness_for(b) for a, b in zip(ms[:-1], ms[1:]))
    hues = {"FERROUS": hue_for("FERROUS", 40), "FOIL": hue_for("FOIL", 30), "NF_low": hue_for("NONFERROUS", 10), "NF_mid": hue_for("NONFERROUS", 100), "NF_high": hue_for("NONFERROUS", 300)}
    hv = sorted(hues.values()); gaps = [min(abs(a - b), 360 - abs(a - b)) for i, a in enumerate(hv) for b in hv[i + 1:]]
    c["hues_distinct_30deg"] = min(gaps) >= 30.0; c["hues"] = {k: round(v, 1) for k, v in hues.items()}
    f_nf = [tone_for("NONFERROUS", t)["f_hz"] for t in (10, 30, 100, 300)]; c["pitch_rises_with_tau"] = all(a < b for a, b in zip(f_nf[:-1], f_nf[1:]))
    c["class_pitch_families_apart"] = tone_for("FERROUS", 300)["f_hz"] * 2 ** (1 / 12) <= tone_for("FOIL", 30)["f_hz"] <= min(f_nf) / 2 ** (1 / 12) and tone_for("FERROUS", 40)["timbre"] != tone_for("FOIL", 30)["timbre"]
    c["tones_inside_transducer_band"] = all(AU.BAND[0] <= tone_for(k, t)["f_hz"] <= AU.BAND[1] for k in ("FERROUS", "FOIL", "NONFERROUS") for t in (3, 10, 30, 100, 300, 3000))
    acc = ("NONFERROUS", 20.0, 0.15); c["signature_set"] = (state(Det("NONFERROUS", 90, 2, 21, 0, 6), "BOTH", accept=acc)["match"] is True and state(Det("NONFERROUS", 90, 2, 150, 0, 6), "BOTH", accept=acc)["match"] is False
                                                               and state(Det("NONFERROUS", 90, 2, 150, 0, 6), "BOTH", accept=acc)["led"]["value"] < state(Det("NONFERROUS", 90, 2, 21, 0, 6), "BOTH", accept=acc)["led"]["value"])
    c["pinpoint_faster"] = state(CASES["small gold, shallow"], "LED", trigger_hold=True)["led"]["speed_rings_s"] > state(CASES["small gold, shallow"], "LED")["led"]["speed_rings_s"]
    f0 = wave_frame(state(None, "BOTH"), xy, None, 0.3); c["dark_when_idle"] = float(f0.max()) == 0.0
    fb = wave_frame(state(CASES["gold, head centred"], "LED"), xy, None, 0.2); cen = np.hypot(xy[:, 0], xy[:, 1]) < 9.0
    c["bullseye_lights_centre_ring"] = bool(state(CASES["gold, head centred"], "LED")["led"]["bullseye"] and fb[cen].max() > fb[~cen].mean() * 2.0)
    c["frames_deterministic"] = bool(np.array_equal(wave_frame(sb, xy, None, 0.37), wave_frame(sb, xy, None, 0.37)))
    res["checks"] = c; res["ok"] = all(v for k, v in c.items() if isinstance(v, bool))
    res["cases"] = {k: state(d, "BOTH") for k, d in CASES.items()}
    res["controls"] = dict(selector="3-position detent: AUDIO | LED | BOTH (coupled); BOTH locks the ripple emission to the beep onset", trigger_hold="PINPOINT / enhanced projection: 1.5x ripple rate and, in the detector, more pulses averaged (rf2_depth_levers: 400 pulses = about +13 % depth on 1 g)",
                           trigger_double="SET SIGNATURE: store the current target's class and tau (+- 0.15 decade); matches get the full light and sound, others 35 % level",
                           audio_location="in the handle pod (rf2_pod.py), not in the head: a loudspeaker magnet or a ferrite is a metal target next to the coil; a piezo or a remote sounder is magnet-free")
    # --- figure: the wave map for each case at one instant, plus the 3 colour/pitch legends
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(13, 9), facecolor="#101012")
    for a, (name, d) in zip(ax.ravel(), CASES.items()):
        st = state(d, "BOTH"); fr = wave_frame(st, xy, None, 0.25); a.set_facecolor("#08080a")
        a.scatter(xy[:, 0], xy[:, 1], s=95, c="#1c1c20", edgecolors="#2a2a30", linewidths=0.6)                  # the dark plate with the 522 conical wells
        lit = fr.max(axis=1) > 0.02; a.scatter(xy[lit, 0], xy[lit, 1], s=95, c=fr[lit], edgecolors="none")
        a.set_title(f"{name}\n{d.cls}, {d.depth} mm, {d.mass} g, tau {d.tau} us -> hue {st['led']['hue']:.0f} deg, {st['led']['speed_rings_s']:.1f} rings/s, {st['audio']['f_hz']:.0f} Hz x {st['audio']['beeps_per_s']:.1f}/s", color="w", fontsize=8)
        a.set_aspect("equal"); a.axis("off")
    fig.suptitle("RF2 wave map (modeled): 522 LEDs in conical wells; colour = class, brightness = size, ripple speed and beep rate = depth", color="w"); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "rf2_ui_wavemap.png"), dpi=110, facecolor=fig.get_facecolor()); plt.close(fig)
    for name in ("deep iron nail", "small gold, shallow", "large silver, mid"): write_wav(os.path.join(OUT, "audio_" + name.split(",")[0].replace(" ", "_") + ".wav"), synth(state(CASES[name], "BOTH")))
    json.dump(res, open(os.path.join(OUT, "rf2_ui.json"), "w"), indent=1, default=lambda o: bool(o) if isinstance(o, np.bool_) else str(o))
    print(json.dumps({k: v for k, v in res["checks"].items()}, indent=1)); return res
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
