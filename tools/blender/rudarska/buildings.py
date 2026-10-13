"""Buildings around Rudarska ulica: a generic facade builder (wall with real openings, reveals,
frames, shutters, grilles, curtains), roof builders, and every individual building."""
import math

from mathutils import Vector

from . import props as P
from .lib import G, collider, collider_mm, collider_seg, rng, rot2
from .palette import M

GW = 'Buildings.walls'
GO = 'Buildings.openings'
GR = 'Buildings.roofs'
GD = 'Buildings.details'
GB = 'Backdrop.buildings'


# ------------------------------------------------------------------------------------------------
# facade builder
# ------------------------------------------------------------------------------------------------

class Style:
    def __init__(self, glass=None, frame=None, fw=0.06, depth=0.16, cols=2, transom=None, sill=None, surround=None,
                 sw=0.13, shutter=None, shut=(0.0, 0.6), grille=None, curtain=None, door=None, reveal=None, proud=0.035,
                 lintel=None):
        self.glass = glass or M['glass']
        self.frame = frame or M['frame_white']
        self.fw, self.depth, self.cols, self.transom = fw, depth, cols, transom
        self.sill, self.surround, self.sw, self.proud = sill, surround, sw, proud
        self.shutter, self.shut, self.grille, self.curtain = shutter, shut, grille, curtain
        self.door, self.reveal, self.lintel = door, reveal, lintel


class Op:
    """rectangular opening on a facade, in facade coordinates (u along the wall, v above its base)."""

    def __init__(self, u0, u1, v0, v1, st, shut=None, curtain=None):
        self.u0, self.u1, self.v0, self.v1, self.st = u0, u1, v0, v1, st
        self.shut = shut
        self.curtain = curtain


def row(L, n, w, v0, v1, st, margin=0.0, skip=(), off=0.0):
    sp = (L - 2 * margin) / n
    return [Op(margin + off + sp * (i + 0.5) - w / 2, margin + off + sp * (i + 0.5) + w / 2, v0, v1, st)
            for i in range(n) if i not in skip]


def floors(L, n, w, levels, st, margin=0.0, skip=(), off=0.0):
    """same window column layout on every level: levels = [(v0, v1), ...]"""
    out = []
    for v0, v1 in levels:
        out += row(L, n, w, v0, v1, st, margin, skip, off)
    return out


class Wall:
    """frame helper for a straight facade p0->p1 (visible side to the right)."""

    def __init__(self, p0, p1, z0):
        self.a = Vector((p0[0], p0[1], 0.0))
        b = Vector((p1[0], p1[1], 0.0))
        d = b - self.a
        self.L = d.length
        self.d = d / self.L
        self.n = Vector((self.d.y, -self.d.x, 0.0))
        self.yaw = math.atan2(self.d.y, self.d.x)
        self.z0 = z0

    def W(self, u, v, o=0.0):
        return self.a + self.d * u + self.n * o + Vector((0, 0, self.z0 + v))

    def box(self, mb, u, v, o, su, sv, so, m):
        """box centred at facade coords (u, v, o) with size along wall / up / out."""
        mb.box(tuple(self.W(u, v, o)), (su, so, sv), m, rz=self.yaw)

    def p2(self, u, o=0.0):
        w = self.W(u, 0, o)
        return (w.x, w.y)


def _r(x):
    return round(x, 4)


def facade(p0, p1, z0, z1, m, ops=(), base=None, ledge=True, grime=True, sink=0.4, g=GW, go=GO):
    """wall surface from p0 to p1 between z0 and z1 with rectangular openings cut out.
    base = (height, material): stone plinth.  Returns the Wall frame for placing details."""
    mb = G[g]
    w = Wall(p0, p1, z0)
    L, H = w.L, z1 - z0
    ops = [o for o in ops if o.u1 > 0.01 and o.u0 < L - 0.01]
    us = sorted({_r(0.0), _r(L)} | {_r(min(L, max(0.0, x))) for o in ops for x in (o.u0, o.u1)})
    vs = sorted({_r(-sink), _r(0.0), _r(H)} | ({_r(base[0])} if base else set()) |
                {_r(min(H, max(0.0, y))) for o in ops for y in (o.v0, o.v1)})
    for j in range(len(vs) - 1):
        v0, v1 = vs[j], vs[j + 1]
        if v1 - v0 < 1e-4:
            continue
        vm = (v0 + v1) / 2
        mm = base[1] if base and vm < base[0] else m
        start = None
        for i in range(len(us) - 1):
            um = (us[i] + us[i + 1]) / 2
            hole = any(o.u0 < um < o.u1 and o.v0 < vm < o.v1 for o in ops)
            if not hole and start is None:
                start = us[i]
            last = i == len(us) - 2
            if start is not None and (hole or last):
                end = us[i] if hole else us[i + 1]
                if end - start > 1e-4:
                    mb.quad([w.W(start, v0), w.W(end, v0), w.W(end, v1), w.W(start, v1)], mm)
                start = None
    for o in ops:
        opening(G[go], w, o, m if not (base and o.v0 < base[0] and o.v1 <= base[0]) else base[1])
    if base and ledge:
        # thin projecting ledge on top of the plinth, interrupted by openings that cross it
        cuts = sorted((o.u0 - 0.02, o.u1 + 0.02) for o in ops if o.v0 < base[0] + 0.02)
        u = 0.0
        segs = []
        for c0, c1 in cuts:
            if c0 > u:
                segs.append((u, c0))
            u = max(u, c1)
        if u < L:
            segs.append((u, L))
        for s0, s1 in segs:
            if s1 - s0 > 0.05:
                w.box(G[g], (s0 + s1) / 2, base[0] + 0.03, 0.02, s1 - s0, 0.06, 0.06, M['sill'])
    if grime:
        G['Buildings.decals'].wall_card(p0, p1, z0, z0 + 0.9, M['grime'], uv=(0, 0, max(1.0, L / 3), 1), off=0.012)
    return w


