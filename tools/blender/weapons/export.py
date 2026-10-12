"""Game export: client/public/assets/weapons/weapons.glb

Per weapon <id>:
    <id>.body, <id>.mag, <id>.bolt, ...   first-person parts: empties at their pivots (gun origin = trigger, bore)
                                          carrying the extras {gun, part}, each with its mesh as a child
    <id>.lod                              everything merged and decimated, for third-person soldiers and far views
    <id>@muzzle, <id>@sight, ...          anchor empties
Materials are the shared wpn_<key> set (textures embedded once, WebP); vertex colours 'Col' -> COLOR_0
(R = AO, G = edge wear, B = cavity; the client's shader patch reads them).
When npx is available the Blender output is quantized + meshopt-compressed with gltf-transform (~45% smaller)."""
import json
import math
import os
import shutil
import subprocess

import bpy
import numpy as np

from . import lib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, 'client', 'public', 'assets', 'weapons', 'weapons.glb')
LOD_TRIS = 1800
GLTF_TRANSFORM = '@gltf-transform/cli@4.5.1'


def _lossless():
    """meshopt without the lossy exponential filter on POSITION (same patch as cars/export.py)."""
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


def make_lod(g):
    obs = []
    for p, ob in g.objects.items():
        if p == 'mag' and g.meta.get('magHidden'):
            continue
        c = ob.copy()
        c.data = ob.data.copy()
        c.data.transform(ob.matrix_world)
        c.matrix_world.identity()
        g.coll.objects.link(c)
        obs.append(c)
    lod = lib.join(obs, f'{g.id}.lod')
    lod['part'] = 'lod'
    lod['gun'] = g.id
    n = sum(len(p.vertices) - 2 for p in lod.data.polygons)
    if n > LOD_TRIS:
        d = lod.modifiers.new('dec', 'DECIMATE')
        d.decimate_type = 'COLLAPSE'
        d.ratio = LOD_TRIS / n
        d.use_symmetry = False
        lib.apply_mods(lod)
    me = lod.data
    if hasattr(me, 'set_sharp_from_angle'):
        me.set_sharp_from_angle(angle=0.7)
    return lod


def _pivot_empties(objs):
    """each part object -> an empty <name> at the part's pivot carrying its custom props, with the mesh as a child at
    identity. Quantization may then rescale/offset the mesh node freely while the client animates the empty."""
    out = []
    for ob in objs:
        name = ob.name
        e = bpy.data.objects.new(name + '.tmp', None)
        for c in ob.users_collection:
            c.objects.link(e)
        e.matrix_world = ob.matrix_world.copy()
        for k in list(ob.keys()):
            e[k] = ob[k]
            del ob[k]
        ob.name = name + '.mesh'
        e.name = name
        ob.parent = e
        ob.matrix_parent_inverse.identity()
        ob.matrix_basis.identity()
        out += [e, ob]
    return out


def _uv_scale(objs):
    """texcoords into [0, 1] ((uv + K) / 2K, K a power of two) plus a Mapping node undoing that, which the glTF
    exporter writes as KHR_texture_transform. gltf-transform then stores them as 16-bit normalized ints (it leaves
    anything outside [0, 1] as float, and the tiling UVs span +-several)."""
    mes = {o.data for o in objs if o.type == 'MESH'}
    m = max((abs(x) for me in mes for l in me.uv_layers for x in _uvs(l)), default=1.0)
    k = 2.0 ** math.ceil(math.log2(max(m, 1.0) * 1.001))
    for me in mes:
        for l in me.uv_layers:
            l.data.foreach_set('uv', (_uvs(l) + k) / (2 * k))
    for mat in {s.material for o in objs if o.type == 'MESH' for s in o.material_slots if s.material}:
        nt = mat.node_tree
        imgs = [n for n in nt.nodes if n.type == 'TEX_IMAGE'] if nt else []
        if not imgs:
            continue
        uv = nt.nodes.new('ShaderNodeUVMap')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (2 * k, 2 * k, 1)
        mp.inputs['Location'].default_value = (-k, -k, 0)
        nt.links.new(uv.outputs['UV'], mp.inputs['Vector'])
        for n in imgs:
            nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
    return k


def _uvs(l):
    a = np.empty(len(l.data) * 2, np.float32)
    l.data.foreach_get('uv', a)
    return a


def write(guns):
    _lossless()
    sel = []
    for g in guns:
        if g.meta.get('client') and 'body' in g.objects:   # gameplay overrides for the client spec (magDir, ...)
            g.objects['body']['client'] = json.dumps(g.meta['client'])
        sel += _pivot_empties([make_lod(g)] + list(g.objects.values()))
        sel += [o for o in g.coll.objects if o.type == 'EMPTY' and '@' in o.name]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in sel:
        o.select_set(True)
    k = _uv_scale(sel)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    npx = shutil.which('npx')
    raw = OUT + '.raw.glb' if npx else OUT
    bpy.ops.export_scene.gltf(
        filepath=raw, export_format='GLB', use_selection=True, export_extras=True,
        export_apply=False, export_yup=True, export_cameras=False, export_lights=False,
        export_materials='EXPORT', export_image_format='WEBP', export_image_quality=88,
        export_vertex_color='NAME', export_vertex_color_name='Col', export_all_vertex_colors=False,
        export_meshopt_compression_enable=not npx, export_normals=True, export_texcoords=True,
        export_tangents=False)
    if npx:
        # quantize (positions 14 bit per mesh, normals 10, uv 16, colour 8) + meshopt
        r = subprocess.run([npx, '-y', GLTF_TRANSFORM, 'meshopt', raw, OUT, '--level', 'medium',
                            '--quantize-texcoord', '16'], capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            raise RuntimeError('gltf-transform failed')
        os.remove(raw)
    print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB', f'(uv scale {k:g})')
    for g in guns:
        print(f'  {g.id}: {g.tris()} tris + lod {sum(len(p.vertices) - 2 for p in bpy.data.objects[g.id + ".lod.mesh"].data.polygons)}')
