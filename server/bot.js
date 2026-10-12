// Server-side TDM bot: patrols via the nav grid, acquires targets by line of sight,
// tracks them with human-like turn rates / aim error and fires bursts with weapon spread.
import { PLAYER, WEAPONS } from '../shared/constants.js'
import { GRENADE } from '../shared/weapons.js'
import { CharacterMotor, lineOfSight } from '../shared/physics.js'

const TAU = Math.PI * 2
const wrap = (a) => { a = (a + Math.PI) % TAU; return (a < 0 ? a + TAU : a) - Math.PI }
const approach = (cur, target, maxStep) => {
  const d = wrap(target - cur)
  return Math.abs(d) <= maxStep ? target : cur + Math.sign(d) * maxStep
}

export class Bot {
  constructor (game, player) {
    this.g = game
    this.p = player
    this.motor = new CharacterMotor(game.RAPIER, game.world)
    this.skill = 0.45 + Math.random() * 0.4
    this.seed = Math.random() * 1000
    this.reset()
  }

  // bots fight with their primary; the loadout is re-rolled from their faction on every spawn
  get wdef () { return WEAPONS[this.p.loadout.primary] }

  reset () {
    this.path = null
    this.pathIdx = 0
    this.goal = null
    this.target = null
    this.visible = false
    this.lastSeenAt = -1e9
    this.lastSeenPos = null
    this.alertPos = null
    this.alertAt = -1e9
    this.reactUntil = 0
    this.acquiredAt = 0
    this.initErr = 0
    this.nextShotAt = 0
    this.burstLeft = 0
    this.mag = this.wdef.mag
    this.reloadUntil = 0
    this.strafeDir = 0
    this.strafeUntil = 0
    this.wantCrouch = false
    this.pauseUntil = 0
    this.nextPerceive = 0
    this.stuckCheckAt = 0
    this.stuckPos = null
    this.stuckCount = 0
    this.jump = false
    this.lastHurtBy = null
    this.lastHurtAt = -1e9
    this.aimHead = false
    this.nadeRollAt = 0
  }

  dispose () { this.motor.dispose() }

  onSpawn () {
    const p = this.p
    this.reset()
    this.motor.setCrouch(false)
    this.motor.setPosition(p.pos[0], p.pos[1], p.pos[2])
    this.pauseUntil = this.g.now() + 300 + Math.random() * 600
  }

  onDamaged (attacker) {
    const now = this.g.now()
    this.lastHurtBy = attacker.id
    this.lastHurtAt = now
    if (!this.visible) {
      this.alertPos = attacker.pos.slice()
      this.alertAt = now
      this.nextPerceive = Math.min(this.nextPerceive, now + 60)
    }
  }

  hear (src) {
    if (this.visible || !this.p.alive) return
    const d = Math.hypot(src.pos[0] - this.p.pos[0], src.pos[2] - this.p.pos[2])
    if (d < 45) {
      this.alertPos = src.pos.slice()
      this.alertAt = this.g.now()
    }
  }

  eye () {
    const p = this.p
    return [p.pos[0], p.pos[1] + (this.motor.crouched ? PLAYER.crouchEye : PLAYER.eye), p.pos[2]]
  }

  perceive (now) {
    const p = this.p
    const eye = this.eye()
    let best = null; let bestScore = Infinity
    for (const q of this.g.players.values()) {
      if (q === p || !q.alive || q.team === p.team) continue
      const dx = q.pos[0] - eye[0]; const dz = q.pos[2] - eye[2]
      const dist = Math.hypot(dx, dz)
      if (dist > 95) continue
      const ang = Math.abs(wrap(Math.atan2(-dx, -dz) - p.yaw))
      const aware = q.id === this.target || q.id === this.lastHurtBy || now - q.firedAt < 600
      if (ang > 1.35 && dist > 4 && !(aware && now - this.lastHurtAt < 3000) && q.id !== this.target) continue
      const h = q.crouch ? PLAYER.crouchHeight : PLAYER.height
      const head = [q.pos[0], q.pos[1] + h - 0.15, q.pos[2]]
      const chest = [q.pos[0], q.pos[1] + h * 0.62, q.pos[2]]
      if (!lineOfSight(this.g.RAPIER, this.g.world, eye, chest) && !lineOfSight(this.g.RAPIER, this.g.world, eye, head)) continue
      const score = dist * (q.id === this.target ? 0.6 : 1)
      if (score < bestScore) { bestScore = score; best = q }
    }
    if (best) {
      if (best.id !== this.target || !this.visible) {
        const fresh = best.id !== this.target || now - this.lastSeenAt > 1500
        this.target = best.id
        if (fresh) {
          this.reactUntil = now + (520 - 300 * this.skill) + Math.random() * 180
          this.acquiredAt = now
          this.initErr = (0.07 + Math.random() * 0.06) * (1.35 - this.skill)
          this.aimHead = Math.random() < this.skill * 0.35
        }
      }
      this.visible = true
      this.lastSeenAt = now
      this.lastSeenPos = best.pos.slice()
    } else {
      this.visible = false
    }
  }

