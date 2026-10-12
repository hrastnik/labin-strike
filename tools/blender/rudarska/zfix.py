"""Z-fighting resolver. Faces of different materials that face the same way, overlap, and lie closer
than MIN_SEP to each other flicker in-game (24-bit depth). After the groups are built, the face that
belongs to the smaller connected piece (sill, frame, taillight, path...) is pushed along its normal
until the pair is MIN_SEP apart, keeping whichever was in front in front (exact ties: the small piece
wins). Ground overlays (road paint, manholes, grates) and `_dec` decals are left alone: the client
draws those with polygon offset."""
import math
from collections import defaultdict

import bmesh
import bpy
from mathutils import Vector

MIN_SEP = 0.015
CELL = 1.0
OVERLAY = ('road_paint', 'manhole', 'grate')   # keep in sync with OVERLAY_RE in client/src/renderer.js


def offset_kind(mat):
    if '_dec' in mat:
        return 'dec'
    if any(k in mat for k in OVERLAY):
        return 'overlay'
    return None


def _basis(n):
    a = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
    u = n.cross(a).normalized()
    return u, n.cross(u)


def _clip(poly, a, b):
    out = []
    def side(p):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        sp, sq = side(p), side(q)
        if sp >= 0:
            out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def _area2(poly):
    s = 0.0
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        s += p[0] * q[1] - q[0] * p[1]
    return s / 2


def _ccw(t):
    return t if _area2(t) > 0 else [t[0], t[2], t[1]]


class Scene:
    """triangles of every visible mesh (world space) with their face, material and island."""

    def __init__(self, skip_parents=('Backdrop',)):
        self.meshes = []   # (object, bmesh)
        self.tris = []     # (mesh idx, face idx, mat, normal, plane d, 3 points)
        self.island_area = []   # per mesh: island id -> area
        self.face_island = []   # per mesh: face idx -> island id
        for ob in bpy.data.objects:
            if ob.type != 'MESH' or ob.name.startswith(('COL_', 'CLIP_')):
                continue
            if ob.parent and ob.parent.name in skip_parents:
                continue
            assert ob.matrix_world == ob.matrix_world.Identity(4), ob.name
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.normal_update()
            mi = len(self.meshes)
            self.meshes.append((ob, bm))
            mats = [s.material.name if s.material else '-' for s in ob.material_slots]
            # islands (connected by shared vertices)
            parent = list(range(len(bm.verts)))
            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x
            for f in bm.faces:
                vs = [v.index for v in f.verts]
                r0 = find(vs[0])
                for v in vs[1:]:
                    r = find(v)
                    if r != r0:
                        parent[r] = r0
            fi = [find(f.verts[0].index) for f in bm.faces]
            ia = defaultdict(float)
            for f in bm.faces:
                ia[fi[f.index]] += f.calc_area()
            self.face_island.append(fi)
            self.island_area.append(ia)
            for lt in bm.calc_loop_triangles():
                f = lt[0].face
                pts = [l.vert.co.copy() for l in lt]
                n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
                if n.length < 2e-5:
                    continue
                n.normalize()
                self.tris.append((mi, f.index, mats[f.material_index] if mats else '-', n, n.dot(pts[0]), pts))

    def island_size(self, t):
        return self.island_area[t[0]][self.face_island[t[0]][t[1]]]

    def pairs(self, gap_max, skip_same_mat=True, skip_down=True):
        """yield (tri_i, tri_j, gap, overlap area) for overlapping near-coplanar same-facing triangles."""
        tris = self.tris
        dirs = defaultdict(list)
        for i, t in enumerate(tris):
            n = t[3]
            dirs[(round(n.x * 20), round(n.y * 20), round(n.z * 20))].append(i)
        seen = set()
        for key, idx in dirs.items():
            cand = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        cand += dirs.get((key[0] + dx, key[1] + dy, key[2] + dz), [])
            n0 = tris[idx[0]][3]
            u, v = _basis(n0)
            grid = defaultdict(list)
            proj = {}
            for j in cand:
                t = tris[j]
                if t[3].dot(n0) < 0.9995:
                    continue
                p2 = _ccw([(p.dot(u), p.dot(v)) for p in t[5]])
                proj[j] = p2
                xs = [p[0] for p in p2]; ys = [p[1] for p in p2]
                for cx in range(math.floor(min(xs) / CELL), math.floor(max(xs) / CELL) + 1):
                    for cy in range(math.floor(min(ys) / CELL), math.floor(max(ys) / CELL) + 1):
                        grid[(cx, cy, math.floor(t[4] / gap_max))].append(j)
            for i in idx:
                if i not in proj:
                    continue
                ti = tris[i]
                if skip_down and ti[3].z < -0.5:
                    continue   # box bottoms are never seen
                pi = proj[i]
                xs = [p[0] for p in pi]; ys = [p[1] for p in pi]
                others = set()
                db = math.floor(ti[4] / gap_max)
                for cx in range(math.floor(min(xs) / CELL), math.floor(max(xs) / CELL) + 1):
                    for cy in range(math.floor(min(ys) / CELL), math.floor(max(ys) / CELL) + 1):
                        for dd in (-1, 0, 1):
                            others.update(grid.get((cx, cy, db + dd), ()))
                for j in others:
                    if j == i:
                        continue
                    key2 = (i, j) if i < j else (j, i)
                    if key2 in seen:
                        continue
                    seen.add(key2)
                    tj = tris[j]
                    if skip_same_mat and ti[2] == tj[2]:
                        continue   # same material: world-projected UVs make the overlap invisible
                    if ti[0] == tj[0] and ti[1] == tj[1]:
                        continue
                    gap = abs(ti[4] - tj[4])
                    if gap >= gap_max:
                        continue
                    poly = pi
                    pj = proj[j]
                    for k in range(3):
                        poly = _clip(poly, pj[k], pj[(k + 1) % 3])
                        if len(poly) < 3:
                            break
                    if len(poly) < 3:
                        continue
                    a = _area2(poly)
                    if a < 1e-5:
                        continue
                    yield ti, tj, gap, a

    def free(self, write=False):
        for ob, bm in self.meshes:
            if write:
                bm.to_mesh(ob.data)
                ob.data.update()
            bm.free()


