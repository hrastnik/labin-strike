"""The map's cats (Labin Strike has cats where Counter-Strike has chickens). Low-poly and vertex-coloured.

Each coat is one hierarchy, cat_<coat>, of separately pivoted parts that the client animates in code (no skinning):
  <coat>_body                       torso, origin on the ground under the middle of the cat
  <coat>_head                       origin at the top of the neck
  <coat>_leg_fl / _fr / _bl / _br   origins at the shoulders and hips
  <coat>_tail0 .. _tail3            a chain: each segment is parented to the one before
The cat faces +Y in Blender, which is -Z in three.js (yaw 0, like the soldiers). Units are metres.

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/cats/build.py
  ... -- --preview /tmp/cats.png   also renders a turntable still of every coat
Written to client/public/assets/cats/cats.glb."""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_GLB = os.path.join(ROOT, 'client', 'public', 'assets', 'cats', 'cats.glb')

SEGS = 14  # around every lofted part


def hexc(h):
    """sRGB hex -> linear rgb (glTF vertex colours are linear)."""
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))


# fur: base, stripes, underside, patches (None = no patches); then eyes, nose, inner ears
COATS = {
    # the main cat: blue-grey tabby with peach-cream belly and patches, yellow-green eyes (from the photo)
    'main': dict(base='#74737b', stripe='#55545c', belly='#dcbb9c', patch='#c8a284', patch_amt=0.55,
                 muzzle='#bdb0a6', eye='#b8ab45', nose='#9a6a64', ear='#c99389', stripes=1.0),
    'ginger': dict(base='#d9893f', stripe='#b0612a', belly='#f2dcbf', patch=None, patch_amt=0,
                   muzzle='#f2dcbf', eye='#c9a43a', nose='#c9827a', ear='#e0a29a', stripes=1.0),
    'tuxedo': dict(base='#1c1c20', stripe='#1c1c20', belly='#efede8', patch=None, patch_amt=0,
                   muzzle='#efede8', eye='#a9b648', nose='#4a3a3a', ear='#7a5a58', stripes=0.0),
}

# pivots in cat space (ground at z = 0)
HEAD = Vector((0, 0.215, 0.28))
LEGS = {'fl': Vector((0.058, 0.13, 0.17)), 'fr': Vector((-0.058, 0.13, 0.17)),
        'bl': Vector((0.064, -0.13, 0.175)), 'br': Vector((-0.064, -0.13, 0.175))}
TAIL = Vector((0, -0.215, 0.215))
TAIL_SEG = 0.07
TAIL_REST = (-0.75, 0.35, 0.3, 0.25)  # x rotation of each segment: up from the rump, then curling back down


# ------------------------------------------------------------------ geometry

def loft(bm, rings, cap0=True, cap1=True, segs=SEGS):
    """rings: [(centre, u, v)], each an ellipse centre + u*cos + v*sin. Returns the new verts."""
    loops = []
    for c, u, v in rings:
        loops.append([bm.verts.new(c + u * math.cos(a) + v * math.sin(a))
                      for a in (2 * math.pi * i / segs for i in range(segs))])
    for a, b in zip(loops, loops[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], a[j], b[j], b[i]))
    for ring, cap, first in ((loops[0], cap0, True), (loops[-1], cap1, False)):
        if not cap:
            continue
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((c, ring[j], ring[i]) if first else (c, ring[i], ring[j]))
    return [v for lp in loops for v in lp]


def along_y(profile):
    """(y, z, half width, half height) -> rings around the Y axis."""
    return [(Vector((0, y, z)), Vector((rx, 0, 0)), Vector((0, 0, rz))) for y, z, rx, rz in profile]


def along_z(profile):
    """(z, y offset, half width, half depth) -> rings around the Z axis (legs hang down from their pivot)."""
    return [(Vector((0, y, z)), Vector((rx, 0, 0)), Vector((0, ry, 0))) for z, y, rx, ry in profile]


