"""Colt M1911A1 (Remington Rand). Reference: 'Remington Rand M1911A1 revers (6825681426).jpg' (right side,
Askild Antonsen, CC BY 2.0). 216 mm, parkerized slide/frame, brown chequered plastic grips, arched mainspring
housing, short chequered trigger, 7-round single-stack magazine. Thumb safety, slide stop and magazine catch
button are on the LEFT side; cases eject to the right."""
import math

import numpy as np

from ..lib import bezier, offset_poly, rrect, section

REF = 'm1911'
GRIP_A = -108.0                     # grip / magazine axis (deg from +u)
GDU, GDV = math.cos(math.radians(GRIP_A)), math.sin(math.radians(GRIP_A))
META = {'kind': 'pistol', 'client': {'magDir': [0, round(GDV, 3), round(-GDU, 3)]}}

SIGHT_V = 12.3                      # front blade top; the rear notch bottoms out 1 mm below it so the blade shows
FIN = 'park'


def smooth_edges(outline, origin, axis_deg, t0, t1, step=3, deg=2, lo_cut=20, hi_cut=10):
    """front/back edges of a swept part as smooth polynomial fits of the traced outline's crossings
    perpendicular to the axis (see stg44.mag_edges) -> (T, lo, hi, to_uv)."""
    a = math.radians(axis_deg)
    du, dv = math.cos(a), math.sin(a)
    nu, nv = -dv, du
    loc = [((p[0] - origin[0]) * du + (p[1] - origin[1]) * dv, (p[0] - origin[0]) * nu + (p[1] - origin[1]) * nv)
           for p in outline]
    ts, los, his = [], [], []
    t = t0
    while t <= t1:
        xs = []
        for i in range(len(loc)):
            (s0, n0), (s1, n1) = loc[i - 1], loc[i]
            if (s0 - t) * (s1 - t) < 0:
                xs.append(n0 + (n1 - n0) * (t - s0) / (s1 - s0))
        if len(xs) >= 2:
            ts.append(t)
            los.append(min(xs))
            his.append(max(xs))
        t += step
    T = np.array(ts)
    m = (T > T[0] + lo_cut) & (T < T[-1] - hi_cut)
    lo = np.polyval(np.polyfit(T[m], np.array(los)[m], deg), T)
    hi = np.polyval(np.polyfit(T[m], np.array(his)[m], deg), T)

    def to_uv(t, n):
        return (origin[0] + du * t + nu * n, origin[1] + dv * t + nv * n)
    return T, lo, hi, to_uv


def screw(g, u, v, w, r, mat=FIN, slot=True):
    s = 1 if w > 0 else -1
    g.lathe([(w, 0), (w, r), (w + s * 0.7, r * 0.9), (w + s * 1.1, r * 0.55), (w + s * 1.2, 0)], mat, axis='w',
            at=(u, v), seg=14)


