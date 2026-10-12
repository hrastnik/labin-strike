// Grenades in flight. Each one replays the server's simulation from the same throw; the server's 'boom' removes it.
import * as THREE from 'three'
import { GRENADE } from '@shared/weapons.js'
import { NADE_DT, createGrenade, stepGrenade } from '@shared/grenade.js'
import { buildGrenade } from './gunmodels.js'

export class Grenades {
  constructor (scene, RAPIER, world) {
    this.scene = scene
    this.R = RAPIER
    this.world = world
    this.live = new Map() // `${thrower id}:${throw number}` -> grenade
    this.template = buildGrenade()
    this.template.traverse((o) => { if (o.isMesh) o.castShadow = true })
  }

  // dir: null when it fell from the hand; fuse: ms left until it goes off
  spawn (key, origin, dir, fuse = GRENADE.fuse * 1000) {
    this.remove(key)
    const mesh = this.template.clone()
    mesh.rotation.order = 'YXZ'
    mesh.rotation.y = dir ? Math.atan2(-dir[0], -dir[2]) : Math.random() * Math.PI * 2
    mesh.position.set(...origin)
    mesh.visible = !dir
    this.scene.add(mesh)
    const g = createGrenade(origin, dir)
    this.live.set(key, { ...g, origin, prev: origin.slice(), acc: 0, mesh, expireAt: performance.now() + fuse + 2000 })
  }

  // returns the last simulated position, or null if the grenade was not known here
  remove (key) {
    const g = this.live.get(key)
    if (!g) return null
    this.scene.remove(g.mesh)
    this.live.delete(key)
    return g.pos
  }

  clear () { for (const key of [...this.live.keys()]) this.remove(key) }

  // onBounce(position, impact speed)
  update (dt, onBounce) {
    const now = performance.now()
    for (const [key, g] of this.live) {
      if (now > g.expireAt) { this.remove(key); continue } // the blast never reached us
      g.acc += dt
      while (g.acc >= NADE_DT) {
        g.acc -= NADE_DT
        g.prev[0] = g.pos[0]; g.prev[1] = g.pos[1]; g.prev[2] = g.pos[2]
        const impact = stepGrenade(this.R, this.world, g)
        if (impact > 1.5) onBounce?.(new THREE.Vector3(...g.pos), impact)
      }
      // it leaves from the thrower's eye: keep it hidden until it is out of their face
      g.mesh.visible ||= Math.hypot(g.pos[0] - g.origin[0], g.pos[1] - g.origin[1], g.pos[2] - g.origin[2]) > 1
      const a = g.acc / NADE_DT
      g.mesh.position.set(g.prev[0] + (g.pos[0] - g.prev[0]) * a, g.prev[1] + (g.pos[1] - g.prev[1]) * a, g.prev[2] + (g.pos[2] - g.prev[2]) * a)
      // tumble end over end in flight, lie on its side once it settles
      const r = g.mesh.rotation
      if (g.rest) r.x += (Math.round((r.x - Math.PI / 2) / Math.PI) * Math.PI + Math.PI / 2 - r.x) * Math.min(1, dt * 12)
      else r.x -= dt * 11
    }
  }
}
