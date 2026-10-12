"""Weapon modelling kit. Everything is in millimetres in side-view coordinates:

    u  forward along the bore (muzzle at +u), u = 0 at the front face of the trigger
    v  up, v = 0 on the bore axis
    w  to the gun's right (+X in Blender)

Blender gets metres with X = w, Y = u, Z = v; the glTF export turns that into three.js +X right, +Y up, bore -Z.

A model is a function build(g) that calls the helpers on a Gun:

    g.extrude(pts, w0, w1, 'blued')        side profile (u, v) extruded across w, bevelled rims; holes allowed
    g.extrude(pts, u0, u1, plane='front')  cross-section (w, v) extruded along u   (plane='top': (u, w) along v)
    g.box(u0, u1, v0, v1, w0, w1)          bevelled box
    g.sweep(outline, 'walnut', width=..)   organic part: rounded sections fitted to a side outline (stocks, grips)
    g.loft([section, ...])                 explicit sections
    g.lathe([(u, r), ...])                 solid of revolution around an axis (barrels, sights, screws)
    g.pipe([(u, v, w), ...], r)            round bar along a path (wire stocks, guards, bipod legs)
    g.cut(target, cutter, ...)             boolean difference (helpers take cutter=True to make cutters)
    g.outline(region)                      traced silhouette of the reference photo inside a region (cached)

Profile points may carry a corner radius as a third value: (u, v, r) is filleted.
Parts: everything goes to 'body' unless `part=` or `with g.part('mag'):`; g.pivot(part, u, v, w) sets the
part's origin (the client animates around it). g.anchor(name, u, v, w) marks muzzle, sight, hands...
"""
import hashlib
import json
import math
import os
import subprocess
from contextlib import contextmanager

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, geometry

from . import materials

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, 'ref')
TRACES = os.path.join(HERE, 'traces')
S = 0.001
PY = os.environ.get('WEAPONS_PY', 'python3')


# ------------------------------------------------------------------ 2D polygon utilities (mm)

def _v2(p):
    return Vector((p[0], p[1]))


def area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i - 1][0], pts[i - 1][1]
        x1, y1 = pts[i][0], pts[i][1]
        a += x0 * y1 - x1 * y0
    return a * 0.5


def ccw(pts):
    return list(pts) if area(pts) >= 0 else list(reversed(pts))


def cw(pts):
    return list(reversed(pts)) if area(pts) >= 0 else list(pts)


def _fillet(a, b, c, r, steps=None, per90=4):
    """points replacing corner b (between a and c) by an arc of radius r."""
    d1 = (a - b)
    d2 = (c - b)
    if d1.length < 1e-9 or d2.length < 1e-9:
        return [b] * ((steps or 0) + 1)
    d1n, d2n = d1.normalized(), d2.normalized()
    ang = d1n.angle(d2n, 0.0)
    if ang < 1e-4 or abs(ang - math.pi) < 1e-4 or r <= 1e-6:
        return [b.copy() for _ in range((steps or 0) + 1)]
    t = r / math.tan(ang / 2)
    t = min(t, 0.5 * d1.length, 0.5 * d2.length)
    r = t * math.tan(ang / 2)
    p1, p2 = b + d1n * t, b + d2n * t
    cen = b + (d1n + d2n).normalized() * (r / math.sin(ang / 2))
    a1 = math.atan2(p1.y - cen.y, p1.x - cen.x)
    a2 = math.atan2(p2.y - cen.y, p2.x - cen.x)
    da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    n = steps if steps is not None else max(1, math.ceil(abs(da) / (math.pi / 2) * per90))
    return [cen + Vector((math.cos(a1 + da * k / n), math.sin(a1 + da * k / n))) * r for k in range(n + 1)]


def prep(pts, per90=4, closed=True):
    """apply (u, v, r) corner radii -> list of (u, v)."""
    P = [_v2(p) for p in pts]
    R = [p[2] if len(p) > 2 else 0 for p in pts]
    if not any(R):
        return [(p.x, p.y) for p in P]
    out = []
    n = len(P)
    for i in range(n):
        if R[i] <= 0 or (not closed and (i == 0 or i == n - 1)):
            out.append(P[i])
            continue
        out.extend(_fillet(P[i - 1], P[i], P[(i + 1) % n], R[i], per90=per90))
    return [(p.x, p.y) for p in out]


