"""Modelling kit for the soldiers and the first-person arms.

Everything is authored in three.js coordinates (x right, y up, z back: a soldier faces -z) through T(), which maps
them to Blender's (x, -z, y); the glTF exporter maps them straight back.

A Kit collects 'parts': closed meshes (lofts, ellipsoids, ribbons ...) that each carry a colour and a bone. The
parts are only a sculpt: Kit.high() unions them with a voxel remesh into one smooth skin, low() decimates that to the
game mesh, and bake() renders the parts' colours, the sculpt's normals and ambient occlusion into its textures.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

TAU = math.pi * 2
HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, 'tex')


def T(x, y=None, z=None):
    """three.js coordinates -> Blender vector."""
    if y is None:
        x, y, z = x
    return Vector((x, -z, y))


def B(v):
    """Blender vector -> three.js coordinates."""
    return Vector((v.x, v.z, -v.y))


def V(*a):
    return Vector(a if len(a) == 3 else a[0])


def hexrgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)  # sRGB -> linear


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def _se(c, s, p):
    """superellipse point on the unit 'circle': p=2 ellipse, larger is squarer."""
    return (math.copysign(abs(c) ** (2 / p), c), math.copysign(abs(s) ** (2 / p), s))


def frame(t, side):
    """orthonormal (side, up) perpendicular to the tangent t, side as close as possible to `side`."""
    t = t.normalized()
    s = side - t * side.dot(t)
    if s.length < 1e-6:
        s = t.orthogonal()
    s.normalize()
    return s, t.cross(s).normalized()


# ------------------------------------------------------------------------------------------------------- the kit

class Kit:
    def __init__(self, name):
        self.name = name
        self.coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        if self.coll.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(self.coll)
        self.parts = []   # (object, colour hex, bone or callable(three-space Vector) -> bone)
        self.mats = {}

    # --- raw geometry
    def mesh(self, verts, faces, color, bone=None, name='part', shade=None):
        me = bpy.data.meshes.new(f'{self.name}_{name}')
        me.from_pydata([tuple(v) for v in verts], [], faces)
        me.validate()
        ob = bpy.data.objects.new(me.name, me)
        self.coll.objects.link(ob)
        ob.data.materials.append(self.colmat(shade or color))
        self.parts.append((ob, color, bone))
        return ob

    def colmat(self, color):
        """emission material carrying the part's colour, for the albedo bake (and Workbench previews)."""
        m = self.mats.get(color)
        if m:
            return m
        m = bpy.data.materials.new(f'col_{color}')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (*hexrgb(color), 1)
        nt.links.new(em.outputs[0], out.inputs[0])
        m.diffuse_color = (*hexrgb(color), 1)
        self.mats[color] = m
        return m

    # --- primitives (three.js space)
    def loft(self, stations, color, bone=None, n=20, p=2.0, side=(1, 0, 0), caps=True, dome=0, name='loft',
             closed=False, twist=0.0):
        """tube through stations [(centre, rx, ry) or (centre, rx, ry, p)]; rx along `side`, ry across.
        dome > 0 rounds the ends off over that many extra rings."""
        C = [V(s[0]) for s in stations]
        sideV = V(side)
        rings = []
        m = len(C)
        for i, s in enumerate(stations):
            if closed:
                t = C[(i + 1) % m] - C[i - 1]
            else:
                t = (C[min(i + 1, m - 1)] - C[max(i - 1, 0)])
            sx, sy = frame(t, sideV)
            rx, ry = s[1], s[2]
            pp = s[3] if len(s) > 3 else p
            ring = []
            for k in range(n):
                a = TAU * k / n + twist
                u, v = _se(math.cos(a), math.sin(a), pp)
                ring.append(C[i] + sx * (u * rx) + sy * (v * ry))
            rings.append((ring, C[i], t.normalized()))
        if dome and not closed:
            # extra shrinking rings beyond each end
            def cap(ring, c, t, sign):
                out = []
                L = sum((q - c).length for q in ring) / len(ring)
                for j in range(1, dome + 1):
                    a = j / (dome + 0.0) * math.pi / 2 * 0.92
                    out.append(([c + (q - c) * math.cos(a) + t * (sign * L * math.sin(a)) for q in ring], None, None))
                return out
            first = cap(*rings[0], -1)[::-1]
            last = cap(*rings[-1], 1)
            rings = first + rings + last
        verts = [T(q) for r in rings for q in r[0]]
        faces = []
        R = len(rings)
        for i in range(R if closed else R - 1):
            i2 = (i + 1) % R
            for k in range(n):
                k2 = (k + 1) % n
                faces.append((i * n + k, i * n + k2, i2 * n + k2, i2 * n + k))
        if caps and not closed:
            for idx, sign in ((0, -1), (R - 1, 1)):
                c = sum((Vector(q) for q in rings[idx][0]), Vector()) / n
                verts.append(T(c))
                ci = len(verts) - 1
                for k in range(n):
                    k2 = (k + 1) % n
                    a, b = idx * n + k, idx * n + k2
                    faces.append((a, b, ci) if sign > 0 else (b, a, ci))
        return self.mesh(verts, faces, color, bone, name)

    def ellipsoid(self, c, r, color, bone=None, rot=None, n=20, rings=12, p=2.0, name='ell'):
        """ellipsoid at c with radii r=(rx, ry, rz); rot: a 3x3 Matrix (three space) applied about c."""
        c = V(c)
        M = rot or Matrix.Identity(3)
        verts, faces = [], []
        for i in range(1, rings):
            th = math.pi * i / rings
            for k in range(n):
                ph = TAU * k / n
                u, w = _se(math.cos(ph), math.sin(ph), p)
                sy, cy = _se(math.sin(th), math.cos(th), p)
                q = Vector((r[0] * sy * u, r[1] * cy, r[2] * sy * w))
                verts.append(T(c + M @ q))
        verts.append(T(c + M @ Vector((0, r[1], 0))))
        verts.append(T(c + M @ Vector((0, -r[1], 0))))
        top, bot = len(verts) - 2, len(verts) - 1
        for i in range(rings - 2):
            for k in range(n):
                k2 = (k + 1) % n
                faces.append((i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k))
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((top, k2, k))
            faces.append((bot, (rings - 2) * n + k, (rings - 2) * n + k2))
        ob = self.mesh(verts, faces, color, bone, name)
        _fix_normals(ob)
        return ob

    def capsule(self, a, b, r0, r1=None, color='#ff00ff', bone=None, n=14, name='cap', flat=1.0, side=(1, 0, 0)):
        """rounded cylinder from a to b, radius r0 -> r1; flat < 1 squashes it across `side`."""
        r1 = r0 if r1 is None else r1
        a, b = V(a), V(b)
        st = [(a.lerp(b, t), lerp(r0, r1, t), lerp(r0, r1, t) * flat) for t in (0, 0.5, 1)]
        return self.loft(st, color, bone, n=n, dome=4, name=name, side=side)

    def rbox(self, c, size, color, bone=None, rot=None, p=5.0, name='box', n=16):
        """rounded box: a squared superellipsoid with half-extents size/2."""
        return self.ellipsoid(c, (size[0] / 2, size[1] / 2, size[2] / 2), color, bone, rot=rot, p=p, n=n, rings=10,
                              name=name)

    def ribbon(self, pts, normals, width, thick, color, bone=None, name='strap', closed=False):
        """flat strap along pts lying on a surface whose outward normals are given (one per point)."""
        P = [V(p) for p in pts]
        N = [V(nn).normalized() for nn in normals]
        m = len(P)
        verts, faces = [], []
        for i in range(m):
            t = P[(i + 1) % m] - P[i - 1] if closed else P[min(i + 1, m - 1)] - P[max(i - 1, 0)]
            b = t.cross(N[i]).normalized()
            w = width[i] if isinstance(width, (list, tuple)) else width
            for (sb, sn) in ((-1, 0), (1, 0), (1, 1), (-1, 1)):
                verts.append(T(P[i] + b * (sb * w / 2) + N[i] * (sn * thick - thick * 0.35)))
        R = m if closed else m - 1
        for i in range(R):
            i2 = (i + 1) % m
            for k in range(4):
                k2 = (k + 1) % 4
                faces.append((i * 4 + k, i * 4 + k2, i2 * 4 + k2, i2 * 4 + k))
        if not closed:
            faces.append((3, 2, 1, 0))
            e = (m - 1) * 4
            faces.append((e, e + 1, e + 2, e + 3))
        ob = self.mesh(verts, faces, color, bone, name)
        _fix_normals(ob)
        return ob

    def disc(self, c, normal, r, thick, color, bone=None, n=12, name='disc', ry=None):
        nrm = V(normal).normalized()
        c = V(c)
        # rx stays horizontal (across a face, a belt ...), ry runs up the surface
        side = V(1, 0, 0) if abs(nrm.x) < 0.8 else V(0, 0, -1)
        return self.loft([(c - nrm * thick * 0.5, r, ry or r), (c + nrm * thick * 0.5, r, ry or r)], color, bone,
                         n=n, name=name, side=side)

    def tile(self, corners, normal, thick, color, bone=None, name='tile'):
        """a flat quad (four corners, three space) given some depth: decals such as flag stripes and patches."""
        nrm = V(normal).normalized()
        C = [V(c) for c in corners]
        verts = [T(c - nrm * thick * 0.5) for c in C] + [T(c + nrm * thick * 0.5) for c in C]
        faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        ob = self.mesh(verts, faces, color, bone, name)
        _fix_normals(ob)
        return ob

    def objects(self, role=None):
        return [p[0] for p in self.parts if role is None or p[0].get('role', 'form') == role]

    def form_parts(self, roles=('form',)):
        return [p for p in self.parts if p[0].get('role', 'form') in roles]

    # --- detail that follows a surface
    def surface(self, objs):
        """BVH of some parts, for snapping details onto them."""
        vs, fs = [], []
        for ob in objs:
            base = len(vs)
            vs += [ob.matrix_world @ v.co for v in ob.data.vertices]
            fs += [[base + i for i in p.vertices] for p in ob.data.polygons]
        return BVHTree.FromPolygons(vs, fs)

    def snap(self, surf, p):
        """nearest surface point and outward normal (three space) to p."""
        hit = surf.find_nearest(T(p))
        loc, nrm = hit[0], hit[1]
        return B(loc), B(nrm).normalized()

    def patch(self, surf, corners, thick, color, bone=None, nu=8, nv=8, sink=0.004, name='patch', role='form',
              bulge=0.0):
        """slab conforming to a surface over the quad corners (three space, roughly on the surface: TL TR BR BL).
        bulge puffs the middle out (pockets)."""
        C = [V(c) for c in corners]
        top, bot = [], []
        for j in range(nv + 1):
            for i in range(nu + 1):
                s, t = i / nu, j / nv
                q = C[0].lerp(C[1], s).lerp(C[3].lerp(C[2], s), t)
                p, n = self.snap(surf, q)
                b = bulge * math.sin(math.pi * s) * math.sin(math.pi * t)
                top.append(T(p + n * (thick + b)))
                bot.append(T(p - n * sink))
        W = nu + 1
        verts = top + bot
        off = len(top)
        faces = []
        for j in range(nv):
            for i in range(nu):
                a = j * W + i
                faces.append((a, a + 1, a + W + 1, a + W))
                faces.append((off + a + W, off + a + W + 1, off + a + 1, off + a))
        edge = [j * 0 + i for i in range(nu)] + [i * W + nu for i in range(nv)] + \
               [nv * W + nu - i for i in range(nu)] + [(nv - i) * W for i in range(nv)]
        for k in range(len(edge)):
            a, b = edge[k], edge[(k + 1) % len(edge)]
            faces.append((a, b, off + b, off + a))
        ob = self.mesh(verts, faces, color, bone, name)
        _fix_normals(ob)
        ob['role'] = role
        return ob

    def strap(self, surf, pts, width, thick, color, bone=None, step=0.02, closed=False, name='strap',
              role='form', lift=0.0):
        """ribbon laid along the surface through pts (three space), resampled every `step` metres."""
        P = [V(p) for p in pts]
        if closed:
            P = P + [P[0]]
        dense = [P[0]]
        for a, b in zip(P, P[1:]):
            k = max(1, int((b - a).length / step))
            dense += [a.lerp(b, (i + 1) / k) for i in range(k)]
        if closed:
            dense = dense[:-1]
        snapped = [self.snap(surf, q) for q in dense]
        ob = self.ribbon([p + n * lift for p, n in snapped], [n for _, n in snapped], width, thick, color, bone,
                         name=name, closed=closed)
        ob['role'] = role
        return ob

    def stud(self, surf, p, r, thick, color, bone=None, name='stud', role='form', n=10, ry=None):
        """button / rivet / disc sitting on the surface at p."""
        q, nrm = self.snap(surf, p)
        ob = self.disc(q + nrm * (thick * 0.5 - 0.002), nrm, r, thick, color, bone, n=n, name=name, ry=ry)
        ob['role'] = role
        return ob


