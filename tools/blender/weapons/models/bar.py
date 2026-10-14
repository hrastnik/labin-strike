"""Browning Automatic Rifle M1918A2. Reference: 'M1918 Browning Automatic Rifle (7351276550).jpg' (US Army drawing
sheet, the M1918A2 view; public domain). The drawing is a line drawing, so the mask is filled from the ink outlines
(cal/bar.json "mask_drawing") and cleaned with "mask_ops" (monopod, raised rear leaf and the folded-back shoulder rest
erased, magazine / trigger guard outlines redrawn). 1214 mm, parkerised receiver, walnut butt and forearm, gas
cylinder under the barrel, A2 bipod on the flash hider (deployed as in the drawing), 20-round box magazine."""
import math

from ..lib import bevel as _bev, hull_circles, rrect, section

REF = 'bar'
META = {'kind': 'rifle'}

SIGHT_V = 35.0      # aperture centre = front blade top
REC_W = 34.0


def screw(g, u, v, w, r=3.0, mat='park', side=1):
    w0 = w * side
    w1 = (w + 1.3) * side
    prof = [(w0, 0), (w0, r), ((w + 0.9) * side, r * 0.85), (w1, r * 0.4), (w1, 0)]
    return g.lathe(prof, mat, axis='w', at=(u, v), seg=12)


def both(g, fn, *a, **kw):
    fn(g, *a, side=1, **kw)
    fn(g, *a, side=-1, **kw)


def leg(g, pts, foot_region, r_up, r_lo, latch, w0, w1):
    """bipod leg: side-view centreline pts [(u, v)], splaying linearly from w0 (top) to w1 (bottom)."""
    v0, v1 = pts[0][1], pts[-1][1]
    W = lambda v: w0 + (w1 - w0) * (v - v0) / (v1 - v0)
    P = [(u, v, W(v)) for u, v in pts]
    lv = latch[1]
    up = [p for p in P if p[1] >= lv] + [(latch[0], lv, W(lv))]
    lo = [(latch[0], lv, W(lv))] + [p for p in P if p[1] < lv]
    g.pipe(up, r_up, 'park', seg=14)
    g.pipe(lo, r_lo, 'park', seg=12)
    # latch sleeve with its wing nut (sticks out forward)
    a = math.atan2(up[-1][0] - up[-2][0], up[-2][1] - up[-1][1])
    sl = g.lathe([(-14, 0), (-14, r_up + 1.5), (-12, r_up + 2.8), (12, r_up + 2.8), (14, r_up + 1.5), (14, 0)],
                 'park', axis='v', at=(0, 0), seg=14)
    g.transform(sl, rot=('w', math.degrees(a)), move=(latch[0], lv - 2, W(lv)))
    g.extrude([(latch[0] - 2, lv + 4), (latch[0] - 14, lv + 12, 2), (latch[0] - 19, lv + 17, 2),
               (latch[0] - 15, lv + 18, 2), (latch[0] - 8, lv + 13), (latch[0] + 2, lv + 8)],
              W(lv) - 2.2, W(lv) + 2.2, 'park', bevel=0.5)
    fo = g.outline(foot_region)
    g.extrude(fo, W(v1) - 9, W(v1) + 9, 'park', bevel=1.0, name='foot')


