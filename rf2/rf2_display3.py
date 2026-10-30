#!/usr/bin/env python3
"""RF2 display and audio v3 (2026-10-30, owner): clean, adaptive, and one timeline for light and sound. MODELED specification with checks; no human-factors test.
SWEEP (trigger released): dark until a signature. Each target is a SMALL dot at its place under the head (1-3 rings by size, breathing at its depth rate). When a target is
  centred (within 12 mm of the head centre) the display LOCKS: the central disc (r 16 mm, rings 1-2) fills solid in the class colour, a white ring flashes once on acquisition,
  other targets dim to half. Audio: a short beep per target at its depth rate and class pitch; on lock a steady pulsing tone.
PINPOINT (trigger held, boost): a SONAR ring leaves the centre, runs out to the rim (0.6 s) and comes back (0.6 s), forever. Where the ring crosses a target the target flashes
  (an 'echo') and the sounder plays that target's echo blip at the same instant; every ring launch plays a soft ping. Targets therefore light and sound in order of their
  distance from the centre: two targets are separated in TIME as well as in place. Centre the head on one and the lock fills the centre as in the sweep.
PROFILES (chosen on the flip-up screen, rf2_pod.py): LED 'Clean' (default, as above), 'Map' (rf2_display.py v2 blobs: size = rings lit), 'Sonar' (the ring also while sweeping),
  'Night' (Clean at 25 % and no status screens except lock); audio 'Class tones' (pitch = class, rate = depth; default), 'Depth pitch' (pitch falls with depth, class by
  timbre), 'Quiet' (only lock and strong targets), 'Stereo' (headphones: each target panned by its bearing).
Writes rf2/head/out/rf2_display3.json, rf2_display3_frames.png, rf2_screen_mockup.png.   usage: python3 rf2/rf2_display3.py"""
import os, sys, json, math
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path[:0] = [os.path.join(ROOT, "rf2"), os.path.join(ROOT, "rf2", "head")]
import rf2_ui as U
import rf2_display as D
OUT = os.path.join(ROOT, "rf2", "head", "out")
R_MAX, RING, LOCK_MM, LOCK_R, PERIOD, RING_W, ECHO_S = 104.0, 8.0, 12.0, 16.0, 1.2, 5.0, 0.15
LED_PROFILES = ("Clean", "Map", "Sonar", "Night"); AUDIO_PROFILES = ("Class tones", "Depth pitch", "Quiet", "Stereo")
def dot_radius(mass_g): return RING * min(3, max(1, 1 + int(math.log10(max(mass_g, 0.1)) + 1)))       # 1 ring < 1 g, 2 rings 1-10 g, 3 rings >= 10 g
def col(tg): return np.array(U.hsv(U.hue_for(tg["cls"], tg["tau_us"]), 1.0, 1.0))
def strength(tg): return tg["mass_g"] / (1 + tg["depth_mm"] / 100.0) ** 6
def locked(targets):
    c = [tg for tg in targets if math.hypot(tg["x_mm"], tg["y_mm"]) <= LOCK_MM]
    return max(c, key=strength) if c else None
def ring_radius(t): ph = (t % PERIOD) / PERIOD; return R_MAX * (2 * ph if ph < 0.5 else 2 * (1 - ph))   # out and back
def echo_times(tg, n_cycles=3):
    rho = min(math.hypot(tg["x_mm"], tg["y_mm"]), R_MAX); f = rho / R_MAX * PERIOD / 2
    return sorted([k * PERIOD + f for k in range(n_cycles)] + [k * PERIOD + PERIOD - f for k in range(n_cycles)])
def _dot(xy, tg, inten, r=None):
    rho = np.hypot(xy[:, 0] - tg["x_mm"], xy[:, 1] - tg["y_mm"]); r = dot_radius(tg["mass_g"]) if r is None else r
    m = rho <= r; m[np.argsort(rho)[:3]] = True                                 # never smaller than the 3 nearest LEDs (the grid is 8 mm: a 1-ring dot can fall between LEDs)
    return m[:, None] * col(tg)[None, :] * inten
