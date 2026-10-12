"""Site: street, sidewalks, parking lot, embankment + park, stairs, retaining wall, SE pocket, terrain and
backdrop, prop placement, gameplay colliders, clips, spawns and bounds."""
import math

from mathutils import Vector

from . import buildings as B
from . import ne_bank as NE
from . import props as P
from .lib import G, collider, collider_mm, collider_seg, marker, pbr, rng
from .palette import M

GG = 'Ground.paving'
Z_WALK = 0.12          # sidewalks / lot / plaza level
Z_PARK = 2.8           # park above the NE bank
Z_PLATEAU = 4.4        # ground behind the SE retaining wall

# street geometry: straight along X, quarter turn into the lower road (x 62.9..69.9) at the SE end
ARC_C = (58.5, -7.9)
R_IN, R_OUT = 4.4, 11.4
WALL_PATH = [(57.5, 70.0), (57.5, 45.0), (60.0, 23.5), (64.5, 8.0), (69.5, 1.5), (71.0, -6.0), (71.0, -110.0)]


def arc_pts(r, n=12, a0=90.0, a1=0.0):
    return [(ARC_C[0] + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             ARC_C[1] + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def centreline():
    return [(-165.0, 0.0)] + arc_pts((R_IN + R_OUT) / 2, 14) + [(66.4, -110.0)]


def strip(mb, left, right, z, m):
    for i in range(len(left) - 1):
        mb.quad([(right[i][0], right[i][1], z), (right[i + 1][0], right[i + 1][1], z),
                 (left[i + 1][0], left[i + 1][1], z), (left[i][0], left[i][1], z)], m)


def offset(pts, off):
    out = []
    for i, p in enumerate(pts):
        a = Vector(pts[max(0, i - 1)])
        b = Vector(pts[min(len(pts) - 1, i + 1)])
        d = (b - a).normalized()
        n = Vector((d.y, -d.x))   # right-hand side
        if 0 < i < len(pts) - 1:
            d0 = (Vector(p) - a).normalized()
            d1 = (b - Vector(p)).normalized()
            n0, n1 = Vector((d0.y, -d0.x)), Vector((d1.y, -d1.x))
            n = (n0 + n1).normalized()
            n /= max(0.3, n.dot(n0))
        out.append((p[0] + n.x * off, p[1] + n.y * off))
    return out


def walk_line(pts, step):
    """yield (pos, dir, s) along a polyline every `step` metres"""
    s = 0.0
    nxt = 0.0
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        L = (b - a).length
        d = (b - a) / L
        while nxt <= s + L:
            yield a + d * (nxt - s), d, nxt
            nxt += step
        s += L


def dashes(mb, pts, on, off, w, z, m, s0=0.0):
    """dashed line along polyline"""
    segs = []
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        L = (b - a).length
        d = (b - a) / L
        t = 0.0
        while t < L:
            phase = (acc + t + s0) % (on + off)
            if phase < on:
                run = min(on - phase, L - t)
                segs.append((a + d * t, a + d * (t + run), d))
                t += run
            else:
                t += min(on + off - phase, L - t)
        acc += L
    for p, q, d in segs:
        n = Vector((-d.y, d.x)) * (w / 2)
        mb.quad([(p.x - n.x, p.y - n.y, z), (q.x - n.x, q.y - n.y, z), (q.x + n.x, q.y + n.y, z), (p.x + n.x, p.y + n.y, z)], m)


def paint_rect(mb, x0, x1, y0, y1, z, m=None):
    mb.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], m or M['paint'])


def slab(pts, top, z=Z_WALK, side=None, g=GG, z0=-0.3):
    G[g].poly_prism(pts, z0, z, top, side=side or M['kerb'])


# ------------------------------------------------------------------------------------------------
# ground surfaces
# ------------------------------------------------------------------------------------------------

