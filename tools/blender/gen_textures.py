"""
Generates the map's procedural decals / foliage cards and resized copies of the Poly Haven (CC0) PBR
textures used by build_rudarska.py.  Run with the system python (needs Pillow + numpy):

    python3 tools/blender/gen_textures.py

inputs : tools/blender/textures/ph/<id>_{diff,nor,rough}.jpg   (downloaded from polyhaven.com, CC0)
outputs: tools/blender/textures/pbr/*.jpg, tools/blender/textures/gen/*.png
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PH = os.path.join(HERE, 'textures/ph')
PBR = os.path.join(HERE, 'textures/pbr')
GEN = os.path.join(HERE, 'textures/gen')
os.makedirs(PBR, exist_ok=True)
os.makedirs(GEN, exist_ok=True)

FONTS = '/System/Library/Fonts/Supplemental/'


def font(name, size):
    for p in (FONTS + name, '/System/Library/Fonts/' + name):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ------------------------------------------------------------------------------------------------
# PBR copies: (poly haven id, output name, diffuse px, normal px, roughness px or 0 = none)
# ------------------------------------------------------------------------------------------------
PBR_SET = [
    ('asphalt_02', 'asphalt', 2048, 1024, 512),
    ('asphalt_04', 'lot', 2048, 1024, 512),
    ('concrete_pavement_02', 'pavers', 1024, 512, 0),
    ('concrete_pavement', 'slabs', 1024, 512, 0),
    ('granite_tile_03', 'plaza', 1024, 1024, 0),
    ('concrete_wall_008', 'concrete', 1024, 512, 0),
    ('plastered_wall', 'plaster', 1024, 512, 0),
    ('grey_plaster_03', 'plaster_old', 1024, 512, 0),
    ('medieval_blocks_03', 'ashlar', 1024, 1024, 0),
    ('white_sandstone_blocks_02', 'stonebase', 1024, 512, 0),
    ('old_stone_wall', 'oldstone', 1024, 1024, 0),
    ('rock_face_03', 'rock', 1024, 1024, 0),
    ('clay_roof_tiles_02', 'rooftiles', 1024, 512, 0),
    ('tarred_gravel', 'flatroof', 512, 512, 0),
    ('leafy_grass', 'grass', 1024, 512, 0),
    ('forest_ground_04', 'soil', 512, 512, 0),
    ('bark_platanus', 'bark', 512, 512, 0),
    ('pine_bark', 'bark_pine', 512, 512, 0),
    ('exterior_wall_cladding_03', 'cladding', 1024, 512, 0),
    ('painted_metal_shutter', 'shutter', 512, 512, 0),
]


def resized(src, dst, px, mode='RGB'):
    if os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
        return
    im = Image.open(src).convert(mode)
    if im.size[0] != px:
        im = im.resize((px, px), Image.LANCZOS)
    im.save(dst, quality=90)


def make_pbr():
    for pid, name, dpx, npx, rpx in PBR_SET:
        resized(f'{PH}/{pid}_diff.jpg', f'{PBR}/{name}_diff.jpg', dpx)
        resized(f'{PH}/{pid}_nor.jpg', f'{PBR}/{name}_nor.jpg', npx)
        if rpx:
            resized(f'{PH}/{pid}_rough.jpg', f'{PBR}/{name}_rough.jpg', rpx)
    # neutralise the plaster albedo so materials can tint it (keeps the luminance detail)
    for name in ('plaster', 'plaster_old', 'cladding', 'shutter', 'concrete', 'rock', 'oldstone', 'lot'):
        p = f'{PBR}/{name}_diff.jpg'
        a = np.asarray(Image.open(p).convert('RGB')).astype(np.float32) / 255
        lum = (a @ np.array([0.299, 0.587, 0.114]))[..., None]
        lum = lum / max(1e-3, float(np.percentile(lum, 70)))  # ~1.0 for typical pixels
        g = np.clip(lum * 0.86, 0, 1)
        Image.fromarray((np.repeat(g, 3, axis=2) * 255).astype(np.uint8)).save(f'{PBR}/{name}_gray.jpg', quality=90)
    # the leafy_grass scan is mostly dead leaves; recolour it to a summer lawn (keeps the luminance detail)
    a = np.asarray(Image.open(f'{PH}/leafy_grass_diff.jpg').convert('RGB').resize((1024, 1024), Image.LANCZOS)).astype(np.float32) / 255
    lum = (a @ np.array([0.299, 0.587, 0.114]))[..., None]
    lum = lum / max(1e-3, float(lum.mean()))
    green = np.array([0.36, 0.45, 0.19]) * lum ** 1.3
    # leaves/dry patches (reddish pixels) become a slightly yellower green instead of brown
    dry = np.clip((a[..., 0:1] - a[..., 1:2]) * 6.0, 0, 1)
    green = green * (1 - dry * 0.35) + np.array([0.45, 0.44, 0.2]) * lum * dry * 0.35
    out = np.clip(green * 0.88 + a * 0.12, 0, 1)
    Image.fromarray((out * 255).astype(np.uint8)).save(f'{PBR}/grass_diff.jpg', quality=90)


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------

def bleed(im):
    """fill RGB of transparent pixels with blurred neighbouring colour (avoids dark fringes in mips)."""
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[..., :3], a[..., 3:4] / 255
    acc = np.zeros_like(rgb)
    w = np.zeros_like(al)
    for r in (2, 6, 16, 40):
        bi = Image.fromarray((rgb * al).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
        ba = Image.fromarray((al[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
        b = np.asarray(bi).astype(np.float32)
        bw = np.asarray(ba).astype(np.float32)[..., None] / 255
        fill = (w < 1e-3) & (bw > 1e-3)
        acc = np.where(fill, b / np.maximum(bw, 1e-3), acc)
        w = np.where(fill, 1.0, w)
    mean = (rgb * al).sum((0, 1)) / max(1, al.sum())
    acc = np.where(w > 0, acc, mean)
    out = np.where(al > 0.5, rgb, acc)
    return Image.fromarray(np.concatenate([np.clip(out, 0, 255), a[..., 3:4]], axis=2).astype(np.uint8), 'RGBA')


def save(im, name):
    im.save(os.path.join(GEN, name))


def hsv_jitter(base, rng, dh=0.03, ds=0.12, dv=0.18):
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in base])
    h = (h + rng.uniform(-dh, dh)) % 1
    s = min(1, max(0, s * (1 + rng.uniform(-ds, ds))))
    v = min(1, max(0, v * (1 + rng.uniform(-dv, dv))))
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))


# ------------------------------------------------------------------------------------------------
# foliage cards
# ------------------------------------------------------------------------------------------------

def _leaf_poly(x, y, a, L, W, tip=0.35):
    """ovate leaf with a pointed tip, base at (x, y) pointing along angle a; returns (left half, right half)."""
    left, right = [], []
    n = 9
    for k in range(n + 1):
        t = k / n
        w = W * math.sin(math.pi * min(1.0, t * (1 + tip))) ** 0.75 * (1 - t) ** 0.25 if t < 1 else 0
        left.append((t * L, w))
        right.append((t * L, -w))
    ca, sa = math.cos(a), math.sin(a)
    tr = lambda p: (x + p[0] * ca - p[1] * sa, y + p[0] * sa + p[1] * ca)
    mid = [tr((t * L, 0)) for t in (1, 0)]
    return [tr(p) for p in left] + mid[::-1][1:], [tr(p) for p in right] + mid[::-1][1:]


def _shade(col, f):
    return tuple(int(max(0, min(255, c * f))) for c in col)


def leaf_card(name, base, seed, n_leaves=1800, leaf=(30, 13), size=1024, twig=(78, 64, 48), back=(0.5, 0.95),
              spread=0.42, clumps=7, twigs=True, hue_dark=0.012):
    """broad-leaf cluster seen from outside the crown.  Twig skeleton from the bottom centre, leaves
    grouped in sub-clumps around the twig ends, drawn back-to-front: the back layers darker / bluer,
    the front ones lit from the top with a lit and a shaded half per leaf (reads as depth at range)."""
    import colorsys
    rng = random.Random(seed)
    S = size * 2
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = S / 2, S * 0.5
    # clump centres on a rough disc, slightly flattened at the bottom
    cl = [(cx + rng.uniform(-0.12, 0.12) * S, cy + rng.uniform(-0.08, 0.04) * S, S * rng.uniform(0.17, 0.22))]
    for i in range(clumps - 1):
        a = i / (clumps - 1) * math.tau + rng.uniform(-0.3, 0.3)
        r = S * rng.uniform(0.2, spread - 0.12)
        cl.append((cx + math.cos(a) * r, cy + math.sin(a) * r * 0.85, S * rng.uniform(0.1, 0.16)))
    if twigs:
        for (kx, ky, kr) in cl:
            x, y = cx + rng.uniform(-30, 30), S * 0.99
            steps = 10
            for k in range(steps):
                t = (k + 1) / steps
                nx = x + (kx - x) / (steps - k) + rng.uniform(-14, 14)
                ny = y + (ky - y) / (steps - k) + rng.uniform(-14, 14)
                d.line((x, y, nx, ny), fill=(*_shade(twig, 0.8 + 0.3 * t), 255), width=max(3, int(16 * (1 - t * 0.8))))
                x, y = nx, ny
            for j in range(4):
                a = rng.uniform(0, math.tau)
                L = kr * rng.uniform(0.5, 0.9)
                d.line((kx, ky, kx + math.cos(a) * L, ky + math.sin(a) * L), fill=(*twig, 255), width=4)
    h0, s0, v0 = colorsys.rgb_to_hsv(*[c / 255 for c in base])
    layers = 4
    for layer in range(layers):
        lt = layer / (layers - 1)
        dark = back[0] + (back[1] - back[0]) * lt
        for i in range(n_leaves // layers):
            kx, ky, kr = rng.choice(cl)
            # back layer fills the clump core, front layers scatter towards the clump rim
            r = kr * (rng.random() ** (0.9 - 0.45 * lt)) * (0.85 + 0.3 * lt)
            a = rng.uniform(0, math.tau)
            x, y = kx + math.cos(a) * r, ky + math.sin(a) * r
            if not (24 < x < S - 24 and 24 < y < S - 24):
                continue
            # top of the card catches the sun, bottom and clump undersides are in shade
            sh = dark * (0.78 + 0.42 * (1 - y / S)) * (1.08 - 0.25 * max(0.0, (y - ky) / kr))
            h = (h0 + rng.uniform(-0.025, 0.025) + hue_dark * (1 - lt)) % 1
            s = min(1, s0 * rng.uniform(0.85, 1.15) * (1.05 - 0.1 * lt))
            v = v0 * rng.uniform(0.82, 1.12)
            col = _shade(tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, s, v)), sh)
            ang = math.atan2(y - ky, x - kx) + rng.uniform(-1.1, 1.1)
            L = leaf[0] * rng.uniform(0.8, 1.25) * S / 1024
            W = leaf[1] * rng.uniform(0.8, 1.2) * S / 1024
            lp, rp = _leaf_poly(x - math.cos(ang) * L * 0.3, y - math.sin(ang) * L * 0.3, ang, L, W)
            lit = (math.sin(ang) < 0)  # the half facing up gets the light
            d.polygon(lp, fill=(*_shade(col, 1.07 if lit else 0.93), 255))
            d.polygon(rp, fill=(*_shade(col, 0.93 if lit else 1.07), 255))
            if lt > 0.5 and L > 40:
                d.line((lp[0], lp[len(lp) - 2]), fill=(*_shade(col, 1.15), 255), width=2)
    im = im.resize((size, size), Image.LANCZOS)
    a = np.asarray(im).copy()
    a[..., 3] = np.where(a[..., 3] > 110, 255, 0)
    save(bleed(Image.fromarray(a, 'RGBA')), name)


def conifer_card(name, seed, size=1024, base=(40, 63, 40), tips=(78, 104, 56)):
    """spruce branch seen from the side: a main branch running out from the trunk (u=0) and drooping,
    with a dense curtain of hanging branchlets covered in short needles.  Mostly opaque in the middle
    so the tree reads as the dark, solid cone the Labin spruces are."""
    rng = random.Random(seed)
    S = size * 2
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bark = (62, 46, 34)

    def needles(x, y, nx, ny, ang, k, steps, depth, shade_y):
        n = int(40 - depth * 10)
        for _ in range(n):
            t = rng.random()
            px, py = x + (nx - x) * t, y + (ny - y) * t
            na = ang + rng.choice((-1, 1)) * rng.uniform(0.5, 1.2) + 0.35
            nl = rng.uniform(14, 26) * (1 - k / steps * 0.35)
            young = (k / steps) ** 2 * (0.6 if depth else 0.3)
            col = tuple(int(base[i] * (1 - young) + tips[i] * young) for i in range(3))
            col = hsv_jitter(col, rng, 0.015, 0.15, 0.22)
            col = _shade(col, shade_y(py))
            d.line((px, py, px + math.cos(na) * nl, py + math.sin(na) * nl), fill=(*col, 255), width=5)

    def branch(x0, y0, ang, L, w, depth, shade_y, droop=0.03):
        x, y = x0, y0
        steps = 16 if depth == 0 else 9
        for k in range(steps):
            nx = x + math.cos(ang) * L / steps
            ny = y + math.sin(ang) * L / steps
            d.line((x, y, nx, ny), fill=(*bark, 255), width=max(2, int(w * (1 - k / steps * 0.7))))
            needles(x, y, nx, ny, ang, k, steps, depth, shade_y)
            if depth == 0 and k >= 1:
                # hanging branchlets (the curtain) plus a few side shoots pointing out/up
                for _ in range(2):
                    branch(nx, ny, math.pi / 2 + rng.uniform(-0.45, 0.25), L * rng.uniform(0.18, 0.34) * (1 - k / steps * 0.5),
                           w * 0.35, 1, shade_y, droop=0.0)
                if k % 2 == 0:
                    branch(nx, ny, ang - rng.uniform(0.5, 0.9), L * rng.uniform(0.12, 0.2), w * 0.3, 1, shade_y)
            elif depth == 1 and k % 3 == 2 and L > 120:
                for sgn in (-1, 1):
                    branch(nx, ny, ang + sgn * rng.uniform(0.5, 0.8), L * 0.35, w * 0.5, 2, shade_y)
            x, y = nx, ny
            ang += droop * (1 if k < steps * 0.7 else -2.2) + rng.uniform(-0.03, 0.03)

    # back branch (darker) then front branch
    branch(S * 0.02, S * 0.36, -0.05, S * 0.95, 20, 0, lambda py: 0.62 + 0.25 * (1 - py / S))
    branch(S * 0.02, S * 0.42, 0.02, S * 0.92, 22, 0, lambda py: 0.85 + 0.4 * (1 - py / S))
    im = im.resize((size, size), Image.LANCZOS)
    a = np.asarray(im).copy()
    a[..., 3] = np.where(a[..., 3] > 100, 255, 0)
    save(bleed(Image.fromarray(a, 'RGBA')), name)


def hedge_tex(name, base, seed, size=1024):
    """tileable dense small-leaf foliage (no alpha) for clipped hedges / shrub volumes: dark gaps,
    leaves with a lit and a shaded half, a few bright sprigs on top."""
    rng = random.Random(seed)
    S = size
    im = Image.new('RGB', (S, S), _shade(base, 0.22))
    d = ImageDraw.Draw(im)
    for layer in range(3):
        for i in range(5200):
            x, y = rng.uniform(0, S), rng.uniform(0, S)
            col = hsv_jitter(base, rng, 0.03, 0.15, 0.25)
            col = _shade(col, (0.45, 0.75, 1.0)[layer] * rng.uniform(0.85, 1.15))
            a = rng.uniform(0, math.tau)
            L, W = rng.uniform(13, 22), rng.uniform(5, 8)
            for ox in (-S, 0, S):
                for oy in (-S, 0, S):
                    px, py = x + ox, y + oy
                    if -30 < px < S + 30 and -30 < py < S + 30:
                        lp, rp = _leaf_poly(px, py, a, L, W)
                        lit = math.sin(a) < 0
                        d.polygon(lp, fill=_shade(col, 1.12 if lit else 0.85))
                        d.polygon(rp, fill=_shade(col, 0.85 if lit else 1.12))
    im.save(os.path.join(GEN, name), quality=92)


def grass_card(name, seed, size=512):
    rng = random.Random(seed)
    S = size * 2
    im = Image.new('RGBA', (S, S // 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(700):
        x = rng.uniform(10, S - 10)
        h = rng.uniform(0.35, 0.95) * S / 2
        lean = rng.uniform(-0.35, 0.35)
        col = hsv_jitter((88, 118, 52), rng, 0.04, 0.2, 0.3)
        y0 = S / 2
        pts = [(x - 4, y0), (x + 4, y0), (x + lean * h, y0 - h)]
        d.polygon(pts, fill=(*col, 255))
    im = im.resize((size, size // 2), Image.LANCZOS)
    a = np.asarray(im).copy()
    a[..., 3] = np.where(a[..., 3] > 100, 255, 0)
    save(bleed(Image.fromarray(a, 'RGBA')), name)


# ------------------------------------------------------------------------------------------------
# signage & decals
# ------------------------------------------------------------------------------------------------

def text_decal(name, lines, size, fnt, color=(255, 255, 255), bg=None, pad=10, align='center', spacing=8):
    im = Image.new('RGBA', size, bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    W, H = size
    heights = []
    for txt, f in lines:
        bb = d.textbbox((0, 0), txt, font=f)
        heights.append((bb[3] - bb[1], bb))
    total = sum(h for h, _ in heights) + spacing * (len(lines) - 1)
    y = (H - total) / 2
    for (txt, f), (h, bb) in zip(lines, heights):
        w = bb[2] - bb[0]
        x = (W - w) / 2 if align == 'center' else pad
        d.text((x - bb[0], y - bb[1]), txt, font=f, fill=color)
        y += h + spacing
    return im


def make_signs():
    # sports centre lettering (white on transparent), 2 lines like the real facade
    f1 = font('DIN Condensed Bold.ttf', 150)
    im = text_decal('sports', [('SPORTSKI CENTAR', f1), ('FRANKO MILETA', f1)], (1400, 400), None, spacing=30)
    save(bleed(im), 'sports_text.png')

    # jumping handball player silhouette (white), drawn from simple shapes
    S = 1024
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    W = (255, 255, 255, 255)
    def limb(p0, p1, w):
        w = int(w * 1.55)
        d.line((*p0, *p1), fill=W, width=w)
        d.ellipse((p1[0] - w / 2, p1[1] - w / 2, p1[0] + w / 2, p1[1] + w / 2), fill=W)
        d.ellipse((p0[0] - w / 2, p0[1] - w / 2, p0[0] + w / 2, p0[1] + w / 2), fill=W)
    hip, chest, neck = (470, 560), (540, 380), (560, 330)
    d.polygon([(420, 600), (520, 615), (625, 395), (575, 330), (480, 365)], fill=W)  # torso
    d.ellipse((530, 215, 640, 325), fill=W)  # head
    limb((585, 365), (700, 250), 46)  # throwing upper arm
    limb((700, 250), (760, 120), 40)  # forearm up
    d.ellipse((730, 60, 820, 150), fill=W)  # ball
    limb((540, 385), (430, 450), 44)  # other arm
    limb((430, 450), (360, 400), 38)
    limb((480, 590), (360, 690), 56)  # thigh (kicked back)
    limb((360, 690), (250, 640), 48)  # shin
    limb((250, 640), (205, 665), 30)  # foot
    limb((490, 590), (560, 760), 56)  # leading thigh
    limb((560, 760), (500, 900), 48)
    limb((500, 900), (560, 925), 30)
    save(bleed(im), 'handball.png')

    # CK logo (yellow-green) for the ground-floor glazing
    im = Image.new('RGBA', (512, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font('Arial Black.ttf', 200)
    d.text((40, 10), 'CK', font=f, fill=(222, 214, 40, 255))
    save(bleed(im), 'ck_logo.png')

    # blue parking sign
    im = Image.new('RGBA', (256, 256), (22, 72, 168, 255))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 6, 249, 249), 18, outline=(255, 255, 255, 255), width=8)
    f = font('Arial Bold.ttf', 210)
    bb = d.textbbox((0, 0), 'P', font=f)
    d.text(((256 - bb[2] - bb[0]) / 2, (256 - bb[3] - bb[1]) / 2 - 6), 'P', font=f, fill=(255, 255, 255, 255))
    save(im, 'sign_p.png')

    # pedestrian crossing sign (blue square, white triangle, black walker)
    im = Image.new('RGBA', (256, 256), (22, 72, 168, 255))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 6, 249, 249), 18, outline=(255, 255, 255, 255), width=6)
    d.polygon([(128, 26), (236, 222), (20, 222)], fill=(255, 255, 255, 255))
    for i in range(4):
        d.rectangle((60 + i * 36, 196, 80 + i * 36, 214), fill=(0, 0, 0, 255))
    K = (0, 0, 0, 255)
    d.ellipse((118, 82, 140, 104), fill=K)
    d.line((128, 108, 120, 150), fill=K, width=11)
    d.line((120, 150, 104, 185), fill=K, width=9)
    d.line((120, 150, 142, 184), fill=K, width=9)
    d.line((126, 116, 104, 136), fill=K, width=7)
    d.line((126, 116, 148, 134), fill=K, width=7)
    save(im, 'sign_cross.png')

    # heating/AC company pole sign (stacked panels like the real one at the corner)
    im = Image.new('RGBA', (256, 768), (240, 240, 236, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 255, 200), fill=(30, 120, 60, 255))
    d.text((20, 40), 'IDEAL', font=font('Arial Black.ttf', 64), fill=(255, 255, 255, 255))
    d.text((24, 120), 'TERMO', font=font('Arial Bold.ttf', 50), fill=(250, 220, 60, 255))
    f = font('Arial Narrow Bold.ttf', 34)
    for i, t in enumerate(['CENTRALNO', 'GRIJANJE', '·', 'KLIMA', 'UREĐAJI', '·', 'SOLARNI', 'SUSTAVI']):
        bb = d.textbbox((0, 0), t, font=f)
        d.text(((256 - bb[2]) / 2, 225 + i * 62), t, font=f, fill=(25, 60, 120, 255))
    d.rectangle((0, 0, 255, 767), outline=(120, 120, 120, 255), width=4)
    save(im, 'sign_ideal.png')

    # small wall signs on the teal building corner
    im = Image.new('RGBA', (512, 128), (196, 28, 30, 255))
    d = ImageDraw.Draw(im)
    f = font('Arial Black.ttf', 78)
    bb = d.textbbox((0, 0), 'RUDARSKI', font=f)
    d.text(((512 - bb[2]) / 2, (128 - bb[3]) / 2 - 4), 'RUDARSKI', font=f, fill=(255, 255, 255, 255))
    save(im, 'sign_rudarski.png')
    im = Image.new('RGBA', (512, 128), (30, 80, 170, 255))
    d = ImageDraw.Draw(im)
    f = font('Arial Black.ttf', 84)
    bb = d.textbbox((0, 0), 'TRIO I', font=f)
    d.text(((512 - bb[2]) / 2, (128 - bb[3]) / 2 - 4), 'TRIO I', font=f, fill=(255, 255, 255, 255))
    save(im, 'sign_trio.png')
    im = Image.new('RGBA', (256, 96), (246, 206, 30, 255))
    d = ImageDraw.Draw(im)
    f = font('Arial Black.ttf', 64)
    bb = d.textbbox((0, 0), '55-70', font=f)
    d.text(((256 - bb[2]) / 2, (96 - bb[3]) / 2 - 6), '55-70', font=f, fill=(20, 20, 20, 255))
    save(im, 'sign_5570.png')
    # FINA lettering
    im = Image.new('RGBA', (512, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((20, 0), 'FINA', font=font('Arial Black.ttf', 140), fill=(20, 70, 150, 255))
    save(bleed(im), 'sign_fina.png')
    # brass plaques by the admin entrance
    im = Image.new('RGBA', (256, 128), (150, 120, 60, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((6, 6, 249, 121), outline=(90, 70, 30, 255), width=4)
    for i in range(5):
        d.rectangle((24, 22 + i * 19, 232 - (i % 2) * 50, 30 + i * 19), fill=(80, 60, 25, 255))
    save(im, 'plaque.png')
    # library sign
    im = Image.new('RGBA', (1024, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font('Arial Bold.ttf', 74)
    d.text((10, 20), 'GRADSKA KNJIŽNICA LABIN', font=f, fill=(245, 245, 240, 255))
    save(bleed(im), 'sign_library.png')


def make_flags():
    # Croatian tricolour with a simplified chequy shield
    W, H = 512, 256
    im = Image.new('RGBA', (W, H), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, H / 3), fill=(220, 30, 40, 255))
    d.rectangle((0, 2 * H / 3, W, H), fill=(23, 23, 150, 255))
    sx, sy, s = W / 2 - 50, 50, 20
    for i in range(5):
        for j in range(5):
            d.rectangle((sx + i * s, sy + j * s, sx + (i + 1) * s, sy + (j + 1) * s),
                        fill=(220, 30, 40, 255) if (i + j) % 2 == 0 else (255, 255, 255, 255))
    d.polygon([(sx, sy + 100), (sx + 100, sy + 100), (sx + 50, sy + 150)], fill=(220, 30, 40, 255))
    d.rectangle((sx, sy - 18, sx + 100, sy), fill=(60, 110, 200, 255))
    save(im, 'flag_hr.png')
    im = Image.new('RGBA', (W, H), (0, 51, 153, 255))
    d = ImageDraw.Draw(im)
    for k in range(12):
        a = k / 12 * math.tau
        cx, cy = W / 2 + math.cos(a) * 80, H / 2 + math.sin(a) * 80
        pts = []
        for j in range(10):
            r = 14 if j % 2 == 0 else 6
            t = -math.pi / 2 + j * math.pi / 5
            pts.append((cx + math.cos(t) * r, cy + math.sin(t) * r))
        d.polygon(pts, fill=(255, 204, 0, 255))
    save(im, 'flag_eu.png')


def make_graffiti():
    """tags + '1950' sprayed on the old SE retaining wall (RGBA overlay, 4:1)."""
    rng = random.Random(1950)
    W, H = 4096, 1024
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fonts = [font('Impact.ttf', 300), font('Arial Black.ttf', 260), font('Trebuchet MS Bold Italic.ttf', 280),
             font('Arial Rounded Bold.ttf', 250)]
    words = ['RUDAR', 'LBN', 'ULTRAS', 'KAOS', 'MINA', 'ZONA', 'BOK', 'ALBONA', 'NKR']
    # the real wall carries a band of dark, weathered spray tags (no bright colours)
    palette = [(20, 20, 24), (28, 28, 34), (44, 44, 52), (60, 58, 66), (34, 38, 64), (70, 40, 40)]
    x = 80
    while x < W - 400:
        wd = rng.choice(words)
        f = rng.choice(fonts)
        col = rng.choice(palette)
        y = rng.uniform(420, 600)
        layer = Image.new('RGBA', (1400, 600), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.text((40, 60), wd, font=f, fill=(*col, rng.randint(150, 215)), stroke_width=rng.choice((0, 0, 6)),
                stroke_fill=rng.choice(palette) + (200,))
        layer = layer.rotate(rng.uniform(-8, 8), resample=Image.BICUBIC, expand=False)
        bb = layer.getbbox()
        if bb:
            layer = layer.crop(bb)
            sc = rng.uniform(0.45, 0.8)
            layer = layer.resize((int(layer.width * sc), int(layer.height * sc)), Image.LANCZOS)
            im.alpha_composite(layer, (int(x), int(y - layer.height / 2)))
            x += layer.width * rng.uniform(0.75, 1.0) + rng.uniform(-40, 120)
        else:
            x += 300
    # '1950' carved/painted date
    f = font('Arial Black.ttf', 210)
    d.text((W * 0.47, 160), '1950', font=f, fill=(60, 58, 56, 120))
    # some spray drips
    a = np.asarray(im).copy()
    for _ in range(140):
        cx = rng.randrange(0, W)
        col = a[:, cx, 3].nonzero()[0]
        if len(col) == 0:
            continue
        y0 = col.max()
        L = rng.randrange(20, 120)
        c = a[y0, cx].copy()
        a[y0:min(H, y0 + L), cx:cx + 4] = c
    g = Image.fromarray(a, 'RGBA').filter(ImageFilter.GaussianBlur(2.2))
    noise = (np.random.default_rng(3).random((H, W)) * 0.35 + 0.65)
    ga = np.asarray(g).astype(np.float32)
    ga[..., 3] *= noise
    save(Image.fromarray(ga.astype(np.uint8), 'RGBA'), 'graffiti.png')


def make_misc():
    # Croatian-style licence plate
    im = Image.new('RGBA', (512, 112), (245, 245, 242, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 511, 111), outline=(20, 20, 20, 255), width=6)
    d.rectangle((6, 6, 60, 105), fill=(0, 51, 153, 255))
    d.text((16, 66), 'HR', font=font('Arial Bold.ttf', 26), fill=(255, 255, 255, 255))
    d.text((80, 12), 'LB 274-KM', font=font('DIN Condensed Bold.ttf', 96), fill=(15, 15, 15, 255))
    save(im, 'plate.png')
    # manhole cover
    S = 256
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((4, 4, S - 4, S - 4), fill=(52, 50, 48, 255))
    d.ellipse((16, 16, S - 16, S - 16), outline=(80, 78, 74, 255), width=6)
    for k in range(-5, 6):
        d.line((S / 2 + k * 18 - 60, 30, S / 2 + k * 18 + 60, S - 30), fill=(70, 68, 64, 255), width=5)
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).ellipse((4, 4, S - 4, S - 4), fill=255)
    im.putalpha(mask)
    save(bleed(im), 'manhole.png')
    # drain grate
    im = Image.new('RGBA', (256, 128), (40, 38, 36, 255))
    d = ImageDraw.Draw(im)
    for i in range(14):
        d.rectangle((10 + i * 17, 12, 18 + i * 17, 116), fill=(8, 8, 8, 255))
    save(im, 'grate.png')
    # window interior / curtains (teal building upper windows: yellow curtains)
    # pale cream-yellow drapes with soft vertical folds (seen through the glass they look washed out)
    x = np.arange(256)[None, :, None]
    fold = 0.86 + 0.14 * np.sin(x / 256 * math.tau * 14) + 0.04 * np.sin(x / 256 * math.tau * 37)
    base = np.array([196, 186, 128], np.float32)[None, None, :]
    a = np.clip(np.repeat(base * fold, 256, axis=0), 0, 255).astype(np.uint8)
    Image.fromarray(a, 'RGB').save(os.path.join(GEN, 'curtain.jpg'), quality=88)
    # glass-block column texture
    im = Image.new('RGB', (256, 256), (170, 182, 186))
    d = ImageDraw.Draw(im)
    for i in range(0, 256, 32):
        d.line((i, 0, i, 255), fill=(120, 124, 122), width=4)
        d.line((0, i, 255, i), fill=(120, 124, 122), width=4)
    for i in range(0, 256, 32):
        for j in range(0, 256, 32):
            d.ellipse((i + 8, j + 8, i + 24, j + 24), fill=(196, 208, 212))
    im.save(os.path.join(GEN, 'glassblock.jpg'), quality=88)
    # far hills: tree-line silhouette strip (RGBA)
    rng = random.Random(5)
    W, H = 2048, 256
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(1600):
        x = rng.uniform(0, W)
        y = H - rng.uniform(10, 120) * (0.6 + 0.4 * math.sin(x / W * math.tau * 2) ** 2)
        r = rng.uniform(8, 22)
        col = hsv_jitter((62, 82, 48), rng, 0.03, 0.15, 0.25)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*col, 255))
        d.rectangle((x - r, y, x + r, H), fill=(*col, 255))
    save(bleed(im), 'treeline.png')
    # soft contact shadow blob (cars, props)
    S = 256
    yy, xx = np.mgrid[0:S, 0:S] / (S - 1) * 2 - 1
    r = np.sqrt((xx * 0.9) ** 2 + (yy * 0.9) ** 2)
    al = np.clip(1 - r, 0, 1) ** 1.6
    b = np.zeros((S, S, 4), np.uint8)
    b[..., 3] = (al * 210).astype(np.uint8)
    save(Image.fromarray(b, 'RGBA'), 'blob.png')
    # vertical grime gradient (dark at the bottom), used on wall bases
    g = np.zeros((256, 64, 4), np.uint8)
    t = np.linspace(0, 1, 256)[:, None]
    g[..., 0:3] = 30
    g[..., 3] = (np.clip(t ** 2.2, 0, 1) * 150).astype(np.uint8)
    save(Image.fromarray(g, 'RGBA'), 'grime.png')


def make_foliage():
    leaf_card('leaf_broad.png', (66, 98, 40), 11, n_leaves=2400, leaf=(30, 11))
    leaf_card('leaf_plane.png', (88, 118, 50), 12, n_leaves=1300, leaf=(40, 30), clumps=6)
    leaf_card('leaf_yellow.png', (138, 156, 50), 13, n_leaves=2400, leaf=(30, 11))
    leaf_card('leaf_cedar.png', (52, 78, 58), 14, n_leaves=9000, leaf=(15, 6), clumps=9, spread=0.46)
    leaf_card('leaf_hedge.png', (58, 92, 38), 15, n_leaves=6000, leaf=(19, 8), clumps=8, twigs=False, back=(0.6, 1.0))
    conifer_card('leaf_spruce.png', 21)
    hedge_tex('hedge.jpg', (58, 90, 38), 31)


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['foliage']:
        make_foliage()
        raise SystemExit
    make_pbr()
    make_foliage()
    grass_card('grass_card.png', 41)
    make_signs()
    make_flags()
    make_graffiti()
    make_misc()
    print('textures ok')
