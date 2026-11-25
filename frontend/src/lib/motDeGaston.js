// [US-353 / CA6, CA7] Le Mot de Gaston : ce que Gaston sait de CET écran, en deux phrases au plus et
// une à trois actions. Il est CALCULÉ SANS MODÈLE (D1) : une fonction pure par vue reçoit ce que la
// vue a déjà lu (et les signaux de `GET /compagnon/etat`) et rend `{ texte, actions }` ou rien.
// Aucun appel réseau, aucun jeton : le même écran, les mêmes données, le même mot.
//
// Ce fichier porte le CONTRAT (forme, limites, normalisation), la RÈGLE COMMUNE (priorité gel >
// étape due > manque de donnée) et l'exécution d'une action. Chaque US de vue (US-354, 355, 356,
// 360) écrit la règle de SA vue et l'inscrit dans `REGLES_PAR_VUE` — ou la passe à `calculerMot`.
//
//   Mot    = { texte: string, actions: Action[] }
//   Action = { libelle: string, principale?: boolean,
//              noter?: true, contexte?: object,        // une action qui ÉCRIT ouvre Gaston (US-358)
//              vue?: string, intention?: object }      // une action qui NAVIGUE change de vue

/** Deux phrases au plus (CA6). */
export const MAX_PHRASES = 2
/** Une à trois actions (CA6). */
export const MAX_ACTIONS = 3

/** La priorité de la règle commune (CA7) : le premier de la liste qui a quelque chose à dire gagne. */
export const PRIORITE_COMMUNE = Object.freeze(['gel', 'etape_due', 'manque'])

const PHRASES = /(?<=[.!?…])\s+/

/** Au plus `MAX_PHRASES` phrases, espaces nettoyés ; chaîne vide si rien à dire. */
export function nettoyerTexte(texte) {
  const propre = String(texte ?? '').replace(/\s+/g, ' ').trim()
  if (!propre) return ''
  return propre.split(PHRASES).slice(0, MAX_PHRASES).join(' ')
}

/** Une action valable a un libellé ; les champs inconnus sont écartés. */
export function normaliserAction(action) {
  const libelle = String(action?.libelle ?? '').trim()
  if (!libelle) return null
  const propre = { libelle }
  if (action.principale) propre.principale = true
  if (action.noter) {
    propre.noter = true
    if (action.contexte) propre.contexte = action.contexte
    // [US-355 / CA8] Une phrase que Gaston reçoit à l'ouverture (« Ajouter le céleri-rave… ») : il répond par
    // une proposition à confirmer, rien n'est écrit avant.
    if (action.phrase) propre.phrase = String(action.phrase)
    // [US-358 / CA1] Le sujet affiché au bandeau (« Céleri-rave · catalogue ») : jamais envoyé au serveur.
    if (action.sujet) propre.sujet = action.sujet
  } else if (action.vue) {
    propre.vue = action.vue
    if (action.intention) propre.intention = action.intention
  }
  return propre
}

/**
 * [CA6] Un mot propre, ou `null` quand Gaston n'a rien à dire : sans texte, le bloc n'est PAS rendu
 * (ni vide, ni en attente). Une seule action est « principale » (vert plein), la première par défaut.
 */
export function normaliserMot(mot) {
  const texte = nettoyerTexte(mot?.texte)
  if (!texte) return null
  const actions = (mot?.actions ?? []).map(normaliserAction).filter(Boolean).slice(0, MAX_ACTIONS)
  if (actions.length) {
    const premiere = actions.findIndex((a) => a.principale)
    actions.forEach((a, i) => { a.principale = i === (premiere === -1 ? 0 : premiere) })
  }
  return { texte, actions }
}

/**
 * [CA7] Les signaux utiles d'une lecture de `GET /compagnon/etat` : le dernier message de gel que
 * le compagnon a envoyé, tant qu'il est récent et que le jardinier n'y a pas réagi.
 * Rend `{ gel: { texte } | null }` — jamais d'exception sur une lecture absente.
 */
export function signauxDeEtat(etat, { maintenant = Date.now(), heures = 36 } = {}) {
  const limite = maintenant - heures * 3600 * 1000
  const gels = (etat?.spontanes ?? [])
    .filter((m) => m?.genre === 'gel' && !m.reagi && Date.parse(m.envoye_le) >= limite)
  const dernier = gels[gels.length - 1]
  return { gel: dernier?.texte ? { texte: dernier.texte } : null }
}

