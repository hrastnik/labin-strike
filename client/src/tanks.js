// Tanks: Quaternius's CC0 low-poly tanks (Allies: the Sherman-like one, Axis: the Panzer-like one), posed from
// snapshots or, for the one we drive, from our own TankBody. Each has its collider in our physics world so we bump
// into it, and the turret, gun and track animations follow what it is doing.
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { PLAYER } from '@shared/constants.js'
import { TANK, TankBody, tankSide, tankTeam, rayVsTank, tankDistance, underHull, wrapAngle } from '@shared/tanks.js'
import { HISTORY } from './killcam.js'

const SCALE = 0.36 // shared/tanks.js is measured at this scale
const MODELS = { allies: '/assets/tanks/sherman.glb', axis: '/assets/tanks/panzer.glb' }
const WRECK = new THREE.Color(0.16, 0.15, 0.14)
const SMOKE_EVERY = 0.22 // seconds between puffs from a wreck

export async function loadTanks (scene, RAPIER, world) {
  const loader = new GLTFLoader()
  const gltfs = {}
  await Promise.all(Object.entries(MODELS).map(async ([team, url]) => { gltfs[team] = await loader.loadAsync(url) }))
  return new Tanks(gltfs, scene, RAPIER, world)
}

// one model per side, reused match after match
class TankView {
  constructor (gltf) {
    this.root = new THREE.Group()
    const model = gltf.scene
    model.rotation.y = -Math.PI / 2 // the model's front is -X
    model.scale.setScalar(SCALE)
    this.root.add(model)
    this.root.updateMatrixWorld(true)
    // turret and gun are loose nodes; hang them from pivots that turn about the model's own axes
    const turret = model.getObjectByName('Tank_Turret')
    const gun = model.getObjectByName('Tank_Gun')
    const base = turret.parent
    this.turret = new THREE.Group()
    this.turret.position.copy(turret.position)
    base.add(this.turret)
    this.gun = new THREE.Group()
    this.gun.position.copy(gun.position).sub(turret.position)
    this.turret.add(this.gun)
    this.root.updateMatrixWorld(true)
    this.turret.attach(turret)
    this.gun.attach(gun)
    this.gunRest = this.gun.position.x
    this.materials = []
    model.traverse((o) => {
      if (!o.isMesh) return
      o.castShadow = true
      o.receiveShadow = true
      if (o.isSkinnedMesh) o.frustumCulled = false // its bounds are the bind pose
      if (!this.materials.some((m) => m.mat === o.material)) this.materials.push({ mat: o.material, color: o.material.color.clone() })
    })
    this.mixer = new THREE.AnimationMixer(model)
    const clip = (k) => this.mixer.clipAction(gltf.animations.find((a) => a.name.endsWith(k)))
    this.tracks = { fwd: clip('Tank_Forward'), back: clip('Tank_Backwards'), left: clip('Tank_TurningLeft'), right: clip('Tank_TurningRight') }
    this.rolling = null
    this.wrecked = false
  }

  wreck (on) {
    if (on === this.wrecked) return
    this.wrecked = on
    for (const m of this.materials) {
      m.mat.color.copy(m.color)
      if (on) m.mat.color.multiply(WRECK)
    }
  }

  // speed: m/s along the hull, turn: rad/s
  pose (s, dt, speed, turn) {
    this.root.position.set(s.pos[0], s.pos[1], s.pos[2])
    this.root.rotation.y = s.yaw
    this.turret.rotation.y = wrapAngle(s.turret - s.yaw)
    this.gun.rotation.z = -s.gun
    const kick = Math.max(0, 1 - (performance.now() - s.firedAt) / 250)
    this.gun.position.x = this.gunRest + kick * kick * 1.5 // recoil: model units, +X is back along the barrel
    let roll = null; let rate = 0
    if (!this.wrecked) {
      if (Math.abs(speed) > 0.3) { roll = speed > 0 ? 'fwd' : 'back'; rate = Math.abs(speed) / 3 }
      else if (Math.abs(turn) > 0.1) { roll = turn > 0 ? 'left' : 'right'; rate = Math.abs(turn) * 1.5 }
    }
    if (roll !== this.rolling) {
      if (this.rolling) this.tracks[this.rolling].stop()
      if (roll) this.tracks[roll].play()
      this.rolling = roll
    }
    if (roll) this.mixer.update(dt * rate)
  }
}

export class Tanks {
  constructor (gltfs, scene, RAPIER, world) {
    this.scene = scene
    this.R = RAPIER
    this.world = world
    this.views = { allies: new TankView(gltfs.allies), axis: new TankView(gltfs.axis) }
    this.map = new Map() // id -> state
    this.mine = null // the state of the tank we drive
  }

  get (id) { return this.map.get(id) ?? null }