def ground():
    M['grass_far'] = pbr('grass_far', 'grass', 16.0, rough=1.0, tint=(0.9, 0.92, 0.85))
    mb = G['Ground.base']
    # base plain under everything (core area), later met by the hills
    mb.quad([(-165, -112, -0.02), (152, -112, -0.02), (152, 88, -0.02), (-165, 88, -0.02)], M['grass'])
    # street + lower road
    c = centreline()
    road = G['Ground.road']
    strip(road, offset(c, -3.5), offset(c, 3.5), 0.0, M['asphalt'])
    # asphalt between the lower road and the retaining wall, and the side street on the SW
    road.quad([(69.8, -110, -0.004), (71.2, -110, -0.004), (71.2, -6, -0.004), (69.8, -6, -0.004)], M['asphalt'])
    road.quad([(-68.8, -60, 0.0), (-62.7, -60, 0.0), (-62.7, -3.4, 0.0), (-68.8, -3.4, 0.0)], M['asphalt'])
    # centre line, crossing, school zig-zag
    pm = G['Ground.paint']
    dashes(pm, [(-165, 0)] + arc_pts((R_IN + R_OUT) / 2, 14) + [(66.4, -110)], 3.0, 3.0, 0.12, 0.006, M['paint'])
    for k in range(7):
        y = -3.0 + k * 1.0
        paint_rect(pm, -56.2, -53.2, y - 0.25, y + 0.25, 0.007)
    zz = [(-20.0 + k * 1.0, -3.1 if k % 2 == 0 else -2.5) for k in range(11)]
    for a, b in zip(zz, zz[1:]):
        pm.quad(seg_quad(a, b, 0.1, 0.007), M['paint_y'])
    # stop line at the side street mouth
    paint_rect(pm, -68.5, -65.8, -3.9, -3.6, 0.007)

    # ---- SW sidewalks (kerb at y = -3.5) ----
    slab([(-165, -8.6), (-68.8, -8.6), (-68.8, -3.5), (-165, -3.5)], M['walk'])
    slab([(-62.7, -8.4), (-25.9, -8.4), (-25.9, -3.5), (-62.7, -3.5)], M['walk'])
    slab([(-25.9, -7.0), (1.1, -7.0), (1.1, -3.5), (-25.9, -3.5)], M['walk'])
    slab([(1.1, -6.1), (37.7, -6.1), (37.7, -3.5), (1.1, -3.5)], M['walk'])
    slab([(37.7, -10.1), (46.8, -10.1), (46.8, -3.5), (37.7, -3.5)], M['walk'])
    collider_mm('walk', -165, -68.8, -8.6, -3.5, -1, Z_WALK)
    collider_mm('walk', -62.7, 46.8, -8.4, -3.5, -1, Z_WALK)
    # SE pocket (paved court) and the plane-tree strip, both bounded by the inner kerb of the turn
    inner = arc_pts(R_IN, 12)
    ain = [p for p in inner if p[0] <= 60.3 + 1e-6]
    pocket = [(46.8, -110.0), (60.3, -110.0), (60.3, ARC_C[1] + math.sqrt(R_IN ** 2 - (60.3 - ARC_C[0]) ** 2))] + \
        list(reversed([p for p in ain if p[0] < 60.29])) + [(46.8, -3.5)]
    pocket = dedupe(pocket)
    slab(ccw(pocket), M['walk'])
    stripp = [(60.3, -110.0), (62.9, -110.0)] + list(reversed([p for p in inner if p[0] >= 60.3])) + \
        [(60.3, ARC_C[1] + math.sqrt(R_IN ** 2 - (60.3 - ARC_C[0]) ** 2))]
    slab(ccw(dedupe(stripp)), M['soil'])
    collider_mm('walk', 46.8, 62.9, -110, -6.5, -1, Z_WALK)
    collider_mm('walk', 46.8, 58.5, -6.5, -3.5, -1, Z_WALK)

    # ---- NE side: lot, plaza / courtyard, school lawn ----
    lot = [(-40, 3.5), (56, 3.5), (56, 23.5), (-34, 23.5), (-34, 18.5), (-40, 18.5)]
    slab(lot, M['lot'])
    collider_mm('lot', -40, 56, 3.5, 23.5, -1, Z_WALK)
    plaza = [(-77.0, 3.5), (-40.0, 3.5), (-40.0, 18.5), (-43.0, 18.5), (-43.0, 18.0), (-64.0, 18.0), (-64.0, 34.4),
             (-74.1, 34.4), (-74.1, 18.2), (-77.0, 18.2)]
    slab(plaza, M['plaza'])
    collider_mm('plaza', -77.4, -40, 3.5, 18.5, -1, Z_WALK)
    collider_mm('plaza', -74.1, -64, 18.0, 34.4, -1, Z_WALK)
    slab([(-165, 3.5), (-77, 3.5), (-77, 5.6), (-165, 5.6)], M['walk'])
    slab([(-165, 5.6), (-77, 5.6), (-77, 18.2), (-165, 18.2)], M['grass'], z=0.16, side=M['concrete'])
    collider_mm('walk', -80, -77.4, 3.5, 18.2, -1, Z_WALK)
    # SE corner bank between the lot and the retaining wall (soil, shrubs, rocks)
    outer = arc_pts(R_OUT, 12)
    bank = [(56.0, 3.5)] + [p for p in outer if p[1] > -4.0 and p[0] > 58.6] + [(70.3, -5.0), (69.5, 1.5), (64.5, 8.0),
                                                                                 (60.0, 23.5), (56.0, 23.5)]
    slab(ccw(dedupe(bank)), M['soil'], z=0.1)
    # dropped kerbs at the lot entries are implied by the 12 cm step (auto-stepped)


def seg_quad(a, b, w, z):
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    n = Vector((-d.y, d.x)) * (w / 2)
    return [(a.x - n.x, a.y - n.y, z), (b.x - n.x, b.y - n.y, z), (b.x + n.x, b.y + n.y, z), (a.x + n.x, a.y + n.y, z)]


