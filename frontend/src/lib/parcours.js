// [US-218] L'onglet « Ma pépinière » — le parcours du plant, en kanban
// emplacement × stade, la bande « Le bon moment pour semer » et le tiroir des
// dormants.
//
// Tout vient du bloc `parcours` de `GET /pepiniere/lots` (US-240) : la colonne de
// chaque étiquette, son état, son échéance, l'ordre dans une case, les compteurs.
// Ce module ne recalcule rien (RT7) : il range et il dit. Les gestes sont choisis
// par la règle de la fiche du lot (`gestesDuLot`, US-216 / CA15), sans copie.
import { dateEnClair, deLaCulture, gestesDuLot, placeEnClair } from './ficheLot.js'
import { niveauxParPepiniere } from './pepiniere.js'

const plur = (n, mot, pl = `${mot}s`) => `${n} ${n > 1 ? pl : mot}`
const normaliser = (t) => String(t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase()

// ── Les onglets ─────────────────────────────────────────────────────────────

/** [CA1] Deux onglets : « Ma pépinière » (le parcours), ouvert par défaut, puis « Lots ». */
export const ONGLETS_PEPINIERE = Object.freeze([
  Object.freeze({ cle: 'parcours', libelle: 'Ma pépinière' }),
  Object.freeze({ cle: 'lots', libelle: 'Lots' }),
])

/**
 * [CA1] L'onglet à ouvrir. Les adresses et intentions d'avant (« aujourdhui »,
 * « calendrier », « emplacements ») ouvrent le parcours.
 */
export function ongletInitial(demande) {
  return demande === 'lots' ? 'lots' : 'parcours'
}

// ── Les colonnes ────────────────────────────────────────────────────────────

/** [CA8] Les quatre colonnes, dans l'ordre du parcours ; `motif` : la trame lisible en gris (RT4). */
export const STADES = Object.freeze([
  Object.freeze({ cle: 'levee', libelle: 'En levée', court: 'Levée', motif: 'sem' }),
  Object.freeze({ cle: 'godet', libelle: 'En godet', court: 'Godet', motif: 'god' }),
  Object.freeze({ cle: 'endurcissement', libelle: 'Endurcissement', court: 'Endurci', motif: 'end' }),
  Object.freeze({ cle: 'pret', libelle: 'Prêt à sortir', court: 'Prêt', motif: 'frk' }),
])

const libelleStade = (cle) => STADES.find((s) => s.cle === cle)?.libelle.toLowerCase() ?? cle

/** « pépinière chaude », « pépinière froide », « type non renseigné » (RT2). */
export function typeEnClair(type) {
  return type ? `pépinière ${type}` : 'type non renseigné'
}

/** « 2,5 m² » — `null` sans superficie. */
export function superficieEnClair(m2) {
  if (m2 == null || m2 === '' || Number.isNaN(Number(m2))) return null
  return `${String(Math.round(Number(m2) * 10) / 10).replace('.', ',')} m²`
}

/**
 * [CA3] La pastille d'une pépinière unique : « SERRE · 2,5 m² · pépinière chaude ».
 * `null` dès qu'il y en a zéro ou plusieurs. Le type absent est dit tel quel (RT2).
 */
export function pastillePepiniere(pepinieres) {
  if (!Array.isArray(pepinieres) || pepinieres.length !== 1) return null
  const p = pepinieres[0]
  return [String(p.nom ?? '').toUpperCase(), superficieEnClair(p.superficie_m2), typeEnClair(p.type_pepiniere)]
    .filter(Boolean).join(' · ')
}

/**
 * [CA3] La pépinière choisie : par identifiant (sélecteur) ou par nom (intention
 * du Plan, US-201 / I5). `null` si elle n'existe pas dans ce potager.
 */
export function pepiniereChoisie(parcours, filtre) {
  if (filtre == null || filtre === '') return null
  const lignes = parcours?.pepinieres ?? []
  return lignes.find((p) => String(p.id) === String(filtre))
    ?? lignes.find((p) => normaliser(p.nom) === normaliser(filtre))
    ?? null
}

/**
 * [CA8-CA10, CA17] Le kanban : une ligne par pépinière (vides comprises, dans
 * l'ordre rendu), puis « Sans emplacement » si elle n'est pas vide. Chaque ligne a
 * ses quatre cases ; dans une case, les étiquettes gardent l'ordre de l'API.
 * Le filtre ne garde que la ligne choisie.
 */
export function kanban(parcours, { filtre = null } = {}) {
  const etiquettes = parcours?.etiquettes ?? []
  const choisie = pepiniereChoisie(parcours, filtre)
  const casesDe = (emplacementId) => Object.fromEntries(STADES.map((s) => [
    s.cle, etiquettes.filter((e) => e.stade === s.cle && (e.emplacement_id ?? null) === emplacementId),
  ]))
  const lignes = (parcours?.pepinieres ?? [])
    .filter((p) => !choisie || p.id === choisie.id)
    .map((p) => ({ ...p, cle: `p${p.id}`, sansEmplacement: false, cases: casesDe(p.id) }))
  if (!choisie && parcours?.sans_emplacement) {
    lignes.push({
      ...parcours.sans_emplacement, id: null, cle: 'sans', nom: 'Sans emplacement',
      type_pepiniere: null, sansEmplacement: true, cases: casesDe(null),
    })
  }
  const colonnes = STADES.map((s) => {
    const siennes = lignes.flatMap((l) => l.cases[s.cle])
    return { ...s, total: siennes.length, alerte: siennes.some((e) => e.echeance?.en_retard) }
  })
  return { lignes, colonnes }
}

/** [CA9] « 10 m² · 4 lots · 4 étiquettes · 1 alerte ». */
export function resumeLigne(ligne) {
  return [
    superficieEnClair(ligne.superficie_m2),
    plur(ligne.nb_lots ?? 0, 'lot'),
    plur(ligne.nb_etiquettes ?? 0, 'étiquette'),
    ligne.nb_alertes ? plur(ligne.nb_alertes, 'alerte') : null,
  ].filter(Boolean).join(' · ')
}

/**
 * [CA9] Ce que dit une case vide : « vide », et pour « Prêt à sortir » le prochain
 * départ de la ligne quand l'API le connaît.
 */
export function caseVide(stade, ligne) {
  const p = ligne?.prochaine_sortie
  if (stade === 'pret' && p) {
    const numero = p.lot_numero != null ? ` #${p.lot_numero}` : ''
    return `Rien à sortir aujourd'hui. Prochain : ${majuscule(p.culture)}${numero}, le ${dateCourte(p.du).replace(/\.$/, '')}.`
  }
  return 'vide'
}

// ── [CA21] Téléphone : les onglets de stade ─────────────────────────────────

/** [CA21] L'onglet de stade ouvert par défaut : le premier en alerte, sinon le premier non vide. */
export function ongletStadeParDefaut(colonnes) {
  return (colonnes.find((c) => c.alerte) ?? colonnes.find((c) => c.total > 0) ?? colonnes[0] ?? STADES[0]).cle
}

// ── Les compteurs ───────────────────────────────────────────────────────────

const COMPTEURS = Object.freeze([
  { cle: 'a_repiquer', libelle: 'à repiquer', surligne: true },
  { cle: 'a_sortir', libelle: 'à sortir', surligne: true },
  { cle: 'endurcit', libelle: 'endurcit', surligne: true },
  { cle: 'a_semer', libelle: 'à semer', surligne: false },
  { cle: 'dormants', libelle: 'dormant', pluriel: 'dormants', surligne: false },
])

/** Les états d'étiquette qu'un compteur met en évidence — la même partition qu'US-240. */
export const ETATS_DU_COMPTEUR = Object.freeze({
  a_repiquer: ['repiquer_retard', 'a_repiquer'],
  a_sortir: ['sortir_retard', 'a_sortir', 'sortir_bientot'],
  endurcit: ['endurcir', 'endurcit_sur_place'],
})

/**
 * [CA4] Les compteurs de la barre, lus dans `parcours.compteurs`. Un compteur à
 * zéro reste à sa place, éteint (maquette HF) : on lit d'un coup d'œil qu'il n'y a
 * rien à faire. `alerte` : il contient un retard.
 */
export function compteursBarre(compteurs) {
  return COMPTEURS.map((c) => {
    const v = compteurs?.[c.cle] ?? { total: 0, retard: false }
    return {
      ...c, total: v.total ?? 0, alerte: Boolean(v.retard),
      texte: v.total > 1 && c.pluriel ? c.pluriel : c.libelle,
      actif: (v.total ?? 0) > 0,
    }
  })
}

/** [CA4] Un second appui sur le même compteur retire l'effet. */
export const basculerCompteur = (courant, cle) => (courant === cle ? null : cle)

/** [CA4] Une étiquette est-elle mise en évidence par le compteur actif ? `null` : aucun effet. */
export function miseEnEvidence(etiquette, compteur) {
  const etats = ETATS_DU_COMPTEUR[compteur]
  if (!etats) return null
  return etats.includes(etiquette?.etat)
}

// ── L'étiquette ─────────────────────────────────────────────────────────────

const JOUR = 86400000
const versJour = (iso) => {
  if (!iso) return null
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number)
  return y && m && d ? Date.UTC(y, m - 1, d) : null
}
/** Jours entiers de `a` à `b` (ISO), `null` si l'une manque. */
export function ecartJours(a, b) {
  const x = versJour(a)
  const y = versJour(b)
  return x == null || y == null ? null : Math.round((y - x) / JOUR)
}

