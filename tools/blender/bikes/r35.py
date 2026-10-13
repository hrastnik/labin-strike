"""BMW R35 (1937-40), Wehrmacht: dark grey all over, 342 cc single, pressed-steel double-loop frame, telescopic fork
with its springs showing at the bottom, shaft drive on the right, rigid rear with a sprung solo saddle and a rack.
Reference: right side, front to the right."""
import math

from mathutils import Matrix, Vector

from . import parts
from .lib import TAU, Bike, catmull, rrect, superellipse

REF = '~/Desktop/bike-reference-photos/bmw-r35.jpg'
CAL = ((131, 309), (524, 311), 1.40, 0.33)
R = 0.33           # tyre radius (3.50-19)
RAKE = math.radians(31)
PAINT = (84, 90, 88)  # Wehrmacht dark grey, lifted a little so it reads in the game's light


def build(bk: Bike):
    P, P3 = bk.P, bk.P3
    wb = CAL[2]
    ra = Vector((0, -wb / 2, R))
    fa = Vector((0, wb / 2, R))
    hc = P3(414, 182)
    up = Vector((0, -math.sin(RAKE), math.cos(RAKE)))
    fw = Vector((0, math.cos(RAKE), math.sin(RAKE)))

    def ax(t, d=0.0, x=0.0):
        return hc + up * t + fw * d + Vector((x, 0, 0))

    bk.pivot('fork', hc, Matrix.Rotation(RAKE, 3, 'X'))
    bk.pivot('wheel_f', fa)
    bk.pivot('wheel_r', ra)

    # ---------------- wheels ----------------
    spec = dict(rim_r=0.255, rim_w=0.065, tire_w=0.092, tire_h=0.088, hub_r=0.03, hub_w=0.12, drum_r=0.085,
                flange_r=0.045, flange_x=0.038, spokes=36, cross=0.75)
    wm = {'rubber': 'rubber', 'rim': 'paint', 'hub': 'paint', 'spoke': 'steel', 'steel': 'steel'}
    parts.wheel(bk, 'wheel_r', R, dict(spec, drum_side=-1, drum_r=0.09), wm, static=('body', ra))
    parts.wheel(bk, 'wheel_f', R, dict(spec, drum_side=1, drum_r=0.088), wm, static=('fork', fa))

    # ---------------- frame: pressed steel, oval-ish sections ----------------
    bk.part('body')
    def beam(pts, w=0.034, h=0.03, smooth=6):
        path = catmull(pts, smooth) if smooth else [Vector(p) for p in pts]
        bk.sweep(path, rrect(w, h, min(w, h) * 0.4, 3), 'paint', cap0=True, cap1=True)

    head_top, head_bot = ax(0.07), ax(-0.08)
    bk.cyl(head_top, head_bot, 0.026, 'paint', seg=14)
    # backbone: head -> under the tank -> splits to the rear axle
    split = P3(232, 247)
    beam([ax(0.03, -0.02), P3(380, 200), P3(320, 218), split], 0.045, 0.038)
    for s in (1, -1):
        x = s * 0.09
        beam([split + Vector((s * 0.01, 0, 0)), P3(190, 266, x * 0.8), ra + Vector((x, 0.02, 0.03))], 0.03, 0.026, smooth=0)
        # double loop: down round the front of the engine, under it, back up to the axle
        xl = s * 0.06
        beam([ax(-0.06, -0.01, s * 0.02), P3(399, 222, xl), P3(397, 280, xl), P3(394, 330, xl), P3(384, 352, xl),
              P3(355, 359, xl), P3(300, 359, xl), P3(255, 348, xl * 1.2), P3(185, 330, x), ra + Vector((x, 0.03, -0.012))], 0.03, 0.032)
        # rear axle plates (the R35 has no rear suspension)
        bk.prism([(ra.y - 0.06, ra.z - 0.03), (ra.y + 0.06, ra.z - 0.035), (ra.y + 0.07, ra.z + 0.035), (ra.y - 0.03, ra.z + 0.05)],
                 x - 0.005, x + 0.005, 'paint', bevel=0.004)
        # stays up to the rack / saddle
        beam([ra + Vector((x, -0.02, 0.03)), P3(118, 200, x * 1.05)], 0.022, 0.018, smooth=0)
        beam([ra + Vector((x, 0.03, 0.04)), P3(205, 225, x * 0.8)], 0.02, 0.018, smooth=0)

    # ---------------- engine: upright single ----------------
    # crankcase and gearbox: one cast aluminium block, the crankcase rounded at the front
    def block(x0, x1, y0, y1, z0, z1, r):
        poly = []
        for cy, cz, a0 in ((y0 + r, z0 + r, 180), (y1 - r, z0 + r, 270), (y1 - r, z1 - r, 0), (y0 + r, z1 - r, 90)):
            poly += [(cy + r * math.cos(a), cz + r * math.sin(a)) for a in _arc(a0, a0 + 90)]
        bk.prism(poly, x0, x1, 'alu', bevel=0.012, seg=2)
    (yc0, zc0), (yc1, zc1) = P(316, 356), P(390, 286)
    block(-0.075, 0.08, yc0, yc1, zc0, zc1, 0.05)
    (yg0, zg0), (yg1, zg1) = P(262, 350), P(318, 280)
    block(-0.065, 0.065, yg0, yg1, zg0, zg1, 0.035)
    cc = P3(352, 320)
    # sump, and the bell of the oil filler on the gearbox
    (ys0, zs0), (ys1, zs1) = P(332, 366), P(386, 352)
    bk.box(Vector((0, (ys0 + ys1) / 2, (zs0 + zs1) / 2)), (0.12, ys1 - ys0, zs1 - zs0 + 0.01), 'alu', bevel=0.01)
    bk.lathe([(0.0, 0.0), (0.04, 0.0), (0.036, 0.02), (0.02, 0.045), (0.012, 0.06), (0.014, 0.068), (0.0, 0.07)], P3(288, 282), (0, 0, 1), 'alu', seg=18)
    # timing cover on the right of the crankcase
    bk.lathe([(0.0, 0.0), (0.075, 0.0), (0.078, 0.008), (0.07, 0.016), (0.0, 0.02)], P3(352, 322, 0.08), (1, 0, 0), 'alu', seg=28)
    for k in range(6):
        a = TAU * k / 6
        bk.cyl(P3(352, 322, 0.096) + Vector((0, math.cos(a) * 0.06, math.sin(a) * 0.06)), P3(352, 322, 0.104) + Vector((0, math.cos(a) * 0.06, math.sin(a) * 0.06)),
               0.005, 'steel', seg=6)
    # barrel: square fins, iron; head: alu, rocker box on top
    cyl_b = P3(368, 286)
    d = Vector((0, 0.04, 1)).normalized()
    fins = lambda t, w, h, mat: bk.sweep([cyl_b + d * t, cyl_b + d * (t + 0.0035)], [rrect(w, h, 0.015, 2)] * 2, mat, cap0=True, cap1=True,
                                         frames=[(Vector((1, 0, 0)), Vector((0, 1, 0)))] * 2)
    for i in range(12):
        fins(0.006 + i * 0.0115, 0.15, 0.165, 'iron')
    bk.cyl(cyl_b - d * 0.01, cyl_b + d * 0.15, 0.048, 'iron', seg=16)
    hd = cyl_b + d * 0.15
    for i in range(5):
        fins(0.152 + i * 0.012, 0.16, 0.17, 'alu')
    bk.cyl(hd, hd + d * 0.06, 0.06, 'alu', seg=16)
    bk.box(hd + d * 0.075, (0.1, 0.12, 0.03), 'alu', bevel=0.01)
    # spark plug on the right
    bk.cyl(hd + d * 0.03 + Vector((0.06, 0, 0)), hd + d * 0.04 + Vector((0.1, 0, 0)), 0.008, 'white', seg=6)
    # push rod tubes on the right of the barrel
    for dy in (-0.015, 0.015):
        bk.cyl(cc + Vector((0.07, dy, 0.05)), hd + Vector((0.07, dy, 0.02)), 0.008, 'steel', seg=8)
    # carburettor behind the barrel, intake up to the air filter under the tank
    carb = P3(312, 245)
    bk.box(carb, (0.05, 0.05, 0.045), 'alu', bevel=0.01)
    bk.cyl(carb + Vector((0, 0, -0.02)), carb + Vector((0, 0, -0.07)), 0.02, 'alu', seg=12)
    bk.cyl(carb + Vector((0, 0.025, 0)), hd + Vector((0, -0.08, 0.01)), 0.016, 'alu', seg=10)
    bk.tube([carb + Vector((0, -0.02, 0.01)), P3(305, 222)], 0.018, 'black', seg=10)
    # air filter box under the tank
    af = P3(326, 220)
    bk.box(af, (0.17, 0.15, 0.07), 'paint', bevel=0.02)
    # exhaust (left): from the front of the head, down round the crankcase, along the bottom, long silencer
    ex0 = hd + Vector((-0.06, 0.08, 0.02))
    bk.tube([ex0, ex0 + Vector((-0.04, 0.05, -0.04)), P3(400, 300, -0.13), P3(388, 362, -0.14), P3(330, 375, -0.15), P3(250, 372, -0.155)],
            0.018, 'black', smooth_path=5)
    m0, m1 = P3(255, 372, -0.155), P3(55, 335, -0.16)
    L = (m1 - m0).length
    prof = [(0.0, 0), (0.018, 0), (0.034, 0.05), (0.036, 0.09), (0.036, L - 0.08), (0.03, L - 0.03), (0.016, L), (0.0, L)]
    bk.lathe(prof, m0, m1 - m0, 'black', seg=18)
    bk.tube([P3(150, 350, -0.15), ra + Vector((-0.1, 0, -0.01))], 0.006, 'paint')
    # shaft drive (right): tube from the gearbox to the bevel box in the rear hub
    sh0, sh1 = P3(250, 305, 0.09), ra + Vector((0.1, 0.06, 0))
    bk.cyl(sh0, sh1, 0.024, 'alu', seg=14)
    bk.lathe([(0.0, -0.03), (0.05, -0.03), (0.07, -0.01), (0.072, 0.02), (0.05, 0.045), (0.02, 0.05), (0.0, 0.05)],
             ra + Vector((0.075, 0, 0)), (1, 0, 0), 'alu', seg=24)

    # ---------------- tank, with the roundels and rubber knee pads ----------------
    prof = [  # px x, top py, bottom py, half width
        (274, 216, 228, 0.06), (282, 206, 232, 0.09), (300, 196, 226, 0.115), (330, 182, 214, 0.125), (360, 170, 210, 0.13),
        (385, 162, 210, 0.128), (398, 163, 208, 0.115), (406, 172, 206, 0.09), (409, 186, 202, 0.05)]
    path, secs = [], []
    for x, t, b, hw in prof:
        yt, zt = P(x, t)
        _, zb = P(x, b)
        path.append(Vector((0, yt, (zt + zb) / 2)))
        secs.append(superellipse(hw * 2, zt - zb, 28, 3.0))
    bk.sweep(path, secs, 'paint', cap0=True, cap1=True, frames=parts.yframes(len(path)))
    # filler cap (left of centre) and the warning lamp
    y, z = P(355, 168)
    bk.lathe([(0.0, -0.01), (0.04, -0.01), (0.042, 0.004), (0.035, 0.016), (0.0, 0.02)], (-0.03, y, z), (0, 0, 1), 'black', seg=18)
    for s in (1, -1):
        y, z = P(398, 200)
        _roundel(bk, Vector((0, y, z)), s, 0.03)
        _pad(bk, Vector((0, *P(322, 212))), s, 0.115, 0.07)

    # ---------------- saddle and its springs ----------------
    st = [(196, 190, 0.0, 0.035), (200, 184, 0.11, 0.04), (215, 183, 0.15, 0.045), (240, 186, 0.145, 0.04), (262, 188, 0.11, 0.035),
          (282, 186, 0.065, 0.03), (296, 183, 0.04, 0.028), (302, 186, 0.0, 0.024)]
    path, secs = [], []
    for x, t, hw, th in st:
        y, z = P(x, t)
        path.append(Vector((0, y, z - th / 2)))
        hw = max(hw, 0.006)
        sc = []
        for i in range(24):
            a = TAU * i / 24
            c, s_ = math.cos(a), math.sin(a)
            sc.append((hw * math.copysign(abs(c) ** 0.6, c), th / 2 * math.copysign(abs(s_) ** 0.7, s_) - (abs(c) ** 3) * th * 0.3))
        secs.append(sc)
    bk.sweep(path, secs, 'leather', cap0=True, cap1=True, frames=parts.yframes(len(path)))
    bk.anchor('seat', P3(235, 184))
    for s in (1, -1):
        bk.spring(P3(208, 196, s * 0.07), P3(214, 240, s * 0.07), 0.017, 0.0032, 7, 'black')
        bk.tube([P3(214, 240, s * 0.07), P3(222, 250, s * 0.05)], 0.008, 'paint')
    bk.tube([P3(292, 192), P3(296, 205), P3(300, 212)], 0.01, 'paint')

    # ---------------- rear fender, rack, lamp, plate ----------------
    parts.fender(bk, ra, 0.37, 0.13, math.radians(-12), math.radians(146), 'paint', depth=0.055, part='body')
    y0, zr = P(64, 192)
    y1, _ = P(188, 192)
    for s in (1, -1):
        bk.tube([(s * 0.085, y0, zr - 0.01), (s * 0.085, y0 + 0.01, zr), (s * 0.085, y1, zr)], 0.008, 'paint', bend=0.01)
        bk.tube([(s * 0.085, y0 + 0.03, zr), P3(118, 228, s * 0.075)], 0.008, 'paint')
    for k in range(5):
        yy = y0 + 0.02 + k * (y1 - y0 - 0.04) / 4
        bk.tube([(0.085, yy, zr), (-0.085, yy, zr)], 0.006, 'paint')
    # leather straps on the rack
    for yy in (y0 + 0.08, y1 - 0.08):
        bk.box((0, yy, zr + 0.006), (0.2, 0.02, 0.004), 'tan')
    tl = P3(40, 224)
    bk.lathe([(0.0, 0.0), (0.024, 0.0), (0.028, -0.02), (0.024, -0.045), (0.0, -0.045)], tl + Vector((0, 0.02, 0)), (0, 1, 0), 'paint', seg=14)
    bk.lathe([(0.0, -0.046), (0.02, -0.046), (0.0, -0.05)], tl + Vector((0, 0.02, 0)), (0, 1, 0), 'red', seg=12)
    _plate(bk, [P3(24, 232, -0.1), P3(24, 232, 0.1), P3(28, 272, 0.1), P3(28, 272, -0.1)], 'back')

    # ---------------- footrests, kick start, stand ----------------
    for s in (1, -1):
        p0 = P3(292, 336, s * 0.08)
        p1 = P3(292, 336, s * 0.22)
        bk.anchor('foot_r' if s > 0 else 'foot_l', P3(292, 330, s * 0.17))
        bk.cyl(p0, p1, 0.008, 'paint', seg=8)
        bk.lathe([(0.0, 0.0), (0.017, 0.0)] + [(0.018 if k % 2 else 0.0155, 0.006 + k * 0.009) for k in range(10)] + [(0.016, 0.1), (0.0, 0.1)],
                 p1 - Vector((s * 0.1, 0, 0)), (s, 0, 0), 'rubber', seg=10)
    bk.tube([P3(300, 318, 0.12), P3(330, 338, 0.14), P3(370, 330, 0.15)], 0.008, 'steel', bend=0.02)
    bk.box(P3(372, 330, 0.16), (0.03, 0.05, 0.015), 'rubber')
    # brake pedal (left)
    bk.tube([P3(300, 340, -0.11), P3(360, 345, -0.15), P3(375, 338, -0.16)], 0.007, 'paint', bend=0.02)
    # centre stand folded up under the frame
    for s in (1, -1):
        bk.tube([P3(255, 360, s * 0.1), P3(190, 352, s * 0.11)], 0.009, 'paint')
    bk.tube([P3(190, 352, 0.11), P3(190, 352, -0.11)], 0.009, 'paint')

    # ---------------- fork (steers) ----------------
    bk.part('fork')
    ta, da = (fa - hc).dot(up), (fa - hc).dot(fw)
    leg_d = da - 0.01
    for s in (1, -1):
        x = s * 0.075
        # upper tube (shroud), black
        bk.cyl(ax(0.075, leg_d, x), ax(ta + 0.14, leg_d, x), 0.022, 'paint', seg=14)
        # exposed spring and stanchion below it, then the slider end with the axle clamp
        bk.cyl(ax(ta + 0.14, leg_d, x), ax(ta + 0.02, leg_d, x), 0.011, 'steel', seg=10)
        bk.spring(ax(ta + 0.135, leg_d, x), ax(ta + 0.045, leg_d, x), 0.019, 0.0035, 8, 'black')
        bk.cyl(ax(ta + 0.05, leg_d, x), ax(ta - 0.025, leg_d + 0.0, x), 0.019, 'paint', seg=12)
        bk.lathe([(0.0, -0.012), (0.026, -0.012), (0.026, 0.012), (0.0, 0.012)], fa + Vector((x, 0, 0)), (1, 0, 0), 'paint', seg=12)
    # crowns
    for t in (0.07, -0.085):
        bk.box(ax(t, leg_d * 0.55), (0.2, 0.08 + leg_d * 0.6, 0.025), 'paint', bevel=0.008, rot=Matrix.Rotation(-RAKE, 4, 'X'))
    # handlebars: moderate width, slight rise, black grips, levers
    clamp = ax(0.1, 0.02)
    for s in (1, -1):
        bk.tube([clamp, clamp + Vector((s * 0.1, -0.01, 0.02)), clamp + Vector((s * 0.22, -0.09, 0.03)), clamp + Vector((s * 0.31, -0.15, 0.025))],
                0.011, 'black', smooth_path=6)
        g0 = clamp + Vector((s * 0.27, -0.125, 0.028))
        g1 = clamp + Vector((s * 0.38, -0.18, 0.02))
        bk.lathe([(0.0, 0), (0.016, 0), (0.018, 0.01)] + [(0.018 if k % 2 else 0.0165, 0.012 + k * 0.009) for k in range(11)] + [(0.017, 0.12), (0.0, 0.122)],
                 g0, g1 - g0, 'rubber', seg=10)
        lv = clamp + Vector((s * 0.22, -0.08, 0.035))
        bk.tube([lv, lv + Vector((s * 0.06, 0.05, -0.005)), lv + Vector((s * 0.15, 0.0, -0.01))], 0.005, 'steel', bend=0.02)
        bk.anchor('grip_r' if s > 0 else 'grip_l', (g0 + g1) / 2)
    # headlamp: the big bowl carried between the fork shrouds, speedometer in its top
    lamp_c = P3(460, 162)
    lamp_d = Vector((0, 1, -0.03)).normalized()
    bk.lathe([(0.0, -0.085), (0.04, -0.082), (0.066, -0.062), (0.078, -0.03), (0.08, 0.0), (0.083, 0.006), (0.078, 0.013)],
             lamp_c, lamp_d, 'paint', seg=28)
    bk.lathe([(0.0, 0.026), (0.055, 0.015), (0.077, 0.01)], lamp_c, lamp_d, 'lens', seg=28, part='lamp')
    bk.lathe([(0.0, 0.0), (0.024, 0.0), (0.024, 0.005), (0.0, 0.007)], lamp_c + Vector((0, -0.025, 0.075)), (0, -0.25, 1), 'glass', seg=16)
    for s in (1, -1):
        bk.tube([lamp_c + Vector((s * 0.078, -0.02, 0)), lamp_c + Vector((s * 0.09, -0.04, -0.01)), ax(-0.02, leg_d, s * 0.075)], 0.007, 'paint')
    # front fender with the number plate standing on it
    parts.fender(bk, fa, 0.365, 0.12, math.radians(52), math.radians(198), 'paint', depth=0.05, part='fork')
    for s in (1, -1):
        for a in (40, 140):
            a = math.radians(a)
            bk.tube([fa + Vector((s * 0.075, 0, 0)), fa + Vector((s * 0.062, math.cos(a) * 0.35, math.sin(a) * 0.35))], 0.006, 'paint')
    _plate(bk, [P3(497, 211), P3(497, 178), P3(582, 178), P3(582, 222)], 'side')


