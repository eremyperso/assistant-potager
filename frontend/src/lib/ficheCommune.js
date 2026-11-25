// [US-355 / CA1-CA3, CA7] La fiche commune : ce qu'elle montre et comment elle le dit. Sans React et sans
// lecture : le composant passe ce que `GET /plan/suivi`, `GET /historique` et `GET /cultures/{c}/fiche` ont
// servi. Aucune règle d'étape, de fenêtre ou de confiance n'est recalculée ici (CA9) : le serveur les dit.
//
// L'onglet Suivi reprend les mises en mots d'US-322 (`lib/suiviCulture.js`) ; ce fichier ajoute ce que la
// fiche commune est seule à porter : le carnet de la culture (récoltes, gestes et notes), l'emplacement quand
// la culture n'a pas encore de place, les phrases de l'onglet Référence.
import { jourEnLettres, nomCulture } from './planDessus.js'
import { symboleDeCulture } from './pictosCultures.js'
import { libelleAction } from './journal.js'
import { frise as friseSuivi, etapeCourante, enTete, bandeauAConfirmer, libelleNoter } from './suiviCulture.js'
import { ETAPE_TERMINEE } from './etapes.js'

export const ONGLET_SUIVI = 'suivi'
export const ONGLET_REFERENCE = 'reference'
export const ONGLETS = Object.freeze([
  Object.freeze({ id: ONGLET_SUIVI, label: 'Suivi' }),
  Object.freeze({ id: ONGLET_REFERENCE, label: 'Référence' }),
])

const nombre = (v) => String(Math.round(Number(v) * 10) / 10).replace('.', ',')
const norm = (s) => String(s ?? '').normalize('NFD').replace(/\p{Diacritic}/gu, '').trim().toLowerCase()

/** Une lecture que la fiche attend : le suivi, le carnet, la référence. */
export const ACTION_RECOLTE = 'recolte'
export const ACTION_NOTE = 'observation'
const ACTIONS_PERTE = Object.freeze(['perte', 'perte_godet'])

// ── En-tête, emplacement, étape courante (CA1) ──────────────────────────────────────────────────

/**
 * « 🥦 Chou de Bruxelles / Long Island · 10 plants » : l'en-tête quand le suivi est lu, sinon ce que
 * l'écran d'origine savait de la culture (`selection`).
 */
export function enteteDeFiche(suivi, selection) {
  if (suivi) return enTete(suivi)
  const c = selection?.culture || ''
  return {
    emoji: symboleDeCulture(c, selection?.variete || ''),
    titre: nomCulture(c, null),
    sousTitre: [selection?.variete, selection?.quantiteTexte].filter(Boolean).join(' · '),
  }
}

/**
 * L'emplacement : « Planche centrale · rang 3 » avec « Voir au plan → », ou, sans place, « Pas encore placé »
 * avec « Placer sur le plan → » (la ligne est alors en pointillé, CA1 / cas complémentaire).
 */
export function emplacementDeFiche(suivi, selection) {
  const parcelle = suivi?.parcelle ?? selection?.parcelle ?? null
  if (!parcelle) {
    return { place: false, texte: 'Pas encore placé', lien: 'Placer sur le plan →' }
  }
  const rangs = [...(suivi?.rangs ?? (selection?.rang ? [selection.rang] : []))].filter(Number.isInteger).sort((a, b) => a - b)
  let rang = ''
  if (rangs.length === 1) rang = `rang ${rangs[0]}`
  else if (rangs.length > 1) rang = `rangs ${rangs[0]} à ${rangs[rangs.length - 1]}`
  return {
    place: true,
    texte: [parcelle, rang].filter(Boolean).join(' · '),
    lien: suivi?.est_pepiniere ? 'Voir la pépinière →' : 'Voir au plan →',
    pepiniere: Boolean(suivi?.est_pepiniere),
  }
}

/**
 * L'étape courante en puce : « Levé · depuis le 20 octobre », ou, quand elle est due, l'état prévu en orange
 * (« Levée prévue aujourd'hui »). Sans étape : « Aucune étape notée ».
 */
