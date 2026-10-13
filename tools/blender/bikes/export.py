"""Game export: both bikes into client/public/assets/bikes/bikes.glb, one node tree per model:

    <model>_body                  frame, engine, tank, saddle, rear fender ...  (origin on the ground between the axles)
      <model>_wheel_r             spins about its local x
      <model>_fork                steers about its local y (the raked steering axis); rest rotation = the rake
        <model>_wheel_f           spins about its local x
        <model>_lamp              headlamp lens, hidden on a wreck
        <model>_grip_r / _grip_l  empties where the hands go
      <model>_seat, _foot_r, _foot_l   empties for the rider's hips and feet

Materials are per model (<model>_paint ...), plain PBR values, no textures. Also saves bikes.blend next to this file."""
import os

import bpy

from . import build

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_GLB = os.path.join(ROOT, 'client', 'public', 'assets', 'bikes', 'bikes.glb')
OUT_BLEND = os.path.join(HERE, 'bikes.blend')


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


def write(names=build.MODELS):
    """build every model at the origin and export them together."""
    stats = {n: build.build_one(n) for n in names}
    _lossless()
    os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
    for o in bpy.data.objects:
        if o.name in bpy.context.view_layer.objects:
            o.select_set(False)
    for n in names:
        coll = bpy.data.collections['BIKE_' + n]
        coll.hide_render = False
        bpy.context.view_layer.layer_collection.children[coll.name].exclude = False
        for o in coll.objects:
            o.hide_set(False)
            o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB, export_format='GLB', use_selection=True, export_extras=False,
        export_apply=False, export_yup=True, export_cameras=False, export_lights=False,
        export_materials='EXPORT', export_meshopt_compression_enable=True, export_normals=True,
        export_texcoords=False)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, copy=True)
    stats['bytes'] = os.path.getsize(OUT_GLB)
    return stats
