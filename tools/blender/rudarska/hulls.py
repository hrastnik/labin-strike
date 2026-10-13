"""Convex-hull colliders fitted to rendered geometry (cars, tree trunks, bushes, hedges), where an oriented box
would stick out past the visible shape and stop bullets in thin air.

A hull collider is an empty COL_<kind>_<n> whose extras carry the hull points in node-local glTF axes (mm ints):
  hull = [x, y, z, ...]   inline points
  hull = '<key>'          shared points from the HULL_<key> marker (every car of a model uses the same pieces)
shared/mapdata.js turns them into Rapier convex hulls."""
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from .lib import BLENDER_DIR, C_COL, C_META, _col_count

CARS_BLEND = os.path.join(BLENDER_DIR, 'cars', 'cars.blend')


def _directions(n):
    """n near-uniform unit vectors (Fibonacci sphere) plus the 26 axis / diagonal ones (flat faces, sharp edges)."""
    i = np.arange(n) + 0.5
    z = 1 - 2 * i / n
    r = np.sqrt(1 - z * z)
    a = np.pi * (1 + 5 ** 0.5) * i
    fib = np.stack([r * np.cos(a), r * np.sin(a), z], 1)
    box = np.array([(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)], float)
    return np.concatenate([fib, box / np.linalg.norm(box, axis=1, keepdims=True)])


DIRS = _directions(192)


def hull_verts(pts):
    """hull vertices of pts: the furthest point along each of ~200 directions.  Always real hull vertices (Blender's
    convex_hull op is unreliable on the many coplanar points of a cut outline); Rapier builds the hull from them and
    the result sits inside the true hull by at most ~1 cm on a car-sized piece."""
    P = np.array([tuple(p) for p in pts], float)
    idx = np.unique(np.argmax(P @ DIRS.T, axis=0))
    return [Vector(P[i]) for i in idx]


def _mm(local):
    """Blender-axis local points -> flat glTF-axis (x, z, -y) millimetre ints."""
    out = []
    for p in local:
        out += [round(p.x * 1000), round(p.z * 1000), round(-p.y * 1000)]
    return out


def _node(kind, loc, rz, hull, clip=False):
    prefix = 'CLIP_' if clip else 'COL_'
    n = _col_count.get(prefix + kind, 0) + 1
    _col_count[prefix + kind] = n
    ob = bpy.data.objects.new(f'{prefix}{kind}_{n:03d}', None)
    ob.empty_display_type = 'PLAIN_AXES'
    ob.location = loc
    ob.rotation_euler = (0, 0, rz)
    ob['hull'] = hull
    C_COL.objects.link(ob)
    return ob


def collider_hull(kind, pts, clip=False):
    """convex hull collider around world-space points pts."""
    hv = hull_verts([Vector(p) for p in pts])
    if len(hv) < 4:
        return None
    c = sum(hv, Vector()) / len(hv)
    return _node(kind, tuple(c), 0.0, _mm([p - c for p in hv]), clip)


def clip_z(verts, zc):
    """points of a mesh part (BMVerts) at or below zc, plus where its edges cross zc (a trunk cut to collider height)."""
    out = []
    for v in verts:
        if v.co.z > zc:
            continue
        out.append(v.co.copy())
        for e in v.link_edges:
            o = e.other_vert(v).co
            if o.z > zc:
                out.append(v.co.lerp(o, (zc - v.co.z) / (o.z - v.co.z)))
    return out


# ------------------------------------------------------------------------------------------------
# cars: the modelled cars (tools/blender/cars) cut into convex pieces
# ------------------------------------------------------------------------------------------------
_car_pieces = {}


def _islands(bm):
    seen, out = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        comp, stack = [], [v]
        seen.add(v)
        while stack:
            a = stack.pop()
            comp.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b not in seen:
                    seen.add(b)
                    stack.append(b)
        out.append(comp)
    return out


def _subset(bm, keep):
    """copy of bm with only the verts in `keep` (by index)."""
    b2 = bm.copy()
    b2.verts.index_update()
    bmesh.ops.delete(b2, geom=[v for v in b2.verts if v.index not in keep], context='VERTS')
    return b2


