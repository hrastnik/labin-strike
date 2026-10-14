"""Bren Mk II light machine gun. Reference: 'BREN GM MK II 1971 Bangladesh Liberation War Arms.jpg' (museum display,
left side, muzzle right; CC BY-SA 4.0) via REF 'bren_photo'. The red display panel is segmented by colour
(cal/bren_photo.json "mask_color"); the raised carrying handle, the frame and the plaque are erased from the mask.
1156 mm, parkerised body, walnut butt and grip, 30-round curved magazine on TOP, sights offset 34 mm to the left
(leaf rear sight raised, blade front sight on a bracket), downward ejection, conical flash hider, bipod folded back
under the gas cylinder (as in the photo), carrying handle folded down on the right of the barrel."""
import math

from ..lib import bevel as _bev, hull_circles, rrect

REF = 'bren_photo'
META = {'kind': 'rifle', 'client': {'magDir': [0, 1, 0]}}

SIGHT_V = 48.0      # aperture centre = front blade top
SW = -34.0          # sight line offset (left of the bore)
BW = 42.0           # body width
GV = -33.0          # gas cylinder axis


def screw(g, u, v, w, r=3.0, mat='park', side=1):
    w0 = w * side
    w1 = (w + 1.3) * side
    prof = [(w0, 0), (w0, r), ((w + 0.9) * side, r * 0.85), (w1, r * 0.4), (w1, 0)]
    return g.lathe(prof, mat, axis='w', at=(u, v), seg=12)


def both(g, fn, *a, **kw):
    fn(g, *a, side=1, **kw)
    fn(g, *a, side=-1, **kw)


def arc_pts(c, r, p0, p1, n):
    """points on the circle (centre c, radius r) from the angle of p0 to the angle of p1."""
    a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    a1 = a0 + (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * k / n), c[1] + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + 1)]


