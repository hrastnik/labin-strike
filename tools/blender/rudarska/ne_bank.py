"""NE edge of the lot (y = 23.5), modelled on the Street View shots along it, NW -> SE:

  x -43 .. -38.4   driveway climbing NE along the sports hall; concrete retaining wall with a mesh fence on its right
  x -38.4 .. -34   grass terrace rising behind a low concrete front wall (info board, signs, big shrub, bamboo),
                   closed towards the lot by a rubble-masonry side wall
  x -34 .. -11     cracked, rain-stained concrete retaining wall (~1.4 m)
  x -11 .. -2.8    blocky limestone outcrop
  x -2.6 .. 9.6    double-branch stair: rubble masonry, concrete treads and coping, dark steel handrails
  x 9.8 .. 59.5    low dry-stone wall with capstones; utility cabinet, tall bamboo thicket, shrubs

Behind the walls a grass bank climbs to the park level at y = Y_TOP.  All shrubs, bamboo and hedges here are solid
(COL_) so bullets and bot sight stop where the player's view does."""
import math

import bmesh
from mathutils import Vector

from . import props as P
from .lib import G, collider, collider_mm, collider_ramp, collider_seg, rng
from .palette import M

Z_WALK = 0.12
Z_PARK = 2.8
Y_LOT = 23.5           # lot edge = front face of the walls
Y_BACK = 23.85         # back face of the walls, foot of the bank
Y_TOP = 27.3           # bank meets the park level
DRIVE = (-43.0, -38.4)  # driveway x range
DRIVE_TOP = 31.0       # driveway reaches Z_PARK here
NW_X = -34.0           # masonry side wall closing the NW terrace towards the lot
NW_FRONT = 18.8        # back face of the terrace's front wall

# top of the lot-edge wall along x (piecewise linear)
WT = [(-38.4, 1.5), (-34.0, 1.5), (-12.0, 1.5), (-11.0, 1.9), (-8.6, 2.45), (-5.4, 2.35), (-3.0, 1.95), (-2.6, 1.0), (1.5, 1.55), (5.5, 1.55),
      (9.6, 1.0), (10.0, 0.72), (61.0, 0.72)]
BANK_X = [(-34.0, 2.0), (5.0, 59.7)]   # the central stair flight (x 2..5) cuts through the bank


def wall_top(x):
    if x <= WT[0][0]:
        return WT[0][1]
    for (xa, za), (xb, zb) in zip(WT, WT[1:]):
        if x <= xb:
            return za + (zb - za) * (x - xa) / (xb - xa)
    return WT[-1][1]


def wall_x(y):
    """inner face line of the SE retaining wall (WALL_PATH (60, 23.5) -> (57.5, 45))"""
    return 60.0 - (y - 23.5) * 2.5 / 21.5


def nw_z(y):
    return 1.4 + (Z_PARK - 1.4) * min(1.0, max(0.0, (y - NW_FRONT) / (Y_TOP - NW_FRONT)))


def drive_z(y):
    return Z_WALK + (Z_PARK - Z_WALK) * min(1.0, max(0.0, (y - 18.5) / (DRIVE_TOP - 18.5)))


def _n(x, y):
    return (0.5 * math.sin(x * 1.31 + y * 0.7) * math.cos(y * 1.9 - x * 0.4) + 0.3 * math.sin(x * 3.1 - y * 2.3 + 1.7) +
            0.2 * math.sin(x * 0.47 + 2.0))


def bank_z(x, y):
    """ground height on the NE bank / terrace (Z_PARK beyond it)."""
    if y >= Y_TOP:
        return Z_PARK
    if x < NW_X - 0.15:
        t = (y - NW_FRONT) / (Y_TOP - NW_FRONT)
        return nw_z(y) + 0.05 * _n(x, y) * min(1.0, max(0.0, min(t, 1 - t) * 6))
    if y <= Y_BACK:
        return wall_top(x)
    t = (y - Y_BACK) / (Y_TOP - Y_BACK)
    z0 = wall_top(x)
    return z0 + (Z_PARK - z0) * t + 0.06 * _n(x, y) * min(1.0, min(t, 1 - t) * 5)


# ------------------------------------------------------------------------------------------------
# geometry helpers
# ------------------------------------------------------------------------------------------------

