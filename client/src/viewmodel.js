// First-person weapon + arms, rendered in their own scene/camera pass so they never clip into walls.
import * as THREE from 'three'

const UNIFORM = { allies: '#5d6638', axis: '#5a6260' }

function mat (color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.72, metalness: 0.0, flatShading: true, ...opts })
}

const M = {
  steel: mat('#2d2f31', { metalness: 0.65, roughness: 0.42 }),
  steelLight: mat('#4a4d50', { metalness: 0.7, roughness: 0.38 }),
  wood: mat('#6a4325', { roughness: 0.6 }),
  woodDark: mat('#4a2e1a', { roughness: 0.65 }),
  bakelite: mat('#3b2a1e', { roughness: 0.5 }),
  skin: mat('#c99a78', { roughness: 0.8 }),
  glove: mat('#3a2f25', { roughness: 0.9 }),
  brass: mat('#c9a043', { metalness: 0.8, roughness: 0.3 })
}

function box (w, h, d, material, x = 0, y = 0, z = 0, parent) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material)
  m.position.set(x, y, z)
  parent?.add(m)
  return m
}

function cylZ (r, len, material, x, y, z, parent, seg = 10) {
  const g = new THREE.CylinderGeometry(r, r, len, seg)
  g.rotateX(Math.PI / 2)
  const m = new THREE.Mesh(g, material)
  m.position.set(x, y, z)
  parent?.add(m)
  return m
}

// tapered cylinder between two points
function limb (a, b, r0, r1, material, parent) {
  const av = new THREE.Vector3(...a); const bv = new THREE.Vector3(...b)
  const len = av.distanceTo(bv)
  const g = new THREE.CylinderGeometry(r1, r0, len, 8)
  g.translate(0, len / 2, 0)
  const m = new THREE.Mesh(g, material)
  m.position.copy(av)
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), bv.clone().sub(av).normalize())
  parent?.add(m)
  return m
}

function hand (x, y, z, rotX, material, parent) {
  const g = new THREE.Group()
  box(0.05, 0.035, 0.09, material, 0, 0, 0, g) // palm
  box(0.052, 0.025, 0.05, material, 0, -0.022, -0.035, g) // curled fingers
  box(0.02, 0.02, 0.05, material, 0.028, 0.008, -0.02, g) // thumb
  g.position.set(x, y, z)
  g.rotation.x = rotX
  parent.add(g)
  return g
}

function buildRifle (sleeve) {
  const root = new THREE.Group()
  const gun = new THREE.Group()
  root.add(gun)
  // receiver + top cover
  box(0.048, 0.06, 0.4, M.steel, 0, 0, -0.04, gun)
  cylZ(0.024, 0.36, M.steelLight, 0, 0.028, -0.05, gun, 8)
  box(0.05, 0.02, 0.1, M.steel, 0, -0.03, 0.02, gun) // trigger housing
  // barrel, gas tube, muzzle nut
  cylZ(0.011, 0.36, M.steel, 0, 0.004, -0.42, gun)
  cylZ(0.014, 0.25, M.steelLight, 0, 0.03, -0.33, gun, 8)
  cylZ(0.016, 0.03, M.steel, 0, 0.004, -0.6, gun)
  // front sight hood and post, rear tangent sight
  box(0.008, 0.032, 0.012, M.steel, 0, 0.055, -0.56, gun)
  box(0.03, 0.03, 0.006, M.steelLight, 0, 0.06, -0.565, gun).scale.set(1, 1, 1)
  box(0.032, 0.022, 0.05, M.steel, 0, 0.055, -0.06, gun)
  box(0.012, 0.012, 0.006, M.steel, -0.011, 0.07, -0.04, gun)
  box(0.012, 0.012, 0.006, M.steel, 0.011, 0.07, -0.04, gun)
  // bakelite handguard
  box(0.056, 0.045, 0.16, M.bakelite, 0, 0.022, -0.27, gun)
  // curved magazine
  const mag = new THREE.Group()
  mag.position.set(0, -0.03, -0.16)
  gun.add(mag)
  for (let i = 0; i < 5; i++) {
    const seg = box(0.026, 0.05, 0.044, M.steel, 0, -0.025 - i * 0.045, -i * i * 0.0045 - i * 0.006, mag)
    seg.rotation.x = -i * 0.09
  }
  // pistol grip + trigger guard
  const grip = box(0.032, 0.1, 0.045, M.wood, 0, -0.075, 0.07, gun)
  grip.rotation.x = 0.28
  box(0.008, 0.008, 0.06, M.steel, 0, -0.06, 0.02, gun)
  box(0.006, 0.02, 0.006, M.steel, 0, -0.045, 0.02, gun)
  // stock (tapered)
  const stockG = new THREE.CylinderGeometry(0.03, 0.042, 0.24, 4, 1)
  stockG.rotateY(Math.PI / 4)
  stockG.rotateX(Math.PI / 2)
  stockG.scale(0.8, 1.5, 1)
  const stock = new THREE.Mesh(stockG, M.wood)
  stock.position.set(0, -0.05, 0.28)
  stock.rotation.x = 0.14
  gun.add(stock)
  box(0.04, 0.11, 0.012, M.steel, 0, -0.075, 0.4, gun).rotation.x = 0.14

  // arms
  const arms = new THREE.Group()
  root.add(arms)
  const sleeveM = mat(sleeve, { roughness: 0.95 })
  hand(0.005, -0.075, 0.075, 0.3, M.skin, arms)
  limb([0.02, -0.09, 0.11], [0.14, -0.2, 0.42], 0.028, 0.036, M.skin, arms)
  limb([0.07, -0.14, 0.25], [0.2, -0.3, 0.6], 0.04, 0.05, sleeveM, arms)
  const lh = hand(-0.01, -0.02, -0.28, 0.1, M.skin, arms)
  lh.rotation.z = 0.5
  limb([-0.025, -0.035, -0.26], [-0.16, -0.2, 0.02], 0.027, 0.034, M.skin, arms)
  limb([-0.1, -0.13, -0.12], [-0.24, -0.32, 0.3], 0.04, 0.05, sleeveM, arms)

  return {
    root, gun, mag,
    muzzle: new THREE.Vector3(0, 0.004, -0.63),
    sightY: 0.068,
    hip: new THREE.Vector3(0.15, -0.2, -0.5),
    ads: new THREE.Vector3(0, -0.068, -0.5),
    ejectPort: new THREE.Vector3(0.03, 0.02, -0.06),
    magRest: mag.position.clone()
  }
}

