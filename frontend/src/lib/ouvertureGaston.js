// [US-358] Gaston s'ouvre déjà renseigné : la phrase d'ouverture et les suggestions se DÉDUISENT
// de ce que le jardinier avait sous les yeux, sans appel au modèle. Le modèle ne répond qu'au
// premier message envoyé (avec le contexte d'écran d'US-323).
//
// Fonctions pures : mêmes données, même ouverture. Une porte (Noter, une fiche, une tuile, un Mot de
// Gaston, le catalogue) fournit un `contexte` (identifiants envoyés au serveur, US-323) et, quand elle
// n'a pas de parcelle à désigner, un `sujet` — ce que le bandeau affiche, JAMAIS envoyé (CA6) :
//
//   contexte = { parcelleId, parcelle, culture, variete, rang, etapes }
//   sujet    = { type: 'catalogue' | 'semer' | 'lot' | 'culture' | 'ajout' | 'mot',
//                culture?, variete?, texte?, emoji?, varietes?, numero? }

import { nomCulture } from './planDessus.js'
import { avecArticle } from './pepiniereSocle.js'
import { libelleEtape } from './etapes.js'
import { normaliserContexte, normaliserSujet, SUJET } from './contexteCompagnon.js'
import { RACCOURCI, SORTE } from './noter.js'

// ── Les phrases d'ouverture (CA2) ───────────────────────────────────────────────────────────────────
export const PHRASE_SANS_CONTEXTE = 'Je vous écoute : une récolte, un semis, une observation, ou une culture à ajouter…'
export const PHRASE_AJOUT = 'Quelle culture voulez-vous ajouter ? Dites-moi son nom, et la variété si vous l’avez déjà choisie.'
export { SUJET }
export const PHRASE_A_ENVOYER = 'Voici la phrase prête : envoyez-la, ou modifiez-la d’abord.'

const bas = (t) => String(t ?? '').replace(/^./, (c) => c.toLowerCase())
const finDePhrase = 'Dites ce que vous voyez, ou touchez une suggestion.'

/** [CA1] « Céleri-rave · catalogue » : l'espèce du catalogue, sans parcelle ni rang. */
export const sujetCatalogue = (ligne) => normaliserSujet({
  type: SUJET.CATALOGUE, culture: ligne.culture, texte: `${ligne.nom || nomCulture(ligne.culture, null)} · catalogue`,
  varietes: ligne.brut?.varietes || ligne.varietes || [],
})

/** [CA1] La tuile « Semer » : la culture, sa variété et sa fenêtre. */
export const sujetSemer = (tuile) => normaliserSujet({
  type: SUJET.SEMER, culture: tuile.culture, variete: tuile.varietes?.length === 1 ? tuile.varietes[0] : null,
  texte: [tuile.nom || nomCulture(tuile.culture, null), tuile.fenetre].filter(Boolean).join(' · '),
})

/** [CA1] Le lot de la fiche : « Lot n° 12 · laitue · Pépinière froide ». */
export const sujetLot = ({ numero, culture, variete = null, emplacement = '' }) => normaliserSujet({
  type: SUJET.LOT, culture, variete, numero,
  texte: [numero != null ? `Lot n° ${numero}` : 'Lot', nomCulture(culture, null), emplacement].filter(Boolean).join(' · '),
})

/** [CA1] Une culture sans place au plan : la culture seule, affichée mais non envoyée. */
export const sujetCulture = (culture, variete = null) => normaliserSujet({
  type: SUJET.CULTURE, culture, variete, texte: nomCulture(culture, variete),
})

/** [CA1] « Une culture absente du catalogue ? Dites-la à Gaston » : aucun contexte, une phrase d'ajout. */
export const sujetAjout = () => normaliserSujet({ type: SUJET.AJOUT })

// ── L'étape sous les yeux : due, prévue, en récolte, terminée ──────────────────────────────────────

/** L'étape qui suit la courante dans la séquence servie par le serveur (US-320). */
function etapeSuivante(etapes) {
  const liste = etapes?.etapes || []
  const i = liste.findIndex((x) => x.code === etapes?.etape)
  return i >= 0 && i + 1 < liste.length ? liste[i + 1].code : null
}

/** `{ sorte: 'due' | 'prevue' | 'en_recolte' | 'terminee' | 'aucune', code }` d'après `contexte.etapes`. */
export function situationDEtape(contexte) {
  const e = contexte?.etapes
  if (!contexte?.culture || !e) return { sorte: 'aucune', code: null }
  if (e.a_liberer || e.etape === 'terminee') return { sorte: 'terminee', code: 'terminee' }
  if (e.a_confirmer) return { sorte: 'due', code: e.etape }
  if (e.etape === 'en_recolte') return { sorte: 'en_recolte', code: 'en_recolte' }
  const suivante = etapeSuivante(e)
  return suivante ? { sorte: 'prevue', code: suivante } : { sorte: 'aucune', code: null }
}

/** La culture en lettres minuscules, sans sa variété : « fève », « chou de Bruxelles ». */
const nomDit = (c) => bas(nomCulture(c.culture, null))

