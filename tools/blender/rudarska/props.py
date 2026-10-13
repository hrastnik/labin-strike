"""Reusable props: vehicles, trees, lamps, signs, street furniture.  Each function writes into the
shared group builders (lib.G) and, where it matters for gameplay, adds colliders."""
import math

import bmesh
from mathutils import Matrix, Vector

from . import hulls
from .lib import G, collider, collider_seg, rng, rot2, v3
from .palette import M

# ------------------------------------------------------------------------------------------------
# vehicles
# ------------------------------------------------------------------------------------------------
CAR_KINDS = {
    #          L     W     H     wb    belt  hood  nose  cab_f  cab_r  roof_f roof_r  style
    'hatch': (4.05, 1.76, 1.48, 2.55, 0.96, 0.86, 0.66, 0.70, -1.62, 0.02, -1.48, 'hatch'),
    'small': (3.65, 1.66, 1.50, 2.40, 0.97, 0.86, 0.66, 0.62, -1.48, -0.02, -1.36, 'hatch'),
    'sedan': (4.65, 1.81, 1.45, 2.75, 0.95, 0.84, 0.64, 0.82, -1.20, 0.08, -0.66, 'sedan'),
    'wagon': (4.70, 1.81, 1.50, 2.75, 0.96, 0.85, 0.64, 0.80, -2.02, 0.06, -1.94, 'wagon'),
    'suv':   (4.45, 1.84, 1.66, 2.65, 1.06, 0.98, 0.76, 0.74, -1.88, 0.02, -1.74, 'hatch'),
    'van':   (4.75, 1.90, 1.90, 2.90, 1.08, 1.00, 0.78, 1.15, -2.30, 0.62, -2.26, 'van'),
}
KIND_WEIGHTS = [('hatch', 30), ('small', 14), ('sedan', 16), ('wagon', 16), ('suv', 20), ('van', 4)]
PAINT_WEIGHTS = [0, 0, 0, 1, 1, 2, 2, 3, 4, 4, 5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 2, 3, 5, 6, 0, 1, 4, 9]


def pick_kind():
    t = rng.uniform(0, sum(w for _, w in KIND_WEIGHTS))
    for k, w in KIND_WEIGHTS:
        t -= w
        if t <= 0:
            return k
    return 'hatch'


def _round(mb, faces, fl, fr, r, m):
    """bevel the shoulder edges of a lofted body (side cap <-> strip) and smooth-shade it."""
    edges = list(set(fl.edges) | set(fr.edges))
    res = bmesh.ops.bevel(mb.bm, geom=edges, offset=r, offset_type='OFFSET', segments=3, profile=0.5, affect='EDGES',
                          clamp_overlap=True)
    idx = mb.mi(m)
    for f in res['faces']:
        f.material_index = idx
    out = [f for f in faces if f.is_valid] + [f for f in (fl, fr) if f.is_valid] + list(res['faces'])
    for f in out:
        f.smooth = True
    return out


MODEL_CARS = True     # instanced Blender-modelled cars (tools/blender/cars -> cars.glb) instead of the box cars


def car(x, y, yaw, z=0.0, kind=None, paint=None, collide=True, g='Vehicles.cars'):
    """procedural car; origin = ground centre, faces +X locally (yaw rotates)."""
    kind = kind or pick_kind()
    if MODEL_CARS:
        return model_car(x, y, yaw, z, kind, paint, collide)
    L, W, H, wb, belt, hood, nose, cab_f, cab_r, roof_f, roof_r, style = CAR_KINDS[kind]
    paint = paint if paint is not None else M['car_paints'][rng.choice(PAINT_WEIGHTS)]
    mb = G[g]
    hl, hw = L / 2, W / 2
    at = (x, y, z)

    def P(lx, ly, lz):
        rx, ry = rot2(lx, ly, yaw)
        return (x + rx, y + ry, z + lz)

    # lower body side profile (x forward, z up)
    rear_deck = belt + (0.02 if style in ('hatch', 'wagon', 'van') else 0.04)
    prof = [
        (hl - 0.06, 0.34), (hl, 0.44), (hl + 0.01, 0.56), (hl - 0.02, nose), (hl - 0.18, nose + 0.08),
        (hl - 0.55, hood - 0.02), (cab_f + 0.08, hood + 0.04), (cab_f, belt),
        (cab_r, belt), (-hl + 0.12, rear_deck), (-hl, rear_deck - 0.14), (-hl - 0.01, 0.56), (-hl, 0.42), (-hl + 0.08, 0.32),
    ]
    if style == 'sedan':
        prof[8] = (cab_r, belt)
        prof.insert(9, (-hl + 0.35, belt + 0.03))
    faces, fl, fr = mb.loft(prof, hw, paint, taper=lambda zz: 1.0 - max(0.0, zz - 0.62) * 0.12, yaw=yaw, at=at)
    _round(mb, faces, fl, fr, 0.09, paint)
    # glasshouse
    gh = [(cab_f, belt), (roof_f, H), (roof_r, H), (cab_r + (0.06 if style != 'sedan' else 0.0), belt)]
    if style == 'van':
        gh = [(cab_f, belt), (roof_f, H), (roof_r, H), (cab_r + 0.02, belt)]
    gfaces, gl, gr = mb.loft(gh, hw - 0.03, M['car_glass'], taper=lambda zz: 1.0 - max(0.0, zz - belt) / max(0.3, H - belt) * 0.16,
                             yaw=yaw, at=at)
    gall = _round(mb, gfaces, gl, gr, 0.06, M['car_glass'])
    for f in gall:
        f.normal_update()
        if f.normal.z > 0.6 and f.calc_center_median().z > z + H - 0.12:
            f.material_index = mb.mi(paint)
    # pillars (A: along the windscreen edges, B: middle of the side glass, C: rear)
    tw = (hw - 0.03) * 0.84
    for s in (-1, 1):
        a0, a1 = P(cab_f, s * (hw - 0.04), belt), P(roof_f, s * tw, H - 0.01)
        mb.tube([a0, a1], 0.045, paint, seg=4, smooth=False)
        bx = (cab_f + cab_r) / 2 + (0.15 if style != 'van' else 0.4)
        mb.tube([P(bx, s * (hw - 0.025), belt), P(bx - 0.06, s * (tw + 0.005), H - 0.01)], 0.05, M['car_trim'], seg=4, smooth=False)
        c0, c1 = P(cab_r + 0.05, s * (hw - 0.04), belt), P(roof_r, s * tw, H - 0.01)
        mb.tube([c0, c1], 0.07 if style in ('hatch', 'wagon') else 0.05, paint, seg=4, smooth=False)
        # mirrors
        mb.box(P(cab_f - 0.1, s * (hw + 0.08), belt + 0.08), (0.12, 0.16, 0.11), M['car_trim'], rz=yaw)
        # sill trim
        mb.box(P(0, s * (hw - 0.01), 0.36), (L * 0.62, 0.04, 0.09), M['car_trim'], rz=yaw)
        # door handles
        for hx in ((cab_f + bx) / 2 - 0.1, (bx + cab_r) / 2):
            mb.box(P(hx, s * (hw + 0.005), belt - 0.1), (0.16, 0.025, 0.03), M['car_trim'], rz=yaw)
    # wheels
    for sx in (-1, 1):
        for s in (-1, 1):
            # tyre and rim sit >= 2 cm inside the body side, which covers their upper half (no z-fighting)
            cx, cy = wb / 2 * sx - (0.05 if sx > 0 else -0.05), s * (hw - 0.16)
            wp = P(cx, cy, 0.32)
            mb.cyl(wp, 0.32, 0.22, M['rubber'], seg=14, rx=math.pi / 2, rz=yaw)
            mb.cyl(P(cx, s * (hw - 0.04), 0.32), 0.21, 0.02, M['rim'], seg=10, rx=math.pi / 2, rz=yaw)
            # dark wheel-arch liner hides the body/wheel intersection
            mb.box(P(cx, s * (hw - 0.07), 0.62), (0.86, 0.06, 0.14), M['car_trim'], rz=yaw)
    # lights, grille, bumpers, plates
    for s in (-1, 1):
        mb.box(P(hl - 0.02, s * (hw - 0.28), nose - 0.04), (0.06, 0.34, 0.11), M['headlight'], rz=yaw)
        mb.box(P(-hl + 0.0, s * (hw - 0.22), rear_deck - 0.2), (0.05, 0.3, 0.13), M['taillight'], rz=yaw)
    mb.box(P(hl + 0.0, 0, nose - 0.12), (0.04, W * 0.42, 0.13), M['car_trim'], rz=yaw)
    mb.box(P(hl - 0.03, 0, 0.38), (0.1, W - 0.06, 0.14), M['car_trim'], rz=yaw)
    mb.box(P(-hl + 0.03, 0, 0.38), (0.1, W - 0.06, 0.14), M['car_trim'], rz=yaw)
    for sx, zz in ((1, 0.47), (-1, 0.62)):
        cpos = Vector(P(sx * (hl + 0.025), 0, zz))
        right = Vector((*rot2(0, -sx, yaw), 0))
        mb.card(cpos, right, (0, 0, 1), 0.52, 0.115, M['plate'])
    # soft contact shadow
    G['Ground.decals'].card((x, y, z + 0.015), (*rot2(1, 0, yaw), 0), (*rot2(0, 1, yaw), 0), L + 0.5, W + 0.6, M['blob'])
    if collide:
        cx, cy = rot2((cab_f + cab_r) / 2, 0, yaw)
        collider('car', (x, y, z + belt / 2 + 0.06), (L - 0.1, W - 0.05, belt - 0.12), rz=yaw)
        collider('car', (x + cx, y + cy, z + (belt + H) / 2), (cab_f - cab_r, W - 0.25, H - belt), rz=yaw)
    return kind


