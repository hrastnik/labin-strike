"""Shared car materials. Names are stable: the game client keys on them (paint is tinted per car)."""
import bpy


def _principled(name, color, rough, metal=0.0, **extra):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    for k, v in extra.items():
        if k in b.inputs:
            b.inputs[k].default_value = v if not isinstance(v, tuple) else (*v, 1.0) if len(v) == 3 else v
    m.diffuse_color = (*color, 1.0)
    return m


def srgb(r, g, b):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (c(r), c(g), c(b))


def define():
    M = {}
    # body paint: white base, tinted per instance in the game; clearcoat gives the lacquer reflections
    M['paint'] = _principled('car_paint', srgb(235, 235, 235), 0.32, 0.35, **{'Coat Weight': 1.0, 'Coat Roughness': 0.04})
    M['glass'] = _principled('car_glass', srgb(14, 17, 20), 0.03, 0.0, **{'Alpha': 0.62})
    M['glass'].surface_render_method = 'BLENDED' if hasattr(M['glass'], 'surface_render_method') else None
    M['trim'] = _principled('car_trim', srgb(16, 16, 17), 0.55)            # unpainted black plastic
    M['gloss'] = _principled('car_gloss_black', srgb(8, 8, 9), 0.12)        # piano black pillars / grille surround
    M['chrome'] = _principled('car_chrome', srgb(220, 222, 226), 0.08, 1.0)
    M['rubber'] = _principled('car_rubber', srgb(22, 22, 23), 0.86)
    M['alloy'] = _principled('car_alloy', srgb(176, 178, 182), 0.28, 1.0)
    M['alloy_dark'] = _principled('car_alloy_dark', srgb(70, 72, 76), 0.35, 1.0)
    M['brake'] = _principled('car_brake', srgb(90, 86, 82), 0.5, 0.8)
    M['lens'] = _principled('car_lens', srgb(230, 235, 240), 0.02, 0.0, **{'Alpha': 0.12})
    M['lamp_inner'] = _principled('car_lamp_inner', srgb(52, 54, 58), 0.22, 1.0)
    M['tail_lens'] = _principled('car_tail_lens', srgb(170, 12, 16), 0.03, 0.0, **{'Alpha': 0.55})
    for k in ('lens', 'tail_lens'):
        M[k].surface_render_method = 'BLENDED'
    M['reflector'] = _principled('car_reflector', srgb(205, 208, 212), 0.12, 1.0)
    M['drl'] = _principled('car_drl', srgb(240, 244, 250), 0.2, 0.0, **{'Emission Color': (0.9, 0.95, 1.0), 'Emission Strength': 0.6})
    M['tail'] = _principled('car_taillight', srgb(150, 10, 12), 0.15, 0.0)
    M['tail_dark'] = _principled('car_taillight_dark', srgb(70, 6, 8), 0.12, 0.0)
    M['amber'] = _principled('car_amber', srgb(230, 120, 20), 0.2)
    M['interior'] = _principled('car_interior', srgb(34, 34, 36), 0.85)
    M['interior2'] = _principled('car_interior_light', srgb(60, 58, 56), 0.8)
    M['liner'] = _principled('car_liner', srgb(10, 10, 10), 0.9)
    M['plate'] = _principled('car_plate', srgb(240, 240, 240), 0.4)
    M['badge'] = _principled('car_badge', srgb(200, 202, 206), 0.15, 1.0)
    return M
