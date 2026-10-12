// First-person weapon + arms, rendered in their own scene/camera pass so they never clip into walls.
import * as THREE from 'three'
import { WEAPONS, GRENADE, KNIFE } from '@shared/weapons.js'
import { M, buildViewmodel, buildGrenadeViewmodel, buildKnifeViewmodel } from './gunmodels.js'

const _m = new THREE.Matrix4()
const _m2 = new THREE.Matrix4()
const _q = new THREE.Quaternion()
const UNIFORM = { allies: '#5d6638', axis: '#5a6260' }

const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t) }
const RELEASE = GRENADE.windup / (GRENADE.windup + GRENADE.recover) // throwFrac at which the grenade leaves the hand
// throwing hand path: up from below, wound back beside the shoulder, then forward and away
const NADE_LOW = new THREE.Vector3(0.3, -0.62, -0.45)
const NADE_BACK = new THREE.Vector3(0.25, -0.17, -0.44)
const NADE_FWD = new THREE.Vector3(0.08, -0.12, -0.75)
const NADE_GONE = new THREE.Vector3(0.12, -0.75, -0.6)
const STRIKE = KNIFE.windup / (KNIFE.windup + KNIFE.recover) // knifeFrac at which the blade connects
// knife hand keyframes [knifeFrac, position, rotation]: raised on the right, then slashed flat across to the left
const KNIFE_KEYS = [
  [0, [0.34, -0.55, -0.38], [0.2, 0.1, -1.3]],
  [STRIKE * 0.65, [0.26, -0.12, -0.44], [0.6, 0.15, -1.3]],
  [STRIKE + 0.2, [-0.14, -0.22, -0.52], [-0.1, 0.9, -1.4]],
  [1, [-0.22, -0.65, -0.42], [-0.3, 1.0, -1.4]]
]

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

    // en-bloc clip thrown out of the M1 Garand
    this.clipFly = { mesh: new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.004, 0.05), M.steelLight), v: new THREE.Vector3(), t: 0 }
    this.clipFly.mesh.visible = false
    this.scene.add(this.clipFly.mesh)

    this.models = {} // weapon id -> built viewmodel (for the current team's sleeves)
    this.nadeVM = null
    this.knifeVM = null
    this.team = null
    this.current = null
    this.bobPhase = 0
    this.sway = new THREE.Vector2()
    this.kick = 0
    this.kickRot = 0
    this.landDip = 0
    this.lastCycle = -1
    this.visible = true
    this.scoped = false // hide the gun while looking through a scope
  }

  setTeam (team) {
    if (team === this.team) return
    this.team = team
    for (const m of Object.values(this.models)) this.holder.remove(m.root)
    this.models = {}
    this.current = null
    if (this.nadeVM) this.holder.remove(this.nadeVM.root)
    this.nadeVM = null
    if (this.knifeVM) this.holder.remove(this.knifeVM.root)
    this.knifeVM = null
  }

  model (id) {
    let m = this.models[id]
    if (!m) {
      m = buildViewmodel(id, UNIFORM[this.team] || UNIFORM.allies)
      m.root.visible = false
      m.root.traverse((o) => { o.frustumCulled = false })
      this.holder.add(m.root)
      this.models[id] = m
    }
    return m
  }

  // build ahead of time so switching weapons does not hitch
  prepare (ids) { for (const id of ids) this.model(id) }

  resize (aspect) {
    this.camera.aspect = aspect
    this.camera.updateProjectionMatrix()
  }

  fire () {
    const m = this.models[this.current]
    if (!m) return
    const fx = WEAPONS[this.current].fx
    this.kick = Math.min(this.kick + 1, 1.6)
    this.flashT = 0.05
    this.flash.rotation.z = Math.random() * Math.PI
    const s = 0.75 + Math.random() * 0.5
    this.flash.scale.setScalar(s * fx.flash)
    if (fx.eject === 'fire') this.eject(m)
  }

  // throw a spent case out of the ejection port
  eject (m) {
    const sh = this.shells[this.shellIdx++ % this.shells.length]
    m.gun.updateMatrixWorld(true)
    sh.mesh.position.copy(m.ejectPort).applyMatrix4(m.gun.matrixWorld)
    const side = m.ejectPort.x < -0.003 ? -1 : 1   // a port on the left (P38) throws cases to the left
    if (m.ejectDown) sh.v.set(side * (0.1 + Math.random() * 0.2), -0.6 - Math.random() * 0.3, 0)
    else sh.v.set(side * (0.7 + Math.random() * 0.3), 0.55 + Math.random() * 0.3, -0.1)
    sh.mesh.rotation.set(Math.random() * 3, Math.random() * 3, 0)
    sh.t = 0.45
    sh.mesh.visible = true
  }

  ping () {
    const m = this.models[this.current]
    if (!m) return
    const c = this.clipFly
    m.gun.updateMatrixWorld(true)
    c.mesh.position.copy(m.mag.position).applyMatrix4(m.gun.matrixWorld)
    c.v.set(0.15 + Math.random() * 0.1, 1.6, 0.1)
    c.t = 0.6
    c.mesh.visible = true
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
   * s: { weapon, ads (0..1), sprint (0..1), speed, grounded, crouched, reloadFrac (-1 if none), drawFrac (0..1, 1 = holstered),
   *      throwFrac (-1 if not throwing), knifeFrac (-1 if not knifing), cycleFrac (-1 if the bolt is not being worked), reloadSteps, mag (rounds loaded),
   *      lookDX, lookDY, dt, alive }
   */
  update (s) {
    const dt = s.dt
    if (s.weapon !== this.current) {
      if (this.current) this.models[this.current].root.visible = false
      this.current = s.weapon
      const m = this.model(this.current)
      m.root.visible = true
      m.gun.add(this.flash)
      this.flash.position.copy(m.muzzle)
      this.lastCycle = -1
    }
    const m = this.models[this.current]
    const w = WEAPONS[this.current]
    this.holder.visible = s.alive && this.visible && !this.scoped

    // walk bob
    const moving = Math.min(1, s.speed / 5) * (s.grounded ? 1 : 0)
    this.bobPhase += dt * (5 + s.speed * 1.1) * (moving > 0.05 ? 1 : 0)
    const bobAmt = moving * (1 - 0.85 * s.ads) * (2 - w.moveMul) * (1 + s.sprint) // heavy guns sway more
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
    pos.z += this.kick * m.kick.z * (1 - 0.4 * s.ads)
    if (s.crouched) { pos.x -= 0.01 * (1 - s.ads); pos.y += 0.004 }
    // sprint carry: muzzle down and across the chest
    pos.x -= 0.03 * s.sprint; pos.y -= 0.03 * s.sprint; pos.z += 0.02 * s.sprint

    let rx = this.kick * m.kick.rot * (1 - 0.5 * s.ads) + this.sway.y * swayAmt - 0.25 * s.sprint
    let ry = this.sway.x * swayAmt + (1 - s.ads) * 0.03 + 0.4 * s.sprint
    let rz = this.sway.x * 0.6 * swayAmt + Math.sin(this.bobPhase) * 0.01 * bobAmt + 0.15 * s.sprint

    // reset animated parts, then pose them for this frame
    m.mag.position.copy(m.magRest)
    m.mag.visible = !m.magHidden
    const bolt = m.parts.bolt
    if (bolt) { bolt.userData.rest ??= bolt.position.clone(); bolt.position.copy(bolt.userData.rest); bolt.rotation.z = 0 }
    if (m.parts.cover) m.parts.cover.rotation.x = 0
    if (m.parts.breakTop) m.parts.breakTop.rotation.x = 0
    if (w.reload.style === 'enbloc') m.mag.visible = s.mag > 0

    // working the bolt between shots: lift, back (case flies out), forward, down
    const c = s.cycleFrac
    if (c >= 0 && bolt) {
      const lift = smooth(0, 0.18, c) * (1 - smooth(0.72, 0.9, c))
      const back = smooth(0.18, 0.42, c) * (1 - smooth(0.48, 0.7, c))
      bolt.rotation.z = lift * 1.2
      bolt.position.z += back * 0.07
      const dip = Math.sin(Math.min(1, c / 0.9) * Math.PI)
      rz += dip * 0.12 * (1 - 0.6 * s.ads)
      pos.y -= dip * 0.015
      if (this.lastCycle < 0.42 && c >= 0.42 && w.fx.eject === 'bolt') this.eject(m)
    }
    this.lastCycle = c

    const r = s.reloadFrac
    if (r >= 0) {
      const style = w.reload.style
      const tilt = Math.sin(Math.min(1, r / 0.18) * Math.PI / 2) * (r > 0.82 ? 1 - (r - 0.82) / 0.18 : 1)
      rz += tilt * m.reloadRoll
      rx += tilt * (style === 'belt' ? 0.3 : 0.18)
      pos.y -= tilt * 0.035
      pos.x -= tilt * 0.03
      const dir = m.magDir
      const offset = (k) => {
        m.mag.position.set(m.magRest.x + dir[0] * k * 0.25, m.magRest.y + dir[1] * k * 0.25, m.magRest.z + dir[2] * k * 0.25)
      }
      if (style === 'mag') {
        // tilt, drop the magazine, insert a fresh one, return
        let magOff = 0
        if (r > 0.15 && r < 0.4) magOff = (r - 0.15) / 0.25
        else if (r >= 0.4 && r < 0.55) magOff = 1
        else if (r >= 0.55 && r < 0.75) magOff = 1 - (r - 0.55) / 0.2
        offset(magOff)
        m.mag.visible = magOff < 0.98 && !(m.magHidden && r < 0.4)
        // break-open revolver: barrel + cylinder tip muzzle-down about the hinge, the grip stays in the hand
        if (m.parts.breakTop) m.parts.breakTop.rotation.x = -0.7 * smooth(0.05, 0.18, r) * (1 - smooth(0.78, 0.9, r))
      } else if (style === 'enbloc') {
        // press a full clip down into the open action, then let the bolt slam home
        const k = 1 - smooth(0.3, 0.6, r)
        m.mag.visible = r > 0.25
        m.mag.position.y = m.magRest.y + k * 0.18
        if (bolt) bolt.position.z += 0.05 * (1 - smooth(0.7, 0.76, r))
      } else if (style === 'charger' || style === 'single') {
        // bolt up and back, push clips / rounds down one after another, bolt forward and down
        const open = smooth(0, 0.12, r) * (1 - smooth(0.86, 0.98, r))
        if (bolt) { bolt.rotation.z = Math.min(1, open * 2) * 1.2; bolt.position.z += smooth(0.06, 0.14, r) * (1 - smooth(0.86, 0.94, r)) * 0.07 }
        const steps = Math.max(1, s.reloadSteps)
        const k = (r - 0.15) / 0.68
        if (k > 0 && k < 1) {
          const ph = (k * steps) % 1
          m.mag.visible = true
          m.mag.position.y = m.magRest.y + 0.12 * (1 - smooth(0.25, 0.85, ph))
        }
        rz += open * 0.15
      } else if (style === 'belt') {
        // flip the feed cover up, swap the belt box, close the cover, charge
        if (m.parts.cover) m.parts.cover.rotation.x = -1.1 * smooth(0.08, 0.22, r) * (1 - smooth(0.68, 0.8, r))
        let k = 0
        if (r > 0.25 && r < 0.42) k = (r - 0.25) / 0.17
        else if (r >= 0.42 && r < 0.48) k = 1
        else if (r >= 0.48 && r < 0.64) k = 1 - (r - 0.48) / 0.16
        offset(k)
        m.mag.visible = k < 0.98
        pos.z += smooth(0.86, 0.92, r) * (1 - smooth(0.92, 0.98, r)) * 0.03
      }
    }

    // draw / holster (the gun also drops out of the way while a grenade is thrown or the knife is out)
    const tf = s.throwFrac
    const kf = s.knifeFrac
    const d = Math.max(s.drawFrac, tf >= 0 ? smooth(0, 0.3, tf) : 0, kf >= 0 ? smooth(0, STRIKE, kf) * (1 - smooth(0.7, 1, kf)) : 0)
    pos.y -= d * d * 0.25
    rx -= d * 0.6

    m.root.position.copy(pos)
    m.root.rotation.set(rx, ry, rz)
    this.poseGrenade(tf)
    this.poseKnife(kf)

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
    const cf = this.clipFly
    if (cf.t > 0) {
      cf.t -= dt
      cf.v.y -= 6 * dt
      cf.mesh.position.addScaledVector(cf.v, dt * 0.35)
      cf.mesh.rotation.x += dt * 14
      if (cf.t <= 0) cf.mesh.visible = false
    }
  }

  poseGrenade (tf) {
    if (tf < 0) { if (this.nadeVM) this.nadeVM.root.visible = false; return }
    if (!this.nadeVM) {
      this.nadeVM = buildGrenadeViewmodel(UNIFORM[this.team] || UNIFORM.allies)
      this.nadeVM.root.traverse((o) => { o.frustumCulled = false })
      this.holder.add(this.nadeVM.root)
    }
    const { root, nade } = this.nadeVM
    root.visible = true
    if (tf < RELEASE) {
      const k = smooth(0, 1, tf / RELEASE)
      root.position.lerpVectors(NADE_LOW, NADE_BACK, k)
      root.rotation.set(0.05 + 0.3 * k, -0.2, -0.15 * k)
      nade.visible = true
    } else {
      const k = (tf - RELEASE) / (1 - RELEASE)
      const a = smooth(0, 0.35, k)
      root.position.lerpVectors(NADE_BACK, NADE_FWD, a).lerp(NADE_GONE, smooth(0.35, 1, k))
      root.rotation.set(0.35 - 0.8 * a, -0.2, -0.15)
      nade.visible = false
    }
  }

  poseKnife (kf) {
    if (kf < 0) { if (this.knifeVM) this.knifeVM.root.visible = false; return }
    if (!this.knifeVM) {
      this.knifeVM = buildKnifeViewmodel(this.team, UNIFORM[this.team] || UNIFORM.allies)
      this.knifeVM.root.traverse((o) => { o.frustumCulled = false })
      this.holder.add(this.knifeVM.root)
    }
    const root = this.knifeVM.root
    root.visible = true
    let i = 0
    while (i < KNIFE_KEYS.length - 2 && kf >= KNIFE_KEYS[i + 1][0]) i++
    const [f0, p0, r0] = KNIFE_KEYS[i]
    const [f1, p1, r1] = KNIFE_KEYS[i + 1]
    const k = smooth(f0, f1, kf)
    const mix = (a, b, j) => a[j] + (b[j] - a[j]) * k
    root.position.set(mix(p0, p1, 0), mix(p0, p1, 1), mix(p0, p1, 2))
    root.rotation.set(mix(r0, r1, 0), mix(r0, r1, 1), mix(r0, r1, 2))
  }

  // `world`/`worldCamera`: the main scene's sky light is reused, rotated so reflections stay fixed to the world
  render (renderer, fov, world, worldCamera) {
    if (!this.holder.visible) return
    if (world?.environment) {
      const sc = this.scene
      sc.environment = world.environment
      sc.environmentIntensity = world.environmentIntensity
      _m.makeRotationFromEuler(world.environmentRotation)
      _q.copy(worldCamera.quaternion).invert()
      sc.environmentRotation.setFromRotationMatrix(_m.premultiply(_m2.makeRotationFromQuaternion(_q)))
    }
    this.camera.fov = fov
    this.camera.updateProjectionMatrix()
    renderer.clearDepth()
    renderer.render(this.scene, this.camera)
  }
}
