// [US-322] Le suivi d'une culture en place — la mise en mots de ce que `GET /plan/suivi`
// renvoie. Aucune règle ici (CA4) : l'étape, la place sur le rang, l'origine, le cumul
// récolté viennent du serveur ; ce fichier ne fait que les dire, dans l'ordre S1 → S10.
//
// Chaque fonction rend `null` quand sa donnée manque : le bloc est absent plutôt que
// vide (CA2).

import { jourEnLettres, nomCulture } from './planDessus.js'
import { etape as lireEtape, VARIANTE_PREVU, VARIANTE_PLEIN } from './etapes.js'
import { symboleDeCulture } from './pictosCultures.js'
import { EVENEMENT_OUVRIR_COMPAGNON } from './contexteCompagnon.js'

/** Le nom d'une étape vue comme un événement (« Levée », pas « Levé »). */
const NOM_EVENEMENT = Object.freeze({
  semee: ['Semis', 'le semis'],
  levee: ['Levée', 'la levée'],
  plantee: ['Plantation', 'la plantation'],
  croissance: ['Croissance', 'la croissance'],
  fleur: ['Floraison', 'la floraison'],
  en_recolte: ['Récolte', 'la récolte'],
  terminee: ['Fin de culture', 'la fin de culture'],
})

export const nomEvenement = (cle) => NOM_EVENEMENT[cle]?.[0] || ''
const nomEvenementMinuscule = (cle) => NOM_EVENEMENT[cle]?.[1] || ''

const nombre = (v) => String(Math.round(v * 10) / 10).replace('.', ',')

/** « 20 oct. » est la forme de la maquette ; on écrit le mois entier, plus lisible. */
export const dateLisible = (iso) => jourEnLettres(iso)

/** [S1] L'en-tête : emoji, nom, variété, quantité. */
export function enTete(s) {
  if (!s) return null
  const unite = s.unite === 'plants' || !s.unite ? (Number(s.quantite) > 1 ? 'plants' : 'plant') : s.unite
  return {
    emoji: symboleDeCulture(s.culture, s.variete || ''),
    titre: nomCulture(s.culture, null),
    sousTitre: [s.variete, s.quantite != null ? `${nombre(Number(s.quantite))} ${unite}` : null].filter(Boolean).join(' · '),
  }
}

function listeRangs(rangs) {
  const n = [...(rangs || [])].sort((a, b) => a - b)
  if (!n.length) return ''
  if (n.length === 1) return `rang ${n[0]}`
  const suite = n.every((v, i) => i === 0 || v === n[i - 1] + 1)
  if (suite && n.length > 2) return `rangs ${n[0]} à ${n[n.length - 1]}`
  return `rangs ${n.slice(0, -1).join(', ')} et ${n[n.length - 1]}`
}

/** [S2] « Planche centrale, rang 3 », ou « pas encore placée ». */
export function localisation(s) {
  if (!s) return null
  if (!s.parcelle) return { texte: 'pas encore placée', lien: false }
  const rangs = listeRangs(s.rangs)
  return { texte: rangs ? `${s.parcelle}, ${rangs}` : s.parcelle, lien: true }
}

/**
 * [S3] La ligne de place : pieds, mètres occupés sur la longueur du rang, espacement,
 * mètres libres — ou « ⚠ +N » en dépassement. `null` si la place n'est pas calculable.
 */
export function lignePlace(s) {
  const p = s?.place
  if (!p) return null
  const morceaux = [`${p.pieds} ${p.pieds > 1 ? 'pieds' : 'pied'}`]
  if (p.metres_occupes != null && p.longueur_m) morceaux.push(`${nombre(p.metres_occupes)} m sur ${nombre(p.longueur_m)} m`)
  if (p.espacement_cm) morceaux.push(`tous les ${p.espacement_cm} cm`)
  const depassement = p.depassement_pieds > 0
  if (!depassement && p.metres_libres != null) morceaux.push(`${nombre(p.metres_libres)} m libres`)
  return {
    texte: morceaux.join(' · '),
    depassement: depassement ? `⚠ +${p.depassement_pieds}` : null,
    nomAccessible: depassement
      ? `${morceaux.join(', ')}, dépassement de ${p.depassement_pieds} ${p.depassement_pieds > 1 ? 'pieds' : 'pied'}`
      : morceaux.join(', '),
  }
}

/** [S4] L'étape courante : son étiquette et sa date, « prévue le … » si prévue. */
export function etapeCourante(s) {
  const e = s?.etapes
  if (!e || !lireEtape(e.etape)) return null
  const prevue = e.etape_statut === 'prevue' || e.etape_statut === 'non_notee'
  const date = e.etape_date ? dateLisible(e.etape_date) : ''
  return {
    cle: e.etape,
    prevue,
    texte: date ? (prevue ? `prévue le ${date}` : `depuis le ${date}`) : (prevue ? 'prévue' : ''),
  }
}

