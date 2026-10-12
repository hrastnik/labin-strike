"""Outline projection helpers: 2D outlines (side / top / front views) become prisms that split the body by
exact booleans (windows, lights, wheel arches...)."""
import math

import bmesh
import bpy
from mathutils import Vector


def rounded(poly, radii, seg=5):
    """closed polygon [(u, v)...] with per-corner fillet radius (number or list) -> dense polygon."""
    n = len(poly)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % n])
        r = radii[i]
        a, b = (p0 - p1), (p2 - p1)
        la, lb = a.length, b.length
        if r <= 0 or la < 1e-6 or lb < 1e-6:
            out.append(p1)
            continue
        a.normalize(); b.normalize()
        ang = math.acos(max(-1.0, min(1.0, a.dot(b))))
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append(p1)
            continue
        t = r / math.tan(ang / 2)
        t = min(t, la * 0.48, lb * 0.48)
        r = t * math.tan(ang / 2)
        q0, q1 = p1 + a * t, p1 + b * t
        bis = (a + b).normalized()
        c = p1 + bis * (r / math.sin(ang / 2))
        v0, v1 = q0 - c, q1 - c
        a0, a1 = math.atan2(v0.y, v0.x), math.atan2(v1.y, v1.x)
        d = a1 - a0
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        for k in range(seg + 1):
            t2 = a0 + d * k / seg
            out.append(c + Vector((math.cos(t2), math.sin(t2))) * r)
    return [tuple(p) for p in out]


def offset_poly(poly, d):
    """grow (d > 0) / shrink a CCW-or-CW polygon by d (miter, fine for gently curved outlines)."""
    n = len(poly)
    P = [Vector(p) for p in poly]
    area = sum(P[i].x * P[(i + 1) % n].y - P[(i + 1) % n].x * P[i].y for i in range(n))
    s = 1 if area > 0 else -1
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e0 = (b - a).normalized(); e1 = (c - b).normalized()
        n0 = Vector((e0.y, -e0.x)) * s; n1 = Vector((e1.y, -e1.x)) * s
        m = (n0 + n1)
        if m.length < 1e-6:
            m = n0
        m.normalize()
        k = max(0.3, m.dot(n0))
        out.append(tuple(b + m * (d / k)))
    return out


def prism(name, poly, view, d0, d1, mat=None, coll=None):
    """extrude a 2D outline along the view axis. view: 'side' (poly in x,z; depth y), 'top' (x,y; depth z),
    'front' (y,z; depth x)."""
    bm = bmesh.new()

    def P(u, v, d):
        if view == 'side':
            return (u, d, v)
        if view == 'top':
            return (u, v, d)
        return (d, u, v)
    a = [bm.verts.new(P(u, v, d0)) for u, v in poly]
    b = [bm.verts.new(P(u, v, d1)) for u, v in poly]
    n = len(poly)
    bm.faces.new(a)
    bm.faces.new(b[::-1])
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def cylinder(name, c, r, y0, y1, seg=48, mat=None, coll=None):
    bm = bmesh.new()
    a, b = [], []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        a.append(bm.verts.new((c[0] + math.cos(t) * r, y0, c[1] + math.sin(t) * r)))
        b.append(bm.verts.new((c[0] + math.cos(t) * r, y1, c[1] + math.sin(t) * r)))
    bm.faces.new(a)
    bm.faces.new(b[::-1])
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    name = old.name
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
        me.name = name
    return ob


def boolean(ob, cutter, op='DIFFERENCE', remove_cutter=True):
    m = ob.modifiers.new('bool', 'BOOLEAN')
    m.operation = op
    m.solver = 'EXACT'
    m.object = cutter
    if hasattr(m, 'material_mode'):
        m.material_mode = 'TRANSFER'
    if hasattr(m, 'use_self'):
        m.use_self = False
    apply_mods(ob)
    if remove_cutter:
        me = cutter.data
        bpy.data.objects.remove(cutter)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return ob