const MOIS_COURTS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
/** « 2026-10-01 » → « 1er oct. ». */
export function dateCourte(iso) {
  const t = versJour(iso)
  if (t == null) return null
  const d = new Date(t)
  return `${d.getUTCDate() === 1 ? '1er' : d.getUTCDate()} ${MOIS_COURTS[d.getUTCMonth()]}`
}
/** « du 13 au 27 oct. », « du 20 nov. au 4 déc. ». */
export function periodeCourte(du, au) {
  if (!du) return null
  if (!au || au === du) return `le ${dateCourte(du)}`
  const [a, b] = [dateCourte(du), dateCourte(au)]
  const memeMois = String(du).slice(0, 7) === String(au).slice(0, 7)
  return `du ${memeMois ? a.split(' ')[0] : a} au ${b}`
}
const majuscule = (t) => (t ? `${String(t).charAt(0).toUpperCase()}${String(t).slice(1)}` : '')

/**
 * [CA12] L'en-tête d'état, en mot, et sa teinte (`ton`) :
 * `retard` (rouge), `levee` (sable), `godet` (vert), `bientot` (ambre),
 * `endurcir` (ciel), `pret` (blé), `inconnu` (gris, bord pointillé).
 */
export function enteteEtiquette(etiquette, lot = null) {
  const e = etiquette?.echeance ?? {}
  switch (etiquette?.etat) {
    case 'repiquer_retard': return { libelle: 'Repiquer — retard', ton: 'retard' }
    case 'a_repiquer': return { libelle: 'Repiquer', ton: 'levee' }
    case 'sortir_retard': return { libelle: 'Sortir — retard', ton: 'retard' }
    case 'a_sortir': return { libelle: 'Mettre en terre', ton: 'pret' }
    case 'sortir_bientot': return { libelle: 'Sortir bientôt', ton: 'bientot' }
    // « J3/7 » est le grand chiffre : l'en-tête ne le répète pas.
    case 'endurcir': return { libelle: 'Endurcir', ton: 'endurcir' }
    case 'endurcit_sur_place': return { libelle: 'S’endurcit sur place', ton: 'endurcir' }
    case 'levee_en_cours': return {
      libelle: lot?.levee_terminee ? 'Levée terminée' : 'Levée en cours', ton: 'levee',
    }
    case 'duree_inconnue': return { libelle: 'Durée ?', ton: 'inconnu' }
    default: return { libelle: 'En cours', ton: etiquette?.stade === 'levee' ? 'levee' : 'godet' }
  }
}

