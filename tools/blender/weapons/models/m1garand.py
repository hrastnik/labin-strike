"""M1 Garand. Reference: M1 Garand rifle USA noBg cropped.jpg (right side). 1107 mm, parkerised steel, walnut
stock and handguards, en-bloc clip of eight .30-06 rounds ('mag'), operating rod handle + bolt ('bolt', slides back
during the en-bloc reload).

The helpers at the top (smooth_edge, cartridge, swivel, knurl) are shared by the other semi-auto / bolt models."""
import math

import numpy as np

from ..lib import hull_circles, rrect, section

REF = 'm1garand'
META = {'kind': 'rifle'}

BORE_V = -1.0
SIGHT_V = 24.5      # top of the front post = centre of the rear aperture


# ------------------------------------------------------------------ shared helpers

def smooth_edge(pts, u0, u1, split, side='bottom', deg=2, tol=1.2, blend=8.0):
    """replace the v of the outline points on one side (below/above `split`, number or callable(u)) with u0 <= u <= u1
    by a robust polynomial fit: kills pixel noise / bumps (swivels, shadows) on long smooth edges."""
    sp = split if callable(split) else (lambda u, s=split: s)
    sel = [i for i, (u, v) in enumerate(pts) if u0 <= u <= u1 and ((v < sp(u)) if side == 'bottom' else (v > sp(u)))]
    if len(sel) < deg + 2:
        return pts
    U = np.array([pts[i][0] for i in sel])
    V = np.array([pts[i][1] for i in sel])
    keep = np.ones(len(U), bool)
    for _ in range(3):
        c = np.polyfit(U[keep], V[keep], deg)
        r = V - np.polyval(c, U)
        keep = np.abs(r) < max(tol, 2.5 * np.std(r[keep]))
    out = list(pts)
    for i in sel:
        u, v = pts[i]
        f = min(1.0, (u - u0) / blend, (u1 - u) / blend) if blend > 0 else 1.0
        out[i] = (u, v + (float(np.polyval(c, u)) - v) * max(0.0, f))
    return out


CASE_3006 = [(0, 0), (0, 5.6), (0.8, 5.95), (1.3, 5.95), (1.6, 5.0), (3.0, 5.0), (3.4, 5.9), (48.5, 5.6),
             (51.8, 4.35), (63.3, 4.3), (63.3, 0)]
BULLET_3006 = [(63.0, 0), (63.0, 3.95), (68.5, 3.95), (75.5, 3.4), (80.5, 2.3), (84.2, 0.8), (84.8, 0)]


def cartridge(g, u, v, w, case=CASE_3006, bullet=BULLET_3006, seg=12, axis_dir=1):
    """a round lying along u (base at u, pointing +u), centre (v, w)."""
    sgn = axis_dir
    g.lathe([(u + sgn * x, r) for x, r in case], 'brass', at=(v, w), seg=seg, name='case')
    g.lathe([(u + sgn * x, r) for x, r in bullet], 'brass', at=(v, w), seg=seg, name='bullet')
    g.lathe([(u - sgn * 0.05, 0), (u - sgn * 0.05, 2.6), (u + sgn * 0.3, 2.6), (u + sgn * 0.3, 0)], 'bright',
            at=(v, w), seg=10, name='primer')


def swivel(g, cu, cv, a_deg, L=22, W=14, r=1.6, mat='park', w0=0.0):
    """sling swivel loop hanging from (cu, cv), tilted a_deg from straight down (positive = toward +u)."""
    a = math.radians(a_deg)
    du, dv = math.sin(a), -math.cos(a)
    pts = []
    for k in range(17):
        t = 2 * math.pi * k / 16
        x = W / 2 * math.sin(t)              # across (w)
        y = L / 2 * (1 - math.cos(t))        # along the hang direction
        pts.append((cu + du * y, cv + dv * y, w0 + x))
    g.pipe(pts[:-1], r, mat, seg=8, closed=True, name='swivel')


