"""Assembles a car: body shell (cage -> mirror -> subdivision), glass/trim assignment, and parts."""
import bmesh
import bpy

from . import body, ops, parts
from .materials import define as define_materials


def _sidx(spec, key):
    if isinstance(key, int):
        return key
    for i, st in enumerate(spec['stations']):
        if st.get('id') == key:
            return i
    raise KeyError(key)


def _link(ob, coll):
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)


def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def clear_collection(c):
    for ob in list(c.objects):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and getattr(me, 'users', 1) == 0:
            bpy.data.meshes.remove(me)


def make_body(spec, M, coll, level=2):
    bm, grid, faces, caps = body.build_cage(spec)
    mats = ['paint', 'glass', 'gloss', 'trim']
    mi = {k: i for i, k in enumerate(mats)}
    glass = set()
    for rule in spec.get('glass', []):
        if rule[0] == 'side':
            s0, s1 = _sidx(spec, rule[1]), _sidx(spec, rule[2])
            for s in range(s0, s1):
                for k in rule[3]:
                    glass.add(faces[('side', s, k)])
        elif rule[0] in ('rear', 'front'):
            for r in rule[1]:
                for c in range(2):
                    glass.add(faces[(rule[0], r, c)])
    for f in glass:
        f.material_index = mi['glass']
    crease = bm.edges.layers.float.get('crease_edge') or bm.edges.layers.float.new('crease_edge')
    # window seals: inset each glass region; the rim becomes gloss black, edges stay crisp under subdivision
    if glass:
        res = bmesh.ops.inset_region(bm, faces=list(glass), thickness=spec.get('seal', 0.03), depth=-0.006,
                                     use_even_offset=True, use_boundary=False)
        for f in res['faces']:
            f.material_index = mi['gloss']
            for e in f.edges:
                e[crease] = 0.85
    for e in bm.edges:
        fs = e.link_faces
        if len(fs) == 2 and fs[0].material_index != fs[1].material_index:
            e[crease] = max(e[crease], 0.9)
    # shoulder line
    S = len(spec['stations'])
    for s in range(S - 1):
        e = bm.edges.get((grid[s][6], grid[s + 1][6]))
        if e:
            e[crease] = max(e[crease], spec.get('shoulder_crease', 0.55))
    # explicit ring creases: (station, k from, k to, value), e.g. the bonnet front edge
    for (si, k0, k1, val) in spec.get('ring_creases', []):
        si = _sidx(spec, si) if not isinstance(si, int) or si >= 0 else S + si
        for k in range(k0, k1):
            e = bm.edges.get((grid[si][k], grid[si][k + 1]))
            if e:
                e[crease] = max(e[crease], val)
    # full mesh (mirror in bmesh so the compensation below sees both halves)
    bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], axis='Y', merge_dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(spec['name'] + '_body')
    bm.to_mesh(me)
    bm.free()
    for k in mats:
        me.materials.append(M[k])
    ob = bpy.data.objects.new(spec['name'] + '_body', me)
    coll.objects.link(ob)
    sub = ob.modifiers.new('subd', 'SUBSURF')
    sub.levels = level
    sub.render_levels = level
    for p in me.polygons:
        p.use_smooth = True
    compensate(ob, iters=spec.get('comp_iters', 6))
    return ob


def compensate(ob, iters=6, damp=1.0):
    """move the cage so the subdivided surface passes through the designed points (the cage as built).
    Subsurf keeps the original vertices first, so the evaluated vertex i is where cage vertex i lands."""
    me = ob.data
    n = len(me.vertices)
    target = [v.co.copy() for v in me.vertices]
    for _ in range(iters):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg).data
        err = 0.0
        for i in range(n):
            d = target[i] - ev.vertices[i].co
            err = max(err, d.length)
            me.vertices[i].co += d * damp
        me.update()
    return err


def build(spec, level=2, decimate=None):
    M = define_materials()
    coll = collection('CAR_' + spec['name'])
    clear_collection(coll)
    ob = make_body(spec, M, coll, level=level)
    ops.apply_mods(ob)
    ratio = spec.get('decimate', decimate)
    if ratio and ratio < 1:
        d = ob.modifiers.new('dec', 'DECIMATE')
        d.decimate_type = 'COLLAPSE'
        d.ratio = ratio
        d.use_symmetry = True
        d.symmetry_axis = 'Y'
        d.use_collapse_triangulate = True
        ops.apply_mods(ob)
    out = {'body': ob}
    cut_arches(spec, M, ob, coll)
    out.update(cut_features(spec, M, ob, coll))
    out['wheels'] = make_wheels(spec, M, coll)
    out.update(make_parts(spec, M, coll, ob, out))
    out['shell'] = inner_shell(spec, M, coll)
    return out


