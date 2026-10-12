// The planted demolition charge: its model, and a lamp and beep that quicken as the fuse runs down.
import { buildBomb } from './gunmodels.js'

export class Bomb {
  constructor (scene, audio) {
    this.scene = scene
    this.audio = audio
    const { group, lamp } = buildBomb()
    group.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true } })
    this.mesh = group
    this.lamp = lamp
    this.planted = false
    this.explodeAt = 0
    this.nextBeep = 0
    this.flashUntil = 0
  }

  // msLeft: fuse remaining, or null to keep the current countdown
  place (pos, msLeft = null) {
    if (!this.planted) {
      this.planted = true
      this.mesh.rotation.y = Math.random() * Math.PI * 2
      this.scene.add(this.mesh)
      this.nextBeep = 0
    }
    this.mesh.position.set(pos[0], pos[1], pos[2])
    if (msLeft != null) this.explodeAt = performance.now() + msLeft
  }

  remove () {
    if (!this.planted) return
    this.planted = false
    this.scene.remove(this.mesh)
  }

  update () {
    if (!this.planted) return
    const now = performance.now()
    const left = Math.max(0, this.explodeAt - now) / 1000
    if (now >= this.nextBeep) {
      this.nextBeep = now + Math.max(0.12, Math.min(1, left / 25)) * 1000
      this.flashUntil = now + 90
      this.audio.bombBeep(this.mesh.position)
    }
    this.lamp.material.emissiveIntensity = now < this.flashUntil ? 4 : 0
  }
}
