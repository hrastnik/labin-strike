// Remote players: Blender-modelled skinned soldiers (procedural box soldiers without soldiers.glb), snapshot
// interpolation and simple procedural animation.
import * as THREE from 'three'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'
import { PLAYER, TEAMS } from '@shared/constants.js'
import { WEAPONS, WEAPON_LIST, KNIFE } from '@shared/weapons.js'
import { buildGun } from './gunmodels.js'
import { buildSoldier, aimArm } from './soldiermodels.js'

const STYLE = {
  allies: { uniform: '#6a6f3e', trousers: '#5f6238', webbing: '#b5a477', helmet: '#4f5631', boots: '#4a3524', marker: '#9fc16a' },
  axis: { uniform: '#5e6662', trousers: '#565c58', webbing: '#2a2622', helmet: '#4b524f', boots: '#1d1b19', marker: '#d0574a' }
}

const matCache = new Map()
function mat (color) {
  if (!matCache.has(color)) matCache.set(color, new THREE.MeshStandardMaterial({ color, roughness: 0.85, flatShading: true }))
  return matCache.get(color)
}
const SKIN = '#c49473'
const FRIEND_TAG = '#8fd8ff'
const GUNMETAL = '#2b2c2e'
const STAB_TIME = KNIFE.windup + KNIFE.recover
const LEAN_TILT = Math.asin(PLAYER.leanDist / 0.76) // 0.76 m from the torso pivot to the head: lands the head where its hitbox shifts
// crouch leg angles: [planted left, kneeling right]
const KNEEL = [{ thigh: 1.6, knee: -1.85, ankle: 0.25 }, { thigh: 0.6, knee: -2.46, ankle: 0 }]
const THIGH = 0.45 // hip to knee, knee to ankle
const SHIN = 0.38
const ARM_REACH = 0.46 // shoulder to a hand on the bars
const FIST = 0.075 // modelled soldiers: wrist to the middle of the fist
const POLE = [new THREE.Vector3(0.75, -1, 0.25), new THREE.Vector3(-0.45, -1, 0.1)] // where the elbows point
const POLE_ADS = [new THREE.Vector3(1, -0.35, 0.15), new THREE.Vector3(-0.25, -1, -0.1)] // aiming: right elbow up and out
// modelled soldiers' gun pivot (aim frame) held ready (muzzle a little down) and aimed down the sights (at the eye)
const STANCE = {
  rifle: { ready: new THREE.Vector3(0.1, -0.1, -0.24), readyPitch: -0.16, ads: new THREE.Vector3(0.07, 0.19, -0.19) },
  pistol: { ready: new THREE.Vector3(0.02, -0.17, -0.4), readyPitch: -0.22, ads: new THREE.Vector3(0.025, 0.15, -0.5) }
}
const _w = new THREE.Vector3()
const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a))
const smoothstep = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t) }
const PISTOL_HANDS = [[0.004, -0.075, 0.03], [-0.03, -0.085, 0.0]]
const _v = new THREE.Vector3()
const _u = new THREE.Vector3()

// one template per weapon; soldiers clone it (geometry and materials shared)
const gunTemplates = new Map()
function gunTemplate (id) {
  let t = gunTemplates.get(id)
  if (!t) {
    const spec = buildGun(id)
    let gun = spec.gun
    if (spec.lod) {
      gun = new THREE.Group()
      gun.add(spec.lod.clone())
    } else {
      spec.mag.visible = !spec.magHidden
    }
    gun.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.userData.shared = true } })
    const pistol = spec.kind === 'pistol'
    t = { gun, muzzle: spec.muzzle.clone(), pistol, hands: pistol ? PISTOL_HANDS : [spec.rh, spec.lh] }
    gunTemplates.set(id, t)
  }
  return t
}

function box (w, h, d, color, x, y, z, parent) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color))
  m.position.set(x, y, z)
  m.castShadow = true
  parent.add(m)
  return m
}

