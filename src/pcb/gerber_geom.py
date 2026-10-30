#!/usr/bin/env python3
"""Rebuild the copper of a Gerber layer as a shapely geometry (gerbonara reads the file; every primitive is applied in file order: dark = add, clear = subtract), and compare two layers by geometry.
Why: KiCad's Gerber export is NOT byte-deterministic (two exports of the same board differ in aperture / flash order in 7 of 12 files even with the timestamps removed), so a hash or a text diff cannot tell
a real change from noise. Used by gerber_plane_check.py (HV distances) and scripts/publish_data.py (is this layer really different from the published one?)."""
import math
from gerbonara import GerberFile
from shapely.geometry import Point, LineString, Polygon, box
from shapely import affinity
from shapely.ops import unary_union
def _geom(pr):
    n = type(pr).__name__
    if n == "Circle": return Point(pr.x, pr.y).buffer(pr.r, 16)
    if n == "Rectangle": return affinity.rotate(box(pr.x - pr.w / 2, pr.y - pr.h / 2, pr.x + pr.w / 2, pr.y + pr.h / 2), math.degrees(pr.rotation) if pr.rotation else 0)
    if n == "Line": return LineString([(pr.x1, pr.y1), (pr.x2, pr.y2)]).buffer(pr.width / 2, 8)
    if n == "ArcPoly": return Polygon(pr.outline).buffer(0)
    if n == "Arc":                                                                    # a stroked arc (KiCad writes the circular Edge_Cuts of the AB1 discs as two arcs); cx, cy are the absolute centre
        r = math.hypot(pr.x1 - pr.cx, pr.y1 - pr.cy); a1 = math.atan2(pr.y1 - pr.cy, pr.x1 - pr.cx); a2 = math.atan2(pr.y2 - pr.cy, pr.x2 - pr.cx)
        d = (a2 - a1) % (2 * math.pi) if not pr.clockwise else -((a1 - a2) % (2 * math.pi))
        if abs(d) < 1e-9: d = -2 * math.pi if pr.clockwise else 2 * math.pi
        k = max(16, int(abs(d) / (2 * math.pi) * 180)); pts = [(pr.cx + r * math.cos(a1 + d * i / k), pr.cy + r * math.sin(a1 + d * i / k)) for i in range(k + 1)]
        return LineString(pts).buffer(pr.width / 2, 8)
    return None
def layer_geometry(path):
    """file order is kept: each run of consecutive same-polarity primitives is merged in one unary_union (the same set as adding them one by one, about 30x faster
    on the plane layers, 2026-10-28), then added (dark) or subtracted (clear)"""
    g = GerberFile.open(path); cu = Polygon(); n = 0; run, dark = [], True
    def flush():
        nonlocal cu
        if run: u = unary_union(run); cu = cu.union(u) if dark else cu.difference(u); run.clear()
    for o in g.objects:
        for pr in o.to_primitives("mm"):
            s = _geom(pr)
            if s is None or s.is_empty: continue
            if bool(pr.polarity_dark) != dark: flush(); dark = bool(pr.polarity_dark)
            run.append(s); n += 1
    flush()
    return cu, n
def layer_geometry_sequential(path):
    """the original one-primitive-at-a-time build (reference for tests/regress.py: the batched build must give the same copper)"""
    g = GerberFile.open(path); cu = Polygon(); n = 0
    for o in g.objects:
        for pr in o.to_primitives("mm"):
            s = _geom(pr)
            if s is None or s.is_empty: continue
            cu = cu.union(s) if pr.polarity_dark else cu.difference(s); n += 1
    return cu, n
def same_geometry(path_a, path_b, tol_mm2=1e-4):
    """True if the two layers describe the same copper (symmetric difference area below tol_mm2). Returns (bool, difference area)."""
    a, _ = layer_geometry(path_a); b, _ = layer_geometry(path_b); d = a.symmetric_difference(b).area
    return d < tol_mm2, d
