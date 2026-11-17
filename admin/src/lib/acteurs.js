// La vue « Potagers et jardiniers » [US-319] : tri, mise en forme et lignes de tableau. Toute l'arithmétique
// (coûts, parts, médiane, usage élevé, bandeau) est côté API ; ici, du texte et un tri.

import { euro, entier, pourcent, nombre, jourBref } from './format.js'
import { libelleCanal } from './cout.js'
import { libellePas } from './consommation.js'

export const ONGLETS = [
  { id: 'potagers', libelle: 'Potagers' },
  { id: 'utilisateurs', libelle: 'Jardiniers' },
]

/** [CA4] Les tris : le même jeu pour les deux onglets. `dernier` : le plus récent d'abord. */
export const TRIS = [
  { id: 'cout', libelle: 'Coût' },
  { id: 'appels', libelle: 'Appels' },
  { id: 'echanges', libelle: 'Échanges' },
  { id: 'dernier', libelle: 'Dernier appel' },
]

const valeurDeTri = {
  cout: (l) => (l.cout_micro_eur === null || l.cout_micro_eur === undefined ? -1 : l.cout_micro_eur),
  appels: (l) => l.appels,
  echanges: (l) => l.echanges,
  dernier: (l) => (l.dernier_appel ? Date.parse(l.dernier_appel) : -1),
}

/** Trie sans modifier l'entrée : décroissant, puis libellé. La ligne « tâches automatiques » reste en dernier. */
export function trier(lignes, tri) {
  const lire = valeurDeTri[tri] || valeurDeTri.cout
  return [...lignes].sort((a, b) => (
    Number(Boolean(a.automatique)) - Number(Boolean(b.automatique))
    || lire(b) - lire(a)
    || String(a.libelle).localeCompare(String(b.libelle), 'fr')
  ))
}

export const jour = (iso) => (iso ? jourBref(iso) : '—')
export const pc = (v) => (v === null || v === undefined ? '—' : pourcent(v, 1))

/** [CA3] Le bandeau : cinq chiffres, chacun avec une précision. */
export function chiffresBandeau(b) {
  const actifsP = b.potagers_actifs
  const actifsJ = b.jardiniers_actifs
  return [
    { id: 'potagers', libelle: 'Potagers existants', texte: entier(b.potagers_existants), note: `${entier(actifsP)} actif${actifsP > 1 ? 's' : ''} sur la période` },
    { id: 'jardiniers', libelle: 'Jardiniers inscrits', texte: entier(b.jardiniers_inscrits), note: `${entier(actifsJ)} actif${actifsJ > 1 ? 's' : ''} sur la période` },
    { id: 'mediane', libelle: 'Coût médian par jardinier actif', texte: euro(b.cout_median_par_jardinier_micro_eur), note: actifsJ ? 'sur la période' : 'aucun jardinier actif' },
    { id: 'p95', libelle: 'Coût P95 par jardinier actif', texte: euro(b.cout_p95_par_jardinier_micro_eur), note: 'sur la période' },
    { id: 'decile', libelle: 'Part du coût du premier décile', texte: pc(b.part_cout_premier_decile), note: 'jardiniers actifs les plus coûteux' },
  ]
}

export const DEFINITION_ACTIF = 'Un potager ou un jardinier actif a au moins une ligne de provenance « usage » sur la période.'

/** [CA7] Le signalement « usage élevé » et sa règle (affichée par l'écran). */
export const regleUsageElevee = (b) => b.regle_usage_eleve

// La part du coût est la dernière colonne : c'est là que le tableau dessine sa barre de part.
const COLONNES_COMMUNES = [
  { id: 'cout', libelle: 'Coût' },
  { id: 'appels', libelle: 'Appels' },
  { id: 'echanges', libelle: 'Échanges' },
  { id: 'jetons', libelle: 'Jetons entrée / sortie' },
  { id: 'echec', libelle: 'Taux d’échec' },
  { id: 'dernier', libelle: 'Dernier appel' },
  { id: 'canaux', libelle: 'Canaux' },
  { id: 'part', libelle: 'Part du coût' },
]
export const COLONNES_POTAGERS = [{ id: 'membres', libelle: 'Membres' }, ...COLONNES_COMMUNES]
export const COLONNES_JARDINIERS = [{ id: 'potagers', libelle: 'Potagers' }, { id: 'inscrit', libelle: 'Inscrit le' }, ...COLONNES_COMMUNES]

const libelleCanaux = (canaux) => (canaux.length ? canaux.map(libelleCanal).join(', ') : '—')

function cellulesCommunes(l) {
  return {
    cout: euro(l.cout_micro_eur),
    part: pc(l.part_cout),
    appels: entier(l.appels),
    echanges: entier(l.echanges),
    jetons: `${entier(l.jetons_entree)} / ${entier(l.jetons_sortie)}`,
    echec: pc(l.taux_echec),
    dernier: jour(l.dernier_appel),
    canaux: libelleCanaux(l.canaux),
  }
}

