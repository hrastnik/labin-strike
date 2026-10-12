"""MG 42. Reference: MG42 1 noBG.jpg (left side of the gun, mirrored by the rectifier; the sling is erased from the
mask via cal/mg42.json "mask_erase"). 1220 mm, stamped receiver with a hinged feed cover, perforated barrel jacket
with a muzzle booster, bakelite stock and grip panels, bipod (one leg down, one folded back as in the photo),
50-round belt drum on the left as the 'mag' part."""
import math
import os

from ..lib import arc, hull_circles, rrect, section

REF = 'mg42'
META = {'kind': 'rifle', 'hide_in_ref': [] if os.environ.get('SHOWMAG') else ['mag']}

SIGHT_V = 70.0      # sight line: rear notch bottom = front post top


def screw(g, u, v, w, r=3.0, mat='paint', side=1, slot=False):
    """round screw / rivet head on a side face at |w| (side = +1 right, -1 left)."""
    w0 = w * side
    w1 = (w + 1.4) * side
    prof = [(w0, 0), (w0, r), ((w + 0.9) * side, r * 0.85), (w1, r * 0.4), (w1, 0)]
    return g.lathe(prof, mat, axis='w', at=(u, v), seg=12)


def both(g, fn, *a, **kw):
    fn(g, *a, side=1, **kw)
    fn(g, *a, side=-1, **kw)


