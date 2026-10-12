"""
Shared scene / material / geometry helpers for the Rudarska ulica map build.

Frame (right-handed, metres): +X runs SE along Rudarska ulica, +Y points NE towards the parking lot,
+Z up.  Origin = street centre at the middle Street View position.  glTF export (Y-up) maps
Blender (x, y, z) -> glTF (x, z, -y).
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)
PROJECT = os.path.dirname(os.path.dirname(BLENDER_DIR))
TEX = os.path.join(BLENDER_DIR, 'textures')
OUT_GLB = os.path.join(PROJECT, 'client/public/assets/maps/parking_lot.glb')
OUT_BLEND = os.path.join(BLENDER_DIR, 'parking_lot.blend')

rng = random.Random(7344)

# ------------------------------------------------------------------------------------------------
# scene
# ------------------------------------------------------------------------------------------------


def reset_scene():
    """the build runs in a factory-startup Blender: wipe everything and start clean."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.curves,
                 bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    scene = bpy.context.scene
    scene.name = 'RudarskaUlica'
    scene.unit_settings.system = 'METRIC'
    return scene


scene = reset_scene()


def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


C_VIS = collection('Visual')
C_COL = collection('Colliders')
C_META = collection('Markers')

# ------------------------------------------------------------------------------------------------
# materials
# ------------------------------------------------------------------------------------------------
MATS = {}
TILE = {}      # material name -> (tile_u, tile_v) metres per texture repeat (world mapped)
_images = {}


def image(rel, color=True):
    key = (rel, color)
    if key in _images:
        return _images[key]
    im = bpy.data.images.load(os.path.join(TEX, rel))
    if not color:
        im.colorspace_settings.name = 'Non-Color'
    _images[key] = im
    return im