def build(g):
    # ---------------------------------------------------------------- slide
    prof = [(-11.6, -13.3), (11.6, -13.3), (11.6, 3.6), (8.6, 10.8, 4.5), (-8.6, 10.8, 4.5), (-11.6, 3.6)]
    sl = g.extrude(prof, -60.6, 122.0, FIN, plane='front', bevel=0.6, name='slide')
    # hammer slot at the rear, ejection port on the right
    g.cut(sl, g.box(-62, -55, -14, 4.5, -4.6, 4.6, cutter=True, bevel=0),
          g.box(4.0, 32.0, 2.6, 9.4, 6.0, 20, cutter=True, bevel=0))
    # rear cocking serrations, both sides
    cs = []
    for i in range(22):
        u = -47.6 + i * 1.45
        for s in (1, -1):
            cs.append(g.box(u - 0.4, u + 0.4, -12.6, 5.0, 11.0 * s - (0 if s > 0 else 4), 11.0 * s + (4 if s > 0 else 0),
                            cutter=True, bevel=0))
    g.cut(sl, *cs)
    # lower nose: recoil spring tunnel under the barrel, ahead of the frame's dust cover
    nose = g.extrude(section(21.0, 21.0, 13.6, 0.5, 8.5, 5, y0=-26.6), 83.6, 122.0, FIN, plane='front', bevel=0.6,
                     name='nose')
    g.cut(nose, g.cyl(115, 125, 4.6, at=(-19.6, 0), seg=18, cutter=True))
    # recoil spring plug, barrel bushing, barrel (muzzle and chamber hood in the port)
    g.lathe([(116, 0), (116, 4.4), (122.4, 4.4), (122.9, 3.8), (122.9, 0)], FIN, at=(-19.6, 0), seg=18)
    g.lathe([(118, 0), (118, 9.6), (122.0, 9.6), (124.6, 9.2), (125.4, 8.0), (125.4, 0)], FIN, at=(0, 0), seg=32,
            name='bushing')
    g.lathe([(-4, 0), (-4, 7.2), (125.8, 7.2), (125.8, 0)], 'blued', at=(0, 0), seg=28, name='barrel')
    g.cyl(124.5, 125.9, 5.7, 'black', at=(0, 0), seg=18)
    g.box(-4, 34, -1, 8.4, width=13.4, mat='blued', bevel=0.8, name='hood')
    # extractor tail at the slide rear, firing pin stop
    g.box(-60.9, -59.8, -3.5, 3.5, width=9.0, mat=FIN, bevel=0.3)
    g.cyl(-61.2, -60, 1.3, 'bright', at=(0, 0), seg=10)

    # ---------------------------------------------------------------- sights
    blade = [(109.4, 10.2), (120.6, 10.2), (120.0, 11.0), (117.6, 12.1), (114.6, SIGHT_V), (112.0, 11.9),
             (110.4, 11.0)]
    g.extrude(blade, width=1.5, mat=FIN, bevel=0.3, name='frontsight')
    rs = g.extrude([(-52.6, 10.2), (-42.4, 10.2), (-44.6, 13.2, 0.8), (-46.6, 15.5, 0.5), (-49.2, 15.5, 0.5),
                    (-51.2, 13.2, 0.8)], width=11.0, mat=FIN, bevel=0.4, name='rearsight')
    g.cut(rs, g.extrude([(-1.2, SIGHT_V - 1), (1.2, SIGHT_V - 1), (1.4, 17), (-1.4, 17)], -55, -40, plane='front',
                        cutter=True, bevel=0))

    # ---------------------------------------------------------------- frame
    upper = g.outline([(-102, -13.3), (83.6, -13.3), (83.6, -30.5), (-102, -30.5)])
    g.extrude(upper, width=20.4, mat=FIN, bevel=0.8, name='frame')
    # trigger guard: explicit smooth curves (the trace closes on itself), flared web into the dust cover at the front
    g_out = ([(-11.0, -29.0), (33.4, -29.0)] + bezier((31.4, -44.0), (30.6, -50.0), (26.0, -55.8), (19.0, -55.8), 9)
             + bezier((4.0, -55.8), (-3.0, -55.8), (-9.6, -51.0), (-10.4, -44.0), 9) + [(-12.4, -38.0)])
    g_in = ([(-2.0, -30.4)] + bezier((21.0, -30.4), (25.5, -30.4), (28.5, -33.5), (29.4, -37.5), 7)
            + bezier((29.8, -42.0), (29.4, -48.0), (25.5, -52.6), (19.0, -52.6), 9)
            + bezier((4.0, -52.6), (-1.0, -52.6), (-2.8, -49.0), (-3.1, -44.0), 8) + [(-3.4, -38.0)])
    g.extrude(g_out, width=8.6, mat=FIN, holes=[g_in], bevel=0.9, name='guard')
    g.extrude([(28, -26.0), (40.0, -26.0), (38.5, -28.5), (36.0, -30.4), (34.0, -32.5), (33.0, -35.0), (28, -35.0)],
              width=12.0, mat=FIN, bevel=0.8, name='guardweb')
    # grip frame (front strap, grip safety, arched mainspring housing): traced, front/back edges smoothed
    gt = g.outline([(-102, -29), (-11.5, -29), (-11.5, -60), (0, -60), (0, -128), (-80, -121), (-83, -116), (-102, -116)])
    T, lo, hi, to_uv = smooth_edges(gt, (-50, -30), GRIP_A, 0, 101, step=3, deg=3, lo_cut=36, hi_cut=6)
    strap = [to_uv(t, n) for t, n in zip(T, lo)] + [to_uv(t, n) for t, n in zip(T[::-1], hi[::-1])]
    g.sweep(gt, FIN, width=19.3, radius=(5.4, 3.9), axis=GRIP_A, origin=(-50, -30), step=2.5, t1=40, name='gripframe')
    gf2 = g.sweep(strap, FIN, width=19.6, radius=(5.5, 4.0), axis=GRIP_A, origin=(-50, -30), step=2.5, t0=38,
                  name='gripframe2')
    bottom = lambda u: -115.0 - (u + 87.5) * 0.119          # the grip's flat bottom (slightly raked)
    g.cut(gf2, g.extrude([(-110, bottom(-110)), (10, bottom(10)), (10, -150), (-110, -150)], width=60, cutter=True,
                         bevel=0))
    # trigger (short, chequered face)
    trig = [(-5.5, -29.5), (3.4, -29.5), (4.2, -34), (4.4, -40), (3.8, -46), (2.4, -50.5), (0.8, -52.6), (-0.8, -52.2),
            (-1.4, -48), (-2.0, -40), (-3.4, -33)]
    g.extrude(trig, width=6.0, mat=FIN, bevel=0.6, name='trigger')

    # hammer (spur, cocked down position as in the photo)
    ham = g.outline([(-86, -13.3), (-60.6, -13.3), (-60.6, 8), (-86, 8)])
    g.extrude(ham, width=8.4, mat=FIN, bevel=0.5, name='hammer')

    # ---------------------------------------------------------------- grip panels (chequered)
    panel = [(-41.0, -18.2, 1.5), (-16.4, -22.6, 2.5), (-17.6, -31.7), (-20.0, -40.0), (-23.3, -50.0), (-28.0, -65.0),
             (-32.5, -80.0), (-36.7, -96.7), (-43.0, -119.4, 1.5), (-80.4, -115.4, 1.5), (-75.0, -95.0), (-68.0, -77.0),
             (-60.0, -55.0), (-55.0, -40.0), (-48.0, -27.0)]
    gp = g.sweep(panel, 'checker_w', width=31.0, radius=(5.5, 5.5), axis=GRIP_A, origin=(-50, -30), step=2.5,
                 name='grip')
    g.cut(gp, g.extrude([(-110, bottom(-110) + 1.0), (10, bottom(10) + 1.0), (10, -150), (-110, -150)], width=60,
                        cutter=True, bevel=0))
    for u, v in ((-34.2, -30.0), (-61.7, -105.0)):
        for s in (1, -1):
            g.lathe([(14.6 * s, 0), (14.6 * s, 4.6), (15.9 * s, 4.4), (15.9 * s, 0)], 'checker_b', axis='w', at=(u, v),
                    seg=18)                                                         # bushing ring
            screw(g, u, v, 15.6 * s, 3.4)

    # ---------------------------------------------------------------- pins (right side) and left-side controls
    for u, v, r in ((-60.0, -19.6, 2.2), (-70.8, -25.4, 2.6), (-50.8, -26.2, 1.8), (16.3, -20.0, 2.6),
                    (-12.5, -47.9, 3.4)):
        screw(g, u, v, 10.2, r, slot=False)
    # thumb safety (left): pivot plate at the safety pin, thumb piece forward
    g.extrude([(-76.5, -22.0, 3), (-74.0, -29.5, 3), (-66.0, -29.0), (-56.0, -21.0), (-44.0, -20.0, 1.2),
               (-43.5, -14.2, 1.2), (-58.0, -14.4), (-70.0, -18.5)], -11.8, -10.2, FIN, bevel=0.4, name='safety')
    g.extrude([(-52, -14.2), (-43.5, -14.2, 1), (-44.0, -20.0, 1), (-52, -19.4)], -14.0, -11.6, FIN, bevel=0.4)
    g.lathe([(-10.2, 0), (-10.2, 3.0), (-12.4, 3.0), (-12.9, 2.2), (-12.9, 0)], FIN, axis='w', at=(-70.8, -25.4), seg=14)
    # slide stop (left): pivot at the slide stop pin, thumb piece at the rear
    g.extrude([(21.0, -17.0, 4), (19.0, -24.5, 3), (10.0, -23.0), (-6.0, -21.5), (-10.0, -19.0, 1.5), (-9.0, -14.5, 1.5),
               (4.0, -13.5), (14.0, -14.5)], -12.4, -10.2, FIN, bevel=0.4, name='slidestop')
    g.lathe([(-10.2, 0), (-10.2, 3.0), (-12.8, 3.0), (-13.4, 2.2), (-13.4, 0)], FIN, axis='w', at=(16.3, -20.0), seg=14)
    # magazine catch button (left, chequered head)
    g.lathe([(-10.2, 0), (-10.2, 5.0), (-13.0, 5.0), (-13.6, 4.2), (-13.6, 0)], FIN, axis='w', at=(-12.5, -47.9),
            seg=20)
    # lanyard loop under the mainspring housing
    g.pipe([(-86.6, -113.0, -3.2), (-86.6, -125.2, -3.2), (-86.6, -125.2, 3.2), (-86.6, -113.0, 3.2)], 1.3, FIN, seg=8,
           corner=2.6)

    # ---------------------------------------------------------------- magazine (7 rounds, inside the grip)
    with g.part('mag'):
        ou, ov = -22.0, -14.0
        nu, nv = -GDV, GDU
        P = lambda t, n: (ou + GDU * t + nu * n, ov + GDV * t + nv * n)
        body = [P(3.0, -16.0), P(3.0, 16.0), P(106.0, 16.0), P(106.0, -16.0)]
        mb = g.extrude(body, width=13.4, mat='blued', bevel=0.6, name='magbody')
        # feed lips and the top round
        g.extrude([P(3.5, -15.6), P(3.5, 15.0), P(0.6, 13.0), P(0.6, -15.6)], width=11.0, mat='blued', bevel=0.4)
        # top round: lies across the mag axis, nose forward
        a = math.degrees(math.atan2(nv, nu))
        r = g.lathe([(0, 0), (0, 5.9), (19, 5.7)], 'brass', axis='u', at=(0, 0), seg=14, name='case')
        b = g.lathe([(19, 0), (19, 5.6), (24.0, 4.8), (27.5, 2.6), (28.4, 0)], 'bright', axis='u', at=(0, 0), seg=14,
                    name='bullet')
        base = P(-1.2, -15.0)
        g.transform([r, b], rot=('w', a))
        g.transform([r, b], move=(base[0], base[1], 0))
        # floor plate
        g.extrude([P(105.5, -16.4), P(105.5, 23.0), P(108.5, 23.0), P(108.5, -16.4)], width=15.4, mat='blued',
                  bevel=0.6, name='floorplate')
    g.pivot('mag', -22.0, -14.0)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 125.8, 0)
    g.anchor('sight', -47.9, SIGHT_V)
    g.anchor('eject', 18, 6, 11.6)
    g.anchor('rh', -55, -68, 0)
    g.anchor('lh', -50, -86, 0)
    g.anchor('eye', -450, SIGHT_V)
