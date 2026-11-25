// [US-357] La carte « À enregistrer » : les propositions d'un même tour, ligne par ligne.
//
// Aucune règle de geste ici, et aucune écriture : ce fichier ne fait que PRÉSENTER les cartes que le
// serveur a déjà posées (`POST /compagnon/messages` → `propositions`) et ordonner leur confirmation
// par le chemin existant (`POST /compagnon/propositions/{id}/confirmer`, US-344). Chaque ligne
// reste une proposition (ou un item de proposition) du serveur ; « Confirmer » les confirme UNE PAR
// UNE, dans l'ordre, et s'arrête à la première qui échoue : ce qui est confirmé le reste, ce qui
// n'a pas été tenté attend un nouvel appui (une ligne « Rappel » ne part pas avant sa « Nouvelle
// culture »).
import { etatCarte } from './compagnon.js'
import { formaterDuree } from './voix.js'
import {
  ETAPE_SEMEE, ETAPE_LEVEE, ETAPE_EN_GODET, ETAPE_PLANTEE, ETAPE_EN_RECOLTE, ETAPE_TERMINEE,
} from './etapes.js'

export const TITRE_CARTE = 'À enregistrer'
export const TEXTE_NOTE_AU_CARNET = 'Note au carnet'
export const TEXTE_PHOTO_BIENTOT = 'Photo · bientôt'

/** L'étape de culture qu'écrit une action dite ; `null` quand l'action n'en fait pas franchir (arrosage…). */
const ETAPE_DE_ACTION = Object.freeze({
  semis: ETAPE_SEMEE,
  levee: ETAPE_LEVEE,
  mise_en_godet: ETAPE_EN_GODET,
  plantation: ETAPE_PLANTEE,
  repiquage: ETAPE_PLANTEE,
  recolte: ETAPE_EN_RECOLTE,
  fin_culture: ETAPE_TERMINEE,
})

const ACTIONS_NOTE = Object.freeze(['note', 'observation', 'commentaire'])

export const etapeDeAction = (action) => ETAPE_DE_ACTION[String(action ?? '').toLowerCase()] ?? null
export const estNote = (action) => ACTIONS_NOTE.includes(String(action ?? '').toLowerCase())

/** Un événement prévu (pas encore vu) se hachure, comme la pastille d'étape du socle. */
const estPrevu = (item) => item?.prevu === true || ['prevu', 'prevue'].includes(item?.statut)

const majuscule = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s)

const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']

/** « 2026-11-24 » → « aujourd'hui », « hier », « demain » ou « 5 nov. » ; tout autre texte reste tel quel. */
export function dateDite(brut, maintenant = new Date()) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(brut ?? ''))
  if (!m) return brut
  const jour = Date.UTC(+m[1], +m[2] - 1, +m[3])
  const aujourdhui = Date.UTC(maintenant.getFullYear(), maintenant.getMonth(), maintenant.getDate())
  const ecart = Math.round((jour - aujourdhui) / 864e5)
  if (ecart === 0) return 'aujourd’hui'
  if (ecart === -1) return 'hier'
  if (ecart === 1) return 'demain'
  return `${+m[3]} ${MOIS[+m[2] - 1]}`
}

/**
 * « levée · fève · rang 6 · 2026-11-24 » → { titre: 'Levée', reste: 'fève · rang 6 · aujourd'hui' }.
 * Le premier morceau est l'action dite (le serveur la place toujours en tête) ; les dates ISO se disent.
 */
export function decouperLigne(ligne, maintenant = new Date()) {
  const [premier, ...autres] = String(ligne ?? '').split(' · ')
  if (autres.length === 0) return { titre: '', reste: premier }
  return { titre: majuscule(premier), reste: autres.map((x) => dateDite(x, maintenant)).join(' · ') }
}

/** Le texte d'une citation tronquée à la maquette : « Les fèves pointent sur tout le rang… ». */
export function citer(texte, max = 44) {
  const t = String(texte ?? '').trim()
  if (!t) return ''
  return t.length > max ? `${t.slice(0, max).trimEnd()}…` : t
}

/**
 * Les lignes d'UNE carte. Un geste compris porte ses items (une ligne par item, avec l'étape que
 * l'action fait franchir) ; une commande ou un plan, ses lignes en clair, sans pastille.
 */
export function lignesDeCarte(carte, maintenant = new Date()) {
  if (!carte) return []
  const lignes = carte.lignes?.length ? carte.lignes : [carte.resume].filter(Boolean)
  const items = carte.items ?? []
  return lignes.map((texte, i) => {
    const item = items[i] ?? null
    const action = item?.action ?? null
    const note = estNote(action)
    const { titre, reste } = decouperLigne(texte, maintenant)
    return {
      cle: `${carte.id}-${i}`,
      carteId: carte.id,
      titre: note ? TEXTE_NOTE_AU_CARNET : titre,
      reste: note ? '' : reste,
      etape: note ? null : etapeDeAction(action),
      prevue: !note && estPrevu(item),
      note,
      citation: note ? citer(item?.commentaire ?? item?.texte ?? item?.note ?? reste) : '',
    }
  })
}

