// The map's cats: Blender-modelled (tools/blender/cats) and animated here in code. The server moves them; each
// part of the model has its own pivot, so walking, galloping, tail swishing and lying on their side are just
// rotations on top of the rest pose.
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { HISTORY } from './killcam.js'

// keep in step with server/cats.js
const STATE = { idle: 0, walk: 1, run: 2, lie: 3 }
const COATS = ['main', 'ginger', 'tuxedo']
const SCALE = 1.1
const LIE_ROLL = 1.45 // rolled onto its side, belly to the room
const TAU = Math.PI * 2
const wrap = (a) => { a = (a + Math.PI) % TAU; return (a < 0 ? a + TAU : a) - Math.PI }
const damp = (cur, target, rate, dt) => cur + (target - cur) * (1 - Math.exp(-rate * dt))

export async function loadCats (url, scene, audio) {
  const gltf = await new GLTFLoader().loadAsync(url)
  return new Cats(gltf, scene, audio)
}

export class Cats {
  constructor (gltf, scene, audio) {
    this.scene = scene
    this.audio = audio
    this.templates = {}
    for (const coat of COATS) {
      const t = gltf.scene.getObjectByName(`cat_${coat}`)
      if (!t) continue
      t.position.set(0, 0, 0)
      t.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true } })
      this.templates[coat] = t
    }
    this.map = new Map() // cat id -> Cat
  }

  // snapshot rows: [id, coat, x, y, z, yaw, state]
  onSnapshot (t, rows = []) {
    const seen = new Set()
    for (const e of rows) {
      seen.add(e[0])
      let c = this.map.get(e[0])
      if (!c) {
        const tpl = this.templates[COATS[e[1]]] || Object.values(this.templates)[0]
        if (!tpl) continue
        c = new Cat(tpl, this.audio)
        this.scene.add(c.root)
        this.map.set(e[0], c)
      }
      c.push(t, e)
    }
    for (const [id, c] of this.map) if (!seen.has(id)) { this.scene.remove(c.root); this.map.delete(id) }
  }

  update (dt, renderT, listener) {
    for (const c of this.map.values()) c.update(dt, renderT, listener)
  }

  clear () {
    for (const c of this.map.values()) this.scene.remove(c.root)
    this.map.clear()
  }
}

class Cat {
  constructor (tpl, audio) {
    this.audio = audio
    this.root = new THREE.Group() // position + heading
    this.model = tpl.clone() // rolls over when lying down
    this.model.scale.setScalar(SCALE)
    this.root.add(this.model)
    const part = (n) => this.model.getObjectByProperty('name', `${tpl.name.slice(4)}_${n}`)
    this.body = part('body')
    this.head = part('head')
    this.legs = ['fl', 'fr', 'bl', 'br'].map((s) => part(`leg_${s}`))
    this.tail = [0, 1, 2, 3].map((i) => part(`tail${i}`))
    this.rest = new Map()
    for (const o of [this.body, this.head, ...this.legs, ...this.tail]) this.rest.set(o, { p: o.position.clone(), r: o.rotation.clone() })
    this.buffer = []
    this.pos = new THREE.Vector3()
    this.yaw = 0
    this.state = STATE.idle
    this.speed = 0
    this.phase = Math.random() * TAU
    this.lie = 0 // 0 standing .. 1 on its side
    this.look = 0; this.lookTarget = 0; this.nextLook = 0
    this.t = Math.random() * 100
    this.nextMeow = performance.now() + 4000 + Math.random() * 15000
    this.first = true
  }

  push (t, e) {
    const b = this.buffer
    const last = b[b.length - 1]
    if (last && t <= last.t) return
    b.push({ t, x: e[2], y: e[3], z: e[4], yaw: e[5], state: e[6] })
    while (b.length > 2 && b[0].t < t - HISTORY) b.shift() // the kill-cam replays the last few seconds
  }

  sample (renderT) {
    const b = this.buffer
    if (!b.length) return false
    let a = b[b.length - 1]; let c = a
    for (let i = b.length - 2; i >= 0; i--) {
      if (b[i].t <= renderT) { a = b[i]; c = b[i + 1]; break }
      a = c = b[i]
    }
    const k = c.t > a.t ? Math.max(0, Math.min(1, (renderT - a.t) / (c.t - a.t))) : 0
    this.pos.set(a.x + (c.x - a.x) * k, a.y + (c.y - a.y) * k, a.z + (c.z - a.z) * k)
    this.yaw = a.yaw + wrap(c.yaw - a.yaw) * k
    const state = k < 0.5 ? a.state : c.state
    if (state === STATE.run && this.state !== STATE.run && !this.first) this.audio?.hiss(this.pos)
    this.state = state
    return true
  }

