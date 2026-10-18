// [US-196, US-224] Déposer un geste dans la file, le faire confirmer au compagnon.
//
// Les écrans des épics 9 à 12 LISENT. Leurs boutons d'action — « Enregistrer le
// semis » de la fiche calendrier, « ajouter une culture » d'un rang libre,
// « Repiquer », « Mettre en terre » — ouvrent le flux existant avec des champs
// pré-remplis ; ils n'écrivent pas eux-mêmes. Ce module et `BoutonGeste.jsx`
// sont le seul endroit où cette règle est implémentée : un écran ne fabrique
// jamais son propre appel à `POST /gestes/intentions`.
//
// ⚠️ Ne pas confondre avec `lib/intentions.js` (US-195), qui porte les
// **intentions de navigation** — ouvrir un écran depuis un autre en emportant
// son contexte. Ici, un geste est **déposé dans une file**, côté serveur, et
// c'est le compagnon Telegram qui le confirme — trois jours durant (US-224).

/**
 * [CA13] Le vocabulaire du moteur de confiance (US-178) → le geste
 * enregistrable, avec sa filière de semis (US-069).
 *
 * Le pendant côté bot est `commandes_confiance._geste_et_contexte`, et c'est
 * voulu : les deux vocabulaires existent déjà, aucun troisième nom d'action
 * n'est inventé ici. Une action absente de cette table n'est pas préparable.
 */
const GESTE_DE_ACTION = Object.freeze({
  semis_pepiniere: { action: 'semis', contexteSemis: 'pepiniere' },
  semis_pleine_terre: { action: 'semis', contexteSemis: 'pleine_terre' },
  plantation: { action: 'plantation', contexteSemis: null },
})

/** Le geste correspondant à une action de confiance, ou `null` si elle n'en a pas. */
export function gesteDeActionConfiance(action) {
  return GESTE_DE_ACTION[action] ?? null
}

/** `YYYY-MM-DD` d'une Date locale — jamais `toISOString()`, qui décale en UTC. */
export function jourLocal(d = new Date()) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/**
 * [US-224 / CA26] La date du geste : la date de référence si elle est passée ou
 * d'aujourd'hui, **aujourd'hui** si elle est à venir.
 *
 * Un écran se consulte volontiers en avant — « où en sera le plan dans trois
 * semaines ? ». Un geste, lui, dit ce que le jardinier vient de faire : il ne
 * se date jamais dans le futur. La règle est reprise côté serveur
 * (`intentions_geste.date_enregistrable`) en garde-fou ; ici, elle sert surtout
 * à ce que le bouton puisse le DIRE avant qu'on appuie.
 *
 * Renvoie `{ date, ramenee }` — `ramenee` est ce qui déclenche la mention.
 *
 * ⚠️ Depuis Plan et Stocks, `ramenee` est TOUJOURS faux, et ce n'est pas un
 * bug : `GET /plan` rend `date_ref_effective = min(date_ref, aujourd'hui)`, et
 * c'est cette date-là que ces écrans passent à la fiche. La règle y est donc
 * déjà tenue en amont. La mention reste vivante pour tout appelant qui
 * fournirait la date de référence BRUTE — vérifié le 21/09/2026 à l'écran.
 */
export function dateDuGeste(dateRef, aujourdhui = jourLocal()) {
  if (!dateRef || dateRef > aujourdhui) {
    return { date: aujourdhui, ramenee: Boolean(dateRef) && dateRef > aujourdhui }
  }
  return { date: dateRef, ramenee: false }
}

/** [US-224 / CA26] La mention portée sous le bouton quand la date a été ramenée au jour. */
export const MENTION_DATE_RAMENEE = 'enregistré à la date d’aujourd’hui'

/**
 * [CA9] La phrase équivalente à dicter, proposée à côté du bouton.
 *
 * Construite ici ET côté serveur (`intentions_geste.phrase_a_dicter`) : celle du
 * serveur fait foi — elle revient dans la réponse et remplace celle-ci dès que
 * l'intention est préparée. Celle-ci n'existe que pour que le bouton puisse
 * montrer la phrase AVANT d'appeler quoi que ce soit, sans aller-retour.
 *
 * Pas de date : la grammaire déterministe du bot présume « aujourd'hui » sans
 * ancrage, et c'est exactement ce que veut dire qui la dicte maintenant.
 */
const LIBELLE_FILIERE = Object.freeze({ pepiniere: 'pépinière', pleine_terre: 'pleine terre' })

/**
 * [US-216] Comment un geste de LOT se dit — miroir de `file_gestes._LIBELLE_DICTEE_LOT`.
 * Les noms d'action du serveur (`mise_en_godet`) ne sont pas des mots de jardinier.
 */
const LIBELLE_DICTEE_LOT = Object.freeze({
  plantation: 'plantation', mise_en_godet: 'mise en godet', perte_godet: 'perte godet', cloture_lot: 'cloture',
  levee: 'levée',   // [US-212]
})

