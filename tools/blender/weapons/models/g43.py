"""Gewehr 43. Reference: Gewehr 43 noBG.jpg (two views; the top one, right side, is used via the cal crop).
1130 mm, phosphated receiver, blued barrel, beech stock and upper handguard (gas cylinder above the barrel under it),
hooded front sight, tangent rear sight, operating-rod assembly with its spring on top of the receiver front,
cocking handle on the left, 10-round detachable magazine ('mag', drops straight down)."""
import math

from ..lib import hull_circles, rrect, section
from .m1garand import knurl, pin, screw, smooth_edge

REF = 'g43'
META = {'kind': 'rifle'}

SIGHT_V = 33.5      # top of the front post (centre of the hood) = centre of the rear notch
MUZZLE = 778.5
ROD_W = 5.5         # the operating-rod assembly sits right of the sight line


def build(g):
    # ---------------------------------------------------------------- stock
    region = [(-344.2, 10), (-55, 10), (-55, -8.6), (64, -8.6), (64, 2.8), (563, 2.8), (563, -60), (212, -60),
              (212, -43.5), (101, -43.5), (101, -54.6), (-26, -54.6), (-40, -200), (-333.3, -200)]
    stock = g.outline(region)
    stock = smooth_edge(stock, -330, -130, lambda u: -60, 'bottom', deg=1)        # toe line
    stock = smooth_edge(stock, -338, -150, lambda u: -60, 'top', deg=2)           # comb
    stock = smooth_edge(stock, 215, 558, lambda u: -15, 'bottom', deg=2)          # forend
    st = g.sweep(stock, 'beech', width=[(-344, 44), (-250, 42), (-150, 36.5), (-100, 32), (-60, 33), (-40, 36),
                                         (0, 38), (120, 38), (300, 36), (450, 34.5), (563, 33)],
                 radius=(8, 10), step=4, n=3, round_ends=(0, 2.0), name='stock')
    # sling slot in the butt: shallow cup each side with a slot through; spring slot near the nose cap (right)
    cup = rrect(-193, -164, -71, -36, 4)
    g.cut(st, g.extrude(cup, 18.0, 30, cutter=True, bevel=0), g.extrude(cup, -30, -18.0, cutter=True, bevel=0),
          g.extrude(rrect(-184.5, -176.5, -66, -41, 3.8), -30, 30, cutter=True, bevel=0),
          g.extrude(rrect(527, 566, -12.5, -5.8, 3.0), 15.0, 30, cutter=True, bevel=0), solver='FLOAT')
    g.extrude(rrect(-185.5, -175.5, -67, -40, 4.2), -18.6, 18.6, 'blued_old', bevel=0.3, name='slotliner')
    g.extrude(rrect(528, 562, -11.8, -6.5, 2.4), 14.2, 16.0, 'phosphate', bevel=0.4, name='capspring')
    # butt plate (steel) with its side screw
    bp = g.outline([(-380, 10), (-344.2, 10), (-333.3, -200), (-380, -200)])
    g.sweep(bp, 'bright', width=44.5, radius=(8, 10), step=2, n=3, name='buttplate')
    for s in (1, -1):
        screw(g, -352, -63, s * 21.6, r=2.4, h=0.7, side=s, mat='bright')
    # escutcheon + cross screw through the stock
    for s in (1, -1):
        g.lathe([(s * 18.2, 0), (s * 18.2, 6.6), (s * 19.0, 6.3), (s * 19.4, 5.4), (s * 19.4, 0)], 'phosphate',
                axis='w', at=(226, -15), seg=24, name='escutcheon')
        for dv in (-2.2, 2.2):
            g.cyl(s * 19.0, s * 19.6, 0.9, 'black', axis='w', at=(226 + dv * 0.3, -15 + dv), seg=8, chamfer=0)

    # ---------------------------------------------------------------- upper handguard (gas cylinder inside)
    g.cyl(283, 580, 8.2, 'phosphate', at=(15.0, 0), seg=20, chamfer=0, name='gascyl')
    hg = [(283, 3.0), (283, 30.4, 1.5), (548, 31.2, 6), (562, 27.0, 2), (562, 3.0)]
    h = g.sweep(hg, 'beech', width=[(283, 33), (562, 31)], radius=(10, 1.5), step=4, n=3, round_ends=(1.0, 1.0),
                name='handguard')
    g.cut(h, *[g.extrude(rrect(u0, u0 + 16, 15.0, 19.5, 1.8), -30, 30, cutter=True, bevel=0) for u0 in (484, 521)],
          solver='FLOAT')

    # ---------------------------------------------------------------- receiver
    low = [(-48, -8.4), (65, -8.4), (65, 3.6), (-48, 3.6)]
    g.sweep(low, 'phosphate', width=29, radius=(1.5, 3), step=3, n=2, round_ends=(1.5, 1.0), name='rec_low')
    up = [(-50, 3.4), (100, 3.4), (100, 15.2), (58, 15.2), (56, 16.7), (-45, 16.7, 2), (-50, 12)]
    g.sweep(up, 'phosphate', width=26, radius=(6, 1), step=3, n=3, round_ends=(2.0, 0), name='rec_up')
    # rear spur and cover latch
    g.extrude([(-58, -10), (-47, -10), (-47, -4.5), (-56, -4.5, 1.5)], width=14, mat='phosphate', bevel=0.8)
    g.lathe([(-47, 0), (-47, 2.0), (-43, 2.0), (-43, 0)], 'phosphate', axis='u', at=(19.5, 0), seg=12)
    g.box(-47.5, -42.5, 15, 19.5, -2.5, 2.5, mat='phosphate', bevel=0.6)
    # ejection-port edge / bolt carrier groove line on the right, carrier step
    g.box(-44, 56, 7.0, 8.0, 12.6, 13.4, mat='phosphate', bevel=0.2)
    g.box(10, 22, -7.6, 3.2, 14.2, 15.0, mat='phosphate', bevel=0.3)
    # receiver front / gas-rod housing
    fr = [(100, 3.4), (282, 3.4), (282, 24.6, 1.5), (197, 24.6), (177, 23.0), (132, 19.6), (132, 15.2), (100, 15.2)]
    g.sweep(fr, 'phosphate', width=26, radius=(8, 1), step=3, n=3, round_ends=(0, 1.0), name='rec_front')
    # cocking handle (left)
    ch = g.lathe([(-13, 0), (-13, 3.0), (-19, 3.0), (-19.6, 4.4), (-24, 4.4), (-24.8, 3.6), (-24.8, 0)], 'phosphate',
                 axis='w', at=(32, 9.5), seg=18, name='cockhandle')
    knurl(g, ch, 32, 9.5, -25.5, -19.3, 4.4, n=16, depth=0.5, width=0.7)
    # operating-rod assembly on top: rear lug + spring guide disc, rod with its spring, front lug
    g.extrude([(197, 22), (197, 36), (199.4, 40), (203, 40), (205, 34), (205, 22)], ROD_W - 2.5, ROD_W + 2.5,
              'phosphate', bevel=0.4, name='rodlug_r')
    g.lathe([(ROD_W - 2.6, 0), (ROD_W - 2.6, 5.3), (ROD_W + 2.6, 5.3), (ROD_W + 2.6, 0)], 'phosphate', axis='w',
            at=(210.5, 33.4), seg=24, name='springdisc')
    g.lathe([(ROD_W + 2.6, 0), (ROD_W + 2.6, 1.6), (ROD_W + 3.2, 1.2), (ROD_W + 3.2, 0)], 'phosphate', axis='w',
            at=(210.5, 33.4), seg=12)
    g.cyl(212, 270, 1.6, 'blued', at=(30.8, ROD_W), seg=12, name='rod')
    spring = []
    pitch, rr = 2.0, 2.9
    n = int((262 - 215) / pitch * 12)
    for k in range(n + 1):
        t = 2 * math.pi * k / 12
        spring.append((215 + pitch * k / 12, 30.8 + rr * math.cos(t), ROD_W + rr * math.sin(t)))
    g.pipe(spring, 0.55, 'blued', seg=6, name='spring')
    g.extrude([(262, 22), (262, 32.5), (265, 36.6, 2.5), (276, 36.6, 2.5), (282, 30), (282, 22)], ROD_W - 3.5,
              ROD_W + 3.5, 'phosphate', bevel=0.5, name='rodlug_f')
    g.lathe([(ROD_W + 3.3, 0), (ROD_W + 3.3, 1.7), (ROD_W + 3.8, 1.4), (ROD_W + 3.8, 0)], 'phosphate', axis='w',
            at=(271, 32.5), seg=12)

    # ---------------------------------------------------------------- rear sight (tangent leaf + slider)
    g.extrude([(100, 3), (121, 3), (121, 32.4, 1), (102, 32.4, 1.5), (100, 30)], width=17, mat='phosphate',
              bevel=0.6, name='rsbase')
    leaf = g.extrude([(121, 15), (131.6, 15), (131.6, 33.5), (129.6, 35.6, 1), (123, 35.6, 1), (121, 33.5)],
                     width=16, mat='phosphate', bevel=0.4, name='rsleaf')
    g.cut(leaf, g.box(118, 135, SIGHT_V - 1.6, 40, -1.2, 1.2, cutter=True, bevel=0), solver='FLOAT')
    # elevation slider wheel on the right of the base
    wh = g.lathe([(8.5, 0), (8.5, 5.4), (11.4, 5.4), (11.8, 4.6), (11.8, 0)], 'phosphate', axis='w', at=(111.5, 12),
                 seg=24, name='rswheel')
    knurl(g, wh, 111.5, 12, 8, 12.4, 5.4, n=20, depth=0.5, width=0.7)
    pin(g, 126, 20, 8.0, r=1.3, h=0.3)

    # ---------------------------------------------------------------- nose cap, barrel, front sight
    cap1 = section(31, 35, 48.6, 12, 8, y0=-24.0)
    g.extrude(cap1, 562.6, 578, 'phosphate', plane='front', bevel=0.8, name='nosecap')
    cap2 = section(24, 30, 39.0, 11, 8, y0=-23.0)
    g.extrude(cap2, 577.5, 600, 'phosphate', plane='front', bevel=1.0, name='nosecap2')
    screw(g, 595, -9, 15.0, r=2.4, h=0.8, side=1, mat='phosphate')
    g.lathe([(560, 0), (560, 9.6), (600, 9.4), (690, 9.0), (MUZZLE - 13.5, 8.6), (MUZZLE - 13.5, 7.4),
             (MUZZLE - 0.5, 7.4), (MUZZLE, 6.8), (MUZZLE, 0)], 'blued', seg=32, name='barrel')
    g.lathe([(MUZZLE - 0.2, 0), (MUZZLE - 0.2, 3.9), (MUZZLE + 0.01, 3.9), (MUZZLE + 0.01, 0)], 'black', seg=14,
            name='bore')
    g.lathe([(733.5, 0), (733.5, 9.2), (735, 10.0), (764.4, 10.0), (765, 9.2), (765, 0)], 'phosphate', seg=28,
            name='fscollar')
    g.extrude([(733.5, 6), (742, 21.5), (765, 21.5), (765, 6)], width=10, mat='phosphate', bevel=0.5,
              name='fsbase')
    g.tube(740, 766.5, 11.0, 9.4, 'phosphate', at=(32.0, 0), seg=32, chamfer=0.4, name='hood')
    g.extrude([(748.5, 21), (757.5, 21), (756.5, SIGHT_V - 1.0), (755.2, SIGHT_V), (750.8, SIGHT_V),
               (749.5, SIGHT_V - 1.0)], width=2.0, mat='phosphate', bevel=0.2, name='post')
    pin(g, 749, 12, 5.0, r=1.0, h=0.2)

    # ---------------------------------------------------------------- trigger guard (+ trigger) and mag catch
    gd, holes = g.outline([(-30, -54.6), (46, -54.6), (46, -98), (-30, -98)], holes=True)
    g.extrude(gd, width=7.0, mat='phosphate', holes=holes, bevel=0.6, name='guard')
    g.box(-26, 44, -56.5, -53.5, width=10, mat='phosphate', bevel=0.5)               # guard tang under the wood
    g.extrude([(92, -48), (105, -48), (105, -66), (99, -66), (92, -58)], width=14, mat='phosphate', bevel=0.6,
              name='magcatch')

    # ---------------------------------------------------------------- magazine (10 rounds)
    with g.part('mag'):
        mo = g.outline([(103.5, -38), (210, -38), (210, -112), (103.5, -112)])
        mo = smooth_edge(mo, 108, 202, lambda u: -70, 'bottom', deg=1)
        g.sweep(mo, 'blued', width=24, radius=(1.0, 2.0), step=2.5, n=2, round_ends=(1.2, 1.2), name='mag')
        for u in (112, 120, 136, 152, 165, 172, 185, 197):
            for s in (1, -1):
                r = g.box(u - 0.7, u + 0.7, -92, -50, s * 11.7, s * 12.5, mat='blued', bevel=0.3)
                g.transform(r, rot=('w', -5), pivot=(u, -70, 0))
    g.pivot('mag', 155, -44, 0)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', MUZZLE, 0)
    g.anchor('sight', 126, SIGHT_V)
    g.anchor('eject', 25, 12, 13)
    g.anchor('rh', -80, -45, 0)
    g.anchor('lh', 330, -10, 0)
    g.anchor('eye', -170, SIGHT_V)
