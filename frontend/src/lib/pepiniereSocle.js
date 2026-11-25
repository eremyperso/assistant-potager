// [US-356] La Pépinière posée sur le socle : trois onglets (Parcours, Semer, Lots), la carte de lot,
// les alertes « à régler », les mots de Gaston de chaque onglet et les données de « Semer ».
//
// Logique pure, sans réseau : tout vient de `GET /pepiniere/lots` (`lots`, `parcours`). Aucune
// fenêtre, aucun délai ni aucune durée n'est recalculé ici (RT6) : les jours restants, la part
// écoulée, les motifs d'écart et les prochaines ouvertures sont ceux du serveur ; un motif qu'il ne
// donne pas n'est pas affiché.
import { STADES, dateCourte, quantitesEtiquette } from './parcours.js'
import { statutLot, quantiteNonDite, comptesFiltres } from './lotsJournal.js'
import { estTermine, estCloture, deLaCulture } from './ficheLot.js'
import { gestesDates } from './lotsJournal.js'
import { normaliserMot } from './motDeGaston.js'
import { symboleDeCulture } from './pictosCultures.js'
import { etapeDuStade } from './etapes.js'

// ── Les trois onglets (CA1) ──────────────────────────────────────────────────────────────────────

export const ONGLETS = Object.freeze(['parcours', 'semer', 'lots'])

/** L'onglet à ouvrir : les adresses d'avant (« aujourdhui », « calendrier »…) ouvrent le Parcours. */
export const ongletPepiniere = (demande) => (ONGLETS.includes(demande) ? demande : 'parcours')

/** La ligne de contexte de l'en-tête, qui change avec l'onglet. */
export const CONTEXTE_ONGLET = Object.freeze({
  parcours: 'Châssis froid et serre chaude, lot par lot',
  semer: 'Le bon moment pour semer',
  lots: 'Le registre de la saison, lot par lot',
})

/** Les onglets d'en-tête : « Parcours », « Semer · 3 », « Lots · 18 ». */
export function ongletsPepiniere({ nbSemer = 0, nbLots = 0 } = {}) {
  return [
    { id: 'parcours', label: 'Parcours' },
    { id: 'semer', label: `Semer · ${nbSemer}` },
    { id: 'lots', label: `Lots · ${nbLots}` },
  ]
}

/** Les adresses `#lot-…` et les liens du Plan : l'onglet qui montre le lot demandé (US-201 / I5). */
export function ongletDeLIntention(intention) {
  if (!intention) return null
  if (ONGLETS.includes(intention.onglet)) return intention.onglet
  if (intention.onglet === 'aujourdhui' || intention.onglet === 'calendrier' || intention.emplacement) return 'parcours'
  return null
}

// ── Les pastilles de stade et d'emplacement (CA2, CA3) ─────────────────────────────────────────

/** La pastille d'étape d'un stade de pépinière : En levée → Levé, En godet → En godet, etc. (US-352 / CA2b). */
export const etapeDuStadePepiniere = (stade) => etapeDuStade(stade)

export const COULEUR_EMPLACEMENT = Object.freeze({ chaude: '#F2A54A', froide: '#5A8CC8', sans: '#9AA58F' })

/** « SERRE CHAUDE · 2 » : l'emplacement d'un groupe, avec la couleur de son type. */
export function enteteGroupe(ligne, n) {
  const sans = Boolean(ligne.sansEmplacement)
  const nom = sans ? 'Sans emplacement' : ligne.nom
  return {
    texte: `${nom} · ${n}`,
    couleur: sans ? COULEUR_EMPLACEMENT.sans : (COULEUR_EMPLACEMENT[ligne.type_pepiniere] ?? COULEUR_EMPLACEMENT.sans),
    sousTitre: sans ? 'à ranger' : (ligne.type_pepiniere ? `pépinière ${ligne.type_pepiniere}` : 'type non renseigné'),
  }
}

/**
 * Le Parcours en colonnes : une colonne par stade, et dans chacune les lots groupés par emplacement.
 * `kanban` est la sortie de `lib/parcours.kanban` ; chaque colonne donne ses groupes non vides.
 */
export function colonnesParStade(kanban) {
  return kanban.colonnes.map((colonne) => ({
    ...colonne,
    groupes: kanban.lignes
      .map((ligne) => ({ ligne, etiquettes: ligne.cases[colonne.cle] ?? [] }))
      .filter((g) => g.etiquettes.length > 0),
  }))
}

