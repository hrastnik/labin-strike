"""Parts both bikes share: spoked wheels, and the material palette."""
import math

from mathutils import Vector

from .lib import TAU, material, rrect


def materials(prefix, paint):
    """the bike's materials, keyed for Bike.M; names are prefixed so each bike can be darkened alone when wrecked."""
    p = prefix + '_'
    return {
        'paint': material(p + 'paint', paint, 0.62),
        'paint_dark': material(p + 'paint_dark', tuple(c * 0.55 for c in paint), 0.6),
        'black': material(p + 'black', (22, 22, 21), 0.55, 0.2),
        'iron': material(p + 'iron', (38, 38, 37), 0.6, 0.55),          # cast iron barrels, black enamel
        'alu': material(p + 'alu', (176, 174, 166), 0.42, 0.85),        # cast aluminium cases and heads
        'steel': material(p + 'steel', (130, 130, 126), 0.35, 0.9),     # bright bare steel: rods, bolts
        'chrome': material(p + 'chrome', (205, 205, 200), 0.18, 1.0),
        'rubber': material(p + 'rubber', (20, 20, 20), 0.9),
        'tan': material(p + 'tan', (116, 82, 56), 0.6),                # russet leather
        'leather': material(p + 'leather', (32, 27, 24), 0.55),         # black leather
        'lens': material(p + 'lens', (236, 230, 205), 0.08, 0.0, emit=(255, 238, 190), emit_strength=0.8),
        'red': material(p + 'red', (150, 14, 12), 0.25, 0.0, emit=(160, 10, 8), emit_strength=0.3),
        'white': material(p + 'white', (222, 220, 210), 0.6),
        'blue': material(p + 'blue', (30, 90, 170), 0.35),
        'brass': material(p + 'brass', (176, 140, 70), 0.35, 0.9),
        'glass': material(p + 'glass', (200, 205, 200), 0.1, 0.6),
    }


def tire(bk, part, r, w, h, mat, cells=44, tread=0.006, rows=None):
    """tyre about the x axis at the part's origin: outer radius r, section w wide and h tall, block tread."""
    rc = r - h / 2
    # section: from the bead on the right, over the crown, to the bead on the left (angle about the section centre)
    sec = []
    n = 16
    for k in range(n + 1):
        a = -math.pi * 0.62 + (math.pi * 1.24) * k / n  # -112..112 deg from the crown
        sec.append((rc + h / 2 * math.cos(a) * 1.0, w / 2 * math.sin(a), abs(a) < 0.62))
    crown = [j for j, s in enumerate(sec) if s[2]]
    verts, faces = [], []
    seg = cells * 2
    m = len(sec)
    for i in range(seg):
        cell, half = divmod(i, 2)
        a = TAU * (cell + (0.18 if half == 0 else 0.82)) / cells
        for j, (rr, x, on) in enumerate(sec):
            d = 0.0
            if on:
                # staggered blocks: two rows each side of the centre groove
                row = 0 if abs(x) < w * 0.16 else 1
                block = (cell + row) % 2 == 0 or row == 0 and abs(x) > w * 0.04
                d = tread if block else 0.0
                if abs(x) < w * 0.035:
                    d = 0.0
            verts.append(Vector((x, (rr + d) * math.sin(a), (rr + d) * math.cos(a))))
    for i in range(seg):
        i2 = (i + 1) % seg
        for j in range(m - 1):
            faces.append((i * m + j, i * m + j + 1, i2 * m + j + 1, i2 * m + j))
    bk.add(verts, faces, mat, True, part)


