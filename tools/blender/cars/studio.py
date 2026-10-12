"""Preview studio for the car models: HDRI world (the game's sky), ground plane, camera presets and a
render-to-PNG helper used while iterating through Blender MCP."""
import math
import os

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HDR = os.path.join(ROOT, 'client', 'public', 'assets', 'sky', 'sky_1k.hdr')


def setup(res=(1100, 760)):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    ee = sc.eevee
    for k, v in (('use_shadows', True), ('use_raytracing', True), ('taa_render_samples', 32)):
        if hasattr(ee, k):
            setattr(ee, k, v)
    w = bpy.data.worlds.get('Studio') or bpy.data.worlds.new('Studio')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(HDR, check_existing=True)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 1.0
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    # neutral asphalt-ish ground
    if 'StudioGround' not in bpy.data.objects:
        me = bpy.data.meshes.new('StudioGround')
        s = 40
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new('StudioGround', me)
        sc.collection.objects.link(ob)
        m = bpy.data.materials.new('studio_ground')
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.09, 0.09, 0.095, 1)
        b.inputs['Roughness'].default_value = 0.9
        me.materials.append(m)
    if 'StudioSun' not in bpy.data.objects:
        ld = bpy.data.lights.new('StudioSun', 'SUN')
        ld.energy = 3.0
        ld.angle = math.radians(2.0)
        ob = bpy.data.objects.new('StudioSun', ld)
        sc.collection.objects.link(ob)
        ob.rotation_euler = (math.radians(40), 0, math.radians(-35))
    if 'StudioCam' not in bpy.data.objects:
        cd = bpy.data.cameras.new('StudioCam')
        cd.lens = 70
        ob = bpy.data.objects.new('StudioCam', cd)
        sc.collection.objects.link(ob)
        sc.camera = ob


VIEWS = {
    # name: (azimuth deg from +X (car front) towards +Y, elevation deg, distance)
    'ref': (38, 32, 10.5),       # like the reference sheet: front three-quarter from above, car's left side
    'front': (0, 8, 10),
    'rear': (180, 14, 10),
    'side': (90, 4, 11),
    'rear3q': (145, 22, 10.5),
    'top': (-90, 89, 11),
    'low': (-30, 6, 8),
}


def look(view='ref', target=(0, 0, 0.7), dist=None, lens=None):
    cam = bpy.data.objects['StudioCam']
    az, el, d = VIEWS[view] if isinstance(view, str) else view
    d = dist or d
    if lens:
        cam.data.lens = lens
    a, e = math.radians(az), math.radians(el)
    t = Vector(target)
    cam.location = t + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * d
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()


def render(path, view='ref', **kw):
    look(view, **kw)
    sc = bpy.context.scene
    sc.render.filepath = path
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    return path