def dedupe(pts, eps=1e-3):
    out = []
    for p in pts:
        if not out or (abs(out[-1][0] - p[0]) > eps or abs(out[-1][1] - p[1]) > eps):
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


def ccw(pts):
    a = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return pts if a > 0 else list(reversed(pts))


# ------------------------------------------------------------------------------------------------
# lot markings and cars
# ------------------------------------------------------------------------------------------------
STALL_X0, STALL_W = -38.0, 2.5
ROWS = [(3.8, 8.6, -math.pi / 2, 0.85), (8.6, 13.4, -math.pi / 2, 0.7), (19.0, 23.5, math.pi / 2, 0.8)]


def lot_and_cars():
    pm = G['Ground.paint']
    z = Z_WALK + 0.006
    nst = int((53.0 - STALL_X0) / STALL_W)
    paint_rect(pm, STALL_X0, STALL_X0 + nst * STALL_W, 8.55, 8.65, z)
    for (y0, y1, yaw_main, p_main) in ROWS:
        x_start = -33.0 if y0 > 15 else STALL_X0
        k0 = int(round((x_start - STALL_X0) / STALL_W))
        for k in range(k0, nst + 1):
            x = STALL_X0 + k * STALL_W
            if y0 > 15 and -3.6 < x < 10.6:
                continue
            yellow = y0 > 15 and -10.6 < x < -3.4
            paint_rect(pm, x - 0.05, x + 0.05, y0 + (0.25 if y0 < 4 else 0.0), y1 - (0.4 if y0 > 15 else 0.0), z,
                       M['paint_y'] if yellow else None)
            if k == nst:
                break
            cx = x + STALL_W / 2
            if y0 > 15 and -3.6 < cx < 10.6:
                continue
            if rng.random() > 0.62:
                continue
            yaw = yaw_main if rng.random() < p_main else yaw_main + math.pi
            yaw += rng.uniform(-0.04, 0.04)
            cy = (y0 + y1) / 2 + rng.uniform(-0.15, 0.15) + (0.1 if y0 < 4 else 0) - (0.35 if y0 > 15 else 0)
            P.car(cx + rng.uniform(-0.12, 0.12), cy, yaw, z=Z_WALK)
    # pocket: nose-in along the admin facade, one SUV near the tower
    for k in range(8):
        y = -27.0 - k * 2.6
        if rng.random() < 0.88:
            P.car(49.4 + rng.uniform(-0.1, 0.2), y, math.pi + rng.uniform(-0.05, 0.05), z=Z_WALK)
    P.car(49.6, -12.4, math.pi, z=Z_WALK, kind='suv', paint=M['car_paints'][2])
    # parallel parking on the strip in front of the annex
    for x in (4.6, 9.4, 17.2, 22.0, 34.0):
        P.car(x, -4.85, 0.0 if rng.random() < 0.5 else math.pi, z=Z_WALK)
    # lower road along the foot of the retaining wall
    for y in (-11.0, -16.2, -21.4, -31.0, -36.2, -44.0):
        P.car(68.8, y + rng.uniform(-0.3, 0.3), math.pi / 2 if rng.random() < 0.5 else -math.pi / 2)
    # white box truck on the NE lane by the lot
    P.box_truck(34.0, 2.25, math.pi)
    # a few cars on the street beyond the playable area and on the upper road
    for (x, y, yaw) in ((-95.0, -2.0, 0.0), (-120.0, 2.1, math.pi), (66.4 + 1.8, -75.0, math.pi / 2)):
        P.car(x, y, yaw, collide=False)
    for y in (-40.0, -20.0, 5.0, 30.0):
        P.car(78.6, y, math.pi / 2 if rng.random() < 0.5 else -math.pi / 2, z=Z_PLATEAU + 0.02, collide=False)
    P.scooter(-44.6, 13.6, 0.5, z=Z_WALK)


# ------------------------------------------------------------------------------------------------
# kerbs, street furniture
# ------------------------------------------------------------------------------------------------

def kerbs():
    mb = G['Ground.kerb']
    m = M['kerb']
    # NE kerb (lot / plaza), with a gap at both lot entries
    for x0, x1 in ((-165.0, -40.5), (-35.5, 52.6)):
        mb.box_mm(x0, x1, 3.45, 3.65, -0.1, 0.15, m)
    # SW kerb
    for x0, x1 in ((-165.0, -68.8), (-62.7, ARC_C[0])):
        mb.box_mm(x0, x1, -3.65, -3.45, -0.1, 0.15, m)
    # inner kerb around the turn and along the plane-tree strip
    pts = arc_pts(R_IN + 0.08, 12) + [(62.98, -110.0)]
    for a, b in zip(pts, pts[1:]):
        mb.seg_box(a, b, 0.2, -0.1, 0.15, m, ext=0.05)
    # outer kerb along the bank (lot corner -> wall)
    pts = [p for p in arc_pts(R_OUT - 0.08, 12) if p[1] > -4.5]
    for a, b in zip(pts, pts[1:]):
        mb.seg_box(a, b, 0.2, -0.1, 0.14, m, ext=0.05)
    # side street corners
    mb.box_mm(-69.0, -68.8, -60, -3.5, -0.1, 0.15, m)
    mb.box_mm(-62.7, -62.5, -60, -3.5, -0.1, 0.15, m)


