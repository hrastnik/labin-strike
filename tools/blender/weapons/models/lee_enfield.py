"""Lee-Enfield No.4 Mk I. Reference: Lee-Enfield No 4 Mk I (1943) - AM.032027 noBG.jpg (two views; the upper,
right-side one is cropped in cal/lee_enfield.json). 1129 mm, two-piece beech stock (butt in the receiver's butt socket,
forend with two upper handguards), parkerised receiver with the No.4 Mk I flip aperture sight on the bridge (ladder
folded forward), rear-locking cock-on-closing bolt with the round knob, 10-round box magazine (fixed in the client,
so it lives in 'body'), nose cap with the protected front sight and the exposed spike-bayonet muzzle.

The reference shows the bolt handle raised; the model has it closed (the client raises it by 1.2 rad when cycling).
'mag' is the five-round .303 charger in the charger guides, shown only while reloading (magHidden)."""
import math

from ..lib import rrect, section
from .m1garand import cartridge, pin, screw, smooth_edge, swivel

REF = 'lee_enfield'
META = {'kind': 'rifle', 'magHidden': True}

SIGHT_V = 30.0      # centre of the battle aperture = top of the front blade
MUZZLE = 786.0
BRIDGE_U = 1.0      # battle aperture plate

CASE_303 = [(0, 0), (0, 6.7), (1.5, 6.7), (1.7, 5.84), (2.6, 5.84), (44.5, 5.1), (48.6, 4.32), (56.4, 4.32),
            (56.4, 0)]
BULLET_303 = [(56.0, 0), (56.0, 3.95), (61.5, 3.95), (68.5, 3.3), (74.0, 2.1), (77.6, 0.7), (78.1, 0)]