def _prism(mb, prof, axis, s0, s1, m, cap=None):
    """extrude a closed profile [(u, z)] along `axis` ('x': u = y, 'y': u = x) from s0 to s1.  Faces pointing up
    (coping, treads) get `cap`."""
    a = sum(prof[i][0] * prof[(i + 1) % len(prof)][1] - prof[(i + 1) % len(prof)][0] * prof[i][1] for i in range(len(prof)))
    if a < 0:
        prof = list(reversed(prof))
    bm = mb.bm
    if axis == 'x':
        A = [bm.verts.new((s0, u, z)) for u, z in prof]
        B = [bm.verts.new((s1, u, z)) for u, z in prof]
    else:
        A = [bm.verts.new((u, s0, z)) for u, z in prof]
        B = [bm.verts.new((u, s1, z)) for u, z in prof]
    n = len(prof)
    faces = [bm.faces.new((A[i], A[(i + 1) % n], B[(i + 1) % n], B[i])) for i in range(n)]
    faces += [bm.faces.new(B), bm.faces.new(list(reversed(A)))]
    if axis == 'y':   # (x, z) -> extrude along +y is a mirrored frame: flip everything outwards
        bmesh.ops.reverse_faces(bm, faces=faces)
    mb._tag(faces, m)
    if cap is not None:
        for f in faces[:n]:
            f.normal_update()
            if f.normal.z > 0.5:
                f.material_index = mb.mi(cap)
    return faces


def heightgrid(mb, xs, ys, f, m, xmax=None):
    bm = mb.bm
    V = {}
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            xx = min(x, xmax(y)) if xmax else x
            V[i, j] = bm.verts.new((xx, y, f(xx, y)))
    faces = [bm.faces.new((V[i, j], V[i + 1, j], V[i + 1, j + 1], V[i, j + 1]))
             for j in range(len(ys) - 1) for i in range(len(xs) - 1)]
    mb._tag(faces, m, smooth=True)


def lin(a, b, step):
    n = max(1, int(math.ceil((b - a) / step)))
    return [a + (b - a) * k / n for k in range(n + 1)]


def _breaks(x0, x1):
    return [x0] + [x for x, _ in WT if x0 < x < x1] + [x1]


def edge_wall(mb, x0, x1, y0, y1, m, cap=None, dz=0.0, zb=-0.1):
    """lot-edge wall from x0 to x1 whose top follows wall_top()."""
    top = [(x, wall_top(x) + dz) for x in _breaks(x0, x1)]
    _prism(mb, [(x0, zb), (x1, zb)] + list(reversed(top)), 'y', y0, y1, m, cap)


def edge_collider(x0, x1, y0, y1, dz=0.0):
    yc, w = (y0 + y1) / 2, y1 - y0
    bx = _breaks(x0, x1)
    for xa, xb in zip(bx, bx[1:]):
        za, zb = wall_top(xa) + dz, wall_top(xb) + dz
        if abs(za - zb) < 0.01:
            collider_mm('nebank', xa, xb, y0, y1, -1.0, za)
        else:
            collider_ramp('nebank', (xa, yc), (xb, yc), w, za, zb, thick=3.0)


def stain_strip(mb, pts, m, per=4.0, off=0.012):
    """alpha-blended weathering decal over a wall face: pts = [(x, y, z_bottom, z_top)] along the face, the
    visible side to the right of the polyline (same convention as wall_card)."""
    s = 0.0
    for a, b in zip(pts, pts[1:]):
        d = Vector((b[0] - a[0], b[1] - a[1], 0))
        L = d.length
        d.normalize()
        n = Vector((d.y, -d.x, 0)) * off
        u0, u1 = s / per, (s + L) / per
        mb.quad([(a[0] + n.x, a[1] + n.y, a[2]), (b[0] + n.x, b[1] + n.y, b[2]), (b[0] + n.x, b[1] + n.y, b[3]),
                 (a[0] + n.x, a[1] + n.y, a[3])], m, [(u0, 0), (u1, 0), (u1, 1), (u0, 1)])
        s += L


def cracks(mb, x0, x1, y, ztop, n):
    """hairline cracks and spalls running down from the top of a wall facing -Y."""
    for k in range(n):
        x = rng.uniform(x0, x1)
        z = ztop(x) - 0.01
        pts = [(x, z)]
        w = rng.uniform(0.004, 0.008)
        for s in range(rng.randint(4, 9)):
            x += rng.uniform(-0.14, 0.14)
            z -= rng.uniform(0.07, 0.22)
            if z < 0.2:
                break
            pts.append((x, z))
            if rng.random() < 0.25:   # short side branch
                bx, bz = x + rng.uniform(-0.3, 0.3), z - rng.uniform(0.1, 0.3)
                _crack_seg(mb, (x, z), (bx, bz), y, w * 0.6)
        for a, b in zip(pts, pts[1:]):
            _crack_seg(mb, a, b, y, w)
            w *= 0.88