def street_furniture():
    zw = Z_WALK
    # two-arm lamps at the lot kerb, one by the plaza, one far NW
    for x in (-30.0, -5.0, 20.0, 45.0):
        P.lamp_double(x, 3.95, zw, arm_dir=(1, 0))
    P.lamp_double(-60.0, 4.0, zw, arm_dir=(1, 0))
    P.lamp_double(-95.0, 4.0, zw, arm_dir=(1, 0))
    P.lamp_double(-20.0, -4.0, zw, arm_dir=(1, 0))
    # mushroom lamps: pocket wall end, plane-tree strip, wall foot, park
    for (x, y, z) in ((60.6, -6.4, zw), (61.7, -22.0, zw), (61.7, -38.0, zw), (70.4, -14.0, 0.0), (70.4, -30.0, 0.0),
                      (68.5, 0.6, 0.1), (-22.0, 29.3, Z_PARK), (12.0, 32.8, Z_PARK), (-37.0, 30.0, Z_PARK), (40.0, 30.5, Z_PARK)):
        P.lamp_mushroom(x, y, z)
    # signs
    P.sign_post(55.4, 4.3, zw, -math.pi / 2, [(M['sign_p'], 0.6, 0.6, 2.25)])
    P.sign_post(-52.5, 4.05, zw, -math.pi / 2, [(M['sign_cross'], 0.6, 0.6, 2.3)])
    P.sign_post(-56.9, -4.05, zw, math.pi / 2, [(M['sign_cross'], 0.6, 0.6, 2.3)])
    # bike hoops in front of the teal building
    for x in (-36.2, -35.3, -34.4, -33.5):
        P.bike_rack(x, -4.0, zw, math.pi / 2)
    # bins
    P.litter_bin(-51.0, 4.6, zw)
    P.litter_bin(-10.0, -4.0, zw, m=M['bin_gray'])
    P.litter_bin(30.0, -4.0, zw, m=M['bin_gray'])
    # recycling containers inside the curved pocket wall
    for k, m in enumerate((M['bin_yellow'], M['bin_blue'], M['bin_green'], M['bin_yellow'])):
        P.container(58.9, -8.4 - k * 1.5, zw, math.pi / 2, m)
    # manholes & drains
    for x in range(-150, 56, 23):
        P.manhole(x + 3.0, 1.6 if (x // 23) % 2 else -1.6, 0.0)
    for y in (-20.0, -42.0, -70.0):
        P.manhole(66.4, y, 0.0)
    for x in range(-150, 56, 17):
        P.drain(x + 1.0, -3.2, 0.0)
        P.drain(x + 9.0, 3.2, 0.0)
    # ELNA-type electrical cabinet by the lot entry
    G['Props.street'].box((51.8, 4.15, zw + 0.65), (0.9, 0.4, 1.3), M['cabinet'])
    collider('cabinet', (51.8, 4.15, zw + 0.65), (0.9, 0.4, 1.3))


# ------------------------------------------------------------------------------------------------
# NE: plaza details, NE bank (ne_bank.py), park
# ------------------------------------------------------------------------------------------------

def plaza():
    zw = Z_WALK
    mb = G['Props.site']
    # raised concrete planter with hedge, shrubs and the yellow-green tree
    x0, x1, y0, y1 = -56.0, -44.0, 8.0, 13.0
    mb.box_mm(x0, x1, y0, y1, zw - 0.05, zw + 0.7, M['concrete'])
    G['Ground.planter'].poly_flat(B.rect(x0 + 0.25, x1 - 0.25, y0 + 0.25, y1 - 0.25), zw + 0.72, M['soil'])
    collider_mm('planter', x0, x1, y0, y1, -1, zw + 0.7)
    P.hedge((x0 + 0.7, y1 - 0.75), (x1 - 0.7, y1 - 0.75), zw + 0.7, h=0.9, w=1.0)
    for x in (-54.0, -51.0, -47.5, -45.5):
        P.bush(x, 9.6 + rng.uniform(-0.3, 0.3), zw + 0.7, r=0.9, h=1.0)
    P.tree_broad(-50.5, 10.4, zw + 0.7, h=6.5, crown=2.8, leaf=M['leaf_yellow'], trunk_h=2.2, collide=True)
    # café terrace in front of the glass corner
    for (x, y) in ((-63.0, 11.0), (-60.4, 11.2), (-63.2, 14.0), (-60.6, 14.2), (-58.2, 12.6), (-65.6, 12.4)):
        P.cafe_set(x, y, zw, rng.uniform(0, math.tau))
    P.parasol(-61.8, 12.6, zw, r=2.0)
    P.parasol(-59.0, 13.6, zw, r=1.6)
    for (x, y) in ((-63.0, 11.0), (-60.4, 11.2), (-63.2, 14.0), (-60.6, 14.2), (-58.2, 12.6), (-65.6, 12.4)):
        collider('table', (x, y, zw + 0.45), (1.6, 1.6, 0.9), clip=True)
    # hedge along the school lawn edge and cedars on the lawn
    P.hedge((-165, 5.9), (-77.6, 5.9), 0.16, h=0.9, w=0.8, collide=False, fuzz=False)
    P.tree_cedar(-84.0, 11.5, 0.16, h=16.0, r=6.0, collide=False)
    P.tree_cedar(-97.0, 12.5, 0.16, h=18.0, r=7.0, collide=False)
    P.tree_cedar(-113.0, 11.0, 0.16, h=15.0, r=6.0, collide=False)
    P.tree_broad(-79.6, 14.8, 0.16, h=9.0, crown=3.2, collide=False)
    P.tree_conifer(-128.0, 12.0, 0.16, h=17.0, rbase=3.2, collide=False)
    # a tree and bench in the courtyard (axis spawn)
    P.tree_broad(-66.0, 31.6, zw, h=9.5, crown=3.0)
    P.bench(-71.5, 33.4, zw, 0.0)


def embankment_and_park():
    # NE lot edge (walls, outcrop, stair, bank, driveway) after the Street View shots
    NE.build()
    # park ground above the bank (its front is the top of the bank; notch for the central stair flight)
    yt = NE.Y_TOP
    park = [(-43.0, 34.4), (-38.0, 34.4), (-38.0, yt), (2.0, yt), (2.0, 29.0), (5.0, 29.0), (5.0, yt), (NE.wall_x(yt), yt),
            (57.5, 45.0), (57.5, 88.0), (-43.0, 88.0)]
    G['Ground.park'].poly_prism(park, -0.3, Z_PARK, M['grass'], side=M['soil'])
    collider_mm('park', -43.0, -38.0, NE.DRIVE_TOP, 88.0, -1, Z_PARK)
    collider_mm('park', -38.0, 2.0, yt, 88.0, -1, Z_PARK)
    collider_mm('park', 5.0, 59.0, yt, 88.0, -1, Z_PARK)
    collider_mm('park', 2.0, 5.0, 29.0, 88.0, -1, Z_PARK)
    # footpaths
    pm = G['Ground.paths']
    # light paving L along the Erste side (very visible on the aerial)
    pm.quad([(-6.0, yt + 0.1, Z_PARK + 0.012), (-3.8, yt + 0.1, Z_PARK + 0.012), (-3.8, 37.5, Z_PARK + 0.012), (-6.0, 37.5, Z_PARK + 0.012)],
            M['slabs'])
    pm.quad([(-6.0, 37.5, Z_PARK + 0.012), (15.0, 37.5, Z_PARK + 0.012), (15.0, 40.0, Z_PARK + 0.012), (-6.0, 40.0, Z_PARK + 0.012)],
            M['slabs'])
    for a, b, w in (((3.5, 28.8), (12.5, 36.2), 2.2), ((12.5, 36.2), (22.8, 43.5), 2.2), ((3.5, 28.8), (-36.0, 28.4), 2.0),
                    ((-36.0, 28.4), (-39.8, 32.8), 2.0), ((3.5, 28.8), (40.0, 29.8), 2.0), ((40.0, 29.8), (56.0, 30.5), 2.0)):
        pm.quad(seg_quad(a, b, w, Z_PARK + 0.012), M['pavers'])
    # benches, bins
    for (x, y) in ((-26.0, 29.9), (-9.0, 29.8), (16.0, 30.6), (30.0, 30.9)):
        P.bench(x, y, Z_PARK, 0.0)
        collider('bench', (x, y + 0.05, Z_PARK + 0.4), (1.9, 0.7, 0.8), clip=True)
    P.litter_bin(-1.0, 29.9, Z_PARK)
    # trees: tall spruces cluster + deciduous (the front ones stand on the bank)
    for (x, y, h) in ((23.5, 27.6, 20.0), (29.6, 31.3, 23.0), (34.8, 26.8, 18.0), (38.6, 32.4, 19.5), (27.0, 25.4, 15.0),
                      (45.0, 33.2, 17.0)):
        P.tree_conifer(x, y, NE.bank_z(x, y), h=h, rbase=h * 0.17)
    for (x, y, h, cr) in ((-30.0, 31.6, 11.0, 4.0), (-21.0, 26.4, 12.0, 4.2), (-12.0, 31.8, 10.5, 3.8), (-3.0, 26.6, 12.0, 4.5),
                          (10.0, 31.6, 11.5, 4.2), (49.0, 27.0, 15.0, 6.2), (53.5, 32.4, 15.0, 5.6),
                          (-39.5, 36.5, 10.0, 3.6), (41.5, 26.0, 15.0, 6.5), (56.0, 25.5, 14.0, 5.5), (12.0, 26.0, 12.0, 4.6)):
        P.tree_broad(x, y, NE.bank_z(x, y), h=h, crown=cr)
    for (x, y, h, cr) in ((-38.0, 41.0, 12.0, 4.5), (-10.0, 40.0, 13.0, 4.8), (-4.0, 52.0, 12.0, 4.5), (-37.0, 54.0, 13.0, 5.0),
                          (50.0, 40.0, 14.0, 5.0), (52.0, 56.0, 13.0, 4.6), (28.0, 60.0, 14.0, 5.0), (-40.0, 70.0, 12.0, 4.5),
                          (0.0, 72.0, 13.0, 5.0), (40.0, 72.0, 12.0, 4.4), (-12.0, 82.0, 14.0, 5.0)):
        P.tree_broad(x, y, Z_PARK, h=h, crown=cr, collide=False, g='Foliage.far')
    for (x, y, h) in ((-22.0, 46.0, 19.0), (-15.0, 50.0, 17.0), (35.0, 58.0, 21.0), (44.0, 63.0, 18.0)):
        P.tree_conifer(x, y, Z_PARK, h=h, rbase=h * 0.17, collide=False, g='Foliage.far')
    P.grass_tufts(-42, 57, yt + 0.2, 34.0, Z_PARK, 200)


# ------------------------------------------------------------------------------------------------
# SE: retaining wall, bank, pocket, plateau
# ------------------------------------------------------------------------------------------------

def retaining_wall():
    mb = G['Props.wall']
    pts = WALL_PATH
    for a, b in zip(pts, pts[1:]):
        top = Z_PLATEAU + 0.3
        mb.seg_box(a, b, 0.8, -0.3, top, M['oldstone'], ext=0.4)
        mb.seg_box(a, b, 0.9, top, top + 0.12, M['concrete'], ext=0.45)
        collider_seg('rwall', a, b, 0.8, -1.0, top + 0.12, ext=0.4)
        collider_seg('bound', a, b, 0.9, top, 30.0, ext=0.4, clip=True)
    # graffiti along the stretch facing the turn ("1950" and tags), continuous across the bend
    path = [(64.5, 8.0), (69.5, 1.5), (71.0, -6.0), (71.0, -30.0)]
    s = 0.0
    H = 2.9
    per = H * 4.0
    for a, b in zip(path, path[1:]):
        L = (Vector(b) - Vector(a)).length
        G['Props.graffiti'].wall_card(a, b, 0.15, 0.15 + H, M['graffiti'], uv=(s / per, 0, (s + L) / per, 1), off=0.415)
        s += L
    # grime at the foot
    for a, b in zip(pts[2:], pts[3:]):
        G['Props.graffiti'].wall_card(a, b, -0.05, 1.2, M['grime'], uv=(0, 0, 4, 1), off=0.42)
    # plateau behind the wall
    plateau = [(71.0, -112.0), (152.0, -112.0), (152.0, 88.0), (57.5, 88.0), (57.5, 45.0), (60.0, 23.5), (64.5, 8.0),
               (69.5, 1.5), (71.0, -6.0)]
    G['Ground.plateau'].poly_prism(plateau, -0.3, Z_PLATEAU, M['grass'], side=M['oldstone'])
    G['Ground.plateau'].quad(seg_quad((77.0, -112.0), (77.0, 88.0), 5.0, Z_PLATEAU + 0.01), M['asphalt'])
    # trees and shrubs over the wall (very visible from the street)
    y = -105.0
    while y < 85.0:
        x = 73.6 + rng.uniform(-0.6, 1.6) if y < 0 else 70.0 - (y / 22.0) * 2.5 + rng.uniform(0.4, 2.0)
        if y > 23.5:
            x = 60.5 + rng.uniform(0, 1.5)
        if rng.random() < 0.82:
            P.tree_broad(x, y, Z_PLATEAU, h=rng.uniform(10, 15), crown=rng.uniform(3.6, 5.2), collide=False, g='Foliage.far')
        else:
            P.tree_conifer(x, y, Z_PLATEAU, h=rng.uniform(13, 18), rbase=2.6, collide=False, g='Foliage.far')
        P.bush(x + rng.uniform(-1.5, 1.5), y + rng.uniform(2, 4), Z_PLATEAU, r=rng.uniform(0.9, 1.6), g='Foliage.far')
        y += rng.uniform(7.0, 10.0)
    for k in range(26):
        P.tree_broad(rng.uniform(84, 145), rng.uniform(-105, 85), Z_PLATEAU, h=rng.uniform(9, 14), crown=rng.uniform(3.5, 5),
                     collide=False, g='Foliage.far', cards=40)


def se_bank_and_pocket():
    zw = Z_WALK
    # bank: big trees, shrubs, rocks (some solid)
    for (x, y, h, cr) in ((58.6, 19.0, 15.0, 5.6), (60.6, 11.0, 13.0, 4.8), (63.6, 5.2, 12.0, 4.2)):
        P.tree_broad(x, y, 0.1, h=h, crown=cr)
    for (x, y, r) in ((57.6, 22.2, 1.2), (61.4, 16.0, 1.0), (59.0, 7.0, 0.9), (62.2, 8.8, 1.1), (66.2, 3.8, 1.0), (57.5, 14.0, 0.8)):
        P.bush(x, y, 0.1, r=r, h=r * 1.3)
    for (x, y, r, col) in ((58.0, 16.5, 1.1, True), (60.2, 21.0, 0.9, True), (63.0, 12.0, 0.8, False), (57.4, 9.6, 0.7, True),
                           (64.0, 6.6, 0.9, True), (61.6, 4.6, 0.5, False), (59.6, 13.2, 0.6, False)):
        P.rock(x, y, 0.1, r=r, squash=0.75, collide=col)
    P.grass_tufts(56.5, 63.0, 4.5, 23.0, 0.1, 70)
    # low stone wall between the pocket and the plane-tree strip (rounded N end, two gaps)
    m = M['oldstone']
    arc = [(60.45 - 2.2 + 2.2 * math.cos(math.radians(a)), -6.4 + 2.2 * math.sin(math.radians(a))) for a in range(150, -1, -30)]
    path = arc + [(60.45, -19.0)]
    segs = [path, [(60.45, -21.2), (60.45, -33.0)], [(60.45, -35.2), (60.45, -46.5)]]
    for pts in segs:
        for a, b in zip(pts, pts[1:]):
            G['Props.site'].seg_box(a, b, 0.5, zw - 0.1, zw + 0.88, m, ext=0.12)
            G['Props.site'].seg_box(a, b, 0.58, zw + 0.88, zw + 0.96, M['concrete'], ext=0.14)
            collider_seg('lowwall', a, b, 0.55, -1.0, zw + 0.96, ext=0.12)
    # plane trees on the strip
    for y in (-10.5, -18.0, -26.5, -34.0, -42.0, -52.0, -62.0):
        P.tree_broad(61.75, y, zw, h=rng.uniform(12.5, 14.5), crown=rng.uniform(4.2, 5.0), leaf=M['leaf_plane'], trunk_h=4.6,
                     collide=y > -47)
    P.grass_tufts(60.8, 62.6, -46, -7, zw, 50)
    # garage block closing the pocket to the south
    gs = B.Style(cols=1, door=M['shutter_gray'], frame=M['frame_dark'], depth=0.15)
    B.box_building(B.rect(46.8, 60.3, -60.0, -47.0), zw, zw + 3.6, M['st_cream'],
                   faces={2: [B.Op(1.0 + k * 3.2, 3.6 + k * 3.2, 0.0, 2.4, gs) for k in range(4)]},
                   base=(0.4, M['concrete_dark']), roof_kw=dict(parapet=0.3, cap=M['concrete']))


# ------------------------------------------------------------------------------------------------
# far terrain
# ------------------------------------------------------------------------------------------------
CORE = (-165.0, 152.0, -112.0, 88.0)


def _noise(x, y):
    return (math.sin(x * 0.011 + 1.3) * math.cos(y * 0.013 - 0.7) + 0.5 * math.sin(x * 0.027 + y * 0.019 + 2.1) +
            0.25 * math.sin(x * 0.061 - y * 0.053))


def terrain():
    mb = G['Backdrop.terrain']
    x0, x1, y0, y1 = CORE
    step = 20.0
    ext = 640.0
    nx = int((x1 - x0 + 2 * ext) / step)
    ny = int((y1 - y0 + 2 * ext) / step)
    gx0, gy0 = x0 - ext, y0 - ext

    def lvl(x, y):
        if x > 70:
            return Z_PLATEAU
        if y > 30 and -45 < x < 58:
            return Z_PARK
        return 0.0

    H = {}
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = gx0 + i * step, gy0 + j * step
            dx = max(x0 - x, 0.0, x - x1)
            dy = max(y0 - y, 0.0, y - y1)
            d = math.hypot(dx, dy)
            cx, cy = min(max(x, x0), x1), min(max(y, y0), y1)
            base = lvl(cx, cy)
            # keep the street (NW) and the lower road (S) running on into the distance
            corr = 1.0
            if x < x0:
                corr = min(1.0, max(0.0, (abs(y) - 12.0) / 50.0))
            elif y < y0 and x < 100:
                corr = min(1.0, max(0.0, (abs(x - 66.4) - 10.0) / 50.0))
            if d <= 0:
                H[i, j] = base - 0.6
            elif corr <= 0.0:
                H[i, j] = base - 0.08
            else:
                ang = math.atan2(y, x)
                dirf = 1.0 + 0.7 * max(0.0, math.sin(ang)) + 0.3 * max(0.0, math.cos(ang))
                rise = 52.0 * (1 - math.exp(-d / 170.0)) * dirf
                H[i, j] = base - 0.08 + corr * (rise * (0.75 + 0.25 * _noise(x, y)) + 3.0 * _noise(x * 3, y * 3) * min(1.0, d / 60))
    for j in range(ny):
        for i in range(nx):
            xa, ya = gx0 + i * step, gy0 + j * step
            if xa >= x0 and xa + step <= x1 and ya >= y0 and ya + step <= y1:
                continue
            q = [(xa, ya, H[i, j]), (xa + step, ya, H[i + 1, j]), (xa + step, ya + step, H[i + 1, j + 1]), (xa, ya + step, H[i, j + 1])]
            mb.quad(q, M['grass_far'], smooth=True)
    # the two roads continue out of the core
    road = G['Ground.road']
    road.quad([(x0 - ext, -3.5, 0.0), (x0, -3.5, 0.0), (x0, 3.5, 0.0), (x0 - ext, 3.5, 0.0)], M['asphalt'])
    road.quad([(62.9, y0 - ext, 0.0), (69.9, y0 - ext, 0.0), (69.9, y0, 0.0), (62.9, y0, 0.0)], M['asphalt'])
    dashes(G['Ground.paint'], [(x0 - ext, 0.0), (x0, 0.0)], 3.0, 3.0, 0.12, 0.006, M['paint'])
    # forest: blob trees over the hills (cheap), some on the ridge lines
    fm = G['Backdrop.forest']
    hm = M['hedge']

    def h_at(x, y):
        i = min(nx - 1, max(0, int((x - gx0) / step)))
        j = min(ny - 1, max(0, int((y - gy0) / step)))
        fx, fy = (x - gx0) / step - i, (y - gy0) / step - j
        return (H[i, j] * (1 - fx) * (1 - fy) + H[i + 1, j] * fx * (1 - fy) + H[i, j + 1] * (1 - fx) * fy + H[i + 1, j + 1] * fx * fy)
    n = 0
    tries = 0
    while n < 900 and tries < 20000:
        tries += 1
        x = rng.uniform(x0 - 420, x1 + 420)
        y = rng.uniform(y0 - 420, y1 + 420)
        if x0 - 8 < x < x1 + 8 and y0 - 8 < y < y1 + 8:
            continue
        if (x < x0 and abs(y) < 14) or (y < y0 and abs(x - 66.4) < 14):
            continue
        if _noise(x * 1.7, y * 1.7) < -0.2:
            continue
        z = h_at(x, y)
        r = rng.uniform(3.5, 7.0)
        fm.blob((x, y, z + r * 0.9), r, hm, scale=(1.0, 1.0, rng.uniform(0.8, 1.2)), jitter=0.18, sub=1, smooth=True)
        n += 1


# ------------------------------------------------------------------------------------------------
# gameplay: clips, spawns, bounds
# ------------------------------------------------------------------------------------------------
BOUNDS = ((-80.0, -49.0, -1.0), (73.0, 37.0, 20.0))


def gameplay():
    collider_mm('ground', -170, 155, -115, 90, -1.0, 0.0)
    # playable-area boundary (players only; bullets pass)
    collider_mm('bound', -78.0, -77.4, -12.0, 18.6, -1, 30, clip=True)          # NW across the street + plaza
    collider_mm('bound', -69.0, -60.8, -11.2, -10.6, -1, 30, clip=True)         # side street mouth
    collider_mm('bound', -43.6, 20.6, 34.4, 35.0, -1, 30, clip=True)            # NE park edge (FINA closes the gap)
    collider_mm('bound', 34.8, 62.0, 34.4, 35.0, -1, 30, clip=True)
    collider_mm('bound', 46.8, 72.0, -47.4, -46.8, -1, 30, clip=True)           # S end of the pocket / lower road
    collider_mm('bound', -80.0, 73.0, -49.0, 37.0, 30.0, 31.0, clip=True)        # ceiling
    # spawns: allies in the SE pocket, axis in the NW courtyard / plaza
    allies = [(55.6, -9.5), (54.0, -14.5), (56.4, -19.0), (54.2, -24.0), (56.6, -28.5), (54.4, -33.5), (56.6, -38.0),
              (54.4, -42.5)]
    axis = [(-69.0, 31.2), (-71.6, 27.5), (-66.4, 27.0), (-69.2, 23.2), (-72.2, 19.6), (-66.0, 20.2), (-71.0, 15.6),
            (-74.4, 11.2)]
    for i, (x, y) in enumerate(allies):
        marker(f'SPAWN_allies_{i + 1:02d}', (x, y, Z_WALK + 0.05))
    for i, (x, y) in enumerate(axis):
        marker(f'SPAWN_axis_{i + 1:02d}', (x, y, Z_WALK + 0.05))
    marker('BOUNDS_MIN', BOUNDS[0])
    marker('BOUNDS_MAX', BOUNDS[1])


def build():
    ground()
    kerbs()
    lot_and_cars()
    street_furniture()
    plaza()
    embankment_and_park()
    retaining_wall()
    se_bank_and_pocket()
    terrain()
    gameplay()
