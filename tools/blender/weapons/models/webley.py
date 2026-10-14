"""Webley Mk VI .455 break-top revolver. Reference: 'Webley Mk VI-Morges Inv 1010650-P5120348-white.jpg' (right side,
Rama, CC BY-SA 3.0 fr). 286 mm, 6-inch barrel with ribbed top and a blade front sight on a ramp, stirrup barrel latch
(rear sight notch on top), chequered vulcanite bird's-head grip, lanyard ring.

Parts: 'breakTop' = the barrel half (barrel, rib, front sight, top strap, lump, hinge knuckle, cam lever, cylinder,
extractor star), pivoting on the joint pin; the client opens it with breakTop.rotation.x = -0.7 rad (muzzle down, the
cylinder rises out of the frame). Frame, grip, hammer, trigger, guard, latch and lanyard ring stay in body with the
hands. The cam lever is screwed to the barrel lump, so it rides with breakTop. 'mag' = the six .455 rounds in the
chambers (pushed in from behind along magDir). Set WEBLEY_OPEN=1 to build the opened state for checking."""
import math
import os

import numpy as np

from ..lib import arc, offset_poly, section

REF = 'webley'
META = {'kind': 'pistol', 'magHidden': True, 'client': {'magDir': [0, -0.3, 1], 'magHidden': True}}

SIGHT_V = 19.8                      # front blade top (a game-tall blade); the V notch in the latch bottoms out 2.5 mm
                                    # below it so most of the blade shows
HINGE = (33.0, -32.5)               # barrel joint pin
CYL_V = -14.9                       # cylinder axis (the top chamber is on the bore)
CYL_R = 21.3
CYL_U0, CYL_U1 = -18.6, 21.0        # cylinder rear / front faces
PITCH = 14.9                        # chamber circle radius
FIN = 'blued'
GRIP_A = -104.0


def smooth_edges(outline, origin, axis_deg, t0, t1, step=3, deg=2, lo_cut=20, hi_cut=10, ext=0.0):
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
    clo, chi = np.polyfit(T[m], np.array(los)[m], deg), np.polyfit(T[m], np.array(his)[m], deg)
    if ext > 0:                       # extrapolate past the end (to be cut off by a cutter)
        T = np.concatenate([T, np.arange(T[-1] + step, T[-1] + ext + 1e-6, step)])
    lo, hi = np.polyval(clo, T), np.polyval(chi, T)

    def to_uv(t, n):
        return (origin[0] + du * t + nu * n, origin[1] + dv * t + nv * n)
    return T, lo, hi, to_uv


def superellipse(cu, cv, a, b, n, t0, t1, k):
    """points on |du/a|^n + |dv/b|^n = 1, parameter angles t0..t1 in degrees (k segments)."""
    out = []
    for i in range(k + 1):
        t = math.radians(t0 + (t1 - t0) * i / k)
        c, s = math.cos(t), math.sin(t)
        out.append((cu + a * math.copysign(abs(c) ** (2 / n), c), cv + b * math.copysign(abs(s) ** (2 / n), s)))
    return out


def lerp_line(pts, u):
    """v of a polyline (sorted by u) at u, clamped at the ends."""
    pts = sorted(pts)
    if u <= pts[0][0]:
        return pts[0][1]
    for (u0, v0), (u1, v1) in zip(pts, pts[1:]):
        if u <= u1:
            return v0 + (v1 - v0) * (u - u0) / (u1 - u0)
    return pts[-1][1]


def dedupe(pts, eps=0.05):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > eps:
            out.append(p)
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


def screw(g, u, v, w, r, mat=FIN):
    s = 1 if w > 0 else -1
    g.lathe([(w, 0), (w, r), (w + s * 0.7, r * 0.9), (w + s * 1.1, r * 0.55), (w + s * 1.2, 0)], mat, axis='w',
            at=(u, v), seg=12)


