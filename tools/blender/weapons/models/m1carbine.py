"""M1 Carbine. Reference: M1 Carbine Mk I - USA - Armemuseum noBG croped.jpg (right side). 904 mm, parkerised steel,
walnut stock with the sling slot (oiler as sling retainer) and handguard, adjustable aperture rear sight, 15-round
box magazine ('mag', drops straight down)."""
import math

from ..lib import hull_circles, rrect, section
from .m1garand import knurl, pin, screw, smooth_edge

REF = 'm1carbine'
META = {'kind': 'rifle'}

SIGHT_V = 22.0      # top of the front blade = centre of the rear aperture (clears the handguard)
BARREL_END = 571.5


def build(g):
    # ---------------------------------------------------------------- stock
    region = [(-326, 40), (-27, 40), (-27, 0.3), (395, 0.3), (395, -22.8), (341, -22.8), (341, -45), (110, -45),
              (110, -34.6), (64, -34.6), (64, -38.4), (-17, -38.4), (-17, -46), (-60, -200), (-326, -200)]
    stock = g.outline(region)
    stock = smooth_edge(stock, -322, -112, lambda u: -60, 'bottom', deg=1)        # straight butt toe line
    stock = smooth_edge(stock, -322, -150, lambda u: -60, 'top', deg=1)           # comb
    stock = smooth_edge(stock, 116, 336, lambda u: -15, 'bottom', deg=2)          # forend
    st = g.sweep(stock, 'walnut', width=[(-326, 40), (-220, 38.5), (-140, 33), (-100, 30.5), (-50, 31), (-25, 34),
                                          (0, 36), (120, 36), (250, 34), (340, 32), (395, 29)],
                 radius=(8, 9), step=4, n=3, round_ends=(0, 3.0), name='stock')
    # sling slot through the butt; the oiler sits in it as the sling retainer
    slot = hull_circles([(-297.6, -49.5, 5.6), (-291.6, -107.5, 5.6)], n=24)
    # band spring recess on the right of the forend
    spr = rrect(311, 346, -11.6, -5.6, 2.9)
    g.cut(st, g.extrude(slot, -30, 30, cutter=True, bevel=0), g.extrude(spr, 14.2, 30, cutter=True, bevel=0),
          solver='FLOAT')
    a = math.degrees(math.atan2(-107.5 + 49.5, -291.6 + 297.6))
    oil = g.lathe([(0, 0), (0, 4.4), (0.8, 5.0), (8, 5.0), (8.6, 4.6), (52, 4.6), (52.8, 5.0), (58, 5.0), (58.6, 4.2),
                   (58.6, 0)], 'blued_old', at=(0, 0), seg=16, name='oiler')
    g.transform(oil, rot=('w', a), move=(-297.6, -49.3, 0))
    # butt plate (steel) + its screw
    bp = g.outline([(-345, 40), (-324.6, 40), (-324.6, -200), (-345, -200)])
    g.sweep(bp, 'park', width=40, radius=(8, 9), step=2, n=3, name='buttplate')

    # ---------------------------------------------------------------- handguard
    hg = [(137, 1.0), (137, 21.0, 1.5), (336, 18.6, 3), (342, 16.8, 2), (342, 1.0)]
    h = g.sweep(hg, 'walnut', width=[(137, 29), (342, 28)], radius=(9, 1.5), step=4, n=3, round_ends=(1.0, 1.0),
                name='handguard')
    g.cut(h, g.box(130, 226, -2, 9.9, 8.6, 25, cutter=True, bevel=0), solver='FLOAT')     # op-slide channel (right)
    for u in (143, 157):
        pin(g, u, 19.0, 11.6, r=1.3, h=0.3, mat='park')                                 # handguard liner rivets

    # ---------------------------------------------------------------- receiver
    rec = [(-29, -9), (122, -9), (122, 9.6), (100, 9.6), (91, 8.8), (41.5, 8.8), (40, 10.2), (-22, 10.2, 3),
           (-29.5, 5.6)]
    rv = g.sweep(rec, 'park', width=25, radius=(8.5, 2), step=2.5, n=4, round_ends=(2.0, 0), name='receiver')
    # ejection port (top right), bolt seen through it
    g.cut(rv, g.box(42, 90, 3.0, 14, 0, 16, cutter=True, bevel=0), solver='FLOAT')
    g.lathe([(30, 0), (30, 6.4), (31, 7.0), (95, 7.0), (96, 6.2), (96, 0)], 'park', at=(2.2, 0), seg=24, name='bolt')
    g.box(55, 75, 7.5, 9.0, 1.5, 4.0, mat='park', bevel=0.3)                          # extractor
    # bolt handle: round knob on the right
    g.lathe([(9, 0), (9, 3.4), (13.5, 3.4), (14, 5.2), (17.2, 5.2), (17.8, 4.4), (17.8, 0)], 'park', axis='w',
            at=(95, 7.2), seg=20, name='boltknob')
    # receiver ring around the chamber
    g.lathe([(100, 0), (100, 10.6), (102, 11.2), (122, 11.2), (123, 10.6), (123, 0)], 'park', at=(0, 0), seg=32,
            name='ring')

    # ---------------------------------------------------------------- operating slide (right side)
    slide = [(100.5, 1.0), (100.5, 9.6), (107, 19.2, 1.5), (113, 20.0, 1.0), (133, 20.0, 1.2), (136.5, 17.5),
             (134.5, 15.5), (134.5, 9.8), (213, 9.8), (219, 7.0), (226, 2.6), (226, 0.5), (135, 0.5), (130, 1.0)]
    g.extrude(slide, 10.2, 13.6, 'park', bevel=0.5, name='opslide')
    g.extrude([(100.5, 8), (134.5, 8), (134.5, 19.4), (113, 19.4, 1.0), (107.5, 18.8, 1.2), (100.5, 9.8)], 10.2,
              16.5, 'park', bevel=0.8, name='handle')                                 # handle block
    g.box(124, 132, 12, 18.5, 16.0, 17.6, mat='park', bevel=0.4)                     # finger tab

    # ---------------------------------------------------------------- rear sight (adjustable, aperture)
    base = [(-12, 9.5), (20.5, 9.5), (20.5, 11.2), (17, 14.2), (-12, 14.2)]
    g.extrude(base, width=17, mat='park', bevel=0.6, name='sightbase')
    # slide cheeks (left / right of the sight line), aperture plate with the peep at SIGHT_V
    cheek = [(-14, 14), (16.5, 14), (16.5, 20.2), (14, 24.4, 1), (0, 24.4), (-1, 27.4, 0.6), (-12.5, 27.4, 1.5),
             (-14, 25)]
    for s in (1, -1):
        g.extrude(cheek, s * 3.6, s * 6.8, 'park', bevel=0.4, name='cheek')
    ap = g.extrude([(7.4, 14), (10.6, 14), (10.6, 26.5), (9.9, 28.6, 0.6), (8.1, 28.6, 0.6), (7.4, 26.5)],
                   width=9.4, mat='park', bevel=0.3, name='aperture')
    g.cut(ap, g.cyl(5, 13, 1.15, at=(SIGHT_V, 0), seg=16, cutter=True, chamfer=0))
    g.lathe([(10.5, 1.15), (10.5, 2.6), (11.0, 2.6), (11.0, 1.15)], 'park', at=(SIGHT_V, 0), seg=16, closed=True,
            name='peep')
    # windage drum on the right, screw end on the left
    drum = g.lathe([(6.8, 0), (6.8, 4.9), (7.3, 5.4), (11.2, 5.4), (11.7, 4.9), (11.7, 0)], 'park', axis='w',
                   at=(-5.6, 21.0), seg=32, name='drum')
    knurl(g, drum, -5.6, 21.0, 6.3, 12.2, 5.4, n=26, depth=0.4, width=0.6)
    g.lathe([(11.7, 0), (11.7, 3.8), (12.2, 3.4), (12.2, 0)], 'bright', axis='w', at=(-5.6, 21.0), seg=24)
    g.box(-12, 0, 13.8, 18.5, -3.6, 3.6, mat='park', bevel=0.5)                      # windage block (below line)
    g.lathe([(-6.8, 0), (-6.8, 2.6), (-8.0, 2.2), (-8.0, 0)], 'park', axis='w', at=(-5.6, 21.0), seg=14)
    pin(g, 4.0, 12.0, 8.5, r=1.2, h=0.3)

    # ---------------------------------------------------------------- barrel, band, front sight
    g.lathe([(122, 0), (122, 9.4), (150, 9.0), (240, 8.2), (345, 7.6), (430, 7.2), (BARREL_END - 0.6, 6.7),
             (BARREL_END, 6.1), (BARREL_END, 0)], 'park', seg=32, name='barrel')
    g.lathe([(BARREL_END - 0.2, 0), (BARREL_END - 0.2, 3.85), (BARREL_END + 0.01, 3.85),
                    (BARREL_END + 0.01, 0)], 'black', seg=16, name='bore')
    # forend nose ahead of the band is part of the stock trace; barrel band (rear lip + main band)
    lip = section(30.5, 33, 38.6, 10, 8, y0=-24.7)
    g.extrude(lip, 341.6, 347, 'park', plane='front', bevel=0.5, name='bandlip')
    band = section(21, 32, 34.4, 9.5, 8, y0=-24.7)
    g.extrude(band, 346.5, 365.2, 'park', plane='front', bevel=0.7, name='band')
    g.lathe([(14.5, 0), (14.5, 2.4), (15.6, 1.9), (15.8, 0)], 'park', axis='w', at=(357.5, -8.2), seg=12)  # spring stud
    # band spring (right) inside its recess
    g.extrude(rrect(312, 345, -11.0, -6.2, 2.3), 13.4, 15.0, 'park', bevel=0.4, name='bandspring')
    # sling swivel lug + swivel screw under the band
    g.box(350.5, 364.5, -28.0, -24.0, -5, 5, mat='park', bevel=0.8)
    sw = g.lathe([(-6, 0), (-6, 4.6), (-5, 5.0), (5, 5.0), (6, 4.6), (6, 0)], 'park', axis='w', at=(357.5, -29.6),
                 seg=20, name='swivelpin')
    for k in range(3):
        c = g.box(350, 365, -30.8 + k * 1.6 - 0.35, -30.8 + k * 1.6 + 0.35, 5.2, 7, cutter=True, bevel=0)
        g.cut(sw, c)
    # front sight: collar on the barrel, two protective ears, blade between them
    g.lathe([(540.8, 0), (540.8, 8.4), (541.8, 9.2), (561.8, 9.2), (562.6, 8.4), (562.6, 0)], 'park', at=(-0.6, 0),
            seg=28, name='fscollar')
    ear = [(540.6, 4.0), (543.4, 14.0, 3), (548.0, 21.6, 2.0), (560.6, 21.6, 1.6), (562.6, 19.5), (562.6, 4.0)]
    fs = g.extrude(ear, width=9.4, mat='park', bevel=0.4, name='fsears')
    g.cut(fs, g.box(538, 566, 13.0, 25, -1.6, 1.6, cutter=True, bevel=0),
          g.cyl(-8, 8, 1.0, axis='w', at=(552, 10.5), seg=12, cutter=True, chamfer=0))
    g.extrude([(549.0, 12), (556.0, 12), (556.0, SIGHT_V - 0.4), (555.2, SIGHT_V), (550.6, SIGHT_V),
               (549.0, SIGHT_V - 1.6)], width=1.8, mat='park', bevel=0.2, name='blade')
    pin(g, 552, 10.5, 4.7, r=0.95, h=0.2)

    # ---------------------------------------------------------------- trigger housing, guard, trigger
    th = [(-18.5, -38.2), (64, -38.2), (64, -48.5), (61, -51.5), (41, -51.5), (31, -44), (-14, -41.2, 1),
          (-18.5, -40.2)]
    g.extrude(th, width=21, mat='park', bevel=0.6, name='trighousing')
    gd, holes = g.outline([(-14, -40.5), (34, -40.5), (34, -73), (-14, -73)], holes=True)
    g.extrude(gd, width=8.5, mat='park', holes=holes, bevel=0.6, name='guard')
    g.extrude([(-0.2, -40.8), (3.4, -40.8), (4.6, -48), (6.6, -55), (8.0, -61), (7.4, -64.6), (5.8, -63.2),
               (3.2, -56), (0.8, -49)], width=4.6, mat='park', bevel=0.5, name='trigger')
    # safety (cross-bolt, right) and magazine catch (knurled, right)
    g.lathe([(10.5, 0), (10.5, 4.2), (11.4, 4.0), (11.8, 3.2), (11.8, 0)], 'park', axis='w', at=(37.3, -46.3), seg=20,
            name='safety')
    mc = g.lathe([(10.5, 0), (10.5, 4.0), (12.8, 4.0), (13.2, 3.4), (13.2, 0)], 'park', axis='w', at=(57.3, -42.4),
                 seg=20, name='magcatch')
    knurl(g, mc, 57.3, -42.4, 10, 14, 4.0, n=14, depth=0.5, width=0.7)
    pin(g, 9.0, -44.5, 10.6, r=1.4, h=0.3)
    pin(g, 47.0, -47.0, 10.6, r=1.4, h=0.3)

    # ---------------------------------------------------------------- magazine (15 rounds)
    with g.part('mag'):
        mag = [(64.6, -31), (110, -31), (110, -100), (109.4, -100.6), (65.2, -100.6), (64.6, -100)]
        g.extrude(mag, width=19.2, mat='blued', bevel=0.6, name='mag')
        g.extrude(rrect(64.2, 110.4, -103.0, -99.6, 1.2), width=20.6, mat='blued', bevel=0.4, name='floor')
        for u in (67.2, 70.2, 93.6, 97.0, 105.6):                                  # pressed stiffening ribs
            for s in (1, -1):
                g.box(u - 0.6, u + 0.6, -97.5, -36, s * 9.4, s * 10.1, mat='blued', bevel=0.25)
        g.box(105, 109, -43, -38, -10.0, 10.0, mat='blued', bevel=0.3)                 # catch notch lug
    g.pivot('mag', 87.3, -31, 0)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', BARREL_END, 0)
    g.anchor('sight', 9.0, SIGHT_V)
    g.anchor('eject', 66, 8, 10)
    g.anchor('rh', -72, -48, 0)
    g.anchor('lh', 210, -14, 0)
    g.anchor('eye', -270, SIGHT_V)
