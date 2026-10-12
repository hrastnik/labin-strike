// Ammunition cans left where soldiers fell. The server places them, hands them out and removes them.
import { buildAmmoCan } from './gunmodels.js'

const BLINK = 5 // seconds left on the ground when the can starts blinking

export class Drops {
  constructor (scene) {
    this.scene = scene
    this.live = new Map() // drop id -> { mesh, expireAt }
    this.templates = {}
    for (const team of ['allies', 'axis']) {
      const t = buildAmmoCan(team)
      t.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true } })
      this.templates[team] = t
    }
  }

  // { i: id, p: ground position, t: team of the fallen soldier, ttl: ms until it despawns }
  add ({ i, p, t, ttl }) {
    this.remove(i)
    const mesh = (this.templates[t] || this.templates.allies).clone()
    mesh.position.set(p[0], p[1], p[2])
    mesh.rotation.set(0, Math.random() * Math.PI * 2, (Math.random() - 0.5) * 0.08)
    this.scene.add(mesh)
    this.live.set(i, { mesh, expireAt: performance.now() + ttl })
  }

  remove (i) {
    const d = this.live.get(i)
    if (!d) return
    this.scene.remove(d.mesh)
    this.live.delete(i)
  }

  clear () { for (const i of [...this.live.keys()]) this.remove(i) }

  update () {
    const now = performance.now()
    for (const [i, d] of this.live) {
      const left = (d.expireAt - now) / 1000
      if (left < -2) { this.remove(i); continue } // the server's removal never reached us
      // blinks faster as it runs out
      d.mesh.visible = left > BLINK || Math.floor(now / (left > 2 ? 250 : 120)) % 2 === 0
    }
  }
}
