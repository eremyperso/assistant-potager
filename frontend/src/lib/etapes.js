// [US-321] Langage visuel commun des étapes d'une culture — couleur, pictogramme,
// libellé. UNE table de présentation (CA6) : le plan, la liste mobile et le suivi de
// culture (US-322, US-327, US-329) la lisent, aucun ne réécrit une correspondance.
//
// Ce fichier ne CALCULE aucune étape : le serveur la donne (`cultures[].etapes` de
// `GET /plan`, US-320). Ici, seulement la mise en forme. Aucune couleur n'est écrite :
// chaque famille nomme une classe (`etape-<famille>`) dont les valeurs sont des tokens
// de `index.css`, avec leur variante sombre (CA2).

export const ETAPE_SEMEE = 'semee'
export const ETAPE_LEVEE = 'levee'
export const ETAPE_PLANTEE = 'plantee'
export const ETAPE_CROISSANCE = 'croissance'
export const ETAPE_FLEUR = 'fleur'
export const ETAPE_EN_RECOLTE = 'en_recolte'
export const ETAPE_TERMINEE = 'terminee'

/** Les pictogrammes (CA3) : SVG monochromes dessinés dans `EtapeCulture.jsx`. */
export const PICTO_GRAINE = 'graine'
export const PICTO_LEVEE = 'levee'
export const PICTO_PLANT = 'plant'
export const PICTO_TIGE = 'tige'
export const PICTO_FLEUR = 'fleur'
export const PICTO_PANIER = 'panier'
export const PICTO_COCHE = 'coche'

/**
 * [V1, V2] Sept étapes, six familles de couleur : Levé et Planté partagent le vert
 * tendre, et c'est le pictogramme (levée / plant) qui les distingue. Dans l'ordre du
 * cycle, qui est aussi celui de la légende (CA4).
 */
export const ETAPES = Object.freeze([
  Object.freeze({ cle: ETAPE_SEMEE, libelle: 'Semé', famille: 'semee', picto: PICTO_GRAINE }),
  Object.freeze({ cle: ETAPE_LEVEE, libelle: 'Levé', famille: 'levee', picto: PICTO_LEVEE }),
  Object.freeze({ cle: ETAPE_PLANTEE, libelle: 'Planté', famille: 'levee', picto: PICTO_PLANT }),
  Object.freeze({ cle: ETAPE_CROISSANCE, libelle: 'En croissance', famille: 'croissance', picto: PICTO_TIGE }),
  Object.freeze({ cle: ETAPE_FLEUR, libelle: 'En fleur', famille: 'fleur', picto: PICTO_FLEUR }),
  Object.freeze({ cle: ETAPE_EN_RECOLTE, libelle: 'En récolte', famille: 'recolte', picto: PICTO_PANIER }),
  Object.freeze({ cle: ETAPE_TERMINEE, libelle: 'Terminé', famille: 'terminee', picto: PICTO_COCHE }),
])

const PAR_CLE = Object.freeze(Object.fromEntries(ETAPES.map((e) => [e.cle, e])))

/** Les six familles de couleur, dans l'ordre de V1 (les tokens de `index.css`). */
export const FAMILLES = Object.freeze(['semee', 'levee', 'croissance', 'fleur', 'recolte', 'terminee'])

/** Le nom des tokens d'une famille : fond et encre (le test de contraste les lit). */
export const jetonFond = (famille) => `--etape-${famille}`
export const jetonEncre = (famille) => `--etape-${famille}-t`

/** L'étape déclarée, ou `null` si la clé est absente ou inconnue — jamais un repli. */
export function etape(cle) {
  return PAR_CLE[cle] || null
}

export const libelleEtape = (cle) => etape(cle)?.libelle || ''
export const classeEtape = (cle) => (etape(cle) ? `etape-${etape(cle).famille}` : '')

// ── Les cinq états d'un segment (V3 à V6) ───────────────────────────────────────

