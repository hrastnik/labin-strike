// 2.5D walkability grid baked from the Rapier map at startup + A* pathfinding for bots.
import { CHAR_GROUPS, BULLET_QUERY } from '../shared/physics.js'

const CELL = 0.5
const MAX_STEP = 0.45
const SQRT2 = Math.SQRT2

export class NavGrid {
  constructor (RAPIER, world, bounds, seeds) {
    this.R = RAPIER
    this.world = world
    this.x0 = bounds.min[0]
    this.z0 = bounds.min[2]
    this.w = Math.ceil((bounds.max[0] - bounds.min[0]) / CELL)
    this.h = Math.ceil((bounds.max[2] - bounds.min[2]) / CELL)
    const n = this.w * this.h
    this.walk = new Uint8Array(n)
    this.height = new Float32Array(n)
    this.clear = new Uint8Array(n) // distance-to-wall in cells (capped), used to prefer open ground
    this._bake()
    this._keepReachable(seeds)
    this._clearance()
  }

  idx (cx, cz) { return cz * this.w + cx }
  cellOf (x, z) {
    return [Math.floor((x - this.x0) / CELL), Math.floor((z - this.z0) / CELL)]
  }

  center (i) {
    const cx = i % this.w
    const cz = (i / this.w) | 0
    return [this.x0 + (cx + 0.5) * CELL, this.height[i], this.z0 + (cz + 0.5) * CELL]
  }

  _bake () {
    const R = this.R
    const shape = new R.Capsule(0.5, 0.42)
    const rot = { x: 0, y: 0, z: 0, w: 1 }
    const down = { x: 0, y: -1, z: 0 }
    for (let cz = 0; cz < this.h; cz++) {
      for (let cx = 0; cx < this.w; cx++) {
        const i = this.idx(cx, cz)
        const x = this.x0 + (cx + 0.5) * CELL
        const z = this.z0 + (cz + 0.5) * CELL
        const ray = new R.Ray({ x, y: 6, z }, down)
        const hit = this.world.castRay(ray, 12, true, undefined, CHAR_GROUPS)
        if (!hit || hit.timeOfImpact <= 0.001) continue
        const gy = 6 - hit.timeOfImpact
        this.height[i] = gy
        // capsule lifted slightly so kerbs/ramps do not count as obstacles
        const blocked = this.world.intersectionWithShape({ x, y: gy + 0.2 + 0.42 + 0.5, z }, rot, shape, undefined, CHAR_GROUPS)
        if (!blocked) this.walk[i] = 1
      }
    }
  }

  neighbors (i, out) {
    out.length = 0
    const cx = i % this.w
    const cz = (i / this.w) | 0
    const hy = this.height[i]
    for (let dz = -1; dz <= 1; dz++) {
      for (let dx = -1; dx <= 1; dx++) {
        if (!dx && !dz) continue
        const nx = cx + dx; const nz = cz + dz
        if (nx < 0 || nz < 0 || nx >= this.w || nz >= this.h) continue
        const j = this.idx(nx, nz)
        if (!this.walk[j] || Math.abs(this.height[j] - hy) > MAX_STEP) continue
        if (dx && dz && (!this.walk[this.idx(cx + dx, cz)] || !this.walk[this.idx(cx, cz + dz)])) continue
        out.push(j)
      }
    }
    return out
  }

  _keepReachable (seeds) {
    const seen = new Uint8Array(this.walk.length)
    const stack = []
    for (const s of seeds) {
      const i = this.nearestWalkable(s[0], s[2], 6)
      if (i >= 0 && !seen[i]) { seen[i] = 1; stack.push(i) }
    }
    const nb = []
    while (stack.length) {
      const i = stack.pop()
      for (const j of this.neighbors(i, nb)) if (!seen[j]) { seen[j] = 1; stack.push(j) }
    }
    let count = 0
    for (let i = 0; i < this.walk.length; i++) {
      if (this.walk[i] && !seen[i]) this.walk[i] = 0
      if (this.walk[i]) count++
    }
    this.walkableCount = count
    this.walkList = []
    for (let i = 0; i < this.walk.length; i++) if (this.walk[i]) this.walkList.push(i)
  }

  _clearance () {
    // multi-pass chamfer distance (cells) from non-walkable cells, capped at 6
    const { w, h } = this
    const d = this.clear
    for (let i = 0; i < d.length; i++) d[i] = this.walk[i] ? 6 : 0
    for (let pass = 0; pass < 6; pass++) {
      for (let cz = 1; cz < h - 1; cz++) {
        for (let cx = 1; cx < w - 1; cx++) {
          const i = cz * w + cx
          if (!d[i]) continue
          const m = Math.min(d[i - 1], d[i + 1], d[i - w], d[i + w]) + 1
          if (m < d[i]) d[i] = m
        }
      }
    }
  }

  isWalkable (x, z) {
    const [cx, cz] = this.cellOf(x, z)
    if (cx < 0 || cz < 0 || cx >= this.w || cz >= this.h) return false
    return !!this.walk[this.idx(cx, cz)]
  }

  nearestWalkable (x, z, radiusM = 4) {
    const [cx, cz] = this.cellOf(x, z)
    const r = Math.ceil(radiusM / CELL)
    let best = -1; let bd = Infinity
    for (let dz = -r; dz <= r; dz++) {
      for (let dx = -r; dx <= r; dx++) {
        const nx = cx + dx; const nz = cz + dz
        if (nx < 0 || nz < 0 || nx >= this.w || nz >= this.h) continue
        const j = this.idx(nx, nz)
        if (!this.walk[j]) continue
        const dd = dx * dx + dz * dz
        if (dd < bd) { bd = dd; best = j }
      }
    }
    return best
  }