def frame(targets, xy, t, trigger=False, profile="Clean", t_lock=None):
    """RGB per LED. t_lock: time the current lock was acquired (for the one-shot white ring)"""
    if profile == "Map" and not trigger: return D.frame(targets, xy, t)
    rgb = np.zeros((len(xy), 3)); r = np.hypot(xy[:, 0], xy[:, 1]); gain = 0.25 if profile == "Night" else 1.0
    lk = locked(targets)
    if trigger or profile == "Sonar":
        rr = ring_radius(t); rgb[np.abs(r - rr) < RING_W] = np.array([0.15, 0.35, 0.4]) * gain
    for tg in targets:
        if lk is not None and tg is lk: continue
        breathe = 0.6 + 0.4 * math.sin(2 * math.pi * D.pulse_hz(tg["depth_mm"]) * t); base = (0.5 if lk is not None else 1.0) * breathe * (0.35 + 0.65 * tg.get("conf", 0.9))
        if trigger or profile == "Sonar":
            dt = min([abs(t - e) for e in echo_times(tg, int(t / PERIOD) + 2)] + [9])
            base = 0.4 * base + (1.0 if dt < ECHO_S else 0.0) * math.exp(-dt / 0.06)
        rgb = np.maximum(rgb, _dot(xy, tg, base * gain))
    if lk is not None:
        rgb = np.maximum(rgb, (r <= LOCK_R)[:, None] * col(lk)[None, :] * (0.75 + 0.25 * math.sin(2 * math.pi * 1.0 * t)) * gain)
        if t_lock is not None and 0 <= t - t_lock < 0.25: rgb[np.abs(r - (LOCK_R + 6)) < 3] = 0.9 * gain
    return np.clip(rgb, 0, 1)
def audio_events(targets, t0, t1, trigger=False, profile="Class tones", led_profile="Clean"):
    """every sound on the same clock as the LEDs: pings at ring launch, echo blips at the ring crossings, beeps at depth rate in the sweep, the lock tone"""
    ev = []; lk = locked(targets)
    def tone(tg):
        tn = U.tone_for(tg["cls"], tg["tau_us"])
        if profile == "Depth pitch": tn = dict(tn, f_hz=round(1200.0 * math.exp(-tg["depth_mm"] / 250.0) + 200.0, 1))
        return tn
    def keep(tg): return profile != "Quiet" or tg is lk or tg["mass_g"] >= 5.0
    pan = lambda tg: round(math.sin(math.atan2(tg["y_mm"], tg["x_mm"])), 3) if profile == "Stereo" else 0.0
    if trigger or led_profile == "Sonar":
        k = math.ceil(t0 / PERIOD)
        while k * PERIOD < t1:
            if profile != "Quiet": ev.append(dict(kind="ping", t=round(k * PERIOD, 4), f_hz=1800.0, dur=0.03, level=0.25, pan=0.0))
            k += 1
        for tg in targets:
            if tg is lk or not keep(tg): continue
            for e in echo_times(tg, int(t1 / PERIOD) + 2):
                if t0 <= e < t1: tn = tone(tg); ev.append(dict(kind="echo", target=tg["id"], t=round(e, 4), f_hz=tn["f_hz"], timbre=tn["timbre"], dur=0.04, level=round(0.3 + 0.7 * min(1, tg["mass_g"] / 20), 3), pan=pan(tg)))
    else:
        for e in D.audio_schedule([tg for tg in targets if tg is not lk and keep(tg)], "BOTH", cycle_s=0.6):
            tg = next(x for x in targets if x["id"] == e["target"])
            for c in range(int((t1 - t0) / 0.6) + 1):
                tt = t0 + c * 0.6 + e["t0"]
                if tt < t1: ev.append(dict(kind="beep", target=e["target"], t=round(tt, 4), f_hz=tone(tg)["f_hz"], timbre=e["timbre"], dur=e["dur"], level=e["level"] * (0.5 if lk else 1.0), pan=pan(tg)))
    if lk is not None:
        rate = U.beep_rate_for(lk["depth_mm"]); n = int((t1 - t0) * rate)
        for j in range(n): ev.append(dict(kind="lock", target=lk["id"], t=round(t0 + j / rate, 4), f_hz=tone(lk)["f_hz"], dur=0.08, level=0.9, pan=0.0))
    return sorted(ev, key=lambda e: e["t"])
