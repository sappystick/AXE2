#!/usr/bin/env python3
"""AXE2 option B, clean-sheet layout question (owner 2026-10-30): which board ORIENTATION and PLACEMENT minimise what the transmit pulse does to the
electronics and what the electronics do to the receiver? MODELED.
Physics: the rim coil is axisymmetric, so its field has no azimuthal component (B_phi = 0 everywhere). A board standing in a radial plane (a 'fin'
containing the head axis) has all its current loops' normals along phi: no EMF from the pulse, no eddy current in its copper, and (reciprocity) no
coupling of its own currents into the mono. Flat (horizontal) boards see B_z, the largest component inside the loop. What breaks the symmetry:
  - the coil leads (a 2-wire pair from the winding at 178 deg to the TXJ terminal, 1.5 mm apart, carrying the coil current), included here;
  - a fin tilted by an assembly error (1 deg and 3 deg about its radial axis, and about the vertical);
  - the quadrupole receive boards (they receive, not transmit; their pattern is not axisymmetric: board currents still reach the bearing channel).
For each architecture and zone: the largest perpendicular field at the peak current, the EMF it induces per cm2 of loop (dI/dt 460 V / L), the
receive coupling per cm2 (nH), and the solid-plane echo relative to a flat plate of the same area at the same place (echo ~ flux^2).
Fins: radial span r 20-100 mm, z 3.8-13.1 (the option-B bay), at the azimuths of the HV (178 deg, next to the leads), analog (122 deg) and digital
(0, 60, 270 deg) sectors. Flat: the same radial span lying at the board tier (z 6.4), 9.3 mm wide.
usage: python3 rf2/rf2_layout.py -> rf2/results/rf2_layout.json"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_zones as Z, rf2_coil_search as C
OUT = os.path.join(HERE, "results"); I0, DIDT = Z.I0, Z.DIDT
# coil leads: from the winding (r 105.4, 178 deg) radially in to TXJ (r 94.5), go and return 1.5 mm apart in z, z 6.0 / 7.5
def lead_paths(deg=178.0, r0=105.4, r1=94.5, z=(6.0, 7.5)):
    u = np.array([math.cos(math.radians(deg)), math.sin(math.radians(deg))]); s = np.linspace(r1, r0, 40)
    go = np.c_[np.outer(s, u), np.full(len(s), z[0])] * 1e-3; back = np.c_[np.outer(s[::-1], u), np.full(len(s), z[1])] * 1e-3
    return [go, back]
LEADS = lead_paths()
def B(P_mm):
    P = np.atleast_2d(P_mm) * 1e-3; return C.B_turns(Z.T, P) + C.B_paths(LEADS, P, chunk=400)
def grid_fin(deg, r=(20.0, 100.0), z=(3.8, 13.1), nr=33, nz=7):
    rr, zz = np.meshgrid(np.linspace(*r, nr), np.linspace(*z, nz)); c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.c_[rr.ravel() * c, rr.ravel() * s, zz.ravel()]
def grid_flat(deg, r=(20.0, 100.0), w=9.3, zt=6.4, nr=33, nw=7):
    rr, ww = np.meshgrid(np.linspace(*r, nr), np.linspace(-w / 2, w / 2, nw)); c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.c_[rr.ravel() * c - ww.ravel() * s, rr.ravel() * s + ww.ravel() * c, np.full(rr.size, zt)]
def normal(deg, kind, tilt_deg=0.0, axis="radial"):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg)); phi = np.array([-s, c, 0.0]); rad = np.array([c, s, 0.0]); zh = np.array([0, 0, 1.0])
    if kind == "flat": return zh
    t = math.radians(tilt_deg); other = zh if axis == "radial" else rad          # a tilt about the radial axis mixes phi with z; about the vertical, with r
    return phi * math.cos(t) + other * math.sin(t)
if __name__ == "__main__":
    res = dict(status=__doc__.split("\n")[1], cases=[])
    for deg, zone in ((178.0, "HV (next to the coil leads)"), (122.0, "analog"), (0.0, "digital"), (60.0, "digital"), (270.0, "digital")):
        rows = []
        cases = [("flat (horizontal) board", "flat", 0, "radial"), ("radial fin, exact", "fin", 0, "radial"), ("radial fin, 1 deg tilt about its radial axis", "fin", 1, "radial"),
                 ("radial fin, 3 deg tilt about its radial axis", "fin", 3, "radial"), ("radial fin, 3 deg twist about the vertical", "fin", 3, "vertical")]
        for lab, kind, tilt, ax in cases:
            P = grid_flat(deg) if kind == "flat" else grid_fin(deg); n = normal(deg, kind, tilt, ax); Bp = B(P) @ n
            dA = (80.0 * 9.3 / len(P)) * 1e-6; flux = float(np.sum(Bp) * dA); flux_abs = float(np.sum(np.abs(Bp)) * dA)
            rows.append(dict(zone=zone, deg=deg, case=lab, B_perp_max_mT=round(float(np.max(np.abs(Bp))) * I0 * 1e3, 4),
                             EMF_per_cm2_max_V=round(float(np.max(np.abs(Bp))) * DIDT * 1e-4, 5), M_per_cm2_max_nH=round(float(np.max(np.abs(Bp))) * 1e-4 * 1e9, 4),
                             flux_net_per_A_nWb=round(flux * 1e9, 4), flux_abs_per_A_nWb=round(flux_abs * 1e9, 4)))
        f0 = rows[0]["flux_abs_per_A_nWb"]
        for r in rows: r["solid_plane_echo_vs_flat"] = float(f"{(r['flux_abs_per_A_nWb'] / f0) ** 2:.3g}") if f0 else None
        for r in rows: print(f"{zone:28s} {r['case']:46s} Bmax {r['B_perp_max_mT']:8.4f} mT  EMF/cm2 {r['EMF_per_cm2_max_V']:8.5f} V  M {r['M_per_cm2_max_nH']:8.4f} nH  echo vs flat {r['solid_plane_echo_vs_flat']}", flush=True)
        res["cases"] += rows
    # centre bore question: field at the axis over the bay height (what a central post / hole would sit in)
    zz = np.linspace(3.8, 13.1, 6); Bc = B(np.c_[np.zeros(6), np.zeros(6), zz]) * I0 * 1e3
    res["axis_field_mT"] = [dict(z=round(float(z), 2), Bz=round(float(b[2]), 3), Br=round(float(np.hypot(b[0], b[1])), 4)) for z, b in zip(zz, Bc)]
    json.dump(res, open(os.path.join(OUT, "rf2_layout.json"), "w"), indent=1); print("axis", res["axis_field_mT"]); print("done")
