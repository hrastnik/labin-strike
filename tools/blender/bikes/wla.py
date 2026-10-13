"""Harley-Davidson WLA (1942), US Army: olive drab all over, 45 cu in flathead V-twin, springer fork, sprung solo
saddle, rear luggage rack, Thompson scabbard on the right fork leg. Reference: right side, front to the right."""
import math

from mathutils import Matrix, Vector

from . import parts
from .lib import TAU, Bike, catmull, rrect, superellipse

REF = '~/Desktop/bike-reference-photos/hraley-davidson-wla.jpg'
CAL = ((192, 432), (852, 447), 1.48, 0.33)  # rear axle px, front axle px, wheelbase m, axle height m
R = 0.33           # tyre radius (4.00-18)
RAKE = math.radians(28)
PAINT = (90, 94, 58)  # olive drab


def build(bk: Bike):
    P, P3, M = bk.P, bk.P3, bk.M
    wb = CAL[2]
    ra = Vector((0, -wb / 2, R))   # rear axle
    fa = Vector((0, wb / 2, R))    # front axle
    hc = P3(716, 232)              # steering head centre
    up = Vector((0, -math.sin(RAKE), math.cos(RAKE)))   # steering axis, upwards
    fw = Vector((0, math.cos(RAKE), math.sin(RAKE)))    # perpendicular to it, forwards

    def ax(t, d=0.0, x=0.0):
        return hc + up * t + fw * d + Vector((x, 0, 0))

    bk.pivot('fork', hc, Matrix.Rotation(RAKE, 3, 'X'))
    bk.pivot('wheel_f', fa)
    bk.pivot('wheel_r', ra)

    # ---------------- wheels ----------------
    spec = dict(rim_r=0.245, rim_w=0.075, tire_w=0.105, tire_h=0.105, hub_r=0.032, hub_w=0.13, drum_r=0.1,
                flange_r=0.048, flange_x=0.042, spokes=40, cross=0.7)
    wm = {'rubber': 'rubber', 'rim': 'paint', 'hub': 'paint', 'spoke': 'paint_dark', 'steel': 'steel'}
    parts.wheel(bk, 'wheel_r', R, dict(spec, drum_side=-1, drum_r=0.105), wm, static=('body', ra))
    parts.wheel(bk, 'wheel_f', R, dict(spec, drum_side=-1, drum_r=0.095), wm, static=('fork', fa))

    # ---------------- frame (body) ----------------
    bk.part('body')
    paint = 'paint'
    tr = 0.016
    head_top, head_bot = ax(0.085), ax(-0.075)
    bk.cyl(head_top, head_bot, 0.024, paint, seg=14)
    # top tube: head -> seat cluster, under the tank
    seat_cl = P3(452, 302)
    bk.tube([ax(0.06, -0.02), P3(600, 292), seat_cl], tr, paint, bend=0.1)
    # front down tube: head -> round the front of the engine -> twin loop rails under it
    dt_bot = P3(686, 515)
    bk.tube([ax(-0.05, -0.02), P3(700, 330), P3(692, 470), dt_bot], 0.018, paint, smooth_path=6)
    for s in (1, -1):
        x = s * 0.07
        rail = [dt_bot + Vector((x * 0.3, 0, 0)), P3(660, 532, x), P3(560, 540, x), P3(470, 536, x), P3(432, 512, x)]
        bk.tube(rail, tr, paint, bend=0.05)
        # chain stays: bottom of seat post -> rear axle
        bk.tube([P3(432, 512, x), P3(300, 470, x * 1.3), ra + Vector((s * 0.095, 0.02, 0))], tr, paint, bend=0.1)
        # seat stays: seat cluster -> rear axle
        bk.tube([seat_cl + Vector((x * 0.4, 0, 0)), P3(330, 372, x * 1.2), ra + Vector((s * 0.095, 0.01, 0.02))], tr * 0.9, paint, bend=0.1)
        # axle plates
        bk.prism([(ra.y - 0.05, ra.z - 0.02), (ra.y + 0.045, ra.z - 0.02), (ra.y + 0.05, ra.z + 0.04), (ra.y - 0.02, ra.z + 0.045)],
                 s * 0.088 - 0.004, s * 0.088 + 0.004, paint, bevel=0.003)
    # seat post tube
    bk.tube([seat_cl, P3(440, 420), P3(432, 512)], 0.02, paint, bend=0.1)
    # gearbox mounting plate behind the engine
    bk.prism([P(430, 455), P(470, 450), P(475, 520), P(432, 518)], -0.05, 0.05, paint, bevel=0.004)

    # ---------------- engine: 45 degree flathead V-twin ----------------
    crank = P3(552, 478)
    # crankcase: rounded body, aluminium
    case = [(0.0, 0.0)]
    cc = crank
    bk.sweep([cc + Vector((-0.075, 0, 0)), cc + Vector((-0.07, 0, 0)), cc + Vector((0.07, 0, 0)), cc + Vector((0.08, 0, 0))],
             [rrect(0.2, 0.17, 0.05, 3), rrect(0.22, 0.19, 0.06, 3), rrect(0.22, 0.19, 0.06, 3), rrect(0.19, 0.16, 0.05, 3)],
             'alu', cap0=True, cap1=True, frames=parts.xframes(4))
    # gear case cover (right side) and the cone
    bk.sweep([cc + Vector((0.08, 0.04, -0.01)), cc + Vector((0.1, 0.04, -0.01)), cc + Vector((0.11, 0.04, -0.01))],
             [rrect(0.13, 0.11, 0.04, 3), rrect(0.12, 0.1, 0.04, 3), rrect(0.1, 0.08, 0.03, 3)],
             'alu', cap1=True, frames=parts.xframes(3))
    bk.lathe([(0.03, 0), (0.028, 0.02), (0.018, 0.035), (0.0, 0.04)], P3(590, 455, 0.1), (1, 0, 0), 'alu', seg=16)
    # primary chain case on the left
    bk.sweep([P3(560, 470, -0.08), P3(560, 470, -0.115), P3(560, 470, -0.125)],
             [rrect(0.36, 0.13, 0.06, 3), rrect(0.34, 0.12, 0.06, 3), rrect(0.32, 0.1, 0.05, 3)],
             'paint', cap1=True, frames=parts.xframes(3))
    # gearbox behind the crankcase
    bk.box(P3(462, 478), (0.16, 0.1, 0.12), 'paint', bevel=0.02)
    # cylinders: iron barrels with round fins, aluminium heads with flat fins
    for k, lean in ((0, -22.5), (1, 22.5)):
        a = math.radians(lean)
        d = Vector((0, math.sin(a), math.cos(a)))
        base = crank + d * 0.075
        # barrel
        fins = []
        n = 9
        for i in range(n):
            t0 = 0.035 + i * 0.0105
            fins += [(0.042, t0), (0.07, t0 + 0.001), (0.07, t0 + 0.004), (0.042, t0 + 0.006)]
        prof = [(0.045, 0.0), (0.04, 0.03)] + fins + [(0.04, 0.135)]
        bk.lathe(prof, base, d, 'iron', seg=20)
        # valve chest: the flathead's side pocket towards the middle of the V
        vc = base + d * 0.06 + Vector((0, -math.sin(a) * 0.0, 0)) + Vector((0.035, 0, 0))
        # head: wide, flat-finned aluminium slab offset forward over the valves
        hd = base + d * 0.15
        side = Vector((0, math.cos(a), -math.sin(a)))
        hdc = hd + side * (0.02 if k == 1 else -0.02)
        for j in range(8):
            w = 0.19 - abs(j - 3.5) * 0.01
            c = hdc + d * (0.0 + j * 0.0105)
            bk.box(c, (0.13 - abs(j - 3.5) * 0.006, w, 0.0055), 'alu', bevel=0.002, seg=1, rot=Matrix.Rotation(a, 4, 'X'))
        bk.box(hdc + d * 0.035, (0.09, 0.15, 0.085), 'alu', bevel=0.02, rot=Matrix.Rotation(a, 4, 'X'))
        # spark plug
        bk.cyl(hdc + d * 0.07 + side * 0.02, hdc + d * 0.1 + side * 0.02, 0.008, 'white', seg=6)
        # tappet guides / push rod covers (chrome) on the right, down into the gear case
        for tt in (-0.018, 0.018):
            p0 = base + side * (0.045 if k == 0 else -0.045) + Vector((0.055, 0, 0)) + side * tt
            bk.cyl(p0 + d * 0.0, p0 - d * 0.07 + Vector((0, 0, -0.01)), 0.009, 'chrome', seg=8)
    # carburettor (right side, in the V) with intake
    carb = crank + Vector((0.07, 0.0, 0.2))
    bk.box(carb, (0.06, 0.055, 0.06), 'alu', bevel=0.012)
    bk.cyl(carb + Vector((0.02, 0, 0)), carb + Vector((0.075, 0, 0.0)), 0.022, 'paint_dark', seg=12)
    # oil-bath air cleaner on the left
    acl = crank + Vector((-0.12, 0.02, 0.22))
    bk.lathe([(0.0, -0.06), (0.065, -0.06), (0.07, -0.05), (0.07, 0.05), (0.065, 0.06), (0.0, 0.06)], acl, (1, 0, 0), 'paint', seg=20)
    bk.tube([acl + Vector((0.06, 0, 0)), carb + Vector((-0.03, 0, 0))], 0.02, 'paint_dark', seg=10)

    # ---------------- exhaust (right side), black ----------------
    ex = 'black'
    front_port = crank + Vector((0.05, 0.14, 0.13))
    rear_port = crank + Vector((0.05, -0.12, 0.14))
    pipe = [front_port, front_port + Vector((0.03, 0.06, -0.05)), P3(668, 470, 0.11), P3(650, 540, 0.12), P3(560, 552, 0.13), P3(478, 545, 0.135)]
    bk.tube(pipe, 0.019, ex, smooth_path=5)
    bk.tube([rear_port, rear_port + Vector((0.025, -0.02, -0.06)), P3(500, 520, 0.12), P3(478, 545, 0.135)], 0.018, ex, smooth_path=5)
    # muffler: long, rising to the back, tail pipe
    m0, m1 = P3(478, 540, 0.135), P3(118, 474, 0.14)
    L = (m1 - m0).length
    prof = [(0.0, 0), (0.02, 0), (0.038, 0.06), (0.04, 0.1), (0.04, L - 0.12), (0.037, L - 0.04), (0.025, L - 0.01), (0.018, L), (0.0, L)]
    bk.lathe(prof, m0, m1 - m0, ex, seg=18)
    bk.cyl(m1 - (m1 - m0).normalized() * 0.01, m1 + (m1 - m0).normalized() * 0.06, 0.016, ex, seg=12)
    # muffler hangers
    bk.tube([P3(300, 505, 0.14), P3(300, 470, 0.1)], 0.006, 'paint')

    # ---------------- tank: split teardrop over the top tube ----------------
    tank_path, tank_sec = [], []
    prof = [  # (px x, top py, bottom py, half width m)
        (478, 272, 280, 0.03), (490, 258, 290, 0.07), (510, 248, 296, 0.1), (540, 238, 300, 0.12), (580, 228, 303, 0.135),
        (620, 220, 304, 0.143), (660, 213, 302, 0.145), (690, 210, 296, 0.14), (705, 212, 282, 0.125), (712, 220, 262, 0.09),
        (715, 232, 245, 0.04)]
    for x, t, b, hw in prof:
        yt, zt = P(x, t)
        _, zb = P(x, b)
        tank_path.append(Vector((0, yt, (zt + zb) / 2)))
        tank_sec.append(_tank_sec(hw, zt - zb))
    bk.sweep(tank_path, tank_sec, 'paint', cap0=True, cap1=True, frames=parts.yframes(len(tank_path)))
    # dash on top between the halves, filler caps
    yt, zt = P(615, 221)
    bk.box((0, yt + 0.03, zt + 0.008), (0.07, 0.16, 0.03), 'paint', bevel=0.012)
    bk.lathe([(0.0, 0), (0.026, 0), (0.026, 0.006), (0.0, 0.007)], (0, yt + 0.06, zt + 0.023), (0, 0, 1), 'glass', seg=16)
    for s in (1, -1):
        y, z = P(642, 214)
        bk.lathe([(0.0, -0.01), (0.03, -0.01), (0.03, 0.006), (0.024, 0.014), (0.0, 0.016)], (s * 0.075, y, z), (0, 0, 1), 'paint', seg=16)
    # star in a circle on each side of the tank (white)
    for s in (1, -1):
        y, z = P(600, 262)
        parts.star(bk, Vector((0, y, z)), s, 0.05, 'white')

    # ---------------- saddle on its sprung post ----------------
    _saddle(bk, P, 'tan')
    bk.anchor('seat', P3(410, 215))
    bk.cyl(P3(420, 262), P3(442, 315), 0.012, 'steel', seg=10)
    bk.spring(P3(424, 268), P3(434, 295), 0.018, 0.003, 6, 'steel')
    # springs under the back of the saddle
    for s in (1, -1):
        bk.tube([P3(375, 250, s * 0.08), P3(400, 262, s * 0.06), P3(424, 270, s * 0.02)], 0.007, 'steel', bend=0.02)
        bk.tube([P3(500, 248, s * 0.04), P3(470, 262, s * 0.03), P3(430, 275, s * 0.02)], 0.006, 'steel', bend=0.02)

    # ---------------- rear fender + rack + tail lamp ----------------
    parts.fender(bk, ra, 0.375, 0.165, math.radians(-8), math.radians(150), 'paint', depth=0.06, part='body')
    # rack: flat top with skirts and keyhole slots, triangulated struts to the axle
    y0, z0 = P(72, 252)
    y1, _ = P(272, 250)
    zt = z0
    bk.box((0, (y0 + y1) / 2, zt), (0.24, y1 - y0, 0.012), 'paint', bevel=0.003)
    for s in (1, -1):
        bk.prism([(y0 + 0.02, zt), (y1 - 0.01, zt), (y1 - 0.03, zt - 0.06), (y0 + 0.05, zt - 0.06)], s * 0.12 - 0.003, s * 0.12 + 0.003, 'paint')
        for kx in range(4):
            yy = y0 + 0.09 + kx * 0.075
            bk.box((s * 0.124, yy, zt - 0.025), (0.004, 0.012, 0.03), 'black')
        # struts: rack -> axle (a V), and rack front -> frame
        foot = ra + Vector((s * 0.105, 0.03, 0.03))
        bk.tube([(s * 0.12, y0 + 0.07, zt - 0.06), foot], 0.011, 'paint')
        bk.tube([(s * 0.12, y1 - 0.05, zt - 0.06), foot], 0.011, 'paint')
        bk.prism([(foot.y - 0.06, foot.z + 0.12), (foot.y + 0.06, foot.z + 0.12), (foot.y, foot.z - 0.02)], s * 0.105 - 0.003, s * 0.105 + 0.003, 'paint', bevel=0.002)
        bk.tube([(s * 0.12, y1 - 0.03, zt - 0.05), P3(330, 365, s * 0.09)], 0.01, 'paint')
        # rear fender stays
        bk.tube([P3(30, 410, s * 0.09), P3(120, 405, s * 0.1), ra + Vector((s * 0.1, -0.02, 0.0))], 0.009, 'paint', bend=0.04)
    # tail lamp (blackout), plate below
    tl = P3(48, 282)
    bk.lathe([(0.0, 0), (0.03, 0), (0.034, -0.02), (0.034, -0.06), (0.026, -0.07), (0.0, -0.07)], tl + Vector((0, 0.03, 0)), (0, 1, 0), 'paint', seg=16)
    bk.lathe([(0.0, -0.071), (0.022, -0.071), (0.0, -0.075)], tl + Vector((0, 0.03, 0)), (0, 1, 0), 'red', seg=12)
    bk.tube([tl + Vector((0, 0.03, -0.02)), P3(70, 300), P3(90, 330)], 0.006, 'paint')
    bk.plate([P3(24, 300, -0.09), P3(24, 300, 0.09), P3(45, 380, 0.09), P3(45, 380, -0.09)], 0.004, 'paint')

    # ---------------- oil tank (right) and battery box (left) under the saddle ----------------
    for s, h in ((1, 0.11), (-1, 0.1)):
        c = P3(390, 395, s * 0.135)
        bk.sweep([c + Vector((-s * 0.05, 0, 0)), c + Vector((-s * 0.045, 0, 0)), c + Vector((s * 0.045, 0, 0)), c + Vector((s * 0.05, 0, 0))],
                 [rrect(0.22, h, 0.03, 3), rrect(0.25, h + 0.02, 0.04, 3), rrect(0.25, h + 0.02, 0.04, 3), rrect(0.22, h, 0.03, 3)],
                 'paint', cap0=True, cap1=True, frames=parts.xframes(4, flip=s < 0))

    # ---------------- footboards, pedals, stand ----------------
    for s in (1, -1):
        c = P3(632, 498, s * 0.25)
        bk.anchor('foot_r' if s > 0 else 'foot_l', c + Vector((0, 0, 0.012)))
        bk.box(c, (0.12, 0.3, 0.012), 'black', bevel=0.004)
        bk.box(c + Vector((0, 0, 0.008)), (0.11, 0.28, 0.006), 'rubber', bevel=0.002)
        bk.tube([c + Vector((-s * 0.05, 0.0, -0.01)), P3(632, 520, s * 0.07)], 0.012, 'paint')
    # brake pedal (right), clutch pedal (left)
    bk.tube([P3(560, 505, 0.17), P3(640, 480, 0.2), P3(665, 470, 0.22)], 0.007, 'paint', bend=0.03)
    bk.box(P3(668, 468, 0.22), (0.05, 0.04, 0.012), 'rubber')
    bk.tube([P3(580, 500, -0.17), P3(660, 470, -0.2)], 0.007, 'paint')
    # kick starter (left)
    bk.tube([P3(470, 470, -0.11), P3(500, 520, -0.16), P3(520, 525, -0.2)], 0.008, 'paint', bend=0.02)
    # rear stand folded up under the rear fender
    for s in (1, -1):
        bk.tube([ra + Vector((s * 0.115, 0, 0)), ra + Vector((s * 0.12, -0.33, 0.12))], 0.01, 'paint')
    bk.tube([ra + Vector((0.12, -0.33, 0.12)), ra + Vector((-0.12, -0.33, 0.12))], 0.01, 'paint')
    # chain (right side) from the gearbox sprocket to the rear sprocket
    gs = P3(462, 498, 0.1)
    rs = ra + Vector((0.1, 0, 0))
    bk.lathe([(0.0, -0.004), (0.09, -0.004), (0.09, 0.004), (0.0, 0.004)], rs, (1, 0, 0), 'black', seg=30)
    bk.lathe([(0.0, -0.004), (0.04, -0.004), (0.04, 0.004), (0.0, 0.004)], gs, (1, 0, 0), 'black', seg=16)
    for sgn in (1, -1):
        bk.tube([gs + Vector((0, 0, sgn * 0.04)), rs + Vector((0, 0, sgn * 0.09))], 0.005, 'black', seg=5)

    # ---------------- fork (steers) ----------------
    bk.part('fork')
    ta, da = (fa - hc).dot(up), (fa - hc).dot(fw)
    for s in (1, -1):
        x = s * 0.075
        # rear legs, fixed to the stem: forged I-beam looking flat bars
        top, bot = ax(0.13, 0.05, x), ax(ta + 0.02, da - 0.035, x)
        parts.flatbar(bk, top, bot, 0.03, 0.016, 'paint')
        # front (sprung) legs ahead of them
        ftop, fbot = ax(0.0, 0.11, x), ax(ta + 0.005, da + 0.03, x)
        parts.flatbar(bk, ftop, fbot, 0.022, 0.014, 'paint')
        # rockers at the axle
        bk.prism(parts.seg_poly(ax(ta + 0.02, da - 0.04), ax(ta - 0.005, da + 0.035), 0.022), x - 0.008, x + 0.008, 'paint', bevel=0.003)
        # spring rods + springs in front of the head
        rod_b, rod_t = ax(-0.02, 0.105, s * 0.035), ax(0.24, 0.105, s * 0.035)
        bk.cyl(rod_b, rod_t, 0.006, 'steel', seg=8)
        bk.spring(ax(-0.04, 0.105, s * 0.035), ax(0.11, 0.105, s * 0.035), 0.022, 0.004, 9, 'paint')
        bk.spring(ax(0.135, 0.105, s * 0.035), ax(0.22, 0.105, s * 0.035), 0.019, 0.0035, 5, 'paint')
    # crowns: lower bridge and top
    bk.box(ax(-0.095, 0.05), (0.19, 0.06, 0.03), 'paint', bevel=0.008, rot=Matrix.Rotation(-RAKE, 4, 'X'))
    bk.box(ax(0.11, 0.06), (0.2, 0.09, 0.03), 'paint', bevel=0.008, rot=Matrix.Rotation(-RAKE, 4, 'X'))
    bk.box(ax(0.0, 0.11), (0.1, 0.03, 0.03), 'paint', bevel=0.006, rot=Matrix.Rotation(-RAKE, 4, 'X'))
    bk.box(ax(0.23, 0.105), (0.1, 0.03, 0.025), 'paint', bevel=0.006, rot=Matrix.Rotation(-RAKE, 4, 'X'))
    # handlebars: wide, swept back, grips black rubber
    clamp = ax(0.135, 0.02)
    for s in (1, -1):
        bar = [clamp + Vector((s * 0.0, 0, 0)), clamp + Vector((s * 0.12, 0.0, 0.02)), clamp + Vector((s * 0.27, -0.11, 0.045)),
               clamp + Vector((s * 0.37, -0.2, 0.035))]
        bk.tube(bar, 0.0125, 'paint', smooth_path=6)
        g0 = clamp + Vector((s * 0.33, -0.165, 0.04))
        g1 = clamp + Vector((s * 0.45, -0.24, 0.025))
        bk.lathe([(0.0, 0), (0.017, 0), (0.019, 0.01)] + [(0.019 if k % 2 else 0.0175, 0.012 + k * 0.009) for k in range(12)] + [(0.017, 0.13), (0.0, 0.132)],
                 g0, g1 - g0, 'rubber', seg=10)
        # levers
        lv = clamp + Vector((s * 0.3, -0.12, 0.04))
        bk.tube([lv, lv + Vector((s * 0.08, 0.05, -0.01)), lv + Vector((s * 0.15, 0.0, -0.01))], 0.005, 'paint', bend=0.02)
        bk.anchor('grip_r' if s > 0 else 'grip_l', (g0 + g1) / 2)
    # mirror on the left
    mb = clamp + Vector((-0.27, -0.1, 0.045))
    mc = P3(657, 36, -0.36)
    bk.tube([mb, P3(690, 140, -0.33), P3(684, 80, -0.35), mc + Vector((0, 0.0, -0.035))], 0.005, 'paint', bend=0.06)
    bk.lathe([(0.0, -0.008), (0.042, -0.008), (0.045, 0.0), (0.0, 0.004)], mc, (0, -1, 0.2), 'paint', seg=16)
    bk.lathe([(0.0, 0.0), (0.04, 0.0), (0.0, 0.0001)], mc + Vector((0, -0.006, 0.001)), (0, -1, 0.2), 'glass', seg=16)
    # headlamp on top of the springs, horn under it
    lamp_c = P3(776, 152)
    lamp_d = Vector((0, 1, -0.04)).normalized()
    bk.lathe([(0.0, -0.075), (0.035, -0.073), (0.06, -0.05), (0.07, -0.02), (0.072, 0.0), (0.074, 0.006), (0.068, 0.012)],
             lamp_c, lamp_d, 'paint', seg=24)
    bk.lathe([(0.0, 0.026), (0.05, 0.012), (0.068, 0.008)], lamp_c, lamp_d, 'lens', seg=24, part='lamp')
    bk.box(lamp_c - lamp_d * 0.04 + Vector((0, 0, -0.07)), (0.03, 0.04, 0.07), 'paint', bevel=0.008)
    horn = ax(0.02, 0.2)
    bk.lathe([(0.0, -0.02), (0.045, -0.02), (0.05, 0.0), (0.045, 0.02), (0.0, 0.022)], horn, (0, 1, 0), 'paint', seg=18)
    # blackout marker lamp on the left of the headlamp
    bl = P3(872, 236, 0.1)
    bk.lathe([(0.0, -0.04), (0.03, -0.04), (0.032, 0.0), (0.0, 0.005)], bl, lamp_d, 'paint', seg=12)
    bk.tube([bl - lamp_d * 0.03, bl - lamp_d * 0.06 + Vector((-0.03, 0, -0.02))], 0.006, 'paint')
    # front fender with its braces
    parts.fender(bk, fa, 0.37, 0.15, math.radians(45), math.radians(196), 'paint', depth=0.05, part='fork')
    for s in (1, -1):
        for a in (52, 128):
            a = math.radians(a)
            bk.tube([fa + Vector((s * 0.09, 0, 0)), fa + Vector((s * 0.078, math.cos(a) * 0.355, math.sin(a) * 0.355))], 0.0065, 'paint')
    # USA marking on the front fender sides is too small to matter in game; the scabbard is the signature
    _scabbard(bk, ax, ta, da)




