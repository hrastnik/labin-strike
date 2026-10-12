"""Generic Croatian-format licence plates (PU = Pula area, which includes Labin) -> tex/plates.png.
One row per plate variant (4 variants, 512 x 112 each). Run with the system python (needs Pillow)."""
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = '/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf'
W, H = 512, 112
TEXTS = [('PU', '482-KD'), ('PU', '117-HR'), ('PU', '930-AL'), ('PU', '256-LB')]


def plate(city, num):
    im = Image.new('RGB', (W, H), (244, 244, 240))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, W - 3, H - 3), radius=10, outline=(20, 20, 20), width=4)
    # EU band
    bw = 46
    d.rounded_rectangle((6, 6, 6 + bw, H - 7), radius=6, fill=(0, 51, 153))
    cx, cy, r = 6 + bw / 2, 34, 15
    for i in range(12):
        a = 2 * math.pi * i / 12
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 204, 0))
    f2 = ImageFont.truetype(FONT, 30)
    d.text((cx, 84), 'HR', font=f2, fill=(255, 255, 255), anchor='mm')
    f = ImageFont.truetype(FONT, 96)
    d.text((80, H / 2 + 6), city, font=f, fill=(15, 15, 15), anchor='lm')
    # red-white chequered shield between the city code and the number
    sx, sy, s = 178, 30, 9
    for i in range(5):
        for j in range(5):
            if (i + j) % 2 == 0:
                d.rectangle((sx + i * s, sy + j * s, sx + i * s + s - 1, sy + j * s + s - 1), fill=(210, 20, 30))
    d.rectangle((sx - 1, sy - 1, sx + 5 * s, sy + 5 * s), outline=(150, 20, 30), width=1)
    d.text((240, H / 2 + 6), num, font=f, fill=(15, 15, 15), anchor='lm')
    return im


if __name__ == '__main__':
    out = Image.new('RGB', (W, H * len(TEXTS)))
    for i, (c, n) in enumerate(TEXTS):
        out.paste(plate(c, n), (0, i * H))
    os.makedirs(os.path.join(HERE, 'tex'), exist_ok=True)
    out.save(os.path.join(HERE, 'tex', 'plates.png'))
