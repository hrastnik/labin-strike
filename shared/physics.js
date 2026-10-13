// Rapier world construction + kinematic character motor shared by the client (local player)
// and the server (bots), so both move with exactly the same collision rules.
import { PLAYER } from './constants.js'

const groups = (member, filter) => ((member << 16) | filter) >>> 0
export const G_SOLID = 0x0001
export const G_CLIP = 0x0002
export const G_BULLET = 0x0004
export const G_CHAR = 0x0008
export const G_TANK = 0x0010
export const G_BIKE = 0x0020
export const SOLID_GROUPS = groups(G_SOLID, 0xffff)
export const CLIP_GROUPS = groups(G_CLIP, 0xffff)
export const BULLET_QUERY = groups(G_BULLET, G_SOLID) // bullets only hit solid geometry (tanks are hit-tested in tanks.js)
export const CHAR_GROUPS = groups(G_CHAR, G_SOLID | G_CLIP | G_TANK | G_BIKE) // characters ignore each other
export const TANK_GROUPS = groups(G_TANK, 0xffff)
export const TANK_QUERY = groups(G_TANK, G_SOLID | G_CLIP | G_TANK) // tanks drive through soldiers (and crush enemies) and bikes
export const BIKE_GROUPS = groups(G_BIKE, 0xffff)
export const BIKE_QUERY = groups(G_BIKE, G_SOLID | G_CLIP | G_TANK | G_BIKE) // bikes ride through soldiers

export function buildMapWorld (RAPIER, mapData) {
  const world = new RAPIER.World({ x: 0, y: 0, z: 0 })
  for (const c of mapData.colliders) {
    const [qx, qy, qz, qw] = c.rotation
    const shape = c.hull ? RAPIER.ColliderDesc.convexHull(c.hull) : RAPIER.ColliderDesc.cuboid(...c.halfExtents)
    if (!shape) continue // degenerate hull
    const desc = shape
      .setTranslation(c.position[0], c.position[1], c.position[2])
      .setRotation({ x: qx, y: qy, z: qz, w: qw })
      .setCollisionGroups(c.clip ? CLIP_GROUPS : SOLID_GROUPS)
    world.createCollider(desc)
  }
  world.step() // builds the broad-phase so scene queries work immediately
  return world
}

// Bullet raycast against solid map geometry. d must be normalized.
export function rayMap (RAPIER, world, o, d, maxDist) {
  const ray = new RAPIER.Ray({ x: o[0], y: o[1], z: o[2] }, { x: d[0], y: d[1], z: d[2] })
  const hit = world.castRayAndGetNormal(ray, maxDist, true, undefined, BULLET_QUERY)
  if (!hit) return null
  return { dist: hit.timeOfImpact, normal: [hit.normal.x, hit.normal.y, hit.normal.z] }
}

export function lineOfSight (RAPIER, world, a, b) {
  const d = [b[0] - a[0], b[1] - a[1], b[2] - a[2]]
  const len = Math.hypot(d[0], d[1], d[2])
  if (len < 1e-4) return true
  const n = [d[0] / len, d[1] / len, d[2] / len]
  return !rayMap(RAPIER, world, a, n, len - 0.05)
}

export class CharacterMotor {
  constructor (RAPIER, world) {
    this.R = RAPIER
    this.world = world
    this.kcc = world.createCharacterController(0.02)
    this.kcc.setUp({ x: 0, y: 1, z: 0 })
    this.kcc.enableAutostep(0.42, 0.12, false)
    this.kcc.enableSnapToGround(0.35)
    this.kcc.setMaxSlopeClimbAngle((52 * Math.PI) / 180)
    this.kcc.setMinSlopeSlideAngle((60 * Math.PI) / 180)
    this.kcc.setSlideEnabled(true)
    this.kcc.setApplyImpulsesToDynamicBodies(false)
    this.radius = PLAYER.radius
    this.height = PLAYER.height
    this.crouched = false
    this.collider = world.createCollider(
      RAPIER.ColliderDesc.capsule(this.height / 2 - this.radius, this.radius).setCollisionGroups(CHAR_GROUPS)
    )
    this.pos = { x: 0, y: 0, z: 0 } // feet position
    this.vel = { x: 0, y: 0, z: 0 }
    this.grounded = false
    this._standShape = new RAPIER.Capsule(PLAYER.height / 2 - this.radius, this.radius - 0.02)
  }