// ── La carte de lot (CA4) et les alertes ───────────────────────────────────────────────────────

const joursEntre = (de, a) => Math.round((Date.parse(`${a}T12:00:00Z`) - Date.parse(`${de}T12:00:00Z`)) / 864e5)

/** « Pas levé après 34 j », « Sans emplacement », « Quantité non dite », « Sans geste depuis 70 j ». */
export const TEXTE_ALERTE = Object.freeze({
  pas_leve: (n) => `Pas levé après ${n} j`,
  sans_emplacement: () => 'Sans emplacement',
  quantite: () => 'Quantité non dite',
  dormant: (n) => `Sans geste depuis ${n} j`,
})

/**
 * Les alertes « à régler », par lot : `Map(lot_id → { code, texte, jours })`. Un lot terminé n'en a pas.
 * Priorité : pas de levée après le délai du serveur, puis sans emplacement, quantité non dite, dormant.
 * `aujourdhui` : le jour de référence (ISO) — jamais l'horloge, la règle des temps le décide.
 */
export function alertesDesLots(lots, parcours, aujourdhui) {
  const sortie = new Map()
  const etiquettes = parcours?.etiquettes ?? []
  const dormants = new Map((parcours?.dormants ?? []).map((d) => [d.lot?.id, d]))
  for (const lot of lots ?? []) {
    if (estTermine(lot) || estCloture(lot)) continue
    const siennes = etiquettes.filter((e) => e.lot?.id === lot.lot_id)
    const jours = lot.date_semis && aujourdhui ? joursEntre(lot.date_semis, aujourdhui) : null
    const enRetardSansLevee = lot.nb_leves == null && siennes.some((e) => e.stade === 'levee' && e.echeance?.en_retard)
    let alerte = null
    if (enRetardSansLevee && jours != null) alerte = { code: 'pas_leve', jours }
    else if (siennes.some((e) => e.emplacement_id == null)) alerte = { code: 'sans_emplacement' }
    else if (quantiteNonDite(lot)) alerte = { code: 'quantite' }
    else if (dormants.has(lot.lot_id)) alerte = { code: 'dormant', jours: dormants.get(lot.lot_id).jours_sans_geste }
    if (alerte) sortie.set(lot.lot_id, { ...alerte, texte: TEXTE_ALERTE[alerte.code](alerte.jours) })
  }
  return sortie
}

/**
 * Le statut d'un lot dans le registre : terminé, « à régler » dès qu'il porte une alerte (pas de levée, sans
 * emplacement, quantité non dite, dormant) — le mot de Gaston et le filtre comptent donc les MÊMES lots —,
 * « en cours » sinon.
 */
export function statutPepiniere(lot, alertes) {
  if (statutLot(lot) === 'termine') return 'termine'
  return alertes?.has(lot.lot_id) ? 'a_regler' : 'en_cours'
}

/** Les comptes des filtres du registre, avec les alertes : En cours / À régler / Terminés / Tous. */
export function comptesRegistre(lots, alertes) {
  const c = { en_cours: 0, a_regler: 0, termine: 0, tous: (lots ?? []).length }
  for (const l of lots ?? []) c[statutPepiniere(l, alertes)] += 1
  return c
}

export { comptesFiltres }

const majuscule = (t) => (t ? t[0].toUpperCase() + t.slice(1) : t)

/**
 * La carte d'un lot — la MÊME dans le Parcours et dans le registre des Lots : emoji, nom, « #57 »,
 * « variété · quantité · semé le 20 oct. », la frise des gestes datés, l'alerte, la note.
 * `quantite` : la quantité à dire quand le lot n'a pas d'étiquette (le registre).
 */
