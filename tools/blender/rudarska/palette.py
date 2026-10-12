"""Material palette.  Colours are given in sRGB 0-255 and converted to linear factors."""
from .lib import decal, mat, pbr


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(r, g, b):
    return (lin(r), lin(g), lin(b))


def tint(r, g, b, base=0.70):
    """factor that turns the neutral gray albedo (~0.7 linear) into the given sRGB colour."""
    return tuple(min(1.0, v / base) for v in rgb(r, g, b))


M = {}


def define():
    # ground
    M['asphalt'] = pbr('asphalt', 'asphalt', 7.0, rough_map=True, nstrength=0.8)
    M['lot'] = pbr('lot_asphalt', 'lot', 6.0, rough_map=True, nstrength=0.8)
    M['pavers'] = pbr('pavers', 'pavers', 2.4)
    M['slabs'] = pbr('slabs', 'slabs', 2.0)
    M['plaza'] = pbr('plaza_slabs', 'plaza', 2.6)
    M['concrete'] = pbr('concrete', 'concrete', 3.0, tint=tint(164, 162, 156), gray=True, rough=0.92)
    M['concrete_dark'] = pbr('concrete_dark', 'concrete', 3.0, tint=tint(120, 120, 116), gray=True, rough=0.95)
    M['kerb'] = pbr('kerb_granite', 'concrete', 1.5, tint=tint(150, 150, 146), gray=True, rough=0.8)
    # Rudarska's sidewalks are worn light-grey asphalt (patched), not paving
    M['walk'] = pbr('walk_asphalt', 'lot', 4.5, tint=tint(128, 128, 125), gray=True, rough=0.9, nstrength=0.8)
    M['concrete_gray'] = pbr('concrete_gray', 'concrete', 3.0, tint=tint(146, 146, 142), gray=True, rough=0.92)
    M['grass'] = pbr('grass', 'grass', 3.0, rough=1.0)
    M['soil'] = pbr('soil', 'soil', 3.0, rough=1.0)
    M['rock'] = pbr('rock_limestone', 'rock', 4.0, tint=tint(150, 147, 138), gray=True, rough=0.9, nstrength=1.4)

    # stone walls
    M['ashlar'] = pbr('ashlar_limestone', 'ashlar', (3.2, 3.2), tint=(1.08, 1.06, 1.0), rough=0.88, nstrength=1.2)
    M['stonebase'] = pbr('stone_base', 'stonebase', 2.4, tint=(1.05, 1.04, 1.0), rough=0.88)
    M['oldstone'] = pbr('old_stone_wall', 'oldstone', 3.5, tint=tint(150, 148, 140), gray=True, rough=0.92, nstrength=1.3)

    # stucco (neutral texture tinted per building)
    def stucco(name, c, old=False):
        M[name] = pbr(name, 'plaster_old' if old else 'plaster', 4.0, tint=tint(*c), gray=True, rough=0.93)
    stucco('st_admin', (212, 194, 150))
    stucco('st_admin_old', (204, 186, 146), old=True)
    stucco('st_peach', (224, 166, 124))
    stucco('st_annex', (196, 188, 170), old=True)
    stucco('st_teal', (150, 180, 168))
    stucco('st_teal_dark', (118, 152, 142))
    stucco('st_red', (172, 78, 58), old=True)
    stucco('st_green', (192, 208, 170), old=True)
    stucco('st_white', (232, 230, 222))
    stucco('st_yellow', (224, 194, 116), old=True)
    stucco('st_cream', (226, 214, 180))
    stucco('st_gray', (170, 168, 160), old=True)
    M['cladding'] = pbr('cladding_gray', 'cladding', (3.0, 3.0), tint=tint(150, 153, 156), gray=True, rough=0.6)
    M['cladding_light'] = pbr('cladding_light', 'cladding', (3.0, 3.0), tint=tint(196, 198, 200), gray=True, rough=0.6)

    # roofs
    M['rooftiles'] = pbr('roof_tiles', 'rooftiles', (2.2, 2.2), tint=(0.95, 0.85, 0.8), rough=0.85)
    M['flatroof'] = pbr('flat_roof', 'flatroof', 3.0, tint=(0.75, 0.75, 0.75), rough=0.95)
    M['flatroof_light'] = pbr('flat_roof_light', 'concrete', 4.0, tint=(0.92, 0.9, 0.85), rough=0.95)
    M['roof_metal'] = mat('roof_metal', rgb(130, 134, 138), 0.45, 0.6)
    M['parapet'] = mat('parapet_tin', rgb(120, 122, 124), 0.5, 0.5)

    # windows & doors
    M['glass'] = mat('window_glass', rgb(30, 38, 46), 0.08, 0.6)
    M['glass_dark'] = mat('glass_dark', rgb(14, 18, 22), 0.06, 0.7)
    M['glass_blue'] = mat('glass_sports', rgb(36, 48, 60), 0.05, 0.75)
    M['frame_white'] = mat('frame_white', rgb(222, 222, 216), 0.5)
    M['frame_brown'] = mat('frame_brown', rgb(92, 56, 32), 0.55)
    M['frame_red'] = mat('frame_red', rgb(122, 40, 32), 0.5)
    M['frame_dark'] = mat('frame_dark', rgb(40, 42, 44), 0.45, 0.5)
    M['frame_alu'] = mat('frame_alu', rgb(170, 172, 174), 0.35, 0.8)
    M['shutter'] = pbr('shutter_brown', 'shutter', (1.2, 0.6), tint=tint(122, 74, 42), gray=True, rough=0.6)
    M['shutter_gray'] = pbr('shutter_gray', 'shutter', (1.2, 0.6), tint=tint(150, 150, 146), gray=True, rough=0.55)
    M['door_wood'] = mat('door_wood', rgb(96, 58, 30), 0.55)
    M['sill'] = mat('stone_sill', rgb(206, 202, 190), 0.75)
    M['curtain'] = mat('curtain_yellow', diff='gen/curtain.jpg', rough=0.9, tile=(1.2, 1.2), tint=(0.72, 0.72, 0.68))
    M['glassblock'] = mat('glass_blocks', diff='gen/glassblock.jpg', rough=0.25, tile=(1.6, 1.6))
    M['grille'] = mat('grille_iron', rgb(30, 30, 32), 0.5, 0.6)
    M['grille_red'] = mat('grille_red', rgb(116, 38, 32), 0.5, 0.3)
    M['canopy'] = mat('canopy_redbrown', rgb(120, 50, 34), 0.6)
    M['interior'] = mat('interior_dark', rgb(36, 32, 28), 0.9)

    # metals / props
    M['metal'] = mat('metal_galv', rgb(150, 152, 150), 0.4, 0.85)
    M['metal_dark'] = mat('metal_dark', rgb(48, 50, 52), 0.45, 0.6)
    M['metal_green'] = mat('metal_green', rgb(52, 104, 70), 0.5, 0.5)
    M['rust'] = mat('metal_rust', rgb(110, 60, 34), 0.75, 0.3)
    M['pipe_gray'] = mat('pipe_gray', rgb(150, 150, 146), 0.5, 0.4)
    M['pipe_red'] = mat('pipe_red', rgb(130, 40, 30), 0.6, 0.3)
    M['ac'] = mat('ac_unit', rgb(228, 228, 224), 0.45)
    M['ac_grille'] = mat('ac_grille', rgb(60, 62, 64), 0.5, 0.4)
    M['cabinet'] = mat('cabinet_gray', rgb(160, 162, 158), 0.5, 0.3)
    M['lamp_glass'] = mat('lamp_glass', rgb(230, 228, 214), 0.2, emit=rgb(255, 236, 200))
    M['bin_yellow'] = mat('bin_yellow', rgb(232, 190, 20), 0.5)
    M['bin_blue'] = mat('bin_blue', rgb(20, 70, 170), 0.5)
    M['bin_green'] = mat('bin_green', rgb(40, 110, 50), 0.5)
    M['bin_orange'] = mat('bin_orange', rgb(230, 110, 20), 0.5)
    M['bin_gray'] = mat('bin_gray', rgb(80, 82, 84), 0.6)
    M['plastic_black'] = mat('plastic_black', rgb(20, 20, 22), 0.6)
    M['rubber'] = mat('tire_rubber', rgb(16, 16, 17), 0.88)
    M['wood'] = mat('wood_bench', rgb(120, 82, 50), 0.7)
    M['wicker'] = mat('wicker', rgb(150, 112, 70), 0.85)
    M['parasol'] = mat('parasol_cream', rgb(228, 220, 200), 0.8, cull=False)
    M['white_paint'] = mat('paint_white', rgb(236, 236, 230), 0.6)
    M['yellow_paint'] = mat('paint_yellow', rgb(236, 190, 30), 0.6)
    M['solar'] = mat('solar_panel', rgb(24, 34, 60), 0.15, 0.6)

    # vegetation
    M['bark'] = pbr('bark', 'bark', (1.4, 2.0), rough=0.95)
    M['bark_pine'] = pbr('bark_pine', 'bark_pine', (1.0, 1.6), rough=0.95)
    M['leaf_broad'] = decal('leaf_broad_cut', 'leaf_broad.png', rough=0.8)
    M['leaf_plane'] = decal('leaf_plane_cut', 'leaf_plane.png', rough=0.8)
    M['leaf_yellow'] = decal('leaf_yellow_cut', 'leaf_yellow.png', rough=0.8)
    M['leaf_cedar'] = decal('leaf_cedar_cut', 'leaf_cedar.png', rough=0.85)
    M['leaf_spruce'] = decal('leaf_spruce_cut', 'leaf_spruce.png', rough=0.85)
    M['grass_card'] = decal('grass_card_cut', 'grass_card.png', rough=0.9)
    M['hedge'] = mat('hedge_leaves', diff='gen/hedge.jpg', rough=0.9, tile=(1.2, 1.2))
    M['leaf_hedge'] = decal('leaf_hedge_cut', 'leaf_hedge.png', rough=0.85)
    M['spruce_core'] = mat('spruce_core_leaves', diff='gen/hedge.jpg', rough=0.95, tile=(1.6, 1.6), tint=(0.3, 0.36, 0.34))

    # decals / signs
    for k, f in [('sports_text', 'sports_text.png'), ('handball', 'handball.png'), ('ck', 'ck_logo.png'),
                 ('graffiti', 'graffiti.png'), ('blob', 'blob.png'), ('grime', 'grime.png'),
                 ('manhole', 'manhole.png'), ('sign_fina', 'sign_fina.png'), ('sign_library', 'sign_library.png'),
                 ('treeline', 'treeline.png')]:
        M[k] = decal(f'{k}_dec' if k in ('graffiti', 'blob', 'grime') else f'{k}_cut', f, rough=0.8)
    for k, f in [('sign_p', 'sign_p.png'), ('sign_cross', 'sign_cross.png'), ('sign_ideal', 'sign_ideal.png'),
                 ('sign_rudarski', 'sign_rudarski.png'), ('sign_trio', 'sign_trio.png'), ('sign_5570', 'sign_5570.png'),
                 ('flag_hr', 'flag_hr.png'), ('flag_eu', 'flag_eu.png'), ('plate', 'plate.png'), ('plaque', 'plaque.png'),
                 ('grate', 'grate.png')]:
        M[k] = decal(k, f, rough=0.5, alpha=False)
    M['flag_hr'].use_backface_culling = False
    M['flag_eu'].use_backface_culling = False
    M['sign_back'] = mat('sign_back', rgb(150, 152, 154), 0.4, 0.7)

    # road paint
    M['paint'] = mat('road_paint_white', rgb(226, 226, 218), 0.65)
    M['paint_y'] = mat('road_paint_yellow', rgb(226, 178, 30), 0.65)

    # vehicles
    M['car_glass'] = mat('car_glass', rgb(20, 24, 28), 0.05, 0.7)
    M['car_trim'] = mat('car_trim_black', rgb(18, 18, 19), 0.55)
    M['chrome'] = mat('car_chrome', rgb(200, 200, 200), 0.18, 1.0)
    M['rim'] = mat('car_rim', rgb(150, 152, 156), 0.3, 0.9)
    M['headlight'] = mat('car_headlight', rgb(220, 222, 220), 0.1, 0.4)
    M['taillight'] = mat('car_taillight', rgb(150, 16, 14), 0.25)
    M['indicator'] = mat('car_indicator', rgb(220, 120, 20), 0.3)
    M['truck_box'] = mat('truck_box_white', rgb(236, 236, 232), 0.5)
    M['truck_stripe'] = mat('truck_stripe', rgb(200, 40, 40), 0.5)
    M['car_paints'] = [mat('car_' + n, rgb(*c), 0.28, 0.45) for n, c in [
        ('white', (232, 232, 230)), ('white2', (240, 238, 232)), ('silver', (168, 170, 172)), ('silver2', (130, 132, 136)),
        ('gray', (92, 94, 98)), ('black', (14, 14, 16)), ('black2', (24, 25, 28)), ('red', (150, 18, 16)),
        ('darkred', (96, 14, 18)), ('blue', (24, 52, 120)), ('navy', (18, 26, 52)), ('lime', (180, 196, 70)),
        ('beige', (176, 160, 130)), ('brown', (78, 52, 36)), ('green', (34, 70, 48)), ('orange', (210, 96, 26))]]
    return M
