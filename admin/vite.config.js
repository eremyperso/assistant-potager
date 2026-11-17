import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// L'application est servie par l'API sous /pilotage/ [US-311 / CA2] : tous les chemins
// (assets, manifeste, service worker) sont relatifs à cette base, jamais à la racine.
export default defineConfig({
  base: '/pilotage/',
  plugins: [react()],
  server: { port: 3001 },
})
