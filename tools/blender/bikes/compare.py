"""Overlay a model's orthographic side render on its reference photo (system python3 with Pillow).

    python3 tools/blender/bikes/compare.py <out dir> wla|r35

Writes <name>_cmp.png: the photo warped into the render's frame with the model on top at partial opacity, and
<name>_edges.png: the model's silhouette outline drawn over the photo."""
import json
import math
import os
import sys

from PIL import Image, ImageChops, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CALS = {
    'wla': (os.path.expanduser('~/Desktop/bike-reference-photos/hraley-davidson-wla.jpg'), ((192, 432), (852, 447), 1.48, 0.33)),
    'r35': (os.path.expanduser('~/Desktop/bike-reference-photos/bmw-r35.jpg'), ((131, 309), (524, 311), 1.40, 0.33)),
}


def main(out, name):
    photo, ((ax, ay), (bx, by), wb, ah) = CALS[name]
    info = json.load(open(os.path.join(out, f'{name}_side.json')))
    W, H, k, cy, cz = info['w'], info['h'], info['k'], info['cy'], info['cz']
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    s = wb / L
    rot = math.atan2(dy, dx)
    c, sn = math.cos(rot), math.sin(rot)
    # render px (u, v) -> model (Y, Z) -> photo px (x, y), all affine
    # Y = (u - W/2)/k + cy ; Z = (H/2 - v)/k + cz
    # x' = (Y + wb/2)/s ; y' = (ah - Z)/s ; x = ax + x' c - y' sn ; y = ay + x' sn + y' c
    def to_photo(u, v):
        Y = (u - W / 2) / k + cy
        Z = (H / 2 - v) / k + cz
        xp, yp = (Y + wb / 2) / s, (ah - Z) / s
        return ax + xp * c - yp * sn, ay + xp * sn + yp * c
    o = to_photo(0, 0)
    du = [a - b for a, b in zip(to_photo(1, 0), o)]
    dv = [a - b for a, b in zip(to_photo(0, 1), o)]
    coeffs = (du[0], dv[0], o[0], du[1], dv[1], o[1])
    ph = Image.open(photo).convert('RGB').transform((W, H), Image.AFFINE, coeffs, Image.BICUBIC, fillcolor=(255, 255, 255))
    rd = Image.open(info['png']).convert('RGBA')
    alpha = rd.split()[3]
    a2 = alpha.point(lambda v: int(v * 0.55))
    cmp = ph.copy()
    cmp.paste(rd.convert('RGB'), (0, 0), a2)
    cmp.save(os.path.join(out, f'{name}_cmp.png'))
    # outline of the model over the photo
    m = alpha.point(lambda v: 255 if v > 100 else 0)
    edge = ImageChops.difference(m.filter(ImageFilter.MaxFilter(3)), m)
    ed = ph.copy()
    ed.paste((255, 0, 40), (0, 0), edge)
    ed.save(os.path.join(out, f'{name}_edges.png'))
    side = Image.new('RGB', (W, H * 2), 'white')
    side.paste(ph, (0, 0))
    bg = Image.new('RGB', (W, H), (235, 235, 235))
    bg.paste(rd.convert('RGB'), (0, 0), alpha)
    side.paste(bg, (0, H))
    side.save(os.path.join(out, f'{name}_pair.png'))
    print('ok', name)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
