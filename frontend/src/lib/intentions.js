// [US-195] Ouvrir un écran depuis un autre en emportant son contexte.
//
// La coquille d'US-053 ne sait changer que de vue (`setView(id)`) : une vue ne
// peut rien recevoir de celle qui l'ouvre. Ce module ajoute ce qui manque — une
// **intention**, petit objet de contexte que la vue d'arrivée applique UNE FOIS
// puis consomme — et la **mémoire de session** des écrans quittés.
//
// Trois règles tenues ici, et nulle part ailleurs :
//
// 1. **Aucun routeur** (CA10). Le bouton Retour du navigateur garde son
//    comportement actuel ; l'adresse n'est lue qu'au démarrage et aussitôt
//    nettoyée par `replaceState`, jamais empilée.
// 2. **Une intention est un contexte de LECTURE, jamais une commande.** Elle ne
//    déclenche aucune écriture, même reçue par l'adresse (règle d'US-221).
// 3. **Rien n'est persisté** (CA9). La mémoire des écrans vit dans la page ; un
//    rechargement repart d'un écran neuf.

/**
 * [CA2] Les intentions reconnues au terme des épics 9 à 12 — **et elles seules**.
 * Une clé absente de cette table est ignorée ; une vue absente n'a pas d'intention.
 *
 * `valide` filtre la VALEUR : une clé reconnue portant une valeur inexploitable
 * (vide, non numérique là où un identifiant est attendu) est écartée comme une
 * clé inconnue. Ce qui EXISTE réellement — la parcelle, le lot, la culture — ne
 * se vérifie pas ici mais à l'arrivée (CA3) : seule la vue connaît ses données.
 */
const ENTIER = (v) => {
  const n = Number(String(v).trim())
  return Number.isInteger(n) && n > 0 ? n : null
}
const TEXTE = (v) => {
  const s = String(v ?? '').trim()
  return s ? s : null
}
const DATE_ISO = (v) => (/^\d{4}-\d{2}-\d{2}$/.test(String(v ?? '').trim()) ? String(v).trim() : null)

export const INTENTIONS = Object.freeze({
  plan: Object.freeze({ parcelle: ENTIER }),
  'plan-vue': Object.freeze({ parcelle: ENTIER }),
  cultures: Object.freeze({ culture: TEXTE }),
  pepiniere: Object.freeze({ onglet: TEXTE, emplacement: TEXTE, lot: TEXTE }),
  journal: Object.freeze({ date: DATE_ISO, culture: TEXTE }),
})

/** Clé réservée de l'adresse : le potager visé (CA7). Jamais une clé de vue. */
export const CLE_POTAGER = 'potager'
/** Clé réservée de l'adresse : la vue visée (CA5). */
export const CLE_VUE = 'vue'

/** Les vues qui acceptent une intention. */
export const vuesAvecIntention = () => Object.keys(INTENTIONS)

/** Les clés reconnues d'une vue, ou `[]` si elle n'en accepte aucune. */
export const clesDe = (vue) => Object.keys(INTENTIONS[vue] || {})

/**
 * [CA1, CA2] Nettoie une intention pour une vue : ne garde que les clés
 * reconnues portant une valeur valide. Rend `null` — et non un objet vide —
 * quand il ne reste rien : une vue sans intention se comporte exactement comme
 * aujourd'hui, et `null` est le seul signal de cette absence.
 */
export function validerIntention(vue, brut) {
  const schema = INTENTIONS[vue]
  if (!schema || !brut || typeof brut !== 'object') return null
  const propre = {}
  for (const [cle, valide] of Object.entries(schema)) {
    if (!(cle in brut)) continue
    const valeur = valide(brut[cle])
    if (valeur !== null) propre[cle] = valeur
  }
  return Object.keys(propre).length > 0 ? propre : null
}

/**
 * [CA5, CA7] Lit une intention dans une adresse — `/?vue=pepiniere&lot=128`.
 *
 * Rend `{ vue, intention, potager }` ou `null`. `intention` peut être `null`
 * (une adresse qui ne nomme qu'une vue reste une navigation légitime).
 *
 * ⚠️ Cohabitation obligatoire avec les deux entrées existantes : le lien de
 * réinitialisation de mot de passe (`/reinitialiser-mot-de-passe?token=…`,
 * US-057), la vérification d'e-mail (US-044) et le retour OAuth
 * (`/auth/callback#…`, US-090) ont leur propre chemin. Une intention ne se lit
 * qu'à la RACINE : ces trois-là ne sont jamais interceptés.
 */
