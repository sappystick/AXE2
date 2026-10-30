# Conventions
- Units: mm, degrees, amperes, volts, microsecond in simulation text. STL in mm.
- Head frame: z up from the underside of the base plate (z = 0); x, y in the plane; azimuth measured counter-clockwise from +x in the top view. Receive X8/quad reference axis = 0 deg. Heel (shaft side) = 178 deg. Spine channel = 90 deg.
- Heel frame (yoke scripts): x' outward from the head centre along 178 deg, y' tangential, z up; assembly STLs are rotated by 178 deg about z.
- Board frames: KiCad/exporter coordinates are y-DOWN; pickplace files write y-UP (PosY = -y). CB1D is mounted rotated 180 deg so JCL faces the heel; LB1 uses pixel coordinates directly.
- Layers: formers L1 (top, nearest the hood) .. L6 (bottom); z_bottom,k = 3.2 + (6-k) x 4.4. Interfaces 1-5 between layers.
- Part naming: NAME_vN_what.stl; boards PF233-NAME; versions only go up; superseded files get a SUPERSEDED note, never silently overwritten.
- Scripts read and write relative kit_vNN/ directories under work/ (make setup flattens src/ into work/).
- Meshes: closed shells, 0 open edges checked with the edge-counting test in check_v22.py; overlapping shells are allowed (slicers merge) but mass from volume is then an upper bound.
- Coordinates in reports always say which frame.