def _cut(bm, co, no):
    """exact cut outline on a piece boundary (the hulls of both sides share it)."""
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=co, plane_no=no)


def car_pieces(name, belt):
    """convex pieces of car model `name` in its local frame (origin ground centre, +X forward):
      cabin   glasshouse above the belt line, between the windscreen and rear-window bases
      body    everything else above the sills (incl. a hood or boot lid that rises above the belt line)
      mirror  the two wing mirrors
      wheel   the four tyres below the sills (open underneath, like the car)
    One hull would bridge the hood to the roof; one box per part sticks out past the slanted glass."""
    if name in _car_pieces:
        return _car_pieces[name]
    with bpy.data.libraries.load(CARS_BLEND, link=False) as (src, dst):
        dst.objects = [f'{name}_{g}' for g in ('paint', 'opaque', 'glass') if f'{name}_{g}' in src.objects]
    bm = bmesh.new()
    glass = []
    for ob in dst.objects:
        me = ob.data.copy()
        me.transform(ob.matrix_world)
        if ob.name.endswith('_glass'):
            glass = [v.co.copy() for v in me.vertices]
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        mesh = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(mesh)
    bm.verts.index_update()
    isl = _islands(bm)
    shell = max(isl, key=len)                                  # the body shell
    half_w = max(abs(v.co.y) for v in shell)
    z_sill = min(v.co.z for v in shell)
    # windscreen / rear-window bases (lamp lenses sit below the belt line)
    win = [p.x for p in glass if p.z > belt + 0.03]
    x_f, x_r = max(win), min(win)
    pieces = {'mirror_l': [], 'mirror_r': []}
    rest, tyres = set(), set()
    for comp in isl:
        if max(abs(v.co.y) for v in comp) > half_w + 0.02:    # wing mirrors stick out of the body side
            pieces['mirror_l' if comp[0].co.y > 0 else 'mirror_r'] += [v.co.copy() for v in comp]
            continue
        rest.update(v.index for v in comp)
        if min(v.co.z for v in comp) < z_sill - 0.01:          # reaches below the floor: tyres
            tyres.update(v.index for v in comp)
    eps = 1e-4
    bw = _subset(bm, tyres)
    _cut(bw, (0, 0, z_sill), (0, 0, 1))
    for v in bw.verts:
        p = v.co
        if p.z <= z_sill + eps:
            pieces.setdefault(f'wheel_{"f" if p.x > 0 else "r"}{"l" if p.y > 0 else "r"}', []).append(p.copy())
    bw.free()
    bb = _subset(bm, rest)
    bm.free()
    _cut(bb, (0, 0, z_sill), (0, 0, 1))
    _cut(bb, (0, 0, belt), (0, 0, 1))
    _cut(bb, (x_f, 0, 0), (1, 0, 0))
    _cut(bb, (x_r, 0, 0), (1, 0, 0))
    for v in bb.verts:
        p = v.co
        if p.z < z_sill - eps:
            continue
        cab_x = x_r - eps <= p.x <= x_f + eps
        if p.z >= belt - eps and cab_x:
            pieces.setdefault('cabin', []).append(p.copy())
        if p.z <= belt + eps or not (x_r + eps < p.x < x_f - eps):
            pieces.setdefault('body', []).append(p.copy())
    bb.free()
    out = {k: hull_verts(v) for k, v in pieces.items() if len(v) >= 4}
    _car_pieces[name] = {k: v for k, v in out.items() if len(v) >= 4}
    for k, hv in _car_pieces[name].items():
        m = bpy.data.objects.new(f'HULL_car_{name}_{k}', None)
        m['pts'] = _mm(hv)
        C_META.objects.link(m)
    return _car_pieces[name]


def car_colliders(name, belt, x, y, z, yaw):
    for k in car_pieces(name, belt):
        _node('car', (x, y, z), yaw, f'car_{name}_{k}')
