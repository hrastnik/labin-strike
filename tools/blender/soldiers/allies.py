"""US paratrooper: M1 helmet with the 101st's spade, M42 jump jacket (open collar over a white undershirt, slanted
chest pockets, flag armband, Screaming Eagle patch), tan suspenders and cartridge belt, M42 trousers with cargo
pockets and leg ties, bloused over brown jump boots."""
import math

from . import body
from .lib import V

C = {
    'jacket': '#6c6a49',
    'jacket_dark': '#5d5b3e',
    'trousers': '#6a6747',
    'webbing': '#b3a273',
    'webbing_dark': '#9a8a5f',
    'helmet': '#4e5333',
    'strap': '#6a6640',
    'boot': '#5b3424',
    'sole': '#2a1d16',
    'shirt': '#e6e3da',
    'cuff': '#646243',
}

# first-person sleeves
FP = {'jacket': C['jacket'], 'cuff': C['cuff'], 'tab': C['jacket_dark'], 'button': '#4a4636'}

HARD = {body.SKIN, body.SKIN_SHADE, body.LIPS, C['helmet'], C['boot'], C['sole'], '#8a8a80', body.MK2, body.FUZE,
        body.RING}

STYLE = {
    'jacket': C['jacket'],
    'trousers': C['trousers'],
    'cuff': C['cuff'],
    'face': {'hair': '#4e3828', 'brow': '#4a3424', 'iris': '#5a4636'},
    # (y, rx, ry, z centre): hem over the hips up to the neck
    'torso': [(0.80, 0.162, 0.118, 0.004), (0.86, 0.168, 0.12, 0.002), (0.95, 0.166, 0.116, 0),
              (1.04, 0.158, 0.108, 0), (1.13, 0.164, 0.112, -0.004), (1.23, 0.174, 0.12, -0.01),
              (1.32, 0.18, 0.122, -0.01), (1.40, 0.178, 0.114, -0.004), (1.46, 0.152, 0.098, 0.0),
              (1.5, 0.105, 0.078, 0.004), (1.53, 0.066, 0.062, 0.004)],
    'shin': lambda x: [((x, 0.49, -0.01), 0.06, 0.066), ((x, 0.4, 0.0), 0.06, 0.068), ((x, 0.32, 0.004), 0.066, 0.07),
                       ((x, 0.27, 0.0), 0.07, 0.072), ((x, 0.23, 0.0), 0.06, 0.062)],
}


def boot(k, x, n):
    b = f'foot_{n}'
    k.loft([((x, 0.27, 0.0), 0.052, 0.056), ((x, 0.18, 0.004), 0.05, 0.054), ((x, 0.1, 0.004), 0.05, 0.058)],
           C['boot'], f'shin_{n}', n=20, name='shaft')
    k.rbox((x, 0.055, -0.035), (0.102, 0.1, 0.27), C['boot'], b, p=3.2, name='foot')
    k.rbox((x, 0.075, -0.13), (0.096, 0.07, 0.1), C['boot'], b, p=2.6, name='toe')
    k.rbox((x, 0.012, -0.04), (0.108, 0.026, 0.285), C['sole'], b, p=4.5, name='sole')
    k.rbox((x, 0.02, 0.06), (0.09, 0.04, 0.07), C['sole'], b, p=4.5, name='heel')


STYLE['boot'] = boot