export function carteLot({ lot, etiquette, alerte = null, quantite = null }) {
  const culture = lot?.culture ?? etiquette?.lot?.culture ?? ''
  const variete = lot?.variete ?? etiquette?.lot?.variete ?? ''
  const numero = lot?.numero_lot ?? etiquette?.lot?.numero ?? null
  const semis = lot?.date_semis ?? etiquette?.lot?.date_semis ?? null
  const meta = [variete, etiquette ? quantitesEtiquette(etiquette).principal : quantite, semis ? `semé le ${dateCourte(semis)}` : null]
    .filter(Boolean).join(' · ')
  const gestes = gestesDates(lot).map((g) => ({ date: g.date ? dateCourte(g.date) : '', titre: g.titre }))
  return {
    cle: etiquette?.id ?? lot?.lot_id,
    emoji: symboleDeCulture(culture, variete),
    nom: majuscule(culture),
    numero: numero != null ? `#${numero}` : null,
    meta,
    gestes,
    alerte: alerte?.texte ?? null,
    note: lot?.note ?? null,
    nomAccessible: [majuscule(culture), numero != null ? `lot ${numero}` : null, meta, alerte?.texte].filter(Boolean).join(', '),
  }
}

// ── Les mots de Gaston (CA5, CA8, CA10) ─────────────────────────────────────────────────────────────

const nomMinuscule = (lot) => String(lot?.culture ?? '').toLowerCase()

/** « l'oignon blanc », « la mâche », « le chou-fleur » : la culture avec son article (règle de `deLaCulture`). */
export function avecArticle(nom) {
  const c = deLaCulture(String(nom ?? '').toLowerCase())
  if (c.startsWith("de l'")) return `l’${c.slice(5)}`
  if (c.startsWith('de la ')) return `la ${c.slice(6)}`
  if (c.startsWith('du ')) return `le ${c.slice(3)}`
  return c
}

/** « Semer l'oignon blanc de Paris en pépinière froide » (CA1, tuile Semer). */
export function phraseSemer(tuile) {
  const variete = tuile.varietes?.length === 1 ? ` ${tuile.varietes[0]}` : ''
  const type = String(tuile.type ?? '').trim().toLowerCase()
  const ou = type ? ` en ${type.startsWith('pépinière') ? type : `pépinière ${type}`}` : ' en pépinière'
  return `Semer ${avecArticle(tuile.culture)}${variete}${ou}`
}

/** « l'oignon blanc n'a pas levé après 34 jours », « le chou-fleur attend un emplacement ». */
function phraseDAlerte(lot, alerte) {
  const sujet = avecArticle(nomMinuscule(lot))
  switch (alerte.code) {
    case 'pas_leve': return `${sujet} n’a pas levé après ${alerte.jours} jours`
    case 'sans_emplacement': return `${sujet} attend un emplacement`
    case 'quantite': return `${sujet} : la quantité semée n’est pas dite`
    case 'dormant': return `${sujet} est sans geste depuis ${alerte.jours} jours`
    default: return sujet
  }
}

/** « **2 lots à régler** : l'oignon blanc n'a pas levé après 34 jours, le chou-fleur attend un emplacement. » */
export function phraseARegler(lots, alertes) {
  const concernes = (lots ?? []).filter((l) => alertes.has(l.lot_id))
  if (!concernes.length) return null
  const liste = concernes.slice(0, 3).map((l) => phraseDAlerte(l, alertes.get(l.lot_id)))
  const sujet = concernes.length === 1 ? '1 lot à régler' : `${concernes.length} lots à régler`
  return { concernes, texte: `**${sujet}** : ${liste.join(', ')}.` }
}

/**
 * [CA5] Le mot du Parcours : les lots à régler → *Ranger le chou-fleur* (Gaston) si l'un attend un
 * emplacement, *Voir les lots* (onglet Lots, filtre À régler). Rien à dire → `null`.
 */
export function motDuParcours({ lots, alertes }) {
  const p = phraseARegler(lots, alertes)
  if (!p) return null
  const actions = []
  const sans = p.concernes.find((l) => alertes.get(l.lot_id).code === 'sans_emplacement')
  if (sans) {
    actions.push({
      libelle: `Ranger ${avecArticle(nomMinuscule(sans))}`,
      noter: true, principale: true,
      // [US-358 / CA1] Le lot sans emplacement : son sujet et sa phrase, prêts dans le champ.
      sujet: { type: 'lot', culture: sans.culture, numero: sans.numero_lot ?? null, texte: [sans.numero_lot != null ? `Lot n° ${sans.numero_lot}` : 'Lot', majuscule(sans.culture ?? '')].join(' · ') },
      phrase: `Ranger ${avecArticle(nomMinuscule(sans))}`,
    })
  }
  actions.push({ libelle: 'Voir les lots', vue: 'pepiniere', intention: { onglet: 'lots', filtreLots: 'a_regler' }, principale: !sans })
  return normaliserMot({ texte: p.texte, actions })
}

