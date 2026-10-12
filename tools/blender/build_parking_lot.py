"""
Builds the low-poly "Rudarska ulica" parking-lot arena (Labin, HR) and exports it as GLB.

Run inside Blender (e.g. through the Blender MCP):  exec(open(PATH).read(), {'__file__': PATH})

Conventions consumed by the game (client + server):
  COL_*      unit-cube mesh (verts at +-1) whose node TRS describes an oriented box collider
             that blocks players AND bullets
  CLIP_*     same as COL_ but only blocks players (invisible boundaries, bullets pass)
  SPAWN_<team>_NN   empty marking a team spawn point (team = allies | axis)
  BOUNDS_MIN / BOUNDS_MAX  empties spanning the playable area (used for the bot nav grid)
Everything else is render-only geometry.

Blender axes: +X runs along the street towards NW, +Y points across towards the parking lot (NE), +Z up.
"""
import bpy
import bmesh
import math
import os
import random
import numpy as np
from mathutils import Matrix, Vector, Euler

try:
    PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:  # exec(open(PATH).read()) leaves __file__ unset
    PROJECT = os.environ["LABIN_STRIKE_DIR"]
OUT_GLB = os.path.join(PROJECT, "client/public/assets/maps/parking_lot.glb")
OUT_BLEND = os.path.join(PROJECT, "tools/blender/parking_lot.blend")
TEX_DIR = os.path.join(PROJECT, "tools/blender/textures")
SCENE_NAME = "LabinParkingLot"
PREFIX = "LS_"  # prefix for every datablock this script owns

rng = random.Random(7344)
os.makedirs(TEX_DIR, exist_ok=True)

LOT_Z = 0.12  # sidewalks / parking lot surface height (street is at 0)
TERRACE_Z = 2.72

# --------------------------------------------------------------------------------------------
# scene setup (non-destructive: builds into its own scene, only removes our own datablocks)
# --------------------------------------------------------------------------------------------

def reset_scene():
    old = bpy.data.scenes.get(SCENE_NAME)
    if old:
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for c in list(old.collection.children_recursive):
            bpy.data.collections.remove(c)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.curves):
        for b in list(coll):
            if b.name.startswith(PREFIX) and b.users == 0:
                coll.remove(b)
    scene = old or bpy.data.scenes.new(SCENE_NAME)
    scene.unit_settings.system = 'METRIC'
    bpy.context.window.scene = scene
    return scene


scene = reset_scene()


def collection(name):
    full = PREFIX + name
    c = bpy.data.collections.get(full)
    if c is None:
        c = bpy.data.collections.new(full)
    if c.name not in scene.collection.children:
        scene.collection.children.link(c)
    return c


C_VIS = collection("Visual")
C_COL = collection("Colliders")
C_META = collection("Markers")

# --------------------------------------------------------------------------------------------
# procedural textures (tileable, generated with numpy; written as sRGB PNGs)
# --------------------------------------------------------------------------------------------
N = 512