export function etapeDeFiche(suivi) {
  const courante = etapeCourante(suivi)
  if (!courante) {
    return { aucune: true, texte: 'Aucune étape notée', precision: 'Gaston la déduira de votre première note' }
  }
  const due = Boolean(suivi?.etapes?.a_confirmer)
  const bandeau = due ? bandeauAConfirmer(suivi) : null
  return {
    aucune: false,
    cle: courante.cle,
    prevue: courante.prevue,
    due,
    texte: due && bandeau ? bandeau.replace(/\s*:\s*à confirmer en notant$/, '') : courante.texte,
  }
}

/** « Noter », « Noter la levée » quand l'étape est prévue (CA1). */
export const libelleDuBoutonNoter = (suivi) => libelleNoter(suivi, { compact: true })

// ── La frise des étapes (CA2) ───────────────────────────────────────────────────────────────────

/**
 * Les étapes de la frise verticale : réalisées avec leur date, la prévue hachurée avec « prévu », les
 * suivantes grisées et sans date (on ne promet pas une fin de culture).
 */
export function friseDeFiche(suivi) {
  const liste = friseSuivi(suivi)
  if (!liste) return null
  return liste.map((x) => ({ ...x, date: /^prévue/.test(x.date) ? 'prévu' : x.date }))
}

/** Une culture terminée dit « rang à libérer » dans son groupe ; la fiche, elle, garde sa frise grisée. */
export const estTerminee = (suivi) => suivi?.etapes?.etape === ETAPE_TERMINEE

// ── Le carnet de la culture (CA2) ───────────────────────────────────────────────────────────────

/** « 1,2 kg », « 3 pièces », « 40 graines » : la quantité d'un geste, comme le serveur la porte. */
function quantiteDeGeste(e) {
  const q = e.quantite ?? e.nb_plants_godets
  if (q == null || q === '') return ''
  const unite = e.unite || (e.nb_plants_godets != null && e.quantite == null ? 'godets' : '')
  return `${nombre(q)}${unite ? ` ${unite}` : ''}`
}

const lieuDe = (e) => [e.parcelle, e.rang ? `rang ${e.rang}` : ''].filter(Boolean).join(' · ')

/**
 * Une ligne du carnet : une note (en Kalam), une récolte (pastille, quantité, mot éventuel) ou un geste
 * (pictogramme de l'action, perte en rouge). `null` pour une note sans texte : il n'y a rien à lire.
 */
function ligneDeCarnet(e) {
  const date = jourEnLettres(e.date)
  const texte = String(e.commentaire ?? '').trim()
  const cle = `c-${e.id ?? `${e.date}-${e.type_action}`}`
  if (e.type_action === ACTION_NOTE) {
    return texte ? { cle, type: 'note', date, texte, lieu: lieuDe(e) } : null
  }
  if (e.type_action === ACTION_RECOLTE) {
    const q = quantiteDeGeste(e)
    return { cle, type: 'recolte', date, titre: q ? `Récolte · ${q}` : 'Récolte', texte, lieu: lieuDe(e) }
  }
  const q = quantiteDeGeste(e)
  const perte = ACTIONS_PERTE.includes(e.type_action)
  const titre = [libelleAction(e.type_action), perte && q ? q.replace(/ godets$/, '') : ''].filter(Boolean).join(' · ')
  return {
    cle, type: 'geste', action: e.type_action, date, titre, perte,
    detail: texte || String(e.traitement ?? '').trim() || (!perte ? q : ''),
    lieu: lieuDe(e),
  }
}

/**
 * Le carnet de la culture, du plus récent au plus ancien (l'ordre du serveur) : `GET /historique` filtré sur
 * la culture et, quand la fiche s'ouvre sur une variété, sur cette variété.
 */
export function carnetDeCulture(evenements, { variete = null } = {}) {
  const v = norm(variete)
  return (evenements || [])
    .filter((e) => !v || !e.variete || norm(e.variete) === v)
    .map(ligneDeCarnet)
    .filter(Boolean)
}

/** Le nombre de récoltes que dit le carnet (« 2,9 kg récoltés · 4 récoltes »). */
export function nombreDeRecoltes(evenements, { variete = null } = {}) {
  const v = norm(variete)
  return (evenements || [])
    .filter((e) => e.type_action === ACTION_RECOLTE && (!v || !e.variete || norm(e.variete) === v)).length
}