def build(g):
    # ---------------------------------------------------------------- butt
    region = [(-342.6, 5), (-52, 5), (-52, -9.5), (-19, -1.0), (-19, -50.5), (-28, -55.5), (-56, -200),
              (-342.6, -200)]
    butt = g.outline(region)
    butt = smooth_edge(butt, -341, -158, lambda u: -90, 'bottom', deg=1)          # toe line (drops the swivel)
    butt = smooth_edge(butt, -340, -125, lambda u: -60, 'top', deg=2)             # comb
    bt = g.sweep(butt, 'beech', width=[(-343, 44), (-250, 42), (-160, 37), (-110, 33), (-70, 32.5), (-40, 35),
                                       (-19, 37)],
                 radius=(9, 10), step=4, n=3, round_ends=(0, 0), name='butt')
    bp = g.outline([(-360, 5), (-342.6, 5), (-342.6, -200), (-360, -200)])
    g.sweep(bp, 'park', width=44.6, radius=(9, 10), step=2, n=3, name='buttplate')
    # butt swivel: base plate on the bottom line, loop lying back
    slope = math.atan2(-99 + 160, -160 + 340)
    bu, bv = -268.0, -160 + (-268 + 340) * math.tan(slope)
    ca, sa = math.cos(slope), math.sin(slope)
    plate = [(bu + x * ca - y * sa, bv + x * sa + y * ca) for x, y in [(-16, -2.2), (14, -2.2), (16, 0.8), (-18, 0.8)]]
    g.extrude(plate, width=11, mat='park', bevel=0.6, name='buttswivelplate')
    lug = [(bu + x * ca - y * sa, bv + x * sa + y * ca) for x, y in [(-6, -1.5), (5, -1.5), (3, -6.5), (-4, -6.5)]]
    g.extrude(lug, width=6, mat='park', bevel=0.5)
    swivel(g, bu - 0.5 + 4.5 * sa, bv - 4.5 * ca, -72, L=24, W=15, r=1.6, mat='park')
    for x in (-12, 10):
        pu, pv = bu + x * ca, bv + x * sa
        g.cyl(pv - 0.6, pv + 0.6, 1.6, 'park', axis='v', at=(pu, 0), seg=10)

    # ---------------------------------------------------------------- forend (+ handguards)
    region = [(-16, 2.2), (136, 2.2), (144, 9.2), (664, 9.2), (664, -60), (454, -60), (454, -33.5), (416, -33.5),
              (416, -60), (134, -60), (130, -44), (38, -44), (38, -50.5), (-16, -50.5)]
    fe = g.outline(region)
    fe = smooth_edge(fe, 140, 660, lambda u: -15, 'bottom', deg=2)
    ft = g.sweep(fe, 'beech', width=[(-16, 38), (40, 38.5), (130, 37), (200, 35), (400, 33.5), (664, 31)],
                 radius=(3, 11), step=6, n=3, round_ends=(1.5, 2.0), name='forend')
    g.cut(ft, g.extrude(rrect(-6, 40, -2, 40, 0), -9.5, 9.5, cutter=True, bevel=0))     # inletting under the action
    hg_r = [(171.5, 9.0), (171.5, 24.6, 1.0), (175, 26.2, 2.0), (260, 25.4), (360, 23.4), (437, 22.2), (437, 9.0)]
    g.sweep(hg_r, 'beech', width=[(172, 30), (437, 29)], radius=(12, 1.5), step=8, n=3, round_ends=(1.2, 1.0),
            name='handguard_r')
    hg_f = [(449, 9.0), (449, 19.6), (600, 19.0), (660, 18.2, 2), (664, 16.0), (664, 9.0)]
    g.sweep(hg_f, 'beech', width=[(449, 29), (664, 28)], radius=(12, 1.5), step=8, n=3, round_ends=(1.0, 1.0),
            name='handguard_f')
    # rear handguard spring clip, forend escutcheon + screw (front trigger-guard screw)
    g.extrude([(196, 23), (224, 23), (224, 27.0, 1), (198, 27.6, 1)], width=12, mat='park', bevel=0.5, name='hgclip')
    for s in (1, -1):
        g.lathe([(s * 18.0, 0), (s * 18.0, 5.4), (s * 19.0, 5.0), (s * 19.4, 4.2), (s * 19.4, 0)], 'park', axis='w',
                at=(9, -18), seg=20, name='escutcheon')
    screw(g, 9, -18, 19.2, r=2.7, h=0.7, side=1, mat='park', ang=60)

    # ---------------------------------------------------------------- butt socket and receiver
    sock = [(-28.5, 1.5), (-10.5, 1.5), (-2.5, -48), (-20.5, -48)]
    g.sweep(sock, 'park', width=40.5, radius=(6, 13), step=2, n=3, name='buttsocket')
    low = [(-27, -4), (128, -4), (128, 8.2), (-27, 8.2)]
    g.sweep(low, 'park', width=31, radius=(1.0, 3), step=6, n=2, round_ends=(1.0, 1.0), name='rec_low')
    # left wall (high) and the front ring
    g.box(12, 128, 6, 17.6, -15.4, -10.5, mat='park', bevel=0.6, name='leftwall')
    ring = [(62, 6), (128, 6), (128, 18.0, 1.0), (66, 18.0, 1.0), (62, 15)]
    g.sweep(ring, 'park', width=30, radius=(12, 1), step=3, n=3, round_ends=(1.0, 0.5), name='rec_ring')
    # knox form / barrel reinforce and the handguard ring in front of the receiver
    g.sweep([(126, 2), (144, 2), (144, 21.0), (139, 21.0), (136, 18.4), (126, 18.4)], 'park', width=28,
            radius=(12, 1), step=2, n=3, name='knox')
    g.sweep([(144, 8), (163, 8), (163, 21.2, 1), (144, 21.2)], 'park', width=27, radius=(12, 1), step=2, n=3,
            name='knox2')
    g.sweep([(163, 8), (172, 8), (172, 22.6, 1), (163, 22.6, 1)], 'park', width=28.5, radius=(12, 1), step=2, n=3,
            name='hgring')
    # bridge: full width, carries the rear sight and the charger guides; bolt-handle notch at its rear right
    br = [(-24, 4), (13, 4), (13, 22.4), (-9, 22.4, 2.0), (-14, 18, 2.0), (-24, 12)]
    bri = g.sweep(br, 'park', width=31, radius=(8, 1), step=2, n=3, round_ends=(1.0, 1.0), name='bridge')
    g.cut(bri, g.box(-26, -14.5, -2, 9.5, 8.5, 20, cutter=True, bevel=0), solver='FLOAT')
    for s in (1, -1):
        g.extrude([(7, 18), (14.5, 18), (14.5, 25.5), (9, 25.5)], s * 6.0, s * 9.0, 'park', bevel=0.3,
                  name='chargerguide')
    # safety catch (left, above the trigger)
    g.extrude([(-16, 4), (-6, 4), (-4, 10.5, 1.5), (-13, 12.0, 2)], -18.6, -15.4, 'park', bevel=0.5, name='safety')
    pin(g, -11, 6.5, 18.6, r=1.6, h=0.4)
    # bolt-head release catch, magazine-cut-off area screw heads
    screw(g, 72, 1.8, 15.6, r=2.2, h=0.6, side=1, mat='park', ang=20)
    screw(g, 112, 1.8, 15.6, r=2.2, h=0.6, side=1, mat='park', ang=-40)

    # ---------------------------------------------------------------- rear sight (No.4 Mk I, battle aperture up)
    g.box(-10, 13, 22, 24.4, -6.5, 6.5, mat='park', bevel=0.4, name='rsbase')
    for s in (1, -1):                                       # protecting wings beside the aperture
        g.extrude([(-10, 20), (7, 20), (7, 26.5), (3, 28.6, 1.5), (-7, 28.6, 1.5), (-10, 25.5)], s * 6.6, s * 9.4,
                  'park', bevel=0.4, name='rswing')
    ap = [(5.2, 22.5)] + [(5.2 * math.cos(math.radians(a)), SIGHT_V + 1.0 + 5.2 * math.sin(math.radians(a)))
                          for a in range(0, 181, 15)] + [(-5.2, 22.5)]
    leaf = g.extrude(ap, BRIDGE_U - 1.2, BRIDGE_U + 1.2, 'park', plane='front', bevel=0.3, name='aperture')
    g.cut(leaf, g.cyl(BRIDGE_U - 3, BRIDGE_U + 3, 2.1, at=(SIGHT_V, 0), seg=20, chamfer=0, cutter=True))
    g.tube(BRIDGE_U - 1.6, BRIDGE_U + 1.6, 3.2, 2.1, 'park', at=(SIGHT_V, 0), seg=20, chamfer=0.3, name='peep')
    pin(g, 0.5, 23.5, 6.5, r=1.4, h=0.3)
    # ladder folded forward over the bridge, elevation slider, leaf head
    g.box(3, 60, 23.6, 26.8, -4.6, 4.6, mat='park', bevel=0.4, name='ladder')
    sl = g.extrude([(14, 23.0), (30, 23.0), (30, 28.0, 0.8), (14, 28.0, 0.8)], -7.4, 7.4, 'park', bevel=0.4,
                   name='slider')
    g.cut(sl, *[g.box(u - 0.5, u + 0.5, 23.5, 30, -9, 9, cutter=True, bevel=0) for u in (16.5, 19, 21.5, 24, 26.5)],
          solver='FLOAT')
    g.extrude([(46, 23.0), (61.5, 23.0), (61.5, 26.5), (59, 28.4, 1.2), (48, 28.4, 1.2), (46, 26.6)], -5.6, 5.6,
              'park', bevel=0.4, name='leafhead')
    g.extrude([(61.5, 6), (70, 6), (70, 23.5, 1.0), (61.5, 23.5)], width=24, mat='park', bevel=0.6, name='chgbridge')

    # ---------------------------------------------------------------- bolt (rotates about the bore, pulls back)
    with g.part('bolt'):
        g.cyl(-30, 106, 8.6, 'bright', seg=24, name='boltbody')
        g.lathe([(105, 0), (105, 8.2), (122, 8.2), (123.5, 7.4), (123.5, 0)], 'bright', seg=24, name='bolthead')
        g.box(108, 124, 6.5, 9.6, -2.2, 2.2, mat='bright', bevel=0.3, name='extractor')
        g.box(0, 98, -2.0, 2.0, 7.0, 10.4, mat='bright', bevel=0.4, name='guiderib')
        # cocking piece with its knurled flanks
        cp = g.extrude([(-47, -10.5), (-31, -10.5), (-31, 12.0), (-34, 14.2, 2), (-45, 14.2, 2), (-47, 10)],
                       width=14.5, mat='park', bevel=1.0, name='cockingpiece')
        g.cut(cp, *[g.box(u - 0.5, u + 0.5, -8.5, 12.5, -9, 9, cutter=True, bevel=0) for u in (-44, -41.5, -39, -36.5)]
              , g.box(-47.6, -46, -12, 16, -2, 2, cutter=True, bevel=0), solver='FLOAT')
        g.lathe([(-31.5, 0), (-31.5, 7.8), (-29, 7.8), (-29, 0)], 'park', seg=20)
        # handle base lug and the straight handle down to the round knob (closed)
        g.extrude([(-25, -7), (-15.5, -7), (-15.5, 9), (-25, 9)], 0, 15.5, 'bright', bevel=0.8, name='handlebase')
        kc = (-27.0, -17.0, 40.0)
        g.pipe([(-20.0, 1.0, 12.0), (-21.5, -4.0, 22.0), (-24.5, -11.0, 32.0), (kc[0], kc[1] + 3.5, kc[2] - 6.0)],
               3.6, 'bright', seg=12, corner=3, name='handle')
        g.lathe([(0, 0)] + [(9.2 * (1 - math.cos(math.radians(a))), 9.2 * math.sin(math.radians(a)))
                            for a in range(15, 180, 15)] + [(18.4, 0)],
                'bright', axis='w', at=(kc[0], kc[1]), seg=20, name='knob')
        g.transform(g.items[-1][0], move=(0, 0, kc[2] - 9.2))
    g.pivot('bolt', 47, 0, 0)

    # ---------------------------------------------------------------- box magazine (10 rounds, stays in the rifle)
    mo = g.outline([(38.5, -44), (134, -44), (134, -100), (38.5, -100)])
    mo = smooth_edge(mo, 50, 118, lambda u: -60 - (u - 40) * 0.1, 'bottom', deg=1)
    mz = g.sweep(mo, 'blued', width=23, radius=(1.0, 2.5), step=2.5, n=2, round_ends=(1.2, 1.2), name='magazine')
    for s in (1, -1):
        g.extrude([(48, -50), (51, -50), (51, -81, 1.5), (48, -81, 1.5)], s * 11.4, s * 12.2, 'blued', bevel=0.3)
        g.extrude([(88, -48), (92, -48), (92, -62, 2), (88, -62, 2)], s * 11.4, s * 12.2, 'blued', bevel=0.3)
    a = math.atan2(-63.5 + 92.0, 124 - 46)
    ca, sa = math.cos(a), math.sin(a)
    rim = [(46 + x * ca - y * sa, -92.0 + x * sa + y * ca) for x, y in [(2, 0.2), (80, 0.2), (80, 3.2), (2, 3.2)]]
    g.extrude(rim, width=24.2, mat='blued', bevel=0.6, name='magrim')
    # magazine catch inside the guard
    g.extrude([(30, -50), (38.6, -50), (38.6, -62), (34, -62), (30, -55)], width=7, mat='park', bevel=0.4,
              name='magcatch')

    # ---------------------------------------------------------------- trigger guard + trigger
    gd, holes = g.outline([(-26, -49), (38.4, -49), (38.4, -97), (-26, -97)], holes=True)
    g.extrude(gd, width=6.0, mat='park', holes=holes, bevel=0.6, seg=2, name='guard')
    g.box(-24, 38, -52.5, -48.0, width=11, mat='park', bevel=0.5, name='guardstrap')
    screw(g, -16, -50.5, 5.5, r=2.0, h=0.5, side=1, mat='park')

    # ---------------------------------------------------------------- lower band with its swivel
    band = section(31.5, 36.5, 58.6, 13, 15, y0=-34.2)
    g.extrude(band, 437, 449, 'park', plane='front', bevel=0.8, name='band')
    g.cyl(17.6, 20.4, 2.6, 'park', axis='w', at=(443, -22), seg=12, name='bandscrew')
    g.extrude([(436, -36), (450, -36), (450, -32), (436, -32)], width=9, mat='park', bevel=0.6)
    swivel(g, 443, -37.5, -62, L=15, W=15, r=1.6, mat='park')

    # ---------------------------------------------------------------- nose cap, front sight, muzzle
    nc = section(25, 30, 41, 10, 13, y0=-24.2)
    cap = g.extrude(nc, 664, 719, 'park', plane='front', bevel=1.2, name='nosecap')
    nc2 = section(26.5, 31.2, 43.0, 10.5, 13.5, y0=-25.0)
    g.extrude(nc2, 669, 699, 'park', plane='front', bevel=0.8, name='nosecap2')
    g.cut(cap, g.box(712, 722, -30, -12, -20, 20, cutter=True, bevel=0))
    g.extrude([(712, -12), (722, -12), (722, -15), (719, -22.5), (712, -24.6)], width=26, mat='park', bevel=1.5)
    for u in (676, 705):
        screw(g, u, -7, 15.4, r=1.8, h=0.5, side=1, mat='park')
    for u0 in (668.5, 689):
        g.extrude(rrect(u0, u0 + 12, 4.0, 6.6, 1.2), 14.6, 15.7, 'black', bevel=0.2, seg=1, name='capslot')
    g.extrude([(678, -27.5), (692, -27.5), (692, -23), (678, -23)], width=9, mat='park', bevel=0.6, name='caplug')
    swivel(g, 685, -27.0, 8, L=10, W=12, r=1.6, mat='park')
    # front sight block, protecting ears, blade
    g.lathe([(714, 0), (714, 11.4), (715, 12.2), (741, 12.2), (742, 11.4), (742, 0)], 'park', seg=28, name='fsblock')
    for s in (1, -1):
        ear = g.extrude([(714, 6), (720, 31.5), (723.5, 34.4), (738.6, 34.4), (742, 31.0), (742, 6)], s * 5.0,
                        s * 7.8, 'park', bevel=0.5, name='ear')
        rec = g.cyl(s * 7.0, s * 9.0, 4.3, axis='w', at=(729.5, 23.5), seg=20, chamfer=0, cutter=True)
        g.cut(ear, rec)
        screw(g, 729.5, 23.5, s * 7.0, r=3.2, h=0.5, side=s, mat='park', ang=70)
    g.extrude([(720, 10), (739, 10), (739, 15), (720, 15)], width=10, mat='park', bevel=0.4, name='bladebase')
    g.extrude([(726, 14), (732.5, 14), (731.5, SIGHT_V - 0.6), (731.0, SIGHT_V), (727.5, SIGHT_V),
               (727.0, SIGHT_V - 0.6)], width=1.9, mat='park', bevel=0.2, name='blade')
    pin(g, 735, 12.5, 5.0, r=1.1, h=0.2)
    # barrel stub, bayonet collar, crown
    g.lathe([(700, 0), (700, 9.6), (742, 9.6), (742, 9.0), (752, 9.0), (753, 8.4), (762, 8.4), (763, 7.5),
             (MUZZLE - 0.6, 7.5), (MUZZLE, 6.8), (MUZZLE, 0)], 'blued', seg=32, name='barrel')
    g.lathe([(MUZZLE - 0.3, 0), (MUZZLE - 0.3, 3.9), (MUZZLE + 0.01, 3.9), (MUZZLE + 0.01, 0)], 'black', seg=14,
            name='bore')
    for s in (1, -1):
        g.box(744, 751, -2.0, 2.0, s * 8.4, s * 10.0, mat='blued', bevel=0.3, name='baylug')

    # ---------------------------------------------------------------- charger with five rounds (reload only)
    with g.part('mag'):
        ub, v0, pitch = 14.0, 12.5, 11.8
        for i in range(5):
            cartridge(g, ub + 0.4, v0 + i * pitch, 0.0, case=CASE_303, bullet=BULLET_303, seg=12)
        top = v0 + 4 * pitch + 8.0
        bot = v0 - 8.0
        g.box(ub - 0.8, ub, bot, top, -8.0, 8.0, 'blued', bevel=0.2, name='charger')
        for s in (1, -1):
            g.box(ub - 0.8, ub + 3.2, bot, top, s * 7.3, s * 8.0, 'blued', bevel=0.15)
            g.box(ub + 2.4, ub + 3.2, bot, top, s * 5.6, s * 8.0, 'blued', bevel=0.15)
    g.pivot('mag', ub + 39, top)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', MUZZLE, 0)
    g.anchor('sight', BRIDGE_U, SIGHT_V)
    g.anchor('eject', 40, 12, 10)
    g.anchor('rh', -72, -45, 0)
    g.anchor('lh', 270, -12, 0)
    g.anchor('eye', BRIDGE_U - 290, SIGHT_V)