/** [CA2] La phrase d'ouverture, affichée comme une bulle de Gaston. Sans appel réseau. */
export function phraseOuverture({ contexte = null, sujet = null, champ = null } = {}) {
  const s = normaliserSujet(sujet)
  const c = normaliserContexte(contexte)
  if (s?.type === SUJET.AJOUT) return PHRASE_AJOUT
  if (champ) {
    // Une phrase pré-écrite : le jardinier l'envoie lui-même.
    if (s?.type === SUJET.CATALOGUE) return `Vous voulez ajouter ${avecArticle(s.culture)} à votre potager. ${PHRASE_A_ENVOYER}`
    if (s?.type === SUJET.SEMER) return `Vous voulez semer ${avecArticle(s.culture)}. ${PHRASE_A_ENVOYER}`
    return PHRASE_A_ENVOYER
  }
  if (c?.culture) {
    const nom = nomDit(c)
    const { sorte, code } = situationDEtape(c)
    if (sorte === 'due' || sorte === 'prevue' || sorte === 'aucune') return `Vous êtes sur ${nom}. ${finDePhrase}`
    if (sorte === 'en_recolte') return `Vous êtes sur ${nom}, en récolte. Une récolte, une observation ?`
    return `Vous êtes sur ${nom}, ${bas(libelleEtape(code))}. Un rang à libérer, une note ?`
  }
  if (s?.type === SUJET.LOT) {
    const dit = s.culture ? `, ${bas(nomCulture(s.culture, null))}` : ''
    return `Vous êtes sur le lot${s.numero != null ? ` n° ${s.numero}` : ''}${dit}. ${finDePhrase}`
  }
  if (s?.type === SUJET.CULTURE) return `Vous êtes sur ${bas(nomCulture(s.culture, null))}. ${finDePhrase}`
  if (c) return `Vous êtes sur ${c.parcelle}${c.rang ? `, rang ${c.rang}` : ''}. ${finDePhrase}`
  return PHRASE_SANS_CONTEXTE
}

// ── Les suggestions (CA3) ───────────────────────────────────────────────────────────────────────────

const p = (libelle, raccourci = null, sorte = SORTE.ENVOYER, extra = {}) => ({ libelle, raccourci, sorte, ...extra })
const NOTE = p('Note', null, SORTE.REDIGER, { debut: 'Note : ' })
const PAS_ENCORE = p('Pas encore', null, SORTE.PAS_ENCORE)
const RECOLTE = p('Récolte', RACCOURCI.RECOLTE, SORTE.SAISIR)
const GESTES_DE_PARCELLE = [p('Arrosé', RACCOURCI.ARROSE), p('Paillé', RACCOURCI.PAILLE), p('Désherbé', RACCOURCI.DESHERBE)]
/** Aucun contexte : trois mots que Gaston relance par une question. */
const SANS_CONTEXTE = [p('Récolte'), p('Semis'), p('Observation')]
/** Au plus ce nombre de variétés en suggestion : la rangée défile, elle ne doit pas se noyer. */
export const VARIETES_MAX = 8

/** « J'ai vu la levée » : la suggestion d'une étape à confirmer ou prévue ; null si l'étape n'a pas de geste. */
function vuDeLEtape(code) {
  if (code === 'levee') return p('J’ai vu la levée', RACCOURCI.ETAPE_LEVEE)
  if (code === 'en_recolte') return RECOLTE
  if (code === 'terminee') return p('Culture terminée', RACCOURCI.CULTURE_TERMINEE)
  return null
}

/**
 * [CA3] Les suggestions selon le contexte — la table de l'US :
 *
 * | aucun                 | Récolte, Semis, Observation                       |
 * | étape prévue ou due   | J'ai vu la levée (l'étape), Pas encore            |
 * | en récolte            | Récolte, Note                                     |
 * | terminé               | Libérer le rang, Note                             |
 * | espèce du catalogue   | après la réponse de Gaston : les variétés         |
 *
 * `repondu` : Gaston a déjà répondu au premier message. Une suggestion de forme `ENVOYER` est envoyée
 * comme message du jardinier ; `SAISIR` attend une quantité ; `REDIGER` pré-écrit le champ ; `PAS_ENCORE`
 * propose le report de l'étape (à confirmer, CA4).
 */
export function suggestionsDe({ contexte = null, sujet = null, repondu = false } = {}) {
  const s = normaliserSujet(sujet)
  if (s?.type === SUJET.AJOUT) return []
  if (s?.type === SUJET.CATALOGUE) return repondu ? s.varietes.slice(0, VARIETES_MAX).map((v) => p(v)) : []
  if (s?.type === SUJET.SEMER || s?.type === SUJET.MOT) return []
  const c = normaliserContexte(contexte)
  if (c?.culture) {
    const { sorte, code } = situationDEtape(c)
    if (sorte === 'terminee') return [p('Libérer le rang', RACCOURCI.RANG_LIBERE), NOTE]
    if (sorte === 'en_recolte') return [RECOLTE, NOTE]
    if (sorte === 'due' || sorte === 'prevue') {
      const vu = vuDeLEtape(code)
      return vu ? [vu, PAS_ENCORE] : [PAS_ENCORE]
    }
    return [RECOLTE, NOTE]
  }
  if (s?.type === SUJET.LOT || s?.type === SUJET.CULTURE) return [NOTE]
  if (c) return GESTES_DE_PARCELLE
  return SANS_CONTEXTE
}

/** [CA4] Le report proposé par « Pas encore » : un texte à confirmer, jamais une écriture directe. */
export function propositionDeReport(contexte) {
  const e = contexte?.etapes
  if (!e?.serie_id || !e?.etape) return null
  const nom = bas(nomCulture(contexte.culture || '', null))
  const quoi = e.etape === 'levee' ? 'la levée' : `l’étape « ${bas(libelleEtape(e.etape))} »`
  return {
    serieId: e.serie_id, etape: e.etape,
    texte: `Je reporte ${quoi}${nom ? ` de ${nom}` : ''} : vous n’avez pas encore vu ? Rien n’est enregistré avant Confirmer.`,
  }
}
