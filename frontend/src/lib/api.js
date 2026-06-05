/**
 * Client API — tous les appels vers FastAPI centralisés ici.
 * VITE_API_URL : http://localhost:8001 en dev (tunnel SSH), URL prod en production.
 */

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'
const TOKEN = import.meta.env.VITE_API_TOKEN || ''

function headers() {
  const h = { 'Content-Type': 'application/json' }
  if (TOKEN) h['Authorization'] = `Bearer ${TOKEN}`
  return h
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: headers() })
  if (!res.ok) throw new Error(`Erreur API ${res.status} sur ${path}`)
  return res.json()
}

export const api = {
  health:     () => get('/health'),
  stats:      () => get('/stats'),
  godets:     () => get('/godets'),
  cultures:   () => get('/cultures'),
  historique: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return get(`/historique${qs ? '?' + qs : ''}`)
  },
}