def duplicate(ob, name):
    d = ob.copy()
    d.data = ob.data.copy()
    d.name = name
    for c in ob.users_collection:
        c.objects.link(d)
    return d


def delete_faces_with_material(ob, mat_name):
    me = ob.data
    idx = [i for i, m in enumerate(me.materials) if m and m.name == mat_name]
    if not idx:
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    dead = [f for f in bm.faces if f.material_index in idx]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    bm.to_mesh(me)
    bm.free()
    return len(dead)


def set_material(ob, mat):
    me = ob.data
    if mat.name not in [m.name for m in me.materials if m]:
        me.materials.append(mat)
    i = [m.name if m else '' for m in me.materials].index(mat.name)
    for p in me.polygons:
        p.material_index = i


def merge_into(dst, src):
    """join src mesh object into dst (materials merged by name)."""
    bm = bmesh.new()
    bm.from_mesh(dst.data)
    names = [m.name for m in dst.data.materials]
    remap = []
    for m in src.data.materials:
        if m.name not in names:
            dst.data.materials.append(m)
            names.append(m.name)
        remap.append(names.index(m.name))
    tmp = src.data.copy()
    tmp.transform(dst.matrix_world.inverted() @ src.matrix_world)
    for p in tmp.polygons:
        p.material_index = remap[p.material_index] if remap else 0
    bm.from_mesh(tmp)
    bm.to_mesh(dst.data)
    bm.free()
    bpy.data.meshes.remove(tmp)
    me = src.data
    bpy.data.objects.remove(src)
    if me.users == 0:
        bpy.data.meshes.remove(me)


AXIS = {'side': 1, 'top': 2, 'front': 0}


def pocket(src, axis, sign, depth, floor_mat, wall_mat, coll, name, raised=False):
    """copy of the patch `src` moved along the axis by sign*depth (the floor) + walls joining its boundary back
    to the original boundary. Used for lamp housings / grille recesses (sunk) and bars / strips (raised)."""
    bm = bmesh.new()
    bm.from_mesh(src.data)
    if not bm.verts:
        bm.free()
        return None
    off = Vector((0, 0, 0))
    off[axis] = sign * depth
    key = {}
    for v in bm.verts:
        key[tuple(round(c, 6) for c in v.co)] = v.co.copy()
        v.co += off
    bnd = [e for e in bm.edges if e.is_boundary]
    for f in bm.faces:
        f.material_index = 0
    res = bmesh.ops.extrude_edge_only(bm, edges=bnd)
    for v in [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]:
        k = tuple(round(c, 6) for c in (v.co - off))
        if k in key:
            v.co = key[k]
    walls = [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace)]
    c = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
    for f in walls:
        f.material_index = 1
        d = c - f.calc_center_median()
        d[axis] = 0.0
        if (f.normal.dot(d) < 0) != raised:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.materials.append(floor_mat)
    me.materials.append(wall_mat)
    for p in me.polygons:
        p.use_smooth = p.material_index == 0
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def gap_poly(line, w):
    """thin closed outline around an open polyline (panel gap of width w)."""
    P = [Vector(p) for p in line]
    L, R = [], []
    n = len(P)
    for i in range(n):
        a = P[max(i - 1, 0)]
        b = P[min(i + 1, n - 1)]
        t = (b - a).normalized()
        nn = Vector((-t.y, t.x)) * (w / 2)
        L.append(tuple(P[i] + nn))
        R.append(tuple(P[i] - nn))
    return L + R[::-1]


def raycast(obs, origin, direction, dist=10.0):
    """nearest hit point + normal on one object or a list (objects have identity transforms)."""
    best = (None, None, dist)
    for ob in (obs if isinstance(obs, (list, tuple)) else [obs]):
        ok, loc, nor, _ = ob.ray_cast(Vector(origin), Vector(direction).normalized(), distance=dist)
        if ok and (loc - Vector(origin)).length < best[2]:
            best = (loc, nor, (loc - Vector(origin)).length)
    return best[0], best[1]