// the shapes hung on one pivot move together: build() merges them into one vertex-coloured mesh per pivot,
// so a soldier costs ~10 draw calls (and as many shadow ones) instead of ~25
const partMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, flatShading: true })
const _col = new THREE.Color()

function mergeParts (pivot) {
  const parts = pivot.children.filter((o) => o.isMesh)
  const geos = parts.map((m) => {
    m.updateMatrix()
    let g = m.geometry.clone().applyMatrix4(m.matrix)
    g.deleteAttribute('uv')
    if (m.userData.twoSided) g = mergeGeometries([g, flipped(g)])
    const n = g.attributes.position.count
    const c = new Float32Array(n * 3)
    _col.copy(m.material.color)
    for (let i = 0; i < n; i++) _col.toArray(c, i * 3)
    g.setAttribute('color', new THREE.BufferAttribute(c, 3))
    m.geometry.dispose()
    pivot.remove(m)
    return g
  })
  const merged = new THREE.Mesh(mergeGeometries(geos), partMat)
  merged.castShadow = true
  pivot.add(merged)
}

// back faces of an open shape (helmet skirt), as its own triangles
function flipped (g) {
  const b = g.clone()
  const idx = b.index.array
  for (let i = 0; i < idx.length; i += 3) { const t = idx[i + 1]; idx[i + 1] = idx[i + 2]; idx[i + 2] = t }
  const nrm = b.attributes.normal.array
  for (let i = 0; i < nrm.length; i++) nrm[i] = -nrm[i]
  return b
}

function pivot (x, y, z, parent) {
  const g = new THREE.Group()
  g.position.set(x, y, z)
  parent.add(g)
  return g
}

function nameSprite (text, color) {
  const c = document.createElement('canvas')
  c.width = 256; c.height = 64
  const g = c.getContext('2d')
  g.font = '600 30px Oswald, Arial Narrow, sans-serif'
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  g.lineWidth = 5
  g.strokeStyle = 'rgba(0,0,0,0.75)'
  g.strokeText(text, 128, 26)
  g.fillStyle = color
  g.fillText(text, 128, 26)
  // little team chevron
  g.beginPath(); g.moveTo(118, 46); g.lineTo(128, 58); g.lineTo(138, 46); g.closePath()
  g.fill(); g.lineWidth = 2; g.stroke()
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  const sm = new THREE.SpriteMaterial({ map: tex, depthTest: false, depthWrite: false, transparent: true, fog: false })
  const s = new THREE.Sprite(sm)
  s.scale.set(1.6, 0.4, 1)
  s.renderOrder = 20
  return s
}

function flashSprite () {
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const g = c.getContext('2d')
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32)
  grd.addColorStop(0, 'rgba(255,245,200,1)')
  grd.addColorStop(0.4, 'rgba(255,170,60,0.7)')
  grd.addColorStop(1, 'rgba(255,120,0,0)')
  g.fillStyle = grd
  g.fillRect(0, 0, 64, 64)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  return new THREE.SpriteMaterial({ map: tex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false })
}
let flashMat = null

export class Avatar {
  // tagColor: the name tag over a friendly's head (spectators see everyone's, in team colours)
  constructor (id, team, name, friendly, tagColor = FRIEND_TAG) {
    this.id = id
    this.team = team
    this.name = name
    this.friendly = friendly
    this.tagColor = tagColor
    this.buffer = []
    this.pos = new THREE.Vector3()
    this.yaw = 0
    this.pitch = 0
    this.lean = 0
    this.crouch = 0
    this.crouched = false
    this.alive = false
    this.life = -1
    this.killedLife = -1
    this.weapon = 0
    this.flags = 0
    this.hp = 100
    this.walkPhase = 0
    this.speed = 0
    this.deathT = 0
    this.deathDir = 1
    this.flashT = 0
    this.stabT = 0
    this.lastPos = new THREE.Vector3()
    this.vel = new THREE.Vector2() // ground velocity (x, z), smoothed
    this.lastYaw = 0
    this.legYaw = 0 // the legs' heading relative to the body's
    this.turning = false // stepping round to catch up with the body
    this.adsK = 0
    this.sprintK = 0
    this.build()
  }

