// [US-354 / CA4-CA6] Les Stocks sur le socle : les quatre chiffres, les cartes par famille, « Récoltes par
// saison » et le Mot de Gaston. Sans React et sans lecture : la vue passe `GET /stats/varietes`,
// `GET /stats/rendement` (une lecture par année) et, pour le mot, `GET /pepiniere/lots` et `GET /plan`.
//
// Une récolte en pièces n'est JAMAIS convertie en kg (US-036, INC-008) : les kg viennent de
// `GET /stats/rendement`, qui ne retient que le poids.
import { symboleDeCulture } from './pictosCultures.js'
import { normaliserMot } from './motDeGaston.js'
import { normaliserRecherche } from './planSocle.js'
import { ETAPE_PLANTEE, ETAPE_SEMEE, ETAPE_EN_RECOLTE, ETAPE_TERMINEE } from './etapes.js'

/** Combien d'années on remonte pour « Récoltes par saison » (celle de lecture comprise). */
export const NB_SAISONS = 5

/** Cultures montrées dans le détail d'une année avant « Autres ». */
export const NB_CULTURES_SAISON = 5

/** Un godet « attend » à partir de 3 semaines (CA6). */
export const SEUIL_ATTENTE_JOURS = 21

const pluriel = (n, un, plusieurs) => (n > 1 ? plusieurs : un)
const JOUR_MS = 86400000
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

/** 1 décimale, virgule : « 21,0 », « 44,7 ». */
export const kgEnLettres = (v) => `${(Math.round((v || 0) * 10) / 10).toFixed(1).replace('.', ',')} kg`

/** [US-036] Le rendement pesé est en g sous 1 kg cumulé, en kg au-delà. */
export function enKg(valeur, unite) {
  if (!valeur) return 0
  return unite === 'g' ? valeur / 1000 : valeur
}

// ── Ce que montrent les Stocks : ce qui est EN TERRE et peut produire ───────────────────────────
//
// Décision du 25/11 (retour de recette sur 3.145) : « Stocks » est la synthèse des cultures de la saison EN
// PLACE — plantées ou semées en pleine terre, donc en capacité de produire. Ni godets, ni graines en
// pépinière (la Pépinière les dit), ni cultures terminées. Une ligne par culture/variété ET par parcelle
// (on ne regroupe pas deux plantations de parcelles différentes), rangées sous leur parcelle. La quantité
// est celle du Plan : un nombre de plants, ou une surface pour un semis en m² ; la récolte vient de
// `GET /stats/varietes`, la même que dans le suivi du carnet.

const norm = (s) => String(s ?? '').normalize('NFD').replace(/\p{Diacritic}/gu, '').trim().toLowerCase()
const nombreFr = (v) => String(Math.round(Number(v) * 100) / 100).replace('.', ',')

/** « Variété non précisée » est le libellé d'une variété vide côté serveur : la même clé que le Plan (''). */
const cleCV = (culture, variete) => {
  const v = norm(variete)
  return `${norm(culture)}|${v.startsWith('variete non precisee') ? '' : v}`
}

/** La récolte d'une culture/variété EN TERRE : kg pesés et nombre de récoltes, tous états hors pépinière. */
function recoltesParCV(varietes) {
  const m = new Map()
  for (const d of varietes || []) {
    if (d.etat === 'pep') continue
    const cle = cleCV(d.culture, d.variete)
    const cur = m.get(cle) || { kg: 0, nb: 0, origine: d.origine }
    cur.kg += enKg(d.rendement_total, d.unite_rendement)
    cur.nb += d.nb_recoltes || 0
    m.set(cle, cur)
  }
  return m
}

/** « 80 plants », « 2,5 m² », « 12 graines » : la quantité EN TERRE de la ligne, dans son unité. */
export function quantiteEnTerre(n, unite) {
  const u = unite || 'plants'
  const q = Number(n) || 0
  if (u === 'm²' || u === 'ml') return `${nombreFr(q)} ${u}`
  if (u === 'plants') return `${q} ${pluriel(q, 'plant', 'plants')}`
  if (u === 'pieds') return `${q} ${pluriel(q, 'pied', 'pieds')}`
  return `${q} ${u}`
}

/** Des plants ou une surface : seuls les plants se comptent dans « plants en terre ». */
const estUnPlant = (u) => !u || u === 'plants' || u === 'pieds'

/** « planté », « semé en terre » : ce que la ligne est, dit en mots. */
export const etatEnTerre = (unite) => (estUnPlant(unite) ? 'planté' : 'semé en terre')

/**
 * Les lignes de stock : chaque culture/variété en place, dans chaque parcelle de plein champ. Hors pépinière,
 * hors cultures terminées ou à libérer, hors quantité nulle.
 */
