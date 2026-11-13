// [US-328] « Aujourd'hui au potager » — ce qui est à confirmer, à libérer et à placer.
//
// Les trois listes viennent du serveur (`GET /plan` → `taches_du_jour`), à la date de référence,
// avec les mêmes comptes que les filtres du plan (CA2) : ce fichier ne fait que les METTRE EN
// FORME (emoji, nom, lieu, libellés) et préparer la proposition de placement que Gaston recevra.
// Rien ici n'écrit : glisser une carte sur un rang ouvre Gaston, qui propose (CA4).
import { nomCulture, jourEnLettres } from './planDessus.js'
import { symboleDeCulture } from './pictosCultures.js'

export const TITRE_AUJOURDHUI = 'Aujourd’hui au potager'
export const AIDE_AUJOURDHUI = 'Glissez sur un rang libre du plan. Touchez une culture pour ouvrir son suivi.'
export const AIDE_CLAVIER = 'Au clavier : Entrée sur une carte, puis Entrée sur un rang libre. Échap pour annuler.'

export const LISTE_A_CONFIRMER = 'a_confirmer'
export const LISTE_A_LIBERER = 'a_liberer'
export const LISTE_A_PLACER = 'a_placer'

/** [CA1] Les blocs A2 à A4, dans l'ordre de la maquette, et ce que dit une liste vide. */
export const LISTES = Object.freeze([
  { cle: LISTE_A_CONFIRMER, titre: 'À confirmer', vide: 'Rien à confirmer' },
  { cle: LISTE_A_LIBERER, titre: 'À libérer', vide: 'Rien à libérer' },
  { cle: LISTE_A_PLACER, titre: 'À placer', vide: 'Rien à placer' },
])

const MOIS_COURTS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const JOURS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi']

/** « 30 oct. » d'une date ISO. */
export function jourCourt(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${Number(m[3])} ${MOIS_COURTS[Number(m[2]) - 1]}` : ''
}

/** Le jour de la semaine d'une date ISO, sans fuseau. */
export function jourDeSemaine(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  if (!m) return ''
  return JOURS[new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))).getUTCDay()]
}

/** « Planche haricots · R2 », ou la parcelle seule. */
export const lieuDeLigne = (l) => (l.rang ? `${l.parcelle} · R${l.rang}` : l.parcelle || '')

/** La sélection d'une ligne, telle que le suivi d'une culture (US-322) la reçoit. */
export function selectionDeLigne(l) {
  return {
    parcelleId: l.parcelle_id,
    parcelle: l.parcelle,
    culture: l.culture,
    variete: l.variete || null,
    rang: l.rang ?? null,
    cle: `${l.culture}|${l.variete || ''}|${l.rang ?? ''}`,
  }
}

/** [A2] Une culture à confirmer : emoji, nom, lieu, étape prévue. */
export function ligneAConfirmer(l) {
  const nom = nomCulture(l.culture, l.variete)
  const etape = l.etape_libelle || ''
  return {
    cle: `c-${l.parcelle_id}-${l.culture}-${l.variete || ''}`,
    emoji: symboleDeCulture(l.culture, l.variete || ''),
    nom,
    lieu: lieuDeLigne(l),
    detail: etape ? `Prévu : ${etape}` : '',
    pastille: 'À confirmer',
    nomAccessible: `${nom}, ${lieuDeLigne(l)}${etape ? `, ${etape} à confirmer` : ''} : ouvrir son suivi`,
    selection: selectionDeLigne(l),
  }
}

/** [A3] Une culture terminée dont le rang n'est pas libéré, avec sa date de fin. */
export function ligneALiberer(l) {
  const nom = nomCulture(l.culture, l.variete)
  const fin = l.fin_le ? `Terminée le ${jourCourt(l.fin_le)}` : 'Terminée'
  return {
    cle: `l-${l.parcelle_id}-${l.culture}-${l.variete || ''}`,
    emoji: symboleDeCulture(l.culture, l.variete || ''),
    nom,
    lieu: lieuDeLigne(l),
    detail: fin,
    pastille: 'À libérer',
    nomAccessible: `${nom}, ${lieuDeLigne(l)}, ${fin.toLowerCase()}, rang à libérer : ouvrir son suivi`,
    selection: selectionDeLigne(l),
  }
}

/** « 12 plants », « 1,5 m² ». */
export function quantiteEnLettres(q, unite = 'plants') {
  if (q == null || q === '') return ''
  const n = Number.isInteger(q) ? String(q) : String(Math.round(q * 10) / 10).replace('.', ',')
  return `${n} ${unite || 'plants'}`
}

/** [A4] Une carte à placer : emoji, nom, variété, quantité, origine. */
export function carteAPlacer(c) {
  const nom = nomCulture(c.culture, null)
  const origine = c.origine === 'lot'
    ? [c.numero_lot != null ? `Lot #${c.numero_lot}` : 'Lot', c.pepiniere].filter(Boolean).join(' · ')
    : 'Dite à Gaston, sans parcelle'
  const quantite = quantiteEnLettres(c.quantite, c.unite)
  return {
    cle: c.origine === 'lot' ? `lot-${c.lot_id ?? c.numero_lot}` : `sp-${c.culture}-${c.variete || ''}`,
    emoji: symboleDeCulture(c.culture, c.variete || ''),
    nom,
    variete: c.variete || '',
    quantite,
    origine,
    nomAccessible: [nom, c.variete, quantite, origine].filter(Boolean).join(', ')
      + ' : à placer sur un rang libre',
    carte: c,
  }
}