  build () {
    const root = new THREE.Group()
    this.root = root
    const model = buildSoldier(this.team, root)
    if (model) this.buildModel(model)
    else this.buildBoxes()

    // long arms are held at the rifle pivot, sidearms out in front (the modelled soldier moves both: stance())
    this.rifle = pivot(0.06, -0.14, -0.3, this.aim)
    this.pistol = pivot(0.0, -0.16, -0.5, this.aim)
    this.guns = new Map()
    this.weaponId = null

    if (!flashMat) flashMat = flashSprite()
    this.flash = new THREE.Sprite(flashMat)
    this.flash.scale.setScalar(0.5)
    this.flash.visible = false
    this.flashPivot = new THREE.Group()
    this.flashPivot.add(this.flash)
    this.setWeapon('stg44')

    if (this.friendly) {
      this.tag = nameSprite(this.name, this.tagColor)
      this.tag.position.set(0, 2.25, 0)
      root.add(this.tag)
    }
  }

  // the procedural stand-in: boxes hung on pivots, merged per pivot
  buildBoxes () {
    const st = STYLE[this.team] || STYLE.allies
    const root = this.root
    const body = pivot(0, 0, 0, root)
    this.body = body

    // legs
    this.hips = pivot(0, 0.94, 0, body)
    this.legs = []
    for (const side of [-1, 1]) {
      const thigh = pivot(side * 0.1, 0, 0, this.hips)
      box(0.16, 0.46, 0.18, st.trousers, 0, -0.22, 0, thigh)
      const knee = pivot(0, -0.45, 0, thigh)
      box(0.14, 0.38, 0.16, st.trousers, 0, -0.19, 0, knee)
      const ankle = pivot(0, -0.38, 0, knee)
      box(0.15, 0.11, 0.27, st.boots, 0, -0.05, -0.05, ankle)
      this.legs.push({ thigh, knee, ankle })
    }
    // torso
    this.torso = pivot(0, 0.94, 0, body)
    box(0.42, 0.56, 0.25, st.uniform, 0, 0.3, 0, this.torso)
    box(0.44, 0.07, 0.27, st.webbing, 0, 0.05, 0, this.torso) // belt
    box(0.06, 0.5, 0.02, st.webbing, -0.12, 0.3, -0.135, this.torso) // straps
    box(0.06, 0.5, 0.02, st.webbing, 0.12, 0.3, -0.135, this.torso)
    box(0.32, 0.3, 0.13, st.webbing, 0, 0.32, 0.18, this.torso) // pack
    if (this.team === 'axis') {
      box(0.09, 0.2, 0.09, GUNMETAL, -0.2, 0.0, 0.08, this.torso) // canister
    } else {
      box(0.12, 0.14, 0.08, st.webbing, 0.2, 0.06, -0.06, this.torso) // pouch
    }
    // head
    this.head = pivot(0, 0.6, 0, this.torso)
    box(0.11, 0.08, 0.11, SKIN, 0, 0.03, 0, this.head)
    box(0.2, 0.22, 0.21, SKIN, 0, 0.16, -0.01, this.head)
    if (this.team === 'axis') {
      const dome = new THREE.Mesh(new THREE.SphereGeometry(0.155, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), mat(st.helmet))
      dome.position.set(0, 0.22, 0)
      dome.scale.set(1, 0.9, 1.08)
      const skirt = new THREE.Mesh(new THREE.CylinderGeometry(0.155, 0.185, 0.09, 10, 1, true), mat(st.helmet))
      skirt.position.set(0, 0.18, 0.01)
      skirt.userData.twoSided = true
      dome.castShadow = skirt.castShadow = true
      this.head.add(dome, skirt)
    } else {
      const dome = new THREE.Mesh(new THREE.SphereGeometry(0.16, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), mat(st.helmet))
      dome.position.set(0, 0.22, 0)
      dome.scale.set(1.02, 0.95, 1.1)
      const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.175, 0.18, 0.02, 10), mat(st.helmet))
      brim.position.set(0, 0.22, 0)
      dome.castShadow = brim.castShadow = true
      this.head.add(dome, brim)
      box(0.02, 0.02, 0.02, st.webbing, 0, 0.1, -0.12, this.head) // chin strap hint
    }
    // arms + weapon pitch with aim
    this.aim = pivot(0, 0.5, 0, this.torso)
    const shoulderR = pivot(0.25, 0, 0, this.aim)
    const upR = box(0.12, 0.3, 0.13, st.uniform, 0, -0.13, 0, shoulderR)
    upR.rotation.x = 0.6
    const foreR = box(0.11, 0.28, 0.11, st.uniform, -0.04, -0.2, -0.22, shoulderR)
    foreR.rotation.x = 1.35
    foreR.rotation.z = 0.35
    box(0.08, 0.08, 0.09, SKIN, -0.1, -0.22, -0.36, shoulderR)
    const shoulderL = pivot(-0.25, 0, 0, this.aim)
    const upL = box(0.12, 0.3, 0.13, st.uniform, 0, -0.1, -0.08, shoulderL)
    upL.rotation.x = 1.0
    const foreL = box(0.11, 0.3, 0.11, st.uniform, 0.08, -0.12, -0.36, shoulderL)
    foreL.rotation.x = 1.5
    foreL.rotation.z = -0.5
    box(0.08, 0.08, 0.09, SKIN, 0.17, -0.12, -0.5, shoulderL)
    // where each hand sits relative to its shoulder, for reach()
    this.shoulders = [{ pivot: shoulderR, hand: new THREE.Vector3(-0.1, -0.22, -0.36) }, { pivot: shoulderL, hand: new THREE.Vector3(0.17, -0.12, -0.5) }]
    const pivots = []
    root.traverse((o) => { if (o.children.some((c) => c.isMesh)) pivots.push(o) })
    for (const p of pivots) mergeParts(p)
  }

  // the modelled soldier: its bones are the pivots (identity rest rotations), the arms are aimed at the grips by IK
  buildModel ({ bones, arms, mesh }) {
    this.mesh = mesh
    this.body = bones.body
    this.hips = bones.hips
    this.legs = ['l', 'r'].map((s) => ({ thigh: bones[`thigh_${s}`], knee: bones[`shin_${s}`], ankle: bones[`foot_${s}`] }))
    this.torso = bones.torso
    this.head = bones.head
    this.aim = bones.aim
    this.arms = arms
  }

  // legs: a stride cycle driven by the distance covered (so the feet do not skate), the legs turned towards the
  // way the soldier is going (side-stepping beyond what the hips can turn), crouch-walking or kneeling when crouched
  locomote (dt, cr) {
    const moving = smoothstep(0.35, 1.2, this.speed)
    let dir = 1
    let side = 0
    let target = this.legYaw
    if (this.speed > 0.35) {
      let rel = wrap(Math.atan2(-this.vel.x, -this.vel.y) - this.yaw)
      if (Math.abs(rel) > 1.75) { rel = wrap(rel - Math.PI); dir = -1 } // backing away: legs face forward, stride reversed
      target = THREE.MathUtils.clamp(rel, -1.05, 1.05)
      side = Math.sin(rel - target) * 1.6
      this.turning = false
    } else if (Math.abs(this.legYaw) > 0.85) this.turning = true // turned on the spot too far: step round
    if (this.turning) {
      target = 0
      if (Math.abs(this.legYaw) < 0.06) this.turning = false
    }
    this.legYaw += (target - this.legYaw) * Math.min(1, dt * (this.turning ? 7 : 9))

    // stride: one cycle per ~1.3 m walking, longer running; a short shuffle while stepping round
    const stride = 1.15 + 0.22 * this.speed - 0.4 * cr
    this.walkPhase += dir * (this.speed * dt / stride) * Math.PI * 2
    if (this.turning && moving < 0.3) this.walkPhase += dt * 9
    const amp = Math.max(moving * Math.min(1, this.speed / 4.2 + 0.25), this.turning ? 0.3 : 0)
    const run = smoothstep(3, 5.5, this.speed)
    const walkK = (1 - cr) * amp
    const crawlK = cr * Math.max(amp, this.turning ? 0.3 : 0) // crouch-walking
    const kneelK = cr - crawlK
    const ph = this.walkPhase

    for (let i = 0; i < 2; i++) {
      const L = this.legs[i]
      const f = ph + (i ? Math.PI : 0)
      const sw = Math.sin(f)
      const lift = Math.max(0, Math.cos(f)) ** 1.3 // swing phase: the foot comes through with the knee bent
      // standing gait
      const tW = (0.42 + 0.22 * run) * sw
      const kW = -(0.12 + (0.95 + 0.55 * run) * lift)
      const aW = -(tW + kW) * 0.65 * (1 - lift) + 0.2 * lift
      // crouch-walk: low, knees well bent, short steps
      const tC = 0.95 + 0.4 * sw
      const kC = -(1.45 + 0.55 * lift)
      const aC = 0.55 - 0.25 * sw
      const K = KNEEL[i]
      L.thigh.rotation.set(tW * walkK + tC * crawlK + K.thigh * kneelK,
        0, side * 0.32 * sw * Math.max(walkK, crawlK) + (i ? -1 : 1) * 0.04 * crawlK, 'XYZ')
      L.knee.rotation.x = kW * walkK + kC * crawlK + K.knee * kneelK
      L.ankle.rotation.x = aW * walkK + aC * crawlK + K.ankle * kneelK
    }
    // hips: bob twice a stride, twist and roll with the legs; kneel or crouch-walk heights
    const bob = -0.035 * walkK * (1 + run) * (1 - Math.cos(2 * ph)) * 0.5
    this.hips.position.set(0, 0.94 + bob - 0.48 * kneelK - 0.36 * crawlK, 0.12 * kneelK + 0.04 * crawlK)
    this.hips.rotation.set(0, this.legYaw + 0.16 * Math.sin(ph) * Math.max(walkK, crawlK), 0.05 * Math.cos(ph) * walkK)
    this.torso.position.copy(this.hips.position)
    // the upper body leans into a run and counter-swings the hips a little
    this.torso.rotation.x = -0.35 * kneelK - 0.3 * crawlK - 0.06 * walkK - 0.1 * run * (1 - cr)
    this.torso.rotation.y = -0.07 * Math.sin(ph) * walkK
  }

  // gun held ready, aimed down the sights (flags bit 4) or carried while sprinting; both hands follow it every frame
  stance (dt) {
    const t = gunTemplate(this.weaponId)
    const S = t.pistol ? STANCE.pistol : STANCE.rifle
    const k = Math.min(1, dt * 9)
    this.adsK += ((this.flags & 4 ? 1 : 0) - this.adsK) * k
    this.sprintK += (smoothstep(5.3, 6.3, this.speed) * (1 - this.adsK) - this.sprintK) * k
    const a = this.adsK; const r = this.sprintK
    const piv = t.pistol ? this.pistol : this.rifle
    piv.position.lerpVectors(S.ready, S.ads, a)
    piv.rotation.set(S.readyPitch * (1 - a) - 0.55 * r, 0.3 * r, 0)
    this.head.rotation.x += 0.2 * a * (t.pistol ? 0.4 : 1)
    this.head.rotation.z = -0.16 * a * (t.pistol ? 0.3 : 1)
    piv.updateMatrix()
    for (let i = 0; i < 2; i++) {
      const h = t.hands[i]
      _w.lerpVectors(POLE[i], POLE_ADS[i], a)
      this.grip(i, _v.set(h[0], h[1], h[2]).applyMatrix4(piv.matrix), _w)
    }
  }

  setWeapon (id) {
    if (id === this.weaponId) return
    if (this.weaponId) this.guns.get(this.weaponId).visible = false
    this.weaponId = id
    const t = gunTemplate(id)
    let g = this.guns.get(id)
    if (!g) {
      g = t.gun.clone()
      ;(t.pistol ? this.pistol : this.rifle).add(g)
      this.guns.set(id, g)
    }
    g.visible = true
    g.add(this.flashPivot)
    this.flashPivot.position.copy(t.muzzle)
    this.flash.scale.setScalar(0.5 * Math.max(0.7, WEAPONS[id].fx.flash))
  }

  // the fist's middle onto point p (aim frame): the wrist stops short of it on the way back to the shoulder
  grip (i, p, pole = POLE[i]) {
    const a = this.arms[i]
    const w = _u.copy(a.shoulder).sub(p).normalize().multiplyScalar(FIST).add(p)
    aimArm(a, w, pole, 0.03)
  }

  setName (name) {
    if (name === this.name || !this.friendly) return
    this.name = name
    this.root.remove(this.tag)
    this.tag.material.map.dispose()
    this.tag.material.dispose()
    this.tag = nameSprite(name, this.tagColor)
    this.tag.position.set(0, 2.25, 0)
    this.root.add(this.tag)
  }

  push (t, e) {
    // e = [id,x,y,z,yaw,pitch,flags,weapon,hp,life,age,lean]; the position belongs to server time t - age
    const b = this.buffer
    t -= e[10] || 0
    const last = b[b.length - 1]
    if (last && t < last.t) return
    const s = { t, x: e[1], y: e[2], z: e[3], yaw: e[4], pitch: e[5], flags: e[6], weapon: e[7], hp: e[8], life: e[9], lean: e[11] || 0 }
    if (last && t === last.t) { b[b.length - 1] = s; return } // same position sample, newer state (hp, death...)
    b.push(s)
    if (b.length > 40) b.splice(0, b.length - 40)
  }

  // interpolate the buffered snapshots at renderT (server ms)
  sample (renderT) {
    const b = this.buffer
    if (!b.length) return false
    let a = b[0]; let c = b[0]
    if (renderT >= b[b.length - 1].t) {
      a = c = b[b.length - 1]
    } else {
      for (let i = b.length - 1; i >= 0; i--) {
        if (b[i].t <= renderT) { a = b[i]; c = b[i + 1] || b[i]; break }
      }
    }
    let k = c.t > a.t ? (renderT - a.t) / (c.t - a.t) : 0
    if (a.life !== c.life) k = renderT - a.t > (c.t - a.t) / 2 ? 1 : 0 // no lerp across respawns
    k = Math.max(0, Math.min(1, k))
    this.pos.set(a.x + (c.x - a.x) * k, a.y + (c.y - a.y) * k, a.z + (c.z - a.z) * k)
    let dy = c.yaw - a.yaw
    dy = Math.atan2(Math.sin(dy), Math.cos(dy))
    this.yaw = a.yaw + dy * k
    this.pitch = a.pitch + (c.pitch - a.pitch) * k
    this.lean = a.lean + (c.lean - a.lean) * k
    const src = k < 0.5 ? a : c
    this.flags = src.flags
    this.weapon = src.weapon
    this.hp = src.hp
    const alive = !!(src.flags & 1) && src.life !== this.killedLife
    if (src.life !== this.life) {
      this.life = src.life
      this.lastPos.copy(this.pos)
      if (alive) this.deathT = 0
    }
    if (this.alive && !alive) { this.deathT = 0.0001; this.deathDir = Math.random() < 0.5 ? 1 : -1 }
    this.alive = alive
    this.crouched = !!(src.flags & 2)
    return true
  }

  // astride a motorcycle, no weapon in hand. fit (all in the root's frame): hips, footR / footL (where the soles
  // rest) and grips [right, left] (where the hands go); the legs bend to reach the feet and the back leans until the
  // hands can reach the bars. Without it: knees up on generic footrests.
  sit (fit = null) {
    this.rifle.visible = this.pistol.visible = false
    this.aim.rotation.x = 0.05
    if (!fit) {
      this.hips.position.set(0, 0.86, 0.08)
      this.torso.position.copy(this.hips.position)
      for (const [i, L] of this.legs.entries()) {
        L.thigh.rotation.set(1.3, 0, (i ? -1 : 1) * 0.16)
        L.knee.rotation.x = -1.5
        L.ankle.rotation.x = 0.25
      }
      this.torso.rotation.set(-0.4, 0, 0)
      return
    }
    this.hips.position.copy(fit.hips)
    this.torso.position.copy(fit.hips)
    for (const [i, L] of this.legs.entries()) {
      // the ankle pivot sits above and a little behind the middle of the sole
      const foot = i ? fit.footR : fit.footL
      const dx = foot.x - (fit.hips.x + L.thigh.position.x)
      const dy = foot.y + 0.1 - fit.hips.y
      const dz = foot.z + 0.05 - fit.hips.z
      // splay the leg's plane sideways (z, applied last), then bend hip and knee within it (x)
      const h = Math.hypot(dx, dy)
      const d = Math.min(Math.hypot(h, dz), THIGH + SHIN - 1e-3)
      const hip = Math.atan2(-dz, h) + Math.acos((THIGH * THIGH + d * d - SHIN * SHIN) / (2 * THIGH * d))
      const knee = -(Math.PI - Math.acos((THIGH * THIGH + SHIN * SHIN - d * d) / (2 * THIGH * SHIN)))
      L.thigh.rotation.set(hip, 0, Math.atan2(dx, -dy), 'ZXY')
      L.knee.rotation.x = knee
      L.ankle.rotation.x = -(hip + knee)
    }
    // lean forward until the shoulders are an arm's length from the grips
    const g = fit.grips[0].clone().add(fit.grips[1]).multiplyScalar(0.5)
    let best = 0; let err = Infinity
    for (let a = 0; a <= 1.2; a += 0.02) {
      const e = Math.abs(Math.hypot(g.y - fit.hips.y - 0.5 * Math.cos(a), g.z - fit.hips.z + 0.5 * Math.sin(a)) - ARM_REACH)
      if (e < err) { err = e; best = a }
    }
    this.torso.rotation.set(-best, 0, 0)
    this.aim.rotation.x = 0
    this.head.rotation.x = best * 0.6 // eyes on the road
  }

  // point shoulder i (0 right, 1 left) so its hand lands on the way to `world` (a world-space point; the matrices
  // must be up to date)
  reach (i, world) {
    if (this.arms) { this.grip(i, this.aim.worldToLocal(_v.copy(world))); return }
    const s = this.shoulders[i]
    const to = this.aim.worldToLocal(_v.copy(world)).sub(s.pivot.position).normalize()
    s.pivot.quaternion.setFromUnitVectors(_u.copy(s.hand).normalize(), to)
  }

  showFlash () { this.flashT = 0.06 }
  stab () { this.stabT = STAB_TIME }

  animate (dt) {
    const root = this.root
    root.position.copy(this.pos)
    // the legs keep their heading in the world while the upper body turns with the view
    this.legYaw -= wrap(this.yaw - this.lastYaw)
    this.lastYaw = this.yaw
    root.rotation.y = this.yaw

    const k10 = Math.min(1, dt * 10)
    const dx = this.pos.x - this.lastPos.x; const dz = this.pos.z - this.lastPos.z
    const moved = Math.hypot(dx, dz)
    this.lastPos.copy(this.pos)
    if (dt > 0 && moved < 2) { // (a respawn or teleport is not a step)
      this.vel.x += (Math.min(8, dx / dt) - this.vel.x) * k10
      this.vel.y += (Math.min(8, dz / dt) - this.vel.y) * k10
    }
    this.speed = this.vel.length()

    const c = this.crouched ? 1 : 0
    this.crouch += (c - this.crouch) * Math.min(1, dt * 12)
    const cr = this.crouch
    this.locomote(dt, cr)

    this.aim.rotation.x = this.pitch - this.torso.rotation.x
    this.head.rotation.x = this.pitch * 0.4
    this.head.rotation.z = 0
    this.torso.rotation.z = -LEAN_TILT * this.lean
    // knife: twist the shoulders into the stab and swing the arms down through it
    if (this.stabT > 0) {
      this.stabT = Math.max(0, this.stabT - dt)
      const lunge = Math.sin((1 - this.stabT / STAB_TIME) * Math.PI)
      this.torso.rotation.y -= 0.5 * lunge
      this.aim.rotation.x -= 0.45 * lunge
    }
    if (this.arms) this.stance(dt)

    this.setWeapon(WEAPON_LIST[this.weapon] || 'stg44')
    if (this.flashT > 0) {
      this.flashT -= dt
      this.flash.visible = this.alive
      this.flash.material.rotation = Math.random() * 6
    } else this.flash.visible = false

    // death: topple over and sink
    if (!this.alive) {
      if (this.deathT > 0) this.deathT += dt
      const k = Math.min(1, this.deathT / 0.45)
      const e = k * k
      this.body.rotation.x = this.deathDir * e * 1.5
      this.body.position.y = -e * 0.12
      this.body.rotation.z = e * 0.2 * this.deathDir
      root.visible = this.deathT > 0 && this.deathT < 4.5
      if (this.tag) this.tag.visible = false
    } else {
      this.body.rotation.set(0, 0, 0)
      this.body.position.y = 0
      root.visible = !this.inTank && !this.onBike // a bike draws its own rider
      if (this.tag) this.tag.visible = true
    }
  }

  get inTank () { return !!(this.flags & 64) }
  get onBike () { return !!(this.flags & 128) }

  // alive and out in the open: what a bullet or a blade can reach
  get exposed () { return this.alive && !this.inTank }

  // hitbox reference point for analytic ray tests
  get hitPos () { return [this.pos.x, this.pos.y, this.pos.z] }

  dispose () {
    this.root.traverse((o) => { if (o.isMesh && !o.userData.shared) o.geometry.dispose() })
    this.mesh?.skeleton.dispose()
    if (this.tag) { this.tag.material.map.dispose(); this.tag.material.dispose() }
    this.root.parent?.remove(this.root)
  }
}