SCREEN_COLS = 23                                                                # 128 px / about 5.4 px per character of a 9 px monospaced font
def screen_text(tg, mode, led_profile, audio_profile, battery=0.72):
    """what the flip-up screen shows for the strongest target (depth and size are firmware estimates; the class is the decay class, not a guaranteed metal)"""
    head = "%3d%% %s %s/%s" % (battery * 100, {"PINPOINT": "PIN", "SWEEP": "SCAN"}.get(mode, mode[:4]), led_profile[:5], audio_profile.split()[0][:5])
    if tg is None: return [head, "", "no target", "", "", ""]
    name = {"FERROUS": "IRON", "FOIL": "FOIL / RING"}.get(tg["cls"], "NON-FERROUS " + ("LOW" if tg["tau_us"] < 40 else ("MID" if tg["tau_us"] < 150 else "HIGH")))
    where = "LOCK" if math.hypot(tg["x_mm"], tg["y_mm"]) <= LOCK_MM else "BEARING %d deg" % (math.degrees(math.atan2(tg["y_mm"], tg["x_mm"])) % 360)
    return [head, "DEPTH %d mm" % tg["depth_mm"], "SIZE ~%g g eq." % tg["mass_g"], name, "tau %d us conf %d%%" % (tg["tau_us"], tg.get("conf", 0.9) * 100), where]
def render_screen(path):
    """mock-ups of a 128 x 128 reflective memory LCD (Sharp LS013B7DH03 class, 1.28 in; part UNVERIFIED): the target page and the settings page"""
    from PIL import Image, ImageDraw, ImageFont
    f = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"; big = ImageFont.truetype(f, 15); sm = ImageFont.truetype(f, 9)
    tg = dict(id=1, cls="NONFERROUS", depth_mm=142, mass_g=1, tau_us=24, x_mm=4, y_mm=3, conf=0.92)
    pages = []
    im = Image.new("1", (128, 128), 1); d = ImageDraw.Draw(im); L = screen_text(tg, "PINPOINT", "Clean", "Class tones")
    d.text((2, 1), L[0], font=sm, fill=0); d.line((0, 12, 127, 12), fill=0); d.text((2, 16), "142 mm", font=big, fill=0); d.text((2, 36), "~1 g eq.", font=big, fill=0)
    d.text((2, 58), "NON-FERROUS LOW", font=sm, fill=0); d.text((2, 70), "tau 24 us", font=sm, fill=0); d.rectangle((2, 84, 2 + int(0.92 * 80), 92), fill=0); d.rectangle((2, 84, 82, 92), outline=0)
    d.text((86, 83), "92%", font=sm, fill=0); d.ellipse((96, 98, 124, 126), outline=0); d.ellipse((108, 110, 112, 114), fill=0); d.text((2, 104), "LOCK", font=big, fill=0); pages.append(im)
    im = Image.new("1", (128, 128), 1); d = ImageDraw.Draw(im); d.text((2, 1), "SETTINGS", font=sm, fill=0); d.line((0, 12, 127, 12), fill=0)
    y = 16
    for title, opts, sel in (("LED", LED_PROFILES, 0), ("AUDIO", AUDIO_PROFILES, 0)):
        d.text((2, y), title, font=sm, fill=0); y += 11
        for k, o in enumerate(opts):
            if k == sel: d.rectangle((0, y - 1, 127, y + 9), fill=0); d.text((6, y), "> " + o, font=sm, fill=1)
            else: d.text((6, y), "  " + o, font=sm, fill=0)
            y += 11
    pages.append(im)
    W = Image.new("L", (128 * 2 * 3 + 30, 128 * 3 + 20), 40)
    for k, p in enumerate(pages): W.paste(p.convert("L").resize((384, 384), Image.NEAREST), (10 + k * 394, 10))
    W.save(path)
