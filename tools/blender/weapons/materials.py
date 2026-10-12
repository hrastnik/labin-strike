"""Shared weapon materials and their tiling textures (generated with numpy, seamless by construction).

Every weapon uses the same small set of materials, so the game loads each texture once. Names are stable
(`wpn_<key>`): the client keys its wear/AO shader patch on them (see WEAR below).

UVs are in millimetres divided by TILE[key] (the helpers in lib.py do that), so a texture always covers the same
physical size whatever part it is on; wood grain runs along U (the length of the part).
"""
import os

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, 'tex')


def srgb(r, g, b):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (c(r), c(g), c(b))


# key: (base sRGB, roughness, metallic, texture kind, tile mm (u, v))
DEFS = {
    'blued':     ((44, 46, 52), 0.34, 0.9, 'blued', (160, 160)),       # deep blue-black polished steel
    'blued_old': ((58, 58, 60), 0.42, 0.85, 'blued', (160, 160)),      # worn / browned blueing (pistols, bolts)
    'phosphate': ((52, 53, 52), 0.55, 0.6, 'park', (120, 120)),        # late-war German phosphate + lacquer
    'paint':     ((36, 37, 38), 0.5, 0.35, 'paint', (160, 160)),       # black enamel (MP40, MG42)
    'park':      ((66, 68, 62), 0.62, 0.55, 'park', (120, 120)),       # US/UK parkerised steel
    'bright':    ((160, 160, 162), 0.3, 1.0, 'brushed', (100, 100)),   # machined bare steel (bolts, worn faces)
    'walnut':    ((88, 55, 34), 0.5, 0.0, 'wood', (320, 160)),        # US walnut (Garand, M1903, Thompson)
    'beech':     ((92, 57, 37), 0.5, 0.0, 'wood', (320, 160)),       # German / British beech, reddish
    'laminate':  ((106, 58, 36), 0.45, 0.0, 'laminate', (320, 160)),   # Kar98k late-war laminated stock
    'bakelite':  ((70, 38, 24), 0.32, 0.0, 'bakelite', (120, 120)),    # brown-red phenolic (P38 grips, MP40 parts)
    'black':     ((24, 23, 22), 0.42, 0.0, 'bakelite', (120, 120)),    # black hard rubber / plastic grips
    'checker_w': ((112, 66, 38), 0.55, 0.0, 'checker', (40, 40)),      # checkered walnut grip panels
    'checker_b': ((30, 28, 26), 0.5, 0.0, 'checker', (40, 40)),        # checkered black grip panels
    'brass':     ((186, 146, 70), 0.3, 1.0, 'brushed', (100, 100)),
    'leather':   ((96, 62, 38), 0.68, 0.0, 'leather', (120, 120)),
    'feldgrau':  ((88, 92, 78), 0.62, 0.15, 'paint', (160, 160)),      # field-grey painted steel (grenade head)
    'glass':     ((12, 18, 26), 0.04, 0.0, None, (100, 100)),          # scope lenses
}

# wear colour (sRGB), roughness and metalness the edges blend to; AO darkens everything (client: gunmodels.js)
WEAR = {
    'blued': ((150, 152, 158), 0.26, 1.0), 'blued_old': ((150, 150, 152), 0.28, 1.0),
    'phosphate': ((120, 120, 118), 0.32, 1.0), 'paint': ((120, 120, 122), 0.3, 1.0),
    'park': ((130, 130, 128), 0.32, 1.0), 'bright': ((190, 190, 192), 0.22, 1.0),
    'walnut': ((150, 102, 64), 0.55, 0.0), 'beech': ((170, 112, 72), 0.55, 0.0),
    'laminate': ((158, 100, 64), 0.5, 0.0), 'bakelite': ((100, 60, 38), 0.28, 0.0),
    'black': ((60, 56, 52), 0.35, 0.0), 'checker_w': ((140, 92, 56), 0.5, 0.0),
    'checker_b': ((58, 54, 50), 0.45, 0.0), 'brass': ((220, 186, 110), 0.22, 1.0),
    'leather': ((130, 90, 58), 0.6, 0.0), 'feldgrau': ((120, 120, 118), 0.3, 1.0),
    'glass': ((12, 18, 26), 0.04, 0.0),
}

TILE = {k: d[4] for k, d in DEFS.items()}


# ------------------------------------------------------------------ texture synthesis

def fnoise(rng, h, w, sy, sx):
    """periodic gaussian-filtered noise, correlation lengths sx/sy in pixels, unit std."""
    n = rng.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-2 * np.pi ** 2 * ((fx * sx) ** 2 + (fy * sy) ** 2))
    r = np.real(np.fft.ifft2(np.fft.fft2(n) * g))
    return (r - r.mean()) / (r.std() + 1e-9)


