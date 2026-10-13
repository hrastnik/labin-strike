// Motorcycles: the Allies' Harley-Davidson WLA and the Axis' BMW R35 (modelled in Blender, tools/blender/bikes), posed
// from snapshots or, for the one we ride, from our own BikeBody. Each carries a seated soldier of its side while
// ridden, leans with the rider's hitbox, and has its collider in our physics world so we bump into it.
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'
import { PLAYER } from '@shared/constants.js'
import { BIKE, BikeBody, bikeTeam, rayVsBike, bikeDistance, bikeBox } from '@shared/bikes.js'
import { wrapAngle } from '@shared/tanks.js'
import { Avatar } from './avatars.js'

const MODELS = { allies: 'wla', axis: 'r35' } // node name prefixes in bikes.glb
const WRECK = new THREE.Color(0.16, 0.15, 0.14)
const WRECK_ROLL = 1.3 // a wreck lies on its left side
const SMOKE_EVERY = 0.3 // seconds between puffs from a wreck
const WHEEL_R = 0.33 // both bikes run 19 inch wheels
// the roll that carries a rider's head as far sideways as a full lean shifts their hitbox
const MAX_ROLL = Math.asin(PLAYER.leanDist / 1.6)
const _p = new THREE.Vector3()

export async function loadBikes (url, scene, RAPIER, world) {
  const loader = new GLTFLoader()
  loader.setMeshoptDecoder(MeshoptDecoder)
  const gltf = await loader.loadAsync(url)
  return new Bikes(gltf, scene, RAPIER, world)
}

// one model per side, reused match after match
class BikeView {
  constructor (gltf, team) {
    const k = MODELS[team]
    const model = gltf.scene.getObjectByName(`${k}_body`)
    const part = (name) => model.getObjectByName(`${k}_${name}`)
    this.root = new THREE.Group()
    this.tilt = new THREE.Group() // leans into the turns, or lies on its side as a wreck
    this.root.add(this.tilt)
    this.tilt.add(model)
    // the fork's rest rotation is the rake about x: steering turns it about its own y after that
    this.fork = part('fork')
    this.front = part('wheel_f')
    this.rear = part('wheel_r')
    this.lamp = part('lamp')
    this.grips = [part('grip_r'), part('grip_l')]
    this.materials = []
    model.traverse((o) => {
      if (!o.isMesh) return
      o.castShadow = true
      o.receiveShadow = true
      if (!this.materials.some((m) => m.mat === o.material)) this.materials.push({ mat: o.material, color: o.material.color.clone() })
    })

    this.rider = new Avatar(0, team, '', false)
    this.root.updateMatrixWorld(true)
    const at = (name) => this.tilt.worldToLocal(part(name).getWorldPosition(new THREE.Vector3()))
    this.rider.sit({
      hips: at('seat').add(new THREE.Vector3(0, 0.08, 0.02)),
      footR: at('foot_r'),
      footL: at('foot_l'),
      grips: this.grips.map((g) => this.tilt.worldToLocal(g.getWorldPosition(new THREE.Vector3())))
    })
    this.rider.root.position.set(0, 0, 0)
    this.rider.root.visible = false
    this.tilt.add(this.rider.root)

    // how high a wreck's lowest point would sink below the ground, lying on its side
    this.tilt.rotation.z = WRECK_ROLL
    this.root.updateMatrixWorld(true)
    this.wreckLift = -new THREE.Box3().setFromObject(model, true).min.y
    this.tilt.rotation.z = 0
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
      this.tilt.rotation.z = WRECK_ROLL
      this.tilt.position.y = this.wreckLift
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
    if (s.driver) {
      // hands follow the bars as they steer
      this.root.updateMatrixWorld(true)
      for (let i = 0; i < 2; i++) this.rider.reach(i, this.grips[i].getWorldPosition(_p))
    }
  }
}

export class Bikes {
  constructor (gltf, scene, RAPIER, world) {
    this.scene = scene
    this.R = RAPIER
    this.world = world
    this.views = { allies: new BikeView(gltf, 'allies'), axis: new BikeView(gltf, 'axis') }
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