/**
 * [CA12] Le grand chiffre : « +6 j » (retard), « 8 j » (avant l'échéance),
 * « reste 8 j » (dans la fourchette de mise en terre), « J3/7 » (endurcissement),
 * « J62 » (délai non renseigné : les jours depuis le semis, « ? » sans date), ou `null` quand aucune échéance n'est attendue (A33).
 * `{ texte, avant, apres }` : `avant` et `apres` s'écrivent en petit.
 */
export function grandChiffre(etiquette, dateRef = null) {
  const e = etiquette?.echeance ?? {}
  if (e.en_retard && e.jours != null) return { texte: `+${e.jours} j` }
  switch (etiquette?.etat) {
    case 'duree_inconnue': {
      // Les jours écoulés depuis le semis sont un fait, pas une durée : ils ne manquent jamais.
      const jours = etiquette?.lot?.date_semis && dateRef ? ecartJours(etiquette.lot.date_semis, dateRef) : null
      return { texte: jours != null && jours >= 0 ? `J${jours}` : '?' }
    }
    case 'endurcir':
      return e.endurcissement ? { texte: `J${e.endurcissement.jour}`, apres: `/${e.endurcissement.sur}` } : null
    case 'a_sortir': {
      const reste = ecartJours(dateRef, e.au)
      return reste != null && reste >= 0 ? { avant: 'reste', texte: `${reste} j` } : { texte: 'J0' }
    }
    case 'a_repiquer': return { texte: 'J0' }
    default: return e.jours != null ? { texte: `${e.jours} j` } : null
  }
}

