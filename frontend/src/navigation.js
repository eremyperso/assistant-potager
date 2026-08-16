import {
  Home,
  LayoutGrid,
  Leaf,
  Sprout,
  Package,
  ScrollText,
  BarChart3,
  MapPin,
  Layers,
  Calendar,
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
    Icon: LayoutGrid,
    title: 'Plan des parcelles',
    sub: 'Vos espaces de culture, leur occupation et leur contenu',
    subnav: [
      { id: 'plan', label: 'Parcelles', icon: MapPin },
      { id: 'plan-vue', label: 'Vue plan', icon: Layers },
      { id: 'plan-rot', label: 'Rotation', icon: Calendar },
    ],
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
  plan: 'plan',
  'plan-vue': 'plan',
  'plan-rot': 'plan',
  cultures: 'cultures',
  pepiniere: 'pepiniere',
  stocks: 'stocks',
  journal: 'journal',
}

/** Vue affichée au démarrage [US-053 / CA4]. */
export const VUE_PAR_DEFAUT = 'bord'

/** Entrées visibles directement dans la barre d'onglets basse ; le reste passe sous « Plus ». */
export const NAV_MOBILE_VISIBLE = 4

export function navEntry(view) {
  return NAV.find((n) => n.id === NAV_OF[view]) ?? NAV[0]
}