  randomCell (rand = Math.random, filter) {
    for (let k = 0; k < 40; k++) {
      const i = this.walkList[(rand() * this.walkList.length) | 0]
      if (this.clear[i] >= 2 && (!filter || filter(this.center(i)))) return i
    }
    return this.walkList[(rand() * this.walkList.length) | 0]
  }

  // A* on the 8-connected grid; returns list of world points (smoothed) or null
  findPath (from, to, maxIter = 30000) {
    const start = this.nearestWalkable(from[0], from[2], 3)
    const goal = this.nearestWalkable(to[0], to[2], 4)
    if (start < 0 || goal < 0) return null
    if (start === goal) return [this.center(goal)]
    const n = this.walk.length
    if (!this._g || this._g.length !== n) {
      this._g = new Float32Array(n)
      this._parent = new Int32Array(n)
      this._stamp = new Uint32Array(n)
      this._closed = new Uint32Array(n)
      this._gen = 0
    }
    const gen = ++this._gen
    const g = this._g; const parent = this._parent; const stamp = this._stamp; const closed = this._closed
    const gw = this.w
    const gx = goal % gw; const gz = (goal / gw) | 0
    const heur = (i) => {
      const dx = Math.abs((i % gw) - gx); const dz = Math.abs(((i / gw) | 0) - gz)
      return (dx + dz) + (SQRT2 - 2) * Math.min(dx, dz)
    }
    const heap = new MinHeap()
    stamp[start] = gen; g[start] = 0; parent[start] = -1
    heap.push(start, heur(start))
    const nb = []
    let iter = 0
    let found = false
    while (heap.size && iter++ < maxIter) {
      const i = heap.pop()
      if (i === goal) { found = true; break }
      if (closed[i] === gen) continue
      closed[i] = gen
      const ix = i % gw; const iz = (i / gw) | 0
      for (const j of this.neighbors(i, nb)) {
        if (closed[j] === gen) continue
        const diag = (j % gw) !== ix && ((j / gw) | 0) !== iz
        // prefer cells away from walls so bots do not hug geometry
        const cost = (diag ? SQRT2 : 1) * (1 + (this.clear[j] < 2 ? 0.8 : 0))
        const ng = g[i] + cost
        if (stamp[j] !== gen || ng < g[j]) {
          stamp[j] = gen; g[j] = ng; parent[j] = i
          heap.push(j, ng + heur(j))
        }
      }
    }
    if (!found) return null
    const cells = []
    for (let c = goal; c !== -1; c = parent[c]) cells.push(c)
    cells.reverse()
    return this._smooth(cells)
  }

  // grid line walk: true if every cell on the segment is walkable with small height deltas
  _walkLine (a, b) {
    const ax = (a % this.w) + 0.5; const az = ((a / this.w) | 0) + 0.5
    const bx = (b % this.w) + 0.5; const bz = ((b / this.w) | 0) + 0.5
    const dist = Math.hypot(bx - ax, bz - az)
    const steps = Math.ceil(dist * 3)
    let prevH = this.height[a]
    for (let s = 1; s <= steps; s++) {
      const t = s / steps
      const x = ax + (bx - ax) * t; const z = az + (bz - az) * t
      for (const [ox, oz] of [[0, 0], [0.45, 0], [-0.45, 0], [0, 0.45], [0, -0.45]]) {
        const cx = Math.floor(x + ox); const cz = Math.floor(z + oz)
        const i = cz * this.w + cx
        if (!this.walk[i]) return false
      }
      const i = Math.floor(z) * this.w + Math.floor(x)
      if (Math.abs(this.height[i] - prevH) > MAX_STEP) return false
      prevH = this.height[i]
    }
    return true
  }

  _smooth (cells) {
    const out = []
    let anchor = 0
    while (anchor < cells.length - 1) {
      let far = anchor + 1
      for (let k = anchor + 2; k < cells.length; k++) {
        if (this._walkLine(cells[anchor], cells[k])) far = k
        else if (k - far > 6) break
      }
      out.push(this.center(cells[far]))
      anchor = far
    }
    return out
  }
}

class MinHeap {
  constructor () { this.items = []; this.prios = [] }
  get size () { return this.items.length }
  push (item, prio) {
    const it = this.items; const pr = this.prios
    it.push(item); pr.push(prio)
    let i = it.length - 1
    while (i > 0) {
      const p = (i - 1) >> 1
      if (pr[p] <= prio) break
      it[i] = it[p]; pr[i] = pr[p]
      i = p
    }
    it[i] = item; pr[i] = prio
  }

  pop () {
    const it = this.items; const pr = this.prios
    const top = it[0]
    const lastI = it.pop(); const lastP = pr.pop()
    if (it.length) {
      let i = 0
      const n = it.length
      while (true) {
        let c = 2 * i + 1
        if (c >= n) break
        if (c + 1 < n && pr[c + 1] < pr[c]) c++
        if (pr[c] >= lastP) break
        it[i] = it[c]; pr[i] = pr[c]
        i = c
      }
      it[i] = lastI; pr[i] = lastP
    }
    return top
  }
}

export { BULLET_QUERY }
