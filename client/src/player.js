// Local first-person controller: look, WASD movement, jump, crouch on the shared Rapier character motor.
import { PLAYER } from '@shared/constants.js'
import { CharacterMotor } from '@shared/physics.js'

const FIXED_DT = 1 / 120

export class LocalPlayer {
  constructor (RAPIER, world) {
    this.motor = new CharacterMotor(RAPIER, world)
    this.yaw = 0
    this.pitch = 0
    this.alive = false
    this.life = 0
    this.hp = PLAYER.maxHealth
    this.eye = PLAYER.eye
    this.wantCrouch = false
    this.acc = 0
    this.prev = { x: 0, y: 0, z: 0 } // feet position before the last physics step (render interpolation)
    this.stepUp = 0 // eye offset easing out autostep / curb climbs
    this.stepDist = 0
    this.speed = 0
    this.landed = 0
    this.fallSpeed = 0
    this.deathAt = 0
    this.deathPos = null
  }

  get pos () { return this.motor.pos }
  get crouched () { return this.motor.crouched }
  get grounded () { return this.motor.grounded }

  spawn (pos, yaw, life) {
    this.motor.setCrouch(false)
    this.motor.setPosition(pos[0], pos[1] + 0.02, pos[2])
    this.yaw = yaw
    this.pitch = 0
    this.alive = true
    this.life = life
    this.hp = PLAYER.maxHealth
    this.eye = PLAYER.eye
    this.acc = 0
    this._snapRender()
  }

  teleport (pos) {
    this.motor.setPosition(pos[0], pos[1] + 0.02, pos[2])
    this._snapRender()
  }

  _snapRender () {
    const p = this.motor.pos
    this.prev.x = p.x; this.prev.y = p.y; this.prev.z = p.z
    this.stepUp = 0
  }

  look (dx, dy) {
    this.yaw -= dx
    this.pitch = Math.max(-1.5, Math.min(1.5, this.pitch - dy))
    if (this.yaw > Math.PI) this.yaw -= Math.PI * 2
    else if (this.yaw < -Math.PI) this.yaw += Math.PI * 2
  }

  /**
   * ctl: { f, b, l, r, jump, crouch, ads, speedMul }  (booleans; ads is 0..1, speedMul from the weapon in hand)
   * returns { steps: number of footsteps to play, landed: impact speed or 0 }
   */
  update (dt, ctl) {
    const out = { steps: 0, landed: 0 }
    if (!this.alive) return out
    this.motor.setCrouch(ctl.crouch)
    let fx = 0; let fz = 0
    if (ctl.f) fz -= 1
    if (ctl.b) fz += 1
    if (ctl.l) fx -= 1
    if (ctl.r) fx += 1
    const len = Math.hypot(fx, fz)
    let speed = this.motor.crouched ? PLAYER.crouchSpeed : PLAYER.walkSpeed
    speed *= 1 - (1 - PLAYER.adsSpeedMul) * ctl.ads
    speed *= ctl.speedMul ?? 1 // weapon weight
    if (fz > 0) speed *= 0.9 // backpedal slower
    let wx = 0; let wz = 0
    if (len > 0) {
      fx /= len; fz /= len
      const s = Math.sin(this.yaw); const c = Math.cos(this.yaw)
      // camera basis: forward (-sin, -cos), right (cos, -sin)
      wx = (fx * c + fz * s) * speed
      wz = (-fx * s + fz * c) * speed
    }
    this.acc = Math.min(this.acc + dt, 0.1)
    let jump = ctl.jump
    const p = this.motor.pos
    while (this.acc >= FIXED_DT) {
      this.acc -= FIXED_DT
      this.prev.x = p.x; this.prev.y = p.y; this.prev.z = p.z
      const vy = this.motor.vel.y
      const wasGrounded = this.motor.grounded
      const r = this.motor.step(FIXED_DT, wx, wz, jump && !this.motor.crouched)
      jump = false
      if (r.landed && vy < -3) out.landed = Math.max(out.landed, -vy)
      // stepping up a curb lifts the capsule several cm in one step: ease the camera up instead
      const rise = p.y - this.prev.y
      if (wasGrounded && this.motor.grounded && rise > 0.03) this.stepUp = Math.max(-0.45, this.stepUp - rise)
    }
    this.stepUp *= Math.exp(-dt * 18)
    const v = this.motor.vel
    this.speed = Math.hypot(v.x, v.z)
    if (this.motor.grounded && this.speed > 0.5) {
      this.stepDist += this.speed * dt
      const stride = this.motor.crouched ? 1.6 : 2.3
      if (this.stepDist > stride) { this.stepDist -= stride; out.steps = 1 }
    }
    // smooth eye height for crouch transitions
    const targetEye = this.motor.crouched ? PLAYER.crouchEye : PLAYER.eye
    this.eye += (targetEye - this.eye) * Math.min(1, dt * 14)
    // void safety
    if (this.motor.pos.y < -10) { this.motor.setPosition(this.motor.pos.x, 5, this.motor.pos.z); this._snapRender() }
    return out
  }

  // camera position: interpolated between the last two physics steps so motion is smooth at any frame rate
  eyePos (out) {
    const p = this.motor.pos; const q = this.prev
    const a = this.alive ? this.acc / FIXED_DT : 1
    out.set(q.x + (p.x - q.x) * a, q.y + (p.y - q.y) * a + this.eye + this.stepUp, q.z + (p.z - q.z) * a)
    return out
  }

  dispose () { this.motor.dispose() }
}
