"""Grades the photographed sky backdrop towards the softer, hazier summer sky of the Street View
references (less saturated blue, brighter haze towards the horizon).  The HDR used for lighting is
left untouched.

    python3 tools/sky_src/grade_sky.py      # sky_tonemapped.jpg -> client/public/assets/sky/sky.jpg
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '../../client/public/assets/sky/sky.jpg')

im = Image.open(os.path.join(HERE, 'sky_tonemapped.jpg')).convert('RGB').resize((4096, 2048), Image.LANCZOS)
a = np.asarray(im).astype(np.float32) / 255
lum = (a @ np.array([0.299, 0.587, 0.114]))[..., None]
# desaturate (mostly the deep blue; clouds are already neutral)
a = lum + (a - lum) * 0.55
# haze: blend towards a pale blue-grey, strongest at the horizon (row 1024), fading out by ~35 deg up
h = a.shape[0]
elev = (h / 2 - np.arange(h)) / (h / 2) * 90          # +90 zenith .. -90 nadir
haze = np.clip(1 - np.abs(elev) / 35, 0, 1) ** 1.6 * 0.45
haze = haze[:, None, None]
a = a * (1 - haze) + np.array([0.80, 0.83, 0.87]) * haze
# a touch brighter overall
a = np.clip(a * 1.05, 0, 1)
Image.fromarray((a * 255).astype(np.uint8)).save(OUT, quality=88)
print('sky ok', OUT)
