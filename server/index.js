// HTTP + Geckos.io entry point. Everything (static assets, WebRTC signaling) lives on one port.
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import geckos from '@geckos.io/server'
import { PORT } from '../shared/constants.js'
import { Game } from './game.js'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const PROD = process.env.NODE_ENV === 'production'
const port = Number(process.env.PORT || PORT)
// WebRTC data channels share one UDP port (geckos enables ICE UDP mux), by default the same number as
// the HTTP port, so a single TCP+UDP firewall rule for 7344 is enough
const UDP_MIN = Number(process.env.UDP_PORT_MIN || port)
const UDP_MAX = Number(process.env.UDP_PORT_MAX || UDP_MIN)

async function createStaticHandler () {
  if (!PROD) {
    const { createServer } = await import('vite')
    const vite = await createServer({
      configFile: path.join(ROOT, 'vite.config.js'),
      server: { middlewareMode: true, hmr: false },
      appType: 'spa'
    })
    console.log('[http] serving client through Vite dev middleware')
    return vite.middlewares
  }
  const dist = path.join(ROOT, 'dist')
  if (!fs.existsSync(path.join(dist, 'index.html'))) {
    throw new Error(`No production build found in ${dist}. Run "npm run build" first.`)
  }
  const { default: sirv } = await import('sirv')
  // Vite's content-hashed bundles never change; everything else (index.html, the map GLB, sky) must
  // revalidate via ETag so a deploy is picked up immediately (304 when unchanged)
  const hashed = /^\/assets\/[^/]+-[\w-]{8}\.\w+$/
  const setHeaders = (res, pathname) => {
    res.setHeader('Cache-Control', hashed.test(pathname) ? 'public, max-age=31536000, immutable' : 'no-cache')
  }
  const serve = sirv(dist, { etag: true, gzip: true, brotli: true, single: true, setHeaders })
  console.log('[http] serving production build from dist/')
  return (req, res) => serve(req, res, () => { res.statusCode = 404; res.end('Not found') })
}

const handler = await createStaticHandler()
const server = http.createServer((req, res) => {
  if (req.url === '/healthz') {
    res.setHeader('content-type', 'application/json')
    res.end(JSON.stringify({ ok: true, ...game.stats() }))
    return
  }
  handler(req, res)
})

const io = geckos({
  portRange: { min: UDP_MIN, max: UDP_MAX },
  cors: { allowAuthorization: true, origin: '*' }
})
io.addServer(server)

const game = new Game(io, ROOT)
await game.init()

server.listen(port, () => {
  console.log(`[http] Labin Strike listening on http://localhost:${port} (UDP ${UDP_MIN}-${UDP_MAX})`)
})

function shutdown (signal) {
  console.log(`[server] ${signal} received, shutting down`)
  game.stop()
  server.close(() => process.exit(0))
  setTimeout(() => process.exit(0), 1500).unref()
}
process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('SIGINT', () => shutdown('SIGINT'))