export function lignesDeStock(plan, varietes) {
  const recoltes = recoltesParCV(varietes)
  const brut = []
  for (const p of plan?.parcelles || []) {
    if (p.est_pepiniere) continue
    for (const c of p.cultures || []) {
      const e = c.etapes || null
      if (e?.a_liberer || e?.etape === ETAPE_TERMINEE) continue
      if (!(Number(c.nb_plants) > 0)) continue
      brut.push({ p, c })
    }
  }
  const parcellesParCV = new Map()
  for (const { p, c } of brut) {
    const cle = cleCV(c.culture, c.variete)
    parcellesParCV.set(cle, new Set([...(parcellesParCV.get(cle) || []), p.id]))
  }
  return brut.map(({ p, c }) => {
    const cle = cleCV(c.culture, c.variete)
    const r = recoltes.get(cle) || { kg: 0, nb: 0, origine: null }
    const plusieurs = (parcellesParCV.get(cle)?.size || 0) > 1
    const unite = c.unite || 'plants'
    const recolte = r.kg > 0 ? `récolté ${kgEnLettres(r.kg)}` : r.nb > 0 ? `${r.nb} ${pluriel(r.nb, 'récolte', 'récoltes')}` : ''
    const detail = [etatEnTerre(unite), recolte && (plusieurs ? `${recolte} (toutes parcelles)` : recolte)].filter(Boolean).join(' · ')
    const rangs = (c.numeros_rangs || []).filter(Number.isInteger)
    const etape = c.etapes?.etape || (r.kg > 0 || r.nb > 0 ? ETAPE_EN_RECOLTE : estUnPlant(unite) ? ETAPE_PLANTEE : ETAPE_SEMEE)
    const quantite = quantiteEnTerre(c.nb_plants, unite)
    return {
      cle: `${p.id}|${c.culture}|${c.variete || ''}`,
      parcelleId: p.id,
      parcelle: p.nom,
      ordreParcelle: p.ordre ?? 0,
      culture: c.culture,
      variete: c.variete || '',
      famille: c.famille || '',
      origine: r.origine,
      unite,
      nbPlants: estUnPlant(unite) ? Number(c.nb_plants) : 0,
      surfaceM2: unite === 'm²' ? Number(c.nb_plants) : 0,
      recolteKg: r.kg,
      nbRecoltes: r.nb,
      etape,
      emoji: symboleDeCulture(c.culture, c.variete || ''),
      titre: c.culture,
      droite: quantite,
      detail,
      nomAccessible: `${c.culture}${c.variete ? ` ${c.variete}` : ''}, ${p.nom}, ${quantite}, ${detail}`,
      // La fiche commune reçoit la parcelle : elle dit « Planche centrale », pas « Pas encore placé ».
      selection: {
        parcelleId: p.id, parcelle: p.nom, culture: c.culture, variete: c.variete || null,
        rang: rangs.length ? Math.min(...rangs) : null, quantiteTexte: quantite,
      },
    }
  })
}

/** Les quatre chiffres : plants en terre, cultures en place, kg récoltés dans l'année, unités perdues. */
export function quatreChiffres(lignes, kgAnnee, annee, varietes = []) {
  const l = lignes || []
  return {
    plants: l.reduce((s, x) => s + x.nbPlants, 0),
    surface: l.reduce((s, x) => s + x.surfaceM2, 0),
    cultures: l.length,
    kg: kgAnnee,
    kgLibelle: `récoltés en ${annee}`,
    // Les pertes se lisent sur les totaux du serveur (une perte n'a pas toujours de parcelle) : hors pépinière.
    perdues: (varietes || []).filter((d) => d.etat !== 'pep').reduce((s, d) => s + (d.plants_perdus || 0), 0),
  }
}

/** Les lignes rangées sous leur parcelle (dans l'ordre du plan), par ordre alphabétique de culture. */
export function groupesParParcelle(lignes) {
  const m = new Map()
  for (const l of lignes || []) {
    if (!m.has(l.parcelleId)) m.set(l.parcelleId, { cle: l.parcelleId, parcelle: l.parcelle, ordre: l.ordreParcelle, lignes: [] })
    m.get(l.parcelleId).lignes.push(l)
  }
  return [...m.values()]
    .sort((a, b) => a.ordre - b.ordre || a.parcelle.localeCompare(b.parcelle, 'fr'))
    .map((g) => {
      const nb = g.lignes.length
      return {
        ...g,
        titre: `${g.parcelle} · ${nb} ${pluriel(nb, 'culture', 'cultures')}`,
        lignes: [...g.lignes].sort((a, b) => a.culture.localeCompare(b.culture, 'fr') || a.variete.localeCompare(b.variete, 'fr')),
      }
    })
}

/** La recherche « Culture, variété ou parcelle » du filtre de la barre. */
export function repondALaRecherche(l, recherche) {
  const q = normaliserRecherche(recherche)
  if (!q) return true
  return [l.culture, l.variete, l.parcelle, l.famille].some((c) => normaliserRecherche(c).includes(q))
}

// ── Récoltes par saison (CA5) ───────────────────────────────────────────────────────────────

/** Les années à lire : celle du jour de lecture et les précédentes, de la plus ancienne à la plus récente. */
export function anneesAChercher(annee, nb = NB_SAISONS) {
  return Array.from({ length: nb }, (_, i) => annee - (nb - 1 - i))
}

