// [US-231 / R3] La teinte d'une famille botanique — **identité, jamais jugement**.
//
// Une famille garde la même couleur d'une parcelle à l'autre et d'une année à
// l'autre : c'est ce qui permet de voir une répétition d'un coup d'œil, avant
// d'avoir lu un seul nom. Cette teinte ne dit donc RIEN de bon ni de mauvais
// (RT4) — le jugement est porté par l'alerte, en teinte d'alerte, et par elle
// seule.
//
// Conséquence directe : la palette **exclut** l'ambre et le rouge du design
// system, qui signifient déjà « attention » et « refus » partout ailleurs dans
// l'application. Les huit teintes vivent dans `index.css`, déclinées clair et
// sombre, et sont lues ici par leur variable CSS : c'est le thème qui choisit
// la valeur, jamais ce module.
//
// La teinte se déduit du NOM normalisé de la famille, pas de son `famille_id` :
// un identifiant de base n'est stable qu'au sein d'une installation, alors que
// « Solanacées » est la même famille partout, y compris sur les pages de
// contrôle visuel qui ne portent aucun identifiant réel.

/** Nombre de teintes disponibles — voir `--fam-N-*` dans `index.css`. */
export const NB_TEINTES_FAMILLE = 8

/** [R7] Ce qui habille une famille inconnue : le neutre, jamais une teinte. */
export const TEINTE_FAMILLE_INCONNUE = Object.freeze({
  index: null,
  fond: 'var(--card-alt)',
  encre: 'var(--txt2)',
  bord: 'var(--border)',
})

/** Normalisation minimale : la casse et les espaces ne font pas deux familles. */
function cleFamille(nom) {
  return String(nom ?? '').trim().toLowerCase()
}

/**
 * Empreinte stable d'un nom de famille → un index de teinte.
 *
 * Volontairement simple et **déterministe** : la même chaîne rend le même index
 * à chaque exécution, dans le navigateur comme dans les tests. Deux familles
 * peuvent partager une teinte au-delà de huit familles la même année — c'est
 * assumé : la teinte aide la lecture, c'est le NOM qui identifie (R2).
 */
export function indexTeinteFamille(nom) {
  const cle = cleFamille(nom)
  if (!cle) return null
  let somme = 0
  for (let i = 0; i < cle.length; i++) {
    somme = (somme * 31 + cle.charCodeAt(i)) % 100000
  }
  return (somme % NB_TEINTES_FAMILLE) + 1
}

/**
 * [R3] La teinte d'une famille, prête à poser en `style` : fond doux, encre
 * contrastée, bord assorti. Les trois viennent de variables CSS — le mode
 * sombre les redéfinit, ce module n'en sait rien.
 *
 * `inconnue` (ou un nom vide) rend le neutre : une lacune n'a pas d'identité.
 */
export function teinteFamille(nom, { inconnue = false } = {}) {
  const index = inconnue ? null : indexTeinteFamille(nom)
  if (index == null) return TEINTE_FAMILLE_INCONNUE
  return {
    index,
    fond: `var(--fam-${index}-soft)`,
    encre: `var(--fam-${index}-txt)`,
    bord: `var(--fam-${index}-bord)`,
  }
}