def opening(mb, w, o, wall_m):
    st = o.st
    u0, u1, v0, v1 = o.u0, o.u1, o.v0, o.v1
    dp = st.depth
    rev = st.reveal or wall_m
    W = w.W
    mb.quad([W(u0, v0, 0), W(u0, v0, -dp), W(u0, v1, -dp), W(u0, v1, 0)], rev)
    mb.quad([W(u1, v0, -dp), W(u1, v0, 0), W(u1, v1, 0), W(u1, v1, -dp)], rev)
    mb.quad([W(u0, v1, 0), W(u0, v1, -dp), W(u1, v1, -dp), W(u1, v1, 0)], rev)
    mb.quad([W(u1, v0, 0), W(u1, v0, -dp), W(u0, v0, -dp), W(u0, v0, 0)], st.sill if st.sill else rev)
    wu, hv = u1 - u0, v1 - v0
    fw = st.fw
    fo = -dp + 0.03
    if st.door is not None:
        # door leaf (with a glazed upper part if a transom is given)
        vt = v0 + hv * (st.transom or 1.0)
        mb.quad([W(u0, v0, -dp), W(u1, v0, -dp), W(u1, vt, -dp), W(u0, vt, -dp)], st.door)
        if vt < v1:
            mb.quad([W(u0, vt, -dp), W(u1, vt, -dp), W(u1, v1, -dp), W(u0, v1, -dp)], st.glass)
            w.box(mb, (u0 + u1) / 2, vt, fo, wu, fw, 0.06, st.frame)
        for k in range(1, st.cols):
            w.box(mb, u0 + wu * k / st.cols, (v0 + vt) / 2, fo + 0.01, 0.04, vt - v0, 0.05, st.frame)
        # handles
        w.box(mb, (u0 + u1) / 2 + 0.1, v0 + 1.05, -dp + 0.05, 0.03, 0.18, 0.04, M['metal'])
    else:
        mb.quad([W(u0, v0, -dp), W(u1, v0, -dp), W(u1, v1, -dp), W(u0, v1, -dp)], st.glass)
        # curtains just in front of the glass, behind the frame
        cur = o.curtain if o.curtain is not None else st.curtain
        if cur is not None:
            for k in range(st.cols):
                a0, a1 = u0 + wu * k / st.cols, u0 + wu * (k + 1) / st.cols
                r = rng.random()
                if r < 0.15:
                    continue
                if r < 0.7:
                    c0, c1 = a0, a1
                else:
                    c0, c1 = (a0, a0 + (a1 - a0) * 0.4) if rng.random() < 0.5 else (a1 - (a1 - a0) * 0.4, a1)
                ct = v1 - 0.04
                cb = v0 + hv * rng.choice((0.0, 0.0, 0.25))
                mb.quad([W(c0, cb, -dp + 0.006), W(c1, cb, -dp + 0.006), W(c1, ct, -dp + 0.006), W(c0, ct, -dp + 0.006)], cur)
    # frame
    fm = st.frame
    w.box(mb, u0 + fw / 2, (v0 + v1) / 2, fo, fw, hv, 0.06, fm)
    w.box(mb, u1 - fw / 2, (v0 + v1) / 2, fo, fw, hv, 0.06, fm)
    w.box(mb, (u0 + u1) / 2, v1 - fw / 2, fo, wu, fw, 0.06, fm)
    w.box(mb, (u0 + u1) / 2, v0 + fw / 2, fo, wu, fw, 0.06, fm)
    if st.door is None:
        for k in range(1, st.cols):
            w.box(mb, u0 + wu * k / st.cols, (v0 + v1) / 2, fo, fw * 0.8, hv, 0.05, fm)
        if st.transom:
            w.box(mb, (u0 + u1) / 2, v0 + hv * st.transom, fo, wu, fw * 0.8, 0.05, fm)
    # roller shutter (partly down)
    if st.shutter is not None:
        frac = o.shut if o.shut is not None else rng.uniform(*st.shut)
        if frac > 0.03:
            vb = v1 - hv * min(1.0, frac)
            so = -dp + 0.085
            mb.quad([W(u0 + 0.01, vb, so), W(u1 - 0.01, vb, so), W(u1 - 0.01, v1, so), W(u0 + 0.01, v1, so)], st.shutter)
            w.box(mb, (u0 + u1) / 2, vb + 0.02, so - 0.01, wu - 0.02, 0.04, 0.03, M['frame_dark'] if st.shutter is M['shutter'] else st.frame)
    # grille bars
    if st.grille is not None:
        go = -0.05
        nb = max(2, int(wu / 0.13))
        for k in range(1, nb):
            w.box(mb, u0 + wu * k / nb, (v0 + v1) / 2, go, 0.018, hv, 0.018, st.grille)
        for t in (0.12, 0.5, 0.88):
            w.box(mb, (u0 + u1) / 2, v0 + hv * t, go, wu, 0.03, 0.012, st.grille)
    # exterior sill / surround
    if st.sill is not None and st.door is None:
        w.box(mb, (u0 + u1) / 2, v0 - 0.03, (0.07 - dp) / 2, wu + 0.12, 0.06, dp + 0.07, st.sill)
    if st.surround is not None:
        s, pr = st.sw, st.proud
        w.box(mb, u0 - s / 2, (v0 + v1) / 2, pr / 2 - 0.005, s, hv + 2 * s, pr, st.surround)
        w.box(mb, u1 + s / 2, (v0 + v1) / 2, pr / 2 - 0.005, s, hv + 2 * s, pr, st.surround)
        w.box(mb, (u0 + u1) / 2, v1 + s / 2, pr / 2 - 0.005, wu, s, pr, st.surround)
        if st.door is None:
            w.box(mb, (u0 + u1) / 2, v0 - s / 2, pr / 2 - 0.005, wu, s, pr, st.surround)
    if st.lintel is not None:
        w.box(mb, (u0 + u1) / 2, v1 + 0.1, 0.01, wu + 0.3, 0.2, 0.04, st.lintel)


# ------------------------------------------------------------------------------------------------
# footprints & roofs
# ------------------------------------------------------------------------------------------------

def rect(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def orect(cx, cy, sx, sy, yaw):
    out = []
    for lx, ly in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2)):
        rx, ry = rot2(lx, ly, yaw)
        out.append((cx + rx, cy + ry))
    return out


def edges(pts):
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def flat_roof(pts, z, parapet=0.5, pw=0.28, wall=None, cap=None, roof=None, g=GR):
    """roof surface at z inside walls that rise to z + parapet (the facade itself is the outer face)."""
    mb = G[g]
    mb.poly_flat(pts, z, roof or M['flatroof'])
    if parapet <= 0:
        return
    for p0, p1 in edges(pts):
        a, b = Vector(p0), Vector(p1)
        d = (b - a).normalized()
        nn = Vector((d.y, -d.x))
        mb.seg_box(a - nn * (pw / 2), b - nn * (pw / 2), pw, z - 0.05, z + parapet, wall or M['st_gray'])
        mb.seg_box(a - nn * (pw / 2 - 0.04), b - nn * (pw / 2 - 0.04), pw + 0.08, z + parapet, z + parapet + 0.06,
                   cap or M['parapet'], ext=0.04)


def hip_roof(cx, cy, sx, sy, yaw, z, rise, over=0.5, m=None, soffit=None, g=GR, gable=False, wall=None):
    """hipped (or gabled) roof over a rectangle; ridge along the longer side."""
    mb = G[g]
    m = m or M['rooftiles']
    hx, hy = sx / 2 + over, sy / 2 + over

    def Pt(lx, ly, lz=0.0):
        rx, ry = rot2(lx, ly, yaw)
        return (cx + rx, cy + ry, z + lz)
    E = [Pt(-hx, -hy), Pt(hx, -hy), Pt(hx, hy), Pt(-hx, hy)]
    if hx >= hy:
        R0, R1 = Pt(-(hx - hy) if not gable else -hx, 0, rise), Pt((hx - hy) if not gable else hx, 0, rise)
        mb.quad([E[0], E[1], R1, R0], m)
        mb.quad([E[2], E[3], R0, R1], m)
        if not gable:
            mb.quad([E[1], E[2], R1], m)
            mb.quad([E[3], E[0], R0], m)
        else:
            gw = wall or M['st_white']
            for s in (-1, 1):
                lx = s * (sx / 2)
                tri = [Pt(lx, -hy), Pt(lx, hy), Pt(lx, 0, rise)]
                if s < 0:
                    tri = [tri[1], tri[0], tri[2]]
                mb.quad(tri, gw)
    else:
        R0 = Pt(0, -(hy - hx) if not gable else -hy, rise)
        R1 = Pt(0, (hy - hx) if not gable else hy, rise)
        mb.quad([E[1], E[2], R1, R0], m)
        mb.quad([E[3], E[0], R0, R1], m)
        if not gable:
            mb.quad([E[0], E[1], R0], m)
            mb.quad([E[2], E[3], R1], m)
        else:
            gw = wall or M['st_white']
            for s in (-1, 1):
                ly = s * (sy / 2)
                tri = [Pt(-hx, ly), Pt(hx, ly), Pt(0, ly, rise)]
                if s > 0:
                    tri = [tri[1], tri[0], tri[2]]
                mb.quad(tri, gw)
    # soffit + fascia board
    mb.quad(list(reversed(E)), soffit or M['frame_white'])
    for a, b in edges([(e[0], e[1]) for e in E]):
        mb.seg_box(a, b, 0.05, z - 0.18, z + 0.02, soffit or M['frame_white'])


