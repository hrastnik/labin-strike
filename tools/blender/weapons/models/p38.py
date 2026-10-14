"""Walther P38. Reference: 'Walther P38 1943 Whermacht.jpg' (byf 43, left side, mirrored into the right-side frame
as ref id p38_mirror: `reftool.py fetch p38_mirror`, then mirror ref/src/p38_mirror.jpg left-right and blank the
inset stamp close-up at x 1320-1710, y 690-860 before `rect`). Right-side details (exposed trigger bar, locking
block plunger) from 'Walther P38 at Tula State Museum of Weapons.jpg' (ref id p38).
216 mm, blued slide with the open top over the barrel, brown bakelite grips, 8-round single-stack magazine.
The safety/decocker, slide stop, takedown lever and lanyard loop are on the LEFT side; cases eject to the left."""
import math

from ..lib import ccw, cw, rrect, section

REF = 'p38_mirror'
GRIP_A = -98.4                      # magazine / grip axis (deg from +u)
MAG_DIR = (math.cos(math.radians(GRIP_A)), math.sin(math.radians(GRIP_A)))
META = {'kind': 'pistol', 'client': {'magDir': [0, round(MAG_DIR[1], 3), round(-MAG_DIR[0], 3)]}}

SIGHT_V = 15.0                      # front blade top; the rear notch bottoms out 1 mm below it so the blade shows


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


def superellipse(c, a, b, p, t0, t1, n):
    """points of |x/a|^p + |y/b|^p = 1 around c from angle t0 to t1 (deg)."""
    out = []
    for k in range(n + 1):
        t = math.radians(t0 + (t1 - t0) * k / n)
        ct, st = math.cos(t), math.sin(t)
        out.append((c[0] + a * math.copysign(abs(ct) ** (2 / p), ct), c[1] + b * math.copysign(abs(st) ** (2 / p), st)))
    return out


def grooves(g, target, u0, u1, n, v0, v1, w, depth=0.5, width=0.8, top=None):
    """vertical grooves cut into a side face at w (sign = side). top(u) optionally limits the groove top."""
    cs = []
    for i in range(n):
        u = u0 + (u1 - u0) * i / max(1, n - 1)
        vt = top(u) if top else v1
        s = 1 if w > 0 else -1
        cs.append(g.box(u - width / 2, u + width / 2, v0, vt, w - s * depth if s > 0 else w - 3,
                        w + 3 if s > 0 else w + depth, cutter=True, bevel=0))
    g.cut(target, *cs)


