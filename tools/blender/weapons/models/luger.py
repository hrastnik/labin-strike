"""Pistole 08 (Luger P08), Mauser S/42 1938. Reference: 'Mauser 9mm Luger S-42 1938 3930 R DSC7744.jpg'
(right side, CC BY-SA 4.0). 222 mm, 4" barrel, toggle lock, checkered walnut grips, aluminium magazine knob.

The photo lies on grey paper with a soft drop shadow, so ref/src/luger.jpg was pre-cleaned: GrabCut foreground,
clipped by a hand-traced polygon along the shadow side (barrel bottom, frame front, guard, grip front), the guard
opening blanked, background painted white, and bright / neutral foreground pixels given a slight blue tint so
reftool's segmentation keeps them (the aluminium knob and the highlights would otherwise read as background).

Toggle ('bolt' part): front link + knuckle knobs + rear link + breech block, pivot at the rear toggle axle.
Magazine ('mag' part): 8 rounds along the grip axis, aluminium knob at the heel."""
import math

from ..lib import ccw, cw, offset_poly, rrect, section

REF = 'luger'
GRIP_A = -120.3                                      # magazine / grip axis (deg from +u)
MAG_DIR = (math.cos(math.radians(GRIP_A)), math.sin(math.radians(GRIP_A)))
META = {'kind': 'pistol', 'client': {'magDir': [0, round(MAG_DIR[1], 3), round(-MAG_DIR[0], 3)]}}
SIGHT_V = 16.2                                       # top of the front blade = bottom of the rear V notch
KNOB = (-57.0, 8.5)                                  # toggle knuckle (knurled knobs)
MAG_TOP = (-27.5, -13.0)


def spline(pts, step=0.8):
    """Catmull-Rom curve through pts (open), resampled to ~step mm segments: smooth outlines from measured points."""
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(1, int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / step + 0.5))
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
    out.append(tuple(pts[-1]))
    return out


def rdp(pts, eps=0.04):
    """Douglas-Peucker simplification (open polyline): drops points on straight runs, keeps curves smooth."""
    if len(pts) < 3:
        return list(pts)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1e-9
    i, dm = 0, -1.0
    for k in range(1, len(pts) - 1):
        d = abs(dy * (pts[k][0] - x0) - dx * (pts[k][1] - y0)) / L
        if d > dm:
            i, dm = k, d
    if dm <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)


def star(cu, cv, r_out, r_in, n):
    pts = []
    for i in range(2 * n):
        a = math.pi * i / n
        r = r_out if i % 2 == 0 else r_in
        pts.append((cu + r * math.cos(a), cv + r * math.sin(a)))
    return pts


def ellipse(c, a, b, t0, t1, n):
    return [(c[0] + a * math.cos(math.radians(t0 + (t1 - t0) * k / n)),
             c[1] + b * math.sin(math.radians(t0 + (t1 - t0) * k / n))) for k in range(n + 1)]