_car_serial = [0]


def model_car(x, y, yaw, z, kind, paint, collide):
    """placement marker CAR_<n> (extras: model, paint colour) for the client's instanced cars, plus the blob shadow
    and convex-hull colliders cut from the model itself (hulls.car_pieces)."""
    from cars import specs as car_specs
    from .lib import marker
    _car_serial[0] += 1
    opts = car_specs.KIND_MODEL[kind]
    name = opts[_car_serial[0] % len(opts)]
    d = car_specs.dims(name)
    paint = paint if paint is not None else M['car_paints'][rng.choice(PAINT_WEIGHTS)]
    col = list(paint.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)[:3]
    ob = marker(f'CAR_{_car_serial[0]:03d}', (x, y, z))
    ob.rotation_euler = (0, 0, yaw)
    ob['car'] = name
    ob['paint'] = [round(c, 4) for c in col]
    ob['plate'] = _car_serial[0] % 4          # (no rng draw: keeps the rest of the map's random layout unchanged)
    L, W, belt = d['L'], d['W'], d['belt']
    G['Ground.decals'].card((x, y, z + 0.015), (*rot2(1, 0, yaw), 0), (*rot2(0, 1, yaw), 0), L + 0.5, W + 0.6, M['blob'])
    if collide:
        hulls.car_colliders(name, belt, x, y, z, yaw)
    return kind


def box_truck(x, y, yaw, z=0.0):
    """white box truck (parked on the lot side near the SE end)."""
    mb = G['Vehicles.cars']

    def P(lx, ly, lz):
        rx, ry = rot2(lx, ly, yaw)
        return (x + rx, y + ry, z + lz)
    L, W = 7.2, 2.35
    # cargo box
    mb.box(P(-0.9, 0, 2.05), (5.2, W, 2.5), M['truck_box'], rz=yaw)
    mb.box(P(-0.9, W / 2 + 0.005, 1.0), (5.2, 0.01, 0.12), M['truck_stripe'], rz=yaw)
    mb.box(P(-0.9, -W / 2 - 0.005, 1.0), (5.2, 0.01, 0.12), M['truck_stripe'], rz=yaw)
    mb.box(P(-3.48, 0, 2.05), (0.04, W - 0.1, 2.3), M['frame_alu'], rz=yaw)
    # cab
    cab = [(2.9, 0.55), (2.95, 1.3), (2.65, 2.55), (1.75, 2.62), (1.65, 0.55)]
    mb.loft(cab, W / 2 - 0.05, M['truck_box'], yaw=yaw, at=(x, y, z))
    mb.box(P(2.83, 0, 2.0), (0.22, W - 0.3, 0.75), M['car_glass'], rz=yaw, ry=-0.32)
    for s in (-1, 1):
        mb.box(P(2.2, s * (W / 2 - 0.04), 1.95), (0.8, 0.02, 0.6), M['car_glass'], rz=yaw)
        mb.box(P(2.95, s * (W / 2 + 0.12), 1.8), (0.06, 0.08, 0.35), M['car_trim'], rz=yaw)
    mb.box(P(-0.6, 0, 0.6), (6.4, 1.0, 0.25), M['metal_dark'], rz=yaw)  # chassis
    mb.box(P(2.95, 0, 0.6), (0.12, W - 0.1, 0.28), M['car_trim'], rz=yaw)
    for lx in (2.0, -2.0, -2.9):
        for s in (-1, 1):
            mb.cyl(P(lx, s * (W / 2 - 0.25), 0.45), 0.45, 0.32, M['rubber'], seg=14, rx=math.pi / 2, rz=yaw)
            mb.cyl(P(lx, s * (W / 2 - 0.08), 0.45), 0.26, 0.02, M['rim'], seg=10, rx=math.pi / 2, rz=yaw)
    for s in (-1, 1):
        mb.box(P(2.94, s * 0.85, 0.95), (0.04, 0.3, 0.16), M['headlight'], rz=yaw)
        mb.box(P(-3.52, s * 0.95, 0.75), (0.04, 0.22, 0.12), M['taillight'], rz=yaw)
    G['Ground.decals'].card((x, y, z + 0.015), (*rot2(1, 0, yaw), 0), (*rot2(0, 1, yaw), 0), L + 0.6, W + 0.8, M['blob'])
    collider('truck', P(-0.9, 0, 1.85), (5.3, W, 3.1), rz=yaw)
    collider('truck', P(2.25, 0, 1.4), (1.4, W - 0.1, 2.2), rz=yaw)


def _se(t, n):
    """superellipse coordinate sign(t) |t|^(2/n): n = 2 is an ellipse, larger n squarer."""
    return math.copysign(abs(t) ** (2 / n), t)


def _sweep(mb, T, secs, m, seg=16, n=2.0, closed=False, warp=None, smooth=True):
    """smooth closed shell through cross-sections (c, u, v, a, b[, d]) in a local frame: a superellipse (exponent n)
    with half-axes a along u and b along v around c, its u-extremes pulled back along -v by d (a legshield's wrap,
    a fender's skirt).  closed: the sections form a loop (a tyre), else the ends get flat caps.  warp(p) bends the
    local points, T maps them to world.  Returns the rings of verts."""
    bm = mb.bm
    rings = []
    for sec in secs:
        c, u, v, a, b = (Vector(sec[0]), Vector(sec[1]), Vector(sec[2]), sec[3], sec[4])
        d = sec[5] if len(sec) > 5 else 0.0
        ring = []
        for k in range(seg):
            t = k / seg * math.tau
            p = c + u * (a * _se(math.cos(t), n)) + v * (b * _se(math.sin(t), n) - d * math.cos(t) ** 2)
            ring.append(bm.verts.new(T(warp(p) if warp else p)))
        rings.append(ring)
    faces = []
    for i in range(len(rings) if closed else len(rings) - 1):
        A, B = rings[i], rings[(i + 1) % len(rings)]
        for k in range(seg):
            faces.append(bm.faces.new((A[k], A[(k + 1) % seg], B[(k + 1) % seg], B[k])))
    mb._tag(faces, m, smooth)
    if not closed:
        caps = [bm.faces.new(rings[0]), bm.faces.new(rings[-1])]
        mb._tag(caps, m, False)
        faces += caps
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return rings


def _pod(mb, T, c, w, m, n=2.0, seg=10, k=5):
    """ellipsoid around c: half-axes w = (dx, dy, dz) in the local frame (lamp lenses, the mirror heads)."""
    c = Vector(c)
    secs = []
    for i in range(k):
        th = math.pi * (i + 0.5) / k
        s = math.sin(th)
        secs.append((c + Vector((0, 0, -math.cos(th) * w[2])), (1, 0, 0), (0, 1, 0), w[0] * s, w[1] * s))
    return _sweep(mb, T, secs, m, seg=seg, n=n)


