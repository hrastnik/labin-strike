// Scene, lighting, sky and map loading.
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'
import { carPlacement } from './cars.js'

// morning sun from the east (lights the teal building and the annex like the reference photos).
// map frame: +X runs SE along Rudarska, glTF -Z points NE; compass north is 58 deg CCW from -Z.
export const SUN_DIR = new THREE.Vector3(0.471, 0.707, -0.527).normalize()
// the HDRI's sun sits at azimuth 34.2 deg (three's equirect atan2(z, x)); rotate the sky so it lines up with SUN_DIR
const SKY_YAW = THREE.MathUtils.degToRad(34.2) - Math.atan2(SUN_DIR.z, SUN_DIR.x)

export function createRenderer (canvas, highQuality) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, highQuality ? 2 : 1.25))
  renderer.setSize(window.innerWidth, window.innerHeight, false)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.autoClear = false
  return renderer
}

export function createScene (renderer, highQuality) {
  const scene = new THREE.Scene()
  const horizon = new THREE.Color('#a9b3c2')
  scene.fog = new THREE.Fog(horizon, 140, 1150)
  scene.background = horizon
  scene.backgroundRotation.set(0, SKY_YAW, 0)
  scene.environmentRotation.set(0, SKY_YAW, 0)

  // photographed sky (equirect JPG) as backdrop, the matching HDR for image-based lighting
  new THREE.TextureLoader().load('/assets/sky/sky.jpg', (tex) => {
    tex.mapping = THREE.EquirectangularReflectionMapping
    tex.colorSpace = THREE.SRGBColorSpace
    tex.anisotropy = 4
    scene.background = tex
    scene.backgroundIntensity = 0.95
  })
  new HDRLoader().load('/assets/sky/sky_1k.hdr', (hdr) => {
    hdr.mapping = THREE.EquirectangularReflectionMapping
    const pmrem = new THREE.PMREMGenerator(renderer)
    scene.environment = pmrem.fromEquirectangular(hdr).texture
    pmrem.dispose()
    hdr.dispose()
  })
  scene.environmentIntensity = 0.55

  const hemi = new THREE.HemisphereLight('#cfe0f0', '#6b6450', 0.45)
  scene.add(hemi)

  const sun = new THREE.DirectionalLight('#fff1d8', 2.8)
  sun.position.copy(SUN_DIR).multiplyScalar(90)
  sun.castShadow = true
  const s = sun.shadow
  s.mapSize.set(highQuality ? 4096 : 2048, highQuality ? 4096 : 2048)
  s.camera.left = -90; s.camera.right = 90; s.camera.top = 60; s.camera.bottom = -60
  s.camera.near = 1; s.camera.far = 400
  s.bias = -0.0004
  s.normalBias = 0.04
  s.radius = 2.5
  scene.add(sun)
  scene.add(sun.target)

  return { scene, sun, hemi }
}

// Centres the sun's shadow frustum on the map (static) – keeps shadows sharp without per-frame updates.
// The ortho frustum is fitted to the playable box (plus tall stuff around it) in light space.
export function fitSunToBounds (sun, bounds) {
  const pad = 14
  const x0 = bounds.min[0] - pad; const x1 = bounds.max[0] + pad
  const z0 = bounds.min[2] - pad; const z1 = bounds.max[2] + pad
  const cx = (x0 + x1) / 2; const cz = (z0 + z1) / 2
  sun.target.position.set(cx, 0, cz)
  sun.position.set(cx, 0, cz).addScaledVector(SUN_DIR, 200)
  sun.target.updateMatrixWorld()
  sun.updateMatrixWorld()
  const cam = sun.shadow.camera
  cam.position.copy(sun.position)
  cam.lookAt(sun.target.position)
  cam.updateMatrixWorld()
  const inv = cam.matrixWorldInverse
  const v = new THREE.Vector3()
  let l = Infinity; let r = -Infinity; let b = Infinity; let t = -Infinity; let n = Infinity; let f = -Infinity
  for (const x of [x0, x1]) for (const y of [-1, 28]) for (const z of [z0, z1]) {
    v.set(x, y, z).applyMatrix4(inv)
    l = Math.min(l, v.x); r = Math.max(r, v.x); b = Math.min(b, v.y); t = Math.max(t, v.y)
    n = Math.min(n, -v.z); f = Math.max(f, -v.z)
  }
  cam.left = l; cam.right = r; cam.bottom = b; cam.top = t
  cam.near = Math.max(0.5, n - 20); cam.far = f + 20
  cam.updateProjectionMatrix()
}