/** [S5] Le bandeau « Levée prévue aujourd'hui : à confirmer en notant ». */
export function bandeauAConfirmer(s) {
  const e = s?.etapes
  if (!e?.a_confirmer) return null
  const quand = e.etape_date && e.etape_date === s.date_ref_effective
    ? 'aujourd’hui'
    : (e.etape_date ? `le ${dateLisible(e.etape_date)}` : '')
  return `${nomEvenement(e.etape)} prévue ${quand} : à confirmer en notant`.replace(/\s+:/, ' :')
}

/** [S6] Le seul bouton : « Noter », ou « Noter la levée » sur mobile quand c'est à confirmer. */
export function libelleNoter(s, { compact = false } = {}) {
  const e = s?.etapes
  if (compact && e?.a_confirmer && NOM_EVENEMENT[e.etape]) return `Noter ${nomEvenementMinuscule(e.etape)}`
  return 'Noter'
}

/** [S7] « 2,9 kg récoltés », si la culture a été récoltée. */
export function texteRecolte(s) {
  const r = s?.recolte
  if (!r || !r.quantite) return null
  return `${nombre(r.quantite)} ${r.unite} récoltés`
}

export const ETAT_FAITE = 'faite'
export const ETAT_COURANTE = 'courante'
export const ETAT_A_VENIR = 'a_venir'

/**
 * [S8] La frise : étapes passées datées, l'étape courante, la prochaine avec sa date
 * prévue. Les suivantes restent sans date — on ne promet pas une fin de culture.
 */
export function frise(s) {
  const e = s?.etapes
  if (!e?.etapes?.length) return null
  const iCourante = e.etapes.findIndex((x) => x.code === e.etape)
  return e.etapes.map((x, i) => {
    const etat = i < iCourante ? ETAT_FAITE : i === iCourante ? ETAT_COURANTE : ETAT_A_VENIR
    const prevue = x.statut === 'prevue' || x.statut === 'non_notee'
    let date = ''
    if (x.date && (etat !== ETAT_A_VENIR || i === iCourante + 1)) {
      date = prevue ? `prévue le ${dateLisible(x.date)}` : dateLisible(x.date)
    }
    if (x.statut === 'non_notee' && etat === ETAT_FAITE) date = 'non notée'
    return {
      cle: x.code,
      nom: nomEvenement(x.code),
      etat,
      date,
      variante: prevue ? VARIANTE_PREVU : VARIANTE_PLEIN,
      aConfirmer: etat === ETAT_COURANTE && Boolean(e.a_confirmer),
    }
  })
}

/** [S9] L'origine : pépinière (lot), achat, ou semis direct. */
export function origine(s) {
  const o = s?.origine
  if (!o) return null
  if (o.type === 'pepiniere') {
    const details = [
      o.date_semis ? `semé le ${dateLisible(o.date_semis)}` : null,
      o.godets ? `${o.godets} godets` : null,
      o.plantes ? `${o.plantes} plantés${o.date_plantation ? ` le ${dateLisible(o.date_plantation)}` : ''}` : null,
    ].filter(Boolean)
    return {
      type: o.type,
      titre: o.numero_lot != null ? `Pépinière · lot #${o.numero_lot}` : 'Pépinière',
      detail: details.join(' · '),
      numeroLot: o.numero_lot ?? null,
    }
  }
  if (o.type === 'achat') {
    return {
      type: o.type,
      titre: 'Achat',
      detail: o.texte || (o.date_plantation ? `planté le ${dateLisible(o.date_plantation)}` : ''),
      numeroLot: null,
    }
  }
  return {
    type: o.type,
    titre: 'Semis direct',
    detail: o.date ? `semé en place le ${dateLisible(o.date)}` : 'semé en place',
    numeroLot: null,
  }
}

/** [S10] Les notes datées, les plus récentes d'abord (le serveur les trie). */
export function notes(s) {
  const n = (s?.notes || []).filter((x) => x.texte)
  if (!n.length) return null
  return n.map((x) => ({ id: x.id, date: dateLisible(x.date), texte: x.texte, dictee: x.dictee === true }))
}

/** [S6] L'événement de fenêtre que la coquille (`App.jsx`) écoute pour ouvrir Gaston. */
export { EVENEMENT_OUVRIR_COMPAGNON }

/**
 * [US-323 / C1] Le contexte d'écran qui ouvre Gaston sur cette culture : la parcelle, la culture,
 * et le rang quand la culture n'en occupe qu'un.
 */
export function contexteNoter(s) {
  if (!s) return null
  const rangs = s.rangs || []
  const contexte = { culture: s.culture, variete: s.variete, parcelleId: s.parcelle_id, parcelle: s.parcelle }
  if (rangs.length === 1) contexte.rang = rangs[0]
  // [US-324 / CA2] L'étape courante choisit les pastilles de « Noter » (affichage seulement).
  if (s.etapes) contexte.etapes = s.etapes
  return contexte
}
