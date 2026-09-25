// [US-205 / CA14] Écran Cultures — tri, filtres, recherche et libellé de
// fenêtre, SANS React, à partir des valeurs BRUTES d'US-204 / CA5
// (`GET /cultures/vue`). Rien n'est recalculé : la confiance, la présence, la
// fenêtre et la suggestion de la semaine viennent telles quelles du serveur —
// ce fichier choisit et met en forme, jamais n'invente une règle métier.
import { libelleAction } from './confiance.js'
import { MOIS_NOMS } from './calendrier.js'

export const FENETRE_MAINTENANT = 'maintenant'
export const FENETRE_BIENTOT = 'bientot'
export const FENETRE_PLUS_TARD = 'plus_tard'
export const FENETRE_AUCUNE = 'aucune'

const ORDRE_FENETRE = Object.freeze({
  [FENETRE_MAINTENANT]: 0, [FENETRE_BIENTOT]: 1, [FENETRE_PLUS_TARD]: 2, [FENETRE_AUCUNE]: 3,
})

export const TRI_CONFIANCE = 'confiance'
export const TRI_ALPHA = 'alpha'
export const TRI_FAMILLE = 'famille'
export const TRI_PAR_DEFAUT = TRI_CONFIANCE

export const HORS_REFERENTIEL_LIBELLE = 'Hors référentiel'

/** [CA5 ter] `mois_zone` (1..12, clés serveur) → 0-based, dans l'ordre de `MonthStrip`. */
const SERVEUR_VERS_FRISE = Object.freeze({
  semis_pepiniere: 'pepiniere', semis_pleine_terre: 'pleineTerre', plantation: 'plantation', recolte: 'rec',
})
const versIndex = (mois) => (mois || []).filter((m) => Number.isInteger(m) && m >= 1 && m <= 12).map((m) => m - 1)

/** [CA5] La frise conseillée de la carte, dans la forme attendue par `MonthStrip`. */
export function friseDeLigne(ligne) {
  const mois = ligne?.mois_zone || {}
  const frise = {}
  for (const [srv, cle] of Object.entries(SERVEUR_VERS_FRISE)) frise[cle] = versIndex(mois[srv])
  return frise
}

/** « février → mars », un seul mois nommé si la fenêtre tient en un mois. */
function plageMois(mois) {
  const valides = (mois || []).filter((m) => Number.isInteger(m) && m >= 1 && m <= 12)
  if (valides.length === 0) return ''
  const debut = MOIS_NOMS[valides[0] - 1]
  const fin = MOIS_NOMS[valides[valides.length - 1] - 1]
  return debut === fin ? debut : `${debut} → ${fin}`
}

const minuscule = (s) => (s ? s.charAt(0).toLowerCase() + s.slice(1) : s)

/**
 * [CA5] Le libellé de fenêtre de la carte — « Semer en place maintenant » (en
 * gras), « bientôt : planter octobre → novembre », « prochaine fenêtre :
 * semer en pépinière février → mars ». `null` sans calendrier pour la zone
 * (CA6, la carte montre alors « pas de calendrier » à la place).
 */
export function libelleFenetre(ligne) {
  if (!ligne?.a_calendrier || ligne.fenetre_etat === FENETRE_AUCUNE) return null
  const geste = libelleAction(ligne.fenetre_geste)
  if (!geste) return null
  const plage = plageMois(ligne.fenetre_mois)
  if (ligne.fenetre_etat === FENETRE_MAINTENANT) return { gras: true, texte: `${geste} maintenant` }
  if (ligne.fenetre_etat === FENETRE_BIENTOT) return { gras: false, texte: `bientôt : ${minuscule(geste)} ${plage}` }
  return { gras: false, texte: `prochaine fenêtre : ${minuscule(geste)} ${plage}` }
}

/** [CA5] « N variétés · Famille » au potager, « Famille » seule sinon, `null` sans famille connue. */
export function sousTitreCarte(ligne) {
  if (ligne?.hors_referentiel) return 'hors référentiel'
  if (!ligne?.au_potager) return ligne?.famille || null
  const n = ligne?.nb_varietes || 0
  const varietes = `${n} variété${n > 1 ? 's' : ''}`
  return ligne?.famille ? `${varietes} · ${ligne.famille}` : varietes
}

const LIBELLE_PHASE_COURT = Object.freeze({ semee: 'Semée', en_place: 'En place', en_recolte: 'En récolte' })

/**
 * [CA5] Le pied de carte, à gauche : phase la plus avancée + parcelles/lots,
 * « en pépinière · N lots » sans aucune ligne en terre, ou `null` (absente du
 * potager — la carte montre alors « pas au potager », CA5/CA7).
 */
export function presenceCarte(ligne) {
  if (ligne?.phase_plus_avancee) {
    // [CA5] Le mot de la phase est déjà porté par `PastillePhase` : `texte` ne
    // répète que ce qui la complète (parcelles, puis lots le cas échéant).
    const morceaux = [`${ligne.nb_parcelles} parcelle${ligne.nb_parcelles > 1 ? 's' : ''}`]
    if (ligne.nb_lots_pepiniere > 0) morceaux.push(`${ligne.nb_lots_pepiniere} lot${ligne.nb_lots_pepiniere > 1 ? 's' : ''}`)
    return { phase: ligne.phase_plus_avancee, texte: morceaux.join(' · ') }
  }
  if (ligne?.nb_lots_pepiniere > 0) {
    return { phase: 'en_pepiniere', texte: `${ligne.nb_lots_pepiniere} lot${ligne.nb_lots_pepiniere > 1 ? 's' : ''}` }
  }
  return null
}

