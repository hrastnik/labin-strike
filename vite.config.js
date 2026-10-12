import { defineConfig } from 'vite'
import path from 'node:path'

export default defineConfig({
  root: path.resolve(import.meta.dirname, 'client'),
  publicDir: path.resolve(import.meta.dirname, 'client/public'),
  resolve: { alias: { '@shared': path.resolve(import.meta.dirname, 'shared') } },
  server: { fs: { allow: [import.meta.dirname] } },
  build: {
    outDir: path.resolve(import.meta.dirname, 'dist'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 6000,
    target: 'es2022'
  }
})