/** [CA12, P17] « 24 graines · 18 levées », « 12 godets · déplacés le 12 oct. », « quantité non dite ». */
export function quantitesEtiquette(etiquette) {
  const q = etiquette?.quantites ?? {}
  let principal
  let detail = []
  if (etiquette?.stade === 'levee') {
    if (q.graines) {
      principal = plur(q.graines, q.unite === 'plants' ? 'plant' : 'graine')
      if (q.leves != null) detail.push(plur(q.leves, 'levée'))
    } else if (q.leves) {
      principal = plur(q.leves, 'plant levé', 'plants levés')
    } else {
      principal = 'quantité non dite'
    }
  } else {
    principal = plur(q.godets ?? 0, 'godet')
  }
  if (etiquette?.mention) detail.push(etiquette.mention)
  return { principal, detail: detail.join(' · ') || null }
}

/**
 * [CA12, P19] La ligne de dates : « semé le 1er oct. · repiquage prévu du 11 au 13 oct. »,
 * « mise en terre du 2 au 16 nov. · endurcir dès le 26 oct. », ou la raison d'une
 * échéance manquante — jamais une date inventée (RT2).
 */
export function datesEtiquette(etiquette) {
  const e = etiquette?.echeance ?? {}
  const semis = etiquette?.lot?.date_semis
  if (etiquette?.etat === 'duree_inconnue') {
    return [semis ? `semé le ${dateCourte(semis)}` : null, e.raison ?? 'délai non renseigné'].filter(Boolean).join(' · ')
  }
  const morceaux = []
  if (etiquette?.stade === 'levee') {
    if (semis) morceaux.push(`semé le ${dateCourte(semis)}`)
    if (e.du) morceaux.push(`repiquage prévu ${periodeCourte(e.du, e.au)}`)
  } else {
    if (e.du) morceaux.push(`${etiquette.stade === 'pret' ? 'fourchette' : 'mise en terre'} ${periodeCourte(e.du, e.au)}`)
    if (e.libelle && etiquette.stade !== 'pret') morceaux.push(e.libelle)
    else if (semis && etiquette.stade === 'pret') morceaux.push(`semé le ${dateCourte(semis)}`)
    if (!e.du && e.raison) morceaux.push(e.raison)
  }
  return morceaux.join(' · ') || null
}

const pct = (x) => Math.max(0, Math.min(100, Math.round(x * 1000) / 10))

/**
 * [CA13] La règle de l'étiquette.
 * - `{ type: 'jours', ecoule, du, largeur, ref }` en pourcentages : la piste va du
 *   début de la règle à la fin de la fourchette (ou à la date de référence si elle
 *   la dépasse) ;
 * - `{ type: 'sept', jour, sur }` en endurcissement ;
 * - `null` sans fourchette (« Durée ? », graines restantes d'un lot repiqué).
 */
export function regleEtiquette(etiquette, dateRef) {
  const e = etiquette?.echeance ?? {}
  if (etiquette?.etat === 'endurcir' && e.endurcissement) {
    return { type: 'sept', jour: e.endurcissement.jour, sur: e.endurcissement.sur ?? 7 }
  }
  if (!e.debut_regle || !e.du || !e.au || !dateRef) return null
  const fin = Math.max(ecartJours(e.debut_regle, e.au), ecartJours(e.debut_regle, dateRef))
  if (!(fin > 0)) return null
  const ecoule = ecartJours(e.debut_regle, dateRef) / fin
  const du = ecartJours(e.debut_regle, e.du) / fin
  const au = ecartJours(e.debut_regle, e.au) / fin
  return { type: 'jours', ecoule: pct(ecoule), du: pct(du), largeur: Math.max(pct(au) - pct(du), 2), ref: pct(ecoule) }
}