/** [CA1, CA2] Les trois listes mises en forme, et leurs comptes (ceux du serveur). */
export function tachesDuPlan(plan) {
  const t = plan?.taches_du_jour || {}
  return {
    [LISTE_A_CONFIRMER]: (t.a_confirmer || []).map(ligneAConfirmer),
    [LISTE_A_LIBERER]: (t.a_liberer || []).map(ligneALiberer),
    [LISTE_A_PLACER]: (t.a_placer || []).map(carteAPlacer),
  }
}

/** [A1, CA6] La date, la température et l'alerte gel ; null sans prévision (la ligne disparaît). */
export function meteoDuJour(meteo) {
  if (!meteo || meteo.localisation_manquante) return null
  const temperature = meteo.temp_actuelle ?? meteo.temp_max
  const gel = (meteo.previsions || []).find((p) => typeof p.temp_min === 'number' && p.temp_min <= 0)
  const alerte = gel ? `gel possible ${jourDeSemaine(gel.date)}`.trim() : null
  if (temperature == null && !alerte) return null
  return { temperature: temperature == null ? null : `${Math.round(temperature)}°`, alerte, emoji: meteo.emoji || '' }
}

/** [A1] « jeudi 12 novembre ». */
export const dateDuJour = (iso) => [jourDeSemaine(iso), jourEnLettres(iso)].filter(Boolean).join(' ')

/**
 * [CA4, CA5, Gherkin] Ce que Gaston reçoit quand une carte est posée sur un rang libre : la phrase
 * « Placer 12 fraisiers Mara des bois · Planche haricots, rang 2 », le rang en contexte d'écran
 * (US-323) et la carte en `placement`, avec la part libre du rang (US-326).
 */
export function propositionDePlacement(carte, forme, segment) {
  const quoi = [carte.quantite, carte.culture, carte.variete].filter((x) => x != null && x !== '').join(' ')
  const lieu = `${forme.nom}, rang ${segment.numero}`
  return {
    phrase: `Placer ${quoi} · ${lieu}`,
    contexte: { parcelleId: forme.id, parcelle: forme.nom, rang: segment.numero },
    placement: {
      culture: carte.culture,
      variete: carte.variete || null,
      quantite: carte.quantite ?? null,
      unite: carte.unite || 'plants',
      numero_lot: carte.numero_lot ?? null,
      part: typeof segment.part === 'number' ? Math.min(1, Math.round(segment.part * 100) / 100) : 1,
    },
  }
}

/** [CA4] L'annonce aux lecteurs d'écran quand une carte est prise au clavier. */
export const annonceCarteEnMain = (c) =>
  `${c.nom}${c.quantite ? `, ${c.quantite}` : ''} en main : choisissez un rang libre du plan, ou Échap pour annuler.`

/** [CA7] Les boutons du mobile : « N à confirmer », « N à libérer » ; absents quand la liste est vide. */
export function boutonsMobile(taches) {
  return [
    { cle: LISTE_A_CONFIRMER, suffixe: 'à confirmer' },
    { cle: LISTE_A_LIBERER, suffixe: 'à libérer' },
  ]
    .map(({ cle, suffixe }) => {
      const liste = taches?.[cle] || []
      return { cle, texte: `${liste.length} ${suffixe}`, premiere: liste[0] || null, nombre: liste.length }
    })
    .filter((b) => b.nombre > 0)
}
