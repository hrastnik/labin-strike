// Pooled combat effects: tracers, impact dust/sparks, bullet holes, blood puffs, muzzle light.
import * as THREE from 'three'

const UP = new THREE.Vector3(0, 1, 0)
const tmpV = new THREE.Vector3()
const tmpQ = new THREE.Quaternion()

function radialTexture (inner, outer) {
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const g = c.getContext('2d')
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32)
  grd.addColorStop(0, inner)
  grd.addColorStop(1, outer)
  g.fillStyle = grd
  g.fillRect(0, 0, 64, 64)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

function holeTexture () {
  const c = document.createElement('canvas')
  c.width = c.height = 64
  const g = c.getContext('2d')
  const grd = g.createRadialGradient(32, 32, 2, 32, 32, 30)
  grd.addColorStop(0, 'rgba(10,8,6,1)')
  grd.addColorStop(0.3, 'rgba(25,20,15,0.95)')
  grd.addColorStop(0.55, 'rgba(60,52,42,0.5)')
  grd.addColorStop(1, 'rgba(60,52,42,0)')
  g.fillStyle = grd
  g.fillRect(0, 0, 64, 64)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

export class Effects {
  constructor (scene) {
    this.scene = scene

    // tracers: stretched additive quads that fly along the bullet path
    this.tracers = []
    const tracerMat = new THREE.MeshBasicMaterial({ color: 0xffd890, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false })
    const tg = new THREE.BoxGeometry(0.018, 0.018, 1)
    for (let i = 0; i < 48; i++) {
      const m = new THREE.Mesh(tg, tracerMat)
      m.visible = false
      m.frustumCulled = false
      scene.add(m)
      this.tracers.push({ mesh: m, from: new THREE.Vector3(), dir: new THREE.Vector3(), len: 0, d: 0, speed: 0 })
    }
    this.tracerIdx = 0

    // particles (dust, sparks, blood) as sprites
    this.particles = []
    this.dustMat = new THREE.SpriteMaterial({ map: radialTexture('rgba(200,190,170,0.85)', 'rgba(200,190,170,0)'), transparent: true, depthWrite: false })
    this.sparkMat = new THREE.SpriteMaterial({ map: radialTexture('rgba(255,230,160,1)', 'rgba(255,140,40,0)'), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false })
    this.bloodMat = new THREE.SpriteMaterial({ map: radialTexture('rgba(140,10,8,0.95)', 'rgba(90,0,0,0)'), transparent: true, depthWrite: false })
    for (let i = 0; i < 160; i++) {
      const s = new THREE.Sprite(this.dustMat)
      s.visible = false
      scene.add(s)
      this.particles.push({ s, v: new THREE.Vector3(), t: 0, life: 1, size: 0.1, grow: 0, grav: 0, fade: true })
    }
    this.pIdx = 0

    // bullet holes
    this.holes = []
    const hm = new THREE.MeshBasicMaterial({ map: holeTexture(), transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 })
    const hg = new THREE.PlaneGeometry(0.11, 0.11)
    for (let i = 0; i < 140; i++) {
      const m = new THREE.Mesh(hg, hm)
      m.visible = false
      m.renderOrder = 1
      scene.add(m)
      this.holes.push(m)
    }
    this.holeIdx = 0

    // a single always-present light avoids shader recompiles when muzzle flashes appear
    this.muzzleLight = new THREE.PointLight(0xffc070, 0, 9, 2)
    scene.add(this.muzzleLight)
    this.muzzleT = 0
  }

  tracer (from, to, speed = 380) {
    const t = this.tracers[this.tracerIdx++ % this.tracers.length]
    t.from.copy(from)
    t.dir.subVectors(to, from)
    t.len = t.dir.length()
    if (t.len < 2) return
    t.dir.divideScalar(t.len)
    t.d = Math.min(1.5, t.len * 0.1)
    t.speed = speed
    t.mesh.visible = true
    t.mesh.quaternion.setFromUnitVectors(tmpV.set(0, 0, 1), t.dir)
  }

  particle (pos, mat, { v, life = 0.5, size = 0.12, grow = 0.4, grav = 0 }) {
    const p = this.particles[this.pIdx++ % this.particles.length]
    p.s.material = mat
    p.s.position.copy(pos)
    p.v.copy(v)
    p.t = 0
    p.life = life
    p.size = size
    p.grow = grow
    p.grav = grav
    p.s.scale.setScalar(size)
    p.s.visible = true
  }

  impact (pos, normal, surface = 'world') {
    const n = tmpV.set(normal[0], normal[1], normal[2])
    for (let i = 0; i < 4; i++) {
      const v = new THREE.Vector3(n.x + (Math.random() - 0.5) * 0.8, n.y + Math.random() * 0.6, n.z + (Math.random() - 0.5) * 0.8).multiplyScalar(0.6 + Math.random() * 0.8)
      this.particle(pos, this.dustMat, { v, life: 0.6 + Math.random() * 0.4, size: 0.1, grow: 0.7, grav: -0.4 })
    }
    if (surface === 'metal' || Math.random() < 0.35) {
      for (let i = 0; i < 3; i++) {
        const v = new THREE.Vector3(n.x + (Math.random() - 0.5) * 1.5, n.y + Math.random(), n.z + (Math.random() - 0.5) * 1.5).multiplyScalar(3 + Math.random() * 3)
        this.particle(pos, this.sparkMat, { v, life: 0.18, size: 0.05, grow: -0.1, grav: 9 })
      }
    }
    // decal, slightly off the surface and randomly rotated
    const h = this.holes[this.holeIdx++ % this.holes.length]
    h.position.set(pos.x + normal[0] * 0.004, pos.y + normal[1] * 0.004, pos.z + normal[2] * 0.004)
    tmpQ.setFromUnitVectors(tmpV.set(0, 0, 1), new THREE.Vector3(normal[0], normal[1], normal[2]))
    h.quaternion.copy(tmpQ)
    h.rotateZ(Math.random() * Math.PI * 2)
    const s = 0.7 + Math.random() * 0.5
    h.scale.set(s, s, 1)
    h.visible = true
  }

  blood (pos, dir) {
    for (let i = 0; i < 6; i++) {
      const v = new THREE.Vector3(dir.x + (Math.random() - 0.5) * 0.9, dir.y + Math.random() * 0.5, dir.z + (Math.random() - 0.5) * 0.9).multiplyScalar(0.8 + Math.random() * 1.2)
      this.particle(pos, this.bloodMat, { v, life: 0.35 + Math.random() * 0.25, size: 0.12, grow: 0.6, grav: 4 })
    }
  }

  muzzle (pos) {
    this.muzzleLight.position.copy(pos)
    this.muzzleLight.intensity = 6
    this.muzzleT = 0.05
  }

  update (dt) {
    for (const t of this.tracers) {
      if (!t.mesh.visible) continue
      t.d += t.speed * dt
      if (t.d - 3 > t.len) { t.mesh.visible = false; continue }
      const head = Math.min(t.d, t.len)
      const tail = Math.max(0, t.d - 3)
      const len = Math.max(0.01, head - tail)
      t.mesh.position.copy(t.from).addScaledVector(t.dir, (head + tail) / 2)
      t.mesh.scale.set(1, 1, len)
    }
    for (const p of this.particles) {
      if (!p.s.visible) continue
      p.t += dt
      if (p.t >= p.life) { p.s.visible = false; continue }
      p.v.y -= p.grav * dt
      p.v.multiplyScalar(Math.exp(-2.5 * dt))
      p.s.position.addScaledVector(p.v, dt)
      const k = p.t / p.life
      p.s.scale.setScalar(Math.max(0.01, p.size * (1 + p.grow * k * 3)))
      p.s.material.opacity = 1 // materials are shared, fade by shrinking alpha via scale instead
      if (k > 0.6) p.s.scale.multiplyScalar(1 - (k - 0.6) / 0.4 * 0.9)
    }
    if (this.muzzleT > 0) {
      this.muzzleT -= dt
      if (this.muzzleT <= 0) this.muzzleLight.intensity = 0
    }
  }
}

export { UP }
