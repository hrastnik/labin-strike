// Parked cars: Blender-modelled bodies from cars.glb (tools/blender/cars), placed at the map's CAR_ markers.
// Every model/LOD/group is one InstancedMesh, so a model costs 2 draw calls per level in use plus 1 for its glass,
// regardless of how many are parked.  Each frame only the cars inside the view frustum are packed into the instance buffers (their shadows
// come from the static shadow cache, which bakes with every car shown at full detail).
//   <model>_paint   white car paint, tinted per instance (instanceColor)
//   <model>_opaque  atlas material (palette cells + licence plates; plate row picked per instance)
//   <model>_glass   windows / lamp lenses (blended)
// LODs of paint and opaque are simplified from the full model at load (meshopt: same vertices, fewer triangles, normals
// and uvs held in place), each with a known geometric error.  A car uses the coarsest level whose error projects to
// under MAX_PX_ERROR on screen, so swapping is invisible (hand-made low-detail models that dropped the interior used
// to pop).  The largest error stays within the sun's normalBias, so the full-detail cached shadow never darkens a
// simplified surface.
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'
import { MeshoptSimplifier } from 'three/addons/libs/meshopt_simplifier.module.js'

const PLATE_V = 448 / 512  // plate strip height in the atlas (glTF v from the top), 4 rows
// plate u runs 0..0.5 (right edge exactly on 0.5); palette cell centres start at 0.5 + 32/1024, so test halfway
const PLATE_U_MAX = 0.5 + 16 / 1024
const GROUPS = ['paint', 'opaque', 'glass']
const LOD_ERRORS = [0.006, 0.012, 0.025]  // m, the simplified levels after the full model
const MAX_PX_ERROR = 0.5
const _frustum = new THREE.Frustum()
const _pv = new THREE.Matrix4()
const _size = new THREE.Vector2()

export async function loadCars (url, placements, renderer) {
  const loader = new GLTFLoader()
  loader.setMeshoptDecoder(MeshoptDecoder)
  const [gltf] = await Promise.all([loader.loadAsync(url), MeshoptSimplifier.ready])
  return new CarSystem(gltf, placements, renderer)
}

// the full geometry plus one per LOD_ERRORS level, sharing its vertex buffers (only the index differs)
function simplifyLevels (geo) {
  const pos = geo.attributes.position
  const nrm = geo.attributes.normal
  const uv = geo.attributes.uv
  const n = pos.count
  // normals and uvs weigh in, so shading and atlas cells stay put (lighter normal weights visibly moved the paint's
  // sky reflections)
  const attr = new Float32Array(n * 5)
  for (let i = 0; i < n; i++) {
    attr[i * 5] = nrm.getX(i); attr[i * 5 + 1] = nrm.getY(i); attr[i * 5 + 2] = nrm.getZ(i)
    if (uv) { attr[i * 5 + 3] = uv.getX(i); attr[i * 5 + 4] = uv.getY(i) }
  }
  const index = new Uint32Array(geo.index.array)
  const levels = [geo]
  for (const err of LOD_ERRORS) {
    const [idx] = MeshoptSimplifier.simplifyWithAttributes(index, pos.array, 3, attr, 5, [2, 2, 2, 2, 2], null, 0, err, ['ErrorAbsolute'])
    const g = new THREE.BufferGeometry()
    for (const k in geo.attributes) g.setAttribute(k, geo.attributes[k])
    g.setIndex(new THREE.BufferAttribute(idx, 1))
    g.boundingSphere = geo.boundingSphere
    levels.push(g)
  }
  return levels
}

function patchPlates (m) {
  m.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float plateRow;')
      .replace('#include <uv_vertex>', `#include <uv_vertex>
#ifdef USE_MAP
  if (vMapUv.x < ${PLATE_U_MAX.toFixed(5)} && vMapUv.y < ${PLATE_V.toFixed(5)}) vMapUv.y += plateRow * ${(PLATE_V / 4).toFixed(5)};
#endif`)
  }
  m.customProgramCacheKey = () => 'car_plates'
}

