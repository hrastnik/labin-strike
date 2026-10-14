"""First-person arms: the team's sleeves and the soldier's own (third-person) fist.

The fists are body.fist_shape, the same palm, finger roll and thumb the soldier model has, built in their grip frame:
    origin  the middle of the fist, where the grip passes through
    +y      along the grip (little finger -> index)
    +x      out of the back of the hand (right hand; the left hand is its mirror image)
    +z      towards the wrist, which sits at +z FIST
Sleeves are modelled along +y from their joint (shoulder or elbow), the forearm with the cuff at its far end.
"""
from . import body
from .lib import V

FORE = 0.26
UPPER = 0.29


def build_fist(k, side):
    """fist (side +1 right, -1 left) with a wrist long enough to disappear into the cuff."""
    d = V(0, 0, -1)
    body.fist_shape(k, V(0, 0, 0), d, side, 'hand')
    # the wrist widens into the forearm, which runs on inside the sleeve (no step where the cuff meets the hand)
    k.loft([(V(0, 0, body.FIST - 0.014), 0.025, 0.02), (V(0, 0.001, body.FIST + 0.012), 0.027, 0.021),
            (V(0, 0.002, body.FIST + 0.05), 0.033, 0.027), (V(0, 0.003, body.FIST + 0.1), 0.038, 0.034)], body.SKIN,
           'hand', n=18, name='wrist', side=V(0, 1, 0))


def build_forearm(k, team, C):
    """forearm sleeve from the elbow (origin) up +y to the cuff at FORE."""
    col = C['jacket']
    k.ellipsoid((0, 0.0, 0), (0.05, 0.05, 0.05), col, 'arm', name='elbow')
    k.loft([((0, 0.0, 0), 0.05, 0.052), ((0, 0.06, 0.002), 0.05, 0.05), ((0, 0.13, 0.0), 0.047, 0.045),
            ((0, 0.2, 0.0), 0.044, 0.041), ((0, FORE - 0.025, 0), 0.042, 0.04)], col, 'arm', n=28, name='fore')
    k.loft([((0, FORE - 0.035, 0), 0.0445, 0.0425), ((0, FORE + 0.004, 0), 0.0445, 0.0425)], C['cuff'], 'arm', n=28,
           name='cuff')
    # cuff hem: a slightly thicker rolled edge
    k.loft([((0, FORE - 0.002, 0), 0.0455, 0.0435), ((0, FORE + 0.006, 0), 0.0452, 0.0432)], C['cuff'], 'arm', n=28,
           name='hem')
    surf = k.surface([o for o in k.objects() if o.name.endswith('cuff')])
    if team == 'allies':
        # M42 jacket: a strap across the cuff, buttoned on the outside
        k.patch(surf, [(0.046, FORE - 0.03, -0.012), (0.046, FORE - 0.03, 0.03), (0.046, FORE - 0.008, 0.03),
                       (0.046, FORE - 0.008, -0.012)], 0.004, C['tab'], 'arm', nu=4, nv=2, name='tab')
        k.stud(surf, (0.05, FORE - 0.019, 0.022), 0.0065, 0.005, C['button'], 'arm', name='button')
    else:
        # M36 tunic: two small buttons beside the cuff slit
        for dy in (-0.022, -0.008):
            k.stud(surf, (0.012, FORE + dy, 0.044), 0.0055, 0.005, C['button'], 'arm', name='button')
        k.strap(surf, [(0.0, FORE - 0.035, 0.046), (0.0, FORE + 0.004, 0.046)], 0.004, 0.003, C['cuff_dark'], 'arm',
                name='slit', role='decal')


def build_upperarm(k, team, C):
    col = C['jacket']
    k.ellipsoid((0, 0.0, 0), (0.064, 0.064, 0.064), col, 'arm', name='shoulder')
    k.loft([((0, 0.0, 0), 0.062, 0.064), ((0, 0.12, 0.0), 0.058, 0.06), ((0, UPPER, 0.0), 0.053, 0.054)], col, 'arm',
           n=24, name='upper')