def build(g):
    # ---------------------------------------------------------------- butt stock (walnut) + butt plate
    region = [(-410, 15), (-100, 15), (-100, -60), (-160, -93), (-200, -84), (-262, -103), (-285, -110),
              (-300, -118), (-410, -152)]
    so = g.outline(region)
    g.sweep(so, 'walnut', width=[(-400, 41), (-330, 40), (-240, 37), (-170, 33), (-110, 32)], radius=(9, 8),
            top=0.9, step=4, name='stock')
    # steel butt plate: the rear 5 mm of the stock outline
    rear = [p for p in so if p[0] < -380 and -140 < p[1] < -12]
    n = len(rear)
    mv = sum(p[1] for p in rear) / n
    mu = sum(p[0] for p in rear) / n
    b = sum((p[1] - mv) * (p[0] - mu) for p in rear) / max(1e-6, sum((p[1] - mv) ** 2 for p in rear))
    ua = lambda v: mu + b * (v - mv)
    plate = g.extrude(so, width=42, mat='park', bevel=0.8, name='buttplate')
    g.cut(plate, g.extrude([(ua(40) + 5, 40), (300, 40), (300, -200), (ua(-200) + 5, -200)], -40, 40, cutter=True,
                           bevel=0))
    # hinged shoulder rest, folded down against the plate
    g.lathe([(-14, 0), (-14, 3.6), (14, 3.6), (14, 0)], 'park', axis='w', at=(ua(-8) - 1.5, -8), seg=12)
    g.extrude([(ua(-10) - 3.5, -10), (ua(-10) - 0.5, -10), (ua(-70) - 0.5, -70), (ua(-66) - 3.5, -66)], width=30,
              mat='park', bevel=0.6, name='rest')
    # stock sling swivel
    g.box(-280, -264, -112, -104, width=12, mat='park', bevel=0.6)
    g.pipe([(-272, -110, 0), (-280, -118, 0), (-279, -128, 0), (-272, -132, 0), (-265, -128, 0), (-264, -118, 0),
            (-272, -110, 0)], 1.8, 'park', seg=8, corner=3)

    # ---------------------------------------------------------------- receiver
    rprof = [(-150, -4), (-140, -1.5), (-130, 3.5), (-120, 10.5), (-112, 17), (-104, 21.5, 3), (-20, 21.5),
             (-12, 27, 3), (-5, 31.5, 3), (33, 31, 3), (40, 26.5, 3), (48, 23.5), (126, 22.5, 2), (130, 17),
             (130, -56), (-90, -56), (-112, -57)]
    rec = g.extrude(rprof, width=REC_W, mat='park', bevel=0, name='receiver')
    # cocking handle slot (left side) and the handle in the forward position
    g.cut(rec, g.extrude(rrect(28, 124, 9, 16, 3), -REC_W / 2 - 1, -REC_W / 2 + 2.5, cutter=True, bevel=0))
    g.lathe([(-REC_W / 2 + 2, 0), (-REC_W / 2 + 2, 3.2), (-REC_W / 2 - 10, 3.6), (-REC_W / 2 - 13, 4.6),
             (-REC_W / 2 - 16, 4.6), (-REC_W / 2 - 17, 0)], 'park', axis='w', at=(116, 12.5), seg=14)
    # ejection port (right side) with the bolt face visible, dust cover slid open beneath it
    g.cut(rec, g.extrude(rrect(36, 104, 4, 18, 2), REC_W / 2 - 3, REC_W / 2 + 1, cutter=True, bevel=0))
    _bev(rec, 1.0, 3)
    g.box(38, 102, 6, 16, REC_W / 2 - 4, REC_W / 2 - 2.5, 'bright', bevel=0.3)
    g.box(40, 106, -4, 3, REC_W / 2 - 0.5, REC_W / 2 + 1.2, 'park', bevel=0.4)
    # side rivets / pins
    for u, v in ((-60, -40), (-20, -42), (60, -44), (118, -40), (-96, 4), (-35, 6)):
        both(g, screw, u, v, REC_W / 2, r=2.6)
    # magazine well lips under the receiver
    g.box(14, 112, -61, -54, width=REC_W - 2, mat='park', bevel=0.6)
    # magazine release (front of the well)
    g.box(110, 118, -66, -56, width=12, mat='park', bevel=0.6)

    # ---------------------------------------------------------------- trigger housing and guard
    g.box(-80, 42, -62, -50, width=28, mat='park', bevel=0.8, name='housing')
    guard = [(-78, -53), (41, -55.5), (40.5, -92, 4), (-70, -90, 4), (-78.5, -77, 3)]
    hole = [(-69, -59), (31, -60.5), (31, -74, 2), (10, -73.6), (9.8, -84, 3), (-69, -82, 4)]
    g.extrude(guard, width=12, holes=[hole], mat='park', bevel=0.6, name='guard')
    g.extrude([(0, -58), (6, -58), (8, -68), (7.8, -78), (5.6, -85.5, 1), (2.6, -85, 1), (3.2, -77), (1.8, -66)],
              width=6, mat='park', bevel=0.5, name='trigger')
    # selector lever (left side, above the guard)
    g.extrude([(-14, -57), (14, -50, 3), (18, -53, 3), (-12, -62, 2)], -REC_W / 2 + 4, -REC_W / 2 - 1.5, 'park',
              bevel=0.4, name='selector')
    g.lathe([(-REC_W / 2 + 4, 0), (-REC_W / 2 + 4, 4), (-REC_W / 2 - 2.5, 4), (-REC_W / 2 - 2.5, 0)], 'park',
            axis='w', at=(-12, -57.5), seg=12)

    # ---------------------------------------------------------------- rear sight (leaf folded, battle aperture)
    g.extrude([(-116, 18), (-92, 18), (-92, 27, 2), (-116, 27, 2)], width=26, mat='park', bevel=0.6, name='rsbase')
    for s in (1, -1):
        g.extrude([(-114, 24), (-96, 24), (-97, SIGHT_V - 2, 3), (-113, SIGHT_V - 2, 3)], s * 8.5, s * 12.5, 'park',
                  bevel=0.5, name='rsear')
    g.extrude([(-98, 26.5), (-52, 25), (-52, 28, 1), (-98, 30, 1)], width=12, mat='park', bevel=0.4, name='leaf')
    g.box(-106, -102.5, 26, SIGHT_V - 3, width=4.5, mat='park', bevel=0.3)
    ap = g.cyl(-106, -102.5, 4.6, axis='u', at=(SIGHT_V, 0), seg=20, chamfer=0.4)
    g.cut(ap, g.cyl(-110, -98, 1.15, axis='u', at=(SIGHT_V, 0), seg=14, cutter=True))
    g.lathe([(-14, 0), (-14, 3.4), (-17, 4.2), (-20, 4.2), (-20, 0)], 'park', axis='w', at=(-104, 22), seg=14)
    g.lathe([(14, 0), (14, 3.4), (17, 4.2), (20, 4.2), (20, 0)], 'park', axis='w', at=(-104, 22), seg=14)

    # ---------------------------------------------------------------- barrel, gas system, flash hider
    g.lathe([(126, 0), (126, 14), (230, 14), (246, 11.4), (560, 10.8), (770, 10.6), (770, 0)], 'park', seg=28,
            name='barrel')
    fh = g.lathe([(766, 0), (766, 12.8), (812, 12.8), (816, 11.6), (816, 0)], 'park', seg=28, name='flash')
    g.cut(fh, g.cyl(795, 825, 6.5, cutter=True, seg=18))
    for k in range(4):                             # flash hider slots
        c = g.box(790, 812, -1.6, 1.6, 0, 20, cutter=True, bevel=0)
        g.transform(c, rot=('u', 45 + 90 * k))
        g.cut(fh, c)
    GV = -28.7
    g.lathe([(330, 0), (330, 10.6), (590, 10.6), (592, 11.2), (598, 11.2), (600, 9.6), (600, 0)], 'park',
            at=(GV, 0), seg=22, name='gascyl')
    g.extrude(hull_circles([(0, 0, 13), (0, GV, 11.6)], n=40), 561, 579, 'park', plane='front', bevel=0.8,
              name='gasblock')
    g.lathe([(-1, 0), (-1, 6), (4, 6), (4, 0)], 'park', axis='u', at=(GV, 0))
    # front band with the sling swivel
    g.extrude(hull_circles([(0, 0, 12.6), (0, GV, 12.2)], n=40), 376, 391, 'park', plane='front', bevel=0.6,
              name='band')
    g.pipe([(383.5, -41, 0), (378, -46, 0), (378, -53, 0), (383.5, -57, 0), (389, -53, 0), (389, -46, 0),
            (383.5, -41, 0)], 1.6, 'park', seg=8, corner=2.5)
    for s in (1, -1):
        g.lathe([(s * 12.2, 0), (s * 12.2, 2.4), (s * 14.5, 2.0), (s * 14.5, 0)], 'park', axis='w', at=(383.5, -14))

    # ---------------------------------------------------------------- forearm (walnut)
    fo = [(128, -5), (337, -5), (337, -42, 4), (330, -53, 6), (320, -59.5, 4), (128, -59.5)]
    fa = g.sweep(fo, 'walnut', width=46, radius=(8, 12), top=0.92, step=5, round_ends=(0, 3), name='forearm')
    g.cut(fa, g.cyl(120, 345, 14.6, seg=24, cutter=True))
    both(g, screw, 273, -47, 23, r=3.6)
    g.box(126, 132, -58, -6, width=44, mat='park', bevel=0.8)                    # receiver front ferrule

    # ---------------------------------------------------------------- front sight (blade with guard ears)
    g.lathe([(689, 0), (689, 12.6), (714, 12.6), (714, 0)], 'park', seg=24, name='fsband')
    g.extrude([(690, 8), (713, 8), (713, 17, 2), (690, 20, 2)], width=16, mat='park', bevel=0.6, name='fsbase')
    for s in (1, -1):
        g.extrude([(692, 14), (712, 14), (711, SIGHT_V - 3, 3), (695, SIGHT_V - 3, 3)], s * 4.6, s * 7.6, 'park',
                  bevel=0.4, name='fsear')
    g.extrude([(697, 15), (707, 15), (705, SIGHT_V, 0.6), (700, SIGHT_V, 0.6)], width=1.5, mat='park', bevel=0.2,
              name='fblade')

    # ---------------------------------------------------------------- bipod (A2, on the flash hider)
    g.extrude(section(34, 34, 38, 9, 7, 4, y0=-21), 716, 768, 'park', plane='front', bevel=0.8, name='bpclamp')
    g.extrude([(719, -22), (759, -22), (756, -46, 4), (722, -46, 4)], width=28, mat='park', bevel=0.8, name='yoke')
    g.lathe([(-17, 0), (-17, 4.5), (17, 4.5), (17, 0)], 'park', axis='w', at=(739, -38), seg=14)
    for u in (730, 765):
        both(g, screw, u, 2, 17, r=2.4)
    leg(g, [(733, -36), (729, -50), (723.7, -100), (718.5, -150), (713, -200), (708, -250), (707, -266)],
        [(668, -258), (744, -258), (744, -296), (668, -296)], 8.0, 6.0, (713.5, -205), -10, -62)
    leg(g, [(744, -36), (748.7, -50), (754.8, -100), (761, -150), (765, -180), (772, -230), (774, -250),
            (778, -280)], [(740, -272), (822, -272), (822, -310), (740, -310)], 8.0, 6.0, (768.5, -212), 10, 66)

    # ---------------------------------------------------------------- magazine (part 'mag')
    with g.part('mag'):
        m = g.extrude([(19, -48), (107, -48), (107, -146), (19, -146)], width=28, mat='park', bevel=0.8, name='mag')
        g.extrude(rrect(17, 109, -151, -144, 2), width=30.5, mat='park', bevel=0.6, name='floor')
        for u in (86, 93):                                         # pressed stiffening ribs
            g.box(u, u + 3, -140, -60, -15.2, 15.2, 'park', bevel=0.8)
        g.box(24, 44, -60, -52, -14.8, 14.8, 'park', bevel=0.4)     # catch notch plate
        for s in (1, -1):
            g.box(30, 80, -138, -124, s * 13.6, s * 14.8, 'park', bevel=0.4)
    g.pivot('mag', 63, -54)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 816, 0)
    g.anchor('sight', -104, SIGHT_V)
    g.anchor('eject', 70, 11, REC_W / 2 + 2)
    g.anchor('rh', -128, -62, 0)
    g.anchor('lh', 240, -62, 0)
    g.anchor('eye', -380, SIGHT_V)