def _crack_seg(mb, a, b, y, w):
    mb.quad([(b[0] - w, y, b[1]), (b[0] + w, y, b[1]), (a[0] + w, y, a[1]), (a[0] - w, y, a[1])], M['wall_crack'])


def shrub_mass(x0, x1, hmin, hmax, y1=Y_TOP - 0.6, step=1.25, leaves=None):
    """overgrown strip along the top of the bank: a lumpy, continuous mass of overlapping shrubs of mixed
    species, a low front row right behind the wall edge and taller ones behind it (each one solid)."""
    leaves = leaves or [M['leaf_shrub'], M['leaf_shrub'], M['leaf_hedge'], M['leaf_ivy']]
    x = x0 + rng.uniform(0.2, 0.6)
    while x < x1 - 0.3:
        r = rng.uniform(0.75, 1.0)
        yf = Y_BACK + 0.45 + rng.uniform(0.0, 0.25)
        P.bush(x, yf, bank_z(x, yf) - 0.1, r=r, h=rng.uniform(0.85, 1.35) * max(hmin, 1.0), leaf=rng.choice(leaves))
        xb = x + rng.uniform(-0.4, 0.4)
        yb = rng.uniform(Y_BACK + 1.2, y1)
        rb = rng.uniform(1.0, 1.6)
        P.bush(xb, yb, bank_z(xb, yb) - 0.15, r=rb, h=rng.uniform(hmin, hmax), leaf=rng.choice(leaves))
        x += step * rng.uniform(0.75, 1.15)


# ------------------------------------------------------------------------------------------------
# pieces
# ------------------------------------------------------------------------------------------------

def bank():
    """grass bank behind the walls + the NW terrace, with ramp colliders that follow it."""
    mb = G['Ground.bank']
    ys = lin(Y_BACK, Y_TOP, 0.6)
    for x0, x1 in BANK_X:
        heightgrid(mb, lin(x0, x1, 0.8), ys, bank_z, M['grass'], xmax=(lambda y: wall_x(y) - 0.3) if x1 > 50 else None)
    heightgrid(mb, lin(-38.0, NW_X - 0.3, 0.8), lin(NW_FRONT, Y_TOP, 0.6), bank_z, M['grass'])
    # colliders: one inclined slab per stretch of constant wall height, ~0.8 m slices where it changes
    for x0, x1 in BANK_X:
        bx = _breaks(x0, x1)
        for xa, xb in zip(bx, bx[1:]):
            if abs(wall_top(xa) - wall_top(xb)) < 0.01:
                cuts = [xa, xb]
            else:
                cuts = lin(xa, xb, 0.8)
            for ca, cb in zip(cuts, cuts[1:]):
                xm = (ca + cb) / 2
                collider_ramp('bank', (xm, Y_BACK), (xm, Y_TOP), cb - ca, wall_top(xm), Z_PARK, thick=3.0)
    collider_ramp('bank', ((DRIVE[1] + NW_X) / 2, 18.5), ((DRIVE[1] + NW_X) / 2, Y_TOP), NW_X - DRIVE[1], nw_z(18.5), Z_PARK, thick=3.0)
    # tufts over the whole bank, a fringe overhanging the wall tops
    for x0, x1 in BANK_X + [(-38.0, NW_X - 0.3)]:
        P.grass_tufts(x0, x1 - 0.3, Y_BACK + 0.1, Y_TOP, bank_z, int((x1 - x0) * 2.6))
    P.grass_tufts(-38.0, NW_X - 0.4, NW_FRONT + 0.2, Y_BACK, bank_z, 50)
    for x0, x1 in BANK_X:
        P.grass_tufts(x0 + 0.2, x1 - 0.2, Y_BACK - 0.02, Y_BACK + 0.25, bank_z, int((x1 - x0) * 1.6))


