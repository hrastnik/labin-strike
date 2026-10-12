// Parked cars: Blender-modelled bodies from cars.glb (tools/blender/cars), placed at the map's CAR_ markers.
// Every model/LOD/group is one InstancedMesh, so a model costs 3 draw calls per LOD regardless of how many are parked.
//   <model>_<lod>_paint   white car paint, tinted per instance (instanceColor)
//   <model>_<lod>_opaque  atlas material (palette cells + licence plates; plate row picked per instance)
//   <model>_<lod>_glass   windows / lamp lenses (blended)
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'

const NEAR_N = 10          // closest cars drawn at full detail
const NEAR_DIST = 45       // ... if within this range (m)
const PLATE_V = 448 / 512  // plate strip height in the atlas (glTF v from the top), 4 rows
// plate u runs 0..0.5 (right edge exactly on 0.5); palette cell centres start at 0.5 + 32/1024, so test halfway
const PLATE_U_MAX = 0.5 + 16 / 1024
const GROUPS = ['paint', 'opaque', 'glass']

export async function loadCars (url, placements, renderer) {
  const loader = new GLTFLoader()
  loader.setMeshoptDecoder(MeshoptDecoder)
  const gltf = await loader.loadAsync(url)
  return new CarSystem(gltf, placements, renderer)
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
    const aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy())
    const src = {}
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return
      const m = /^(.+)_(\d)_(paint|opaque|glass)$/.exec(o.name)
      if (!m) return
      const [, model, lod, group] = m
      ;((src[model] ||= [])[+lod] ||= {})[group] = o
    })
    const byModel = {}
    for (const p of placements) {
      const model = src[p.model] ? p.model : Object.keys(src)[0]
      ;(byModel[model] ||= []).push(p)
    }
    this.models = []
    this.cars = []
    for (const [model, list] of Object.entries(byModel)) {
      const n = list.length
      const lods = src[model].map((groups) => {
        const out = {}
        for (const g of GROUPS) {
          const s = groups[g]
          if (!s) continue
          const mat = s.material
          for (const k of ['map', 'roughnessMap', 'metalnessMap']) if (mat[k]) mat[k].anisotropy = aniso
          if (g === 'paint') mat.color.setRGB(1, 1, 1)
          if (g === 'opaque' && mat.map && !mat.userData.plates) { patchPlates(mat); mat.userData.plates = true }
          if (g === 'glass') { mat.transparent = true; mat.depthWrite = false }
          const geo = s.geometry
          if (g === 'opaque') geo.setAttribute('plateRow', new THREE.InstancedBufferAttribute(new Float32Array(n), 1))
          const im = new THREE.InstancedMesh(geo, mat, n)
          im.name = s.name
          im.count = 0
          im.frustumCulled = false
          im.castShadow = g !== 'glass'
          im.receiveShadow = true
          if (g === 'paint') im.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3)
          this.add(im)
          out[g] = im
        }
        return out
      })
      const entry = { model, lods, cars: list }
      this.models.push(entry)
      for (const p of list) this.cars.push(p)
    }
    this._t = 0
    this._near = null
    this._last = new THREE.Vector3(1e9, 0, 0)
    this._col = new THREE.Color()
    this.repack(new Set())
  }

  // nearest cars -> LOD0, the rest -> LOD1 (only re-packed when that set changes)
  update (camPos, dt = 0) {
    this._t -= dt
    if (this._t > 0 && camPos.distanceToSquared(this._last) < 4) return
    this._t = 0.25
    this._last.copy(camPos)
    const near = this.cars
      .map((c) => [c, c.position.distanceToSquared(camPos)])
      .filter(([, d]) => d < NEAR_DIST * NEAR_DIST)
      .sort((a, b) => a[1] - b[1])
      .slice(0, NEAR_N)
      .map(([c]) => c)
    const key = near.map((c) => c.id).sort((a, b) => a - b).join(',')
    if (key === this._near) return
    this._near = key
    this.repack(new Set(near))
  }

  repack (near) {
    for (const e of this.models) {
      const counts = e.lods.map(() => 0)
      for (const c of e.cars) {
        const lod = near.has(c) || e.lods.length === 1 ? 0 : 1
        const i = counts[lod]++
        const groups = e.lods[lod]
        for (const g of GROUPS) {
          const im = groups[g]
          if (!im) continue
          im.setMatrixAt(i, c.matrix)
          if (g === 'paint') im.setColorAt(i, this._col.setRGB(c.paint[0], c.paint[1], c.paint[2]))
          if (g === 'opaque') im.geometry.attributes.plateRow.setX(i, c.plate)
        }
      }
      e.lods.forEach((groups, lod) => {
        for (const g of GROUPS) {
          const im = groups[g]
          if (!im) continue
          im.count = counts[lod]
          im.instanceMatrix.needsUpdate = true
          if (im.instanceColor) im.instanceColor.needsUpdate = true
          if (g === 'opaque') im.geometry.attributes.plateRow.needsUpdate = true
        }
      })
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