def build(g):
    # ---------------------------------------------------------------- butt (walnut) + butt plate
    so = [(-404, -118, 3), (-340, -106), (-284, -99, 10), (-262, -80, 14), (-236, -64, 14), (-200, -54, 10),
          (-178, -53, 6), (-160, -58), (-146, -60), (-146, 0), (-160, -1), (-185, -4.5, 8), (-215, -7, 10),
          (-245, -6.5, 10), (-268, 1, 10), (-290, 7, 8), (-340, 10.5), (-390, 13.5), (-406, 15, 5), (-412.5, -20),
          (-409.5, -60), (-403.5, -100)]
    g.sweep(so, 'walnut', width=[(-430, 44), (-300, 42), (-250, 34), (-150, 34)], radius=(9, 11), top=0.9,
            step=4, round_ends=(2, 0), name='butt')
    # hinged shoulder strap at the heel of the butt
    g.extrude([(-409, -44), (-383, -44, 2), (-381, -94, 2), (-403, -96), (-406, -70)], width=45, mat='park', bevel=0.8,
              name='buttstrap2')
    # butt plate (follows the traced rear edge)
    bp = [(-413, 9, 3), (-406, 10), (-406.5, -20), (-403.5, -60), (-397, -100), (-395, -117), (-401.5, -117),
          (-403.5, -100), (-410.5, -60), (-413.5, -20)]
    g.extrude(bp, width=46, mat='park', bevel=1.0, name='buttplate')
    for v in (-10, -80):
        g.lathe([(-406, 0), (-406, 3.2), (-404, 2.6), (-404, 0)], 'park', at=(v, 0), seg=10)
    # metal butt strap / return spring housing showing along the wrist
    g.box(-272, -148, -45, -21, width=35, mat='park', bevel=1.2, name='buttstrap')
    both(g, screw, -262, -33, 17.5, r=3.0)
    # sling swivel under the butt
    g.lathe([(-6, 0), (-6, 7.5), (6, 7.5), (6, 0)], 'park', axis='w', at=(-296, -98), seg=16)
    g.pipe([(-296, -104, 0), (-290, -112, 0), (-296, -118, 0), (-302, -112, 0), (-296, -104, 0)], 1.8, 'park',
           seg=8, corner=3)

    # ---------------------------------------------------------------- body
    bo = [(-150, -60), (-150, 9), (-146, 13, 3), (-140, 16), (-112, 16), (-105, 23), (-98, 30, 3), (-90, 32.5, 3),
          (30, 33.5), (140, 33.5), (163, 33.5), (166, 22, 1.5), (196, 21.5), (207, 19), (212, 15), (212, -64, 2),
          (-96, -64), (-100, -61), (-150, -60)]
    body = g.extrude(bo, width=BW, mat='park', bevel=0, name='body')
    # ejection opening (downward) and the cocking handle slot (right)
    hw = BW / 2
    g.cut(body, g.box(50, 150, -70, -56, -11, 11, cutter=True, bevel=0),                  # ejection opening (bottom)
          g.box(-62, 206, -31.5, -24.5, hw - 4, hw + 3, cutter=True, bevel=0),           # cocking handle slot (right)
          g.box(-110, 48, -37, -24, -hw - 3, -hw + 1.6, cutter=True, bevel=0),           # slide groove (left)
          g.box(-150, -100, -12, -9.5, -hw - 3, hw + 3, cutter=True, bevel=0))           # butt-joint seam
    _bev(body, 1.2, 3)
    g.box(56, 144, -60, -57, -10, 10, mat='black', bevel=0)                         # bolt seen through the port
    g.box(-60, 204, -30.5, -25.5, hw - 4, hw - 3, mat='black', bevel=0)            # slot floor (piston post)
    g.box(32, 48, -35.5, -25.5, -hw + 0.6, -hw - 1.2, 'bright', bevel=0.5)          # slide block in the groove
    # butt-group collar where the body meets the butt (stepped joint)
    g.extrude(rrect(-hw - 1.2, hw + 1.2, -62, 12, 4), -154, -147, 'park', plane='front', bevel=0.8, name='buttcollar')
    # body locking pin (head left, retaining ring right)
    g.lathe([(-hw - 4, 0), (-hw - 4, 5.6), (-hw - 2.6, 6.0), (-hw, 4.6), (hw + 1.5, 3.2), (hw + 1.5, 0)], 'bright',
            axis='w', at=(-130, 6), seg=16)
    g.cut(g.lathe([(-hw - 4.5, 0), (-hw - 4.5, 1.6), (-hw - 2, 1.6), (-hw - 2, 0)], 'park', axis='w', at=(-130, 6),
                  seg=10), g.box(-140, -120, 5.4, 6.6, -hw - 6, -hw - 3, cutter=True, bevel=0))
    g.lathe([(hw + 1, 0), (hw + 1, 5.0), (hw + 3, 5.0), (hw + 3, 0)], 'park', axis='w', at=(-130, 6), seg=14)
    # barrel-nut catch plunger at the front top-left of the body
    g.lathe([(163, 0), (163, 5.2), (166, 6.2), (194, 6.2), (196, 5), (196, 0)], 'bright', at=(15, -hw + 2), seg=14)
    # longitudinal side panels / grooves of the body
    for s in (1, -1):
        g.box(-98, 150, -13, -11, s * (BW / 2), s * (BW / 2 + 0.8), 'park', bevel=0.3)
    for u, v in ((-20, -50), (100, -50), (150, -42), (-104, 2), (160, 8)):
        both(g, screw, u, v, BW / 2, r=2.2)
    both(g, screw, -60, -52, BW / 2, r=2.4)
    both(g, screw, 75, 4, BW / 2, r=2.2)
    both(g, screw, 196, 4, BW / 2, r=2.6)
    # cocking handle (right side, forward position): stem in the slot, hinge, handle folded forward along the body
    g.box(188, 200, -30.5, -25.5, hw - 4, hw + 5, 'park', bevel=0.6, name='ckstem')
    g.lathe([(-6, 0), (-6, 4.2), (6, 4.2), (6, 0)], 'park', axis='v', at=(194, hw + 7.5), seg=14)
    g.extrude([(186, -33), (224, -33, 3), (230, -30, 3), (230, -25, 3), (224, -22, 3), (186, -23, 3)], hw + 5,
              hw + 10, 'park', bevel=1.0, name='ckhandle')
    for u in (206, 212, 218):
        g.box(u, u + 2, -32, -23.5, hw + 9.6, hw + 10.4, 'park', bevel=0)                   # finger grooves
    # body locking lug under the front of the body
    g.extrude([(172, -60), (196, -60), (194, -76, 6), (185, -83, 6), (176, -78, 5)], width=16, mat='park', bevel=0.8,
              name='lug')
    # barrel latch lever sloping down onto the barrel nut
    g.extrude([(164, 27), (172, 32), (183, 39, 2), (190, 38.5, 2), (205, 22, 3), (222, 17), (224, 13), (210, 13),
               (198, 20), (188, 26)], -12, 2, 'park', bevel=0.8, name='latch')
    g.lathe([(-13, 0), (-13, 3.4), (3, 3.4), (3, 0)], 'bright', axis='w', at=(168, 29), seg=12)       # latch pivot
    # gas cylinder housing / piston tube in front of the body
    g.extrude([(206, 6), (214, 4, 4), (224, -6, 10), (236, -22, 8), (264, -26), (264, -60), (206, -64)], width=30,
              mat='park', bevel=1.0, name='gashousing')
    g.box(218, 266, -26, -10, width=20, mat='park', bevel=1.0, name='barrelnutblock')   # behind the fillet
    both(g, screw, 246, -36, 15, r=2.4)
    both(g, screw, 222, -50, 15, r=2.4)
    # magazine opening lips and the magazine catch lever behind the magazine
    g.box(26, 134, 31, 36.5, width=34, mat='park', bevel=0.8, name='maglips')
    g.extrude([(17, 33), (24, 33), (22, 44), (16.5, 60, 1.5), (12.5, 61, 1.5), (13, 57), (18, 43)], width=8, mat='park',
              bevel=0.5, name='magcatch')
    g.box(14, 26, 30, 36, width=16, mat='park', bevel=0.6)

    # ---------------------------------------------------------------- rear sight (left, raised leaf with aperture)
    g.extrude([(-104, 25), (8, 25), (8, 33.5), (-98, 33.5, 2)], SW - 6, -BW / 2 + 2, 'park', bevel=0.8,
              name='rsbase')                                                       # sight arm along the body top
    # range drum on the arm (knurled), turned by the thumb
    g.lathe([(-17, 0), (-17, 5.0), (-16, 6.2), (-14, 6.2), (-13.4, 5.6), (-12.6, 6.2), (-10.6, 6.2), (-10, 5.6),
             (-9.4, 6.2), (-7.4, 6.2), (-6.8, 5.6), (-6.2, 6.2), (-4.2, 6.2), (-3, 5.0), (-3, 0)], 'park',
            at=(30.5, SW + 2), seg=20, name='rsdrum')
    g.cyl(-22, 2, 2.2, 'bright', at=(30.5, SW + 2), seg=10)                       # drum spindle
    g.extrude([(-50, 33), (-34, 33), (-36, 37, 2), (-48, 37, 2)], SW - 4, SW + 4, 'park', bevel=0.6)  # slide
    for s in (1, -1):                                                              # leaf hinge ears
        g.box(-100, -86, 33, 39, SW + s * 6.5, SW + s * 9.5, 'park', bevel=0.5)
    g.lathe([(SW - 10, 0), (SW - 10, 2.2), (SW + 10, 2.2), (SW + 10, 0)], 'park', axis='w', at=(-93, 36), seg=12)
    leaf = g.extrude([(-95, 34), (-90, 34), (-90.5, SIGHT_V + 4.5, 2), (-95.5, SIGHT_V + 4.5, 2)], SW - 6, SW + 6,
                     'park', bevel=0.4, name='rleaf')
    ring = g.cyl(-95, -90, 4.6, axis='u', at=(SIGHT_V, SW), seg=20, chamfer=0.4)
    g.cut(leaf, g.cyl(-100, -85, 2.2, axis='u', at=(SIGHT_V, SW), seg=16, cutter=True))      # game-sized peep
    g.cut(ring, g.cyl(-100, -85, 2.2, axis='u', at=(SIGHT_V, SW), seg=16, cutter=True))

    # ---------------------------------------------------------------- barrel, carrying handle, regulator, flash hider
    g.lathe([(194, 0), (194, 14.5), (222, 14.5), (225, 12), (225, 0)], 'park', seg=28, name='barrelnut')
    g.lathe([(222, 0), (222, 11.6), (530, 11.2), (650, 11.6), (650, 0)], 'park', seg=28, name='barrel')
    fh = g.lathe([(648, 0), (648, 12.0), (734, 16.6), (737, 15.4), (737, 0)], 'park', seg=32, name='flash')
    g.cut(fh, g.cyl(705, 745, 5.2, cutter=True, seg=18))
    for u in (262, 300, 402):                                                     # barrel pins / dimples
        g.cyl(-11.9, 11.9, 1.5, 'black', axis='w', at=(u, 3), seg=10, chamfer=0)
    # carrying handle socket (perforated block) and the handle folded down on the right
    hs = g.extrude(rrect(-14, 14, -19, 17, 4), 318, 362, 'park', plane='front', bevel=0, name='handlesock')
    g.cut(hs, *[g.cyl(-20, 20, 4.2, axis='w', at=(u, 6), seg=14, cutter=True) for u in (328, 340, 352)])
    _bev(hs, 0.8, 2)
    g.pipe([(340, 12, 12), (340, 10, 24), (338, 2, 34), (330, -4, 38)], 3.5, 'park', seg=10, corner=6)
    g.pipe([(330, -4, 38), (318, -5, 40)], 4.5, 'park', seg=10)
    g.lathe([(196, 0), (196, 8.6), (204, 10.5), (300, 10.5), (308, 9.2), (318, 6.5), (318, 0)], 'walnut', seg=16,
            at=(-5, 40), name='handle')
    # gas cylinder, bipod clamp ring, regulator with its key
    g.lathe([(262, 0), (262, 13.5), (534, 13.5), (534, 0)], 'park', at=(GV, 0), seg=24, name='gascyl')
    for u in (402, 412, 422, 432):                                               # cooling holes
        for v in (GV - 3, GV + 4):
            for sd in (1, -1):
                g.lathe([(sd * 12.2, 0), (sd * 12.2, 1.7), (sd * 13.3, 1.7), (sd * 13.3, 0)], 'black', axis='w', at=(u, v),
                        seg=8)
    g.extrude(hull_circles([(0, 0, 12.5), (0, GV, 15.6)], n=36), 462, 500, 'park', plane='front', bevel=0.6, name='bpclamp')
    for s in (1, -1):
        g.cyl(min(s * 13, s * 18), max(s * 13, s * 18), 4.5, 'park', axis='w', at=(481, GV), seg=12)
    g.extrude(hull_circles([(0, 2, 14.2), (0, GV, 13.0), (0, -37, 12.6)], n=48), 532, 576, 'park', plane='front',
              bevel=1.2, name='regulator')
    g.lathe([(-13, 0), (-13, 9.5), (-16, 9.5), (-16, 0)], 'bright', axis='w', at=(553, -34), seg=20)
    k = g.box(546, 560, -38, -30, -18.5, -15.5, 'bright', bevel=0.6)
    g.transform(k, rot=('w', -40), pivot=(553, -34, 0))
    # keel under the gas cylinder (piston tube rib) with its pins
    g.extrude([(240, -40), (500, -40), (500, -66, 4), (400, -70, 6), (370, -67, 6), (246, -64, 4)], width=18, mat='park',
              bevel=0.8, name='keel')
    both(g, screw, 366, -50, 9, r=2.4)
    both(g, screw, 398, -55, 9, r=2.6)
    # front sight: band, bracket to the left, blade with ears
    g.lathe([(590, 0), (590, 14.2), (615, 14.2), (615, 0)], 'park', seg=24, name='fsband')
    g.extrude([(-6, 8), (-4, 15), (SW + 4, 25), (SW - 4, 25), (SW - 6, 19), (-12, 6)], 594, 613, 'park',
              plane='front', bevel=0.8, name='fsbracket')
    for s in (1, -1):
        g.extrude([(597, 23), (613, 23), (612, SIGHT_V + 1, 3), (599, SIGHT_V + 1, 3)], SW + s * 3.5, SW + s * 6,
                  'park', bevel=0.4, name='fsear')
    g.extrude([(601, 23), (610, 23), (609, SIGHT_V, 0.6), (603, SIGHT_V, 0.6)], SW - 0.7, SW + 0.7, 'park', bevel=0.2,
              name='fblade')

    # ---------------------------------------------------------------- bipod (folded back under the gas cylinder)
    # yoke clamped on the gas cylinder, two tubular legs (upper tube + telescoped lower section, clamp collar with
    # its lock lever, spade foot). Folded back as in the photo: the near (left) leg lies a little higher than the far
    # one, both splaying out sideways toward the feet.
    g.extrude([(496, -40), (540, -40), (543, -62, 6), (534, -80, 6), (502, -78, 4)], width=24, mat='park',
              bevel=0.8, name='bpyoke')
    g.lathe([(-24, 0), (-24, 4.2), (24, 4.2), (24, 0)], 'park', axis='w', at=(528, -64), seg=12)    # hinge pin
    for s, top, mid, end, uc in ((-1, (528, -70), (340, -80), (222, -102), 340),
                                 (1, (522, -79.5), (350, -95), (232, -109), 350)):
        wa, wb, wc = s * 9, s * 15, s * 19
        for k in (0, 1):
            g.box(512, 538, -76, -58, s * (5 + k * 9), s * (9 + k * 9), 'park', bevel=0.6)     # leg knuckle
        g.pipe([(top[0], top[1], wa), (mid[0], mid[1], wb)], 7.0, 'park', seg=14, name='bpleg')
        g.pipe([(mid[0] + 2, mid[1] - 0.2, wb), (end[0], end[1], wc)], 6.4, 'park', seg=12, name='bpleg2')
        # clamp collar at the joint and its lock lever
        g.transform(g.lathe([(uc - 9, 0), (uc - 9, 8.6), (uc + 9, 8.6), (uc + 9, 0)], 'park',
                            at=(mid[1] + (end[1] - mid[1]) * (uc - mid[0]) / (end[0] - mid[0]), wb), seg=16),
                    rot=('w', math.degrees(math.atan2(mid[1] - top[1], mid[0] - top[0])) + 180),
                    pivot=(uc, mid[1], wb))
        if s < 0:
            g.extrude([(uc - 52, -84), (uc - 48, -70, 2), (uc - 40, -68.5, 2), (uc - 24, -69.5, 2), (uc - 25, -74, 2),
                       (uc - 38, -76), (uc - 44, -82), (uc - 40, -86)], wb - 12, wb - 9, 'park', bevel=0.4, name='bplever')
        # spade foot (vertical when folded) with its toe claw
        if s < 0:      # near foot: curved spade, toe forward
            fp = [(209, -60), (222, -60, 3), (238, -68, 6), (242, -92, 6), (250, -106, 4), (258, -112, 2),
                  (256, -120, 2), (228, -123, 3), (217, -108, 5), (211, -94, 5), (209, -78)]
        else:          # far foot, a little forward and higher
            fp = [(216, -62), (246, -62, 2), (248, -70, 4), (246, -92, 6), (254, -104, 3), (252, -112, 2),
                  (234, -114, 3), (222, -100, 5), (217, -80)]
        g.extrude(fp, wc - 3.5, wc + 3.5, 'park', bevel=0.6, name='bpfoot')
        g.cyl(min(wc - 6, wc + 6), max(wc - 6, wc + 6), 6.0, 'park', axis='w', at=(end[0], end[1]), seg=14)

    # ---------------------------------------------------------------- pistol grip, guard, trigger, change lever
    go = g.outline([(-100, -62), (-26, -62), (-26, -180), (-100, -180)])
    g.sweep(go, 'walnut', width=30, radius=(7, 9), top=0.95, step=3, round_ends=(0, 3), name='grip')
    def ring(r):
        a0 = math.asin(min(1.0, 18.0 / r))
        return [(9 + r * math.cos(a), -80 + r * math.sin(a))
                for a in [a0 - k * (math.pi + 2 * a0) / 24 for k in range(25)]]
    gi_ = ring(16.0)
    go_ = [(29.5, -62)] + ring(20.5) + [(-11.5, -62), (-11.5, -60), (29.5, -60)]
    g.extrude(go_, width=9, mat='park', holes=[gi_[:-1]], bevel=0.6, name='guard')
    g.extrude([(-34, -62), (-8, -62), (-8, -70), (-10, -88, 4), (-20, -97, 4), (-30, -92), (-34, -78)], width=18,
              mat='park', bevel=0.8, name='trighousing')
    g.extrude([(-6, -63), (0, -63), (1.5, -72), (0.5, -82, 3), (-4, -88), (-3.5, -80), (-5, -71)], width=5,
              mat='park', bevel=0.4, name='trigger')
    # change lever (A / R / S) on the left above the grip: boss, lever lying back along the trigger group
    g.lathe([(-hw, 0), (-hw, 6.5), (-hw - 2.5, 6.5), (-hw - 3, 5), (-hw - 3, 0)], 'park', axis='w', at=(-48, -58),
            seg=16)
    g.extrude([(-94, -55), (-50, -54, 3), (-28, -64, 2), (-31, -68, 2), (-52, -61, 3), (-94, -60, 2)], -hw - 5.5,
              -hw - 3, 'park', bevel=0.5, name='changelever')
    for k, u in enumerate((-86, -76, -66)):                                       # A / R / S index marks
        g.box(u, u + 1.4, -51, -47, -hw - 0.6, -hw + 0.2, 'bright', bevel=0)

    # ---------------------------------------------------------------- magazine (part 'mag', on top)
    BC, BR = (259.1, 49.2), 229.1          # back edge arc
    FC, FR = (280.9, 36.9), 155.7          # front edge arc
    with g.part('mag'):
        back = arc_pts(BC, BR, (30.5, 30), (116, 228), 18)
        front = arc_pts(FC, FR, (189, 167), (125.2, 30), 14)
        mp = back + [(130, 231.5, 5), (142, 231), (189, 166, 4)] + front[1:]
        g.extrude(mp, width=29, mat='park', bevel=1.4, name='mag')
        # pressed ribs along the curve, both sides
        for d in (13.0, 19.0):
            pts = arc_pts(BC, BR - d, (34, 45), (112, 222), 14)
            for s in (1, -1):
                g.pipe([(u, v, s * 14.4) for u, v in pts], 1.3, 'park', seg=6)
        g.box(28, 128, 30, 38, width=31, mat='park', bevel=0.6)                    # feed-lip housing
    g.pivot('mag', 78, 34)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 737, 0)
    g.anchor('sight', -92.5, SIGHT_V, SW)
    g.anchor('eject', 100, -64, 0)
    g.anchor('rh', -62, -110, 0)
    g.anchor('lh', 230, -45, 0)
    g.anchor('eye', -370, SIGHT_V, SW)
