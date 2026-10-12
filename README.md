# Labin Strike

A browser-based, low-poly multiplayer team deathmatch shooter set on **Rudarska ulica in Labin, Croatia**. The map is rebuilt from street-level references, and the gunplay is old-school: hitscan rifles, health that regenerates, and bots that fill empty slots.

![Aerial view of the Rudarska ulica map](docs/screenshots/overview.jpg)

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/gameplay.jpg" alt="In-game view with HUD and bots" /></td>
    <td width="50%"><img src="docs/screenshots/scoreboard.jpg" alt="Team Deathmatch scoreboard" /></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/menu.jpg" alt="Main menu" /></td>
    <td width="50%" valign="top">

**Allies vs Axis.** First team to 50 kills, or the leading team when the 10-minute timer runs out.

- StG 44 and M1911, each with its own spread, recoil, damage falloff and head/leg multipliers
- Aim down sights, crouch, jump, and spawn protection
- Health regenerates COD2-style after 5 s without taking damage
- Server-side bots fill the match up to 8 players. They use A* pathfinding, line-of-sight targeting and human-like aim error
- Killfeed, compass/minimap, hitmarkers, damage direction indicators

</td>
  </tr>
</table>

## Quick start

Requires **Node.js 20+**.

```bash
npm install
npm run dev          # http://localhost:7344
```

In dev, the Node server runs the game simulation and serves the client through Vite middleware, all on one port. Open the URL, pick a callsign and hit **Deploy**. Open a second tab to play against yourself, or let the bots handle it.

Handy URL params: `?name=Mateo` pre-fills the callsign and `?autojoin` deploys as soon as the map loads.

### Controls

| Key | Action | Key | Action |
| --- | --- | --- | --- |
| <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> | Move | Mouse | Aim |
| <kbd>LMB</kbd> | Fire | <kbd>RMB</kbd> | Aim down sights |
| <kbd>Space</kbd> | Jump | <kbd>C</kbd> / <kbd>Ctrl</kbd> | Crouch |
| <kbd>R</kbd> | Reload | <kbd>1</kbd> / <kbd>2</kbd> / <kbd>Q</kbd> | Rifle / pistol / last weapon |
| <kbd>Tab</kbd> | Scoreboard | <kbd>Esc</kbd> | Pause |

## How it works

```
client/   three.js renderer, input, HUD, viewmodel, audio, prediction   (Vite)
server/   authoritative TDM simulation, bots, nav grid, HTTP + signaling
shared/   constants, Rapier physics + character motor, hitboxes, map parsing
tools/    Blender build scripts for the map and cars, texture/sky generators
```

- **Networking.** [geckos.io](https://github.com/geckos-io/geckos.io) sends data over WebRTC data channels, so it behaves like UDP inside the browser. The server ticks at 30 Hz and sends snapshots at 20 Hz. Clients upload input at 30 Hz and interpolate remote players with a 110 ms buffer. HTTP and the WebRTC UDP mux share port **7344**, so one TCP+UDP firewall rule is enough.
- **Physics.** [Rapier](https://rapier.rs/) runs the same kinematic character motor on both sides: the client for the local player, the server for bots. Movement collides identically everywhere.
- **Hits.** Players have a head sphere plus body and leg capsules, defined in `shared/hitbox.js`. The client claims a hit, and the server checks the shooter's position, the target's position and line of sight before applying damage.
- **Map.** Colliders, spawns and car markers are stored as named nodes inside `parking_lot.glb`. Server and client both read them with `shared/mapdata.js`. The server bakes a 0.5 m walkability grid from the map at startup to give bots their pathfinding.
- **Cars.** Parked cars are instanced from `cars.glb`. Each model costs three draw calls per LOD (paint, opaque, glass), however many copies are on the map.

All gameplay tuning lives in [`shared/constants.js`](shared/constants.js): match rules, movement and the weapon stats.

## Production

```bash
npm run build        # builds the client into dist/
npm start            # NODE_ENV=production, serves dist/ + game on :7344
```

`server.sh {start|stop|restart|status}` runs the server as a detached background process with a pid file and `server.log`. `GET /healthz` returns server stats as JSON.

`deploy.sh` builds locally, rsyncs to a VPS, runs `npm ci --omit=dev` only when the lockfile changed, and restarts the server. Set the target in a gitignored `.deploy.env`:

```bash
DEPLOY_HOST=user@example.com
DEPLOY_DIR=/srv/labin-strike
```

Environment variables: `PORT` (default `7344`), `UDP_PORT_MIN` / `UDP_PORT_MAX` (default: same as `PORT`).

## Rebuilding assets

The map and cars are generated procedurally in Blender. Their output is committed, so you only need these steps to change the art.

```bash
# Map → client/public/assets/maps/parking_lot.glb
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/rudarska/build.py

# Procedural decals / foliage cards / resized PBR textures (needs Pillow + numpy)
python3 tools/blender/gen_textures.py

# Sky backdrop grading → client/public/assets/sky/sky.jpg
python3 tools/sky_src/grade_sky.py
```

The car models are built with `tools/blender/cars/` and exported to `client/public/assets/cars/cars.glb` by `export.py`.

`node tools/test/run_straight.mjs` is a movement check. It runs the character motor across the map in straight lines and reports places where you would snag on open ground.

## License

[MIT](LICENSE) © Mateo Hrastnik
