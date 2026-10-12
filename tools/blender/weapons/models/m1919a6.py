"""Browning M1919A6. Reference: 'Browning Model 1919A6 machine gun left side view.jpg' (CC BY-SA 2.5; left side,
muzzle left, lying on a carpet; the rectifier turns it muzzle-right). The carpet, the grey stock and the cast shadow
defeat colour segmentation, so the mask is hand-traced in cal/m1919a6.json (mask_add polygons).
1346 mm: parkerised receiver with the hinged top cover (part 'cover', front hinge), back plate with pistol grip and
the A6 sheet-steel shoulder stock, perforated barrel jacket, front barrel bearing with the front sight and bipod
(legs down, splayed sideways), conical flash hider, carrying handle, 100-round belt box on the left (part 'mag')."""
import math
import os

from ..lib import bevel as _bev, rrect

REF = 'm1919a6'
META = {'kind': 'rifle', 'hide_in_ref': [] if os.environ.get('SHOWMAG') else ['mag']}

SIGHT_V = 58.0      # sight line: rear aperture centre = front blade top
REC_W = 56.0        # receiver width
JR = 23.5           # barrel jacket radius


def screw(g, u, v, w, r=3.0, mat='park', side=1):
    """round rivet head on a side face at |w| (side = +1 right, -1 left)."""
    w0 = w * side
    w1 = (w + 1.3) * side
    prof = [(w0, 0), (w0, r), ((w + 0.8) * side, r * 0.85), (w1, r * 0.4), (w1, 0)]
    return g.lathe(prof, mat, axis='w', at=(u, v), seg=10)


def both(g, fn, *a, **kw):
    fn(g, *a, side=1, **kw)
    fn(g, *a, side=-1, **kw)