def wheel(bk, part, r, spec, mats, static=None):
    """spoked wheel about the x axis at the part's origin. spec: rim_r, rim_w, tire_w, tire_h, hub_r, hub_w, drum_r,
    spokes, flange_r, flange_x, drum_side (+1 right / -1 left). static: the part for the brake plate (non-rotating)
    and its origin offset."""
    rim_r = spec['rim_r']
    bk.parts[part].local = True
    tire(bk, part, r, spec['tire_w'], spec['tire_h'], mats['rubber'])
    # drop-centre rim, painted
    rw = spec['rim_w'] / 2
    prof = [(rim_r - 0.004, -rw - 0.002), (rim_r + 0.012, -rw - 0.003), (rim_r + 0.014, -rw + 0.006),
            (rim_r + 0.004, -rw + 0.01), (rim_r - 0.012, -rw * 0.35), (rim_r - 0.014, 0.0),
            (rim_r - 0.012, rw * 0.35), (rim_r + 0.004, rw - 0.01), (rim_r + 0.014, rw - 0.006),
            (rim_r + 0.012, rw + 0.003), (rim_r - 0.004, rw + 0.002), (rim_r - 0.016, 0.0), (rim_r - 0.004, -rw - 0.002)]
    bk.lathe(prof, (0, 0, 0), (1, 0, 0), mats['rim'], seg=64, part=part)
    # hub: barrel with flanges, the brake drum on one side
    hr, hw = spec['hub_r'], spec['hub_w']
    ds = spec.get('drum_side', -1)
    fx = spec['flange_x']
    fr = spec['flange_r']
    dr = spec['drum_r']
    prof = [(0.012, -hw / 2 - 0.02), (0.02, -hw / 2 - 0.02), (0.022, -hw / 2), (fr, -fx - 0.004), (fr, -fx + 0.004),
            (hr, -fx + 0.012), (hr, fx - 0.012), (fr, fx - 0.004), (fr, fx + 0.004), (0.022, hw / 2),
            (0.02, hw / 2 + 0.02), (0.012, hw / 2 + 0.02)]
    bk.lathe(prof, (0, 0, 0), (1, 0, 0), mats['hub'], seg=20, part=part)
    # drum: a wide shallow can on the brake side, finned edge
    x0 = ds * (fx + 0.006)
    x1 = ds * (fx + 0.045)
    prof = [(hr, 0.0), (dr - 0.004, 0.004), (dr, 0.01), (dr + 0.004, 0.014), (dr + 0.004, 0.02), (dr, 0.024),
            (dr, 0.034), (dr - 0.006, 0.039)]
    bk.lathe([(rr, t * ds) for rr, t in prof], (x0, 0, 0), (1, 0, 0), mats['hub'], seg=28, part=part)
    # spokes: 40, tangentially laced, alternating flanges
    n = spec.get('spokes', 40)
    cross = spec.get('cross', 0.62)
    sp = mats['spoke']
    for k in range(n):
        side = 1 if k % 2 == 0 else -1
        lead = 1 if (k // 2) % 2 == 0 else -1
        a_rim = TAU * k / n
        a_hub = a_rim + lead * cross
        hx = side * fx if not (side == ds) else side * fx
        h = Vector((hx, fr * 0.92 * math.sin(a_hub), fr * 0.92 * math.cos(a_hub)))
        q = Vector((side * 0.006, (rim_r - 0.014) * math.sin(a_rim), (rim_r - 0.014) * math.cos(a_rim)))
        bk.tube([h, q], spec.get('spoke_r', 0.0022), sp, seg=4, caps=False, part=part)
        # nipple
        bk.cyl(q, q + (h - q).normalized() * 0.012, 0.0035, sp, seg=5, part=part, caps=False)
    if static:
        sp_part, off = static
        # brake backing plate: stays with the fork / frame
        off = Vector(off)
        xs = ds * (fx + 0.05)
        prof = [(0.02, 0.0), (dr - 0.01, 0.002), (dr - 0.004, 0.006), (dr - 0.004, 0.012), (0.03, 0.018), (0.016, 0.03)]
        bk.lathe([(rr, t * ds) for rr, t in prof], off + Vector((xs - ds * 0.012, 0, 0)), (1, 0, 0), mats['hub'], seg=24,
                 part=sp_part)
        # axle nuts both sides
        for s in (1, -1):
            bk.lathe([(0.0, 0), (0.014, 0), (0.014, 0.012 * s), (0.008, 0.02 * s), (0.0, 0.02 * s)],
                     off + Vector((s * (hw / 2 + 0.03 + (0.03 if s == ds else 0)), 0, 0)), (1, 0, 0), mats['steel'], seg=6,
                     part=sp_part, smooth=False)


def xframes(n, flip=False):
    """frames for a path along x: section a = y (forward), b = z (up)."""
    s = -1 if flip else 1
    return [(Vector((0, 1 * s, 0)), Vector((0, 0, 1)))] * n


def yframes(n):
    """frames for a path along y: section a = x, b = z."""
    return [(Vector((1, 0, 0)), Vector((0, 0, 1)))] * n


def seg_poly(a, b, w):
    """side-view polygon of a bar from a to b, w wide."""
    d = (b - a)
    d = Vector((d.y, d.z)).normalized()
    nrm = Vector((-d.y, d.x)) * w / 2
    A, B = Vector((a.y, a.z)), Vector((b.y, b.z))
    return [tuple(A + nrm - d * w / 2), tuple(B + nrm + d * w / 2), tuple(B - nrm + d * w / 2), tuple(A - nrm - d * w / 2)]


def flatbar(bk, a, b, w, t, mat):
    """bar of section w (in the side plane) by t (across), tapering a little to b."""
    path = [a, b]
    secs = [rrect(t, w, t * 0.35, 2), rrect(t * 0.9, w * 0.75, t * 0.3, 2)]
    d = (b - a).normalized()
    side = Vector((1, 0, 0))
    frames = [(side, side.cross(d).normalized())] * 2
    bk.sweep(path, secs, mat, cap0=True, cap1=True, frames=frames)


def fender(bk, c, r, w, a0, a1, mat, depth=0.05, part=None, n=28):
    """open fender arc about the axle c, from angle a0 to a1 (0 = forward, pi/2 = up), U section w wide with
    valances `depth` deep, a rolled edge."""
    path, secs = [], []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        path.append(c + Vector((0, math.cos(a) * r, math.sin(a) * r)))
    # section in (x, outward): from the inner edge of the right valance, over the crown, to the left one
    sec = []
    hw = w / 2
    for k in range(9):
        t = k / 8
        ang = math.pi * (1 - t)
        sec.append((hw * math.cos(ang), depth * 0.15 * math.sin(ang)))
    sec = [(hw + 0.004, -depth), (hw, -depth + 0.004)] + [(x, y) for x, y in reversed(sec)] + [(-hw, -depth + 0.004), (-hw - 0.004, -depth)]
    # outer skin then the inner skin (offset inwards), joined at the edges: a thin shell
    m = len(sec)
    inner = [(x * 0.97, y - 0.004) for x, y in sec]
    ring = sec + list(reversed(inner))
    frames = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        out = Vector((0, math.cos(a), math.sin(a)))
        frames.append((Vector((1, 0, 0)), out))
    bk.sweep(path, [ring] * (n + 1), mat, closed_sec=True, part=part, frames=frames)


def project(bk, pts, d, off=0.0015):
    """points moved along d onto the current part's surface (from outside), lifted off it by off."""
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromBMesh(bk.cur.bm)
    d = Vector(d).normalized()
    out = []
    for p in pts:
        p = Vector(p)
        hit = tree.ray_cast(p - d * 0.5, d, 1.0)
        out.append(hit[0] - d * off if hit[0] is not None else p)
    return out


def star(bk, c, s, r, mat, ring=True):
    """five-pointed star (in a ring) on the flank, s: +1 right side, -1 left, projected onto the surface."""
    c = Vector(c)
    d = Vector((-s, 0, 0))

    def at(y, z):
        return c + Vector((0, y, z))
    pts = [at(0, 0)]
    for i in range(10):
        a = math.pi / 2 + TAU * i / 10
        k = r * (1 if i % 2 == 0 else 0.4)
        pts.append(at(math.cos(a) * k, math.sin(a) * k))
    pts = project(bk, pts, d)
    faces = [(0, 1 + i, 1 + (i + 1) % 10) if s > 0 else (0, 1 + (i + 1) % 10, 1 + i) for i in range(10)]
    bk.add(pts, faces, mat, False, keep=True)
    if not ring:
        return
    pts = []
    for i in range(36):
        a = TAU * i / 36
        for rr in (r * 1.1, r * 1.22):
            pts.append(at(math.cos(a) * rr, math.sin(a) * rr))
    pts = project(bk, pts, d)
    faces = []
    for i in range(36):
        j = (i + 1) % 36
        f = (2 * i, 2 * i + 1, 2 * j + 1, 2 * j)
        faces.append(f if s > 0 else tuple(reversed(f)))
    bk.add(pts, faces, mat, False, keep=True)
