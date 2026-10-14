"""Thompson M1A1. Reference: ThompsonM1A1VWM.jpg (right side, public domain). 811 mm, parkerized receiver with the
cocking knob on the RIGHT side, fixed L rear sight with protective ears, walnut butt stock, pistol grip and
horizontal forend, plain barrel with a blade front sight, 30-round stick magazine."""
import math

import numpy as np

from ..lib import clean, offset_poly, rrect

REF = 'thompson'
META = {'kind': 'rifle'}

SIGHT_V = 27.0      # top of the front blade = centre of the rear peep


def edges(outline, origin, axis_deg, t0, t1, step=4, trim=(20, 15), deg=2):
    """smooth front/back edges of a swept part (polynomial fits of the traced outline crossings)."""
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
    m = (T > T[0] + trim[0]) & (T < T[-1] - trim[1])
    lo = np.polyval(np.polyfit(T[m], np.array(los)[m], deg), T)
    hi = np.polyval(np.polyfit(T[m], np.array(his)[m], deg), T)

    def to_uv(t, n):
        return (origin[0] + du * t + nu * n, origin[1] + dv * t + nv * n)
    return T, lo, hi, to_uv


def dome(g, u, v, w, r=2.6, mat='park', h=None):
    """dome head (screw, pin, rivet) on a side face at depth w (sign gives the side)."""
    s = 1 if w > 0 else -1
    h = h or r * 0.5
    g.lathe([(w, 0), (w, r), (w + s * h * 0.45, r * 0.92), (w + s * h * 0.85, r * 0.6), (w + s * h, 0)], mat,
            axis='w', at=(u, v), seg=12)