def mat(name, color=(0.8, 0.8, 0.8), rough=0.85, metal=0.0, diff=None, nor=None, rough_tex=None,
        tile=None, tint=None, alpha=False, emit=None, nstrength=1.0, cull=True):
    """Principled material. `diff`/`nor`/`rough_tex` are paths under textures/.  `tile` = metres per
    repeat for world-space UVs (None -> explicit UVs from the geometry).  `tint` multiplies the
    albedo texture (exported as baseColorFactor)."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if diff:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = image(diff)
        out = t.outputs['Color']
        if tint is not None:
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            nt.links.new(out, mix.inputs[6])
            mix.inputs[7].default_value = (*tint, 1)
            out = mix.outputs[2]
        nt.links.new(out, b.inputs['Base Color'])
        if alpha:
            nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
    if nor:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = image(nor, False)
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = nstrength
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if rough_tex:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = image(rough_tex, False)
        nt.links.new(t.outputs['Color'], b.inputs['Roughness'])
    if emit is not None:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = 1.5
    m.use_backface_culling = cull and not alpha
    m.diffuse_color = (*(tint or color), 1)
    if tile is not None:
        TILE[name] = tile if isinstance(tile, tuple) else (tile, tile)
    MATS[name] = m
    return m


def pbr(name, tex, tile, tint=None, rough=0.9, rough_map=False, gray=False, nstrength=1.0, metal=0.0):
    """material from the resized Poly Haven set in textures/pbr/<tex>_{diff|gray,nor,rough}.jpg"""
    d = f'pbr/{tex}_gray.jpg' if gray else f'pbr/{tex}_diff.jpg'
    return mat(name, rough=rough, metal=metal, diff=d, nor=f'pbr/{tex}_nor.jpg',
               rough_tex=f'pbr/{tex}_rough.jpg' if rough_map else None, tile=tile, tint=tint, nstrength=nstrength)


def decal(name, tex, rough=0.7, alpha=True, emit=None, color=(1, 1, 1), metal=0.0):
    """explicit-UV texture material (signs, cards, decals).  Names ending in _cut are alpha-tested
    by the client, _dec are alpha-blended overlays."""
    return mat(name, color=color, rough=rough, metal=metal, diff=f'gen/{tex}', alpha=alpha, emit=emit)


# ------------------------------------------------------------------------------------------------
# geometry builder: accumulates primitives into one bmesh per group (merged per material at export)
# ------------------------------------------------------------------------------------------------

def v3(p):
    return Vector((p[0], p[1], p[2] if len(p) > 2 else 0.0))


class MB:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.verify()
        self.fixed = self.bm.faces.layers.int.new('fixeduv')
        self.cn = self.bm.verts.layers.float_vector.new('cn')   # optional custom vertex normal
        self.mats = []
        self.has_cn = False

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _tag(self, faces, m, smooth=False):
        idx = self.mi(m)
        for f in faces:
            f.material_index = idx
            f.smooth = smooth

    @staticmethod
    def _faces_of(verts):
        return {f for v in verts for f in v.link_faces}

    # -- primitives ------------------------------------------------------------------------------
    def box(self, c, s, m, rz=0.0, rx=0.0, ry=0.0, mats=None):
        """centre c, full size s. `mats` optional dict side->material (top,bottom,px,nx,py,ny)."""
        mtx = Matrix.Translation(v3(c)) @ Euler((rx, ry, rz)).to_matrix().to_4x4() @ Matrix.Diagonal((*s, 1))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=mtx)
        faces = self._faces_of(r['verts'])
        self._tag(faces, m)
        if mats:
            rot = Euler((rx, ry, rz)).to_matrix()
            dirs = {'top': (0, 0, 1), 'bottom': (0, 0, -1), 'px': (1, 0, 0), 'nx': (-1, 0, 0), 'py': (0, 1, 0), 'ny': (0, -1, 0)}
            for f in faces:
                f.normal_update()
                for k, mm in mats.items():
                    if f.normal.dot(rot @ Vector(dirs[k])) > 0.9:
                        f.material_index = self.mi(mm)
        return r['verts']

    def box_mm(self, x0, x1, y0, y1, z0, z1, m, mats=None):
        return self.box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), m, mats=mats)

    def seg_box(self, p0, p1, w, z0, z1, m, ext=0.0):
        """box running horizontally from p0 to p1 (2D), width w, z0..z1; ext extends both ends."""
        a, b = Vector((p0[0], p0[1])), Vector((p1[0], p1[1]))
        d = b - a
        L = d.length
        if L < 1e-4:
            return []
        yaw = math.atan2(d.y, d.x)
        c = (a + b) / 2
        return self.box((c.x, c.y, (z0 + z1) / 2), (L + 2 * ext, w, z1 - z0), m, rz=yaw)

    def poly_prism(self, pts, z0, z1, m, top=None, bottom=False, side=None):
        """extrude a CCW 2D polygon from z0 to z1."""
        bm = self.bm
        n = len(pts)
        lo = [bm.verts.new((p[0], p[1], z0)) for p in pts]
        hi = [bm.verts.new((p[0], p[1], z1)) for p in pts]
        faces = []
        for i in range(n):
            j = (i + 1) % n
            faces.append(bm.faces.new((lo[i], lo[j], hi[j], hi[i])))
        self._tag(faces, side or m)
        ft = bm.faces.new(hi)
        self._tag([ft], top or m)
        if bottom:
            fb = bm.faces.new(list(reversed(lo)))
            self._tag([fb], m)
        return faces + [ft]

    def poly_flat(self, pts, z, m, up=True):
        bm = self.bm
        vs = [bm.verts.new((p[0], p[1], p[2] if len(p) > 2 else z)) for p in pts]
        f = bm.faces.new(vs if up else list(reversed(vs)))
        self._tag([f], m)
        return f

    def quad(self, pts, m, uvs=None, smooth=False):
        """face from 3D points (CCW seen from the front). uvs -> fixed explicit UVs."""
        vs = [self.bm.verts.new(v3(p)) for p in pts]
        f = self.bm.faces.new(vs)
        self._tag([f], m, smooth)
        if uvs is not None:
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv].uv = uv
            f[self.fixed] = 1
        return f

    def card(self, c, right, up, w, h, m, uv=(0, 0, 1, 1), normal=None, double=False):
        """textured rectangle centred at c spanning right*w and up*h."""
        c, r, u = v3(c), v3(right).normalized() * (w / 2), v3(up).normalized() * (h / 2)
        u0, v0, u1, v1 = uv
        pts = [c - r - u, c + r - u, c + r + u, c - r + u]
        f = self.quad(pts, m, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
        if normal is not None:
            self.has_cn = True
            for v in f.verts:
                v[self.cn] = v3(normal) if not callable(normal) else normal(v.co)
        if double:
            self.quad(list(reversed(pts)), m, [(u0, v1), (u1, v1), (u1, v0), (u0, v0)])
        return f

    def wall_card(self, p0, p1, z0, z1, m, uv=(0, 0, 1, 1), off=0.0):
        """vertical textured rectangle from 2D p0 to p1.  Convention used everywhere: the visible
        (outward) side is to the RIGHT of p0->p1, so a CCW footprint's edges face outwards and the
        texture reads from p0 to p1 for the viewer."""
        a, b = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
        d = (b - a).normalized()
        n = Vector((d.y, -d.x, 0))
        a, b = a + n * off, b + n * off
        u0, v0, u1, v1 = uv
        return self.quad([(a.x, a.y, z0), (b.x, b.y, z0), (b.x, b.y, z1), (a.x, a.y, z1)], m,
                         [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    def cyl(self, c, r, h, m, seg=8, r2=None, rx=0.0, ry=0.0, rz=0.0, smooth=True, caps=True):
        """cylinder/cone centred at c (along local Z)."""
        mtx = Matrix.Translation(v3(c)) @ Euler((rx, ry, rz)).to_matrix().to_4x4()
        res = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=seg,
                                    radius1=r, radius2=r if r2 is None else r2, depth=h, matrix=mtx)
        faces = self._faces_of(res['verts'])
        self._tag(faces, m, smooth)
        if smooth and caps:
            for f in faces:
                if len(f.verts) > 4:
                    f.smooth = False
        return res['verts']

    def pole(self, p, z0, z1, r, m, seg=8, r2=None):
        return self.cyl((p[0], p[1], (z0 + z1) / 2), r, z1 - z0, m, seg=seg, r2=r2)

    def tube(self, pts, r, m, seg=6, closed=False, smooth=True, caps=True):
        """tube through 3D points (polyline), circular section."""
        bm = self.bm
        P = [v3(p) for p in pts]
        rings = []
        for i, p in enumerate(P):
            if i == 0:
                t = (P[1] - P[0])
            elif i == len(P) - 1:
                t = (P[-1] - P[-2])
            else:
                t = (P[i + 1] - P[i - 1])
            t.normalize()
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            u = t.cross(ref).normalized()
            w = t.cross(u).normalized()
            ring = [bm.verts.new(p + (u * math.cos(a) + w * math.sin(a)) * r)
                    for a in (k / seg * math.tau for k in range(seg))]
            rings.append(ring)
        faces = []
        for i in range(len(rings) - 1):
            A, B = rings[i], rings[i + 1]
            for k in range(seg):
                faces.append(bm.faces.new((A[k], A[(k + 1) % seg], B[(k + 1) % seg], B[k])))
        self._tag(faces, m, smooth)
        if caps:
            f0 = bm.faces.new(list(reversed(rings[0])))
            f1 = bm.faces.new(rings[-1])
            self._tag([f0, f1], m, False)
        return faces

    def blob(self, c, r, m, scale=(1, 1, 1), jitter=0.15, sub=1, smooth=False, rz=0.0):
        mtx = Matrix.Translation(v3(c)) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Diagonal((*scale, 1))
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=r, matrix=mtx)
        for v in res['verts']:
            v.co += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * r * jitter
        self._tag(self._faces_of(res['verts']), m, smooth)
        return res['verts']

    def loft(self, profile, half_w, m, taper=None, yaw=0.0, at=(0, 0, 0), mats_side=None):
        """extrude a closed side profile [(x, z), ...] (CCW in x-z) symmetrically in y (+-half_w).
        taper(z) -> y-scale factor (tumblehome)."""
        bm = self.bm
        # make the profile clockwise in (x right, z up) so the strip faces point outwards
        area = sum(profile[i][0] * profile[(i + 1) % len(profile)][1] - profile[(i + 1) % len(profile)][0] * profile[i][1]
                   for i in range(len(profile)))
        if area > 0:
            profile = list(reversed(profile))
        n = len(profile)
        mtx = Matrix.Translation(v3(at)) @ Matrix.Rotation(yaw, 4, 'Z')
        L, R = [], []
        for (x, z) in profile:
            s = taper(z) if taper else 1.0
            L.append(bm.verts.new(mtx @ Vector((x, half_w * s, z))))
            R.append(bm.verts.new(mtx @ Vector((x, -half_w * s, z))))
        faces = []
        for i in range(n):
            j = (i + 1) % n
            faces.append(bm.faces.new((R[i], R[j], L[j], L[i])))
        self._tag(faces, m)
        fl = bm.faces.new(L)
        fr = bm.faces.new(list(reversed(R)))
        self._tag([fl, fr], mats_side or m)
        return faces, fl, fr

    def stairs(self, p0, direction, width, n, rise, run, z0, m):
        """straight flight: p0 = 2D centre of the first riser's foot, climbing along `direction`.
        Each step is a solid block down to z0 (no gaps underneath)."""
        d = Vector((direction[0], direction[1])).normalized()
        yaw = math.atan2(d.y, d.x)
        for i in range(n):
            ztop = z0 + rise * (i + 1)
            cx = p0[0] + d.x * (run * i + run / 2)
            cy = p0[1] + d.y * (run * i + run / 2)
            self.box((cx, cy, (z0 - 0.02 + ztop) / 2), (run, width, ztop - z0 + 0.02), m, rz=yaw)

    # -- finalise --------------------------------------------------------------------------------
    def build(self, coll=None, parent=None):
        bm = self.bm
        if not bm.faces:
            bm.free()
            return None
        bm.normal_update()
        uv = self.uv
        Z = Vector((0, 0, 1))
        for f in bm.faces:
            if f[self.fixed]:
                continue
            m = self.mats[f.material_index]
            tile = TILE.get(m.name)
            if tile is None:
                continue
            n = f.normal
            if abs(n.z) > 0.985:
                t = Vector((1, 0, 0))
                b = Vector((0, 1, 0)) if n.z > 0 else Vector((0, -1, 0))
            else:
                t = Z.cross(n)
                t.normalize()
                b = n.cross(t)
                b.normalize()
            for loop in f.loops:
                co = loop.vert.co
                loop[uv].uv = (co.dot(t) / tile[0], co.dot(b) / tile[1])
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        has_cn = self.has_cn
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        if has_cn:
            attr = me.attributes.get('cn')
            vals = [0.0] * (len(me.vertices) * 3)
            attr.data.foreach_get('vector', vals)
            normals = [Vector(vals[i * 3:i * 3 + 3]) for i in range(len(me.vertices))]
            # vertices without a requested normal keep their face normal (or the vertex normal on smooth faces)
            vn = [v.normal.copy() for v in me.vertices]
            loop_normals = []
            for poly in me.polygons:
                for li in poly.loop_indices:
                    vi = me.loops[li].vertex_index
                    nn = normals[vi]
                    loop_normals.append(nn.normalized() if nn.length > 1e-6 else vn[vi] if poly.use_smooth else poly.normal.copy())
            me.normals_split_custom_set(loop_normals)
        if 'cn' in me.attributes:
            me.attributes.remove(me.attributes['cn'])
        if 'fixeduv' in me.attributes:
            me.attributes.remove(me.attributes['fixeduv'])
        ob = bpy.data.objects.new(self.name, me)
        (coll or C_VIS).objects.link(ob)
        if parent is not None:
            ob.parent = parent
        return ob


class Groups:
    """named builders 'Parent.part'; each becomes one mesh object (one draw call per material),
    parented to an empty called 'Parent' (the client keys shadow settings off Ground / Backdrop)."""

    def __init__(self):
        self.g = {}

    def __getitem__(self, k):
        if k not in self.g:
            self.g[k] = MB(k)
        return self.g[k]

    def build_all(self):
        parents = {}
        for k, mb in self.g.items():
            pname = k.split('.')[0]
            if pname not in parents:
                e = bpy.data.objects.new(pname, None)
                C_VIS.objects.link(e)
                parents[pname] = e
            mb.build(parent=parents[pname])


G = Groups()


# ------------------------------------------------------------------------------------------------
# gameplay nodes
# ------------------------------------------------------------------------------------------------

def unit_cube_mesh():
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    me = bpy.data.meshes.new('ColliderCube')
    bm.to_mesh(me)
    bm.free()
    return me


UNIT = unit_cube_mesh()
_col_count = {}


def collider(kind, c, s, rz=0.0, rx=0.0, ry=0.0, clip=False):
    """oriented box collider: centre c, full size s.  COL_ blocks players + bullets, CLIP_ players only."""
    prefix = 'CLIP_' if clip else 'COL_'
    n = _col_count.get(prefix + kind, 0) + 1
    _col_count[prefix + kind] = n
    ob = bpy.data.objects.new(f'{prefix}{kind}_{n:03d}', UNIT)
    ob.location = c
    ob.rotation_euler = (rx, ry, rz)
    ob.scale = (s[0] / 2, s[1] / 2, s[2] / 2)
    ob.display_type = 'WIRE'
    ob.hide_render = True
    C_COL.objects.link(ob)
    return ob


def collider_mm(kind, x0, x1, y0, y1, z0, z1, clip=False):
    return collider(kind, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), clip=clip)


def collider_seg(kind, p0, p1, w, z0, z1, clip=False, ext=0.0):
    a, b = Vector((p0[0], p0[1])), Vector((p1[0], p1[1]))
    d = b - a
    c = (a + b) / 2
    return collider(kind, (c.x, c.y, (z0 + z1) / 2), (d.length + 2 * ext, w, z1 - z0), rz=math.atan2(d.y, d.x), clip=clip)


def collider_ramp(kind, p0, p1, w, z0, z1, thick=0.3):
    """inclined slab whose top surface runs from (p0, z0) up to (p1, z1)."""
    a, b = Vector((p0[0], p0[1], z0)), Vector((p1[0], p1[1], z1))
    d = b - a
    horiz = Vector((d.x, d.y)).length
    L = d.length
    pitch = math.atan2(d.z, horiz)
    yaw = math.atan2(d.y, d.x)
    # centre lies `thick/2` below the top surface's midpoint, along the slab normal
    mid = (a + b) / 2
    nrm = Vector((-math.sin(pitch) * math.cos(yaw), -math.sin(pitch) * math.sin(yaw), math.cos(pitch)))
    c = mid - nrm * (thick / 2)
    # rotation: yaw about Z then pitch (negative rotation about local Y lifts +X)
    ob = collider(kind, tuple(c), (L, w, thick))
    ob.rotation_mode = 'XYZ'
    ob.rotation_euler = (Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(-pitch, 3, 'Y')).to_euler('XYZ')
    return ob


def marker(name, loc):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = 'ARROWS'
    ob.empty_display_size = 1.0
    ob.location = loc
    C_META.objects.link(ob)
    return ob


def rot2(x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return x * c - y * s, x * s + y * c


def lerp(a, b, t):
    return a + (b - a) * t


def _lossless_meshopt_positions():
    """Blender's meshopt export runs POSITION through the exponential filter with 12-bit mantissas
    and a shared exponent per vertex: a vertex 50 m from the origin snaps to a 3 cm grid, at 500 m
    to 25 cm. That collapses every few-mm offset (frames, sills, paint) into one plane -> z-fighting.
    Encode positions unfiltered instead (meshopt is lossless on raw floats)."""
    from io_scene_gltf2.io.exp.meshopt import MeshoptEncoder
    if getattr(MeshoptEncoder, '_labin_patched', False):
        return
    orig = MeshoptEncoder.encode_attribute

    def encode_attribute(attribute_name, data, byteStride, export_settings):
        if attribute_name in ('POSITION', 'SK_POSITION'):
            attribute_name = 'RAW_' + attribute_name   # unknown name -> no filter
        return orig(attribute_name, data, byteStride, export_settings)
    MeshoptEncoder.encode_attribute = staticmethod(encode_attribute)
    MeshoptEncoder._labin_patched = True


def export():
    bpy.context.view_layer.update()
    _lossless_meshopt_positions()
    os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB, export_format='GLB', use_active_scene=True, export_extras=True,
        export_apply=True, export_yup=True, export_cameras=False, export_lights=False,
        export_materials='EXPORT', export_image_format='WEBP', export_image_quality=78,
        export_meshopt_compression_enable=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, copy=True)