def main():
    import rf2_ledgrid as LG
    xy = np.array([(e["x"], e["y"]) for e in LG.layout()["leds"]]); r = np.hypot(xy[:, 0], xy[:, 1]); c = {}
    g1 = dict(id=1, cls="NONFERROUS", depth_mm=150, mass_g=1, tau_us=28, x_mm=45, y_mm=30, conf=0.9)
    big = dict(id=2, cls="NONFERROUS", depth_mm=200, mass_g=60, tau_us=200, x_mm=-40, y_mm=-35, conf=0.9)
    g_lock = dict(g1, x_mm=5, y_mm=4)
    two = [dict(id=1, cls="NONFERROUS", depth_mm=80, mass_g=0.5, tau_us=14, x_mm=-30, y_mm=10, conf=0.9), dict(id=2, cls="FERROUS", depth_mm=180, mass_g=3, tau_us=40, x_mm=60, y_mm=-40, conf=0.85)]
    c["dark_without_target"] = float(frame([], xy, 0.4).max()) == 0.0 and audio_events([], 0, 2) == []
    c["every_target_visible"] = all(int((frame([dict(g1, mass_g=0.1, x_mm=x, y_mm=y)], xy, 0.1).max(axis=1) > 0.05).sum()) >= 3 for x, y in ((-30, 10), (3, 70), (-90, -20), (50, 50)))
    lit = frame([g1], xy, 0.1).max(axis=1) > 0.05; c["sweep_dot_is_small"] = bool(lit.sum() > 0 and np.hypot(xy[lit, 0] - 45, xy[lit, 1] - 30).max() <= 3 * RING + 0.1)
    litb = frame([big], xy, 0.1).max(axis=1) > 0.05; c["bigger_target_bigger_dot_but_capped"] = bool(litb.sum() > lit.sum() and np.hypot(xy[litb, 0] + 40, xy[litb, 1] + 35).max() <= 3 * RING + 0.1)
    fl = frame([g_lock], xy, 0.3, t_lock=0.25); litl = fl.max(axis=1) > 0.05; c["lock_fills_only_the_centre"] = bool(litl.sum() > 0 and r[litl].max() <= LOCK_R + 9 + 0.1 and np.all(fl[r <= LOCK_R].max(axis=1) > 0.3))
    c["sonar_goes_out_and_back"] = abs(ring_radius(PERIOD / 4) - R_MAX / 2) < 1e-6 and abs(ring_radius(PERIOD / 2) - R_MAX) < 1e-6 and abs(ring_radius(3 * PERIOD / 4) - R_MAX / 2) < 1e-6 and ring_radius(PERIOD) < 1e-6
    e = echo_times(g1, 2)[0]; f_on = frame([g1], xy, e, trigger=True); f_off = frame([g1], xy, e + 0.3, trigger=True); m = np.hypot(xy[:, 0] - 45, xy[:, 1] - 30) <= RING
    c["echo_flash_when_ring_crosses"] = bool(f_on[m].max() > 1.5 * f_off[m].max())
    ev = audio_events([g1], 0, 2.4, trigger=True); c["audio_echo_at_the_flash_instant"] = all(any(abs(x["t"] - t_) < 1e-3 for x in ev if x["kind"] == "echo") for t_ in echo_times(g1, 2))
    c["ping_at_every_launch"] = [x["t"] for x in ev if x["kind"] == "ping"] == [0.0, 1.2]
    et = sorted((x["t"], x["target"]) for x in audio_events(two, 0, 1.2, trigger=True) if x["kind"] == "echo"); c["two_targets_echo_in_distance_order"] = [k for _, k in et][:2] == [1, 2]
    c["lock_has_steady_tone"] = any(x["kind"] == "lock" for x in audio_events([g_lock], 0, 1)) and not any(x["kind"] == "beep" and x["target"] == 1 for x in audio_events([g_lock], 0, 1))
    c["profiles_render"] = all(frame(two, xy, 0.3, profile=p).shape == (len(xy), 3) for p in LED_PROFILES) and all(isinstance(audio_events(two, 0, 1, profile=p), list) for p in AUDIO_PROFILES)
    c["night_is_dim"] = frame([g1], xy, 0.1, profile="Night").max() <= 0.26
    c["quiet_skips_small_targets"] = not any(x.get("target") == 1 for x in audio_events(two, 0, 2, profile="Quiet"))
    c["depth_pitch_falls_with_depth"] = audio_events([dict(g1, depth_mm=50)], 0, 1, profile="Depth pitch")[0]["f_hz"] > audio_events([dict(g1, depth_mm=300)], 0, 1, profile="Depth pitch")[0]["f_hz"]
    st = screen_text(g_lock, "PINPOINT", "Clean", "Class tones"); c["screen_text_fits_and_shows_lock"] = all(len(l) <= SCREEN_COLS for l in st) and st[5] == "LOCK" and all(len(l) <= SCREEN_COLS for l in screen_text(g1, "SWEEP", "Night", "Depth pitch"))
    res = dict(status="MODELED specification (no human-factors or bench data)", checks=c, ok=all(c.values()),
               timing=dict(sonar_period_s=PERIOD, out_s=PERIOD / 2, back_s=PERIOD / 2, ring_width_mm=RING_W, echo_flash_s=ECHO_S, lock_radius_mm=LOCK_MM, lock_disc_mm=LOCK_R),
               profiles=dict(led=list(LED_PROFILES), audio=list(AUDIO_PROFILES)))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    panels = [("sweep: 1 g gold off-centre", lambda: frame([g1], xy, 0.1)), ("sweep: 60 g silver (capped at 3 rings)", lambda: frame([big], xy, 0.1)),
              ("sweep: two targets", lambda: frame(two, xy, 0.1)), ("sweep: LOCK on centre", lambda: frame([g_lock], xy, 0.3, t_lock=0.25)),
              ("trigger: sonar ring going out", lambda: frame(two, xy, 0.2, trigger=True)), ("trigger: echo on the gold", lambda: frame(two, xy, echo_times(two[0])[0], trigger=True)),
              ("trigger: echo on the iron", lambda: frame(two, xy, echo_times(two[1])[0], trigger=True)), ("trigger: ring coming back", lambda: frame(two, xy, 0.95, trigger=True)),
              ("trigger: LOCK while scanning", lambda: frame([g_lock, two[1]], xy, 0.45, trigger=True)), ("profile Night", lambda: frame([g1], xy, 0.1, profile="Night"))]
    fig, ax = plt.subplots(2, 5, figsize=(20, 8.6), facecolor="#101012")
    for a, (name, fn) in zip(ax.ravel(), panels):
        fr = fn(); a.set_facecolor("#08080a"); a.scatter(xy[:, 0], xy[:, 1], s=40, c="#1c1c20", edgecolors="#2a2a30", linewidths=0.5); li = fr.max(axis=1) > 0.02
        a.scatter(xy[li, 0], xy[li, 1], s=40, c=fr[li], edgecolors="none"); a.set_title(name, color="w", fontsize=9); a.set_aspect("equal"); a.axis("off")
    fig.suptitle("RF2 display v3 (modeled): small dots while sweeping, centre fills on lock; trigger held = sonar ring out and back, targets echo (light + sound) as it passes", color="w")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rf2_display3_frames.png"), dpi=95, facecolor=fig.get_facecolor()); plt.close(fig)
    render_screen(os.path.join(OUT, "rf2_screen_mockup.png"))
    json.dump(res, open(os.path.join(OUT, "rf2_display3.json"), "w"), indent=1, default=lambda o: bool(o) if isinstance(o, np.bool_) else str(o))
    print(json.dumps({k: bool(v) for k, v in c.items()}, indent=1)); return res
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
