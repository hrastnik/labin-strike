"""FG 42, 2nd model (Type G): wooden stock, near-vertical wooden pistol grip, stamped receiver, folding bipod under
the barrel, annular-groove muzzle brake. Reference: 'Fallschirmjaegergewehr 42 noBG.png' (CC BY-SA 4.0), the upper
of the two rifles (crop). The photo has its sights folded; the model shows them erect (diopter drum at the rear,
post at the front) so the ADS sight line works. 975 mm.

Magazine ('mag' part): 20-round box inserted from the LEFT (hidden behind the receiver in the right-side
silhouette), removed along -w (magDir [-1, 0, 0]). Pivot at its inner end."""
import math

from ..lib import clean, offset_poly, rrect, section

REF = 'fg42'
META = {'kind': 'rifle', 'client': {'magDir': [-1, 0, 0]}}
SIGHT_V = 47.0           # aperture centre of the rear diopter = top of the front post
GRIP_A = -107.0          # pistol grip axis (deg from +u)


def build(g):
    # ---------------------------------------------------------------- stock (wood) + steel butt plate
    stock = g.outline([(-400, -150), (-150, -150), (-150, 40), (-400, 40)])
    g.sweep(stock, 'walnut', width=[(-385, 42), (-300, 40), (-220, 35), (-150, 31)], radius=(9, 8), top=0.86,
            step=4, round_ends=(0, 0), name='stock')
    plate = g.outline([(-400, 40), (-377.5, 40), (-367.5, -150), (-400, -150)])
    g.sweep(plate, 'blued_old', width=43, radius=(9, 8), top=0.86, step=3, name='buttplate')
    for v in (-20, -108):                                     # butt plate screws (on the slanted plate)
        ur = -380 + max(0, -17 - v) * 10 / 110
        g.lathe([(ur + 1.0, 0), (ur + 1.0, 3.2), (ur - 0.4, 2.6), (ur - 0.9, 0)], 'blued_old', axis='u',
                at=(v, 0), seg=10)

    # ---------------------------------------------------------------- receiver (steel)
    g.extrude(section(27, 28, 58.6, 3, 2, 3, y0=-49), -151, -90, 'phosphate', plane='front', bevel=0.8,
              name='rec_rear')
    g.extrude(section(24, 28, 4, 2, 0.5, 2, y0=9), -93, -86, 'phosphate', plane='front', bevel=0.5)
    rec = g.extrude(section(28, 30, 67, 4, 2, 3, y0=-50), -90, 28, 'phosphate', plane='front', bevel=0.8,
                    name='receiver')
    g.extrude(section(22, 26, 3, 1.5, 0.5, 2, y0=16), -21, 25, 'phosphate', plane='front', bevel=0.5)  # cover top
    g.extrude(section(30, 32, 68, 5, 2, 3, y0=-51), 27, 112, 'phosphate', plane='front', bevel=0.8,
              name='frontrec')
    g.box(63, 79, -61.5, -48, width=14, mat='phosphate', bevel=1.0)                 # mag-catch lug underneath
    # pressed ribs along the sides of the receiver
    for v in (-4.5, -12.5, -20.5, -37):
        for w0, w1 in ((14.6, 15.6), (-15.6, -14.6)):
            g.box(-87, -14, v - 1.5, v + 1.5, w0, w1, mat='phosphate', bevel=0.4)
    # ejection port cover (right) and the cocking handle (right, on the operating rod)
    g.extrude(rrect(14, 84, -9, 12, 2), 15.4, 16.8, 'phosphate', bevel=0.5, name='portcover')
    g.cyl(15, 28, 3.6, 'phosphate', axis='w', at=(92, -38), seg=14)
    g.lathe([(26, 0), (26, 6.5), (30, 7), (33, 6), (34, 0)], 'phosphate', axis='w', at=(92, -38), seg=16)
    # pins (both sides)
    for u, v, r in ((-120, -20, 2.4), (-120, -40, 2.4), (-70, -30, 2.6), (-30, -44, 2.4), (8, -44, 2.4),
                    (45, -30, 2.4), (98, -14, 2.2)):
        for sgn in (1, -1):
            w0 = 13.6 if u < -90 else (14.7 if u < 28 else 15.6)
            g.lathe([(sgn * w0, 0), (sgn * w0, r), (sgn * (w0 + 1.0), r * 0.8), (sgn * (w0 + 1.3), 0)],
                    'phosphate', axis='w', at=(u, v), seg=10)
    # magazine housing on the left side
    g.box(-2, 96, -16, 16, -31, -14, mat='phosphate', bevel=1.2, name='magwell')

    # ---------------------------------------------------------------- trigger housing, guard, trigger
    housing, holes = g.outline([(-96, -40), (32, -40), (32, -108), (-30, -108), (-40, -95), (-40, -68),
                                (-96, -68)], holes=True)
    housing = clean(housing, eps=0.3)
    holes = [clean(h, eps=0.3) for h in holes]
    g.extrude(housing, width=21, mat='phosphate', holes=holes, bevel=1.0, name='housing')
    trig = [(-6, -60), (0, -60), (0.2, -68), (1.4, -76), (3.0, -84, 1.0), (1.4, -86), (-1.0, -82), (-2.6, -74),
            (-4.5, -66)]
    g.extrude(trig, width=6, mat='blued', bevel=0.5, name='trigger')
    g.lathe([(10.5, 0), (10.5, 4.5), (12, 4), (12.5, 0)], 'blued', axis='w', at=(-62, -58), seg=14)    # selector
    g.lathe([(-10.5, 0), (-10.5, 4.5), (-12, 4), (-12.5, 0)], 'blued', axis='w', at=(-62, -58), seg=14)

    # ---------------------------------------------------------------- pistol grip (wood)
    grip = g.outline([(-125, -64), (-30, -64), (-36, -96), (-60, -172), (-125, -172)])
    g.sweep(grip, 'walnut', width=[(0, 26), (60, 30), (100, 31)], radius=7, axis=GRIP_A, origin=(-62, -64), step=4,
            name='grip')
    g.lathe([(14.5, 0), (14.5, 3.4), (15.8, 2.8), (16.2, 0)], 'blued', axis='w', at=(-80, -118), seg=12)
    g.lathe([(-14.5, 0), (-14.5, 3.4), (-15.8, 2.8), (-16.2, 0)], 'blued', axis='w', at=(-80, -118), seg=12)

    # ---------------------------------------------------------------- handguard (wood) with its front ring
    hg = g.extrude(section(38, 42, 65, 9, 6, 3, y0=-48.5), 111, 201, 'walnut', plane='front', bevel=0.8,
                   name='handguard')
    for k in range(13):                                     # cooling slots (dark inserts, both sides)
        u = 116 + k * 6.6
        for w0, w1 in ((20.2, 21.3), (-21.3, -20.2)):
            g.box(u, u + 3.0, -27, -19, w0, w1, mat='black', bevel=0)
    g.extrude(section(40, 42, 75, 8, 6, 3, y0=-56), 200, 218, 'phosphate', plane='front', bevel=1.0,
              name='hgring')

    # ---------------------------------------------------------------- barrel, gas cylinder, bipod
    g.lathe([(110, 0), (110, 7.3), (430, 6.6), (505, 6.4), (505, 0)], 'blued', seg=28, name='barrel')
    g.lathe([(215, 0), (215, 9), (470, 9), (470, 0)], 'phosphate', at=(-16.3, 0), seg=20, name='gascyl')
    sleeve = section(26, 30, 48, 7, 6, 3, y0=-41)
    g.extrude(sleeve, 217, 237, 'phosphate', plane='front', bevel=0.8, name='sleeve')
    g.extrude(section(24, 30, 48.5, 7, 6, 3, y0=-41), 236, 267, 'phosphate', plane='front', bevel=0.8)
    g.box(267, 279, 4, 9, width=8, mat='phosphate', bevel=0.6)                       # bayonet catch
    g.pipe([(271, 8, 0), (276, 15.5, 0)], 1.0, 'phosphate', seg=8)
    for w in (9.5, -9.5):                                                            # folded bipod legs + feet
        g.pipe([(262, -32.5, w), (470, -32.5, w)], 7.2, 'phosphate', seg=12)
        g.extrude([(238, -38), (264, -38), (264, -43), (256, -50), (249, -52.5), (243, -51), (238, -45)],
                  w - 4, w + 4, 'phosphate', bevel=0.8)
    g.box(465, 480, -39, -9, width=30, mat='phosphate', bevel=1.2, name='bipodclamp')
    g.box(468, 477, -51, -38, width=9, mat='phosphate', bevel=0.8)
    g.cyl(-16, 16, 3.0, 'phosphate', axis='w', at=(472, -32.5), seg=12)

    # ---------------------------------------------------------------- front sight (erect post) and base
    base = [(430, -10), (433, 6), (443, 16.5), (447, 19.5), (501, 19.5), (502, 17), (506, 17), (506, -12),
            (497, -12), (497, -24), (480, -24), (480, -10)]
    g.extrude(base, width=24, mat='phosphate', bevel=0.8, name='fsbase')
    g.extrude([(446, 19), (482, 19), (482, 26), (478, 28), (450, 28)], width=12, mat='phosphate', bevel=0.6)
    for w0, w1 in ((4.0, 7.0), (-7.0, -4.0)):                                       # protecting ears
        g.extrude([(464, 26), (479, 26), (479, 31.5), (476, 32), (466, 30.5)], w0, w1, 'phosphate', bevel=0.4)
    post = [(450, 26), (458, 26), (457, 31), (455.4, 40), (455.2, SIGHT_V), (452.8, SIGHT_V), (452.6, 40),
            (451, 31)]
    g.extrude(post, width=1.8, mat='blued', bevel=0.3, name='post')

    # ---------------------------------------------------------------- muzzle brake (annular grooves)
    prof = [(503, 0), (503, 12.6), (512, 12.6)]
    for k in range(9):
        c = 517.5 + 7.5 * k
        prof += [(c - 3.0, 12.0), (c - 1.2, 14.0), (c + 1.2, 14.0), (c + 3.0, 12.0)]
    prof += [(581, 12.2), (586, 13.4), (590, 12.4), (592.5, 9.5), (593, 7.0), (593, 0)]
    g.lathe(prof, 'blued', seg=32, name='brake')
    g.tube(585, 593.2, 5.0, 4.1, 'black', seg=16)

    # ---------------------------------------------------------------- rear sight: base + erect diopter drum
    g.extrude([(-66, 16), (-21, 16), (-21, 24), (-23, 25), (-30, 25), (-31, 29.5, 1), (-64, 29.5, 1), (-66, 27)],
              width=20, mat='phosphate', bevel=0.8, name='rsbase')
    g.extrude([(-50, 29), (-33, 29), (-33.5, 31.2), (-49.5, 31.2)], width=14, mat='phosphate', bevel=0.5)
    stem = [(-60.5, 29), (-53.5, 29), (-54.2, SIGHT_V - 4), (-59.8, SIGHT_V - 4)]
    g.extrude(stem, width=10, mat='blued', bevel=0.5, name='diopter_stem')
    ring = g.cyl(-60.5, -53.5, 6.0, 'blued', at=(SIGHT_V, 0), seg=24, name='diopter')
    g.cut(ring, g.cyl(-70, -40, 2.6, at=(SIGHT_V, 0), cutter=True, seg=16))
    g.lathe([(7, 0), (7, 2.5), (9.5, 2.5), (10, 0)], 'blued', axis='w', at=(-42, 24), seg=14)     # range knob

    # ---------------------------------------------------------------- magazine (left side)
    with g.part('mag'):
        g.box(4, 90, -12.5, 12.5, -150, -20, mat='blued', bevel=1.0, name='mag')
        g.box(2.5, 91.5, -14, 14, -155, -149, mat='blued', bevel=1.0, name='floorplate')
        for v in (-5, 5):                                                          # pressed ribs (front face)
            g.box(12, 82, v - 1.2, v + 1.2, -146, -34, mat='blued', bevel=0.4)
        for u in (20, 74):
            g.box(u - 1.5, u + 1.5, 12, 13.2, -146, -34, mat='blued', bevel=0.4)
    g.pivot('mag', 47, 0, -20)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 593, 0)
    g.anchor('sight', -57, SIGHT_V)
    g.anchor('eject', 48, 2, 16)
    g.anchor('rh', -72, -105, 0)
    g.anchor('lh', 160, -40, 0)
    g.anchor('eye', -330, SIGHT_V)
