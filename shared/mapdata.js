// Extracts gameplay data (colliders, spawns, bounds) from the map's glTF JSON.
// Box collider nodes reference a unit cube (+-1), so a node's scale is the box half-extents.
// Hull collider nodes (extras.hull) are convex hulls fitted to the rendered geometry (cars, trunks, bushes):
// node-local points in mm, inline or shared from a HULL_<key> node's extras.pts (every car of a model).

export function parseGlbJson (arrayBuffer) {
  const dv = new DataView(arrayBuffer)
  if (dv.getUint32(0, true) !== 0x46546c67) throw new Error('Not a GLB file')
  const jsonLen = dv.getUint32(12, true)
  const jsonBytes = new Uint8Array(arrayBuffer, 20, jsonLen)
  return JSON.parse(new TextDecoder().decode(jsonBytes))
}

export function extractMapData (gltf) {
  const colliders = []
  const spawns = { allies: [], axis: [] }
  const bounds = { min: [-50, -1, -50], max: [50, 20, 50] }
  const mm = (pts) => Float32Array.from(pts, (v) => v / 1000)
  const hulls = {}
  for (const node of gltf.nodes || []) {
    if (node.name?.startsWith('HULL_') && node.extras?.pts) hulls[node.name.slice(5)] = mm(node.extras.pts)
  }
  for (const node of gltf.nodes || []) {
    const name = node.name || ''
    const t = node.translation || [0, 0, 0]
    const r = node.rotation || [0, 0, 0, 1]
    const s = node.scale || [1, 1, 1]
    if (name.startsWith('COL_') || name.startsWith('CLIP_')) {
      const clip = name.startsWith('CLIP_')
      const h = node.extras?.hull
      if (h) {
        const hull = typeof h === 'string' ? hulls[h] : mm(h)
        if (hull) colliders.push({ name, clip, position: t, rotation: r, hull })
      } else {
        colliders.push({ name, clip, position: t, rotation: r, halfExtents: s.map(Math.abs) })
      }
    } else if (name.startsWith('SPAWN_')) {
      const team = name.split('_')[1]
      if (spawns[team]) spawns[team].push(t)
    } else if (name === 'BOUNDS_MIN' || name === 'BOUNDS_MAX') {
      bounds[name === 'BOUNDS_MIN' ? 'min' : 'max'] = t
    }
  }
  // glTF is Y-up with Blender's +Y mapped to -Z, so min/max can swap on Z
  const min = bounds.min.map((v, i) => Math.min(v, bounds.max[i]))
  const max = bounds.min.map((v, i) => Math.max(v, bounds.max[i]))
  return { colliders, spawns, bounds: { min, max } }
}