def scooter(x, y, yaw, z=0.0):
    """a Vespa-style step-through scooter (proportions of a Primavera 125: 1.85 m long, 1.33 m wheelbase, 11" / 10"
    wheels), parked on its centre stand.  Local frame: +X forward, +Y left, origin on the ground mid-wheelbase.
    Engine and exhaust on the right, as on the real thing."""
    mb = G['Vehicles.cars']
    paint, seat, trim = M['car_paints'][0], M['scooter_seat'], M['car_trim']
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)

    def T(p):
        rx, ry = rot2(p[0], p[1], yaw)
        return Vector((x + rx, y + ry, z + p[2]))

    def tube(pts, r, m, seg=8):
        mb.tube([T(p) for p in pts], r, m, seg=seg)

    def disc(c, r, h, m, axis, seg=16):
        rot = axis if isinstance(axis, dict) else {'x': dict(ry=math.pi / 2), 'y': dict(rx=math.pi / 2)}[axis]
        return mb.cyl(T(c), r, h, m, seg=seg, rz=yaw, **rot)

    # -- wheels: tyre (squarish torus), rim, hub ---------------------------------------------------------------
    tyres = []
    for wx, r, w in ((0.667, 0.215, 0.11), (-0.667, 0.21, 0.12)):
        tr = 0.06
        secs = []
        for i in range(24):
            ph = i / 24 * math.tau
            rad = Vector((math.cos(ph), 0, math.sin(ph)))
            secs.append((Vector((wx, 0, r)) + rad * (r - tr), Y, rad, w / 2, tr))
        tyres.append(_sweep(mb, T, secs, M['rubber'], seg=10, n=2.8, closed=True))
        disc((wx, 0, r), r - 0.075, w - 0.02, M['rim'], 'y', seg=18)
        disc((wx, 0, r), 0.045, w + 0.03, M['metal_dark'], 'y', seg=10)
    # front: brake disc + caliper on the right, the single-sided link and shock on the left
    disc((0.667, -0.06, 0.215), 0.1, 0.006, M['metal'], 'y', seg=18)
    mb.box(T((0.6, -0.068, 0.27)), (0.07, 0.03, 0.05), trim, rz=yaw)
    tube([(0.667, 0.07, 0.215), (0.61, 0.08, 0.44)], 0.024, M['metal_dark'])
    tube([(0.64, 0.085, 0.24), (0.585, 0.09, 0.45)], 0.016, M['chrome'])

    # -- front fender: a hood over the wheel, skirted down at the sides ---------------------------------------
    secs = []
    for i, deg in enumerate(range(122, 14, -12)):
        ph = math.radians(deg)
        rad = Vector((math.cos(ph), 0, math.sin(ph)))
        f = math.sin(math.pi * (i + 0.5) / 10) ** 0.4
        secs.append((Vector((0.667, 0, 0.215)) + rad * 0.278, Y, rad, 0.125 * f, 0.035 * f + 0.01, 0.075 * f))
    fender = _sweep(mb, T, secs, paint, seg=16, n=2.4)
    tube([(0.62, 0, 0.46), (0.5, 0, 0.56), (0.43, 0, 0.62)], 0.028, M['metal_dark'])   # fork up into the legshield

    # -- legshield: curved panel wrapping back at the sides, chrome-edged, with the horn cover down the front ----
    LS = [(0.25, 0.39, 0.19, 0.035, 0.05), (0.32, 0.395, 0.215, 0.035, 0.06), (0.46, 0.405, 0.225, 0.035, 0.065),
          (0.6, 0.415, 0.215, 0.035, 0.06), (0.72, 0.425, 0.185, 0.035, 0.05), (0.81, 0.44, 0.14, 0.035, 0.035),
          (0.87, 0.452, 0.095, 0.035, 0.02), (0.93, 0.462, 0.06, 0.035, 0.01)]
    legshield = _sweep(mb, T, [((xc, 0, zz), Y, X, a, b, d) for zz, xc, a, b, d in LS], paint, seg=20, n=2.2)
    for s in (-1, 1):
        tube([(xc - d + 0.004, s * a, zz) for zz, xc, a, b, d in LS], 0.009, M['chrome'], seg=6)
    _sweep(mb, T, [((0.45, 0, 0.5), Y, X, 0.02, 0.015), ((0.458, 0, 0.56), Y, X, 0.04, 0.02),
                   ((0.47, 0, 0.74), Y, X, 0.035, 0.02), ((0.482, 0, 0.88), Y, X, 0.025, 0.018)], paint, seg=12, n=2.6)
    for i in range(3):
        zz = 0.6 + i * 0.035
        tube([(0.476, -0.03, zz - 0.012), (0.484, 0, zz), (0.476, 0.03, zz - 0.012)], 0.006, M['chrome'], seg=5)
    for s in (-1, 1):                                                          # front indicators on the legshield
        _pod(mb, T, (0.425, s * 0.155, 0.64), (0.018, 0.026, 0.05), M['indicator'], 3.0)

    # -- floorboard: painted tray, black mat with rubber strips ---------------------------------------------
    floor = _sweep(mb, T, [((xx, 0, 0.24), Y, Z, a, 0.05) for xx, a in
                           ((-0.44, 0.14), (-0.4, 0.17), (0.3, 0.17), (0.38, 0.17), (0.41, 0.14))], paint, seg=16, n=4.0)
    mb.box(T((0.08, 0, 0.292)), (0.58, 0.3, 0.012), M['plastic_black'], rz=yaw)
    for i in range(5):
        mb.box(T((0.08, -0.12 + i * 0.06, 0.3)), (0.54, 0.03, 0.01), M['rubber'], rz=yaw)

    # -- rear body: the bulbous cowl (pear-shaped section, narrower under the seat), seat, rack, tail light -----
    CW = [(-0.965, 0.56, 0.61, 0.04), (-0.94, 0.5, 0.66, 0.12), (-0.88, 0.43, 0.7, 0.21), (-0.78, 0.37, 0.725, 0.28),
          (-0.64, 0.325, 0.73, 0.315), (-0.5, 0.305, 0.73, 0.32), (-0.36, 0.295, 0.73, 0.29), (-0.24, 0.285, 0.725, 0.23),
          (-0.15, 0.28, 0.71, 0.175), (-0.1, 0.29, 0.695, 0.145), (-0.07, 0.31, 0.67, 0.1), (-0.055, 0.34, 0.64, 0.05)]

    def pear(p):
        """narrower towards the seat; the front leans forward at the top (the rider's knee panel)"""
        lean = 0.1 * max(0.0, min(1.0, (p.x + 0.34) / 0.25)) * (p.z - 0.3) / 0.4
        return Vector((p.x + lean, p.y * (1 - 0.3 * max(0.0, (p.z - 0.33) / 0.4) ** 2), p.z))
    cowl = _sweep(mb, T, [((xx, 0, (lo + hi) / 2), Y, Z, a, (hi - lo) / 2) for xx, lo, hi, a in CW], paint,
                  seg=24, n=2.6, warp=pear)
    ST = [(-0.86, 0.745, 0.07, 0.03), (-0.83, 0.755, 0.13, 0.05), (-0.72, 0.76, 0.165, 0.06), (-0.56, 0.76, 0.175, 0.062),
          (-0.4, 0.755, 0.172, 0.06), (-0.24, 0.75, 0.16, 0.057), (-0.12, 0.745, 0.13, 0.052), (-0.04, 0.735, 0.085, 0.04),
          (-0.015, 0.725, 0.04, 0.025)]
    saddle = _sweep(mb, T, [((xx, 0, zc), Y, Z, a, b) for xx, zc, a, b in ST], seat, seg=20, n=3.2)
    rack = [(-0.72, 0.15, 0.735), (-0.84, 0.14, 0.75), (-0.91, 0.085, 0.75), (-0.93, 0, 0.75)]
    tube(rack + [(px, -py, pz) for px, py, pz in reversed(rack[:-1])], 0.011, M['chrome'])
    for s in (-1, 1):
        tube([(-0.72, s * 0.15, 0.735), (-0.71, s * 0.13, 0.68)], 0.01, M['chrome'], seg=6)
    _pod(mb, T, (-0.962, 0, 0.58), (0.025, 0.065, 0.032), M['taillight'], 3.0)
    mb.box(T((-0.945, 0, 0.47)), (0.012, 0.17, 0.12), M['white_paint'], rz=yaw, ry=-0.25)   # licence plate
    mb.box(T((-0.94, 0, 0.53)), (0.03, 0.18, 0.02), trim, rz=yaw)

    # -- under the cowl: engine / transmission case and exhaust on the right, centre stand ------------------
    engine = _sweep(mb, T, [((xx, -0.12, zc), Y, Z, a, b) for xx, zc, a, b in
                            ((-0.8, 0.22, 0.03, 0.05), (-0.74, 0.21, 0.05, 0.08), (-0.55, 0.22, 0.055, 0.09),
                             (-0.36, 0.24, 0.05, 0.08), (-0.26, 0.25, 0.035, 0.05))], M['metal'], seg=12, n=2.6)
    tube([(-0.3, -0.06, 0.16), (-0.42, -0.15, 0.15), (-0.52, -0.2, 0.22)], 0.018, M['metal_dark'])
    muffler = _sweep(mb, T, [((xx, -0.21, zc), Y, Z, a, b) for xx, zc, a, b in
                             ((-0.53, 0.25, 0.035, 0.04), (-0.58, 0.27, 0.055, 0.065), (-0.8, 0.31, 0.055, 0.065),
                              (-0.84, 0.32, 0.04, 0.045))], M['metal_dark'], seg=12, n=2.4)
    tube([(-0.83, -0.21, 0.31), (-0.89, -0.21, 0.32)], 0.014, M['chrome'], seg=8)
    for s in (-1, 1):
        tube([(-0.16, s * 0.1, 0.2), (-0.3, s * 0.13, 0.015)], 0.013, M['metal_dark'], seg=6)
    tube([(-0.3, -0.15, 0.015), (-0.3, 0.15, 0.015)], 0.013, M['metal_dark'], seg=6)

    # -- headset: painted handlebar cover with the round headlight, grips, levers, mirrors, speedo -----------
    head = _sweep(mb, T, [((xx, 0, zc), Y, Z, a, b) for xx, zc, a, b in
                          ((0.38, 1.0, 0.04, 0.03), (0.41, 1.0, 0.09, 0.055), (0.47, 1.0, 0.12, 0.07),
                           (0.54, 0.995, 0.11, 0.075), (0.59, 0.99, 0.09, 0.075), (0.615, 0.985, 0.08, 0.07))],
                  paint, seg=20, n=2.3)
    _sweep(mb, T, [((0.47, yy, 1.0), X, Z, a, b) for yy, a, b in
                   ((-0.29, 0.028, 0.024), (-0.2, 0.045, 0.034), (-0.1, 0.06, 0.045), (0, 0.065, 0.05),
                    (0.1, 0.06, 0.045), (0.2, 0.045, 0.034), (0.29, 0.028, 0.024))], paint, seg=12, n=2.2)
    disc((0.618, 0, 0.985), 0.078, 0.02, M['chrome'], 'x', seg=20)
    disc((0.626, 0, 0.985), 0.066, 0.006, M['headlight'], 'x', seg=20)
    disc((0.41, 0, 1.04), 0.05, 0.012, M['car_glass'], dict(ry=-0.7), seg=14)
    for s in (-1, 1):
        tube([(0.465, s * 0.28, 1.0), (0.465, s * 0.4, 1.0)], 0.019, M['plastic_black'], seg=8)
        disc((0.465, s * 0.405, 1.0), 0.016, 0.012, M['chrome'], 'y', seg=8)
        tube([(0.5, s * 0.27, 1.005), (0.535, s * 0.33, 1.0), (0.525, s * 0.4, 0.99)], 0.006, M['chrome'], seg=5)
        tube([(0.47, s * 0.22, 1.03), (0.46, s * 0.28, 1.12), (0.45, s * 0.34, 1.19)], 0.008, M['chrome'], seg=6)
        _pod(mb, T, (0.45, s * 0.37, 1.215), (0.02, 0.055, 0.04), M['chrome'], 2.2, seg=14)
        _pod(mb, T, (0.437, s * 0.37, 1.215), (0.01, 0.048, 0.034), M['car_glass'], 2.2, seg=14)

    # colliders: front (wheel, fender, legshield, headset), floor, rear (cowl, seat, wheel, engine, exhaust)
    def pts(*parts):
        return [v.co for rings in parts for ring in rings for v in ring]
    hulls.collider_hull('scooter', pts(tyres[0], fender, legshield, head))
    hulls.collider_hull('scooter', pts(floor))
    hulls.collider_hull('scooter', pts(tyres[1], cowl, saddle, engine, muffler))


