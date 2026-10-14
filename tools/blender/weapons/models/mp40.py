"""MP 40. Reference: MP 40 AYF 2.JPG (left side, mirrored by the calibration). 833 mm with the stock extended
(the game shows it extended), ribbed steel receiver tube, bakelite lower housing, 32-round stick magazine.
Note: the photo shows the LEFT side, so the cocking handle, magazine release and stock button visible in it sit at
w < 0."""
import math

import numpy as np

from ..lib import offset_poly, rrect, section

REF = 'mp40'
META = {'kind': 'rifle'}

L = -1          # the side seen in the photo (left)
SIGHT_V = 27.0      # top of the front post; the rear notch bottoms out NOTCH_DROP below it
NOTCH_DROP = 2.0    # so the post's tip shows in the notch (the game's eye sits exactly on the sight line)


def edges(outline, origin, axis_deg, t0, t1, step=4, trim=(20, 15), deg=2):
    """smooth front/back edges of a swept part (quadratic fits of the traced outline crossings)."""
    a = math.radians(axis_deg)
    du, dv = math.cos(a), math.sin(a)
    nu, nv = -dv, du
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
    m = (T > T[0] + trim[0]) & (T < T[-1] - trim[1])
    lo = np.polyval(np.polyfit(T[m], np.array(los)[m], deg), T)
    hi = np.polyval(np.polyfit(T[m], np.array(his)[m], deg), T)

    def to_uv(t, n):
        return (origin[0] + du * t + nu * n, origin[1] + dv * t + nv * n)
    return T, lo, hi, to_uv


def screw(g, u, v, w, r=2.6, mat='blued', axis_sign=1, slot=True):
    """dome screw head on a side face at depth w (sign gives the side)."""
    s = 1 if w > 0 else -1
    g.lathe([(w, 0), (w, r), (w + s * 0.6, r * 0.92), (w + s * 1.1, r * 0.6), (w + s * 1.3, 0)], mat, axis='w',
            at=(u, v), seg=12)


