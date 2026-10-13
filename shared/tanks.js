// Tanks: one per side, driven by a soldier. Dimensions are fitted to the Quaternius models in client/public/assets/tanks
// (scaled by 0.36): a hull box and a turret box per side, analytic ray / distance tests against them, the gun's line, and
// the motor that drives the hull on the shared Rapier world (the driver's client runs it, the server only poses it).
import { PLAYER } from './constants.js'
import { GRENADE } from './weapons.js'
import { SD } from './modes.js'
import { TANK_GROUPS, TANK_QUERY } from './physics.js'

export const TANK = {
  maxHealth: 600,
  speed: 6.5, // m/s forward
  reverse: 3,
  accel: 4, // m/s²
  brake: 9,
  turnRate: 0.85, // rad/s, hull
  traverse: 1.1, // rad/s, turret
  elevate: 0.5, // rad/s, gun
  pitchMin: -0.14,
  pitchMax: 0.3,
  half: [1.85, 2.68], // hull half width (x) and half length (z)
  reach: 1.2, // how close to the hull a soldier has to be to climb in
  reload: 4, // seconds between shells
  range: 250,
  damage: 230, // shell, on soldiers
  killRadius: 2.5,
  blastRadius: 8,
  crushSpeed: 1.5, // m/s from which the tracks kill an enemy they roll over
  gunId: 'tankgun',
  crushId: 'tracks',
  // turret pivot and gun pivot in hull space (x right, y up, -z the front), the turret box around its centre
  sides: {
    allies: { id: 1, name: 'M4 Sherman', gunName: '75 mm M3', hullH: 1.78, pivot: [0, 0], turret: { c: [0, 1.8, 0], h: [0.94, 0.63, 0.94] }, gunAt: [0, 1.88, -0.77], barrel: 1.87 },
    axis: { id: 2, name: 'Panzer IV', gunName: '7.5 cm KwK 40', hullH: 1.17, pivot: [0, 0.56], turret: { c: [0, 1.37, 0.54], h: [0.83, 0.33, 0.86] }, gunAt: [0, 1.4, -0.19], barrel: 3.34 }
  }
}

// what the armour makes of each kind of hit: small arms barely scratch it, explosives are what kills a tank
const ARMOUR = { [GRENADE.id]: 2, [SD.bomb.id]: 3, [TANK.gunId]: 0.9 }
export const armourFor = (weapon) => ARMOUR[weapon] ?? 0.08

export const tankSide = (team) => TANK.sides[team]
export const tankTeam = (id) => id === TANK.sides.allies.id ? 'allies' : id === TANK.sides.axis.id ? 'axis' : null

export function shellDamage (distance) {
  const { damage, killRadius, blastRadius } = TANK
  if (!(distance < blastRadius)) return 0
  if (distance <= killRadius) return damage
  return Math.round(damage * (1 - (distance - killRadius) / (blastRadius - killRadius)))
}

const wrap = (a) => { a = (a + Math.PI) % (Math.PI * 2); return (a < 0 ? a + Math.PI * 2 : a) - Math.PI }
export { wrap as wrapAngle }

// t: { team, pos: [x, y, z] (bottom centre), yaw, turret (world yaw), gun (pitch) }
function toWorld (t, lx, ly, lz) {
  const c = Math.cos(t.yaw); const s = Math.sin(t.yaw)
  return [t.pos[0] + lx * c + lz * s, t.pos[1] + ly, t.pos[2] - lx * s + lz * c]
}

// a point in the turret's frame (relative to its pivot), in hull space
function turretToHull (t, x, z) {
  const sd = tankSide(t.team)
  const r = t.turret - t.yaw
  const c = Math.cos(r); const s = Math.sin(r)
  return [sd.pivot[0] + x * c + z * s, sd.pivot[1] - x * s + z * c]
}

