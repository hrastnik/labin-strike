"""Reference photos for the weapon models: fetch, calibrate, rectify to model space, compare against renders.
Run with the system python (needs numpy, Pillow, opencv-python):

    python3 tools/blender/weapons/reftool.py fetch [id ...]      download the Wikimedia Commons originals (refs.json)
    python3 tools/blender/weapons/reftool.py pixgrid <id>        source photo with a labelled pixel grid (to pick cal points)
    python3 tools/blender/weapons/reftool.py rect <id>           rectify with refs.json "cal" -> ref/<id>_rect.png + grid + mask
    python3 tools/blender/weapons/reftool.py crop <id> u0 u1 v0 v1 [px_per_mm]   zoomed, finely gridded crop (model mm)
    python3 tools/blender/weapons/reftool.py profile <id> u0 u1 [step]           mask top/bottom v along u (model mm)
    python3 tools/blender/weapons/reftool.py compare <id>        overlay ref/<id>_render.png (from compare_render) on the ref
    python3 tools/blender/weapons/reftool.py trace <id> '<json>'  mask outline(s) inside a region polygon (model mm, JSON)

Model space (mm): u forward along the bore (muzzle at +u), v up, u = 0 at the trigger, v = 0 on the bore axis.
Calibration ("cal" in refs.json, all in source-image pixels):
    muzzle  [x, y]  centre of the muzzle face, on the bore axis
    axis    [x, y]  any other point on the bore axis (further back)
    origin  [x, y]  the model origin (front face of the trigger blade); only its position along the bore counts
Calibrate in cal/<id>.json ({"cal": {...}} plus any other refs.json key, e.g. a whole new reference with title/page/
license/length_mm) rather than editing refs.json.
    rear    [x, y]  rearmost point of the weapon (butt plate); with length_mm it sets the scale
    or mm_per_px    instead of rear/length_mm
    crop    [x0, y0, x1, y1]   optional source crop (e.g. one rifle of a two-view photo); points stay in full-image px
    k       px per mm in the rectified image (default: 2400 / length, max 4)
    bg      'auto' | 'white'   segmentation hint
Written files live in tools/blender/weapons/ref/ (git-ignored; re-create them with fetch + rect).
"""
import io
import json
import math
import os
import sys
import urllib.parse
import urllib.error
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, 'ref')
SRC = os.path.join(REF, 'src')
REFS = os.path.join(HERE, 'refs.json')
CAL = os.path.join(HERE, 'cal')
UA = {'User-Agent': 'LabinStrikeRefTool/1.0 (weapon modelling references)'}


def load_refs():
    """refs.json, with per-reference overrides/additions from cal/<id>.json (any refs.json keys; lets several people
    calibrate different references at once without touching the shared file)."""
    refs = json.load(open(REFS))
    if os.path.isdir(CAL):
        for f in sorted(os.listdir(CAL)):
            if f.endswith('.json'):
                refs.setdefault(f[:-5], {}).update(json.load(open(os.path.join(CAL, f))))
    return refs


def save_refs(refs):
    """writes refs.json back without the cal/ overrides."""
    base = json.load(open(REFS))
    for rid, r in refs.items():
        if os.path.exists(os.path.join(CAL, rid + '.json')):
            continue
        base[rid] = r
    json.dump(base, open(REFS, 'w'), indent=1, ensure_ascii=False)


