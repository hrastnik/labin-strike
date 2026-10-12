"""Build weapon models headless, compare them with their reference photos, export the game GLB.

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/weapons/build.py -- stg44 [ids...] [flags]

flags:
    --norender   skip the silhouette compare and beauty renders
    --nobeauty   compare only
    --fp         beauty: first-person view only
    --export     build every model in models/ (or the ids given) and write client/public/assets/weapons/weapons.glb
    --blend      also save tools/blender/weapons/weapons.blend
Each model is tools/blender/weapons/models/<id>.py with build(g) (see lib.py); REF = reference id (default: id).
"""
import importlib
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402

from weapons import bake, lib, render  # noqa: E402

PY = lib.PY


def build_one(gid):
    mod = importlib.import_module(f'weapons.models.{gid}')
    g = lib.Gun(gid, ref=getattr(mod, 'REF', gid))
    g.meta.update(getattr(mod, 'META', {}))
    t = time.time()
    mod.build(g)
    g.finish()
    bake.bake(list(g.objects.values()), seed=len(gid))
    print(f'[{gid}] {g.tris()} tris, parts {sorted(g.objects)}, {time.time() - t:.1f}s', flush=True)
    return g


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    flags = {a for a in argv if a.startswith('--')}
    ids = [a for a in argv if not a.startswith('--')]
    if '--export' in flags and not ids:
        ids = sorted(f[:-3] for f in os.listdir(os.path.join(HERE, 'models')) if f.endswith('.py') and not f.startswith('_'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    guns = []
    for gid in ids:
        g = build_one(gid)
        guns.append(g)
        if '--norender' in flags or '--export' in flags:
            continue
        if g.meta.get('compare', True) and os.path.exists(os.path.join(lib.REF, g.ref + '_rect.json')):
            render.silhouette(g)
            r = subprocess.run([PY, os.path.join(HERE, 'reftool.py'), 'compare', g.ref], capture_output=True, text=True)
            print(r.stdout.strip(), r.stderr.strip()[-800:], flush=True)
        if '--nobeauty' not in flags:
            views = ('fp',) if '--fp' in flags else ('side', 'fp', 'q34')
            for p in render.beauty(g, views=views):
                print(p, flush=True)
    if '--export' in flags:
        from weapons import export
        export.write(guns)
    if '--blend' in flags:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'weapons.blend'))


main()