/** « Tomate jaune · #4 » sans majuscule forcée sur la variété. */
export function nomEtiquette(etiquette) {
  const l = etiquette?.lot ?? {}
  return { culture: majuscule(l.culture), variete: l.variete ?? null, numero: l.numero != null ? `#${l.numero}` : null }
}

/** [CA12] « 1/2 » si le lot est coupé, `null` sinon. */
export function repereFragment(etiquette) {
  const f = etiquette?.fragment
  return f && f.total > 1 ? `${f.rang}/${f.total}` : null
}

/** [CA16] Les autres fragments du même lot. */
export function fragmentsLies(etiquettes, etiquette) {
  if (!etiquette || (etiquette.fragment?.total ?? 1) < 2) return []
  return (etiquettes ?? []).filter((e) => e.id !== etiquette.id && e.lot?.id === etiquette.lot?.id)
}

/** [CA16] « #23 · voir 2/2 › » (ou « ‹ » vers un fragment d'avant). */
export function lienFragment(etiquette, autre) {
  const numero = etiquette?.lot?.numero != null ? `#${etiquette.lot.numero} · ` : ''
  const fleche = (autre?.fragment?.rang ?? 0) > (etiquette?.fragment?.rang ?? 0) ? '›' : '‹'
  return `${numero}voir ${autre.fragment.rang}/${autre.fragment.total} ${fleche}`
}

/**
 * [CA22] Téléphone : le lien vers un fragment rangé dans un autre onglet de stade —
 * « 6 godets au châssis froid › », « 4 graines en levée › ».
 */
export function lienAutreOnglet(autre, pepinieres = []) {
  const lieu = (pepinieres ?? []).find((p) => p.id === autre?.emplacement_id)?.nom ?? 'sans emplacement'
  const stade = STADES.find((s) => s.cle === autre?.stade)?.libelle.toLowerCase() ?? ''
  return `${quantitesEtiquette(autre).principal} ${stade} · ${lieu} ›`
}

/**
 * [US-216 / CA19, amendement du 19/10/2026] Où se trouve chaque partie d'un lot coupé,
 * d'après les étiquettes d'US-240 : « 4 graines en levée · serre chaude », « 6 godets ·
 * châssis froid, s'endurcit sur place ». Vide pour un lot d'un seul tenant.
 */
export function fragmentsDuLot(parcours, lotId) {
  const siennes = (parcours?.etiquettes ?? []).filter((e) => e.lot?.id === lotId)
  if (siennes.length < 2) return []
  const nomDe = (id) => (parcours?.pepinieres ?? []).find((p) => p.id === id)?.nom ?? 'sans emplacement'
  return siennes.map((e) => {
    const quoi = quantitesEtiquette(e).principal
    const stade = e.stade === 'levee' ? ' en levée' : ''
    const etat = e.etat === 'endurcit_sur_place' ? ', s’endurcit sur place' : e.etat === 'endurcir' ? ', en endurcissement' : e.stade === 'pret' ? ', prêts à sortir' : ''
    return `${quoi}${stade} · ${nomDe(e.emplacement_id)}${etat}`
  })
}

/** [CA24] « Lot 23, tomate cerise, fragment 1 sur 2, en levée, 4 graines ». */
export function nomAccessible(etiquette) {
  const l = etiquette?.lot ?? {}
  const f = etiquette?.fragment
  return [
    l.numero != null ? `Lot ${l.numero}` : 'Lot sans numéro',
    [l.culture, l.variete].filter(Boolean).join(' '),
    f && f.total > 1 ? `fragment ${f.rang} sur ${f.total}` : null,
    libelleStade(etiquette?.stade),
    quantitesEtiquette(etiquette).principal,
    enteteEtiquette(etiquette).libelle,
  ].filter(Boolean).join(', ')
}

/**
 * [CA15] La phrase à dicter pour renseigner le délai manquant (US-213) :
 * semis → godet sur une étiquette en levée, semis → mise en place sur les godets.
 */
export function phraseDuree(etiquette) {
  if (etiquette?.etat !== 'duree_inconnue') return null
  const culture = String(etiquette.lot?.culture ?? '').toLowerCase()
  const etape = etiquette.stade === 'levee' ? 'semis-godet' : 'repiquage'
  return `/calendrier duree ${culture} ${etape} 10-15`
}