export class Avatars {
  constructor (scene) {
    this.scene = scene
    this.map = new Map()
    this.offset = null // server time - local time
    this.lastSnapLocal = 0
    this.hidden = false // kept up to date but not drawn (while the kill-cam shows the soldiers as they were)
  }

  // myTeam: null for a spectator, who is on neither side
  ensure (id, info, myTeam) {
    let a = this.map.get(id)
    if (a && a.team !== info.team) { a.dispose(); this.map.delete(id); a = null }
    if (!a) {
      a = myTeam ? new Avatar(id, info.team, info.name, info.team === myTeam) : new Avatar(id, info.team, info.name, true, TEAMS[info.team]?.hud)
      this.map.set(id, a)
      this.scene.add(a.root)
    } else a.setName(info.name)
    return a
  }

  onSnapshot (snap, myId, roster, myTeam) {
    const now = performance.now()
    const target = snap.t - now
    if (this.offset == null || Math.abs(target - this.offset) > 400) this.offset = target
    else if (target > this.offset) this.offset += (target - this.offset) * 0.2 // packets that arrive faster pull the clock forward
    else this.offset += (target - this.offset) * 0.02
    this.lastSnapLocal = now
    const seen = new Set()
    for (const e of snap.p) {
      const id = e[0]
      if (id === myId) continue
      const info = roster.get(id)
      if (!info) continue
      seen.add(id)
      this.ensure(id, info, myTeam).push(snap.t, e)
    }
    for (const [id, a] of this.map) {
      if (!seen.has(id)) { a.dispose(); this.map.delete(id) }
    }
  }

  renderTime (delay) {
    return performance.now() + (this.offset || 0) - delay
  }

  update (dt, delay) {
    const rt = this.renderTime(delay)
    for (const a of this.map.values()) {
      if (a.sample(rt)) a.animate(dt)
      if (this.hidden) a.root.visible = false
    }
  }

  clear () {
    for (const a of this.map.values()) a.dispose()
    this.map.clear()
  }
}

export const AVATAR_EYE = PLAYER.eye