/** « 2,9 kg récoltés · 4 récoltes » ; rien pour une culture qui n'a jamais été récoltée. */
export function ligneDeRecolte(suivi, nb) {
  const r = suivi?.recolte
  if (!r || !r.quantite) return null
  const total = `${nombre(r.quantite)} ${r.unite} récoltés`
  return nb > 0 ? `${total} · ${nb} ${nb > 1 ? 'récoltes' : 'récolte'}` : total
}

// ── L'origine (CA2) ─────────────────────────────────────────────────────────────────────────────

/** « Pépinière · lot #18, semé le 2 juin », « Semis direct », « Achat · 3 têtes » : une seule phrase. */
export function phraseOrigine(o) {
  if (!o) return null
  return o.detail ? `${o.titre}${o.type === 'pepiniere' ? ',' : ' ·'} ${o.detail}` : o.titre
}

// ── L'onglet Référence (CA3) ────────────────────────────────────────────────────────────────────

/** L'espacement tel que la fiche de culture le porte, ou « non renseigné ». */
export const espacementDe = (fiche) => fiche?.espacement || null

/**
 * La rotation : la famille et son délai de retour, dits tels que le référentiel les porte
 * (« Brassicacées : pas de la même famille à cet endroit avant 4 ans »).
 */
export function rotationDe(fiche) {
  if (!fiche?.famille) return null
  const n = fiche.delai_retour_annees
  if (!n) return `${fiche.famille} : délai de retour non renseigné`
  return `${fiche.famille} : pas de la même famille à cet endroit avant ${n} an${n > 1 ? 's' : ''}`
}

/** Le cas où la composition de la fiche n'a pas pu être lue : le bandeau, et chaque section le dit à sa place. */
export const MESSAGE_LECTURE_INCOMPLETE =
  'La composition de la fiche n’a pas pu être lue. « Maintenant » et le calendrier restent affichés.'

// ── La fiche catalogue (CA7) ────────────────────────────────────────────────────────────────────

/**
 * La pilule et le bouton de la fiche catalogue : « Pas encore au potager » + **Ajouter à mon potager**, ou
 * « Au potager » + « Ouvrir la culture en place ». Ajouter n'écrit rien : il ouvre Gaston.
 */
export function etatDeCatalogue(ligne) {
  return ligne?.au_potager
    ? { pilule: 'Au potager', dans: true, bouton: 'Ouvrir la culture en place' }
    : { pilule: 'Pas encore au potager', dans: false, bouton: 'Ajouter à mon potager' }
}

/** La phrase que Gaston reçoit : il répond par une proposition à confirmer, rien n'est écrit avant. */
export const phraseAjouter = (nom, article) => `Ajouter ${article || nom.toLowerCase()} à mon potager`

// ── Retrouver la place d'une culture (Journal, Stocks, Tableau de bord) ────────────────────────────

/**
 * Une fiche ouverte depuis le Journal ou les Stocks sait la culture, pas toujours sa parcelle : on la cherche
 * dans `GET /plan` (parcelles de pleine terre, la variété et la parcelle quand elles sont connues). Rend
 * `{ parcelleId, parcelle, rang, variete }` ou `null` quand la culture n'a pas de place en ce moment.
 */
export function resoudreSelection(plan, selection) {
  const trouvee = chercherDansLePlan(plan, selection)
  // Un geste d'une parcelle qui ne porte plus la culture : la même culture ailleurs vaut mieux que « pas placée ».
  return trouvee ?? (selection?.parcelle ? chercherDansLePlan(plan, { ...selection, parcelle: null }) : null)
}

function chercherDansLePlan(plan, selection) {
  const culture = norm(selection?.culture)
  const variete = norm(selection?.variete)
  const parcelle = norm(selection?.parcelle)
  if (!culture) return null
  const trouvees = []
  for (const p of plan?.parcelles || []) {
    if (p.est_pepiniere) continue
    if (parcelle && norm(p.nom) !== parcelle) continue
    for (const c of p.cultures || []) {
      if (norm(c.culture) !== culture) continue
      if (variete && norm(c.variete) !== variete) continue
      const rangs = (c.numeros_rangs || []).filter(Number.isInteger)
      trouvees.push({ parcelleId: p.id, parcelle: p.nom, variete: c.variete || selection?.variete || null, rang: rangs.length ? Math.min(...rangs) : null })
    }
  }
  // Une culture en place à l'étape la plus avancée d'abord n'est pas une règle d'ici : la première du plan.
  return trouvees[0] ?? null
}
