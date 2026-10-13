// Motorcycles: procedural low-poly WWII bikes (Allies: a Harley-Davidson WLA, Axis: a BMW R35), posed from snapshots
// or, for the one we ride, from our own BikeBody. Each carries a seated soldier of its side while ridden, leans with
// the rider's hitbox, and has its collider in our physics world so we bump into it.
import * as THREE from 'three'
import { PLAYER } from '@shared/constants.js'
import { BIKE, BikeBody, bikeTeam, rayVsBike, bikeDistance, bikeBox } from '@shared/bikes.js'
import { wrapAngle } from '@shared/tanks.js'
import { Avatar } from './avatars.js'

const WRECK = new THREE.Color(0.16, 0.15, 0.14)
const SMOKE_EVERY = 0.3 // seconds between puffs from a wreck
const WHEEL_R = 0.35
const AXLE = 0.73 // front and rear axles either side of the middle
const HEAD = [0.97, -0.5] // steering head [y, z]
const RAKE = Math.atan2(HEAD[1] + AXLE, HEAD[0] - WHEEL_R) // the steering axis leans back from the front axle to the head
// the roll that carries a rider's head as far sideways as a full lean shifts their hitbox
const MAX_ROLL = Math.asin(PLAYER.leanDist / 1.6)
const PAINT = { allies: '#4d5230', axis: '#565b55' }

function mesh (geo, mat, x, y, z, parent) {
  const m = new THREE.Mesh(geo, mat)
  m.position.set(x, y, z)
  m.castShadow = true
  m.receiveShadow = true
  parent.add(m)
  return m
}

const boxGeo = (w, h, d) => new THREE.BoxGeometry(w, h, d)
// a cylinder lying along x (axles, bars) or z (pipes, lamps)
const rodX = (r, len, seg = 8) => new THREE.CylinderGeometry(r, r, len, seg).rotateZ(Math.PI / 2)
const rodZ = (r, len, seg = 8) => new THREE.CylinderGeometry(r, r, len, seg).rotateX(Math.PI / 2)
// a strut from a to b ([y, z] in the bike's middle plane), x across
function strut (a, b, r, mat, x, parent) {
  const len = Math.hypot(b[0] - a[0], b[1] - a[1])
  const m = mesh(new THREE.CylinderGeometry(r, r, len, 6), mat, x, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, parent)
  m.rotation.x = Math.atan2(b[1] - a[1], b[0] - a[0])
  return m
}

function starShape (r) {
  const s = new THREE.Shape()
  for (let i = 0; i < 10; i++) {
    const a = (i / 10) * Math.PI * 2
    const k = i % 2 ? r * 0.4 : r
    s[i ? 'lineTo' : 'moveTo'](Math.sin(a) * k, Math.cos(a) * k)
  }
  return s
}