def driveway():
    """concrete driveway between the sports hall and the terrace, its retaining wall, mesh fence and the signs
    at its mouth."""
    x0, x1 = DRIVE
    gd = G['Ground.drive']
    gd.quad([(x0, 18.5, Z_WALK), (x1, 18.5, Z_WALK), (x1, DRIVE_TOP, Z_PARK), (x0, DRIVE_TOP, Z_PARK)], M['concrete'])
    gd.quad([(x0, DRIVE_TOP, Z_PARK), (x1, DRIVE_TOP, Z_PARK), (x1, 34.4, Z_PARK), (x0, 34.4, Z_PARK)], M['concrete'])
    collider_ramp('drive', ((x0 + x1) / 2, 18.5), ((x0 + x1) / 2, DRIVE_TOP), x1 - x0, Z_WALK, Z_PARK, thick=3.0)
    # trench drain across the mouth, two gullies further up
    slope = Vector((0, DRIVE_TOP - 18.5, Z_PARK - Z_WALK)).normalized()
    dec = G['Ground.decals']
    for k in range(8):
        x = x0 + 0.3 + 0.55 * (k + 0.5)
        dec.card((x, 18.78, drive_z(18.78) + 0.008), (1, 0, 0), slope, 0.55, 0.3, M['grate'])
    for y in (22.4, 27.6):
        dec.card((x0 + 1.1, y, drive_z(y) + 0.008), (1, 0, 0), slope, 0.5, 0.5, M['grate'])
    # retaining wall on the right of the driveway (its top follows the terrace), low front wall towards the lot
    wm = G['Props.nebank']
    xw0, xw1 = x1, x1 + 0.4
    prof = [(18.5, -0.3), (34.4, -0.3), (34.4, Z_PARK + 0.12), (Y_TOP, Z_PARK + 0.12), (NW_FRONT, nw_z(NW_FRONT) + 0.12),
            (18.5, nw_z(NW_FRONT) + 0.12)]
    _prism(wm, prof, 'x', xw0, xw1, M['retwall'], cap=M['concrete'])
    zf = nw_z(NW_FRONT) + 0.12
    wm.box_mm(xw1, NW_X - 0.3, 18.5, NW_FRONT, -0.1, zf, M['retwall'], mats={'top': M['concrete']})
    collider_mm('nebank', xw0, xw1, 18.5, NW_FRONT, -1.0, zf)
    collider_ramp('nebank', ((xw0 + xw1) / 2, NW_FRONT), ((xw0 + xw1) / 2, Y_TOP), 0.4, zf, Z_PARK + 0.12, thick=3.0)
    collider_mm('nebank', xw0, xw1, Y_TOP, 34.4, -1.0, Z_PARK + 0.12)
    collider_mm('nebank', xw1, NW_X, 18.5, NW_FRONT, -1.0, zf)
    # weathering: driveway face (sloping top) and the front wall
    sd = G['Props.nestains']
    ys = [18.5, NW_FRONT, 21.0, 23.5, 25.5, Y_TOP, 29.0, 30.6]
    stain_strip(sd, [(x1, y, drive_z(y), nw_z(y) + 0.1) for y in reversed(ys)], M['wall_stains'], per=4.5)
    stain_strip(sd, [(xw0, 18.5, Z_WALK, zf - 0.02), (NW_X - 0.3, 18.5, Z_WALK, zf - 0.02)], M['wall_stains'], per=4.5)
    cracks(sd, xw1 + 0.2, NW_X - 0.6, 18.5 - 0.004, lambda x: zf, 4)
    # welded-mesh fence on the wall tops (up the driveway, and along the front); ends before the top so the
    # driveway still leads into the park
    fx = (xw0 + xw1) / 2
    run = [(NW_X - 0.45, 18.62), (fx, 18.62)] + [(fx, y) for y in (21.0, 23.5, 25.4, Y_TOP, 28.9, 30.4)]
    fence(run, lambda x, y: (zf if y < NW_FRONT else nw_z(y) + 0.12) if y < Y_TOP else Z_PARK + 0.12)
    # info board in front of the shrubs, no-stopping sign and the red fire-access plate at the corner
    s = G['Props.signs']
    bx, by = -36.1, 18.28
    for px in (bx - 0.9, bx + 0.9):
        s.pole((px, by + 0.03), Z_WALK, Z_WALK + 2.05, 0.035, M['metal'], seg=8)
    s.card((bx, by - 0.03, Z_WALK + 1.42), (1, 0, 0), (0, 0, 1), 1.95, 1.2, M['sign_board'])
    s.box((bx, by + 0.0, Z_WALK + 1.42), (2.0, 0.02, 1.25), M['sign_back'])
    collider('sign', (bx, by, Z_WALK + 1.42), (2.0, 0.1, 1.25))
    P.sign_post(-38.75, 18.32, Z_WALK, -math.pi / 2, [(M['sign_nostop'], 0.6, 0.6, 2.25)])
    s.card((-37.75, 18.57, zf + 0.42), (1, 0, 0), (0, 0, 1), 0.56, 0.28, M['sign_fire'])
    s.box((-37.75, 18.59, zf + 0.42), (0.6, 0.02, 0.32), M['sign_back'])


