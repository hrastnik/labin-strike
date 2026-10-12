"""Stielhandgranate 24 (M24 stick grenade). Reference: 'Stielhandgranate Deutschlandmuseum Berlin, CC BY-SA 4.0.jpg'
(CC BY-SA 4.0), lying diagonally; calibrated along the stick axis. 365 mm: field-grey can head (rolled rear rim,
spring-steel belt clip), wooden stick, riveted steel ferrule at the head and a threaded screw cap at the end.
Grenade frame: u along the stick toward the head, origin at the balance point (head/ferrule joint)."""
import math

REF = 'stielhandgranate'
META = {'kind': 'grenade'}

R_CAN = 31.3


def build(g):
    # ---------------------------------------------------------------- head (painted steel can)
    head = [(4.5, 0), (4.5, 21.0), (5.5, 27), (6.5, 32.5), (8.0, 34.6), (10.5, 35.0), (12.6, 34.2), (14.0, 32.4),
            (15.5, R_CAN), (106.5, R_CAN), (108.6, 30.6), (109.8, 29.2), (110.3, 26), (110.3, 0)]
    g.lathe(head, 'feldgrau', seg=40, name='head')
    g.lathe([(110.0, 0), (110.0, 9), (110.8, 8.4), (111.0, 0)], 'feldgrau', seg=20)       # filler plug on the face
    # belt clip: spring-steel strip lying on the +w side, bent onto the can at its front end
    a0, a1 = math.radians(-42), math.radians(-17)
    n = 8
    outer = [(33.9 * math.cos(a0 + (a1 - a0) * k / n), 33.9 * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
    inner = [(32.7 * math.cos(a1 + (a0 - a1) * k / n), 32.7 * math.sin(a1 + (a0 - a1) * k / n)) for k in range(n + 1)]
    g.extrude(outer + inner, 22, 101, 'feldgrau', plane='front', bevel=0.4, name='clip')
    inner2 = [(31.0 * math.cos(a1 + (a0 - a1) * k / n), 31.0 * math.sin(a1 + (a0 - a1) * k / n)) for k in range(n + 1)]
    g.extrude(outer + inner2, 99, 104, 'feldgrau', plane='front', bevel=0.4)                   # bend / weld
    am = (a0 + a1) / 2                                       # rivet on the clip's front end
    rv = g.lathe([(33.9, 0), (33.9, 2.3), (34.9, 1.8), (35.2, 0)], 'feldgrau', axis='w', seg=10, at=(101.5, 0))
    g.transform(rv, rot=('u', -math.degrees(am)))

    # ---------------------------------------------------------------- ferrule (steel collar joining head and stick)
    ferr = [(-23, 0), (-23, 19.6), (-16, 20.0), (-10, 20.6), (-6, 21.4), (-4, 21.9), (-2.6, 22.6), (-1.4, 22.6),
            (-0.4, 22.0), (5.0, 22.2), (5.0, 0)]
    g.lathe(ferr, 'feldgrau', seg=32, name='ferrule')
    for k in range(4):                                       # rivets fixing the ferrule to the stick
        a = math.radians(45 + 90 * k)
        rv = g.lathe([(20.2, 0), (20.2, 2.2), (21.1, 1.7), (21.4, 0)], 'feldgrau', axis='w', seg=10, at=(-12, 0))
        g.transform(rv, rot=('u', math.degrees(a)))

    # ---------------------------------------------------------------- wooden stick
    stick = [(-238.5, 0), (-238.5, 18.6), (-236, 18.9), (-230, 19.2), (-222, 19.0), (-215, 18.5), (-208, 17.8),
             (-199, 16.6), (-190, 16.0), (-176, 15.9), (-160, 16.2), (-148, 16.8), (-136, 17.6), (-124, 18.2),
             (-112, 18.8), (-100, 19.2), (-85, 19.6), (-62, 19.8), (-22, 19.9), (-22, 0)]
    g.lathe(stick, 'beech', seg=32, name='stick')

    # ---------------------------------------------------------------- threaded screw cap at the end of the stick
    cap = [(-258.4, 0), (-258.4, 14.0), (-257.6, 16.4), (-256.2, 17.6)]
    for k in range(3):
        c = -254.2 + 3.4 * k
        cap += [(c - 1.0, 18.5), (c + 0.5, 18.5), (c + 1.3, 17.4), (c + 2.1, 17.4)]
    cap += [(-245.6, 18.2), (-239.0, 18.2), (-238.0, 18.8), (-237.0, 18.8), (-237.0, 0)]
    g.lathe(cap, 'feldgrau', seg=32, name='cap')
    g.lathe([(17.2, 0), (17.2, 1.8), (17.9, 1.4), (18.4, 0)], 'feldgrau', axis='w', seg=8, at=(-242, -6))

    g.pivot('body', 0, 0)