export function lireIntentionAdresse({ pathname = '/', search = '' } = {}) {
  if (pathname !== '/' && pathname !== '') return null
  const params = new URLSearchParams(search)
  const vue = params.get(CLE_VUE)
  if (!vue || !INTENTIONS[vue]) return null
  const brut = {}
  for (const cle of clesDe(vue)) {
    if (params.has(cle)) brut[cle] = params.get(cle)
  }
  return {
    vue,
    intention: validerIntention(vue, brut),
    potager: ENTIER(params.get(CLE_POTAGER)),
  }
}

/**
 * [CA5] Retire de la barre d'adresse tout ce qui relève d'une intention, sans
 * toucher au reste des paramètres ni empiler d'entrée d'historique : recharger
 * la page ne rejoue rien. Rend la nouvelle adresse (utile aux tests).
 */
export function adresseSansIntention({ pathname = '/', search = '', hash = '' } = {}) {
  const params = new URLSearchParams(search)
  const vue = params.get(CLE_VUE)
  for (const cle of [CLE_VUE, CLE_POTAGER, ...clesDe(vue)]) params.delete(cle)
  const reste = params.toString()
  return `${pathname || '/'}${reste ? `?${reste}` : ''}${hash || ''}`
}

/**
 * [CA5, CA6] Consomme l'intention de l'adresse courante : elle est lue UNE fois,
 * puis effacée de la barre d'adresse. Le résultat est rendu à l'appelant, qui le
 * garde en mémoire de page — c'est ce qui la fait **survivre à la connexion**
 * (CA6) : l'écran d'authentification s'intercale, l'intention l'attend.
 */
export function consommerIntentionAdresse(fenetre = globalThis.window) {
  if (!fenetre?.location) return null
  const { pathname, search, hash } = fenetre.location
  const lue = lireIntentionAdresse({ pathname, search })
  if (!lue) return null
  fenetre.history?.replaceState?.({}, '', adresseSansIntention({ pathname, search, hash }))
  return lue
}

// ── Mémoire des écrans (CA9) ─────────────────────────────────────────────────

/**
 * [CA9] L'état d'un écran quitté, pour le rendre **exact** quand on y revient :
 * sous-onglet, sélection, recherche, tri, filtre, position de défilement, focus.
 *
 * Vit en mémoire de session, dans la page, jamais dans `localStorage` ni dans
 * l'adresse : un rechargement repart d'un écran neuf, et rien ne fuite d'un
 * onglet du navigateur à l'autre.
 */
export function creerMemoireEcrans() {
  const etats = new Map()
  return {
    lire: (vue) => etats.get(vue) ?? null,
    ecrire: (vue, etat) => {
      if (etat && typeof etat === 'object') etats.set(vue, { ...etat })
    },
    oublier: (vue) => etats.delete(vue),
    vider: () => etats.clear(),
  }
}

/**
 * [CA9] L'état de départ d'un écran : ses valeurs par défaut, complétées par ce
 * dont on se souvient, **puis** écrasées par l'intention reçue.
 *
 * L'ordre est la règle : *une intention reçue l'emporte toujours sur l'état
 * mémorisé*. Revenir sur Parcelles rend la parcelle qu'on y regardait ; y
 * arriver par « Fiche parcelle → » rend celle que le lien désigne.
 */
export function etatInitial({ defauts = {}, memorise = null, intention = null } = {}) {
  return { ...defauts, ...(memorise || {}), ...(intention || {}) }
}

/**
 * [CA7] L'adresse qui rejoue une intention — l'inverse exact de
 * `adresseSansIntention`. Un seul usage : la bascule de potager d'US-054 se fait
 * par un rechargement complet de la page (`PotagerContext.activer`), qui
 * effacerait l'intention en mémoire ; on la remet donc dans l'adresse juste
 * avant, pour qu'elle soit relue une fois le bon potager actif.
 */
export function adresseAvecIntention({ vue, intention = null, potager = null } = {}, pathname = '/') {
  if (!vue || !INTENTIONS[vue]) return pathname
  const params = new URLSearchParams({ [CLE_VUE]: vue })
  for (const [cle, valeur] of Object.entries(intention || {})) params.set(cle, String(valeur))
  if (potager) params.set(CLE_POTAGER, String(potager))
  return `${pathname}?${params.toString()}`
}