def barrel_roof(x0, x1, y0, y1, z, rise, m=None, wall=None, seg=16, g=GR):
    """curved roof spanning x, running along y; end walls filled with `wall`."""
    mb = G[g]
    m = m or M['roof_metal']
    hx = (x1 - x0) / 2
    cx = (x0 + x1) / 2
    R = (hx * hx + rise * rise) / (2 * rise)
    a0 = math.asin(hx / R)
    pts = []
    for k in range(seg + 1):
        a = -a0 + 2 * a0 * k / seg
        pts.append((cx + R * math.sin(a), z + R * math.cos(a) - (R - rise)))
    for k in range(seg):
        (xa, za), (xb, zb) = pts[k], pts[k + 1]
        mb.quad([(xa, y0, za), (xb, y0, zb), (xb, y1, zb), (xa, y1, za)], m, smooth=True)
    for k in range(seg):
        (xa, za), (xb, zb) = pts[k], pts[k + 1]
        if wall:
            mb.quad([(xa, y0, z), (xb, y0, z), (xb, y0, zb), (xa, y0, za)], wall)
            mb.quad([(xb, y1, z), (xa, y1, z), (xa, y1, za), (xb, y1, zb)], wall)


def lean_to(x0, x1, y_lo, y_hi, z_lo, z_hi, m=None, over=0.3, g=GR):
    """single-pitch roof falling from y_hi (z_hi) to y_lo (z_lo)."""
    mb = G[g]
    m = m or M['rooftiles']
    s = 1 if y_lo < y_hi else -1
    dz = (z_hi - z_lo) / abs(y_hi - y_lo)
    ylo, yhi = y_lo - s * over, y_hi
    zlo = z_lo - over * dz
    pts = [(x0 - over, ylo, zlo), (x1 + over, ylo, zlo), (x1 + over, yhi, z_hi), (x0 - over, yhi, z_hi)]
    if s < 0:
        pts = [pts[1], pts[0], pts[3], pts[2]]
    mb.quad(pts, m)
    mb.quad(list(reversed(pts)), M['frame_white'])


def box_building(pts, z0, z1, wall, faces=None, roof='flat', roof_kw=None, base=None, collide=True, g=GW, go=GO,
                 grime=True, kind='bld'):
    """closed building from a CCW footprint.  faces: {edge_index: ops} for openings; roof 'flat' / None."""
    faces = faces or {}
    walls = []
    for i, (p0, p1) in enumerate(edges(pts)):
        walls.append(facade(p0, p1, z0, z1, wall, faces.get(i, ()), base=base, g=g, go=go, grime=grime))
    if roof == 'flat':
        kw = dict(parapet=0.5, wall=wall)
        kw.update(roof_kw or {})
        flat_roof(pts, z1 - kw['parapet'], g=GR if g == GW else g, **kw)
    elif roof == 'cap':
        G[GR if g == GW else g].poly_flat(pts, z1, (roof_kw or {}).get('roof', M['flatroof']))
    if collide:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if len(pts) == 4 and abs((pts[1][1] - pts[0][1])) < 1e-3 and abs(pts[2][0] - pts[1][0]) < 1e-3:
            collider_mm(kind, min(xs), max(xs), min(ys), max(ys), z0 - 0.5, z1 + 0.5)
        else:
            # oriented rectangle
            a, b, c = Vector(pts[0]), Vector(pts[1]), Vector(pts[2])
            cc = (Vector(pts[0]) + Vector(pts[2])) / 2
            collider(kind, (cc.x, cc.y, (z0 + z1) / 2), ((b - a).length, (c - b).length, z1 - z0 + 1.0),
                     rz=math.atan2(b.y - a.y, b.x - a.x))
    return walls


# ------------------------------------------------------------------------------------------------
# styles (built after the palette exists)
# ------------------------------------------------------------------------------------------------
S = {}


def styles():
    S['annex_g'] = Style(cols=2, sill=M['sill'], surround=M['sill'], shutter=M['shutter'], shut=(0.7, 1.0), sw=0.14)
    S['annex_u'] = Style(cols=2, transom=0.72, sill=M['sill'], surround=M['sill'], shutter=M['shutter'], shut=(0.0, 0.6), sw=0.12)
    S['annex_door'] = Style(cols=1, door=M['door_wood'], frame=M['frame_brown'], surround=M['sill'], sw=0.16)
    S['admin'] = Style(cols=2, transom=0.75, sill=M['sill'], shutter=M['shutter'], shut=(0.05, 0.75), depth=0.2)
    S['admin_hall'] = Style(cols=2, transom=0.8, sill=M['sill'], shutter=M['shutter'], shut=(0.0, 0.5), depth=0.22)
    S['admin_door'] = Style(cols=2, door=M['door_wood'], frame=M['frame_brown'], transom=0.78, glass=M['glass_dark'],
                            surround=M['sill'], sw=0.22, depth=0.35)
    S['glassblock'] = Style(cols=1, glass=M['glassblock'], frame=M['sill'], fw=0.05, depth=0.12)
    S['peach_grid'] = Style(cols=3, transom=0.5, sill=M['sill'], depth=0.18)
    S['teal_low'] = Style(cols=4, frame=M['frame_red'], grille=M['grille_red'], curtain=M['curtain'], sill=M['concrete'],
                          depth=0.12)
    S['teal_up'] = Style(cols=4, frame=M['frame_red'], curtain=M['curtain'], sill=M['concrete'], transom=0.25, depth=0.1)
    S['teal_door'] = Style(cols=2, door=M['frame_red'], glass=M['glass'], frame=M['frame_red'], transom=0.25, depth=0.3)
    S['wall_low'] = Style(cols=1, glass=M['glass_dark'], frame=M['frame_dark'], grille=M['grille'], depth=0.3,
                          reveal=M['sill'])
    S['school'] = Style(cols=2, transom=0.7, frame=M['frame_white'], sill=M['sill'], surround=M['st_cream'], sw=0.12,
                        depth=0.22)
    S['plain'] = Style(cols=2, transom=0.7, sill=M['sill'], depth=0.15)
    S['plain_sh'] = Style(cols=2, sill=M['sill'], shutter=M['shutter_gray'], shut=(0.0, 0.8), depth=0.15)
    S['dark'] = Style(cols=1, glass=M['glass_dark'], frame=M['frame_dark'], depth=0.1)
    S['ribbon'] = Style(cols=6, glass=M['glass'], frame=M['frame_alu'], depth=0.12)
    S['curtainwall'] = Style(cols=4, transom=0.5, glass=M['glass_blue'], frame=M['frame_dark'], fw=0.08, depth=0.06)
    S['shopfront'] = Style(cols=4, glass=M['glass_blue'], frame=M['frame_dark'], depth=0.15, transom=0.82)
    S['green_bldg'] = Style(cols=2, sill=M['sill'], frame=M['frame_white'], shutter=M['shutter_gray'], shut=(0.0, 0.4))


# ------------------------------------------------------------------------------------------------
# SW side of the street (from the SE end to the NW end)
# ------------------------------------------------------------------------------------------------
Z_SW = 0.12   # sidewalk level on the SW side