def blob(bm, c, r):
    """small ellipsoid (eyes, nose, pupils)."""
    res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1)
    for v in res['verts']:
        v.co = Vector((c.x + v.co.x * r[0], c.y + v.co.y * r[1], c.z + v.co.z * r[2]))
    return res['verts']


def body_mesh(bm):
    # a chunky cat: deep chest and a round belly
    loft(bm, along_y([
        (-0.225, 0.20, 0.03, 0.03),
        (-0.205, 0.195, 0.075, 0.075),
        (-0.15, 0.19, 0.105, 0.10),
        (-0.06, 0.185, 0.118, 0.112),
        (0.04, 0.19, 0.112, 0.108),
        (0.12, 0.205, 0.095, 0.095),
        (0.18, 0.225, 0.075, 0.08),
        (0.225, 0.26, 0.05, 0.055),
    ]))


def head_mesh(bm, coat):
    """returns {region: [verts]} for colouring."""
    out = {}
    # round British-shorthair face, full cheeks, short muzzle
    out['skull'] = loft(bm, along_y([
        (-0.06, 0.01, 0.025, 0.025),
        (-0.048, 0.01, 0.058, 0.055),
        (-0.015, 0.012, 0.078, 0.066),
        (0.025, 0.006, 0.074, 0.06),
        (0.055, -0.006, 0.05, 0.042),
        (0.072, -0.012, 0.03, 0.028),
    ], ), cap1=False)
    # muzzle, its own little dome so it can be lighter
    out['muzzle'] = loft(bm, along_y([
        (0.06, -0.02, 0.034, 0.028),
        (0.078, -0.022, 0.026, 0.022),
        (0.088, -0.024, 0.012, 0.012),
    ]), cap0=False)
    out['ears'] = []
    out['inner_ears'] = []
    for s in (1, -1):
        base = Vector((s * 0.046, -0.012, 0.05))
        tilt = Matrix.Rotation(s * 0.42, 3, 'Y')
        rings = [(base, tilt @ Vector((0.027, 0, 0)), tilt @ Vector((0, 0.014, 0))),
                 (base + tilt @ Vector((0, 0.002, 0.03)), tilt @ Vector((0.014, 0, 0)), tilt @ Vector((0, 0.008, 0)))]
        vs = loft(bm, rings, cap0=False, cap1=False, segs=6)
        tip = bm.verts.new(base + tilt @ Vector((0, 0.004, 0.05)))
        top = vs[6:]
        for i in range(6):
            bm.faces.new((top[i], top[(i + 1) % 6], tip))
        out['ears'] += vs + [tip]
        # the pink inside, a thin triangle just in front of the ear
        f = [bm.verts.new(base + tilt @ Vector((x, 0.0135, z))) for x, z in ((0.019, 0.004), (-0.019, 0.004), (0, 0.042))]
        bm.faces.new(f if s > 0 else f[::-1])
        out['inner_ears'] += f
    out['eyes'] = []
    out['pupils'] = []
    for s in (1, -1):
        c = Vector((s * 0.034, 0.05, 0.016))
        out['eyes'] += blob(bm, c, (0.016, 0.01, 0.015))
        out['pupils'] += blob(bm, c + Vector((s * 0.002, 0.0085, 0)), (0.0045, 0.003, 0.012))
    out['nose'] = blob(bm, Vector((0, 0.088, -0.006)), (0.011, 0.006, 0.007))
    return out


def leg_mesh(bm, front):
    top = 0.04 if front else 0.05  # haunches are thicker
    loft(bm, along_z([
        (0.03, 0, top * 0.8, top * 0.8),
        (0, 0, top, top * 1.05),
        (-0.07, -0.005 if front else 0.01, top * 0.75, top * 0.8),
        (-0.13, 0.0 if front else 0.02, 0.022, 0.024),
        (-0.155, 0.012, 0.026, 0.032),
        (-0.172, 0.016, 0.024, 0.03),
    ]))


