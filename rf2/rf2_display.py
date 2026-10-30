#!/usr/bin/env python3
"""RF2 display and audio coding v2 (2026-10-30, owner): dark while sweeping; on a detection the LEDs light a pulsing blob at the target's place whose SIZE (number of rings lit)
grows with the target's size; several targets are drawn as separate blobs with their own colour, pulse phase and audio voice; status screens for power-on, ground learning,
battery, interference, sweep speed, thermal limit and signature memory. MODELED specification with checks; no human-factors test.
Coding (redundant, so no single channel carries meaning alone):
  class -> colour + timbre (rf2_ui: iron red / buzz, foil violet / soft, non-iron gold-green-blue by decay time / clear tone, pitch rising with tau)
  size (mass-equivalent from the signal strength and the estimated depth) -> blob radius: 1 ring for 0.1 g up to the whole display for >= 100 g
  depth -> pulse rate of the blob and beep rate (shallow fast, deep slow) and edge softness (deep = softer edge)
  confidence -> brightness; a stored signature (double-press) -> white halo + double chirp; iron -> dark cross through the blob (shape, not only colour)
  several targets -> one blob each; where blobs meet, a dark seam keeps them apart; their pulses are phase-staggered; audio time-slots one voice per target
Where the targets come from (firmware, rf2_separation.py): spatial peaks in the sweep map (gyro position x quadrupole bearing x mono amplitude) and decay-time components
(multi-exponential fit on the AD7389-4 full waveform). Writes rf2/head/out/rf2_display.json, rf2_display_frames.png.   usage: python3 rf2/rf2_display.py"""
import os, sys, json, math
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path[:0] = [os.path.join(ROOT, "rf2"), os.path.join(ROOT, "rf2", "head")]
import rf2_ui as U
OUT = os.path.join(ROOT, "rf2", "head", "out")
RING = 8.0; R_MAX = 104.0
def blob_radius_mm(mass_g):
    """one ring (8 mm) for 0.1 g, the whole display (104 mm) for 100 g and above; logarithmic in between (size is judged by eye on a log scale)"""
    x = (math.log10(max(mass_g, 0.1)) + 1.0) / 3.0
    return float(min(max(RING + (R_MAX - RING) * x, RING), R_MAX))
def rings_lit(mass_g): return int(math.ceil(blob_radius_mm(mass_g) / RING))
def pulse_hz(depth_mm): return U.beep_rate_for(depth_mm) / 2.0                 # blob pulses at half the beep rate: one swell per two beeps
def edge_mm(depth_mm): return 3.0 + depth_mm / 60.0                              # deeper = softer edge
def target_fields(targets, xy, t):
    """per target: intensity at every LED (0..1) and its colour"""
    out = []
    for k, tg in enumerate(targets):
        cx, cy = tg["x_mm"], tg["y_mm"]; rho = np.hypot(xy[:, 0] - cx, xy[:, 1] - cy); r = blob_radius_mm(tg["mass_g"]); e = edge_mm(tg["depth_mm"])
        disc = np.where(rho < r + 1.5 * e, 1.0 / (1.0 + np.exp((rho - r) / e)), 0.0)          # soft edge, cut 1.5 edge-widths out so faint tails do not bridge two blobs
        ph = 2 * math.pi * k / max(len(targets), 1); puls = 0.7 + 0.3 * math.sin(2 * math.pi * pulse_hz(tg["depth_mm"]) * t + ph)
        inten = disc * puls * (0.35 + 0.65 * tg.get("conf", 0.9))
        if tg["cls"] == "FERROUS":                                              # dark cross through an iron blob
            dx, dy = xy[:, 0] - cx, xy[:, 1] - cy; inten = inten * np.where((np.abs(dx) < 3.5) | (np.abs(dy) < 3.5), 0.15, 1.0)
        col = np.array(U.hsv(U.hue_for(tg["cls"], tg["tau_us"]), 1.0, 1.0))
        halo = (np.abs(rho - (r + RING)) < 3.0) * 0.8 if tg.get("match") else np.zeros(len(xy))
        out.append((inten, col, halo))
    return out