def _fix_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def rot(x=0.0, y=0.0, z=0.0, order='XYZ'):
    """three-space rotation matrix (intrinsic, like three.js Euler with the given order)."""
    R = {'X': lambda a: Matrix.Rotation(a, 3, 'X'), 'Y': lambda a: Matrix.Rotation(a, 3, 'Y'),
         'Z': lambda a: Matrix.Rotation(a, 3, 'Z')}
    ang = {'X': x, 'Y': y, 'Z': z}
    M = Matrix.Identity(3)
    for ax in order:
        M = M @ R[ax](ang[ax])
    return M


def axis_rot(axis, ang):
    return Matrix.Rotation(ang, 3, V(axis).normalized())


# ------------------------------------------------------------------------------------------------- mesh processing

def _new_object(name, me, coll):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def evaluated(ob, name, coll):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.name = name
    return _new_object(name, me, coll)


def union(objs, name, coll, voxel, smooth_iter=6, smooth_fac=0.5):
    """voxel-remeshed union of closed meshes, lightly smoothed."""
    bm = bmesh.new()
    for ob in objs:
        me = ob.data.copy()
        me.transform(ob.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name + '_src')
    bm.to_mesh(me)
    bm.free()
    src = _new_object(name + '_src', me, coll)
    r = src.modifiers.new('remesh', 'REMESH')
    r.mode = 'VOXEL'
    r.voxel_size = voxel
    r.adaptivity = 0
    r.use_smooth_shade = True
    if smooth_iter:
        s = src.modifiers.new('smooth', 'SMOOTH')
        s.factor = smooth_fac
        s.iterations = smooth_iter
    out = evaluated(src, name, coll)
    bpy.data.objects.remove(src)
    bpy.data.meshes.remove(me)
    return out


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def decimate(src, name, coll, target, detail=None, detail_factor=4.0):
    """collapse-decimate a copy of src to about `target` triangles; detail(three-space Vector) -> 0..1 marks
    regions that keep more of their triangles (faces, hands)."""
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = name + '_tmp'
    coll.objects.link(ob)
    n = tris(ob)
    if n > target:
        d = ob.modifiers.new('dec', 'DECIMATE')
        d.decimate_type = 'COLLAPSE'
        d.ratio = target / n
        d.use_collapse_triangulate = True
        if detail:
            g = ob.vertex_groups.new(name='detail')
            # the group's weight is how freely a vertex may collapse
            for v in ob.data.vertices:
                g.add([v.index], 1.0 - (1 - 1 / detail_factor) * detail(B(v.co)), 'REPLACE')
            d.vertex_group = 'detail'
            d.vertex_group_factor = 1.0
    out = evaluated(ob, name, coll)
    bpy.data.objects.remove(ob)
    for p in out.data.polygons:
        p.use_smooth = True
    return out


