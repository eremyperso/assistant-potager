// [US-354 / CA7, CA8] Le Journal sur le socle : les jours, les notes regroupées, le bilan de la semaine.
// Sans React et sans lecture : la vue passe les événements de `GET /historique`.
//
// Les notes sont les événements `observation`. Dans un jour elles sont REGROUPÉES : « 3 notes », la
// première en Kalam avec sa culture et sa parcelle, « 1 sans texte » (comptées, jamais listées) et
// « + 1 autre » qui déplie les suivantes. Les gestes restent en ligne.
import { libelleAction, libelleJour, phraseEvenement } from './journal.js'
import { normaliserMot } from './motDeGaston.js'
import { nomCulture } from './planDessus.js'
import { normaliserRecherche } from './planSocle.js'

export const ACTION_NOTE = 'observation'
export const ACTION_RECOLTE = 'recolte'
export const ACTIONS_PERTE = Object.freeze(['perte', 'perte_godet'])

/** Une semaine = les 7 derniers jours, le jour de lecture compris (CA8). */
export const JOURS_BILAN = 7

const pluriel = (n, un, plusieurs) => (n > 1 ? plusieurs : un)
const texteDe = (e) => String(e?.commentaire ?? '').trim()

/** Le jour d'un événement : sa date ISO sans l'heure. */
const jourDe = (e) => String(e?.date ?? '').slice(0, 10)

/** « Planche centrale · rang 3 », ou ce qu'on en sait. */
export const lieuDeEvenement = (e) => [e?.parcelle, e?.rang ? `rang ${e.rang}` : ''].filter(Boolean).join(' · ')

/** Le texte d'une note, sa culture et sa parcelle (CA7 : « Fève · Planche centrale »). */
function noteDe(e) {
  return {
    cle: `n-${e.id ?? `${jourDe(e)}-${texteDe(e).slice(0, 12)}`}`,
    texte: texteDe(e),
    culture: e.culture || '',
    ou: [e.culture ? nomCulture(e.culture, e.variete) : '', e.parcelle].filter(Boolean).join(' · '),
  }
}

/** Une ligne de geste : récolte, paillage, perte (en rouge)… avec son lieu et la culture qu'elle ouvre. */
function gesteDe(e) {
  return {
    cle: `g-${e.id}`,
    type: e.type_action,
    titre: phraseEvenement(e),
    detail: lieuDeEvenement(e),
    perte: ACTIONS_PERTE.includes(e.type_action),
    recolte: e.type_action === ACTION_RECOLTE,
    culture: e.culture || null,
    // [US-355 / CA1] La fiche commune s'ouvre sur cette culture ; sa place est retrouvée dans le plan.
    selection: e.culture ? { culture: e.culture, variete: e.variete || null, parcelle: e.parcelle || null } : null,
  }
}

/**
 * Les jours du journal, du plus récent au plus ancien (l'ordre du serveur) : chacun avec ses gestes en
 * ligne et, s'il y en a, son groupe de notes `{ total, sansTexte, premiere, autres }`.
 */
export function joursDuJournal(evenements, aujourdhui = new Date()) {
  const jours = []
  for (const e of evenements || []) {
    const label = libelleJour(e.date, aujourdhui)
    let jour = jours[jours.length - 1]
    if (!jour || jour.label !== label) {
      jour = { label, iso: jourDe(e), gestes: [], notes: [] }
      jours.push(jour)
    }
    if (e.type_action === ACTION_NOTE) jour.notes.push(e)
    else jour.gestes.push(gesteDe(e))
  }
  return jours.map(({ notes, ...jour }) => {
    if (!notes.length) return { ...jour, notes: null }
    const avecTexte = notes.filter((n) => texteDe(n)).map(noteDe)
    return {
      ...jour,
      notes: {
        total: notes.length,
        sansTexte: notes.length - avecTexte.length,
        premiere: avecTexte[0] ?? null,
        autres: avecTexte.slice(1),
      },
    }
  })
}

/** « 3 notes », « 1 note ». */
export const titreDuGroupe = (n) => `${n} ${pluriel(n, 'note', 'notes')}`