/**
 * [CA10] Le mot des Lots : les lots à régler. Sans action : le tableau montre déjà la colonne
 * « À régler » (la maquette « Socle commun » a retiré le bouton avec la colonne « Tous »).
 */
export function motDesLots({ lots, alertes }) {
  const p = phraseARegler(lots, alertes)
  if (!p) return null
  return normaliserMot({ texte: p.texte, actions: [] })
}

// ── « Semer » (CA6, CA7, CA8) ─────────────────────────────────────────────────────────────────────

const JOUR_COURT = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']

/** « 1er sept. », « 30 nov. » d'une date ISO. */
export function jourCourt(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  if (!m) return ''
  return `${Number(m[3]) === 1 ? '1er' : Number(m[3])} ${JOUR_COURT[Number(m[2]) - 1]}`
}

/** « 1er sept. → 30 nov. », ou la fenêtre en lettres du serveur quand les bornes manquent. */
export const fenetreEnClair = (c) => (c?.du && c?.au ? `${jourCourt(c.du)} → ${jourCourt(c.au)}` : (c?.fenetre ?? ''))

/** Le type de pépinière du moteur : « pépinière froide », ou rien — jamais deviné. */
export const typeDePepiniere = (c) => c?.confiance?.pepiniere?.libelle ?? ''

/** Les tuiles de « Fenêtre ouverte » : celles de `parcours.a_semer`, la plus pressée d'abord. */
export function tuilesASemer(parcours) {
  return (parcours?.a_semer ?? []).map((c) => ({
    culture: c.culture,
    nom: majuscule(c.culture),
    reste: c.jours_restants != null ? `reste ${c.jours_restants} j` : null,
    joursRestants: c.jours_restants ?? null,
    part: c.part_ecoulee != null ? Math.round(c.part_ecoulee * 100) : null,
    fenetre: [fenetreEnClair(c), typeDePepiniere(c)].filter(Boolean).join(' · '),
    type: typeDePepiniere(c),   // [US-358] « pépinière froide », pour la phrase « Semer … en pépinière froide »
    varietes: c.varietes_en_stock ?? [],
  }))
}

/** « Graines épuisées : à racheter », « Un lot est déjà en cours (#59) » ; `null` : motif non calculable, non dit. */
export function motifEcarte(e) {
  if (e?.motif === 'graines_epuisees') return 'Graines épuisées : à racheter'
  if (e?.motif === 'lot_en_cours') return e.lot_numero != null ? `Un lot est déjà en cours (#${e.lot_numero})` : 'Un lot est déjà en cours'
  return null
}

/** Les cultures écartées dont le motif est dit. */
export function ecartees(parcours) {
  return (parcours?.a_semer_ecartees ?? [])
    .map((e) => ({ culture: e.culture, nom: majuscule(e.culture), motif: motifEcarte(e), code: e.motif }))
    .filter((e) => e.motif)
}

/** « Poireau d'été — semis en pépinière à partir du 1er janv. », « dans 45 j ». */
export function prochainesOuvertures(parcours) {
  return (parcours?.prochaines_ouvertures ?? []).map((o) => ({
    culture: o.culture,
    nom: majuscule(o.culture),
    texte: `semis en pépinière à partir du ${jourCourt(o.date)}`,
    dans: o.jours != null ? `dans ${o.jours} j` : '',
  }))
}

/** Le nombre de l'onglet « Semer · n » : les cultures dont la fenêtre est ouverte et qu'on peut semer. */
export const nbASemer = (parcours) => (parcours?.a_semer ?? []).length

/**
 * [CA8] Le mot de Semer : « **3 cultures sont dans leur fenêtre** et vous avez les graines. L'oignon blanc ferme
 * dans 7 jours. » → *Semer l'oignon blanc* (Gaston). Aucune fenêtre ouverte : la prochaine ouverture.
 */
