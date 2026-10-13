// Spectator camera: follow a soldier through their own eyes or over their shoulder, or fly free.
// Used by spectators (anyone, plus the free camera) and by the fallen in Search and Destroy (their own side only).
// Everything comes from the snapshots: the first-person weapon is posed from the flags (aiming, reloading) and the
// shot / stab / grenade messages, so it is an approximation of what the followed player sees.
import * as THREE from 'three'
import { PLAYER } from '@shared/constants.js'
import { WEAPONS, WEAPON_LIST, GRENADE, KNIFE } from '@shared/weapons.js'
import { tankSide } from '@shared/tanks.js'
import { leanShift } from '@shared/hitbox.js'

const SHOULDER = { back: 2.4, right: 0.45, up: 0.15 } // over-the-shoulder camera offset, metres
const TANK_BACK = 8 // behind a turret, as when driving
const LEAN_ROLL = 0.18 // camera roll at a full lean, as for our own soldier
const HOLD_FALLEN = 2000 // ms to stay on a soldier who went down before moving to the next one
const FREE_SPEED = 9 // m/s flying, Shift triples it
const THROW_TIME = GRENADE.windup + GRENADE.recover
const KNIFE_TIME = KNIFE.windup + KNIFE.recover

const fwd = new THREE.Vector3()
const right = new THREE.Vector3()
const pivot = new THREE.Vector3()
const dir = new THREE.Vector3()

const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a))

export class Spectator {
  // ray(o, d, maxDist) -> { dist } | null against the map, to keep the camera out of walls
  constructor (camera, viewmodel, ray, baseFov) {
    this.camera = camera
    this.baseFov = baseFov
    this.viewmodel = viewmodel
    this.ray = ray
    this.reset()
  }

  reset () {
    this.targetId = 0
    this.third = false
    this.free = false // the free camera, by choice
    this.flying = false // in the free camera this frame (by choice, or with nobody to follow)
    this.fallenAt = 0
    this.freeYaw = 0
    this.freePitch = -0.3
    this.firstPerson = false // the camera is in a followed soldier's head this frame (draw the viewmodel)
    this.vm = null
  }

  // the soldiers that may be followed, in a stable order
  candidates (avatars, pool) {
    return [...avatars.map.values()].filter((a) => a.alive && pool(a)).sort((a, b) => a.id - b.id)
  }

  cycle (avatars, pool, step) {
    const list = this.candidates(avatars, pool)
    this.free = false
    this.fallenAt = 0
    if (!list.length) { this.follow(0); return null }
    const i = list.findIndex((a) => a.id === this.targetId)
    const next = list[i < 0 ? (step > 0 ? 0 : list.length - 1) : (i + step + list.length) % list.length]
    this.follow(next.id)
    return next
  }

  follow (id) {
    if (id === this.targetId) return
    this.targetId = id
    this.vm = null // no draw animation for the weapon of someone we just switched to
  }

  /**
   * ctx: { avatars, tanks, input (null while the pointer is free), look: [dx, dy], pool: (avatar) => may follow,
   *        canFree: free camera allowed, bounds: map bounds, dt, now }
   * Places the camera and returns { target, mode: 'first' | 'third' | 'tank' | 'free', fov (0 = default), scoped },
   * or null when there is nobody to follow and no free camera (the caller shows its overview).
   */
  update (ctx) {
    const { avatars, input, pool, canFree } = ctx
    this.firstPerson = false
    if (input) {
      if (canFree && input.wasPressed('KeyF')) this.free = !this.free
      if (input.mouse.leftPressed) this.cycle(avatars, pool, 1)
      if (input.mouse.rightPressed) this.cycle(avatars, pool, -1)
      if (!this.free && input.wasPressed('Space')) this.third = !this.third
    }
    if (this.free && canFree) return this.fly(ctx)
    this.free = false
    this.flying = false

    let a = avatars.map.get(this.targetId)
    if (a && !pool(a)) a = null // switched sides, or not ours to watch
    if (a && !a.alive) {
      // stay on the fallen for a moment, then move on to the next one
      if (!this.fallenAt) this.fallenAt = ctx.now
      if (ctx.now - this.fallenAt > HOLD_FALLEN) a = this.cycle(avatars, pool, 1)
      else return { target: a, mode: this.third ? 'third' : 'first', fov: 0, scoped: false }
    }
    if (!a) a = this.cycle(avatars, pool, 1)
    if (!a) return canFree ? this.fly(ctx) : null // until someone is out there to follow
    this.fallenAt = 0
    if (a.tag) a.tag.visible = false

    const tank = a.inTank ? [...(ctx.tanks?.map.values() ?? [])].find((t) => t.driver === a.id) : null
    if (tank) return this.chaseTank(a, tank)
    const eye = PLAYER.eye + (PLAYER.crouchEye - PLAYER.eye) * a.crouch
    // a rider has both hands on the bars: nothing to see through their eyes
    if (this.third || a.onBike) return this.shoulder(a, eye)
    return this.eyes(a, eye, ctx)
  }