def select_only(obs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (obs[0] if obs else None)


def unwrap(ob, margin=0.004, angle=60, emphasis=None):
    """smart UV project; emphasis(three-space Vector) -> (centre, scale) enlarges a region (the head) while
    unwrapping so it gets more of the texture, then puts it back."""
    rest = None
    if emphasis:
        me = ob.data
        rest = [v.co.copy() for v in me.vertices]
        for v in me.vertices:
            c, k = emphasis(B(v.co))
            if k != 1:
                v.co = T(c + (B(v.co) - c) * k)
    select_only([ob])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    if rest:
        for v, co in zip(ob.data.vertices, rest):
            v.co = co
        ob.data.update()


def nearest_part(kit_parts, pts):
    """index of the part whose surface is nearest each point (Blender space)."""
    trees = []
    for ob, _, _ in kit_parts:
        me = ob.data
        vs = [ob.matrix_world @ v.co for v in me.vertices]
        trees.append(BVHTree.FromPolygons(vs, [p.vertices for p in me.polygons]))
    out = np.zeros(len(pts), np.int32)
    for i, p in enumerate(pts):
        best, bi = 1e9, 0
        for j, t in enumerate(trees):
            hit = t.find_nearest(p, best)
            if hit[0] is not None and hit[3] < best:
                best, bi = hit[3], j
        out[i] = bi
    return out


def skin_weights(ob, parts, bones, iters=6, pin=()):
    """per-vertex bone weights: the bone of the nearest sculpt part, then blended over the mesh's own edges so the
    joints bend smoothly. bones: ordered bone names. pin: bones whose vertices are never blended (fingers ...)."""
    me = ob.data
    pts = [ob.matrix_world @ v.co for v in me.vertices]
    near = nearest_part(parts, pts)
    nb = len(bones)
    W = np.zeros((len(pts), nb), np.float32)
    for i, j in enumerate(near):
        b = parts[j][2]
        if callable(b):
            b = b(Vector((pts[i].x, pts[i].z, -pts[i].y)))
        W[i, bones.index(b)] = 1
    pinned = np.zeros(len(pts), bool)
    for b in pin:
        pinned |= W[:, bones.index(b)] > 0.5
    ev = np.zeros(len(me.edges) * 2, np.int32)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)
    deg = np.bincount(ev.ravel(), minlength=len(pts)).astype(np.float32)
    for _ in range(iters):
        acc = np.zeros_like(W)
        np.add.at(acc, ev[:, 0], W[ev[:, 1]])
        np.add.at(acc, ev[:, 1], W[ev[:, 0]])
        nw = 0.5 * W + 0.5 * acc / np.maximum(deg, 1)[:, None]
        W = np.where(pinned[:, None], W, nw)
    # four influences at most, normalised
    for i in range(len(pts)):
        row = W[i]
        if np.count_nonzero(row > 1e-4) > 4:
            keep = np.argsort(row)[-4:]
            m = np.zeros_like(row)
            m[keep] = row[keep]
            W[i] = m
    W /= np.maximum(W.sum(1, keepdims=True), 1e-6)
    ob.vertex_groups.clear()
    groups = [ob.vertex_groups.new(name=b) for b in bones]
    for j, g in enumerate(groups):
        idx = np.nonzero(W[:, j] > 1e-4)[0]
        for i in idx:
            g.add([int(i)], float(W[i, j]), 'REPLACE')
    return W


