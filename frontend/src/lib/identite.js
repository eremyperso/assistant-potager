/**
 * Dérivation d'un nom affichable et d'initiales à partir d'un compte
 * (`nom` + `email`) [US-055]. Mutualisé entre `AccountMenu` (identité du
 * compte connecté) et `GestionMembres` (liste des membres) — les deux
 * affichent des comptes dont `nom` peut être vide (colonne facultative).
 */

/** « Jean Dupont » → « JD » ; à défaut, les deux premières lettres de l'e-mail. */
export function initiales(nom, email) {
  const source = (nom || '').trim()
  if (source) {
    const mots = source.split(/\s+/).slice(0, 2)
    return mots.map((m) => m[0]).join('').toUpperCase()
  }
  return (email || '?').slice(0, 2).toUpperCase()
}

/** Nom complet affiché : le nom renseigné, sinon la partie locale de l'e-mail. */
export function nomAffiche(nom, email) {
  if (nom?.trim()) return nom.trim()
  return email?.split('@')[0] || 'Compte'
}

/** Prénom seul — utilisé là où la place manque pour le nom complet. */
export function prenomAffiche(nom, email) {
  return nomAffiche(nom, email).split(/\s+/)[0]
}