def make_parts(spec, M, coll, body, out):
    res = {}
    hard = [body] + out.get('parts', [])
    if 'mirror' in spec:
        res['mirrors'] = parts.mirror_housing(spec, M, coll, body)
    if 'handles' in spec:
        res['handles'] = parts.handles(spec, M, coll, body)
    if 'wipers' in spec:
        res['wipers'] = parts.wipers(spec, M, coll, out.get('glass', []) + [body])
    if 'plate_z' in spec:
        res['plates'] = parts.plates(spec, M, coll, hard)
    if 'antenna_x' in spec:
        res['antenna'] = parts.antenna(spec, M, coll, body)
    if 'cabin' in spec:
        res['cabin'] = parts.cabin(spec, M, coll)
    return res


def inner_shell(spec, M, coll, shrink=0.03):
    """cabin lining seen through the glass: the coarse cage (its points lie on the designed surface, so its flat
    faces sit inside the smooth body) shrunk inwards, window / arch openings cut out, normals flipped."""
    bm, grid, faces, caps = body.build_cage(spec)
    bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], axis='Y', merge_dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    for v in bm.verts:
        v.co -= v.normal * shrink
    me = bpy.data.meshes.new(spec['name'] + '_shell')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M['interior'])
    ob = bpy.data.objects.new(spec['name'] + '_shell', me)
    coll.objects.link(ob)
    cut = _cutmat()
    for n, f in enumerate(spec.get('features', [])):
        if f['type'] != 'window':
            continue
        outer = ops.offset_poly(_poly(f, 'outer'), f.get('seal', 0.022) * 0.5)
        for c in _prisms(f, outer, coll, cut, f'shellcut{n}'):
            ops.boolean(ob, c, 'DIFFERENCE')
    R = spec['wheel_r']
    y0 = spec['track'] / 2 - 0.25
    for ax in spec['axles']:
        for a, b in ((y0, 1.5), (-1.5, -y0)):
            c = ops.cylinder('arch_cut', (ax, R), spec.get('arch_r', R + 0.06) + 0.03, a, b, seg=24, mat=cut, coll=coll)
            ops.boolean(ob, c, 'DIFFERENCE')
    ops.delete_faces_with_material(ob, cut.name)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def _mirror_poly(f, poly):
    if f['view'] == 'front':
        return [(-u, v) for u, v in poly][::-1]
    return poly


def _prisms(f, poly, coll, mat, tag):
    """one prism per side (mirrored features get the second side)."""
    d0, d1 = f['depth']
    out = [ops.prism(tag, poly, f['view'], d0, d1, mat, coll)]
    if f.get('mirror', True):
        if f['view'] == 'side':
            out.append(ops.prism(tag + '_r', poly, 'side', -d1, -d0, mat, coll))
        elif f['view'] == 'front':
            out.append(ops.prism(tag + '_r', _mirror_poly(f, poly), 'front', d0, d1, mat, coll))
    return out


def _poly(f, key='poly'):
    p = f[key]
    return ops.rounded(p, f.get('radii', 0.0), seg=f.get('seg', 5))


def cut_arches(spec, M, ob, coll):
    R = spec['wheel_r']
    ar = spec.get('arch_r', R + 0.06)
    for ax in spec['axles']:
        for sgn in (1, -1):
            y0, y1 = spec['track'] / 2 - 0.22, 1.5
            c = ops.cylinder('arch_cut', (ax, R + spec.get('arch_dz', 0.0)), ar, *(sorted((sgn * y0, sgn * y1)))
                             , seg=48, mat=M['liner'], coll=coll)
            ops.boolean(ob, c, 'DIFFERENCE')


def _cutmat():
    m = bpy.data.materials.get('car_cut_tmp') or bpy.data.materials.new('car_cut_tmp')
    return m


def _inward(f):
    """axis index and the sign pointing into the car for a feature's prisms (first / left copy)."""
    ax = ops.AXIS[f['view']]
    if f['view'] == 'top':
        return ax, -1
    d0, d1 = f['depth']
    return ax, (-1 if d0 + d1 > 0 else 1)


def _split(ob, cutter, mat, cut):
    """faces of ob inside cutter -> material mat (cutter is consumed)."""
    part = ops.duplicate(ob, ob.name + '_part')
    ops.boolean(part, cutter, 'INTERSECT', remove_cutter=False)
    ops.boolean(ob, cutter, 'DIFFERENCE')
    ops.delete_faces_with_material(part, cut.name)
    ops.delete_faces_with_material(ob, cut.name)
    ops.set_material(part, mat)
    ops.merge_into(ob, part)


def _take(ob, cutter, cut, name):
    """patch = ob inside cutter (returned, cutter faces removed); ob loses it (cutter consumed)."""
    p = ops.duplicate(ob, name)
    ops.boolean(p, cutter, 'INTERSECT', remove_cutter=False)
    ops.delete_faces_with_material(p, cut.name)
    ops.boolean(ob, cutter, 'DIFFERENCE')
    return p