def build(g):
    # ---------------------------------------------------------------- stock (black bakelite) + band
    stock = g.outline([(-430, -110), (-262, -110), (-262, 60), (-430, 60)])
    g.sweep(stock, 'black', width=[(-430, 44), (-380, 42), (-300, 38), (-262, 38)], radius=(9, 8), top=0.85,
            step=4, name='stock')
    g.extrude(section(40, 40, 60, 8, 6, 4, y0=-37), -268, -252, 'bright', plane='front', bevel=0.6, name='band')

    # ---------------------------------------------------------------- receiver (body below the cover seam)
    REC_W = 46
    g.extrude(section(REC_W - 2, REC_W - 2, 61, 4, 5, 4, y0=-40), -253, -182, 'paint', plane='front', bevel=0.6,
              name='rec_rear')
    rec = g.extrude(section(REC_W, REC_W, 44, 2, 5, 4, y0=-38.5), -182, 176, 'paint', plane='front', bevel=0.6,
                    name='receiver')
    # feed tray block under the cover front, with the belt slot through both sides
    tray = g.extrude([(52, 3), (152, 3), (152, 30), (52, 30)], -REC_W / 2, REC_W / 2, 'paint', bevel=0.8,
                     name='tray')
    g.cut(tray, g.extrude(rrect(62, 146, 7, 25, 2), -40, 40, cutter=True, bevel=0))
    g.box(56, 148, 1, 9, -REC_W / 2 + 1, REC_W / 2 - 1, 'bright', bevel=0.4)            # feed tray floor (lip)
    # front block (barrel trunnion / cover hinge housing)
    g.extrude([(150, -38), (180, -38), (180, 24), (176, 30), (170, 37, 2), (150, 37, 2)], width=REC_W + 2,
              mat='paint', bevel=1.0, name='trunnion')
    g.lathe([(-REC_W / 2 - 2.5, 0), (-REC_W / 2 - 2.5, 3.5), (REC_W / 2 + 2.5, 3.5), (REC_W / 2 + 2.5, 0)],
            'bright', axis='w', at=(158, 32), seg=14)                                     # cover hinge pin
    # side rivets / screws
    for u, v in ((-158, -8), (-75, -8), (8, -10), (120, -21), (-205, -15)):
        both(g, screw, u, v, REC_W / 2, r=3.4)
    # bolt guide rail and the lower strips
    g.box(45, 150, -41, -36, width=10, mat='bright', bevel=0.6)
    g.box(-245, -195, -49, -40, width=14, mat='paint', bevel=0.8)                       # rear bottom bracket
    g.box(-195, -170, -46, -40, width=12, mat='paint', bevel=0.6)
    # charging handle (right side, forward position) and its slot
    g.cut(rec, g.box(-20, 150, -16, -10, REC_W / 2 - 2, 30, cutter=True, bevel=0))
    g.box(126, 146, -18, -8, REC_W / 2 - 3, REC_W / 2 + 4, 'paint', bevel=0.8)
    g.lathe([(REC_W / 2 + 3, 0), (REC_W / 2 + 3, 5.5), (REC_W / 2 + 18, 6.2), (REC_W / 2 + 21, 5.2),
             (REC_W / 2 + 22, 0)], 'paint', axis='w', at=(136, -13), seg=14)
    # rear sling loop on top
    g.pipe([(-186, 19, 0), (-186, 30, 0), (-177, 36, 0), (-168, 30, 0), (-168, 19, 0)], 2.2, 'paint', corner=4)
    # safety (cross bolt) above the grip
    g.lathe([(-28, 0), (-28, 4.5), (28, 4.5), (28, 0)], 'paint', axis='w', at=(-52, -46), seg=14)

    # ---------------------------------------------------------------- feed cover (part 'cover', front hinge)
    with g.part('cover'):
        cov = g.outline([(-184, 5), (160, 5), (160, 60), (-184, 60)])
        cv = g.extrude(cov, width=REC_W - 2, mat='paint', bevel=0, name='cover')
        g.cut(cv, g.extrude(section(REC_W - 2, REC_W - 2, 60, 9, 0.5, 5, y0=-12), -200, 170, plane='front', bevel=0,
                            cutter=True), op='INTERSECT')
        from ..lib import bevel as _bev
        _bev(cv, 0.8, 2)
        # three feed-pawl rivets on top of the front block
        for u in (88, 112, 136):
            g.lathe([(36, 0), (36, 6), (41, 5), (43, 3), (43.5, 0)], 'paint', axis='v', at=(u, -10), seg=14)
        g.lathe([(26, 0), (26, 5), (32, 4.2), (33, 0)], 'bright', axis='v', at=(-128, 0), seg=16)  # latch button
        g.box(-182, -172, 18, 30, width=REC_W - 6, mat='paint', bevel=0.8)                     # rear latch lip
    g.pivot('cover', 158, 32)

    # ---------------------------------------------------------------- barrel jacket
    jacket = section(46, 46, 54, 15, 9, 5, y0=-31)
    jk = g.extrude(jacket, 176, 700, 'paint', plane='front', bevel=0.8, name='jacket')
    cut = []
    for u0 in (316, 393, 470, 547):
        cut.append(g.extrude(rrect(u0, u0 + 58, -8.5, 8.5, 8.4), -40, 40, cutter=True, bevel=0))
    cut.append(g.cyl(-40, 40, 9.0, axis='w', at=(632, 0), cutter=True, seg=20))
    # square port (barrel catch window)
    cut.append(g.box(258, 268, -9, 9, -40, 40, cutter=True, bevel=0))
    g.cut(jk, *cut)
    # barrel inside the jacket (seen through the holes)
    g.lathe([(170, 0), (170, 9.5), (700, 9.0), (700, 0)], 'blued', at=(0, 0), seg=20, name='barrel')
    # jacket nose: tapers into the booster
    nose = []
    for i, (u, s) in enumerate(((698, 1.0), (712, 0.93), (726, 0.88))):
        sec = section(46 * s, 46 * s, 54 * s, 15 * s, 9 * s, 5, y0=-31 * s + (1 - s) * -4)
        nose.append([(u, y, x) for x, y in sec])
    g.loft(nose, 'paint', name='nose')
    # muzzle booster: perforated cup, ribbed sleeve, flared cone
    boo = g.lathe([(722, 0), (722, 22.5), (724, 23.5), (744, 23.5), (744, 0)], 'paint', at=(-0.5, 0), seg=32,
                  name='booster')
    holes = []
    for k in range(8):
        a = k * 45 + 22.5
        c = g.cyl(0, 30, 3.2, axis='w', at=(734, 0), cutter=True, seg=10)
        g.transform(c, rot=('u', a), pivot=(0, -0.5, 0))
        holes.append(c)
    g.cut(boo, *holes)
    g.lathe([(743, 0), (743, 24), (746, 24.5), (747, 22), (749, 22), (750, 24.5), (752, 24.5), (753, 22),
             (755, 22), (756, 24), (757, 24), (757, 0)], 'paint', at=(-0.5, 0), seg=32)
    g.lathe([(756, 0), (756, 10.5), (762, 9.5), (796, 14.5), (797.5, 13.8), (797.5, 0)], 'blued', at=(-0.5, 0),
            seg=28, name='cone')
    g.tube(780, 798, 7.5, 6.0, 'blued', at=(-0.5, 0), seg=20)

    # ---------------------------------------------------------------- sights
    # rear: base block, graduated leaf, notch blade (sight line at SIGHT_V)
    g.extrude([(212, 22), (302, 22), (302, 42, 2), (296, 45, 2), (222, 45, 2), (212, 38, 2)], width=24,
              mat='paint', bevel=0.8, name='rsbase')
    g.extrude([(216, 46), (296, 46), (296, 49), (222, 54, 2), (216, 53)], width=16, mat='paint', bevel=0.4,
              name='leaf')
    for u in range(232, 292, 4):
        g.box(u, u + 1.4, 50, 54.2 - (u - 222) * 0.06, width=17, mat='bright', bevel=0)
    g.lathe([(-12, 0), (-12, 7.5), (12, 7.5), (12, 0)], 'paint', axis='w', at=(222, 44), seg=18)   # slider wheel
    blade = g.extrude([(206, 40), (213, 40), (213, SIGHT_V + 5), (206, SIGHT_V + 5)], width=12, mat='paint',
                      bevel=0.4, name='rblade')
    g.cut(blade, g.extrude([(-1.5, SIGHT_V + 6), (1.5, SIGHT_V + 6), (1.2, SIGHT_V), (-1.2, SIGHT_V)], 200, 220,
                           plane='front', cutter=True, bevel=0))
    # front: collar on the jacket and the folding post
    g.extrude([(612, 18), (660, 18), (660, 27, 3), (612, 27, 3)], width=30, mat='paint', bevel=0.8, name='fscollar')
    for u in (634, 650):
        both(g, screw, u, 22.5, 15, r=2.0)
    g.extrude([(622, 24), (640, 24), (640, SIGHT_V - 4, 3), (637, SIGHT_V), (632, SIGHT_V), (632, 56),
               (626, 52), (626, 34), (622, 30)], width=6, mat='paint', bevel=0.4, name='fpost')

    # ---------------------------------------------------------------- trigger group, grip, guard
    housing = [(-132, -36), (-36, -36), (-36, -62), (-55, -62), (-108, -60), (-128, -62), (-132, -54)]
    g.extrude(housing, width=26, mat='paint', bevel=1.0, name='housing')
    both(g, screw, -112, -50, 13, r=4.0, mat='bright')
    both(g, screw, -73, -50, 13, r=3.6, slot=True)
    guard, holes = g.outline([(-34, -36), (54, -36), (54, -104), (-34, -104)], holes=True)
    g.extrude(guard, width=14, mat='paint', holes=holes, bevel=1.2, name='guard')
    trig = [(-1, -42), (8, -42), (10, -52), (9, -64), (5, -74), (-2, -82), (-6, -84), (-3, -78), (1, -70),
            (2, -60), (-1, -50)]
    g.extrude(trig, width=7, mat='blued', bevel=0.6, name='trigger')
    grip = g.outline([(-95, -38), (-28, -38), (-28, -100), (-50, -168), (-95, -168)])
    g.sweep(grip, 'paint', width=24, radius=6, axis=-112, origin=(-55, -40), step=3, name='gripframe')
    from ..lib import offset_poly
    panel = offset_poly(grip, -3.0)
    g.sweep(panel, 'bakelite', width=31, radius=(4, 4), axis=-112, origin=(-55, -40), step=2.5, t0=6, t1=112,
            name='grippanel')
    for u, v in ((-58, -78), (-82, -140)):
        both(g, screw, u, v, 15.5, r=3.2, mat='blued')
    g.lathe([(-14, 0), (-14, 5), (14, 5), (14, 0)], 'bright', axis='w', at=(-102, -152), seg=12)   # sling bar

    # ---------------------------------------------------------------- bipod (left leg down, right leg folded)
    g.extrude([(596, -28), (656, -28), (656, -44, 3), (596, -44, 3)], width=40, mat='paint', bevel=0.8,
              name='bpclamp')
    g.lathe([(-20, 0), (-20, 10), (20, 10), (20, 0)], 'paint', axis='w', at=(636, -50), seg=20)        # hinge
    g.lathe([(-25, 0), (-25, 8), (-20, 8), (-20, 0)], 'bright', axis='w', at=(636, -50), seg=16)
    # down leg (left, -w): tube with a latch strip and a foot plate
    LW = -14
    g.pipe([(636, -50, LW), (640.5, -160, LW), (651, -260, LW), (657, -334, LW)], 11.0, 'paint', seg=16)
    yoke = g.outline([(604, -44), (662, -44), (662, -138), (604, -138)])
    g.extrude(yoke, LW - 9, LW + 9, 'paint', bevel=1.2, name='yoke')
    g.box(640, 649, -152, -60, LW - 12, LW - 7, 'paint', bevel=0.5)
    g.box(612, 650, -208, -192, LW - 11, LW - 6, 'paint', bevel=0.5)
    foot = g.outline([(640, -322), (705, -322), (705, -370), (640, -370)])
    g.extrude(foot, LW - 12, LW + 10, 'paint', bevel=1.0, name='foot')
    # folded leg (right, +w): points back under the jacket
    RW = 14
    g.pipe([(630, -42, RW), (600, -54, RW), (574, -68, RW)], 8.0, 'paint', seg=14)
    pad = g.outline([(528, -48), (586, -48), (586, -92), (528, -92)])
    g.extrude(pad, RW - 10, RW + 10, 'paint', bevel=1.0, name='pad')

    # sling swivel under the jacket
    g.box(492, 516, -33, -29, width=12, mat='paint', bevel=0.5)
    sw, swh = g.outline([(486, -30), (526, -30), (526, -76), (486, -76)], holes=True)
    g.extrude(sw, width=4, mat='paint', holes=swh, bevel=0.6, name='swivel')

    # ---------------------------------------------------------------- belt drum (part 'mag', left side)
    with g.part('mag'):
        DW = -REC_W / 2 - 38
        drum = [(52, -10), (150, -10), (154, -18, 6), (154, -118, 14), (52, -118, 14), (48, -18, 6)]
        g.extrude(drum, DW - 30, DW + 30, 'paint', bevel=2.5, name='drum')
        g.extrude(rrect(60, 146, -112, -18, 10), DW - 32, DW - 29, 'paint', bevel=0.8)     # pressed lid panel
        for dv in (-40, -64, -88):
            g.box(48.5, 153.5, dv - 2, dv + 2, DW - 28, DW + 28, 'paint', bevel=0.8)       # pressed ribs
        g.pipe([(70, -10, DW), (70, 2, DW), (132, 2, DW), (132, -10, DW)], 2.4, 'bright', corner=5)  # carry bail
        g.lathe([(DW - 33, 0), (DW - 33, 6), (DW - 30, 6), (DW - 30, 0)], 'bright', axis='w', at=(140, -100), seg=12)
        # short belt from the drum mouth up into the feed tray (rounds lie along the bore)
        for w, v in ((-27, 16), (-36.5, 12), (-45.5, 6.5), (-53.5, -0.5), (-60, -8)):
            g.lathe([(60, 0), (60, 6.0), (62, 6.0), (62.5, 5.6), (63.5, 5.9), (120, 5.6), (126, 4.4), (128, 4.2),
                     (131, 4.1), (138, 2.6), (141, 0.8), (141.5, 0)], 'brass', axis='u', at=(v, w), seg=10)
            g.box(72, 82, v - 6.6, v + 6.6, w - 3.5, w + 3.5, 'blued', bevel=0.3)       # link
            g.box(104, 114, v - 6.6, v + 6.6, w - 3.5, w + 3.5, 'blued', bevel=0.3)
    g.pivot('mag', 100, 2, -REC_W / 2 - 8)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 797.5, -0.5)
    g.anchor('sight', 210, SIGHT_V)
    g.anchor('eject', 100, -38, 0)              # spent cases drop out of the bottom
    g.anchor('rh', -62, -95, 0)
    g.anchor('lh', 240, -36, 0)               # under the jacket, just ahead of the receiver
    g.anchor('eye', -90, SIGHT_V)
