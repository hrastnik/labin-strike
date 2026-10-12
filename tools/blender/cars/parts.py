"""Separate car parts built in bmesh: wheels (tyre, alloy rim, brake), mirrors, handles, wipers, plates..."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector


def _mesh(name, bm, mats, coll, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def lathe(bm, prof, seg, mat=0, axis='Y', cap=False, phase=0.0, smooth=True):
    """revolve a (radius, axial) polyline around the axis; returns rings of verts."""
    rings = []
    for (r, a) in prof:
        ring = []
        for i in range(seg):
            t = phase + 2 * math.pi * i / seg
            c, s = math.cos(t) * r, math.sin(t) * r
            p = Vector((c, a, s)) if axis == 'Y' else Vector((a, c, s))
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for j in range(len(rings) - 1):
        for i in range(seg):
            a0, a1 = rings[j][i], rings[j][(i + 1) % seg]
            b0, b1 = rings[j + 1][i], rings[j + 1][(i + 1) % seg]
            if a0.co == b0.co and a1.co == b1.co:
                continue
            f = bm.faces.new((a0, b0, b1, a1))
            f.material_index = mat
            f.smooth = smooth
    return rings


def wheel(spec, M, coll, name):
    """one wheel in local frame: axle = Y, outer face towards +Y, centre at origin. Materials:
    0 rubber, 1 alloy, 2 brake/dark."""
    R = spec['wheel_r']
    tw = spec['tyre_w']
    rr = spec.get('rim_in', 16) * 0.0254 / 2 + 0.012     # rim flange radius
    h = tw / 2
    bm = bmesh.new()
    seg = spec.get('wheel_seg', 32)
    # tyre: inner bead -> sidewall -> tread -> sidewall -> outer bead (profile runs from inner to outer side)
    sw = R - rr
    prof = [(rr - 0.004, -h * 0.80), (rr + sw * 0.45, -h * 1.02), (R - 0.016, -h * 0.94), (R, -h * 0.55), (R, h * 0.55),
            (R - 0.016, h * 0.94), (rr + sw * 0.45, h * 1.02), (rr - 0.004, h * 0.80)]
    lathe(bm, prof, seg, mat=0)
    # rim: barrel (seen through the spokes) + lip
    yf = h * 0.80                                         # rim face plane
    lathe(bm, [(rr - 0.004, yf), (rr - 0.014, yf + 0.006), (rr - 0.024, yf - 0.006), (rr - 0.024, -h * 0.6)], seg, mat=1)
    # spoke face: polar grid; windows between spokes are removed and walled
    n_sp = spec.get('spokes', 5)
    per = spec.get('rim_seg_per_spoke', 8)
    nseg = n_sp * per
    radii = [0.0, 0.035, 0.055, 0.075, 0.11, 0.145, rr - 0.045, rr - 0.024]
    dish = spec.get('rim_dish', 0.028)

    def face_y(r):
        return yf + 0.004 - dish * (1 - min(1.0, r / (rr - 0.024))) ** 1.5 + (0.012 if r < 0.06 else 0.0)
    style = spec.get('rim_style', 'double5')
    grid = []
    for j, r in enumerate(radii):
        row = []
        for i in range(nseg if r > 0 else 1):
            t = 2 * math.pi * i / nseg
            row.append(bm.verts.new((math.cos(t) * r, face_y(r), math.sin(t) * r)))
        grid.append(row)

    def is_window(i, j):
        if j < 3 or j >= len(radii) - 1:
            return False
        p = (i % per) / per
        if style == 'double5':      # two thin spokes per pair, window between pairs and a slot inside
            return 0.25 <= p < 0.875 and not (0.5 <= p < 0.625 and j < 5)
        return 0.25 <= p < 0.875
    face_walls = []
    for j in range(len(radii) - 1):
        for i in range(nseg):
            if j == 0:
                f = bm.faces.new((grid[0][0], grid[1][(i + 1) % nseg], grid[1][i]))
                f.material_index = 1
                continue
            if is_window(i, j):
                continue
            f = bm.faces.new((grid[j][i], grid[j][(i + 1) % nseg], grid[j + 1][(i + 1) % nseg], grid[j + 1][i]))
            f.material_index = 1
            face_walls.append(f)
    # spoke sides: extrude the window boundaries inwards
    bnd = [e for e in bm.edges if len(e.link_faces) == 1 and all(f.material_index == 1 for f in e.link_faces)
           and all(abs(v.co.y - face_y(v.co.xz.length)) < 1e-6 for v in e.verts)]
    inner = [e for e in bnd if 0.05 < (e.verts[0].co.xz.length + e.verts[1].co.xz.length) / 2 < rr - 0.03]
    res = bmesh.ops.extrude_edge_only(bm, edges=inner)
    nv = [v for v in res['geom'] if isinstance(v, bmesh.types.BMVert)]
    for v in nv:
        v.co.y -= 0.045
    for f in [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace)]:
        f.material_index = 1
    # centre cap (dark) and lug nuts
    lathe(bm, [(0.0, face_y(0) + 0.006), (0.03, face_y(0) + 0.004), (0.034, face_y(0) - 0.004)], 16, mat=2)
    # brake disc + caliper behind the spokes
    lathe(bm, [(0.06, -0.02), (rr - 0.04, -0.02), (rr - 0.04, -0.045)], 20, mat=2)
    cal = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((-rr + 0.075, -0.03, 0.09)) @ Matrix.Diagonal((0.06, 0.05, 0.13, 1)))
    for v in cal['verts']:
        for f in v.link_faces:
            f.material_index = 2
    ob = _mesh(name, bm, [M['rubber'], M['alloy'], M['brake']], coll)
    return ob


def _rbox(bm, c, size, r, mat, seg=2):
    """rounded box (bevelled cube) centred at c with full size (sx, sy, sz)."""
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(c) @ Matrix.Diagonal((*size, 1)))
    vs = res['verts']
    es = list({e for v in vs for e in v.link_edges})
    bmesh.ops.bevel(bm, geom=es, offset=r, segments=seg, affect='EDGES', profile=0.5, clamp_overlap=True)
    fs = {f for v in bm.verts for f in v.link_faces}
    return fs


def _set_mat(faces, mat):
    for f in faces:
        f.material_index = mat


def _new_faces(bm, before):
    return [f for f in bm.faces if f.index == -1 or f not in before]


def mirror_housing(spec, M, coll, body):
    """door mirrors: painted pebble housing (subdivided box, crisp rear rim), mirror glass inset in the rear face,
    gloss black arm to the door. Both sides."""
    from .ops import apply_mods, raycast
    m = spec['mirror']
    x, z = m['x'], m['z']
    L, h, d = m.get('len', 0.22), m.get('h', 0.125), m.get('d', 0.105)
    hit, _ = raycast(body, (m.get('arm_x', x + 0.03), 3.0, m.get('arm_z', z - 0.05)), (0, -1, 0))
    ys = hit.y if hit else 0.85
    y0 = ys + m.get('arm', 0.05)
    bm = bmesh.new()
    res = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    for v in bm.verts:
        u, w, t = v.co.x + 0.5, v.co.y + 0.5, v.co.z     # u: rear(0)->front(1), w: inner(0)->outer(1), t: -0.5..0.5
        taper = 0.72 + 0.28 * min(1.0, w * 2.2)
        v.co = Vector((x - d * 0.5 + u * d * (0.8 + 0.2 * w), y0 + w * L, z - 0.012 * (1 - w) + t * h * taper))
    crease = bm.edges.layers.float.get('crease_edge') or bm.edges.layers.float.new('crease_edge')
    xr = x - d * 0.5
    for e in bm.edges:
        if all(abs(v.co.x - xr) < 1e-5 for v in e.verts):
            e[crease] = 1.0
    me = bpy.data.meshes.new('mirror_tmp')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('mirror_tmp', me)
    coll.objects.link(ob)
    ob.modifiers.new('s', 'SUBSURF').levels = 1
    apply_mods(ob)
    bm = bmesh.new()
    me = ob.data
    bm.from_mesh(me)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    for f in bm.faces:
        f.material_index = 0
    rear = [f for f in bm.faces if f.normal.x < -0.9]
    r = bmesh.ops.inset_region(bm, faces=rear, thickness=0.009, depth=-0.004)
    for f in r['faces']:
        f.material_index = 1
    for f in rear:
        f.material_index = 2
    before = set(bm.faces)
    _rbox(bm, Vector((x + 0.005, (ys + y0) / 2 + 0.01, z - 0.045)), (0.075, y0 - ys + 0.04, 0.032), 0.008, 1)
    _set_mat([f for f in bm.faces if f not in before], 1)
    bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], axis='Y', merge_dist=-1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return _mesh(spec['name'] + '_mirrors', bm, [M['paint'], M['gloss'], M['chrome']], coll)


def handles(spec, M, coll, body):
    from .ops import raycast
    bm = bmesh.new()
    for (x, z) in spec.get('handles', []):
        hit, nor = raycast(body, (x, 3.0, z), (0, -1, 0))
        if not hit:
            continue
        c = hit + nor * 0.008
        fs = _rbox(bm, c, (0.165, 0.028, 0.032), 0.012, 0)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.mirror(bm, geom=geom, axis='Y', merge_dist=-1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return _mesh(spec['name'] + '_handles', bm, [M['paint']], coll)


def _bar(bm, a, b, nrm, w, t, mat):
    """thin box from a to b lying on a surface with normal nrm."""
    a, b, nrm = Vector(a), Vector(b), Vector(nrm).normalized()
    ax = (b - a)
    L = ax.length
    ax.normalize()
    side = nrm.cross(ax).normalized()
    up = ax.cross(side).normalized()
    m = Matrix((ax, side, up)).transposed().to_4x4()
    m.translation = (a + b) / 2
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal((L, w, t, 1)))
    for f in {f for v in res['verts'] for f in v.link_faces}:
        f.material_index = mat


def wipers(spec, M, coll, targets):
    from .ops import raycast
    bm = bmesh.new()
    for (p0, p1) in spec.get('wipers', []):
        pts = []
        for (x, y) in (p0, p1):
            hit, nor = raycast(targets, (x, y, 3.0), (0, 0, -1))
            pts.append((hit, nor) if hit else None)
        if None in pts:
            continue
        n = (pts[0][1] + pts[1][1]).normalized()
        a = pts[0][0] + n * 0.016
        b = pts[1][0] + n * 0.016
        _bar(bm, a, a + (b - a) * 0.45, n, 0.012, 0.012, 0)           # arm
        _bar(bm, a + (b - a) * 0.05, b, n, 0.02, 0.010, 0)             # blade
        hub = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.018, radius2=0.014, depth=0.02,
                                    matrix=Matrix.Translation(pts[0][0] + n * 0.01))
    return _mesh(spec['name'] + '_wipers', bm, [M['trim']], coll, smooth=False)


def plates(spec, M, coll, body, variant=0, n_variants=4):
    """front + rear plates (520 x 112 mm, EU), textured from tex/plates.png (one row per variant)."""
    from .ops import raycast
    import os
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    W, H, T = 0.52, 0.112, 0.008
    for end, z in (('front', spec['plate_z'][0]), ('rear', spec['plate_z'][1])):
        sgn = 1 if end == 'front' else -1
        hit, nor = raycast(body, (sgn * 4.0, 0.0, z), (-sgn, 0, 0))
        if not hit:
            continue
        nrm = Vector((sgn, 0, nor.z if abs(nor.z) < 0.5 else 0)).normalized()
        c = hit + nrm * (T / 2 + 0.004)
        up = Vector((0, 0, 1))
        up = (up - nrm * up.dot(nrm)).normalized()
        m = Matrix((nrm, up.cross(nrm), up)).transposed().to_4x4()
        m.translation = c
        res = bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal((T, W, H, 1)))
        bm.normal_update()
        for f in {f for v in res['verts'] for f in v.link_faces}:
            f.material_index = 0
            if f.normal.dot(nrm) > 0.9:
                f.material_index = 1
                # u along the plate width (left -> right as seen from outside), v up
                rgt = nrm.cross(up)
                for l in f.loops:
                    d = l.vert.co - c
                    u = 0.5 - d.dot(rgt) / W
                    v = 0.5 + d.dot(up) / H
                    l[uv].uv = (u, (n_variants - 1 - variant + v) / n_variants)
    out = _mesh(spec['name'] + '_plates', bm, [M['trim'], plate_material(M)], coll, smooth=False)
    return out


def plate_material(M):
    import os
    m = bpy.data.materials.get('car_plate_tex')
    if m is None:
        m = bpy.data.materials.new('car_plate_tex')
        m.use_nodes = True
        nt = m.node_tree
        b = nt.nodes['Principled BSDF']
        tex = nt.nodes.new('ShaderNodeTexImage')
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tex', 'plates.png')
        tex.image = bpy.data.images.load(path, check_existing=True)
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.45
    return m


def antenna(spec, M, coll, body):
    from .ops import raycast
    x = spec.get('antenna_x')
    if x is None:
        return None
    hit, nor = raycast(body, (x, 0.0, 3.0), (0, 0, -1))
    if not hit:
        return None
    bm = bmesh.new()
    # shark fin: wedge (long base, short raked top), subdivided
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        u, top = v.co.x + 0.5, v.co.z > 0
        if top:
            v.co = Vector((x - 0.075 + u * 0.06, v.co.y * 0.014, hit.z + 0.06))
        else:
            v.co = Vector((x - 0.09 + u * 0.18, v.co.y * 0.06, hit.z - 0.01))
    me = bpy.data.meshes.new('ant_tmp')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(spec['name'] + '_antenna', me)
    coll.objects.link(ob)
    me.materials.append(M['gloss'])
    s = ob.modifiers.new('s', 'SUBSURF')
    s.levels = 2
    from .ops import apply_mods
    apply_mods(ob)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def _rbox_m(bm, m, size, r, mat, seg=1):
    """rounded box with an arbitrary placement matrix m (rotation + translation)."""
    before = set(bm.faces)
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal((*size, 1)))
    es = list({e for v in res['verts'] for e in v.link_edges})
    if r > 0:
        bmesh.ops.bevel(bm, geom=es, offset=r, segments=seg, affect='EDGES', profile=0.5, clamp_overlap=True)
    for f in bm.faces:
        if f not in before:
            f.material_index = mat


def _rot(x, y, z, ry=0.0, rx=0.0):
    return Matrix.Translation((x, y, z)) @ Matrix.Rotation(ry, 4, 'Y') @ Matrix.Rotation(rx, 4, 'X')


def cabin(spec, M, coll):
    """low-poly seats, dash, console, steering wheel and parcel shelf. Materials: 0 interior, 1 seats."""
    c = spec['cabin']
    bm = bmesh.new()
    fx, rx, sy, hz = c['front_x'], c['rear_x'], c['seat_y'], c['hip_z']
    rad = math.radians
    for y in (sy, -sy):
        _rbox_m(bm, _rot(fx, y, hz - 0.03), (0.50, 0.50, 0.13), 0.04, 1)                      # cushion
        _rbox_m(bm, _rot(fx - 0.27, y, hz + 0.29, ry=rad(-14)), (0.12, 0.50, 0.62), 0.04, 1)  # backrest
        _rbox_m(bm, _rot(fx - 0.36, y, hz + 0.69, ry=rad(-10)), (0.09, 0.26, 0.17), 0.03, 1)  # headrest
        _rbox_m(bm, _rot(fx - 0.02, y, hz - 0.17), (0.40, 0.36, 0.16), 0.0, 0)                # base
    w = c.get('bench_w', 1.30)
    _rbox_m(bm, _rot(rx, 0, hz - 0.01), (0.48, w, 0.14), 0.04, 1)
    _rbox_m(bm, _rot(rx - 0.27, 0, hz + 0.27, ry=rad(-18)), (0.12, w, 0.56), 0.04, 1)
    for y in (0.40, -0.40):
        _rbox_m(bm, _rot(rx - 0.36, y, hz + 0.63, ry=rad(-14)), (0.09, 0.24, 0.15), 0.03, 1)
    dx = c['dash_x']
    dash_w = c.get('dash_w', 1.42)
    _rbox_m(bm, _rot(dx + 0.08, 0, c.get('dash_z', 0.84)), (0.46, dash_w, 0.22), 0.06, 0)
    _rbox_m(bm, _rot(dx - 0.12, 0, c.get('dash_z', 0.84) - 0.10, ry=rad(30)), (0.18, dash_w - 0.06, 0.22), 0.04, 0)
    _rbox_m(bm, _rot(dx - 0.30, 0, hz - 0.08), (0.75, 0.22, 0.26), 0.04, 0)                  # console
    # steering wheel: rim torus + hub, tilted towards the driver
    wx, wy, wz = c['wheel']
    m = Matrix.Translation((wx, wy, wz)) @ Matrix.Rotation(rad(-62), 4, 'Y')
    R, r, n1, n2 = 0.185, 0.016, 20, 5
    rings = []
    for i in range(n1):
        a = 2 * math.pi * i / n1
        ring = []
        for j in range(n2):
            b = 2 * math.pi * j / n2
            p = Vector(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
            ring.append(bm.verts.new(m @ p))
        rings.append(ring)
    for i in range(n1):
        for j in range(n2):
            f = bm.faces.new((rings[i][j], rings[(i + 1) % n1][j], rings[(i + 1) % n1][(j + 1) % n2], rings[i][(j + 1) % n2]))
            f.material_index = 0
    _rbox_m(bm, m @ Matrix.Translation((0, 0, 0.01)), (0.12, 0.10, 0.05), 0.02, 0)
    _rbox_m(bm, m @ Matrix.Translation((-0.0, -0.09, 0.0)), (0.03, 0.17, 0.02), 0.0, 0)
    _rbox_m(bm, m @ Matrix.Translation((0, 0, -0.12)), (0.05, 0.05, 0.22), 0.0, 0)          # column
    if 'shelf' in c:
        x0, x1, z = c['shelf']
        _rbox_m(bm, _rot((x0 + x1) / 2, 0, z), (abs(x1 - x0), c.get('shelf_w', 1.30), 0.02), 0.0, 0)
    bm.normal_update()
    return _mesh(spec['name'] + '_cabin', bm, [M['interior'], M['interior2']], coll, smooth=False)