const pluriel = (n, un, plusieurs) => (n > 1 ? plusieurs : un)

function motDeGel(gel) {
  if (!gel) return null
  const texte = gel.texte
    || `Gel annoncé${gel.jour ? ` ${gel.jour}` : ''}${Number.isFinite(gel.temperature) ? ` (${gel.temperature} °C)` : ''}. Protégez vos cultures sensibles.`
  return {
    texte,
    actions: [
      { libelle: 'Voir les cultures', vue: 'cultures' },
      { libelle: 'Noter la protection', noter: true, principale: true, phrase: 'J’ai protégé les cultures du gel' },
    ],
  }
}

function motDEtapeDue(etapesDues) {
  const liste = Array.isArray(etapesDues) ? etapesDues : []
  const n = Array.isArray(etapesDues) ? liste.length : Number(etapesDues) || 0
  if (!n) return null
  const un = liste[0]
  const texte = n === 1 && un?.culture
    ? `${un.culture} : ${String(un.etape ?? 'une étape').toLowerCase()} prévue, à confirmer. Dites-moi si c'est fait.`
    : `${n} ${pluriel(n, 'étape à confirmer', 'étapes à confirmer')}. Dites-moi ce que vous voyez au potager.`
  return {
    texte,
    actions: [
      { libelle: 'Voir à confirmer', vue: 'cultures' },
      { libelle: 'Noter', noter: true, contexte: n === 1 ? (un?.contexte ?? undefined) : undefined },
    ],
  }
}

function motDeManque(manques) {
  const liste = (manques ?? []).filter(Boolean)
  if (!liste.length) return null
  return {
    texte: `Il me manque ${liste.length === 1 ? 'une information' : `${liste.length} informations`} : ${liste.slice(0, 2).join(', ')}.`,
    actions: [{ libelle: 'Compléter', noter: true, principale: true }],
  }
}

/**
 * [CA7] La règle commune : gel > étape due > manque de donnée. Reçoit ce que la vue a déjà lu :
 * `{ gel, etapesDues, manques }` (le gel vient de `signauxDeEtat`). Rend un mot propre ou `null`.
 */
export function motCommun({ gel = null, etapesDues = 0, manques = [] } = {}) {
  const regles = { gel: () => motDeGel(gel), etape_due: () => motDEtapeDue(etapesDues), manque: () => motDeManque(manques) }
  for (const cle of PRIORITE_COMMUNE) {
    const mot = normaliserMot(regles[cle]())
    if (mot) return mot
  }
  return null
}

/** Les règles propres à chaque vue — `{ [vue]: (donnees) => Mot | null }`. Les US de vue y inscrivent la leur. */
export const REGLES_PAR_VUE = {}

/**
 * Le mot d'une vue : sa règle propre si elle en a une, la règle commune sinon. Pure : mêmes données,
 * même mot. Une règle qui échoue (donnée absente) n'a rien à dire — jamais d'exception à l'écran.
 */
export function calculerMot(vue, donnees = {}, regles = REGLES_PAR_VUE) {
  const regle = regles[vue] ?? motCommun
  try {
    return normaliserMot(regle(donnees))
  } catch {
    return null
  }
}

/**
 * [CA6] Exécute une action du mot : celle qui écrit ouvre Gaston (avec son contexte éventuel),
 * celle qui navigue change de vue. `ouvrirGaston(contexte, phrase, sujet)` et `aller(vue, intention)` sont
 * fournis par la coquille.
 */
export function executerAction(action, { ouvrirGaston, aller }) {
  if (action?.noter) { ouvrirGaston?.(action.contexte ?? null, action.phrase, action.sujet); return 'noter' }
  if (action?.vue) { aller?.(action.vue, action.intention); return 'aller' }
  return null
}

/** « ce matin », « cet après-midi », « ce soir » : le moment de la signature « Gaston · ce matin ». */
export function momentDeJournee(date = new Date()) {
  const h = date.getHours()
  if (h < 12) return 'ce matin'
  if (h < 18) return 'cet après-midi'
  return 'ce soir'
}

/** La clé sous laquelle le × mémorise « masqué pour la session et pour cette vue ». */
export const cleMasque = (vue) => `potager:mot-masque:${vue}`
