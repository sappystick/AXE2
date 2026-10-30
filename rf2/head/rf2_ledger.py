#!/usr/bin/env python3
"""RF2 volume ledger (Phase A, 2026-10-29): every cubic millimetre of the head envelope (D233 x 25.4) is either a named solid or free volume inside a named
region with a declared fill. The envelope is PARTITIONED into regions (so nothing is unassigned by construction); for each region: total, solid, free,
fill, fill mass. Check: sum of regions = envelope, solids inside the envelope, regions disjoint. Fill levels are design decisions (stated here):
  base stack z 0-3.8: air in the gaps (edge gap, pin clearances)          coil channel r >= 108.4, z 3.8-18.8: epoxy around the litz
  channel top r >= 108.4, z 18.8-23.9: air                                  analog sector: gel to z 11.0 (over the AB1 parts), air above
  HV sector: epoxy to z 13.0 (over TXJ and MP1), air above                  digital sector + centre: air (CB1D conformal coated), lid zone: air
Densities (ASSUMED): epoxy 1.15, gel 0.98 g/cm3. Writes out/rf2_ledger.json.  usage: python3 rf2/head/rf2_ledger.py"""
import os, sys, json, math
import numpy as np
import manifold3d as m3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf2_head as H
S = H.SPEC; R = S["envelope"]["R"]; HT = S["envelope"]["H"]; RC = S["channel"]["inner_wall_r"][0]
DENS = dict(epoxy=1.15, gel=0.98, air=0.0)
def sector(d0, d1, z0, z1, r=RC):
    pts = [(0, 0)] + [(400 * math.cos(math.radians(a)), 400 * math.sin(math.radians(a))) for a in np.linspace(d0, d1, 96)]
    return m3.CrossSection([pts]).extrude(z1 - z0).translate([0, 0, z0]) ^ H.cyl(r, z0 - 1, z1 + 1)
def main():
    P = H.parts(); solids = None
    for k, v in P.items():
        if k == "REF3_FORMER": continue
        solids = v if solids is None else solids + v
    env = H.cyl(R, 0, HT); zb = S["bay"]["z"][0]; hv, an = S["sectors"]["hv"], S["sectors"]["analog"]
    regions = [("base stack", H.cyl(R, 0, zb), "air"), ("coil channel", H.ring(RC, R, zb, S["channel"]["z"][1]), "epoxy"),
               ("channel top", H.ring(RC, R, S["channel"]["z"][1], S["shell"]["lid_z"][0]), "air"),
               ("analog sector, potted", sector(an[0], an[1], zb, 11.0), "gel"), ("analog sector, above", sector(an[0], an[1], 11.0, S["shell"]["lid_z"][0]), "air"),
               ("HV sector, potted", sector(hv[0], hv[1], zb, 13.0), "epoxy"), ("HV sector, above", sector(hv[0], hv[1], 13.0, S["shell"]["lid_z"][0]), "air")]
    dig = H.cyl(RC, zb, S["shell"]["lid_z"][0]) - sector(an[0], an[1], zb - 1, 30) - sector(hv[0], hv[1], zb - 1, 30)
    regions += [("digital sector + centre", dig, "air"), ("lid zone", H.cyl(R, S["shell"]["lid_z"][0], HT), "air")]
    rows = []; tot = 0.0
    for name, reg, fill in regions:
        v = reg.volume(); vs = (reg ^ solids).volume(); vf = v - vs; tot += v
        rows.append(dict(region=name, total_cm3=round(v / 1000, 3), solid_cm3=round(vs / 1000, 3), free_cm3=round(vf / 1000, 3), fill=fill, fill_g=round(vf / 1000 * DENS[fill], 1)))
    over = 0.0
    for i in range(len(regions)):
        for j in range(i + 1, len(regions)): over += (regions[i][1] ^ regions[j][1]).volume()
    outside = (solids - env).volume(); V = env.volume()
    res = dict(status="MEASURED on the RF2 head v1 solids; fill levels are stated design decisions", envelope_cm3=round(V / 1000, 3), regions=rows,
               sum_regions_cm3=round(tot / 1000, 3), solids_cm3=round((solids ^ env).volume() / 1000, 3), free_cm3=round(sum(r["free_cm3"] for r in rows), 3),
               regions_overlap_mm3=round(over, 3), solids_outside_envelope_mm3=round(outside, 3), potting_g=round(sum(r["fill_g"] for r in rows), 1),
               ok=abs(tot - V) < 1e-3 * V and over < 1.0 and outside < 0.01)
    json.dump(res, open(os.path.join(H.OUT, "rf2_ledger.json"), "w"), indent=1); return res
if __name__ == "__main__":
    r = main(); print(json.dumps({k: v for k, v in r.items() if k != "regions"})); [print(x) for x in r["regions"]]