# ------------------------------------------------------------------------------------------------
# vegetation
# ------------------------------------------------------------------------------------------------

def _rand_unit():
    while True:
        v = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        if 0.05 < v.length <= 1:
            return v.normalized()


Z_UP = Vector((0, 0, 1))


def _facing_card(mb, p, n, size, m, nrm, twist=0.6, aspect=1.0):
    """card centred at p whose face points along n (twigs of the cluster texture towards the inside/down)."""
    n = n.normalized()
    ref = Z_UP if abs(n.z) < 0.92 else Vector((math.cos(rng.uniform(0, math.tau)), math.sin(rng.uniform(0, math.tau)), 0))
    up = (ref - n * ref.dot(n)).normalized()
    right = up.cross(n).normalized()
    a = rng.uniform(-twist, twist)
    up, right = up * math.cos(a) + right * math.sin(a), right * math.cos(a) - up * math.sin(a)
    mb.card(p, right, up, size * aspect, size, m, normal=nrm)


def _inner(leaf):
    """darker twin of a leaf material for the cards deep inside a crown (fake self-shadowing)."""
    from .lib import mat
    key = leaf.name + '_in'
    if key not in M:
        tex = leaf.node_tree.nodes.get('Image Texture').image.filepath
        tex = 'gen/' + tex.replace('\\', '/').split('/')[-1]
        M[key] = mat(leaf.name.replace('_cut', '_in_cut'), diff=tex, alpha=True, rough=0.85, tint=(0.3, 0.34, 0.28))
    return M[key]


def tree_broad(x, y, z, h=11.0, crown=4.0, leaf=None, trunk_h=None, lean=(0, 0), cards=None, collide=True, g='Foliage.trees',
               squash=0.8, trunk_r=None):
    """deciduous tree: curved tapered trunk splitting into limbs, each ending in a clump of leaf-cluster
    cards.  The clumps give the lumpy 'cauliflower' crown silhouette; outer cards face outwards with
    normals pointing away from their clump, inner cards are darker so the crown has depth."""
    leaf = leaf or M['leaf_broad']
    inner = _inner(leaf)
    mb = G[g]
    trunk_h = trunk_h or h * 0.36
    r0 = trunk_r or max(0.15, h * 0.024)
    base = Vector((x, y, z))
    top = Vector((x + lean[0], y + lean[1], z + trunk_h))
    wob = Vector((rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), 0))
    trunk = mb.tube([(x, y, z - 0.25), tuple(base.lerp(top, 0.35) + wob * 0.6 + Vector((0, 0, 0.0))),
                     tuple(base.lerp(top, 0.7) + wob), tuple(top)], r0, M['bark'], seg=9)
    flare = mb.cyl((x, y, z + 0.12), r0 * 1.55, 0.5, M['bark'], seg=9, r2=r0 * 1.02)
    cz = z + trunk_h + (h - trunk_h) * 0.52
    cc = Vector((x + lean[0] * 1.3, y + lean[1] * 1.3, cz))
    rz_ = (h - trunk_h) / 2
    # clumps: one central/top, the rest around the crown
    nk = 4 + int(crown > 3.2) + int(crown > 4.4) + rng.randint(0, 1)
    clumps = [(cc + Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rz_ * 0.35)), crown * 0.62, rz_ * 0.62)]
    a0 = rng.uniform(0, math.tau)
    for k in range(nk - 1):
        a = a0 + k / (nk - 1) * math.tau + rng.uniform(-0.35, 0.35)
        rr = crown * rng.uniform(0.45, 0.62)
        zz = rng.uniform(-0.45, 0.35) * rz_
        clumps.append((cc + Vector((math.cos(a) * rr, math.sin(a) * rr, zz)), crown * rng.uniform(0.44, 0.58), rz_ * rng.uniform(0.5, 0.66)))
    # limbs from the trunk top to each clump (plus a stub towards the inside of it)
    for (kc, kr, kz) in clumps:
        d = kc - top
        mid = top + d * 0.5 + Vector((0, 0, 0.35 * d.length * 0.3))
        end = kc - d.normalized() * kr * 0.25
        mb.tube([tuple(top - Vector((0, 0, 0.3))), tuple(mid), tuple(end)], r0 * 0.5, M['bark'], seg=6)
        for j in range(2):
            a = rng.uniform(0, math.tau)
            tip = end + Vector((math.cos(a) * kr * 0.6, math.sin(a) * kr * 0.6, rng.uniform(0, kz * 0.6)))
            mb.tube([tuple(end), tuple(tip)], r0 * 0.2, M['bark'], seg=4, caps=False)
    total = cards or int(60 + crown * crown * 11)
    vol = [kr * kr * kz for (_, kr, kz) in clumps]
    sv = sum(vol)
    s0 = (0.8 + crown / 10)
    for (kc, kr, kz), v in zip(clumps, vol):
        n = max(10, int(total * v / sv))
        for i in range(n):
            d = _rand_unit()
            if d.z < -0.55:
                d.z = -0.55 - (d.z + 0.55) * 0.3   # flatter underside
            outer = i < n * 0.74
            rr = rng.uniform(0.72, 1.0) if outer else rng.uniform(0.15, 0.6)
            p = kc + Vector((d.x * kr * rr, d.y * kr * rr, d.z * kz * rr))
            nrm = lambda co, k=kc, c=cc: (((co - k).normalized() * 0.65 + (co - c).normalized() * 0.35) + Vector((0, 0, 0.35))).normalized()
            if outer:
                _facing_card(mb, p, (p - kc) + Vector((0, 0, 0.3 * kz)), rng.uniform(1.3, 2.1) * s0, leaf, nrm)
            else:
                _facing_card(mb, p, _rand_unit(), rng.uniform(1.4, 2.2) * s0, inner, nrm, twist=1.5)
    if collide:
        # the trunk curves (wobble, lean): one hull per tube segment, plus the root flare
        for i in range(3):
            hulls.collider_hull('tree', [v.co for f in trunk[i * 9:(i + 1) * 9] for v in f.verts])
        hulls.collider_hull('tree', [v.co for v in flare])