export function motDeSemer(parcours) {
  const tuiles = tuilesASemer(parcours).sort((a, b) => (a.joursRestants ?? 1e9) - (b.joursRestants ?? 1e9))
  if (tuiles.length) {
    const premiere = tuiles[0]
    const defini = avecArticle(premiere.culture)
    const sujet = tuiles.length === 1 ? '**1 culture est dans sa fenêtre**' : `**${tuiles.length} cultures sont dans leur fenêtre**`
    const ferme = premiere.joursRestants != null
      ? ` ${majuscule(defini)} ferme dans ${premiere.joursRestants} ${premiere.joursRestants > 1 ? 'jours' : 'jour'}.` : ''
    return normaliserMot({
      texte: `${sujet} et vous avez les graines.${ferme}`,
      actions: [{
        libelle: `Semer ${defini}`, noter: true, principale: true,
        sujet: { type: 'semer', culture: premiere.culture, texte: [premiere.nom, premiere.fenetre].filter(Boolean).join(' · ') },
        phrase: phraseSemer(premiere),
      }],
    })
  }
  const prochaine = prochainesOuvertures(parcours)[0]
  if (!prochaine) return null
  return normaliserMot({
    texte: `**Aucune fenêtre n’est ouverte** pour l’instant. ${majuscule(avecArticle(prochaine.culture))} s’ouvre ${prochaine.dans.replace(/ j$/, ' jours')}.`,
    actions: [],
  })
}

// ── Le registre des lots (CA9) ────────────────────────────────────────────────────────────────────

/** « **18 lots** cette saison · **14** en cours dont 2 à régler · **4** terminés, 34 plants sortis vers le potager » */
export function bilanRegistre(lots, alertes) {
  const c = comptesRegistre(lots, alertes)
  // Les plants sortis vers le potager : les mises en terre de TOUS les lots de la saison.
  const sortis = (lots ?? []).reduce((n, l) => n + Math.max(0, Number(l.nb_plantes) || 0), 0)
  const enCours = c.en_cours + c.a_regler
  return {
    ...c,
    enCours,
    plantsSortis: sortis,
    texte: `${c.tous} lot${c.tous > 1 ? 's' : ''} cette saison · ${enCours} en cours${c.a_regler ? ` dont ${c.a_regler} à régler` : ''} · ${c.termine} terminé${c.termine > 1 ? 's' : ''}${sortis ? `, ${sortis} plants sortis vers le potager` : ''}`,
  }
}

/**
 * Les trois colonnes du registre — l'état d'un lot —, avec la couleur de leur pastille. Plus de
 * colonne « Tous » : elle doublait les trois autres (maquette « Socle commun »).
 */
export const COLONNES_REGISTRE = Object.freeze([
  Object.freeze({ cle: 'en_cours', libelle: 'En cours', couleur: '#4A7C22' }),
  Object.freeze({ cle: 'a_regler', libelle: 'À régler', couleur: '#D9822B' }),
  Object.freeze({ cle: 'termine', libelle: 'Terminés', couleur: '#9AA58F' }),
])
/** La colonne à montrer en premier sur mobile : celle qu'on demande, sinon « En cours ». */
export const colonneRegistreInitiale = (cle) => (COLONNES_REGISTRE.some((c) => c.cle === cle) ? cle : 'en_cours')

