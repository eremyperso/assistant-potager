/**
 * Client API — tous les appels vers FastAPI centralisés ici.
 * VITE_API_URL : http://localhost:8001 en dev (tunnel SSH), URL prod en production.
 *
 * [US-044] Authentification JWT : l'access token est lu depuis localStorage à
 * chaque requête (mis à jour par AuthContext après /auth/login ou /auth/refresh).
 * Sur une réponse 401 { code: "token_expired" }, un unique refresh automatique
 * est tenté via /auth/refresh puis la requête d'origine est rejouée — sans
 * redemander le mot de passe à l'utilisateur.
 */

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const LS_ACCESS_TOKEN  = 'potager_access_token'
const LS_REFRESH_TOKEN = 'potager_refresh_token'

function getAccessToken() {
  try { return localStorage.getItem(LS_ACCESS_TOKEN) || '' } catch { return '' }
}

function getRefreshToken() {
  try { return localStorage.getItem(LS_REFRESH_TOKEN) || '' } catch { return '' }
}

export function setTokens({ access_token, refresh_token } = {}) {
  try {
    if (access_token) localStorage.setItem(LS_ACCESS_TOKEN, access_token)
    if (refresh_token) localStorage.setItem(LS_REFRESH_TOKEN, refresh_token)
  } catch {}
}

export function clearTokens() {
  try {
    localStorage.removeItem(LS_ACCESS_TOKEN)
    localStorage.removeItem(LS_REFRESH_TOKEN)
  } catch {}
}

function headers() {
  const h = { 'Content-Type': 'application/json' }
  const token = getAccessToken()
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

// Notifie AuthContext qu'une session ne peut plus être maintenue (refresh
// impossible) — déclenche un retour à l'écran de connexion.
function notifySessionExpired() {
  clearTokens()
  window.dispatchEvent(new CustomEvent('potager:auth:session-expired'))
}

let _refreshEnCours = null

async function rafraichirAccessToken() {
  const refresh_token = getRefreshToken()
  if (!refresh_token) return false

  // Mutualise les refresh concurrents (plusieurs requêtes en 401 en même temps)
  if (!_refreshEnCours) {
    _refreshEnCours = fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token }),
    })
      .then(async (res) => {
        if (!res.ok) return false
        const body = await res.json()
        setTokens(body)
        return true
      })
      .catch(() => false)
      .finally(() => { _refreshEnCours = null })
  }
  return _refreshEnCours
}

async function requeteAvecRefresh(path, options) {
  let res = await fetch(`${BASE}${path}`, options)

  if (res.status === 401) {
    let code = null
    try { code = (await res.clone().json())?.detail?.code } catch {}

    if (code === 'token_expired') {
      const ok = await rafraichirAccessToken()
      if (ok) {
        res = await fetch(`${BASE}${path}`, { ...options, headers: headers() })
      } else {
        notifySessionExpired()
      }
    } else {
      notifySessionExpired()
    }
  }

  return res
}

async function get(path) {
  const res = await requeteAvecRefresh(path, { headers: headers() })
  if (!res.ok) throw new Error(`Erreur API ${res.status} sur ${path}`)
  return res.json()
}

async function post(path) {
  const res = await requeteAvecRefresh(path, { method: 'POST', headers: headers() })
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
  // [US-045] Génère un code de liaison Telegram (TTL 10 min) pour le compte connecté
  genererCodeLiaisonTelegram: () => post('/auth/lien/generer-code'),
}

// [US-044] Endpoints d'authentification — pas de token requis pour register/login,
// pas de logique de refresh automatique (ce sont eux qui produisent les tokens).
export const authApi = {
  async register(email, mot_de_passe) {
    const res = await fetch(`${BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, mot_de_passe }),
    })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(body.detail || `Erreur inscription (${res.status})`)
    return body
  },

  async login(email, mot_de_passe) {
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, mot_de_passe }),
    })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(body.detail || `Erreur connexion (${res.status})`)
    setTokens(body)
    return body
  },

  logout() {
    clearTokens()
  },

  hasSession() {
    return Boolean(getAccessToken())
  },
}