def tree_conifer(x, y, z, h=16.0, rbase=3.0, collide=True, g='Foliage.trees', leaf=None, levels=None, droop=0.25):
    """Norway spruce: straight trunk, a dark irregular core cone (the shaded inside of the tree that
    shows between branches) and whorls of drooping branch cards that get shorter towards the tip."""
    leaf = leaf or M['leaf_spruce']
    mb = G[g]
    r0 = max(0.16, h * 0.018)
    trunk = mb.cyl((x, y, z + h * 0.5 - 0.2), r0, h + 0.4, M['bark_pine'], seg=7, r2=0.03)
    # core: stacked rings of an irregular star section, radius following the crown profile
    core = M['spruce_core']
    z0 = z + h * 0.1
    rings = []
    nr, seg = 8, 9
    for k in range(nr + 1):
        t = k / nr
        zz = z0 + (z + h * 0.95 - z0) * t
        # tucked in at the bottom (towards the trunk), crown profile above, a point at the top
        R = (rbase * (1 - t) + 0.1) * 0.42 * min(1.0, 0.25 + t * 6)
        ring = []
        for i in range(seg):
            a = i / seg * math.tau
            rr = R * rng.uniform(0.7, 1.15) if k < nr else 0.02
            ring.append(mb.bm.verts.new((x + math.cos(a) * rr, y + math.sin(a) * rr, zz + (rng.uniform(-0.2, 0.2) if 0 < k < nr else 0))))
        rings.append(ring)
    faces = []
    for k in range(nr):
        A, B = rings[k], rings[k + 1]
        for i in range(seg):
            faces.append(mb.bm.faces.new((A[i], A[(i + 1) % seg], B[(i + 1) % seg], B[i])))
    faces.append(mb.bm.faces.new(list(reversed(rings[0]))))
    mb._tag(faces, core, True)
    levels = levels or int(h * 1.3)
    for k in range(levels):
        t = k / max(1, levels - 1)
        zz = z + h * (0.1 + 0.87 * t) + rng.uniform(-0.12, 0.12)
        R = rbase * (1 - t) ** 0.95 + 0.4
        n = max(5, int(9 - t * 4))
        a0 = rng.uniform(0, math.tau)
        for i in range(n):
            a = a0 + i / n * math.tau + rng.uniform(-0.3, 0.3)
            d = Vector((math.cos(a), math.sin(a), 0))
            L = R * rng.uniform(0.85, 1.12)
            hgt = max(0.7, L * 0.62)
            dn = (d + Vector((0, 0, -droop - 0.1 * (1 - t)))).normalized()
            side = Vector((-d.y, d.x, 0))
            # branch-card texture: trunk end at u=0, main branch at v~0.6, branchlets hanging below.
            # alternate between a hanging (vertical) card and one rolled towards horizontal
            roll = 0.0 if (i + k) % 2 == 0 else rng.uniform(0.9, 1.25) * rng.choice((-1, 1))
            up = (Vector((0, 0, 1)) * math.cos(roll) + side * math.sin(roll))
            up = (up - dn * up.dot(dn)).normalized()
            c = Vector((x, y, zz)) + dn * (L / 2) - up * (hgt * 0.1)
            nrm = lambda co, cx=x, cy=y: (Vector((co.x - cx, co.y - cy, 0)).normalized() * 0.75 + Vector((0, 0, 0.5))).normalized()
            mb.card(c, dn, up, L, hgt, leaf, normal=nrm)
    # leader
    mb.card((x, y, z + h * 0.99), (1, 0, 0), (0, 0, 1), 0.7, 1.4, leaf, uv=(0.0, 0.2, 0.6, 0.8))
    mb.card((x, y, z + h * 0.99), (0, 1, 0), (0, 0, 1), 0.7, 1.4, leaf, uv=(0.0, 0.2, 0.6, 0.8))
    if collide:
        hulls.collider_hull('tree', hulls.clip_z(trunk, z + 4.0))


def tree_cedar(x, y, z, h=15.0, r=5.5, g='Foliage.trees', collide=True):
    """broad cedar: layered, slightly drooping plates of foliage around a dark core (the big cedars by the school)."""
    mb = G[g]
    r0 = h * 0.03
    leaf = M['leaf_cedar']
    inner = _inner(leaf)
    trunk = mb.tube([(x, y, z - 0.2), (x + 0.3, y, z + h * 0.55), (x + 0.1, y + 0.2, z + h)], r0, M['bark'], seg=8)
    mb.blob((x + 0.2, y + 0.1, z + h * 0.55), 1.0, M['spruce_core'], scale=(r * 0.55, r * 0.55, h * 0.36), jitter=0.12, sub=2,
            smooth=True)
    layers = 9
    for k in range(layers):
        t = k / (layers - 1)
        zz = z + h * (0.2 + 0.76 * t)
        R = r * (1 - t * 0.78) * rng.uniform(0.9, 1.08)
        cz = Vector((x, y, zz))
        nrm = lambda co, c=cz: (Vector((co.x - c.x, co.y - c.y, (co.z - c.z) * 2)).normalized() * 0.5 + Vector((0, 0, 0.85))).normalized()
        for i in range(int(14 + R * 5)):
            a = rng.uniform(0, math.tau)
            rr = math.sqrt(rng.uniform(0.2, 1)) * R
            c = Vector((x + math.cos(a) * rr, y + math.sin(a) * rr, zz + rng.uniform(-0.35, 0.35) - 0.25 * rr / R))
            # mostly horizontal plates, tilted down towards the rim
            n = Vector((math.cos(a) * 0.35 * rr / R, math.sin(a) * 0.35 * rr / R, 1))
            _facing_card(mb, c, n, rng.uniform(1.8, 2.8), leaf, nrm, twist=3.1)
        # hanging rim cards so it is not see-through from the side
        for i in range(int(6 + R * 1.6)):
            a = rng.uniform(0, math.tau)
            rr = rng.uniform(0.6, 1.0) * R
            c = Vector((x + math.cos(a) * rr, y + math.sin(a) * rr, zz - 0.45))
            _facing_card(mb, c, Vector((math.cos(a), math.sin(a), 0.35)), rng.uniform(1.8, 2.5), leaf if i % 3 else inner, nrm,
                         twist=0.4, aspect=1.3)
    if collide:
        hulls.collider_hull('tree', hulls.clip_z([v for f in trunk[:8] for v in f.verts], z + 4.0))


def _fuzz(mb, p, n, s, m):
    """small foliage card on a shrub surface, leaning out of it."""
    nn = (n + _rand_unit() * 0.45).normalized()
    _facing_card(mb, p + n * s * 0.22, nn, s, m, (n + Vector((0, 0, 0.4))).normalized(), twist=3.1)


def bush(x, y, z, r=1.0, h=None, leaf=None, g='Foliage.bushes', collide=None):
    """shrub: a small dark leafy core inside a slightly lopsided ball of foliage cards (outer ones facing out,
    inner ones darker) so the edge is soft and leafy instead of a solid lump; the lowest cards reach the ground
    so it sits in the grass instead of hovering.  Shrubs you can't see through are solid (bullets and bot sight
    stop at them too); only the far, out-of-bounds ones skip the collider."""
    mb = G[g]
    h = h or r * 1.2
    c = Vector((x, y, z + h * 0.5))
    core = mb.blob(tuple(c - Vector((0, 0, h * 0.06))), 1.0, M['shrub_core'], scale=(r * 0.5, r * 0.5, h * 0.32), jitter=0.1,
                   sub=2, smooth=True)
    mass = [v.co.copy() for v in core]     # where the foliage is dense: the core and every leaf card's centre
    m = leaf or M['leaf_hedge']
    inner = _inner(m)
    nrm = lambda co, cc=c: ((co - cc).normalized() + Vector((0, 0, 0.45))).normalized()
    # lopsided: stretched along a random axis, the top pushed a little off-centre
    a = rng.uniform(0, math.pi)
    ax, ay = Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))
    kx, ky = rng.uniform(1.0, 1.18), rng.uniform(0.85, 1.0)
    lean = Vector((rng.uniform(-0.12, 0.12) * r, rng.uniform(-0.12, 0.12) * r, 0))
    n = int(14 + r * r * 30)
    for i in range(n):
        d = _rand_unit()
        if d.z < -0.6:
            d.z = -0.6 - (d.z + 0.6) * 0.3
        outer = i < n * 0.75
        rr = rng.uniform(0.62, 0.95) if outer else rng.uniform(0.2, 0.55)
        s = rng.uniform(0.7, 1.05) * max(0.75, r * 0.75)
        lat = (ax * (d.dot(ax) * kx) + ay * (d.dot(ay) * ky)) * r * rr
        p = c + lat + lean * (0.5 + d.z * 0.5) + Vector((0, 0, d.z * h * 0.5 * rr))
        p.z = max(p.z, z + s * 0.3)
        mass.append(p.copy())
        if outer:
            _facing_card(mb, p, (p - c) + Vector((0, 0, 0.2)), s, m, nrm, twist=3.1)
        else:
            _facing_card(mb, p, _rand_unit(), s, inner, nrm, twist=3.1)
    # skirt: a ring of cards low down so the foot is leafy right to the ground
    for i in range(int(5 + r * 9)):
        a = rng.uniform(0, math.tau)
        d = ax * (math.cos(a) * kx) + ay * (math.sin(a) * ky)
        s = rng.uniform(0.6, 0.9) * max(0.7, r * 0.7)
        p = Vector((x, y, z)) + d * r * rng.uniform(0.6, 0.85) + lean * 0.3 + Vector((0, 0, s * 0.42 + rng.uniform(0.0, 0.12) * h))
        mass += [p.copy(), Vector((p.x, p.y, z - 0.1))]     # the skirt reaches the ground
        _facing_card(mb, p, d + Vector((0, 0, 0.1)), s, m, nrm, twist=3.1)
    if collide is None:
        collide = g != 'Foliage.far'
    if collide:
        # the lopsided foliage ball itself (a box's corners stuck out past its rounded top and sides)
        hulls.collider_hull('bush', mass)


