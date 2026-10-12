// Thin wrapper around the geckos.io (WebRTC data channel) client.
import geckos from '@geckos.io/client'

export class Net {
  constructor () {
    this.channel = null
    this.connected = false
    this.handlers = new Map()
    this.onDisconnect = null
  }

  connect (timeoutMs = 12000) {
    const secure = location.protocol === 'https:'
    const port = Number(location.port) || (secure ? 443 : 80)
    const ch = geckos({ url: `${location.protocol}//${location.hostname}`, port })
    this.channel = ch
    for (const [ev, fn] of this.handlers) ch.on(ev, fn)
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Connection timed out (UDP ports may be blocked)')), timeoutMs)
      ch.onConnect((err) => {
        clearTimeout(timer)
        if (err) { reject(err instanceof Error ? err : new Error(String(err.message || err))); return }
        this.connected = true
        ch.onDisconnect(() => {
          this.connected = false
          this.onDisconnect?.()
        })
        resolve()
      })
    })
  }

  on (event, fn) {
    this.handlers.set(event, fn)
    this.channel?.on(event, fn)
  }

  emit (event, data, reliable = false) {
    if (!this.connected) return
    this.channel.emit(event, data, reliable ? { reliable: true } : undefined)
  }

  close () {
    try { this.channel?.close() } catch {}
    this.connected = false
  }
}
