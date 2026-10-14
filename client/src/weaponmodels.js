// Blender-modelled weapons from weapons.glb (tools/blender/weapons). Per weapon <id>:
//   <id>.body, <id>.mag, <id>.bolt, <id>.cover, <id>.breakTop   first-person parts: pivot nodes with the (quantized) mesh as a child
//   <id>.lod                                                       merged + decimated, for third-person soldiers
//   <id>@muzzle, <id>@sight, <id>@eject, <id>@rh, <id>@lh, <id>@eye anchor empties
// Gun origin = trigger face on the bore axis, bore down -Z. Vertex colour COLOR_0 carries baked AO (r), edge wear (g)
// and cavity (b); materials carry their wear colour/roughness/metalness in userData.wear (glTF extras).
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'

const templates = new Map()
const CLIENT_KEYS = { magDir: 1, magHidden: 1, ejectDown: 1, lhRotZ: 1, reloadRoll: 1, kick: 1 }
// Aimed, the first-person camera of a gun narrows (a telephoto view of the gun alone) until its rear sight looks
// as big as it would REAR_SIGHT_LOOK from the eye at REAR_SIGHT_FOV: big enough to read the notch or aperture.
const REAR_SIGHT_LOOK = 0.05 // m
const REAR_SIGHT_FOV = 51.6 // degrees (vertical)

export async function loadWeaponModels (url) {
  const loader = new GLTFLoader()
  loader.setMeshoptDecoder(MeshoptDecoder)
  const gltf = await loader.loadAsync(url)
  const patched = new Map()
  gltf.scene.updateMatrixWorld(true)
  for (const o of [...gltf.scene.children]) {
    // GLTFLoader strips '.' from node names, so parts are identified by their extras (gun, part)
    const a = /^(\w+)@([a-z]+)/i.exec(o.name)
    const id = a ? a[1] : o.userData.gun
    const key = a ? a[2] : o.userData.part
    if (!id || !key) continue
    let t = templates.get(id)
    if (!t) templates.set(id, (t = { parts: {}, anchors: {}, lod: null }))
    if (a) { t.anchors[key] = o.position.clone(); continue }
    o.traverse((c) => {
      if (!c.isMesh) return
      const g = c.geometry
      if (g.attributes.color) { g.setAttribute('wpnCol', g.attributes.color); g.deleteAttribute('color') }
      c.material = patched.get(c.material) || patchMaterial(c.material, patched)
      c.userData.shared = true
    })
    if (key === 'lod') t.lod = o
    else t.parts[key] = o
    if (o.userData.client) t.client = JSON.parse(o.userData.client)
  }
  return templates
}

export const hasWeaponModel = (id) => templates.has(id)

// AO / wear / cavity from the baked vertex colours
function patchMaterial (src, cache) {
  const m = src.clone()
  m.vertexColors = false
  m.side = THREE.FrontSide
  const w = src.userData.wear || [0.3, 0.3, 0.3, 0.3, 1]
  const uWear = { value: new THREE.Vector3(w[0], w[1], w[2]) }
  const uWearRM = { value: new THREE.Vector2(w[3], w[4]) }
  m.onBeforeCompile = (sh) => {
    sh.uniforms.wearColor = uWear
    sh.uniforms.wearRM = uWearRM
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec3 wpnCol;\nvarying vec3 vWpn;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvWpn = wpnCol;')
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWpn;\nuniform vec3 wearColor;\nuniform vec2 wearRM;')
      .replace('#include <color_fragment>', `#include <color_fragment>
  float wpnWear = clamp(vWpn.g, 0.0, 1.0);
  diffuseColor.rgb = mix(diffuseColor.rgb, wearColor, wpnWear);
  diffuseColor.rgb *= 1.0 - 0.45 * clamp(vWpn.b, 0.0, 1.0);
  diffuseColor.rgb *= mix(1.0, vWpn.r, 0.35);`)
      .replace('#include <metalnessmap_fragment>', `#include <metalnessmap_fragment>
  roughnessFactor = mix(roughnessFactor, wearRM.x, wpnWear);
  metalnessFactor = mix(metalnessFactor, wearRM.y, wpnWear);`)
      .replace('#include <aomap_fragment>', `#include <aomap_fragment>
  reflectedLight.indirectDiffuse *= vWpn.r;
  reflectedLight.indirectSpecular *= mix(1.0, vWpn.r, 0.85);`)
  }
  m.customProgramCacheKey = () => 'wpn_baked'
  cache.set(src, m)
  return m
}

