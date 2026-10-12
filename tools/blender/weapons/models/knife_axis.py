"""S84/98 (3rd pattern) bayonet, blade out. Reference: 'Bayonet and scabbard and frog (AM 696924-5).jpg' (Weyersberg,
Kirschbaum & Cie, CC BY 4.0), right side; 385 mm overall, 250 mm blade. Frame (knife): u along the blade toward the
tip, origin at the middle of the grip, v = spine up, edge down, w right.

Steel pommel with the T-slot along the spine and the press-stud release on the right, walnut scales held by two
through-screws, oval crossguard, bright blade with a wide fuller below the spine and a long flat edge grind starting
at the ricasso, short false edge at the point."""
import math

import numpy as np

REF = 'knife_axis'
META = {'kind': 'melee'}

STEEL = 'blued_old'
GUARD_U0, GUARD_U1 = 63.5, 72.0


def crossings(outline, u):
    """lowest / highest v where the vertical line at u crosses the closed outline."""
    xs = []
    for i in range(len(outline)):
        (u0, v0), (u1, v1) = outline[i - 1][:2], outline[i][:2]
        if (u0 - u) * (u1 - u) < 0:
            xs.append(v0 + (v1 - v0) * (u - u0) / (u1 - u0))
    return (min(xs), max(xs)) if len(xs) >= 2 else None


def blade_rings(bo, stations, fit_u=(76, 262), tf0=2.7, tf1=2.35, fuller=(0.6, 10.4, 86, 262, 1.1),
                grind=(85.0, 91.0, -0.8), false_edge=274.0, false_len=14.0, taper_from=262.0, tip_t=0.45):
    """loft rings for a blade traced as `bo`: spine/edge lines fitted with smooth polynomials on the straight part,
    raw (lightly smoothed) toward the point. Section: rounded spine, fuller, flat, long grind down to the edge."""
    tip = max(bo, key=lambda p: p[0])
    U = np.arange(fit_u[0], fit_u[1] + 0.1, 2.0)
    C = [crossings(bo, u) for u in U]
    lo_c = np.polyfit(U, [c[0] for c in C], 2)
    hi_c = np.polyfit(U, [c[1] for c in C], 2)

    def lines(u):
        if u <= fit_u[1]:
            return float(np.polyval(lo_c, u)), float(np.polyval(hi_c, u))
        if u >= tip[0] - 0.05:
            return tip[1], tip[1]
        cs = [crossings(bo, x) for x in (u - 1.0, u, u + 1.0) if x < tip[0]]
        cs = [c for c in cs if c]
        lo, hi = sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs)
        k = min(1.0, (u - fit_u[1]) / 6.0)               # blend from the fit into the trace
        flo, fhi = float(np.polyval(lo_c, u)), float(np.polyval(hi_c, u))
        return flo + (lo - flo) * k, fhi + (hi - fhi) * k

    f0, f1, fu0, fu1, fdep = fuller or (0, 1, 0, 0, 0)
    g0, g1, gtop = grind
    rings = []
    for u in stations:
        vb, vt = lines(u)
        H = vt - vb
        if u < taper_from:
            tf = tf0 + (tf1 - tf0) * (u - stations[0]) / (taper_from - stations[0])
        else:
            tf = tf1 + (tip_t - tf1) * min(1.0, (u - taper_from) / (tip[0] - taper_from))
        # fuller with round ends
        k = min(1.0, max(0.0, (u - fu0) / 6.0), max(0.0, (fu1 - u) / 7.0)) if fuller else 0.0
        if k > 0:
            f1u = min(f1, vt - 2.2)
            hw = (f1u - f0) / 2 * math.sqrt(1 - (1 - k) ** 2)
            fc = (f0 + f1u) / 2
            d = fdep * math.sqrt(k)
            fa, fd = fc - hw - 0.5, fc + hw + 0.5
            fb, fcc = fc - hw + 0.9 * k, fc + hw - 0.9 * k
        else:
            d = 0.0
        # edge grind starts at the ricasso with a rounded plunge
        gk = 0.0 if u <= g0 else min(1.0, math.sqrt(min(1.0, (u - g0) / (g1 - g0))))
        e = tf * 0.55 * (1 - gk) + 0.22 * gk
        vg = vb + 0.7 * min(1.0, H / 4) + (min(gtop, vb + 0.6 * H) - vb - 0.7 * min(1.0, H / 4)) * gk
        # false edge at the point
        fk = 0.0 if u <= false_edge else min(1.0, (u - false_edge) / false_len)
        etop = tf * 0.7 * (1 - fk) + 0.22 * fk
        vtg = max(vt - min(0.8, 0.2 * H) - (vt - vg) * 0.45 * fk, vg + 0.3 * (vt - vg))
        if d == 0.0:
            a, b = vg + (vtg - vg) * 0.2, vtg - (vtg - vg) * 0.2
            fa, fb, fcc, fd = a, a + (b - a) / 3, a + 2 * (b - a) / 3, b
        P = [(vb, e), (vg, tf), (fa, tf), (fb, tf - d), (fcc, tf - d), (fd, tf), (vtg, tf), (vt, etop)]
        ring = [(u, v, -w) for v, w in P] + [(u, v, w) for v, w in reversed(P)]     # outward winding
        rings.append(ring)
    return rings