/**
 * Les saisons qui ont des récoltes (poids), de la plus ancienne à la plus récente. `lectures` :
 * `[{ annee, total_general_kg, cultures: [{ culture, total }] }]`, les réponses de `GET /stats/rendement`.
 * Les années sans récolte disparaissent : une barre vide ne dit rien.
 */
export function saisonsDepuis(lectures) {
  return (lectures || [])
    .filter((l) => l && (l.total_general_kg || 0) > 0)
    .map((l) => ({
      annee: l.annee,
      total: l.total_general_kg,
      cultures: (l.cultures || []).map((c) => ({ culture: c.culture, total: c.total })),
    }))
    .sort((a, b) => a.annee - b.annee)
}

/** Une barre par année, proportionnelle au maximum. */
export function barresParAnnee(saisons) {
  const max = Math.max(0, ...saisons.map((s) => s.total))
  return saisons.map((s) => ({ annee: s.annee, libelle: kgEnLettres(s.total), pct: max ? (s.total / max) * 100 : 0 }))
}

/** Les cultures d'une année en barres : les plus récoltées, le reste en « Autres ». */
export function culturesDeLAnnee(saison, max = NB_CULTURES_SAISON) {
  if (!saison) return []
  const triees = [...saison.cultures].sort((a, b) => b.total - a.total)
  const tete = triees.slice(0, max)
  const reste = triees.slice(max).reduce((s, c) => s + c.total, 0)
  const lignes = tete.map((c) => ({ cle: c.culture, emoji: symboleDeCulture(c.culture, ''), nom: c.culture, total: c.total }))
  if (reste > 0) lignes.push({ cle: '__autres', emoji: '', nom: 'Autres', total: reste })
  const plus = Math.max(0, ...lignes.map((l) => l.total))
  return lignes.map((l) => ({ ...l, libelle: kgEnLettres(l.total), pct: plus ? (l.total / plus) * 100 : 0 }))
}

/** « Saison 2026 : du 1er janvier au 23 novembre » ; une saison close va jusqu'au 31 décembre. */
export function libelleSaison(annee, jourLu) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(jourLu || '')
  const enCours = m && Number(m[1]) === annee
  const fin = enCours ? `${Number(m[3])} ${MOIS[Number(m[2]) - 1]}` : '31 décembre'
  return `Saison ${annee} : du 1er janvier au ${fin}`
}

export const MENTION_STATISTIQUES = 'Le détail mois par mois reste dans Tableau de bord › Statistiques.'

// ── Le Mot de Gaston (CA6) ──────────────────────────────────────────────────────────────────

const joursEntre = (de, a) => Math.floor((Date.parse(`${a}T12:00:00Z`) - Date.parse(`${de}T12:00:00Z`)) / JOUR_MS)

/**
 * Les godets d'un lot qui attendent depuis plus de 3 semaines : le plus ancien en attente d'abord.
 * L'attente se compte depuis la dernière mise en godet du lot.
 */
export function godetsEnAttente(lots, aujourdhui) {
  return (lots || [])
    .filter((l) => (l.stock_residuel_godet || 0) > 0 && l.date_derniere_mise_en_godet && !l.date_cloture)
    .map((l) => ({ lot: l, jours: joursEntre(String(l.date_derniere_mise_en_godet).slice(0, 10), aujourdhui) }))
    .filter((x) => x.jours > SEUIL_ATTENTE_JOURS)
    .sort((a, b) => b.jours - a.jours)
}

/** Une parcelle de plein champ qui a un rang libre : `{ nom, rangs }` ou null. */
export function rangLibre(plan) {
  for (const p of plan?.parcelles || []) {
    if (p.est_pepiniere) continue
    const n = p.disposition?.rangs_libres || 0
    if (n > 0) return { nom: p.nom, rangs: n }
  }
  return null
}

/**
 * « **14 godets de chou pommé** attendent une place depuis 4 semaines.  * haricots : je l'y propose ? » → *Oui, proposer* (Gaston). Rien tant qu'aucun godet n'attend plus de
 * 3 semaines, ou qu'aucun rang n'est libre.
 */
export function motDesStocks({ lots = [], plan = null, aujourdhui } = {}) {
  const attente = godetsEnAttente(lots, aujourdhui)[0]
  const libre = rangLibre(plan)
  if (!attente || !libre) return null
  const { lot, jours } = attente
  const n = lot.stock_residuel_godet
  const semaines = Math.floor(jours / 7)
  const culture = String(lot.culture || '').toLowerCase()
  return normaliserMot({
    texte: `**${n} ${pluriel(n, 'godet', 'godets')} de ${culture}** ${pluriel(n, 'attend', 'attendent')} une place depuis ${semaines} semaines. Un rang est libre (${libre.nom}) : je l’y propose ?`,
    actions: [{
      libelle: 'Oui, proposer', noter: true, principale: true,
      // [US-358 / CA1] Le sujet (les godets en attente) et la phrase, prêts dans le champ.
      sujet: { type: 'lot', culture: lot.culture, numero: lot.numero_lot ?? null, texte: `${n} ${pluriel(n, 'godet', 'godets')} de ${culture}` },
      phrase: `Oui, proposez-moi le rang ${libre.nom} pour les godets de ${culture}`,
    }],
  })
}
