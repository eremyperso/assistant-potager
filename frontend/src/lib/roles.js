/**
 * Libellés et teintes des rôles sur un potager [US-047].
 *
 * Mutualisé entre le sélecteur de potager (US-054) et le menu Compte (US-055),
 * qui affichent tous deux le rôle de l'utilisateur : un seul endroit à corriger
 * si un rôle est renommé ou ajouté côté backend.
 */
export const ROLES = {
  owner: { label: 'Propriétaire', tint: 'brand' },
  editor: { label: 'Éditeur', tint: 'blue' },
  lecteur: { label: 'Lecture seule', tint: 'violet' },
}

/** Libellé lisible d'un rôle — retombe sur la valeur brute si le rôle est inconnu. */
export function libelleRole(role) {
  return ROLES[role]?.label ?? role ?? '—'
}

/** Teinte associée à un rôle, pour les pastilles `Badge`. */
export function teinteRole(role) {
  return ROLES[role]?.tint ?? 'brand'
}

/**
 * [US-085 / CA7] Un changement de rôle demande-t-il une confirmation explicite ?
 *
 * - `'promotion'` : nommer un propriétaire donne tous les droits (archiver,
 *   supprimer le potager, gérer les membres) — action rare, à relire avant de valider.
 * - `'retrogradation'` : un owner qui se rétrograde lui-même perd le pouvoir de
 *   défaire sa décision — le même geste à sens unique, vu de l'autre côté.
 * - `null` : correction de rôle courante (`lecteur` ↔ `editor`, ou rétrograder un
 *   autre membre), réversible d'un clic, appliquée sans détour.
 */
export function confirmationChangementRole({ ancienRole, nouveauRole, estMoi }) {
  if (!nouveauRole || nouveauRole === ancienRole) return null
  if (nouveauRole === 'owner') return 'promotion'
  if (ancienRole === 'owner' && estMoi) return 'retrogradation'
  return null
}