def knurl(g, ob, cu, cv, w0, w1, R, n=24, depth=0.7, width=0.9):
    """axial grooves around a knob whose axis is w (centre (cu, cv)), between w0..w1."""
    cs = []
    for k in range(n):
        c = g.box(cu - width / 2, cu + width / 2, cv + R - depth, cv + R + 2, w0, w1, cutter=True, bevel=0)
        g.transform(c, rot=('w', 360.0 * k / n), pivot=(cu, cv, 0))
        cs.append(c)
    g.cut(ob, *cs)


def screw(g, u, v, w, r=2.6, h=1.0, side=1, slot=True, mat='park', ang=30):
    """slotted screw head on a side face at w (side=+1 right, -1 left)."""
    ob = g.lathe([(w, 0), (w, r), (w + side * h * 0.6, r * 0.92), (w + side * h, r * 0.6), (w + side * h, 0)], mat,
                 axis='w', at=(u, v), seg=14, name='screw')
    if slot:
        f = w + side * h
        a, b = sorted((f - side * 0.45, f + side * 1.0))
        c = g.box(u - r * 1.2, u + r * 1.2, v - 0.35, v + 0.35, a, b, cutter=True, bevel=0)
        g.transform(c, rot=('w', ang), pivot=(u, v, 0))
        g.cut(ob, c)
    return ob


def pin(g, u, v, w, r=1.6, h=0.5, mat='park'):
    """pin end flush-ish on both sides (w = half width of the part)."""
    for s in (1, -1):
        g.lathe([(s * (w - 0.5), 0), (s * (w - 0.5), r), (s * (w + h), r * 0.9), (s * (w + h), 0)], mat, axis='w',
                at=(u, v), seg=10, name='pin')


# ------------------------------------------------------------------ the rifle