function buildPistol (sleeve) {
  const root = new THREE.Group()
  const gun = new THREE.Group()
  root.add(gun)
  box(0.027, 0.032, 0.2, M.steel, 0, 0, -0.06, gun) // slide
  box(0.025, 0.02, 0.17, M.steelLight, 0, -0.024, -0.05, gun) // frame
  cylZ(0.008, 0.02, M.steel, 0, 0.002, -0.165, gun)
  box(0.006, 0.01, 0.01, M.steel, 0, 0.021, -0.15, gun) // front sight
  box(0.018, 0.01, 0.01, M.steel, 0, 0.021, 0.03, gun) // rear sight
  const grip = box(0.03, 0.11, 0.05, M.woodDark, 0, -0.08, 0.02, gun)
  grip.rotation.x = 0.22
  box(0.006, 0.006, 0.05, M.steel, 0, -0.045, -0.04, gun)
  const mag = new THREE.Group()
  mag.position.set(0, -0.13, 0.03)
  box(0.022, 0.012, 0.035, M.steel, 0, 0, 0, mag)
  gun.add(mag)
  box(0.012, 0.012, 0.02, M.steel, 0, 0.012, 0.045, gun) // hammer

  const arms = new THREE.Group()
  root.add(arms)
  const sleeveM = mat(sleeve, { roughness: 0.95 })
  const rh = hand(0.004, -0.075, 0.03, 0.22, M.skin, arms)
  rh.scale.setScalar(0.95)
  limb([0.01, -0.09, 0.06], [0.11, -0.2, 0.4], 0.027, 0.035, M.skin, arms)
  limb([0.06, -0.15, 0.24], [0.16, -0.3, 0.6], 0.04, 0.05, sleeveM, arms)
  const lh = hand(-0.025, -0.08, 0.02, 0.3, M.skin, arms)
  lh.rotation.z = -0.4
  limb([-0.03, -0.09, 0.05], [-0.15, -0.21, 0.38], 0.027, 0.035, M.skin, arms)
  limb([-0.1, -0.16, 0.22], [-0.2, -0.32, 0.58], 0.04, 0.05, sleeveM, arms)

  return {
    root, gun, mag,
    muzzle: new THREE.Vector3(0, 0.002, -0.18),
    sightY: 0.026,
    hip: new THREE.Vector3(0.13, -0.16, -0.42),
    ads: new THREE.Vector3(0, -0.026, -0.5),
    ejectPort: new THREE.Vector3(0.016, 0.018, -0.04),
    magRest: mag.position.clone()
  }
}

