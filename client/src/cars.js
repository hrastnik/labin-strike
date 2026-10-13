// Parked cars: Blender-modelled bodies from cars.glb (tools/blender/cars), placed at the map's CAR_ markers.
// Every model/group is one InstancedMesh, so a model costs 3 draw calls regardless of how many are parked.
// Full detail only: there are no LODs (swapping them made the cars visibly pop).
//   <model>_paint   white car paint, tinted per instance (instanceColor)
//   <model>_opaque  atlas material (palette cells + licence plates; plate row picked per instance)
//   <model>_glass   windows / lamp lenses (blended)
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'

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
    for (const [model, list] of Object.entries(byModel)) {
      const n = list.length
      for (const g of GROUPS) {
        const s = src[model][g]
        if (!s) continue
        const mat = s.material
        for (const k of ['map', 'roughnessMap', 'metalnessMap']) if (mat[k]) mat[k].anisotropy = aniso
        if (g === 'paint') mat.color.setRGB(1, 1, 1)
        if (g === 'opaque' && mat.map && !mat.userData.plates) { patchPlates(mat); mat.userData.plates = true }
        if (g === 'glass') { mat.transparent = true; mat.depthWrite = false }
        const geo = s.geometry
        const im = new THREE.InstancedMesh(geo, mat, n)
        im.name = s.name
        im.frustumCulled = false
        im.castShadow = g !== 'glass'
        im.receiveShadow = true
        if (g === 'opaque') geo.setAttribute('plateRow', new THREE.InstancedBufferAttribute(new Float32Array(list.map((c) => c.plate)), 1))
        list.forEach((c, i) => {
          im.setMatrixAt(i, c.matrix)
          if (g === 'paint') im.setColorAt(i, col.setRGB(c.paint[0], c.paint[1], c.paint[2]))
        })
        this.add(im)
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