/** Les notes d'une ligne : « usage élevé » (avec la règle dans le bandeau), « aucun appel ». */
function note(l) {
  if (l.usage_eleve) return 'Usage élevé'
  if (l.automatique) return 'Appels de fond, sans jardinier'
  return l.appels === 0 ? 'Aucun appel sur la période' : ''
}

export function lignesPotagers(lignes, tri) {
  return trier(lignes, tri).map((l) => ({
    cle: String(l.id), id: l.id, titre: l.libelle, usageEleve: l.usage_eleve, note: note(l), part: l.part_cout || 0,
    cellules: { membres: entier(l.membres), ...cellulesCommunes(l) },
  }))
}

export function lignesJardiniers(lignes, tri) {
  return trier(lignes, tri).map((l) => ({
    cle: l.automatique ? 'automatique' : String(l.id), id: l.id, titre: l.libelle, usageEleve: l.usage_eleve, note: note(l), part: l.part_cout || 0,
    automatique: l.automatique,
    cellules: { potagers: l.potagers === null ? '—' : entier(l.potagers), inscrit: l.inscrit_le ? jour(l.inscrit_le) : '—', ...cellulesCommunes(l) },
  }))
}

// ── Fiches [CA5, CA6] ───────────────────────────────────────────────────────────────────────────

/** Un graphique à une série, à la forme que `Graphique` attend. */
function modeleUneSerie(graphique, cle, libelle) {
  const valeurs = graphique[cle].map((v) => v || 0)
  const points = graphique.points.map((p) => ({ cle: p, libelle: libellePas(p, graphique.pas) }))
  const total = valeurs.reduce((a, v) => a + v, 0)
  return { mode: 'empile', pas: graphique.pas, points, series: [{ cle, libelle, valeurs, total, part: total ? 1 : null }], total: valeurs, cache: [] }
}
export const modeleCout = (graphique) => modeleUneSerie(graphique, 'cout_micro_eur', 'Coût')
export const modeleAppels = (graphique) => modeleUneSerie(graphique, 'appels', 'Appels')
export const aucunAppel = (graphique) => graphique.appels.every((v) => !v)

export const COLONNES_REPARTITION = [
  { id: 'appels', libelle: 'Appels' },
  { id: 'cout', libelle: 'Coût' },
  { id: 'part', libelle: 'Part du coût' },
]

/** La répartition par type d'appel ou par canal. `canal` : libellés de canal de l'application. */
export function lignesRepartition(lignes, canal = false) {
  return lignes.map((l) => ({
    cle: String(l.cle), titre: canal ? libelleCanal(l.cle) : String(l.libelle), mono: !canal, part: l.part || 0,
    cellules: { appels: entier(l.appels), cout: euro(l.cout_micro_eur), part: pc(l.part) },
  }))
}

export const COLONNES_PARTAGE = [
  { id: 'role', libelle: 'Rôle' },
  { id: 'appels', libelle: 'Appels' },
  { id: 'cout', libelle: 'Coût' },
  { id: 'part', libelle: 'Part de la consommation' },
]
const ROLES = { owner: 'propriétaire', editor: 'éditeur', lecteur: 'lecteur' }

/** Les membres d'un potager (ou les potagers d'un jardinier) avec leur part de la consommation. */
export function lignesPartage(lignes) {
  return lignes.map((l) => ({
    cle: l.automatique ? 'automatique' : String(l.id), titre: l.libelle, part: l.part || 0,
    cellules: { role: l.role ? (ROLES[l.role] || l.role) : '—', appels: entier(l.appels), cout: euro(l.cout_micro_eur), part: pc(l.part) },
  }))
}

/** « ok 12 · erreur 2 » — les issues de la période, dans l'ordre de l'API. */
export function texteIssues(issues) {
  const paires = Object.entries(issues)
  return paires.length ? paires.map(([i, n]) => `${i} ${entier(n)}`).join(' · ') : 'aucun appel'
}

/** Le coût médian d'un échange et le nombre d'échanges de la fiche. */
export function resumeEchange(echange) {
  if (!echange.nb) return { texte: '—', note: 'aucun échange sur la période' }
  return {
    texte: euro(echange.cout_micro_eur.mediane),
    note: `${entier(echange.nb)} échange${echange.nb > 1 ? 's' : ''} · ${nombre(echange.appels.mediane, Number.isInteger(echange.appels.mediane) ? 0 : 1)} appel${echange.appels.mediane > 1 ? 's' : ''} médian${echange.appels.mediane > 1 ? 's' : ''}`,
  }
}
