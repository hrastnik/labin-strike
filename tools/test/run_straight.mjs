// Movement smoothness check: runs the shared character motor in straight lines across the map at
// 120 Hz and reports steps where horizontal progress collapses on open ground (ghost collisions).
// node tools/test/run_straight.mjs
import fs from 'node:fs'
import RAPIER from '@dimforge/rapier3d-compat'
import { parseGlbJson, extractMapData } from '../../shared/mapdata.js'
import { buildMapWorld, CharacterMotor } from '../../shared/physics.js'

await RAPIER.init()
const buf = fs.readFileSync(new URL('../../client/public/assets/maps/parking_lot.glb', import.meta.url))
const map = extractMapData(parseGlbJson(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)))
const world = buildMapWorld(RAPIER, map)
const motor = new CharacterMotor(RAPIER, world)
const DT = 1 / 120
const SPEED = 5

// [start x, z, direction x, z, seconds]
const runs = (process.argv[2] ? JSON.parse(process.argv[2]) : [
  [54.2, 28.5, -1, 0, 1.6],
  [40, 2, -1, 0, 6], [40, -2, -1, 0, 6], [-10, 6, 1, 0, 6], [-30, -6, 1, 0, 4],
  [0, -10, 0, 1, 3], [20, -12, 0, 1, 3], [-50, -15, 0.7, 0.7, 3], [30, 20, -0.7, -0.7, 4]
])
let totalDrops = 0; let totalSteps = 0
for (const [x, z, dx, dz, secs] of runs) {
  motor.setPosition(x, 3, z)
  for (let i = 0; i < 240; i++) motor.step(DT, 0, 0, false) // settle onto the ground
  const n = Math.hypot(dx, dz)
  let drops = 0; let stuck = false; let still = 0
  const events = []
  for (let i = 0; i < 60 * secs * 2; i++) {
    const px = motor.pos.x; const pz = motor.pos.z
    motor.step(DT, (dx / n) * SPEED, (dz / n) * SPEED, false)
    const v = Math.hypot(motor.pos.x - px, motor.pos.z - pz) / DT
    totalSteps++
    still = v < 0.05 ? still + 1 : 0
    if (still > 60) { stuck = true; drops -= 60; break } // half a second without moving: a real wall
    if (i > 30 && v < SPEED * 0.8) {
      drops++
      if (events.length < 6) events.push(`(${motor.pos.x.toFixed(2)}, ${motor.pos.y.toFixed(2)}, ${motor.pos.z.toFixed(2)}) v=${v.toFixed(2)}`)
    }
  }
  totalDrops += drops
  console.log(`run from (${x}, ${z}) dir (${dx}, ${dz}): ${drops} slow steps${stuck ? ` (wall at ${motor.pos.x.toFixed(2)}, ${motor.pos.z.toFixed(2)})` : ''} ${events.join(' ')}`)
}
console.log(`total slow steps ${totalDrops}/${totalSteps}`)