def admin_block():
    """beige 4-storey municipal building facing the SE pocket (x = 46.8), its taller entrance hall and
    the peach stair tower on the street corner."""
    z0 = Z_SW
    # -- main block -----------------------------------------------------------------------------
    x0, x1, y0, y1 = 30.0, 46.8, -46.5, -24.0
    H = 14.6
    lv = [(1.25, 2.85), (4.65, 6.25), (8.05, 9.65), (11.45, 13.05)]
    front = floors(22.5, 11, 0.95, lv, S['admin'], margin=0.3)
    # library entrance at the far (SW) end with a red-brown canopy
    front = [o for o in front if not (3.0 < (o.u0 + o.u1) / 2 < 7.0 and o.v0 < 3)]
    front.append(Op(4.0, 6.0, 0.0, 2.6, Style(cols=2, door=M['glass_dark'], frame=M['frame_dark'], transom=0.85, depth=0.25)))
    pts = rect(x0, x1, y0, y1)
    walls = box_building(pts, z0, H, M['st_admin'], faces={1: front, 0: floors(16.8, 7, 0.95, lv, S['admin'])},
                         base=(0.9, M['stonebase']), roof_kw=dict(parapet=0.45, cap=M['parapet'], roof=M['flatroof_light']))
    wf = walls[1]
    mb = G[GD]
    # canopy over the library door
    wf.box(mb, 5.0, 2.95, 0.9, 3.4, 0.18, 1.8, M['canopy'])
    collider('canopy', tuple(wf.W(5.0, 2.95, 0.9)), (3.4, 1.8, 0.18), rz=wf.yaw)
    for u in (3.5, 6.5):
        mb.pole(wf.p2(u, 1.7), z0, z0 + 2.9, 0.04, M['metal_dark'])
    sign_c = wf.W(5.0, 3.3, 0.05)
    G['Props.signs'].card(sign_c, wf.d, (0, 0, 1), 3.0, 0.38, M['sign_library'])
    # cornice
    wf.box(mb, wf.L / 2, H - 0.45, 0.12, wf.L + 0.2, 0.14, 0.24, M['sill'])
    # downpipes, AC units
    for u in (0.15, 7.6, 15.2, 22.35):
        P.downpipe(wf.p2(u), wf.n, z0, H - 0.4)
    for o in rng.sample([o for o in front if o.v0 > 3], 9):
        P.ac_unit(wf.p2((o.u0 + o.u1) / 2 + 0.95), wf.n, z0 + o.v0 - 0.45)
    # rooftop flag / antenna poles near the far end (seen against the sky)
    for k, u in enumerate((1.0, 2.4, 3.8, 5.2)):
        p = wf.p2(u, -0.4)
        mb.pole(p, H, H + 4.5 + k * 0.2, 0.025, M['metal'])

    # -- entrance hall (taller, between the main block and the tower) --------------------------------
    hx0, hy0, hy1 = 34.0, -24.0, -16.0
    HH = 15.5
    lvh = [(1.4, 3.3), (5.0, 7.0), (8.7, 10.7), (12.3, 14.2)]
    hall_front = floors(8.0, 3, 1.05, lvh[1:], S['admin_hall'])
    hall_front.append(Op(2.6, 5.4, 0.45, 3.4, S['admin_door']))
    hall_front += [Op(0.55, 1.6, 1.4, 3.3, S['admin_hall']), Op(6.4, 7.45, 1.4, 3.3, S['admin_hall'])]
    walls = box_building(rect(hx0, x1, hy0, hy1), z0, HH, M['st_admin_old'], faces={1: hall_front},
                         base=(0.9, M['stonebase']), roof_kw=dict(parapet=0.45, cap=M['parapet'], roof=M['flatroof_light']))
    wh = walls[1]
    wh.box(mb, 4.0, HH - 0.45, 0.12, 8.2, 0.14, 0.24, M['sill'])
    # entrance steps + landing
    for i in range(3):
        wh.box(mb, 4.0, 0.075 + i * 0.15, 1.3 - i * 0.35, 4.6 - i * 0.3, 0.15, 2.6 - i * 0.7, M['concrete'])
    for i in range(3):
        collider('steps', tuple(wh.W(4.0, (i + 1) * 0.15 / 2, 1.3 - i * 0.35)), (4.6 - i * 0.3, 2.6 - i * 0.7, (i + 1) * 0.15),
                 rz=wh.yaw, clip=True)
    # plaques and info boards beside the door, flags out over the entrance
    for u, v in ((2.2, 1.9), (5.8, 1.9), (5.8, 1.35)):
        G['Props.signs'].card(wh.W(u, v, 0.02), wh.d, (0, 0, 1), 0.42, 0.55, M['plaque'])
    P.flagpole_wall(wh.p2(3.4), wh.n, z0 + 4.4, M['flag_hr'], ang=0.75)
    P.flagpole_wall(wh.p2(4.6), wh.n, z0 + 4.4, M['flag_eu'], ang=0.75)
    for o in hall_front:
        if o.v0 > 4 and rng.random() < 0.5:
            P.ac_unit(wh.p2(o.u1 + 0.6), wh.n, z0 + o.v0 - 0.4)
    P.downpipe(wh.p2(7.9), wh.n, z0, HH - 0.4)

    # -- peach stair tower on the street corner ---------------------------------------------------
    tx0, tx1, ty0, ty1 = 37.7, 46.8, -16.0, -10.1
    TH = 16.6
    # edge 2 = NE face (street), p0 = (46.8,-10.1) -> p1 = (37.7,-10.1); glass blocks near the annex end
    ne = [Op(5.6, 6.9, 2.6, 9.6, S['glassblock']), Op(5.75, 6.75, 10.4, 11.9, S['glassblock']),
          Op(5.5, 7.0, 13.2, 15.0, S['peach_grid'])]
    east = [Op(2.2, 3.2, 13.4, 15.0, S['plain'])]
    walls = box_building(rect(tx0, tx1, ty0, ty1), z0, TH, M['st_peach'], faces={2: ne, 1: east},
                         base=(0.6, M['stonebase']), roof_kw=dict(parapet=0.4, cap=M['parapet'], roof=M['flatroof_light']))
    wt = walls[2]
    wt.box(mb, wt.L / 2, TH - 0.2, 0.08, wt.L + 0.16, 0.4, 0.16, M['st_peach'])
    mb.pole(wt.p2(7.9, -1.0), TH, TH + 2.2, 0.03, M['metal'])
    P.downpipe(wt.p2(0.2), wt.n, z0, TH - 0.4, red=False)
    # planter with a low stone wall in front of the tower
    pw = [(37.7, -6.7), (45.6, -6.7), (45.6, -10.1)]
    for a, b in zip(pw, pw[1:]):
        G[GD].seg_box(a, b, 0.4, z0, z0 + 0.85, M['concrete_gray'], ext=0.2)
        collider_seg('lowwall', a, b, 0.42, z0, z0 + 0.85, ext=0.2)
    G['Ground.planter'].poly_flat(rect(37.9, 45.4, -10.0, -6.9), z0 + 0.55, M['soil'])
    for x in (39.0, 41.2, 43.4):
        P.bush(x, -8.4, z0 + 0.55, r=1.0, h=1.3)

    # -- inner wings & back masses (seen over the roofs) ----------------------------------------------
    box_building(rect(13.0, 30.0, -30.0, -14.0), z0, 12.6, M['st_admin_old'],
                 faces={2: floors(17.0, 8, 0.95, [(1.3, 2.8), (4.6, 6.1), (7.9, 9.4)], S['plain_sh'])}, collide=False,
                 roof_kw=dict(parapet=0.4, roof=M['flatroof_light']))
    box_building(rect(1.4, 13.0, -40.0, -14.0), z0, 8.2, M['st_annex'], collide=False, roof_kw=dict(parapet=0.4, roof=M['flatroof_light']))
    box_building(rect(1.4, 46.8, -78.0, -46.5), z0, 10.0, M['st_admin_old'], g=GB, go=GB, collide=False, grime=False,
                 faces={0: floors(45.4, 18, 1.0, [(1.3, 2.9), (4.6, 6.2), (7.6, 9.0)], S['plain'])},
                 roof_kw=dict(parapet=0.4))


