"""Game export: every car model becomes 2 LODs x 3 meshes, named <model>_<lod>_<group>:
  paint  - car_paint only (white; the client tints it per instance)
  opaque - everything else that is opaque, one material sampling a small atlas (palette cells + licence plates)
  glass  - windows and lamp lenses, the same atlas with alpha (blended)
so a model costs 3 draw calls per LOD however many cars use it. Written to client/public/assets/cars/cars.glb."""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import model, parts, specs
from .materials import define as define_materials

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_GLB = os.path.join(ROOT, 'client', 'public', 'assets', 'cars', 'cars.glb')
OUT_BLEND = os.path.join(HERE, 'cars.blend')

AW, AH = 1024, 512          # atlas: plates 512x448 top-left, palette 8x8 cells of 64 px in the right half
CELL = 64
GLASS = ('car_glass', 'car_lens', 'car_tail_lens')
LOD1_SKIP = ('_cabin', '_wipers', '_antenna', '_handles')
LOD1_TRIS = {'paint': 950, 'opaque': 650, 'glass': 160}


def _lin2srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _mat_params(m):
    b = m.node_tree.nodes.get('Principled BSDF')
    col = list(b.inputs['Base Color'].default_value)[:3]
    return dict(color=col, alpha=b.inputs['Alpha'].default_value, rough=b.inputs['Roughness'].default_value,
                metal=b.inputs['Metallic'].default_value)


class Atlas:
    def __init__(self):
        self.cells = {}
        self.rgba = np.zeros((AH, AW, 4), np.float32)
        self.mr = np.zeros((AH, AW, 4), np.float32)
        self.rgba[..., 3] = 1.0
        self.mr[..., 0] = 1.0
        self.mr[..., 3] = 1.0
        # plates (rows top->bottom in the png; numpy rows here are bottom->top like Blender pixels)
        img = bpy.data.images.load(os.path.join(HERE, 'tex', 'plates.png'), check_existing=True)
        pw, ph = img.size
        px = np.array(img.pixels[:], np.float32).reshape(ph, pw, 4)
        self.rgba[AH - ph:AH, 0:pw] = px
        self.mr[AH - ph:AH, 0:pw, 1] = 0.45
        self.mr[AH - ph:AH, 0:pw, 2] = 0.0
        self.plate_uv = (pw / AW, ph / AH)

    def cell(self, m):
        """uv centre of the material's palette cell (allocated on first use)."""
        if m.name in self.cells:
            return self.cells[m.name]
        i = len(self.cells)
        cx, cy = i % 8, i // 8
        x0, y0 = AW // 2 + cx * CELL, AH - (cy + 1) * CELL
        p = _mat_params(m)
        srgb = [_lin2srgb(c) for c in p['color']]
        self.rgba[y0:y0 + CELL, x0:x0 + CELL] = (*srgb, p['alpha'])
        self.mr[y0:y0 + CELL, x0:x0 + CELL] = (1.0, p['rough'], p['metal'], 1.0)
        uv = ((x0 + CELL / 2) / AW, (y0 + CELL / 2) / AH)
        self.cells[m.name] = uv
        return uv

    def images(self):
        out = []
        for name, data, cs in (('car_atlas', self.rgba, 'sRGB'), ('car_atlas_mr', self.mr, 'Non-Color')):
            img = bpy.data.images.get(name)
            if img is None or tuple(img.size) != (AW, AH):
                if img:
                    bpy.data.images.remove(img)
                img = bpy.data.images.new(name, AW, AH, alpha=True)
            img.colorspace_settings.name = cs
            img.pixels.foreach_set(data.ravel())
            img.filepath_raw = os.path.join(HERE, 'tex', name + '.png')
            img.file_format = 'PNG'
            img.save()
            out.append(img)
        return out


def atlas_material(name, rgba, mr, blend=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = rgba
    t.interpolation = 'Linear'
    t2 = nt.nodes.new('ShaderNodeTexImage')
    t2.image = mr
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    nt.links.new(t2.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], b.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])
    if blend:
        nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
        m.surface_render_method = 'BLENDED'
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    return m


def _gather(objs, coll_name):
    """world-space copy of all objects as one bmesh; material list by name."""
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats = []
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        me.transform(ob.matrix_world)
        if ob.matrix_world.determinant() < 0:
            me.flip_normals()
        remap = []
        for m in me.materials:
            if m.name not in [x.name for x in mats]:
                mats.append(m)
            remap.append([x.name for x in mats].index(m.name))
        for p in me.polygons:
            p.material_index = remap[p.material_index] if remap else 0
        if 'UVMap' not in me.uv_layers:
            me.uv_layers.new(name='UVMap')
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    return bm, mats


def _group_of(m):
    if m.name == 'car_paint':
        return 'paint'
    if m.name in GLASS:
        return 'glass'
    return 'opaque'