def _tank_sec(hw, h, n=28):
    """tank section: full flanks, flatter top, a tunnel under the middle for the top tube."""
    out = []
    for i in range(n):
        a = TAU * i / n
        c, s = math.cos(a), math.sin(a)
        x = hw * math.copysign(abs(c) ** 0.75, c)
        y = h / 2 * math.copysign(abs(s) ** (0.8 if s > 0 else 0.9), s)
        if s < -0.85:  # tunnel
            y += h * 0.12 * (abs(s) - 0.85) / 0.15
        out.append((x, y))
    return out





def _saddle(bk, P, mat):
    """solo saddle: wide sprung seat, rolled rear edge, tapering nose; top line traced from the photo."""
    st = [  # px x, top py, half width, thickness m
        (358, 222, 0.0, 0.04), (362, 214, 0.12, 0.05), (372, 212, 0.155, 0.055), (395, 214, 0.165, 0.055), (420, 220, 0.155, 0.05),
        (450, 228, 0.12, 0.045), (480, 232, 0.085, 0.04), (505, 233, 0.06, 0.04), (525, 232, 0.045, 0.04), (536, 233, 0.03, 0.035),
        (540, 236, 0.0, 0.03)]
    path, secs = [], []
    for x, t, hw, th in st:
        y, z = P(x, t)
        path.append(Vector((0, y, z - th / 2)))
        hw = max(hw, 0.006)
        sec = []
        for i in range(24):
            a = TAU * i / 24
            c, s = math.cos(a), math.sin(a)
            sec.append((hw * math.copysign(abs(c) ** 0.6, c), th / 2 * math.copysign(abs(s) ** 0.7, s) - (abs(c) ** 3) * th * 0.25))
        secs.append(sec)
    bk.sweep(path, secs, mat, cap0=True, cap1=True, frames=parts.yframes(len(path)))
    # pan under it
    y0, z0 = P(370, 248)
    y1, z1 = P(520, 248)
    bk.box((0, (y0 + y1) / 2, z0), (0.2, y1 - y0, 0.01), 'black', bevel=0.003)



