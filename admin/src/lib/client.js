// Client de l'API [US-311 / CA3]. Fabrique pure (stockage, `fetch` et base injectés) : testable sans
// navigateur. La connexion est CELLE DU JARDINIER — mêmes clés de stockage, mêmes routes `/auth/...` —
// donc un administrateur déjà connecté à l'application des jardiniers l'est ici aussi (même origine).

export const CLE_ACCES = 'potager_access_token'
export const CLE_RAFRAICHISSEMENT = 'potager_refresh_token'

/** `statut` 0 = l'API est injoignable (réseau coupé, serveur arrêté). */
export class ErreurApi extends Error {
  constructor(statut, message, code = null) {
    super(message)
    this.name = 'ErreurApi'
    this.statut = statut
    this.code = code
  }
}

function lire(stockage, cle) {
  try { return stockage.getItem(cle) || '' } catch { return '' }
}

export function creerClient({ base = '', stockage, fetchImpl = (...a) => fetch(...a), surSessionExpiree = () => {} }) {
  const acces = () => lire(stockage, CLE_ACCES)

  function ecrireJetons({ access_token, refresh_token } = {}) {
    try {
      if (access_token) stockage.setItem(CLE_ACCES, access_token)
      if (refresh_token) stockage.setItem(CLE_RAFRAICHISSEMENT, refresh_token)
    } catch { /* stockage indisponible : la session ne survivra pas au rechargement */ }
  }

  function effacerJetons() {
    try {
      stockage.removeItem(CLE_ACCES)
      stockage.removeItem(CLE_RAFRAICHISSEMENT)
    } catch { /* idem */ }
  }

  async function envoyer(chemin, options = {}) {
    try {
      return await fetchImpl(`${base}${chemin}`, options)
    } catch {
      throw new ErreurApi(0, 'API injoignable')
    }
  }

  let rafraichissement = null
  function rafraichir() {
    const jeton = lire(stockage, CLE_RAFRAICHISSEMENT)
    if (!jeton) return Promise.resolve(false)
    if (!rafraichissement) {
      rafraichissement = envoyer('/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: jeton }),
      })
        .then(async (res) => {
          if (!res.ok) return false
          ecrireJetons(await res.json())
          return true
        })
        .catch(() => false)
        .finally(() => { rafraichissement = null })
    }
    return rafraichissement
  }

  const entetes = () => {
    const h = { 'Content-Type': 'application/json' }
    if (acces()) h.Authorization = `Bearer ${acces()}`
    return h
  }

  async function code(res) {
    try { return (await res.clone().json())?.detail?.code ?? null } catch { return null }
  }

  async function lireReponse(res, chemin) {
    if (res.ok) return res.json()
    let detail = ''
    try { const corps = await res.clone().json(); detail = corps?.detail?.message || corps?.detail || '' } catch { /* corps vide */ }
    throw new ErreurApi(res.status, typeof detail === 'string' && detail ? detail : `Erreur ${res.status} sur ${chemin}`, await code(res))
  }

  /** GET authentifié ; un jeton expiré est rafraîchi une fois, sans redemander le mot de passe. */
  async function appeler(chemin, parametres = {}) {
    const requete = new URLSearchParams()
    for (const [cle, valeur] of Object.entries(parametres)) {
      if (valeur !== undefined && valeur !== null && valeur !== '') requete.set(cle, String(valeur))
    }
    const url = requete.toString() ? `${chemin}?${requete}` : chemin

    let res = await envoyer(url, { headers: entetes() })
    if (res.status === 401) {
      if ((await code(res)) === 'token_expired' && (await rafraichir())) {
        res = await envoyer(url, { headers: entetes() })
      }
      if (res.status === 401) {
        effacerJetons()
        surSessionExpiree()
      }
    }
    return lireReponse(res, chemin)
  }

  /** PATCH JSON authentifié [US-316] — même rafraîchissement de jeton qu'un GET. */
  async function modifier(chemin, corps) {
    const options = () => ({ method: 'PATCH', headers: entetes(), body: JSON.stringify(corps) })
    let res = await envoyer(chemin, options())
    if (res.status === 401) {
      if ((await code(res)) === 'token_expired' && (await rafraichir())) {
        res = await envoyer(chemin, options())
      }
      if (res.status === 401) {
        effacerJetons()
        surSessionExpiree()
      }
    }
    return lireReponse(res, chemin)
  }

  async function connecter(email, motDePasse) {
    const res = await envoyer('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, mot_de_passe: motDePasse }),
    })
    const corps = await lireReponse(res, '/auth/login')
    ecrireJetons(corps)
    return corps
  }

  return {
    appeler,
    modifier,
    connecter,
    deconnecter: effacerJetons,
    aUnJeton: () => Boolean(acces()),
    /** Qui suis-je, et suis-je l'administrateur ? Aucune requête `/admin/...` n'est faite ici. */
    moi: () => appeler('/auth/me'),
  }
}
