"""Car body shell: a subdivision-surface cage generated from a station list (cross-sections along the car),
mirrored at y = 0 and closed front/rear by Coons-patch caps.

Frame: +X = car front, +Y = car left, +Z = up; origin on the ground at the middle of the car.

Every station has the same 12 ring levels, from the bottom centre up the side and over the top:
  k0 bottom centre   k1 bottom mid     k2 sill corner   k3 rocker        k4 widest (door middle)
  k5 upper door      k6 shoulder line  k7 belt (window bottom / hood edge)
  k8 window top / roof rail            k9 roof edge     k10 roof mid     k11 top centre
Bands (faces between consecutive levels) are named by their lower level: band 7 = k7..k8 (side glass).
Caps use ring levels k2..k9 as rows and k2,k1,k0 / k9,k10,k11 as columns.
"""
import math

import bmesh
import bpy
from mathutils import Vector

NK = 12
CAP_ROWS = 7   # k2..k9


def lerp(a, b, t):
    return a + (b - a) * t


def ring(st):
    """the 12 (x, y, z) cage points (left half) of one station."""
    x = st['x']
    zb, wb, w = st['zb'], st['wb'], st['w']
    zs, ws, zbelt, top = st['zs'], st['ws'], st['belt'], st['top']
    kind = st.get('kind', 'gh')
    z4 = st.get('z4', lerp(zb, zs, 0.45))
    pts = [
        (0.0, zb),
        (wb * 0.55, zb),
        (wb, zb + 0.035),
        (lerp(wb, w, 0.8), st.get('z3', zb + 0.13)),
        (w, z4),
        (lerp(w, ws, 0.45) + st.get('bulge5', 0.0), st.get('z5', lerp(z4, zs, 0.62))),
        (ws, zs),
    ]
    if kind == 'gh':
        wr, crown = st['wr'], st.get('crown', 0.045)
        zr = top - crown
        wg = st.get('wg', ws - 0.035)          # glass bottom
        pts += [
            (wg, zbelt),
            (lerp(wr, wg, st.get('rail_t', 0.12)), zr - st.get('rail_h', 0.07)),
            (wr, zr),
            (wr * 0.5, top - crown * 0.22),
            (0.0, top),
        ]
    elif kind == 'cowl':
        wr = st['wr']
        pts += [
            (ws - 0.04, zbelt),
            (ws - 0.075, zbelt + 0.015),
            (lerp(ws - 0.075, wr, 0.18), zbelt + 0.02 + (top - zbelt) * 0.25),
            (wr * 0.5, top - (top - zbelt) * 0.1),
            (0.0, top),
        ]
    else:   # hood / deck: crowned panel from the edge (belt) to the centre (top)
        we = st.get('we', ws - 0.045)

        def hz(f):
            return top - (top - zbelt) * f ** st.get('crown_pow', 2.2)
        pts += [(we, zbelt)] + [(we * f, hz(f)) for f in (0.84, 0.6, 0.3)] + [(0.0, top)]
    out = []
    lean = st.get('lean', {})
    over = st.get('over', {})
    for k, (y, z) in enumerate(pts):
        if k in over:
            y, z = over[k][0], over[k][1]
        dx = lean.get(k, 0.0)
        out.append(Vector((x + dx, y, z)))
    return out


def _coons(left, bottom, top, right):
    """grid points for a patch given its four boundary polylines.
    left[r], right[r] (r = 0..R), bottom[c], top[c] (c = 0..C); corners must match."""
    R, C = len(left) - 1, len(bottom) - 1
    g = [[None] * (C + 1) for _ in range(R + 1)]
    for r in range(R + 1):
        v = r / R
        for c in range(C + 1):
            u = c / C
            p = (left[r] * (1 - u) + right[r] * u + bottom[c] * (1 - v) + top[c] * v
                 - (bottom[0] * (1 - u) * (1 - v) + bottom[C] * u * (1 - v) + top[0] * (1 - u) * v + top[C] * u * v))
            g[r][c] = p
    return g


def build_cage(spec, name='body_cage'):
    """half cage (y >= 0) as a bmesh; returns (bm, grid) where grid[s][k] are BMVerts and cap grids are kept
    for face-material rules."""
    sts = spec['stations']
    bm = bmesh.new()
    grid = [[bm.verts.new(p) for p in ring(st)] for st in sts]
    S = len(sts)
    faces = {}
    for s in range(S - 1):
        for k in range(NK - 1):
            f = bm.faces.new((grid[s][k], grid[s][k + 1], grid[s + 1][k + 1], grid[s + 1][k]))   # outward
            faces[('side', s, k)] = f
    caps = {}
    for end, s, sign in (('front', S - 1, 1), ('rear', 0, -1)):
        st = sts[s]
        rg = [v.co.copy() for v in grid[s]]
        left = rg[2:10]                                    # k2..k9
        bottom = [rg[2], rg[1], rg[0]]
        top = [rg[9], rg[10], rg[11]]
        bul = st.get('cap_bulge', 0.06)
        right = []
        for r in range(CAP_ROWS + 1):
            p = left[r].copy()
            t = r / CAP_ROWS
            p.y = 0.0
            # centreline follows the edge profile (tailgate / bumper lean) plus a gentle plan-view bulge
            p.x = left[r].x + sign * bul * math.sin(math.pi * t) ** 0.7
            right.append(p)
        right[0] = rg[0].copy()
        right[-1] = rg[11].copy()
        g = _coons(left, bottom, top, right)
        # interior column 1 gets a little extra bulge so the cap is not flat
        verts = [[None] * 3 for _ in range(CAP_ROWS + 1)]
        for r in range(CAP_ROWS + 1):
            for c in range(3):
                if c == 0:
                    verts[r][c] = grid[s][2 + r]
                elif r == 0:
                    verts[r][c] = grid[s][2 - c]
                elif r == CAP_ROWS:
                    verts[r][c] = grid[s][9 + c]
                else:
                    p = g[r][c]
                    p.x += sign * bul * 0.35 * math.sin(math.pi * r / CAP_ROWS) * (1.0 if c == 1 else 0.0)
                    verts[r][c] = bm.verts.new(p)
        for r in range(CAP_ROWS):
            for c in range(2):
                q = (verts[r][c], verts[r][c + 1], verts[r + 1][c + 1], verts[r + 1][c])
                if sign > 0:
                    q = q[::-1]   # outward
                f = bm.faces.new(q)
                faces[(end, r, c)] = f
        caps[end] = verts
    return bm, grid, faces, caps