def hedge(p0, p1, z, h=1.1, w=0.9, collide=True, g='Foliage.hedges', fuzz=True):
    """clipped hedge along p0->p1: a smooth loaf (rounded section, slightly wavy) with leaf cards on its skin."""
    mb = G[g]
    a, b = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = b - a
    L = d.length
    if L < 0.1:
        return
    t = d.normalized()
    nside = Vector((-t.y, t.x, 0))
    # rounded-rectangle section, open at the bottom: (lateral, height) from one foot over the top to the other
    rc = min(w, h) * 0.32
    sec = [(-w / 2, 0.0), (-w / 2, h * 0.3), (-w / 2, (h - rc) * 0.7 + h * 0.09)]
    for k in range(5):
        ang = math.pi - k / 4 * math.pi / 2
        sec.append((-w / 2 + rc + math.cos(ang) * rc, h - rc + math.sin(ang) * rc))
    sec = sec + [(-q[0], q[1]) for q in reversed(sec)]
    sec = [(q[0] * (1 - 0.08 * (q[1] / h)), q[1]) for q in sec]   # hedges are trimmed slightly narrower at the top
    nseg = max(2, int(L / 0.6))
    rings = []
    for i in range(nseg + 1):
        s = i / nseg
        wav = 1 + 0.05 * math.sin(s * L * 2.1 + x_phase(p0)) if 0 < i < nseg else 1
        ring = []
        for (u, v) in sec:
            j = rng.uniform(-0.03, 0.03) if 0 < i < nseg else 0
            p = a + d * s + nside * (u * wav + j) + Vector((0, 0, z + v * (1 + j) if v > 0 else z - 0.05))
            ring.append(mb.bm.verts.new(p))
        rings.append(ring)
    faces = []
    for i in range(nseg):
        A, B = rings[i], rings[i + 1]
        for k in range(len(sec) - 1):
            faces.append(mb.bm.faces.new((A[k], B[k], B[k + 1], A[k + 1])))
    faces.append(mb.bm.faces.new(rings[0]))
    faces.append(mb.bm.faces.new(list(reversed(rings[-1]))))
    mb._tag(faces, M['hedge'], True)
    for f in faces[-2:]:
        f.smooth = False
    if fuzz:
        m = M['leaf_hedge']
        for i in range(int(L * 10)):
            s = rng.random()
            k = rng.randint(1, len(sec) - 2)
            u, v = sec[k]
            q0, q1 = sec[k - 1], sec[k + 1]
            tn = Vector((q1[0] - q0[0], q1[1] - q0[1]))
            nn2 = Vector((tn.y, -tn.x)).normalized()
            if nn2.dot(Vector((u, v - h / 2))) < 0:
                nn2 = -nn2
            p = a + d * s + nside * u + Vector((0, 0, z + v))
            n3 = (nside * nn2.x + Vector((0, 0, nn2.y))).normalized()
            _fuzz(mb, p, n3, rng.uniform(0.45, 0.7), m)
    if collide:
        hulls.collider_hull('hedge', [v.co for ring in rings for v in ring])


def x_phase(p):
    return (p[0] * 1.7 + p[1] * 0.9) % math.tau


def grass_tufts(x0, x1, y0, y1, z, n, g='Foliage.grass'):
    mb = G[g]
    for i in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        zz = z(x, y) if callable(z) else z
        s = rng.uniform(0.5, 0.9)
        for a in (rng.uniform(0, math.pi), ):
            for k in range(2):
                aa = a + k * math.pi / 2
                mb.card((x, y, zz + s * 0.24), (math.cos(aa), math.sin(aa), 0), (0, 0, 1), s, s * 0.5, M['grass_card'],
                        normal=Vector((0, 0, 1)))


def rock(x, y, z, r=0.8, squash=0.7, g='Props.rocks', collide=False):
    mb = G[g]
    mb.blob((x, y, z + r * squash * 0.4), r, M['rock'], scale=(1.0, rng.uniform(0.7, 1.0), squash), jitter=0.22, sub=2, smooth=True,
            rz=rng.uniform(0, math.tau))
    if collide:
        collider('rock', (x, y, z + r * squash * 0.4), (r * 1.4, r * 1.2, r * squash * 1.4))


def rock_block(x, y, z0, sx, sy, sz, rz=0.0, g='Props.rocks', m=None, cuts=2, jit=0.09, collide=True):
    """blocky limestone: a subdivided box with jittered vertices, flat shaded (bedded, fissured outcrop
    blocks and the dry-stone wall's stones).  z0 = foot of the block."""
    mb = G[g]
    mtx = Matrix.Translation((x, y, z0 + sz / 2)) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Diagonal((sx, sy, sz, 1))
    res = bmesh.ops.create_cube(mb.bm, size=1.0, matrix=mtx)
    verts = set(res['verts'])
    if cuts:
        edges = list({e for v in verts for e in v.link_edges})
        sub = bmesh.ops.subdivide_edges(mb.bm, edges=edges, cuts=cuts, use_grid_fill=True)
        faces = {f for f in sub['geom'] if isinstance(f, bmesh.types.BMFace) and f.is_valid}
        faces |= {f for v in verts if v.is_valid for f in v.link_faces}
        verts = {v for f in faces for v in f.verts}
    j = min(sx, sy, sz) * jit
    c = Vector((x, y, z0 + sz / 2))
    for v in verts:
        v.co += Vector((rng.uniform(-j, j), rng.uniform(-j, j), rng.uniform(-j, j) * 0.6))
        # knock the top edges back a little (weathered arrises)
        if v.co.z > z0 + sz * 0.8:
            d = Vector((v.co.x - c.x, v.co.y - c.y, 0))
            v.co -= d * rng.uniform(0.0, 0.12)
    mb._tag(mb._faces_of(verts), m or M['rock'], False)
    if collide:
        collider('rock', (x, y, z0 + sz / 2), (sx * 0.92, sy * 0.92, sz * 0.96), rz=rz)