def up_periodic(g):
    s = g.shape[0]
    x = np.arange(N) * s / N
    i0 = np.floor(x).astype(int)
    f = x - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % s
    a = g[np.ix_(i0, i0)]
    b = g[np.ix_(i0, i1)]
    c = g[np.ix_(i1, i0)]
    d = g[np.ix_(i1, i1)]
    fx = f[None, :]
    fy = f[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(seed, scales=(4, 8, 16, 32, 64, 128), gain=0.55):
    r = np.random.default_rng(seed)
    out = np.zeros((N, N))
    amp, tot = 1.0, 0.0
    for s in scales:
        out += amp * up_periodic(r.random((s, s)))
        tot += amp
        amp *= gain
    return out / tot


def streaks(seed, cols=64):
    """vertical grime streaks (rows = y)."""
    r = np.random.default_rng(seed)
    g = r.random(cols)
    x = np.arange(N) * cols / N
    i0 = np.floor(x).astype(int)
    f = x - i0
    v = g[i0] * (1 - f) + g[(i0 + 1) % cols] * f
    return np.tile(v[None, :], (N, 1))


def save_tex(name, rgb):
    rgb = np.clip(rgb, 0, 1)
    rgba = np.concatenate([rgb, np.ones((N, N, 1))], axis=2)
    img = bpy.data.images.get(PREFIX + name)
    if img is None:
        img = bpy.data.images.new(PREFIX + name, N, N, alpha=False)
    img.pixels.foreach_set(rgba[::-1].astype(np.float32).ravel())
    path = os.path.join(TEX_DIR, name + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return img


def tint(base, v):
    return np.stack([v * base[0], v * base[1], v * base[2]], axis=2)


def blocks_pattern(seed, row_h, wmin, wmax, mortar=3, jitter=0.1):
    """returns (block_id_value, mortar_mask) for a running-bond stone pattern, tileable."""
    r = np.random.default_rng(seed)
    val = np.zeros((N, N))
    mask = np.zeros((N, N))
    rows = N // row_h
    for ri in range(rows):
        y0 = ri * row_h
        x = int(r.integers(0, wmax))
        widths = []
        total = 0
        while total < N:
            w = int(r.integers(wmin, wmax))
            if N - total - w < wmin:
                w = N - total
            widths.append(w)
            total += w
        cx = x
        for w in widths:
            v = 1 + r.uniform(-jitter, jitter)
            xs = (np.arange(cx, cx + w)) % N
            val[y0:y0 + row_h][:, xs] = v
            mask[y0:y0 + row_h][:, xs[:mortar]] = 1
            cx += w
        mask[y0:y0 + mortar, :] = 1
    return val, mask


def make_textures():
    T = {}
    n1, n2, n3 = fbm(1), fbm(2), fbm(3, scales=(2, 4, 8))
    r = np.random.default_rng(9)
    speck = (r.random((N, N)) > 0.985).astype(float)

    # asphalt
    v = 0.78 + 0.28 * n1 + 0.12 * (n3 - 0.5) - 0.18 * speck + 0.1 * (r.random((N, N)) - 0.5)
    T['asphalt'] = save_tex('asphalt', tint((0.30, 0.30, 0.31), v))

    # parking lot concrete-asphalt (lighter, stained, panel joints)
    v = 0.82 + 0.22 * n2 + 0.25 * (n3 - 0.5) + 0.06 * (r.random((N, N)) - 0.5)
    stain = np.clip((fbm(11, scales=(3, 6, 12)) - 0.58) * 4, 0, 1)
    v -= 0.22 * stain
    v[:, 0:2] *= 0.75
    v[0:2, :] *= 0.75
    T['lot'] = save_tex('lot', tint((0.58, 0.57, 0.55), v))

    # sidewalk pavers
    v = 0.86 + 0.16 * n1 + 0.05 * (r.random((N, N)) - 0.5)
    for k in range(0, N, 128):
        v[:, k:k + 2] *= 0.7
        v[k:k + 2, :] *= 0.7
    T['sidewalk'] = save_tex('sidewalk', tint((0.70, 0.69, 0.66), v))

    # limestone cut blocks (building bases, retaining wall)
    bv, bm_ = blocks_pattern(21, 32, 50, 96, mortar=3)
    v = bv * (0.88 + 0.18 * fbm(22)) + 0.05 * (r.random((N, N)) - 0.5)
    v = v * (1 - 0.28 * bm_)
    T['limestone'] = save_tex('limestone', tint((0.86, 0.83, 0.74), v))

    # old rough stone wall (SE retaining wall) and graffiti variant
    bv, bm_ = blocks_pattern(31, 40, 40, 110, mortar=4, jitter=0.18)
    v = bv * (0.75 + 0.35 * fbm(32)) + 0.1 * (r.random((N, N)) - 0.5)
    v = v * (1 - 0.35 * bm_)
    stone = tint((0.62, 0.60, 0.54), v)
    T['oldstone'] = save_tex('oldstone', stone)
    g = stone.copy()
    yy, xx = np.mgrid[0:N, 0:N]
    rg = np.random.default_rng(77)
    palette = [(0.06, 0.06, 0.07), (0.10, 0.16, 0.45), (0.08, 0.08, 0.10), (0.55, 0.12, 0.10)]
    for s in range(26):
        col = palette[s % len(palette)]
        cx, cy = rg.uniform(30, N - 30), rg.uniform(180, 380)
        ang = rg.uniform(0, math.pi * 2)
        length, width = rg.uniform(30, 110), rg.uniform(5, 13)
        dx, dy = math.cos(ang), math.sin(ang) * 0.5
        t = np.clip(((xx - cx) * dx + (yy - cy) * dy) / length, -0.5, 0.5)
        px, py = cx + t * length * dx, cy + t * length * dy
        d = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
        a = np.clip((width - d) / 2.0, 0, 1)[..., None] * 0.9
        g = g * (1 - a) + np.array(col) * a
    T['graffiti'] = save_tex('graffiti', g)

    # plaster facades
    def plaster(name, base, seed):
        s = streaks(seed)
        v = 0.86 + 0.16 * fbm(seed) + 0.08 * (s - 0.5) + 0.04 * (r.random((N, N)) - 0.5)
        T[name] = save_tex(name, tint(base, v))

    plaster('plaster_beige', (0.86, 0.77, 0.58), 41)
    plaster('plaster_peach', (0.88, 0.68, 0.52), 42)
    plaster('plaster_gray', (0.72, 0.71, 0.66), 43)
    plaster('plaster_teal', (0.50, 0.74, 0.69), 44)
    plaster('plaster_red', (0.70, 0.32, 0.24), 45)

    # facade panels (sports center)
    v = 0.92 + 0.08 * n2
    for k in range(0, N, 128):
        v[:, k:k + 2] *= 0.72
    for k in range(0, N, 64):
        v[k:k + 1, :] *= 0.85
    T['panel'] = save_tex('panel', tint((0.60, 0.61, 0.62), v))

    # grass / dirt
    v = 0.7 + 0.45 * n1 + 0.25 * (fbm(51) - 0.5) + 0.1 * (r.random((N, N)) - 0.5)
    T['grass'] = save_tex('grass', tint((0.32, 0.46, 0.20), v))
    v = 0.75 + 0.4 * fbm(52) + 0.1 * (r.random((N, N)) - 0.5)
    T['dirt'] = save_tex('dirt', tint((0.42, 0.37, 0.27), v))

    # bricks (red building, chimney)
    bv, bm_ = blocks_pattern(61, 16, 44, 46, mortar=2, jitter=0.12)
    v = bv * (0.85 + 0.2 * n2)
    v = v * (1 - 0.35 * bm_)
    T['brick'] = save_tex('brick', tint((0.62, 0.30, 0.22), v))

    # hedges / foliage
    v = 0.65 + 0.6 * fbm(71, scales=(16, 32, 64, 128)) + 0.12 * (r.random((N, N)) - 0.5)
    T['leaves'] = save_tex('leaves', tint((0.25, 0.40, 0.15), v))
    return T


TEX = make_textures()

# --------------------------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------------------------
MATS = {}
TILE = {}  # material name -> world-space texture tile size (m)


def mat(name, color=(0.8, 0.8, 0.8), rough=0.9, metal=0.0, tex=None, tile=4.0, emit=None):
    key = PREFIX + name
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.get(key) or bpy.data.materials.new(key)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if tex is not None:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = TEX[tex]
        nt.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
        TILE[key] = tile
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1)
        bsdf.inputs["Emission Strength"].default_value = 2.0
    m.diffuse_color = (*color, 1)
    MATS[key] = m
    return m


M = {
    'asphalt': mat('asphalt', tex='asphalt', tile=6),
    'lot': mat('lot', tex='lot', tile=8),
    'sidewalk': mat('sidewalk', tex='sidewalk', tile=4),
    'curb': mat('curb', (0.45, 0.44, 0.42), 0.95),
    'paint': mat('paint_white', (0.85, 0.85, 0.82), 0.7),
    'paint_y': mat('paint_yellow', (0.80, 0.62, 0.08), 0.7),
    'limestone': mat('limestone', tex='limestone', tile=4),
    'oldstone': mat('oldstone', tex='oldstone', tile=5),
    'graffiti': mat('graffiti', tex='graffiti', tile=7),
    'beige': mat('plaster_beige', tex='plaster_beige', tile=5),
    'peach': mat('plaster_peach', tex='plaster_peach', tile=5),
    'gray': mat('plaster_gray', tex='plaster_gray', tile=5),
    'teal': mat('plaster_teal', tex='plaster_teal', tile=5),
    'redplaster': mat('plaster_red', tex='plaster_red', tile=5),
    'panel': mat('panel', tex='panel', tile=6),
    'grass': mat('grass', tex='grass', tile=6),
    'dirt': mat('dirt', tex='dirt', tile=8),
    'brick': mat('brick', tex='brick', tile=3),
    'leaves': mat('leaves', tex='leaves', tile=3),
    'pine': mat('pine', (0.05, 0.12, 0.05), 0.95),
    'bark': mat('bark', (0.12, 0.08, 0.05), 0.95),
    'glass': mat('window_glass', (0.04, 0.06, 0.08), 0.12, 0.4),
    'frame_white': mat('frame_white', (0.75, 0.75, 0.72), 0.6),
    'shutter': mat('shutter_brown', (0.30, 0.13, 0.06), 0.7),
    'frame_red': mat('frame_red', (0.40, 0.06, 0.04), 0.6),
    'door': mat('door_brown', (0.18, 0.09, 0.04), 0.6),
    'metal': mat('metal_gray', (0.35, 0.36, 0.37), 0.45, 0.8),
    'darkmetal': mat('metal_dark', (0.06, 0.06, 0.065), 0.5, 0.6),
    'concrete': mat('concrete', (0.50, 0.49, 0.46), 0.95),
    'roof_tile': mat('roof_tile', (0.42, 0.12, 0.06), 0.85),
    'roof_dark': mat('roof_dark', (0.18, 0.18, 0.19), 0.9),
    'ac': mat('ac_unit', (0.78, 0.78, 0.76), 0.5),
    'lamp': mat('lamp', (0.9, 0.85, 0.6), 0.3, emit=(1.0, 0.85, 0.55)),
    'tire': mat('tire', (0.025, 0.025, 0.025), 0.9),
    'headlight': mat('headlight', (0.9, 0.9, 0.85), 0.2),
    'taillight': mat('taillight', (0.6, 0.02, 0.02), 0.3),
    'bumper': mat('bumper', (0.06, 0.06, 0.06), 0.7),
    'dump_yellow': mat('dumpster_yellow', (0.85, 0.65, 0.02), 0.6),
    'dump_blue': mat('dumpster_blue', (0.03, 0.12, 0.55), 0.6),
    'sign_blue': mat('sign_blue', (0.05, 0.20, 0.65), 0.5),
    'sign_white': mat('sign_white', (0.9, 0.9, 0.9), 0.5),
    'truck_white': mat('truck_white', (0.82, 0.82, 0.80), 0.5),
    'flag_red': mat('flag_red', (0.6, 0.03, 0.03), 0.8),
    'flag_blue': mat('flag_blue', (0.03, 0.08, 0.45), 0.8),
    'glassblock': mat('glass_block', (0.55, 0.62, 0.65), 0.3),
    'sportglass': mat('sport_glass', (0.12, 0.16, 0.2), 0.1, 0.5),
    'hill': mat('hill_far', (0.10, 0.17, 0.07), 1.0),
    'cone': mat('cone_orange', (0.85, 0.25, 0.02), 0.6),
}
CAR_PAINTS = [mat('car_' + n, c, 0.35, 0.3) for n, c in [
    ('white', (0.78, 0.78, 0.78)), ('white2', (0.82, 0.82, 0.80)), ('silver', (0.40, 0.41, 0.43)),
    ('silver2', (0.30, 0.31, 0.33)), ('black', (0.015, 0.015, 0.018)), ('graphite', (0.08, 0.085, 0.09)),
    ('red', (0.45, 0.02, 0.015)), ('blue', (0.02, 0.05, 0.22)), ('navy', (0.01, 0.015, 0.06)),
    ('lime', (0.45, 0.55, 0.12)), ('maroon', (0.18, 0.02, 0.03)), ('beige', (0.50, 0.42, 0.30))]]

# --------------------------------------------------------------------------------------------
# geometry builder: accumulates primitives into one bmesh per group (few objects, few draw calls)
# --------------------------------------------------------------------------------------------


class MB:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []
        self.xf = Matrix.Identity(4)

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _tag(self, verts, m, smooth=False):
        idx = self.mi(m)
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = idx
            f.smooth = smooth

    def box(self, c, s, m, rz=0.0, rx=0.0, ry=0.0):
        mtx = self.xf @ Matrix.Translation(c) @ Euler((rx, ry, rz)).to_matrix().to_4x4() \
            @ Matrix.Diagonal((s[0], s[1], s[2], 1))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=mtx)
        self._tag(r['verts'], m)
        return r['verts']

    def box_mm(self, x0, x1, y0, y1, z0, z1, m):
        return self.box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), m)

    def tbox(self, c, s, m, top=(1, 1), shift=(0, 0), rz=0.0):
        """box whose top face is scaled by `top` (x, y) and shifted by `shift` (local units)."""
        r = bmesh.ops.create_cube(self.bm, size=1.0)
        for v in r['verts']:
            if v.co.z > 0:
                v.co.x = v.co.x * top[0] + shift[0]
                v.co.y = v.co.y * top[1] + shift[1]
        mtx = self.xf @ Matrix.Translation(c) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Diagonal((s[0], s[1], s[2], 1))
        bmesh.ops.transform(self.bm, matrix=mtx, verts=r['verts'])
        self._tag(r['verts'], m)
        return r['verts']

    def cyl(self, c, r, h, m, seg=8, r2=None, rx=0.0, ry=0.0, rz=0.0, smooth=True):
        mtx = self.xf @ Matrix.Translation(c) @ Euler((rx, ry, rz)).to_matrix().to_4x4()
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                                    radius1=r, radius2=r if r2 is None else r2, depth=h, matrix=mtx)
        self._tag(res['verts'], m, smooth)
        return res['verts']

    def blob(self, c, r, m, scale=(1, 1, 1), jitter=0.15, sub=1):
        mtx = self.xf @ Matrix.Translation(c) @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1))
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=r, matrix=mtx)
        for v in res['verts']:
            v.co += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * r * jitter
        self._tag(res['verts'], m)
        return res['verts']

    def build(self, coll=None):
        bm = self.bm
        bm.normal_update()
        uv = bm.loops.layers.uv.verify()
        for f in bm.faces:
            mname = self.mats[f.material_index].name
            tile = TILE.get(mname)
            if tile is None:
                continue
            n = f.normal
            ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
            for loop in f.loops:
                co = loop.vert.co
                if az >= ax and az >= ay:
                    u, v = co.x, co.y
                elif ax >= ay:
                    u, v = co.y, co.z
                else:
                    u, v = co.x, co.z
                loop[uv].uv = (u / tile, v / tile)
        me = bpy.data.meshes.new(PREFIX + self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        (coll or C_VIS).objects.link(ob)
        return ob


# collider unit cube (shared mesh -> exported once, instanced per node)
def unit_cube_mesh():
    me = bpy.data.meshes.get(PREFIX + "ColliderCube")
    if me:
        return me
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    me = bpy.data.meshes.new(PREFIX + "ColliderCube")
    bm.to_mesh(me)
    bm.free()
    return me


UNIT = unit_cube_mesh()
_col_count = {}


def collider(kind, c, s, rz=0.0, rx=0.0, ry=0.0, clip=False):
    prefix = "CLIP_" if clip else "COL_"
    n = _col_count.get(prefix + kind, 0) + 1
    _col_count[prefix + kind] = n
    ob = bpy.data.objects.new(f"{prefix}{kind}_{n:03d}", UNIT)
    ob.location = c
    ob.rotation_euler = (rx, ry, rz)
    ob.scale = (s[0] / 2, s[1] / 2, s[2] / 2)
    ob.display_type = 'WIRE'
    ob.hide_render = True
    C_COL.objects.link(ob)
    return ob


def collider_mm(kind, x0, x1, y0, y1, z0, z1, clip=False):
    return collider(kind, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), clip=clip)