// oriented boxes { c, yaw, h }: the hull, then the turret
export function tankBoxes (t) {
  const sd = tankSide(t.team)
  const tc = sd.turret.c
  const [lx, lz] = turretToHull(t, tc[0] - sd.pivot[0], tc[2] - sd.pivot[1])
  return [
    { c: toWorld(t, 0, sd.hullH / 2, 0), yaw: t.yaw, h: [TANK.half[0], sd.hullH / 2, TANK.half[1]] },
    { c: toWorld(t, lx, tc[1], lz), yaw: t.turret, h: sd.turret.h }
  ]
}

function toBox (b, v) {
  const c = Math.cos(b.yaw); const s = Math.sin(b.yaw)
  return [v[0] * c - v[2] * s, v[1], v[0] * s + v[2] * c]
}

// distance along the ray (d normalized) to the oriented box { c, yaw, h } within maxT, or null
export function rayBox (o, d, maxT, b) {
  const lo = toBox(b, [o[0] - b.c[0], o[1] - b.c[1], o[2] - b.c[2]])
  const ld = toBox(b, d)
  let t0 = 0; let t1 = maxT
  for (let i = 0; i < 3; i++) {
    if (Math.abs(ld[i]) < 1e-9) {
      if (Math.abs(lo[i]) > b.h[i]) return null
      continue
    }
    let a = (-b.h[i] - lo[i]) / ld[i]
    let z = (b.h[i] - lo[i]) / ld[i]
    if (a > z) [a, z] = [z, a]
    t0 = Math.max(t0, a)
    t1 = Math.min(t1, z)
    if (t0 > t1) return null
  }
  return t0
}

// distance along the ray (d normalized) to the tank within maxT, or null
export function rayVsTank (o, d, maxT, t) {
  let best = null
  for (const b of tankBoxes(t)) {
    const h = rayBox(o, d, best ?? maxT, b)
    if (h != null && (best == null || h < best)) best = h
  }
  return best
}

// distance from p to the nearest point of the oriented box (0 inside it)
export function boxDistance (p, b) {
  const l = toBox(b, [p[0] - b.c[0], p[1] - b.c[1], p[2] - b.c[2]])
  return Math.hypot(Math.max(0, Math.abs(l[0]) - b.h[0]), Math.max(0, Math.abs(l[1]) - b.h[1]), Math.max(0, Math.abs(l[2]) - b.h[2]))
}

// distance from p to the nearest point of the tank (0 inside it)
export function tankDistance (p, t) {
  return Math.min(...tankBoxes(t).map((b) => boxDistance(p, b)))
}

// true if (x, z) at height y is under the hull, give or take pad metres
export function underHull (t, x, y, z, pad = 0) {
  if (y < t.pos[1] - 0.6 || y > t.pos[1] + tankSide(t.team).hullH) return false
  const l = toBox({ yaw: t.yaw }, [x - t.pos[0], 0, z - t.pos[2]])
  return Math.abs(l[0]) < TANK.half[0] + pad && Math.abs(l[2]) < TANK.half[1] + pad
}

// the gun's pivot o, its direction d and the muzzle
export function gunRay (t) {
  const sd = tankSide(t.team)
  const [lx, lz] = turretToHull(t, sd.gunAt[0] - sd.pivot[0], sd.gunAt[2] - sd.pivot[1])
  const o = toWorld(t, lx, sd.gunAt[1], lz)
  const cp = Math.cos(t.gun)
  const d = [-Math.sin(t.turret) * cp, Math.sin(t.gun), -Math.cos(t.turret) * cp]
  return { o, d, muzzle: [o[0] + d[0] * sd.barrel, o[1] + d[1] * sd.barrel, o[2] + d[2] * sd.barrel] }
}

// a point in hull space (x right, y up, z back) in the world
export function tankPoint (t, lx, ly, lz) { return toWorld(t, lx, ly, lz) }

const yawQuat = (yaw) => ({ x: 0, y: Math.sin(yaw / 2), z: 0, w: Math.cos(yaw / 2) })