/** Les lots visibles : filtre (avec alertes), recherche, tri par date de semis décroissante. */
export function lotsDuRegistre(lots, alertes, { filtre = 'tous', q = '' } = {}) {
  const t = String(q ?? '').trim().toLowerCase().replace(/^#/, '')
  return (lots ?? [])
    .filter((l) => filtre === 'tous' || statutPepiniere(l, alertes) === filtre)
    .filter((l) => !t || `${l.numero_lot ?? ''} ${l.culture ?? ''} ${l.variete ?? ''}`.toLowerCase().includes(t))
    .sort((a, b) => String(b.date_semis ?? '').localeCompare(String(a.date_semis ?? '')) || (b.numero_lot ?? 0) - (a.numero_lot ?? 0))
}

const MOIS_LONGS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

/** La teinte de chaque rangée du registre, du mois le plus récent au plus ancien (maquette « Socle commun »). */
export const COULEURS_MOIS = Object.freeze(['#5A8CC8', '#C27C0E', '#8C6BC0', '#7C8A72'])
const COULEUR_SANS_DATE = '#9AA58F'

const capitale = (t) => (t ? t[0].toUpperCase() + t.slice(1) : t)
const moisDe = (n) => MOIS_LONGS[((n % 12) + 12) % 12]

/**
 * Les RANGÉES du registre : les lots rangés par mois de semis, du plus récent au plus ancien, chacune
 * avec sa teinte. Le mois en cours (et tout lot daté plus tard), le mois d'avant, les deux mois
 * précédents réunis (« Septembre et août »), puis « Plus tôt dans la saison » (« mars → juillet ») ;
 * un lot sans date de semis a sa rangée à part. Une rangée sans lot n'existe pas.
 * Rien d'autre n'est calculé ici que l'écart en mois à `aujourdhui`.
 */
export function rangeesParMoisDeSemis(lots, aujourdhui) {
  const an = Number(String(aujourdhui ?? '').slice(0, 4)) || new Date().getFullYear()
  const m0 = Number(String(aujourdhui ?? '').slice(5, 7)) - 1
  const maintenant = an * 12 + (m0 >= 0 ? m0 : new Date().getMonth())
  const rangs = [
    { cle: 'courant', titre: capitale(moisDe(maintenant)), sousTitre: 'semés ce mois-ci', couleur: COULEURS_MOIS[0], lots: [] },
    { cle: 'precedent', titre: capitale(moisDe(maintenant - 1)), sousTitre: '', couleur: COULEURS_MOIS[1], lots: [] },
    { cle: 'avant', titre: `${capitale(moisDe(maintenant - 2))} et ${moisDe(maintenant - 3)}`, sousTitre: '', couleur: COULEURS_MOIS[2], lots: [] },
    { cle: 'plus-tot', titre: 'Plus tôt dans la saison', sousTitre: '', couleur: COULEURS_MOIS[3], lots: [] },
    { cle: 'sans', titre: 'Sans date de semis', sousTitre: '', couleur: COULEUR_SANS_DATE, lots: [] },
  ]
  const parCle = Object.fromEntries(rangs.map((r) => [r.cle, r]))
  for (const lot of lots ?? []) {
    const d = lot.date_semis
    if (!d) { parCle.sans.lots.push(lot); continue }
    const ecart = maintenant - (Number(d.slice(0, 4)) * 12 + Number(d.slice(5, 7)) - 1)
    parCle[ecart <= 0 ? 'courant' : ecart === 1 ? 'precedent' : ecart <= 3 ? 'avant' : 'plus-tot'].lots.push(lot)
  }
  // « mars → juillet » : l'étendue des lots rangés « plus tôt » (l'année dite quand ce n'est pas la nôtre).
  const tot = parCle['plus-tot']
  if (tot.lots.length) {
    const dates = tot.lots.map((l) => l.date_semis).sort()
    const dire = (d) => `${MOIS_LONGS[Number(d.slice(5, 7)) - 1]}${Number(d.slice(0, 4)) !== an ? ` ${d.slice(0, 4)}` : ''}`
    const [debut, fin] = [dire(dates[0]), dire(dates[dates.length - 1])]
    tot.sousTitre = debut === fin ? debut : `${debut} → ${fin}`
  }
  return rangs.filter((r) => r.lots.length > 0)
}

/**
 * Le registre en matrice : colonnes = état du lot (En cours, À régler, Terminés), rangées = mois de
 * semis. `cases[cle]` : les lots de la rangée dans cet état (vide → « vide » à l'écran).
 */
export function matriceRegistre(lots, alertes, aujourdhui, { q = '' } = {}) {
  const visibles = lotsDuRegistre(lots, alertes, { filtre: 'tous', q })
  const rangees = rangeesParMoisDeSemis(visibles, aujourdhui).map((r) => ({
    ...r,
    total: r.lots.length,
    cases: Object.fromEntries(COLONNES_REGISTRE.map((c) => [c.cle, r.lots.filter((l) => statutPepiniere(l, alertes) === c.cle)])),
  }))
  const comptes = comptesRegistre(visibles, alertes)
  return { colonnes: COLONNES_REGISTRE.map((c) => ({ ...c, total: comptes[c.cle] })), rangees, total: visibles.length }
}

/** La carte d'un lot du registre : celle du Parcours, avec la quantité que dit le stock quand il n'a pas d'étiquette. */
export function carteLotDuRegistre(lot, parcours, alertes) {
  return carteLot({ lot, etiquette: null, alerte: alertes?.get(lot.lot_id) ?? null, quantite: quantiteDuLot(lot, parcours) })
}

// ── La ligne du registre et la fiche d'un lot (CA9, CA11) ─────────────────────────────────────────

const PRIORITE_STADE = ['pret', 'endurcissement', 'godet', 'levee']

/**
 * Le stade d'un lot : celui de son étiquette la plus avancée dans le Parcours ; `terminee` pour un lot
 * terminé ou clôturé ; à défaut, ce que dit le stock du lot (godets → En godet, graines → En levée).
 */
export function stadeDuLot(lot, parcours) {
  if (estTermine(lot) || estCloture(lot)) return 'terminee'
  const siennes = (parcours?.etiquettes ?? []).filter((e) => e.lot?.id === lot.lot_id)
  for (const s of PRIORITE_STADE) if (siennes.some((e) => e.stade === s)) return s
  if ((lot.stock_residuel_godet ?? 0) > 0) return 'godet'
  return 'levee'
}

const LIBELLE_STADE = Object.freeze({
  levee: 'En levée', godet: 'En godet', endurcissement: 'Endurcissement', pret: 'Prêt à sortir', terminee: 'Terminé',
})
export const libelleStadeLot = (stade) => LIBELLE_STADE[stade] ?? ''

/** « Serre · pépinière chaude » : l'emplacement d'un lot et son type, ou « Sans emplacement ». */
export function emplacementDuLot(lot, parcours) {
  const sans = (parcours?.etiquettes ?? []).some((e) => e.lot?.id === lot.lot_id && e.emplacement_id == null)
  const nom = lot.parcelle
  if (!nom || sans) return { nom: 'Sans emplacement', type: 'à ranger', texte: 'Sans emplacement · à ranger' }
  const type = lot.type_pepiniere ? `pépinière ${lot.type_pepiniere}` : 'type non renseigné'
  return { nom, type, texte: `${nom} · ${type}` }
}

/** La quantité d'un lot en une expression : « 12 godets », « 24 graines », « 1 caissette ». */
export function quantiteDuLot(lot, parcours) {
  const e = (parcours?.etiquettes ?? []).find((x) => x.lot?.id === lot.lot_id)
  if (e) return quantitesEtiquette(e).principal
  if ((lot.stock_residuel_godet ?? 0) > 0) return `${lot.stock_residuel_godet} godet${lot.stock_residuel_godet > 1 ? 's' : ''}`
  if ((lot.graines_semees ?? 0) > 0) return `${lot.graines_semees} graine${lot.graines_semees > 1 ? 's' : ''}`
  return 'quantité non dite'
}

/** Une ligne du registre : n°, stade, culture · variété, emplacement · quantité · date, frise, alerte. */
export function ligneRegistre(lot, parcours, alertes) {
  const stade = stadeDuLot(lot, parcours)
  const lieu = emplacementDuLot(lot, parcours)
  const gestes = gestesDates(lot)
  const alerte = alertes?.get(lot.lot_id) ?? null
  const detail = [lieu.nom, quantiteDuLot(lot, parcours), lot.date_semis ? `semé le ${dateCourte(lot.date_semis)}` : null].filter(Boolean).join(' · ')
  return {
    cle: lot.lot_id,
    numero: lot.numero_lot != null ? `#${lot.numero_lot}` : '—',
    stade,
    etape: etapeDuStade(stade),
    emoji: symboleDeCulture(lot.culture, lot.variete),
    culture: majuscule(lot.culture ?? ''),
    variete: lot.variete ?? '',
    detail,
    nbGestes: gestes.length,
    alerte: alerte?.texte ?? null,
    nomAccessible: `Lot ${lot.numero_lot ?? ''}, ${lot.culture}${lot.variete ? ` ${lot.variete}` : ''}, ${libelleStadeLot(stade)}, ${detail}, ${gestes.length} gestes datés${alerte ? `, ${alerte.texte}` : ''}`,
  }
}

/** « Gestes datés » de la fiche : `[{ date, titre }]`, du plus ancien au plus récent (dates ISO courtes dites). */
export function gestesDeLaFiche(lot) {
  return gestesDates(lot).map((g) => ({
    code: g.code, titre: g.titre, detail: g.detail, date: g.date ? dateCourte(g.date) : '',
  }))
}

export { STADES }
