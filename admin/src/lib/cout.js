// Vue Coût [US-313] : ce qui transforme les réponses de `/admin/pilotage/cout`, `series` et `ventilation`
// en ce que l'écran affiche. Les sommes, médianes et projections sont celles de l'API ; ici, seulement de
// la mise en forme, le regroupement « Autres » des séries, et la marge d'un abonnement (le prix n'existe
// que sur l'appareil, l'API ne le connaît pas).
import { euro, entier, nombre, pourcent, jourBref } from './format.js'
import { grouperAutres, libellePas } from './consommation.js'

/** « Ventiler par » du graphique de coût [CA3]. */
export const DIMENSIONS_COUT = [
  { id: 'modele', libelle: 'Modèle' },
  { id: 'appel_type', libelle: 'Type' },
  { id: 'canal', libelle: 'Canal' },
]

/** Libellés de canaux de l'application, pour le tableau « coût d'un échange ». */
export const LIBELLES_CANAL = { telegram: 'Telegram', pwa: 'Application', mcp: 'Assistants (MCP)', fond: 'Tâches de fond', outil: 'Outils', inconnu: 'Inconnu' }
export const libelleCanal = (canal) => LIBELLES_CANAL[canal] || canal

/** « 1 nov. – 10 nov. » */
const fenetre = (m) => `${jourBref(m.depuis)} – ${jourBref(m.jusqu_a)}`

/** Les quatre chiffres clés du bandeau [CA1]. Aucun n'a d'écart : la vue ne compare pas à la période précédente. */
export function chiffresCles(cout) {
  const nonChiffre = cout.appels > 0 && cout.cout_micro_eur === null
  const actifs = cout.jardiniers_actifs
  return [
    { id: 'periode', libelle: 'Coût de la période', valeur: cout.cout_micro_eur, texte: euro(cout.cout_micro_eur),
      note: nonChiffre ? 'aucun appel chiffré' : `${entier(cout.appels)} appel${cout.appels > 1 ? 's' : ''}` },
    { id: 'mois', libelle: 'Coût du mois en cours', valeur: cout.mois.cout_micro_eur, texte: euro(cout.mois.cout_micro_eur),
      note: fenetre(cout.mois) },
    { id: 'projection', libelle: 'Projection fin de mois', valeur: cout.mois.projection_fin_de_mois_micro_eur,
      texte: euro(cout.mois.projection_fin_de_mois_micro_eur), note: 'moyenne des 7 derniers jours prolongée' },
    { id: 'par_actif', libelle: 'Coût par jardinier actif', valeur: cout.cout_par_jardinier_actif_micro_eur,
      texte: euro(cout.cout_par_jardinier_actif_micro_eur),
      note: `${entier(actifs)} jardinier${actifs > 1 ? 's' : ''} actif${actifs > 1 ? 's' : ''}` },
  ]
}

/** [CA2] La définition, affichée sous le bandeau. */
export const DEFINITION_ACTIF = 'Un jardinier actif est un utilisateur ayant au moins une ligne de provenance « usage » sur la période.'

/** [CA9] La mention de périmètre du coût. */
export const MENTION_TARIF = 'Coût estimé au tarif public, hors palier gratuit.'

/** [CA7] « 12 appels non chiffrés » et les modèles concernés ; `null` quand tout est chiffré. */
export function avertissementNonChiffres(cout) {
  const n = cout.lignes_non_chiffrees
  if (!n) return null
  return {
    titre: `${entier(n)} appel${n > 1 ? 's' : ''} non chiffré${n > 1 ? 's' : ''}`,
    detail: 'Modèle absent de la grille tarifaire : ces appels ne sont pas dans les montants.',
    modeles: cout.modeles_non_chiffres.map((m) => ({ modele: m.modele, appels: m.appels, texte: `${m.modele} (${entier(m.appels)})` })),
  }
}

/** [CA8] La version de grille dominante de la période. */
export function texteGrille(cout) {
  if (!cout.tarif_version) return 'Grille tarifaire : aucune ligne chiffrée sur la période'
  const autres = Object.keys(cout.versions_tarif).length - 1
  return `Grille tarifaire ${cout.tarif_version}${autres > 0 ? ` · ${autres} autre${autres > 1 ? 's' : ''} version${autres > 1 ? 's' : ''} sur la période` : ''}`
}

/** Le graphique de coût par jour, ventilé [CA3]. Un pas sans ligne chiffrée vaut zéro ici : le graphique
 *  montre des euros, et le nombre d'appels non chiffrés est signalé à part (CA7). */