def build(g):
    # ---------------------------------------------------------------- frame: smooth fitted outline (measured off the photo)
    ring_c, ring_a, ring_b, ring_t = (9.0, -35.25), 17.75, 14.3, 1.7      # oval guard ring (semi-axes, bar width)
    # rear of the frame: toggle ramp, the ears block (rounded top-rear corner), rear face, lip over the backstrap
    ramp = spline([(-59.9, -10.4), (-62.8, -8.5), (-65.2, -5.9), (-67.6, -2.5), (-70.2, 1.3), (-72.8, 5.2),
                   (-75.2, 9.0), (-77.2, 12.1), (-78.9, 14.0), (-81.0, 14.8), (-84.0, 15.1), (-88.0, 15.5),
                   (-91.0, 15.5), (-93.3, 14.5), (-95.0, 12.6), (-96.0, 10.0), (-96.3, 6.0), (-96.1, 2.0),
                   (-95.9, -2.0), (-95.7, -6.0), (-95.4, -10.4)])
    lip = spline([(-95.4, -10.4), (-94.7, -12.2), (-94.8, -14.0), (-95.8, -15.2), (-96.0, -16.0), (-95.2, -16.5),
                  (-93.4, -16.4), (-91.4, -17.0)])
    backstrap = spline([(-91.4, -17.0), (-89.4, -18.0), (-87.3, -19.5), (-84.5, -21.2), (-81.0, -22.9), (-77.9, -25.0),
                        (-75.3, -27.8), (-73.5, -31.0), (-72.3, -35.0), (-72.0, -39.5), (-72.6, -43.8), (-74.2, -47.5),
                        (-76.4, -50.8), (-79.5, -55.0), (-83.2, -60.0), (-86.8, -65.0), (-90.2, -70.0), (-94.0, -75.0),
                        (-97.6, -79.8), (-101.0, -83.6), (-102.9, -87.4), (-103.7, -91.0), (-103.8, -96.0),
                        (-103.8, -103.0), (-103.7, -107.4)], step=1.0)
    bottom = (spline([(-103.7, -107.4), (-102.2, -109.2), (-100.0, -110.3), (-95.0, -112.5), (-92.5, -113.4)])[1:]
              + [(-83.0, -114.6)]
              + spline([(-82.4, -116.0), (-81.8, -120.0), (-80.6, -121.0), (-77.0, -120.8), (-72.0, -120.6),
                        (-68.0, -120.2), (-65.6, -119.4), (-64.2, -118.4), (-63.4, -117.4)]))
    frontstrap = spline([(-63.4, -117.4), (-62.4, -115.0), (-61.4, -112.0), (-60.0, -110.0), (-59.0, -108.0), (-57.5, -104.0),
                         (-55.8, -100.0), (-53.5, -95.0), (-50.5, -90.0), (-46.8, -85.0), (-43.0, -80.0), (-39.2, -75.0),
                         (-36.2, -70.0), (-33.2, -65.0), (-30.0, -60.0), (-26.6, -55.0), (-23.8, -51.8), (-21.0, -49.6),
                         (-17.4, -47.8), (-13.2, -46.2), (-10.0, -46.0), (-6.5, -46.2)], step=1.0)
    # the side walls hug (overlap) the guard ring from the web under its rear round over the top to its front lug
    hug = ellipse(ring_c, ring_a - 0.3, ring_b - 0.3, 222, 12, 50)
    front = spline([hug[-1], (26.6, -29.6), (27.2, -27.2), (29.5, -25.6), (33.0, -24.4), (35.4, -23.4), (37.2, -21.0),
                    (38.4, -18.0), (39.2, -15.0), (39.9, -12.0), (40.3, -10.4)])
    lower_rear = rdp(backstrap, 0.05) + bottom + rdp(frontstrap, 0.05)[1:]
    # lower frame: full width; its top edge in the ears area forms the bottom rim of the ear recesses
    lower = ([(40.3, -10.4), (-95.4, -10.4)] + rdp(lip)[1:] + lower_rear + hug
             + rdp(front)[1:-1])
    g.extrude(ccw(lower), width=21.0, mat='blued_old', bevel=0.8, name='frame')
    # ears block: core (its side face is the recess floor) + raised rims around the recesses, no booleans
    ears = rdp(ramp, 0.05) + [(-95.3, -14.0), (-60.0, -14.0)]
    core = g.extrude(ccw(ears), width=19.8, mat='blued_old', bevel=0.8, name='ears')
    g.cut(core, g.box(-99, -58, 8.5, 20, -7.0, 7.0, cutter=True, bevel=0))      # slot for the rear toggle link
    recess = ([(-93.4, -12.5, 0), (-93.4, 10.6, 2.6), (-83.6, 10.6, 2.0)]
              + spline([(-81.4, 9.4), (-79.6, 7.0), (-77.0, 3.0), (-74.0, -1.4), (-71.2, -5.4), (-69.4, -8.4),
                        (-68.6, -10.6), (-68.9, -12.5)], step=0.7))
    for s in (1, -1):
        g.extrude(ccw(ears), min(8.0 * s, 10.45 * s), max(8.0 * s, 10.45 * s), 'blued_old', bevel=0.6, seg=2,
                  holes=[cw(recess)], name='earrim')
    # guard ring (round bar bent into a ring around w)
    g.extrude(ellipse(ring_c, ring_a, ring_b, 0, 360, 48)[:-1], width=9.2, mat='blued_old', bevel=1.0, seg=2, name='guard',
              holes=[ellipse(ring_c, ring_a - ring_t, ring_b - ring_t, 360, 0, 48)[:-1]])
    # trigger
    trig = [(-6.0, -20), (0.5, -20), (-0.5, -28.3), (-0.1, -33.3), (1.2, -38.3), (3.7, -42.5), (7.0, -45.8),
            (8.6, -47.4), (8.0, -48.0), (4.5, -46.6), (1.2, -43.8), (-2.2, -38.8), (-3.9, -33.3), (-4.4, -26.7),
            (-5.5, -23)]
    g.extrude(trig, width=7.0, mat='blued', bevel=0.6, name='trigger')
    # takedown lever axle and the trigger-plate pin (right side), takedown lever + safety (left side)
    g.lathe([(10.4, 0), (10.4, 3.6), (11.2, 3.3), (11.6, 2.2), (11.8, 0)], 'blued', axis='w', at=(34.5, -17.5), seg=20)
    g.lathe([(10.4, 0), (10.4, 1.4), (11.0, 1.1), (11.1, 0)], 'blued', axis='w', at=(2.0, -16.5), seg=10)
    g.extrude([(27, -14), (40, -14.5, 1.5), (40, -21, 1.5), (31, -22), (27, -19)], -11.6, -10.3, 'blued', bevel=0.3)
    g.extrude([(-80, -15), (-67, -13.5, 1), (-66, -9.5, 1), (-80, -10.5, 1)], -11.6, -10.3, 'blued', bevel=0.3)
    # left side plate over the trigger bar
    g.extrude(rrect(-42, 6, -9.5, -3.5, 1.5), -11.1, -10.3, 'blued_old', bevel=0.3)

    # ---------------------------------------------------------------- grip panels (checkered walnut)
    panel = ([(-11.9, -16.9), (-69.9, -16.9)] + spline([(-69.9, -16.9), (-72.6, -21.8), (-75.4, -24.6),
                                                        (-77.9, -25.0)])[1:-1]
             + [p for p in lower_rear if p[1] < -25.2 and p[0] < -8.5] + [(-8.1, -46.2), (-8.1, -21.1)])
    panel = offset_poly(ccw(panel), -1.4)
    g.sweep(panel, 'checker_w', width=31.0, radius=(6.5, 6.5), axis=GRIP_A, origin=(-42, -40), step=4.0, n=3,
            name='grip')
    for s in (1, -1):                                  # grip screw
        g.lathe([(15.0 * s, 0), (15.0 * s, 3.2), (15.9 * s, 2.8), (16.3 * s, 1.5), (16.4 * s, 0)], 'blued', axis='w',
                at=(-55, -62), seg=14)
    # heel boss with a slot (magazine knob seat)
    g.lathe([(9.0, 0), (9.0, 4.4), (10.8, 4.0), (11.4, 2.6), (11.5, 0)], 'blued', axis='w', at=(-80.5, -104), seg=18)

    # ---------------------------------------------------------------- receiver (barrel extension)
    rec = g.extrude(section(21.0, 21.0, 20.4, 1.2, 1.0, 2, y0=-10.4), -66, 21.0, 'blued_old', plane='front',
                    bevel=0.5, name='receiver')
    g.extrude(section(21.0, 21.0, 22.0, 2.5, 1.0, 3, y0=-10.4), 20.8, 40.5, 'blued_old', plane='front', bevel=0.6,
              name='recfront')
    # side grooves (the frame / barrel-extension seam and the side-plate slot)
    cs = []
    for s in (1, -1):
        w0 = 10.5 * s
        cs.append(g.box(-60, 40, -5.4, -4.8, w0 - 0.5 * s, w0 + 2 * s, cutter=True, bevel=0))
        cs.append(g.extrude(rrect(-52, -11.5, -1.4, 0.4, 0.9), w0 - 0.5 * s, w0 + 2 * s, cutter=True, bevel=0))
    g.cut(rec, *cs)

    # ---------------------------------------------------------------- barrel, front sight
    g.lathe([(40.0, 0), (40.0, 8.8), (42.6, 8.8), (43.0, 8.0), (60, 7.85), (107.8, 7.0), (108.2, 7.45),
             (121.8, 7.45), (122.9, 6.4), (123.7, 4.2), (124.0, 0)], 'blued', seg=32, name='barrel')
    g.cyl(123.0, 124.1, 4.5, 'black', seg=16)
    g.extrude([(108.6, 6.0), (122.4, 6.0), (122.0, 8.4), (109.4, 8.4)], width=7.5, mat='blued', bevel=0.5)
    blade = [(109.6, 8.0), (122.6, 8.0), (121.6, 9.6), (120.2, 11.6), (118.6, 13.6), (117.0, 15.3), (115.6, SIGHT_V),
             (114.0, SIGHT_V), (112.6, 14.6), (111.0, 11.6)]
    g.extrude(blade, width=2.6, mat='blued', bevel=0.4, name='frontsight')

    # ---------------------------------------------------------------- toggle = 'bolt'
    with g.part('bolt'):
        # breech block + front link (one profile; the block runs inside the receiver, the link on top)
        g.extrude([(-49, 6.0), (-3, 6.0), (-3, 10.6), (-4.5, 12.6), (-8, 14.3, 1.0), (-10.5, 14.7, 1.0), (-15.5, 14.7, 1.0),
                   (-19, 13.6), (-48, 13.6)], width=13.0, mat='blued', bevel=0.5, name='frontlink')
        g.box(-46, -4, 4.0, 9.6, width=19.4, mat='blued', bevel=0.4)          # block top between the side walls
        g.lathe([(6.6, 0), (6.6, 2.4), (7.0, 2.1), (7.2, 0)], 'blued', axis='w', at=(-14.5, 10.5), seg=12)
        g.lathe([(-6.6, 0), (-6.6, 2.4), (-7.0, 2.1), (-7.2, 0)], 'blued', axis='w', at=(-14.5, 10.5), seg=12)
        # extractor on top of the block
        g.extrude([(-38, 13.4), (-26, 13.4), (-26.5, 14.2), (-37.5, 14.2)], width=3.0, mat='blued', bevel=0.2)
        # rear link with the rear sight
        g.extrude([(-92, 8.6), (-75.5, 8.6), (-72.5, 4.5), (-69.5, 0.5), (-66.5, -3.5), (-63, -6.5), (-56, -6.5),
                   (-56, 14.9), (-91.5, 14.9, 1.2)], width=13.4, mat='blued', bevel=0.5,
                  name='rearlink')
        rs = g.extrude([(-90.8, 14.3), (-85.6, 14.3), (-86.2, 16.8, 0.6), (-87.6, 18.0, 0.5), (-89.6, 18.0, 0.5),
                        (-90.6, 16.9)], width=6.0, mat='blued', bevel=0.3, name='rearsight')
        g.cut(rs, g.extrude([(0, SIGHT_V), (2.2, 19), (-2.2, 19)], -95, -84, plane='front', cutter=True, bevel=0))
        # knuckle with the knurled knobs
        g.cyl(-12.0, 12.0, 6.0, 'blued', axis='w', at=KNOB, seg=24)
        for s in (1, -1):
            hole = ellipse(KNOB, 3.2, 3.2, 360, 0, 16)[:-1]
            g.extrude(star(*KNOB, 9.1, 8.5, 38), min(7.0 * s, 13.4 * s), max(7.0 * s, 13.4 * s), 'blued', bevel=0,
                      holes=[hole], name='knob')
            g.cyl(min(11.0 * s, 12.6 * s), max(11.0 * s, 12.6 * s), 3.3, 'blued', axis='w', at=KNOB, seg=16)       # recessed centre
    g.pivot('bolt', -88.0, 11.5)

    # ---------------------------------------------------------------- magazine (8 rounds) with aluminium knob
    with g.part('mag'):
        du, dv = MAG_DIR
        nu, nv = -dv, du
        P = lambda t, n: (MAG_TOP[0] + du * t + nu * n, MAG_TOP[1] + dv * t + nv * n)
        g.extrude([P(1, -16), P(1, 15), P(112, 15), P(112, -16)], width=11.0, mat='blued', bevel=0.5,
                  name='magbody')
        kc = (-88.0, -117.3)
        g.lathe([(-10.8, 0), (-10.8, 6.4), (-10.2, 7.1), (10.2, 7.1), (10.8, 6.4), (10.8, 0)], 'bright', axis='w',
                at=kc, seg=28, name='magknob')
        for s in (1, -1):                              # knob face rings
            g.lathe([(10.6 * s, 0), (10.6 * s, 3.0), (11.0 * s, 2.6), (11.0 * s, 0)], 'bright', axis='w', at=kc,
                    seg=16)
        # top round
        g.lathe([(-38, 0), (-38, 4.4), (-23, 4.5), (-19, 4.0), (-15.5, 0)], 'brass', at=(-8.6, 0), seg=14)
    g.pivot('mag', *MAG_TOP)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 124.0, 0)
    g.anchor('sight', -88.2, SIGHT_V)
    g.anchor('eject', -28, 14, 4)
    g.anchor('rh', -60, -62, 0)
    g.anchor('lh', -66, -84, 0)
    g.anchor('eye', -450, SIGHT_V)
