// [US-183] Fiche calendrier d'une culture — ce que ses trois parties affichent.
//
// Tout vient de deux lectures déjà servies : `GET /plan/calendriers` (fenêtres,
// zone, attributions, projections des séries en terre — US-176 / US-070) et
// `GET /plan/confiances/candidates` (US-178 / US-180). Ici, rien que du choix et
// de la mise en forme : aucune date n'est calculée, aucune n'est inventée.
import {
  TIRET, MOIS_NOMS, friseDeCulture, friseRecalee, jourLisible, zoneAffichable,
  attributionsAffichables,
} from './calendrier.js'

const minuscule = (v) => (v || '').trim().toLowerCase()

/**
 * [CA5] Une fenêtre du référentiel en clair : « avril à juin », « mai », ou un
 * tiret. `mois` est la liste 1..12 servie par le calendrier, dans l'ordre de la
 * fenêtre (une fenêtre qui enjambe l'année commence en novembre et finit en
 * février : son premier et son dernier mois restent ses bornes).
 */
export function fenetreLisible(mois) {
  const valides = (mois || []).filter((m) => Number.isInteger(m) && m >= 1 && m <= 12)
  if (valides.length === 0) return TIRET
  const [debut, fin] = [valides[0], valides[valides.length - 1]]
  return debut === fin ? MOIS_NOMS[debut - 1] : `${MOIS_NOMS[debut - 1]} à ${MOIS_NOMS[fin - 1]}`
}

/** Clé de `mois` dans `GET /plan/calendriers` pour une action du moteur. */
const PHASE_SERVEUR = { semis_pepiniere: 'semis_pepiniere', semis_pleine_terre: 'semis_pleine_terre', plantation: 'plantation' }

/** [CA5] Fenêtre conseillée de l'action choisie, pour la zone du potager. */
export function fenetreDeAction(calendriers, culture, action) {
  const mois = calendriers?.cultures?.[culture]?.mois?.[PHASE_SERVEUR[action]]
  return fenetreLisible(mois)
}

// ── Partie 2 — déjà en terre ─────────────────────────────────────────────────

/** « 22 avril », « 16 – 26 juillet », « 28 juin – 5 juillet » : une plage, jamais une date sèche. */
export function plageCourte(plage) {
  if (!plage?.debut || !plage?.fin) return null
  if (plage.debut === plage.fin) return jourLisible(plage.debut)
  const [, mD, jD] = plage.debut.split('-').map(Number)
  const [, mF] = plage.fin.split('-').map(Number)
  return mD === mF
    ? `${jD === 1 ? '1er' : jD} – ${jourLisible(plage.fin)}`
    : `${jourLisible(plage.debut)} – ${jourLisible(plage.fin)}`
}

const jours = (n) => `${n} jour${n > 1 ? 's' : ''}`

/**
 * [CA9] Pourquoi une série n'a pas de projection — dit, jamais masqué
 * (US-070 / CA11). Les codes sont ceux de `recalage_calendrier.MOTIF_*`.
 */
const RAISON_SANS_PROJECTION = {
  referentiel_absent: 'Aucun calendrier pour cette culture : aucune projection n’est calculée.',
  plantation_sans_semis: 'Durée entre plantation et récolte inconnue pour cette culture : aucune projection n’est calculée.',
  contexte_inconnu: 'Semis sans filière connue (pépinière ou pleine terre) : aucune projection n’est calculée.',
  duree_recolte_absente: 'Durée inconnue pour cette culture : aucune projection n’est calculée.',
}
const RAISON_PAR_DEFAUT = RAISON_SANS_PROJECTION.duree_recolte_absente

/** [CA8] Le geste d'origine en clair : « Semée en place le 12 avril », « Plantée le 20 octobre ». */
function origineLisible(origine) {
  if (!origine?.date) return null
  const jour = jourLisible(origine.date)
  if (origine.action === 'plantation') return `Plantée le ${jour}`
  const filiere = { pepiniere: ' en pépinière', pleine_terre: ' en place' }[origine.contexte] || ''
  return `Semée${filiere} le ${jour}`
}