export function modeleGraphiqueCout(serie) {
  const points = serie.points.map((p) => ({ cle: p, libelle: libellePas(p, serie.pas) }))
  const utiles = serie.series.map((s) => ({
    cle: s.cle, libelle: String(s.cle).replace(/^mistral\//, ''),
    valeurs: s.valeurs.map((v) => v || 0), total: s.total || 0,
  })).filter((s) => s.total > 0)
  const grandTotal = utiles.reduce((a, s) => a + s.total, 0)
  const series = grouperAutres(utiles).map((s) => ({ ...s, part: grandTotal ? s.total / grandTotal : null }))
  return { mode: 'empile', pas: serie.pas, points, series, total: serie.total.map((v) => v || 0), cache: [] }
}

export const aucunCout = (serie) => serie.series.every((s) => !s.total)

/** [CA4] Le coût d'un échange par canal. */
export function lignesEchanges(cout) {
  return cout.echanges_par_canal.map((l) => ({
    cle: l.canal,
    titre: libelleCanal(l.canal),
    cellules: {
      echanges: entier(l.nb_echanges),
      mediane: euro(l.cout_micro_eur.mediane),
      p95: euro(l.cout_micro_eur.p95),
      maximum: euro(l.cout_micro_eur.maximum),
      appels: nombre(l.appels.mediane, Number.isInteger(l.appels.mediane) ? 0 : 1),
    },
    note: l.echanges_non_chiffres ? `${entier(l.echanges_non_chiffres)} échange${l.echanges_non_chiffres > 1 ? 's' : ''} non chiffré${l.echanges_non_chiffres > 1 ? 's' : ''}` : '',
  }))
}

export const COLONNES_ECHANGES = [
  { id: 'echanges', libelle: 'Échanges' },
  { id: 'mediane', libelle: 'Coût médian' },
  { id: 'p95', libelle: 'P95' },
  { id: 'maximum', libelle: 'Maximum' },
  { id: 'appels', libelle: 'Appels médians' },
]

/** [CA5] Les potagers les plus coûteux. */
export function lignesPotagers(ventilation) {
  return ventilation.lignes.map((l) => ({
    cle: l.cle,
    titre: l.libelle,
    part: l.part,
    cellules: {
      cout: euro(l.cout_micro_eur),
      appels: entier(l.appels),
      part: l.part === null || l.part === undefined ? '—' : pourcent(l.part, 1),
    },
  }))
}

export const COLONNES_POTAGERS = [
  { id: 'cout', libelle: 'Coût' },
  { id: 'appels', libelle: 'Appels' },
  { id: 'part', libelle: 'Part du total' },
]

// ── CA6 : la marge d'un abonnement ──────────────────────────────────────────────────────────────

/** « 3 », « 3,50 », « 3.5 », « 3,5 € » → 3.5 ; vide, illisible ou négatif → null. */
export function lirePrix(texte) {
  const propre = String(texte ?? '').replace(/€/g, '').replace(/[\s  ]/g, '').replace(',', '.')
  if (!/^\d+(\.\d{0,2})?$/.test(propre)) return null
  const valeur = Number(propre)
  return Number.isFinite(valeur) ? valeur : null
}

/**
 * La marge mensuelle pour un prix donné : le prix moins le coût mensuel (30 jours) du jardinier actif
 * médian, puis du jardinier au P95. `null` sans prix lisible ou sans jardinier actif.
 */
export function marge(prixEuros, parJardinier) {
  if (prixEuros === null || prixEuros === undefined || !parJardinier.nb) return null
  const ligne = (cout) => {
    if (cout === null || cout === undefined) return null
    const margeMicro = Math.round(prixEuros * 1_000_000 - cout)
    return { coutMicro: cout, margeMicro, positive: margeMicro >= 0, texte: euro(margeMicro), cout: euro(cout) }
  }
  return { mediane: ligne(parJardinier.mensuel.mediane), p95: ligne(parJardinier.mensuel.p95) }
}

/** Le prix saisi se garde sur l'appareil, jamais envoyé nulle part [CA6]. */
export const CLE_PRIX = 'pilotage_prix_abonnement'
export function lirePrixGarde(stockage) {
  try { return stockage.getItem(CLE_PRIX) || '' } catch { return '' }
}
export function garderPrix(stockage, texte) {
  try {
    if (texte) stockage.setItem(CLE_PRIX, texte)
    else stockage.removeItem(CLE_PRIX)
  } catch { /* appareil sans stockage : le prix ne survivra pas au rechargement */ }
}