def build(g):
    # ---------------------------------------------------------------- slide
    # rear block (breech), open-top middle (side walls only, the barrel shows between them), nose block
    sl = g.extrude(section(23.0, 23.0, 26.1, 4.0, 0.8, 5, y0=-14.6), -83.2, -3.4, 'blued_old', plane='front',
                   bevel=0.6, name='slide')
    g.cut(sl, g.extrude([(-90, 4), (-83.2, 4), (-83.2, 7.0), (-82.6, 7.6), (-78.4, 7.7), (-76.6, 9.4), (-75.0, 10.7), (-73.4, 11.6),
                         (-73.4, 20), (-90, 20)], -20, 20, cutter=True, bevel=0))
    g.cut(sl, g.cyl(-86, -80, 1.6, at=(5.0, 0), seg=12, cutter=True))        # firing-pin hole
    mid = g.extrude(section(23.0, 23.0, 21.8, 1.2, 0.8, 2, y0=-14.6), -3.6, 44.8, 'blued_old', plane='front',
                    bevel=0.4, name='slidemid')
    g.cut(mid, g.extrude(rrect(-7.6, 7.6, -6.0, 14.0, 2.0), -10, 50, plane='front', cutter=True, bevel=0))
    nose = g.extrude(section(23.0, 23.0, 24.9, 4.0, 0.8, 5, y0=-14.6), 44.6, 56.6, 'blued_old', plane='front',
                     bevel=0.6, name='nose')
    g.cut(nose, g.cyl(40, 60, 6.5, at=(0, 0), seg=28, cutter=True))
    # rear cocking serrations (both sides), front edge raked forward-down
    for side in (11.5, -11.5):
        grooves(g, sl, -77.5, -52.5, 15, -13.6, 0.0, side, depth=0.6, width=0.95,
                top=lambda u: 0.0 if u < -62 else -13.6 + (-51.5 - u) * 1.3)
    # loaded-chamber indicator pin at the rear of the slide top
    g.cyl(-83.6, -80, 1.1, 'bright', at=(6.9, 0), seg=10)
    # extractor (left wall, ahead of the breech face) - cases eject to the left
    g.extrude([(-12, 1.0), (1.5, 1.0), (2.5, 3.0), (-12, 4.0)], -11.9, -10.8, 'blued_old', bevel=0.3)

    # ---------------------------------------------------------------- barrel + front sight
    g.lathe([(-3.2, 0), (-3.2, 6.6), (44, 6.6), (46, 6.35), (106, 6.35), (106.4, 6.9), (120.2, 6.9), (120.6, 6.2),
             (122.2, 6.0), (122.6, 5.3), (122.6, 0)], 'blued', at=(0, 0), seg=32, name='barrel')
    g.tube(118, 122.8, 5.0, 4.5, 'blued', at=(0, 0), seg=20)
    g.cyl(121, 122.8, 4.52, 'black', at=(0, 0), seg=16)        # dark bore
    blade = [(106.5, 5.0), (120.3, 5.0), (120.3, 9.6), (119.2, 11.6), (117.6, 13.3), (115.6, 14.5), (113.2, 15.0),
             (111.6, 15.0), (110.6, 12.0), (108.4, 8.4)]
    g.extrude(blade, width=1.8, mat='blued', bevel=0.3, name='frontsight')
    g.extrude([(105.8, 4.0), (121, 4.0), (121, 7.6), (107.5, 7.6)], width=7.0, mat='blued', bevel=0.5)

    # ---------------------------------------------------------------- rear sight (U notch, bottom under the sight line)
    rs = g.extrude([(-70.6, 11.0), (-62.4, 11.0), (-63.6, 14.4, 0.8), (-65.6, 16.0, 0.6), (-70.6, 16.0, 0.4)],
                   width=12.0, mat='blued', bevel=0.4, name='rearsight')
    notch = [(-1.3, SIGHT_V - 1), (1.3, SIGHT_V - 1), (1.3, 18), (-1.3, 18)]
    g.cut(rs, g.extrude(notch, -75, -58, plane='front', cutter=True, bevel=0))

    # ---------------------------------------------------------------- frame
    # outline from measured mask edges as smooth splines (a traced outline shades faceted up close)
    gc = (0.1, -42.0)                                         # trigger-guard opening centre
    front = spline([(56.8, -14.0), (56.7, -18.0), (56.0, -20.2), (54.3, -21.3), (50.5, -22.2), (47.0, -23.5),
                    (43.5, -25.5), (39.5, -27.3), (35.5, -28.9), (32.0, -30.8), (29.0, -32.8), (27.0, -34.8),
                    (25.8, -37.5), (25.5, -40.5), (25.6, -42.5)])
    # frame bottom: just outside the opening's upper half, then down its rear side into the web below the guard
    rim = (superellipse(gc, 23.4, 11.8, 2.8, 0, 180, 36)
           + superellipse(gc, 23.4, 16.3, 2.5, 180, 240, 14)[1:])
    web = spline([rim[-1], (-16.0, -59.0), (-21.0, -59.2), (-25.5, -60.2), (-28.5, -62.5), (-29.8, -65.5)])[1:]
    strap = [(-38.8, -106.0)] + spline([(-38.8, -106.0), (-39.4, -109.4), (-40.6, -111.6), (-42.5, -112.5)])[1:]
    back = spline([(-90.6, -112.5), (-90.8, -108), (-91.0, -102), (-90.8, -96), (-90.2, -91), (-89.4, -86),
                   (-88.2, -81), (-86.7, -76.5), (-85.0, -72), (-83.4, -68), (-81.6, -64), (-80.0, -60), (-78.5, -57),
                   (-77.0, -54), (-75.6, -51), (-74.5, -48), (-73.7, -44.5), (-73.6, -41), (-74.1, -37), (-75.2, -34),
                   (-76.8, -31.6), (-79.0, -29.9), (-82.5, -28.5), (-86.0, -27.4), (-89.2, -26.2), (-91.6, -25.0),
                   (-93.0, -23.5), (-93.1, -22.2), (-92.2, -21.0), (-90.4, -19.8), (-88.3, -18.2), (-86.3, -16.3),
                   (-84.8, -14.6), (-84.5, -14.0)])
    frame = rdp(front) + rdp(rim)[1:] + rdp(web) + rdp(strap) + rdp(back)
    g.extrude(ccw(frame), width=21.0, mat='blued_old', bevel=0.8, name='frame')
    # trigger guard: bar around a rounded-rectangle opening (flat top along the frame)
    hole = (superellipse(gc, 23.1, 11.5, 2.8, 0, 180, 28)[:-1] + superellipse(gc, 23.1, 16.0, 2.5, 180, 360, 36)[:-1])
    outer = (superellipse((1.0, -42.0), 25.0, 13.0, 4.0, 0, 180, 20)[:-1]
             + superellipse((1.0, -42.0), 25.0, 18.0, 2.3, 180, 360, 36)[:-1])
    g.extrude(ccw(outer), width=9.0, mat='blued_old', holes=[cw(hole)], bevel=0.9, seg=2, name='guard')

    # trigger (curved forward), pivot boss
    trig = [(-9.5, -29.5)] + spline([(3.6, -29.5), (2.6, -31.5), (1.3, -34), (0.5, -37), (0.5, -40.5), (1.2, -43.5),
                                     (2.6, -46.2), (4.8, -48.4), (7.6, -49.8), (10.5, -50.4), (13.0, -50.8),
                                     (14.0, -51.7), (13.3, -52.7), (10.2, -53.1), (7.4, -52.9), (4.8, -52.0),
                                     (2.2, -50.6), (0.0, -48.6), (-1.8, -46.3), (-3.2, -43.5), (-3.9, -40.0),
                                     (-4.0, -36.5), (-5.2, -34.4), (-7.4, -32.3), (-9.5, -31.0)], step=0.6)
    trig = [trig[0]] + rdp(trig[1:], 0.06)
    g.extrude(ccw(trig), width=6.5, mat='blued', bevel=0.6, name='trigger')

    # hammer (cocked, chequered spur)
    ham = [(-85.2, -14.1), (-81.0, -14.1), (-81.0, 3.4), (-82.3, 6.3), (-83.9, 8.4, 0.6), (-86.0, 9.7, 0.8),
           (-88.5, 9.9, 0.8), (-90.5, 9.4, 0.8), (-91.9, 7.2, 0.4), (-89.7, 5.9), (-86.8, 5.1), (-84.3, 3.4),
           (-83.3, 0.9), (-82.9, -1.6), (-83.1, -7.4), (-83.8, -11.6)]
    g.extrude(ham, width=8.0, mat='blued', bevel=0.5, name='hammer')
    for i in range(5):                                  # chequered spur: little ribs on top
        u = -90.4 + i * 1.15
        g.box(u - 0.3, u + 0.3, 9.0, 10.2, width=7.0, mat='blued', bevel=0)

    # ---------------------------------------------------------------- grip panels (bakelite, horizontal ribs)
    # panel outline: straight front edge, rear edge along the backstrap spline (inset), rounded corners
    panel = ([(-36.0, -17.5)] + spline([(-38.0, -108.5), (-38.6, -111.6), (-40.5, -113.4), (-43.5, -113.6)])
             + spline([(-87.0, -113.6), (-89.8, -111.6), (-90.6, -107), (-90.8, -100), (-90.5, -94), (-89.8, -89),
                       (-88.6, -83), (-87.0, -78), (-85.0, -72), (-83.4, -68), (-81.6, -64), (-80.0, -60),
                       (-78.5, -57), (-77.0, -54), (-75.6, -51), (-74.5, -48), (-73.7, -44.5), (-73.6, -41),
                       (-74.1, -37), (-75.2, -34), (-76.6, -30), (-78.0, -25), (-79.2, -20.5), (-78.8, -18.2),
                       (-77.0, -17.4)]))
    from ..lib import offset_poly
    panel = offset_poly(ccw(rdp(panel, 0.04)), -0.6)
    gp = g.sweep(panel, 'bakelite', width=31.5, radius=(7.5, 7.5), axis=GRIP_A, origin=(-58, -16), step=4.0, n=3,
                 name='grip')
    # horizontal ribs: shallow grooves across both panels
    cs = []
    for k in range(30):
        v = -40.5 - k * 2.45
        if v < -112:
            break
        for s in (1, -1):
            cs.append(g.box(-100, -30, v - 0.45, v + 0.45, 14.9 * s - (0 if s > 0 else 3), 14.9 * s + (3 if s > 0 else 0),
                            cutter=True, bevel=0))
    g.cut(gp, *cs)
    # grip screws
    for s in (1, -1):
        g.lathe([(15.4 * s, 0), (15.4 * s, 3.4), (16.4 * s, 3.0), (16.9 * s, 1.6), (17.0 * s, 0)], 'blued', axis='w',
                at=(-70.5, -61), seg=16)
    # heel magazine catch
    g.extrude([(-91.6, -112), (-88.0, -112), (-88.0, -121), (-91.0, -121.2), (-92.0, -117)], width=10, mat='blued',
              bevel=0.4)

    # ---------------------------------------------------------------- left-side controls
    # safety / decocker lever on the slide: round thumb piece with a ribbed tail
    g.lathe([(-11.5, 0), (-11.5, 4.6), (-12.6, 4.4), (-13.6, 3.6), (-13.9, 0)], 'blued', axis='w', at=(-52.5, 2.5),
            seg=20)
    g.extrude([(-52, 0.0), (-36.5, -0.8, 0.8), (-36.5, 3.2, 0.8), (-50, 5.0)], -12.8, -11.2, 'blued', bevel=0.3)
    # slide stop
    g.extrude([(-31, -18.6), (-17, -19.6, 1), (-16.5, -23.0, 1), (-31, -24.4, 1)], -11.8, -10.3, 'blued', bevel=0.4)
    # takedown lever with a ribbed thumb piece
    g.extrude([(24.5, -16.8), (43.5, -16.8, 1), (39.5, -22.4, 1), (24.5, -22.4, 1)], -11.6, -10.3, 'blued', bevel=0.3)
    for i in range(5):
        u = 25.6 + i * 1.3
        g.box(u - 0.3, u + 0.3, -22.2, -17.0, -12.0, -11.4, 'blued', bevel=0)
    # trigger pin heads, both sides
    for s in (1, -1):
        g.lathe([(10.5 * s, 0), (10.5 * s, 1.9), (11.2 * s, 1.6), (11.4 * s, 0)], 'bright', axis='w', at=(-1.2, -25.0),
                seg=12)
    # lanyard loop (left, low on the grip)
    g.pipe([(-84, -104, -15.0), (-82.5, -106.5, -16.8), (-77, -108.5, -17.0), (-72.5, -108.5, -15.8)], 1.3, 'blued',
           seg=8, corner=1.5)

    # ---------------------------------------------------------------- right-side details
    # exposed trigger bar and the locking-block plunger
    g.extrude([(-22, -16.8), (8, -16.8, 0.8), (8, -19.8, 0.8), (-2, -21.0), (-22, -21.0, 0.8)], 10.3, 11.3, 'blued',
              bevel=0.3)
    g.lathe([(10.4, 0), (10.4, 2.6), (11.3, 2.4), (11.7, 1.2), (11.8, 0)], 'bright', axis='w', at=(45.0, -18.5), seg=16)

    # ---------------------------------------------------------------- magazine (8 rounds, inside the grip)
    with g.part('mag'):
        t0, t1 = 2.0, 95.5
        cu, cv = -53.0, -21.0
        du, dv = MAG_DIR
        nu, nv = -dv, du
        P = lambda t, n: (cu + du * t + nu * n, cv + dv * t + nv * n)
        body = [P(t0, -15.5), P(t0, 13.5), P(t1, 13.5), P(t1, -15.5)]
        g.extrude(body, width=11.0, mat='blued', bevel=0.5, name='magbody')
        # floor plate (visible under the grip)
        fp = g.outline([(-95, -113.6), (-34, -113.6), (-34, -126), (-95, -126)])
        g.extrude(fp, width=23.5, mat='blued', bevel=0.8, name='floorplate')
        # top round
        g.lathe([(-34 - 0, 0), (-34, 4.4), (-50, 4.5), (-55, 4.3), (-58, 0)], 'brass', at=(-17.5, 0), seg=14)
    g.pivot('mag', -53.0, -21.0)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 122.6, 0)
    g.anchor('sight', -66.5, SIGHT_V)
    g.anchor('eject', 18, 5, -11.5)
    g.anchor('rh', -62, -66, 0)
    g.anchor('lh', -58, -80, 0)
    g.anchor('eye', -450, SIGHT_V)
