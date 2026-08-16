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