def tail_mesh(bm, i):
    r0 = 0.026 - i * 0.003
    loft(bm, [(Vector((0, -y, 0)), Vector((r, 0, 0)), Vector((0, 0, r)))
              for y, r in ((-0.012, r0 * 0.6), (-0.004, r0), (TAIL_SEG * 0.5, r0 - 0.0015), (TAIL_SEG + 0.004, r0 - 0.003))],
         cap0=True, cap1=i == 3, segs=8)


# ------------------------------------------------------------------ colour

def noise(p, k=1.0):
    """cheap smooth value in -1..1 for patches and stripe wobble."""
    x, y, z = p.x * k, p.y * k, p.z * k
    return (math.sin(x * 23 + y * 7) + math.sin(y * 19 - z * 13 + 1.3) + math.sin(z * 29 + x * 11 + 2.1)) / 3


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def fur(coat, p, n, part):
    """colour of the fur at cat-space point p with normal n."""
    C = {k: hexc(v) for k, v in coat.items() if isinstance(v, str)}
    col = C['base']
    # tabby stripes: across the back and flanks, rings on legs and tail, lines on the forehead
    if part == 'body':
        s = math.sin(p.y * 75 + noise(p, 0.8) * 2.5)
    elif part == 'leg':
        s = math.sin(p.z * 80 + p.y * 10)
    elif part == 'tail':
        s = math.sin((p.y * -1 + p.z) * 70)
    else:
        s = math.sin(p.x * 140) if n.z > 0.45 else -1
    col = mix(col, C['stripe'], smooth(0.35, 0.75, s) * coat['stripes'] * (0.4 + 0.6 * smooth(-0.3, 0.6, n.z + 0.3)))
    # blue-cream patches
    if coat['patch']:
        col = mix(col, C['patch'], smooth(0.25, 0.5, noise(p, 1.4)) * coat['patch_amt'])
    # underside: belly, chest, inside of the legs, chin
    under = 0.0
    if part == 'body':
        under = smooth(-0.15, -0.6, n.z) + smooth(0.1, 0.22, p.y) * smooth(0.25, 0.19, p.z) * 0.9
    elif part == 'leg':
        under = smooth(-0.04, -0.16, p.z - 0.17) * 0.6 if coat['stripes'] == 0 else smooth(0.0, -0.8, n.y) * 0.4
    elif part == 'head':
        under = smooth(-0.2, -0.7, n.z) * smooth(0.0, 0.05, p.y - HEAD.y)
    elif part == 'tail' and coat['stripes'] == 0:
        under = 0
    col = mix(col, C['belly'], under)
    if part == 'tail':  # darker tip
        col = mix(col, C['stripe'], smooth(-0.43, -0.5, p.y) * coat['stripes'])
    return col


def paint(ob, coat, part, regions=None):
    me = ob.data
    attr = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    M = ob.matrix_world
    R = M.to_3x3().normalized()
    me.update()
    C = {k: hexc(v) for k, v in coat.items() if isinstance(v, str)}
    fixed = {}
    if regions:
        for key, colour in (('muzzle', C['muzzle']), ('inner_ears', C['ear']), ('eyes', C['eye']),
                            ('pupils', hexc('#0b0b0c')), ('nose', C['nose'])):
            for i in regions.get(key, []):
                fixed[i] = colour
    for v in me.vertices:
        if v.index in fixed:
            c = fixed[v.index]
            if v.index in regions.get('muzzle', []):  # keep a hint of the face markings on the muzzle
                c = mix(c, fur(coat, M @ v.co, (R @ v.normal).normalized(), part), 0.25)
        else:
            c = fur(coat, M @ v.co, (R @ v.normal).normalized(), part)
        attr.data[v.index].color = (*c, 1.0)


# ------------------------------------------------------------------ assembly

