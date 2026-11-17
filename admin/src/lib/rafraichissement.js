// Rafraîchissement automatique de la vue du jour [US-311 / CA5].
import { estVueDuJour } from './periode.js'

export const INTERVALLE_MS = 60_000

/** Se rafraîchit seule : la vue du jour, onglet visible. Une période passée ne change pas. */
export const rafraichissementAutomatique = ({ periode, visibilite }) =>
  estVueDuJour(periode) && visibilite === 'visible'

/** « données de 14 h 32 » quand l'API est en panne et que l'on montre les dernières valeurs. */
export function mentionAge(misAJour, heureTexte) {
  return misAJour ? `données de ${heureTexte}` : 'aucune donnée'
}
