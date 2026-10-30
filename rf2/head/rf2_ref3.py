#!/usr/bin/env python3
"""RF2 Phase B: REF3 reference coil (the EMI canceller's input, rf2_emi.py) sized from the noise it adds (2026-10-29). MODELED.
The canceller subtracts w x REF from the mono; with REF area-turns = g x the mono's, w = 1 / g and the REF channel's own noise e_ref enters the mono as
e_ref / g. Depth follows SNR^(1/5.1) (sim_head1 scaling), so the penalty is (1 + (e_ref / g / e_mono)^2)^(-1 / 10.2).
e_ref = sqrt(e_preamp^2 + 4 k T R_coil) with e_preamp = e_mono = 1.7 nV/rtHz; R_coil = rho x wire length / wire area; air-core square-ish former (one per axis,
3 orthogonal), copper density 8.96. The study in rf2_emi.py ASSUMED e_ref = 1.9 nV/rtHz at g = 3.
usage: python3 rf2/head/rf2_ref3.py"""
import os, sys, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import rf2_ground as G
kT4 = 4 * 1.380649e-23 * 300; RHO = 1.72e-8; E_MONO = 1.7e-9
NA_MONO = sum(math.pi * r ** 2 for r, z, s in G.COILS["A"]["T"])
rows = []
for g in (1.0, 2.0, 3.0):
    for d in (0.06, 0.08, 0.10, 0.12):                       # former diameter (each axis a circular winding of this diameter)
        for wd in (0.15, 0.20, 0.25, 0.32):                  # wire diameter, mm
            A = math.pi * (d / 2) ** 2; N = g * NA_MONO / A; L = N * math.pi * d; aw = math.pi * (wd * 1e-3 / 2) ** 2; R = RHO * L / aw
            e = math.sqrt(E_MONO ** 2 + kT4 * R); pen = (1 + (e / g / E_MONO) ** 2) ** (-1 / 10.2) - 1
            mass = 3 * L * aw * 8960 * 1e3
            rows.append(dict(gain=g, former_mm=round(d * 1e3), wire_mm=wd, turns_per_axis=round(N), wire_m_per_axis=round(L, 1), R_ohm=round(R, 1),
                             e_ref_nV=round(e * 1e9, 2), depth_penalty_pct=round(pen * 100, 2), copper_g_3axes=round(mass, 1)))
ok = [r for r in rows if r["depth_penalty_pct"] >= -1.5 and r["former_mm"] <= 100]
best = min(ok, key=lambda r: (r["copper_g_3axes"], r["former_mm"])) if ok else None
res = dict(status="MODELED (RF2 REF3 sizing)", NA_mono_m2=round(NA_MONO, 3), rule="depth penalty <= 1.5 %, former <= 100 mm, then least copper", chosen=best, options=rows,
           emi_study_assumption=dict(gain=3, e_ref_nV=1.9))
# ---- SLEEVE layout (owner 2026-10-30: no box on the shaft). The same three axes wound ON the tube under a thin cover: X and Y as long saddle-coil pairs
# (nested turns, two 120 deg saddles per axis, one axis per layer group), Z as a fine-wire solenoid on top. Each saddle turn links L x chord (2 a sin phi).
def sleeve(L=0.35, a0=0.0145, g_t=3.0, g_z=4.0, wd_t=0.20, wd_z=0.15, phi=math.radians(60.0)):
    out = {}; pitch_t = wd_t * 1.1e-3; a = a0
    for axis in ("X", "Y"):
        need = g_t * NA_MONO; NA = 0.0; Lw = 0.0; layers = 0; turns = 0
        while NA < need:
            n_side = int((phi * a) / pitch_t)                                           # nested turns per saddle in this layer (one side's arc half-width / pitch)
            for k in range(n_side):
                ph = phi - k * pitch_t / a
                if ph <= 0.05: break
                for _ in range(2):                                                       # two saddles per axis, in series
                    NA += L * 2 * a * math.sin(ph); Lw += 2 * L + 2 * (2 * ph * a); turns += 1
                    if NA >= need: break
                if NA >= need: break
            layers += 1; a += pitch_t
        aw = math.pi * (wd_t * 1e-3 / 2) ** 2; R = RHO * Lw / aw; e = math.sqrt(E_MONO ** 2 + kT4 * R); pen = (1 + (e / g_t / E_MONO) ** 2) ** (-1 / 10.2) - 1
        out[axis] = dict(gain=g_t, turns=turns, layers=layers, wire_mm=wd_t, wire_m=round(Lw, 1), R_ohm=round(R, 1), e_ref_nV=round(e * 1e9, 2), depth_penalty_pct=round(pen * 100, 2), copper_g=round(Lw * aw * 8960e3, 1))
    pitch_z = wd_z * 1.1e-3; A = math.pi * a ** 2; Nz = g_z * NA_MONO / A; per_layer = L / pitch_z; lz = math.ceil(Nz / per_layer)
    Lw = sum(min(per_layer, Nz - i * per_layer) * 2 * math.pi * (a + i * pitch_z) for i in range(lz)); aw = math.pi * (wd_z * 1e-3 / 2) ** 2; R = RHO * Lw / aw
    e = math.sqrt(E_MONO ** 2 + kT4 * R); pen = (1 + (e / g_z / E_MONO) ** 2) ** (-1 / 10.2) - 1; a_out = a + lz * pitch_z
    out["Z"] = dict(gain=g_z, turns=round(Nz), layers=lz, wire_mm=wd_z, wire_m=round(Lw, 1), R_ohm=round(R, 1), e_ref_nV=round(e * 1e9, 2), depth_penalty_pct=round(pen * 100, 2), copper_g=round(Lw * aw * 8960e3, 1))
    out["length_mm"] = L * 1e3; out["winding_outer_r_mm"] = round(a_out * 1e3, 2); out["sleeve_od_mm"] = round(2 * (a_out * 1e3 + 1.0), 1)
    out["worst_axis_penalty_pct"] = min(out[k]["depth_penalty_pct"] for k in ("X", "Y", "Z")); out["copper_g_total"] = round(sum(out[k]["copper_g"] for k in ("X", "Y", "Z")), 1)
    return out
