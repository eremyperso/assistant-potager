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

function qs(params) {
  const s = new URLSearchParams(params).toString()
  return s ? '?' + s : ''
}

export const api = {
  health:     () => get('/health'),
  // [US-030/US-031] dateRef optionnel : ISO YYYY-MM-DD ou null → état à la date passée
  plan:       (dateRef) => get(`/plan${dateRef ? qs({ date_ref: dateRef }) : ''}`),
  stats:      (dateRef) => get(`/stats${dateRef ? qs({ date_ref: dateRef }) : ''}`),
  godets:     (dateRef) => get(`/godets${dateRef ? qs({ date_ref: dateRef }) : ''}`),
  cultures:   () => get('/cultures'),
  historique: (params = {}) => get(`/historique${qs(params)}`),
  meteoHistory: (days = 30) => get(`/meteo/history${qs({ days })}`),
  activite:     (annee, dateRef) => get(`/stats/activite${qs({ annee, ...(dateRef ? { date_ref: dateRef } : {}) })}`),
  rendement:    (annee, dateRef) => get(`/stats/rendement${qs({ annee, ...(dateRef ? { date_ref: dateRef } : {}) })}`),
  godetsDetail: (culture, variete) => {
    const params = new URLSearchParams({ culture })
    if (variete) params.append('variete', variete)
    return get(`/godets/detail?${params}`)
  },
  // [US-039] parcelleId seul (carte parcelle) | parcelleId+culture+variete (ligne culture) | culture seule (Stocks)
  observations: ({ parcelleId, culture, variete } = {}) => {
    const params = {}
    if (parcelleId != null) params.parcelle_id = parcelleId
    if (culture) params.culture = culture
    if (variete) params.variete = variete
    return get(`/observations${qs(params)}`)
  },
}
