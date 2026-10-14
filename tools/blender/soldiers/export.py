"""Game export: client/public/assets/soldiers/soldiers.glb

    soldier_rig                   armature; bone heads are the pivots of client/src/avatars.js (body.SKELETON)
      soldier_allies, soldier_axis  skinned to it, one baked material each (albedo + normal, WebP)
    fp_upper_<team>, fp_fore_<team> first-person sleeves along +y from the shoulder / elbow (fparms.py)
    fp_hand_r, fp_hand_l          first-person fists (the soldier's hand) in their grip frame; extras wrist, fore
The client rebuilds the skeleton from the bone positions (its pivots have identity rest rotations), so only the bone
heads and names matter here."""
import os

import bpy

from . import body, lib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, 'client', 'public', 'assets', 'soldiers', 'soldiers.glb')


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


def rig(coll):
    arm = bpy.data.armatures.new('soldier_rig')
    ob = bpy.data.objects.new('soldier_rig', arm)
    coll.objects.link(ob)
    lib.select_only([ob])
    bpy.ops.object.mode_set(mode='EDIT')
    eb = {}
    for name, (parent, head) in body.SKELETON.items():
        b = arm.edit_bones.new(name)
        b.head = lib.T(head)
        b.tail = lib.T(head) + lib.T(0, 0.06, 0)
        if parent:
            b.parent = eb[parent]
        eb[name] = b
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


def bind(mesh, arm):
    mesh.parent = arm
    m = mesh.modifiers.new('rig', 'ARMATURE')
    m.object = arm
    for a in list(mesh.data.color_attributes):
        mesh.data.color_attributes.remove(a)


def write(objs):
    _lossless()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    lib.select_only(objs)
    bpy.ops.export_scene.gltf(
        filepath=OUT, export_format='GLB', use_selection=True, export_extras=True, export_apply=False,
        export_yup=True, export_cameras=False, export_lights=False, export_materials='EXPORT',
        export_image_format='WEBP', export_image_quality=88, export_skins=True, export_animations=False,
        export_def_bones=False, export_vertex_color='ACTIVE', export_all_vertex_colors=False,
        export_meshopt_compression_enable=True, export_normals=True, export_texcoords=True, export_tangents=False)
    return os.path.getsize(OUT)
