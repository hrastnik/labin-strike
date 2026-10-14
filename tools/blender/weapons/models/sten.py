"""Sten Mk II. Reference: STEN MK II submachinegun.png (right side, public domain). 762 mm. Blackened tube receiver
with a fixed peep rear sight on the end cap, cocking handle in the right-hand slot, rotating magazine housing (the
magazine sticks out to the LEFT, removal direction -w), ejection port on the right, perforated barrel sleeve with the
front blade, stamped trigger housing with a wire trigger guard and change lever, skeleton tube stock with a
lightened brace and a T butt plate."""
import math

from ..lib import rrect

REF = 'sten'
META = {'kind': 'rifle', 'client': {'magDir': [-1, 0, 0]}}    # the left-hand magazine stays inside the side silhouette

SIGHT_V = 29.5      # top of the front blade = centre of the rear peep
RT = 20.8           # receiver tube radius


def dome(g, u, v, w, r=2.6, mat='black', h=None):
    """dome head (screw, pin, rivet) on a side face at depth w (sign gives the side)."""
    s = 1 if w > 0 else -1
    h = h or r * 0.5
    g.lathe([(w, 0), (w, r), (w + s * h * 0.45, r * 0.92), (w + s * h * 0.85, r * 0.6), (w + s * h, 0)], mat,
            axis='w', at=(u, v), seg=12)