/**
 * [CA8, CA9, CA12 d'US-070] Une série en terre, telle que la carte l'affiche.
 * `enAvant` : c'est la série de la parcelle depuis laquelle la fiche a été
 * ouverte (US-183 / CA2).
 */
export function carteDeSerie(projection, parcelleIdEnAvant = null) {
  const p = projection || {}
  const sansProjection = !p.etat || p.etat === 'sans_recalage'
  const constatee = p.recolte_reelle?.premiere
  const r = p.jours_restants
  let reste = null
  if (!sansProjection && r && p.etat !== 'en_recolte' && p.etat !== 'recolte_depassee') {
    reste = r.min === r.max ? jours(r.min) : `${r.min} à ${jours(r.max)}`
  }
  return {
    parcelleId: p.parcelle_id ?? null,
    parcelle: p.parcelle_nom || TIRET,
    variete: p.variete || null,
    origine: p.origine?.action === 'plantation' ? 'plantation' : 'semis',
    origineLisible: origineLisible(p.origine),
    levee: sansProjection ? null : plageCourte(p.levee_attendue),
    // [US-070 / CA5] Une récolte commencée remplace l'attendue.
    recolteLibelle: constatee ? '1ʳᵉ récolte constatée' : '1ʳᵉ récolte attendue',
    recolte: constatee ? jourLisible(constatee) : (sansProjection ? null : plageCourte(p.recolte_attendue)),
    reste,
    ecart: p.etat === 'recolte_depassee' && p.retard_jours
      ? `Récolte attendue il y a ${jours(p.retard_jours)}, aucune récolte notée`
      : null,
    raisonSansProjection: sansProjection ? (RAISON_SANS_PROJECTION[p.motif] || RAISON_PAR_DEFAUT) : null,
    autresSeries: p.series_suivantes || 0,
    enAvant: parcelleIdEnAvant != null && p.parcelle_id === parcelleIdEnAvant,
    // Pour la frise (CA11) : la série la plus ancienne qui SAIT se projeter.
    _projection: p,
  }
}

/**
 * [CA8] Toutes les séries en terre de la culture, TOUTES variétés confondues
 * (le calendrier est au niveau culture), la plus ancienne en tête.
 */
export function seriesDeCulture(calendriers, culture, parcelleIdEnAvant = null) {
  const date = (p) => p.origine?.date || p.plantation_reelle || '9999-12-31'
  return (calendriers?.projections || [])
    .filter((p) => minuscule(p.culture) === minuscule(culture))
    .sort((a, b) => date(a).localeCompare(date(b)))
    .map((p) => carteDeSerie(p, parcelleIdEnAvant))
}

// ── Partie 3 — frise ─────────────────────────────────────────────────────────

/**
 * [CA11] La frise de la fiche : RECALÉE sur la plus ancienne série en terre qui
 * se projette, CONSEILLÉE sinon — et elle dit laquelle des deux elle montre.
 */
export function friseDeFiche(calendriers, culture, series) {
  const ancre = (series || []).find((s) => friseRecalee(s._projection))
  if (ancre) {
    return {
      frise: friseRecalee(ancre._projection),
      recalee: true,
      titre: `Calendrier recalé sur la série de ${ancre.parcelle}`,
    }
  }
  const frise = friseDeCulture(calendriers, culture)
  const zone = zoneAffichable(calendriers)?.zone
  return {
    frise,
    recalee: false,
    titre: frise.degrade
      ? 'Aucune fenêtre connue pour cette zone'
      : `Calendrier conseillé pour la zone ${zone || TIRET}`,
  }
}

/** [CA16] Attribution du référentiel, une seule fois dans la fiche. */
export const attributionDeFiche = (calendriers) => attributionsAffichables(calendriers).join(' · ') || null
