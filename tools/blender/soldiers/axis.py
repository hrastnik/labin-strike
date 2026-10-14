"""Wehrmacht rifleman: M40 Stahlhelm, M36 field tunic (dark green collar with grey Litzen, piped shoulder straps,
breast eagle, four pleated pockets, five buttons), black belt with a silver buckle, brown leather Y-straps and
three-cell cartridge pouches, gas-mask canister and bread bag, trousers bloused over black ankle boots."""
import math

from . import body
from .lib import V

C = {
    'tunic': '#4f5952',
    'tunic_dark': '#434c46',
    'collar': '#2c3832',
    'litzen': '#a9ad9f',
    'trousers': '#4b544f',
    'leather': '#7a4b2b',
    'leather_dark': '#5e3a22',
    'belt': '#2a2420',
    'buckle': '#b9bab2',
    'button': '#8f9289',
    'eagle': '#d6d6cc',
    'helmet': '#434947',
    'boot': '#1f1e1c',
    'sole': '#151413',
    'canister': '#4c5650',
    'breadbag': '#6c6a52',
    'cuff': '#4a544d',
}

# first-person sleeves
FP = {'jacket': C['tunic'], 'cuff': C['cuff'], 'button': C['button'], 'cuff_dark': C['tunic_dark']}

HARD = {body.SKIN, body.SKIN_SHADE, body.LIPS, C['helmet'], C['boot'], C['sole'], C['buckle'], C['canister'],
        C['button'], body.STICK_HEAD, body.STICK_RING, body.STICK_WOOD}

STYLE = {
    'jacket': C['tunic'],
    'trousers': C['trousers'],
    'cuff': C['cuff'],
    'face': {'hair': '#7a6040', 'brow': '#6a5034', 'iris': '#5b6d78'},
    'torso': [(0.78, 0.168, 0.12, 0.006), (0.84, 0.172, 0.12, 0.004), (0.95, 0.164, 0.114, 0),
              (1.04, 0.154, 0.106, 0), (1.13, 0.16, 0.11, -0.004), (1.23, 0.17, 0.118, -0.01),
              (1.32, 0.178, 0.12, -0.01), (1.40, 0.176, 0.112, -0.004), (1.46, 0.15, 0.096, 0.0),
              (1.5, 0.1, 0.076, 0.004), (1.53, 0.066, 0.062, 0.004)],
    # trousers narrow down the shin and puff out where they are bloused over the boots
    'shin': lambda x: [((x, 0.49, -0.01), 0.058, 0.064), ((x, 0.4, 0.0), 0.058, 0.066), ((x, 0.3, 0.004), 0.056, 0.062),
                       ((x, 0.2, 0.004), 0.066, 0.07), ((x, 0.15, 0.002), 0.062, 0.066), ((x, 0.12, 0.0), 0.05, 0.054)],
}


def boot(k, x, n):
    b = f'foot_{n}'
    k.loft([((x, 0.15, 0.004), 0.048, 0.052), ((x, 0.1, 0.004), 0.05, 0.058)], C['boot'], f'shin_{n}', n=20,
           name='ankle')
    k.rbox((x, 0.055, -0.035), (0.1, 0.095, 0.27), C['boot'], b, p=3.2, name='foot')
    k.rbox((x, 0.07, -0.13), (0.094, 0.065, 0.1), C['boot'], b, p=2.6, name='toe')
    k.rbox((x, 0.012, -0.04), (0.106, 0.024, 0.28), C['sole'], b, p=4.5, name='sole')
    k.rbox((x, 0.02, 0.06), (0.088, 0.04, 0.07), C['sole'], b, p=4.5, name='heel')


STYLE['boot'] = boot


