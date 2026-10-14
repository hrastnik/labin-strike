"""Extract the meshes the soldiers borrow from Blender Studio's Human Base Meshes bundle (CC0, public domain):
    https://www.blender.org/download/demo-files/#assets  ->  human-base-meshes-bundle-v1.4.1.zip

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --disable-autoexec \
        --python tools/blender/soldiers/import_base.py -- <path to human_base_meshes_bundle.blend>

writes tools/blender/soldiers/base/base_meshes.blend with, multires applied and moved to the origin:
    head    GEO-head_animation_realistic, with its eyes (sclera_L/R, iris_L/R): origin between the eyes
"""
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'base', 'base_meshes.blend')

WANT = {
    'head': 'GEO-head_animation_realistic',
    'sclera_L': 'GEO-head_animation_realistic.sclera.L',
    'sclera_R': 'GEO-head_animation_realistic.sclera.R',
    'iris_L': 'GEO-head_animation_realistic.iris.L',
    'iris_R': 'GEO-head_animation_realistic.iris.R',
}


def main():
    src = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(src, link=False) as (data_from, data_to):
        data_to.objects = [n for n in WANT.values() if n in data_from.objects]
    sc = bpy.context.scene
    for o in data_to.objects:
        sc.collection.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for key, name in WANT.items():
        o = bpy.data.objects[name]
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(o.matrix_world)
        out[key] = me
    # origin between the eyeballs
    eyes = [sum((v.co for v in out[k].vertices), Vector()) / len(out[k].vertices) for k in ('sclera_L', 'sclera_R')]
    head_o = (eyes[0] + eyes[1]) / 2
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for key, me in out.items():
        me.transform(Matrix.Translation(-head_o))
        me.name = key
        ob = bpy.data.objects.new(key, me)
        sc.collection.objects.link(ob)
        print(f'{key}: {len(me.vertices)} verts, {len(me.polygons)} faces', flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for c in (bpy.data.meshes, bpy.data.materials):
        for d in list(c):
            if d.users == 0:
                c.remove(d)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print(OUT, os.path.getsize(OUT))


main()