/** Les cartes d'un tour de parole à présenter ensemble : celles de la réponse, dans l'ordre reçu. */
export const cartesDuTour = (entree) => (entree?.cartes ?? []).filter(Boolean)

/** Ce que « Confirmer » doit confirmer : les cartes en attente ET confirmables ici. */
export const cartesAConfirmer = (cartes) => (cartes ?? []).filter((c) => {
  const etat = etatCarte(c)
  return !etat.finale && Boolean(c.confirmable)
})

/** « Corriger » reprend la phrase du premier geste : il n'y en a pas pour une commande ou un plan. */
export const carteACorriger = (cartes) => (cartes ?? []).find((c) => !etatCarte(c).finale && c.phrase) ?? null

/** La carte est-elle encore à régler (au moins une proposition en attente) ? */
export const carteEnAttente = (cartes) => (cartes ?? []).some((c) => !etatCarte(c).finale)

/** Une issue qui n'a rien écrit : le service a refusé, ou la proposition ne s'est pas confirmée. */
export const issueEnEchec = (issue) => Boolean(!issue || issue.erreur || (issue.carte && issue.carte.etat !== 'confirmee'))

/**
 * Confirme les cartes UNE PAR UNE, dans l'ordre, par `confirmer(carte)` (l'appel de l'API du
 * compagnon, fourni par l'écran) ; `parCarte(carte, issue | null, erreur | null)` est appelé après
 * chaque tentative pour que l'écran dise l'état de la ligne. S'arrête à la première qui échoue :
 * les lignes déjà confirmées le restent, les suivantes n'ont pas été tentées.
 *
 * @returns {{ confirmees: object[], echec: { carte: object, erreur: any } | null, restantes: object[] }}
 */
export async function confirmerEnSerie(cartes, confirmer, parCarte = () => {}) {
  const confirmees = []
  const liste = [...(cartes ?? [])]
  for (let i = 0; i < liste.length; i += 1) {
    const carte = liste[i]
    let issue = null
    try {
      issue = await confirmer(carte)
    } catch (erreur) {
      parCarte(carte, null, erreur)
      return { confirmees, echec: { carte, erreur }, restantes: liste.slice(i + 1) }
    }
    parCarte(carte, issue, null)
    if (issueEnEchec(issue)) {
      return { confirmees, echec: { carte, erreur: issue?.erreur ?? null }, restantes: liste.slice(i + 1) }
    }
    confirmees.push(carte)
  }
  return { confirmees, echec: null, restantes: [] }
}

// ── La méta de la bulle du jardinier : « 🎤 Dicté · 0:06 » ou « ✎ Écrit » ────────────────────────

/** « Dicté · 0:06 » (durée connue), « Dicté » (durée inconnue) ou « Écrit ». */
export function metaBulle({ dictee = false, dureeS = null } = {}) {
  if (!dictee) return 'Écrit'
  return Number.isFinite(dureeS) && dureeS > 0 ? `Dicté · ${formaterDuree(dureeS)}` : 'Dicté'
}

// ── L'origine d'un message, retenue d'une ouverture à l'autre ────────────────────────────────────
//
// Le serveur ne garde pas si une phrase a été dictée ou écrite : le fil relu (US-343) la montrerait
// toujours « Écrit ». L'écran retient donc, sur cet appareil, l'origine des dernières phrases
// envoyées (clé : le texte), pour que les messages déjà au fil gardent leur origine.

export const CLE_ORIGINES = 'potager_compagnon_origines'
export const MAX_ORIGINES = 60

const cleOrigine = (texte) => String(texte ?? '').trim().toLowerCase().replace(/\s+/g, ' ')

function lireOrigines(stockage) {
  try {
    const brut = JSON.parse(stockage?.getItem(CLE_ORIGINES) ?? '[]')
    return Array.isArray(brut) ? brut : []
  } catch {
    return []
  }
}

/** Retient « dictée en 6 s » d'une phrase ; ne retient rien pour une phrase écrite (c'est le défaut). */
export function retenirOrigine(stockage, texte, { dictee = false, dureeS = null } = {}) {
  if (!dictee) return
  const cle = cleOrigine(texte)
  if (!cle) return
  const liste = lireOrigines(stockage).filter((o) => o.cle !== cle)
  liste.push({ cle, dureeS: Number.isFinite(dureeS) ? Math.round(dureeS * 10) / 10 : null })
  try { stockage?.setItem(CLE_ORIGINES, JSON.stringify(liste.slice(-MAX_ORIGINES))) } catch { /* sans stockage : « Écrit » */ }
}

/** Ajoute `dictee` et `dureeS` aux bulles du jardinier d'un fil relu, d'après ce qui a été retenu. */
export function origineDesPhrases(fil, stockage) {
  const origines = lireOrigines(stockage)
  if (origines.length === 0) return fil
  return fil.map((e) => {
    if (e.role !== 'jardinier' || e.dictee) return e
    const trouvee = origines.find((o) => o.cle === cleOrigine(e.texte))
    return trouvee ? { ...e, dictee: true, dureeS: trouvee.dureeS } : e
  })
}