def build(g):
    # ---------------------------------------------------------------- receiver tube, end cap, rear sight
    rec = g.lathe([(-33, 0), (-33, RT), (191, RT), (191, 0)], 'black', at=(0, 0), seg=36, name='receiver')
    # cocking slot along the upper right with the bolt showing through
    g.cut(rec, g.box(4, 146, 10.5, 17.5, 8, 24, cutter=True, bevel=0))
    g.box(4, 146, 9.5, 18.5, 4, 14.5, 'blued', bevel=0.3)
    for u in (-29.5, -16):                                                       # rolled rings at the rear
        g.lathe([(u - 0.6, RT - 0.1), (u - 0.6, RT + 0.5), (u + 0.6, RT + 0.5), (u + 0.6, RT - 0.1)], 'black',
                closed=True, seg=36)
    cap = g.lathe([(-43, 0), (-43, 20.5), (-42, 23.8, 1.5), (-40, 25.4), (-33, 25.4), (-32, 24.6), (-32, 0)],
                  'black', at=(0, 0), seg=36, name='endcap')
    g.cut(cap, g.box(-44, -39.5, -11, 8, -30, 30, cutter=True, bevel=0))   # catch recess at the back
    g.lathe([(-32, 0), (-32, 22.6), (-12.5, 22.6), (-11.5, 21.8), (-11.5, 0)], 'black', at=(0, 0), seg=36)   # rear reinforce
    peep = g.extrude([(-29.6, 22), (-25.2, 22), (-25.2, 38.4, 1.2), (-26.2, 39.6), (-28.6, 39.6), (-29.6, 38.4, 1.2)],
                     width=9, mat='black', bevel=0.3, name='peep')
    g.cut(peep, g.cyl(-35, -20, 1.6, axis='u', at=(SIGHT_V, 0), seg=12, cutter=True, chamfer=0))
    # cocking handle (right): knob on a stem out of the slot
    g.cyl(10, 17, 3.2, 'black', axis='w', at=(153, 15), seg=12)
    g.lathe([(17, 0), (17, 6.5), (19, 7.6), (27, 7.6), (29, 6.4), (29.6, 4), (29.6, 0)], 'black', axis='w',
            at=(153, 15.8), seg=20, name='knob')

    # ---------------------------------------------------------------- magazine housing and ejection port
    hs = g.lathe([(190, RT), (190, 21.2), (191, 21.7), (272, 21.7), (273, 21.2), (273, RT)], 'black', closed=True,
                 seg=36, name='housing')
    port = g.box(213, 250, 0, 5.5, 8, 26, cutter=True, bevel=0)
    g.cut(hs, port)
    g.cut(rec, g.box(213, 250, 0, 5.5, 8, 26, cutter=True, bevel=0))
    g.box(212, 251, -1, 6.5, 6, 12, 'blued', bevel=0.2)                          # bolt face behind the port
    ps = g.extrude(rrect(199, 259, -10, 10, 3), 21.3, 22.3, 'black', bevel=0.3)  # port surround plate
    g.cut(ps, g.box(213, 250, 0, 5.5, 8, 26, cutter=True, bevel=0))
    # magazine housing stub on the LEFT
    mh = g.extrude(rrect(-62, -14, -16, 16, 3), 204, 246, 'black', plane='front', bevel=0.8, name='maghousing')
    g.cut(mh, g.box(207.5, 242.5, -11.8, 11.8, -64, -20, cutter=True, bevel=0))
    g.box(206, 244, -17.5, 17.5, -62, -58, 'black', bevel=0.6)                   # lip at the mouth
    g.box(222, 228, 15.5, 19, -50, -30, 'black', bevel=0.4)                      # catch housing
    dome(g, 225, 19, -40, 2.2)

    # ---------------------------------------------------------------- front blade, barrel sleeve, barrel
    g.lathe([(272, 0), (272, 21.2), (276, 21.2), (276, 0)], 'black', at=(0, 0), seg=36, name='nut')
    blade = [(274, 20), (280, 20), (282, 22.5, 1.2), (279.3, SIGHT_V, 1.0), (276.5, SIGHT_V, 1.0),
             (274.6, 24)]
    g.extrude(blade, width=1.8, mat='black', bevel=0.3, name='blade')
    sl = g.lathe([(276, 9.4), (276, 19.2), (368, 19.2), (371.5, 17.5), (372.6, 14), (372.6, 9.4)], 'black',
                 at=(0, 0), seg=36, closed=True, name='sleeve')
    for u in (308, 330, 354):                                                    # cooling holes, three rows
        for rot in (0, 45, -45):
            c = g.cyl(-30, 30, 3.3, axis='w', at=(u, 0), seg=12, cutter=True, chamfer=0)
            if rot:
                g.transform(c, rot=('u', rot))
            g.cut(sl, c)
    g.lathe([(276, 0), (276, 9.0), (432, 9.0), (433.5, 9.5), (451, 9.5), (452.2, 8.7), (452.2, 0)], 'black',
            at=(0, 0), seg=24, name='barrel')
    g.cyl(451, 452.6, 4.6, 'black', seg=14, chamfer=0)                          # bore

    # ---------------------------------------------------------------- trigger housing
    th = [(-41.5, -14), (176, -14), (176, -19.2), (150, -30.6), (125, -43.7), (100, -56.7), (90, -61.7),
          (80, -66.2, 4), (68, -68.8, 6), (55, -66.8, 4), (42, -62), (33, -57), (30, -55), (-41.5, -55)]
    g.extrude(th, width=23, mat='black', bevel=1.0, name='trighousing')
    g.extrude([(-41.5, -18), (-34, -18), (-34, -55), (-41.5, -55)], width=24.6, mat='black', bevel=0.6)   # rear plate
    dome(g, 44, -26, 11.5, 6.0, 'black', 2.2)                                    # cross-bolt safety/selector
    dome(g, 44, -26, -11.5, 4.5, 'black', 1.8)
    dome(g, 88, -38, 11.5, 2.2)
    dome(g, 88, -38, -11.5, 2.2)
    # change lever (right side) and its slide
    lv = g.extrude([(0, -1.2, 1.2), (36, -1.2), (36, 1.2), (0, 1.2, 1.2)], 11.5, 13, 'blued', bevel=0.3,
                   name='lever')
    g.transform(lv, rot=('w', -12), move=(-3.5, -37.8, 0))
    g.extrude(rrect(30, 45, -50, -43, 1.5), 11.5, 14, 'black', bevel=0.4)
    trig = [(-9, -55), (0, -55), (-0.6, -62), (-2.2, -70), (-1.8, -77), (0.2, -82.5), (-1, -84), (-5.5, -80.5),
            (-8, -73), (-9.4, -63)]
    g.extrude(trig, width=6, mat='blued', bevel=0.5, name='trigger')
    guard = [(-18.6, -54, 0), (-18.6, -88.8, 0), (31, -88.8, 0), (31, -54, 0)]
    g.pipe(guard, 2.0, 'black', seg=10, corner=4.0, name='guard')

    # ---------------------------------------------------------------- skeleton stock
    vc = lambda u: -72.95 + 0.316 * (u + 200)                                    # tube centre line
    g.pipe([(-291, vc(-291), 0), (-36, vc(-36), 0)], 9.6, 'black', seg=18, name='stocktube')
    brace = [(-117, -55.5), (-87, -89.5, 4), (-81, -92, 4), (-41, -56.5), (-38, -56.5), (-38, -30), (-60, vc(-60))]
    hole = [(-81 + 12.4 * math.cos(math.radians(a)), -64.5 + 12.4 * math.sin(math.radians(a))) for a in range(0, 360, 15)]
    g.extrude(brace, width=6, mat='black', holes=[hole], bevel=0.6, name='brace')
    g.lathe([(-3.5, 12.4), (-3.5, 14.6), (3.5, 14.6), (3.5, 12.4)], 'black', axis='w', at=(-81, -64.5), seg=24,
            closed=True, name='holerim')
    # T butt plate: dished plate with two lightening slots, tilted back at the top
    pl = g.extrude(rrect(-17, 17, -55.5, 55.5, 10), -6.5, -1.5, 'black', plane='front', bevel=0.8, name='buttplate')
    for v0, v1 in ((28, 48), (-48, -28)):
        g.cut(pl, g.extrude(rrect(-6, 6, v0, v1, 5.5), -8, 3, plane='front', cutter=True, bevel=0))
    rim = g.extrude(rrect(-17, 17, -55.5, 55.5, 10), -7.5, 7.5, 'black', plane='front', bevel=0.6, name='rim')
    g.cut(rim, g.extrude(rrect(-14.6, 14.6, -53.1, 53.1, 8), -9, 9, plane='front', cutter=True, bevel=0))
    g.transform([pl, rim], rot=('w', 11.0), move=(-294, -103.5, 0))

    # ---------------------------------------------------------------- 32-round magazine (out to the LEFT)
    with g.part('mag'):
        body = [(208, -16), (242, -16), (242, -214), (208, -214)]
        g.extrude(body, -11, 11, 'black', plane='top', bevel=1.2, name='magbody')
        g.extrude([(212, -6), (238, -6), (238, -18), (212, -18)], -9, 9, 'black', plane='top', bevel=0.5)   # lips
        g.extrude([(206.5, -212), (243.5, -212), (243.5, -218), (206.5, -218)], -12.5, 12.5, 'black', plane='top',
                  bevel=0.8, name='floor')
        for s in (1, -1):                                                        # pressed ribs on the flanks
            g.pipe([(225, s * 11, -40), (225, s * 11, -200)], 1.3, 'black', seg=8)
    g.pivot('mag', 225, 0, -12)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 452.2, 0)
    g.anchor('sight', -27.4, SIGHT_V)
    g.anchor('eject', 232, 3, 22)
    g.anchor('rh', -40, -62, 0)          # firing hand on the housing / stock wrist behind the trigger
    g.anchor('lh', 225, -4, -40)         # support hand on the magazine housing (left)
    g.anchor('eye', -285, SIGHT_V)