def _recess(spec, M, ob, coll, f, n, cut, out, parts):
    """lamp / grille / plate pocket: the outlined surface patch becomes the lens (or is dropped), a sunk copy is the
    housing floor, walls join the two. zones split the floor (optionally raised: bars, DRL strips)."""
    ax, sgn = _inward(f)
    poly = _poly(f, 'poly')
    for side, c in enumerate(_prisms(f, poly, coll, cut, f'rc{n}')):
        s = sgn if side == 0 else (-sgn if f['view'] == 'side' else sgn)
        p = _take(ob, c, cut, f'{spec["name"]}_{f.get("name", "recess")}{n}_{side}')
        fl = ops.pocket(p, ax, s, f.get('sink', 0.04), M[f.get('floor', 'trim')], M[f.get('wall', f.get('floor', 'trim'))],
                        coll, p.name + '_housing')
        for z in f.get('zones', []):
            zp = ops.rounded(z['poly'], z.get('radii', 0.0), seg=4)
            zf = dict(f, mirror=False)
            if side == 1:
                zp = _mirror_poly(f, zp) if f['view'] == 'front' else zp
            d0, d1 = f['depth']
            if side == 1 and f['view'] == 'side':
                d0, d1 = -d1, -d0
            zc = ops.prism('zone', zp, f['view'], d0, d1, cut, coll)
            if z.get('lift'):
                zpatch = _take(fl, zc, cut, fl.name + '_z')
                bar = ops.pocket(zpatch, ax, -s, z['lift'], M[z['mat']], M[z.get('wall', z['mat'])], coll,
                                 fl.name + '_bar', raised=True)
                bpy.data.objects.remove(zpatch)
                ops.delete_faces_with_material(fl, cut.name)
                ops.merge_into(fl, bar)
            else:
                _split(fl, zc, M[z['mat']], cut)
        parts.append(fl)
        if f.get('lens'):
            ops.set_material(p, M[f['lens']])
            if M[f['lens']].name in ('car_lens', 'car_glass', 'car_tail_lens'):
                out.setdefault('glass', []).append(p)
            else:
                parts.append(p)
        else:
            me = p.data
            bpy.data.objects.remove(p)
            bpy.data.meshes.remove(me)


def _gap(spec, M, ob, coll, f, n, cut):
    w = f.get('w', 0.005)
    lines = f['lines'] if 'lines' in f else [f['line']]
    for i, ln in enumerate(lines):
        poly = ops.gap_poly(ln, w)
        for c in _prisms(f, poly, coll, M['liner'], f'gap{n}_{i}'):
            ops.boolean(ob, c, 'DIFFERENCE')


def cut_features(spec, M, ob, coll):
    """windows / lamps / grilles / gaps from projected outlines. Order of the spec list matters: lamps before the
    gaps that run across them, everything before the windows (they open the shell)."""
    out = {}
    cut = _cutmat()
    patches = []          # merged into the body at the end
    parts = []            # separate opaque meshes (housings, lenses that are opaque)
    for n, f in enumerate(spec.get('features', [])):
        kind = f['type']
        if kind == 'patch':
            for c in _prisms(f, _poly(f, 'poly'), coll, cut, f'patch{n}'):
                p = _take(ob, c, cut, f'{spec["name"]}_patch{n}')
                ops.set_material(p, M[f['mat']])
                patches.append(p)
        elif kind in ('recess', 'lamp'):
            _recess(spec, M, ob, coll, f, n, cut, out, parts)
        elif kind == 'gap':
            _gap(spec, M, ob, coll, f, n, cut)
        elif kind == 'window':
            outer = _poly(f, 'outer')
            outer_g = ops.offset_poly(outer, f.get('seal', 0.022))
            inner = [ops.rounded(p, f.get('inner_radii', 0.03), seg=4) for p in f['inner']] if 'inner' in f else [outer]
            for i, ip in enumerate(inner):
                for c in _prisms(f, ip, coll, cut, f'win{n}_{i}'):
                    g = ops.duplicate(ob, f'{spec["name"]}_glass{n}_{i}')
                    ops.boolean(g, c, 'INTERSECT')
                    ops.delete_faces_with_material(g, 'car_cut_tmp')
                    ops.set_material(g, M['glass'])
                    out.setdefault('glass', []).append(g)
            for c in _prisms(f, outer_g, coll, cut, f'seal{n}'):
                t = ops.duplicate(ob, f'{spec["name"]}_seal{n}')
                ops.boolean(t, c, 'INTERSECT', remove_cutter=False)
                for ip in inner:
                    for c2 in _prisms(f, ip, coll, cut, 'pane_cut'):
                        ops.boolean(t, c2, 'DIFFERENCE')
                ops.delete_faces_with_material(t, 'car_cut_tmp')
                ops.set_material(t, M[f.get('frame', 'gloss')])
                patches.append(t)
                ops.boolean(ob, c, 'DIFFERENCE')
    ops.delete_faces_with_material(ob, 'car_cut_tmp')
    for t in patches:
        ops.merge_into(ob, t)
    out['parts'] = parts
    return out
