// Vue Consommation [US-312] : tout ce qui transforme les réponses de `/admin/pilotage/...` en ce
// que l'écran affiche. Aucune arithmétique propre à l'écran : les chiffres affichés SONT ceux de
// l'API (CA10), seulement mis en forme ; les écarts, parts et regroupements sont les seules
// opérations faites ici, et chacune a son test.
import { compact, entier, pourcent, nombre, jourBref, abrege } from './format.js'
import { ecart, SENS } from './ecart.js'

/** « Ventiler par » (maquette d'US-318) : Cache = jetons hors cache / servis par le cache (sans
 *  dimension côté API) ; les autres sont des dimensions de `GET /admin/pilotage/series`. */
export const DIMENSIONS = [
  { id: '', libelle: 'Cache' },
  { id: 'modele', libelle: 'Modèle' },
  { id: 'appel_type', libelle: 'Type' },
  { id: 'canal', libelle: 'Canal' },
]

/** Types d'appel dont l'unité n'est pas le jeton : un bloc à part, jamais additionnés [CA6]. */
export const TYPES_AUDIO = { dictee: 'dictee', voix: 'voix' }

/** Cinq teintes (maquette d'US-318) : au-delà de cinq séries, les suivantes sont regroupées en
 *  « Autres » (gris) — six entrées au plus dans la légende. */
export const MAX_SERIES = 5
export const CLE_AUTRES = '__autres__'

/** Les cinq chiffres clés du bandeau, chacun avec son écart à la période précédente [CA1]. */
export function chiffresCles(synthese) {
  const m = synthese.mesures
  const p = synthese.mesures_precedentes
  return [
    { id: 'appels', libelle: 'Appels', valeur: m.appels, texte: entier(m.appels),
      ecart: ecart(m.appels, p.appels, { sens: SENS.NEUTRE }) },
    { id: 'jetons_entree', libelle: "Jetons d'entrée", valeur: m.jetons_entree, texte: compact(m.jetons_entree),
      ecart: ecart(m.jetons_entree, p.jetons_entree, { sens: SENS.MAUVAISE }) },
    { id: 'jetons_sortie', libelle: 'Jetons de sortie', valeur: m.jetons_sortie, texte: entier(m.jetons_sortie),
      ecart: ecart(m.jetons_sortie, p.jetons_sortie, { sens: SENS.NEUTRE }) },
    { id: 'taux_cache', libelle: 'Taux de cache', valeur: m.taux_cache, texte: pourcent(m.taux_cache, 0),
      ecart: ecart(m.taux_cache, p.taux_cache, { sens: SENS.BONNE, mode: 'points' }) },
    { id: 'mediane', libelle: "Jetons d'entrée médians par appel", valeur: m.jetons_entree_mediane_par_appel,
      texte: entier(m.jetons_entree_mediane_par_appel),
      ecart: ecart(m.jetons_entree_mediane_par_appel, p.jetons_entree_mediane_par_appel, { sens: SENS.MAUVAISE }) },
  ]
}

/** Aucun appel sur la période : des zéros et un message, pas une erreur [brief §4.3]. */
export const periodeSansAppel = (synthese) => synthese.mesures.appels === 0

/** Le bloc audio : dictées (secondes) et voix (caractères), à part des jetons [CA6]. */
export function blocAudio(synthese, parType) {
  const ligne = (type) => parType.lignes.find((l) => l.cle === type)
  return {
    dictee: { appels: ligne(TYPES_AUDIO.dictee)?.appels ?? 0, secondes: synthese.mesures.secondes_audio },
    voix: { appels: ligne(TYPES_AUDIO.voix)?.appels ?? 0, caracteres: synthese.mesures.caracteres },
  }
}

/** Les lignes d'un tableau de ventilation, formatées ; l'audio en est retiré (il a son bloc). */
export const estLigneAudio = (l) =>
  Object.values(TYPES_AUDIO).includes(l.cle) || (l.jetons_entree === 0 && (l.secondes_audio > 0 || l.caracteres > 0))

