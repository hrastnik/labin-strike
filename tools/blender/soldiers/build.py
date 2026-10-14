"""Build the soldiers headless, render previews, export the game GLB.

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/soldiers/build.py -- [allies axis fp] [flags]

flags:
    --sculpt    preview the sculpt parts only (fast: no remesh, no bake)
    --export    build everything and write client/public/assets/soldiers/soldiers.glb
Previews go to tools/blender/soldiers/out/ (gitignored).
"""
import importlib
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from soldiers import lib  # noqa: E402

OUT = os.path.join(HERE, 'out')


def camera(loc, look, ortho=None, lens=50):
    cam = bpy.data.objects.get('pv_cam')
    if cam is None:
        cam = bpy.data.objects.new('pv_cam', bpy.data.cameras.new('pv_cam'))
        bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    d = Vector(look) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho
    cam.data.lens = lens
    cam.data.clip_start = 0.01
    bpy.context.scene.camera = cam
    return cam


def workbench(path, views, res=(900, 1200), show=None):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    if show is not None:
        for o in sc.objects:
            if o.type == 'MESH':
                o.hide_render = o not in show
    out = []
    for name, (loc, look, ortho) in views.items():
        camera(loc, look, ortho)
        sc.render.filepath = f'{path}_{name}.png'
        bpy.ops.render.render(write_still=True)
        out.append(sc.render.filepath)
    return out


def sheet(paths, out, scale=0.5):
    """side-by-side contact sheet of PNGs (same height), downscaled by an integer step."""
    import numpy as np
    step = int(round(1 / scale))
    tiles = []
    for p in paths:
        im = bpy.data.images.load(p)
        a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::step, ::step]
        tiles.append(a)
        bpy.data.images.remove(im)
    h = max(t.shape[0] for t in tiles)
    tiles = [np.pad(t, ((h - t.shape[0], 0), (0, 0), (0, 0)), constant_values=1) for t in tiles]
    a = np.concatenate(tiles, axis=1)
    im = bpy.data.images.new('sheet', a.shape[1], a.shape[0])
    im.pixels.foreach_set(a.ravel())
    im.filepath_raw = out
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    for p in paths:
        os.remove(p)
    return out


SOLDIER_VIEWS = {
    'front': (lib.T(0, 1.0, -6), lib.T(0, 1.0, 0), 2.1),
    'side': (lib.T(6, 1.0, 0), lib.T(0, 1.0, 0), 2.1),
    'q34': (lib.T(-2.2, 1.6, -2.6), lib.T(0, 1.05, 0), None),
    'face': (lib.T(-0.35, 1.75, -0.75), lib.T(0, 1.66, 0), None),
    'face_front': (lib.T(0.0, 1.69, -0.62), lib.T(0, 1.68, 0), None),
}


def eevee(path, views, res=(900, 1200), show=None):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 32
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = 'PNG'
    w = bpy.data.worlds.get('pv_world') or bpy.data.worlds.new('pv_world')
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(os.path.join(HERE, '..', '..', '..', 'client', 'public', 'assets', 'sky',
                                                  'sky_1k.hdr'), check_existing=True)
    bg.inputs['Strength'].default_value = 0.9
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs[0], out.inputs[0])
    sc.world = w
    sun = bpy.data.objects.get('pv_sun')
    if sun is None:
        sun = bpy.data.objects.new('pv_sun', bpy.data.lights.new('pv_sun', 'SUN'))
        sc.collection.objects.link(sun)
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), 0, math.radians(-150))
    if show is not None:
        for o in sc.objects:
            if o.type == 'MESH':
                o.hide_render = o not in show
    paths = []
    for name, (loc, look, ortho) in views.items():
        camera(loc, look, ortho)
        sc.render.filepath = f'{path}_{name}.png'
        bpy.ops.render.render(write_still=True)
        paths.append(sc.render.filepath)
    return paths