def fence(pts, ztop, h=1.2, post=2.5):
    """welded-mesh panel fence along pts standing on ztop(x, y): green posts, alpha-cut mesh panels (1 m texture
    repeat), CLIP collider (stops players, not bullets)."""
    mb = G['Props.fence']
    s = 0.0
    for a, b in zip(pts, pts[1:]):
        A, B = Vector(a), Vector(b)
        L = (B - A).length
        n = max(1, int(math.ceil(L / post)))
        for k in range(n):
            p, q = A + (B - A) * (k / n), A + (B - A) * ((k + 1) / n)
            zp, zq = ztop(p.x, p.y) + 0.02, ztop(q.x, q.y) + 0.02
            ll = (q - p).length
            mb.quad([(p.x, p.y, zp), (q.x, q.y, zq), (q.x, q.y, zq + h), (p.x, p.y, zp + h)], M['fence_mesh'],
                    [(s, 0), (s + ll, 0), (s + ll, h), (s, h)])
            s += ll
            mb.box((p.x, p.y, zp + h / 2), (0.06, 0.06, h + 0.06), M['fence_green'])
            collider_seg('fence', p, q, 0.12, min(zp, zq) - 0.1, max(zp, zq) + h + 0.1, clip=True)
    zb = ztop(B.x, B.y) + 0.02
    mb.box((B.x, B.y, zb + h / 2), (0.06, 0.06, h + 0.06), M['fence_green'])


def nw_terrace():
    """masonry side wall towards the lot and the planting on the terrace (shrub mass, bamboo, trimmed bushes)."""
    wm = G['Props.nebank']
    prof = [(18.5, -0.1), (Y_TOP, -0.1), (Y_TOP, Z_PARK + 0.15), (Y_BACK, nw_z(Y_BACK) + 0.15), (18.5, nw_z(18.5) + 0.2)]
    _prism(wm, prof, 'x', NW_X - 0.3, NW_X, M['oldstone'], cap=M['concrete'])
    collider_ramp('nebank', (NW_X - 0.15, 18.5), (NW_X - 0.15, Y_TOP), 0.3, nw_z(18.5) + 0.2, Z_PARK + 0.15, thick=4.0)
    P.ivy_wall((NW_X, 18.6), (NW_X, 23.4), 0.3, lambda t: nw_z(18.5 + t * 4.9) - 0.1, 26)
    sh = M['leaf_shrub']
    P.bush(-36.6, 20.3, nw_z(20.3) - 0.15, r=1.9, h=3.1, leaf=sh)
    P.bush(-37.5, 21.9, nw_z(21.9) - 0.15, r=1.3, h=2.4, leaf=M['leaf_hedge'])
    P.bamboo(NW_X - 1.55, NW_X - 0.45, 19.3, 23.2, bank_z, h=5.2, density=6.0)
    P.bush(-35.4, 25.2, nw_z(25.2) - 0.1, r=1.3, h=1.9, leaf=sh)
    for y in (23.0, 25.7):
        P.bush(-37.3, y, nw_z(y) - 0.1, r=0.95, h=1.25)   # trimmed balls along the fence