  fly ({ input, look, bounds, dt }) {
    const cam = this.camera
    if (!this.flying) {
      // take off from wherever the camera is now
      this.flying = true
      this.freeYaw = cam.rotation.y
      this.freePitch = cam.rotation.x
    }
    this.freeYaw = wrap(this.freeYaw - look[0])
    this.freePitch = Math.max(-1.5, Math.min(1.5, this.freePitch - look[1]))
    if (input) {
      const k = (input.down('ShiftLeft') || input.down('ShiftRight') ? 3 : 1) * FREE_SPEED * dt
      const y = this.freeYaw; const p = this.freePitch
      fwd.set(-Math.sin(y) * Math.cos(p), Math.sin(p), -Math.cos(y) * Math.cos(p))
      right.set(Math.cos(y), 0, -Math.sin(y))
      const ax = (input.down('KeyD') ? 1 : 0) - (input.down('KeyA') ? 1 : 0)
      const az = (input.down('KeyW') ? 1 : 0) - (input.down('KeyS') ? 1 : 0)
      const ay = (input.down('Space') ? 1 : 0) - (input.down('KeyC') || input.down('ControlLeft') ? 1 : 0)
      cam.position.addScaledVector(fwd, az * k).addScaledVector(right, ax * k)
      cam.position.y += ay * k
    }
    const m = 20
    cam.position.x = THREE.MathUtils.clamp(cam.position.x, bounds.min[0] - m, bounds.max[0] + m)
    cam.position.z = THREE.MathUtils.clamp(cam.position.z, bounds.min[2] - m, bounds.max[2] + m)
    cam.position.y = THREE.MathUtils.clamp(cam.position.y, bounds.min[1] + 0.5, bounds.max[1] + 40)
    cam.rotation.set(this.freePitch, this.freeYaw, 0)
    return { target: null, mode: 'free', fov: 0, scoped: false }
  }

  // camera at `from`, pulled in along `dir` to `dist` short of a wall
  pullIn (from, dist, min) {
    const hit = this.ray(from.toArray(), dir.toArray(), dist)
    return hit ? Math.max(min, hit.dist - 0.3) : dist
  }

  shoulder (a, eye) {
    const cam = this.camera
    const y = a.yaw; const p = a.pitch
    fwd.set(-Math.sin(y) * Math.cos(p), Math.sin(p), -Math.cos(y) * Math.cos(p))
    right.set(Math.cos(y), 0, -Math.sin(y))
    pivot.set(a.pos.x, a.pos.y + eye + SHOULDER.up, a.pos.z)
    // over the right shoulder: first out to the side (stopping at a wall), then back
    dir.copy(right)
    const side = this.pullIn(pivot, SHOULDER.right, 0)
    pivot.addScaledVector(right, side)
    dir.copy(fwd).negate()
    cam.position.copy(pivot).addScaledVector(dir, this.pullIn(pivot, SHOULDER.back, 0.3))
    cam.rotation.set(p, y, 0)
    return { target: a, mode: 'third', fov: 0, scoped: false }
  }

  chaseTank (a, t) {
    const cam = this.camera
    const y = t.turret; const p = Math.max(-0.5, Math.min(0.45, t.gun))
    fwd.set(-Math.sin(y) * Math.cos(p), Math.sin(p), -Math.cos(y) * Math.cos(p))
    pivot.set(t.pos[0], t.pos[1] + tankSide(t.team).hullH + 1.5, t.pos[2])
    dir.copy(fwd).negate()
    dir.y += 0.4
    dir.normalize()
    cam.position.copy(pivot).addScaledVector(dir, this.pullIn(pivot, TANK_BACK, 0.8))
    cam.rotation.set(p, y, 0)
    return { target: a, mode: 'tank', fov: 0, scoped: false }
  }