def annex():
    """3-storey weathered building along the street (x 1.1..37.7), limestone plinth, brown shutters."""
    z0 = Z_SW
    x0, x1, y0, y1 = 1.1, 37.7, -14.0, -6.1
    H = 11.2
    L = x1 - x0
    n = 11
    gl = [(1.45, 2.95)]
    up = [(4.45, 5.95), (7.55, 9.05)]
    street = row(L, n, 1.45, *gl[0], S['annex_g'], margin=0.5)
    street += floors(L, n, 1.2, up, S['annex_u'], margin=0.5)
    # two doors on the ground floor
    street = [o for o in street if not (o.v0 < 3 and (abs((o.u0 + o.u1) / 2 - 8.75) < 0.5 or abs((o.u0 + o.u1) / 2 - 25.4) < 0.5))]
    sp = (L - 1.0) / n
    for i in (2, 7):
        c = 0.5 + sp * (i + 0.5)
        street.append(Op(c - 0.6, c + 0.6, 0.35, 2.75, S['annex_door']))
    se = [Op(1.4, 2.6, 1.45, 2.95, S['annex_g'], shut=1.0), Op(1.5, 2.5, 4.45, 5.95, S['annex_u'], shut=0.0),
          Op(1.5, 2.5, 7.55, 9.05, S['annex_u'], shut=0.8)]
    nw = [Op(5.4, 6.4, 7.55, 9.05, S['annex_u']), Op(5.4, 6.4, 4.45, 5.95, S['annex_u'])]
    back = floors(L, 9, 1.1, [(1.5, 2.9), (4.5, 5.9), (7.6, 9.0)], S['plain_sh'], margin=1.0)
    # edges: 0 = back (y0), 1 = SE end (x1), 2 = street (y1, p0 = x1 -> p1 = x0), 3 = NW end (x0)
    walls = box_building(rect(x0, x1, y0, y1), z0, H, M['st_annex'], faces={0: back, 1: se, 2: street, 3: nw},
                         base=(1.25, M['stonebase']), roof_kw=dict(parapet=0.35, cap=M['parapet']))
    w = walls[2]
    mb = G[GD]
    w.box(mb, L / 2, H - 0.25, 0.1, L + 0.2, 0.22, 0.2, M['sill'])
    # rusty pipe rail along the plinth, gray ELNA cabinet, downpipes, AC units
    P.railing([w.p2(0.6, 0.3), w.p2(L - 0.6, 0.3)], z0, h=0.75, g='Props.rails', posts=2.4, m=M['rust'], rails=1)
    w.box(mb, 30.6, 0.65, 0.2, 0.8, 1.3, 0.38, M['cabinet'])
    collider('cabinet', tuple(w.W(30.6, 0.65, 0.2)), (0.8, 0.4, 1.3), rz=w.yaw)
    for u in (0.2, 12.4, 24.6, L - 0.2):
        P.downpipe(w.p2(u), w.n, z0, H - 0.3)
    wins = [o for o in street if o.st is S['annex_u']]
    for o in rng.sample(wins, 7):
        P.ac_unit(w.p2((o.u0 + o.u1) / 2 + 1.25), w.n, z0 + o.v0 + 0.3)
    for o in [o for o in street if o.st is S['annex_g']][1::3]:
        P.ac_unit(w.p2((o.u0 + o.u1) / 2), w.n, z0 + 3.45, w=0.7, h=0.5)
    # NW end: corner downpipe with a red foot, horizontal pipe
    wn = walls[3]
    P.downpipe(wn.p2(0.25), wn.n, z0, H - 0.3)
    G[GD].tube([wn.W(0.25, 3.3, 0.09), wn.W(4.0, 3.3, 0.09)], 0.05, M['pipe_gray'], seg=6)


def stone_wall_block():
    """limestone ashlar wall with low barred windows (x -25.9..1.1), lean-to roof and low building behind,
    the tall brick chimney and the big red-roofed hall further back."""
    z0 = Z_SW
    x0, x1, yf = -25.9, 1.1, -7.0
    H = 3.7
    L = x1 - x0
    low = row(L, 9, 0.75, 0.3, 1.15, S['wall_low'], margin=0.8)
    w = facade((x1, yf), (x0, yf), z0, z0 + H, M['ashlar'], low)
    mb = G[GD]
    # tile coping on the wall
    w.box(mb, L / 2, H + 0.08, 0.05, L, 0.16, 0.5, M['rooftiles'])
    collider_mm('wall', x0, x1, yf - 7.0, yf, z0 - 0.5, z0 + 6.4)
    # lean-to roof behind the wall rising to the back building
    lean_to(x0, x1, yf - 0.15, -14.0, z0 + H + 0.1, z0 + 6.1, m=M['roof_metal'])
    facade((x0, yf), (x0, -14.0), z0, z0 + H, M['ashlar'], grime=False)
    G[GW].quad([(x0, yf, z0 + H), (x0, -14.0, z0 + H), (x0, -14.0, z0 + 6.1)], M['st_gray'])
    # low building behind
    box_building(rect(x0, x1, -24.0, -14.0), z0, z0 + 7.2, M['st_gray'], collide=False,
                 faces={2: row(L, 8, 1.2, 4.2, 5.6, S['plain'], margin=1.0)}, roof_kw=dict(parapet=0.4))
    # chimney
    cx, cy = -30.0, -28.0
    G[GR].cyl((cx, cy, 11.0), 1.15, 22.0, M['st_cream'], seg=4, r2=0.8, rz=math.pi / 4, smooth=False)
    G[GR].cyl((cx, cy, 21.6), 0.85, 0.8, M['metal_dark'], seg=4, rz=math.pi / 4, smooth=False)
    # red-roofed hall
    box_building(rect(-56.5, -18.5, -43.0, -27.0), z0, 8.0, M['st_cream'], collide=False,
                 faces={2: row(38.0, 9, 2.2, 4.5, 6.8, S['plain'])}, roof=None)
    hip_roof(-37.5, -35.0, 38.0, 16.0, 0.0, 8.0, 3.4, over=0.5, gable=True, wall=M['st_cream'])