def concrete_wall():
    """x -34..-11: the cracked, stained concrete retaining wall."""
    wm = G['Props.nebank']
    x0, x1 = NW_X, -11.0
    edge_wall(wm, x0, x1, Y_LOT, Y_BACK, M['retwall'])
    edge_collider(x0, x1, Y_LOT, Y_BACK)
    sd = G['Props.nestains']
    xs = lin(x0, -12.0, 3.0) + [-11.6]
    stain_strip(sd, [(x, Y_LOT, Z_WALK - 0.02, wall_top(x) - 0.02) for x in xs], M['wall_stains'])
    cracks(sd, x0 + 0.5, -12.0, Y_LOT - 0.004, wall_top, 12)
    # expansion joints, a couple of repair patches
    for k in range(1, 5):
        x = x0 + k * 5.4 + rng.uniform(-0.3, 0.3)
        sd.quad([(x - 0.012, Y_LOT - 0.004, Z_WALK), (x + 0.012, Y_LOT - 0.004, Z_WALK), (x + 0.012, Y_LOT - 0.004, wall_top(x)),
                 (x - 0.012, Y_LOT - 0.004, wall_top(x))], M['wall_crack'])
    for (x, z, w, h) in ((-29.4, 0.75, 1.3, 0.42), (-21.0, 1.05, 0.8, 0.3), (-15.2, 0.5, 1.6, 0.36)):
        wm.box((x, Y_LOT - 0.012, z), (w, 0.024, h), M['concrete_gray'])
    # planting on the bank above: bamboo spilling at the W end, then big deciduous shrubs with a grassy gap
    sh = M['leaf_shrub']
    P.bamboo(NW_X + 0.2, -31.0, 24.1, 25.9, bank_z, h=6.0)
    shrub_mass(-31.0, -26.2, 1.8, 3.0)
    P.bush(-23.6, 26.3, bank_z(-23.6, 26.3) - 0.1, r=0.8, h=1.0, leaf=sh)    # the grassy gap
    shrub_mass(-21.6, -11.0, 2.0, 3.2)
    P.drape((-30.6, Y_LOT), (-27.0, Y_LOT), 1.5, 14, drop=(0.3, 0.8))
    P.drape((-18.8, Y_LOT), (-15.6, Y_LOT), 1.5, 10, drop=(0.3, 0.7))
    P.drape((-13.6, Y_LOT), (-11.4, Y_LOT), 1.5, 10, drop=(0.4, 0.9))


def outcrop():
    """x -11..-2.8: pale, fissured limestone in big bedded blocks standing proud of the bank by different amounts,
    dark soil showing in the joints; creeper hanging over the top, a shrub mass above."""
    wm = G['Props.nebank']
    edge_wall(wm, -11.0, -2.6, 23.75, Y_BACK, M['wall_crack'])
    edge_collider(-11.0, -2.6, Y_LOT, Y_BACK)
    m = M['drystone']
    x = -11.5
    while x < -3.0:
        L = min(rng.uniform(0.7, 1.6), -2.7 - x)
        if L < 0.4:
            break
        cx = x + L / 2
        top = wall_top(min(cx, -3.0)) + rng.uniform(-0.02, 0.16)
        proud = rng.uniform(-0.04, 0.2)
        d = rng.uniform(0.75, 1.1)
        cy = Y_LOT + d / 2 - proud
        rz = rng.uniform(-0.08, 0.08)
        if rng.random() < 0.35:   # one tall slab
            P.rock_block(cx, cy, Z_WALK - 0.15, L, d, top - Z_WALK + 0.15, rz=rz, m=m, jit=0.13)
        else:                     # a lower block with a smaller one set back on it
            h1 = (top - Z_WALK) * rng.uniform(0.45, 0.7)
            P.rock_block(cx, cy, Z_WALK - 0.15, L, d, h1 + 0.15, rz=rz, m=m, jit=0.13)
            L2 = L * rng.uniform(0.6, 1.0)
            back = rng.uniform(0.08, 0.3)
            P.rock_block(cx + rng.uniform(-0.2, 0.2), cy + back, Z_WALK + h1 - 0.06, L2, d - back * 0.5, top - Z_WALK - h1 + 0.06,
                         rz=rng.uniform(-0.12, 0.12), m=m, jit=0.15)
        x += L + rng.uniform(0.03, 0.14)
    # creeper hanging over the edge, shrubs above, weeds at the foot
    P.drape((-10.9, Y_LOT - 0.15), (-3.3, Y_LOT - 0.15), lambda t: wall_top(-10.9 + 7.6 * t), 60, drop=(0.5, 1.5), off=0.0)
    shrub_mass(-11.0, -3.4, 1.8, 3.0, step=1.4)
    P.grass_tufts(-10.8, -3.2, Y_LOT - 0.35, Y_LOT - 0.05, lambda x, y: Z_WALK - 0.03, 22)