/** [CA15] Ce que dit la phrase, en clair, sous la commande. */
export function aideDuree(etiquette) {
  const de = deLaCulture(etiquette?.lot?.culture)
  return etiquette?.stade === 'levee'
    ? `Le délai entre le semis et le godet ${de}, en jours (remplacez 10-15).`
    : `Le délai entre le semis et la mise en terre ${de}, en jours (remplacez 10-15).`
}

// ── Les gestes ──────────────────────────────────────────────────────────────

/**
 * [CA14] Les gestes d'une étiquette : ceux de la fiche du lot (`gestesDuLot`,
 * même règle, action suggérée en premier) que CE fragment peut porter, deux au plus.
 * - en levée : *Repiquer*, *Noter la levée* — *Noter la levée (terminée)* sur les
 *   graines restantes d'un lot déjà repiqué (A33) ;
 * - avec des godets : *Mettre en terre* ;
 * - sans emplacement : *Ranger dans…* (un déplacement, destination demandée).
 */
export function gestesEtiquette(etiquette, lot, opts = {}) {
  if (!etiquette || !lot) return []
  const tous = gestesDuLot(lot, opts)
  const garde = etiquette.stade === 'levee' ? ['repiquer', 'noter_levee'] : ['mettre_en_terre']
  const choisis = tous
    .filter((g) => garde.includes(g.code))
    .map((g) => {
      if (g.code === 'repiquer') {
        const leves = etiquette.quantites?.leves
        return { ...g, libelle: leves && lot.levee_terminee ? `Repiquer les ${leves}` : 'Repiquer' }
      }
      if (g.code === 'noter_levee' && etiquette.soldable_par_levee_terminee) {
        return { ...g, libelle: 'Noter la levée (terminée)' }
      }
      if (g.code === 'mettre_en_terre') {
        return { ...g, quantite: etiquette.quantites?.godets ?? g.quantite, disponibleDuLot: etiquette.quantites?.godets ?? g.disponibleDuLot }
      }
      return g
    })
  // [A33] Les graines restantes d'un lot repiqué : la levée à solder passe devant.
  if (etiquette.soldable_par_levee_terminee) {
    choisis.sort((a, b) => (b.code === 'noter_levee') - (a.code === 'noter_levee'))
  }
  if (etiquette.emplacement_id == null) {
    const base = tous[0] ?? { lotId: lot.semis_id ?? null, numeroLot: lot.numero_lot ?? null, culture: lot.culture, variete: lot.variete ?? null }
    choisis.push({
      lotId: base.lotId, numeroLot: base.numeroLot, culture: base.culture, variete: base.variete,
      code: 'ranger', libelle: 'Ranger dans…', action: 'deplacement', quantite: null, unite: null, principal: false,
    })
  }
  return choisis.slice(0, 2).map((g, i) => ({
    ...g,
    principal: i === 0 && (g.principal || etiquette.echeance?.en_retard || etiquette.stade === 'pret'),
    ouvreFiche: g.code === 'noter_levee',
    ariaLabel: `${g.libelle.replace('…', '')} le lot ${lot.numero_lot ?? String(lot.culture ?? '').toLowerCase()}`.replace('  ', ' '),
  }))
}

/** [CA10] Tant qu'US-241 ne range pas sans destination : la phrase à dire au compagnon. */
export function phraseRanger(etiquette) {
  const n = etiquette?.lot?.numero
  return n != null ? `le lot ${n} est dans la serre` : `le lot de ${String(etiquette?.lot?.culture ?? '').toLowerCase()} est dans la serre`
}

/**
 * [US-217] « Où les mettre », sur une étiquette prête à sortir : deux suggestions au
 * plus, et ce qui manque de places quand l'API le sait.
 */
export function ouMettreEtiquette(lot, etiquette) {
  if (etiquette?.stade !== 'pret') return null
  const s = lot?.ou_mettre?.suggestions ?? []
  if (!s.length) return null
  const godets = etiquette.quantites?.godets ?? 0
  const places = s.reduce((t, x) => t + (x.places_libres ?? 0), 0)
  return {
    lignes: s.slice(0, 2).map((x) => ({
      parcelle: x.parcelle, detail: [placeEnClair(x, null), x.exposition?.parcelle ?? null].filter(Boolean).join(' · '),
    })),
    manque: places > 0 && places < godets ? `${places} places libres pour ${godets} godets` : null,
  }
}

