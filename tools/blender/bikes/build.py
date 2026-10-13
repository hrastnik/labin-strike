"""Build the motorcycles in the running Blender (via Blender MCP) and render previews.

    import sys; sys.path.insert(0, '<repo>/tools/blender'); from bikes import build; build.run(['wla', 'r35'])

Writes previews to OUT (side view orthographic, matching the reference photos' framing, plus 3/4 views);
compare.py (system python3) overlays the side view on the photo. build.run(..., export=True) writes the game GLB
via export.py."""
import importlib
import json
import math
import os

import bpy
from mathutils import Vector

from . import lib, parts

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('BIKES_OUT', os.path.join(HERE, 'out'))
MODELS = ('wla', 'r35')


def model(name):
    mod = importlib.import_module(f'bikes.{name}')
    importlib.reload(mod)
    return mod


def build_one(name, offset=(0, 0, 0)):
    for m in (lib, parts):
        importlib.reload(m)
    mod = model(name)
    coll = lib.collection('BIKE_' + name)
    mats = parts.materials(name, mod.PAINT)
    bk = lib.Bike(name, mats, mod.CAL)
    mod.build(bk)
    objs = bk.finish(coll)
    objs['body'].location = Vector(offset)
    lib.purge_meshes()
    tris = 0
    for ob in coll.objects:
        if ob.type == 'MESH':
            ob.data.calc_loop_triangles()
            tris += len(ob.data.loop_triangles)
    return {'tris': tris, 'objects': len(coll.objects)}


def _scene():
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        if ob.name in ('Cube', 'Light', 'Camera'):
            bpy.data.objects.remove(ob)
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    w = bpy.data.worlds.get('BikeStudio') or bpy.data.worlds.new('BikeStudio')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.55, 0.57, 0.6, 1)
    bg.inputs['Strength'].default_value = 0.9
    if 'BikeSun' not in bpy.data.objects:
        ld = bpy.data.lights.new('BikeSun', 'SUN')
        ld.energy = 3.5
        ld.angle = math.radians(3)
        ob = bpy.data.objects.new('BikeSun', ld)
        sc.collection.objects.link(ob)
        ob.rotation_euler = (math.radians(35), math.radians(10), math.radians(70))
    if 'BikeCam' not in bpy.data.objects:
        cd = bpy.data.cameras.new('BikeCam')
        ob = bpy.data.objects.new('BikeCam', cd)
        sc.collection.objects.link(ob)
    sc.camera = bpy.data.objects['BikeCam']
    ee = sc.eevee
    for k, v in (('use_shadows', True), ('use_raytracing', True), ('taa_render_samples', 24)):
        if hasattr(ee, k):
            setattr(ee, k, v)


def _only(name):
    for c in bpy.data.collections:
        if c.name.startswith('BIKE_'):
            c.hide_render = c.name != 'BIKE_' + name


def render_side(name, res=(1400, 800), scale=2.8, cz=0.62, path=None):
    """orthographic right-side view; returns the camera mapping for compare.py."""
    _scene()
    _only(name)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = True
    cam = bpy.data.objects['BikeCam']
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = scale
    cam.location = (6, 0, cz)
    cam.rotation_euler = (math.radians(90), 0, math.radians(90))
    path = path or os.path.join(OUT, f'{name}_side.png')
    sc.render.filepath = path
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    bpy.ops.render.render(write_still=True)
    info = {'png': path, 'w': res[0], 'h': res[1], 'k': res[0] / scale, 'cy': 0.0, 'cz': cz}
    with open(os.path.join(OUT, f'{name}_side.json'), 'w') as f:
        json.dump(info, f)
    return info


def render_view(name, az, el, dist=3.1, target=(0, 0, 0.55), lens=50, res=(1100, 800), tag='q34'):
    """perspective view: azimuth from +y (front) towards +x (right side), elevation, degrees."""
    _scene()
    _only(name)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    cam = bpy.data.objects['BikeCam']
    cam.data.type = 'PERSP'
    cam.data.lens = lens
    a, e = math.radians(az), math.radians(el)
    t = Vector(target)
    cam.location = t + Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    path = os.path.join(OUT, f'{name}_{tag}.png')
    sc.render.filepath = path
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    bpy.ops.render.render(write_still=True)
    return path


VIEWS = {'q34': (45, 18), 'rear34': (215, 25), 'left': (-90, 5), 'front': (0, 8), 'top': (90, 80), 'chase': (180, 22)}


def run(names=MODELS, views=('side', 'q34'), export=False):
    os.makedirs(OUT, exist_ok=True)
    stats = {}
    for i, n in enumerate(names):
        stats[n] = build_one(n)
    for n in names:
        for v in views:
            if v == 'side':
                render_side(n)
            else:
                az, el = VIEWS[v]
                render_view(n, az, el, tag=v)
    if export:
        from . import export as ex
        importlib.reload(ex)
        stats['export'] = ex.write(names)
    return stats
