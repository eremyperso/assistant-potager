// [US-061] Règles d'affichage d'un lot de pépinière.
// Isolées de la vue pour être vérifiables : le déroulé de référence du CA2 doit
// donner exactement les valeurs du tableau de l'US, dénominateur variable compris.

/** [CA11] Code couleur du taux de germination : vert ≥ 80 %, ambre 50–79 %, rouge en dessous. */
export function tauxTint(taux) {
  if (taux == null) return 'blue'
  if (taux >= 80) return 'brand'
  if (taux >= 50) return 'amber'
  return 'red'
}

/**
 * [CA2] Les quantités et les trois pourcentages d'un lot.
 *
 * Le dénominateur des barres Godet et Terre change de nature au cours de la vie
 * du lot : tant qu'il reste des graines à lever, il vaut le nombre de graines
 * semées ; une fois la germination close, il vaut le nombre de plants réellement
 * obtenus. Un lot sans semis rattaché n'a jamais eu de graines connues : il se
 * calcule d'emblée sur ses plants.
 *
 * [CA5] `germination` vaut `null` — la frise ne remplit alors rien — quand aucune
 * graine semée n'est connue, plutôt que d'afficher un 0 % trompeur.
 */
export function stades(lot) {
  const S = lot.graines_semees ?? 0
  const P = lot.plants_obtenus ?? 0
  const T = lot.nb_plantes ?? 0
  const G = lot.stock_residuel_godet ?? 0
  const V = lot.nb_vendus ?? 0
  const L = lot.nb_pertes_godet ?? 0

  const close = lot.sans_semis_rattache || lot.etat_germination === 'close'
  const D = close ? P : (S || P)
  const part = (n) => (D > 0 ? Math.round((n / D) * 100) : 0)

  return {
    S, P, T, G, V, L,
    germination: lot.sans_semis_rattache || S <= 0 ? null : Math.round((P / S) * 100),
    godet: part(G),
    terre: part(T),
  }
}

/**
 * Stade courant du lot, index de la frise à trois segments de la maquette :
 * 0 Germination, 1 Godet, 2 Terre.
 *
 * Un lot est « en germination » tant qu'aucun plant n'a été mis en godet, et
 * passe en « Terre » lorsqu'il n'a plus de godet disponible mais des plants en
 * place — c'est-à-dire quand il n'y a plus rien à repiquer.
 */
export function stadeCourant(lot, st = stades(lot)) {
  if (st.P === 0) return 0
  if (st.G === 0 && st.T > 0) return 2
  return 1
}

/**
 * Badge de germination de la maquette : un seul libellé, `Germination N %`,
 * coloré par le taux.
 *
 * La distinction « en cours » / « close » n'est plus rendue — un taux de
 * germination est un taux de germination, et le doubler d'un « Réussite N % »
 * pour la même valeur n'apprenait rien. Seules les deux situations où le taux
 * n'existe pas gardent un libellé propre.
 */
export function phaseGermination(lot, st = stades(lot)) {
  if (lot.sans_semis_rattache) {
    return {
      tint: 'violet',
      label: 'Germination inconnue',
      aide: "Aucun semis n'est rattaché à ce lot : son taux de germination ne peut pas être établi.",
    }
  }
  if (lot.etat_germination === 'indeterminee') {
    return {
      tint: 'amber',
      label: 'Germination indéterminée',
      aide: "Nombre de graines d'origine non déclaré sur au moins une mise en godet — le taux ne peut pas être établi.",
    }
  }
  const taux = st.germination ?? lot.taux_germination ?? 0
  return {
    tint: tauxTint(taux),
    label: `Germination ${taux} %`,
    aide: 'Part des graines semées ayant effectivement donné un plant.',
  }
}

/** Jours écoulés depuis le semis — `null` si le lot n'a pas de date de semis. */
export function joursDepuis(dateISO, aujourdhui = new Date()) {
  if (!dateISO) return null
  const d = new Date(`${dateISO}T00:00:00`)
  if (Number.isNaN(d.getTime())) return null
  return Math.max(0, Math.floor((aujourdhui - d) / 86400000))
}