def _roundel(bk, c, s, r):
    """BMW roundel: black ring, blue and white quarters, projected on the flank."""
    d = Vector((-s, 0, 0))
    segs = 24
    for q in range(4):
        pts = [c]
        for i in range(segs // 4 + 1):
            a = TAU * (q / 4 + i / segs)
            pts.append(c + Vector((0, math.cos(a) * r * 0.72, math.sin(a) * r * 0.72)))
        pts = parts.project(bk, pts, d, 0.0015)
        faces = [(0, k, k + 1) if s > 0 else (0, k + 1, k) for k in range(1, len(pts) - 1)]
        bk.add(pts, faces, 'blue' if q % 2 == 0 else 'white', False, keep=True)
    pts = []
    for i in range(segs):
        a = TAU * i / segs
        for rr in (r * 0.72, r):
            pts.append(c + Vector((0, math.cos(a) * rr, math.sin(a) * rr)))
    pts = parts.project(bk, pts, d, 0.0015)
    faces = []
    for i in range(segs):
        j = (i + 1) % segs
        f = (2 * i, 2 * i + 1, 2 * j + 1, 2 * j)
        faces.append(f if s > 0 else tuple(reversed(f)))
    bk.add(pts, faces, 'black', False, keep=True)


def _plate(bk, quad, facing):
    """Wehrmacht number plate: white with a black border. quad: four corners."""
    q = [Vector(p) for p in quad]
    if facing == 'side':
        bk.plate(q, 0.004, 'white')
        # border, both faces
        for s in (1, -1):
            off = Vector((s * 0.0025, 0, 0))
            _border(bk, [p + off for p in q], s, 0.008)
    else:
        bk.plate(q, 0.004, 'white')
        _border(bk, [p + Vector((0, -0.0025, 0)) for p in q], -1, 0.008, axis='y')


def _border(bk, q, s, w, axis='x'):
    c = sum(q, Vector()) / 4
    inner = [p + (c - p).normalized() * w * 1.4 for p in q]
    verts = q + inner
    faces = []
    for i in range(4):
        j = (i + 1) % 4
        f = (i, j, 4 + j, 4 + i)
        faces.append(f)
    out = bk.add(verts, faces, 'black', False, keep=True)
    # face the plate's outside
    want = Vector((s, 0, 0)) if axis == 'x' else Vector((0, s, 0))
    for f in out:
        f.normal_update()
        if f.normal.dot(want) < 0:
            f.normal_flip()


def _arc(a0, a1, n=4):
    return [math.radians(a0 + (a1 - a0) * k / n) for k in range(n + 1)]


def _pad(bk, c, s, a, b, rings=5, seg=32, t=0.007):
    """oval rubber knee pad, semi-axes a (along y) and b (z), domed t thick, laid on the flank."""
    d = Vector((-s, 0, 0))
    pts = parts.project(bk, [c], d, t)
    for i in range(1, rings + 1):
        k = i / rings
        ring = [c + Vector((0, math.cos(TAU * j / seg) * a * k, math.sin(TAU * j / seg) * b * k)) for j in range(seg)]
        lift = t * (1 - k ** 4) + 0.0015
        pts += [p for p in (parts.project(bk, [q], d, lift)[0] for q in ring)]
    faces = []
    for j in range(seg):
        j2 = (j + 1) % seg
        faces.append((0, 1 + j, 1 + j2))
    for i in range(rings - 1):
        o0, o1 = 1 + i * seg, 1 + (i + 1) * seg
        for j in range(seg):
            j2 = (j + 1) % seg
            faces.append((o0 + j, o1 + j, o1 + j2, o0 + j2))
    if s < 0:
        faces = [tuple(reversed(f)) for f in faces]
    bk.add(pts, faces, 'rubber', True, keep=True)
