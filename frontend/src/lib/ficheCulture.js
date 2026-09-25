// [US-207 / CA14] Fiche culture — composition SANS React, pour que `npm test`
// couvre la mise en forme sans monter de composant. Deux lectures déjà
// servies par ailleurs alimentent la section « Maintenant » : le calendrier
// de zone (`GET /plan/calendriers`) et la confiance (`GET /plan/confiances/candidates`,
// mêmes réponses que la fiche calendrier d'US-183) — rien n'est recalculé ici,
// seulement choisi et mis en forme (point de vigilance de l'US : deux valeurs
// différentes entre la carte, la fiche culture et la fiche calendrier au même
// instant sont un bug).
import { actionsDeFiche, meilleureCandidate, recolteLisible, meteoIndeterminee, libelleAction } from './confiance.js'
import { fenetreDeAction } from './ficheCalendrier.js'

/** L'état de la règle R1 (« dans la fenêtre conseillée ») d'une évaluation. */
function etatFenetre(action) {
  return (action?.motifs || []).find((m) => m.regle === 'R1')?.etat ?? null
}

/**
 * [CA4] Ce que « Maintenant » affiche : le geste le mieux noté, ouvert ou non,
 * et l'état au potager. `entree` est `confiances.cultures[culture]` (ou
 * `null`/`undefined` si la lecture a échoué) ; `calendriers` sert à lire la
 * fenêtre du geste choisi. Jamais de valeur devinée : une confiance illisible
 * se dit, un geste sans fenêtre pour la zone se dit aussi (CA5 côté fiche
 * calendrier, même honnêteté ici).
 */
export function sectionMaintenant({ entree, calendriers, culture, confianceLue }) {
  if (!confianceLue) {
    return { etat: 'illisible' }
  }
  const actions = actionsDeFiche(entree)
  if (!entree?.a_calendrier || actions.length === 0) {
    return { etat: 'sans_calendrier' }
  }
  const meilleure = meilleureCandidate(actions)
  const geste = libelleAction(meilleure.action)
  const fenMois = fenetreDeAction(calendriers, culture, meilleure.action)
  const ouverte = etatFenetre(meilleure) === 'gagne'
  return {
    etat: ouverte ? 'ouverte' : 'fermee',
    geste,
    etoiles: meilleure.etoiles,
    fenMois,
    recolteAttendue: ouverte ? recolteLisible(meilleure) : null,
    meteoIndeterminee: meteoIndeterminee(meilleure),
  }
}

const LIBELLE_PHASE_COURT = { semee: 'Semée', en_place: 'En place', en_recolte: 'En récolte' }

/**
 * [CA4] « en récolte sur 2 parcelles · 1 lot en pépinière », « pas au potager » —
 * l'union des parcelles et des lots de pépinière de TOUTES les variétés
 * cultivées de la fiche (US-206), jamais recalculée : `varietesCultivees`
 * vient telle quelle de `GET /cultures/{culture}/fiche`.
 */
export function etatAuPotager(varietesCultivees) {
  const parcelles = new Map()
  let lots = 0
  let phase = null
  for (const v of varietesCultivees || []) {
    for (const p of v.parcelles || []) {
      parcelles.set(p.parcelle_id, true)
      if (!phase) phase = p.phase
    }
    lots += (v.lots_pepiniere || []).length
  }
  const partieParcelles = parcelles.size > 0
    ? `${LIBELLE_PHASE_COURT[phase] || 'En place'} sur ${parcelles.size} parcelle${parcelles.size > 1 ? 's' : ''}`
    : null
  const partieLots = lots > 0 ? `${lots} lot${lots > 1 ? 's' : ''} en pépinière` : null
  return [partieParcelles, partieLots].filter(Boolean).join(' · ') || 'Pas au potager'
}

const LIBELLE_ORGANE = { 'végétatif': 'Végétatif', 'reproducteur': 'Reproducteur' }

/**
 * [CA6] Les neuf lignes fixes du bloc Référentiel, dans l'ordre de la
 * maquette gelée. Attributs et durées portent déjà leur libellé et leur
 * affichage honnête (« non renseigné », fourchette) depuis le serveur — cette
 * fonction ne fait qu'assembler, jamais recalculer une valeur agronomique.
 */
export function lignesReferentiel(fiche) {
  const familleTexte = fiche?.famille
    ? `${fiche.famille}${fiche.delai_retour_annees ? ` · retour ${fiche.delai_retour_annees} an${fiche.delai_retour_annees > 1 ? 's' : ''}` : ''}`
    : null
  const lignes = [{ cle: 'famille', libelle: 'Famille · délai de retour', valeur: familleTexte }]
  for (const a of fiche?.attributs || []) lignes.push({ cle: a.cle, libelle: a.libelle, valeur: a.affichage })
  for (const d of fiche?.durees || []) lignes.push({ cle: d.etape, libelle: d.libelle, valeur: d.affichage })
  lignes.push({ cle: 'organe', libelle: 'Organe récolté', valeur: LIBELLE_ORGANE[fiche?.type_organe_recolte] || null })
  return lignes
}

/**
 * [CA22] Les quatre groupes de voisinages : favorables et défavorables
 * établis en premier, puis la pratique traditionnelle (pointillé, sans
 * preuve établie) — jamais rendus par la seule couleur (RT4), le signe est
 * toujours écrit par l'appelant.
 */
export function groupesVoisinages(associations) {
  const grp = { favorablesEtablis: [], defavorablesEtablis: [], favorablesTrad: [], defavorablesTrad: [] }
  for (const a of associations || []) {
    if (a.nature === 'favorable' && a.niveau_preuve === 'etabli') grp.favorablesEtablis.push(a)
    else if (a.nature === 'defavorable' && a.niveau_preuve === 'etabli') grp.defavorablesEtablis.push(a)
    else if (a.nature === 'favorable') grp.favorablesTrad.push(a)
    else if (a.nature === 'defavorable') grp.defavorablesTrad.push(a)
  }
  return grp
}

/** [CA20] Le badge d'en-tête, seulement depuis une parcelle (Plan, Parcelles). */
export function badgeContexte({ nomParcelle, rang } = {}) {
  if (!nomParcelle) return null
  return `depuis ${nomParcelle}${rang != null ? ` · rang ${rang}` : ''}`
}

/** [CA21] Les sources dédoublonnées du pied de fiche, une seule ligne. */
export const sourcesDeFiche = (fiche) => (fiche?.attributions || []).join(' · ') || null