export function phraseADicter({ action, culture, contexteSemis: filiere, parcelle, numeroLot, quantite } = {}) {
  // [US-212 / CA11] « levée du lot 128 » — le seul lot : la PWA ne dit ni le nombre de levés ni
  // « terminée », le bot les demande (miroir de `phrase_a_dicter`).
  if (action === 'levee' && numeroLot != null) return `levée du lot ${numeroLot}`
  // [US-216] « mise en godet 30 plants du lot 128 » — le lot cité porte sa culture.
  if (numeroLot != null && LIBELLE_DICTEE_LOT[action]) {
    const nb = action !== 'cloture_lot' && quantite != null ? ` ${Math.trunc(quantite)} plants` : ''
    // [US-217 / CA7] « Mettre en terre ici » nomme la parcelle choisie.
    const ici = action === 'plantation' && parcelle ? ` parcelle ${String(parcelle).toLowerCase()}` : ''
    return `${LIBELLE_DICTEE_LOT[action]}${nb} du lot ${numeroLot}${ici}`
  }
  const morceaux = [action]
  if (culture) morceaux.push(`de ${String(culture).toLowerCase()}`)
  if (action === 'semis' && LIBELLE_FILIERE[filiere]) morceaux.push(`en ${LIBELLE_FILIERE[filiere]}`)
  if (parcelle) morceaux.push(`parcelle ${String(parcelle).toLowerCase()}`)
  return morceaux.filter(Boolean).join(' ')
}

/**
 * [US-224 / CA24] Un membre en lecture seule ne voit aucun bouton d'action.
 *
 * Le serveur refuse de son côté (`require_role`) : l'écran cache, le
 * serveur interdit — jamais l'un sans l'autre. Un rôle inconnu (potager pas
 * encore chargé) ne donne pas le droit d'écrire.
 */
export function peutEnregistrer(role) {
  return role === 'owner' || role === 'editor'
}

/**
 * Le corps de `POST /gestes/intentions` à partir de ce qu'un écran connaît.
 * Tout est facultatif sauf l'action : ce qui manque, le bot le demandera dans
 * son flux habituel (la parcelle, la quantité) — il ne l'inventera pas.
 */
export function corpsIntention({ action, culture, variete, quantite, unite, parcelleId, rang, lotId, date, contexteSemis, ecran, potagerId } = {}) {
  return {
    action,
    culture: culture ?? null,
    variete: variete ?? null,
    quantite: quantite ?? null,
    unite: unite ?? null,
    parcelle_id: parcelleId ?? null,
    rang: rang ?? null,
    lot_id: lotId ?? null,
    date: date ?? null,
    contexte_semis: contexteSemis ?? null,
    ecran: ecran ?? null,
    potager_id: potagerId ?? null,
  }
}

// [INC-014] Aucun bouton de geste de lot n'empile sans limite. Miroir de
// `file_gestes._RESERVOIR_DU_GESTE` : la plantation et la perte piochent dans les mêmes
// godets, le repiquage dans les graines en germination ; déplacer et clôturer ne portent
// aucun nombre.
const RESERVOIR = Object.freeze({ plantation: 'godets', perte_godet: 'godets', mise_en_godet: 'graines' })
const DE_LOT = Object.freeze(['plantation', 'perte_godet', 'mise_en_godet', 'deplacement', 'cloture_lot', 'levee'])

const duLot = (enAttente, lotId) => (enAttente ?? []).filter((g) => g.lot_id === lotId)

/** Plants (ou graines) d'un lot déjà promis par les gestes en attente qui piochent dans `action`. */
export function plantsReserves(enAttente, lotId, action = 'plantation') {
  const reservoir = RESERVOIR[action]
  if (lotId == null || !reservoir) return 0
  return duLot(enAttente, lotId)
    .filter((g) => RESERVOIR[g.action] === reservoir)
    .reduce((somme, g) => somme + (Number(g.quantite) || 0), 0)
}

/**
 * [INC-014] Ce qu'un bouton de geste de lot peut déposer, ou `null` pour tout autre geste.
 *
 *  - `epuise` : le lot ne peut plus rien fournir, ou un geste identique SANS nombre attend
 *    déjà pour ce lot (le serveur refuserait le dépôt dans les deux cas) ;
 *  - `disponibles`, `reserves` : de quoi dire ce qu'il reste à répartir ;
 *  - `quantite` : le nombre à envoyer, jamais au-delà. Seule la plantation propose le reste
 *    d'elle-même ; une perte ou un repiquage sans nombre laisse le compagnon le demander.
 */
export function plafondGesteDeLot(geste, enAttente) {
  if (geste?.lotId == null || !DE_LOT.includes(geste.action)) return null
  const memes = duLot(enAttente, geste.lotId).filter((g) => g.action === geste.action)
  const sansNombre = memes.some((g) => g.quantite == null)
  const reserves = plantsReserves(enAttente, geste.lotId, geste.action)
  const borne = geste.disponibleDuLot != null ? Math.trunc(geste.disponibleDuLot) : null
  const disponibles = borne == null ? null : Math.max(0, borne - reserves)
  const voulue = geste.quantite != null ? Math.trunc(geste.quantite) : null
  const quantite = voulue != null
    ? (disponibles == null ? voulue : Math.min(voulue, disponibles))
    : (geste.action === 'plantation' ? disponibles : null)
  const doublon = memes.length > 0 && (geste.quantite == null || sansNombre)
  return {
    reserves, disponibles, quantite, doublon,
    epuise: doublon || (voulue != null && disponibles != null && disponibles <= 0),
  }
}