export class CarSystem extends THREE.Group {
  constructor (gltf, placements, renderer) {
    super()
    this.name = 'Cars'
    this.renderer = renderer
    this.maxPxError = MAX_PX_ERROR
    const aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy())
    const src = {}
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return
      const m = /^(.+)_(paint|opaque|glass)$/.exec(o.name)
      if (!m) return
      const [, model, group] = m
      ;(src[model] ||= {})[group] = o
    })
    const byModel = {}
    for (const p of placements) {
      const model = src[p.model] ? p.model : Object.keys(src)[0]
      ;(byModel[model] ||= []).push(p)
    }
    const col = new THREE.Color()
    this.models = []
    for (const [model, list] of Object.entries(byModel)) {
      const n = list.length
      const entry = { list, meshes: [], spheres: [], shown: null }
      for (const g of GROUPS) {
        const s = src[model][g]
        if (!s) continue
        const mat = s.material
        for (const k of ['map', 'roughnessMap', 'metalnessMap']) if (mat[k]) mat[k].anisotropy = aniso
        if (g === 'paint') mat.color.setRGB(1, 1, 1)
        if (g === 'opaque' && mat.map && !mat.userData.plates) { patchPlates(mat); mat.userData.plates = true }
        if (g === 'glass') { mat.transparent = true; mat.depthWrite = false }
        if (!s.geometry.boundingSphere) s.geometry.computeBoundingSphere()
        // full per-instance data to pack the visible cars from
        const full = {
          instanceMatrix: new Float32Array(n * 16),
          instanceColor: g === 'paint' ? new Float32Array(n * 3) : null,
          plateRow: g === 'opaque' ? new Float32Array(list.map((c) => c.plate)) : null
        }
        list.forEach((c, i) => {
          c.matrix.toArray(full.instanceMatrix, i * 16)
          if (full.instanceColor) col.setRGB(c.paint[0], c.paint[1], c.paint[2]).toArray(full.instanceColor, i * 3)
        })
        // glass keeps its full shape at every level: simplified lenses poked out through the cabin
        const levels = g === 'glass' ? [s.geometry] : simplifyLevels(s.geometry)
        levels.forEach((geo, lod) => {
          const im = new THREE.InstancedMesh(geo, mat, n)
          im.name = g === 'glass' ? s.name : `${s.name}_${lod}`
          im.frustumCulled = false
          im.castShadow = g !== 'glass'
          im.receiveShadow = true
          if (full.instanceColor) im.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3)
          if (full.plateRow) geo.setAttribute('plateRow', new THREE.InstancedBufferAttribute(new Float32Array(n), 1))
          this.add(im)
          const attrs = [[im.instanceMatrix, full.instanceMatrix], [im.instanceColor, full.instanceColor], [geo.attributes.plateRow, full.plateRow]]
          entry.meshes.push({ im, lod: g === 'glass' ? -1 : lod, attrs: attrs.filter(([a]) => a).map(([a, full]) => ({ a, full })) })
        })
        const bs = s.geometry.boundingSphere
        entry.radius = Math.max(entry.radius || 0, bs.center.length() + bs.radius)
      }
      entry.spheres = list.map((c) => new THREE.Sphere(new THREE.Vector3().setFromMatrixPosition(c.matrix), entry.radius * c.matrix.getMaxScaleOnAxis()))
      entry.scales = list.map((c) => c.matrix.getMaxScaleOnAxis())
      this.models.push(entry)
    }
  }

  // pack the cars visible from camera (null: all of them, at full detail) into the instance buffers of their LOD
  cull (camera) {
    // a level's error in metres times this, over the distance, is its error in pixels
    let pxPerM = 0
    if (camera) {
      _frustum.setFromProjectionMatrix(_pv.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse))
      pxPerM = this.renderer.getDrawingBufferSize(_size).y * camera.zoom / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2))
    }
    for (const e of this.models) {
      const shown = [[], ...LOD_ERRORS.map(() => [])]
      e.spheres.forEach((s, i) => {
        if (!camera) { shown[0].push(i); return }
        if (!_frustum.intersectsSphere(s)) return
        const d = Math.max(0.01, s.center.distanceTo(camera.position) - s.radius)
        let lod = 0
        while (lod < LOD_ERRORS.length && LOD_ERRORS[lod] * e.scales[i] * pxPerM / d < this.maxPxError) lod++
        shown[lod].push(i)
      })
      const key = shown.map((l) => l.join(',')).join('|')
      if (key === e.shown) continue
      e.shown = key
      const all = shown.flat()
      for (const { im, lod, attrs } of e.meshes) {
        const cars = lod < 0 ? all : shown[lod]
        for (const { a, full } of attrs) {
          const k = a.itemSize
          cars.forEach((i, j) => a.array.set(full.subarray(i * k, i * k + k), j * k))
          a.needsUpdate = true
        }
        im.count = cars.length
        im.visible = cars.length > 0
      }
    }
  }
}

// CAR_ marker nodes from the map GLB -> placements (removed from the scene graph by prepareMap)
export function carPlacement (o, id) {
  o.updateWorldMatrix(true, false)
  const position = new THREE.Vector3().setFromMatrixPosition(o.matrixWorld)
  const u = o.userData || {}
  return {
    id,
    model: u.car || 'hatch',
    paint: u.paint || [0.8, 0.8, 0.8],
    plate: u.plate || 0,
    matrix: o.matrixWorld.clone(),
    position
  }
}