def rect_sleeve(W=0.038, H=0.032, L=0.35, g_t=3.0, g_z=4.0, wd_t=0.20, wd_z=0.15):
    """rectangular-profile layout (owner 2026-10-30: rectangular housing along the shaft): X and Y as pairs of flat nested rectangular coils on opposite
    faces of the W x H profile (each turn links its own area), Z as a solenoid around the rectangle; layers build outward"""
    out = {}; pt = wd_t * 1.1e-3
    for axis, face_w in (("X", W), ("Y", H)):
        need = g_t * NA_MONO; NA = Lw = 0.0; turns = layers = 0
        while NA < need and layers < 40:
            for k in range(int(min(face_w, L) / (2 * pt))):
                a_, b_ = L - 2 * k * pt, face_w - 2 * k * pt
                if b_ < 0.004: break
                for _ in range(2):
                    NA += a_ * b_; Lw += 2 * (a_ + b_); turns += 1
                    if NA >= need: break
                if NA >= need: break
            layers += 1
        aw = math.pi * (wd_t * 1e-3 / 2) ** 2; R = RHO * Lw / aw; e = math.sqrt(E_MONO ** 2 + kT4 * R); pen = (1 + (e / g_t / E_MONO) ** 2) ** (-1 / 10.2) - 1
        out[axis] = dict(gain=g_t, turns=turns, layers=layers, wire_mm=wd_t, wire_m=round(Lw, 1), R_ohm=round(R, 1), e_ref_nV=round(e * 1e9, 2), depth_penalty_pct=round(pen * 100, 2), copper_g=round(Lw * aw * 8960e3, 1))
    build_t = max(out["X"]["layers"], out["Y"]["layers"]) * pt; Wz, Hz = W + 2 * build_t, H + 2 * build_t; pz = wd_z * 1.1e-3; Nz = g_z * NA_MONO / (Wz * Hz)
    per = L / pz; lz = math.ceil(Nz / per); Lw = sum(min(per, Nz - i * per) * 2 * (Wz + Hz + 4 * i * pz) for i in range(lz)); aw = math.pi * (wd_z * 1e-3 / 2) ** 2; R = RHO * Lw / aw
    e = math.sqrt(E_MONO ** 2 + kT4 * R); pen = (1 + (e / g_z / E_MONO) ** 2) ** (-1 / 10.2) - 1
    out["Z"] = dict(gain=g_z, turns=round(Nz), layers=lz, wire_mm=wd_z, wire_m=round(Lw, 1), R_ohm=round(R, 1), e_ref_nV=round(e * 1e9, 2), depth_penalty_pct=round(pen * 100, 2), copper_g=round(Lw * aw * 8960e3, 1))
    tot = build_t + lz * pz + 1.0e-3
    out.update(profile_mm=[W * 1e3, H * 1e3], length_mm=L * 1e3, outer_mm=[round((W + 2 * tot) * 1e3, 1), round((H + 2 * tot) * 1e3, 1)], worst_axis_penalty_pct=min(out[k]["depth_penalty_pct"] for k in ("X", "Y", "Z")),
               copper_g_total=round(sum(out[k]["copper_g"] for k in ("X", "Y", "Z")), 1))
    return out
res["rect_sleeve"] = rect_sleeve()
res["sleeve"] = sleeve()
res["layout"] = dict(chosen="rect_sleeve" if res["rect_sleeve"]["worst_axis_penalty_pct"] >= res["sleeve"]["worst_axis_penalty_pct"] - 0.3 else "sleeve", why="owner 2026-10-30: the 100 mm cube on the shaft is not acceptable; the sleeve keeps the 3 axes on the tube (OD about "
                     f"{res['sleeve']['sleeve_od_mm']} mm over {res['sleeve']['length_mm']:.0f} mm); the box (chosen above) is kept only as the reference row",
                     box_penalty_pct=best["depth_penalty_pct"] if best else None, sleeve_worst_penalty_pct=res["sleeve"]["worst_axis_penalty_pct"])
print("sleeve", json.dumps(res["sleeve"])); print("rect_sleeve", json.dumps(res["rect_sleeve"])); print("chosen", res["layout"]["chosen"])
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "rf2_ref3.json"), "w"), indent=1)
print("chosen", best)
for r in rows:
    if r["gain"] == 3 and r["former_mm"] in (80, 100): print(r)