def build(g):
    # ================================================================ body: frame, grip, hammer, latch, trigger
    # frame outline as lines + fillets (measured off the reference): grip tang with a concave sweep up to the hammer,
    # standing breech, window under the cylinder, fork hugging the joint knuckle, straight underside back to the grip
    fr = ([(-84, -31.5), (-62.0, -30.0)] + arc(-61.0, -14.5, 15.5, 266, 360, n=9)
          + [(-45.5, -10.6, 1.0), (-39.5, -8.4, 3.0), (-36.6, -3.0, 2.0), (-36.4, 5.6), (CYL_U0 + 0.6, 5.6),
             (CYL_U0 + 0.6, -35.4), (20.0, -35.4)]
          + arc(HINGE[0], HINGE[1], 10.4, 192, 285, n=7)
          + [(36.0, -44.2, 1.0), (34.4, -46.3, 0.6), (24.0, -46.9), (14.0, -48.2), (-1.7, -50.2), (-18.3, -52.8, 4.0),
             (-47.5, -66.2), (-60, -67.5), (-84, -67.5)])
    g.extrude(fr, width=26.0, mat=FIN, bevel=1.2, seg=2, name='frame')
    # recoil shield behind the cylinder, standing breech up to the top strap
    g.extrude([(-23.6, -37), (CYL_U0 - 0.6, -37), (CYL_U0 - 0.6, 6.2), (-23.6, 6.2)], width=34.0, mat=FIN,
              bevel=1.0, name='shield')
    # hammer (traced), latch stirrup with the rear sight notch on top
    hm = g.outline([(-66, -12), (-34, -12), (-34, 13), (-66, 13)])
    g.extrude(hm, width=8.4, mat=FIN, bevel=0.6, name='hammer')
    for s in (1, -1):
        g.extrude([(-31.6, -8.0), (-27.5, -9.4, 1.5), (-24.4, -6.0), (-22.6, 12.0), (-22.6, 16.0), (-31.6, 16.0)],
                  7.4 * s if s > 0 else -10.6, 10.6 if s > 0 else -7.4, FIN, bevel=0.8, name='latcharm')
        screw(g, -26.7, -2.1, 10.6 * s, 2.0)
    lt = g.extrude([(-31.6, 12.0), (-22.6, 12.0), (-22.6, 19.8, 1.0), (-24.4, 21.6, 1.0), (-29.6, 21.6, 1.5),
                    (-31.6, 19.2, 1.5)], width=21.2, mat=FIN, bevel=0.8, name='latch')
    g.cut(lt, g.extrude([(-2.4, 23.0), (2.4, 23.0), (0.3, SIGHT_V - 2.5), (-0.3, SIGHT_V - 2.5)], -40, -15, plane='front',
                        cutter=True, bevel=0))
    # trigger: crescent between two fitted circles, tip pointing back
    trig = (arc(2.0, -66.0, 17.4, 110, 256, n=18) + [(-1.4, -82.1)] + arc(2.5, -67.2, 14.1, 250, 102, n=15)
            + [(-0.4, -48.6), (-4.8, -48.6)])
    g.extrude(trig, width=5.0, mat=FIN, bevel=0.6, seg=2, name='trigger')
    # trigger guard: bow between two fitted superellipses, spur along the frame underside back to the grip
    top = [(20.5, -44.5), (0.0, -47.0), (-18.0, -49.6), (-47.0, -61.5)]
    g_out = ([(-47.0, -61.5), (-48.2, -63.5, 1.5), (-47.6, -67.6, 1.2), (-40.0, -68.0), (-35.2, -68.8, 2.0)]
             + superellipse(-8.9, -65.9, 25.2, 22.3, 2.13, 192, 370, 26)
             + [(16.6, -57.0), (16.2, -53.5, 2.0), (18.0, -49.8, 2.0), (21.0, -47.2), (20.5, -44.5), (0.0, -47.0),
                (-18.0, -49.6)])
    g_in = dedupe([(u, min(v, -49.8, lerp_line(top, u) - 1.0))
                   for u, v in superellipse(-8.3, -67.3, 21.5, 17.8, 2.12, 90, -270, 44)[:-1]])
    g.extrude(g_out, width=7.0, mat=FIN, holes=[g_in], bevel=1.0, seg=2, name='guard')
    # frame pins and the joint screw heads (the pin runs through the fork)
    for u, v, r in ((-7.9, -42.5, 1.6), (-40.6, -33.8, 2.0)):
        for s in (1, -1):
            screw(g, u, v, 13.0 * s, r, mat='bright')
    for s in (1, -1):
        g.lathe([(10.5 * s, 0), (10.5 * s, 3.8), (11.3 * s, 3.5), (11.7 * s, 2.0), (11.8 * s, 0)], FIN, axis='w',
                at=HINGE, seg=18)
    # grip: traced, smoothed front/back edges; vulcanite with a chequered field inside a plain border
    gt = g.outline([(-125, -30.5), (-46, -30.5), (-46, -64), (-52, -90), (-55, -130.5), (-125, -130.5)])
    T, lo, hi, to_uv = smooth_edges(gt, (-64, -31), GRIP_A, 0, 102, step=3, deg=3, lo_cut=8, hi_cut=8, ext=9)
    clean = [to_uv(t, n) for t, n in zip(T, lo)] + [to_uv(t, n) for t, n in zip(T[::-1], hi[::-1])]
    gob = g.sweep(clean, 'black', width=33.0, radius=(9.0, 7.0), axis=GRIP_A, origin=(-64, -31), step=3.0,
                  name='grip')
    field = offset_poly(clean, -4.2)
    g.sweep(field, 'checker_b', width=33.8, radius=(9.0, 7.0), axis=GRIP_A, origin=(-64, -31), step=3.0,
            t0=12, t1=86, name='chequer')
    # butt: flat bottom, rounded heel and toe; top edge along the frame line
    cuts = [g.extrude([(-135, -36.2), (-56, -29.3), (-56, 0), (-135, 0)], -30, 30, cutter=True, bevel=0),
            g.extrude([(-135, -114), (-117.6, -116.5)] + arc(-111.5, -122.3, 5.5, 166, 268, n=6)
                      + arc(-67.8, -125.4, 3.6, 270, 360, n=6) + [(-40, -125.4), (-40, -165), (-135, -165)], -30, 30,
                      cutter=True, bevel=0)]
    g.cut(gob, *cuts)
    for s in (1, -1):
        g.lathe([(16.6 * s, 0), (16.6 * s, 4.2), (17.4 * s, 4.0), (17.4 * s, 0)], 'bright', axis='w',
                at=(-84.2, -79.2), seg=18)
        screw(g, -84.2, -79.2, 17.2 * s, 2.4, mat='bright')
    # lanyard ring on a swivel under the butt
    g.cyl(-133.4, -128, 1.9, 'brass', axis='v', at=(-90.2, 0), seg=12)
    ring = [(1.3 * math.cos(2 * math.pi * k / 10), 7.3 + 1.3 * math.sin(2 * math.pi * k / 10)) for k in range(10)]
    g.lathe(ring, 'brass', axis='w', at=(-90.4, -141.3), seg=16, closed=True, name='ring')

    # ================================================================ breakTop: barrel half
    with g.part('breakTop'):
        g.lathe([(21.0, 0), (21.0, 9.3), (166.8, 9.3), (168.6, 9.0), (170.0, 8.0), (170.0, 0)], FIN, at=(0.3, 0),
                seg=28, name='barrel')
        g.tube(160, 170.3, 6.0, 5.8, 'black', at=(0.3, 0), seg=20)
        g.cyl(169, 170.2, 5.85, 'black', at=(0.3, 0), seg=16)
        g.extrude([(30, 6.0), (167.0, 6.0), (167.8, 9.2), (167.2, 10.3), (30, 10.3)], width=6.4, mat=FIN, bevel=0.6,
                  name='rib')
        # front sight: ramp on the rib, pinned blade
        g.extrude([(131.0, 9.0), (133.5, 10.4), (137.0, 12.4), (139.5, 14.8), (141.5, 15.8), (158.3, 15.8),
                   (161.5, 14.6), (165.0, 11.8), (168.0, 10.0), (168.0, 9.0)], width=6.4, mat=FIN, bevel=0.5,
                  name='ramp')
        g.extrude([(142.0, 15.0), (142.6, SIGHT_V - 0.3), (143.4, SIGHT_V), (155.6, SIGHT_V), (158.4, 16.6),
                   (158.4, 15.0)], width=1.5, mat=FIN, bevel=0.3, name='frontsight')
        for s in (1, -1):
            g.lathe([(3.2 * s, 0), (3.2 * s, 1.3), (3.6 * s, 1.1), (3.7 * s, 0)], 'bright', axis='w', at=(151.0, 14.3),
                    seg=10)
        # top strap (traced top line incl. the taper onto the rib), rounded on top
        ts = g.outline([(-23.4, 6.4), (40, 6.4), (40, 22), (-23.4, 22)])
        g.sweep(ts, FIN, width=17.0, radius=(5.5, 0.8), axis=0, origin=(0, 0), step=2.5, name='topstrap')
        # barrel lump: concave flare off the barrel, flat step, concave sweep down to the joint knuckle
        lump = ([(20.0, -4.0), (56.0, -4.0, 8.0), (74.0, -8.6), (78.0, -8.8)] + arc(75.0, -19.2, 9.8, 90, 180, n=8)
                + [(65.2, -20.4, 0.8)] + arc(60.0, -32.9, 12.5, 90, 180, n=9)
                + [(43.6, -33.3), (40.0, -37.5), (28.0, -37.5), (20.6, -35.8)])
        g.extrude(dedupe(lump), width=20.0, mat=FIN, bevel=0.8, name='lump')
        g.cyl(-10.5, 10.5, 10.0, FIN, axis='w', at=HINGE, seg=28, chamfer=0.8, name='knuckle')
        # cam lever and its screw (right side of the lump, ahead of the cylinder)
        g.extrude([(21.8, -8.6), (43.2, -10.4, 1.2), (44.0, -13.4, 1.5), (41.0, -15.6, 2), (30.5, -14.4),
                   (26.6, -16.6), (29.4, -28.6, 1.5), (26.4, -30.2, 1.5), (22.6, -22.0), (21.8, -16.0)], 10.0, 11.6,
                  FIN, bevel=0.4, name='camlever')
        screw(g, 40.0, -17.9, 11.6, 2.7)
        # cylinder: 6 chambers, short flutes on the front half
        cyl = g.lathe([(CYL_U0, 0), (CYL_U0, CYL_R - 1.0), (CYL_U0 + 1.0, CYL_R), (CYL_U1 - 1.2, CYL_R),
                       (CYL_U1, CYL_R - 1.4), (CYL_U1, 0)], FIN, at=(CYL_V, 0), seg=36, name='cylinder')
        cut = []
        for k in range(6):
            a = math.radians(90 + 60 * k)
            cv, cw = CYL_V + PITCH * math.sin(a), PITCH * math.cos(a)
            cut.append(g.cyl(CYL_U0 - 1, CYL_U1 + 1, 6.05, at=(cv, cw), seg=14, cutter=True, chamfer=0))
            fa = a + math.radians(30)
            fv, fw = CYL_V + (CYL_R + 2.4) * math.sin(fa), (CYL_R + 2.4) * math.cos(fa)
            fl = g.lathe([(3.0, 0), (3.0, 1.0), (4.6, 3.6), (7.0, 4.7), (CYL_U1 + 2, 4.7), (CYL_U1 + 2, 0)],
                         at=(fv, fw), seg=10, cutter=True)
            cut.append(fl)
        g.cut(cyl, *cut)
        g.cyl(CYL_U1 - 0.5, CYL_U1 + 2.0, 4.0, FIN, at=(CYL_V, 0), seg=16)               # axis / extractor stem
        # extractor star in the rear face: a disc notched round each cartridge rim
        star = []
        for k in range(48):
            ph = 2 * math.pi * k / 48
            r = 12.6
            for j in range(6):
                d = ph - math.radians(90 + 60 * j)
                h = PITCH * math.sin(d)
                if abs(h) < 6.9 and math.cos(d) > 0:
                    r = min(r, PITCH * math.cos(d) - math.sqrt(6.9 ** 2 - h * h))
            star.append((r * math.cos(ph), CYL_V + r * math.sin(ph)))
        g.extrude(star, CYL_U0 - 0.6, CYL_U0 + 0.2, 'bright', plane='front', bevel=0, name='star')
    g.pivot('breakTop', *HINGE)

    # ================================================================ mag: six .455 rounds in the chambers
    with g.part('mag'):
        for k in range(6):
            a = math.radians(90 + 60 * k)
            cv, cw = CYL_V + PITCH * math.sin(a), PITCH * math.cos(a)
            g.lathe([(CYL_U0 - 1.1, 0), (CYL_U0 - 1.1, 6.8), (CYL_U0 - 0.1, 6.8), (CYL_U0 - 0.1, 5.9), (CYL_U0 + 18, 5.8),
                     (CYL_U0 + 18, 0)], 'brass', at=(cv, cw), seg=12, name='case')
            g.lathe([(CYL_U0 + 18, 0), (CYL_U0 + 18, 5.75), (CYL_U0 + 24, 5.5), (CYL_U0 + 29, 3.6), (CYL_U0 + 31, 0)],
                    'bright', at=(cv, cw), seg=10, name='bullet')
            g.cyl(CYL_U0 - 1.3, CYL_U0 - 1.0, 1.9, 'bright', at=(cv, cw), seg=8)      # primer
    g.pivot('mag', CYL_U0 - 1.1, CYL_V)

    # ================================================================ anchors
    g.anchor('muzzle', 170.0, 0.3)
    g.anchor('sight', -27.0, SIGHT_V)
    g.anchor('eject', 0, -5, 21.5)
    g.anchor('rh', -82, -82, 0)
    g.anchor('lh', -78, -98, 0)
    g.anchor('eye', -450, SIGHT_V)

    if os.environ.get('WEBLEY_OPEN'):        # test: the reload pose (client breakTop.rotation.x = -0.7 rad)
        obs = [ob for ob, p in g.items if p == 'breakTop']
        g.transform(obs, rot=('w', math.degrees(-0.7)), pivot=(HINGE[0], HINGE[1], 0))