// one model per side, reused match after match
class BikeView {
  constructor (team) {
    this.root = new THREE.Group()
    this.tilt = new THREE.Group() // leans into the turns, or lies on its side as a wreck
    this.root.add(this.tilt)
    const std = (color, roughness = 0.75, metalness = 0) => new THREE.MeshStandardMaterial({ color, roughness, metalness, flatShading: true })
    const paint = std(PAINT[team], 0.7)
    paint.side = THREE.DoubleSide // the open fenders
    const metal = std('#2c2c2b', 0.5, 0.5)
    const rubber = std('#141414', 0.95)
    const leather = std(team === 'allies' ? '#5a3d24' : '#2a2420', 0.9)
    const chrome = std('#8d8d88', 0.35, 0.8)
    const lens = new THREE.MeshStandardMaterial({ color: '#e9e2c0', emissive: '#4a4530', roughness: 0.2 })
    this.materials = [paint, metal, rubber, leather, chrome, lens].map((mat) => ({ mat, color: mat.color.clone() }))
    const t = this.tilt

    const wheel = (z, parent) => {
      const w = new THREE.Group()
      w.position.set(0, WHEEL_R, z)
      parent.add(w)
      mesh(new THREE.TorusGeometry(WHEEL_R - 0.06, 0.06, 6, 16).rotateY(Math.PI / 2), rubber, 0, 0, 0, w)
      mesh(rodX(0.07, 0.13), metal, 0, 0, 0, w)
      for (let i = 0; i < 3; i++) mesh(boxGeo(0.02, (WHEEL_R - 0.08) * 2, 0.02), metal, 0, 0, 0, w).rotation.x = (i / 3) * Math.PI
      return w
    }
    // an arc over the wheel at z, from angle `from` (0 straight back, pi/2 the top) through len
    const fender = (z, parent, from, len) => {
      const g = new THREE.CylinderGeometry(WHEEL_R + 0.05, WHEEL_R + 0.05, 0.15, 12, 1, true, from, len).rotateZ(Math.PI / 2)
      mesh(g, paint, 0, WHEEL_R, z, parent)
    }

    this.rear = wheel(AXLE, t)
    fender(AXLE, t, -0.3, 2.2)
    // the fork steers about the raked axis through the head; parts inside it are placed in the bike's own frame
    const head = new THREE.Group()
    head.position.set(0, HEAD[0], HEAD[1])
    head.rotation.x = RAKE
    t.add(head)
    this.fork = new THREE.Group()
    head.add(this.fork)
    const unrake = new THREE.Group()
    unrake.rotation.x = -RAKE
    this.fork.add(unrake)
    const f = new THREE.Group()
    f.position.set(0, -HEAD[0], -HEAD[1])
    unrake.add(f)
    this.front = wheel(-AXLE, f)
    fender(-AXLE, f, 1.2, 2.1)
    for (const x of [-0.09, 0.09]) strut([WHEEL_R, -AXLE], [HEAD[0] + 0.02, HEAD[1] - 0.03], 0.025, chrome, x, f)
    mesh(rodX(0.018, 0.56), metal, 0, 1.02, -0.43, f) // bars
    for (const x of [-0.26, 0.26]) mesh(rodX(0.03, 0.1), rubber, x, 1.02, -0.43, f) // grips
    mesh(rodZ(0.095, 0.14, 10), metal, 0, 0.9, -0.62, f) // headlamp
    this.lamp = mesh(new THREE.CircleGeometry(0.08, 10), lens, 0, 0.9, -0.691, f)
    this.lamp.rotation.y = Math.PI

    // frame, engine and seat
    strut([0.5, 0.05], HEAD, 0.03, metal, 0, t) // down tube
    strut([0.92, 0.25], HEAD, 0.03, metal, 0, t) // top tube
    for (const x of [-0.08, 0.08]) strut([WHEEL_R, AXLE], [0.42, 0.05], 0.022, metal, x, t) // chain stays
    for (const x of [-0.08, 0.08]) strut([WHEEL_R, AXLE], [0.82, 0.35], 0.02, metal, x, t) // seat stays
    mesh(boxGeo(0.3, 0.2, 0.5), paint, 0, 0.9, -0.2, t) // fuel tank
    mesh(boxGeo(0.28, 0.08, 0.36), leather, 0, 0.8, 0.16, t) // saddle
    mesh(boxGeo(0.24, 0.24, 0.36), metal, 0, 0.42, 0, t) // crankcase
    if (team === 'axis') {
      // the BMW's flat twin, its cylinders standing out either side
      mesh(rodX(0.075, 0.62, 8), metal, 0, 0.5, -0.12, t)
      for (const x of [-0.3, 0.3]) mesh(boxGeo(0.06, 0.18, 0.18), metal, x, 0.5, -0.12, t)
      for (const x of [-0.17, 0.17]) mesh(rodZ(0.035, 0.85), chrome, x, 0.28, 0.32, t) // exhausts
    } else {
      // the Harley's V-twin and its single pipe; a white star on the tank
      for (const [a, z] of [[0.45, -0.13], [-0.45, 0.13]]) mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.3, 8), metal, 0, 0.66, z, t).rotation.x = a
      mesh(rodZ(0.04, 1), chrome, 0.16, 0.3, 0.3, t)
      const star = new THREE.MeshStandardMaterial({ color: '#d8d6c8', roughness: 0.8, side: THREE.DoubleSide })
      this.materials.push({ mat: star, color: star.color.clone() })
      for (const x of [-0.152, 0.152]) mesh(new THREE.ShapeGeometry(starShape(0.07)), star, x, 0.9, -0.2, t).rotation.y = Math.PI / 2
      mesh(boxGeo(0.12, 0.26, 0.32), leather, -0.22, 0.6, 0.58, t) // saddlebags
      mesh(boxGeo(0.12, 0.26, 0.32), leather, 0.22, 0.6, 0.58, t)
    }
    for (const x of [-0.24, 0.24]) mesh(boxGeo(0.12, 0.03, 0.06), metal, x, 0.3, -0.16, t) // footrests

    this.rider = new Avatar(0, team, '', false)
    this.rider.sit()
    this.rider.root.position.set(0, 0, 0)
    this.rider.root.visible = false
    t.add(this.rider.root)
    this.wrecked = false
  }

  wreck (on) {
    if (on === this.wrecked) return
    this.wrecked = on
    for (const m of this.materials) {
      m.mat.color.copy(m.color)
      if (on) m.mat.color.multiply(WRECK)
    }
    this.lamp.visible = !on
  }

  // s: { pos, yaw, lean, driver }, speed: m/s along the bike, turn: rad/s
  pose (s, dt, speed, turn) {
    this.root.position.set(s.pos[0], s.pos[1], s.pos[2])
    this.root.rotation.y = s.yaw
    if (this.wrecked) {
      this.tilt.rotation.z = 1.3
      this.tilt.position.y = 0.12
      this.fork.rotation.y = 0.5
      this.rider.root.visible = false
      return
    }
    this.tilt.rotation.z = -s.lean * MAX_ROLL
    this.tilt.position.y = 0
    const spin = speed * dt / WHEEL_R
    this.rear.rotation.x -= spin
    this.front.rotation.x -= spin
    const lock = Math.max(-0.45, Math.min(0.45, turn / Math.max(1.5, Math.abs(speed)) * 1.6))
    this.fork.rotation.y += (lock - this.fork.rotation.y) * Math.min(1, dt * 10)
    this.rider.root.visible = !!s.driver
  }
}

