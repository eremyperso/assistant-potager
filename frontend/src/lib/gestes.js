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
function jourLocal(d = new Date()) {
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

export function phraseADicter({ action, culture, contexteSemis: filiere, parcelle } = {}) {
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
