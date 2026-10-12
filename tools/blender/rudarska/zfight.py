"""Z-fighting audit: builds the map like build.py (incl. the zfix pass, no export) and lists overlapping
coplanar / near-coplanar faces of different materials that are still closer than ZF_GAP metres.
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/rudarska/zfight.py
ZF_RAW=1 skips the zfix pass (shows what the generators produce)."""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rudarska import lib, palette  # noqa: E402

palette.define()
from rudarska import buildings, site, zfix  # noqa: E402

buildings.build()
site.build()
lib.G.build_all()
if os.environ.get('ZF_RAW') != '1':
    zfix.resolve()

GAP = float(os.environ.get('ZF_GAP', '0.012'))
MIN_AREA = float(os.environ.get('ZF_AREA', '0.002'))

sc = zfix.Scene()
print(f'[zfight] {len(sc.tris)} triangles')
pairs = defaultdict(lambda: [0.0, 1.0, None])
for ti, tj, gap, a in sc.pairs(GAP):
    if not zfix.needs_fix(ti, tj):
        continue
    ki = (sc.meshes[ti[0]][0].name, ti[2])
    kj = (sc.meshes[tj[0]][0].name, tj[2])
    e = pairs[tuple(sorted([ki, kj]))]
    e[0] += a
    e[1] = min(e[1], gap)
    if e[2] is None:
        c = (ti[5][0] + ti[5][1] + ti[5][2]) / 3
        e[2] = (round(c.x, 2), round(c.y, 2), round(c.z, 2), tuple(round(x, 2) for x in ti[3]))
sc.free()

rows = sorted(((v[0], v[1], k, v[2]) for k, v in pairs.items() if v[0] >= MIN_AREA), reverse=True)
print(f'[zfight] {len(rows)} overlapping surface pairs (gap < {GAP} m)')
for a, gap, k, p in rows[:200]:
    print(f'  {a:8.3f} m2  gap {gap * 1000:5.1f}mm  {k[0][0]}[{k[0][1]}]  <>  {k[1][0]}[{k[1][1]}]  at {p}')