def _split(bm, mats, atlas, M_out, prefix, coll):
    """one object per group; opaque / glass faces get atlas UVs."""
    uv = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    pu, pv = atlas.plate_uv
    for f in bm.faces:
        m = mats[f.material_index]
        g = _group_of(m)
        if g == 'paint':
            continue
        if m.name == 'car_plate_tex':
            for l in f.loops:
                u, v = l[uv].uv
                l[uv].uv = (u * pu, 1.0 - pv + v * pv)
        else:
            c = atlas.cell(m)
            for l in f.loops:
                l[uv].uv = c
    out = {}
    for g in ('paint', 'opaque', 'glass'):
        b2 = bm.copy()
        dead = [f for f in b2.faces if _group_of(mats[f.material_index]) != g]
        bmesh.ops.delete(b2, geom=dead, context='FACES')
        bmesh.ops.remove_doubles(b2, verts=b2.verts[:], dist=1e-5)
        if not b2.faces:
            b2.free()
            continue
        for f in b2.faces:
            f.material_index = 0
        me = bpy.data.meshes.new(f'{prefix}_{g}')
        b2.to_mesh(me)
        b2.free()
        me.materials.append(M_out[g])
        ob = bpy.data.objects.new(f'{prefix}_{g}', me)
        coll.objects.link(ob)
        out[g] = ob
    return out


def _decimate_to(ob, tris):
    n = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    if n <= tris:
        return
    d = ob.modifiers.new('dec', 'DECIMATE')
    d.decimate_type = 'COLLAPSE'
    d.ratio = tris / n
    d.use_symmetry = True
    d.symmetry_axis = 'Y'
    from .ops import apply_mods
    apply_mods(ob)
    ob.data.validate()


def low_wheels(spec, M, coll):
    """LOD1 wheels: 12-sided tyre + flat rim disc, 4 copies."""
    R, tw = spec['wheel_r'], spec['tyre_w']
    rr = spec.get('rim_in', 16) * 0.0254 / 2
    obs = []
    for ax in spec['axles']:
        for s in (1, -1):
            bm = bmesh.new()
            rings = parts.lathe(bm, [(rr, -tw / 2), (R, -tw / 2), (R, tw / 2), (rr, tw / 2)], 12, mat=0)
            c = bm.verts.new((0, tw / 2 - 0.01, 0))
            ring = parts.lathe(bm, [(rr, tw / 2 - 0.01)], 12, mat=1)[0]
            for i in range(12):
                f = bm.faces.new((c, ring[(i + 1) % 12], ring[i]))
                f.material_index = 1
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            ob = parts._mesh(f'{spec["name"]}_lowwheel', bm, [M['rubber'], M['alloy']], coll, smooth=False)
            ob.matrix_world = Matrix.Translation((ax, s * spec['track'] / 2, R)) @ (Matrix.Rotation(math.pi, 4, 'Z') if s < 0 else Matrix())
            obs.append(ob)
    return obs


def export_models(names=None, decimate=0.45, write=True):
    names = names or list(specs.SPECS)
    M = define_materials()
    atlas = Atlas()
    coll = model.collection('CARS_EXPORT')
    model.clear_collection(coll)
    tmp = []
    stats = {}
    # atlas images are filled after all models allocated their cells; materials reference the image datablocks
    rgba = bpy.data.images.get('car_atlas') or bpy.data.images.new('car_atlas', AW, AH, alpha=True)
    mr = bpy.data.images.get('car_atlas_mr') or bpy.data.images.new('car_atlas_mr', AW, AH, alpha=True)
    M_out = {'paint': M['paint'], 'opaque': atlas_material('car_atlas', rgba, mr),
             'glass': atlas_material('car_atlas_glass', rgba, mr, blend=True)}
    for name in names:
        spec = specs.SPECS[name]
        r = model.build(spec, decimate=decimate)
        src = [o for o in bpy.data.collections['CAR_' + name].objects if o.type == 'MESH']
        bm, mats = _gather(src, name)
        g0 = _split(bm, mats, atlas, M_out, f'{name}_0', coll)
        bm.free()
        lw = low_wheels(spec, M, bpy.data.collections['CAR_' + name])
        src1 = [o for o in src if not any(o.name.endswith(k) for k in LOD1_SKIP) and '_wheel' not in o.name] + lw
        bm, mats = _gather(src1, name)
        g1 = _split(bm, mats, atlas, M_out, f'{name}_1', coll)
        bm.free()
        for g, ob in g1.items():
            _decimate_to(ob, LOD1_TRIS[g] + (300 if g == 'opaque' else 0))
        for o in lw:
            bpy.data.objects.remove(o)
        stats[name] = {f'{lod}_{g}': sum(len(p.vertices) - 2 for p in ob.data.polygons)
                       for lod, gs in (('0', g0), ('1', g1)) for g, ob in gs.items()}
    atlas.images()
    if write:
        export_glb(coll)
    return stats


def _lossless():
    """meshopt without the lossy exponential filter on POSITION (same patch as rudarska/lib.py)."""
    from io_scene_gltf2.io.exp.meshopt import MeshoptEncoder
    if getattr(MeshoptEncoder, '_labin_patched', False):
        return
    orig = MeshoptEncoder.encode_attribute

    def encode_attribute(attribute_name, data, byteStride, export_settings):
        if attribute_name in ('POSITION', 'SK_POSITION'):
            attribute_name = 'RAW_' + attribute_name
        return orig(attribute_name, data, byteStride, export_settings)
    MeshoptEncoder.encode_attribute = staticmethod(encode_attribute)
    MeshoptEncoder._labin_patched = True


def export_glb(coll):
    _lossless()
    os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in coll.objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB, export_format='GLB', use_selection=True, export_extras=False,
        export_apply=True, export_yup=True, export_cameras=False, export_lights=False,
        export_materials='EXPORT', export_image_format='WEBP', export_image_quality=90,
        export_meshopt_compression_enable=True, export_normals=True, export_texcoords=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, copy=True)