def font(size):
    for p in ('/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Helvetica.ttc',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def src_path(rid):
    for ext in ('.jpg', '.png'):
        p = os.path.join(SRC, rid + ext)
        if os.path.exists(p):
            return p
    raise SystemExit(f'{rid}: not fetched yet (reftool.py fetch {rid})')


# ------------------------------------------------------------------ fetch

def _get(url, tries=6):
    import time
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == tries - 1:
                raise
            time.sleep(20 * (i + 1))


def fetch(ids):
    import time
    os.makedirs(SRC, exist_ok=True)
    refs = load_refs()
    for rid in ids or refs:
        r = refs[rid]
        if not ids and os.path.exists(os.path.join(SRC, rid + '.jpg')):
            continue
        time.sleep(8)
        url = ('https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo'
               '&iiprop=url|size|extmetadata&iiurlwidth=1920&titles=' + urllib.parse.quote(r['title']))
        d = json.loads(_get(url))
        ii = next(iter(d['query']['pages'].values()))['imageinfo'][0]
        src = ii['thumburl']   # standard thumbnail step (Wikimedia throttles originals)
        data = _get(src)
        im = Image.open(io.BytesIO(data))
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA')
            bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
            bg.alpha_composite(im)
            im = bg
        im = im.convert('RGB')
        im.save(os.path.join(SRC, rid + '.jpg'), quality=93)
        r['artist'] = ii['extmetadata'].get('Artist', {}).get('value', '')[:300]
        r['license'] = ii['extmetadata'].get('LicenseShortName', {}).get('value', r.get('license'))
        print(rid, im.size)
    save_refs(refs)


def pixgrid(rid):
    im = Image.open(src_path(rid)).convert('RGB')
    w, h = im.size
    dr = ImageDraw.Draw(im)
    step = 100 if max(w, h) <= 3200 else 200
    f = font(max(14, w // 120))
    for x in range(0, w, step // 2):
        major = x % step == 0
        dr.line((x, 0, x, h), fill=(255, 0, 0) if major else (255, 170, 170), width=2 if major else 1)
        if major:
            dr.text((x + 3, 3), str(x), fill=(200, 0, 0), font=f)
            dr.text((x + 3, h - f.size - 6), str(x), fill=(200, 0, 0), font=f)
    for y in range(0, h, step // 2):
        major = y % step == 0
        dr.line((0, y, w, y), fill=(0, 0, 255) if major else (170, 170, 255), width=2 if major else 1)
        if major:
            dr.text((3, y + 3), str(y), fill=(0, 0, 200), font=f)
            dr.text((w - 5 * f.size // 2 - 6, y + 3), str(y), fill=(0, 0, 200), font=f)
    os.makedirs(REF, exist_ok=True)
    out = os.path.join(REF, rid + '_pixgrid.jpg')
    im.save(out, quality=85)
    print(out, im.size)


# ------------------------------------------------------------------ calibration -> affine (source px -> model mm)

def calib(r):
    c = r['cal']
    if not c:
        raise SystemExit('no "cal" in refs.json')
    m = np.array(c['muzzle'], float)
    a = np.array(c['axis'], float)
    d = (m - a) / np.linalg.norm(m - a)          # unit vector toward the muzzle (source px)
    n = np.array([d[1], -d[0]])                 # perpendicular
    # "up" in model space must be up in the photo (negative image y), whatever the axis direction
    if n[1] > 0:
        n = -n
    if 'mm_per_px' in c:
        s = c['mm_per_px']
    else:
        rear = np.array(c['rear'], float)
        s = r['length_mm'] / abs(np.dot(m - rear, d))
    o = np.array(c['origin'], float)
    t0 = np.dot(o - m, d)                       # origin position along the axis (px, negative = behind muzzle)
    # model u of a pixel p: (dot(p - m, d) - t0) * s ; v: dot(p - m, n) * s
    return m, d, n, s, t0


def to_model(r, pts):
    m, d, n, s, t0 = calib(r)
    p = np.asarray(pts, float) - m
    return np.stack([(p @ d - t0) * s, (p @ n) * s], -1)


def segment(img, hint='auto'):
    """foreground mask (uint8 0/255) of a weapon photographed on a plain background."""
    import cv2
    a = np.asarray(img).astype(np.float32)
    h, w = a.shape[:2]
    border = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3), a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    bgc = np.median(border, 0)
    dist = np.linalg.norm(a - bgc, axis=-1)
    hsv = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2HSV).astype(np.float32)
    val = hsv[..., 2]
    sat = hsv[..., 1]
    # cal "bg": "grey" = greyscale cut-out without shadows (every pixel is neutral, so the shadow tests below
    # would delete the weapon itself); any other value keeps the default behaviour
    grey = hint == 'grey'
    # soft drop shadows: dark-ish but unsaturated and close to the background hue -> not foreground
    fg = (dist > 48) if grey else (dist > 48) & ~((sat < 40) & (val > 0.62 * 255) & (dist < 110))
    # synthetic drop shadows (the "noBG" cut-outs): exactly neutral grey and smooth -> background
    chroma = a.max(-1) - a.min(-1)
    g = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY).astype(np.float32)
    mu = cv2.blur(g, (5, 5))
    sd = np.sqrt(np.maximum(cv2.blur(g * g, (5, 5)) - mu * mu, 0))
    neutral = cv2.blur((chroma <= 5).astype(np.float32), (5, 5)) > 0.5
    if not grey:
        fg &= ~(neutral & (val > 60) & (sd < 40))
    m = (fg * 255).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    nlab, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if nlab > 1:
        big = stats[1:, cv2.CC_STAT_AREA].max()
        keep = np.zeros(nlab, bool)
        keep[1:] = stats[1:, cv2.CC_STAT_AREA] > 0.02 * big
        m = (keep[lab] * 255).astype(np.uint8)
    # fill holes (trigger guard openings stay open: only fill holes smaller than ~0.05% of the image)
    inv = 255 - m
    nlab, lab, stats, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, nlab):
        x, y, ww, hh, area = stats[i]
        if x > 0 and y > 0 and x + ww < w and y + hh < h:
            # small holes, and enclosed holes that are not bright background (bare metal removed as "neutral")
            # real openings (trigger guards) show background or its neutral drop shadow; holes of tinted pixels
            # are bare metal the background test rejected
            sel = lab == i
            if os.environ.get('HOLEDBG') and area > 0.0005 * h * w:
                print('hole', x, y, area, round(float((chroma[sel] <= 5).mean()), 2), round(float(sd[sel].mean()), 1), round(float(np.median(sd[sel])), 1), file=sys.stderr)
            if area < 0.0005 * h * w or (chroma[sel] <= 5).mean() < 0.5 or np.median(sd[sel]) > 6.5:
                m[lab == i] = 255
    return m


def rect(rid):
    import cv2
    refs = load_refs()
    r = refs[rid]
    c = r['cal']
    img = Image.open(src_path(rid)).convert('RGB')
    W, H = img.size
    m, d, n, s, t0 = calib(r)
    L = r['length_mm'] or 1000
    k = c.get('k') or min(4.0, round(2400.0 / L, 2))
    # model-space bounds: from the segmented weapon (inside the optional crop)
    crop = c.get('crop') or [0, 0, W, H]
    sub = img.crop(crop)
    mask_full = np.zeros((H, W), np.uint8)
    mask_full[crop[1]:crop[3], crop[0]:crop[2]] = segment(sub, c.get('bg', 'auto'))
    ys, xs = np.nonzero(mask_full)
    uv = to_model(r, np.stack([xs, ys], -1)[::17])
    u0, v0 = uv.min(0) - 25
    u1, v1 = uv.max(0) + 25
    u0, u1 = math.floor(u0 / 10) * 10, math.ceil(u1 / 10) * 10
    v0, v1 = math.floor(v0 / 10) * 10, math.ceil(v1 / 10) * 10
    ow, oh = int(round((u1 - u0) * k)), int(round((v1 - v0) * k))
    # output pixel (X, Y) -> model (u, v) = (u0 + X/k, v1 - Y/k) -> source pixel p = m + d*(u/s + t0) + n*(v/s)
    # p = A @ [X, Y, 1]
    du = d / (s * k)
    dv = -n / (s * k)
    base = m + d * (u0 / s + t0) + n * (v1 / s)
    A = np.array([[du[0], dv[0], base[0]], [du[1], dv[1], base[1]]], np.float32)
    src = np.asarray(img)
    out = cv2.warpAffine(src, A, (ow, oh), flags=cv2.INTER_AREA | cv2.WARP_INVERSE_MAP, borderValue=(255, 255, 255))
    mk = cv2.warpAffine(mask_full, A, (ow, oh), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=0)
    mk = ((mk > 127) * 255).astype(np.uint8)
    os.makedirs(REF, exist_ok=True)
    Image.fromarray(out).save(os.path.join(REF, rid + '_rect.png'))
    Image.fromarray(mk).save(os.path.join(REF, rid + '_mask.png'))
    meta = dict(u0=u0, u1=u1, v0=v0, v1=v1, k=k, w=ow, h=oh)
    json.dump(meta, open(os.path.join(REF, rid + '_rect.json'), 'w'))
    grid_image(rid, out, meta, os.path.join(REF, rid + '_grid.jpg'))
    tr = os.path.join(HERE, 'traces', rid + '.json')     # traced outlines depend on the mask
    if os.path.exists(tr):
        os.remove(tr)
    print(rid, meta)


def grid_image(rid, arr, meta, path, minor=10, major=50, label=True):
    im = Image.fromarray(arr).convert('RGB')
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    k, u0, u1, v0, v1 = meta['k'], meta['u0'], meta['u1'], meta['v0'], meta['v1']
    f = font(max(11, int(min(28, 5 * k * major / 50))))
    X = lambda u: (u - u0) * k
    Y = lambda v: (v1 - v) * k
    u = math.ceil(u0 / minor) * minor
    while u <= u1:
        mj = abs(u % major) < 1e-6
        col = (255, 0, 0, 255) if u == 0 else ((220, 40, 40, 170) if mj else (230, 120, 120, 70))
        dr.line((X(u), 0, X(u), im.size[1]), fill=col, width=2 if (mj or u == 0) else 1)
        if mj and label:
            dr.text((X(u) + 2, 2), f'{u:g}', fill=(200, 0, 0, 255), font=f)
            dr.text((X(u) + 2, im.size[1] - f.size - 4), f'{u:g}', fill=(200, 0, 0, 255), font=f)
        u += minor
    v = math.ceil(v0 / minor) * minor
    while v <= v1:
        mj = abs(v % major) < 1e-6
        col = (0, 0, 255, 255) if v == 0 else ((40, 40, 220, 170) if mj else (120, 120, 230, 70))
        dr.line((0, Y(v), im.size[0], Y(v)), fill=col, width=2 if (mj or v == 0) else 1)
        if mj and label:
            dr.text((2, Y(v) + 1), f'{v:g}', fill=(0, 0, 200, 255), font=f)
        v += minor
    im = Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB')
    im.save(path, quality=88)
    return path


def rect_meta(rid):
    return json.load(open(os.path.join(REF, rid + '_rect.json')))


def crop(rid, u0, u1, v0, v1, ppm=None):
    meta = rect_meta(rid)
    k = meta['k']
    im = np.asarray(Image.open(os.path.join(REF, rid + '_rect.png')).convert('RGB'))
    X0, X1 = int((u0 - meta['u0']) * k), int((u1 - meta['u0']) * k)
    Y0, Y1 = int((meta['v1'] - v1) * k), int((meta['v1'] - v0) * k)
    sub = Image.fromarray(im[max(0, Y0):Y1, max(0, X0):X1])
    ppm = ppm or max(k, min(12.0, 1600.0 / max(1, u1 - u0)))
    sub = sub.resize((max(1, int((u1 - u0) * ppm)), max(1, int((v1 - v0) * ppm))), Image.LANCZOS)
    span = max(u1 - u0, v1 - v0)
    minor, major = (1, 5) if span <= 60 else ((2, 10) if span <= 160 else (5, 25))
    m2 = dict(u0=u0, u1=u1, v0=v0, v1=v1, k=ppm)
    path = os.path.join(REF, f'{rid}_crop_{u0:g}_{u1:g}_{v0:g}_{v1:g}.jpg')
    grid_image(rid, np.asarray(sub), m2, path, minor=minor, major=major)
    print(path)


def profile(rid, u0, u1, step=5.0):
    meta = rect_meta(rid)
    k = meta['k']
    mk = np.asarray(Image.open(os.path.join(REF, rid + '_mask.png'))) > 127
    u = u0
    while u <= u1 + 1e-6:
        X = int((u - meta['u0']) * k)
        if 0 <= X < mk.shape[1]:
            col = np.nonzero(mk[:, X])[0]
            if len(col):
                # runs of foreground (top to bottom) -> v intervals
                runs = []
                start = col[0]
                prev = col[0]
                for y in col[1:]:
                    if y != prev + 1:
                        runs.append((start, prev))
                        start = y
                    prev = y
                runs.append((start, prev))
                iv = ' '.join(f'[{meta["v1"] - b / k:.1f},{meta["v1"] - a / k:.1f}]' for a, b in runs)
                print(f'u={u:7.1f}  {iv}')
            else:
                print(f'u={u:7.1f}  -')
        u += step


def trace(rid, opts):
    """outlines of the reference mask clipped to opts['region'] (polygon in model mm, optional), as JSON:
    [{"outer": [[u, v], ...], "holes": [[[u, v], ...], ...], "area": mm2}, ...] largest first, outer CCW, holes CW.
    opts: eps (simplification, mm, default 0.3), blur (mask smoothing, mm, default 0.6), min_area (mm2, default 20),
    min_hole (mm2, default 12), fill_holes (bool)."""
    import cv2
    meta = rect_meta(rid)
    k = meta['k']
    mk = (np.asarray(Image.open(os.path.join(REF, rid + '_mask.png'))) > 127).astype(np.uint8) * 255
    blur = opts.get('blur', 0.6) * k
    if blur > 0.5:
        r = int(math.ceil(blur * 2)) * 2 + 1
        mk = ((cv2.GaussianBlur(mk, (r, r), blur) > 127) * 255).astype(np.uint8)
    reg = opts.get('region')
    if reg:
        rm = np.zeros_like(mk)
        pts = np.array([[(u - meta['u0']) * k, (meta['v1'] - v) * k] for u, v in reg], np.float32)
        cv2.fillPoly(rm, [np.round(pts * 16).astype(np.int32)], 255, lineType=cv2.LINE_8, shift=4)
        mk = mk & rm
    cs, hier = cv2.findContours(mk, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return []
    hier = hier[0]
    eps = opts.get('eps', 0.3) * k
    to_mm = lambda c: [[round(meta['u0'] + (x + 0.5) / k, 2), round(meta['v1'] - (y + 0.5) / k, 2)] for x, y in c.reshape(-1, 2)]

    def area(p):
        a = np.asarray(p)
        return 0.5 * float(np.dot(a[:, 0], np.roll(a[:, 1], -1)) - np.dot(np.roll(a[:, 0], -1), a[:, 1]))

    out = []
    for i, c in enumerate(cs):
        if hier[i][3] != -1:
            continue
        outer = to_mm(cv2.approxPolyDP(c, eps, True))
        A = area(outer)
        if abs(A) < opts.get('min_area', 20):
            continue
        if A < 0:
            outer.reverse()
        holes = []
        j = hier[i][2]
        while j != -1 and not opts.get('fill_holes'):
            h = to_mm(cv2.approxPolyDP(cs[j], eps, True))
            ha = area(h)
            if abs(ha) >= opts.get('min_hole', 12) and len(h) >= 3:
                if ha > 0:
                    h.reverse()
                holes.append(h)
            j = hier[j][0]
        out.append(dict(outer=outer, holes=holes, area=round(abs(A), 1)))
    out.sort(key=lambda o: -o['area'])
    return out


def compare(rid):
    """ref/<id>_render.png must be rendered by weapons.compare.render (same u/v window and k as the rect image)."""
    import cv2
    meta = rect_meta(rid)
    ref = np.asarray(Image.open(os.path.join(REF, rid + '_rect.png')).convert('RGB')).astype(np.float32)
    mk = np.asarray(Image.open(os.path.join(REF, rid + '_mask.png'))) > 127
    ren = Image.open(os.path.join(REF, rid + '_render.png')).convert('RGBA')
    if ren.size != (meta['w'], meta['h']):
        ren = ren.resize((meta['w'], meta['h']), Image.LANCZOS)
    ren = np.asarray(ren).astype(np.float32)
    ma = ren[..., 3] > 127
    inter = (ma & mk).sum()
    union = (ma | mk).sum()
    iou = inter / max(1, union)
    # 1) model silhouette outline (red) + ref mask outline (cyan) over the photo
    out = ref.copy()
    k3 = np.ones((3, 3), np.uint8)
    e_model = cv2.morphologyEx(ma.astype(np.uint8), cv2.MORPH_GRADIENT, k3) > 0
    e_ref = cv2.morphologyEx(mk.astype(np.uint8), cv2.MORPH_GRADIENT, k3) > 0
    out[e_ref] = (0, 200, 255)
    out[e_model] = (255, 0, 0)
    a = Image.fromarray(out.astype(np.uint8))
    p1 = os.path.join(REF, rid + '_cmp_outline.jpg')
    grid_image(rid, np.asarray(a), meta, p1, minor=10, major=50)
    # 2) 50 % blend of the shaded render over the photo
    alpha = ren[..., 3:4] / 255.0 * 0.55
    blend = ref * (1 - alpha) + ren[..., :3] * alpha
    p2 = os.path.join(REF, rid + '_cmp_blend.jpg')
    Image.fromarray(blend.astype(np.uint8)).save(p2, quality=88)
    # 3) photo above, render (on white) below
    white = ref * 0 + 255
    rr = white * (1 - ren[..., 3:4] / 255.0) + ren[..., :3] * (ren[..., 3:4] / 255.0)
    stack = np.concatenate([ref, rr], 0).astype(np.uint8)
    p3 = os.path.join(REF, rid + '_cmp_stack.jpg')
    Image.fromarray(stack).save(p3, quality=88)
    # where are the biggest differences? (mm of silhouette mismatch per 25 mm band along u)
    k = meta['k']
    diff = (ma ^ mk)
    bands = []
    for X0 in range(0, meta['w'], int(25 * k)):
        cols = diff[:, X0:X0 + int(25 * k)]
        bands.append((meta['u0'] + X0 / k, cols.sum() / (k * k)))
    worst = sorted(bands, key=lambda b: -b[1])[:6]
    print(f'{rid}: IoU {iou:.3f}')
    print('largest mismatch (u band start mm, area mm2):', ', '.join(f'{u:.0f}:{a:.0f}' for u, a in worst))
    print(p1)
    print(p2)
    print(p3)


if __name__ == '__main__':
    cmd, *args = sys.argv[1:]
    if cmd == 'fetch':
        fetch(args)
    elif cmd == 'pixgrid':
        pixgrid(args[0])
    elif cmd == 'rect':
        for a in args:
            rect(a)
    elif cmd == 'crop':
        crop(args[0], *map(float, args[1:6]))
    elif cmd == 'profile':
        profile(args[0], float(args[1]), float(args[2]), float(args[3]) if len(args) > 3 else 5.0)
    elif cmd == 'compare':
        compare(args[0])
    elif cmd == 'trace':
        print(json.dumps(trace(args[0], json.loads(args[1]) if len(args) > 1 else {})))
    else:
        raise SystemExit(__doc__)
