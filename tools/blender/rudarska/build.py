"""Headless build of the Rudarska map:
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/rudarska/build.py"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

t0 = time.time()
from rudarska import lib, palette  # noqa: E402  (lib resets the scene on import)

palette.define()
from rudarska import buildings, site, zfix  # noqa: E402

buildings.build()
site.build()
lib.G.build_all()
zfix.resolve()   # push apart near-coplanar faces (z-fighting)
lib.export()
print(f'[rudarska] done in {time.time() - t0:.1f}s')
