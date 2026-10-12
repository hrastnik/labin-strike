"""Renders for checking a weapon model:
    silhouette(g)  orthographic right-side render in exactly the window of ref/<ref>_rect.png (for reftool compare)
    beauty(g)      Eevee renders with the game's sky: side, first-person (viewmodel camera) and front three-quarter
"""
import json
import math
import os

import bpy
from mathutils import Euler, Vector

from . import materials

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, 'ref')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SKY = os.path.join(ROOT, 'client', 'public', 'assets', 'sky', 'sky_1k.hdr')
S = 0.001


def _only(g, include_hidden=False):
    """hide everything but this gun's parts (and optionally its magHidden part)."""
    keep = set()
    for p, ob in g.objects.items():
        if p == 'mag' and g.meta.get('magHidden') and not include_hidden:
            continue
        if p in g.meta.get('hide_in_ref', ()) and not include_hidden:
            continue
        keep.add(ob.name)
    for ob in bpy.context.scene.objects:
        ob.hide_render = ob.type == 'MESH' and ob.name not in keep
    return [bpy.data.objects[n] for n in keep]


def _camera(name):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def silhouette(g, path=None):
    sc = bpy.context.scene
    meta = json.load(open(os.path.join(REF, g.ref + '_rect.json')))
    _only(g)
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = meta['w'], meta['h']
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    cam = _camera('cmp_cam')
    cd = cam.data
    cd.type = 'ORTHO'
    cd.sensor_fit = 'HORIZONTAL'
    cd.ortho_scale = (meta['u1'] - meta['u0']) * S
    cd.clip_start, cd.clip_end = 0.01, 10
    cam.location = (1.0, (meta['u0'] + meta['u1']) / 2 * S, (meta['v0'] + meta['v1']) / 2 * S)
    cam.rotation_euler = (math.pi / 2, 0, math.pi / 2)
    sc.render.filepath = path or os.path.join(REF, g.ref + '_render.png')
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath


def _world():
    w = bpy.data.worlds.get('wpn_world') or bpy.data.worlds.new('wpn_world')
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(SKY, check_existing=True)
    bg.inputs['Strength'].default_value = 0.8
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    bpy.context.scene.world = w
    sun = bpy.data.objects.get('wpn_sun')
    if sun is None:
        sun = bpy.data.objects.new('wpn_sun', bpy.data.lights.new('wpn_sun', 'SUN'))
        bpy.context.scene.collection.objects.link(sun)
    sun.data.energy = 3.0
    sun.data.angle = math.radians(3)
    sun.rotation_euler = Euler((math.radians(50), math.radians(-20), math.radians(120)))


def _preview_materials(obs, on):
    for ob in obs:
        for slot in ob.material_slots:
            m = slot.material
            if m is None or not m.name.startswith('wpn_'):
                continue
            key = m.name[4:].removesuffix('_pv')
            slot.material = materials.get(key, preview=on)


def beauty(g, views=('side', 'fp', 'q34'), res=1400, samples=32):
    sc = bpy.context.scene
    obs = _only(g)
    _preview_materials(obs, True)
    _world()
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else 'BLENDER_EEVEE_NEXT'
    try:
        sc.eevee.taa_render_samples = samples
        sc.eevee.use_shadows = True
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = 'AgX' if 'AgX' in [v for v in ('AgX',)] else 'Filmic'
    sc.view_settings.look = 'None'
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    # bounds of the gun (mm)
    pts = [ob.matrix_world @ Vector(c) for ob in obs for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    cen = (lo + hi) / 2
    size = hi - lo
    out = []
    for view in views:
        cam = _camera('beauty_cam')
        cd = cam.data
        cd.clip_start, cd.clip_end = 0.005, 20
        if view == 'side':
            cd.type = 'ORTHO'
            cd.sensor_fit = 'HORIZONTAL'
            cd.ortho_scale = size.y * 1.06
            sc.render.resolution_x = res
            sc.render.resolution_y = int(res * max(0.3, (size.z * 1.12) / (size.y * 1.06)))
            cam.location = (1.0, cen.y, cen.z)
            cam.rotation_euler = (math.pi / 2, 0, math.pi / 2)
        elif view == 'fp':
            # the game's viewmodel camera: gun origin at hip offset (three.js camera space), vertical fov 58
            hip = g.meta.get('hip', (0.13, -0.16, -0.42) if g.meta.get('kind') == 'pistol' else (0.15, -0.2, -0.5))
            cd.type = 'PERSP'
            cd.sensor_fit = 'VERTICAL'
            cd.angle_y = math.radians(58)
            sc.render.resolution_x, sc.render.resolution_y = res, int(res * 9 / 16)
            cam.location = (-hip[0], hip[2], -hip[1])      # three (x, y, z) -> blender (x, -z, y), negated
            cam.rotation_euler = (math.pi / 2, 0, 0)        # look along +Y (three -Z)
        else:
            cd.type = 'PERSP'
            cd.sensor_fit = 'HORIZONTAL'
            cd.lens = 70
            sc.render.resolution_x, sc.render.resolution_y = res, int(res * 0.5)
            d = max(size.y, 0.25) * 1.25
            loc = cen + Vector((-0.75, 0.9, 0.45)).normalized() * d
            cam.location = loc
            cam.rotation_euler = (cen - loc).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(REF, f'{g.id}_beauty_{view}.png')
        bpy.ops.render.render(write_still=True)
        out.append(sc.render.filepath)
    _preview_materials(obs, False)
    return out
