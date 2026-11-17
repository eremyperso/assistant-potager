import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // [US-311] En local, Pilotage (l'application construite, servie par l'API) s'ouvre sur la même origine que
    // l'application des jardiniers : http://localhost:3000/pilotage/ — même session, même stockage.
    proxy: {
      '/pilotage': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