def bamboo(x0, x1, y0, y1, zf, h=6.0, density=4.5, g='Foliage.bamboo', collide=True):
    """bamboo thicket over the rectangle x0..x1 / y0..y1 (zf(x, y) = ground height): thin leaning culms
    with leaf sprays on their upper two thirds, a skin of outward-facing leaf cards and a dark core so it
    reads as the dense wall it is in the photos.  Solid (blocks bullets and sight)."""
    mb = G[g]
    leaf = M['leaf_bamboo']
    inner = _inner(leaf)
    culm = M['bamboo_culm']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2, (y1 - y0) / 2
    zs = [zf(x, y) for x in (x0, cx, x1) for y in (y0, cy, y1)]
    zmin, zmax = min(zs), max(zs)
    for i in range(int(4 * hx * hy * density)):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        z = zf(x, y)
        hh = h * rng.uniform(0.72, 1.06)
        # culms fan outwards (more at the edges of the clump) and arch over at the top
        lx = (x - cx) / max(hx, 0.1) * 0.9 + rng.uniform(-0.35, 0.35)
        ly = (y - cy) / max(hy, 0.1) * 0.9 + rng.uniform(-0.35, 0.35)
        lean = Vector((lx, ly, 0)) * hh * 0.14
        pts = [Vector((x, y, z - 0.1))] + [Vector((x, y, z)) + lean * (t ** 1.6) + Vector((0, 0, hh * t)) for t in (0.35, 0.7, 1.0)]
        mb.tube([tuple(p) for p in pts], rng.uniform(0.016, 0.03), culm, seg=5, caps=False)
        out = Vector((lx, ly, 0))
        out = out.normalized() if out.length > 0.2 else _rand_unit()
        nrm = (out + Vector((0, 0, 0.5))).normalized()
        for k in range(rng.randint(2, 4)):
            t = rng.uniform(0.15, 1.0) ** 0.8
            p = Vector((x, y, z)) + lean * (t ** 1.6) + Vector((0, 0, hh * t))
            _facing_card(mb, p + out * 0.25, out + _rand_unit() * 0.7 + Vector((0, 0, 0.15)), rng.uniform(1.1, 1.8), leaf, nrm,
                         twist=0.7)
    # outer skin: cards on the sides and top of the (slightly bulging) clump volume
    for i in range(int((hx + hy) * 2 * h * 4.5 + hx * hy * 6)):
        side = rng.random()
        if side < 0.85:
            a = rng.uniform(0, math.tau)
            d = Vector((math.cos(a), math.sin(a), 0))
            k = min(hx / max(abs(d.x), 1e-3), hy / max(abs(d.y), 1e-3))
            t = rng.uniform(0.0, 1.0) ** 1.15
            bulge = 1.0 + 0.35 * math.sin(t * math.pi)
            p = Vector((cx, cy, 0)) + d * k * rng.uniform(0.85, 1.05) * bulge
            p.z = zf(min(max(p.x, x0), x1), min(max(p.y, y0), y1)) + max(h * t, 0.45)
            n = d + Vector((0, 0, 0.25))
        else:
            p = Vector((rng.uniform(x0, x1), rng.uniform(y0, y1), 0))
            p.z = zf(p.x, p.y) + h * rng.uniform(0.85, 1.02)
            n = Vector((p.x - cx, p.y - cy, 1.2))
        nrm = (n.normalized() + Vector((0, 0, 0.4))).normalized()
        _facing_card(mb, p, n, rng.uniform(1.2, 2.0), leaf if rng.random() < 0.8 else inner, nrm, twist=0.8)
    # dark core (well inside the skin) keeps it from being see-through between the cards
    mb.blob((cx, cy, zmin + h * 0.42), 1.0, M['bamboo_core'], scale=(max(0.15, hx - 0.5), max(0.15, hy - 0.5), h * 0.4), jitter=0.12,
            sub=2, smooth=True)
    if collide:
        collider('bamboo', (cx, cy, (zmin - 0.3 + zmax + h * 0.88) / 2),
                 (2 * hx - 0.25, 2 * hy - 0.25, zmax + h * 0.88 - zmin + 0.3))


def ivy_wall(p0, p1, z0, z1, n, off=0.03, g='Foliage.ivy', m=None):
    """ivy / creeper leaf cards stuck on a vertical face from p0 to p1 (outward = right of p0->p1).
    z0, z1: numbers or callables of the 0..1 position along the face."""
    mb = G[g]
    m = m or M['leaf_ivy']
    a, b = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = (b - a).normalized()
    nn = Vector((d.y, -d.x, 0))
    nrm = (nn + Vector((0, 0, 0.6))).normalized()
    for i in range(n):
        t = rng.random()
        lo = z0(t) if callable(z0) else z0
        hi = z1(t) if callable(z1) else z1
        p = a + (b - a) * t + nn * (off + rng.uniform(0.0, 0.07)) + Vector((0, 0, rng.uniform(lo, hi)))
        _facing_card(mb, p, nn + _rand_unit() * 0.35, rng.uniform(0.4, 0.75), m, nrm, twist=3.1)


def drape(p0, p1, ztop, n, drop=(0.5, 1.3), off=0.06, g='Foliage.ivy', m=None):
    """creeper / shrub branches hanging over the top edge of a wall face from p0 to p1 (outward = right of
    p0->p1): tall leaf cards whose tops sit on the edge, longer and denser in clumps.  ztop: number or callable of
    the 0..1 position along the face."""
    mb = G[g]
    m = m or M['leaf_ivy']
    a, b = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0))
    d = (b - a).normalized()
    nn = Vector((d.y, -d.x, 0))
    nrm = (nn + Vector((0, 0, 0.8))).normalized()
    ph = rng.uniform(0, math.tau)
    L = (b - a).length
    for i in range(n):
        t = rng.random()
        clump = 0.5 + 0.5 * math.sin(t * L * 1.3 + ph) * math.sin(t * L * 0.47 + ph * 2)
        hh = rng.uniform(*drop) * (0.55 + 0.6 * clump)
        w = rng.uniform(0.45, 0.8)
        zt = ztop(t) if callable(ztop) else ztop
        p = a + (b - a) * t + nn * (off + rng.uniform(0.0, 0.08) + 0.06 * clump) + Vector((0, 0, zt + 0.12 - hh / 2))
        up = (Vector((0, 0, 1)) + d * rng.uniform(-0.15, 0.15) - nn * 0.08).normalized()
        mb.card(p, d, up, w, hh, m, normal=nrm)


# ------------------------------------------------------------------------------------------------
# street furniture
# ------------------------------------------------------------------------------------------------

def lamp_double(x, y, z=0.12, arm_dir=(1, 0), h=8.6, g='Props.lamps'):
    """galvanised street light with two curved arms (the lot's Y-shaped lamps)."""
    mb = G[g]
    mb.pole((x, y), z, z + h, 0.1, M['metal'], seg=10, r2=0.065)
    mb.cyl((x, y, z + 0.35), 0.16, 0.7, M['metal'], seg=10, r2=0.12)
    d = Vector((arm_dir[0], arm_dir[1], 0)).normalized()
    top = Vector((x, y, z + h))
    for s in (-1, 1):
        pts = []
        for k in range(7):
            t = k / 6
            off = d * s * (1.55 * t)
            pts.append(top + off + Vector((0, 0, 1.0 * math.sin(t * math.pi * 0.62))))
        mb.tube([tuple(p) for p in pts], 0.045, M['metal'], seg=6)
        end = pts[-1]
        yaw = math.atan2(d.y * s, d.x * s)
        mb.box(tuple(end + d * s * 0.28 + Vector((0, 0, -0.04))), (0.72, 0.28, 0.12), M['metal'], rz=yaw, ry=0.12 * s * 0)
        mb.box(tuple(end + d * s * 0.28 + Vector((0, 0, -0.12))), (0.58, 0.22, 0.04), M['lamp_glass'], rz=yaw)
    collider('pole', (x, y, z + 1.5), (0.24, 0.24, 3.0))


def lamp_mushroom(x, y, z=0.12, h=4.2, g='Props.lamps'):
    """park / pocket lamp: slim pole with a flat round cap."""
    mb = G[g]
    mb.pole((x, y), z, z + h, 0.06, M['metal_dark'], seg=8, r2=0.05)
    mb.cyl((x, y, z + h + 0.06), 0.48, 0.1, M['metal_dark'], seg=16)
    mb.cyl((x, y, z + h - 0.05), 0.36, 0.12, M['lamp_glass'], seg=16)
    collider('pole', (x, y, z + 1.4), (0.16, 0.16, 2.8))


def sign_post(x, y, z, yaw, panels, h=None, g='Props.signs', r=0.035):
    """panels: [(material, width, height, z_centre)] facing direction yaw (normal)."""
    mb = G[g]
    top = h or max(p[3] + p[2] / 2 for p in panels) + 0.05
    mb.pole((x, y), z, z + top, r, M['metal'], seg=8)
    n = Vector((math.cos(yaw), math.sin(yaw), 0))
    right = Vector((math.sin(yaw), -math.cos(yaw), 0))
    for m, w, hh, zc in panels:
        c = Vector((x, y, z + zc)) + n * (r + 0.012)
        mb.card(c, right, (0, 0, 1), w, hh, m)
        mb.box(tuple(c - n * 0.01), (0.012, w, hh), M['sign_back'], rz=yaw)


def bike_rack(x, y, z, yaw, g='Props.street'):
    mb = G[g]
    d = Vector((*rot2(1, 0, yaw), 0))
    pts = []
    for k in range(11):
        a = k / 10 * math.pi
        pts.append(Vector((x, y, z)) + d * (math.cos(a) * 0.36) + Vector((0, 0, 0.45 + math.sin(a) * 0.38)))
    pts = [pts[0] - Vector((0, 0, 0.45))] + pts + [pts[-1] - Vector((0, 0, 0.45))]
    mb.tube([tuple(p) for p in pts], 0.03, M['metal'], seg=6)


def bench(x, y, z, yaw, L=1.8, g='Props.street'):
    mb = G[g]

    def P(lx, ly, lz):
        rx, ry = rot2(lx, ly, yaw)
        return (x + rx, y + ry, z + lz)
    for i in range(3):
        mb.box(P(0, -0.18 + i * 0.16, 0.45), (L, 0.12, 0.04), M['wood'], rz=yaw)
    for i in range(2):
        mb.box(P(0, 0.26, 0.62 + i * 0.14), (L, 0.04, 0.11), M['wood'], rz=yaw, rx=0.1)
    for lx in (-L / 2 + 0.15, L / 2 - 0.15):
        mb.box(P(lx, 0.0, 0.22), (0.06, 0.5, 0.44), M['metal_dark'], rz=yaw)
        mb.box(P(lx, 0.27, 0.6), (0.05, 0.05, 0.35), M['metal_dark'], rz=yaw)


