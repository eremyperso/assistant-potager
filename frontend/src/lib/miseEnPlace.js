// [US-334] Mettre en place le plan d'un potager neuf ou existant — tout ce qui se calcule, sans React.
//
// Deux points d'entrée, un seul état de départ : toutes les parcelles sont « à placer » (aucune
// position, US-326). Rien n'est mémorisé : l'encart se déduit de `GET /plan` (M5 — il se masque quand
// tout est posé, il se rouvre dès qu'une parcelle est retirée du plan ou créée sans position, par
// Telegram par exemple), et la première ouverture de l'éditeur se reconnaît à un potager encore vierge.
import { dimensionsDeParcelle, estPlacee, MODE_PLAN, MODE_ZONES, modeDuPlan } from './planDessus.js'
import { aimanter, texteMetres, COTE_MIN_M } from './editeurPlan.js'

export const DUREE_MISE_EN_PLACE = 'environ 5 minutes'
export const ENCART_INITIAL = 'initial'
export const ENCART_PARTIEL = 'partiel'

const nombre = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

// ── L'encart du Plan (M1, M2, M5) ─────────────────────────────────────────────

/**
 * [M1, M2, M5] L'encart au-dessus du plan, ou `null`.
 *  - aucune parcelle placée (plan par zones) → « Mettre en place le plan », la durée, ce que ça apporte ;
 *  - quelques-unes seulement → « N parcelles à placer » ;
 *  - toutes placées, ou aucune parcelle du tout (l'invitation à créer la première, CA1) → rien.
 */
export function encartMiseEnPlace(plan) {
  const mode = modeDuPlan(plan)
  const aPlacer = (plan?.parcelles || []).filter((p) => !estPlacee(p))
  if (!aPlacer.length) return null
  const n = aPlacer.length
  if (mode === MODE_ZONES) {
    return {
      type: ENCART_INITIAL,
      titre: 'Mettre en place le plan',
      duree: DUREE_MISE_EN_PLACE,
      texte: 'Posez vos parcelles sur le terrain : le plan montrera enfin où est quoi, à l’échelle, avec le nord et les rangs.',
      libelleBouton: 'Mettre en place le plan',
      nombre: n,
    }
  }
  if (mode === MODE_PLAN) {
    return {
      type: ENCART_PARTIEL,
      titre: `${n} parcelle${n > 1 ? 's' : ''} à placer`,
      duree: null,
      texte: `${n > 1 ? 'Ces parcelles ne sont' : 'Cette parcelle n’est'} pas encore dessinée${n > 1 ? 's' : ''} : le plan ne ${n > 1 ? 'leur' : 'lui'} invente aucune place.`,
      libelleBouton: `Placer ${n > 1 ? 'les parcelles' : 'la parcelle'}`,
      nombre: n,
    }
  }
  return null
}

/** Sans éditeur (téléphone, lecteur), l'encart dit pourquoi le bouton manque — jamais un bouton qui ne fait rien. */
export const TEXTE_SUR_ORDINATEUR = 'À faire sur ordinateur : la mise en place se fait à la souris, sur un grand écran.'

// ── La première ouverture de l'éditeur (M4) ───────────────────────────────────

/** Les quatre étapes enchaînées, dans l'ordre de M4. */
export const ETAPES = Object.freeze([
  { id: 'emprise', libelle: 'Emprise', titre: 'La taille du potager', aide: 'Longueur × largeur du terrain cultivé, en mètres. Une estimation suffit : elle se corrige à tout moment.' },
  { id: 'nord', libelle: 'Nord', titre: 'Où est le nord ?', aide: 'Regardez le plan comme vu du ciel : d’où vient le soleil de midi ? Cela oriente la rose des vents.' },
  { id: 'fond', libelle: 'Fond', titre: 'Le fond du plan', aide: 'Un fond (photo aérienne, plan) viendra se glisser sous le dessin. Pour l’instant, le plan se dessine sans fond.' },
  { id: 'pose', libelle: 'Pose', titre: 'Poser les parcelles', aide: 'Glissez chaque parcelle « À placer » sur le plan, ou posez-les toutes d’un coup et ajustez ensuite.' },
])