def stairs():
    """double-branch stair: side flights up to a landing at 1.4 m, central flight up to the park.  Rubble masonry
    with concrete treads/risers and coping, sloping parapets on the lot side, steel handrails."""
    st = G['Props.stairs']
    stone, conc = M['oldstone'], M['concrete']
    zw, zl = Z_WALK, 1.4
    rise = (zl - zw) / 8
    # landing + its front parapet
    st.box_mm(1.5, 5.5, 21.8, 25.0, -0.1, zl, stone, mats={'top': conc})
    collider_mm('stairs', 1.5, 5.5, 21.8, 25.0, -1, zl)
    st.box_mm(1.5, 5.5, 21.78, 22.05, zl - 0.05, zl + 0.5, stone)
    st.box_mm(1.46, 5.54, 21.74, 22.09, zl + 0.5, zl + 0.58, conc)
    collider_mm('stairwall', 1.46, 5.54, 21.74, 22.09, -1, zl + 0.58)
    # side flights
    for p0x, dx in ((-2.5, 1), (9.5, -1)):
        yaw = 0.0 if dx > 0 else math.pi
        for i in range(8):
            ztop = zw + rise * (i + 1)
            cx = p0x + dx * (0.5 * i + 0.25)
            st.box((cx, 22.6, (ztop - 0.1) / 2), (0.5, 1.6, ztop + 0.1), stone, rz=yaw, mats={'top': conc, 'nx': conc})
            collider('stairs', (cx, 22.6, (ztop - 1.0) / 2), (0.5, 1.6, ztop + 1.0))
        xe = p0x + dx * 4.0
        lo, hi = (p0x, xe) if dx > 0 else (xe, p0x)
        zlo, zhi = (zw, zl) if dx > 0 else (zl, zw)
        # sloping parapet on the lot side (its top 0.5 m over the nosings) with a concrete coping
        _prism(st, [(lo, -0.1), (hi, -0.1), (hi, zhi + 0.5), (lo, zlo + 0.5)], 'y', 21.78, 22.05, stone)
        _prism(st, [(lo - 0.04, zlo + 0.5), (hi + 0.04, zhi + 0.5), (hi + 0.04, zhi + 0.58), (lo - 0.04, zlo + 0.58)],
               'y', 21.74, 22.09, conc)
        collider_ramp('stairwall', (p0x, 21.92), (xe, 21.92), 0.35, zw + 0.58, zl + 0.58, thick=2.0)
        # handrail along the back wall
        P.railing([(p0x + dx * 0.1, 23.28, zw + rise), (xe, 23.28, zl)], 0, h=0.9, rails=1, m=M['metal_dark'], posts=1.4)
    # walls behind the side flights (the bank retaining wall), coping on top
    for x0, x1 in ((-2.6, 2.0), (5.0, 9.8)):
        edge_wall(st, x0, x1, 23.4, Y_BACK, stone, cap=conc)
        edge_collider(x0, x1, 23.4, Y_BACK)
    # central flight between masonry cheek walls whose coping climbs with it
    run = 4.0 / 9
    crise = (Z_PARK - zl) / 9
    for i in range(9):
        ztop = zl + crise * (i + 1)
        cy = 25.0 + run * (i + 0.5)
        st.box((3.5, cy, (ztop + 1.3) / 2), (2.4, run, ztop - 1.3), stone, mats={'top': conc, 'ny': conc})
        collider('stairs', (3.5, cy, (ztop - 1.0) / 2), (2.4, run, ztop + 1.0))
    cheek = [(23.5, 1.0), (29.0, 1.0), (29.0, Z_PARK + 0.45), (Y_TOP, Z_PARK + 0.35), (25.0, zl + 0.9), (23.5, zl + 0.6)]
    for x0, x1 in ((2.0, 2.3), (4.7, 5.0)):
        _prism(st, cheek, 'x', x0, x1, stone, cap=conc)
        collider_mm('stairwall', x0, x1, 23.5, 25.0, -1, zl + 0.75)
        collider_ramp('stairwall', ((x0 + x1) / 2, 25.0), ((x0 + x1) / 2, Y_TOP), 0.3, zl + 0.9, Z_PARK + 0.35, thick=3.0)
        collider_mm('stairwall', x0, x1, Y_TOP, 29.0, -1, Z_PARK + 0.45)
    for x in (2.42, 4.58):
        P.railing([(x, 25.0, zl), (x, 29.0, Z_PARK)], 0, h=0.9, rails=1, m=M['metal_dark'], posts=2.0)
    P.ivy_wall((5.4, 21.76), (9.4, 21.76), 0.0, 0.55, 10)
    P.bush(7.4, 25.6, bank_z(7.4, 25.6) - 0.1, r=1.0, h=1.4, leaf=M['leaf_shrub'])
    P.bush(-0.9, 25.2, bank_z(-0.9, 25.2) - 0.1, r=0.9, h=1.2, leaf=M['leaf_shrub'])


