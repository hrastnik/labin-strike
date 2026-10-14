"""US Rifle, Cal. .30, M1903 (Springfield). Reference: NMAH photo (Springfield Model 1903, JN2016-02641),
1098 mm, straight bolt handle, model 1905 rear sight (leaf folded, battle-sight notch on the drift slide),
straight walnut stock with finger grooves, two-piece handguard, upper band with bayonet stud.

build(g, scoped=False) is reused by m1903a4.py (no iron sights, bent bolt handle, single round instead of the
stripper clip). Generic helpers come from kar98k.py."""
import math

from .kar98k import cartridge, sphere, stripper_clip

REF = 'm1903'
META = {'kind': 'rifle', 'magHidden': True}

SIGHT_V = 29.5        # sight line: top of the front blade; the battle-sight notch bottoms out NOTCH_DROP below it
NOTCH_DROP = 2.0      # so the blade's tip shows in the notch (the game's eye sits exactly on the sight line)
REAR_U = 214.0        # rear (battle-sight) notch


def ellipse_path(c, a, b, ang=0.0, n=16, plane='uv'):
    """closed loop of points (u, v, w): in the u-v plane (ang = tilt in degrees) or the v-w plane."""
    out = []
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    for k in range(n):
        t = 2 * math.pi * k / n
        x, y = a * math.cos(t), b * math.sin(t)
        if plane == 'uv':
            out.append((c[0] + x * ca - y * sa, c[1] + x * sa + y * ca, c[2]))
        else:
            out.append((c[0], c[1] + y, c[2] + x))
    return out


def stock_outline():
    return [
        # top line, butt (heel at the butt plate) to the forend nose
        (-318.5, -51.0, 1), (-300, -47.8), (-250, -44.0), (-200, -39.8), (-150, -36.2, 8), (-131, -35.0, 5),
        (-121, -36.4, 4), (-112, -39.2, 6), (-102, -38.2, 6), (-90, -34.1), (-80, -31.3), (-70, -27.7),
        (-60, -24.5), (-50, -21.0), (-40, -18.3), (-30, -15.2, 4), (-18, -12.0, 4), (0, -10.6), (100, -9.6),
        (180, -8.2), (268, -4.0), (649, -2.6, 1),
        # nose, bottom line back to the toe
        (650, -26.8, 2), (620, -25.2), (560, -27.2), (500, -30.0), (450, -31.8), (400, -34.4), (350, -37.0),
        (300, -39.1), (250, -40.9), (200, -43.2), (150, -45.6), (140, -47.6, 4), (100, -48.6), (40, -49.8),
        (10, -51.5, 4), (-12, -55.0, 4), (-25, -58.6), (-50, -65.6), (-69, -74.0), (-100, -85.2), (-150, -104.8),
        (-200, -125.8), (-250, -147.4), (-282, -160.0, 6), (-290.5, -160.8, 1),
        # rear face against the butt plate
        (-301.6, -146), (-309.4, -121), (-315.8, -97), (-320.2, -75), (-320.6, -58, 2),
    ]


def handle_pt(s, bent):
    """point on the bolt handle centre line, s mm out from the bore axis."""
    if not bent:      # straight, ~50 deg below horizontal, slightly swept back
        a = math.radians(-50)
        return (25.0 - 5.0 * s / 62, s * math.sin(a), s * math.cos(a))
    # M1903A4: forged down and back to clear the scope
    a1, a2 = math.radians(-22), math.radians(-62)
    if s <= 26:
        return (25.0 - 2.0 * s / 26, s * math.sin(a1), s * math.cos(a1))
    p = (23.0, 26 * math.sin(a1), 26 * math.cos(a1))
    d = s - 26
    return (p[0] - 12.0 * d / 34, p[1] + d * math.sin(a2), p[2] + d * math.cos(a2))


