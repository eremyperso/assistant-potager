// Vue Fiabilité [US-314] : mise en forme des réponses de `/admin/pilotage/fiabilite` et `series`
// (dimension `issue`). Les décomptes, taux et percentiles sont ceux de l'API ; l'écran ne calcule que
// des écarts à la période précédente.
import { entier, pourcent, millisecondes, jourBref, jourCourt } from './format.js'
import { ecart, SENS } from './ecart.js'
import { libellePas } from './consommation.js'

/** Les cinq chiffres clés du bandeau [CA1]. Les taux s'écartent en points (un taux de quota de 1,2 %
 *  à 1,9 %, c'est 0,7 point — pas « +58 % »). */
export function chiffresCles(fiabilite) {
  const m = fiabilite.mesures
  const p = fiabilite.mesures_precedentes
  const points = { mode: 'points', decimales: 1 }
  return [
    { id: 'succes', libelle: 'Taux de succès', valeur: m.taux_succes, texte: pourcent(m.taux_succes, 1),
      ecart: ecart(m.taux_succes, p.taux_succes, { sens: SENS.BONNE, ...points }) },
    { id: 'quota', libelle: 'Taux de quota', valeur: m.taux_quota, texte: pourcent(m.taux_quota, 1),
      ecart: ecart(m.taux_quota, p.taux_quota, { sens: SENS.MAUVAISE, ...points }) },
    { id: 'erreur', libelle: "Taux d'erreur", valeur: m.taux_erreur, texte: pourcent(m.taux_erreur, 1),
      ecart: ecart(m.taux_erreur, p.taux_erreur, { sens: SENS.MAUVAISE, ...points }) },
    { id: 'p50', libelle: 'Latence P50', valeur: m.latence_p50_ms, texte: millisecondes(m.latence_p50_ms),
      ecart: ecart(m.latence_p50_ms, p.latence_p50_ms, { sens: SENS.MAUVAISE }) },
    { id: 'p95', libelle: 'Latence P95', valeur: m.latence_p95_ms, texte: millisecondes(m.latence_p95_ms),
      ecart: ecart(m.latence_p95_ms, p.latence_p95_ms, { sens: SENS.MAUVAISE }) },
  ]
}

export const periodeSansAppel = (fiabilite) => fiabilite.mesures.appels === 0

/** [CA7] La latence des échecs, donnée à part, sous le bandeau. */
export function texteLatenceEchecs(fiabilite) {
  const m = fiabilite.mesures
  if (m.latence_echecs_p50_ms === null) return 'Aucun échec sur la période.'
  return `Latence des échecs : P50 ${millisecondes(m.latence_echecs_p50_ms)} · P95 ${millisecondes(m.latence_echecs_p95_ms)}`
}

export const NOTE_LATENCE = 'Latences calculées sur les appels réussis seulement ; celle des échecs est donnée à part.'

/** Le graphique par jour des issues [CA2] : toute issue que l'API rend, sans regroupement ni filtre, y
 *  compris une valeur que l'écran ne connaît pas. Le total d'un pas est la pile. */
export function modeleGraphiqueIssues(serie) {
  const points = serie.points.map((p) => ({ cle: p, libelle: libellePas(p, serie.pas) }))
  const total = serie.series.reduce((a, s) => a + (s.total || 0), 0)
  const series = serie.series.map((s) => ({
    cle: s.cle, libelle: String(s.cle), valeurs: s.valeurs.map((v) => v || 0), total: s.total || 0,
    part: total ? (s.total || 0) / total : null,
  }))
  return { mode: 'empile', pas: serie.pas, points, series, total: serie.total.map((v) => v || 0), cache: [] }
}

/** Les colonnes communes aux deux tableaux [CA3, CA4]. « Autres » : les issues hors des quatre
 *  connues (`voix_inconnue`…), pour que les colonnes se somment à « Appels ». */
export const COLONNES_ISSUES = [
  { id: 'appels', libelle: 'Appels' },
  { id: 'succes', libelle: 'Succès' },
  { id: 'quota', libelle: 'Quota' },
  { id: 'erreur', libelle: 'Erreur' },
  { id: 'delai', libelle: 'Délai' },
  { id: 'autres', libelle: 'Autres' },
  { id: 'p50', libelle: 'P50' },
  { id: 'p95', libelle: 'P95' },
]

export function lignesIssues(lignes) {
  return lignes.map((l) => {
    const autres = Object.values(l.autres).reduce((a, b) => a + b, 0)
    return {
      cle: l.cle,
      titre: String(l.cle).replace(/^mistral\//, ''),
      mono: true,
      cellules: {
        appels: entier(l.appels), succes: entier(l.succes), quota: entier(l.quota), erreur: entier(l.erreur),
        delai: entier(l.delai), autres: autres ? entier(autres) : '—',
        p50: millisecondes(l.latence_p50_ms), p95: millisecondes(l.latence_p95_ms),
      },
      note: autres ? Object.entries(l.autres).map(([i, n]) => `${i} : ${entier(n)}`).join(' · ') : '',
    }
  })
}

// ── CA5 : grille heure × jour ──────────────────────────────────────────────────────────────────

/** Un texte lisible pour une cellule : « lun. 9 nov., 14 h : 3 appels en quota ». */
export function descriptionCellule(jour, heure, n) {
  return `${jourCourt(jour)}, ${heure} h : ${n === 0 ? 'aucun appel' : `${entier(n)} appel${n > 1 ? 's' : ''}`} en quota`
}

export const titreGrille = (grille) => `du ${jourBref(grille.depuis)} au ${jourBref(grille.jusqu_a)}`

// ── CA6 : derniers échecs ──────────────────────────────────────────────────────────────────────

/** « 10 nov. 14 h 32 » depuis « 2026-11-10T14:32:05 » (heure du serveur, sans conversion). */
export function heureEchec(echec) {
  const iso = echec.cree_le || `${echec.date}T00:00`
  const [jour, h = '00:00'] = iso.split('T')
  const [hh, mm] = h.split(':')
  return `${jourBref(jour)} ${Number(hh)} h ${mm}`
}

export function lignesEchecs(echecs) {
  return echecs.map((e, i) => ({
    cle: `${e.cree_le}-${i}`,
    titre: heureEchec(e),
    cellules: {
      type: e.appel_type, modele: String(e.modele).replace(/^mistral\//, ''), issue: e.issue, canal: e.canal,
      latence: millisecondes(e.latence_ms),
    },
  }))
}

export const COLONNES_ECHECS = [
  { id: 'type', libelle: 'Type' },
  { id: 'modele', libelle: 'Modèle', mono: true },
  { id: 'issue', libelle: 'Issue' },
  { id: 'canal', libelle: 'Canal' },
  { id: 'latence', libelle: 'Latence' },
]