  update (dt, now, active) {
    const p = this.p
    const m = this.motor
    if (now >= this.nextPerceive) {
      this.perceive(now)
      this.nextPerceive = now + 110 + Math.random() * 90
    }
    let tgt = this.target ? this.g.players.get(this.target) : null
    if (tgt && !tgt.alive) { this.target = null; this.visible = false; tgt = null; this.burstLeft = 0 }
    const w = this.wdef
    if (this.reloadUntil && now >= this.reloadUntil) { this.reloadUntil = 0; this.mag = w.mag }

    let wishX = 0; let wishZ = 0
    let lookYaw = p.yaw; let lookPitch = 0
    let crouch = false
    const speed = PLAYER.walkSpeed * 0.92 * w.moveMul

    if (tgt && this.visible && active) {
      // ----- combat
      const eye = this.eye()
      const h = tgt.crouch ? PLAYER.crouchHeight : PLAYER.height
      const aimY = tgt.pos[1] + (this.aimHead ? h - 0.17 : h * 0.6)
      const dx = tgt.pos[0] - eye[0]; const dy = aimY - eye[1]; const dz = tgt.pos[2] - eye[2]
      const flat = Math.hypot(dx, dz)
      lookYaw = Math.atan2(-dx, -dz)
      lookPitch = Math.atan2(dy, flat)

      if (now >= this.strafeUntil) {
        const r = Math.random()
        this.strafeDir = r < 0.38 ? -1 : r < 0.76 ? 1 : 0
        this.wantCrouch = this.strafeDir === 0 && Math.random() < 0.6
        this.strafeUntil = now + 450 + Math.random() * 1100
      }
      crouch = this.wantCrouch
      let fwd = 0
      if (flat > 38) fwd = 0.7
      else if (flat < 6) fwd = -0.6
      const fx = -Math.sin(lookYaw); const fz = -Math.cos(lookYaw)
      const rx = -fz; const rz = fx
      let mx = fx * fwd + rx * this.strafeDir
      let mz = fz * fwd + rz * this.strafeDir
      const ml = Math.hypot(mx, mz)
      if (ml > 0.01) {
        mx /= ml; mz /= ml
        if (!this.g.nav.isWalkable(p.pos[0] + mx * 1.0, p.pos[2] + mz * 1.0)) {
          this.strafeDir = -this.strafeDir
          mx = 0; mz = 0
        }
        const sp = crouch ? PLAYER.crouchSpeed : speed * 0.7
        wishX = mx * sp; wishZ = mz * sp
      }
      this.path = null
      this.tryFire(now, tgt, flat, ml > 0.01)
    } else {
      this.burstLeft = 0
      if (active) this.maybeThrowGrenade(now)
      if (!this.reloadUntil && this.mag < w.mag * 0.4) this.reloadUntil = now + w.reloadTime * 1000
      // ----- navigation: last seen target > alert > patrol
      let dest = null
      if (this.target && this.lastSeenPos && now - this.lastSeenAt < 7000) dest = this.lastSeenPos
      else if (this.alertPos && now - this.alertAt < 9000) dest = this.alertPos
      else this.target = null

      if (dest && (!this.goal || Math.hypot(this.goal[0] - dest[0], this.goal[2] - dest[2]) > 3)) this.setGoal(dest)
      if (!dest && (!this.path || this.pathIdx >= this.path.length) && now >= this.pauseUntil) {
        if (this.path && this.pathIdx >= this.path.length && Math.random() < 0.45) {
          this.path = null
          this.pauseUntil = now + 600 + Math.random() * 1800
        } else {
          this.setGoal(this.pickPatrolGoal())
        }
      }
      if (this.path && this.pathIdx < this.path.length && active) {
        const wp = this.path[this.pathIdx]
        const dx = wp[0] - p.pos[0]; const dz = wp[2] - p.pos[2]
        const d = Math.hypot(dx, dz)
        if (d < 0.65) {
          this.pathIdx++
          if (dest && this.pathIdx >= this.path.length) {
            // reached last known position without contact: look around and give up the chase
            this.alertPos = null
            if (this.target) this.lastSeenAt = -1e9
          }
        } else {
          wishX = (dx / d) * speed; wishZ = (dz / d) * speed
          lookYaw = Math.atan2(-dx, -dz)
        }
      } else if (now < this.pauseUntil) {
        lookYaw = p.yaw + Math.sin(now * 0.0012 + this.seed) * 0.02
      }
      if (dest && !this.path) lookYaw = Math.atan2(-(dest[0] - p.pos[0]), -(dest[2] - p.pos[2]))
    }

    // separation from nearby players so bots do not stack
    for (const q of this.g.players.values()) {
      if (q === p || !q.alive) continue
      const dx = p.pos[0] - q.pos[0]; const dz = p.pos[2] - q.pos[2]
      const d = Math.hypot(dx, dz)
      if (d < 1.1 && d > 0.001) { wishX += (dx / d) * 2.5 * (1.1 - d); wishZ += (dz / d) * 2.5 * (1.1 - d) }
    }

    // stuck detection
    if (now >= this.stuckCheckAt) {
      const moving = Math.hypot(wishX, wishZ) > 1
      if (this.stuckPos && moving && Math.hypot(p.pos[0] - this.stuckPos[0], p.pos[2] - this.stuckPos[2]) < 0.35) {
        this.stuckCount++
        this.jump = true
        if (this.stuckCount >= 2) { this.path = null; this.goal = null; this.stuckCount = 0; this.alertPos = null }
      } else {
        this.stuckCount = 0
      }
      this.stuckPos = p.pos.slice()
      this.stuckCheckAt = now + 1200
    }

    // aim / look with limited turn rate
    const turn = (3.2 + 3.8 * this.skill) * dt * (this.visible ? 1 : 0.7)
    p.yaw = wrap(approach(p.yaw, lookYaw, turn))
    p.pitch = p.pitch + (lookPitch - p.pitch) * Math.min(1, dt * 8)

    m.setCrouch(crouch)
    m.step(dt, active ? wishX : 0, active ? wishZ : 0, this.jump)
    this.jump = false
    if (m.pos.y < -10) { // fell out of the world somehow
      this.g.spawn(p)
      return
    }
    p.pos = [m.pos.x, m.pos.y, m.pos.z]
    p.posAt = now
    p.crouch = m.crouched
    p.reloading = !!this.reloadUntil
    p.slot = 0
  }