def build(g):
    # ---------------------------------------------------------------- stock
    region = [(-350, 60), (-37, 60), (-37, -9.8), (142, -9.8), (142, 0.3), (409, 0.3), (409, -44.4), (200, -90),
              (134, -90), (134, -53.5), (44, -53.5), (44, -63.6), (-33, -63.6), (-38, -130), (-350, -200)]
    stock = g.outline(region)
    stock = smooth_edge(stock, -335, -120, lambda u: -80, 'bottom', deg=1)       # straight butt bottom (swivel)
    stock = smooth_edge(stock, -336, -140, lambda u: -80, 'top', deg=2)          # comb
    stock = smooth_edge(stock, 150, 405, lambda u: -20, 'bottom', deg=2)         # forend
    st = g.sweep(stock, 'walnut', width=[(-345, 43), (-250, 41), (-140, 37), (-95, 36.5), (-45, 39), (-20, 47),
                                          (140, 48), (300, 46), (409, 43)],
                 radius=(9, 11), step=5, n=3,
                 round_ends=(0, 2.0), name='stock')
    # channel for the operating rod on the right, recess for the receiver / handguard
    g.cut(st, g.box(138, 322, -4.6, 8, 12.5, 30, cutter=True, bevel=0),
          g.box(-34, 142, -10.2, 8, -16.2, 16.2, cutter=True, bevel=0), solver='FLOAT')
    # butt plate (checkered steel, trap door seen from the back only)
    bp = g.outline([(-360, 60), (-337.5, 60), (-337.5, -200), (-360, -200)])
    g.sweep(bp, 'park', width=44, radius=(10, 10), step=2, name='buttplate')
    swivel(g, -250, -141.5, 55, L=20, W=13)
    g.box(-262, -238, -143.5, -139, width=11, mat='park', bevel=0.8)              # swivel plate on the toe line
    pin(g, -250, -138.5, 6.5, r=1.6)
    # stock ferrule + swivel at the forend tip
    fer = section(44, 44, 34.5, 7, 12, 5, y0=-31.5)
    g.extrude(fer, 407, 420, 'park', plane='front', bevel=0.7, name='ferrule')
    swivel(g, 408, -40, -35, L=20, W=13)
    pin(g, 413.5, -26, 22.3, r=1.7)

    # ---------------------------------------------------------------- receiver
    rec = [(6, -11), (122, -11), (122, 5.6), (70, 4.8), (36, 4.6), (12, 6.2), (6, 5.4)]
    rv = g.extrude(rec, width=31, mat='park', bevel=1.2, name='receiver')
    g.cut(rv, g.box(9, 121, -6, 12, -10.5, 10.5, cutter=True, bevel=0))           # open top (bolt / clip well)
    # receiver heel: rounded on top, behind the rear sight
    g.sweep([(-34.5, -4), (-31, 2.4), (0, 4.6), (8, 5.4), (8, -11), (-34, -11)], 'park', width=31,
            radius=(7.5, 1.0), step=2.5, n=4, round_ends=(2.0, 0), name='heel')
    g.cut(rv, g.box(60, 121, -12, 12, -7.5, 7.5, cutter=True, bevel=0))           # clip well
    # receiver ring around the chamber (round, seats the barrel)
    g.lathe([(118, 0), (118, 12.0), (121, 12.6), (136, 12.6), (139, 11.2), (139, 0)], 'park', at=(-4.0, 0), seg=32,
            name='ring')
    # rails each side of the bolt raceway, receiver heel radius
    for s in (1, -1):
        g.box(3, 121, 2.2, 5.0, s * 10.5, s * 13.2, mat='park', bevel=0.5)
    # clip latch (left), operating-rod catch strip (right), receiver leg pins
    g.box(64, 82, -6, 3.5, -17.4, -15.2, mat='park', bevel=0.7)
    screw(g, 73, -1.5, -17.4, r=2.2, h=0.8, side=-1, slot=False)
    for s in (1, -1):
        for u, v in ((100, -6.5), (18, -6.5)):
            g.lathe([(s * 15.3, 0), (s * 15.3, 1.7), (s * 16.1, 1.5), (s * 16.4, 0)], 'park', axis='w', at=(u, v),
                    seg=10, name='rivet')

    # ---------------------------------------------------------------- rear sight
    base = [(9, 3), (36, 3), (36, 11, 2), (30, 15.5, 3), (14, 15.5, 3), (9, 11)]
    g.extrude(base, width=24, mat='park', bevel=0.8, name='sightbase')
    # protective ears with the windage / elevation knobs between them
    ear = [(31, 3), (70, 3), (70, 12, 1.5), (63, 18.5, 1.5), (59, 18.6, 1.0), (37, 13.4), (33, 9)]
    for s in (1, -1):
        e = g.extrude(ear, s * 9.5, s * 13.8, 'park', bevel=0.6, name='ear')
        g.cut(e, g.extrude(rrect(41, 66, 5.5, 12.5, 2.5), -20, 20, cutter=True, bevel=0))
    # aperture plate (peep), hole centre on the sight line; slide behind it
    ap = g.extrude([(17, 9), (23.5, 9), (23.5, 28.5, 2), (21.5, 31, 2), (19, 31, 2), (17, 28.5, 2)], width=11,
                   mat='park', bevel=0.5, name='aperture')
    g.cut(ap, g.cyl(10, 30, 2.4, at=(SIGHT_V, 0), seg=20, cutter=True, chamfer=0))
    g.lathe([(16.8, 2.4), (16.8, 3.6), (17.6, 4.6), (23.7, 4.6), (24.4, 3.6), (24.4, 2.4)], 'park', at=(SIGHT_V, 0),
            seg=24, closed=True, name='peepring')
    # windage knob (right, graduated drum) and elevation knob (left, larger)
    for s, w0, w1, R in ((1, 12.0, 17.8, 9.8), (-1, -12.0, -18.8, 10.6)):
        kb = g.lathe([(w0, 0), (w0, R - 0.6), (w0 + s * 0.6, R), (w1 - s * 0.8, R), (w1, R - 0.9), (w1, 0)], 'park',
                     axis='w', at=(24, 20), seg=36, name='knob')
        knurl(g, kb, 24, 20, min(w0, w1) - 1, max(w0, w1) + 1, R, n=30, depth=0.55, width=0.9)
        g.lathe([(w1, 0), (w1, 3.2), (w1 + s * 1.0, 2.6), (w1 + s * 1.2, 0)], 'park', axis='w', at=(24, 20), seg=14)
    # windage graduations (small ticks around the right drum face)
    for k in range(12):
        a = math.radians(30 * k)
        cu, cv = 24 + 7.6 * math.cos(a), 20 + 7.6 * math.sin(a)
        t = g.box(cu - 0.3, cu + 0.3, cv - 1.0, cv + 1.0, 17.7, 18.1, mat='bright', bevel=0)
        g.transform(t, rot=('w', 30 * k - 90), pivot=(cu, cv, 0))

    # ---------------------------------------------------------------- trigger group
    housing = [(30, -61.5), (43, -61.5), (46, -58), (55, -57), (56, -52.5), (133, -52.5), (133, -68, 1.5),
               (56, -68, 1), (51, -66), (30, -66)]
    hs = g.extrude(housing, width=24, mat='park', bevel=0.9, name='housing')
    for s in (1, -1):
        g.cut(hs, g.box(58, 131, -57.2, -56.2, s * 11.4, s * 13, cutter=True, bevel=0))
    pin(g, 120, -61, 12, r=1.8)
    pin(g, 64, -63, 12, r=1.6)
    guard, holes = g.outline([(-33, -90), (27.5, -90), (27.5, -61), (-33, -61)], holes=True)
    g.extrude(guard, width=9, mat='park', holes=holes, bevel=0.9, name='guard')
    safe = g.extrude(rrect(27.5, 38.5, -79.5, -61.5, 1.8), width=8, mat='park', bevel=0.7, name='safety',
                     holes=[rrect(30.3, 36, -77, -67, 1.2)])
    trig = [(-3.5, -60), (2.5, -60), (1.8, -65), (0.6, -71), (-0.6, -77), (-1.6, -82.5, 1.2), (-4.4, -83.5),
            (-4.6, -80), (-3.8, -74), (-3.4, -68), (-4.2, -63)]
    g.extrude(trig, width=5.5, mat='park', bevel=0.6, name='trigger')

    # ---------------------------------------------------------------- barrel, gas cylinder, front sight
    g.lathe([(125, 0), (125, 12.0), (150, 11.6), (190, 10.4), (260, 9.4), (420, 8.3), (600, 7.6), (715, 7.4),
             (753, 7.0), (753, 6.3), (768, 6.1), (769.5, 5.4), (769.5, 3.9), (766, 3.8), (766, 0)], 'park',
            at=(BORE_V, 0), seg=28, name='barrel')
    gas_v = -16.0
    gc = g.lathe([(612, 0), (612, 8.3), (750, 8.3), (751.8, 7.6), (752.2, 0)], 'park', at=(gas_v, 0), seg=24,
                 name='gascyl')
    g.lathe([(751, 0), (751, 6.0), (755.5, 5.6), (756.5, 4.0), (756.5, 0)], 'park', at=(gas_v, 0), seg=18,
            name='plug')
    g.box(755.8, 757.2, gas_v - 4.6, gas_v + 4.6, -0.5, 0.5, cutter=False, mat='park', bevel=0)
    # rear band of the gas cylinder (clamps the barrel) and its front collar with the sight
    g.extrude(hull_circles([(0, BORE_V, 9.8), (0, gas_v, 9.6)]), 607, 619, 'park', plane='front', bevel=0.8,
              name='gasband')
    g.extrude(hull_circles([(0, BORE_V, 8.4), (0, gas_v, 8.9)]), 714, 742, 'park', plane='front', bevel=0.8,
              name='gasfront')
    gl = g.lathe([(741, 0), (741, 8.0), (752, 8.0), (753, 7.2), (753, 0)], 'park', at=(BORE_V, 0), seg=28,
                 name='gaslock')
    for k in range(6):                                                            # gas cylinder lock flats
        c = g.box(742, 754, BORE_V + 7.4, BORE_V + 10, -6, 6, cutter=True, bevel=0)
        g.transform(c, rot=('u', 60 * k), pivot=(0, BORE_V, 0))
        g.cut(gl, c)
    # bayonet lug under the front collar
    g.box(728, 750, gas_v - 11.5, gas_v - 7.0, width=6, mat='park', bevel=0.6)
    # front sight: base, protective ears, post
    fs = [(714, 5.5), (742, 5.5), (741, 12, 2), (739.5, 26, 5), (733, 30.2, 5), (720, 30.2, 6), (715, 22, 3),
          (714, 12)]
    for s in (1, -1):
        e = g.extrude(fs, s * 2.0, s * 5.6, 'park', bevel=0.6, name='fsear')
        g.cut(e, g.cyl(-10, 10, 1.6, axis='w', at=(727, 24.2), cutter=True, seg=12, chamfer=0))
    g.box(714.5, 741.5, 5.5, 12.5, width=11.2, mat='park', bevel=0.8)
    post = [(724.2, 11), (729.8, 11), (729.4, SIGHT_V - 0.3), (729, SIGHT_V), (725, SIGHT_V), (724.6, SIGHT_V - 0.3)]
    g.extrude(post, width=1.3, mat='park', bevel=0.2, name='post')
    screw(g, 728, 8.8, 5.6, r=1.6, h=0.6, side=1, ang=80)
    # stacking swivel under the gas cylinder (folded)
    g.lathe([(660, 0), (660, 9.4), (668, 9.4), (668, 0)], 'park', at=(gas_v, 0), seg=24, name='stackband')
    stk = g.extrude([(659, -24), (684, -24), (684, -27), (679, -32.3, 1.5), (662, -32.3, 1.5), (659, -28)], width=7,
                    mat='park', bevel=0.6, name='stacking')
    g.cut(stk, g.extrude(rrect(666, 677, -30, -26.5, 1), -10, 10, cutter=True, bevel=0))
    # lower band swivel
    swivel(g, 613, -26, -38, L=21, W=12, r=1.5)
    screw(g, 613, -4, 9.8, r=1.8, h=0.6, side=1, slot=False)

    # ---------------------------------------------------------------- handguards and bands
    rear_hg = [(182, -2), (419, -2), (419, 14.3), (330, 15.2), (200, 15.8), (186, 15.2, 3), (182, 12)]
    g.sweep(rear_hg, 'walnut', width=[(182, 31), (419, 33)], radius=(13, 2), step=4, name='rearhg')
    # lower band (holds the front of the rear handguard and the rear of the front handguard)
    lb = section(38, 40, 46, 13, 9, 5, y0=-30.5)
    g.extrude(lb, 419, 433, 'park', plane='front', bevel=0.7, name='lowerband')
    pin(g, 426, -24, 20, r=1.5)
    front_hg = [(432, -27.2), (607, -25.5), (608, 8, 4), (604, 13.4, 3), (520, 14.0), (432, 14.4)]
    g.sweep(front_hg, 'walnut', width=[(432, 37), (600, 35), (608, 30)], radius=(13, 8), step=4, round_ends=(0, 2),
            name='fronthg')
    # handguard ferrule in front of the front handguard
    g.extrude(section(26, 30, 36, 11, 8, 4, y0=-26.5), 604, 610, 'park', plane='front', bevel=0.6, name='hgferrule')
    # operating rod: under the front handguard, along the right of the stock, handle at the receiver
    with g.part('bolt'):
        rod_low = [(428, -34), (612, -32.5), (612, -24.5), (428, -26)]
        g.extrude(rod_low, 2, 11, 'park', bevel=0.8, name='oprodlow')
        g.extrude([(180, -4), (316, -4), (301, 4.6), (180, 4.6)], 13.0, 21.0, 'park', bevel=0.8, name='oprod')
        h = [(140, -4), (181, -4), (181, 14.5, 2.5), (178.5, 17.2, 1.5), (167, 17.2, 2.5), (161.5, 11.6, 2),
             (151, 10.8), (140, 10.4, 1.5)]
        oh = g.extrude(h, 12.5, 23.0, 'park', bevel=0.8, name='ophandle')
        g.cut(oh, g.extrude(rrect(141.5, 158, -2.2, 7.6, 1.2), 21.2, 30, cutter=True, bevel=0))
        # bolt in the raceway: body, right lug + roller, extractor
        g.lathe([(30, 0), (30, 7.0), (31.5, 8.4), (118, 8.4), (120, 7.6), (120, 0)], 'park', at=(-3.8, 0), seg=28,
                name='boltbody')
        g.box(36, 58, -2, 6.4, 6.2, 10.4, mat='park', bevel=0.8)                 # bolt rear lug / cam
        g.lathe([(9, 0), (9, 3.0), (13.2, 3.0), (13.2, 0)], 'bright', axis='w', at=(47, 2.8), seg=16, name='roller')
        g.box(86, 116, 1.4, 4.9, 6.4, 9.6, mat='park', bevel=0.5)                 # extractor
        g.lathe([(28.5, 0), (28.5, 4.0), (30.2, 4.0), (30.2, 0)], 'park', at=(-3.8, 0), seg=18)  # firing pin tail
        # loop of the operating rod catch / follower rod seen in the receiver
        g.extrude(rrect(132.8, 139.2, -2.5, 14.2, 3), 13.5, 16.0, 'bright', bevel=0.5, name='loop',
                  holes=[rrect(134.4, 137.6, 1.0, 11.6, 1.5)])
    g.pivot('bolt', 75, BORE_V, 0)

    # ---------------------------------------------------------------- en-bloc clip with eight rounds
    with g.part('mag'):
        top = -13.6
        for k in range(8):
            w = 5.3 if k % 2 == 0 else -5.3
            cartridge(g, 37.0, top - 5.0 * k, w, seg=12)
        # clip: spine across the case heads, side walls with the rim ribs
        cb = -13.6 - 5 * 7 - 6.8
        for s in (1, -1):
            wall = g.extrude([(35.5, cb), (58, cb), (58, top - 1.5, 2), (50, top + 2.8, 3), (35.5, top + 2.8)],
                             s * 10.6, s * 11.6, 'bright', bevel=0.3, name='clipwall')
            g.cut(wall, g.extrude(rrect(43, 54, cb + 6, top - 6, 3), -20, 20, cutter=True, bevel=0))
            g.box(35.5, 37.5, cb, top - 3, s * 6.5, s * 11.6, mat='bright', bevel=0.3)
            g.pipe([(37.4, top + 2.0, s * 10.3), (37.4, cb + 1, s * 10.3)], 0.7, 'bright', seg=6)
        g.box(35.5, 58, cb - 0.8, cb, width=23.2, mat='bright', bevel=0.3)
    g.pivot('mag', 47, top + 6.0, 0)

    # ---------------------------------------------------------------- small details on the stock
    # trigger guard pin and stock cartouche screws: escutcheons
    for s in (1, -1):
        g.lathe([(s * 22.6, 0), (s * 22.6, 3.4), (s * 23.6, 3.1), (s * 23.9, 0)], 'park', axis='w', at=(-10, -36),
                seg=14, name='escutcheon')

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 769.5, BORE_V)
    g.anchor('sight', 20.0, SIGHT_V)
    g.anchor('eject', 85, 6.0, 9.0)
    g.anchor('rh', -66, -60, 0)
    g.anchor('lh', 330, -22, 0)
    g.anchor('eye', -255, SIGHT_V)