/** Normalisation accent-insensible pour la recherche et la comparaison de familles. */
export const normaliser = (s) => (s || '').normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()

/**
 * [CA4] La recherche porte sur le nom, et — dans « Au potager » seulement —
 * sur les variétés cultivées.
 */
export function correspondRecherche(ligne, recherche, onglet) {
  const q = normaliser((recherche || '').trim())
  if (!q) return true
  if (normaliser(ligne.nom_culture).includes(q)) return true
  if (onglet === 'potager') {
    return (ligne.varietes || []).some((v) => normaliser(v).includes(q))
  }
  return false
}

/** [CA9 de l'écran Plan / CA3] Une culture visible dans l'onglet donné. */
export function visibleDansOnglet(ligne, onglet) {
  return onglet === 'potager' ? Boolean(ligne.au_potager || ligne.suggestion) : true
}

/** [CA3] Familles disponibles dans un ensemble de lignes, triées en français. */
export function famillesDisponibles(lignes) {
  return [...new Set((lignes || []).map((l) => l.famille).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'fr'))
}

/**
 * [CA2] Tri « confiance ↓ » — les étoiles d'abord (une culture sans étoile
 * jamais devant une étoilée), puis la fenêtre, puis le nom.
 */
export function comparerConfiance(a, b, { meteoDisponible = true } = {}) {
  const etoilesA = meteoDisponible ? (a.etoiles || 0) : 0
  const etoilesB = meteoDisponible ? (b.etoiles || 0) : 0
  return (etoilesB - etoilesA)
    || (ORDRE_FENETRE[a.fenetre_etat] - ORDRE_FENETRE[b.fenetre_etat])
    || a.nom_culture.localeCompare(b.nom_culture, 'fr')
}

export function comparerAlpha(a, b) {
  return a.nom_culture.localeCompare(b.nom_culture, 'fr')
}

/** [CA20] Tri « Par famille » : groupes titrés, hors-référentiel à part, triés dans chaque groupe par nom. */
export function grouperParFamille(lignes) {
  const groupes = new Map()
  for (const l of [...(lignes || [])].sort(comparerAlpha)) {
    const cle = l.hors_referentiel || !l.famille ? HORS_REFERENTIEL_LIBELLE : l.famille
    if (!groupes.has(cle)) groupes.set(cle, [])
    groupes.get(cle).push(l)
  }
  return [...groupes.entries()]
    .sort(([a], [b]) => (a === HORS_REFERENTIEL_LIBELLE) - (b === HORS_REFERENTIEL_LIBELLE) || a.localeCompare(b, 'fr'))
    .map(([famille, cultures]) => ({ famille, cultures }))
}

/**
 * [CA1-CA4] Applique recherche, filtre famille, filtre mois puis le tri
 * choisi à l'ensemble des lignes d'un onglet. `mois` est 1..12 ou `null`.
 */
export function listeFiltree(lignes, { onglet, recherche, famille, mois, tri, meteoDisponible = true } = {}) {
  const base = (lignes || []).filter((l) => visibleDansOnglet(l, onglet))
    .filter((l) => correspondRecherche(l, recherche, onglet))
    .filter((l) => !famille || l.famille === famille)
    .filter((l) => !mois || (l.mois_actifs || []).includes(mois))
  if (tri === TRI_ALPHA) return [...base].sort(comparerAlpha)
  if (tri === TRI_FAMILLE) return base  // [CA20] Regroupée par `grouperParFamille`, pas ici.
  return [...base].sort((a, b) => comparerConfiance(a, b, { meteoDisponible }))
}

/**
 * [CA4] « N autres dans Toutes → » — cultures qui correspondent à la
 * recherche mais ne sont pas dans le sous-ensemble courant de « Au potager ».
 */
export function autresDansToutes(toutesLesLignes, ligesOnglet, recherche) {
  const q = (recherche || '').trim()
  if (!q) return 0
  const dansOnglet = new Set((ligesOnglet || []).map((l) => l.culture))
  return (toutesLesLignes || []).filter((l) => !dansOnglet.has(l.culture) && correspondRecherche(l, recherche, 'toutes')).length
}

/** [CA19] Le nombre de filtres actifs — famille, mois, tri différent du défaut. */
export function nombreFiltresActifs({ famille, mois, tri }) {
  return (famille ? 1 : 0) + (mois ? 1 : 0) + (tri && tri !== TRI_PAR_DEFAUT ? 1 : 0)
}

/** [CA13] Le nom accessible d'une carte : culture, phase/présence, confiance, fenêtre. */
export function nomAccessibleCarte(ligne, { meteoDisponible = true } = {}) {
  const presence = presenceCarte(ligne)
  const presenceTexte = ligne.suggestion ? 'suggestion — pas au potager'
    : presence ? (presence.phase === 'en_pepiniere' ? 'en pépinière' : (LIBELLE_PHASE_COURT[presence.phase] || '').toLowerCase())
    : 'pas au potager'
  const confianceTexte = ligne.hors_referentiel ? 'hors référentiel'
    : !ligne.a_calendrier ? 'pas de calendrier'
    : !meteoDisponible ? 'confiance indisponible'
    : ligne.etoiles ? `confiance ${ligne.confiance_equivalent}, ${ligne.etoiles} étoile${ligne.etoiles > 1 ? 's' : ''} sur 3`
    : 'confiance indisponible'
  // [CA12] Confiance indisponible : la fenêtre reste dite, seule l'étoile disparaît.
  const fenetre = libelleFenetre(ligne)
  return [ligne.nom_culture, presenceTexte, confianceTexte, fenetre?.texte].filter(Boolean).join(', ')
}
