"""Modelling kit for the motorcycles. Model frame: x right, y forward, z up, metres; origin on the ground midway
between the axles (the game's bike position). glTF turns that into three.js x right, y up, z back.

A Bike collects geometry per part (body, fork, wheel_f, wheel_r, lamp) into bmeshes with material slots, then makes
one object per part. Side-view shapes are drawn in the reference photo's pixels: Bike.P(px, py) -> (y, z).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

TAU = math.pi * 2


# --- 2D helpers -----------------------------------------------------------------------------------------------------

def superellipse(w, h, n=24, p=2.6, phase=0.0):
    """closed section, w wide (x) and h tall (y), centred; p=2 ellipse, larger is squarer."""
    out = []
    for i in range(n):
        a = phase + TAU * i / n
        c, s = math.cos(a), math.sin(a)
        out.append((w / 2 * math.copysign(abs(c) ** (2 / p), c), h / 2 * math.copysign(abs(s) ** (2 / p), s)))
    return out


def rrect(w, h, r, n=4):
    """closed rounded rectangle section, centred."""
    r = min(r, w / 2 - 1e-5, h / 2 - 1e-5)
    out = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def fillet_path(pts, r, per90=4):
    """polyline with its interior corners rounded by radius r (a scalar or one per point)."""
    pts = [Vector(p) for p in pts]
    if len(pts) < 3:
        return pts
    rs = r if isinstance(r, (list, tuple)) else [r] * len(pts)
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u, v = (a - b), (c - b)
        if u.length < 1e-6 or v.length < 1e-6 or rs[i] <= 0:
            out.append(b)
            continue
        u.normalize()
        v.normalize()
        ang = u.angle(v)
        if ang > math.pi - 1e-3:
            out.append(b)
            continue
        t = rs[i] / math.tan(ang / 2)
        t = min(t, (a - b).length * 0.5, (c - b).length * 0.5)
        p0, p1 = b + u * t, b + v * t
        rr = t * math.tan(ang / 2)
        bis = (u + v).normalized()
        centre = b + bis * (rr / math.sin(ang / 2))
        steps = max(2, int(round((math.pi - ang) / (math.pi / 2) * per90)) + 1)
        d0, d1 = p0 - centre, p1 - centre
        for k in range(steps + 1):
            q = d0.slerp(d1, k / steps) if hasattr(d0, 'slerp') else d0.lerp(d1, k / steps)
            out.append(centre + q.normalized() * rr)
    out.append(pts[-1])
    return out


def bezier(p0, p1, p2, p3, n=12):
    p0, p1, p2, p3 = map(Vector, (p0, p1, p2, p3))
    out = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        out.append(p0 * mt ** 3 + p1 * 3 * mt * mt * t + p2 * 3 * mt * t * t + p3 * t ** 3)
    return out


def catmull(pts, n=6):
    """smooth curve through the points."""
    P = [Vector(p) for p in pts]
    if len(P) < 3:
        return P
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return out


def resample(pts, step):
    """polyline resampled at roughly even spacing (keeps the ends)."""
    P = [Vector(p) for p in pts]
    L = [0.0]
    for a, b in zip(P, P[1:]):
        L.append(L[-1] + (b - a).length)
    n = max(1, int(round(L[-1] / step)))
    out = []
    j = 0
    for k in range(n + 1):
        s = L[-1] * k / n
        while j < len(P) - 2 and L[j + 1] < s:
            j += 1
        seg = L[j + 1] - L[j]
        t = 0 if seg < 1e-9 else (s - L[j]) / seg
        out.append(P[j].lerp(P[j + 1], t))
    return out


# --- materials -------------------------------------------------------------------------------------------------------

def srgb(r, g, b):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (c(r), c(g), c(b))


def material(name, rgb, rough, metal=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    col = srgb(*rgb)
    b.inputs['Base Color'].default_value = (*col, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*srgb(*emit), 1.0)
        b.inputs['Emission Strength'].default_value = emit_strength
    else:
        b.inputs['Emission Strength'].default_value = 0.0
    m.diffuse_color = (*col, 1.0)
    m.use_backface_culling = True  # single sided in glTF too; wrong normals show up as holes in the previews
    return m


# --- the kit ---------------------------------------------------------------------------------------------------------

class Part:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []
        self.local = False  # geometry already in the part's own frame
        self.keep = set()   # faces whose winding is deliberate (flat decals), left out of the normals fix

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)


class Bike:
    PARTS = ('body', 'fork', 'wheel_f', 'wheel_r', 'lamp')

    def __init__(self, prefix, mats, cal=None):
        """mats: {key: bpy material}; cal: ((px, py) rear axle, (px, py) front axle, wheelbase m, axle height m)."""
        self.prefix = prefix
        self.M = mats
        self.parts = {p: Part(p) for p in self.PARTS}
        self.cur = self.parts['body']
        self.anchors = {}
        self.pivots = {}
        if cal:
            (ax, ay), (bx, by), wb, ah = cal
            self.c_a = Vector((ax, ay))
            d = Vector((bx - ax, by - ay))
            self.c_s = wb / d.length
            self.c_rot = math.atan2(d.y, d.x)
            self.c_wb, self.c_ah = wb, ah

    # side-view photo pixels -> model (y, z)
    def P(self, px, py):
        v = Vector((px, py)) - self.c_a
        c, s = math.cos(-self.c_rot), math.sin(-self.c_rot)
        x, y = v.x * c - v.y * s, v.x * s + v.y * c
        return (-self.c_wb / 2 + x * self.c_s, self.c_ah - y * self.c_s)

    def P3(self, px, py, x=0.0):
        y, z = self.P(px, py)
        return Vector((x, y, z))

    def px(self, n):
        """photo pixels -> metres."""
        return n * self.c_s

    def part(self, name):
        self.cur = self.parts[name]
        return self

    # --- raw geometry ---
    def add(self, verts, faces, mat, smooth=True, part=None, keep=False):
        p = self.parts[part] if part else self.cur
        bm = p.bm
        mi = p.mi(mat)
        vs = [bm.verts.new(v) for v in verts]
        out = []
        for f in faces:
            try:
                face = bm.faces.new([vs[i] for i in f])
            except ValueError:
                continue
            face.material_index = mi
            face.smooth = smooth
            out.append(face)
        if keep:
            p.keep.update(out)
        return out

    def sweep(self, path, sections, mat, closed_sec=True, cap0=False, cap1=False, up=None, smooth=True, part=None,
              frames=None):
        """section rings along a path. path: 3D points; sections: one 2D section (list of (a, b)) per path point, or
        one for all. Section axes: a along `side` (parallel-transported, starts perpendicular to the path in the
        plane of `up`), b along side x tangent. With the default up (+x) a path in the yz plane has a = x and b
        pointing to the path's left (up when the path runs forward)."""
        path = [Vector(p) for p in path]
        n = len(path)
        if sections and isinstance(sections[0][0], (int, float)):
            sections = [sections] * n
        if frames is None:
            frames = transport(path, Vector(up) if up else Vector((1, 0, 0)))
        verts, faces = [], []
        m = len(sections[0])
        for i, (p, (side, nrm)) in enumerate(zip(path, frames)):
            for a, b in sections[i]:
                verts.append(p + side * a + nrm * b)
        jm = m if closed_sec else m - 1
        for i in range(n - 1):
            for j in range(jm):
                j2 = (j + 1) % m
                faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
        if cap0 and closed_sec:
            faces.append(tuple(reversed(range(m))))
        if cap1 and closed_sec:
            faces.append(tuple((n - 1) * m + j for j in range(m)))
        return self.add(verts, faces, mat, smooth, part)

    def tube(self, pts, r, mat, seg=10, bend=0.0, caps=True, part=None, smooth_path=0, r1=None, up=None):
        """round tube through the points; bend rounds the corners, smooth_path>0 makes a Catmull-Rom curve instead."""
        P = catmull(pts, smooth_path) if smooth_path else fillet_path(pts, bend) if bend else [Vector(p) for p in pts]
        n = len(P)
        secs = []
        for i in range(n):
            rr = r if r1 is None else r + (r1 - r) * i / max(1, n - 1)
            secs.append([(rr * math.cos(TAU * k / seg), rr * math.sin(TAU * k / seg)) for k in range(seg)])
        return self.sweep(P, secs, mat, cap0=caps, cap1=caps, part=part, up=up)

    def lathe(self, prof, centre, axis, mat, seg=24, cap0=False, cap1=False, phase=0.0, smooth=True, part=None,
              ref=None):
        """revolve prof [(r, a)] (r radius, a along axis) about axis through centre."""
        c = Vector(centre)
        ax = Vector(axis).normalized()
        u = (ref or (Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0)))).cross(ax).normalized()
        v = ax.cross(u)
        verts, faces = [], []
        m = len(prof)
        for i in range(seg):
            a = phase + TAU * i / seg
            d = u * math.cos(a) + v * math.sin(a)
            for r, t in prof:
                verts.append(c + ax * t + d * r)
        for i in range(seg):
            i2 = (i + 1) % seg
            for j in range(m - 1):
                faces.append((i * m + j, i2 * m + j, i2 * m + j + 1, i * m + j + 1))
        if cap0 and prof[0][0] > 1e-6:
            faces.append(tuple(i * m for i in range(seg)))
        if cap1 and prof[-1][0] > 1e-6:
            faces.append(tuple(i * m + m - 1 for i in reversed(range(seg))))
        return self.add(verts, faces, mat, smooth, part)

    def cyl(self, a, b, r, mat, seg=16, caps=True, part=None, r1=None, smooth=True):
        a, b = Vector(a), Vector(b)
        L = (b - a).length
        rr = r if r1 is None else r1
        prof = [(r, 0.0), (rr, L)]
        if caps:
            prof = [(0.0, 0.0)] + prof + [(0.0, L)]
        return self.lathe(prof, a, b - a, mat, seg, part=part, smooth=smooth)

    def disc_stack(self, a, b, prof_r, mat, seg=20, part=None):
        """lathe along a->b of [(r, t in 0..1)]."""
        a, b = Vector(a), Vector(b)
        L = (b - a).length
        return self.lathe([(r, t * L) for r, t in prof_r], a, b - a, mat, seg, part=part)

    def box(self, c, size, mat, bevel=0.0, seg=2, rot=None, part=None, smooth=False):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=bevel, segments=seg, affect='EDGES',
                            profile=0.5)
        M = Matrix.Translation(Vector(c))
        if rot is not None:
            M = M @ (rot if isinstance(rot, Matrix) else euler(rot))
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        return self.take(bm, mat, smooth or bevel > 0, part)

    def take(self, bm, mat, smooth=True, part=None):
        """append a bmesh (freed afterwards)."""
        verts = [v.co.copy() for v in bm.verts]
        idx = {v: i for i, v in enumerate(bm.verts)}
        faces = [[idx[v] for v in f.verts] for f in bm.faces]
        bm.free()
        return self.add(verts, faces, mat, smooth, part)

    def prism(self, poly, x0, x1, mat, bevel=0.0, seg=1, part=None, smooth=False):
        """side-view polygon [(y, z)] extruded across x0..x1 (bevelled edges)."""
        bm = bmesh.new()
        vs0 = [bm.verts.new((x0, y, z)) for y, z in poly]
        vs1 = [bm.verts.new((x1, y, z)) for y, z in poly]
        n = len(poly)
        area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
        if area < 0:
            vs0.reverse()
            vs1.reverse()
        bm.faces.new(list(reversed(vs0)))
        bm.faces.new(vs1)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((vs0[i], vs0[j], vs1[j], vs1[i]))
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=seg, affect='EDGES', profile=0.5,
                            clamp_overlap=True)
        return self.take(bm, mat, smooth or bevel > 0, part)

    def plate(self, poly3, thick, mat, part=None, smooth=False):
        """flat plate from a planar 3D polygon, thick along its normal."""
        P = [Vector(p) for p in poly3]
        nrm = (P[1] - P[0]).cross(P[2] - P[0]).normalized()
        n = len(P)
        verts = [p - nrm * thick / 2 for p in P] + [p + nrm * thick / 2 for p in P]
        faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        return self.add(verts, faces, mat, smooth, part)

    def spring(self, a, b, r, wire, turns, mat, seg=6, per_turn=10, part=None):
        a, b = Vector(a), Vector(b)
        ax = (b - a)
        L = ax.length
        ax.normalize()
        u = (Vector((1, 0, 0)) if abs(ax.x) < 0.9 else Vector((0, 1, 0))).cross(ax).normalized()
        v = ax.cross(u)
        n = int(turns * per_turn)
        pts = [a + ax * (L * k / n) + (u * math.cos(TAU * turns * k / n) + v * math.sin(TAU * turns * k / n)) * r
               for k in range(n + 1)]
        return self.tube(pts, wire, mat, seg=seg, part=part)

    def mirror_x(self, fn):
        """run fn(sign) for the right (+1) and the left (-1) side."""
        for s in (1, -1):
            fn(s)

    def anchor(self, name, p):
        """a named point (an empty in the export) that moves with the current part: seat, grips, foot rests."""
        self.anchors[name] = (Vector(p), self.cur.name)

    def pivot(self, part, origin, rot=None):
        """part's object origin (and rotation): fork about the steering axis, wheels at their axles."""
        self.pivots[part] = (Vector(origin), rot)

    # --- build the objects ---
    def finish(self, coll, smooth_angle=50.0):
        objs = {}
        for name, p in self.parts.items():
            if not p.bm.faces:
                p.bm.free()
                continue
            me = bpy.data.meshes.new(f'{self.prefix}_{name}')
            bmesh.ops.recalc_face_normals(p.bm, faces=[f for f in p.bm.faces if f not in p.keep])
            bmesh.ops.remove_doubles(p.bm, verts=p.bm.verts[:], dist=1e-6)
            p.bm.to_mesh(me)
            p.bm.free()
            for m in p.mats:
                me.materials.append(self.M[m])
            if hasattr(me, 'set_sharp_from_angle'):
                me.set_sharp_from_angle(angle=math.radians(smooth_angle))
            ob = bpy.data.objects.new(f'{self.prefix}_{name}', me)
            coll.objects.link(ob)
            o, rot = self.pivots.get(name, (Vector((0, 0, 0)), None))
            W = Matrix.Translation(o) @ (rot.to_4x4() if rot is not None else Matrix.Identity(4))
            if not p.local:
                me.transform(W.inverted())
            ob.matrix_world = W
            objs[name] = ob
        # hierarchy: fork and rear wheel on the body, front wheel and lamp on the fork
        par = {'fork': 'body', 'wheel_r': 'body', 'wheel_f': 'fork', 'lamp': 'fork'}
        for c, pn in par.items():
            if c in objs and pn in objs:
                mw = objs[c].matrix_world.copy()
                objs[c].parent = objs[pn]
                objs[c].matrix_parent_inverse = objs[pn].matrix_world.inverted()
                objs[c].matrix_world = mw
        for k, (v, pn) in self.anchors.items():
            e = bpy.data.objects.new(f'{self.prefix}_{k}', None)
            e.empty_display_size = 0.05
            coll.objects.link(e)
            pa = objs[pn]
            e.parent = pa
            e.matrix_parent_inverse = Matrix.Identity(4)
            e.matrix_world = Matrix.Translation(v)
        return objs