def build(g):
    # ================================================================ blade
    bo = g.outline([(GUARD_U1 + 0.5, -30), (340, -30), (340, 30), (GUARD_U1 + 0.5, 30)])
    tip_u = max(p[0] for p in bo)
    st = [GUARD_U0 + 0.5, 72.0, 78.0, 83.0, 85.0, 86.5, 88.0, 90.0, 92.0, 95.0]
    st += list(np.arange(104.0, 250.0, 12.0)) + [250.0, 254.0, 257.0, 259.5, 262.0, 266.0, 270.0, 274.0]
    st += list(np.arange(278.0, tip_u - 4, 4.0)) + [tip_u - 3.0, tip_u - 1.6, tip_u - 0.5]
    g.loft(blade_rings(bo, st), 'bright', name='blade')

    # ================================================================ crossguard (oval plate) and tang shoulder
    gv0, gv1 = -21.2, 18.7
    hw = 7.6
    oval = [(hw * math.cos(a), (gv0 + gv1) / 2 + ((gv1 - gv0) / 2 - hw) * (1 if math.sin(a) > 0 else -1)
             + hw * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 33)[:-1]]
    g.extrude(oval, GUARD_U0, GUARD_U1, STEEL, plane='front', bevel=2.6, seg=3, name='guard')
    g.box(58.0, GUARD_U0 + 0.5, 11.5, 15.6, width=14.0, mat=STEEL, bevel=1.0, name='shoulder')

    # ================================================================ handle: steel pommel + walnut scales
    H = g.outline([(-75, -26), (GUARD_U0, -26), (GUARD_U0, 26), (-75, 26)])
    pom = g.sweep(H, STEEL, width=22.4, radius=(5.5, 5.5), axis=0, origin=(0, 0), step=3.0, t1=-14.0,
                  round_ends=(1.4, 0), name='pommel')
    # T-slot for the bayonet lug along the spine, open at the back
    g.cut(pom, g.extrude([(-5.0, 12.4), (5.0, 12.4), (5.0, 14.2), (3.2, 14.2), (3.2, 22), (-3.2, 22), (-3.2, 14.2),
                          (-5.0, 14.2)], -80, -36.0, plane='front', cutter=True, bevel=0))
    wood = g.sweep(H, 'walnut', width=23.0, radius=(6.0, 6.0), axis=0, origin=(0, 0), step=3.0, t0=-47.0,
                   t1=GUARD_U0 + 0.3, name='scales')
    # scales end in a curved line: the pommel's steel shows along the spine back to u -16
    g.cut(wood, g.extrude([(-60, -30), (-44.5, -14), (-42.0, -4), (-40.0, 3.4), (-34, 5.4), (-24.0, 6.6),
                           (-20.5, 8.3), (-17.8, 11.0), (-16.4, 13.6), (-15.8, 30), (-60, 30)], -20, 20,
                          cutter=True, bevel=0))
    # through-screws with countersunk washers (both sides)
    for u, v, r in ((-11.0, 3.0, 4.4), (40.0, 2.5, 4.1)):
        for s in (1, -1):
            g.lathe([(11.0 * s, 0), (11.0 * s, r), (11.7 * s, r * 0.92), (11.7 * s, 0)], STEEL, axis='w',
                    at=(u, v), seg=16)
            g.lathe([(11.5 * s, 0), (11.5 * s, r * 0.55), (12.0 * s, r * 0.45), (12.25 * s, 0)], STEEL, axis='w',
                    at=(u, v), seg=12)
    # press stud (right side of the pommel)
    g.lathe([(10.6, 0), (10.6, 6.0), (11.6, 5.8), (12.0, 5.0), (12.0, 0)], STEEL, axis='w', at=(-57.0, 1.5),
            seg=20, name='stud_ring')
    g.lathe([(11.8, 0), (11.8, 2.9), (12.8, 2.6), (13.4, 1.6), (13.6, 0)], 'bright', axis='w', at=(-57.0, 1.5),
            seg=14, name='stud')
    g.lathe([(-10.6, 0), (-10.6, 4.0), (-11.5, 3.6), (-11.7, 0)], STEEL, axis='w', at=(-57.0, 1.5), seg=14)