  // rows: [id, x, y, z, yaw, turret, gun, hp, driver, flags, age] (see server/tanks.js)
  onSnapshot (t, rows = []) {
    const seen = new Set()
    for (const e of rows) {
      const team = tankTeam(e[0])
      if (!team) continue
      seen.add(e[0])
      let s = this.map.get(e[0])
      if (!s) {
        s = {
          id: e[0], team, buffer: [], pos: [e[1], e[2], e[3]], yaw: e[4], turret: e[5], gun: e[6], hp: e[7], driver: 0,
          destroyed: false, firedAt: -1e9, speed: 0, turn: 0, smokeT: 0, view: this.views[team], body: new TankBody(this.R, this.world, team)
        }
        s.body.setPose(e[1], e[2], e[3], e[4])
        this.scene.add(s.view.root)
        this.map.set(e[0], s)
      }
      const at = t - (e[10] || 0)
      const b = s.buffer
      if (!b.length || at > b[b.length - 1].t) b.push({ t: at, x: e[1], y: e[2], z: e[3], yaw: e[4], turret: e[5], gun: e[6], driver: e[8], destroyed: !!(e[9] & 1) })
      while (b.length > 2 && b[0].t < at - HISTORY) b.shift() // the kill-cam replays the last few seconds
      s.hp = e[7]
      s.driver = e[8]
      s.destroyed = !!(e[9] & 1)
      s.view.wreck(s.destroyed)
    }
    for (const [id, s] of this.map) if (!seen.has(id)) this.remove(id, s)
  }

  remove (id, s) {
    if (s === this.mine) this.mine = null
    s.body.dispose()
    s.view.wreck(false)
    this.scene.remove(s.view.root)
    this.map.delete(id)
  }

  clear () { for (const [id, s] of this.map) this.remove(id, s) }

  // the tank we drive is posed by our own TankBody; the others are interpolated at renderT (server ms).
  // smoke(pos): called for each puff a wreck gives off; past: renderT is the kill-cam's, so who drives and whether it
  // is a wreck come from then too (the next snapshot puts them back)
  update (dt, renderT, smoke, past = false) {
    for (const s of this.map.values()) {
      const yaw0 = s.yaw; const x0 = s.pos[0]; const z0 = s.pos[2]
      if (s === this.mine) {
        const p = s.body.pos
        s.pos = [p.x, p.y, p.z]
        s.yaw = s.body.yaw
      } else if (sample(s, renderT)) {
        s.body.setPose(s.pos[0], s.pos[1], s.pos[2], s.yaw)
        if (past) {
          s.driver = s.then.driver
          s.destroyed = s.then.destroyed
          s.view.wreck(s.destroyed)
        }
      }
      if (dt > 0) {
        const along = ((s.pos[0] - x0) * -Math.sin(s.yaw) + (s.pos[2] - z0) * -Math.cos(s.yaw)) / dt
        s.speed += (along - s.speed) * Math.min(1, dt * 8)
        s.turn += (wrapAngle(s.yaw - yaw0) / dt - s.turn) * Math.min(1, dt * 8)
      }
      s.view.pose(s, dt, s.speed, s.turn)
      if (s.destroyed && (s.smokeT -= dt) <= 0) {
        s.smokeT = SMOKE_EVERY
        smoke?.(new THREE.Vector3(s.pos[0] + (Math.random() - 0.5) * 1.5, s.pos[1] + tankSide(s.team).hullH + 0.3, s.pos[2] + (Math.random() - 0.5) * 2))
      }
    }
  }

  // nearest tank hit along a ray: { t, tank } or null (skip: a tank to look past, e.g. our own)
  ray (o, d, maxT, skip = null) {
    let best = null
    for (const s of this.map.values()) {
      if (s === skip) continue
      const h = rayVsTank(o, d, best?.t ?? maxT, s)
      if (h != null) best = { t: h, tank: s }
    }
    return best
  }

  // pos ({ x, y, z }) moved out sideways from under a hull it is in, or null
  pushOut (pos) {
    for (const s of this.map.values()) {
      if (s === this.mine || !underHull(s, pos.x, pos.y + 0.3, pos.z)) continue
      const c = Math.cos(s.yaw); const sn = Math.sin(s.yaw)
      const dx = pos.x - s.pos[0]; const dz = pos.z - s.pos[2]
      let lx = dx * c - dz * sn; let lz = dx * sn + dz * c
      const pad = PLAYER.radius + 0.1
      if (TANK.half[0] - Math.abs(lx) < TANK.half[1] - Math.abs(lz)) lx = Math.sign(lx || 1) * (TANK.half[0] + pad)
      else lz = Math.sign(lz || 1) * (TANK.half[1] + pad)
      return [s.pos[0] + lx * c + lz * sn, pos.y, s.pos[2] - lx * sn + lz * c]
    }
    return null
  }

  // our own side's tank close enough to climb into (the server's test, a little stricter), if it is free
  boardable (team, pos) {
    for (const s of this.map.values()) {
      if (s.team !== team || s.destroyed || s.driver) continue
      if (tankDistance([pos.x, pos.y + 1, pos.z], s) <= TANK.reach + PLAYER.radius - 0.1) return s
    }
    return null
  }
}

function sample (s, renderT) {
  const b = s.buffer
  if (!b.length) return false
  let a = b[0]; let c = b[0]
  if (renderT >= b[b.length - 1].t) a = c = b[b.length - 1]
  else {
    for (let i = b.length - 1; i >= 0; i--) {
      if (b[i].t <= renderT) { a = b[i]; c = b[i + 1] || b[i]; break }
    }
  }
  const k = c.t > a.t ? Math.max(0, Math.min(1, (renderT - a.t) / (c.t - a.t))) : 0
  s.then = k < 0.5 ? a : c
  s.pos = [a.x + (c.x - a.x) * k, a.y + (c.y - a.y) * k, a.z + (c.z - a.z) * k]
  s.yaw = a.yaw + wrapAngle(c.yaw - a.yaw) * k
  s.turret = a.turret + wrapAngle(c.turret - a.turret) * k
  s.gun = a.gun + (c.gun - a.gun) * k
  return true
}