def euler(r):
    from mathutils import Euler
    return Euler(r, 'XYZ').to_matrix().to_4x4()


def transport(path, up):
    """parallel-transported (side, normal) frames along a path; side starts as `up` made perpendicular."""
    n = len(path)
    T = []
    for i in range(n):
        d = Vector((0, 0, 0))
        if i > 0:
            s = path[i] - path[i - 1]
            if s.length > 1e-9:
                d += s.normalized()
        if i < n - 1:
            s = path[i + 1] - path[i]
            if s.length > 1e-9:
                d += s.normalized()
        T.append(d.normalized() if d.length > 1e-9 else None)
    for i in range(n):  # zero-length steps take a neighbour's tangent
        if T[i] is None:
            T[i] = next((T[j] for j in list(range(i, n)) + list(range(i, -1, -1)) if T[j] is not None), Vector((0, 1, 0)))
    side = up - T[0] * up.dot(T[0])
    if side.length < 1e-6:
        side = Vector((0, 0, 1)) - T[0] * T[0].z
    side.normalize()
    frames = []
    for i in range(n):
        if i:
            q = T[i - 1].rotation_difference(T[i])
            side = (q @ side)
            side = (side - T[i] * side.dot(T[i])).normalized()
        frames.append((side.copy(), side.cross(T[i]).normalized()))
    return frames


def collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    for ob in list(c.objects):
        bpy.data.objects.remove(ob)
    return c


def purge_meshes():
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