  eyes (a, eye, ctx) {
    const cam = this.camera
    const s = leanShift(a.yaw, a.lean)
    cam.position.set(a.pos.x + s[0], a.pos.y + eye, a.pos.z + s[1])
    cam.rotation.set(a.pitch, a.yaw, -a.lean * LEAN_ROLL)
    a.root.visible = false // we are inside their head
    this.firstPerson = true
    const { fov, scoped } = this.poseWeapon(a, ctx)
    return { target: a, mode: 'first', fov, scoped }
  }

  // drive the first-person weapon from what the snapshots say the followed soldier is doing
  poseWeapon (a, { dt, now }) {
    const id = WEAPON_LIST[a.weapon] || 'stg44'
    const w = WEAPONS[id]
    let s = this.vm
    if (!s || s.id !== a.id) {
      s = this.vm = { id: a.id, weapon: id, switchAt: -1e9, adsT: 0, sprintT: 0, reloadAt: 0, shotAt: -1e9, stabAt: -1e9, nadeAt: -1e9, yaw: a.yaw, pitch: a.pitch }
    }
    if (s.weapon !== id) { s.weapon = id; s.switchAt = now; s.reloadAt = 0 }
    this.viewmodel.setTeam(a.team)

    const ads = (a.flags & 4) && !a.inTank ? 1 : 0
    s.adsT = ads ? Math.min(1, s.adsT + dt / w.adsTime) : Math.max(0, s.adsT - dt / w.adsTime)
    const sprinting = !ads && !a.crouched && a.speed > PLAYER.walkSpeed * 1.12
    s.sprintT = THREE.MathUtils.clamp(s.sprintT + (sprinting ? dt : -dt) / 0.18, 0, 1)
    const reloading = !!(a.flags & 8)
    if (reloading && !s.reloadAt) s.reloadAt = now
    else if (!reloading) s.reloadAt = 0
    const r = w.reload
    const steps = r.style === 'single' ? w.mag : r.style === 'charger' ? Math.floor(w.mag / r.clip) + w.mag % r.clip : 1
    const sec = (t) => (now - t) / 1000
    const frac = (t, len) => { const f = sec(t) / len; return f >= 0 && f < 1 ? f : -1 }
    const dyaw = wrap(a.yaw - s.yaw); const dpitch = a.pitch - s.pitch
    s.yaw = a.yaw; s.pitch = a.pitch

    this.viewmodel.update({
      dt,
      weapon: id,
      ads: s.adsT,
      sprint: s.sprintT,
      speed: a.speed,
      grounded: true,
      crouched: a.crouched,
      reloadFrac: s.reloadAt ? Math.min(0.98, sec(s.reloadAt) / w.reloadTime) : -1,
      drawFrac: Math.max(0, 1 - sec(s.switchAt) / w.drawTime),
      // the grenade message comes at the release, so the throw is shown from there
      throwFrac: frac(s.nadeAt - GRENADE.windup * 1000, THROW_TIME),
      knifeFrac: frac(s.stabAt, KNIFE_TIME),
      cycleFrac: w.action === 'bolt' ? frac(s.shotAt, 60 / w.rpm) : -1,
      reloadSteps: steps,
      mag: w.mag,
      lookDX: -dyaw,
      lookDY: -dpitch,
      alive: a.alive && !a.inTank
    })
    const scoped = !!w.scope && s.adsT > 0.85
    this.viewmodel.scoped = scoped
    return { fov: this.baseFov + (w.adsFov - this.baseFov) * s.adsT, scoped }
  }

  // what the followed soldier did, from the server's messages
  onShot (id) {
    if (!this.firstPerson || id !== this.targetId || !this.vm) return
    this.vm.shotAt = performance.now()
    this.viewmodel.fire()
  }

  onStab (id) { if (this.vm && id === this.targetId) this.vm.stabAt = performance.now() }
  onNade (id) { if (this.vm && id === this.targetId) this.vm.nadeAt = performance.now() }
}