export class Bikes {
  constructor (scene, RAPIER, world) {
    this.scene = scene
    this.R = RAPIER
    this.world = world
    this.views = { allies: new BikeView('allies'), axis: new BikeView('axis') }
    this.map = new Map() // id -> state
    this.mine = null // the state of the bike we ride
  }

  get (id) { return this.map.get(id) ?? null }

  // rows: [id, x, y, z, yaw, lean, hp, driver, flags, age] (see server/bikes.js)
  onSnapshot (t, rows = []) {
    const seen = new Set()
    for (const e of rows) {
      const team = bikeTeam(e[0])
      if (!team) continue
      seen.add(e[0])
      let s = this.map.get(e[0])
      if (!s) {
        s = {
          id: e[0], team, buffer: [], pos: [e[1], e[2], e[3]], yaw: e[4], lean: e[5], hp: e[6], driver: 0, destroyed: false,
          speed: 0, turn: 0, smokeT: 0, view: this.views[team], body: new BikeBody(this.R, this.world)
        }
        s.body.setPose(e[1], e[2], e[3], e[4])
        this.scene.add(s.view.root)
        this.map.set(e[0], s)
      }
      const destroyed = !!(e[8] & 1)
      // a new bike at the base: no gliding over from where the wreck lay
      if (s.destroyed && !destroyed) s.buffer.length = 0
      const at = t - (e[9] || 0)
      const b = s.buffer
      if (!b.length || at > b[b.length - 1].t) b.push({ t: at, x: e[1], y: e[2], z: e[3], yaw: e[4], lean: e[5] })
      if (b.length > 30) b.splice(0, b.length - 30)
      s.hp = e[6]
      s.driver = e[7]
      s.destroyed = destroyed
      s.view.wreck(destroyed)
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

  // the bike we ride is posed by our own BikeBody; the others are interpolated at renderT (server ms).
  // smoke(pos): called for each puff a wreck gives off
  update (dt, renderT, smoke) {
    for (const s of this.map.values()) {
      const yaw0 = s.yaw; const x0 = s.pos[0]; const z0 = s.pos[2]
      if (s === this.mine) {
        const p = s.body.pos
        s.pos = [p.x, p.y, p.z]
        s.yaw = s.body.yaw
        s.lean = s.body.lean
      } else if (sample(s, renderT)) {
        s.body.setPose(s.pos[0], s.pos[1], s.pos[2], s.yaw)
      }
      if (dt > 0) {
        const along = ((s.pos[0] - x0) * -Math.sin(s.yaw) + (s.pos[2] - z0) * -Math.cos(s.yaw)) / dt
        s.speed += (along - s.speed) * Math.min(1, dt * 8)
        s.turn += (wrapAngle(s.yaw - yaw0) / dt - s.turn) * Math.min(1, dt * 8)
      }
      s.view.pose(s, dt, s.speed, s.turn)
      if (s.destroyed && (s.smokeT -= dt) <= 0) {
        s.smokeT = SMOKE_EVERY
        smoke?.(new THREE.Vector3(s.pos[0] + (Math.random() - 0.5) * 0.8, s.pos[1] + 0.4, s.pos[2] + (Math.random() - 0.5) * 1.2))
      }
    }
  }

  // nearest bike hit along a ray: { t, bike } or null (skip: a bike to look past, e.g. our own)
  ray (o, d, maxT, skip = null) {
    let best = null
    for (const s of this.map.values()) {
      if (s === skip) continue
      const h = rayVsBike(o, d, best?.t ?? maxT, s)
      if (h != null) best = { t: h, bike: s }
    }
    return best
  }

  // pos ({ x, y, z }) moved out sideways from a bike that rode into it, or null
  pushOut (pos) {
    for (const s of this.map.values()) {
      if (s === this.mine) continue
      const box = bikeBox(s)
      if (bikeDistance([pos.x, pos.y + 0.3, pos.z], s) > 0) continue
      const c = Math.cos(box.yaw); const sn = Math.sin(box.yaw)
      const dx = pos.x - s.pos[0]; const dz = pos.z - s.pos[2]
      let lx = dx * c - dz * sn; let lz = dx * sn + dz * c
      const pad = PLAYER.radius + 0.1
      if (BIKE.half[0] - Math.abs(lx) < BIKE.half[2] - Math.abs(lz)) lx = Math.sign(lx || 1) * (BIKE.half[0] + pad)
      else lz = Math.sign(lz || 1) * (BIKE.half[2] + pad)
      return [s.pos[0] + lx * c + lz * sn, pos.y, s.pos[2] - lx * sn + lz * c]
    }
    return null
  }

  // our own side's bike close enough to get on (the server's test, a little stricter), if it is free
  boardable (team, pos) {
    for (const s of this.map.values()) {
      if (s.team !== team || s.destroyed || s.driver) continue
      if (bikeDistance([pos.x, pos.y + 1, pos.z], s) <= BIKE.reach + PLAYER.radius - 0.1) return s
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
  s.pos = [a.x + (c.x - a.x) * k, a.y + (c.y - a.y) * k, a.z + (c.z - a.z) * k]
  s.yaw = a.yaw + wrapAngle(c.yaw - a.yaw) * k
  s.lean = a.lean + (c.lean - a.lean) * k
  return true
}