// The hull's collider in a Rapier world. Posed from the network everywhere except on the driver's client, which
// drives it with a character controller: turning on the spot, throttle with momentum, climbing kerbs.
export class TankBody {
  constructor (RAPIER, world, team) {
    this.R = RAPIER
    this.world = world
    this.hh = tankSide(team).hullH / 2
    this.collider = world.createCollider(RAPIER.ColliderDesc.cuboid(TANK.half[0], this.hh, TANK.half[1]).setCollisionGroups(TANK_GROUPS))
    // a little smaller and lifted off the ground, so turning is only refused by walls, not by the road it sits on
    this.probe = new RAPIER.Cuboid(TANK.half[0] - 0.05, this.hh - 0.1, TANK.half[1] - 0.05)
    this.kcc = null
    this.pos = { x: 0, y: 0, z: 0 }
    this.yaw = 0
    this.speed = 0 // m/s along the hull, negative in reverse
    this.vy = 0
    this.grounded = true
  }

  setPose (x, y, z, yaw) {
    this.pos.x = x; this.pos.y = y; this.pos.z = z
    this.yaw = yaw
    this._sync()
  }

  stop () { this.speed = 0; this.vy = 0 }

  _sync () {
    this.collider.setTranslation({ x: this.pos.x, y: this.pos.y + this.hh, z: this.pos.z })
    this.collider.setRotation(yawQuat(this.yaw))
  }

  // throttle and steer in -1..1 (steer > 0 turns left); returns the distance moved
  drive (dt, throttle, steer) {
    if (!this.kcc) {
      const k = this.world.createCharacterController(0.03)
      k.setUp({ x: 0, y: 1, z: 0 })
      k.enableAutostep(0.45, 0.3, false)
      k.enableSnapToGround(0.5)
      k.setMaxSlopeClimbAngle((38 * Math.PI) / 180)
      k.setMinSlopeSlideAngle((45 * Math.PI) / 180)
      k.setSlideEnabled(true)
      k.setApplyImpulsesToDynamicBodies(false)
      this.kcc = k
    }
    const p = this.pos
    if (steer) {
      const yaw = wrap(this.yaw + steer * TANK.turnRate * dt)
      const hit = this.world.intersectionWithShape({ x: p.x, y: p.y + this.hh + 0.1, z: p.z }, yawQuat(yaw), this.probe, undefined, TANK_QUERY, this.collider)
      if (!hit) { this.yaw = yaw; this.collider.setRotation(yawQuat(yaw)) }
    }
    const target = throttle >= 0 ? throttle * TANK.speed : throttle * TANK.reverse
    const rate = Math.abs(target) < Math.abs(this.speed) || target * this.speed < 0 ? TANK.brake : TANK.accel
    this.speed += Math.max(-rate * dt, Math.min(rate * dt, target - this.speed))
    this.vy = this.grounded ? 0 : Math.max(-30, this.vy - PLAYER.gravity * dt)
    const fx = -Math.sin(this.yaw); const fz = -Math.cos(this.yaw)
    // see CharacterMotor.step: pushing into the ground while grounded can stall the controller
    const desired = { x: fx * this.speed * dt, y: this.vy * dt, z: fz * this.speed * dt }
    this.kcc.computeColliderMovement(this.collider, desired, undefined, TANK_QUERY)
    const m = this.kcc.computedMovement()
    p.x += m.x; p.y += m.y; p.z += m.z
    this.grounded = this.kcc.computedGrounded()
    // what a wall stopped is speed lost, so the tank does not sit against it with the throttle wound up
    const want = this.speed * dt
    if (Math.abs(want) > 1e-4) this.speed *= Math.max(0, Math.min(1, (m.x * fx + m.z * fz) / want))
    this._sync()
    return Math.hypot(m.x, m.z)
  }

  dispose () {
    if (this.kcc) this.world.removeCharacterController(this.kcc)
    this.world.removeCollider(this.collider, false)
  }
}