  tryFire (now, tgt, dist, moving) {
    if (now < this.reactUntil || now < this.nextShotAt || this.reloadUntil) return
    const p = this.p
    const eye = this.eye()
    const h = tgt.crouch ? PLAYER.crouchHeight : PLAYER.height
    const aimY = tgt.pos[1] + (this.aimHead ? h - 0.17 : h * 0.6)
    const want = Math.atan2(-(tgt.pos[0] - eye[0]), -(tgt.pos[2] - eye[2]))
    if (Math.abs(wrap(want - p.yaw)) > 0.14) return
    const w = this.wdef
    if (this.burstLeft <= 0) {
      if (w.action === 'bolt') this.burstLeft = 1
      else if (w.action === 'semi') this.burstLeft = Math.round(2 + Math.random() * 3)
      else this.burstLeft = Math.round(3 + Math.random() * (dist < 15 ? 8 : 4))
    }

    // tracking error shrinks the longer the bot stays on target
    const t = (now - this.acquiredAt) / 1000
    const err = 0.008 + 0.022 * (1 - this.skill) + this.initErr * Math.exp(-t / 0.75)
    const ex = Math.sin(now * 0.0047 + this.seed) * err
    const ey = Math.cos(now * 0.0039 + this.seed * 1.7) * err * 0.7
    const yaw = want + ex
    const pitch = Math.atan2(aimY - eye[1], Math.hypot(tgt.pos[0] - eye[0], tgt.pos[2] - eye[2])) + ey
    // automatics are sprayed from the hip; rifles are aimed when the bot stands still
    const still = w.action === 'auto' ? w.spread.hip * 0.9 : w.spread.hip + (w.spread.ads - w.spread.hip) * 0.7
    let spread = (moving ? w.spread.hip * 1.35 : still) * (this.motor.crouched ? w.spread.crouchMul : 1) * (1.25 - this.skill * 0.5)
    spread += Math.min(w.spread.bloomMax, (this.burstShots || 0) * w.spread.bloom * 0.6)
    const d = coneDir(yaw, pitch, spread)
    this.g.fireBot(p, w.id, eye, d)

    this.mag--
    this.burstLeft--
    this.burstShots = (this.burstShots || 0) + 1
    this.nextShotAt = now + 60000 / w.rpm + Math.random() * 15
    if (w.action === 'semi') this.nextShotAt = Math.max(this.nextShotAt, now + 170 + Math.random() * 200) // trigger finger
    else if (w.action === 'bolt') this.nextShotAt += Math.random() * 350
    if (this.burstLeft <= 0) {
      this.burstShots = 0
      this.nextShotAt += 220 + Math.random() * (180 + dist * 14)
    }
    if (this.mag <= 0) {
      this.reloadUntil = now + w.reloadTime * 1000
      this.burstShots = 0
    }
  }