def teal_building():
    """the long teal 1970s building (x -54.7..-25.9): red-grilled lower windows, ribbon windows with yellow
    curtains, teal pilasters and a projecting flat-roof fascia; entrance with the 55-70 canopy."""
    z0 = Z_SW
    x0, x1, yf, yb = -54.7, -25.9, -8.4, -22.0
    H = 7.0
    L = x1 - x0
    nb = 6
    bay = L / nb
    pil = 0.55
    ops = []
    door_u = x1 - (-41.5)
    for i in range(nb):
        a, b = i * bay + pil / 2 + 0.25, (i + 1) * bay - pil / 2 - 0.25
        ops.append(Op(a, b, 3.75, 6.0, S['teal_up']))
        if a < door_u < b:
            ops.append(Op(a, door_u - 1.3, 0.45, 1.6, S['teal_low']))
            ops.append(Op(door_u - 1.0, door_u + 1.0, 0.38, 2.9, S['teal_door']))
            ops.append(Op(door_u + 1.3, b, 0.45, 1.6, S['teal_low']))
        else:
            ops.append(Op(a, b, 0.45, 1.6, S['teal_low']))
    walls = box_building(rect(x0, x1, yb, yf), z0, H, M['st_teal'],
                         faces={2: ops, 3: [Op(2.0, 6.0, 3.75, 6.0, S['teal_up']), Op(8.0, 12.0, 3.75, 6.0, S['teal_up'])]},
                         base=(0.3, M['concrete_dark']), roof='flat', roof_kw=dict(parapet=0.2, cap=M['st_teal_dark']))
    w = walls[2]
    mb = G[GD]
    # pilasters (darker teal), fascia and roof overhang
    for i in range(nb + 1):
        u = min(L - pil / 2, max(pil / 2, i * bay))
        w.box(mb, u, (H - 0.6) / 2 - 0.1, 0.09, pil, H - 0.6 + 0.2, 0.18, M['st_teal_dark'])
    w.box(mb, L / 2, H - 0.25, 0.4, L + 0.9, 0.5, 0.8, M['st_teal_dark'])
    w.box(mb, L / 2, 2.9, 0.06, L, 0.12, 0.12, M['st_teal_dark'])
    for wi in (walls[1], walls[3]):
        wi.box(mb, wi.L / 2, H - 0.25, 0.4, wi.L + 0.9, 0.5, 0.8, M['st_teal_dark'])
    # entrance: steps, canopy, 55-70 sign, bench, bin
    for i in range(2):
        w.box(mb, door_u, 0.065 + i * 0.13, 0.9 - i * 0.3, 3.2 - i * 0.4, 0.13, 1.8 - i * 0.6, M['concrete'])
    w.box(mb, door_u, 3.1, 0.9, 3.4, 0.16, 1.8, M['st_teal_dark'])
    G['Props.signs'].card(w.W(door_u, 3.1, 1.81), w.d, (0, 0, 1), 1.4, 0.3, M['sign_5570'])
    P.bench(*w.p2(door_u + 2.6, 0.5), z0, w.yaw)
    P.litter_bin(*w.p2(door_u - 2.3, 0.4), z0)
    # signs at the NW corner (RUDARSKI, TRIO I)
    G['Props.signs'].card(w.W(L - 1.2, 3.2, 0.03), w.d, (0, 0, 1), 0.9, 1.6, M['sign_rudarski'])
    s = w.W(L - 0.15, 4.2, 0.45)
    G['Props.signs'].card(s, w.n, (0, 0, 1), 0.7, 1.9, M['sign_trio'], double=True)
    # AC units on the upper band, downpipes
    for u in (4.0, 9.0, 21.0):
        P.ac_unit(w.p2(u), w.n, z0 + 3.2)
    for u in (0.4, L - 0.4):
        P.downpipe(w.p2(u, 0.18), w.n, z0, H - 0.5)
    # roof: solar panels and a small wind turbine on a mast near the SE end
    for k in range(4):
        G[GR].box((x1 - 6 - k * 2.2, -15.0, H - 0.2 + 0.55), (2.0, 3.2, 0.06), M['solar'], rx=0.5)
        G[GR].box((x1 - 6 - k * 2.2, -14.4, H - 0.2 + 0.25), (0.06, 0.06, 0.6), M['metal'])
    mx, my = x1 - 2.0, -13.0
    G[GR].pole((mx, my), H - 0.2, H + 6.5, 0.07, M['metal'], r2=0.05)
    G[GR].cyl((mx, my, H + 6.5), 0.18, 0.6, M['white_paint'], rx=math.pi / 2, rz=0.4)
    for k in range(3):
        a = k * math.tau / 3
        tip = Vector((mx, my, H + 6.5)) + Vector((math.cos(0.4 + math.pi / 2) * 0.35, math.sin(0.4 + math.pi / 2) * 0.35, 0))
        G[GR].tube([tip, tip + Vector((math.cos(a) * 0.02, 0, math.sin(a))) * 1.3], 0.05, M['white_paint'], seg=4)
    # satellite dish
    G[GR].cyl((x1 - 12.0, -10.5, H + 0.4), 0.45, 0.12, M['white_paint'], rx=1.0, seg=12)


