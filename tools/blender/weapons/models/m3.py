"""M3 'grease gun'. Reference: M3GreasegunVWM.jpg (right side, public domain). 757 mm with the wire stock extended.
Stamped parkerized tube receiver with the ejection-port cover on the right, fixed peep rear sight, blade front sight
on the receiver ring, knurled barrel collar, stamped trigger housing with pistol grip and a wire trigger guard,
cocking crank on the right, retractable wire stock with a looped butt, 30-round double-column magazine."""
import math

import numpy as np

from ..lib import clean, offset_poly, rrect

REF = 'm3'
META = {'kind': 'rifle'}

SIGHT_V = 35.0      # top of the front blade = centre of the rear peep
RT = 25.3           # receiver tube radius


def edges(outline, origin, axis_deg, t0, t1, step=4, trim=(20, 15), deg=2):
    """smooth front/back edges of a long part (polynomial fits of the traced outline crossings)."""
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
    # ---------------------------------------------------------------- tube receiver
    g.lathe([(-84.8, 0), (-84.8, 20), (-84.2, 23.0), (-82, 24.8), (-79, RT), (200, RT), (200, 0)], 'park',
            at=(0, 0), seg=40, name='receiver')
    g.cyl(-87.0, -84, 2.6, 'park', at=(-7.0, 0), seg=14, chamfer=0.8)                        # rear guide-rod stub
    # receiver front ring and the knurled barrel collar
    g.lathe([(198, 0), (198, 27.6), (199, 28), (216, 28), (217, 27.4), (217, 0)], 'park', at=(1.5, 0), seg=40,
            name='ring')
    col = g.lathe([(217, 0), (217, 27.4), (218.5, 28), (234.5, 28), (237.5, 26.5), (240.5, 22.6), (244, 16.2),
                   (248, 13.2), (252, 10.8), (252, 0)], 'park', at=(0.4, 0), seg=40, name='collar')
    for k in range(16):                                                          # knurl grooves on the collar
        a = k * 22.5
        cut = g.box(219, 236, -0.7, 0.7, 26.8, 30, cutter=True, bevel=0)
        g.transform(cut, rot=('u', a), move=(0, 0.4, 0))
        g.cut(col, cut)
    # ratchet lug under the collar
    g.extrude([(223.5, -18), (235, -18), (234.5, -31, 3), (232, -35.5, 3), (227, -35.5, 3), (224.5, -31, 2)],
              width=8, mat='park', bevel=0.8, name='lug')
    g.extrude([(236, -10), (252.5, -10), (252, -16, 2), (248, -22, 3), (241, -24.5, 3), (236, -24)], width=14, mat='park',
              bevel=1.0, name='collarlug')

    # ---------------------------------------------------------------- ejection-port cover (right side)
    sec = [(1.5, RT - 0.5), (1.5, 32.6), (2.8, 33.8), (8.5, 33.8)]
    for a in range(30, 101, 10):
        sec.append((28.2 * math.sin(math.radians(a)), 28.2 * math.cos(math.radians(a))))
    for a in range(100, 3, -12):
        sec.append(((RT - 0.5) * math.sin(math.radians(a)), (RT - 0.5) * math.cos(math.radians(a))))
    g.extrude(sec, 113, 198, 'park', plane='front', bevel=0.8, name='cover')
    g.box(118, 192, 31.5, 32.4, 7, 9.2, 'park', bevel=0.2)                      # stiffening bead
    g.cyl(112, 199, 1.8, 'park', at=(-2, 27.6), seg=10)                          # hinge pin along the bottom edge

    # ---------------------------------------------------------------- rear peep sight (aperture at SIGHT_V)
    side = [(-71.2, 24), (-70, 38, 3), (-66.5, 45.4, 3), (-62.5, 43.5, 3), (-56.5, 34.5), (-50, 31), (-44.5, 28.2),
            (-41.5, 25), (-41.5, 24)]
    for s in (1, -1):
        g.extrude(side, s * 3.6, s * 5.6, 'park', bevel=0.4, name='sightwing')
    leaf = g.extrude([(-68.5, 24), (-68.5, 42.5), (-67, 44.8, 1.5), (-65, 44.8, 1.5), (-64.5, 24)], width=7.4,
                     mat='park', bevel=0.3, name='peep')
    g.cut(leaf, g.cyl(-75, -58, 1.7, axis='u', at=(SIGHT_V, 0), seg=12, cutter=True, chamfer=0))
    g.box(-71, -41, 24, 26.2, -5.6, 5.6, 'park', bevel=0.4)                      # base plate on the tube

    # ---------------------------------------------------------------- front blade on the ring
    blade = [(201.5, 27), (215, 27), (214.5, 31, 2.5), (211.5, SIGHT_V, 1.5), (205, SIGHT_V, 1.5), (202, 32, 2.5)]
    g.extrude(blade, width=2.0, mat='park', bevel=0.3, name='blade')

    # ---------------------------------------------------------------- barrel
    g.lathe([(250, 0), (250, 9.6), (414, 9.6), (418, 9.0), (419.2, 7.6), (419.2, 0)], 'park', at=(0, 0), seg=26,
            name='barrel')
    g.tube(410, 419.4, 5.2, 4.5, 'black', seg=14)

    # ---------------------------------------------------------------- trigger housing (stamped) and magwell
    hous = [(-60, -12), (151, -12), (153, -52), (150, -48.5), (145, -45.6), (140, -45.1), (135, -46.4),
            (130, -49), (125, -53), (120, -56), (115, -59), (110, -62.8), (105, -65), (100, -66.6, 2), (40, -66.9),
            (35, -66.3), (30, -63.3), (25, -60.5), (20, -56.2), (15, -55), (-22, -55), (-60, -45)]
    g.extrude(hous, width=24, mat='park', bevel=1.2, name='housing')
    g.box(-60, 150, -24.5, -23.5, 11.4, 12.4, 'park', bevel=0.2)                # seam flange, right
    g.box(-60, 150, -24.5, -23.5, -12.4, -11.4, 'park', bevel=0.2)
    well = [(150, -14), (200.3, -14), (200.3, -56), (199.5, -86), (198.5, -95, 1.5), (196.5, -97.5), (157, -100.5, 1.5),
            (155, -98), (153, -86), (152.3, -50)]
    g.extrude(well, width=30, mat='park', bevel=1.4, name='magwell')
    g.extrude([(197, -56), (200, -43), (202, -36), (205.5, -31), (210, -28), (214, -26.5), (214, -18), (197, -18)], width=24,
              mat='park', bevel=0.8, name='wellfillet')
    g.box(152, 157, -84, -76, -16, 16, 'park', bevel=0.8)                        # mag catch lip
    for s in (1, -1):
        dome(g, 192, -72, s * 15, 2.0)
        dome(g, 160, -30, s * 12, 2.0)
    # cocking crank on the right side, folded back along the housing
    g.cyl(12, 18, 7.2, 'park', axis='w', at=(146, -27), seg=18)
    arm = g.extrude([(-2, -3.6, 3), (34, -2.6, 2.5), (34, 2.6, 2.5), (-2, 3.6, 3)], 17.5, 19.5, 'park', bevel=0.4,
                    name='crank')
    g.transform(arm, rot=('w', 196), move=(146, -27, 0))
    g.cyl(17.5, 26, 2.8, 'park', axis='w', at=(146 - 32 * math.cos(math.radians(16)),
                                               -27 - 32 * math.sin(math.radians(16))), seg=12)

    # ---------------------------------------------------------------- pistol grip (stamped, part of the housing)
    raw = g.outline([(-92, -28), (-19.5, -28), (-19.5, -142), (-92, -142)], smooth=False)
    grip = offset_poly(clean(raw, iters=30, eps=0.25), 0.6)
    g.sweep(grip, 'park', width=[(0, 24), (40, 27), (90, 26)], radius=7, axis=-98.0, origin=(-50, -30), step=3,
            name='grip')
    trig = [(-20, -54), (-1, -54), (-1.2, -66), (-0.2, -75), (-2.2, -78.4), (-9, -79.5), (-16, -81.5),
            (-20, -82.5)]
    g.extrude(trig, width=7, mat='blued', bevel=0.6, name='trigger')
    guard = [(-21, -82.2, 0), (-10, -85.6, 0), (0, -86.6, 0), (10, -86.6, 0), (20, -85.2, 0), (28, -82.4, 0),
             (34.5, -77.5, 0), (38.5, -71.5, 0), (40.5, -63, 0)]
    g.pipe(guard, 1.7, 'park', seg=10, corner=4.0, name='guard')
    for s in (1, -1):
        dome(g, -32, -40, s * 12, 2.2)
        dome(g, 70, -45, s * 12, 2.2)

    # ---------------------------------------------------------------- wire stock (one bent rod, extended)
    R = 3.4
    upper = [(-306, -8.4), (-300, -8.0), (-275, -7.0), (-250, -7.5), (-225, -8.8), (-200, -10.2), (-175, -12.2),
             (-150, -13.5), (-125, -14.2), (-100, -14.8), (-64, -15.2)]
    lower = [(-306, -15.2), (-300, -15.0), (-275, -16.5), (-250, -17.8), (-200, -20.3), (-150, -22.4),
             (-100, -23.1), (-64, -23.3)]
    # smooth (quadratic) rod centre lines fitted to the measured edges
    def fit(pts):
        c = np.polyfit([p[0] for p in pts], [p[1] for p in pts], 2)
        return [(u, float(np.polyval(c, u))) for u in np.linspace(pts[0][0], pts[-1][0], 14)]
    upper, lower = fit(upper), fit(lower)
    loop = [(-323, -12.6, -5), (-333.5, -20.5, -2.5), (-335.0, -30, -1), (-332.5, -40, 0),
            (-329.6, -50, 0), (-327.3, -60, 0), (-325.4, -70, 0), (-324.0, -80, 0), (-323.0, -91, 0),
            (-318.2, -101.6, 0), (-313.4, -93, 0), (-313.4, -80, 0), (-314.9, -70, 0), (-316.3, -60, 0),
            (-318.3, -50, 0), (-321, -40, 1), (-323.8, -30, 2.5), (-323.2, -21.5, 5), (-319, -17.2, 6.5),
            (-312, -15.6, 7.5)]
    wire = [(u, v, -7.5) for u, v in upper[::-1]] + loop + [(u, v, 7.5) for u, v in lower]
    g.pipe(wire, 3.6, 'park', seg=12, corner=3.0, name='stock')
    for s, v in ((-1, -15.0), (1, -23.2)):                                        # guide tubes at the housing rear
        g.cyl(-86, -62, R + 1.0, 'park', at=(v, s * 7.5), seg=14)

    # ---------------------------------------------------------------- 30-round magazine
    with g.part('mag'):
        traced = g.outline([(154, -84), (202, -84), (202, -250), (154, -250)])
        T, lo, hi, to_uv = edges(traced, (177, -84), -90.0, 0, 166, trim=(6, 14), deg=1)
        body = [to_uv(t, n) for t, n in zip(T, lo)] + [to_uv(t, n) for t, n in zip(T[::-1], hi[::-1])]
        g.extrude(body, width=24, mat='park', bevel=1.4, name='magbody')
        top = [to_uv(-64, lo[0] + 1.5), to_uv(T[0] + 1, lo[0] + 1.5), to_uv(T[0] + 1, hi[0] - 1.5),
               to_uv(-64, hi[0] - 1.5)]
        g.extrude(top, width=22, mat='park', bevel=0.6)
        i0, i1 = 3, len(T) - 4
        for s in (1, -1):                                                        # pressed flank ribs
            for f in (0.3, 0.7):
                line = [to_uv(T[i], lo[i] + (hi[i] - lo[i]) * f) for i in (i0, i1)]
                g.pipe([(u, v, s * 12.0) for u, v in line], 1.2, 'park', seg=8)
        te = T[-1]
        g.extrude([to_uv(te - 4, lo[-1] - 0.8), to_uv(te + 2.5, lo[-1] - 0.8), to_uv(te + 2.5, hi[-1] + 0.8),
                   to_uv(te - 4, hi[-1] + 0.8)], width=26, mat='park', bevel=0.8, name='floor')
    g.pivot('mag', 177, -20)

    # ---------------------------------------------------------------- anchors
    g.anchor('muzzle', 419.2, 0)
    g.anchor('sight', -66.5, SIGHT_V)
    g.anchor('eject', 150, 12, 26)
    g.anchor('rh', -50, -95, 0)
    g.anchor('lh', 176, -70, 0)          # the support hand holds the magazine housing
    g.anchor('eye', -330, SIGHT_V)