/**
 * [M4] Le potager est-il vierge ? Ni emprise, ni nord, aucune parcelle posée : l'éditeur, ouvert à ce
 * moment-là, déroule l'assistant. Dès que quelque chose est enregistré, il ne se redéroule plus.
 */
export function estPremiereOuverture(plan) {
  const g = plan?.potager_geometrie || {}
  if (nombre(g.emprise_longueur_m) || nombre(g.emprise_largeur_m) || g.orientation_nord) return false
  const parcelles = plan?.parcelles || []
  return parcelles.length > 0 && !parcelles.some(estPlacee)
}

/**
 * [M3] L'emprise proposée à partir de ce que le jardinier a déjà dit : superficie et longueur de ses
 * parcelles (assistant « Premier potager », fiche). Le terrain fait le double de la surface cultivée
 * (allées, bordures), au format 3 : 2, sans jamais être plus petit que la plus grande parcelle + 2 m.
 * `null` quand rien ne permet de proposer. C'est une proposition : rien n'est écrit tant qu'on ne la valide pas.
 */
export function empriseProposee(plan) {
  const dims = (plan?.parcelles || []).map((p) => dimensionsDeParcelle(p))
  if (!dims.length) return null
  const surface = dims.reduce((s, d) => s + d.w * d.h, 0)
  const maxW = Math.max(...dims.map((d) => d.w))
  const maxH = Math.max(...dims.map((d) => d.h))
  const aire = surface * 2
  const longueur = Math.max(Math.ceil(Math.sqrt(aire * 1.5)), Math.ceil(maxW) + 2, 4)
  const largeur = Math.max(Math.ceil(aire / longueur), Math.ceil(maxH) + 2, 3)
  return { longueur, largeur }
}

/**
 * [M3] La phrase qui dit d'où vient la proposition d'emprise (la superficie dite, pas un chiffre tombé du ciel).
 */
export function texteProposition(plan, proposition) {
  if (!proposition) return ''
  const n = (plan?.parcelles || []).length
  return `Proposée d’après vos ${n} parcelle${n > 1 ? 's' : ''} : ${texteMetres(proposition.longueur)} × ${texteMetres(proposition.largeur)} m.`
}

/**
 * [M4 / pose] Pose d'un coup toutes les parcelles « À placer », rangée par rangée, dans l'ordre du chemin,
 * à l'intérieur de l'emprise : un point de départ à ajuster, jamais un plan présenté comme exact.
 * Rend la liste `{ id, x, y }` ; l'appelant la rejoue par `poser`.
 */
export function dispositionEnRangees(parcelles, emprise, ecartM = 1) {
  const L = nombre(emprise?.longueur) || 20
  let x = 0
  let y = 0
  let hauteurRangee = 0
  const posees = []
  for (const p of parcelles) {
    const w = Math.max(COTE_MIN_M, aimanter(p.w))
    const h = Math.max(COTE_MIN_M, aimanter(p.h))
    if (x > 0 && x + w > L) {
      x = 0
      y += hauteurRangee + ecartM
      hauteurRangee = 0
    }
    posees.push({ id: p.id, x: aimanter(x), y: aimanter(y) })
    x += w + ecartM
    hauteurRangee = Math.max(hauteurRangee, h)
  }
  return posees
}

// ── Après l'assistant « Premier potager » (M3, CA3) ───────────────────────────

/** Les deux sorties de l'assistant : « maintenant » ouvre le Plan et son éditeur, « plus tard » le Plan et son encart. */
export const ADRESSE_PLAN = '/?vue=plan-vue'
export const ADRESSE_PLAN_EDITEUR = '/?vue=plan-vue&editeur=oui'