def nw_corner_sw():
    """limestone block wall, the light-green single-storey building beyond the side street, IDEAL sign."""
    z0 = Z_SW
    # big limestone block wall between the teal building and the side street
    w = facade((-54.7, -8.4), (-61.0, -8.4), z0, z0 + 2.4, M['ashlar'])
    facade((-61.0, -8.4), (-61.0, -16.0), z0, z0 + 2.4, M['ashlar'])
    G[GD].box_mm(-61.1, -54.7, -16.0, -8.3, z0 + 2.4, z0 + 2.5, M['concrete'])
    collider_mm('wall', -61.0, -54.7, -16.0, -8.4, z0 - 0.5, z0 + 2.5)
    # light-green building (street face x -75.4..-68.8)
    x0, x1, y0, y1 = -75.4, -68.8, -17.0, -8.3
    H = 4.3
    front = [Op(1.2, 2.4, 1.0, 2.4, S['green_bldg']), Op(4.0, 5.2, 1.0, 2.4, S['green_bldg'])]
    side = [Op(2.0, 3.2, 1.0, 2.4, S['green_bldg']), Op(5.0, 6.0, 0.15, 2.3, S['annex_door'])]
    walls = box_building(rect(x0, x1, y0, y1), z0, H, M['st_green'], faces={2: front, 1: side},
                         base=(0.5, M['stonebase']), roof_kw=dict(parapet=0.3, cap=M['concrete']))
    wf = walls[2]
    wf.box(G[GD], 0.3, H / 2 - 0.1, 0.06, 0.6, H + 0.2, 0.14, M['ashlar'])
    # IDEAL sign pole at the corner
    P.sign_post(-61.6, -6.9, z0, math.radians(110), [(M['sign_ideal'], 0.9, 2.7, 2.65)], h=4.1, r=0.05)
    # cream building on the street corner: its east end (x > -78) is inside the playable area and the NW bound
    # stops in it, so it must be solid or players walk through it and out
    box_building(rect(-82.0, -75.4, -20.0, -8.0), z0, 6.5, M['st_cream'],
                 faces={2: [Op(1.5, 2.7, 3.6, 5.0, S['plain_sh'])]}, roof_kw=dict(parapet=0.3))
    # buildings further down the side street / behind (backdrop)
    box_building(rect(-92.0, -77.0, -42.0, -24.0), z0, 7.5, M['st_white'], g=GB, go=GB, collide=False, grime=False,
                 faces={2: row(15.0, 5, 1.1, 4.4, 5.8, S['plain'])}, roof_kw=dict(parapet=0.3))
    box_building(rect(-61.5, -56.8, -42.0, -26.0), z0, 6.0, M['st_cream'], g=GB, go=GB, collide=False, grime=False,
                 faces={3: row(16.0, 4, 1.1, 3.4, 4.8, S['plain'])}, roof_kw=dict(parapet=0.3))
    # street frontage further NW (both sides), closing the view down the street
    for (x0, x1, y0, y1, h, c, face) in ((-112.0, -84.0, -20.0, -8.4, 7.2, 'st_white', 2), (-138.0, -114.0, -21.0, -8.6, 9.5, 'st_cream', 2),
                                          (-162.0, -140.0, -22.0, -8.8, 6.5, 'st_yellow', 2), (-170.0, -158.0, -8.0, 30.0, 10.0, 'st_white', 1),
                                          (-160.0, -144.0, 6.0, 16.0, 6.0, 'st_peach', 0)):
        n = max(2, int(abs((x1 - x0) if face % 2 == 0 else (y1 - y0)) / 3.2))
        L = (x1 - x0) if face % 2 == 0 else (y1 - y0)
        box_building(rect(x0, x1, y0, y1), z0, h, M[c], g=GB, go=GB, collide=False, grime=False, roof=None,
                     faces={face: row(L, n, 1.2, 1.1, 2.6, S['plain_sh']) + row(L, n, 1.2, 4.0, 5.5, S['plain_sh'])})
        hip_roof((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, 0.0, h, 2.6, over=0.5, g=GB)


# ------------------------------------------------------------------------------------------------
# NE side
# ------------------------------------------------------------------------------------------------

def sports_centre():
    """Sportski centar 'Franko Mileta': gray clad box with glass corner, dark glazed balcony box, handball
    figure and lettering; the big barrel-roofed hall behind."""
    z0 = 0.12
    x0, x1, yf, yb = -64.0, -43.0, 18.0, 34.0
    H = 10.6
    L = x1 - x0
    front = [Op(4.6, 13.0, 0.0, 3.2, S['shopfront']), Op(15.0, 17.5, 0.0, 2.8, S['shopfront'])]
    east = [Op(1.5, 3.5, 0.0, 9.8, S['curtainwall']), Op(6.0, 14.0, 7.2, 9.0, S['ribbon'])]
    west = [Op(1.5, 8.0, 6.0, 9.2, S['ribbon']), Op(4.0, 6.0, 0.0, 2.6, S['shopfront'])]
    # edges: 0 front (y=18, p0 x0->x1), 1 east (x1), 2 back, 3 west (x0, p0 = (x0,34) -> (x0,18))
    walls = box_building(rect(x0, x1, yf, yb), z0, H, M['cladding'], faces={0: front, 1: east, 3: west},
                         base=(0.25, M['concrete_dark']), roof_kw=dict(parapet=0.4, cap=M['parapet'], wall=M['cladding']))
    w = walls[0]
    mb = G[GD]
    # glass corner volume (NW corner, full height)
    gx0, gx1, gy0, gy1 = x0 - 0.35, x0 + 4.2, yf - 0.35, yf + 7.0
    G[GD].box_mm(gx0, gx1, gy0, gy1, z0, z0 + H + 0.3, M['glass_blue'])
    for x in [gx0 + k * (gx1 - gx0) / 4 for k in range(5)]:
        mb.box((x, gy0 - 0.03, z0 + (H + 0.3) / 2), (0.08, 0.08, H + 0.3), M['frame_dark'])
    for y in [gy0 + k * (gy1 - gy0) / 6 for k in range(7)]:
        mb.box((gx0 - 0.03, y, z0 + (H + 0.3) / 2), (0.08, 0.08, H + 0.3), M['frame_dark'])
    for z in (0.0, 3.4, 6.9, H + 0.3):
        mb.box(((gx0 + gx1) / 2, gy0 - 0.03, z0 + z), (gx1 - gx0, 0.1, 0.12), M['frame_dark'])
        mb.box((gx0 - 0.03, (gy0 + gy1) / 2, z0 + z), (0.1, gy1 - gy0, 0.12), M['frame_dark'])
    # it stands 0.35 m proud of the building's footprint (+ frames): its own collider, or players clip into the glass
    collider_mm('bld', gx0 - 0.08, gx1, gy0 - 0.08, gy1, z0 - 0.5, z0 + H + 0.3)
    # dark glazed box with a balcony (protrudes from the facade)
    bx0, bx1 = x0 + 4.8, x0 + 10.6
    mb.box_mm(bx0, bx1, yf - 1.3, yf, z0 + 4.3, z0 + 8.6, M['glass_dark'])
    mb.box_mm(bx0 - 0.15, bx1 + 0.15, yf - 1.45, yf, z0 + 8.6, z0 + 8.85, M['frame_dark'])
    mb.box_mm(bx0 - 0.15, bx1 + 0.15, yf - 1.45, yf, z0 + 4.05, z0 + 4.3, M['frame_dark'])
    for k in range(6):
        x = bx0 + k * (bx1 - bx0) / 5
        mb.box((x, yf - 1.31, z0 + 6.45), (0.06, 0.04, 4.3), M['frame_dark'])
    mb.box_mm(bx0, bx1, yf - 1.42, yf - 1.36, z0 + 4.3, z0 + 5.35, M['glass_blue'])
    mb.box_mm(bx0, bx1, yf - 1.44, yf - 1.34, z0 + 5.35, z0 + 5.42, M['metal'])
    collider_mm('bld', bx0 - 0.15, bx1 + 0.15, yf - 1.45, yf, z0 + 4.05, z0 + 8.85)
    # entrance canopy band over the ground-floor glazing
    mb.box_mm(x0 + 4.4, x0 + 17.8, yf - 1.6, yf, z0 + 3.25, z0 + 3.55, M['cladding_light'])
    collider_mm('canopy', x0 + 4.4, x0 + 17.8, yf - 1.6, yf, z0 + 3.25, z0 + 3.55)
    for x in (x0 + 4.6, x0 + 17.6):
        mb.pole((x, yf - 1.45), z0, z0 + 3.25, 0.06, M['metal'])
        collider('pole', (x, yf - 1.45, z0 + 1.6), (0.12, 0.12, 3.3))
    # lettering and handball figure on the facade, CK logo on the ground-floor glass
    dec = G['Buildings.decals']
    dec.card(w.W(13.2, 4.75, 0.015), w.d, (0, 0, 1), 5.6, 1.6, M['sports_text'])
    dec.card(w.W(18.0, 6.9, 0.015), w.d, (0, 0, 1), 5.8, 5.8, M['handball'])
    dec.card(w.W(8.0, 1.6, -0.13), w.d, (0, 0, 1), 1.2, 1.2, M['ck'])
    # panel joints on the cladding
    for k in range(1, 7):
        w.box(mb, k * L / 7, H / 2 + 1.7, 0.005, 0.03, H - 3.6, 0.01, M['metal_dark'])
    # big hall behind (barrel roof)
    hx0, hx1, hy0, hy1 = -81.0, -45.0, 34.4, 88.0
    box_building(rect(hx0, hx1, hy0, hy1), z0, z0 + 8.5, M['cladding_light'], collide=False, roof=None,
                 faces={1: [Op(4.0, 50.0, 6.0, 8.0, S['ribbon'])], 3: [Op(4.0, 50.0, 6.0, 8.0, S['ribbon'])]})
    barrel_roof(hx0, hx1, hy0, hy1, z0 + 8.5, 5.0, wall=M['cladding_light'])
    collider_mm('bld', hx0, hx1, hy0, hy1, 0, 14)


def red_school():
    """3-storey rust-red school with a limestone plinth and hipped tile roof (SE end x = -74.1)."""
    z0 = 0.12
    x0, x1, y0, y1 = -142.0, -74.1, 18.2, 34.8
    H = 11.6
    lv = [(1.5, 3.3), (5.1, 6.9), (8.5, 10.3)]
    front = floors(x1 - x0, 20, 1.25, lv, S['school'], margin=0.8)
    se = floors(y1 - y0, 4, 1.25, lv, S['school'], margin=0.6)
    se = [o for o in se if not (o.v0 < 3 and 1 < (o.u0 + o.u1) / 2 < 8)]
    se.append(Op(3.2, 4.8, 0.4, 3.4, S['annex_door']))
    walls = box_building(rect(x0, x1, y0, y1), z0, H, M['st_red'], faces={0: front, 1: se},
                         base=(1.0, M['stonebase']), roof=None)
    for wi in walls[:2]:
        wi.box(G[GD], wi.L / 2, 4.4, 0.04, wi.L, 0.18, 0.08, M['st_cream'])
    hip_roof((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, 0.0, z0 + H, 4.4, over=0.7, soffit=M['st_cream'])
    G[GR].box((x1 - 9.0, 27.0, z0 + H + 3.6), (0.9, 0.9, 3.0), M['st_red'])
    G[GR].box((x1 - 9.0, 27.0, z0 + H + 5.15), (1.1, 1.1, 0.14), M['concrete'])
    # back wing (L-shape)
    box_building(rect(-112.0, -96.0, 34.8, 62.0), z0, H, M['st_red'], g=GB, go=GB, collide=False, roof=None, grime=False,
                 faces={1: floors(27.2, 7, 1.2, lv, S['school'])})
    hip_roof(-104.0, 48.4, 16.0, 27.2, 0.0, z0 + H, 4.4, over=0.7, g=GB, soffit=M['st_cream'])
    # stone entrance steps on the SE gable
    w = walls[1]
    for i in range(3):
        w.box(G[GD], 4.0, 0.07 + i * 0.13, 0.9 - i * 0.3, 2.6 - i * 0.2, 0.14, 1.8 - i * 0.6, M['stonebase'])


def fina_and_background():
    """buildings above the park (FINA, Erste), the white apartment block, the yellow houses on the hill
    above the retaining wall, and the mine headframe."""
    zp = 2.8
    # FINA: white 2-storey with a glazed round corner
    x0, x1, y0, y1 = 22.0, 35.0, 33.0, 47.0
    H = zp + 8.2
    walls = box_building(rect(x0, x1, y0, y1), zp, H, M['st_white'],
                         faces={0: [Op(6.0, 12.0, 0.8, 2.8, S['ribbon']), Op(6.0, 12.0, 4.6, 6.8, S['ribbon'])],
                                1: [Op(2.0, 12.0, 4.6, 6.8, S['ribbon'])]},
                         base=(0.4, M['concrete']), roof=None)
    hip_roof((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, 0.0, H, 2.6, over=0.6)
    G['Props.signs'].card(walls[0].W(9.0, 7.6, 0.02), walls[0].d, (0, 0, 1), 2.6, 0.8, M['sign_fina'])
    rx, ry, rr = 24.7, 35.5, 4.4
    G[GD].cyl((rx, ry, zp + 3.6), rr, 7.2, M['glass_blue'], seg=28)
    G[GD].cyl((rx, ry, zp + 7.35), rr + 0.2, 0.3, M['st_white'], seg=28)
    G[GD].cyl((rx, ry, zp + 7.9), rr - 0.2, 0.8, M['flatroof_light'], seg=28, r2=rr - 1.4)
    for k in range(18):
        a = k / 18 * math.tau
        G[GD].pole((rx + math.cos(a) * (rr + 0.02), ry + math.sin(a) * (rr + 0.02)), zp, zp + 7.2, 0.05, M['frame_alu'], seg=4)
    collider('bld', (rx, ry, zp + 3.6), (2 * rr, 2 * rr, 7.4))
    # Erste: cream 3-storey, hipped red roof (no logo)
    box_building(rect(1.5, 14.5, 40.0, 60.0), 3.2, 3.2 + 10.0, M['st_cream'], collide=False, roof=None,
                 faces={0: floors(13.0, 4, 1.3, [(1.0, 2.6), (4.2, 5.8), (7.3, 8.9)], S['plain']),
                        3: floors(20.0, 6, 1.3, [(1.0, 2.6), (4.2, 5.8), (7.3, 8.9)], S['plain'])})
    hip_roof(8.0, 50.0, 13.0, 20.0, 0.0, 13.2, 3.0, over=0.6)
    # white 7-storey apartment block with green balconies
    ax0, ax1, ay0, ay1 = -30.9, -17.4, 57.7, 78.5
    lv = [(0.9 + 2.95 * k, 2.4 + 2.95 * k) for k in range(7)]
    box_building(rect(ax0, ax1, ay0, ay1), 3.0, 3.0 + 21.2, M['st_white'], g=GB, go=GB, collide=False, grime=False,
                 faces={0: floors(13.5, 4, 1.4, lv, S['plain_sh']), 1: floors(20.8, 6, 1.4, lv, S['plain_sh'])},
                 roof_kw=dict(parapet=0.5))
    for k in range(1, 7):
        z = 3.0 + 2.95 * k
        G[GB].box_mm(ax0 + 1.0, ax1 - 1.0, ay0 - 1.2, ay0, z - 0.1, z + 0.05, M['concrete'])
        G[GB].box_mm(ax0 + 1.0, ax1 - 1.0, ay0 - 1.2, ay0 - 1.1, z + 0.05, z + 1.0, M['metal_green'])
    # yellow houses with red roofs on the high ground beyond the retaining wall (N-S oriented)
    yaw = math.radians(148.24 - 180)   # long axis north-south
    for (cx, cy, zz) in ((99.0, -30.0, 6.0), (101.0, -2.0, 6.5), (100.0, 26.0, 7.0), (104.0, 54.0, 7.5)):
        pts = orect(cx, cy, 24.0, 8.5, yaw)
        box_building(pts, zz, zz + 7.2, M['st_yellow'], g=GB, go=GB, collide=False, roof=None, grime=False,
                     faces={i: row(24.0 if i % 2 == 0 else 8.5, 6 if i % 2 == 0 else 2, 1.1, 1.0, 2.4, S['plain_sh'])
                            + row(24.0 if i % 2 == 0 else 8.5, 6 if i % 2 == 0 else 2, 1.1, 4.0, 5.4, S['plain_sh'])
                            for i in range(4)})
        hip_roof(cx, cy, 24.0, 8.5, yaw, zz + 7.2, 2.8, over=0.6, g=GB)
    # far houses (backdrop on the hills)
    for (cx, cy, zz, sx, sy, c) in ((92.0, 85.0, 9.0, 16, 10, 'st_cream'), (60.0, 96.0, 7.0, 20, 12, 'st_yellow'),
                                    (-60.0, 120.0, 10.0, 22, 12, 'st_white'), (130.0, 20.0, 14.0, 18, 10, 'st_cream'),
                                    (126.0, -60.0, 12.0, 20, 11, 'st_yellow'), (-130.0, -40.0, 4.0, 24, 12, 'st_cream'),
                                    (-150.0, 60.0, 8.0, 18, 10, 'st_peach')):
        box_building(rect(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2), zz, zz + 7.5, M[c], g=GB, go=GB, collide=False,
                     roof=None, grime=False, faces={0: row(sx, int(sx / 3), 1.1, 1.0, 2.4, S['plain']) +
                                                    row(sx, int(sx / 3), 1.1, 4.0, 5.4, S['plain'])})
        hip_roof(cx, cy, sx, sy, 0.0, zz + 7.5, 2.6, over=0.5, g=GB)
    headframe(19.6, -137.5, -2.0)


def headframe(x, y, z):
    """green lattice mine headframe (Labin coal mine 'Pijacal' shaft tower), ~35 m."""
    mb = G[GB]
    m = M['metal_green']
    H = 32.0
    b0, b1 = 4.0, 1.9
    levels = 9
    corners = lambda t: [((-1) ** (k // 2) * (b0 + (b1 - b0) * t), (-1) ** ((k + 1) // 2) * (b0 + (b1 - b0) * t)) for k in range(4)]
    for k in range(4):
        c0, c1 = corners(0)[k], corners(1)[k]
        mb.tube([(x + c0[0], y + c0[1], z), (x + c1[0], y + c1[1], z + H)], 0.22, m, seg=6, smooth=False)
    for lv in range(levels):
        t0, t1 = lv / levels, (lv + 1) / levels
        A, B = corners(t0), corners(t1)
        for k in range(4):
            j = (k + 1) % 4
            p = (x + A[k][0], y + A[k][1], z + H * t0)
            q = (x + A[j][0], y + A[j][1], z + H * t0)
            r = (x + B[j][0], y + B[j][1], z + H * t1)
            s = (x + B[k][0], y + B[k][1], z + H * t1)
            mb.tube([p, q], 0.08, m, seg=4, smooth=False)
            mb.tube([p, r], 0.06, m, seg=4, smooth=False)
            mb.tube([q, s], 0.06, m, seg=4, smooth=False)
    # head platform, sheave wheels, inclined back legs
    mb.box((x, y, z + H + 0.3), (b1 * 2 + 1.6, b1 * 2 + 1.6, 0.4), m)
    for s in (-1.1, 1.1):
        pts = [(x + s, y + math.cos(a) * 2.4, z + H + 2.6 + math.sin(a) * 2.4) for a in (k / 20 * math.tau for k in range(21))]
        mb.tube(pts, 0.1, M['metal_dark'], seg=4, smooth=False)
        mb.tube([(x + s, y - 2.4, z + H + 2.6), (x + s, y + 2.4, z + H + 2.6)], 0.06, M['metal_dark'], seg=4)
    mb.box((x, y, z + H + 1.4), (0.3, 2.0, 2.2), m)
    for s in (-1, 1):
        mb.tube([(x + s * 2.0, y + 18.0, z), (x + s * b1, y + b1, z + H - 2)], 0.3, m, seg=6, smooth=False)
    # hoist house
    mb.box((x, y + 22.0, z + 5.0), (12.0, 9.0, 10.0), M['st_cream'])
    mb.box((x, y + 22.0, z + 10.2), (12.6, 9.6, 0.4), M['flatroof'])


def build():
    styles()
    admin_block()
    annex()
    stone_wall_block()
    teal_building()
    nw_corner_sw()
    sports_centre()
    red_school()
    fina_and_background()