  setPosition (x, y, z) {
    this.pos.x = x; this.pos.y = y; this.pos.z = z
    this.vel.x = this.vel.y = this.vel.z = 0
    this._sync()
  }

  _sync () {
    this.collider.setTranslation({ x: this.pos.x, y: this.pos.y + this.height / 2, z: this.pos.z })
  }

  // returns the resulting crouch state (standing up needs headroom)
  setCrouch (want) {
    if (want === this.crouched) return this.crouched
    if (!want) {
      const free = !this.world.intersectionWithShape(
        { x: this.pos.x, y: this.pos.y + PLAYER.height / 2 + 0.03, z: this.pos.z },
        { x: 0, y: 0, z: 0, w: 1 }, this._standShape, undefined, CHAR_GROUPS, this.collider)
      if (!free) return this.crouched
    }
    this.crouched = want
    this.height = want ? PLAYER.crouchHeight : PLAYER.height
    this.collider.setHalfHeight(this.height / 2 - this.radius)
    this._sync()
    return this.crouched
  }

  /**
   * Integrates one step. wish = desired horizontal velocity (m/s).
   */
  step (dt, wishX, wishZ, jump) {
    const v = this.vel
    const accel = this.grounded ? 60 : 9
    const dx = wishX - v.x
    const dz = wishZ - v.z
    const dl = Math.hypot(dx, dz)
    const maxDv = accel * dt
    if (dl > maxDv) { v.x += (dx / dl) * maxDv; v.z += (dz / dl) * maxDv } else { v.x = wishX; v.z = wishZ }

    if (this.grounded && jump) {
      v.y = PLAYER.jumpSpeed
      this.grounded = false
    }
    v.y -= PLAYER.gravity * dt
    if (v.y < -40) v.y = -40

    // While grounded, don't push down into the floor: Rapier's controller sometimes resolves that
    // contact at toi 0 and cancels the whole step (a stall on flat ground). Snap-to-ground keeps
    // the character glued to slopes and down-steps instead.
    const wasAirborne = !this.grounded
    const dy = this.grounded && v.y <= 0 ? 0 : v.y * dt
    const desired = { x: v.x * dt, y: dy, z: v.z * dt }
    this.kcc.computeColliderMovement(this.collider, desired, undefined, CHAR_GROUPS)
    const m = this.kcc.computedMovement()
    this.pos.x += m.x; this.pos.y += m.y; this.pos.z += m.z
    this._sync()

    this.grounded = this.kcc.computedGrounded()
    if (this.grounded && v.y < 0) v.y = 0
    if (v.y > 0 && m.y < desired.y * 0.5) v.y = 0 // bumped head
    // lose the velocity that went into walls (only real side hits; a momentary short step must not
    // zero the speed, or the player visibly stutters while re-accelerating)
    for (let i = 0, n = this.kcc.numComputedCollisions(); i < n; i++) {
      const c = this.kcc.computedCollision(i)
      if (!c) continue
      const nx = c.normal1.x; const ny = c.normal1.y; const nz = c.normal1.z
      if (Math.abs(ny) > 0.3) continue // floors, ceilings and curb/step edges (autostep climbs those)
      const hl = Math.hypot(nx, nz)
      if (hl < 1e-3) continue
      const into = (v.x * nx + v.z * nz) / hl
      if (into < 0) { v.x -= (nx / hl) * into; v.z -= (nz / hl) * into }
    }
    return { landed: wasAirborne && this.grounded }
  }

  dispose () {
    this.world.removeCharacterController(this.kcc)
    this.world.removeCollider(this.collider, false)
  }
}