def build(g):
    # ---------------------------------------------------------------- receiver tube (ribbed), end cap
    tube = g.lathe([(-52, 0), (-52, 18.0), (75, 18.0), (76, 19.2), (266, 19.2), (266, 0)], 'blued', at=(0, 0),
                   seg=32, name='tube')
    # pressed longitudinal ribs along both sides of the tube
    for ang in (60, 82, 104, 126):
        for s in (1, -1):
            a = math.radians(ang)
            pts = [(u, 19.2 * math.cos(a), s * 19.2 * math.sin(a)) for u in ((80 if s > 0 else 172), 255)]
            g.pipe(pts, 0.9, 'blued', seg=6)
    # rear end cap: domed, with a grooved grip ring
    g.lathe([(-79, 0), (-79, 6), (-77, 12), (-73, 16.5), (-66, 19.3), (-58, 20.0), (-46, 20.0), (-46, 0)], 'blued',
            at=(0, 0), seg=32, name='endcap')
    ring = g.lathe([(-47, 0), (-47, 21.5), (-46, 22.3), (-22, 22.3), (-21, 21.5), (-21, 0)], 'blued', at=(0, 0), seg=32,
                   name='capring')
    grooves = [g.tube(u, u + 1.6, 23, 21.4, cutter=True, seg=32) for u in (-41, -36, -31)]
    g.cut(ring, *grooves)
    # cocking slot along the left side, with the safety notch at the rear
    slot = [(-6, 3), (165, 3), (165, 9), (36, 9), (36, 13.5), (20, 13.5), (20, 9), (-6, 9)]
    g.cut(tube, g.extrude(slot, -25, -12, cutter=True, bevel=0))
    # cocking knob (left), bolt forward
    g.lathe([(-19, 0), (-19, 4.5), (-24, 4.5), (-26, 6.5), (-31, 6.8), (-33.5, 5), (-34.5, 0)], 'blued', axis='w',
            at=(158, 3), seg=16, name='knob')
    # clamp bands
    g.lathe([(190, 0), (190, 21.0), (191, 21.6), (199, 21.6), (200, 21.0), (200, 0)], 'blued', at=(0, 0), seg=32)
    g.lathe([(264, 0), (264, 20.8), (265, 21.4), (279, 21.4), (280, 20.8), (280, 0)], 'blued', at=(0, 0), seg=32)

    # ---------------------------------------------------------------- rear sight
    g.extrude([(72, 15), (108, 15), (108, 21, 1.5), (106.5, 22.6, 1), (73.5, 22.6, 1), (72, 21, 1.5)], width=17,
              mat='blued', bevel=0.6, name='sightbase')
    g.extrude([(80, 21), (89, 21), (89, 23.5, 1), (86.5, 24.6), (82, 24.6), (80, 23.5)], width=13, mat='blued',
              bevel=0.4, name='leaf200')
    g.lathe([(-6.5, 0), (-6.5, 2.4), (6.5, 2.4), (6.5, 0)], 'blued', axis='w', at=(85.5, 22.4), seg=12)
    leaf = g.extrude([(90.5, 21), (95, 21), (95, SIGHT_V + 2.0), (91.5, SIGHT_V + 2.0)], width=14, mat='blued', bevel=0.4,
                     name='leaf')
    nb = SIGHT_V - NOTCH_DROP
    g.cut(leaf, g.extrude([(-2.6, SIGHT_V + 3), (2.6, SIGHT_V + 3), (0.4, nb), (-0.4, nb)], 86, 100, plane='front',
                          cutter=True, bevel=0))

    # ---------------------------------------------------------------- lower housing (bakelite) and hinge plate
    hous = g.outline([(-60, -1), (192, -1), (192, -68), (40, -68), (35, -58), (-30, -58), (-60, -58)])
    hb = g.extrude(hous, width=30, mat='bakelite', bevel=1.6, name='housing')
    # scalloped recess in front of the grooved panel, both sides
    rec = [(124, -25, 6), (182, -25, 5), (182, -38), (124, -38, 4)]
    g.cut(hb, g.extrude(rec, 14.0, 20, cutter=True, bevel=0), g.extrude(rec, -20, -14.0, cutter=True, bevel=0))
    for u, v in ((145, -32), (-28, -23)):
        screw(g, u, v, 14.2 if u > 100 else 15.2)
        screw(g, u, v, -14.2 if u > 100 else -15.2)
    g.cyl(-16.5, 16.5, 3.6, 'blued', axis='w', at=(150, -59), seg=14)          # takedown knob pin
    # grip grooves on the housing flanks
    for v in range(-52, -32, 3):
        for s in (1, -1):
            g.extrude([(78, v), (160, v), (160, v + 1.4), (78, v + 1.4)], s * 15.0, s * 15.8, 'bakelite', bevel=0.3)
    # steel hinge plate at the rear with the sling slot and the stock hinge boss
    plate = [(-56, 19.5), (-66, 19.5, 3), (-77, 14.5, 4), (-87, 3, 6), (-94, -11, 6), (-97.5, -26, 6), (-98.5, -42),
             (-96, -51), (-88, -57), (-78, -62), (-70, -60, 2), (-58, -58)]
    hp = g.extrude(plate, width=32, mat='blued', bevel=1.0, name='hinge')
    sl = rrect(-2.3, 2.3, -9, 9, 2.2)
    c = g.extrude(sl, -20, 20, cutter=True, bevel=0)
    g.transform(c, rot=('w', -35), move=(-87, -7, 0))
    g.cut(hp, c)
    g.lathe([(-16, 0), (-16, 13.5), (-17.5, 13.5), (-18.5, 12), (-18.5, 0)], 'blued', axis='w', at=(-82, -41), seg=28)
    g.lathe([(16, 0), (16, 13.5), (17.5, 13.5), (18.5, 12), (18.5, 0)], 'blued', axis='w', at=(-82, -41), seg=28)
    g.lathe([(-18, 0), (-18, 8.5), (-21.5, 8.5), (-22.5, 7), (-22.5, 0)], 'blued', axis='w', at=(-82, -41), seg=20)

    # ---------------------------------------------------------------- grip frame, bakelite grip, trigger guard
    grip = g.outline([(-115, -56), (-31, -56), (-31, -100), (-60, -170), (-125, -170)])
    gax, gor = -110.0, (-56, -60)
    g.sweep(grip, 'blued', width=22, radius=5, axis=gax, origin=gor, step=3, name='gripframe')
    panel = offset_poly(grip, -2.2)
    g.sweep(panel, 'black', width=31, radius=(6, 6), axis=gax, origin=gor, step=2.5, t0=10, name='grippanel')
    screw(g, -68, -108, 15.6)
    screw(g, -68, -108, -15.6)
    guard, holes = g.outline([(-31, -55), (40, -55), (40, -100), (-31, -100)], holes=True)
    g.extrude(guard, width=11, mat='blued', holes=holes, bevel=1.2, name='guard')
    trig = [(0, -56), (8, -56), (6, -62), (4, -70), (3.5, -78), (5, -86), (8, -91, 1), (6.5, -92), (1.5, -88),
            (-0.8, -80), (-1.2, -70), (-0.5, -62)]
    g.extrude(trig, width=6, mat='blued', bevel=0.6, name='trigger')

    # ---------------------------------------------------------------- magazine housing
    mh = [(190, 19), (262, 19), (262, -60), (266, -70), (266, -73), (219, -73), (219, -64), (213, -52, 3),
          (203, -46, 4), (190, -40, 6)]
    mw = g.extrude(mh, width=33, mat='blued', bevel=1.0, name='magwell')
    port = g.extrude(rrect(208, 250, 3, 14, 2), 8, 30, cutter=True, bevel=0)          # ejection port (right)
    g.cut(mw, port)
    g.cut(tube, g.extrude(rrect(208, 250, 3, 14, 2), 8, 30, cutter=True, bevel=0))
    g.box(206, 252, -3, 3.5, 6, 10.5, 'blued', bevel=0.3)                              # bolt face seen in the port
    for v in (-25, -37, -49, -61):
        for s in (1, -1):
            g.pipe([(226, v, s * 16.6), (252, v, s * 16.6)], 1.3, 'blued', seg=8)
    g.lathe([(-16.5, 0), (-16.5, 7.5), (-18, 7.5), (-18.8, 6.5), (-18.8, 0)], 'blued', axis='w', at=(213, -29), seg=24)

    # ---------------------------------------------------------------- barrel nut, barrel, resting bar, front sight
    nut = g.lathe([(279, 0), (279, 19.6), (322, 19.6), (325, 17.5), (334, 12.5), (338, 11), (338, 0)], 'blued',
                  at=(0, 0), seg=32, name='nut')
    g.cut(nut, *[g.box(296, 318, -30, 30, s * 17.6, s * 30, cutter=True, bevel=0) for s in (1, -1)])   # spanner flats
    g.lathe([(330, 0), (330, 10.8), (340, 10.2), (430, 7.0), (430, 0)], 'blued', at=(-0.5, 0), seg=28, name='barrel')
    g.lathe([(428, 0), (428, 8.2), (466, 8.4), (488, 8.4), (488, 0)], 'blued', at=(0, 0), seg=28)
    g.lathe([(487, 0), (487, 9.4), (504, 9.4), (505.5, 8.4), (505.5, 4.2), (504, 4.2), (504, 0)], 'blued', at=(0, 0),
            seg=28, name='muzzle')
    g.tube(495, 505.6, 4.5, 3.8, 'black', seg=16)
    rest = [(333, -6), (345, -8), (428, -7), (466, -6), (466, -9.5), (456, -12.5), (448, -18), (442, -27),
            (435, -27), (432, -16), (428, -14), (345, -14), (336, -12)]
    g.extrude(rest, width=10, mat='blued', bevel=0.8, name='rest')
    fs = [(450, 6), (490.5, 6), (490.5, 20), (488, 24), (470, 24), (469, 19), (464, 13.5), (456, 9.5)]
    g.extrude(fs, width=11, mat='blued', bevel=0.8, name='fsbase')
    hood = g.lathe([(468, 6), (468, 7.4), (490, 7.4), (490, 6)], 'blued', at=(28.4, 0), seg=28, closed=True,
                   a0=-110, a1=110, name='hood')
    g.intersect(hood, g.extrude(rrect(467, 491, 14, 36, 7), width=30, cutter=True, bevel=0))
    g.extrude([(476, 18), (480, 18), (479.5, SIGHT_V), (476.5, SIGHT_V)], width=1.4, mat='blued', bevel=0.3)

    # ---------------------------------------------------------------- folding stock (extended)
    def strut_v(u):
        return -44.0 + (u + 110) * 0.079
    for s in (1, -1):
        prof = [(-95, strut_v(-95) + 5), (-300, strut_v(-300) + 5.5), (-300, strut_v(-300) - 6),
                (-95, strut_v(-95) - 5.5)]
        g.extrude(prof, s * 5.0, s * 11.0, 'blued', bevel=1.6, seg=2, name='strut')
    butt, bh = g.outline([(-335, 5), (-293, 5), (-293, -135), (-335, -135)], holes=True)
    g.extrude(butt, width=34, mat='blued', holes=bh, bevel=2.0, name='butt')
    g.lathe([(-17.5, 0), (-17.5, 3.6), (17.5, 3.6), (17.5, 0)], 'bright', axis='w', at=(-300, -59), seg=14)

    # ---------------------------------------------------------------- magazine
    with g.part('mag'):
        traced = g.outline([(215, -70), (265, -70), (265, -255), (215, -255)])
        T, lo, hi, to_uv = edges(traced, (240, -60), -90.0, 0, 192, deg=1)
        mag = [to_uv(t, n) for t, n in zip(T, lo)] + [to_uv(t, n) for t, n in zip(T[::-1], hi[::-1])]
        top = [to_uv(-52, lo[0]), to_uv(0, lo[0]), to_uv(0, hi[0]), to_uv(-52, hi[0])]
        g.extrude(mag + [], width=22, mat='blued', bevel=1.2, name='magbody')
        g.extrude(top, width=21, mat='blued', bevel=0.8)
        for f in (0.42, 0.68):
            line = [to_uv(t, lo[i] + (hi[i] - lo[i]) * f) for i, t in enumerate(T) if 14 < t < 150]
            for s in (1, -1):
                g.pipe([(u, v, s * 11.0) for u, v in line], 1.2, 'blued', seg=8)
        te = T[-1]
        g.extrude([to_uv(te - 4, lo[-1] - 1.5), to_uv(te + 1, lo[-1] - 1.5), to_uv(te + 1, hi[-1] + 1),
                   to_uv(te - 4, hi[-1] + 1)], width=24, mat='blued', bevel=0.8, name='floor')
    g.pivot('mag', 240, -8)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 505.5, 0)
    g.anchor('sight', 93, SIGHT_V)
    g.anchor('eject', 229, 9, 17)
    g.anchor('rh', -68, -104, 0)
    g.anchor('lh', 240, -56, 0)          # the soldier holds the magazine housing
    g.anchor('eye', -190, SIGHT_V)


def _last(g, name):
    for ob, _ in reversed(g.items):
        if f'~{name}' in ob.name:
            return ob
    raise KeyError(name)