def build(k):
    st = STYLE
    torso = body.build_torso(k, st)
    body.build_pelvis(k, st)
    legs = body.build_legs(k, st)
    body.build_neck_head(k, st)
    arms = body.build_arms(k, st)
    body.stahlhelm(k, C['helmet'])
    ts = k.surface([torso])
    hb = lambda p: 'hips' if p.y < 0.99 else 'torso'  # noqa: E731

    # --- standing collar with Litzen, shoulder straps with piping
    k.loft([((0, 1.505, 0.004), 0.072, 0.07), ((0, 1.56, 0.002), 0.066, 0.064)], C['collar'], 'torso', n=24,
           name='collar', p=2.2)
    for s in (-1, 1):
        for dy in (0.0, 0.016):
            k.tile([(s * 0.03, 1.53 + dy, -0.068), (s * 0.058, 1.53 + dy, -0.048), (s * 0.058, 1.537 + dy, -0.048),
                    (s * 0.03, 1.537 + dy, -0.068)], (s * 0.5, 0, -1), 0.012, C['litzen'], 'torso',
                   name='litzen')['role'] = 'decal'
        k.strap(ts, [(s * 0.075, 1.515, -0.005), (s * 0.13, 1.48, -0.002), (s * 0.175, 1.45, 0.0)], 0.05, 0.007,
                C['tunic_dark'], 'torso', step=0.01, name='shoulderstrap')
        k.stud(ts, (s * 0.08, 1.514, -0.005), 0.008, 0.008, C['button'], 'torso', name='strap_button')

    # --- front: placket, five buttons, pleated pockets with scalloped flaps, breast eagle
    k.strap(ts, [(0.0, 1.5, -0.075), (0.0, 0.8, -0.128)], 0.032, 0.005, C['tunic'], hb, name='placket')
    for y in (1.42, 1.3, 1.18, 1.06, 0.94):
        k.stud(ts, (0.0, y, -0.13), 0.009, 0.008, C['button'], hb, name='button')
    for s in (-1, 1):
        x0, x1 = s * 0.04, s * 0.14
        k.patch(ts, [(x0, 1.37, -0.13), (x1, 1.37, -0.116), (x1, 1.22, -0.12), (x0, 1.22, -0.13)], 0.01, C['tunic'],
                'torso', bulge=0.01, name='pocket')
        k.strap(ts, [((x0 + x1) / 2, 1.37, -0.13), ((x0 + x1) / 2, 1.23, -0.13)], 0.022, 0.012, C['tunic'], 'torso',
                name='pleat', step=0.01)
        k.patch(ts, [(x0 - s * 0.004, 1.385, -0.13), (x1 + s * 0.004, 1.385, -0.116), (x1 + s * 0.004, 1.34, -0.118),
                     (x0 - s * 0.004, 1.34, -0.13)], 0.02, C['tunic_dark'],
                'torso', nu=6, nv=3, name='flap')
        k.stud(ts, ((x0 + x1) / 2, 1.345, -0.15), 0.008, 0.008, C['button'], 'torso', name='flap_button')
        x0, x1 = s * 0.05, s * 0.17
        k.patch(ts, [(x0, 0.99, -0.125), (x1, 0.99, -0.1), (x1, 0.82, -0.105), (x0, 0.82, -0.125)], 0.012, C['tunic'],
                'hips', bulge=0.014, name='skirt_pocket')
        k.patch(ts, [(x0 - s * 0.004, 0.995, -0.127), (x1 + s * 0.004, 0.995, -0.102), (x1 + s * 0.004, 0.945, -0.106),
                     (x0 - s * 0.004, 0.945, -0.127)], 0.022, C['tunic_dark'], 'hips', nu=6, nv=3, name='skirt_flap')
        k.stud(ts, ((x0 + x1) / 2, 0.96, -0.15), 0.008, 0.008, C['button'], 'hips', name='flap_button')
    # breast eagle over the right pocket: spread wings and a small body
    for s in (-1, 1):
        k.patch(ts, [(0.09 + s * 0.006, 1.425, -0.13), (0.09 + s * 0.055, 1.44, -0.125), (0.09 + s * 0.05, 1.428, -0.126),
                     (0.09 + s * 0.006, 1.413, -0.13)], 0.003, C['eagle'], 'torso', nu=4, nv=2, name='eagle',
                role='decal')
    k.patch(ts, [(0.083, 1.44, -0.13), (0.097, 1.44, -0.13), (0.095, 1.405, -0.13), (0.085, 1.405, -0.13)], 0.0035,
            C['eagle'], 'torso', nu=2, nv=3, name='eagle_body', role='decal')

    # --- belt with buckle, Y-straps, cartridge pouches
    belt = [(0.165 * math.cos(a), 1.02, -0.112 * math.sin(a)) for a in [i * math.tau / 16 for i in range(16)]]
    k.strap(ts, belt, 0.05, 0.01, C['belt'], hb, closed=True, name='belt')
    k.rbox((0.0, 1.02, -0.128), (0.065, 0.048, 0.016), C['buckle'], 'torso', name='buckle', p=4)
    for s in (-1, 1):
        k.strap(ts, [(s * 0.1, 1.03, -0.125), (s * 0.105, 1.2, -0.135), (s * 0.11, 1.38, -0.116), (s * 0.115, 1.48, -0.06),
                     (s * 0.115, 1.505, 0.0), (s * 0.1, 1.46, 0.08), (s * 0.05, 1.32, 0.125), (0.0, 1.22, 0.125)],
                0.036, 0.008, C['leather'], 'torso', step=0.015, name='ystrap')
        for i in range(3):
            body.belt_pouch(k, ts, math.pi / 2 - s * (0.36 + 0.29 * i), 1.0, 0.04, 0.075, 0.03, C['leather'],
                            C['leather_dark'], 'hips', rx=0.162, ry=0.11)
    # a stick grenade pushed down behind the belt on the left
    body.stick_grenade(k, (-0.178, 1.19, -0.04), (0.04, -1, -0.08), 'hips')
    k.strap(ts, [(0.0, 1.22, 0.125), (0.0, 1.03, 0.115)], 0.04, 0.008, C['leather'], 'torso', name='ystrap_back')
    # gas-mask canister (fluted) and bread bag at the back
    can = V(0.13, 0.86, 0.13)
    k.capsule(can + V(0, 0.13, 0), can - V(0, 0.12, 0), 0.05, 0.05, C['canister'], 'hips', name='canister')
    for dy in (-0.06, 0.0, 0.06):
        k.loft([(can + V(0, dy - 0.006, 0), 0.054, 0.054), (can + V(0, dy + 0.006, 0), 0.054, 0.054)], C['canister'],
               'hips', n=16, name='flute')
    k.rbox((-0.13, 0.9, 0.11), (0.08, 0.17, 0.12), C['breadbag'], 'hips', name='breadbag', p=3.0)
    k.rbox((-0.13, 0.96, 0.115), (0.085, 0.06, 0.13), C['breadbag'], 'hips', name='breadbag_flap', p=3.0)
    # chinstrap, helmet vents
    for s in (-1, 1):
        k.ribbon([V(s * 0.104, 1.71, 0.02 - body.HEAD_FWD), V(s * 0.082, 1.645, -0.025 - body.HEAD_FWD), V(s * 0.045, 1.598, -0.058 - body.HEAD_FWD),
                  V(0, 1.585, -0.072 - body.HEAD_FWD)],
                 [V(s, 0.1, 0), V(s, -0.2, -0.3), V(s, -0.6, -0.5), V(0, -0.7, -0.7)], 0.014, 0.004, C['belt'],
                 'head', name='chinstrap')
    hs = k.surface([o for o in k.objects() if o.name.endswith('stahlhelm')])
    for s in (-1, 1):
        k.stud(hs, (s * 0.11, 1.79, 0.03 - body.HEAD_FWD), 0.006, 0.006, C['helmet'], 'head', name='vent')
    return {'torso': torso, **legs, **arms}