def litter_bin(x, y, z, m=None, g='Props.street'):
    mb = G[g]
    mb.cyl((x, y, z + 0.45), 0.22, 0.7, m or M['bin_orange'], seg=12)
    mb.pole((x, y - 0.25), z, z + 0.9, 0.03, M['metal_dark'], seg=6)


def container(x, y, z, yaw, m, g='Props.street', collide=True):
    """1100 l wheeled recycling container."""
    mb = G[g]

    def P(lx, ly, lz):
        rx, ry = rot2(lx, ly, yaw)
        return (x + rx, y + ry, z + lz)
    mb.box(P(0, 0, 0.72), (1.25, 1.0, 1.12), m, rz=yaw)
    mb.box(P(0.0, 0, 1.33), (1.32, 1.08, 0.1), m, rz=yaw, ry=0.0)
    mb.box(P(0.0, -0.53, 1.0), (1.2, 0.06, 0.08), M['plastic_black'], rz=yaw)
    for lx in (-0.5, 0.5):
        for ly in (-0.4, 0.4):
            mb.cyl(P(lx, ly, 0.09), 0.09, 0.06, M['rubber'], seg=8, rx=math.pi / 2, rz=yaw)
    G['Ground.decals'].card((x, y, z + 0.016), (*rot2(1, 0, yaw), 0), (*rot2(0, 1, yaw), 0), 1.7, 1.4, M['blob'])
    if collide:
        collider('bin', P(0, 0, 0.7), (1.3, 1.05, 1.4), rz=yaw)


def ac_unit(p, n, z, g='Props.walls', w=0.82, h=0.56):
    """outdoor AC unit mounted on a wall (p on the wall plane, n = outward normal 2D)."""
    mb = G[g]
    n = Vector((n[0], n[1], 0)).normalized()
    yaw = math.atan2(n.y, n.x)
    c = Vector((p[0], p[1], z)) + n * 0.16
    mb.box(tuple(c), (0.3, w, h), M['ac'], rz=yaw)
    mb.cyl(tuple(c + n * 0.152 + Vector((*rot2(0, w * 0.15, yaw), 0))), h * 0.36, 0.01, M['ac_grille'], seg=14,
           rx=math.pi / 2, rz=yaw + math.pi / 2)
    mb.box(tuple(Vector((p[0], p[1], z - h / 2 - 0.03)) + n * 0.16), (0.32, w + 0.05, 0.03), M['metal'], rz=yaw)


def downpipe(p, n, z0, z1, g='Props.walls', red=True):
    mb = G[g]
    n = Vector((n[0], n[1], 0)).normalized()
    c = Vector((p[0], p[1], 0)) + n * 0.09
    mb.pole((c.x, c.y), z0 + (1.6 if red else 0), z1, 0.055, M['pipe_gray'], seg=8)
    if red:
        mb.pole((c.x, c.y), z0, z0 + 1.6, 0.06, M['pipe_red'], seg=8)
    mb.cyl((c.x, c.y, z1 + 0.05), 0.09, 0.14, M['pipe_gray'], seg=8)


def flagpole_wall(p, n, z, flag_m, g='Props.flags', ang=0.6):
    """short flagpole sticking out of a facade at an angle, with a flag hanging from it."""
    mb = G[g]
    n = Vector((n[0], n[1], 0)).normalized()
    base = Vector((p[0], p[1], z))
    d = (n * math.cos(ang) + Vector((0, 0, math.sin(ang)))).normalized()
    tip = base + d * 2.6
    mb.tube([tuple(base), tuple(tip)], 0.025, M['white_paint'], seg=6)
    # flag hangs from the pole: quad spanning along the pole, droops down
    a = base + d * 0.6
    b = tip
    drop = Vector((0, 0, -1.1))
    side = Vector((-n.y, n.x, 0)) * 0.08
    mb.quad([tuple(a + drop + side), tuple(b + drop * 0.85 - side), tuple(b), tuple(a)], flag_m, [(0, 0), (1, 0), (1, 1), (0, 1)])
    mb.quad([tuple(a), tuple(b), tuple(b + drop * 0.85 - side), tuple(a + drop + side)], flag_m, [(0, 1), (1, 1), (1, 0), (0, 0)])


def flagpole(x, y, z, h, flag_m, wind=(1, 0), g='Props.flags'):
    mb = G[g]
    mb.pole((x, y), z, z + h, 0.045, M['white_paint'], seg=8, r2=0.03)
    mb.cyl((x, y, z + h + 0.04), 0.06, 0.08, M['metal'], seg=8)
    d = Vector((wind[0], wind[1], 0)).normalized()
    top = Vector((x, y, z + h - 0.1))
    pts = []
    for k in range(5):
        t = k / 4
        pts.append(top + d * (t * 1.6) + Vector((*rot2(0, 0.1 * math.sin(t * 5), math.atan2(d.y, d.x)), -t * 0.2)))
    for k in range(4):
        a, b = pts[k], pts[k + 1]
        u0, u1 = k / 4, (k + 1) / 4
        mb.quad([tuple(a - Vector((0, 0, 1.0))), tuple(b - Vector((0, 0, 1.0))), tuple(b), tuple(a)], flag_m,
                [(u0, 0), (u1, 0), (u1, 1), (u0, 1)])
        mb.quad([tuple(a), tuple(b), tuple(b - Vector((0, 0, 1.0))), tuple(a - Vector((0, 0, 1.0)))], flag_m,
                [(u0, 1), (u1, 1), (u1, 0), (u0, 0)])


def railing(pts, z, h=1.0, g='Props.rails', posts=1.6, m=None, rails=2, collide=False):
    """tubular railing along a 3D/2D polyline at height z (or per-point z if 3D)."""
    mb = G[g]
    m = m or M['metal']
    P = [Vector((p[0], p[1], p[2] if len(p) > 2 else z)) for p in pts]
    for k in range(rails):
        hh = h * (1 - k * 0.5)
        mb.tube([tuple(p + Vector((0, 0, hh))) for p in P], 0.025, m, seg=6)
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        L = (b - a).length
        n = max(1, int(L / posts))
        for j in range(n + (1 if i == len(P) - 2 else 0)):
            p = a + (b - a) * (j / n)
            mb.pole((p.x, p.y), p.z, p.z + h, 0.022, m, seg=6)
    if collide:
        for i in range(len(P) - 1):
            collider_seg('rail', P[i], P[i + 1], 0.12, min(P[i].z, P[i + 1].z), max(P[i].z, P[i + 1].z) + h, clip=True)


def bollard(x, y, z, g='Props.street'):
    mb = G[g]
    mb.cyl((x, y, z + 0.45), 0.08, 0.9, M['metal_dark'], seg=10)
    mb.cyl((x, y, z + 0.78), 0.085, 0.06, M['white_paint'], seg=10)


def cafe_set(x, y, z, yaw, g='Props.cafe'):
    """round table, 3-4 wicker chairs."""
    mb = G[g]
    mb.cyl((x, y, z + 0.74), 0.38, 0.03, M['metal'], seg=14)
    mb.pole((x, y), z, z + 0.74, 0.03, M['metal_dark'], seg=6)
    mb.cyl((x, y, z + 0.02), 0.22, 0.04, M['metal_dark'], seg=10)
    for k in range(rng.choice((2, 3, 4))):
        a = yaw + k * math.tau / 4 + rng.uniform(-0.2, 0.2)
        cx, cy = x + math.cos(a) * 0.68, y + math.sin(a) * 0.68
        mb.box((cx, cy, z + 0.22), (0.48, 0.48, 0.44), M['wicker'], rz=a)
        bx, by = cx + math.cos(a) * 0.22, cy + math.sin(a) * 0.22
        mb.box((bx, by, z + 0.66), (0.08, 0.5, 0.48), M['wicker'], rz=a)


def parasol(x, y, z, r=1.4, g='Props.cafe'):
    mb = G[g]
    mb.pole((x, y), z, z + 2.45, 0.025, M['metal'], seg=6)
    mb.cyl((x, y, z + 2.3), r, 0.4, M['parasol'], seg=8, r2=0.05, smooth=False)
    mb.cyl((x, y, z + 2.06), r, 0.1, M['parasol'], seg=8, smooth=False, caps=False)


def manhole(x, y, z, g='Ground.decals'):
    G[g].card((x, y, z + 0.006), (1, 0, 0), (0, 1, 0), 0.75, 0.75, M['manhole'])


def drain(x, y, z, yaw=0.0, g='Ground.decals'):
    G[g].card((x, y, z + 0.006), (*rot2(1, 0, yaw), 0), (*rot2(0, 1, yaw), 0), 0.55, 0.32, M['grate'])
