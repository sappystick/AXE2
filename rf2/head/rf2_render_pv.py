#!/usr/bin/env python3
"""RF2 head v1 cut-away and exploded view with pyvista (VTK, off-screen): the same generated scene as rf2_render.py (true boolean cuts of the housing,
routed copper from the KiCad files, part bodies at their netlist positions, the RF1 AB1 meshes, CB1D as its envelope), with VTK lighting, silhouettes and
labels. MODELED design, not a photograph. usage: python3 rf2/head/rf2_render_pv.py -> out/rf2_cutaway.png, out/rf2_exploded.png"""
import os, sys, math
import numpy as np
os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
import pyvista as pv
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rf2_render as R
def poly(T):
    V = T.reshape(-1, 3); F = np.hstack([np.full((len(T), 1), 3), np.arange(len(V)).reshape(-1, 3)]).ravel()
    return pv.PolyData(V, F).clean(tolerance=1e-6)
def draw(items, path, az, el, dist, target, size, title):
    pl = pv.Plotter(off_screen=True, window_size=size, lighting="three lights"); pl.set_background("#f6f7f9")
    labels, lpts = [], []
    for name, T, col, lab in items:
        if len(T) == 0: continue
        m = poly(T); pl.add_mesh(m, color=col, smooth_shading=False, specular=0.25, specular_power=20, ambient=0.18, diffuse=0.85)
        if lab:
            c = np.array(m.center); labels.append(lab); lpts.append(T.reshape(-1, 3)[np.argmax(T.reshape(-1, 3) @ np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), 0.6]))])
    eye = np.array(target) + dist * np.array([math.cos(math.radians(el)) * math.cos(math.radians(az)), math.cos(math.radians(el)) * math.sin(math.radians(az)), math.sin(math.radians(el))])
    pl.camera.position = tuple(eye); pl.camera.focal_point = tuple(target); pl.camera.up = (0, 0, 1); pl.camera.view_angle = 30
    pl.enable_anti_aliasing("ssaa")
    if labels:
        pl.add_point_labels(np.array(lpts), labels, font_size=13, point_size=6, point_color="#1d2733", text_color="#1d2733", shape_color="white", shape_opacity=0.85,
                            always_visible=True, margin=4)
    pl.add_text(title, position="lower_left", font_size=9, color="#1d2733")
    pl.screenshot(path); pl.close()
if __name__ == "__main__":
    draw(R.scene(False), os.path.join(R.OUT, "rf2_cutaway.png"), az=232, el=34, dist=330, target=(-10, 10, 9), size=(2600, 1750),
         title="RF2 head v1, D233 x 25.4 mm: cut-away of the generated geometry: routed TXJ, MP1, LR1 copper, SH1, SB1R (MODELED; CB1D and AB1 shown as envelopes / RF1 meshes)")
    draw(R.scene(True), os.path.join(R.OUT, "rf2_exploded.png"), az=232, el=22, dist=760, target=(0, 0, 80), size=(2200, 2400),
         title="RF2 head v1: exploded stack (z offsets for clarity), same geometry")
    print("rendered")