// Replace a procedural spec's meshes with the modelled ones; gameplay metadata (hip, kick, magDir...) stays.
// Returns false when there is no model for this id.
export function applyWeaponModel (id, spec) {
  const t = templates.get(id)
  if (!t || !t.parts.body) return false
  spec.gun.traverse((o) => { if (o.isMesh) o.geometry.dispose() })
  const gun = new THREE.Group()
  gun.name = id
  for (const [k, o] of Object.entries(t.parts)) {
    const c = o.clone()
    gun.add(c)
    if (k !== 'body') spec.parts[k] = c
  }
  spec.gun = gun
  spec.mag = spec.parts.mag || new THREE.Group()
  delete spec.parts.mag
  if (!spec.mag.parent) gun.add(spec.mag)
  const a = t.anchors
  if (a.muzzle) spec.muzzle = a.muzzle.clone()
  if (a.sight) {
    spec.sightY = a.sight.y
    spec.sightX = a.sight.x
    spec.ads = new THREE.Vector3(-a.sight.x, -a.sight.y, spec.ads.z)
  }
  if (a.eye) spec.ads.z = -a.eye.z   // ADS puts the eye here (over the cheek rest), not at a fixed distance
  // seen from the cheek rest a real rear sight is a few pixels wide; magnify the gun instead of moving it closer, so
  // the receiver keeps its place below the sights
  if (a.sight && a.eye) {
    t.rearSightZ ??= rearSightBack(t.parts.body, a.sight)
    const d = a.eye.z - t.rearSightZ
    spec.adsViewFov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(REAR_SIGHT_FOV / 2)) * REAR_SIGHT_LOOK / d))
  }
  if (a.eject) spec.ejectPort = a.eject.clone()
  // long-arm hands only: pistols keep their fixed two-handed grip (no spec.rh / lh)
  if (a.rh && spec.rh) spec.rh = [spec.rh[0], a.rh.y, a.rh.z]
  if (a.lh && spec.lh) spec.lh = [spec.lh[0], a.lh.y, a.lh.z]
  // per-model gameplay overrides from the Blender model's META.client
  for (const [k, v] of Object.entries(t.client || {})) {
    if (k === 'hip') spec.hip = new THREE.Vector3(...v)
    else if (k in CLIENT_KEYS) spec[k] = v
  }
  spec.lod = t.lod
  spec.modelled = true
  return true
}

// z of the back face of the rear sight: the hindmost body vertex standing above the sight line near the sight anchor
// (the anchor marks the notch or aperture, which can sit a couple of centimetres into the sight's leaf or base)
function rearSightBack (body, sight) {
  const v = new THREE.Vector3()
  let back = sight.z
  body.updateMatrixWorld(true)
  body.traverse((o) => {
    if (!o.isMesh) return
    const pos = o.geometry.attributes.position
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld)
      if (v.y > sight.y + 0.001 && Math.abs(v.x - sight.x) < 0.025 && v.z > back && v.z < sight.z + 0.04) back = v.z
    }
  })
  return back
}

// Single-piece models (knives, grenade): a clone of all the model's parts, or null when it is not modelled.
export function modelClone (id) {
  const t = templates.get(id)
  if (!t || !t.parts.body) return null
  const g = new THREE.Group()
  for (const o of Object.values(t.parts)) g.add(o.clone())
  return g
}