// ── La bande « Le bon moment pour semer » ───────────────────────────────────

/**
 * [CA5-CA7] Ce que montre la bande : les tuiles des cultures à semer (graines en
 * stock), la phrase des cultures repliées sans graines, et — quand il n'y a rien —
 * le calendrier des six mois qui viennent (`calendrier_semis`). `null` : rien à dire.
 */
export function bandeSemer(parcours) {
  const tuiles = (parcours?.a_semer ?? []).map((c) => ({
    culture: c.culture, nom: majuscule(c.culture),
    reste: c.jours_restants != null ? `reste ${c.jours_restants} j` : null,
    part: c.part_ecoulee != null ? Math.round(c.part_ecoulee * 100) : null,
    fenetre: c.periode ? `fenêtre ${c.periode}` : c.fenetre ? `fenêtre ${c.fenetre}` : null,
    varietes: c.varietes_en_stock ?? [],
    niveaux: niveauxParPepiniere(c),   // [US-220 / CA8]
  }))
  const replies = (parcours?.a_semer_sans_graines ?? []).map((c) => c.culture)
  const calendrier = parcours?.calendrier_semis ?? null
  if (!tuiles.length && !replies.length && !calendrier?.mois?.length) return null
  return { tuiles, replies, calendrier: tuiles.length || replies.length ? null : calendrier }
}

/** [CA7] « Aussi dans leur fenêtre, sans graines en stock : mâche, oignon blanc ». */
export function phraseReplies(replies) {
  return replies?.length ? `Aussi dans leur fenêtre, sans graines en stock : ${replies.join(', ')}` : null
}

/** [CA6] Le semis pré-rempli d'une tuile : la variété seulement si une seule est en stock. */
export function gesteSemer(tuile) {
  return {
    action: 'semis', culture: tuile.culture, contexteSemis: 'pepiniere',
    variete: tuile.varietes.length === 1 ? tuile.varietes[0] : null,
  }
}

/** Le mois où rien ne s'ouvre ; « aujourd'hui », « dans 105 j ». */
export function enteteMois(m) {
  return { libelle: m.libelle, repere: m.dans_jours ? `dans ${m.dans_jours} j` : 'aujourd’hui' }
}

/** « Prochaine ouverture le 1er février » — `null` si rien ne s'ouvre dans les six mois. */
export function phraseProchaineOuverture(calendrier) {
  const p = calendrier?.prochaine_ouverture
  return p ? `Prochaine ouverture le ${dateEnClair(p.date)}.` : 'Aucune ouverture dans les six prochains mois.'
}

// ── Le tiroir des dormants ──────────────────────────────────────────────────

/** [CA19] « 5 graines non levées », « 10 godets · 20 graines ». */
export function resteDormant(d) {
  const r = d?.reste ?? {}
  return [
    r.godets ? plur(r.godets, 'godet') : null,
    r.graines ? `${plur(r.graines, r.unite === 'plants' ? 'plant' : 'graine')} non levée${r.graines > 1 ? 's' : ''}` : null,
  ].filter(Boolean).join(' · ') || 'rien de compté'
}

/**
 * [CA19, A37] Les gestes d'un dormant : *Mettre en terre* s'il a des godets, puis
 * *Clôturer* — tirés de la fiche du lot, deux au plus.
 */
export function gestesDormant(dormant, lot, opts = {}) {
  if (!lot) return []
  const tous = gestesDuLot(lot, opts)
  const garde = dormant?.a_des_godets ? ['mettre_en_terre', 'cloturer'] : ['cloturer']
  return garde.map((code) => tous.find((g) => g.code === code)).filter(Boolean)
    .map((g, i) => ({ ...g, principal: i === 0 && g.code === 'mettre_en_terre', ariaLabel: `${g.libelle} le lot ${lot.numero_lot ?? ''}`.trim() }))
}

// ── [US-218, maquette HF option B] La fiche en bandeau sous la rangée ───────

/** L'index (0 à 3) de la colonne d'une étiquette : la pointe du bandeau la désigne. */
export function indexColonne(etiquette) {
  return Math.max(0, STADES.findIndex((s) => s.cle === etiquette?.stade))
}

