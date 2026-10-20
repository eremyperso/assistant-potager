// [US-242] L'onglet « Lots » en journal de saison — règles d'affichage, sans React.
//
// Un registre sans geste : chaque lot est une ligne de gestes datés sur une frise.
// Toutes les dates viennent de `GET /pepiniere/lots` (US-065, US-211, US-212, US-214,
// US-216) ; les mises en terre et les ventes, que l'API ne date pas, sont comptées et
// jamais placées sur la frise (RT2 : aucune date inventée).
import {
  dateEnClair, echeanceEnClair, estCloture, estDormant, estTermine, grainesRestantes, tauxLevee,
} from './ficheLot.js'
import { dateCourte, ecartJours } from './parcours.js'
import { emplacementLot } from './pepiniere.js'

const MOIS_COURTS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
export const MOIS_LONGS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

const pluriel = (n, mot, pl = `${mot}s`) => `${n} ${n > 1 ? pl : mot}`
const iso = (d) => (d ? String(d).slice(0, 10) : null)
const versJour = (s) => {
  if (!s) return null
  const [y, m, d] = String(s).slice(0, 10).split('-').map(Number)
  return y && m && d ? Date.UTC(y, m - 1, d) / 86400000 : null
}
const versIso = (y, m, d) => `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
const finDuMois = (y, m) => new Date(Date.UTC(y, m + 1, 0)).getUTCDate()

// ── Filtre (CA1) ─────────────────────────────────────────────────────────────

export const FILTRES = Object.freeze([
  Object.freeze({ cle: 'en_cours', libelle: 'En cours' }),
  Object.freeze({ cle: 'a_regler', libelle: 'À régler' }),
  Object.freeze({ cle: 'termine', libelle: 'Terminés' }),
  Object.freeze({ cle: 'tous', libelle: 'Tous' }),
])
export const filtreInitial = (f) => (FILTRES.some((x) => x.cle === f) ? f : 'tous')

/** Quantité semée non dite : un semis rattaché sans nombre de graines. */
export const quantiteNonDite = (lot) => !lot?.sans_semis_rattache && !(lot?.graines_semees > 0)

/**
 * [CA1] `termine` (terminé ou clôturé, règle de la fiche du lot), `a_regler` (quantité
 * semée non dite, ou échéance incalculable faute de délai), `en_cours` sinon.
 */
export function statutLot(lot) {
  if (estTermine(lot)) return 'termine'
  if (quantiteNonDite(lot)) return 'a_regler'
  const raisons = lot?.echeances?.raisons
  if (!estDormant(lot) && Array.isArray(raisons) && raisons.length > 0 && echeanceEnClair(lot).ton === 'na') return 'a_regler'
  return 'en_cours'
}
export const LIBELLE_STATUT = Object.freeze({ en_cours: 'En cours', a_regler: 'À régler', termine: 'Terminé' })

/** Les lots visibles : filtre, recherche (culture, variété, numéro), tri par date de semis. */
export function lotsVisibles(lots, { filtre = 'tous', q = '' } = {}) {
  const t = String(q ?? '').trim().toLowerCase().replace(/^#/, '')
  return (lots ?? [])
    .filter((l) => filtre === 'tous' || statutLot(l) === filtre)
    .filter((l) => !t || `${l.numero_lot ?? ''} ${l.culture ?? ''} ${l.variete ?? ''}`.toLowerCase().includes(t))
    .sort((a, b) => {
      const da = iso(a.date_semis ?? a.date_derniere_mise_en_godet) ?? ''
      const db = iso(b.date_semis ?? b.date_derniere_mise_en_godet) ?? ''
      return da < db ? -1 : da > db ? 1 : (a.numero_lot ?? 0) - (b.numero_lot ?? 0)
    })
}

export function comptesFiltres(lots) {
  const c = { en_cours: 0, a_regler: 0, termine: 0, tous: (lots ?? []).length }
  for (const l of lots ?? []) c[statutLot(l)] += 1
  return c
}

/** [CA3] Les lots groupés par mois de semis : `[{ mois: 'Septembre', lots }]`, dans l'ordre reçu. */
export function groupesParMois(lots) {
  const acc = []
  for (const l of lots ?? []) {
    const d = iso(l.date_semis ?? l.date_derniere_mise_en_godet)
    const cle = d ? d.slice(0, 7) : 'sans'
    const mois = d ? MOIS_LONGS[Number(d.slice(5, 7)) - 1] : 'Sans date'
    const g = acc[acc.length - 1]
    if (g && g.cle === cle) g.lots.push(l)
    else acc.push({ cle, mois, lots: [l] })
  }
  return acc
}

// ── Les nombres d'un lot ─────────────────────────────────────────────────────

/**
 * Les parts de la barre empilée : mis en terre, en godet, en levée, vendus, pertes,
 * non levées. « En levée » = levés à repiquer (levée terminée) ou graines encore
 * en germination ; « non levées » = le reste des graines semées, une fois tout compté.
 */
export function partsDuLot(lot) {
  const graines = lot?.graines_semees > 0 ? lot.graines_semees : 0
  const pl = lot?.nb_plantes ?? 0
  const go = lot?.stock_residuel_godet ?? 0
  const vd = lot?.nb_vendus ?? 0
  const pe = lot?.nb_pertes_godet ?? 0
  const obtenus = lot?.plants_obtenus ?? 0
  let le = estCloture(lot) ? 0 : grainesRestantes(lot)
  if (lot?.levee_terminee && lot?.nb_leves != null) le = Math.min(le, Math.max(0, lot.nb_leves - obtenus))
  const nl = graines ? Math.max(0, graines - obtenus - le) : 0
  const parts = { pl, go, le, vd, pe, nl }
  const somme = pl + go + le + vd + pe + nl
  return { parts, base: Math.max(graines, somme) }
}

export const SEGMENTS = Object.freeze([
  ['pl', 'mis en terre'], ['go', 'en godet'], ['le', 'en levée'], ['vd', 'vendus'], ['pe', 'pertes'], ['nl', 'non levées'],
])

/** La barre : `[{ cle, valeur, libelle, largeur }]`, sans les parts nulles. */
export function barreDuLot(lot) {
  const { parts, base } = partsDuLot(lot)
  if (!base) return []
  return SEGMENTS.filter(([k]) => parts[k] > 0)
    .map(([k, libelle]) => ({ cle: k, valeur: parts[k], libelle, largeur: (parts[k] / base) * 100 }))
}

/** [CA6] Le grand chiffre du bilan : levée si elle est notée, germination sinon. `null` sans base. */
export function tauxDuLot(lot) {
  const graines = lot?.graines_semees
  if (!(graines > 0)) return null
  if (lot?.nb_leves != null) {
    return { valeur: tauxLevee(lot.nb_leves, graines), libelle: `levée, ${lot.levee_terminee ? 'terminée' : 'en cours'}`, sur: graines }
  }
  const obtenus = lot?.plants_obtenus ?? 0
  if (obtenus === 0 && !estCloture(lot)) return null
  const { parts } = partsDuLot(lot)
  return {
    valeur: Math.round((obtenus / graines) * 100),
    libelle: parts.le > 0 ? 'germination, levée en cours' : 'germination',
    sur: graines,
  }
}

// ── « Où il en est » (CA5) ───────────────────────────────────────────────────

/** Le mot court de l'échéance, pour la ligne : « sortie dans 14 j », « mise en terre à faire ». */
function echeanceCourte(lot) {
  const e = lot?.echeances ?? {}
  const rep = e.repiquage ?? {}
  const terre = e.mise_en_terre ?? {}
  if (rep.etat === 'en_retard') return `repiquage en retard de ${rep.retard_jours} j`
  if (terre.etat === 'depassee') return `mise en terre en retard de ${terre.retard_jours} j`
  if (rep.etat === 'a_repiquer') return 'à repiquer'
  if (terre.etat === 'atteinte') return 'mise en terre à faire'
  if (rep.etat === 'a_venir' && rep.dans_jours != null) return `repiquage dans ${rep.dans_jours} j`
  if (terre.etat === 'a_venir' && terre.dans_jours != null) return `sortie dans ${terre.dans_jours} j`
  return null
}

export function etatEnUneLigne(lot) {
  const statut = statutLot(lot)
  const { parts } = partsDuLot(lot)
  if (estCloture(lot)) {
    const j = dateCourte(lot.date_cloture)
    return `clôturé${j ? ` le ${j}` : ''}${(lot.plants_obtenus ?? 0) === 0 && (lot.nb_leves ?? 0) === 0 ? ' · aucune levée' : ''}`
  }
  if (statut === 'termine') {
    return parts.pl > 0 ? `tout planté · ${parts.pl} sur ${lot.graines_semees || parts.pl}` : 'tout soldé'
  }
  if (quantiteNonDite(lot)) return 'quantité semée non dite'
  const bouts = []
  if (statut === 'a_regler') bouts.push('délai non renseigné')
  if (parts.pl > 0) bouts.push(`${parts.pl} mis en terre`)
  if (parts.go > 0) bouts.push(pluriel(parts.go, 'godet'))
  if (parts.le > 0) {
    bouts.push(lot.levee_terminee && lot.nb_leves != null
      ? `${pluriel(parts.le, 'levé')} à repiquer`
      : `${pluriel(parts.le, 'graine')} en levée`)
  }
  const ech = echeanceCourte(lot)
  if (ech) bouts.push(ech)
  if (estDormant(lot)) bouts.push(`sans geste depuis ${lot.echeances.dormance.jours_sans_geste} j`)
  return bouts.join(' · ') || 'en levée'
}

// ── Les gestes datés (CA3, CA6) ──────────────────────────────────────────────

/**
 * Les gestes datés d'un lot, dans l'ordre : `[{ code, date, titre, detail }]`.
 * `code` : S semé, L levée notée, G mise en godet, D déplacé, C clôturé, T mis en terre,
 * V vendu, P perdu en godet, X dernier geste (quand il ne coïncide avec aucun autre —
 * l'API n'en donne pas le type). Mises en terre, ventes et pertes viennent de
 * `sorties_datees` (une ligne par geste imputé au lot, avec sa date et, pour la mise en
 * terre, sa parcelle).
 */
export function gestesDates(lot) {
  const out = []
  const graines = lot?.graines_semees > 0 ? lot.graines_semees : null
  if (lot?.date_semis) {
    out.push({ code: 'S', date: iso(lot.date_semis), titre: 'Semé', detail: graines ? pluriel(graines, 'graine') : 'quantité non dite' })
  }
  if (lot?.date_derniere_mise_en_godet) {
    const n = lot.nb_mises_en_godet ?? 1
    const plants = pluriel(lot.plants_obtenus ?? 0, 'plant')
    out.push(n > 1
      ? { code: 'G', date: iso(lot.date_derniere_mise_en_godet), titre: 'Dernière mise en godet', detail: `${n} mises en godet en tout · ${plants}` }
      : { code: 'G', date: iso(lot.date_derniere_mise_en_godet), titre: 'Mis en godet', detail: plants })
  }
  if (lot?.date_deplacement) {
    const vers = lot.emplacement?.nom
    out.push({ code: 'D', date: iso(lot.date_deplacement), titre: 'Déplacé', detail: vers ? `vers ${vers}` : 'destination non renseignée' })
  }
  if (lot?.date_derniere_levee) {
    out.push({
      code: 'L', date: iso(lot.date_derniere_levee),
      titre: `Levée notée${lot.levee_terminee ? ', terminée' : ''}`,
      detail: lot.nb_leves != null ? `${pluriel(lot.nb_leves, 'levé')}${graines ? ` sur ${graines}` : ''}` : 'nombre non dit',
    })
  }
  if (lot?.cloture && lot?.date_cloture) {
    out.push({ code: 'C', date: iso(lot.date_cloture), titre: 'Clôturé', detail: 'tout ce qui restait est soldé' })
  }
  for (const x of lot?.sorties_datees ?? []) {
    const date = iso(x.date)
    if (!date || !(x.quantite > 0)) continue
    const plants = pluriel(x.quantite, 'plant')
    if (x.nature === 'plantation') {
      out.push({ code: 'T', date, titre: 'Mis en terre', detail: `${plants} · ${x.parcelle ?? 'parcelle non renseignée'}` })
    } else if (x.nature === 'vente') {
      out.push({ code: 'V', date, titre: 'Vendu', detail: plants })
    } else if (x.nature === 'perte') {
      out.push({ code: 'P', date, titre: 'Perte en godet', detail: plants })
    }
  }
  const dernier = iso(lot?.date_dernier_geste)
  if (dernier && !out.some((g) => g.date === dernier)) {
    out.push({ code: 'X', date: dernier, titre: 'Dernier geste', detail: 'type non transmis' })
  }
  const rang = { S: 0, G: 1, D: 2, L: 3, C: 4, T: 5, V: 6, P: 7, X: 8 }
  return out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : rang[a.code] - rang[b.code]))
}

/**
 * Ce qui est compté sans date : le reste des mises en terre, ventes et pertes que
 * `sorties_datees` ne couvre pas (lot lu sans ce détail, ou geste sans date). Vide dès que
 * chaque plant est daté — jamais de date inventée (RT2).
 */
export function gestesNonDates(lot) {
  const datees = { plantation: 0, vente: 0, perte: 0 }
  for (const x of lot?.sorties_datees ?? []) if (x.date && x.nature in datees) datees[x.nature] += x.quantite ?? 0
  const out = []
  const reste = (total, nature) => Math.max(0, (total ?? 0) - datees[nature])
  if (reste(lot?.nb_plantes, 'plantation') > 0) out.push({ code: 'T', titre: 'Mis en terre', detail: pluriel(reste(lot.nb_plantes, 'plantation'), 'plant') })
  if (reste(lot?.nb_vendus, 'vente') > 0) out.push({ code: 'T', titre: 'Vendus', detail: pluriel(reste(lot.nb_vendus, 'vente'), 'plant') })
  if (reste(lot?.nb_pertes_godet, 'perte') > 0) out.push({ code: 'T', titre: 'Pertes en godet', detail: pluriel(reste(lot.nb_pertes_godet, 'perte'), 'plant') })
  return out
}

/** Le dernier geste daté du lot (ou son semis). */
export function dernierGeste(lot) {
  const d = gestesDates(lot).map((g) => g.date)
  return d.length ? d[d.length - 1] : null
}

/** Le journal du lot : chaque geste en J+n depuis le semis, puis les non datés, puis « aujourd'hui ». */
export function journalDuLot(lot, aujourdhui) {
  const semis = iso(lot?.date_semis)
  const lignes = gestesDates(lot).map((g) => ({
    ...g, jour: semis ? `J${ecartJours(semis, g.date)}` : null, quand: dateEnClair(g.date),
  }))
  for (const g of gestesNonDates(lot)) lignes.push({ ...g, jour: '?', quand: null, nonDate: true })
  if (!estTermine(lot) && aujourdhui) {
    const dernier = dernierGeste(lot)
    const sans = dernier ? ecartJours(dernier, aujourdhui) : null
    lignes.push({
      code: 'N', aujourdhui: true, titre: "Aujourd'hui", quand: dateEnClair(aujourdhui),
      jour: semis ? `J${ecartJours(semis, aujourdhui)}` : null,
      detail: sans == null ? null : sans <= 0 ? 'geste du jour' : `${sans} j sans geste`,
    })
  }
  return lignes
}

// ── La fenêtre de temps (CA4) ────────────────────────────────────────────────

/**
 * `saison` : du 1er mars au 30 novembre de l'année du jour de référence, étendue pour
 * le contenir. `recent` : du 1er du mois, deux mois avant, à la fin du mois suivant.
 * Retourne `{ debut, fin, libelle }` en ISO.
 */
export function fenetre(zoom, aujourdhui) {
  const [y, m] = String(aujourdhui).slice(0, 10).split('-').map(Number)
  const mo = m - 1
  if (zoom === 'recent') {
    const d = new Date(Date.UTC(y, mo - 2, 1))
    const f = new Date(Date.UTC(y, mo + 2, 0))
    const debut = versIso(d.getUTCFullYear(), d.getUTCMonth(), 1)
    const fin = versIso(f.getUTCFullYear(), f.getUTCMonth(), f.getUTCDate())
    const premier = MOIS_LONGS[d.getUTCMonth()]
    return { debut, fin, libelle: `${premier} → ${MOIS_COURTS[f.getUTCMonth()]}` }
  }
  const mDebut = Math.min(2, mo)
  const mFin = Math.max(10, mo)
  return { debut: versIso(y, mDebut, 1), fin: versIso(y, mFin, finDuMois(y, mFin)), libelle: 'Saison' }
}

/** Position d'une date dans la fenêtre, en % de 0 à 100 (bornée). */
export function position(date, f) {
  const r0 = versJour(f.debut)
  const span = versJour(f.fin) - r0 + 1
  const x = ((versJour(date) - r0) / span) * 100
  return Math.max(0, Math.min(100, x))
}

/** Les débuts de mois de la fenêtre : `[{ date, mois, gauche }]`. */
export function moisDeLaFenetre(f) {
  const out = []
  const [y0, m0] = f.debut.split('-').map(Number)
  for (let y = y0, m = m0 - 1; ; m += 1) {
    if (m > 11) { m = 0; y += 1 }
    const d = versIso(y, m, 1)
    if (d > f.fin) break
    out.push({ date: d, mois: MOIS_COURTS[m], gauche: position(d, f) })
  }
  return out
}

/**
 * [CA3] Ce que la frise d'un lot dessine, en % de la fenêtre : le trait plein (semis →
 * dernier geste), le pointillé (→ aujourd'hui, lot non terminé), la fenêtre de mise en
 * terre, le repère d'aujourd'hui et les pastilles. Deux pastilles plus proches que
 * `ecartMin` (%) se décalent au-dessus (`niveau` -1) ou au-dessous (+1) du trait.
 */
export function frise(lot, f, aujourdhui, ecartMin = 3) {
  const debutLot = iso(lot?.date_semis) ?? iso(lot?.date_derniere_mise_en_godet)
  const dernier = dernierGeste(lot) ?? debutLot
  const avant = debutLot && debutLot < f.debut
  const x0 = debutLot ? position(debutLot, f) : null
  const xDernier = dernier ? position(dernier, f) : null
  const xAujourdhui = position(aujourdhui, f)
  const fin = estTermine(lot)
  const terre = lot?.echeances?.mise_en_terre
  const fenetreTerre = !fin && terre?.du && terre?.au && terre.au >= f.debut && terre.du <= f.fin
    ? { gauche: position(terre.du, f), largeur: position(terre.au, f) - position(terre.du, f), du: terre.du, au: terre.au }
    : null

  const derniers = { 0: -Infinity, '-1': -Infinity, 1: -Infinity }
  const pastilles = []
  for (const g of gestesDates(lot)) {
    if (g.date < f.debut) continue
    const x = position(g.date, f)
    let niveau = [0, -1, 1].find((v) => x - derniers[v] >= ecartMin)
    if (niveau === undefined) niveau = [0, -1, 1].sort((a, b) => derniers[a] - derniers[b])[0]
    derniers[niveau] = x
    pastilles.push({ ...g, gauche: x, niveau, info: `${dateCourte(g.date)} · ${g.titre.toLowerCase()}` })
  }
  if (avant) {
    pastilles.unshift({ code: 'S', date: debutLot, gauche: 0, niveau: 0, pale: true, titre: 'Semé', info: `semé le ${dateCourte(debutLot)}` })
  }
  return {
    trait: x0 != null && xDernier != null ? { gauche: x0, largeur: Math.max(0, xDernier - x0) } : null,
    attente: !fin && xDernier != null ? { gauche: xDernier, largeur: Math.max(0, xAujourdhui - xDernier) } : null,
    aujourdhui: xAujourdhui,
    fenetreTerre,
    pastilles,
  }
}

// ── Le bilan des lots visibles (CA2) ─────────────────────────────────────────

export function bilanDesLots(lots, aujourdhui = null) {
  const s = { lots: (lots ?? []).length, semees: 0, obtenus: 0, pl: 0, go: 0, le: 0, vd: 0, pe: 0, nl: 0 }
  for (const l of lots ?? []) {
    const { parts } = partsDuLot(l)
    s.semees += l.graines_semees > 0 ? l.graines_semees : 0
    s.obtenus += (l.plants_obtenus ?? 0) > 0 ? l.plants_obtenus : (l.nb_leves ?? 0)
    for (const k of ['pl', 'go', 'le', 'vd', 'pe', 'nl']) s[k] += parts[k]
  }
  const pourcent = s.semees ? Math.round((s.obtenus / s.semees) * 100) : null
  // Le lot dont la mise en terre est à faire (fenêtre atteinte ou dépassée), le plus pressé.
  const pret = (lots ?? [])
    .filter((l) => !estTermine(l) && (l.stock_residuel_godet ?? 0) > 0 && ['atteinte', 'depassee'].includes(l.echeances?.mise_en_terre?.etat))
    .sort((a, b) => String(a.echeances.mise_en_terre.au ?? '').localeCompare(String(b.echeances.mise_en_terre.au ?? '')))[0] ?? null
  let phrase
  if (s.go > 0) phrase = `${pluriel(s.go, 'plant attend', 'plants attendent')} en godet`
  else if (s.pl > 0) phrase = `${pluriel(s.pl, 'plant mis', 'plants mis')} en terre sur ${pluriel(s.lots, 'lot')}.`
  else phrase = s.lots ? "Aucun plant obtenu pour l'instant." : 'Aucun lot.'
  let urgence = null
  if (s.go > 0 && pret) {
    const nom = [pret.culture, pret.variete].filter(Boolean).join(' ').toLowerCase()
    const au = pret.echeances.mise_en_terre.au
    const depasse = pret.echeances.mise_en_terre.etat === 'depassee' || (aujourdhui && au && au < aujourdhui)
    urgence = `${pluriel(pret.stock_residuel_godet, 'godet')} de ${nom} à mettre en terre${au ? (depasse ? `, attendue au plus tard le ${dateCourte(au)}` : ` avant le ${dateCourte(au)}`) : ''}`
  } else if (s.go > 0) phrase += '.'
  const barre = s.semees
    ? SEGMENTS.filter(([k]) => s[k] > 0).map(([k, libelle]) => ({ cle: k, valeur: s[k], libelle, largeur: (s[k] / Math.max(s.semees, 1)) * 100 }))
    : []
  return { ...s, pourcent, phrase, urgence, barre }
}

// ── La fiche (CA6, CA7) ──────────────────────────────────────────────────────

/** Le ton du bloc d'échéance de la fiche : `fin`, `pret`, `bien`, `retard`, `na` ou `info`. */
export function echeanceFiche(lot) {
  if (estCloture(lot)) {
    const j = dateEnClair(lot.date_cloture)
    return {
      ton: 'fin', titre: j ? `Clôturé le ${j}` : 'Clôturé',
      detail: (lot.plants_obtenus ?? 0) === 0 && (lot.nb_leves ?? 0) === 0 ? "aucune graine n'a levé" : 'tout ce qui restait est soldé',
    }
  }
  if (estTermine(lot)) {
    const { parts } = partsDuLot(lot)
    return { ton: 'fin', titre: parts.pl > 0 ? 'Tout planté' : 'Lot terminé', detail: 'tout est mis en terre, vendu ou perdu' }
  }
  const e = echeanceEnClair(lot)
  const terre = lot?.echeances?.mise_en_terre ?? {}
  if (quantiteNonDite(lot) && !e.titre) return { ton: 'na', titre: 'Durée ?', detail: 'quantité semée non dite' }
  if (!e.titre) return null
  let ton = e.ton
  if (ton === 'info' && terre.etat === 'atteinte') ton = 'pret'
  else if (ton === 'info' && terre.etat === 'a_venir' && (terre.dans_jours ?? 99) <= 21) ton = 'bien'
  return { ton, titre: e.titre, detail: e.detail }
}

/** L'identité de la fiche : semé le…, depuis N jours, et l'emplacement courant. */
export function identiteFiche(lot, aujourdhui) {
  const semis = iso(lot?.date_semis)
  const jours = semis && aujourdhui ? ecartJours(semis, aujourdhui) : null
  return {
    semis: semis ? `semé le ${dateEnClair(semis)}${jours != null && jours >= 0 ? ` · ${jours} j` : ''}` : 'godets formés sans semis rattaché',
    lieu: emplacementLot(lot),
    deplace: lot?.date_deplacement ? `déplacé le ${dateEnClair(lot.date_deplacement)}` : null,
  }
}

/** Le jour de référence de l'écran : la date choisie, sinon celle de l'API, sinon aujourd'hui. */
export function jourDeReference(dateRef, lots, maintenant = new Date()) {
  if (dateRef) return iso(dateRef)
  const api = (lots ?? []).map((l) => l?.echeances?.date_reference).find(Boolean)
  if (api) return iso(api)
  return versIso(maintenant.getFullYear(), maintenant.getMonth(), maintenant.getDate())
}