def frame(targets, xy, t, boost=False):
    """RGB per LED; dark with no target. Overlaps: each LED belongs to the strongest target; where the second strongest is above 45 % of the strongest the LED stays dark (seam)"""
    rgb = np.zeros((len(xy), 3))
    if not targets: return rgb
    if boost:                                                                     # pinpoint: zoom x2 around the strongest target
        k0 = max(range(len(targets)), key=lambda k: targets[k]["mass_g"] / (1 + targets[k]["depth_mm"] / 100) ** 6)
        c = targets[k0]; targets = [dict(tg, x_mm=(tg["x_mm"] - c["x_mm"]) * 2.0, y_mm=(tg["y_mm"] - c["y_mm"]) * 2.0, mass_g=tg["mass_g"] * 4.0) for tg in targets]
    F = target_fields(targets, xy, t); I = np.stack([f[0] for f in F]); order = np.argsort(-I, axis=0)
    top = I[order[0], np.arange(len(xy))]; second = I[order[1], np.arange(len(xy))] if len(F) > 1 else np.zeros(len(xy))
    seam = np.zeros(len(xy), bool)
    if len(F) > 1:                                                                # boundary: a lit LED with a lit neighbour (<= 11 mm) that belongs to another target goes dark
        from scipy.spatial import cKDTree
        lab = order[0]; lit = top > 0.02; tree = cKDTree(xy)
        for j in np.flatnonzero(lit):
            nb = [n for n in tree.query_ball_point(xy[j], 11.0) if n != j and lit[n]]
            if any(lab[n] != lab[j] for n in nb) and lab[j] != order[0, int(np.argmax(top))]: seam[j] = True
        seam |= (second > 0.12) & (second > 0.6 * top)
    for j in range(len(xy)):
        k = order[0, j]; rgb[j] = F[k][1] * top[j]
        for f in F: rgb[j] = np.maximum(rgb[j], f[2][j])                           # halos on top, white
    rgb[seam] = 0.0
    return np.clip(rgb, 0, 1)