def _scabbard(bk, ax, ta, da):
    """Thompson SMG scabbard strapped to the right of the fork: a leather boot, its front edge upright, its back edge
    raking down to a narrow toe; the mouth is cut on a slant."""
    bk.part('fork')
    P = bk.P
    rows = [(190, 840, 874), (218, 762, 874), (280, 784, 873), (350, 804, 871), (420, 822, 868), (462, 836, 863), (478, 846, 858)]
    path, secs = [], []
    for i, (py, xr, xf) in enumerate(rows):
        y0, z = P(xr, py)
        y1, _ = P(xf, py)
        t = i / (len(rows) - 1)
        path.append(Vector((0.16, (y0 + y1) / 2, z)))
        secs.append(superellipse(0.085 - 0.035 * t, max(0.02, y1 - y0), 20, 3.2))
    frames = [(Vector((1, 0, 0)), Vector((0, 1, 0)))] * len(rows)
    # sections: a across (x), b along y
    bk.sweep(path, secs, 'tan', cap0=True, cap1=True, frames=frames)
    for py in (300, 452):
        k = next(i for i, r in enumerate(rows) if r[0] >= py)
        p = path[k].lerp(path[k - 1], (rows[k][0] - py) / (rows[k][0] - rows[k - 1][0]))
        sec = [(a * 1.08, b * 1.04) for a, b in secs[k]]
        bk.sweep([p + Vector((0, 0, 0.018)), p - Vector((0, 0, 0.018))], [sec, sec], 'paint', frames=frames[:2])
        bk.tube([p + Vector((-0.04, -0.02, 0)), ax(0.0 if py < 400 else ta + 0.08, 0.06 if py < 400 else da, 0.075)], 0.006, 'paint')