def _sm(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _normal_from_height(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * strength
    n = np.stack([-dx, -dy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def synth(kind, base, rough, metal, seed):
    """-> (albedo sRGB float HxWx3, roughness HxW, metal HxW, normal HxWx3 or None); rows top -> bottom = +v -> -v."""
    rng = np.random.default_rng(seed)
    b = np.array(base, np.float32) / 255.0
    if kind in ('wood', 'laminate'):
        H, W = 512, 1024                                              # 320 x 160 mm: ~0.31 mm per pixel
        y = np.arange(H, dtype=np.float32)[:, None] / H
        warp = fnoise(rng, H, W, 120, 700) * 0.035 + fnoise(rng, H, W, 25, 220) * 0.006
        if kind == 'wood':
            rings = (y * 38 + warp * 30) % 1.0                        # growth rings ~4 mm apart, gently wavy
            late = _sm(0.6, 0.85, rings) * (1 - _sm(0.9, 1.0, rings))
            late *= 0.6 + 0.4 * _sm(-1, 1, fnoise(rng, H, W, 6, 80))  # rings fade in and out
        else:
            rings = (y * 50 + warp * 6) % 1.0                         # laminate plies: regular, dense, contrasty
            late = _sm(0.45, 0.6, rings) * (1 - _sm(0.85, 0.95, rings))
        pores = np.clip(fnoise(rng, H, W, 0.7, 22), 0, None)          # long thin open pores
        figure = fnoise(rng, H, W, 30, 160)
        blotch = fnoise(rng, H, W, 80, 120)
        tone = 1.0 + 0.09 * figure + 0.10 * blotch - (0.13 if kind == 'wood' else 0.3) * late - 0.12 * _sm(0.8, 2.6, pores)
        alb = np.clip(b[None, None] * tone[..., None] * np.array([1.0, 0.97, 0.94]) ** (late[..., None] * 2), 0, 1)
        r = np.clip(rough + 0.06 * late + 0.10 * _sm(0.8, 2.6, pores) + 0.03 * figure, 0.05, 1)
        nrm = _normal_from_height(-0.5 * _sm(0.6, 2.6, pores) - 0.08 * late, 0.6)
        return alb, r, np.full((H, W), metal, np.float32), nrm
    H = W = 512
    if kind in ('blued', 'brushed'):
        streak = fnoise(rng, H, W, 0.7, 120)
        mott = fnoise(rng, H, W, 45, 45)
        fine = fnoise(rng, H, W, 1.5, 1.5)
        k = 0.015 if kind == 'blued' else 0.08
        alb = np.clip(b[None, None] * (1 + k * streak + 0.07 * mott + 0.02 * fine)[..., None], 0, 1)
        if kind == 'blued':   # faint blue/plum shift across the surface, like real salt blueing
            alb = alb * (1 + 0.06 * np.stack([-mott, -0.3 * mott, mott], -1))
        # blueing is polished before it is blued: only a faint trace of the streaks (strong ones read as a barcode
        # on broad flat sheet metal like magazines); bare brushed steel keeps them
        ks = 0.06 if kind == 'blued' else 0.4
        r = np.clip(rough + (0.01 if kind == 'blued' else 0.05) * streak + 0.05 * mott, 0.05, 1)
        nrm = _normal_from_height(ks * streak + 0.2 * fine, 0.12)
        return np.clip(alb, 0, 1), r, np.full((H, W), metal, np.float32), nrm
    if kind in ('park', 'paint', 'leather'):
        grain = fnoise(rng, H, W, 1.0, 1.0)
        mott = fnoise(rng, H, W, 60, 60)
        mid = fnoise(rng, H, W, 8, 8)
        amp = {'park': 0.05, 'paint': 0.03, 'leather': 0.06}[kind]
        alb = np.clip(b[None, None] * (1 + amp * grain + 0.06 * mott + 0.03 * mid)[..., None], 0, 1)
        r = np.clip(rough + 0.08 * grain + 0.05 * mott, 0.05, 1)
        nrm = _normal_from_height(grain * (0.5 if kind == 'leather' else 0.12) + mid * (0.8 if kind == 'leather' else 0.05), 0.35)
        return alb, r, np.full((H, W), metal, np.float32), nrm
    if kind == 'bakelite':
        mott = fnoise(rng, H, W, 25, 25)
        swirl = fnoise(rng, H, W, 6, 14)
        alb = np.clip(b[None, None] * (1 + 0.10 * mott + 0.05 * swirl)[..., None], 0, 1)
        r = np.clip(rough + 0.04 * mott, 0.05, 1)
        return alb, r, np.full((H, W), metal, np.float32), _normal_from_height(0.1 * swirl, 0.5)
    if kind == 'checker':
        # 40 mm tile, diamond checkering at ~1.6 mm pitch (25 lines per tile), pyramids as height
        y, x = np.mgrid[0:H, 0:W].astype(np.float32) / H
        n = 25
        a = np.abs(((x + y) * n) % 1.0 - 0.5)
        c = np.abs(((x - y) * n) % 1.0 - 0.5)
        h = 0.5 - np.maximum(a, c)                               # pyramid height 0..0.5
        mott = fnoise(rng, H, W, 30, 30)
        alb = np.clip(b[None, None] * (0.8 + 0.5 * h + 0.06 * mott)[..., None], 0, 1)
        r = np.clip(rough + 0.15 * (0.5 - h), 0.05, 1)
        return alb, r, np.full((H, W), metal, np.float32), _normal_from_height(h, 9.0)
    raise ValueError(kind)


def _save(name, arr, colorspace):
    """arr rows top->bottom (HxWxC float 0..1) -> image datablock saved as PNG in tex/."""
    os.makedirs(TEX, exist_ok=True)
    H, W = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, -1)
    rgba = np.concatenate([arr, np.ones((H, W, 1), np.float32)], -1)[::-1]   # Blender pixels: bottom row first
    img = bpy.data.images.get(name)
    if img is None or tuple(img.size) != (W, H):
        if img:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(name, W, H, alpha=False)
    img.colorspace_settings.name = colorspace
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    # write to a private temp file and rename, so parallel builds never see a half-written PNG
    final = os.path.join(TEX, name + '.png')
    tmp = os.path.join(TEX, f'.{name}.{os.getpid()}.png')
    img.filepath_raw = tmp
    img.file_format = 'PNG'
    img.save()
    os.replace(tmp, final)
    img.filepath_raw = final
    return img


def _textures(key):
    base, rough, metal, kind, _ = DEFS[key]
    if kind is None:
        return None
    seed = sum(map(ord, key)) * 7919
    alb, r, m, nrm = synth(kind, base, rough, metal, seed)
    mr = np.stack([np.ones_like(r), r, m], -1)            # glTF metallicRoughness: G = roughness, B = metal
    return (_save(f'wpn_{key}_col', alb, 'sRGB'), _save(f'wpn_{key}_mr', mr, 'Non-Color'),
            _save(f'wpn_{key}_nrm', nrm, 'Non-Color') if nrm is not None else None)


_cache = {}


def get(key, preview=False):
    """material `wpn_<key>`; preview=True adds the AO / wear vertex-colour mix (Blender renders only; not glTF-safe)."""
    name = f'wpn_{key}' + ('_pv' if preview else '')
    if name in _cache and _cache[name].name == name:
        return _cache[name]
    base, rough, metal, kind, _ = DEFS[key]
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    lin = srgb(*base)
    b.inputs['Base Color'].default_value = (*lin, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = (*lin, 1)
    m.use_backface_culling = True
    if key in WEAR:   # glTF extras -> material.userData.wear in three.js: linear rgb, roughness, metalness
        wc, wr, wm = WEAR[key]
        m['wear'] = [*srgb(*wc), wr, wm]
    if key == 'glass':
        b.inputs['Specular IOR Level'].default_value = 0.8
    texs = _textures(key)
    if texs:
        col, mr, nrm = texs
        tc = nt.nodes.new('ShaderNodeTexImage')
        tc.image = col
        tm = nt.nodes.new('ShaderNodeTexImage')
        tm.image = mr
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(tm.outputs['Color'], sep.inputs['Color'])
        rough_out, metal_out, col_out = sep.outputs['Green'], sep.outputs['Blue'], tc.outputs['Color']
        if preview:
            wc, wr, wm = WEAR[key]
            attr = nt.nodes.new('ShaderNodeVertexColor')
            attr.layer_name = 'Col'
            sa = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(attr.outputs['Color'], sa.inputs['Color'])
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            nt.links.new(sa.outputs['Green'], mix.inputs['Factor'])
            nt.links.new(col_out, mix.inputs['A'])
            mix.inputs['B'].default_value = (*srgb(*wc), 1)
            ao = nt.nodes.new('ShaderNodeMix')
            ao.data_type = 'RGBA'
            ao.blend_type = 'MULTIPLY'
            ao.inputs['Factor'].default_value = 1.0
            nt.links.new(mix.outputs['Result'], ao.inputs['A'])
            nt.links.new(sa.outputs['Red'], ao.inputs['B'])
            col_out = ao.outputs['Result']
            mr_mix = nt.nodes.new('ShaderNodeMix')
            nt.links.new(sa.outputs['Green'], mr_mix.inputs['Factor'])
            nt.links.new(rough_out, mr_mix.inputs['A'])
            mr_mix.inputs['B'].default_value = wr
            rough_out = mr_mix.outputs['Result']
            mm = nt.nodes.new('ShaderNodeMix')
            nt.links.new(sa.outputs['Green'], mm.inputs['Factor'])
            nt.links.new(metal_out, mm.inputs['A'])
            mm.inputs['B'].default_value = wm
            metal_out = mm.outputs['Result']
        nt.links.new(col_out, b.inputs['Base Color'])
        nt.links.new(rough_out, b.inputs['Roughness'])
        nt.links.new(metal_out, b.inputs['Metallic'])
        if nrm is not None:
            tn = nt.nodes.new('ShaderNodeTexImage')
            tn.image = nrm
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nm.inputs['Strength'].default_value = 1.0
            nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    _cache[name] = m
    return m