/** Étape validée : plein. */
export const VARIANTE_PLEIN = 'plein'
/** Étape prévue, pas encore vue : hachuré. */
export const VARIANTE_PREVU = 'prevu'
/** Prévue ET date atteinte : hachuré + pastille orange. */
export const VARIANTE_A_CONFIRMER = 'a_confirmer'
/** Culture terminée, rang à libérer : gris hachuré. */
export const VARIANTE_A_LIBERER = 'a_liberer'
/** Rang libre : contour pointillé. */
export const VARIANTE_LIBRE = 'libre'

export const VARIANTES = Object.freeze([
  VARIANTE_PLEIN, VARIANTE_PREVU, VARIANTE_A_CONFIRMER, VARIANTE_A_LIBERER, VARIANTE_LIBRE,
])

/**
 * L'état d'un segment d'après ce que dit le serveur (`etape_statut`, `a_confirmer`,
 * `a_liberer`). Le serveur dit « à confirmer » : le front ne compare aucune date.
 * Une étape passée mais jamais notée (`non_notee`) est « pas encore vue » : hachurée.
 */
export function variante({ statut = 'validee', aConfirmer = false, aLiberer = false, libre = false } = {}) {
  if (libre) return VARIANTE_LIBRE
  if (aLiberer) return VARIANTE_A_LIBERER
  if (statut === 'prevue' || statut === 'non_notee') {
    return aConfirmer ? VARIANTE_A_CONFIRMER : VARIANTE_PREVU
  }
  return VARIANTE_PLEIN
}

/** Une ligne de `GET /plan` → ce que dessine un segment, ou `null` sans étape (pépinière). */
export function segmentDeLigne(ligne) {
  const e = ligne?.etapes
  if (!e || !etape(e.etape)) return null
  return {
    etape: e.etape,
    variante: variante({
      statut: e.etape_statut, aConfirmer: Boolean(e.a_confirmer), aLiberer: Boolean(e.a_liberer),
    }),
  }
}

/** Les classes CSS d'une variante : la couleur vient de l'étape, la trame de l'état. */
export function classesSegment(cle, v) {
  if (v === VARIANTE_LIBRE) return 'etape-libre'
  if (v === VARIANTE_A_LIBERER) return 'etape-terminee etape-prevue'
  const base = classeEtape(cle)
  return v === VARIANTE_PLEIN ? base : `${base} etape-prevue`
}

/**
 * Le texte lu par un lecteur d'écran et par n'importe quel œil en niveaux de gris
 * (V8) : le libellé d'abord, l'état ensuite.
 */
export function libelleAccessible(cle, v) {
  if (v === VARIANTE_LIBRE) return 'Rang libre'
  if (v === VARIANTE_A_LIBERER) return 'Terminé, rang à libérer'
  const nom = libelleEtape(cle)
  if (!nom) return ''
  if (v === VARIANTE_A_CONFIRMER) return `${nom}, prévu, à confirmer`
  if (v === VARIANTE_PREVU) return `${nom}, prévu`
  return nom
}

// ── Légende (CA4) ───────────────────────────────────────────────────────────────

/**
 * [CA4] La légende dans l'ordre de la maquette : les étapes, puis « hachuré : prévu,
 * à confirmer », « à confirmer aujourd'hui », « rang libre ». La version compacte
 * (mobile) fusionne Levé et Planté — six étapes.
 */
export function entreesLegende({ compact = false } = {}) {
  const etapes = ETAPES
    .filter((e) => !(compact && e.cle === ETAPE_PLANTEE))
    .map((e) => (compact && e.cle === ETAPE_LEVEE
      ? { type: 'etape', cle: e.cle, libelle: 'Levé / Planté', famille: e.famille, picto: e.picto }
      : { type: 'etape', cle: e.cle, libelle: e.libelle, famille: e.famille, picto: e.picto }))
  return [
    ...etapes,
    { type: 'prevu', libelle: 'hachuré : prévu, à confirmer' },
    { type: 'pastille', libelle: 'à confirmer aujourd’hui' },
    { type: 'libre', libelle: 'rang libre' },
  ]
}
