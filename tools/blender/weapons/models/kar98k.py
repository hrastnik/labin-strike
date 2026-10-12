"""Karabiner 98k. Reference: Kar 98K noBG.jpg (two views; the upper, right-side one is cropped in cal/kar98k.json).
1110 mm, Mauser 98 action, turned-down bolt handle, laminated/walnut stock with semi-pistol grip, H-shaped nose cap.

build(g, scoped=False) is reused by kar98k_scoped.py (adds the ZF39 on turret mounts, single round instead of the
stripper clip). Shared helpers (sphere, cartridge, bolt-handle pipe) are imported by the Springfield models too."""
import math

from ..lib import arc, rrect, section

REF = 'kar98k'
META = {'kind': 'rifle', 'magHidden': True}

SIGHT_V = 21.5        # sight line: top of the front blade = bottom of the rear notch
REAR_U = 252.0        # rear notch


# ------------------------------------------------------------------ shared helpers

def sphere(g, c, r, mat='blued', seg=16, squash=1.0, name='sphere'):
    """sphere (optionally squashed along v) at c = (u, v, w), as a lathe around a v-axis line."""
    prof = [(c[1] - r * squash * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for a in range(0, 181, 15)]
    return g.lathe(prof, mat, axis='v', at=(c[0], c[2]), seg=seg, name=name)


def circle_pts(cw, cv, r, n=24, vmax=None, vmin=None):
    """circle in a (w, v) section, optionally clipped flat at vmax / vmin."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        w, v = cw + r * math.cos(a), cv + r * math.sin(a)
        if vmax is not None:
            v = min(v, vmax)
        if vmin is not None:
            v = max(v, vmin)
        pts.append((w, v))
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > 1e-3 or abs(p[1] - out[-1][1]) > 1e-3:
            out.append(p)
    return out


def cartridge(g, u0, v, w=0.0, kind='792', name='round'):
    """rimless rifle cartridge lying along +u with its base at u0. 7.92x57 (kind '792') or .30-06 ('3006')."""
    if kind == '792':
        L, sh, nk, rb, rs, rn, rbul, tot = 57.0, 45.0, 49.5, 5.95, 5.5, 4.55, 4.1, 80.5
    else:
        L, sh, nk, rb, rs, rn, rbul, tot = 63.3, 49.5, 53.5, 6.0, 5.6, 4.5, 3.9, 84.0
    case = [(u0, 0), (u0, rb - 0.5), (u0 + 0.4, rb), (u0 + 1.2, rb), (u0 + 1.4, rb - 0.9), (u0 + 2.4, rb - 0.9),
            (u0 + 3.2, rb - 0.1), (u0 + sh, rs), (u0 + nk, rn), (u0 + L, rn), (u0 + L, 0)]
    g.lathe(case, 'brass', at=(v, w), seg=14, name=name)
    bl = tot - L
    bul = [(u0 + L - 0.5, 0), (u0 + L - 0.5, rbul)]
    for k in range(1, 9):
        t = k / 8
        bul.append((u0 + L + bl * (0.35 + 0.65 * t), rbul * math.sqrt(max(0.0, 1 - t ** 2.2)) + 0.25 * t))
    bul[-1] = (u0 + tot, 0)
    g.lathe(bul, 'brass', at=(v, w), seg=14, name=name + 'b')


def stripper_clip(g, u_base, v0, kind='792', n=5, pitch=11.6, name='clip'):
    """stripper clip with n rounds stacked upward from v0 (bore-ish), bases in the clip at u_base."""
    for i in range(n):
        cartridge(g, u_base + 0.6, v0 + i * pitch, 0.0, kind, name=f'{name}r{i}')
    top = v0 + (n - 1) * pitch + 7.5
    bot = v0 - 7.5
    # spring-steel channel holding the rims: back plate + two lips
    g.box(u_base - 1.0, u_base, bot, top, -7.2, 7.2, 'blued', bevel=0.25)
    for s in (-1, 1):
        g.box(u_base - 1.0, u_base + 2.2, bot, top, s * 7.2 - 0.5, s * 7.2 + 0.5, 'blued', bevel=0.2)
    return top


# ------------------------------------------------------------------ Kar98k

def stock_outline():
    return [
        # top line, butt to nose
        (-345, -40.4, 1), (-300, -36.3), (-200, -27.2), (-150, -22.7, 6), (-131, -23.4, 8), (-108, -31.6, 18),
        (-82, -25.6), (-60, -17.8), (-40, -11.4), (-27, -8.8, 3), (-18, -5.0, 2), (60, -1.5), (150, -1.0),
        (330, 3.6), (520, 4.5), (612, 5.0, 2),
        # nose, bottom line back to the toe
        (614, -27.3, 2), (540, -29.8), (500, -32.9), (400, -37.2), (300, -41.3), (200, -44.8), (170, -46.6),
        (60, -48.5), (-22, -51.5, 3), (-32, -57.4, 3), (-50, -62.2), (-62, -66.5), (-72, -72.5), (-82, -83.0, 6),
        (-94, -95.0, 6), (-104, -97.6, 4), (-116, -96.5, 6), (-131, -93.4, 10), (-150, -100.2), (-200, -117.8),
        (-300, -153.4), (-320, -160.8), (-331, -164.6, 1),
    ]


def build(g, scoped=False):
    # ---------------------------------------------------------------- stock
    st = g.sweep(stock_outline(), 'walnut', step=4, top=0.92, n=4,
                 width=[(-345, 43), (-200, 41), (-140, 36), (-110, 31), (-70, 34), (-30, 40), (0, 44), (60, 44),
                        (160, 42), (250, 39), (340, 37), (520, 34), (614, 31)],
                 radius=[(-345, 9, 9), (-150, 10, 10), (-110, 13, 13), (-60, 12, 12), (-20, 6, 10), (200, 5, 11),
                         (614, 5, 10)],
                 name='stock')
    cuts = []
    # bolt-knob recess in the right flank
    rec = [(27 + 25 * math.cos(a * math.pi / 16), -32 + 16 * math.sin(a * math.pi / 16)) for a in range(32)]
    cuts.append(g.extrude(rec, 16.8, 30, cutter=True, bevel=0))
    # sling slot through the butt, reinforced by an eyelet
    cuts.append(g.extrude(rrect(-184, -178, -71, -44, 2.9), -30, 30, cutter=True, bevel=0))
    # barrel channel ahead of the receiver (the barrel shows between handguard / band and the stock nose)
    cuts.append(g.lathe([(196, 0), (196, 12.8), (330, 10.8), (540, 8.6), (640, 8.4), (640, 0)], at=(0, 0), seg=24,
                        cutter=True))
    g.cut(st, *cuts)
    # butt plate: steel cap over the butt end, wrapping round the heel and toe
    plate = [(-345.2, -40.2, 1), (-330.8, -164.8, 1), (-334, -168.6, 2), (-344.5, -169.4, 4), (-348.2, -164),
             (-355.0, -56, 5), (-351.6, -44.0, 4), (-347.4, -40.6)]
    g.sweep(plate, 'blued_old', width=[(-355, 41), (-331, 44)], radius=(9, 9), top=0.92, step=2, name='buttplate')
    # disassembly disc in the butt (right side) and the sling-slot eyelet
    for s in (1, -1):
        wb = s * 20.4
        if s > 0:
            g.lathe([(wb - s * 1, 0), (wb - s * 1, 12.6), (wb + s * 0.6, 12.6), (wb + s * 1.2, 11.5), (wb + s * 1.2, 6),
                     (wb + s * 0.4, 4.2), (wb - s * 0.6, 4.2)], 'blued_old', axis='w', at=(-226, -70), seg=28)
        g.extrude(rrect(-191, -171, -75, -40, 4), wb - s * 0.8, wb + s * 0.6, 'blued_old', holes=[rrect(-184, -178, -71, -44, 2.9)],
                  bevel=0.4)
    # cross bolts with washers (recoil lug cross bolt, rear cross bolt)
    for u, v, r in ((178, -12, 6.0), (-6, -36, 5.2)):
        for s in (1, -1):
            w = s * (21.6 if u > 100 else 20.0)
            g.lathe([(w - s * 1, 0), (w - s * 1, r), (w + s * 0.5, r - 0.3), (w + s * 0.9, r * 0.5), (w + s * 0.9, 0)],
                    'blued_old', axis='w', at=(u, v), seg=20)

    # upper handguard (front of the rear sight to the lower band)
    hg = [(333, 3.2), (333, 13.5, 3), (345, 16.9, 30), (380, 16.3), (450, 14.8), (500, 13.0), (514, 12.4),
          (514, 3.2)]
    g.sweep(hg, 'walnut', width=[(333, 29), (514, 27)], radius=(11, 3), top=0.86, step=4, name='handguard')

    # ---------------------------------------------------------------- receiver
    # front ring
    g.lathe([(150, 0), (150, 16.6), (151.2, 17.6), (195.5, 17.6), (197, 16.4), (197, 0)], 'blued', seg=40,
            name='ring')
    # rear bridge: round with a flat top, charger guide on its front edge
    bridge = circle_pts(0, 0, 15.6, 40, vmax=13.9, vmin=-16)
    g.extrude(bridge, 20, 52, 'blued', plane='front', bevel=0.6, name='bridge')
    for s in (-1, 1):
        g.extrude([(s * 4.6, 10), (s * 9.4, 10), (s * 9.4, 16.2), (s * 4.6, 16.8)], 49, 60, 'blued', plane='front',
                  bevel=0.4)
    # receiver walls between bridge and ring (right wall cut low, left wall high), and the floor
    g.extrude([(-16.2, -16), (16.2, -16), (16.2, 2.6), (13.5, 3.2), (9.6, 3.2), (9.6, -5), (-9.6, -5), (-9.6, 8.6),
               (-12.5, 8.8), (-16.2, 7.8)], 52, 151, 'blued', plane='front', bevel=0.5, name='walls')
    # rear tang running back over the wrist
    g.extrude([(-27, -9.4), (20, -9.4), (20, -3.5), (-20, -3.5, 4)], width=21, mat='blued', bevel=0.8)
    # magazine box housing / guard screws seen from below
    g.box(40, 152, -47, -18, width=24, mat='blued', bevel=0.6)

    # ---------------------------------------------------------------- trigger guard, floor plate, trigger
    guard = [(-27, -50), (42, -49), (40, -56, 3), (35, -66, 6), (29, -82, 6), (0, -84.0, 6), (-14, -83.6, 8),
             (-24, -72, 6), (-25.5, -60, 3)]
    hole = [(-19.5, -54), (33.5, -53), (31.6, -63.6, 5), (25.8, -79.8, 5), (0, -80.6, 6), (-12, -80.2, 6),
            (-20, -70, 5), (-21, -60, 2)]
    g.extrude(guard, width=8.5, mat='blued', holes=[hole], bevel=0.9, name='guard')
    g.box(-30, -14, -53.5, -49, width=11, mat='blued', bevel=0.8)               # rear tang of the guard
    g.extrude([(40, -46.5), (170, -45.0), (172, -47.6, 1.5), (120, -52.0), (40, -52.8)], width=22, mat='blued', bevel=0.8,
              name='floorplate')
    g.lathe([(-1, 0), (-1, 3.6), (0.4, 3.0), (0.8, 0)], 'blued', axis='v', at=(162, 0), seg=12)   # release
    g.cyl(-11.5, 11.5, 2.4, 'blued', axis='w', at=(-18, -51), seg=10)                 # guard screws
    g.cyl(-11.5, 11.5, 2.4, 'blued', axis='w', at=(150, -47.5), seg=10)
    trig = [(-1.2, -48), (5.0, -48), (4.6, -56), (2.6, -63), (3.4, -71), (5.6, -78.4), (4.6, -81.2, 1),
            (2.6, -80.6), (-0.2, -74), (-2.6, -67), (-3.3, -62, 3), (-2.4, -55)]
    g.extrude(trig, width=5.5, mat='blued', bevel=0.6, name='trigger')

    # ---------------------------------------------------------------- barrel
    g.lathe([(196, 0), (196, 12.6), (245, 12.4), (252, 11.8), (330, 10.4), (450, 9.0), (540, 8.3), (612, 7.9),
             (700, 7.4), (746, 7.2), (747, 6.8), (755, 6.8), (755.6, 6.0), (755.6, 0)], 'blued', seg=32,
            name='barrel')
    g.tube(745, 755.8, 4.6, 4.0, 'black', seg=16)     # bore

    # ---------------------------------------------------------------- rear sight (tangent leaf)
    base = [(244, 6), (317, 6), (317, 19.0), (306, 19.8, 3), (258, 16.2, 6), (246, 13.6, 3)]
    g.extrude(base, width=23, mat='blued', bevel=0.8, name='rsbase')
    g.lathe([(-11.5, 0), (-11.5, 5.4), (11.5, 5.4), (11.5, 0)], 'blued', axis='w', at=(325, 18.8), seg=20)  # hinge
    g.extrude([(316, 9), (333, 9), (333, 17.5), (329, 23.0, 5), (319, 23.6, 4), (316, 19)], width=19, mat='blued',
              bevel=0.6)
    leaf = [(255.5, 19.6), (325, 20.4), (326, 22.0, 1), (264, 21.0), (257, 21.1)]
    g.extrude(leaf, width=15, mat='blued', bevel=0.4, name='leaf')
    # notch plate at the rear end: notch bottom exactly on the sight line
    notch = g.extrude([(249.5, 17.2), (256.5, 17.2), (256.5, SIGHT_V + 2.4, 0.6), (249.5, SIGHT_V + 2.4, 0.6)],
                      width=16, mat='blued', bevel=0.3, name='notch')
    g.cut(notch, g.extrude([(-1.2, SIGHT_V + 3), (1.2, SIGHT_V + 3), (0.15, SIGHT_V), (-0.15, SIGHT_V)], 246, 260,
                           plane='front', cutter=True, bevel=0))
    # slider (set to the battle-sight position): stays below the sight line
    g.extrude([(262, 14), (277, 14), (277, SIGHT_V - 0.5, 1), (262, SIGHT_V - 0.5, 1)], width=19.5, mat='blued',
              bevel=0.5, name='slider')
    for s in (1, -1):
        g.lathe([(s * 9.7, 0), (s * 9.7, 2.6), (s * 11.4, 2.4), (s * 11.6, 0)], 'blued', axis='w', at=(269.5, 17),
                seg=12)

    # ---------------------------------------------------------------- bands
    lb = section(37.5, 34.5, 47.5, 11, 9, 4, y0=-33.6)
    band = g.extrude(lb, 512, 535, 'blued_old', plane='front', bevel=0.6, name='lowerband')
    g.cut(band, g.extrude(section(36, 33.5, 49, 10, 8, 4, y0=-34), 520, 527, plane='front', cutter=True, bevel=0))
    g.extrude(section(37.6, 34.6, 47.0, 11, 9, 4, y0=-33.4), 519.5, 527.5, 'blued_old', plane='front', bevel=0.3)
    # band spring ahead of the band (right side)
    g.extrude([(536, -12), (560, -11.4), (560, -9.6), (536, -9.0)], 15.0, 16.6, 'blued_old', bevel=0.3)
    # H-shaped nose cap with the bayonet lug
    nc = g.extrude([(-15.5, -29.5), (15.5, -29.5), (15.5, 2), (11.5, 9.8), (-11.5, 9.8), (-15.5, 2)], 612, 659,
                   'bright', plane='front', bevel=1.0, name='nosecap')
    nc_cut = [g.box(627, 644, 7.6, 12, -20, 20, cutter=True, bevel=0),
              g.box(627, 644, -32, -27.5, -20, 20, cutter=True, bevel=0),
              g.box(627, 644, -19, 3.5, 13.6, 20, cutter=True, bevel=0),
              g.box(627, 644, -19, 3.5, -20, -13.6, cutter=True, bevel=0)]
    g.cut(nc, *nc_cut)
    g.extrude(section(26, 26, 22, 6, 6, 4, y0=-19), 627, 644, 'walnut', plane='front', bevel=0.5)   # stock nose inside
    g.cyl(-16.5, 16.5, 2.0, 'bright', axis='w', at=(621, -6), seg=10)        # nose-cap screw
    g.extrude([(650, -7.0), (703, -7.0), (703, -18.8), (650, -18.8)], width=9, mat='bright', bevel=0.8, name='lug')
    g.cyl(560, 707, 3.0, 'bright', at=(-13, 0), seg=14)                       # cleaning rod
    g.lathe([(696, 0), (696, 3.6), (705, 4.0), (708, 3.4), (708, 0)], 'bright', at=(-13, 0), seg=14)

    # ---------------------------------------------------------------- front sight
    g.lathe([(712, 0), (712, 8.6), (713, 9.6), (745, 9.6), (746, 8.6), (746, 0)], 'blued', seg=32, name='fsbase')
    g.extrude([(718, 6), (744, 6), (744, 12.6, 1), (722, 13.2, 1)], width=11, mat='blued', bevel=0.5)
    g.extrude([(-2.7, 12.5), (2.7, 12.5), (0.45, SIGHT_V), (-0.45, SIGHT_V)], 727.5, 737.5, 'blued', plane='front',
              bevel=0.25, name='blade')

    # ---------------------------------------------------------------- bolt (rotates about the bore, pulls back)
    with g.part('bolt'):
        g.cyl(20, 151, 8.9, 'bright', seg=28, name='boltbody')
        # long Mauser claw extractor along the right side
        g.extrude([(-1.6, 6.8), (1.6, 6.8), (1.6, 9.6), (-1.6, 9.6)], 40, 148, 'bright', plane='front', bevel=0.3)
        g.transform(g.items[-1][0], rot=('u', 80))
        g.lathe([(147, 0), (147, 9.6), (150, 9.6), (150, 0)], 'bright', seg=20)
        # bolt shroud with the wing safety, cocking piece
        g.lathe([(-9.5, 0), (-9.5, 10.6), (-8.0, 12.4), (17, 12.8), (19.5, 11.6), (19.5, 0)], 'blued', at=(2.0, 0),
                seg=28, name='shroud')
        g.extrude([(-11, 7), (-1.5, 7), (-1.5, 13.4), (-3.5, 17.0, 1.5), (-9.0, 17.2, 1.5), (-11, 14.5)], width=3.4,
                  mat='blued', bevel=0.4, name='safety')
        g.box(-12, -1, 9, 12.8, width=9, mat='blued', bevel=0.6)
        g.extrude([(-17.8, -6.2), (-9, -6.2), (-9, 10.2), (-12, 11.4, 2), (-16.6, 10.4, 2.5), (-18.0, 2)], width=15,
                  mat='blued', bevel=1.0, name='cockingpiece')
        # turned-down handle and its pear-shaped knob
        g.pipe([(27.0, 2.0, 7), (27.0, 1.5, 17), (26.0, -6, 24.5), (24.8, -16, 28.4), (24.2, -22, 29.8)], 4.0,
               'bright', seg=12, corner=4, name='handle')
        g.lathe([(7, 0), (7, 5.6), (8, 6.3), (14, 6.0), (16, 4.6), (16, 0)], 'bright', axis='w', at=(27.0, 1.0),
                seg=14)  # handle root
        sphere(g, (24.0, -29.5, 30.2), 9.0, 'bright', seg=18, squash=1.08, name='knob')
    g.pivot('bolt', 65, 0, 0)

    # ---------------------------------------------------------------- clip (shown only while reloading)
    with g.part('mag'):
        if scoped:
            cartridge(g, 58.0, 3.5, 0.0, '792', name='single')
            top = 3.5 + 6.0
        else:
            top = stripper_clip(g, 57.0, 3.5, '792')
    g.pivot('mag', 97, top)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 755.6, 0)
    g.anchor('sight', REAR_U, SIGHT_V)
    g.anchor('eject', 100, 6, 12)
    g.anchor('rh', -84, -58, 0)
    g.anchor('lh', 330, -18, 0)
    g.anchor('eye', REAR_U - 320, SIGHT_V)