def build(g, scoped=False):
    # ---------------------------------------------------------------- stock
    st = g.sweep(stock_outline(), 'walnut', step=4, top=0.9, n=4,
                 width=[(-321, 42), (-200, 41), (-130, 35), (-105, 31), (-60, 34), (-30, 39), (0, 42), (150, 40),
                        (300, 36), (500, 32), (650, 29)],
                 radius=[(-321, 9, 9), (-150, 10, 10), (-105, 13, 13), (-60, 12, 12), (-20, 7, 11), (200, 5, 11),
                         (650, 5, 10)], name='stock')
    cuts = []
    for s in (1, -1):    # finger grooves along both sides of the forend
        cuts.append(g.lathe([(186, 0), (190, 6.5), (200, 10.5), (346, 10.5), (357, 6.5), (362, 0)],
                            at=(-19.0, s * 27.0), seg=20, cutter=True))
    g.cut(st, *cuts)
    # butt plate (steel, follows the slanted butt) + heel tang on top
    plate = [(-318.5, -50.8, 1), (-322, -50.6, 2), (-324.6, -58, 5), (-323.8, -75), (-319.4, -98), (-313, -122),
             (-305.2, -147), (-299.5, -158.5, 3), (-294, -162, 2), (-290.5, -160.6, 1), (-301.6, -146),
             (-309.4, -121), (-315.8, -97), (-320.2, -75), (-320.6, -58, 2)]
    g.sweep(plate, 'blued_old', width=[(-325, 42), (-290, 43)], radius=(9, 9), top=0.9, step=2, name='buttplate')
    g.extrude([(-321, -50.6), (-287, -47.6), (-287, -49.0), (-321, -52.2)], width=13, mat='blued_old',
              plane='side', bevel=0.5, name='heeltang')
    g.cyl(-50, -47, 3.0, 'blued_old', axis='v', at=(-300, 0), seg=12)          # heel-tang screw
    # butt swivel
    g.box(-236, -206, -139.5, -133.5, width=11, mat='blued', bevel=0.8)
    g.pipe(ellipse_path((-221, -140.5, 0), 13.5, 4.6, 23.6), 1.6, 'blued', seg=8, closed=True, name='swivel_b')
    # cross bolt washers
    for s in (1, -1):
        g.cyl(s * 19.5, s * 21.3, 4.0, 'blued', axis='w', at=(34, -39), seg=14)
        g.cyl(s * 17.0, s * 18.8, 3.6, 'blued', axis='w', at=(176, -22), seg=14)

    # ---------------------------------------------------------------- handguard
    hg = [(268, -3.2), (268, 19, 6), (279, 27.3, 8), (300, 27.4), (318, 24.2, 16), (340, 19.8), (360, 17.4),
          (380, 16.2), (400, 15.0), (424, 12.6, 10), (500, 12.7), (560, 13.3), (649.6, 12.8, 1), (649.6, -3.2)]
    if scoped:   # M1903A3/A4 style: no rear sight to protect, the handguard runs back to the receiver ring
        hg = [(188, -7.6), (188, 11.5, 3), (194, 15.4, 8), (300, 15.0), (400, 14.2), (424, 12.6, 10),
              (500, 12.7), (560, 13.3), (649.6, 12.8, 1), (649.6, -3.2), (268, -3.6)]
    g.sweep(hg, 'walnut', width=[(268, 30), (330, 30), (420, 28), (650, 27)], radius=(11, 2), top=0.8, step=4,
            name='handguard')

    # ---------------------------------------------------------------- receiver
    g.lathe([(144, 0), (144, 13.5), (147, 16.7), (185, 16.7), (186, 15.5), (186, 0)], 'blued', seg=32, name='ring')
    g.extrude([(-15, -16), (15, -16), (15, 1.2), (12, 1.6), (9.4, -4), (-9.4, -4), (-9.4, 10.5), (-12, 10.6),
               (-15, 9)], 60, 145, 'blued', plane='front', bevel=0.5, name='walls')
    g.extrude([(-16, -15), (16, -15), (16.5, 8), (12, 14.5), (6, 17.2), (-6, 17.2), (-12, 14.5), (-16.5, 8)],
              16, 62, 'blued', plane='front', bevel=0.8, name='bridge')
    g.extrude([(62, 10.5), (66, 10.5), (62, 16.5)], width=16, mat='blued', plane='side', bevel=0.3)
    for s in (() if scoped else (1, -1)):    # charger guide on the bridge (the A4 scope base replaces it)
        g.box(30, 52, 15, 19.2, w0=min(s * 3.2, s * 8.2), w1=max(s * 3.2, s * 8.2), mat='blued', bevel=0.4)
    g.extrude([(-13, -14), (13, -14), (14, 6), (9, 13), (4, 15), (-4, 15), (-9, 13), (-14, 6)], -2, 16, 'blued',
              plane='front', bevel=0.8, name='rearrec')
    g.extrude([(-38, -17.4), (-12, -8.6), (-2, -8.6), (-2, -13.5), (-14, -13.5), (-38, -21.0)], width=15,
              mat='blued', plane='side', bevel=0.8, name='tang')
    g.box(36, 146, -47, -15, width=24, mat='blued', bevel=0.5)                    # magazine well (inside wood)
    # trigger guard + floorplate
    guard = [(-22, -55.5), (-14, -56.5), (-13, -62, 4), (-8, -75, 6), (5, -81.6, 6), (28, -80, 6), (36, -70, 5),
             (38.5, -58, 3), (39.5, -51), (-22, -51)]
    hole = [(-7.5, -57.5), (33, -57.5), (33, -66, 4), (28, -75.5, 5), (6, -77.2, 5), (-3, -72, 4), (-7, -63, 2)]
    g.extrude(guard, width=8.5, mat='blued', holes=[hole], bevel=0.9, name='guard')
    g.extrude([(36, -48.6), (146, -45.4), (148, -47.4, 1.5), (100, -51.4), (42, -54.2), (36, -53)], width=22,
              mat='blued', bevel=1.0, name='floorplate')
    g.cyl(-12, 12, 2.4, 'blued', axis='w', at=(-17, -53.5), seg=10)               # guard screw heads
    trig = [(0.5, -52), (5.5, -52), (6.2, -56), (5.2, -63), (6.6, -70), (10.0, -76.4), (8.4, -77.6, 1),
            (3.4, -71.5), (0.6, -64), (-0.2, -56)]
    g.extrude(trig, width=5.5, mat='blued', bevel=0.6, name='trigger')

    # ---------------------------------------------------------------- barrel
    g.lathe([(186, 0), (186, 11.8), (275, 11.0), (400, 9.6), (560, 8.7), (650, 8.3), (695, 8.0), (740, 7.8),
             (767, 7.6), (768, 7.1), (773, 7.1), (773.6, 6.4), (773.6, 0)], 'blued', seg=32, name='barrel')
    g.cyl(760, 773.8, 3.3, 'black', seg=16, name='bore')

    # ---------------------------------------------------------------- upper band (nose cap) and lower band
    nose = [(645, 13.2, 1), (652, 13.0, 3), (662, 7.8, 3), (679, 7.8), (680, 10.6, 1), (695, 10.6, 1),
            (695.5, -21, 2), (660, -22.4), (645, -26.0, 2)]
    g.sweep(nose, 'blued', width=[(645, 31), (660, 25), (695, 25)], radius=(10, 7), top=0.9, step=2,
            name='upperband')
    g.extrude([(670, -21), (688, -21), (688, -29.7, 1.5), (672, -29.7, 1.5)], width=9, mat='blued', plane='side',
              bevel=0.6, name='bayonetstud')
    g.cyl(11, 14.5, 4.2, 'blued', axis='w', at=(675, -10), seg=14)              # band screw
    g.box(630, 642, -27.5, -24.5, width=8, mat='blued', bevel=0.5)
    g.pipe(ellipse_path((633, -32.5, 0), 10.0, 6.0, 0), 1.6, 'blued', seg=8, closed=True, name='swivel_u')
    lb = [(413.5, 14.2, 1.5), (425, 14.0, 1.5), (425, -35.0, 2), (413.5, -35.2, 2)]
    g.sweep(lb, 'blued', width=[(413, 34.5), (426, 34.5)], radius=(12, 10), top=0.85, step=1.5, name='lowerband')
    g.box(414, 424, -40, -34, width=7, mat='blued', bevel=0.5)
    g.pipe(ellipse_path((419, -50.5, 0), 4.5, 11.5, plane='vw'), 1.6, 'blued', seg=8, closed=True, name='swivel_l')

    if not scoped:
        # ------------------------------------------------------------ front sight: band, stud, blade
        g.lathe([(737, 0), (737, 8.2), (742, 9.2), (766, 9.2), (767, 8.4), (767, 0)], 'blued', seg=28)
        g.extrude([(737, 8), (747, 8), (749, 22), (746, 22)], width=7, mat='blued', plane='side', bevel=0.5)
        g.extrude([(746, 7), (766, 7), (766, 25.5, 2), (763, 27.4, 1.5), (751, 27.4, 1.5), (748.5, 25)], width=7,
                  mat='blued', plane='side', bevel=0.7, name='fs_stud')
        g.extrude([(-0.9, 25), (0.9, 25), (0.35, SIGHT_V), (-0.35, SIGHT_V)], 751.5, 763.5, 'blued', plane='front',
                  bevel=0.2, name='fs_blade')
        # ------------------------------------------------------------ model 1905 rear sight
        g.extrude([(185, -4.6), (270, -4.6), (270, 19.8, 1), (186, 19.8, 1)], width=22, mat='blued', plane='side',
                  bevel=0.8, name='rs_base')
        g.cyl(-11.5, 11.5, 3.6, 'blued', axis='w', at=(266, 23), seg=14)            # leaf hinge
        for s in (1, -1):   # folded leaf: two rails + cross pieces (window open from above)
            g.box(192, 269.5, 19.8, 27.2, w0=min(s * 4.6, s * 7.2), w1=max(s * 4.6, s * 7.2), mat='blued',
                  bevel=0.4)
        g.box(192, 198, 19.8, 27.2, width=14.4, mat='blued', bevel=0.4)
        g.box(262, 269.5, 19.8, 26.4, width=14.4, mat='blued', bevel=0.4)
        # drift slide with the battle-sight notch at its rear; the slide stays under the line through the notch
        nb = SIGHT_V - NOTCH_DROP
        g.box(214.5, 222, 19.5, nb - 0.6, width=17.5, mat='blued', bevel=0.5, name='rs_slide')
        g.extrude([(-8.7, 24), (8.7, 24), (8.7, SIGHT_V + 1.8), (2.4, SIGHT_V + 1.8), (0.3, nb), (-0.3, nb),
                   (-2.4, SIGHT_V + 1.8), (-8.7, SIGHT_V + 1.8)], 212, 215, 'blued', plane='front', bevel=0,
                  name='rs_notch')
        g.cyl(8.7, 12.0, 4.4, 'blued', axis='w', at=(217.5, 21.5), seg=14)          # slide binding screw
        g.lathe([(11, 0), (11, 7.4), (14.5, 7.4), (15.5, 6.4), (15.5, 0)], 'blued', axis='w', at=(261.5, 13.4),
                seg=18, name='windage')

    # ---------------------------------------------------------------- bolt
    with g.part('bolt'):
        g.cyl(-2, 145.5, 8.9, 'bright', seg=28, name='boltbody')
        g.lathe([(-14, 0), (-14, 8.6), (-12.5, 10.2), (-1, 10.2), (0, 9.2), (0, 0)], 'blued', seg=28, name='sleeve')
        g.extrude([(-12, 8), (2, 8), (2, 12), (-1, 17.4, 1.5), (-9, 17.4, 1.5), (-12, 14)], width=4, mat='blued',
                  bevel=0.4, name='safety')
        g.lathe([(-28.5, 0), (-28.5, 6.0), (-27.5, 8.4), (-21, 8.6), (-17.5, 6.6), (-14, 5.6), (-14, 0)], 'blued',
                at=(0.5, 0), seg=24, name='cockingpiece')
        bent = scoped
        path = [handle_pt(s, bent) for s in ((4, 18, 30, 42, 55) if bent else (4, 28, 54))]
        g.pipe(path, 4.3, 'bright', seg=12, corner=6 if bent else 0, name='handle')
        sphere(g, handle_pt(9, bent), 6.4, 'bright', seg=14, name='handleroot')
        sphere(g, handle_pt(62, bent), 9.5, 'bright', seg=18, name='knob')
    g.pivot('bolt', 58, 0, 0)

    # ---------------------------------------------------------------- clip (shown only while reloading)
    with g.part('mag'):
        if scoped:
            cartridge(g, 54.0, 3.5, 0.0, '3006', name='single')
            top = 3.5 + 6.0
        else:
            top = stripper_clip(g, 52.5, 3.5, '3006', pitch=12.0)
    g.pivot('mag', 95, top)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 773.6, 0)
    g.anchor('sight', REAR_U, SIGHT_V)
    g.anchor('eject', 100, 6, 12)
    g.anchor('rh', -80, -55, 0)
    g.anchor('lh', 330, -16, 0)
    g.anchor('eye', REAR_U - 320, SIGHT_V)
