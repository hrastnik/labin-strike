// Static / dynamic split of the sun's shadow map.
// The map and the parked cars never move, yet drawing them into the 4096² shadow map every frame cost as much
// as the main pass (~2M triangles).  Their depth is rendered once into a cache.  Every frame only the casters that
// can move (players, cats, tanks, bikes, grenades, drops, the bomb) are drawn, on top of the previous frame's map with the
// tiles they covered last frame copied back from the cache (copying the whole 4096² map costs ~1 ms by itself).
// Same shadow map, same filtering, so the result is identical.
import * as THREE from 'three'

const TILES = 64                 // restore grid: TILES x TILES tiles over the shadow map
const PAD = 2                    // texels of slack around each caster's footprint
const _sphere = new THREE.Sphere()
const _v = new THREE.Vector3()
const _m = new THREE.Matrix4()

export class ShadowCache {
  constructor (renderer, light) {
    this.renderer = renderer
    this.light = light
    this.statics = new Set()   // meshes whose shadow lives in the cache (castShadow off between bakes)
    this.dirty = true
    this.bakedFor = null       // the shadow.map the cache was copied from (a quality change replaces it)
    this.onBake = null         // called before a bake (cars put every instance back)
    this.fbo = null
    this.rb = null
    this.size = [0, 0]
    this.prev = new Uint8Array(TILES * TILES)   // tiles moving casters were drawn into last frame
    this.next = new Uint8Array(TILES * TILES)
    this.scene = null
    const sm = renderer.shadowMap
    const render = sm.render
    sm.render = (lights, scene, camera) => {
      if (!this.statics.size || lights.length !== 1 || lights[0] !== light || !sm.enabled) return render.call(sm, lights, scene, camera)
      this.scene = scene
      const shadow = light.shadow
      if (this.dirty || !shadow.map || shadow.map !== this.bakedFor || !this.fits(shadow.map)) this.bake(render, lights, scene, camera)
      const clear = renderer.clear
      renderer.clear = () => this.restore()
      try { render.call(sm, lights, scene, camera) } finally { renderer.clear = clear }
    }
  }

  // meshes under these roots that cast shadows now are static from here on
  addStatic (...roots) {
    for (const r of roots) r.traverse((o) => { if (o.isMesh && o.castShadow) { this.statics.add(o); o.castShadow = false } })
    this.dirty = true
  }

  fits (map) {
    return this.size[0] === map.width && this.size[1] === map.height
  }

  // full shadow render of the static casters alone, then copy its depth into the cache
  bake (render, lights, scene, camera) {
    const moving = []
    scene.traverse((o) => { if (o.castShadow) { o.castShadow = false; moving.push(o) } })
    for (const o of this.statics) o.castShadow = true
    this.onBake?.()
    render.call(this.renderer.shadowMap, lights, scene, camera)
    for (const o of this.statics) o.castShadow = false
    for (const o of moving) o.castShadow = true
    const map = this.light.shadow.map
    const gl = this.renderer.getContext()
    if (!this.fits(map)) {
      if (this.rb) gl.deleteRenderbuffer(this.rb)
      this.fbo ||= gl.createFramebuffer()
      this.rb = gl.createRenderbuffer()
      gl.bindRenderbuffer(gl.RENDERBUFFER, this.rb)
      // three allocates the shadow DepthTexture (UnsignedIntType) as DEPTH_COMPONENT24; blits need the same format
      gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT24, map.width, map.height)
      gl.bindRenderbuffer(gl.RENDERBUFFER, null)
      this.size = [map.width, map.height]
      this.blit(this.fbo, null, null, () => gl.framebufferRenderbuffer(gl.DRAW_FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, this.rb))
    }
    this.blit(this.fbo, this.mapFbo(map), [[0, 0, map.width, map.height]])
    this.prev.fill(0)
    this.bakedFor = map
    this.dirty = false
  }

  // replaces the shadow pass's clear: erase last frame's moving casters by copying their tiles back from the cache
  restore () {
    const map = this.light.shadow.map
    const [W, H] = this.size
    const tw = W / TILES; const th = H / TILES
    const rects = []
    for (let j = 0; j < TILES; j++) {
      for (let i = 0; i < TILES; i++) {
        if (!this.prev[j * TILES + i]) continue
        const i0 = i
        while (i + 1 < TILES && this.prev[j * TILES + i + 1]) i++
        rects.push([i0 * tw, j * th, (i + 1) * tw, (j + 1) * th])
      }
    }
    if (rects.length) this.blit(this.mapFbo(map), this.fbo, rects)
    this.markMoving()
    this.renderer.setRenderTarget(map)
  }

  // tiles this frame's casters will be drawn into (bounding sphere footprint in the light's ortho view)
  markMoving () {
    const cam = this.light.shadow.camera
    const [W, H] = this.size
    const now = this.next.fill(0)
    _m.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse)
    const kx = cam.projectionMatrix.elements[0] * W / 2   // texels per world unit
    const ky = cam.projectionMatrix.elements[5] * H / 2
    const tw = W / TILES; const th = H / TILES
    const visit = (o) => {
      if (!o.visible) return
      if (o.castShadow && o.isMesh) {
        if (o.isInstancedMesh) now.fill(1)
        else {
          const g = o.geometry
          if (!g.boundingSphere) g.computeBoundingSphere()
          _sphere.copy(g.boundingSphere).applyMatrix4(o.matrixWorld)
          const r = _sphere.radius * (o.isSkinnedMesh ? 1.5 : 1)   // skinned bounds are the bind pose
          _v.copy(_sphere.center).applyMatrix4(_m)
          const cx = (_v.x * 0.5 + 0.5) * W; const cy = (_v.y * 0.5 + 0.5) * H
          const rx = r * kx + PAD; const ry = r * ky + PAD
          const i0 = Math.max(0, Math.floor((cx - rx) / tw)); const i1 = Math.min(TILES - 1, Math.floor((cx + rx) / tw))
          const j0 = Math.max(0, Math.floor((cy - ry) / th)); const j1 = Math.min(TILES - 1, Math.floor((cy + ry) / th))
          for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) now[j * TILES + i] = 1
        }
      }
      for (const c of o.children) visit(c)
    }
    visit(this.scene)
    this.next = this.prev
    this.prev = now
  }

  mapFbo (map) {
    return this.renderer.properties.get(map).__webglFramebuffer
  }

  // depth blit src -> dst through three's state tracker (so its idea of the bound framebuffers stays right)
  blit (dst, src, rects, attach) {
    const gl = this.renderer.getContext()
    const st = this.renderer.state
    st.bindFramebuffer(gl.DRAW_FRAMEBUFFER, dst)
    if (attach) attach()
    else {
      st.bindFramebuffer(gl.READ_FRAMEBUFFER, src)
      for (const [x0, y0, x1, y1] of rects) gl.blitFramebuffer(x0, y0, x1, y1, x0, y0, x1, y1, gl.DEPTH_BUFFER_BIT, gl.NEAREST)
      st.bindFramebuffer(gl.READ_FRAMEBUFFER, null)
    }
    st.bindFramebuffer(gl.DRAW_FRAMEBUFFER, null)
  }
}
