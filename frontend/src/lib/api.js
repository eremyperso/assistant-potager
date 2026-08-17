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

async function post(path, body) {
  const options = { method: 'POST', headers: headers() }
  if (body !== undefined) options.body = JSON.stringify(body)
  const res = await requeteAvecRefresh(path, options)
  if (!res.ok) {
    const detail = await res.clone().json().catch(() => ({}))
    throw new Error(detail?.detail?.message || detail?.detail || `Erreur API ${res.status} sur ${path}`)
  }
  return res.json()
}

// [US-074] PATCH /potagers/{id} — mêmes conventions d'erreur que post()
async function patch(path, body) {
  const options = { method: 'PATCH', headers: headers() }
  if (body !== undefined) options.body = JSON.stringify(body)
  const res = await requeteAvecRefresh(path, options)
  if (!res.ok) {
    const detail = await res.clone().json().catch(() => ({}))
    throw new Error(detail?.detail?.message || detail?.detail || `Erreur API ${res.status} sur ${path}`)
  }
  return res.json()
}

async function del(path) {
  const res = await requeteAvecRefresh(path, { method: 'DELETE', headers: headers() })
  if (!res.ok) {
    const detail = await res.clone().json().catch(() => ({}))
    throw new Error(detail?.detail?.message || detail?.detail || `Erreur API ${res.status} sur ${path}`)
  }
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
  // [US-072] Détail par variété toutes cultures confondues, avec parcelles — écran Stocks (US-073)
  statsVarietes: (dateRef) => get(`/stats/varietes${dateRef ? qs({ date_ref: dateRef }) : ''}`),
  godets:     (dateRef) => get(`/godets${dateRef ? qs({ date_ref: dateRef }) : ''}`),
  cultures:   () => get('/cultures'),
  historique: (params = {}) => get(`/historique${qs(params)}`),
  meteoHistory: (days = 30) => get(`/meteo/history${qs({ days })}`),
  // [US-075/US-076] Météo du jour + prévision 5 jours sur la localisation du
  // potager actif — `{ localisation_manquante: true }` si non renseignée (CA4).
  meteo: () => get('/meteo'),
  activite:     (annee, dateRef) => get(`/stats/activite${qs({ annee, ...(dateRef ? { date_ref: dateRef } : {}) })}`),
  rendement:    (annee, dateRef) => get(`/stats/rendement${qs({ annee, ...(dateRef ? { date_ref: dateRef } : {}) })}`),
  // [US-065/US-061] Pépinière lot de semis par lot de semis — lecture distincte de
  // `/godets`, qui reste agrégée par culture + variété pour Stocks, Stats et le bot.
  pepiniereLots: (dateRef) => get(`/pepiniere/lots${dateRef ? qs({ date_ref: dateRef }) : ''}`),
  // [US-061 CA10] `semisId` / `sansSemisRattache` ciblent le lot ouvert ; sans eux
  // l'endpoint conserve son comportement agrégé (culture + variété).
  godetsDetail: (culture, variete, { semisId, sansSemisRattache } = {}) => {
    const params = new URLSearchParams({ culture })
    if (variete) params.append('variete', variete)
    if (semisId != null) params.append('semis_id', semisId)
    if (sansSemisRattache) params.append('sans_semis_rattache', 'true')
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
  // [US-055] Identité du compte connecté + état de la liaison Telegram (menu Compte)
  moi: () => get('/auth/me'),
  // [US-045] Génère un code de liaison Telegram (TTL 10 min) pour le compte connecté
  genererCodeLiaisonTelegram: () => post('/auth/lien/generer-code'),
  // [US-050 / CA1] Dissocie le chat Telegram lié au compte — identité seule, sans corps de requête
  delierTelegram: () => post('/auth/lien/delier'),
  // [US-046] Potagers du compte connecté — liste vide = CA5 (aucun potager), pas une erreur
  potagers: () => get('/potagers'),
  activerPotager: (potagerId) => post(`/potagers/${potagerId}/activer`),
  // [US-048] Création de potager, invitations et gestion des membres (owner)
  // [US-074 / CA3] `ville` optionnelle, choisie via VilleSearch (géocodage Open-Meteo)
  creerPotager: (nom, ville, latitude, longitude) => post('/potagers', { nom, ville, latitude, longitude }),
  // [US-074 / CA4, CA5] Modification (nom/ville/localisation) d'un potager déjà créé — owner uniquement
  modifierPotager: (potagerId, { nom, ville, latitude, longitude } = {}) =>
    patch(`/potagers/${potagerId}`, { nom, ville, latitude, longitude }),
  creerInvitation: (potagerId, rolePropose, emailInvite) =>
    post(`/potagers/${potagerId}/invitations`, { role_propose: rolePropose, email_invite: emailInvite }),
  accepterInvitation: (code) => post(`/invitations/${code}/accepter`),
  listerMembres: (potagerId) => get(`/potagers/${potagerId}/membres`),
  retirerMembre: (potagerId, membreUserId) => del(`/potagers/${potagerId}/membres/${membreUserId}`),
}

// [US-044] Endpoints d'authentification — pas de token requis pour register/login,
// pas de logique de refresh automatique (ce sont eux qui produisent les tokens).
export const authApi = {
  // [US-056 / CA3] `nom` optionnel côté API (colonne User.nom déjà existante)
  async register(email, mot_de_passe, nom) {
    const res = await fetch(`${BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, mot_de_passe, nom }),
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
    if (!res.ok) {
      // [CA11] body.detail est un objet {code, message} pour EMAIL_NOT_VERIFIED,
      // une simple chaîne pour les autres erreurs (identifiants incorrects...).
      const detail = body.detail
      const message = typeof detail === 'string' ? detail : detail?.message
      const err = new Error(message || `Erreur connexion (${res.status})`)
      if (typeof detail === 'object' && detail?.code) err.code = detail.code
      throw err
    }
    setTokens(body)
    return body
  },

  logout() {
    clearTokens()
  },

  hasSession() {
    return Boolean(getAccessToken())
  },

  // [CA10] Valide le token reçu par e-mail — pas de token requis (utilisateur pas encore connecté)
  async verifyEmail(token) {
    const res = await fetch(`${BASE}/auth/verify-email${qs({ token })}`)
    const body = await res.json().catch(() => ({}))
    if (!res.ok) {
      const detail = body.detail
      throw new Error((typeof detail === 'string' ? detail : detail?.message) || `Erreur de vérification (${res.status})`)
    }
    return body
  },

  // [CA12] Réponse toujours générique (anti-énumération) — jamais d'erreur à afficher
  async resendVerification(email) {
    const res = await fetch(`${BASE}/auth/resend-verification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
    return res.json().catch(() => ({}))
  },

  // [US-057 / CA1] Réponse toujours générique (anti-énumération) — jamais d'erreur à afficher
  async motDePasseOublie(email) {
    const res = await fetch(`${BASE}/auth/mot-de-passe-oublie`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
    return res.json().catch(() => ({}))
  },

  // [US-057 / CA3, CA4] token issu du lien reçu par e-mail — pas de session requise
  async reinitialiserMotDePasse(token, nouveau_mot_de_passe) {
    const res = await fetch(`${BASE}/auth/reinitialiser-mot-de-passe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, nouveau_mot_de_passe }),
    })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) {
      const detail = body.detail
      throw new Error((typeof detail === 'string' ? detail : detail?.message) || `Erreur de réinitialisation (${res.status})`)
    }
    return body
  },
}