# ------------------------------------------------------------------------------------------------------- baking

def _image(name, size, non_color=False, alpha=False):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=alpha, float_buffer=False)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


def _bake_target(low, img):
    """give low a material whose active node is an image texture writing into img."""
    m = bpy.data.materials.get('bake_' + low.name) or bpy.data.materials.new('bake_' + low.name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfDiffuse')
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.nodes.active = tex
    low.data.materials.clear()
    low.data.materials.append(m)


def bake(low, colour_src, normal_src, size=1024, name=None, ao_mix=0.75, ao_dist=0.08, extrusion=0.03,
         ray=0.06, ao_samples=48):
    """albedo (part colours x ambient occlusion) and tangent-space normals for low; returns (albedo, normal) paths."""
    name = name or low.name
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.render.bake.margin = 6
    sc.render.bake.margin_type = 'EXTEND'
    os.makedirs(TEX, exist_ok=True)
    nsrc = normal_src if isinstance(normal_src, (list, tuple)) else [normal_src]
    meshes = [o for o in sc.objects if o.type == 'MESH']
    keep = set(colour_src) | set(nsrc) | {low}
    for o in meshes:
        o.hide_render = o not in keep

    # colour: the sculpt parts' emission colours, seen from the low mesh
    col = _image(name + '_col', size)
    _bake_target(low, col)
    sc.cycles.samples = 1
    select_only(colour_src + [low], low)
    bpy.ops.object.bake(type='EMIT', use_selected_to_active=True, cage_extrusion=extrusion, max_ray_distance=ray,
                        margin=6)
    # normals from the smooth sculpt
    nrm = _image(name + '_nrm', size, non_color=True)
    _bake_target(low, nrm)
    select_only(nsrc + [low], low)
    bpy.ops.object.bake(type='NORMAL', use_selected_to_active=True, cage_extrusion=extrusion, max_ray_distance=ray,
                        normal_space='TANGENT', margin=6)
    # ambient occlusion of the low mesh against itself
    ao = _image(name + '_ao', size, non_color=True)
    _bake_target(low, ao)
    sc.cycles.samples = ao_samples
    sc.world = sc.world or bpy.data.worlds.new('w')
    sc.world.light_settings.distance = ao_dist
    for o in meshes:
        o.hide_render = o is not low
    select_only([low], low)
    bpy.ops.object.bake(type='AO', use_selected_to_active=False, margin=6)

    if os.environ.get('BAKE_DEBUG'):
        for img in (col, ao):
            img.filepath_raw = os.path.join(TEX, img.name + '_raw.png')
            img.file_format = 'PNG'
            img.save()
    c = np.array(col.pixels[:], np.float32).reshape(-1, 4)
    a = np.array(ao.pixels[:], np.float32).reshape(-1, 4)[:, :1]
    # skin keeps most of its light: deep AO on a face reads as bruises
    skin = (c[:, 0] > 0.3) & (c[:, 0] - c[:, 2] > 0.22) & (c[:, 1] > 0.15)
    mix = np.where(skin, ao_mix * 0.35, ao_mix)[:, None]
    c[:, :3] *= (1 - mix) + mix * a
    col.pixels.foreach_set(c.ravel())
    paths = []
    for img, suffix in ((col, 'col'), (nrm, 'nrm')):
        p = os.path.join(TEX, f'{name}_{suffix}.png')
        img.filepath_raw = p
        img.file_format = 'PNG'
        img.save()
        paths.append(p)
    bpy.data.images.remove(ao)
    return paths


def game_material(name, col_path, nrm_path, roughness=0.88, normal_strength=1.0):
    """Principled material the glTF exporter turns into baseColorTexture + normalTexture."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = 0.0
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    ct = nt.nodes.new('ShaderNodeTexImage')
    ct.image = bpy.data.images.load(col_path, check_existing=True)
    ct.image.reload()
    nt.links.new(ct.outputs['Color'], bsdf.inputs['Base Color'])
    nt_ = nt.nodes.new('ShaderNodeTexImage')
    nt_.image = bpy.data.images.load(nrm_path, check_existing=True)
    nt_.image.reload()
    nt_.image.colorspace_settings.name = 'Non-Color'
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.inputs['Strength'].default_value = normal_strength
    nt.links.new(nt_.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def purge():
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def folds(high, hard_parts, name, coll, depth=0.0025, fine=0.0006):
    """copy of the sculpt with cloth wrinkles pressed in: anisotropic noise (folds run around limbs and across the
    body, so the noise is stretched horizontally), skipped wherever a hard part (skin, steel, leather) is the surface."""
    from mathutils import noise
    ob = high.copy()
    ob.data = high.data.copy()
    ob.name = name
    coll.objects.link(ob)
    hard = None
    if hard_parts:
        vs, fs = [], []
        for h in hard_parts:
            base = len(vs)
            vs += [h.matrix_world @ v.co for v in h.data.vertices]
            fs += [[base + i for i in p.vertices] for p in h.data.polygons]
        hard = BVHTree.FromPolygons(vs, fs)
    me = ob.data
    n = len(me.vertices)
    co = np.zeros(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    nr = np.zeros(n * 3, np.float32)
    me.vertices.foreach_get('normal', nr)
    nr = nr.reshape(-1, 3)
    for i in range(n):
        p = Vector(co[i])
        w = 1.0
        if hard:
            hit = hard.find_nearest(p, 0.012)
            if hit[0] is not None:
                w = smooth(0.003, 0.012, hit[3])
        if w <= 0:
            continue
        # Blender space: z up. Wrinkles: fast along z, slow across
        q = Vector((p.x * 7, p.y * 7, p.z * 7))
        q.z += 1.5 * noise.noise(q * 0.8)
        f = noise.noise(Vector((q.x * 1.6, q.y * 1.6, q.z * 4.5))) + 0.45 * noise.noise(q * 4.0)
        g = noise.noise(Vector((p.x * 160, p.y * 160, p.z * 160)))
        co[i] += nr[i] * (w * (depth * f + fine * g))
    me.vertices.foreach_set('co', co.ravel())
    me.update()
    return ob


def join_into(dst, objs, coll):
    """append copies of objs' geometry (world space) to dst's mesh."""
    bm = bmesh.new()
    bm.from_mesh(dst.data)
    for ob in objs:
        me = ob.data.copy()
        me.transform(ob.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bm.to_mesh(dst.data)
    bm.free()
    for p in dst.data.polygons:
        p.use_smooth = True
