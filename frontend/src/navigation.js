import {
  Home,
  Leaf,
  Sprout,
  Package,
  ScrollText,
  BarChart3,
  Layers,
} from 'lucide-react'

/**
 * Configuration de la navigation à deux niveaux [US-053].
 *
 * Niveau 1 — `NAV` : navigation principale (bandeau haut ≥ 900px, barre
 * d'onglets basse en dessous).
 * Niveau 2 — `subnav` : tuiles de sous-navigation affichées sous le titre de
 * page, uniquement pour les entrées qui en déclarent.
 *
 * `id` d'une entrée NAV = identifiant de la vue affichée par défaut pour cette
 * section ; les identifiants de sous-vues (`stats`, `plan-vue`…) sont rattachés
 * à leur section via `NAV_OF`.
 */

function dateDuJour() {
  return new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export const NAV = [
  {
    id: 'bord',
    label: 'Tableau de bord',
    shortLabel: 'Accueil',
    Icon: Home,
    title: 'Tableau de bord',
    sub: () => `Vue d'ensemble de votre potager, ${dateDuJour()}`,
    subnav: [
      { id: 'bord', label: "Vue d'ensemble", icon: Home },
      { id: 'stats', label: 'Statistiques', icon: BarChart3 },
    ],
  },
  {
    id: 'plan',
    label: 'Plan',
    shortLabel: 'Plan',
    Icon: Layers,
    title: 'Plan des parcelles',
    sub: 'Vos espaces de culture, leur occupation et leur contenu',
    // [US-330 / CA1] Plus de sous-navigation : les tuiles « Plan » et « Rotation · à venir » ont été
    // retirées pour gagner en hauteur. Le détail d'une parcelle s'ouvre dans le Plan, et les anciens
    // liens (vue `plan`) y sont redirigés (`VUES_REDIRIGEES`, lib/intentions.js).
    // `entree` : la vue d'ouverture de la section.
    entree: 'plan-vue',
  },
  {
    id: 'cultures',
    label: 'Cultures',
    shortLabel: 'Cultures',
    Icon: Leaf,
    title: 'Mes cultures',
    sub: 'Fiches, variétés et calendrier cultural de la saison',
  },
  {
    id: 'pepiniere',
    label: 'Pépinière',
    shortLabel: 'Pépinière',
    Icon: Sprout,
    title: 'Semis & pépinière',
    sub: 'Suivi des lots semés, de leur stade et des plants disponibles',
  },
  {
    id: 'stocks',
    label: 'Stocks',
    shortLabel: 'Stocks',
    Icon: Package,
    title: 'Stocks',
    sub: 'Toutes les cultures de la saison, regroupées par famille botanique',
  },
  {
    // [US-053 / CA5] Renommage « Historique » → « Journal » côté interface.
    id: 'journal',
    label: 'Journal',
    shortLabel: 'Journal',
    Icon: ScrollText,
    title: 'Journal du potager',
    sub: 'Historique de toutes vos interventions',
  },
]

/** Section de navigation principale à laquelle appartient une vue donnée. */
export const NAV_OF = {
  bord: 'bord',
  stats: 'bord',
  'plan-vue': 'plan',
  cultures: 'cultures',
  pepiniere: 'pepiniere',
  stocks: 'stocks',
  journal: 'journal',
}

/** Vue affichée au démarrage [US-053 / CA4]. */
export const VUE_PAR_DEFAUT = 'bord'

/**
 * [US-325] « Noter » n'est pas une section : c'est une ACTION, toujours active, qui ouvre Gaston
 * (US-324) avec la sélection courante pour contexte (US-323). Elle n'est jamais l'onglet courant.
 */
export const NOTER = Object.freeze({ id: 'noter', label: 'Noter, avec Gaston', shortLabel: 'Noter', action: true })

/**
 * [US-325 / CA1, arbitrage P1 du 13/11/2026] La barre basse mobile : Accueil, Plan, **Noter** au
 * centre, Pépinière, puis « Plus », qui ouvre Cultures, Stocks et Journal. La navigation de
 * bureau (`NAV`, bandeau haut) ne change pas (CA4).
 */
export const NAV_MOBILE = Object.freeze(['bord', 'plan', NOTER.id, 'pepiniere'])
export const NAV_MOBILE_PLUS = Object.freeze(['cultures', 'stocks', 'journal'])

/** Les entrées de la barre basse : `principales` (dont l'action Noter) et celles de « Plus ». */
export function barreBasse() {
  const section = (id) => NAV.find((n) => n.id === id)
  return {
    principales: NAV_MOBILE.map((id) => (id === NOTER.id ? NOTER : section(id))),
    secondaires: NAV_MOBILE_PLUS.map(section),
  }
}

export function navEntry(view) {
  return NAV.find((n) => n.id === NAV_OF[view]) ?? NAV[0]
}

/** Sous-onglets que l'on peut réellement ouvrir [US-223 / CA2]. */
export const sousOngletsActifs = (navId) =>
  (NAV.find((n) => n.id === navId)?.subnav ?? []).filter((t) => !t.disabled).map((t) => t.id)

/**
 * [US-223 / CA3, CA4] La vue qu'ouvre un appui sur une section de la navigation
 * principale : le dernier sous-onglet visité pendant la session s'il y en a un,
 * sinon l'entrée déclarée par la section, sinon son identifiant.
 *
 * `dernieres` : `{ [idSection]: idVue }`, tenu en mémoire de page par la coquille
 * — une nouvelle session repart donc toujours de l'entrée.
 */
export function vueDeSection(navId, dernieres = {}) {
  const section = NAV.find((n) => n.id === navId)
  if (!section) return VUE_PAR_DEFAUT
  const derniere = dernieres[navId]
  if (section.memoriser && derniere && sousOngletsActifs(navId).includes(derniere)) return derniere
  return section.entree ?? section.id
}