  // lob the grenade at an enemy who just ducked out of sight
  maybeThrowGrenade (now) {
    const p = this.p
    if (!(p.grenades > 0) || !this.target || !this.lastSeenPos || now < this.nadeRollAt) return
    const lost = now - this.lastSeenAt
    if (lost < 700 || lost > 4000) return
    this.nadeRollAt = now + 5000
    if (Math.random() > 0.15 + 0.4 * this.skill) return
    const eye = this.eye()
    const t = this.lastSeenPos
    const dx = t[0] - eye[0]; const dz = t[2] - eye[2]
    const x = Math.hypot(dx, dz) * 0.9 // short: it bounces on
    if (x < 7 || x > 24) return
    const y = t[1] + 0.3 - eye[1]
    const v2 = GRENADE.speed ** 2; const g = GRENADE.gravity
    const disc = v2 * v2 - g * (g * x * x + 2 * y * v2)
    if (disc < 0) return
    const err = 1.3 - this.skill
    const pitch = Math.atan((v2 - Math.sqrt(disc)) / (g * x)) - GRENADE.loft + (Math.random() - 0.5) * 0.08 * err
    const yaw = Math.atan2(-dx, -dz) + (Math.random() - 0.5) * 0.1 * err
    const d = [-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch)]
    if (!lineOfSight(this.g.RAPIER, this.g.world, eye, [eye[0] + d[0] * 2, eye[1] + d[1] * 2, eye[2] + d[2] * 2])) return
    p.yaw = yaw
    this.g.throwGrenade(p, eye, d)
  }

  setGoal (pos) {
    const path = this.g.nav.findPath(this.p.pos, pos)
    this.goal = pos.slice()
    this.path = path
    this.pathIdx = 0
  }

  pickPatrolGoal () {
    const nav = this.g.nav
    const enemyBase = this.p.team === 'allies' ? -1 : 1 // allies spawn at +X, axis at -X
    const r = Math.random()
    let filter = null
    if (r < 0.45) filter = (c) => Math.abs(c[0]) < 28 // contested middle
    else if (r < 0.7) filter = (c) => c[0] * enemyBase > 10 // push towards the enemy side
    else if (r < 0.82) filter = (c) => c[1] > 2 // terrace
    const i = nav.randomCell(Math.random, filter)
    return nav.center(i)
  }
}

function coneDir (yaw, pitch, spread) {
  // random direction inside a cone around (yaw, pitch)
  const a = Math.random() * TAU
  const r = Math.sqrt(Math.random()) * spread
  const y2 = yaw + Math.cos(a) * r
  const p2 = pitch + Math.sin(a) * r
  const cp = Math.cos(p2)
  return [-Math.sin(y2) * cp, Math.sin(p2), -Math.cos(y2) * cp]
}