def build(g):
    RW = 15.0          # receiver half width
    # ---------------------------------------------------------------- receiver
    rec = [(-213.5, -27), (-213.5, 9), (-211, 11.8), (126, 12.5), (128, 11), (128, -25.8), (76, -25.8), (76, -14),
           (33, -14), (33, -29.5), (-208, -29.5), (-210, -27)]
    r = g.extrude(rec, width=2 * RW, mat='park', bevel=1.8, name='receiver')
    cuts = []
    # actuator (cocking knob) slot, right side
    cuts.append(g.extrude(rrect(-107, 22, -10.5, -2, 4.2), RW - 2.5, RW + 2, cutter=True, bevel=0))
    # ejection port, right side, high on the receiver
    cuts.append(g.extrude([(40, 0), (97, 0), (97, 9.5, 2), (52, 9.5, 2), (44, 6)], 6, RW + 2, cutter=True, bevel=0))
    # long grooves (frame rail lines) and the receiver/barrel-seat seam, both sides
    for s in (1, -1):
        for v in (-14.8, -21.0):
            cuts.append(g.box(-209, 31, v - 0.5, v + 0.5, s * (RW - 0.5), s * (RW + 1), cutter=True, bevel=0))
        cuts.append(g.box(96.5, 97.5, -24, -1, s * (RW - 0.5), s * (RW + 1), cutter=True, bevel=0))
    for c in cuts:
        g.cut(r, c)
    g.box(48, 97, 0.5, 8, 4, 9, 'blued', bevel=0.3)                         # bolt seen through the port
    g.box(-104, 20, -9, -3.5, RW - 3, RW - 1.5, 'blued', bevel=0.2)         # actuator in the slot
    # cocking knob (right), bolt forward
    g.lathe([(RW - 1, 0), (RW - 1, 3.5), (RW + 3, 3.5), (RW + 3.5, 7.4), (RW + 9, 7.6), (RW + 10.5, 6.5),
             (RW + 11, 4), (RW + 11, 0)], 'park', axis='w', at=(14, -6.5), seg=20, name='knob')
    g.cyl(RW + 9.5, RW + 11.2, 3.5, 'black', axis='w', at=(14, -6.5), seg=14)
    # rear buffer knob at the back of the receiver
    g.lathe([(-216.5, 0), (-216.5, 3.0), (-215.5, 3.6), (-212, 3.6), (-212, 0)], 'park', at=(-3.5, 0), seg=16)

    # ---------------------------------------------------------------- rear sight (L type with protective ears)
    g.extrude([(-192, 10), (-127, 10), (-127, 12.5, 1), (-130, 14.5), (-189, 14.5)], width=17, mat='park', bevel=0.6,
              name='sightbase')
    ear = [(-191.5, 12), (-181, 33.5, 2.5), (-174.5, 37.2, 2.5), (-129, 19.8, 2), (-127, 12)]
    for s in (1, -1):
        g.extrude(ear, s * 5.0, s * 8.0, 'park', bevel=0.5, name='ear')
    leaf = g.extrude([(-180, 12), (-175, 12), (-175, 31.5, 1.5), (-180, 31.5, 1.5)], width=10.2, mat='park', bevel=0.3,
                     name='peep')
    g.cut(leaf, g.cyl(-190, -170, 2.4, axis='u', at=(SIGHT_V, 0), seg=16, cutter=True, chamfer=0))   # game-sized peep

    # ---------------------------------------------------------------- frame (trigger housing) and trigger guard
    fr = g.outline([(-134, -24), (34, -24), (34, -49), (-60, -49), (-100, -51), (-134, -51)])
    g.extrude(fr, width=27, mat='park', bevel=1.2, name='frame')
    guard, gh = g.outline([(-27, -48), (34, -48), (34, -90), (-26, -90)], holes=True)
    g.extrude(guard, width=13, mat='park', holes=gh, bevel=1.0, name='guard')
    trig = [(-6, -48), (1, -48), (0.6, -57), (0, -65), (1.2, -72), (2.2, -75), (0.2, -75.6), (-2.8, -72),
            (-5, -64), (-6.4, -56)]
    g.extrude(trig, width=6, mat='blued', bevel=0.6, name='trigger')
    # selector and safety plate with lever pivots (right side)
    g.extrude([(-60, -33, 5), (12, -33, 5), (12, -45, 5), (-60, -45, 5)], 13.4, 14.4, 'park', bevel=0.4)
    for u, v, rr in ((-80, -41, 3.2), (-47, -38.5, 3.0), (5, -38, 3.2)):
        dome(g, u, v, 14.4 if -60 < u < 12 else 13.5, rr)
        dome(g, u, v, -13.5, rr * 0.8)
    for u, v in ((-24, -42), (20, -44), (27, -63)):
        dome(g, u, v, 13.5, 1.8)
        dome(g, u, v, -13.5, 1.8)
    # fire selector and safety levers (left side)
    for (u, v, ang, L) in ((-47, -38.5, -100, 15), (-80, -41, -75, 13)):
        lv = g.extrude([(-3.2, -3.2, 3), (L, -2.2, 2), (L, 2.2, 2), (-3.2, 3.2, 3)], -15.2, -13.6, 'park', bevel=0.4,
                       name='lever')
        g.transform(lv, rot=('w', ang), move=(u, v, 0))
    lev = g.extrude(rrect(0, 17, -1.1, 1.1, 1.0), 14.0, 15.4, 'park', bevel=0.3, name='lever')
    g.transform(lev, rot=('w', -28), move=(-78, -43, 0))

    # ---------------------------------------------------------------- pistol grip (walnut)
    raw = g.outline([(-125, -47), (-60, -47.5), (-27, -50), (-26, -88), (-30, -165), (-125, -165)], smooth=False)
    grip = offset_poly(clean(raw, iters=30, eps=0.25), 0.4)
    gax, gor = -100.0, (-72, -47)
    g.sweep(grip, 'walnut', width=[(0, 26), (60, 29), (110, 27)], radius=8, axis=gax, origin=gor, step=3,
            name='grip')

    # ---------------------------------------------------------------- butt stock (walnut)
    # hand-fitted to the traced outline (smooth lines: no pixel waviness in the shading)
    stock = [(-421.5, -83.2, 8), (-246, -36.4, 9), (-226, -43.8, 7), (-212, -45.8, 5), (-201, -40.5, 4),
             (-197, -29.5), (-133, -29.5), (-133, -49), (-117.5, -49), (-120, -58, 4), (-130, -65.2),
             (-140, -71.4), (-150, -77.4), (-160, -81.2), (-175, -84), (-185, -86.4), (-195, -90.4), (-205, -95.3),
             (-215, -99.4), (-225, -103.5), (-235, -108.2), (-250, -116), (-300, -148), (-355, -178.4),
             (-365, -184.8), (-380, -191.2), (-397, -196, 4), (-409, -191.5, 6), (-413, -180), (-416.3, -160), (-419, -135), (-421.8, -100)]
    g.sweep(stock, 'walnut', width=[(0, 27), (90, 30), (200, 37), (300, 40)], radius=(8, 9), top=0.92,
            axis=197.0, origin=(-120, -50), step=3.5, name='stock')
    corner = g.outline([(-138, -48), (-112, -48), (-112, -68), (-138, -68)])
    g.extrude(corner, width=25, mat='walnut', bevel=1.5, name='stockcorner')
    # stock lug under the back of the receiver
    g.extrude([(-213.5, -26), (-213.5, -29.5), (-205, -33), (-199, -38.5), (-195.5, -41.2), (-188, -41.2),
               (-188, -26)], width=25, mat='park', bevel=1.0, name='lug')
    dome(g, -175, -48, 13.5, 5.5, 'blued', 2.2)            # stock mounting bolt head
    dome(g, -175, -48, -13.5, 5.5, 'blued', 2.2)

    # ---------------------------------------------------------------- barrel, front sight
    g.lathe([(124, 0), (124, 11.6), (200, 10.8), (300, 9.8), (370, 9.0), (392, 8.8), (392, 0)], 'park',
            at=(0, 0), seg=28, name='barrel')
    g.tube(380, 392.2, 5.8, 5.0, 'black', seg=16)
    g.lathe([(371.5, 0), (371.5, 9.8), (372.5, 10.5), (390, 10.5), (391.2, 9.6), (391.2, 8.5), (371.5, 8.5)], 'park',
            at=(0, 0), seg=28, closed=True, name='fsband')
    blade = [(372, 8), (391, 8), (391, 20), (389, 25.3, 2.5), (386, SIGHT_V), (377, SIGHT_V), (373.6, 25, 2.5),
             (372.2, 20)]
    g.extrude(blade, width=1.8, mat='park', bevel=0.3, name='blade')

    # ---------------------------------------------------------------- horizontal forend (walnut)
    fe = [(129.5, -1.5, 1.5), (350.5, -1.5, 2), (350.5, -35.2, 7.5), (135, -41.8, 3), (129.5, -41.8, 2)]
    g.sweep(fe, 'walnut', width=34, radius=(5, 9), top=0.94, step=4, name='forend')
    # front band screw / swivel stud under the forend
    g.cyl(-43.5, -36, 2.4, 'park', axis='v', at=(296, 0), seg=12)
    ring = [(296 + 3.6 * math.sin(math.radians(a)), -47 + 3.6 * math.cos(math.radians(a)), 0) for a in range(0, 360, 30)]
    g.pipe(ring, 1.1, 'park', seg=8, closed=True)

    # ---------------------------------------------------------------- 30-round stick magazine
    with g.part('mag'):
        traced = g.outline([(28, -15), (76, -15), (76, -232), (28, -232)])
        T, lo, hi, to_uv = edges(traced, (53, -15), -90.0, 0, 212, trim=(10, 14), deg=1)
        body = [to_uv(t, n) for t, n in zip(T, lo)] + [to_uv(t, n) for t, n in zip(T[::-1], hi[::-1])]
        top = [to_uv(-6, lo[0] + 1), to_uv(T[0] + 1, lo[0] + 1), to_uv(T[0] + 1, hi[0] - 1), to_uv(-6, hi[0] - 1)]
        g.extrude(body, width=22, mat='blued', bevel=1.2, name='magbody')
        g.extrude(top, width=20, mat='blued', bevel=0.6)
        # pressed spine along the back and a centre rib on each flank
        i0, i1 = 6, len(T) - 6
        for s in (1, -1):
            line = [to_uv(T[i], lo[i] + (hi[i] - lo[i]) * 0.55) for i in (i0, i1)]
            g.pipe([(u, v, s * 11.0) for u, v in line], 1.4, 'blued', seg=8)
            line = [to_uv(T[i], lo[i] + 4.0) for i in (i0, i1)]
            g.pipe([(u, v, s * 10.6) for u, v in line], 1.0, 'blued', seg=6)
        te = T[-1]
        g.extrude([to_uv(te - 4, lo[-1] - 1), to_uv(te + 1.5, lo[-1] - 1), to_uv(te + 1.5, hi[-1] + 0.5),
                   to_uv(te - 4, hi[-1] + 0.5)], width=23.5, mat='blued', bevel=0.8, name='floor')
    g.pivot('mag', 54, -12)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 392, 0)
    g.anchor('sight', -177.5, SIGHT_V)
    g.anchor('eject', 70, 5, RW)
    g.anchor('rh', -80, -100, 0)
    g.anchor('lh', 240, -24, 0)          # the soldier holds the horizontal forend
    g.anchor('eye', -370, SIGHT_V)