def arc(cu, cv, r, a0, a1, n=8):
    """points on an arc, angles in degrees (0 = +u, 90 = +v)."""
    return [(cu + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cv + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def bezier(p0, p1, p2, p3, n=10):
    out = []
    for k in range(n + 1):
        t = k / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def _resample_open(P, step):
    seg = [(P[i + 1] - P[i]).length for i in range(len(P) - 1)]
    L = sum(seg)
    if L < 1e-9:
        return [P[0], P[-1]]
    n = max(1, round(L / step))
    out = [P[0]]
    acc, j = 0.0, 0
    for k in range(1, n):
        s = L * k / n
        while j < len(seg) - 1 and acc + seg[j] < s:
            acc += seg[j]
            j += 1
        f = (s - acc) / seg[j] if seg[j] > 1e-12 else 0
        out.append(P[j].lerp(P[j + 1], f))
    out.append(P[-1])
    return out


def _dp(P, eps):
    """Douglas-Peucker on an open chain (keeps the ends)."""
    if len(P) < 3:
        return list(P)
    a, b = P[0], P[-1]
    ab = b - a
    L = ab.length
    best, bi = -1, 0
    for i in range(1, len(P) - 1):
        d = abs(ab.x * (a.y - P[i].y) - ab.y * (a.x - P[i].x)) / L if L > 1e-9 else (P[i] - a).length
        if d > best:
            best, bi = d, i
    if best <= eps:
        return [a, b]
    return _dp(P[:bi + 1], eps)[:-1] + _dp(P[bi:], eps)


def clean(pts, step=0.8, iters=6, corner=38.0, eps=0.1, base=2.0):
    """smooth a traced (pixel-noisy) outline but keep its real corners: resample, Laplacian smooth between
    corners (turning angle > `corner` deg measured over +-`base` mm), re-simplify to `eps` mm."""
    P = _resample_open([_v2(p) for p in pts] + [_v2(pts[0])], step)[:-1]
    n = len(P)
    if n < 6:
        return [(p.x, p.y) for p in P]
    k = max(1, round(base / step))
    turn = []
    for i in range(n):
        d1 = P[i] - P[(i - k) % n]
        d2 = P[(i + k) % n] - P[i]
        turn.append(math.degrees(d1.angle(d2, 0.0)) if d1.length > 1e-9 and d2.length > 1e-9 else 0.0)
    corners = [i for i in range(n) if turn[i] > corner and turn[i] >= max(turn[(i + j) % n] for j in range(-k, k + 1))]
    # non-maximum suppression leaves plateaus: keep one per run
    cs = []
    for i in corners:
        if not cs or i - cs[-1] > k:
            cs.append(i)
    if len(cs) > 1 and cs[0] + n - cs[-1] <= k:
        cs.pop()
    fixed = set(cs)
    for _ in range(iters):
        Q = list(P)
        for i in range(n):
            if i in fixed:
                continue
            Q[i] = P[i] * 0.5 + (P[i - 1] + P[(i + 1) % n]) * 0.25
        P = Q
    if not cs:
        half = n // 2
        out = _dp(P[:half + 1], eps)[:-1] + _dp(P[half:] + [P[0]], eps)[:-1]
    else:
        out = []
        for j, c in enumerate(cs):
            d = cs[(j + 1) % len(cs)]
            chain = P[c:d + 1] if d > c else P[c:] + P[:d + 1]
            out += _dp(chain, eps)[:-1]
    return [(p.x, p.y) for p in out]


def hull(pts):
    """convex hull (monotone chain), CCW."""
    P = sorted(set((round(p[0], 6), round(p[1], 6)) for p in pts))
    if len(P) < 3:
        return P
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def hull_circles(circles, n=48):
    """smooth convex outline around circles [(cx, cy, r), ...] (stamped shrouds, sight bases...)."""
    pts = []
    for cx, cy, r in circles:
        pts += [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    return hull(pts)


def rrect(x0, x1, y0, y1, r):
    """rounded rectangle as (x, y, r) corner points for prep()/extrude."""
    return [(x0, y0, r), (x1, y0, r), (x1, y1, r), (x0, y1, r)]


def offset_poly(pts, d):
    """naive polygon offset (miter, positive = outward for a CCW polygon). Fine for smooth/convex-ish shapes."""
    P = [_v2(p) for p in ccw(pts)]
    n = len(P)
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        n1 = Vector(((b - a).y, -(b - a).x)).normalized()
        n2 = Vector(((c - b).y, -(c - b).x)).normalized()
        m = (n1 + n2)
        if m.length < 1e-6:
            m = n1
        m.normalize()
        cosh = max(0.3, m.dot(n1))
        out.append(tuple(b + m * (d / cosh)))
    return out


def clip_u(pts, u0=None, u1=None):
    """clip a polygon to u0 <= u <= u1 (Sutherland-Hodgman)."""
    def clip(P, keep, inter):
        out = []
        for i in range(len(P)):
            a, b = P[i - 1], P[i]
            if keep(b):
                if not keep(a):
                    out.append(inter(a, b))
                out.append(b)
            elif keep(a):
                out.append(inter(a, b))
        return out
    P = [tuple(p[:2]) for p in pts]
    for lim, sgn in ((u0, 1), (u1, -1)):
        if lim is None or not P:
            continue
        keep = lambda p, lim=lim, sgn=sgn: (p[0] - lim) * sgn >= 0
        inter = lambda a, b, lim=lim: (lim, a[1] + (b[1] - a[1]) * (lim - a[0]) / ((b[0] - a[0]) or 1e-9))
        P = clip(P, keep, inter)
    return P


def interp(table, t):
    """piecewise-linear lookup in [(t, value...), ...] (values may be tuples)."""
    if callable(table):
        return table(t)
    if not isinstance(table, (list, tuple)) or not table or not isinstance(table[0], (list, tuple)):
        return table
    if t <= table[0][0]:
        r = table[0][1:]
    elif t >= table[-1][0]:
        r = table[-1][1:]
    else:
        for i in range(len(table) - 1):
            a, b = table[i], table[i + 1]
            if a[0] <= t <= b[0]:
                f = (t - a[0]) / ((b[0] - a[0]) or 1e-9)
                r = tuple(x + (y - x) * f for x, y in zip(a[1:], b[1:]))
                break
    return r[0] if len(r) == 1 else r


def section(Wt, Wb, H, rt, rb, n=4, y0=None):
    """rounded trapezoid (x across = w, y up), top width Wt, bottom width Wb, height H, corner radii rt / rb;
    4 * (n + 1) points, counter-clockwise starting at the top right. y spans [y0, y0 + H] (default centred)."""
    y0 = -H / 2 if y0 is None else y0
    y1 = y0 + H
    Wt, Wb = max(Wt, 0.02), max(Wb, 0.02)
    H = max(H, 0.02)
    # corners: TR, TL, BL, BR (counter-clockwise seen from +t looking back: x right, y up)
    C = [Vector((Wt / 2, y1)), Vector((-Wt / 2, y1)), Vector((-Wb / 2, y0)), Vector((Wb / 2, y0))]
    R = [rt, rt, rb, rb]
    out = []
    for i in range(4):
        a, b, c = C[i - 1], C[i], C[(i + 1) % 4]
        lim = 0.5 * min((a - b).length, (c - b).length) - 1e-3
        out.extend(_fillet(a, b, c, max(0.0, min(R[i], lim)), steps=n))
    return [(p.x, p.y) for p in out]


def ellipse(W, H, n=4, y0=None):
    """ellipse with the same point count as section()."""
    m = 4 * (n + 1)
    yc = 0 if y0 is None else y0 + H / 2
    return [(W / 2 * math.cos(2 * math.pi * (k + 0.5) / m), yc + H / 2 * math.sin(2 * math.pi * (k + 0.5) / m))
            for k in range(m)]


class Frame:
    """2D frame in the side plane: t along `a` degrees from +u, s perpendicular (left of t)."""

    def __init__(self, o=(0, 0), a=0.0):
        self.o = Vector(o[:2])
        r = math.radians(a)
        self.t = Vector((math.cos(r), math.sin(r)))
        self.s = Vector((-math.sin(r), math.cos(r)))

    def uv(self, t, s):
        p = self.o + self.t * t + self.s * s
        return p.x, p.y

    def ts(self, u, v):
        d = Vector((u, v)) - self.o
        return d.dot(self.t), d.dot(self.s)


# ------------------------------------------------------------------ mesh building

class MB:
    """mesh under construction: verts in mm (u, v, w), faces with a material key and per-loop UVs in mm."""

    def __init__(self):
        self.v = []
        self.f = []

    def vert(self, u, v, w):
        self.v.append((w, u, v))
        return len(self.v) - 1

    def face(self, idx, mat, uvs):
        if len(set(idx)) >= 3:
            self.f.append((list(idx), mat, uvs))

    def obj(self, name, coll, recalc=True, merge=True):
        me = bpy.data.meshes.new(name)
        mats = []
        for _, m, _ in self.f:
            if m not in mats:
                mats.append(m)
        me.from_pydata([(x * S, y * S, z * S) for x, y, z in self.v], [], [f[0] for f in self.f])
        for m in mats:
            me.materials.append(materials.get(m))
        mi = [mats.index(f[1]) for f in self.f]
        me.polygons.foreach_set('material_index', mi)
        uvl = me.uv_layers.new(name='UVMap')
        rng = np.random.default_rng(int(hashlib.md5(name.encode()).hexdigest()[:8], 16))
        off = rng.random(2)
        data = []
        for (idx, m, uvs) in self.f:
            tu, tv = materials.TILE[m]
            for (a, b) in uvs:
                data += [a / tu + off[0], b / tv + off[1]]
        uvl.data.foreach_set('uv', data)
        me.validate()
        bm = bmesh.new()
        bm.from_mesh(me)
        if merge:
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.004 * S)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=0.002 * S)
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)


