"""StG 44 (MP 44). Reference: Sturmgewehr44 noBG(1).jpg (right side). 940 mm, stamped receiver, wooden stock,
bakelite grip panels, 30-round curved magazine."""
import math

import numpy as np

from ..lib import arc, hull_circles, rrect, section

REF = 'stg44'
META = {'kind': 'rifle', 'client': {'magDir': [0, -0.97, -0.26]}}   # magazine drops along its forward rake

BORE_V = -1.0      # the barrel sits ~1 mm under the calibrated axis in this photo


def mag_edges(outline, origin, axis_deg, t0, t1, step=4):
    """front/back edges of a swept part (axis through origin at axis_deg), as smooth quadratic fits of the traced
    outline's crossings at stations t along the axis -> (T, lo, hi, to_uv)."""
    a = math.radians(axis_deg)
    du, dv = math.cos(a), math.sin(a)          # along the axis
    nu, nv = -dv, du                           # across
    loc = [((p[0] - origin[0]) * du + (p[1] - origin[1]) * dv, (p[0] - origin[0]) * nu + (p[1] - origin[1]) * nv)
           for p in outline]
    ts, los, his = [], [], []
    t = t0
    while t <= t1:
        xs = []
        for i in range(len(loc)):
            (s0, n0), (s1, n1) = loc[i - 1], loc[i]
            if (s0 - t) * (s1 - t) < 0:
                xs.append(n0 + (n1 - n0) * (t - s0) / (s1 - s0))
        if len(xs) >= 2:
            ts.append(t)
            los.append(min(xs))
            his.append(max(xs))
        t += step
    T = np.array(ts)
    # fit on the clean middle (the ends catch the housing lip / the floor plate), extrapolate to the ends
    m = (T > T[0] + 30) & (T < T[-1] - 15)
    lo = np.polyval(np.polyfit(T[m], np.array(los)[m], 2), T)
    hi = np.polyval(np.polyfit(T[m], np.array(his)[m], 2), T)

    def to_uv(t, n):
        return (origin[0] + du * t + nu * n, origin[1] + dv * t + nv * n)
    return T, lo, hi, to_uv