def marker(name, loc):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = 'ARROWS'
    ob.empty_display_size = 1.0
    ob.location = loc
    C_META.objects.link(ob)
    return ob


def rot2(x, y, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return x * c - y * s, x * s + y * c


# groups
G_GROUND = MB("Ground")
G_BUILD = MB("Buildings")
G_CARS = MB("Vehicles")
G_PROPS = MB("Props")
G_FOLIAGE = MB("Foliage")
G_BACK = MB("Backdrop")

# --------------------------------------------------------------------------------------------
# ground, street, sidewalks, lot
# --------------------------------------------------------------------------------------------
X0, X1 = -52.0, 56.0
g = G_GROUND
g.box_mm(-300, 300, -300, 300, -0.6, -0.02, M['grass'])           # far ground
g.box_mm(X0 - 70, X1 + 10, -4, 4, -0.3, 0.0, M['asphalt'])         # street (continues NW)
g.box_mm(X0, 54, -14, -4.12, -0.3, LOT_Z, M['sidewalk'])           # SW sidewalk / forecourts
g.box_mm(27, 54, -13.5, -6.6, LOT_Z, LOT_Z + 0.005, M['lot'])     # admin forecourt surface
g.box_mm(X0, 54, 4.12, 5.6, -0.3, LOT_Z, M['sidewalk'])            # NE sidewalk strip
g.box_mm(-34, 54, 5.6, 35.5, -0.3, LOT_Z, M['lot'])                # parking lot
g.box_mm(X0, -34, 5.6, 14, -0.3, LOT_Z, M['sidewalk'])             # sports plaza
g.box_mm(X0 - 70, X0, 4.12, 9, -0.3, LOT_Z, M['sidewalk'])         # sidewalks beyond NW barrier
g.box_mm(X0 - 70, X0, -9, -4.12, -0.3, LOT_Z, M['sidewalk'])
# curbs
for y in (-4.12, 4.12):
    g.box_mm(X0 - 70, 54, y - 0.12, y + 0.12, 0.0, LOT_Z + 0.03, M['curb'])
# lane paint
g.box_mm(X0 - 70, 54, -0.07, 0.07, 0.0, 0.008, M['paint'])
for k in range(-48, 52, 6):  # pedestrian crossing near the sports center & admin
    pass
for x in (-31.5, 38.0):
    for i in range(6):
        y = -3.3 + i * 1.3
        g.box_mm(x - 1.6, x + 1.6, y, y + 0.55, 0.0, 0.009, M['paint'])

# colliders: ground slab + raised slabs
collider_mm("ground", -80, 90, -40, 60, -1.0, 0.0)
collider_mm("sidewalk", X0 - 2, 54, -16, -4.0, 0.0, LOT_Z)
collider_mm("lot", X0 - 2, 54, 4.0, 35.5, 0.0, LOT_Z)

# street name painted on the asphalt
def add_text(body, loc, size, rot_z, m, extrude=0.0, coll=None, rot_x=0.0, name=None):
    cu = bpy.data.curves.new(PREFIX + (name or body[:12]), 'FONT')
    cu.body = body
    cu.size = size
    cu.align_x = 'CENTER'
    cu.extrude = extrude
    ob = bpy.data.objects.new(name or ("Text_" + body[:10]), cu)
    (coll or C_VIS).objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (rot_x, 0, rot_z)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(ob)
    me.name = PREFIX + "TextMesh_" + body[:10]
    me.materials.clear()
    me.materials.append(m)
    mo = bpy.data.objects.new(ob.name + "_mesh", me)
    mo.matrix_world = ob.matrix_world
    (coll or C_VIS).objects.link(mo)
    bpy.data.objects.remove(ob, do_unlink=True)
    return mo


add_text("Rudarska ul.", (20.0, 1.9, 0.012), 1.3, math.pi / 2, M['paint'])
add_text("Rudarska ul.", (-20.0, -1.9, 0.012), 1.3, -math.pi / 2, M['paint'])

# --------------------------------------------------------------------------------------------
# facades helpers
# --------------------------------------------------------------------------------------------


def window_row_y(mb, x_from, x_to, spacing, face_y, z0, w, h, outward, frame=M['frame_white'],
                 shutter=0.4, skip=()):
    """windows on a facade plane at y=face_y facing +/-Y (outward = +1 or -1)."""
    n = int((x_to - x_from) // spacing)
    start = x_from + ((x_to - x_from) - (n - 1) * spacing) / 2
    for i in range(n):
        if i in skip:
            continue
        x = start + i * spacing
        y = face_y + outward * 0.03
        mb.box((x, y, z0 + h / 2), (w + 0.16, 0.06, h + 0.16), frame)
        mb.box((x, face_y + outward * 0.065, z0 + h / 2), (w, 0.02, h), M['glass'])
        if shutter > 0:
            sh = h * shutter * rng.uniform(0.6, 1.4) if shutter < 1 else h
            sh = min(sh, h)
            mb.box((x, face_y + outward * 0.08, z0 + h - sh / 2), (w, 0.03, sh), M['shutter'])
        mb.box((x, face_y + outward * 0.12, z0 - 0.06), (w + 0.3, 0.2, 0.08), M['concrete'])


def window_col_x(mb, y_from, y_to, spacing, face_x, z0, w, h, outward, frame=M['frame_white'], shutter=0.4):
    n = int((y_to - y_from) // spacing)
    start = y_from + ((y_to - y_from) - (n - 1) * spacing) / 2
    for i in range(n):
        y = start + i * spacing
        mb.box((face_x + outward * 0.03, y, z0 + h / 2), (0.06, w + 0.16, h + 0.16), frame)
        mb.box((face_x + outward * 0.065, y, z0 + h / 2), (0.02, w, h), M['glass'])
        if shutter > 0:
            sh = min(h, h * shutter * rng.uniform(0.6, 1.4))
            mb.box((face_x + outward * 0.08, y, z0 + h - sh / 2), (0.03, w, sh), M['shutter'])


def ac_unit(mb, x, y, z, outward):
    mb.box((x, y + outward * 0.2, z), (0.8, 0.32, 0.55), M['ac'])
    mb.cyl((x - 0.1, y + outward * 0.37, z), 0.18, 0.02, M['darkmetal'], seg=10, rx=math.pi / 2)


def downpipe(mb, x, y, z0, z1):
    mb.cyl((x, y, (z0 + z1) / 2), 0.06, z1 - z0, M['metal'], seg=6)


b = G_BUILD

# ---- B1: administrative building (4 storeys, beige + peach tower) ------------------------
FY = -13.5
b.box_mm(33, 54, FY - 14, FY, LOT_Z, 13.8, M['beige'])
b.box_mm(27, 33, FY - 14, FY + 0.3, LOT_Z, 14.4, M['peach'])
b.box_mm(32.7, 54, FY - 0.15, FY + 0.15, 13.8, 14.3, M['concrete'])  # parapet
for f in range(4):
    z = LOT_Z + 1.0 + f * 3.35
    window_row_y(b, 33.5, 54, 2.3, FY, z, 1.15, 1.65, 1, shutter=0.45 if f else 0.0,
                 skip=(3, 4) if f == 0 else ())
    # side windows facing the forecourt (NW face of the peach tower is blank, add glass block strip)
b.box_mm(29.2, 30.4, FY + 0.3, FY + 0.38, 1.6, 13.4, M['glassblock'])
for f in range(4):
    window_row_y(b, 31, 33, 1.5, FY + 0.3, LOT_Z + 1.0 + f * 3.35, 1.0, 1.4, 1, shutter=0.5)
# entrance
b.box_mm(40.6, 43.4, FY, FY + 0.12, LOT_Z, 2.9, M['door'])
b.box_mm(40.2, 43.8, FY, FY + 1.6, 3.0, 3.18, M['concrete'])
b.box_mm(39.8, 44.2, FY, FY + 1.2, LOT_Z, LOT_Z + 0.16, M['concrete'])
# flags
for i, (fx) in enumerate((38.6, 39.2)):
    b.cyl((fx, FY + 0.6, 6.0), 0.03, 2.4, M['metal'], seg=5, rx=-0.7)
    b.box((fx, FY + 1.35, 6.95), (0.02, 0.9, 0.6), M['flag_red'] if i == 0 else M['flag_blue'], rx=0.0)
for k in range(6):
    ac_unit(b, 35 + k * 3.1, FY, LOT_Z + 3.2 + (k % 3) * 3.35, 1)
downpipe(b, 33.15, FY + 0.1, LOT_Z, 13.8)
collider_mm("building", 27, 56, FY - 16, FY, 0, 14.4)
collider_mm("building", 27, 33, FY, FY + 0.3, 0, 14.4)
collider_mm("canopy", 40.2, 43.8, FY, FY + 1.6, 3.0, 3.18)

# forecourt low stone wall with hedge
b.box_mm(27.2, 36.0, -6.85, -6.35, LOT_Z, 0.95, M['limestone'])
G_FOLIAGE.box_mm(27.3, 35.9, -6.8, -6.4, 0.95, 1.35, M['leaves'])
collider_mm("lowwall", 27.2, 36.0, -6.85, -6.35, 0, 0.95)

# ---- B2: annex (3 storeys, beige) -----------------------------------------------------------
AY = -8.6
b.box_mm(12, 27, AY - 18, AY, LOT_Z, 10.6, M['beige'])
b.box_mm(12, 27, AY - 0.02, AY + 0.04, LOT_Z, 1.3, M['limestone'])
for f in range(3):
    window_row_y(b, 12.5, 26.5, 2.4, AY, LOT_Z + 1.2 + f * 3.25, 1.2, 1.5, 1, shutter=0.55)
b.box_mm(11.8, 27.2, AY - 0.1, AY + 0.3, 10.6, 10.9, M['roof_dark'])
for k in range(4):
    ac_unit(b, 13.5 + k * 3.7, AY, LOT_Z + 4.0 + (k % 2) * 3.25, 1)
collider_mm("building", 12, 27, AY - 20, AY, 0, 10.9)
# planter with bushes in front of annex
b.box_mm(13, 26, AY + 0.0, AY + 1.6, LOT_Z, 0.55, M['limestone'])
for k in range(6):
    G_FOLIAGE.blob((14 + k * 2.2, AY + 0.8, 0.9), 0.75, M['leaves'], scale=(1.3, 0.9, 0.8))
collider_mm("planter", 13, 26, AY, AY + 1.6, 0, 0.55)

# ---- B3: long gray building with limestone base ------------------------------------------
GY = -7.2
b.box_mm(-18, 12, GY - 18, GY, LOT_Z, 10.8, M['gray'])
b.box_mm(-18, 12, GY - 0.02, GY + 0.06, LOT_Z, 1.75, M['limestone'])
window_row_y(b, -17.5, 11.5, 2.6, GY, LOT_Z + 1.9, 1.25, 1.5, 1, shutter=1.0)
for f in (1, 2):
    window_row_y(b, -17.5, 11.5, 2.6, GY, LOT_Z + 1.7 + f * 3.0, 1.2, 1.55, 1,
                 shutter=0.0 if f == 2 else 0.35)
b.box_mm(-18.2, 12.2, GY - 0.3, GY + 0.35, 10.8, 11.1, M['roof_dark'])
for k in range(7):
    ac_unit(b, -15.0 + k * 4.1, GY, LOT_Z + 4.0 + (k % 3) * 2.2, 1)
for x in (-12.0, -0.5, 9.0):
    downpipe(b, x, GY + 0.1, LOT_Z, 10.8)
b.box_mm(-2.8, -1.4, GY, GY + 0.1, LOT_Z, 2.4, M['door'])
collider_mm("building", -18, 12, GY - 20, GY, 0, 11.1)

# ---- B4: limestone wall with barred windows + chimney --------------------------------------
WY = -7.2
b.box_mm(-36, -18, WY - 9, WY, LOT_Z, 4.7, M['limestone'])
b.tbox((-27, WY - 0.6, 5.0), (18.6, 1.6, 0.6), M['roof_tile'], top=(1, 0.3), shift=(0, -0.3))
for i in range(6):
    x = -34 + i * 2.6
    b.box((x, WY + 0.02, 2.4), (1.1, 0.04, 1.6), M['glass'])
    for k in range(5):
        b.box((x - 0.44 + k * 0.22, WY + 0.08, 2.4), (0.035, 0.04, 1.6), M['darkmetal'])
    for k in range(3):
        b.box((x, WY + 0.08, 1.7 + k * 0.7), (1.1, 0.04, 0.035), M['darkmetal'])
b.box_mm(-36, -18, WY - 9, WY - 8.5, LOT_Z, 6.5, M['teal'])
b.cyl((-29.5, WY - 6.5, 9.5), 0.75, 19, M['brick'], seg=10, r2=0.6, smooth=False)
collider_mm("building", -36, -18, WY - 12, WY, 0, 5.3)

# ---- B5: teal two-storey mine building -----------------------------------------------------
TY = -7.9
b.box_mm(-56, -36, TY - 14, TY, LOT_Z, 7.4, M['teal'])
b.box_mm(-56, -36, TY - 0.2, TY + 0.9, 7.4, 7.9, M['concrete'])   # flat roof overhang
b.box_mm(-56, -36, TY, TY + 0.25, 3.85, 4.1, M['teal'])           # band
for i in range(7):
    x = -54.5 + i * 2.7
    b.box((x, TY + 0.04, 5.6), (2.3, 0.08, 1.9), M['frame_red'])
    b.box((x, TY + 0.09, 5.6), (2.1, 0.04, 1.7), M['glass'])
    b.box((x, TY + 0.11, 5.85), (2.1, 0.03, 1.0), mat('curtain', (0.55, 0.50, 0.25), 0.9))
    if i != 3:
        b.box((x, TY + 0.04, 1.5), (2.3, 0.08, 1.3), M['frame_red'])
        b.box((x, TY + 0.09, 1.5), (2.1, 0.04, 1.1), M['glass'])
# entrance with steps
b.box_mm(-47.0, -45.0, TY, TY + 0.1, LOT_Z, 2.8, M['frame_red'])
b.box_mm(-46.8, -45.2, TY + 0.05, TY + 0.15, LOT_Z + 0.3, 2.6, M['glass'])
b.box_mm(-48.0, -44.0, TY, TY + 1.4, LOT_Z, LOT_Z + 0.3, M['concrete'])
b.box_mm(-48.2, -43.8, TY, TY + 1.5, 3.0, 3.15, M['teal'])
collider_mm("building", -56, -36, TY - 16, TY, 0, 7.9)
collider_mm("steps", -48.0, -44.0, TY, TY + 1.4, 0, LOT_Z + 0.3)
# bollard railings
for i in range(4):
    x = -43.0 + i * 1.5
    b.cyl((x - 0.35, TY + 2.4, 0.6), 0.03, 0.95, M['darkmetal'], seg=6)
    b.cyl((x + 0.35, TY + 2.4, 0.6), 0.03, 0.95, M['darkmetal'], seg=6)
    b.box((x, TY + 2.4, 1.07), (0.76, 0.06, 0.06), M['darkmetal'])

# ---- sports center "Franko Mileta" ------------------------------------------------------------
SX0, SX1, SY0, SY1 = -56.0, -34.0, 14.0, 44.0
b.box_mm(SX0, SX1, SY0, SY1, LOT_Z, 10.5, M['panel'])
b.box_mm(-49, -41, SY0 - 0.05, SY0 + 0.02, 5.2, 8.4, M['sportglass'])        # upper glass box
b.box_mm(-49.2, -40.8, SY0 - 1.6, SY0, 5.0, 5.2, M['concrete'])               # balcony
b.box_mm(-49.2, -40.8, SY0 - 1.6, SY0 - 1.5, 5.2, 6.2, M['sportglass'])
b.box_mm(-48.5, -41.5, SY0 - 0.04, SY0 + 0.02, LOT_Z, 3.6, M['sportglass'])  # entrance glass
b.box_mm(-40.5, -34.5, SY0 - 0.04, SY0 + 0.02, LOT_Z + 0.4, 2.4, M['sportglass'])
b.box_mm(-56, -50, SY0 - 0.04, SY0 + 0.02, 1.0, 9.6, M['sportglass'])        # stairwell glass
window_col_x(b, SY0 + 2, SY1 - 2, 4.0, SX1, 6.0, 2.6, 1.2, 1, frame=M['metal'], shutter=0.0)
# arched roof
b.cyl((-45, 30, 8.6), 5.2, 22.0, M['sportglass'], seg=14, rx=math.pi / 2)
b.box_mm(SX0 - 0.2, SX1 + 0.2, SY0 - 0.2, SY1, 10.5, 10.8, M['roof_dark'])
add_text("SPORTSKI CENTAR", (-37.6, SY0 - 0.03, 3.25), 0.45, 0, M['darkmetal'], extrude=0.02,
         rot_x=math.pi / 2, name="SignSC1")
add_text("FRANKO MILETA", (-37.6, SY0 - 0.03, 2.7), 0.45, 0, M['darkmetal'], extrude=0.02,
         rot_x=math.pi / 2, name="SignSC2")
# white jumping handball player silhouette
fig = [((-36.4, 7.6), (0.35, 0.35)), ((-36.6, 6.9), (0.32, 1.0)), ((-36.0, 7.35), (0.9, 0.14)),
       ((-37.1, 7.5), (0.7, 0.12)), ((-36.9, 6.1), (0.14, 0.9)), ((-36.3, 6.25), (0.8, 0.14))]
for (fx, fz), (sw, sh) in fig:
    b.box((fx, SY0 - 0.03, fz), (sw, 0.04, sh), M['sign_white'])
collider_mm("building", SX0, SX1, SY0, SY1 + 2, 0, 10.8)
collider_mm("balcony", -49.2, -40.8, SY0 - 1.6, SY0, 5.0, 6.2)
# plaza planter with hedge + cafe tables
b.box_mm(-45.5, -35.5, 7.3, 8.6, LOT_Z, 0.85, M['concrete'])
G_FOLIAGE.box_mm(-45.4, -35.6, 7.4, 8.5, 0.85, 1.25, M['leaves'])
collider_mm("planter", -45.5, -35.5, 7.3, 8.6, 0, 0.85)
for i, (tx, ty) in enumerate([(-47.5, 11.0), (-44.5, 11.6), (-41.5, 11.0), (-38.5, 11.6)]):
    b.cyl((tx, ty, 0.82), 0.45, 0.05, M['metal'], seg=10)
    b.cyl((tx, ty, 0.47), 0.04, 0.7, M['darkmetal'], seg=6)
    for a in range(3):
        cx, cy = tx + math.cos(a * 2.1) * 0.75, ty + math.sin(a * 2.1) * 0.75
        b.box((cx, cy, 0.5), (0.42, 0.42, 0.06), mat('chair', (0.35, 0.33, 0.30), 0.8))
        b.box((cx, cy, 0.27), (0.04, 0.04, 0.45), M['darkmetal'])
    collider("table", (tx, ty, 0.43), (0.9, 0.9, 0.86))

# ---- SE end: old stone retaining wall with graffiti ---------------------------------------
b.box_mm(54, 58, -30, 50, 0, 4.6, M['oldstone'])
b.box_mm(53.98, 54.0, -4, 4.1, 0.3, 4.2, M['graffiti'])
b.box_mm(53.98, 54.0, 6, 20, 0.4, 4.2, M['graffiti'])
b.box_mm(53.8, 58, -30, 50, 4.6, 4.85, M['concrete'])
collider_mm("wall", 54, 60, -30, 50, 0, 4.85)
# curved low stone wall with the bins (corner of lot and street)
for i in range(6):
    a = i / 5 * (math.pi / 2)
    cx, cy = 48.5 + math.cos(a) * 1.8, 6.2 + math.sin(a) * 1.8 - 1.8
    b.box((cx, cy, 0.62), (1.0, 0.6, 1.0), M['oldstone'], rz=a + math.pi / 2)
collider_mm("lowwall", 46.5, 50.6, 4.2, 6.6, 0, 1.12)

# ---- retaining wall at back of lot + terrace -------------------------------------------------
RY = 35.5
b.box_mm(-34, 54, RY, RY + 0.6, 0, TERRACE_Z, M['limestone'])
b.box_mm(-34, 54, RY, RY + 0.7, TERRACE_Z, TERRACE_Z + 0.12, M['concrete'])
G_GROUND.box_mm(-34, 54, RY + 0.6, 46, 0, TERRACE_Z, M['grass'])
collider_mm("terrace", -34, 56, RY, 47, 0, TERRACE_Z)
# metal railing on the terrace edge with gaps at the stairs
STAIRS_X = (6.0, -22.0)
x = -33.5
while x < 53.5:
    if all(abs(x - sx) > 2.2 for sx in STAIRS_X):
        b.cyl((x, RY + 0.35, TERRACE_Z + 0.55), 0.03, 0.9, M['darkmetal'], seg=5)
    x += 1.5
for sx_from, sx_to in [(-33.6, STAIRS_X[1] - 2.0), (STAIRS_X[1] + 2.0, STAIRS_X[0] - 2.0), (STAIRS_X[0] + 2.0, 53.6)]:
    b.box_mm(sx_from, sx_to, RY + 0.32, RY + 0.38, TERRACE_Z + 0.97, TERRACE_Z + 1.03, M['darkmetal'])
    collider_mm("railing", sx_from, sx_to, RY + 0.25, RY + 0.45, TERRACE_Z, TERRACE_Z + 1.05)

# stairs up to the terrace (visual steps + one ramp collider each)
for sx in STAIRS_X:
    run_from, run_to = 31.4, RY + 0.6
    nsteps = 13
    rise = (TERRACE_Z - LOT_Z) / nsteps
    run = (run_to - run_from) / nsteps
    for i in range(nsteps):
        y0 = run_from + i * run
        b.box_mm(sx - 1.5, sx + 1.5, y0, run_to, LOT_Z, LOT_Z + (i + 1) * rise, M['concrete'])
    for side in (-1, 1):
        b.box_mm(sx + side * 1.5 - 0.15, sx + side * 1.5 + 0.15, run_from, run_to, LOT_Z, LOT_Z + 0.3, M['limestone'])
        b.tbox((sx + side * 1.65, (run_from + run_to) / 2, (LOT_Z + TERRACE_Z) / 2 + 0.3),
               (0.3, run_to - run_from, TERRACE_Z - LOT_Z), M['limestone'], top=(1, 0.05), shift=(0, 0.475))
    length = math.hypot(run_to - run_from, TERRACE_Z - LOT_Z)
    ang = math.atan2(TERRACE_Z - LOT_Z, run_to - run_from)
    th = 0.4
    cz = (LOT_Z + TERRACE_Z) / 2 - math.cos(ang) * th / 2
    collider("ramp", (sx, (run_from + run_to) / 2 + math.sin(ang) * th / 2, cz), (3.0, length + 0.1, th), rx=ang)
    for side in (-1, 1):
        collider_mm("stairwall", sx + side * 1.65 - 0.2, sx + side * 1.65 + 0.2, run_from + 1.6, run_to, 0, TERRACE_Z + 0.4)

# --------------------------------------------------------------------------------------------
# vehicles
# --------------------------------------------------------------------------------------------
CAR_TYPES = {
    'hatch': dict(L=4.0, W=1.75, b0=0.28, b1=0.95, c1=1.48, cl=2.3, co=-0.25, top=(0.72, 0.84), sh=-0.08),
    'sedan': dict(L=4.55, W=1.8, b0=0.28, b1=0.92, c1=1.42, cl=2.45, co=-0.15, top=(0.66, 0.84), sh=-0.04),
    'suv': dict(L=4.5, W=1.86, b0=0.36, b1=1.08, c1=1.72, cl=2.75, co=-0.32, top=(0.84, 0.88), sh=-0.06),
    'wagon': dict(L=4.65, W=1.8, b0=0.3, b1=0.93, c1=1.47, cl=3.1, co=-0.45, top=(0.86, 0.86), sh=-0.06),
    'pickup': dict(L=5.25, W=1.9, b0=0.42, b1=1.12, c1=1.82, cl=1.75, co=0.65, top=(0.8, 0.88), sh=-0.04),
}


def car(x, y, yaw, kind=None, paint=None):
    kind = kind or rng.choice(['hatch', 'hatch', 'sedan', 'sedan', 'suv', 'suv', 'wagon', 'pickup'])
    p = CAR_TYPES[kind]
    paint = paint or rng.choice(CAR_PAINTS)
    mb = G_CARS
    z = LOT_Z if y > 4 or y < -4 else 0.0
    mb.xf = Matrix.Translation((x, y, z)) @ Matrix.Rotation(yaw, 4, 'Z')
    L, W = p['L'], p['W']
    mb.tbox((0, 0, (p['b0'] + p['b1']) / 2), (L, W, p['b1'] - p['b0']), paint, top=(0.97, 0.97))
    mb.box((L / 2 - 0.06, 0, p['b0'] + 0.12), (0.16, W + 0.02, 0.24), M['bumper'])
    mb.box((-L / 2 + 0.06, 0, p['b0'] + 0.12), (0.16, W + 0.02, 0.24), M['bumper'])
    ch = p['c1'] - p['b1']
    mb.tbox((p['co'], 0, p['b1'] + ch / 2), (p['cl'], W - 0.12, ch), M['glass'], top=p['top'],
            shift=(p['sh'], 0))
    rl, rw = p['cl'] * p['top'][0], (W - 0.12) * p['top'][1]
    mb.box((p['co'] + p['sh'] * p['cl'], 0, p['c1'] + 0.03), (rl + 0.04, rw + 0.04, 0.07), paint)
    mb.box((p['co'], 0, p['b1'] + 0.02), (p['cl'] * 0.5, W - 0.08, 0.06), paint)  # door belt / pillars hint
    if kind == 'pickup':
        bx0 = -L / 2 + 0.1
        bx1 = p['co'] - p['cl'] / 2 - 0.05
        for sy in (-1, 1):
            mb.box(((bx0 + bx1) / 2, sy * (W / 2 - 0.05), p['b1'] + 0.22), (bx1 - bx0, 0.08, 0.44), paint)
        mb.box((bx0 + 0.04, 0, p['b1'] + 0.22), (0.08, W, 0.44), paint)
    wx = L / 2 - 0.8
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.cyl((sx * wx, sy * (W / 2 - 0.1), 0.33), 0.33, 0.24, M['tire'], seg=10, rx=math.pi / 2)
    for sy in (-1, 1):
        mb.box((L / 2 - 0.01, sy * (W / 2 - 0.3), p['b1'] - 0.15), (0.04, 0.38, 0.14), M['headlight'])
        mb.box((-L / 2 + 0.01, sy * (W / 2 - 0.25), p['b1'] - 0.15), (0.04, 0.32, 0.16), M['taillight'])
    mb.xf = Matrix.Identity(4)
    # colliders: lower body + cabin
    collider("car", (x, y, z + p['b1'] / 2), (L, W, p['b1']), rz=yaw)
    cx, cy = rot2(p['co'] + p['sh'] * p['cl'] * 0.5, 0, yaw)
    collider("car", (x + cx, y + cy, z + p['b1'] + ch / 2), (p['cl'] * (1 + p['top'][0]) / 2, W - 0.2, ch), rz=yaw)


def box_truck(x, y, yaw):
    mb = G_CARS
    mb.xf = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(yaw, 4, 'Z')
    mb.box((-0.9, 0, 2.15), (5.2, 2.45, 2.7), M['truck_white'])          # cargo box
    mb.box((-0.9, -1.235, 2.25), (4.6, 0.02, 0.5), mat('gls_blue', (0.02, 0.06, 0.3), 0.5))
    mb.box((-0.9, 1.235, 2.25), (4.6, 0.02, 0.5), mat('gls_blue', (0.02, 0.06, 0.3), 0.5))
    mb.box((-0.9, -1.24, 1.55), (1.2, 0.02, 0.5), M['dump_yellow'])
    mb.box((2.55, 0, 1.25), (1.7, 2.3, 1.5), M['truck_white'])           # cab
    mb.tbox((2.45, 0, 2.3), (1.5, 2.2, 0.6), M['glass'], top=(0.75, 0.95), shift=(-0.12, 0))
    mb.box((1.0, 0, 0.62), (6.6, 1.1, 0.3), M['darkmetal'])               # chassis
    mb.box((3.42, 0, 0.6), (0.12, 2.35, 0.35), M['bumper'])
    for wx in (2.5, -2.1, -2.9):
        for sy in (-1, 1):
            mb.cyl((wx, sy * 1.05, 0.48), 0.48, 0.32, M['tire'], seg=12, rx=math.pi / 2)
    mb.xf = Matrix.Identity(4)
    cx, cy = rot2(-0.9, 0, yaw)
    collider("truck", (x + cx, y + cy, 1.9), (5.2, 2.45, 3.0), rz=yaw)
    cx, cy = rot2(2.55, 0, yaw)
    collider("truck", (x + cx, y + cy, 1.3), (1.75, 2.3, 2.6), rz=yaw)
    cx, cy = rot2(-0.9, 0, yaw)
    collider("truck", (x + cx, y + cy, 0.4), (6.0, 1.6, 0.8), rz=yaw)


def slot_fill(xs, y, yaws, prob, keep_clear=()):
    for xx in xs:
        if any(abs(xx - k) < 1.6 for k in keep_clear):
            continue
        if rng.random() < prob:
            car(xx + rng.uniform(-0.12, 0.12), y + rng.uniform(-0.15, 0.15), rng.choice(yaws) + rng.uniform(-0.04, 0.04))


PERP = (math.pi / 2, -math.pi / 2)
SLOT = 2.6
rowA = [-31.0 + i * SLOT for i in range(30)]
rowB = [-26.0 + i * SLOT for i in range(26)]
rowC = [-31.0 + i * SLOT for i in range(31)]
LAMP_B = (-16.0, 8.0, 32.0)
slot_fill(rowA, 8.25, PERP, 0.62, keep_clear=(-18.0, 2.0, 22.0, 40.0, 43.8))
slot_fill(rowB, 18.35, PERP, 0.55, keep_clear=LAMP_B + (-5.0, 19.0))
slot_fill(rowB, 23.75, PERP, 0.55, keep_clear=LAMP_B + (-5.0, 19.0))
slot_fill(rowC, 32.95, PERP, 0.6, keep_clear=STAIRS_X + (STAIRS_X[0] + 2.6, STAIRS_X[1] - 2.6, 48.0, 50.6))
# forecourt cars facing the admin building
for xx in (30.2, 32.8, 44.6, 47.2, 49.8):
    car(xx, -10.9, rng.choice(PERP))
# parallel-parked cars along the SW kerb
for xx in (-44.0, -39.2, -27.5, -22.7, -8.5, -3.7, 5.0, 17.0, 21.8, 47.0):
    car(xx, -2.85, math.pi if rng.random() < 0.5 else 0.0)
box_truck(31.0, 1.9, math.pi)

# lot parking lines
for xs, y in ((rowA, 8.25), (rowB, 18.35), (rowB, 23.75), (rowC, 32.95)):
    for xx in xs + [xs[-1] + SLOT]:
        G_GROUND.box((xx - SLOT / 2, y, LOT_Z + 0.004), (0.1, 4.6, 0.01), M['paint'])

# --------------------------------------------------------------------------------------------
# props: light poles, dumpsters, barriers, signs, cones
# --------------------------------------------------------------------------------------------
pr = G_PROPS


def light_pole(x, y, arms=2, h=8.5, z=LOT_Z):
    pr.cyl((x, y, z + 0.3), 0.18, 0.6, M['concrete'], seg=8)
    pr.cyl((x, y, z + h / 2), 0.09, h, M['metal'], seg=8, r2=0.06)
    dirs = [0, math.pi] if arms == 2 else [math.pi / 2]
    for a in dirs:
        dx, dy = math.cos(a), math.sin(a)
        pr.box((x + dx * 0.7, y + dy * 0.7, z + h - 0.15), (1.5 if dx else 0.06, 0.06 if dx else 1.5, 0.06), M['metal'],
               ry=-0.25 * dx, rx=0.25 * dy)
        pr.box((x + dx * 1.4, y + dy * 1.4, z + h + 0.05), (0.55 if dx else 0.25, 0.25 if dx else 0.55, 0.1), M['metal'])
        pr.box((x + dx * 1.4, y + dy * 1.4, z + h - 0.01), (0.45 if dx else 0.18, 0.18 if dx else 0.45, 0.03), M['lamp'])
    collider("pole", (x, y, z + h / 2), (0.26, 0.26, h))


for x in (-30.0, -6.0, 18.0, 42.0):
    light_pole(x, 4.85, arms=1)
for x in LAMP_B:
    light_pole(x, 21.0, arms=2)
light_pole(50.5, 8.2, arms=1)
light_pole(-6.0, -5.0, arms=1)


def dumpster(x, y, yaw, m):
    pr.xf = Matrix.Translation((x, y, LOT_Z)) @ Matrix.Rotation(yaw, 4, 'Z')
    pr.tbox((0, 0, 0.72), (1.9, 1.15, 1.1), m, top=(1.04, 1.08))
    pr.box((0, -0.05, 1.32), (2.0, 1.3, 0.1), m, rx=0.08)
    for sx in (-0.75, 0.75):
        for sy in (-0.42, 0.42):
            pr.cyl((sx, sy, 0.1), 0.09, 0.08, M['tire'], seg=6, rx=math.pi / 2)
    pr.xf = Matrix.Identity(4)
    collider("dumpster", (x, y, LOT_Z + 0.7), (2.0, 1.3, 1.4), rz=yaw)


dumpster(44.6, 7.0, 0.05, M['dump_yellow'])
dumpster(44.6, 9.0, -0.03, M['dump_blue'])
dumpster(-33.0, -5.5, 0.0, M['dump_yellow'])
dumpster(-14.0, -5.4, 0.0, M['dump_blue'])
dumpster(51.5, 33.2, 0.0, M['dump_blue'])


def jersey(x, y, yaw, z=0.0):
    pr.tbox((x, y, z + 0.43), (2.0, 0.62, 0.86), M['concrete'], top=(1.0, 0.38), rz=yaw)
    pr.box((x, y, z + 0.6), (2.01, 0.2, 0.1), mat('barrier_red', (0.55, 0.06, 0.04), 0.8), rz=yaw)
    collider("barrier", (x, y, z + 0.43), (2.0, 0.6, 0.86), rz=yaw)


# road closed at the NW end
for i, yy in enumerate((-3.0, -1.0, 1.0, 3.0)):
    jersey(-50.2, yy, math.pi / 2 + rng.uniform(-0.05, 0.05))
jersey(-50.2, 6.0, math.pi / 2, z=LOT_Z)
jersey(-50.2, 8.0, math.pi / 2, z=LOT_Z)
jersey(-50.2, 10.0, math.pi / 2, z=LOT_Z)
jersey(-50.2, 12.0, math.pi / 2, z=LOT_Z)
# roadworks cover in the street
jersey(-13.0, 1.4, 0.15)
jersey(-10.9, 1.1, -0.1)
jersey(12.0, -0.9, -0.12)
jersey(9.9, -1.1, 0.1)
jersey(-34.5, -0.9, 0.3)
for (cx, cy) in [(-15.0, 0.8), (-8.8, 0.5), (14.0, -0.3), (8.0, -0.4), (-36.4, 0.2), (-32.8, -0.2)]:
    pr.cyl((cx, cy, 0.36), 0.03, 0.7, M['cone'], seg=8, r2=0.17, smooth=False)
    pr.box((cx, cy, 0.02), (0.4, 0.4, 0.04), M['tire'])
# blue "P" parking signs
for (sx, sy) in [(43.0, 5.3), (-28.0, 5.3)]:
    pr.cyl((sx, sy, LOT_Z + 1.2), 0.035, 2.4, M['metal'], seg=6)
    pr.box((sx, sy, LOT_Z + 2.55), (0.04, 0.6, 0.6), M['sign_blue'])
    pr.box((sx + 0.025, sy, LOT_Z + 2.55), (0.01, 0.25, 0.38), M['sign_white'])
# benches on the terrace
for bx in (-10.0, 20.0, 38.0):
    pr.box((bx, RY + 3.0, TERRACE_Z + 0.45), (2.0, 0.45, 0.07), mat('bench_wood', (0.30, 0.17, 0.08), 0.8))
    pr.box((bx, RY + 3.2, TERRACE_Z + 0.75), (2.0, 0.06, 0.4), mat('bench_wood', (0.30, 0.17, 0.08), 0.8))
    for k in (-0.8, 0.8):
        pr.box((bx + k, RY + 3.05, TERRACE_Z + 0.22), (0.08, 0.5, 0.44), M['darkmetal'])
    collider("bench", (bx, RY + 3.1, TERRACE_Z + 0.4), (2.0, 0.6, 0.8))
# terrace low stone planters (cover up top)
for px in (-28.0, -14.0, 1.0, 14.0, 28.0, 44.0):
    pr.box((px, RY + 5.2, TERRACE_Z + 0.45), (3.0, 1.0, 0.9), M['limestone'])
    G_FOLIAGE.blob((px, RY + 5.2, TERRACE_Z + 1.1), 0.9, M['leaves'], scale=(1.6, 0.7, 0.6))
    collider("planter", (px, RY + 5.2, TERRACE_Z + 0.45), (3.0, 1.0, 0.9))

# --------------------------------------------------------------------------------------------
# foliage
# --------------------------------------------------------------------------------------------
fo = G_FOLIAGE


def tree(x, y, z=LOT_Z, h=None, collide=True):
    h = h or rng.uniform(3.0, 4.2)
    r = rng.uniform(0.18, 0.28)
    fo.cyl((x, y, z + h / 2), r, h, M['bark'], seg=6, r2=r * 0.7, smooth=False)
    crown = rng.uniform(2.0, 3.0)
    for k in range(3):
        fo.blob((x + rng.uniform(-1, 1), y + rng.uniform(-1, 1), z + h + crown * 0.5 + rng.uniform(-0.3, 0.8)),
                crown * rng.uniform(0.7, 1.0), M['leaves'], scale=(1, 1, 0.85), jitter=0.2)
    if collide:
        collider("trunk", (x, y, z + h / 2), (r * 2, r * 2, h))


def pine(x, y, z=LOT_Z, h=None, collide=True):
    h = h or rng.uniform(9, 14)
    fo.cyl((x, y, z + 1.5), 0.3, 3.0, M['bark'], seg=6, smooth=False)
    for k in range(4):
        t = k / 4
        fo.cyl((x, y, z + 2.0 + t * h * 0.75 + h * 0.12), (1 - t) * h * 0.24 + 0.6, h * 0.32, M['pine'],
               seg=7, r2=0.05, smooth=False)
    if collide:
        collider("trunk", (x, y, z + 1.5), (0.6, 0.6, 3.0))


# terrace trees
for tx in (-31.0, -18.0, -8.0, 3.0, 10.0, 17.0, 24.0, 33.0, 40.0, 49.0):
    if rng.random() < 0.6:
        tree(tx + rng.uniform(-1, 1), RY + rng.uniform(1.8, 2.4), z=TERRACE_Z)
    else:
        pine(tx + rng.uniform(-1, 1), RY + rng.uniform(1.8, 2.4), z=TERRACE_Z, h=rng.uniform(8, 12))
for tx in range(-30, 54, 7):
    pine(tx + rng.uniform(-2, 2), RY + rng.uniform(7.5, 9.5), z=TERRACE_Z, h=rng.uniform(10, 16), collide=False)
# SE corner trees in lot and near the bins
tree(52.6, 17.0)
tree(52.4, 22.0)
tree(52.6, 25.8)
# trees on the NW plaza and by the teal building
tree(-51.0, 12.5)
tree(-37.0, 12.2)
# hedges along the lot edge by the sports center
fo.box_mm(-34.0, -33.2, 14.5, 35.0, LOT_Z, 1.1, M['leaves'])
collider_mm("hedge", -34.0, -33.2, 14.5, 35.0, 0, 1.1)
# bushes against the SE wall
for k in range(7):
    fo.blob((52.6, 12 + k * 3.2, 0.9), 1.0, M['leaves'], scale=(0.9, 1.4, 0.9))

# --------------------------------------------------------------------------------------------
# backdrop (out of bounds)
# --------------------------------------------------------------------------------------------
bk = G_BACK
# hill rising behind the terrace
bm = bk.bm
res = bmesh.ops.create_grid(bm, x_segments=26, y_segments=10, size=1.0)
gx = [v.co.x for v in res['verts']]
gy = [v.co.y for v in res['verts']]
for v in res['verts']:
    u = (v.co.x - min(gx)) / (max(gx) - min(gx))
    w = (v.co.y - min(gy)) / (max(gy) - min(gy))
    v.co.x = -140 + u * 300
    v.co.y = 44 + w * 70
    v.co.z = TERRACE_Z - 0.4 + (w ** 1.3) * 28 + math.sin(u * 9.0) * 2.5 * w + rng.uniform(-0.8, 0.8) * w
bk._tag(res['verts'], M['grass'])
for v in res['verts']:
    for f in v.link_faces:
        f.smooth = False
# distant hills ring
for i in range(28):
    a = i / 28 * math.pi * 2
    rr = rng.uniform(230, 280)
    bk.cyl((math.cos(a) * rr, math.sin(a) * rr, 0), rng.uniform(55, 95), rng.uniform(40, 80), M['hill'], seg=7,
           r2=rng.uniform(5, 25), smooth=False)
# pines on hill
for k in range(60):
    hx = rng.uniform(-120, 150)
    hy = rng.uniform(50, 100)
    w = (hy - 44) / 70
    pine(hx, hy, z=TERRACE_Z - 0.4 + (w ** 1.3) * 28 - 0.5, h=rng.uniform(9, 16), collide=False)
# red building and houses beyond the NW barrier
bk.box_mm(-82, -60, 12, 28, 0, 11, M['redplaster'])
bk.tbox((-71, 20, 12.0), (23, 17, 2.0), M['roof_tile'], top=(1.0, 0.1))
for f in range(3):
    window_row_y(bk, -81, -61, 2.4, 12, 1.4 + f * 3.2, 1.0, 1.5, -1, shutter=0.0)
bk.box_mm(-95, -62, -24, -9, 0, 13, M['beige'])
bk.tbox((-78.5, -16.5, 14.0), (34, 16, 2.0), M['roof_tile'], top=(1.0, 0.1))
for f in range(4):
    window_row_y(bk, -94, -63, 2.4, -9, 1.4 + f * 3.0, 1.0, 1.5, 1, shutter=0.5)
for k in range(6):
    car(-62.0 - k * 6.5, 2.8 if k % 2 else -2.8, 0.0 if k % 2 else math.pi)
# houses with red roofs above the SE wall
for i in range(6):
    hx = rng.uniform(64, 95)
    hy = -30 + i * 13 + rng.uniform(-2, 2)
    hz = rng.uniform(4, 10)
    w, d, h = rng.uniform(9, 14), rng.uniform(8, 11), rng.uniform(6, 9)
    bk.box((hx, hy, hz + h / 2), (d, w, h), rng.choice([M['beige'], M['peach'], M['gray']]))
    bk.tbox((hx, hy, hz + h + 1.0), (d + 0.6, w + 0.6, 2.0), M['roof_tile'], top=(0.1, 1.0))
    tree(hx - 8, hy + 3, z=hz - 1, h=4, collide=False)
# buildings behind the SW blocks peeking over the roofs
bk.box_mm(-10, 30, -60, -42, 0, 16, M['beige'])
bk.tbox((10, -51, 17.0), (40, 18, 2.0), M['roof_tile'], top=(1.0, 0.1))
# mining headframe (Labin's coal mining heritage) in the distance
HX, HY = -120.0, -75.0
for sx in (-1, 1):
    for sy in (-1, 1):
        bk.box((HX + sx * 2.5, HY + sy * 2.5, 16), (0.5, 0.5, 32), M['darkmetal'], rx=-sy * 0.06, ry=sx * 0.06)
for k in range(8):
    zz = 3 + k * 3.8
    s = 5.0 - k * 0.11
    bk.box((HX, HY - s / 2, zz), (s, 0.25, 0.25), M['darkmetal'])
    bk.box((HX, HY + s / 2, zz), (s, 0.25, 0.25), M['darkmetal'])
    bk.box((HX - s / 2, HY, zz), (0.25, s, 0.25), M['darkmetal'])
    bk.box((HX + s / 2, HY, zz), (0.25, s, 0.25), M['darkmetal'])
bk.box((HX, HY, 33), (7, 4.5, 2.5), M['redplaster'])
for sy in (-1.2, 1.2):
    bk.cyl((HX, HY + sy, 35.5), 2.4, 0.3, M['metal'], seg=14, rx=math.pi / 2)
bk.box((HX + 9, HY, 9), (0.4, 0.4, 22), M['darkmetal'], ry=-0.45)
bk.box_mm(HX - 12, HX + 6, HY - 22, HY - 6, 0, 10, M['brick'])
bk.cyl((HX + 18, HY - 10, 20), 1.6, 40, M['brick'], seg=10, r2=1.1, smooth=False)

# --------------------------------------------------------------------------------------------
# boundaries (player clip, bullets pass) and markers
# --------------------------------------------------------------------------------------------
collider_mm("bound", -52.5, -50.6, -20, 50, -1, 30, clip=True)   # NW (behind the barriers)
collider_mm("bound", 54.0, 56, -20, 50, -1, 30, clip=True)       # SE wall top
collider_mm("bound", -60, 60, 43.5, 46, -1, 30, clip=True)       # NE terrace edge
collider_mm("bound", -60, 60, -30, -28, -1, 30, clip=True)       # SW (behind buildings, safety)
collider_mm("bound", -60, 60, -30, 50, 30, 31, clip=True)        # ceiling

spawns = {
    'allies': [(50.5, -1.2), (40.0, -9.8), (51.5, 13.4), (51.0, 28.4), (46.0, 13.4), (44.0, 28.3), (48.5, -6.0), (39.0, -1.5)],
    'axis': [(-47.0, -1.4), (-47.5, 9.0), (-40.0, 10.0), (-31.0, 13.4), (-31.0, 28.2), (-36.2, -5.6), (-27.0, 28.2), (-44.0, 2.2)],
}
for team, pts in spawns.items():
    for i, (sx, sy) in enumerate(pts):
        z = LOT_Z if (sy > 4.1 or sy < -4.1) else 0.0
        marker(f"SPAWN_{team}_{i + 1:02d}", (sx, sy, z + 0.05))
marker("BOUNDS_MIN", (-50.6, -14.0, -1.0))
marker("BOUNDS_MAX", (54.0, 43.5, 20.0))

# --------------------------------------------------------------------------------------------
# finalize + export
# --------------------------------------------------------------------------------------------
objs = [grp.build() for grp in (G_GROUND, G_BUILD, G_CARS, G_PROPS, G_FOLIAGE, G_BACK)]

# keep a dark world so viewport previews look sane
scene.world = bpy.data.worlds.get(PREFIX + "World") or bpy.data.worlds.new(PREFIX + "World")
scene.world.color = (0.55, 0.65, 0.8)

os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    use_active_scene=True,
    export_extras=True,
    export_apply=True,
    export_yup=True,
    export_cameras=False,
    export_lights=False,
    export_materials='EXPORT',
    export_image_format='JPEG',
    export_jpeg_quality=82,
    export_image_quality=82,
)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, copy=True)

tri = 0
for o in objs:
    tri += sum(len(p.vertices) - 2 for p in o.data.polygons)
result = {
    "glb": OUT_GLB,
    "size_kb": round(os.path.getsize(OUT_GLB) / 1024),
    "triangles": tri,
    "colliders": len([o for o in C_COL.objects]),
    "markers": len(C_META.objects),
    "materials": len(MATS),
}
