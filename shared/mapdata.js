// Extracts gameplay data (colliders, spawns, bounds) from the map's glTF JSON.
// Collider nodes reference a unit cube (+-1), so a node's scale is the box half-extents.

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
  for (const node of gltf.nodes || []) {
    const name = node.name || ''
    const t = node.translation || [0, 0, 0]
    const r = node.rotation || [0, 0, 0, 1]
    const s = node.scale || [1, 1, 1]
    if (name.startsWith('COL_') || name.startsWith('CLIP_')) {
      colliders.push({
        name,
        clip: name.startsWith('CLIP_'),
        position: t,
        rotation: r,
        halfExtents: s.map(Math.abs)
      })
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
