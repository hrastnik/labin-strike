"""The soldiers' heads: Blender Studio's realistic head base mesh (CC0, see import_base.py), cut off at the collar,
fitted under the helmets and painted (lips, brows, cropped hair, irises) in vertex colours for the colour bake.

The head stays its own mesh rather than joining the voxel-remeshed body (which would blur the eyelids and lips); the
collar hides the seam. Its parts carry role 'head': build.game_mesh decimates them separately and joins them into the
game mesh before unwrapping, skinning and baking.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from .lib import T, hexrgb, smooth

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'base', 'base_meshes.blend')

from .body import HEAD_FWD  # noqa: E402

EYES = (0.0, 1.703, -0.072 - HEAD_FWD)   # three space: midway between the eyeballs
NECK_CUT = -0.235             # base-mesh z (relative to the eyes) where the neck is cut off


def base_mesh(name):
    """a fresh copy of one of the extracted base meshes (base mesh coordinates: front -y, origin between the eyes)."""
    key = '_base_' + name
    me = bpy.data.meshes.get(key)
    if me is None:
        with bpy.data.libraries.load(BASE, link=False) as (src, dst):
            dst.meshes = [name]
        me = dst.meshes[0]
        me.name = key
    return me.copy()


def _cut_neck(me, z):
    bm = bmesh.new()
    bm.from_mesh(me)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z), plane_no=(0, 0, 1), clear_inner=True)
    edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
    bmesh.ops.holes_fill(bm, edges=edges or [e for e in bm.edges if e.is_boundary], sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(me)
    bm.free()


def _neck_column(me, top=-0.128, full=-0.17, rx=0.052, ry=0.057, spine_y=None):
    """below the jaw the base mesh flares out into the shoulders: pull that flare in to a neck column leaning back
    towards the spine, so the head's own skin runs on down inside the collar with no seam to see. It only ever pulls
    the surface in, so the throat under the chin keeps its shape."""
    if spine_y is None:
        spine_y = 0.075 + HEAD_FWD   # base-mesh y of the neck's centre where it enters the jacket (three z ~ +0.003)
    band = [v.co for v in me.vertices if abs(v.co.z - (top - 0.012)) < 0.005]
    c0 = (min(v.y for v in band) + max(v.y for v in band)) / 2
    for v in me.vertices:
        z = v.co.z
        if z >= top:
            continue
        t = smooth(top, full, z)
        cy = c0 + (max(c0, spine_y) - c0) * smooth(top, full - 0.02, z)
        d = Vector((v.co.x, v.co.y - cy))
        r = d.length
        if r < 1e-6:
            continue
        k = 1 - 0.06 * smooth(full, NECK_CUT, z)
        dn = d / r
        R = 1 / math.sqrt((dn.x / (rx * k)) ** 2 + (dn.y / (ry * k)) ** 2)
        if r <= R:
            continue
        q = Vector((0.0, cy)) + dn * (r + (R - r) * t)
        v.co.x, v.co.y = q.x, q.y


def _place(me):
    """base mesh -> soldier: turn to face +y (Blender) = -z (three) and move the eyes onto EYES."""
    me.transform(Matrix.Translation(T(EYES)) @ Matrix.Rotation(math.pi, 4, 'Z'))


def _vcol_material():
    m = bpy.data.materials.get('col_vertex')
    if m:
        return m
    m = bpy.data.materials.new('col_vertex')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'Col'
    nt.links.new(at.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def _paint(me, colour):
    """per-vertex colours from colour(p, n) with p, n in base-mesh coordinates (front -y, eyes at the origin)."""
    attr = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    for v in me.vertices:
        c = colour(v.co, v.normal)
        attr.data[v.index].color = (*c, 1.0)


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def face_colours(skin, lips, brow, hair, blush):
    S, L, Bw, H, Bl = (hexrgb(c) for c in (skin, lips, brow, hair, blush))

    def colour(p, n):
        x, y, z = abs(p.x), p.y, p.z
        c = S
        # cheeks: a little warmer
        d = ((x - 0.042) / 0.03) ** 2 + ((z + 0.035) / 0.03) ** 2
        c = _mix(c, Bl, 0.45 * (1 - smooth(0.4, 1.0, d)) * smooth(0.0, -0.02, y))
        # lips (front of the mouth only)
        d = (x / 0.024) ** 2 + ((z + 0.066) / 0.0115) ** 2
        c = _mix(c, L, (1 - smooth(0.55, 1.0, d)) * smooth(-0.012, -0.024, y))
        # eyebrows: an arch over each eye
        bz = 0.027 + 0.006 * math.cos((x - 0.034) / 0.026 * 1.4) - 0.006 * smooth(0.045, 0.06, x)
        d = ((x - 0.034) / 0.024) ** 2 + ((z - bz) / 0.0055) ** 2
        c = _mix(c, Bw, 0.9 * (1 - smooth(0.5, 1.0, d)) * smooth(0.01, -0.01, y))
        # cropped hair: the scalp above the brow line and down the back, short sideburns
        top = smooth(0.064, 0.078, z)
        back = smooth(0.03, 0.05, y) * smooth(-0.075, -0.045, z)
        side = smooth(0.064, 0.072, x) * smooth(-0.02, 0.0, z) * smooth(0.0, 0.016, y) * (1 - smooth(0.035, 0.05, y))
        c = _mix(c, H, max(top, back, side) * 0.92)
        return c
    return colour


def build(k, skin, lips, brow, hair, blush, iris):
    """add the head (and eyes) to the kit as 'head' parts; returns the head object."""
    out = []
    me = base_mesh('head')
    _neck_column(me)
    _cut_neck(me, NECK_CUT)
    _paint(me, face_colours(skin, lips, brow, hair, blush))
    _place(me)
    head = _add(k, 'head_real', me, skin, lambda p: 'torso' if p.y < 1.535 else 'head')
    out.append(head)
    for side in ('L', 'R'):
        m = base_mesh(f'sclera_{side}')
        _paint_eye(m, hexrgb('#cfc7bb'), hexrgb(iris), hexrgb('#141110'))
        _place(m)
        out.append(_add(k, f'eye_{side}', m, '#cfc7bb', 'head'))
    return head


def _paint_eye(me, white, iris, pupil):
    """iris and pupil painted onto the eyeball around its forward (-y) axis."""
    c = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)

    def colour(p, n):
        d = (p - c).normalized()
        a = math.degrees(math.acos(max(-1.0, min(1.0, -d.y))))
        col = _mix(white, iris, 1 - smooth(24, 29, a))
        return _mix(col, pupil, 1 - smooth(9, 12, a))
    _paint(me, colour)


def _add(k, name, me, colour, bone, vcol=True):
    me.name = f'{k.name}_{name}'
    ob = bpy.data.objects.new(me.name, me)
    k.coll.objects.link(ob)
    me.materials.clear()
    me.materials.append(_vcol_material() if vcol else k.colmat(colour))
    for p in me.polygons:
        p.use_smooth = True
    ob['role'] = 'head'
    k.parts.append((ob, colour, bone))
    return ob