def build(g):
    # ---------------------------------------------------------------- stock
    stock = g.outline([(-368, -200), (-171, -200), (-171, 60), (-368, 60)])
    st = g.sweep(stock, 'beech', width=[(-368, 42), (-260, 40), (-171, 35)], radius=(9, 7), top=0.88, step=4,
            round_ends=(0, 0), name='stock')
    # sling slot: shallow dish on both sides with a slot through
    dish = rrect(-333, -283, -66, -27, 15)
    c1 = g.extrude(dish, 16.5, 30, 'beech', cutter=True, bevel=0)
    c2 = g.extrude(dish, -30, -16.5, 'beech', cutter=True, bevel=0)
    c3 = g.extrude(rrect(-315, -302, -61, -34, 6), -30, 30, 'beech', cutter=True, bevel=0)
    g.cut(st, c1, c2, c3)
    butt = g.outline([(-385, -200), (-366, -200), (-366, 60), (-385, 60)])
    g.sweep(butt, 'phosphate', width=43, radius=(9, 7), top=0.88, step=2, name='buttplate')
    cap = g.outline([(-176, -60), (-143, -60), (-143, 60), (-176, 60)])
    g.sweep(cap, 'paint', width=[(-176, 35.5), (-143, 34)], radius=(9, 6), step=3, name='stockcap')

    # ---------------------------------------------------------------- receiver
    ring = section(35, 35, 69, 10, 4, 4, y0=-33.5)
    g.extrude(ring, -146, -128, 'bright', plane='front', bevel=0.8, name='ring')
    endcap = section(33, 33, 59, 9, 3, 4, y0=-25)
    g.extrude(endcap, -129, -95, 'bright', plane='front', bevel=0.6, name='endcap')
    g.lathe([(16.5, 0), (16.5, 5), (18, 4.5), (18.6, 2.5), (18.8, 0)], 'bright', axis='w', at=(-101, -13), seg=16)
    rec = section(31, 31, 58.5, 9, 2.5, 4, y0=-24)
    recv = g.extrude(rec, -96, 196, 'phosphate', plane='front', bevel=0.6, name='receiver')
    # raised dust-cover strip on the right side, rivets
    g.extrude(rrect(-78, 48, -3, 8, 5), 15, 16.6, 'phosphate', bevel=0.4, name='cover')
    for u, v in ((-70, -14), (-38, -14), (-20, -32), (8, -35), (40, -35), (66, -12), (96, -24), (155, -6)):
        g.lathe([(15.4, 0), (15.4, 2.4), (16.6, 2.0), (17.0, 0)], 'phosphate', axis='w', at=(u, v), seg=10)
        g.lathe([(-15.4, 0), (-15.4, 2.4), (-16.6, 2.0), (-17.0, 0)], 'phosphate', axis='w', at=(u, v), seg=10)

    # ---------------------------------------------------------------- lower receiver, grip, guard, trigger
    lower = g.outline([(-90, -18), (57, -18), (57, -58), (40, -58), (-30, -54), (-36, -48), (-90, -48)])
    g.extrude(lower, width=27, mat='phosphate', bevel=1.0, name='housing')
    well = g.outline([(56, -18), (152, -18), (152, -60), (56, -60)])
    g.extrude(well, width=31, mat='phosphate', bevel=1.0, name='magwell')
    g.lathe([(15.5, 0), (15.5, 7), (17.5, 6.5), (18.3, 0)], 'phosphate', axis='w', at=(76, -38), seg=20)  # mag release
    g.lathe([(15.5, 0), (15.5, 2.6), (17.3, 2.2), (17.6, 0)], 'phosphate', axis='w', at=(76, -38), seg=12)
    # pins and rivets of the trigger housing / magazine housing (both sides)
    for u, v, r in ((-62, -20, 2.4), (-28, -46, 2.2), (-1, -41, 2.6), (35, -32, 2.4), (14, -24, 2.0),
                    (68, -55, 3.2), (63, -22, 2.2), (82, -17, 2.0)):
        for sgn in (1, -1):
            w0 = 13.5 if v < -18 else 15.5
            g.lathe([(sgn * w0, 0), (sgn * w0, r), (sgn * (w0 + 1.0), r * 0.85), (sgn * (w0 + 1.3), 0)],
                    'phosphate', axis='w', at=(u, v), seg=10)
    # selector button (pushed through the housing, sticks out on both sides)
    g.lathe([(-17.5, 0), (-17.5, 5.5), (17.5, 5.5), (17.5, 0)], 'blued', axis='w', at=(-47, -21), seg=18)
    # ejection-port cover groove on the right
    g.cut(recv, g.extrude(rrect(108, 165, -8, -3, 2.4), 14.6, 20, cutter=True, bevel=0))
    guard, holes = g.outline([(-36, -50), (42, -50), (42, -102), (-50, -102)], holes=True)
    g.extrude(guard, width=10, mat='phosphate', holes=holes, bevel=1.2, name='guard')
    trig = [(-5, -50), (2, -50), (3, -58), (4.5, -67), (4, -76), (1.5, -84, 1), (-0.5, -85), (-1.5, -82),
            (-1, -74), (-1.5, -66), (-3.5, -58)]
    g.extrude(trig, width=6, mat='blued', bevel=0.6, name='trigger')
    grip = g.outline([(-95, -44), (-36, -44), (-50, -100), (-78, -160), (-150, -160)])
    g.sweep(grip, 'phosphate', width=24, radius=6, axis=-125, origin=(-60, -48), step=3, name='gripframe')
    from ..lib import offset_poly
    panel = offset_poly(grip, -2.6)
    gp = g.sweep(panel, 'bakelite', width=30, radius=(4, 4), axis=-125, origin=(-60, -48), step=2.5, t1=118,
                 name='grippanel')
    # moulded grooves running along the grip, both panels
    grooves = []
    for k in range(-9, 10):
        n = k * 2.5
        for w0, w1 in ((14.3, 17), (-17, -14.3)):
            c = g.box(-60 + 18, -60 + 125, -48 + n - 0.45, -48 + n + 0.45, w0, w1, cutter=True, bevel=0)
            g.transform(c, rot=('w', -125), pivot=(-60, -48, 0))
            grooves.append(c)
    g.cut(gp, *grooves)
    g.lathe([(15, 0), (15, 3.2), (16.2, 2.6), (16.6, 0)], 'blued', axis='w', at=(-82, -99), seg=12)
    g.lathe([(-15, 0), (-15, 3.2), (-16.2, 2.6), (-16.6, 0)], 'blued', axis='w', at=(-82, -99), seg=12)

    # ---------------------------------------------------------------- rear sight (tangent leaf)
    base = [(98, 34), (174, 34), (174, 39, 2), (164, 46, 2), (106, 46, 2), (98, 40, 2)]
    g.extrude(base, width=24, mat='phosphate', bevel=0.8, name='sightbase')
    leaf = [(100, 45), (170, 47.5, 2), (170, 51, 1.5), (104, 52.5, 1), (100, 50)]
    g.extrude(leaf, width=15, mat='blued', bevel=0.5, name='leaf')
    notch = g.box(100, 112, 46, 58, width=16, mat='blued', bevel=0.5)
    g.cut(notch, g.extrude([(-2.4, 58.5), (2.4, 58.5), (0.7, 52), (-0.7, 52)], 96, 116, plane='front', cutter=True, bevel=0))
    g.box(140, 152, 45.5, 50.5, width=19, mat='blued', bevel=0.8)                 # slider
    g.lathe([(9.5, 0), (9.5, 3), (12, 3), (12.5, 0)], 'blued', axis='w', at=(146, 48), seg=14)

    # ---------------------------------------------------------------- gas system and barrel
    front_ring = section(31, 31, 58, 9, 6, 4, y0=-26)
    g.extrude(front_ring, 186, 204, 'phosphate', plane='front', bevel=0.8, name='frontring')
    shroud = hull_circles([(0, 19.5, 11.2), (0, -6, 15)])
    sh = g.extrude(shroud, 200, 388, 'phosphate', plane='front', bevel=0.8, name='shroud')
    holes = [g.cyl(-30, 30, 2.6, axis='w', at=(u, -6), cutter=True, seg=12) for u in (262, 287, 312, 337)]
    g.cut(sh, *holes)
    for u in range(225, 380, 30):
        g.cut(sh, g.extrude(rrect(u, u + 14, -18, -14, 2), -30, 30, cutter=True, bevel=0))
    gb = g.extrude(hull_circles([(0, 19.5, 12.5), (0, -2, 12.5)]), 386, 428, 'phosphate', plane='front', bevel=1.0,
                   name='gasblock')
    g.cut(gb, g.extrude(rrect(393, 413, 12, 22, 4), 8, 30, cutter=True, bevel=0))
    g.cyl(426, 438, 6.5, 'phosphate', at=(18, 0), seg=20)
    g.lathe([(436, 0), (436, 3), (464, 3), (465, 3.6), (467, 4.2), (469.5, 3.5), (471, 0)], 'bright', at=(22.3, 0), seg=16)
    g.lathe([(380, 0), (380, 8.5), (430, 8.0), (440, 7.0), (556, 6.8), (556, 0)], 'blued', at=(BORE_V, 0), seg=28,
            name='barrel')

    # front sight: barrel collar, pillar, hood ring, post
    g.cyl(518, 556, 9.2, 'phosphate', at=(BORE_V, 0), seg=28)
    pillar = [(520, 2), (556, 2), (552, 38, 3), (551, 46), (529, 46), (524, 38, 3)]
    g.extrude(pillar, width=11, mat='phosphate', bevel=0.8, name='pillar')
    g.tube(527, 553, 11.2, 9.6, 'phosphate', at=(52.5, 0), seg=32)
    g.box(536, 542, 40, 52, width=2.4, mat='blued', bevel=0.3)
    # muzzle nut (knurled)
    nut = g.lathe([(556, 3.5), (556, 8.6), (558, 9.6), (574, 9.6), (576, 8.6), (576, 3.5)], 'blued', at=(BORE_V, 0),
                  seg=36, closed=True, name='nut')
    knurl = [g.box(562, 580, 8.8, 11, -0.6, 0.6, cutter=True, bevel=0) for _ in range(20)]
    for i, c in enumerate(knurl):
        g.transform(c, rot=('u', i * 18), pivot=(0, BORE_V, 0))
    g.cut(nut, *knurl)
    g.tube(540, 577, 4.0, 3.2, 'blued', at=(BORE_V, 0), seg=16)        # bore

    # cocking handle (left side)
    g.lathe([(-15, 0), (-15, 3), (-26, 2.6), (-27, 4.2), (-31, 4.4), (-33, 3), (-33.6, 0)], 'blued', axis='w',
            at=(214, 21), seg=14)

    # ---------------------------------------------------------------- magazine
    with g.part('mag'):
        traced = g.outline([(60, -54), (240, -54), (240, -280), (60, -280)])
        T, lo, hi, to_uv = mag_edges(traced, (120, -54), -75, -6, 240)
        # clean outline from the fitted edges (the traced one is pixel-noisy and shades wavy)
        mag = [to_uv(t, n) for t, n in zip(T, lo)] + [to_uv(t, n) for t, n in zip(T[::-1], hi[::-1])]
        g.sweep(mag, 'blued', width=25, radius=2.5, axis=-75, origin=(120, -54), step=4, name='mag')
        g.box(92, 148, -58, -24, width=22, mat='blued', bevel=0.5)
        # pressed stiffening ribs along both sides of the magazine body
        sel = (T > 8) & (T < T[-1] - 22)
        for f in (0.19, 0.34, 0.49, 0.64, 0.79):
            line = [to_uv(t, n) for t, n in zip(T[sel], (lo + (hi - lo) * f)[sel])]
            for wr in (11.9, -11.9):
                g.pipe([(u, v, wr) for u, v in line], 1.25, 'blued', seg=8)
        # floor plate: a slightly oversized lip at the bottom
        te = T[-1]
        fp = [to_uv(te - 6, lo[-1] - 1.4), to_uv(te + 1.5, lo[-1] - 1.4), to_uv(te + 1.5, hi[-1] + 1.6),
              to_uv(te - 6, hi[-1] + 1.6)]
        g.extrude(fp, width=27.5, mat='blued', bevel=0.8, name='floorplate')
    g.pivot('mag', 120, -56)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 577, BORE_V)
    g.anchor('sight', 120, 52.0)            # sight line height (rear notch bottom ~ front post top)
    g.anchor('eject', 100, 14, 16)
    g.anchor('rh', -78, -86, 0)
    g.anchor('lh', 290, -16, 0)
    g.anchor('eye', -150, 52.0)             # aiming eye position (cheek on the stock); ADS camera goes here