  update (dt, renderT, listener) {
    const prev = this.pos.clone()
    if (!this.sample(renderT)) return
    const moved = this.first ? 0 : Math.hypot(this.pos.x - prev.x, this.pos.z - prev.z)
    this.first = false
    this.speed = damp(this.speed, dt > 0 ? Math.min(8, moved / dt) : 0, 10, dt)
    this.root.position.copy(this.pos)
    this.root.rotation.y = this.yaw
    this.t += dt
    this.animate(dt)
    // the odd meow, from a cat that isn't busy running for its life
    const now = performance.now()
    if (now > this.nextMeow) {
      this.nextMeow = now + 8000 + Math.random() * 20000
      if (this.state !== STATE.run && listener && listener.distanceTo(this.pos) < 25) this.audio?.meow(this.pos)
    }
  }

  animate (dt) {
    const run = this.state === STATE.run
    const lying = this.state === STATE.lie
    this.lie = damp(this.lie, lying ? 1 : 0, lying ? 2.5 : 8, dt)
    // strides of ~0.3 m walking, ~0.75 m galloping
    const stride = run ? 0.75 : 0.3
    this.phase += (this.speed / stride) * TAU * dt * 0.5
    const gait = Math.min(1, this.speed / 0.4)
    const ph = this.phase
    const R = (o) => this.rest.get(o)

    // lying on its side, the model rolls about its long axis and settles on the ground
    const roll = LIE_ROLL * this.lie
    this.model.rotation.z = roll
    this.model.position.y = 0.1 * Math.sin(roll) * SCALE
    this.model.position.x = 0.19 * Math.sin(roll) * SCALE // rolled about the ground under it: keep the body in place

    // body: a bounce in the gallop, a slow breath at rest
    const B = R(this.body)
    const bounce = run ? Math.abs(Math.sin(ph)) * 0.025 * gait : Math.abs(Math.sin(ph)) * 0.006 * gait
    this.body.position.y = B.p.y + bounce + Math.sin(this.t * 2.2) * 0.002
    this.body.rotation.x = B.r.x + (run ? Math.sin(ph) * 0.12 * gait : 0)

    // legs: diagonal pairs walking, front pair / hind pair galloping; curled up when lying down
    const offs = run ? [0, 0.3, Math.PI, Math.PI + 0.3] : [0, Math.PI, Math.PI, 0]
    const amp = run ? 0.85 : 0.42
    const curl = [1.3, 0.9, 0.55, 0.3]
    this.legs.forEach((leg, i) => {
      const r = R(leg)
      const swing = Math.sin(ph + offs[i]) * amp * gait
      leg.rotation.x = r.r.x + swing * (1 - this.lie) + curl[i] * this.lie
      leg.rotation.z = r.r.z + (i % 2 ? -1 : 1) * 0.25 * this.lie
      // lift the foot on the forward swing
      leg.position.y = r.p.y + Math.max(0, Math.cos(ph + offs[i])) * 0.02 * gait * (1 - this.lie)
    })

    // head: looks around when idle, bobs walking, tips back towards you lying down
    if (this.t > this.nextLook) {
      this.nextLook = this.t + 1 + Math.random() * 3
      this.lookTarget = this.state === STATE.idle ? (Math.random() - 0.5) * 1.6 : (Math.random() - 0.5) * 0.3
    }
    this.look = damp(this.look, run ? 0 : this.lookTarget, 4, dt)
    const H = R(this.head)
    this.head.rotation.set(
      H.r.x + Math.sin(ph * 2) * 0.05 * gait - (run ? 0.25 : 0) + 0.2 * this.lie,
      H.r.y + this.look * (1 - this.lie),
      H.r.z - 0.55 * this.lie
    )

    // tail: up and swaying when strolling, streaming out behind when running, flicking on the ground lying down
    const sway = Math.sin(this.t * (run ? 9 : 1.6))
    this.tail.forEach((seg, i) => {
      const r = R(seg)
      const flat = run ? [0.55, -0.25, -0.25, -0.2][i] : 0
      const down = [0.75, -0.2, -0.2, -0.2][i] * this.lie
      seg.rotation.x = r.r.x + flat + down
      seg.rotation.z = r.r.z + sway * (run ? 0.12 : 0.18 + i * 0.06) * (1 - this.lie * 0.5)
      seg.rotation.y = r.r.y + Math.sin(this.t * 3 + i) * 0.15 * this.lie
    })
  }
}