def material(name, rough):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    ca = nt.nodes.new('ShaderNodeVertexColor')
    ca.layer_name = 'Col'
    nt.links.new(ca.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    return m


def mesh_object(name, bm, coll, parent=None, loc=(0, 0, 0), rot_x=0.0, subdivide=False):
    if subdivide:  # rounder, and enough vertices to carry the stripes
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True, smooth=1.0)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(bpy.data.materials['cat_fur'])
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = (rot_x, 0, 0)
    return ob


def build_cat(key, coat, coll, x_offset=0.0):
    root = bpy.data.objects.new(f'cat_{key}', None)
    coll.objects.link(root)
    root.location = (x_offset, 0, 0)
    bm = bmesh.new()
    body_mesh(bm)
    body = mesh_object(f'{key}_body', bm, coll, root, subdivide=True)
    bm = bmesh.new()
    regions = head_mesh(bm, coat)
    bm.verts.index_update()
    regions = {k: [v.index for v in vs] for k, vs in regions.items()}
    head = mesh_object(f'{key}_head', bm, coll, root, HEAD)
    legs = []
    for side, at in LEGS.items():
        bm = bmesh.new()
        leg_mesh(bm, side[0] == 'f')
        legs.append(mesh_object(f'{key}_leg_{side}', bm, coll, root, at, subdivide=True))
    tail = []
    prev = root
    for i in range(4):
        bm = bmesh.new()
        tail_mesh(bm, i)
        seg = mesh_object(f'{key}_tail{i}', bm, coll, prev, TAIL if i == 0 else (0, -TAIL_SEG, 0), TAIL_REST[i])
        tail.append(seg)
        prev = seg
    bpy.context.view_layer.update()
    # colours are worked out in cat space, so the root's own offset is taken back out
    off = Matrix.Translation((-x_offset, 0, 0))
    for ob, part in [(body, 'body'), (head, 'head')] + [(l, 'leg') for l in legs] + [(t, 'tail') for t in tail]:
        saved = ob.matrix_world.copy()
        ob.matrix_world = off @ saved
        paint(ob, coat, part, regions if ob is head else None)
        ob.matrix_world = saved
    # the eyes get their own glossy material
    eye_idx = set(regions['eyes'] + regions['pupils'])
    head.data.materials.append(bpy.data.materials['cat_eye'])
    for p in head.data.polygons:
        if all(v in eye_idx for v in p.vertices):
            p.material_index = 1
    return root


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def export(coll):
    os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(o.name in coll.objects)
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB, export_format='GLB', use_selection=True, export_extras=False,
        export_apply=True, export_yup=True, export_cameras=False, export_lights=False,
        export_materials='EXPORT', export_normals=True, export_texcoords=False)


def preview(path, roots):
    """a still of every coat lined up, for checking the look without starting the game."""
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = 1400, 700
    sc.render.film_transparent = False
    world = bpy.data.worlds.new('w') if not sc.world else sc.world
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.55, 0.52, 0.48, 1)
    bg.inputs['Strength'].default_value = 0.6
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
    floor = bpy.context.object
    fm = bpy.data.materials.new('floor')
    fm.use_nodes = True
    fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*hexc('#cdbfae'), 1)
    floor.data.materials.append(fm)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3.5
    sun.rotation_euler = (0.7, 0.2, 2.4)
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 50
    sc.collection.objects.link(cam)
    cam.location = (1.5, 1.9, 0.85)
    look = Vector((0, 0, 0.17))
    cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    for i, r in enumerate(roots):
        r.rotation_euler = (0, 0, 0.5 - i * 0.25)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    clear_scene()
    material('cat_fur', 0.85)
    material('cat_eye', 0.12)
    coll = bpy.data.collections.get('CATS') or bpy.data.collections.new('CATS')
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    roots = [build_cat(k, c, coll, (i - 1) * 0.6) for i, (k, c) in enumerate(COATS.items())]
    export(coll)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in coll.objects if o.type == 'MESH')
    print(f'[cats] {len(roots)} coats, {tris} triangles -> {OUT_GLB}')
    if '--preview' in argv:
        preview(argv[argv.index('--preview') + 1], roots)


main()
