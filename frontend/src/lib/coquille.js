// [US-353] La coquille commune : ce qui est partagé par chaque écran — la structure en bandes, la
// barre d'outils, le défilement, le panneau droit. Logique pure ; `App.jsx` et les composants de
// `components/` la dessinent.
//
// Cinq bandes, toujours dans cet ordre : en-tête de page, Mot de Gaston, barre d'outils, contenu
// (seule bande qui défile), fiche commune (panneau). Une bande sans contenu disparaît.
import { dateCourte } from './regleTemps.js'

/** Repli de l'en-tête (CA11) : au-delà de ce défilement (px)… */
export const SEUIL_REPLI_PX = 24
/** … et seulement si le contenu déborde de plus que cela : replier rend de la hauteur à la zone qui défile. */
export const DEBORD_MIN_REPLI_PX = 220
/** On ne déplie qu'une fois revenu en haut. */
export const SEUIL_DEPLI_PX = 2

/** Largeur du panneau droit sur ordinateur (CA12). */
export const LARGEUR_PANNEAU_PX = 400
/** Le bouton Noter de bureau se décale à gauche du panneau ouvert : largeur + marge (CA3). */
export const DECALAGE_NOTER_PX = LARGEUR_PANNEAU_PX + 28

/** Sous cette largeur de conteneur, Filtrer se réduit à son icône (CA8, container query). */
export const LARGEUR_FILTRER_COMPLET_PX = 520

/**
 * [CA11] L'en-tête replié (et le Mot de Gaston sur une ligne), avec hystérésis : replier change la
 * hauteur de la zone qui défile, un seuil unique ferait « sauter » l'écran. `debord` vaut
 * `scrollHeight - clientHeight`. Entre les deux seuils, l'état ne change jamais.
 */
export function etatReplie(scrollTop, debord, repliActuel) {
  if (repliActuel) return scrollTop > SEUIL_DEPLI_PX
  return scrollTop > SEUIL_REPLI_PX && debord > DEBORD_MIN_REPLI_PX
}

/**
 * [CA8] L'ordre FIXE de la barre d'outils : date, recherche, Filtrer, menu ⋯. Une vue peut retirer
 * la date ou Filtrer ; rien ne s'y ajoute et l'ordre ne change jamais.
 */
export const ORDRE_BARRE = Object.freeze(['date', 'recherche', 'filtre', 'menu'])

/**
 * Les vues SANS barre d'outils : le tableau de bord n'en a pas (maquette). Les vues non dessinées
 * (Statistiques) reçoivent la coquille avec la barre réduite à la date (CA13).
 */
const SANS_BARRE = Object.freeze(['bord'])

export const aUneBarre = (vue) => !SANS_BARRE.includes(vue)

/**
 * La barre effective d'une vue : ce qu'elle déclare, borné par l'ordre et les droits de la coquille.
 *  - `date` : présente sauf si la vue la retire (`date: false`) ;
 *  - `recherche` : `{ placeholder, valeur, onChange }` — absente tant que la vue n'en fournit pas ;
 *  - `filtre` : `{ nombre, onOuvrir }` — idem ;
 *  - `menu` : `{ exporterCsv, exporterJson, aide }` — idem.
 * Une vue sans barre rend `null`.
 */
export function barreEffective(vue, declaree = null) {
  if (!aUneBarre(vue)) return null
  const d = declaree ?? {}
  return {
    date: d.date !== false,
    recherche: d.recherche ?? null,
    filtre: d.filtre === false ? null : (d.filtre ?? null),
    menu: entreesMenu(d.menu).length ? d.menu : null,
  }
}

/** Les contrôles réellement présents, dans l'ordre fixe. */
export function controlesPresents(barre) {
  if (!barre) return []
  return ORDRE_BARRE.filter((c) => (c === 'date' ? barre.date : Boolean(barre[c])))
}

/**
 * [CA9] Les entrées du menu ⋯, dans l'ordre : Exporter en CSV, Exporter en JSON, un séparateur,
 * Aide de la vue. Chaque entrée n'apparaît que si la vue la fournit ; le séparateur n'existe que
 * s'il sépare quelque chose. « Pièces jointes » est supprimé pour l'instant (D10).
 */
export function entreesMenu(menu) {
  const m = menu ?? {}
  const exports = [
    m.exporterCsv && { id: 'csv', libelle: 'Exporter en CSV', action: m.exporterCsv },
    m.exporterJson && { id: 'json', libelle: 'Exporter en JSON', action: m.exporterJson },
  ].filter(Boolean)
  const aide = m.aide ? [{ id: 'aide', libelle: 'Aide de la vue', action: m.aide }] : []
  return [...exports, ...(exports.length && aide.length ? [{ id: 'separateur' }] : []), ...aide]
}

/**
 * [CA10] Le bouton date : « Aujourd'hui » sur le jour même ; sur un autre jour, il passe en ambre
 * avec la date courte (« 12 nov. »).
 */
export function boutonDate(dateRef) {
  return dateRef
    ? { libelle: dateCourte(dateRef), ambre: true }
    : { libelle: 'Aujourd’hui', ambre: false }
}

/**
 * [CA2] Ce que prend le bouton « Plus » de la barre basse quand la vue active est rangée dessous
 * (Cultures, Stocks, Journal) : son nom, son icône et la pastille. `null` sinon.
 */
export function entreePlus(navId, secondaires) {
  return (secondaires ?? []).find((n) => n.id === navId) ?? null
}

/** [CA3] Un seul occupant du panneau droit à la fois. */
export const OCCUPANTS_PANNEAU = Object.freeze(['gaston', 'fiche', 'catalogue', 'recoltes'])

export const estOccupantValide = (cle) => OCCUPANTS_PANNEAU.includes(cle)

/**
 * [CA12] Le panneau droit de bureau et la feuille montante du mobile : Gaston y est en plein écran
 * sur mobile, les autres occupants dans une feuille.
 */
export function formePanneau({ occupant, bureau }) {
  if (!occupant) return null
  if (bureau) return 'lateral'
  return occupant === 'gaston' ? 'plein-ecran' : 'feuille'
}

/**
 * [US-353 / CA12, US-358] Un seul occupant du panneau à la fois : le DERNIER ARRIVÉ reste, l'autre part.
 *  - Gaston s'ouvre alors qu'une fiche est ouverte (Noter depuis la fiche) → la fiche se ferme ;
 *  - une fiche s'ouvre alors que Gaston est ouvert → Gaston se ferme ;
 *  - les deux arrivent dans le même rendu → Gaston l'emporte (c'est le geste de l'utilisateur).
 * `maintenant` et `avant` : `{ gastonOuvert, occupant }`. Rend `'fiche'`, `'gaston'` ou `null`.
 */
export function occupantAFermer(maintenant, avant) {
  if (!maintenant.gastonOuvert || !maintenant.occupant) return null
  const gastonArrive = !avant.gastonOuvert
  const ficheArrive = maintenant.occupant !== avant.occupant
  if (ficheArrive && !gastonArrive) return 'gaston'
  return 'fiche'
}