/** « + 1 autre », « + 2 autres » ; déplié : « Réduire ». */
export const libelleAutres = (n) => `+ ${n} ${pluriel(n, 'autre', 'autres')}`

/** « 1 sans texte », « 2 sans texte » : comptées, jamais listées. */
export const libelleSansTexte = (n) => `${n} sans texte`

/** Un événement répond-il à la recherche « Culture, parcelle ou mot » ? Sans recherche, tout répond. */
export function repondALaRecherche(e, recherche) {
  const q = normaliserRecherche(recherche)
  if (!q) return true
  return [e.culture, e.variete, e.parcelle, texteDe(e), phraseEvenement(e)]
    .some((c) => normaliserRecherche(c).includes(q))
}

// ── Mot de Gaston : le bilan de la semaine (CA8) ────────────────────────────────────────────

/** « 1,2 kg » : virgule décimale, une décimale utile. */
const nombre = (n) => String(Math.round(n * 10) / 10).replace('.', ',')

/** Met le premier mot d'un libellé au pluriel : « paillage » → « paillages », « mise en godet » → « mises en godet ». */
function auPluriel(libelle, n) {
  if (n <= 1) return libelle
  const [premier, ...reste] = libelle.split(' ')
  return [`${premier}${/[sxz]$/.test(premier) ? '' : 's'}`, ...reste].join(' ')
}

/**
 * Ce que pèsent les récoltes : les kg s'additionnent ; une autre unité se dit dans la sienne. Une
 * récolte en pièces n'est JAMAIS convertie en kg (US-036, INC-008).
 */
export function quantiteRecoltes(recoltes) {
  const parUnite = new Map()
  for (const r of recoltes) {
    if (typeof r.quantite !== 'number') continue
    const u = String(r.unite || '').toLowerCase()
    parUnite.set(u, (parUnite.get(u) || 0) + r.quantite)
  }
  return [...parUnite.entries()].map(([u, q]) => (u === 'kg' ? `${nombre(q)} kg` : `${nombre(q)}${u ? ` ${u}` : ''}`))
}

/**
 * « Cette semaine : **1 récolte (1,2 kg)**, 1 paillage et 6 notes. » Un bilan, sans action : la
 * semaine vide ne dit rien. Le serveur ne garde pas si une note a été dictée ou écrite : la mention
 * « dont 4 dictées » n'est pas écrite (rien n'est inventé).
 */
export function motDuJournal(evenements) {
  const liste = evenements || []
  const recoltes = liste.filter((e) => e.type_action === ACTION_RECOLTE)
  const notes = liste.filter((e) => e.type_action === ACTION_NOTE)
  const autres = new Map()
  for (const e of liste) {
    if (e.type_action === ACTION_RECOLTE || e.type_action === ACTION_NOTE) continue
    autres.set(e.type_action, (autres.get(e.type_action) || 0) + 1)
  }
  const morceaux = []
  if (recoltes.length) {
    const quantites = quantiteRecoltes(recoltes)
    morceaux.push(`**${recoltes.length} ${pluriel(recoltes.length, 'récolte', 'récoltes')}${quantites.length ? ` (${quantites.join(', ')})` : ''}**`)
  }
  for (const [type, n] of [...autres.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2)) {
    morceaux.push(`${n} ${auPluriel(libelleAction(type).toLowerCase(), n)}`)
  }
  if (notes.length) morceaux.push(`${notes.length} ${pluriel(notes.length, 'note', 'notes')}`)
  if (!morceaux.length) return null
  const dit = morceaux.length > 1
    ? `${morceaux.slice(0, -1).join(', ')} et ${morceaux[morceaux.length - 1]}`
    : morceaux[0]
  return normaliserMot({ texte: `Cette semaine : ${dit}.`, actions: [] })
}

/** Le premier jour du bilan (ISO) : 6 jours avant le jour de lecture. */
export function debutDuBilan(iso) {
  const [a, m, j] = String(iso).slice(0, 10).split('-').map(Number)
  if (!a || !m || !j) return ''
  const d = new Date(Date.UTC(a, m - 1, j - (JOURS_BILAN - 1)))
  return d.toISOString().slice(0, 10)
}