function flashTexture () {
  const c = document.createElement('canvas')
  c.width = c.height = 128
  const g = c.getContext('2d')
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64)
  grd.addColorStop(0, 'rgba(255,250,220,1)')
  grd.addColorStop(0.25, 'rgba(255,200,90,0.9)')
  grd.addColorStop(0.6, 'rgba(255,120,30,0.25)')
  grd.addColorStop(1, 'rgba(255,90,0,0)')
  g.fillStyle = grd
  g.translate(64, 64)
  for (let i = 0; i < 6; i++) {
    g.rotate(Math.PI / 3)
    g.beginPath(); g.moveTo(-6, 0); g.lineTo(0, -62); g.lineTo(6, 0); g.fill()
  }
  g.beginPath(); g.arc(0, 0, 26, 0, Math.PI * 2); g.fill()
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

export class Viewmodel {
  constructor () {
    this.scene = new THREE.Scene()
    this.camera = new THREE.PerspectiveCamera(58, 1, 0.01, 10)
    this.scene.add(new THREE.HemisphereLight('#e4ecf4', '#5a5040', 1.4))
    const key = new THREE.DirectionalLight('#fff0d8', 2.2)
    key.position.set(-0.6, 1, 0.4)
    this.scene.add(key)
    this.holder = new THREE.Group()
    this.scene.add(this.holder)

    const ft = flashTexture()
    const fm = new THREE.MeshBasicMaterial({ map: ft, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false })
    this.flash = new THREE.Group()
    const front = new THREE.Mesh(new THREE.PlaneGeometry(0.16, 0.16), fm)
    const side1 = new THREE.Mesh(new THREE.PlaneGeometry(0.1, 0.26), fm)
    side1.rotation.x = Math.PI / 2; side1.position.z = -0.1
    const side2 = side1.clone(); side2.rotation.y = Math.PI / 2
    this.flash.add(front, side1, side2)
    this.flash.visible = false
    this.flashT = 0

    this.shells = []
    const sg = new THREE.CylinderGeometry(0.0035, 0.0035, 0.014, 6)
    sg.rotateZ(Math.PI / 2)
    for (let i = 0; i < 10; i++) {
      const s = new THREE.Mesh(sg, M.brass)
      s.visible = false
      this.scene.add(s)
      this.shells.push({ mesh: s, v: new THREE.Vector3(), t: 0 })
    }
    this.shellIdx = 0

    this.models = null
    this.team = null
    this.current = null
    this.bobPhase = 0
    this.sway = new THREE.Vector2()
    this.kick = 0
    this.kickRot = 0
    this.landDip = 0
    this.visible = true
  }

  setTeam (team) {
    if (team === this.team) return
    this.team = team
    if (this.models) for (const m of Object.values(this.models)) this.holder.remove(m.root)
    const sleeve = UNIFORM[team] || UNIFORM.allies
    this.models = { rifle: buildRifle(sleeve), pistol: buildPistol(sleeve) }
    for (const m of Object.values(this.models)) {
      m.root.visible = false
      m.root.traverse((o) => { o.frustumCulled = false })
      this.holder.add(m.root)
    }
    this.current = null
  }

  resize (aspect) {
    this.camera.aspect = aspect
    this.camera.updateProjectionMatrix()
  }

  fire () {
    this.kick = Math.min(this.kick + 1, 1.6)
    this.flashT = 0.05
    this.flash.rotation.z = Math.random() * Math.PI
    const s = 0.75 + Math.random() * 0.5
    this.flash.scale.setScalar(this.current === 'pistol' ? s * 0.7 : s)
    // eject a shell from the port
    const m = this.models[this.current]
    const sh = this.shells[this.shellIdx++ % this.shells.length]
    m.gun.updateMatrixWorld(true)
    sh.mesh.position.copy(m.ejectPort).applyMatrix4(m.gun.matrixWorld)
    sh.v.set(0.7 + Math.random() * 0.3, 0.55 + Math.random() * 0.3, -0.1)
    sh.mesh.rotation.set(Math.random() * 3, Math.random() * 3, 0)
    sh.t = 0.45
    sh.mesh.visible = true
  }

  land (strength) { this.landDip = Math.min(1, this.landDip + strength) }

  // world-space muzzle position for tracers, given the main camera
  muzzleWorld (mainCamera, out) {
    const m = this.models[this.current]
    m.gun.updateMatrixWorld(true)
    out.copy(m.muzzle).applyMatrix4(m.gun.matrixWorld) // viewmodel camera space == main camera space
    return out.applyMatrix4(mainCamera.matrixWorld)
  }

