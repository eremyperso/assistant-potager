// [US-077] Préférence d'affichage des widgets du Tableau de bord — stockée
// côté client (localStorage), pas en base : c'est une préférence de
// présentation personnelle, pas une donnée métier partagée par le potager
// (décision assumée au cadrage de l'US, pas de synchronisation multi-appareil).
//
// [CA5] Catalogue déclaratif unique : enregistrer un futur widget réel (Lot D)
// se limite à ajouter une entrée ci-dessous, sans toucher à la modale
// (`ModalPersonnaliserDashboard.jsx`) ni à cette logique de stockage.
//
// `useSyncExternalStore` + état de module (au lieu d'un contexte React) :
// le bouton d'en-tête (`PageHeader.jsx`) et la vue `Dashboard.jsx` sont deux
// arbres React distincts qui doivent réagir au même changement sans lien de
// parenté entre eux — un contexte imposerait un provider commun pour un
// simple besoin de lecture/écriture partagée.
import { useCallback, useSyncExternalStore } from 'react'

const STORAGE_KEY = 'potager.dashboard.widgets'

export const WIDGETS_CATALOGUE = [
  { id: 'meteo', label: 'Météo' },
  { id: 'todo', label: 'À faire cette semaine' },
  { id: 'recoltes', label: 'Récoltes de la saison' },
  { id: 'journal', label: 'Dernières interventions' },
]

const IDS_CONNUS = WIDGETS_CATALOGUE.map((w) => w.id)
const DEFAUT = IDS_CONNUS

function lire() {
  try {
    const brut = localStorage.getItem(STORAGE_KEY)
    if (!brut) return DEFAUT
    const parsed = JSON.parse(brut)
    const filtres = Array.isArray(parsed) ? parsed.filter((id) => IDS_CONNUS.includes(id)) : []
    return filtres.length ? filtres : DEFAUT
  } catch {
    return DEFAUT
  }
}

let cache = lire()
const abonnes = new Set()

function ecrire(next) {
  cache = next
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch {}
  abonnes.forEach((cb) => cb())
}

function subscribe(cb) {
  abonnes.add(cb)
  return () => abonnes.delete(cb)
}

function getSnapshot() {
  return cache
}

export function useDashboardWidgets() {
  const visible = useSyncExternalStore(subscribe, getSnapshot)

  // [CA4] Décocher est refusé quand `id` est le dernier widget encore visible.
  const toggle = useCallback((id) => {
    const estVisible = cache.includes(id)
    if (estVisible && cache.length <= 1) return
    ecrire(estVisible ? cache.filter((w) => w !== id) : [...cache, id])
  }, [])

  return { visible, toggle }
}