STATUS = ("self_test", "ground_learn", "battery", "low_battery", "interference", "sweep_too_fast", "thermal_limit", "heartbeat")
def status_frame(kind, xy, t, value=0.0):
    """status screens: the rim (r 104), the centre (r 8) or the whole display; each is unmistakable by shape, not only colour"""
    assert kind in STATUS
    r = np.hypot(xy[:, 0], xy[:, 1]); a = (np.degrees(np.arctan2(xy[:, 1], xy[:, 0])) - 178.0) % 360   # angle from the heel, the user's side
    rgb = np.zeros((len(xy), 3)); rim = r > 100; ctr = r < 10
    if kind == "self_test":       rgb[np.abs(r - (8 + (t * 96 % 96))) < 4] = (0.6, 0.6, 0.6)                # a white ring runs from the centre to the rim: every chain lit once
    elif kind == "ground_learn":  rgb[rim & (a <= 360 * value)] = (0.0, 0.5, 0.7)                             # rim fills clockwise with the 80-frame ground pump
    elif kind == "battery":       rgb[rim & (a <= 360 * value)] = (0.1, 0.7, 0.1) if value > 0.25 else (0.8, 0.5, 0.0)
    elif kind == "low_battery":   rgb[rim & ((a < 12) | (a > 348))] = (0.8, 0.0, 0.0) if int(t * 2) % 2 else (0.2, 0.0, 0.0)
    elif kind == "interference":  rgb[rim] = np.array((0.35, 0.0, 0.5)) * (0.5 + 0.5 * math.sin(2 * math.pi * 0.5 * t))
    elif kind == "sweep_too_fast": rgb[rim & (np.abs(((a - (90 if value > 0 else 270)) + 180) % 360 - 180) < 40)] = (0.9, 0.55, 0.0)
    elif kind == "thermal_limit": rgb[rim & ((a // 30) % 2 == 0)] = np.array((0.9, 0.3, 0.0)) * (0.5 + 0.5 * math.sin(2 * math.pi * 1.0 * t))
    elif kind == "heartbeat":     rgb[ctr] = (0.0, 0.15, 0.05) if (t % 3.0) < 0.12 else (0, 0, 0)
    return rgb
def audio_schedule(targets, mode, cycle_s=0.6):
    """one voice per target, time-sliced: the cycle is split into equal slots (at most 3 voices; further targets wait their turn); within its slot a target beeps at its own
    depth rate and class pitch, at a level set by its size; silent with no target or in LED mode"""
    if mode == "LED" or not targets: return []
    T = sorted(targets, key=lambda tg: -tg["mass_g"] / (1 + tg["depth_mm"] / 100) ** 6)[:3]; slot = cycle_s / len(T); ev = []
    for k, tg in enumerate(T):
        tone = U.tone_for(tg["cls"], tg["tau_us"]); rate = U.beep_rate_for(tg["depth_mm"]); n = max(1, int(slot * rate)); d = min(0.06, slot / n * 0.6)
        for j in range(n): ev.append(dict(target=tg["id"], t0=round(k * slot + j * slot / n, 4), dur=round(d, 4), f_hz=round(tone["f_hz"], 1), level=round(0.2 + 0.8 * min(1, blob_radius_mm(tg["mass_g"]) / R_MAX), 3), timbre=tone["timbre"]))
    return sorted(ev, key=lambda e: e["t0"])
def connected_clusters(xy, lit, link=10.0):
    """number of separate lit regions (LEDs closer than 'link' mm are joined)"""
    idx = np.flatnonzero(lit); seen = set(); n = 0
    for s in idx:
        if s in seen: continue
        n += 1; stack = [s]; seen.add(s)
        while stack:
            u = stack.pop(); d = np.hypot(xy[idx, 0] - xy[u, 0], xy[idx, 1] - xy[u, 1])
            for v in idx[d < link]:
                if v not in seen: seen.add(v); stack.append(v)
    return n
SCENES = {
    "1 g gold, 150 mm": [dict(id=1, cls="NONFERROUS", depth_mm=150, mass_g=1, tau_us=28, x_mm=30, y_mm=20, conf=0.9)],
    "20 g silver, 200 mm": [dict(id=1, cls="NONFERROUS", depth_mm=200, mass_g=20, tau_us=150, x_mm=-20, y_mm=10, conf=0.95)],
    "two gold, 80 mm and 220 mm": [dict(id=1, cls="NONFERROUS", depth_mm=80, mass_g=0.5, tau_us=14, x_mm=-45, y_mm=-20, conf=0.9),
                                   dict(id=2, cls="NONFERROUS", depth_mm=220, mass_g=5, tau_us=60, x_mm=40, y_mm=25, conf=0.8)],
    "nail beside a ring (iron + foil)": [dict(id=1, cls="FERROUS", depth_mm=120, mass_g=3, tau_us=40, x_mm=-30, y_mm=30, conf=0.9),
                                         dict(id=2, cls="FOIL", depth_mm=100, mass_g=2, tau_us=30, x_mm=35, y_mm=-25, conf=0.85)],
    "stored signature matched": [dict(id=1, cls="NONFERROUS", depth_mm=120, mass_g=2, tau_us=20, x_mm=10, y_mm=-10, conf=0.9, match=True)],
    "pinpoint (trigger held): zoom": [dict(id=1, cls="NONFERROUS", depth_mm=100, mass_g=1, tau_us=22, x_mm=12, y_mm=8, conf=0.95),
                                      dict(id=2, cls="NONFERROUS", depth_mm=160, mass_g=1, tau_us=26, x_mm=40, y_mm=-10, conf=0.7)],
}
def main():
    import rf2_ledgrid as LG
    xy = np.array([(e["x"], e["y"]) for e in LG.layout()["leds"]]); c = {}
    c["dark_without_target"] = float(frame([], xy, 0.3).max()) == 0.0 and audio_schedule([], "BOTH") == []
    c["radius_grows_with_size"] = all(blob_radius_mm(a) < blob_radius_mm(b) for a, b in ((0.3, 1), (1, 10), (10, 60)))
    c["one_ring_for_0p1g_whole_display_for_100g"] = rings_lit(0.1) == 1 and rings_lit(100) == 13
    lit_small = frame(SCENES["1 g gold, 150 mm"], xy, 0.1).max(axis=1) > 0.1; lit_big = frame(SCENES["20 g silver, 200 mm"], xy, 0.1).max(axis=1) > 0.1
    c["bigger_target_lights_more_leds"] = int(lit_big.sum()) > 2 * int(lit_small.sum())
    two = frame(SCENES["two gold, 80 mm and 220 mm"], xy, 0.1).max(axis=1) > 0.1; c["two_targets_two_blobs"] = connected_clusters(xy, two) == 2
    c["deeper_pulses_slower"] = pulse_hz(220) < pulse_hz(80)
    ev = audio_schedule(SCENES["two gold, 80 mm and 220 mm"], "BOTH"); c["audio_voices_do_not_overlap"] = all(a["t0"] + a["dur"] <= b["t0"] + 1e-9 for a, b in zip(ev[:-1], ev[1:])) and len({e["target"] for e in ev}) == 2
    c["led_mode_is_silent"] = audio_schedule(SCENES["1 g gold, 150 mm"], "LED") == []
    fe = frame(SCENES["nail beside a ring (iron + foil)"], xy, 0.1); c["iron_has_a_cross"] = bool(np.any((np.abs(xy[:, 0] + 30) < 3) & (np.hypot(xy[:, 0] + 30, xy[:, 1] - 30) < 20) & (fe.max(axis=1) < 0.2)))
    m = frame(SCENES["stored signature matched"], xy, 0.1); c["match_has_white_halo"] = bool(np.any(np.all(m > 0.7, axis=1)))
    c["status_screens_render"] = all(status_frame(k, xy, 0.4, 0.6).shape == (len(xy), 3) for k in STATUS)
    c["frames_deterministic"] = bool(np.array_equal(frame(SCENES["two gold, 80 mm and 220 mm"], xy, 0.37), frame(SCENES["two gold, 80 mm and 220 mm"], xy, 0.37)))
    res = dict(status="MODELED specification (no human-factors or bench data)", checks=c, ok=all(c.values()),
               coding=dict(radius="8 mm (1 ring) at 0.1 g to 104 mm (13 rings) at >= 100 g, log scale", pulse="half the beep rate: %.1f Hz at 50 mm, %.1f Hz at 300 mm" % (pulse_hz(50), pulse_hz(300)),
                           multi="one blob per target, dark seam where blobs meet, pulses phase-staggered, one audio voice per slot (up to 3)", status=list(STATUS)),
               controls=dict(power="recessed push button on top of the handle pod above the trigger (rf2_pod.py): hold 2 s on / off; its light ring shows green on, amber boost, red low battery",
                             selector="AUDIO | LED | BOTH", trigger="hold: pinpoint boost, continuous (rf2_continuous.py: the limits are thermal); double-press: store signature"))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    panels = list(SCENES.items()) + [("status: ground learning 60 %", ("ground_learn", 0.6)), ("status: sweep too fast (moving right)", ("sweep_too_fast", 1)), ("status: thermal limit in boost", ("thermal_limit", 0)), ("status: power-on self-test", ("self_test", 0))]
    fig, ax = plt.subplots(2, 5, figsize=(20, 8.6), facecolor="#101012")
    for a, (name, sc) in zip(ax.ravel(), panels):
        fr = status_frame(sc[0], xy, 0.3, sc[1]) if isinstance(sc, tuple) else frame(sc, xy, 0.1, boost=name.startswith("pinpoint"))
        a.set_facecolor("#08080a"); a.scatter(xy[:, 0], xy[:, 1], s=40, c="#1c1c20", edgecolors="#2a2a30", linewidths=0.5); lit = fr.max(axis=1) > 0.02
        a.scatter(xy[lit, 0], xy[lit, 1], s=40, c=fr[lit], edgecolors="none"); a.set_title(name, color="w", fontsize=9); a.set_aspect("equal"); a.axis("off")
    fig.suptitle("RF2 display v2 (modeled): dark until a signature; blob size = target size, pulse = depth, colour = class, cross = iron, halo = stored match; status screens", color="w")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rf2_display_frames.png"), dpi=95, facecolor=fig.get_facecolor()); plt.close(fig)
    json.dump(res, open(os.path.join(OUT, "rf2_display.json"), "w"), indent=1, default=lambda o: bool(o) if isinstance(o, np.bool_) else str(o))
    print(json.dumps(c, indent=1)); return res
if __name__ == "__main__":
    sys.exit(0 if main()["ok"] else 1)
