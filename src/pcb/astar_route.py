#!/usr/bin/env python3
"""AXE2 fallback router (2026-10-30): routes ONLY the connections still open on a KiCad board, deterministically, when Freerouting stalls or fails.
Owner rule: never re-run a whole board for a few open nets; every route is then checked by KiCad DRC like any other.

Method (2 copper layers):
  1. connectivity: per net, its copper (pads, tracks, vias) is merged per layer with shapely; vias / through pads join the layers; more than one
     connected group = open. The two nearest groups are joined first, then the net is re-measured, until it is one group.
  2. obstacles: copper of every other net, inflated by clearance + half the track width (track cells) or clearance + half the via diameter (via
     cells); rule-area keep-outs that forbid tracks / vias; the board outline shrunk by the edge clearance + half the track width.
  3. search: A* on a grid (default 0.05 mm) over a window around the two groups (grown if no path), 8-way moves (45 deg tracks), a layer change
     costs a via; start = every free cell inside the source group's copper, goal = any free cell inside the target group's copper.
  4. output: the path becomes straight track runs and vias (net of the connection); the board is saved; a JSON report lists every connection.
usage: python3 src/pcb/astar_route.py IN.kicad_pcb OUT.kicad_pcb --track 0.15 --clear 0.2 --via 0.6,0.3 [--edge 0.5] [--grid 0.05] [--hv NETS --hv-clear 1.0]
                                      [--nets A,B] [--report r.json] [--max-window 60]"""
import os, sys, json, math, heapq, argparse, time
import numpy as np


def poly_from_set(ps):
    """SHAPE_POLY_SET -> shapely geometry"""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i); pts = [(o.CPoint(j).x / 1e6, -o.CPoint(j).y / 1e6) for j in range(o.PointCount())]
        holes = []
        for h in range(ps.HoleCount(i)):
            hh = ps.Hole(i, h); holes.append([(hh.CPoint(j).x / 1e6, -hh.CPoint(j).y / 1e6) for j in range(hh.PointCount())])
        if len(pts) >= 3: out.append(Polygon(pts, holes).buffer(0))
    return unary_union(out) if out else None


def copper(board):
    """{net: {'F': geom, 'B': geom}} and the via / through-pad points that join the layers, in mm (y up)"""
    import pcbnew
    from shapely.geometry import Point, LineString
    from shapely.ops import unary_union
    per, links = {}, {}
    def add(net, lay, g): per.setdefault(net, {"F": [], "B": []})[lay].append(g)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if not net: continue
            for lay, L in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)):
                if pad.IsOnLayer(L):
                    g = poly_from_set(pad.GetEffectivePolygon(L, pcbnew.ERROR_INSIDE))
                    if g is not None: add(net, lay, g)
            if pad.IsOnLayer(pcbnew.F_Cu) and pad.IsOnLayer(pcbnew.B_Cu):
                p = pad.GetPosition(); links.setdefault(net, []).append((p.x / 1e6, -p.y / 1e6))
    for t in board.GetTracks():
        net = t.GetNetname()
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition(); d = t.GetWidth(pcbnew.F_Cu) / 1e6; c = Point(p.x / 1e6, -p.y / 1e6).buffer(d / 2, 16)
            add(net, "F", c); add(net, "B", c); links.setdefault(net, []).append((p.x / 1e6, -p.y / 1e6))
        else:
            a, b = t.GetStart(), t.GetEnd(); g = LineString([(a.x / 1e6, -a.y / 1e6), (b.x / 1e6, -b.y / 1e6)]).buffer(t.GetWidth() / 2e6, 8)
            add(net, "F" if t.GetLayer() == pcbnew.F_Cu else "B", g)
    return {n: {k: unary_union(v) if v else None for k, v in d.items()} for n, d in per.items()}, links