def bevel(ob, width, seg=3, angle=40.0, profile=0.5):
    if width <= 0:
        return ob
    m = ob.modifiers.new('bevel', 'BEVEL')
    m.width = width * S
    m.segments = seg
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.use_clamp_overlap = True
    m.profile = profile
    m.miter_outer = 'MITER_ARC'
    apply_mods(ob)
    return ob


def _plane(plane, a, b, d):
    """profile coords (a, b) + depth d -> (u, v, w)."""
    if plane == 'side':
        return a, b, d
    if plane == 'front':     # (w, v) section, depth along u
        return d, b, a
    if plane == 'top':       # (u, w) outline, depth along v
        return a, d, b
    raise ValueError(plane)


# ------------------------------------------------------------------ the gun being built

class Gun:
    def __init__(self, gid, ref=None, coll=None):
        self.id = gid
        self.ref = ref or gid
        self.coll = coll or _fresh_collection('W_' + gid)
        self.tmp = _fresh_collection('W_tmp')
        self.items = []           # (object, part)
        self.anchors = {}
        self.pivots = {}
        self.meta = {}
        self._part = 'body'
        self._n = 0
        self.objects = {}         # finished part objects

    # --- context
    @contextmanager
    def part(self, name):
        old = self._part
        self._part = name
        try:
            yield
        finally:
            self._part = old

    def _new(self, mb, name, part, cutter, **kw):
        self._n += 1
        nm = f'{self.id}~{name}{self._n}'
        ob = mb.obj(nm, self.tmp if cutter else self.coll, **kw)
        if not cutter:
            self.items.append((ob, part or self._part))
        return ob

    def anchor(self, name, u, v, w=0.0):
        self.anchors[name] = (u, v, w)

    def pivot(self, part, u, v, w=0.0):
        self.pivots[part] = (u, v, w)

    def set(self, **kw):
        self.meta.update(kw)

    # --- primitives
    def extrude(self, pts, d0=None, d1=None, mat='blued', holes=(), plane='side', width=None, bevel=0.6, seg=3,
                angle=40.0, part=None, name='ext', cutter=False, uvrot=0.0, per90=4):
        """closed profile extruded between depths d0..d1 (or `width` centred on 0)."""
        if width is not None:
            d0, d1 = -width / 2, width / 2
        outer = ccw(prep(pts, per90))
        hs = [cw(prep(h, per90)) for h in holes]
        loops = [outer] + hs
        flat = [p for l in loops for p in l]
        tris = geometry.tessellate_polygon([[Vector((p[0], p[1], 0)) for p in l] for l in loops])
        mb = MB()
        ca, sa = math.cos(math.radians(uvrot)), math.sin(math.radians(uvrot))
        cuv = lambda p: (p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca)
        lo = [mb.vert(*_plane(plane, p[0], p[1], d0)) for p in flat]
        hi = [mb.vert(*_plane(plane, p[0], p[1], d1)) for p in flat]
        for t in tris:
            mb.face([hi[t[0]], hi[t[1]], hi[t[2]]], mat, [cuv(flat[i]) for i in t])
            mb.face([lo[t[2]], lo[t[1]], lo[t[0]]], mat, [cuv(flat[i]) for i in (t[2], t[1], t[0])])
        base = 0
        for l in loops:
            n = len(l)
            s = 0.0
            for i in range(n):
                j = (i + 1) % n
                L = math.dist(l[i], l[j])
                a, b = base + i, base + j
                wuv = [(s, d0), (s + L, d0), (s + L, d1), (s, d1)]
                if plane == 'front':   # depth runs along the gun: keep texture u (streaks, grain) along it
                    wuv = [(d, t) for t, d in wuv]
                mb.face([lo[a], lo[b], hi[b], hi[a]], mat, wuv)
                s += L
            base += n
        ob = self._new(mb, name, part, cutter)
        if bevel:
            globals()['bevel'](ob, bevel, seg, angle)
        return ob

    def box(self, u0, u1, v0, v1, w0=None, w1=None, mat='blued', width=None, bevel=0.5, **kw):
        return self.extrude([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], w0, w1, mat, width=width, bevel=bevel, **kw)

    def loft(self, rings, mat='blued', caps=(True, True), part=None, name='loft', cutter=False, closed=False):
        """rings: list of point lists [(u, v, w), ...], equal length, consistent order."""
        mb = MB()
        R = [[mb.vert(*p) for p in ring] for ring in rings]
        m = len(rings[0])
        # uv: u = distance along the ring centroids, v = perimeter arc
        cents = [Vector(tuple(sum(p[i] for p in ring) / m for i in range(3))) for ring in rings]
        along = [0.0]
        for i in range(1, len(rings)):
            along.append(along[-1] + (cents[i] - cents[i - 1]).length)
        arcs = []
        for ring in rings:
            a = [0.0]
            for k in range(1, m + 1):
                a.append(a[-1] + math.dist(ring[k - 1], ring[k % m]))
            arcs.append(a)
        nr = len(rings) if not closed else len(rings) + 1
        for i in range(nr - 1):
            i2 = (i + 1) % len(rings)
            for k in range(m):
                k2 = (k + 1) % m
                ta, tb = along[i], along[i2] if i2 else along[-1] + (cents[0] - cents[-1]).length
                mb.face([R[i][k], R[i][k2], R[i2][k2], R[i2][k]], mat,
                        [(ta, arcs[i][k]), (ta, arcs[i][k + 1]), (tb, arcs[i2][k + 1]), (tb, arcs[i2][k])])
        if not closed:
            for which, ring, idx in ((0, rings[0], R[0]), (1, rings[-1], R[-1])):
                if not caps[which]:
                    continue
                c = cents[0 if which == 0 else -1]
                ci = mb.vert(c.x, c.y, c.z)
                # cap uv: planar projection on the two largest extents
                for k in range(m):
                    k2 = (k + 1) % m
                    p, q = ring[k], ring[k2]
                    mb.face([idx[k], idx[k2], ci] if which else [idx[k2], idx[k], ci], mat,
                            [(p[0] + p[2], p[1]), (q[0] + q[2], q[1]), (c.x + c.z, c.y)] if which else
                            [(q[0] + q[2], q[1]), (p[0] + p[2], p[1]), (c.x + c.z, c.y)])
        return self._new(mb, name, part, cutter)

    def sweep(self, outline, mat='walnut', width=30.0, radius=6.0, axis=0.0, origin=(0, 0), step=3.0, n=4,
              t0=None, t1=None, top=1.0, wc=0.0, shape='rect', inset=0.25, round_ends=(0.0, 0.0), part=None,
              name='sweep', cutter=False, pick='max'):
        """part whose side silhouette is `outline` (closed (u, v) polygon), with rounded sections across w.
        Sections are cut perpendicular to the axis (`axis` degrees from +u through `origin`), so the outline should
        be single-span along it. width / radius / top / wc: number, callable(t) or [(t, value), ...] with t in mm
        along the axis (for axis=0 and origin=(0, 0), t == u). radius may be (r_top, r_bottom). top = top width as
        a fraction of the bottom width. round_ends = (start, end) mm of round-over at the end caps."""
        P = prep(outline)
        fr = Frame(origin, axis)
        TS = [fr.ts(*p) for p in P]
        tmin = max(min(t for t, _ in TS), t0 if t0 is not None else -1e9)
        tmax = min(max(t for t, _ in TS), t1 if t1 is not None else 1e9)
        L = tmax - tmin
        N = max(2, math.ceil(L / step))
        ts = []
        for k in range(N + 1):
            x = k / N
            x = 0.75 * x + 0.25 * (0.5 - 0.5 * math.cos(math.pi * x))     # a little denser near the ends
            ts.append(tmin + inset + (L - 2 * inset) * x)
        rings = []
        prev = None
        for t in ts:
            xs = []
            for i in range(len(TS)):
                (ta, sa), (tb, sb) = TS[i - 1], TS[i]
                if (ta - t) * (tb - t) < 0 or (ta == t and tb != t):
                    xs.append(sa + (sb - sa) * (t - ta) / (tb - ta))
            xs.sort()
            spans = [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]
            if not spans:
                continue
            if pick == 'max' or prev is None:
                s0, s1 = max(spans, key=lambda s: s[1] - s[0])
            else:
                s0, s1 = min(spans, key=lambda s: abs((s[0] + s[1]) / 2 - prev))
            prev = (s0 + s1) / 2
            rings.append(self._ring(fr, t, s0, s1, interp(width, t), interp(radius, t), interp(top, t),
                                    interp(wc, t), n, shape))
        rings = self._round_ends(rings, fr, round_ends)
        return self.loft(rings, mat, part=part, name=name, cutter=cutter)

    def _ring(self, fr, t, s0, s1, W, r, top, wc, n, shape):
        rt, rb = (r, r) if not isinstance(r, (tuple, list)) else r
        H = s1 - s0
        if shape == 'ellipse':
            sec = ellipse(W, H, n, y0=0)
        else:
            sec = section(W * top, W, H, rt, rb, n, y0=0)
        out = []
        for x, y in sec:
            u, v = fr.uv(t, s0 + y)
            out.append((u, v, wc + x))
        return out

    def _round_ends(self, rings, fr, round_ends):
        """approximate a round-over at the open ends by shrinking extra rings toward the cap."""
        out = list(rings)
        for which in (0, 1):
            b = round_ends[which]
            if not b or len(rings) < 2:
                continue
            ring = rings[0] if which == 0 else rings[-1]
            nxt = rings[1] if which == 0 else rings[-2]
            m = len(ring)
            c = Vector([sum(p[i] for p in ring) / m for i in range(3)])
            cn = Vector([sum(p[i] for p in nxt) / m for i in range(3)])
            d = (c - cn).normalized()
            extra = []
            for f in (0.5, 0.85, 1.0):
                ang = math.acos(1 - f) if f < 1 else math.pi / 2
                shrink = b * (1 - math.cos(ang))
                fwd = b * math.sin(ang)
                rr = []
                for p in ring:
                    pv = Vector(p)
                    rad = pv - c - d * (pv - c).dot(d)
                    L = rad.length
                    k = max(0.15, (L - shrink) / L) if L > 1e-6 else 1
                    q = c + rad * k + d * (fwd - b)
                    rr.append(tuple(q))
                extra.append(rr)
            # the original end ring moves back by b so the total length is kept
            base = [tuple(Vector(p) - d * b) for p in ring]
            if which == 0:
                out = list(reversed(extra)) + [base] + out[1:]
            else:
                out = out[:-1] + [base] + extra
        return out

    def lathe(self, prof, mat='blued', axis='u', at=(0.0, 0.0), seg=24, closed=False, part=None, name='lathe',
              cutter=False, a0=0.0, a1=360.0, smooth=True):
        """solid of revolution. prof: [(x, r), ...] along the axis (x = u, v or w); `at` = the axis position in the
        other two coords ((v, w) for axis u, (u, w) for axis v, (u, v) for axis w). Open profiles get end discs
        where r > 0; closed=True treats prof as a closed loop (tubes, rings)."""
        P = prep(prof, closed=closed)
        full = abs(a1 - a0) >= 359.999
        nseg = seg if full else max(1, round(seg * abs(a1 - a0) / 360))
        angs = [math.radians(a0 + (a1 - a0) * k / nseg) for k in range(nseg + 1)]

        def pos(x, r, a):
            c, s = r * math.cos(a), r * math.sin(a)
            if axis == 'u':      # angle 0 = +v (up), 90 = +w
                return x, at[0] + c, at[1] + s
            if axis == 'v':      # angle 0 = +u, 90 = +w
                return at[0] + c, x, at[1] + s
            return at[0] + c, at[1] + s, x   # axis w: angle 0 = +u, 90 = +v

        mb = MB()
        ring_count = len(P)
        ids = [[mb.vert(*pos(x, r, a)) for a in (angs[:-1] if full else angs)] for x, r in P]
        na = nseg if full else nseg + 1
        arcl = [0.0]
        for i in range(1, len(P)):
            arcl.append(arcl[-1] + math.dist(P[i - 1], P[i]))
        rows = range(ring_count) if closed else range(ring_count - 1)
        for i in rows:
            i2 = (i + 1) % ring_count
            rm = 0.5 * (P[i][1] + P[i2][1])
            for k in range(nseg):
                k2 = (k + 1) % na if full else k + 1
                ua, ub = arcl[i], arcl[i2] if i2 else arcl[-1] + math.dist(P[-1], P[0])
                ca, cb = angs[k] * max(rm, 2), angs[k + 1] * max(rm, 2)
                mb.face([ids[i][k], ids[i2][k], ids[i2][k2], ids[i][k2]], mat, [(ua, ca), (ub, ca), (ub, cb), (ua, cb)])
        if not closed and full:
            for end in (0, ring_count - 1):
                x, r = P[end]
                if r <= 1e-6:
                    continue
                c = mb.vert(*pos(x, 0, 0))
                for k in range(nseg):
                    k2 = (k + 1) % na
                    a, b = angs[k], angs[k + 1]
                    mb.face([ids[end][k], ids[end][k2], c], mat,
                            [(r * math.cos(a), r * math.sin(a)), (r * math.cos(b), r * math.sin(b)), (0, 0)])
        ob = self._new(mb, name, part, cutter)
        return ob

    def cyl(self, x0, x1, r, mat='blued', axis='u', at=(0.0, 0.0), seg=20, chamfer=0.3, **kw):
        c = min(chamfer, r * 0.4, abs(x1 - x0) * 0.4)
        if c > 0:
            prof = [(x0, 0), (x0, r - c), (x0 + c, r), (x1 - c, r), (x1, r - c), (x1, 0)]
        else:
            prof = [(x0, 0), (x0, r), (x1, r), (x1, 0)]
        return self.lathe(prof, mat, axis, at, seg, **kw)

    def tube(self, x0, x1, r_out, r_in, mat='blued', axis='u', at=(0.0, 0.0), seg=24, chamfer=0.3, **kw):
        c = min(chamfer, (r_out - r_in) * 0.4)
        prof = [(x0, r_in), (x0, r_out - c), (x0 + c, r_out), (x1 - c, r_out), (x1, r_out - c), (x1, r_in)]
        return self.lathe(prof, mat, axis, at, seg, closed=True, **kw)

    def pipe(self, path, r, mat='blued', seg=10, closed=False, corner=0.0, part=None, name='pipe', cutter=False,
             caps=True):
        """round bar of radius r along a 3D path [(u, v, w), ...]; corner = fillet radius at the path vertices."""
        Pt = [Vector(p) for p in path]
        if corner > 0 and len(Pt) > 2:
            Q = [Pt[0]] if not closed else []
            n = len(Pt)
            rng = range(n) if closed else range(1, n - 1)
            for i in rng:
                a, b, c = Pt[i - 1], Pt[i], Pt[(i + 1) % n]
                d1, d2 = (a - b), (c - b)
                ang = d1.angle(d2, 0.0)
                if ang < 1e-3 or abs(ang - math.pi) < 1e-3:
                    Q.append(b)
                    continue
                t = min(corner / math.tan(ang / 2), 0.5 * d1.length, 0.5 * d2.length)
                p1, p2 = b + d1.normalized() * t, b + d2.normalized() * t
                for k in range(7):
                    f = k / 6
                    Q.append((1 - f) ** 2 * p1 + 2 * (1 - f) * f * b + f * f * p2)    # quadratic approx of the arc
            if not closed:
                Q.append(Pt[-1])
            Pt = Q
        n = len(Pt)
        tang = []
        for i in range(n):
            if closed:
                d = Pt[(i + 1) % n] - Pt[i - 1]
            else:
                d = Pt[min(i + 1, n - 1)] - Pt[max(i - 1, 0)]
            tang.append(d.normalized())
        ref = Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((0, 1, 0))
        nrm = (ref - tang[0] * ref.dot(tang[0])).normalized()
        rings = []
        for i in range(n):
            if i:
                nrm = (nrm - tang[i] * nrm.dot(tang[i])).normalized()
            bi = tang[i].cross(nrm)
            rings.append([tuple(Pt[i] + (nrm * math.cos(2 * math.pi * k / seg) + bi * math.sin(2 * math.pi * k / seg)) * r)
                          for k in range(seg)])
        return self.loft(rings, mat, caps=(caps, caps), part=part, name=name, cutter=cutter, closed=closed)

    # --- operations
    def cut(self, target, *cutters, solver='EXACT', op='DIFFERENCE'):
        cs = [c for c in cutters if c is not None]
        if not cs:
            return target
        if len(cs) > 1:
            cutter = join(cs, cs[0].name + '_j')
        else:
            cutter = cs[0]
        m = target.modifiers.new('bool', 'BOOLEAN')
        m.operation = op
        m.solver = solver
        m.object = cutter
        if hasattr(m, 'use_self'):
            m.use_self = False
        apply_mods(target)
        bpy.data.objects.remove(cutter)
        return target

    def intersect(self, target, other):
        if other.users_collection and other.users_collection[0] == self.coll:
            self.items = [it for it in self.items if it[0] != other]
        return self.cut(target, other, op='INTERSECT')

    def drop(self, ob):
        """remove an object created earlier (e.g. after deciding to use it as a cutter)."""
        self.items = [it for it in self.items if it[0] != ob]
        bpy.data.objects.remove(ob)

    def transform(self, obs, rot=None, move=(0, 0, 0), scale=None, pivot=(0, 0, 0)):
        """rot = (axis 'u'|'v'|'w', degrees) about `pivot` (u, v, w); +deg about w turns +u toward +v."""
        if not isinstance(obs, (list, tuple)):
            obs = [obs]
        pv = Vector((pivot[2], pivot[0], pivot[1])) * S
        M = Matrix.Translation(Vector((move[2], move[0], move[1])) * S) @ Matrix.Translation(pv)
        if rot:
            ax = {'w': 'X', 'u': 'Y', 'v': 'Z'}[rot[0]]
            M = M @ Matrix.Rotation(math.radians(rot[1]), 4, ax)
        if scale:
            sc = scale if isinstance(scale, (tuple, list)) else (scale,) * 3
            M = M @ Matrix.Diagonal((sc[2], sc[0], sc[1], 1))
        M = M @ Matrix.Translation(-pv)
        for ob in obs:
            ob.data.transform(M)
            if M.determinant() < 0:
                ob.data.flip_normals()
        return obs

    def mirror_w(self, ob, name=None):
        """copy of ob mirrored to the other side (w -> -w)."""
        me = ob.data.copy()
        me.transform(Matrix.Diagonal((-1, 1, 1, 1)))
        me.flip_normals()
        nob = bpy.data.objects.new(name or ob.name + '_m', me)
        self.coll.objects.link(nob)
        part = next((p for o, p in self.items if o == ob), self._part)
        self.items.append((nob, part))
        return nob

    def dup(self, ob, move=(0, 0, 0), rot=None, pivot=(0, 0, 0), cutter=False):
        me = ob.data.copy()
        nob = bpy.data.objects.new(ob.name + '_d', me)
        (self.tmp if cutter else self.coll).objects.link(nob)
        if not cutter:
            part = next((p for o, p in self.items if o == ob), self._part)
            self.items.append((nob, part))
        self.transform(nob, rot=rot, move=move, pivot=pivot)
        return nob

    # --- reference tracing
    def trace(self, region=None, ref=None, **opts):
        """mask outlines of the reference inside `region` (polygon, mm): [{'outer', 'holes', 'area'}, ...]."""
        ref = ref or self.ref
        q = dict(opts)
        if region:
            q['region'] = [[round(float(a), 3), round(float(b), 3)] for a, b in region]
        key = hashlib.sha1(json.dumps([ref, q], sort_keys=True).encode()).hexdigest()[:16]
        os.makedirs(TRACES, exist_ok=True)
        path = os.path.join(TRACES, ref + '.json')
        cache = json.load(open(path)) if os.path.exists(path) else {}
        if key not in cache:
            if not os.path.exists(os.path.join(REF, ref + '_mask.png')):
                raise RuntimeError(f'no cached trace and no reference mask for {ref} (run reftool.py fetch + rect)')
            r = subprocess.run([PY, os.path.join(HERE, 'reftool.py'), 'trace', ref, json.dumps(q)],
                               capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError(r.stderr)
            cache[key] = json.loads(r.stdout)
            json.dump(cache, open(path, 'w'))
        return cache[key]

    def outline(self, region=None, idx=0, smooth=True, ref=None, holes=False, **opts):
        """the idx-th largest traced outline in region, cleaned of pixel noise -> [(u, v), ...] (CCW)."""
        res = self.trace(region, ref, **opts)
        if not res:
            raise RuntimeError(f'{self.id}: nothing traced in {region}')
        o = res[idx]
        pts = clean(o['outer']) if smooth else [tuple(p) for p in o['outer']]
        if holes:
            return ccw(pts), [cw(clean(h) if smooth else h) for h in o['holes']]
        return ccw(pts)

    # --- finishing
    def finish(self, smooth_angle=38.0, weighted=True):
        """join objects per part, set pivots, shading; anchors become empties named <id>@<name>."""
        parts = {}
        for ob, p in self.items:
            parts.setdefault(p, []).append(ob)
        for p, obs in parts.items():
            ob = join(obs, f'{self.id}.{p}')
            me = ob.data
            # flat faces come out as fans of thin triangles whose vertices all lie on the border; merged back into
            # n-gons they outweigh the bevels in the weighted normals and shade flat instead of streaky
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.3), use_dissolve_boundaries=False,
                                     verts=bm.verts[:], edges=bm.edges[:], delimit={'MATERIAL', 'UV'})
            bm.to_mesh(me)
            bm.free()
            me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
            if hasattr(me, 'set_sharp_from_angle'):
                me.set_sharp_from_angle(angle=math.radians(smooth_angle))
            if weighted:
                m = ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
                m.keep_sharp = True
                m.mode = 'FACE_AREA_WITH_ANGLE'
                m.weight = 60
                apply_mods(ob)
            pu, pv, pw = self.pivots.get(p, (0, 0, 0))
            T = Vector((pw, pu, pv)) * S
            ob.data.transform(Matrix.Translation(-T))
            ob.location = T
            ob['part'] = p
            ob['gun'] = self.id
            self.objects[p] = ob
        for name, (u, v, w) in self.anchors.items():
            e = bpy.data.objects.new(f'{self.id}@{name}', None)
            e.empty_display_size = 0.01
            e.location = (w * S, u * S, v * S)
            self.coll.objects.link(e)
        for o in list(self.tmp.objects):
            bpy.data.objects.remove(o)
        return self.objects

    def tris(self):
        return sum(sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob in self.objects.values())


def join(obs, name):
    """merge meshes (all with identity transforms) into one object named `name`, in the first object's collection."""
    coll = obs[0].users_collection[0]
    bm = bmesh.new()
    mats = []
    for ob in obs:
        me = ob.data.copy()
        me.transform(ob.matrix_world)
        remap = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        if remap:
            idx = np.zeros(len(me.polygons), np.int32)
            me.polygons.foreach_get('material_index', idx)
            me.polygons.foreach_set('material_index', np.array(remap, np.int32)[idx])
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    nm = bpy.data.meshes.new(name)
    bm.to_mesh(nm)
    bm.free()
    for m in mats:
        nm.materials.append(m)
    for ob in obs:
        bpy.data.objects.remove(ob)
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old)
    out = bpy.data.objects.new(name, nm)
    coll.objects.link(out)
    return out


def _fresh_collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o)
    return c
