// Motorcycles: one per side, always parked at each base. The rider sits up in the open, so they are shot like any
// soldier (their standing hitbox, leaned with the bike); the bike itself is one box. A destroyed bike is replaced at
// its base a minute later. BikeBody is the motor: the rider's client runs it, the server only poses it.
import { PLAYER } from './constants.js'
import { GRENADE } from './weapons.js'
import { SD } from './modes.js'
import { TANK, rayBox, boxDistance, wrapAngle } from './tanks.js'
import { BIKE_GROUPS, BIKE_QUERY } from './physics.js'

export const BIKE = {
  maxHealth: 180,
  speed: 15, // m/s forward
  reverse: 2.5,
  accel: 6, // m/s²
  brake: 14,
  coast: 2.5, // m/s² lost with the throttle shut
  steer: 0.45, // rad/s of turn per m/s of speed at full lock...
  turnRate: 1.9, // ...up to this
  leanAt: 12, // m/s² of cornering that leans the bike over fully
  half: [0.38, 0.55, 1.06], // half width, half height, half length
  reach: 1, // how close to the bike a soldier has to be to get on
  respawn: 60, // seconds from being destroyed to a new one at the base
  sides: {
    allies: { id: 1, name: 'Harley-Davidson WLA' },
    axis: { id: 2, name: 'BMW R35' }
  }
}

// small arms chip it, explosives wreck it
const TOUGHNESS = { [GRENADE.id]: 1.2, [SD.bomb.id]: 3, [TANK.gunId]: 2 }
export const toughnessFor = (weapon) => TOUGHNESS[weapon] ?? 0.6

export const bikeSide = (team) => BIKE.sides[team]
export const bikeTeam = (id) => id === BIKE.sides.allies.id ? 'allies' : id === BIKE.sides.axis.id ? 'axis' : null

// b: { pos: [x, y, z] (bottom centre), yaw }
export const bikeBox = (b) => ({ c: [b.pos[0], b.pos[1] + BIKE.half[1], b.pos[2]], yaw: b.yaw, h: BIKE.half })
export const rayVsBike = (o, d, maxT, b) => rayBox(o, d, maxT, bikeBox(b))
export const bikeDistance = (p, b) => boxDistance(p, bikeBox(b))

// a point in bike space (x right, y up, z back) in the world
export function bikePoint (b, lx, ly, lz) {
  const c = Math.cos(b.yaw); const s = Math.sin(b.yaw)
  return [b.pos[0] + lx * c + lz * s, b.pos[1] + ly, b.pos[2] - lx * s + lz * c]
}

const yawQuat = (yaw) => ({ x: 0, y: Math.sin(yaw / 2), z: 0, w: Math.cos(yaw / 2) })

export class BikeBody {
  constructor (RAPIER, world) {
    this.world = world
    const [hx, hy, hz] = BIKE.half
    this.collider = world.createCollider(RAPIER.ColliderDesc.cuboid(hx, hy, hz).setCollisionGroups(BIKE_GROUPS))
    this.probe = new RAPIER.Cuboid(hx - 0.03, hy - 0.12, hz - 0.03)
    this.kcc = null
    this.pos = { x: 0, y: 0, z: 0 }
    this.yaw = 0
    this.speed = 0 // m/s along the bike, negative in reverse
    this.vy = 0
    this.grounded = true
    this.lean = 0 // -1 hard over to the left .. 1 to the right
  }

  setPose (x, y, z, yaw) {
    this.pos.x = x; this.pos.y = y; this.pos.z = z
    this.yaw = yaw
    this._sync()
  }

  stop () { this.speed = 0; this.vy = 0; this.lean = 0 }

  _sync () {
    this.collider.setTranslation({ x: this.pos.x, y: this.pos.y + BIKE.half[1], z: this.pos.z })
    this.collider.setRotation(yawQuat(this.yaw))
  }

  // throttle and steer in -1..1 (steer > 0 turns left); a bike only turns while it rolls
  drive (dt, throttle, steer) {
    if (!this.kcc) {
      const k = this.world.createCharacterController(0.02)
      k.setUp({ x: 0, y: 1, z: 0 })
      k.enableAutostep(0.32, 0.2, false)
      k.enableSnapToGround(0.4)
      k.setMaxSlopeClimbAngle((38 * Math.PI) / 180)
      k.setMinSlopeSlideAngle((45 * Math.PI) / 180)
      k.setSlideEnabled(true)
      k.setApplyImpulsesToDynamicBodies(false)
      this.kcc = k
    }
    const p = this.pos
    const rate = Math.sign(this.speed) * Math.min(BIKE.turnRate, Math.abs(this.speed) * BIKE.steer)
    let turned = 0
    if (steer && rate) {
      const yaw = wrapAngle(this.yaw + steer * rate * dt)
      const hit = this.world.intersectionWithShape({ x: p.x, y: p.y + BIKE.half[1] + 0.1, z: p.z }, yawQuat(yaw), this.probe, undefined, BIKE_QUERY, this.collider)
      if (!hit) { this.yaw = yaw; turned = steer * rate; this.collider.setRotation(yawQuat(yaw)) }
    }
    const target = throttle > 0 ? throttle * BIKE.speed : throttle < 0 ? -BIKE.reverse : 0
    const accel = !throttle ? BIKE.coast : Math.abs(target) < Math.abs(this.speed) || target * this.speed < 0 ? BIKE.brake : BIKE.accel
    this.speed += Math.max(-accel * dt, Math.min(accel * dt, target - this.speed))
    this.vy = this.grounded ? 0 : Math.max(-30, this.vy - PLAYER.gravity * dt)
    const fx = -Math.sin(this.yaw); const fz = -Math.cos(this.yaw)
    // see CharacterMotor.step: pushing into the ground while grounded can stall the controller
    const desired = { x: fx * this.speed * dt, y: this.vy * dt, z: fz * this.speed * dt }
    this.kcc.computeColliderMovement(this.collider, desired, undefined, BIKE_QUERY)
    const m = this.kcc.computedMovement()
    p.x += m.x; p.y += m.y; p.z += m.z
    this.grounded = this.kcc.computedGrounded()
    const want = this.speed * dt
    if (Math.abs(want) > 1e-4) this.speed *= Math.max(0, Math.min(1, (m.x * fx + m.z * fz) / want))
    const lean = Math.max(-1, Math.min(1, -turned * Math.abs(this.speed) / BIKE.leanAt))
    this.lean += (lean - this.lean) * Math.min(1, dt * 6)
    this._sync()
  }

  dispose () {
    if (this.kcc) this.world.removeCharacterController(this.kcc)
    this.world.removeCollider(this.collider, false)
  }
}