def groups(cu, links):
    """connected groups of one net: list of {'F': geom, 'B': geom}"""
    from shapely.geometry import Point
    items = [("F", g) for g in (list(cu["F"].geoms) if cu["F"] is not None and hasattr(cu["F"], "geoms") else ([cu["F"]] if cu["F"] is not None else []))] + \
            [("B", g) for g in (list(cu["B"].geoms) if cu["B"] is not None and hasattr(cu["B"], "geoms") else ([cu["B"]] if cu["B"] is not None else []))]
    parent = list(range(len(items)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for x, y in links:
        hit = [i for i, (l, g) in enumerate(items) if g.distance(Point(x, y)) < 1e-6]
        for i in hit[1:]: parent[find(i)] = find(hit[0])
    out = {}
    for i, (l, g) in enumerate(items): out.setdefault(find(i), {"F": [], "B": []})[l].append(g)
    from shapely.ops import unary_union
    return [{k: unary_union(v) if v else None for k, v in d.items()} for d in out.values()]


def route_pair(src, dst, obst_t, obst_v, allowed, grid, win, via_cost=30.0):
    """A* between two copper groups. obst_t / obst_v: {'F','B'} shapely obstacles for track / via cells; allowed: shapely region for track centres.
    Returns [(layer, x, y), ...] cell centres or None."""
    import shapely
    from shapely.geometry import box
    bx = box(*src_bounds(src, dst)).buffer(win, join_style=2); x0, y0, x1, y1 = bx.bounds
    nx, ny = int((x1 - x0) / grid) + 1, int((y1 - y0) / grid) + 1
    xs = x0 + np.arange(nx) * grid; ys = y0 + np.arange(ny) * grid; X, Y = np.meshgrid(xs, ys, indexing="ij")
    free, vfree, start, goal = {}, None, {}, {}
    ok_region = shapely.contains_xy(allowed, X, Y)
    for k, L in enumerate("FB"):
        blocked = shapely.contains_xy(obst_t[L], X, Y) if obst_t[L] is not None else np.zeros_like(ok_region)
        free[k] = ok_region & ~blocked
        start[k] = free[k] & (shapely.contains_xy(src[L], X, Y) if src[L] is not None else False)
        goal[k] = free[k] & (shapely.contains_xy(dst[L], X, Y) if dst[L] is not None else False)
    vfree = ok_region.copy()
    for L in "FB":
        if obst_v[L] is not None: vfree &= ~shapely.contains_xy(obst_v[L], X, Y)
    gpts = np.argwhere(goal[0] | goal[1])
    if not len(gpts): return None
    gc = gpts.mean(axis=0)
    def h(i, j): return math.hypot(i - gc[0], j - gc[1]) * 0.9
    D = [np.full((nx, ny), np.inf), np.full((nx, ny), np.inf)]; prev = {}
    pq = []
    for k in (0, 1):
        for i, j in np.argwhere(start[k]): D[k][i, j] = 0.0; heapq.heappush(pq, (h(i, j), 0.0, k, int(i), int(j)))
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
    end = None; n_exp = 0
    while pq:
        f, g, k, i, j = heapq.heappop(pq)
        if g > D[k][i, j]: continue
        n_exp += 1
        if goal[k][i, j]: end = (k, i, j); break
        for di, dj, c in moves:
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and free[k][a, b]:
                ng = g + c
                if ng < D[k][a, b]: D[k][a, b] = ng; prev[(k, a, b)] = (k, i, j); heapq.heappush(pq, (ng + h(a, b), ng, k, a, b))
        o = 1 - k
        if vfree[i, j] and free[o][i, j]:
            ng = g + via_cost
            if ng < D[o][i, j]: D[o][i, j] = ng; prev[(o, i, j)] = (k, i, j); heapq.heappush(pq, (ng + h(i, j), ng, o, i, j))
    if end is None: return None
    path = [end]
    while path[-1] in prev: path.append(prev[path[-1]])
    path.reverse()
    return [("FB"[k], float(xs[i]), float(ys[j])) for k, i, j in path]


def src_bounds(a, b):
    from shapely.ops import unary_union
    g = unary_union([x for d in (a, b) for x in d.values() if x is not None]); return g.bounds


def simplify(path):
    """cell path -> runs of (layer, [points]) with straight segments merged; layer changes become vias"""
    runs, cur = [], [path[0]]
    for p in path[1:]:
        if p[0] != cur[-1][0]: runs.append(cur); cur = [p]
        else: cur.append(p)
    runs.append(cur)
    out = []
    for r in runs:
        pts = [(r[0][1], r[0][2])]
        for k in range(1, len(r) - 1):
            ax, ay = r[k][1] - pts[-1][0], r[k][2] - pts[-1][1]; bx, by = r[k + 1][1] - r[k][1], r[k + 1][2] - r[k][2]
            if abs(ax * by - ay * bx) > 1e-9: pts.append((r[k][1], r[k][2]))
        if len(r) > 1: pts.append((r[-1][1], r[-1][2]))
        out.append((r[0][0], pts))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--track", type=float, default=0.15); ap.add_argument("--clear", type=float, default=0.2); ap.add_argument("--via", default="0.6,0.3")
    ap.add_argument("--edge", type=float, default=0.5); ap.add_argument("--grid", type=float, default=0.05); ap.add_argument("--nets", default="")
    ap.add_argument("--report", default=""); ap.add_argument("--max-window", type=float, default=60.0)
    ap.add_argument("--hv", default="", help="high-voltage nets: rule 6, everything else keeps --hv-clear from them"); ap.add_argument("--hv-clear", type=float, default=1.0)
    a = ap.parse_args()
    import pcbnew
    from shapely.ops import unary_union
    t0 = time.time(); vd, vh = (float(x) for x in a.via.split(","))
    b = pcbnew.LoadBoard(a.inp)
    ps = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ps); outline = poly_from_set(ps)
    keep = {"F": [], "B": []}
    for z in b.Zones():
        if z.GetIsRuleArea() and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
            g = poly_from_set(z.Outline())
            for L, LL in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)):
                if z.IsOnLayer(LL) and g is not None: keep[L].append(g)
    allowed = outline.buffer(-(a.edge + a.track / 2))
    want = {n for n in a.nets.split(",") if n}; hv = {n for n in a.hv.split(",") if n}
    if hv and a.hv_clear < 1.0: sys.exit("astar_route: rule 6 needs --hv-clear >= 1.0 mm")
    report = dict(tool="astar_route", grid_mm=a.grid, track_mm=a.track, clear_mm=a.clear, via_mm=[vd, vh], connections=[])
    for rnd in range(500):
        cu, links = copper(b); todo = []
        for net, d in cu.items():
            if want and net not in want: continue
            gs = groups(d, links.get(net, []))
            if len(gs) > 1: todo.append((net, gs))
        if not todo: break
        net, gs = sorted(todo, key=lambda x: x[0])[0]
        best = min(((i, j) for i in range(len(gs)) for j in range(i + 1, len(gs))),
                   key=lambda ij: unary_union([g for g in gs[ij[0]].values() if g is not None]).distance(unary_union([g for g in gs[ij[1]].values() if g is not None])))
        src, dst = gs[best[0]], gs[best[1]]
        def obst(extra):                                                  # other nets' copper inflated by the clearance that applies to the pair (rule 6 for HV)
            res = {}
            for L in "FB":
                parts = [d[L].buffer((a.hv_clear if (net in hv or n in hv) else a.clear) + extra, 8) for n, d in cu.items() if n != net and d[L] is not None]
                parts += [k.buffer(extra, 8) for k in keep[L]]
                g = unary_union(parts) if parts else None; res[L] = g if g is not None and not g.is_empty else None
            return res
        obst_t, obst_v = obst(a.track / 2), obst(vd / 2)
        path, win = None, 4.0
        while path is None and win <= a.max_window:
            path = route_pair(src, dst, obst_t, obst_v, allowed, a.grid, win); win *= 2
        if path is None:
            report["connections"].append(dict(net=net, ok=False, reason="no path within the window")); want.discard(net)
            if not want: want = {n for n, _ in todo if n != net} or {"__none__"}
            continue
        runs = simplify(path); nv = 0
        for k, (L, pts) in enumerate(runs):
            for p, q in zip(pts[:-1], pts[1:]):
                t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(int(p[0] * 1e6), int(-p[1] * 1e6))); t.SetEnd(pcbnew.VECTOR2I(int(q[0] * 1e6), int(-q[1] * 1e6)))
                t.SetWidth(int(a.track * 1e6)); t.SetLayer(pcbnew.F_Cu if L == "F" else pcbnew.B_Cu); t.SetNet(b.FindNet(net)); b.Add(t)
            if k + 1 < len(runs):
                v = pcbnew.PCB_VIA(b); x, y = pts[-1]; v.SetPosition(pcbnew.VECTOR2I(int(x * 1e6), int(-y * 1e6))); v.SetWidth(int(vd * 1e6)); v.SetDrill(int(vh * 1e6))
                v.SetNet(b.FindNet(net)); b.Add(v); nv += 1
        report["connections"].append(dict(net=net, ok=True, cells=len(path), runs=len(runs), vias=nv))
        print(f"astar: {net} routed ({len(path)} cells, {nv} vias)", flush=True)
    pcbnew.SaveBoard(a.out, b)
    cu, links = copper(b)
    report["open_after"] = sorted(n for n, d in cu.items() if len(groups(d, links.get(n, []))) > 1)
    report["seconds"] = round(time.time() - t0, 1)
    if a.report: json.dump(report, open(a.report, "w"), indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != "connections"}))


if __name__ == "__main__": main()