// Downloads the GLB once; the same bytes feed both the renderer (GLTFLoader) and the collision world.
export async function fetchMap (url, onProgress) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Map download failed (${res.status})`)
  const total = Number(res.headers.get('content-length')) || 0
  if (!res.body || !total) return res.arrayBuffer()
  const reader = res.body.getReader()
  const out = new Uint8Array(total)
  let got = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    if (got + value.length > out.length) return concatRest(out, got, value, reader)
    out.set(value, got)
    got += value.length
    onProgress?.(got / total)
  }
  return out.buffer.slice(0, got)
}

// content-length can be the compressed size; fall back to growing the buffer
async function concatRest (head, got, value, reader) {
  const chunks = [head.subarray(0, got), value]
  for (;;) {
    const { done, value: v } = await reader.read()
    if (done) break
    chunks.push(v)
  }
  const len = chunks.reduce((a, c) => a + c.length, 0)
  const out = new Uint8Array(len)
  let o = 0
  for (const c of chunks) { out.set(c, o); o += c.length }
  return out.buffer
}

export function parseMap (buffer, renderer) {
  const loader = new GLTFLoader()
  loader.setMeshoptDecoder(MeshoptDecoder)
  return new Promise((resolve, reject) => {
    loader.parse(buffer, '', (gltf) => resolve(prepareMap(gltf, renderer)), reject)
  })
}

// ground markings drawn with polygon offset (keep in sync with OVERLAY in tools/blender/rudarska/zfix.py)
const OVERLAY_RE = /road_paint|manhole|grate/
const TEX_SLOTS = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap', 'alphaMap']

function prepareMap (gltf, renderer) {
  const root = gltf.scene
  const remove = []
  const cars = []
  const aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy())
  root.updateMatrixWorld(true)
  root.traverse((o) => {
    const n = o.name || ''
    if (n.startsWith('CAR_')) {
      cars.push(carPlacement(o, cars.length))
      remove.push(o)
      return
    }
    if (n.startsWith('COL_') || n.startsWith('CLIP_') || n.startsWith('SPAWN_') || n.startsWith('BOUNDS_')) {
      remove.push(o)
      return
    }
    if (!o.isMesh) return
    const backdrop = isUnder(o, 'Backdrop')
    o.castShadow = !backdrop && !isUnder(o, 'Ground')
    o.receiveShadow = true
    const mats = Array.isArray(o.material) ? o.material : [o.material]
    for (const m of mats) {
      // anisotropic filtering on every map (normal maps at grazing angles sparkle without it)
      for (const k of TEX_SLOTS) if (m[k]) { m[k].anisotropy = aniso; m[k].needsUpdate = true }
      const name = m.name || ''
      if (name.includes('glass') || name.includes('gls')) {
        m.roughness = 0.12
        m.metalness = 0.4
        m.envMapIntensity = 1.5
      }
      if (/leaf|grass_card|leaves/.test(name)) patchFoliage(m)
      if (name.includes('_cut')) {
        // alpha-tested cards (leaves, grass, cut-out signs)
        m.transparent = false
        m.alphaTest = 0.45
        m.depthWrite = true
        m.side = THREE.DoubleSide
        m.alphaToCoverage = true
      } else if (OVERLAY_RE.test(name)) {
        // opaque markings lying a few mm above the ground: depth-offset so they never z-fight with it
        m.polygonOffset = true
        m.polygonOffsetFactor = -2
        m.polygonOffsetUnits = -4
      } else if (name.includes('_dec')) {
        // decals (graffiti, grime, blob shadows) lying on top of other surfaces
        m.transparent = true
        m.depthWrite = false
        m.polygonOffset = true
        m.polygonOffsetFactor = -2
        m.polygonOffsetUnits = -2
        m.side = THREE.FrontSide
      } else if (name.includes('leaves') || name.includes('pine')) {
        m.side = THREE.DoubleSide
        if (m.map) { m.alphaTest = 0.4; m.transparent = false }
      } else if (!name.includes('flag') && !name.includes('sign') && !name.includes('chair')) {
        m.side = THREE.FrontSide
      }
      if (backdrop) m.fog = true
    }
    if (mats.every((m) => (m.name || '').includes('_dec'))) o.castShadow = false
  })
  // backface-culling everything closed saves a lot of fill; flip back to double-sided if normals face inward
  for (const o of remove) o.parent?.remove(o)
  root.updateMatrixWorld(true)
  root.userData.cars = cars
  return root
}

// foliage: alpha cards seen edge-on pick up strong Fresnel sky reflections (grey-white sheen) on a dark
// albedo, so damp the specular terms and lift the ambient a little (light scattering through leaves)
function patchFoliage (m) {
  m.onBeforeCompile = (sh) => {
    sh.fragmentShader = sh.fragmentShader.replace('#include <aomap_fragment>', `reflectedLight.directSpecular *= 0.15;
  reflectedLight.indirectSpecular *= 0.1;
  reflectedLight.indirectDiffuse *= 1.3;
#include <aomap_fragment>`)
  }
  m.customProgramCacheKey = () => 'foliage'
}

function isUnder (o, name) {
  for (let p = o; p; p = p.parent) if (p.name === name) return true
  return false
}