export function lignesTableau(ventilation) {
  return ventilation.lignes
    .filter((l) => !estLigneAudio(l))
    .map((l) => ({
      cle: l.cle,
      libelle: l.libelle,
      appels: l.appels,
      jetonsEntree: l.jetons_entree,
      jetonsSortie: l.jetons_sortie,
      part: l.part,
      mediane: l.jetons_entree_mediane_par_appel,
      court: String(l.libelle).replace(/^mistral\//, ''),
      texte: {
        abrege: abrege(l.jetons_entree),
        appels: entier(l.appels),
        jetonsEntree: entier(l.jetons_entree),
        jetonsSortie: entier(l.jetons_sortie),
        part: l.part === null ? '—' : pourcent(l.part, 1),
        mediane: entier(l.jetons_entree_mediane_par_appel),
      },
    }))
}

/** Regroupe les séries au-delà de `max` dans « Autres » (somme pas à pas). */
export function grouperAutres(series, max = MAX_SERIES) {
  if (series.length <= max) return series
  const gardees = series.slice(0, max)
  const reste = series.slice(max)
  const valeurs = reste[0].valeurs.map((_, i) => reste.reduce((somme, s) => somme + (s.valeurs[i] || 0), 0))
  return [...gardees, { cle: CLE_AUTRES, libelle: 'Autres', valeurs, total: valeurs.reduce((a, b) => a + b, 0) }]
}

/** « 2026-11-09 » → « 9 nov. » ; « 08h » reste « 08h ». */
export const libellePas = (point, pas) => (pas === 'heure' ? point : jourBref(point))

/**
 * Le modèle du graphique [CA2, CA3, CA8].
 * - sans ventilation : une pile « cache » + « hors cache » par pas ;
 * - ventilé : une pile par série (≤ 6 + Autres) et une ligne « dont cache » en pointillé.
 * Les pas sans appel sont à zéro dans les deux (l'API les fournit), jamais absents.
 */
export function modeleGraphique(serieEntree, serieCache, dimension) {
  const points = serieEntree.points.map((p) => ({ cle: p, libelle: libellePas(p, serieEntree.pas) }))
  const cache = serieCache.total
  if (!dimension) {
    const total = serieEntree.total
    return {
      mode: 'total', pas: serieEntree.pas, points, cache,
      series: [
        { cle: 'hors_cache', libelle: 'hors cache', valeurs: total.map((v, i) => Math.max(0, v - cache[i])) },
        { cle: 'cache', libelle: 'servi par le cache', valeurs: cache },
      ],
      total,
    }
  }
  // Une série sans aucun jeton (un modèle d'audio, par exemple) n'a rien à montrer dans ce graphique.
  const utiles = serieEntree.series.filter((s) => s.total > 0)
  const grandTotal = utiles.reduce((a, s) => a + s.total, 0)
  const series = grouperAutres(utiles.map((s) => ({
    cle: s.cle, libelle: String(s.cle).replace(/^mistral\//, ''), valeurs: s.valeurs, total: s.total,
  }))).map((s) => ({ ...s, part: grandTotal ? s.total / grandTotal : null }))
  return { mode: 'ventile', pas: serieEntree.pas, points, cache, series, total: serieEntree.total }
}

export const sommeSerie = (valeurs) => valeurs.reduce((a, b) => a + (b || 0), 0)

/** Le tableau équivalent du graphique, accessible au clavier [CA9] : une ligne par pas. */
export function tableauGraphique(modele) {
  const entetes = ['Période', ...modele.series.map((s) => s.libelle), "Total jetons d'entrée", 'dont cache']
  const lignes = modele.points.map((p, i) => [
    p.libelle,
    ...modele.series.map((s) => entier(s.valeurs[i])),
    entier(modele.total[i]),
    entier(modele.cache[i]),
  ])
  return { entetes, lignes }
}

export const texteAxe = (valeur) => (valeur >= 1000 ? compact(valeur) : nombre(valeur))

/** Échelle « ronde » : le plus grand pas de 1, 2, 5 × 10^n qui couvre le maximum en 4 graduations. */
export function echelle(maximum, graduations = 4) {
  if (!maximum || maximum <= 0) return { max: 1, pas: 1, graduations: [0, 1] }
  const brut = maximum / graduations
  const puissance = 10 ** Math.floor(Math.log10(brut))
  const pas = [1, 2, 5, 10].map((f) => f * puissance).find((p) => p >= brut)
  const max = Math.ceil(maximum / pas) * pas
  const marques = []
  for (let v = 0; v <= max + 1e-9; v += pas) marques.push(Math.round(v))
  return { max, pas, graduations: marques }
}
