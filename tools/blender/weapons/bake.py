"""Per-corner vertex colours 'Col' for the weapon shader:
    R = ambient occlusion (hemisphere raycasts against the whole gun, ~2.5 cm reach)
    G = edge wear (narrow, strongly convex faces = bevels, broken up by noise, less in occluded spots)
    B = cavity (concave creases) for a little grime
The client multiplies the albedo by R and blends G towards the material's bare-metal / worn colour."""
import math

import numpy as np
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

S = 0.001


def _dirs(n):
    """cosine-weighted hemisphere directions around +Z (fibonacci spiral)."""
    out = []
    ga = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        r = math.sqrt((i + 0.5) / n)
        a = i * ga
        out.append(Vector((r * math.cos(a), r * math.sin(a), math.sqrt(max(0.0, 1 - r * r)))))
    return out


def _sm(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def bake(objs, rays=24, reach=25.0, wear=1.0, seed=0):
    objs = [o for o in objs if o.type == 'MESH']
    verts, polys = [], []
    for ob in objs:
        M = ob.matrix_world
        base = len(verts)
        verts += [M @ v.co for v in ob.data.vertices]
        polys += [[base + i for i in p.vertices] for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    D = _dirs(rays)
    for ob in objs:
        me = ob.data
        M = ob.matrix_world
        R3 = M.to_3x3().normalized()
        nl = len(me.loops)
        cn = np.zeros(nl * 3, np.float32)
        me.corner_normals.foreach_get('vector', cn) if hasattr(me, 'corner_normals') else me.loops.foreach_get('normal', cn)
        cn = cn.reshape(-1, 3)
        lv = np.zeros(nl, np.int32)
        me.loops.foreach_get('vertex_index', lv)
        co = [M @ v.co for v in me.vertices]
        # --- AO per (vertex, shading normal)
        cache = {}
        ao = np.ones(nl, np.float32)
        for li in range(nl):
            vi = lv[li]
            n = (R3 @ Vector(cn[li])).normalized()
            key = (vi, round(n.x, 2), round(n.y, 2), round(n.z, 2))
            a = cache.get(key)
            if a is None:
                t = n.orthogonal().normalized()
                b = n.cross(t)
                rot = (vi * 0.618034) % 1.0 * 2 * math.pi       # rotate the spiral per vertex (less banding)
                c, s = math.cos(rot), math.sin(rot)
                p = co[vi] + n * (0.12 * S)
                hit = 0.0
                for d in D:
                    x, y = d.x * c - d.y * s, d.x * s + d.y * c
                    dirw = t * x + b * y + n * d.z
                    loc, _, _, dist = bvh.ray_cast(p, dirw, reach * S)
                    if loc is not None:
                        hit += (1.0 - dist / (reach * S)) ** 0.5
                a = 1.0 - 0.9 * hit / len(D)
                cache[key] = a
            ao[li] = a
        # --- wear per face: curvature = convex dihedral angle / face width
        fw = np.zeros(len(me.polygons), np.float32)
        fc = np.zeros(len(me.polygons), np.float32)
        edge_faces = {}
        for p in me.polygons:
            for ek in p.edge_keys:
                edge_faces.setdefault(ek, []).append(p.index)
        fn = [R3 @ p.normal for p in me.polygons]
        fcen = [M @ p.center for p in me.polygons]
        for p in me.polygons:
            longest = max(((co[a] - co[b]).length for a, b in p.edge_keys), default=1e-6)
            width = 2 * p.area * (M.median_scale ** 2) / max(longest, 1e-9) / S          # mm
            kmax, kcav = 0.0, 0.0
            for ek in p.edge_keys:
                for q in edge_faces[ek]:
                    if q == p.index:
                        continue
                    ang = fn[p.index].angle(fn[q], 0.0)
                    convex = (fcen[q] - fcen[p.index]).dot(fn[p.index]) < 0
                    if convex:
                        kmax = max(kmax, ang / max(width, 0.05))
                    else:
                        kcav = max(kcav, ang)
            fw[p.index] = kmax
            fc[p.index] = kcav
        col = np.zeros((nl, 4), np.float32)
        col[:, 3] = 1.0
        rng_off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
        for p in me.polygons:
            base_w = _sm(0.35, 1.5, fw[p.index]) * wear
            cav = _sm(0.5, 1.4, fc[p.index])
            for li in p.loop_indices:
                q = co[lv[li]] / S
                nz = noise.noise(q / 7.0 + rng_off) + 0.5 * noise.noise(q / 2.2 + rng_off)
                w = base_w * _sm(-0.35, 0.45, nz) * (ao[li] ** 1.5)
                col[li] = (ao[li], w, cav * 0.6, 1.0)
        attr = me.color_attributes.get('Col') or me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        attr.data.foreach_set('color', col.ravel())
        me.color_attributes.active_color = attr
        if hasattr(me.color_attributes, 'render_color_index'):
            me.color_attributes.render_color_index = me.color_attributes.active_color_index