/** Les étiquettes d'un lot dans l'ordre du parcours (levée d'abord), telles que rendues. */
export function etiquettesDuLot(parcours, lotId) {
  return (parcours?.etiquettes ?? [])
    .filter((e) => e.lot?.id === lotId)
    .sort((a, b) => (a.fragment?.rang ?? 1) - (b.fragment?.rang ?? 1))
}

/**
 * L'étiquette à ouvrir pour un lot : celle demandée si elle est encore là, sinon la
 * première du lot ; `null` si le lot n'a pas d'étiquette (dormant, terminé) — la fiche
 * s'ouvre alors en fenêtre.
 */
export function etiquetteOuverte(parcours, lotId, demandee = null) {
  const siennes = etiquettesDuLot(parcours, lotId)
  return siennes.find((e) => e.id === demandee) ?? siennes[0] ?? null
}

/** La ligne du kanban qui porte une étiquette — le bandeau s'ouvre dessous. */
export const cleLigneDe = (etiquette) => (etiquette?.emplacement_id == null ? 'sans' : `p${etiquette.emplacement_id}`)

/** « semé le 21 sept. · J28 · serre extérieure (type non renseigné) ». */
export function metaBandeau(lot, etiquette, pepinieres = [], dateRef = null) {
  const semis = lot?.date_semis ?? etiquette?.lot?.date_semis
  const jours = semis && dateRef ? ecartJours(semis, dateRef) : null
  const p = (pepinieres ?? []).find((x) => x.id === etiquette?.emplacement_id)
  const lieu = p ? `${p.nom} (${typeEnClair(p.type_pepiniere)})` : 'sans emplacement'
  return {
    semis: semis ? `semé le ${dateCourte(semis)}` : 'sans semis rattaché',
    jour: jours != null && jours >= 0 ? `J${jours}` : null,
    lieu,
  }
}

/** Un fragment, en une ligne du bandeau : « 3 levés · levée terminée », « 15 godets · déplacés le 12 oct. ». */
export function ligneFragment(etiquette, lot = null) {
  const q = etiquette?.quantites ?? {}
  let nombre
  let texte
  if (etiquette?.stade === 'levee') {
    if (q.graines) { nombre = q.graines; texte = q.graines > 1 ? 'graines' : 'graine' }
    else if (q.leves) { nombre = q.leves; texte = q.leves > 1 ? 'levés' : 'levé' }
    else { nombre = '?'; texte = 'graines, quantité non dite' }
    if (lot?.levee_terminee) texte += ' · levée terminée'
  } else {
    nombre = q.godets ?? 0
    texte = nombre > 1 ? 'godets' : 'godet'
  }
  const etat = enteteEtiquette(etiquette, lot).libelle.toLowerCase()
  // La partie en levée d'un lot coupé ne répète pas ce que dit la ligne de ses godets.
  const coupe = (etiquette?.fragment?.total ?? 1) > 1
  const suite = etiquette?.stade === 'levee' ? (coupe ? null : etiquette?.mention ?? null) : (etiquette?.mention ?? etat)
  return { nombre, texte: suite ? `${texte} · ${suite}` : texte, rang: repereFragment(etiquette), stade: etiquette?.stade }
}

/**
 * Le bilan du lot, en nombres et en barre : semées, levés, en godet, en terre. La barre
 * dit la part des graines devenues godets ou plantées, celle encore en levée, et le reste.
 * Les nombres viennent du lot (US-061, US-212) ; rien n'est estimé.
 */
export function bilanLot(lot) {
  const semees = lot?.graines_semees ?? 0
  const godets = lot?.stock_residuel_godet ?? 0
  const terre = lot?.nb_plantes ?? 0
  const levee = lot?.graines_non_soldees ?? lot?.graines_en_germination ?? 0
  const base = Math.max(semees, godets + terre + levee, 1)
  const part = (n) => Math.round((n / base) * 100)
  return {
    nombres: [
      { cle: 'semees', valeur: semees || null, libelle: 'semées' },
      { cle: 'leves', valeur: lot?.nb_leves ?? null, libelle: 'levés' },
      { cle: 'godet', valeur: godets, libelle: 'en godet' },
      { cle: 'terre', valeur: terre, libelle: 'en terre' },
    ],
    barre: { godet: part(godets + terre), levee: part(levee), reste: Math.max(0, 100 - part(godets + terre) - part(levee)) },
  }
}