def drystone_wall(x0=9.8, x1=59.6):
    """x 9.8..59.6: low dry-stone wall, three rough courses and a row of capstones, soil showing in the joints."""
    g = 'Props.drystone'
    G[g].box_mm(x0, x1, Y_LOT + 0.14, Y_BACK, -0.1, 0.64, M['soil'])
    m = M['drystone']
    courses = [(Z_WALK - 0.06, 0.24), (0.3, 0.2), (0.47, 0.17)]
    for zc, hc in courses:
        x = x0 + rng.uniform(-0.2, 0.0)
        while x < x1 - 0.1:
            L = min(rng.uniform(0.26, 0.62), x1 - x)
            d = rng.uniform(0.3, 0.4)
            hh = hc * rng.uniform(0.82, 1.08)
            P.rock_block(x + L / 2, Y_LOT + d / 2 + rng.uniform(-0.02, 0.03), zc, L - 0.03, d, hh, rz=rng.uniform(-0.07, 0.07), g=g, m=m,
                         cuts=1, jit=0.07, collide=False)
            x += L
    x = x0 - 0.05
    while x < x1:
        L = min(rng.uniform(0.38, 0.75), x1 + 0.05 - x)
        t = rng.uniform(0.07, 0.11)
        P.rock_block(x + L / 2, Y_LOT + 0.19, 0.72 - t + rng.uniform(-0.015, 0.02), L - 0.025, rng.uniform(0.4, 0.46), t,
                     rz=rng.uniform(-0.05, 0.05), g=g, m=m, cuts=1, jit=0.06, collide=False)
        x += L
    collider_mm('nebank', x0, x1, Y_LOT, Y_BACK, -1.0, 0.72)
    # creeper over a few stretches of the wall
    for xa, xb in ((14.0, 16.5), (27.2, 29.0), (37.5, 40.5), (47.0, 48.5), (55.0, 57.5)):
        P.drape((xa, Y_LOT), (xb, Y_LOT), 0.72, int((xb - xa) * 5), drop=(0.2, 0.45), off=0.0)


def cabinet(x, y):
    """small utility cabinet on a concrete plinth with a red-tiled gable roof (just E of the stair)."""
    mb = G['Props.nebank']
    zs = [bank_z(x + dx, y + dy) for dx in (-0.6, 0.6) for dy in (-0.4, 0.4)]
    zb, zp = min(zs) - 0.15, max(zs) + 0.12
    mb.box_mm(x - 0.6, x + 0.6, y - 0.4, y + 0.4, zb, zp, M['concrete'])
    H = 1.35
    mb.box((x, y, zp + H / 2), (0.95, 0.5, H), M['st_cream'])
    mb.box((x, y - 0.256, zp + 0.62), (0.72, 0.014, 0.95), M['cabinet'])
    mb.box((x + 0.28, y - 0.268, zp + 0.68), (0.03, 0.02, 0.12), M['metal_dark'])
    zt = zp + H
    _prism(mb, [(y - 0.25, zt), (y + 0.25, zt), (y, zt + 0.17)], 'x', x - 0.475, x + 0.475, M['st_cream'])
    for s in (-1, 1):
        mb.box((x, y + s * 0.165, zt + 0.1), (1.12, 0.4, 0.045), M['rooftiles'], rx=-s * 0.6)
    mb.box((x, y, zt + 0.205), (1.14, 0.08, 0.06), M['rooftiles'])
    collider('cabinet', (x, y, (zb + zt + 0.2) / 2), (1.2, 0.8, zt + 0.2 - zb))


def east_planting():
    sh = M['leaf_shrub']
    P.bamboo(13.4, 22.8, 23.95, 26.7, bank_z, h=6.6, density=4.0)
    P.bush(23.9, 24.9, bank_z(23.9, 24.9) - 0.1, r=1.2, h=1.8, leaf=sh)
    for xa, xb in ((25.0, 35.0), (39.0, 46.5), (50.5, 57.8)):
        shrub_mass(xa, xb, 1.6, 2.6, step=1.4)


def build():
    bank()
    driveway()
    nw_terrace()
    concrete_wall()
    outcrop()
    stairs()
    drystone_wall()
    cabinet(11.8, 24.55)
    east_planting()