def build(g):
    hw = REC_W / 2

    # ---------------------------------------------------------------- shoulder stock (sheet steel) + butt plate
    stock = [(-349, 24), (-300, 21), (-250, 19), (-200, 16.5), (-150, 14.5), (-100, 13), (-50, 12), (-20, 13),
             (-20, -22), (-60, -23), (-100, -24), (-130, -26, 6), (-150, -30, 8), (-165, -38, 8), (-180, -52, 8),
             (-195, -68, 8), (-208, -82, 6), (-220, -88, 4), (-232, -87, 4), (-242, -80, 5), (-252, -66, 6),
             (-268, -46, 8), (-285, -28, 8), (-305, -12, 8), (-325, -2, 6), (-340, 3), (-349, 8)]
    g.sweep(stock, 'park', width=[(-349, 30), (-250, 26), (-120, 22), (-20, 26)], radius=(7, 5), top=0.9,
            step=4, name='stock')
    # pressed stiffening rib along the top bar and the lightening dish in the fin
    g.extrude([(-340, 18), (-60, 8), (-60, 4), (-340, 14)], width=31, mat='park', bevel=0.8, name='rib')
    g.extrude([(-348.5, 25), (-344, 25), (-344, 2), (-348.5, 6)], width=36, mat='black', bevel=1.0, name='buttplate')
    g.extrude([(-352, 24), (-348, 24), (-348, 7), (-352, 9)], width=33, mat='park', bevel=0.8, name='buttcap')
    g.lathe([(-14, 0), (-14, 3.5), (14, 3.5), (14, 0)], 'park', axis='w', at=(-212, -76), seg=12)   # sling bar
    # stock tang into the back plate
    g.box(-30, -18, -18, 10, width=24, mat='park', bevel=0.8)

    # ---------------------------------------------------------------- back plate, grip, trigger
    g.extrude([(-24, -45), (-4, -45), (-4, 48), (-12, 52, 3), (-22, 50, 3), (-24, 40)], width=REC_W - 4,
              mat='park', bevel=1.2, name='backplate')
    g.lathe([(-30, 0), (-30, 4), (30, 4), (30, 0)], 'park', axis='w', at=(-14, 35), seg=12)        # latch pin
    grip = [(-78, -22), (-42, -22), (-40, -45), (-40, -62, 8), (-43, -86, 10), (-50, -97, 8), (-60, -99, 6),
            (-70, -96, 8), (-77, -85, 10), (-79, -60, 8)]
    g.sweep(grip, 'walnut', width=[(-79, 26), (-60, 30), (-40, 27)], radius=(6, 8), step=2.5, name='grip')
    g.box(-80, -38, -27, -20, width=26, mat='park', bevel=0.8)                                   # grip cap
    both(g, screw, -59, -60, 15, r=3.4, mat='bright')
    # trigger housing under the back plate + trigger
    g.extrude([(-26, -22), (-4, -22), (-4, -46), (-14, -48), (-26, -44)], width=22, mat='park', bevel=1.0,
              name='trhousing')
    g.extrude([(-12, -42), (-4, -42), (-3, -50, 2), (-6, -58, 2), (-10, -56), (-8, -50)], width=7, mat='blued',
              bevel=0.5, name='trigger')

    # ---------------------------------------------------------------- receiver body (below the top cover)
    body = [(-5, -64), (330, -64), (340, -60, 3), (346, -52), (346, 44, 2), (340, 48), (304, 48), (304, 30),
            (100, 30), (100, 48), (-5, 48)]
    rec = g.extrude(body, width=REC_W, mat='park', bevel=0, name='receiver')
    cuts = [g.box(226, 300, 1, 27, -hw - 5, -hw + 8, cutter=True, bevel=0),                 # belt feedway (left)
            g.box(232, 300, 4, 22, hw - 8, hw + 5, cutter=True, bevel=0),                   # link exit (right)
            g.box(40, 232, -15, -8, hw - 4, hw + 5, cutter=True, bevel=0),                  # cocking slot (right)
            g.box(110, 230, -70, -58, -12, 12, cutter=True, bevel=0)]                       # ejection (bottom)
    g.cut(rec, *cuts)
    _bev(rec, 1.0, 2)
    g.box(-4, 334, -69, -62, width=REC_W - 8, mat='park', bevel=0.8, name='bottomplate')
    g.box(226, 300, 0, 2, -hw + 1, hw - 1, 'bright', bevel=0.3)                             # feed tray floor
    # side plates: the raised bolt-guide strip and rivets
    for s in (1, -1):
        g.box(0, 300, -46, -36, s * hw - 0.8 * s, s * (hw + 1.6), 'park', bevel=0.4)
        g.box(104, 300, 28, 32, s * hw - 0.8 * s, s * (hw + 1.2), 'park', bevel=0.3)
    for u, v in ((20, -54), (70, -54), (130, -54), (190, -54), (250, -54), (300, -54), (20, 20), (80, 20),
                 (320, 30), (320, -10), (320, -40), (172, 14), (130, -22)):
        both(g, screw, u, v, hw + 1.0, r=3.0)
    # trunnion block at the front of the receiver
    g.extrude([(304, 30), (346, 30), (346, 44, 2), (340, 49), (304, 49)], width=REC_W + 2, mat='park',
              bevel=1.0, name='trunnion')
    g.lathe([(48, 0), (48, 6), (64, 5.5), (66, 4), (66.5, 0)], 'park', axis='v', at=(330, -hw + 8), seg=14)
    # cocking handle (right side, forward position) and the pintle ring under the receiver
    g.box(188, 214, -16, -7, hw - 3, hw + 4, 'park', bevel=0.8)
    g.lathe([(hw + 3, 0), (hw + 3, 5), (hw + 22, 5.6), (hw + 25, 4.6), (hw + 26, 0)], 'park', axis='w',
            at=(201, -11.5), seg=14)
    g.extrude([(42, -64), (68, -64), (68, -72, 4), (55, -80, 8), (42, -72, 4)], width=14, mat='park', bevel=0.8,
              holes=[[(51, -70), (59, -70), (59, -76), (51, -76)]], name='pintle')
    # rear sight: base, raised leaf with the aperture at the sight line, windage knob on the left
    g.extrude([(0, 48), (62, 48), (62, 53, 2), (56, 56, 2), (4, 56, 2), (0, 53)], width=26, mat='park', bevel=0.6,
              name='rsbase')
    leaf = g.extrude([(-8, 54), (8, 54), (8, 70, 3), (5, 73, 2), (-5, 73, 2), (-8, 70, 3)], 44, 51, 'park',
                     plane='front', bevel=0.4, name='rsleaf')
    g.cut(leaf, g.cyl(30, 60, 1.6, axis='u', at=(SIGHT_V, 0), cutter=True, seg=12))
    sl = g.extrude([(-6, 52), (6, 52), (6, 64), (-6, 64)], 42.5, 52.5, 'park', plane='front', bevel=0.3,
                   name='rsslide')
    g.cut(sl, g.cyl(30, 60, 2.0, axis='u', at=(SIGHT_V, 0), cutter=True, seg=12))
    g.lathe([(-13, 0), (-13, 7), (-24, 7), (-24, 0)], 'park', axis='w', at=(8, 63), seg=16)      # windage knob
    g.lathe([(-6, 0), (-6, 3), (-13, 3), (-13, 0)], 'park', axis='w', at=(8, 63), seg=10)

    # ---------------------------------------------------------------- top cover (part 'cover', hinged at the front)
    with g.part('cover'):
        cv = g.extrude([(100, 30), (304, 30), (304, 44), (300, 50, 2), (108, 50, 2), (100, 46)], width=REC_W - 2,
                       mat='park', bevel=0, name='cover')
        g.cut(cv, g.extrude([(-hw, 30), (hw, 30), (hw, 44), (hw - 5, 51), (-hw + 5, 51), (-hw, 44)], 90, 310,
                            plane='front', cutter=True, bevel=0), op='INTERSECT')
        _bev(cv, 0.8, 2)
        g.extrude([(282, 49), (303, 49), (303, 56, 2), (282, 57, 3)], width=22, mat='park', bevel=0.6,
                  name='feedlever')                                         # belt feed lever housing
        g.lathe([(49, 0), (49, 7), (56, 6.2), (57, 4), (57.5, 0)], 'park', axis='v', at=(206, 0), seg=14)  # latch
        g.box(104, 116, 44, 52, width=REC_W - 10, mat='park', bevel=0.6)                       # rear latch lip
    g.pivot('cover', 304, 44)
    g.lathe([(-hw - 2, 0), (-hw - 2, 3.2), (hw + 2, 3.2), (hw + 2, 0)], 'bright', axis='w', at=(304, 44), seg=12)

    # ---------------------------------------------------------------- barrel jacket, barrel, carrying handle
    jk = g.tube(344, 758, JR, JR - 1.6, 'park', seg=40, name='jacket')
    holes = []
    for j, phi in enumerate((29, 74, 119, 164)):
        off = 0 if j % 2 == 0 else 19.75
        for k in range(9):
            u = 393 + off + 39.5 * k
            c = g.cyl(-JR - 4, JR + 4, 6.4, axis='w', at=(u, 0), cutter=True, seg=12)
            g.transform(c, rot=('u', phi), pivot=(u, 0, 0))
            holes.append(c)
    g.cut(jk, *holes)
    g.lathe([(340, 0), (340, 11), (760, 10.5), (760, 0)], 'blued', seg=20, name='barrel')
    g.lathe([(344, 0), (344, JR + 0.5), (352, JR + 0.5), (352, 0)], 'park', seg=40)              # jacket rear ring
    # carrying handle: clamp band on the jacket and the upright handle plate
    g.tube(350, 388, JR + 2.5, JR - 0.5, 'park', seg=40, name='hband')
    hp = g.extrude([(350, 20), (388, 20), (388, 49, 3), (384, 52), (354, 52), (350, 49, 3)], width=8, mat='park',
                   bevel=0.8, name='handle')
    g.cut(hp, g.extrude(rrect(357, 380, 39, 46, 3), -10, 10, cutter=True, bevel=0))

    # ---------------------------------------------------------------- front barrel bearing, front sight, flash hider
    g.lathe([(756, 0), (756, 26.5), (848, 26.5), (848, 0)], 'park', seg=40, name='bearing')
    g.lathe([(757, 0), (757, 27.5), (764, 27.5), (764, 0)], 'park', seg=40)
    g.lathe([(846, 0), (846, 24.5), (862, 24.5), (862, 20.5), (877, 20.5), (877, 0)], 'park', seg=36, name='collar')
    fh = g.lathe([(875, 0), (875, 20.5), (994, 29), (997, 28), (997, 0)], 'park', seg=40, name='flashhider')
    g.cut(fh, g.cyl(900, 1010, 6.5, axis='u', cutter=True, seg=16))
    g.cut(fh, g.lathe([(930, 0), (930, 9), (998, 25), (998, 0)], seg=32, cutter=True))
    # front sight: base on the bearing, guard ears fore and aft, blade at the sight line
    g.extrude([(762, 24), (808, 24), (808, 34, 3), (762, 34, 3)], width=20, mat='park', bevel=0.8, name='fsbase')
    for u0, u1 in ((764, 777), (793, 806)):
        g.extrude([(u0, 33), (u1, 33), (u1, 51, 4), (u1 - 3, 56, 3), (u0 + 2, 56, 3), (u0, 50, 4)], width=12,
                  mat='park', bevel=0.6, name='fsear')
    g.extrude([(780, 33), (790, 33), (788, SIGHT_V), (783, SIGHT_V)], width=2.4, mat='park', bevel=0.3,
              name='fsblade')

    # ---------------------------------------------------------------- bipod (clamped under the bearing, legs down)
    g.extrude([(760, -18), (805, -18), (805, -50, 4), (798, -62, 4), (768, -62, 4), (760, -50, 4)], width=34,
              mat='park', bevel=1.0, name='bpyoke')
    g.lathe([(-20, 0), (-20, 7), (20, 7), (20, 0)], 'park', axis='w', at=(783, -50), seg=16)       # leg hinge
    for s in (1, -1):
        w0, w1 = 8 * s, 46 * s
        g.extrude([(767, -58), (799, -58), (797, -96, 4), (769, -96, 4)], w0 - 9, w0 + 9, 'park', bevel=1.0,
                  name='bpsleeve')
        lw = lambda v: w0 + (w1 - w0) * (-96 - v) / (-96 + 282)
        g.pipe([(782.5, -94, lw(-94)), (782.5, -282, w1)], 7.0, 'park', seg=14)
        g.pipe([(782.5, -100, lw(-100)), (782.5, -150, lw(-150))], 8.5, 'park', seg=14)
        foot = [(763, -279), (822, -276), (824, -287, 3), (812, -297, 4), (771, -297, 4), (763, -289, 3)]
        g.extrude(foot, w1 - 11, w1 + 11, 'park', bevel=1.0, name='bpfoot')
        # leg-lock wing levers
        g.extrude([(755, -82), (790, -104), (786, -112), (751, -90)], w0 + 9 * s, w0 + 15 * s, 'park', bevel=0.5)
        g.extrude([(790, -100), (818, -78), (823, -86), (795, -108)], w0 + 9 * s, w0 + 15 * s, 'park', bevel=0.5)
    g.extrude([(750, -122), (784, -106), (786, -114), (753, -130)], -26, -20, 'park', bevel=0.5)

    # ---------------------------------------------------------------- belt box (part 'mag', left side)
    with g.part('mag'):
        BW = -hw - 42
        box = g.extrude(rrect(176, 336, -142, -6, 6), BW - 36, BW + 36, 'paint', bevel=2.0, name='beltbox')
        g.extrude(rrect(186, 326, -132, -16, 6), BW - 38, BW - 35, 'paint', bevel=0.8)        # pressed panel
        for dv in (-50, -96):
            g.box(176.5, 335.5, dv - 2, dv + 2, BW - 34, BW + 34, 'paint', bevel=0.8)
        g.box(172, 340, -10, -4, BW - 38, BW + 38, 'paint', bevel=1.0)                        # lid rim
        g.pipe([(220, -4, BW), (220, 6, BW), (292, 6, BW), (292, -4, BW)], 2.4, 'bright', corner=5)   # bail
        g.box(196, 316, -60, -20, -hw - 6, -hw - 1, 'park', bevel=0.8)                          # mounting bracket
        # short belt from the box mouth up into the feedway (rounds lie along the bore)
        for w, v in ((-31, 14), (-41, 10), (-51, 4), (-60, -3), (-67, -11)):
            g.lathe([(222, 0), (222, 6.0), (224, 6.0), (224.5, 5.6), (225.5, 5.9), (284, 5.6), (290, 4.4),
                     (292, 4.2), (295, 4.1), (302, 2.6), (305, 0.8), (305.5, 0)], 'brass', axis='u', at=(v, w),
                    seg=10)
            g.box(236, 246, v - 6.6, v + 6.6, w - 3.5, w + 3.5, 'blued', bevel=0.3)
            g.box(266, 276, v - 6.6, v + 6.6, w - 3.5, w + 3.5, 'blued', bevel=0.3)
    g.pivot('mag', 256, -6, BW)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 997, 0)
    g.anchor('sight', 47.5, SIGHT_V)
    g.anchor('eject', 170, -64, 0)              # links and cases drop out of the bottom
    g.anchor('rh', -60, -62, 0)
    g.anchor('lh', 420, -28, 0)                 # under the jacket, ahead of the carrying handle
    g.anchor('eye', -230, SIGHT_V)