def game_mesh(k, name, voxel=0.004, target=5000, tex=1024, bones=None, pin=(), extrusion=0.014, ray=0.032,
              ao_dist=0.08, smooth_iter=6, hard=None, fold=1.0, detail=None, emphasis=None, head_tris=1800):
    """sculpt parts -> remeshed high -> decimated, unwrapped, skinned, baked low."""
    t = time.time()
    form = [p[0] for p in k.form_parts()]
    high = lib.union(form, name + '_high', k.coll, voxel, smooth_iter=smooth_iter)
    print(f'  high {lib.tris(high)} tris {time.time() - t:.1f}s', flush=True)
    low = lib.decimate(high, name, k.coll, target, detail, detail_factor=8.0)
    heads = [p[0] for p in k.form_parts(('head',))]
    if heads:
        # the realistic head and eyes: decimated on their own (they keep their shape far better than the remesh)
        tmp = []
        for h in heads:
            n_ = head_tris if h.name.endswith('head_real') else 60
            tmp.append(lib.decimate(h, h.name + '_low', k.coll, n_))
        lib.join_into(low, tmp, k.coll)
        for o in tmp:
            bpy.data.objects.remove(o)
    lib.unwrap(low, emphasis=emphasis)
    print(f'  low {lib.tris(low)} tris {time.time() - t:.1f}s', flush=True)
    if bones:
        lib.skin_weights(low, k.form_parts(('form', 'head')), bones, pin=pin)
        print(f'  weights {time.time() - t:.1f}s', flush=True)
    nsrc = high
    if fold:
        nsrc = lib.folds(high, [p[0] for p in k.form_parts() if p[1] in (hard or ())], name + '_folds', k.coll,
                         depth=0.0025 * fold, fine=0.0006 * fold)
        high.hide_render = True
        print(f'  folds {time.time() - t:.1f}s', flush=True)
    col, nrm = lib.bake(low, k.objects(), [nsrc] + heads, size=tex, name=name, extrusion=extrusion, ray=ray, ao_dist=ao_dist)
    print(f'  baked {time.time() - t:.1f}s', flush=True)
    low.data.materials.clear()
    low.data.materials.append(lib.game_material('mat_' + name, col, nrm))
    return low, high


def export_all():
    from soldiers import body, export, fparms
    t = time.time()
    coll = bpy.data.collections.new('EXPORT')
    bpy.context.scene.collection.children.link(coll)
    arm = export.rig(coll)
    objs = [arm]
    for n in ('allies', 'axis'):
        mod = importlib.import_module(f'soldiers.{n}')
        k = lib.Kit('S_' + n)
        mod.build(k)
        low, _ = game_mesh(k, 'soldier_' + n, bones=body.BONES, hard=mod.HARD, target=7000, detail=body.detail,
                           emphasis=body.uv_emphasis)
        export.bind(low, arm)
        objs.append(low)
        for part, fn in (('fore', fparms.build_forearm), ('upper', fparms.build_upperarm)):
            kf = lib.Kit(f'FP_{part}_{n}')
            fn(kf, n, mod.FP)
            sl, _ = game_mesh(kf, f'fp_{part}_{n}', voxel=0.0025, target=1600 if part == 'fore' else 900,
                              tex=1024 if part == 'fore' else 512, hard=('#4a4636', '#8f9289'), fold=1.3)
            objs.append(sl)
        print(f'[{n}] {time.time() - t:.1f}s', flush=True)
    # first-person fists: the soldier's own hand shape, shared by both teams
    for side, s in ((1, 'r'), (-1, 'l')):
        kh = lib.Kit(f'FP_hand_{s}')
        fparms.build_fist(kh, side)
        h, _ = game_mesh(kh, f'fp_hand_{s}', voxel=0.002, target=1400, tex=512, hard=(body.SKIN,), fold=0)
        h['wrist'] = [0.0, 0.0, body.FIST]
        h['fore'] = [0.0, 0.0, 1.0]
        objs.append(h)
    for o in objs:
        if o.name not in coll.objects:
            for c in o.users_collection:
                c.objects.unlink(o)
            coll.objects.link(o)
    size = export.write(objs)
    print(f'wrote {export.OUT} ({size // 1024} KB) in {time.time() - t:.1f}s', flush=True)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    flags = {a for a in argv if a.startswith('--')}
    names = [a for a in argv if not a.startswith('--')] or ['allies', 'axis']
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(OUT, exist_ok=True)
    if '--export' in flags:
        export_all()
        return
    for n in names:
        t = time.time()
        mod = importlib.import_module(f'soldiers.{n}')
        k = lib.Kit('S_' + n)
        mod.build(k)
        print(f'[{n}] {len(k.parts)} parts, {time.time() - t:.1f}s', flush=True)
        if '--sculpt' in flags:
            ps = workbench(os.path.join(OUT, f'{n}_sculpt'), SOLDIER_VIEWS, show=k.objects())
            print(sheet(ps, os.path.join(OUT, f'{n}_sculpt.png')), flush=True)
            for o in k.objects():
                o.hide_render = True
            continue
        from soldiers import body
        low, high = game_mesh(k, 'soldier_' + n, bones=body.BONES, hard=mod.HARD, target=7000, detail=body.detail,
                              emphasis=body.uv_emphasis)
        ps = eevee(os.path.join(OUT, f'{n}'), SOLDIER_VIEWS, show=[low])
        print(sheet(ps, os.path.join(OUT, f'{n}.png')), flush=True)
        low.hide_render = True


if __name__ == '__main__':
    main()
