// [US-294] Logique pure de l'écran « Assistants connectés » : libellés, dates, regroupements.
// Aucune dépendance à React : testée par `assistants.test.js`.

/** [CA7] Le mode d'emploi d'US-295 (fiche de documentation) et la politique des éditeurs. */
export const AIDE_ASSISTANTS = {
  titre: 'Qu’est-ce que c’est ?',
  texte:
    'Un assistant IA (Claude, ChatGPT, Le Chat…) connecté à votre potager lit vos données pour vous répondre. ' +
    'Ces données suivent la politique de l’éditeur de l’assistant, pas la nôtre : vous pouvez couper l’accès à tout moment.',
}

export const LIBELLE_STATUT = { active: 'Active', revoquee: 'Révoquée', expiree: 'Expirée' }
export const LIBELLE_RESULTAT = { ok: 'ok', refus: 'refusé', erreur: 'erreur' }
export const TEINTE_RESULTAT = { ok: 'brand', refus: 'amber', erreur: 'red' }

const OUTILS = {
  lister_potagers: 'Lister les potagers',
  proposer_geste: 'Proposer un geste',
  proposer_correction: 'Proposer une correction',
  proposer_commande: 'Proposer une commande',
  confirmer_proposition: 'Confirmer une proposition',
  abandonner_proposition: 'Abandonner une proposition',
  ouvrir_dans_l_application: 'Ouvrir dans l’application',
}

/** Le libellé d'un outil MCP ; un outil inconnu garde son nom (jamais une chaîne vide). */
export function libelleOutil(nom) {
  return OUTILS[nom] || String(nom || '').replace(/_/g, ' ')
}

/** « 7 nov. 2026, 14:03 » ; une date absente se dit « jamais ». */
export function dateCourte(iso, locale = 'fr-FR') {
  if (!iso) return 'jamais'
  const d = new Date(iso.endsWith('Z') || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return 'jamais'
  return d.toLocaleString(locale, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/** « Les Mésanges, Le Verger » ; les potagers fermés aux assistants sont signalés. */
export function potagersDits(potagers = []) {
  if (!potagers.length) return 'aucun potager'
  return potagers.map((p) => (p.interdit ? `${p.nom} (interdit)` : p.nom)).join(', ')
}

/** Une connexion peut être révoquée tant qu'elle n'est pas déjà révoquée. */
export const revocable = (connexion) => connexion?.statut !== 'revoquee'

/** Actives d'abord (la plus récente en tête, ordre du serveur), puis révoquées / expirées. */
export function trierConnexions(connexions = []) {
  const rang = (c) => (c.statut === 'active' ? 0 : 1)
  return [...connexions].sort((a, b) => rang(a) - rang(b))
}

/** [CA3] Le lien vers le geste dans le Journal : le jour du geste, sinon rien. */
export function lienGeste(appel) {
  const date = appel?.geste?.date
  return date ? `/?vue=journal&date=${encodeURIComponent(date)}` : null
}

/** [CA4] Durées proposées pour un jeton personnel, en jours (le serveur accepte 1 à 365). */
export const DUREES_JETON = [
  { jours: 7, libelle: '7 jours' },
  { jours: 30, libelle: '30 jours' },
  { jours: 90, libelle: '90 jours' },
  { jours: 365, libelle: '1 an' },
]

/** [CA5] « Claude (lecture) » — ce qu'un membre a connecté, pour l'écran « Membres ». */
export function assistantsDits(assistants = []) {
  return assistants
    .map((a) => `${a.client} (${a.portee === 'ecriture' ? 'lecture + écriture' : 'lecture'})`)
    .join(', ')
}