def build(k):
    st = STYLE
    torso = body.build_torso(k, st)
    body.build_pelvis(k, st)
    legs = body.build_legs(k, st)
    body.build_neck_head(k, st)
    arms = body.build_arms(k, st)
    body.m1_helmet(k, C['helmet'], C['strap'])
    ts = k.surface([torso])

    # --- collar, lapels and the undershirt in the V
    k.patch(ts, [(-0.045, 1.53, -0.055), (0.045, 1.53, -0.055), (0.012, 1.43, -0.115), (-0.012, 1.43, -0.115)], 0.006,
            C['shirt'], 'torso', nu=4, nv=4, name='shirt')
    k.loft([((0.045, 1.5, -0.06), 0.016, 0.018), ((0.075, 1.53, -0.02), 0.016, 0.02), ((0.06, 1.56, 0.04), 0.015, 0.02),
            ((0, 1.565, 0.068), 0.015, 0.02), ((-0.06, 1.56, 0.04), 0.015, 0.02), ((-0.075, 1.53, -0.02), 0.016, 0.02),
            ((-0.045, 1.5, -0.06), 0.016, 0.018)], C['jacket'], 'torso', n=10, name='collar')
    for s in (-1, 1):
        k.patch(ts, [(s * 0.035, 1.505, -0.08), (s * 0.12, 1.46, -0.1), (s * 0.075, 1.36, -0.125),
                     (s * 0.022, 1.405, -0.12)], 0.009, C['jacket'], 'torso', nu=4, nv=4, name='lapel')

    # --- slanted chest pockets with flaps, big skirt pockets
    for s in (-1, 1):
        x0 = s * 0.035
        k.patch(ts, [(x0, 1.36, -0.13), (s * 0.165, 1.33, -0.1), (s * 0.165, 1.16, -0.11), (x0, 1.19, -0.13)],
                0.012, C['jacket'], 'torso', bulge=0.012, name='pocket')
        k.patch(ts, [(x0 - s * 0.004, 1.375, -0.13), (s * 0.168, 1.345, -0.1), (s * 0.168, 1.3, -0.104),
                     (x0 - s * 0.004, 1.33, -0.13)], 0.022, C['jacket_dark'], 'torso', nu=6, nv=3, name='flap')
        k.patch(ts, [(s * 0.04, 1.0, -0.12), (s * 0.165, 1.0, -0.1), (s * 0.165, 0.83, -0.11), (s * 0.04, 0.83, -0.12)],
                0.012, C['jacket'], 'hips', bulge=0.014, name='skirt_pocket')
        k.patch(ts, [(s * 0.038, 1.0, -0.125), (s * 0.168, 1.0, -0.104), (s * 0.168, 0.955, -0.108),
                     (s * 0.038, 0.955, -0.125)], 0.02, C['jacket_dark'], 'hips', nu=6, nv=3, name='skirt_flap')
    # zip / front closure
    k.strap(ts, [(0.0, 1.38, -0.13), (0.0, 0.82, -0.13)], 0.022, 0.006, C['jacket_dark'],
            lambda p: 'hips' if p.y < 0.99 else 'torso', name='placket')

    # --- webbing: cartridge belt with pockets, suspenders, canteen and first-aid pouch
    belt = [(0.17 * math.cos(a), 1.01, -0.118 * math.sin(a)) for a in [i * math.tau / 16 for i in range(16)]]
    k.strap(ts, belt, 0.06, 0.012, C['webbing'], 'hips', closed=True, name='belt')
    for a in (-1.05, -0.66, -0.27, 0.27, 0.66, 1.05):
        body.belt_pouch(k, ts, math.pi / 2 + a, 1.005, 0.05, 0.062, 0.022, C['webbing'], C['webbing_dark'], 'hips',
                        rx=0.17, ry=0.118)
    k.rbox((0.0, 1.0, -0.14), (0.05, 0.05, 0.02), '#8a8a80', 'hips', name='buckle')
    for s in (-1, 1):
        k.strap(ts, [(s * 0.09, 1.03, -0.125), (s * 0.1, 1.2, -0.135), (s * 0.11, 1.38, -0.115), (s * 0.12, 1.48, -0.06),
                     (s * 0.12, 1.5, 0.0), (s * 0.11, 1.46, 0.08), (s * 0.08, 1.3, 0.13), (s * 0.06, 1.05, 0.12)],
                0.042, 0.008, C['webbing'], 'torso', step=0.015, name='suspender')
    # two Mk 2 grenades hooked onto the suspenders
    for s in (-1, 1):
        body.mk2(k, (s * 0.1, 1.215, -0.155), 'torso')
    k.capsule((0.17, 0.98, 0.07), (0.17, 0.82, 0.08), 0.05, 0.05, C['webbing_dark'], 'hips', name='canteen', flat=0.6,
              side=(1, 0, 0))
    k.rbox((-0.17, 0.93, -0.04), (0.06, 0.1, 0.13), C['webbing'], 'hips', name='first_aid')
    # musette bag low on the belly (as in the illustration)
    k.rbox((-0.07, 0.9, -0.17), (0.2, 0.15, 0.06), C['webbing'], 'hips', name='musette', p=3.2)
    k.rbox((-0.07, 0.955, -0.19), (0.2, 0.05, 0.035), C['webbing_dark'], 'hips', name='musette_flap', p=3.2)

    # --- shoulder insignia: flag armband on the right, Screaming Eagle on the left
    up_r = k.surface([arms['upper_r']])
    s_, e_, _, _, _ = body.arm_rest(1)
    ax = (e_ - s_).normalized()
    out = V(1, 0, 0)
    fwd = out.cross(ax).normalized()
    c0 = s_ + ax * 0.075 + out * 0.06
    w, h = 0.07, 0.05   # across x down
    for i in range(7):
        t0, t1 = i / 7, (i + 1) / 7
        corners = [c0 - fwd * w / 2 + ax * (t0 * h), c0 + fwd * w / 2 + ax * (t0 * h),
                   c0 + fwd * w / 2 + ax * (t1 * h), c0 - fwd * w / 2 + ax * (t1 * h)]
        k.patch(up_r, corners, 0.0025, '#b22234' if i % 2 == 0 else '#efece4', 'upperarm_r', nu=3, nv=1,
                name='stripe', role='decal')
    k.patch(up_r, [c0 + fwd * w / 2 - fwd * 0.03, c0 + fwd * w / 2, c0 + fwd * w / 2 + ax * (h * 4 / 7),
                   c0 + fwd * w / 2 - fwd * 0.03 + ax * (h * 4 / 7)], 0.0035, '#2b3165', 'upperarm_r', nu=2, nv=2,
            name='canton', role='decal')
    up_l = k.surface([arms['upper_l']])
    s_, e_, _, _, _ = body.arm_rest(-1)
    ax = (e_ - s_).normalized()
    out = V(-1, 0, 0)
    fwd = ax.cross(out).normalized()
    c0 = s_ + ax * 0.07 + out * 0.06
    k.patch(up_l, [c0 - fwd * 0.026, c0 + fwd * 0.026, c0 + fwd * 0.02 + ax * 0.06, c0 - fwd * 0.02 + ax * 0.06],
            0.003, '#17171a', 'upperarm_l', nu=3, nv=3, name='patch', role='decal')
    k.patch(up_l, [c0 - fwd * 0.015 + ax * 0.018, c0 + fwd * 0.012 + ax * 0.018, c0 + fwd * 0.01 + ax * 0.045,
                   c0 - fwd * 0.012 + ax * 0.045], 0.0045, '#ecebe6', 'upperarm_l', nu=2, nv=2, name='eagle',
            role='decal')
    k.patch(up_l, [c0 - fwd * 0.026 - ax * 0.016, c0 + fwd * 0.026 - ax * 0.016, c0 + fwd * 0.026 - ax * 0.002,
                   c0 - fwd * 0.026 - ax * 0.002], 0.003, '#c9a43c', 'upperarm_l', nu=3, nv=1, name='tab',
            role='decal')

    # --- trousers: cargo pockets and leg ties, the bloused cuff over the boots
    for side, n in ((1, 'r'), (-1, 'l')):
        x = side * 0.1
        ls = k.surface([legs['thigh_' + n]])
        k.patch(ls, [(x + side * 0.07, 0.82, -0.075), (x + side * 0.088, 0.82, 0.03), (x + side * 0.08, 0.6, 0.03),
                     (x + side * 0.065, 0.6, -0.06)], 0.018, C['trousers'], f'thigh_{n}', bulge=0.02, name='cargo')
        k.patch(ls, [(x + side * 0.068, 0.835, -0.08), (x + side * 0.09, 0.835, 0.035), (x + side * 0.088, 0.78, 0.035),
                     (x + side * 0.066, 0.78, -0.075)], 0.03, C['trousers'], f'thigh_{n}', nu=5, nv=3, name='cargo_flap')
        ring = [(x + 0.083 * math.cos(a), 0.66, -0.088 * math.sin(a)) for a in [i * math.tau / 16 for i in range(16)]]
        k.strap(ls, ring, 0.018, 0.008, C['webbing'], f'thigh_{n}', closed=True, name='legtie')
        ss = k.surface([legs['shin_' + n]])
        ring = [(x + 0.064 * math.cos(a), 0.42, -0.07 * math.sin(a)) for a in [i * math.tau / 16 for i in range(16)]]
        k.strap(ss, ring, 0.016, 0.007, C['webbing'], f'shin_{n}', closed=True, name='kneetie')
    # helmet: chinstrap and the spade on both sides
    for s in (-1, 1):
        k.ribbon([V(s * 0.112, 1.722, 0.012 - body.HEAD_FWD), V(s * 0.082, 1.65, -0.03 - body.HEAD_FWD), V(s * 0.045, 1.6, -0.06 - body.HEAD_FWD),
                  V(0, 1.585, -0.075 - body.HEAD_FWD)],
                 [V(s, 0.1, 0), V(s, -0.2, -0.3), V(s, -0.6, -0.5), V(0, -0.7, -0.7)], 0.016, 0.005, C['strap'],
                 'head', name='chinstrap')
    hs = k.surface([o for o in k.objects() if o.name.endswith('m1')])
    for s in (-1, 1):
        k.stud(hs, (s * 0.125, 1.79, -body.HEAD_FWD), 0.018, 0.004, '#e8e6e0', 'head', name='spade', ry=0.021)['role'] = 'decal'
    return {'torso': torso, **legs, **arms}
