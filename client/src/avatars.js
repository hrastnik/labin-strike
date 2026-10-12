// Remote players: procedural low-poly soldiers, snapshot interpolation and simple procedural animation.
import * as THREE from 'three'
import { PLAYER } from '@shared/constants.js'

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
const WOOD = '#5f3d22'

function box (w, h, d, color, x, y, z, parent) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color))
  m.position.set(x, y, z)
  m.castShadow = true
  parent.add(m)
  return m
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
  constructor (id, team, name, friendly) {
    this.id = id
    this.team = team
    this.name = name
    this.friendly = friendly
    this.buffer = []
    this.pos = new THREE.Vector3()
    this.yaw = 0
    this.pitch = 0
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
    this.lastPos = new THREE.Vector3()
    this.build()
  }

  build () {
    const st = STYLE[this.team] || STYLE.allies
    const root = new THREE.Group()
    this.root = root
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
      box(0.15, 0.11, 0.27, st.boots, 0, -0.43, -0.05, knee)
      this.legs.push({ thigh, knee })
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
      skirt.material.side = THREE.DoubleSide
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

    this.rifle = pivot(0.06, -0.14, -0.3, this.aim)
    box(0.05, 0.08, 0.5, GUNMETAL, 0, 0, -0.1, this.rifle)
    box(0.04, 0.04, 0.3, GUNMETAL, 0, 0.01, -0.5, this.rifle)
    box(0.04, 0.14, 0.05, GUNMETAL, 0, -0.1, -0.12, this.rifle)
    box(0.045, 0.1, 0.25, WOOD, 0, -0.03, 0.25, this.rifle)
    this.pistol = pivot(0.0, -0.16, -0.5, this.aim)
    box(0.04, 0.05, 0.18, GUNMETAL, 0, 0, 0, this.pistol)
    box(0.035, 0.1, 0.05, WOOD, 0, -0.06, 0.06, this.pistol)
    this.pistol.visible = false

    if (!flashMat) flashMat = flashSprite()
    this.flash = new THREE.Sprite(flashMat)
    this.flash.scale.setScalar(0.5)
    this.flash.visible = false
    this.flashPivot = pivot(0, 0, -0.68, this.rifle)
    this.flashPivot.add(this.flash)

    if (this.friendly) {
      this.tag = nameSprite(this.name, FRIEND_TAG)
      this.tag.position.set(0, 2.25, 0)
      root.add(this.tag)
    }
  }

  setName (name) {
    if (name === this.name || !this.friendly) return
    this.name = name
    this.root.remove(this.tag)
    this.tag.material.map.dispose()
    this.tag.material.dispose()
    this.tag = nameSprite(name, FRIEND_TAG)
    this.tag.position.set(0, 2.25, 0)
    this.root.add(this.tag)
  }

  push (t, e) {
    // e = [id,x,y,z,yaw,pitch,flags,weapon,hp,life,age]; the position belongs to server time t - age
    const b = this.buffer
    t -= e[10] || 0
    const last = b[b.length - 1]
    if (last && t < last.t) return
    const s = { t, x: e[1], y: e[2], z: e[3], yaw: e[4], pitch: e[5], flags: e[6], weapon: e[7], hp: e[8], life: e[9] }
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

  showFlash () { this.flashT = 0.06 }

  animate (dt) {
    const root = this.root
    root.position.copy(this.pos)
    root.rotation.y = this.yaw

    const moved = Math.hypot(this.pos.x - this.lastPos.x, this.pos.z - this.lastPos.z)
    this.lastPos.copy(this.pos)
    const inst = dt > 0 ? Math.min(8, moved / dt) : 0
    this.speed += (inst - this.speed) * Math.min(1, dt * 10)

    const c = this.crouched ? 1 : 0
    this.crouch += (c - this.crouch) * Math.min(1, dt * 12)
    const cr = this.crouch

    const sp = Math.min(1, this.speed / 4.5)
    this.walkPhase += dt * (3 + this.speed * 1.7) * (sp > 0.05 ? 1 : 0)
    const swing = Math.sin(this.walkPhase) * 0.65 * sp * (1 - 0.5 * cr)
    this.hips.position.y = 0.94 - 0.4 * cr
    this.torso.position.y = 0.94 - 0.42 * cr
    for (let i = 0; i < 2; i++) {
      const s = i === 0 ? swing : -swing
      const L = this.legs[i]
      L.thigh.rotation.x = s - 1.15 * cr + (i === 0 ? 0.3 * cr : -0.2 * cr)
      L.knee.rotation.x = Math.max(0, -s) * 0.9 * sp + 1.7 * cr - (i === 0 ? 0.4 * cr : 0)
    }
    this.torso.rotation.x = -0.1 * cr - 0.08 * sp
    this.aim.rotation.x = this.pitch - this.torso.rotation.x
    this.head.rotation.x = this.pitch * 0.4
    this.torso.rotation.y = Math.sin(this.walkPhase) * 0.06 * sp

    const pistol = this.weapon === 1
    this.rifle.visible = !pistol
    this.pistol.visible = pistol
    if (this.flashPivot.parent !== (pistol ? this.pistol : this.rifle)) {
      (pistol ? this.pistol : this.rifle).add(this.flashPivot)
      this.flashPivot.position.set(0, 0, pistol ? -0.14 : -0.68)
    }
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
      root.visible = true
      if (this.tag) this.tag.visible = true
    }
  }

  // hitbox reference point for analytic ray tests
  get hitPos () { return [this.pos.x, this.pos.y, this.pos.z] }

  dispose () {
    this.root.traverse((o) => { if (o.isMesh) o.geometry.dispose() })
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
  }

  ensure (id, info, myTeam) {
    let a = this.map.get(id)
    if (a && a.team !== info.team) { a.dispose(); this.map.delete(id); a = null }
    if (!a) {
      a = new Avatar(id, info.team, info.name, info.team === myTeam)
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
    }
  }

  clear () {
    for (const a of this.map.values()) a.dispose()
    this.map.clear()
  }
}

export const AVATAR_EYE = PLAYER.eye
