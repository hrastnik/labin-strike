"""US M3 trench knife. Reference: 'M3 knife.jpg' (Eytancal, CC BY-SA 4.0), right side; 292 mm overall, 6.75 in blade.
Frame (knife): u along the blade toward the tip, origin at the middle of the grip, v = spine up, edge down, w right.

Stacked leather washer grip (grooved washer packs with fibre spacers), parkerised steel pommel cap, bent stamped
crossguard (upper arm bent forward), spear-point blade with the edge grind starting at the ricasso and a false edge on
the front of the spine."""
import math

import numpy as np

from .knife_axis import blade_rings

REF = 'knife_allies'
META = {'kind': 'melee'}

STEEL = 'park'
GRIP_U0, GRIP_U1 = -55.8, 62.5
# grip silhouette envelope (top / bottom v at u), measured on the reference
TOP = [(-56, 12.5), (-50, 12.0), (-44, 11.7), (-37, 11.7), (-33, 12.6), (-30, 13.3), (-24, 14.0), (-18, 14.6),
       (-12, 14.9), (-7, 15.0), (0, 15.1), (6, 15.2), (10, 14.9), (15, 14.6), (21, 14.3), (27, 14.0), (33, 13.8),
       (38, 13.5), (43, 12.9), (48, 12.3), (53, 12.8), (58, 13.2), (62.5, 12.7)]
BOT = [(-56, -12.5), (-50, -12.3), (-44, -12.1), (-37, -12.1), (-33, -13.0), (-30, -13.75), (-24, -14.3),
       (-18, -14.8), (-12, -15.1), (-7, -15.4), (0, -15.6), (6, -15.7), (10, -15.5), (15, -15.2), (21, -15.0),
       (27, -14.8), (33, -14.4), (38, -14.0), (43, -13.4), (48, -12.9), (53, -13.1), (58, -13.3), (62.5, -12.5)]
GROOVES = [-1.7 + 11.4 * k for k in range(-4, 6)]          # deep grooves between washer packs
SPACERS = [-1.7 + 11.4 * k for k in range(-1, 4)]          # fibre spacers in the middle of the grip
WR = 0.84                                                  # grip width / height


def lerp(table, x):
    return float(np.interp(x, [p[0] for p in table], [p[1] for p in table]))


def ell(u, vc, a, b, n=20):
    return [(u, vc + a * math.sin(2 * math.pi * k / n), b * math.cos(2 * math.pi * k / n)) for k in range(n)]


def groove_depth(u):
    d = 0.0
    for gq in GROOVES:
        x = abs(u - gq)
        if x < 1.8:
            d = max(d, 1.5 * (1 - (x / 1.8) ** 2))
    for gq0, gq1 in zip(GROOVES, GROOVES[1:]):      # fine joint in the middle of each pack
        x = abs(u - (gq0 + gq1) / 2)
        if x < 0.7:
            d = max(d, 0.45 * (1 - (x / 0.7) ** 2))
    return d


def build(g):
    # ================================================================ blade
    bo = g.outline([(65.6, -30), (245, -30), (245, 26), (65.6, 26)])
    tip_u = max(p[0] for p in bo)
    st = [63.0, 66.0, 70.0, 73.0, 74.3, 75.3, 76.3, 78.0, 81.0, 86.0] + list(np.arange(92.0, 180.0, 11.0))
    st += list(np.arange(180.0, tip_u - 3, 4.0)) + [tip_u - 2.2, tip_u - 1.0, tip_u - 0.35]
    g.loft(blade_rings(bo, st, fit_u=(77, 182), tf0=2.4, tf1=2.0, fuller=None, grind=(74.0, 77.0, -0.6),
                       false_edge=146.0, false_len=30.0, taper_from=182.0, tip_t=0.4), 'bright', name='blade')

    # ================================================================ crossguard: stamped plate, upper arm bent forward
    g.extrude([(62.5, -27.4), (63.1, -28.6, 0.6), (64.6, -28.6, 0.6), (65.2, -27.4), (65.2, 14.0), (71.4, 27.0),
               (70.9, 28.4, 1.0), (69.4, 28.8, 1.0), (68.3, 28.4), (62.5, 16.8)], width=12.0, mat=STEEL, bevel=0.5,
              name='guard')

    # ================================================================ grip: stacked leather washers
    rings = []
    us = sorted(set([round(x, 2) for x in np.arange(GRIP_U0, GRIP_U1 + 0.01, 3.0)]
                    + [round(gq + d, 2) for gq in GROOVES for d in (-1.2, -0.5, 0.0, 0.5, 1.2)
                       if GRIP_U0 <= gq + d <= GRIP_U1]
                    + [round((a + b) / 2 + d, 2) for a, b in zip(GROOVES, GROOVES[1:]) for d in (-0.4, 0, 0.4)]))
    for u in us:
        t, b = lerp(TOP, u), lerp(BOT, u)
        a = (t - b) / 2 - groove_depth(u) + 0.1
        rings.append(ell(u, (t + b) / 2, a, a * WR, n=16))
    g.loft(rings, 'leather', name='washers')
    # fibre spacers, showing in the grooves
    for gq in SPACERS:
        t, b = lerp(TOP, gq), lerp(BOT, gq)
        a = (t - b) / 2 - 0.9
        g.loft([ell(gq - 0.75, (t + b) / 2, a - 0.3, (a - 0.3) * WR), ell(gq - 0.55, (t + b) / 2, a, a * WR),
                ell(gq + 0.55, (t + b) / 2, a, a * WR), ell(gq + 0.75, (t + b) / 2, a - 0.3, (a - 0.3) * WR)],
               'bakelite', name='spacer')
    # tang shoulder washer against the guard
    g.loft([ell(61.0, -0.1, 12.0, 12.0 * WR), ell(61.4, -0.1, 12.6, 12.6 * WR), ell(62.6, -0.1, 12.6, 12.6 * WR)],
           STEEL, name='ferrule')

    # ================================================================ pommel cap (peened tang end on the back)
    prof = [(-62.6, 12.6), (-62.3, 14.6), (-61.4, 15.6), (-60.0, 16.0), (-57.0, 16.0), (-56.2, 15.5), (-55.8, 14.0),
            (-55.4, 12.0)]
    g.loft([ell(u, -0.2, a, a * WR) for u, a in prof], STEEL, name='pommel')
    g.lathe([(-62.5, 3.4), (-62.9, 3.0), (-63.2, 1.8), (-63.3, 0)], STEEL, axis='u', at=(-0.2, 0), seg=16,
            name='peen')