  /**
   * s: { weapon, ads (0..1), speed, grounded, crouched, reloadFrac (-1 if none), drawFrac (0..1, 1 = holstered),
   *      lookDX, lookDY, dt, alive }
   */
  update (s) {
    const dt = s.dt
    if (s.weapon !== this.current) {
      if (this.current) this.models[this.current].root.visible = false
      this.current = s.weapon
      const m = this.models[this.current]
      m.root.visible = true
      m.gun.add(this.flash)
      this.flash.position.copy(m.muzzle)
    }
    const m = this.models[this.current]
    this.holder.visible = s.alive && this.visible

    // walk bob
    const moving = Math.min(1, s.speed / 5) * (s.grounded ? 1 : 0)
    this.bobPhase += dt * (5 + s.speed * 1.1) * (moving > 0.05 ? 1 : 0)
    const bobAmt = moving * (1 - 0.85 * s.ads)
    const bx = Math.sin(this.bobPhase) * 0.011 * bobAmt
    const by = -Math.abs(Math.cos(this.bobPhase)) * 0.009 * bobAmt
    // idle breathing
    const t = performance.now() / 1000
    const breathe = Math.sin(t * 1.6) * 0.0025 * (1 - 0.7 * s.ads)

    // sway lags behind mouse look
    const swayK = 1 - Math.exp(-10 * dt)
    this.sway.x += (THREE.MathUtils.clamp(-s.lookDX * 2.2, -0.06, 0.06) - this.sway.x) * swayK
    this.sway.y += (THREE.MathUtils.clamp(-s.lookDY * 2.2, -0.06, 0.06) - this.sway.y) * swayK
    const swayAmt = 1 - 0.75 * s.ads

    this.kick *= Math.exp(-16 * dt)
    this.landDip *= Math.exp(-7 * dt)
    if (this.flashT > 0) this.flashT -= dt
    this.flash.visible = this.flashT > 0 && this.holder.visible

    const pos = m.hip.clone().lerp(m.ads, s.ads)
    pos.x += bx + this.sway.x * 0.15 * swayAmt
    pos.y += by + breathe - this.landDip * 0.03 + this.sway.y * 0.12 * swayAmt
    pos.z += this.kick * (this.current === 'rifle' ? 0.035 : 0.045) * (1 - 0.4 * s.ads)
    if (s.crouched) { pos.x -= 0.01 * (1 - s.ads); pos.y += 0.004 }

    let rx = this.kick * (this.current === 'rifle' ? 0.05 : 0.11) * (1 - 0.5 * s.ads) + this.sway.y * swayAmt
    let ry = this.sway.x * swayAmt + (1 - s.ads) * 0.03
    let rz = this.sway.x * 0.6 * swayAmt + Math.sin(this.bobPhase) * 0.01 * bobAmt

    // reload: tilt, drop mag, insert, return
    const r = s.reloadFrac
    if (r >= 0) {
      const tilt = Math.sin(Math.min(1, r / 0.18) * Math.PI / 2) * (r > 0.82 ? 1 - (r - 0.82) / 0.18 : 1)
      rz += tilt * (this.current === 'rifle' ? 0.55 : 0.35)
      rx += tilt * 0.18
      pos.y -= tilt * 0.035
      pos.x -= tilt * 0.03
      let magOff = 0
      if (r > 0.15 && r < 0.4) magOff = (r - 0.15) / 0.25
      else if (r >= 0.4 && r < 0.55) magOff = 1
      else if (r >= 0.55 && r < 0.75) magOff = 1 - (r - 0.55) / 0.2
      m.mag.position.copy(m.magRest)
      m.mag.position.y -= magOff * 0.25
      m.mag.visible = magOff < 0.98
    } else {
      m.mag.position.copy(m.magRest)
      m.mag.visible = true
    }

    // draw / holster
    const d = s.drawFrac
    pos.y -= d * d * 0.25
    rx -= d * 0.6

    m.root.position.copy(pos)
    m.root.rotation.set(rx, ry, rz)

    // shells
    for (const sh of this.shells) {
      if (sh.t <= 0) continue
      sh.t -= dt
      sh.v.y -= 6 * dt
      sh.mesh.position.addScaledVector(sh.v, dt * 0.35)
      sh.mesh.rotation.x += dt * 20
      sh.mesh.rotation.y += dt * 13
      if (sh.t <= 0) sh.mesh.visible = false
    }
  }

  render (renderer, fov) {
    if (!this.holder.visible) return
    this.camera.fov = fov
    this.camera.updateProjectionMatrix()
    renderer.clearDepth()
    renderer.render(this.scene, this.camera)
  }
}