def needs_fix(ti, tj):
    ki, kj = offset_kind(ti[2]), offset_kind(tj[2])
    if ki == 'dec' or kj == 'dec':
        return False   # decals don't write depth; decal vs surface is polygon-offset
    if (ki == 'overlay') != (kj == 'overlay'):
        return False   # overlay vs ground is polygon-offset
    return True


def resolve(min_sep=MIN_SEP, passes=8):
    """push apart every flickering pair; repeats because one push can create a new near-pair."""
    total = 0
    locked = {}   # face -> direction it was pushed in; a face never reverses (prevents ping-pong)
    for _ in range(passes):
        sc = Scene()
        moves = {}   # (mesh idx, face idx) -> signed distance along the face normal
        for ti, tj, gap, a in sc.pairs(min_sep - 1e-4):
            if not needs_fix(ti, tj):
                continue
            si, sj = sc.island_size(ti), sc.island_size(tj)
            order = [(ti, tj), (tj, ti)] if (si, ti[1]) <= (sj, tj[1]) else [(tj, ti), (ti, tj)]
            for mover, other in order:
                front = mover[4] - other[4] >= -1e-5
                sign = 1 if front else -1
                k = (mover[0], mover[1])
                if locked.get(k, sign) != sign:
                    continue   # would undo an earlier push: move the other face instead
                amt = (min_sep - gap) * sign
                if abs(amt) > abs(moves.get(k, 0.0)):
                    moves[k] = amt
                break
        for k, amt in moves.items():
            locked[k] = 1 if amt > 0 else -1
        if not moves:
            sc.free()
            break
        # per vertex: largest push per normal direction, summed over directions (box corners)
        per_vert = defaultdict(dict)
        for (mi, fi), amt in moves.items():
            bm = sc.meshes[mi][1]
            f = bm.faces[fi]
            n = f.normal
            dk = (round(n.x, 2), round(n.y, 2), round(n.z, 2))
            for v in f.verts:
                d = per_vert[(mi, v.index)]
                if abs(amt) > abs(d.get(dk, (0.0, None))[0]):
                    d[dk] = (amt, n.copy())
        for (mi, vi), d in per_vert.items():
            v = sc.meshes[mi][1].verts[vi]
            for amt, n in d.values():
                v.co += n * amt
        total += len(moves)
        print(f'[zfix] pushed {len(moves)} faces')
        sc.free(write=True)
    return total
