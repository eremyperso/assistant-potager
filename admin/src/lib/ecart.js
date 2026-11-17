// Écart d'un chiffre clé à la période précédente de même durée [US-311 / US-312 / CA1].
// Le jugement (favorable / défavorable) ne repose jamais sur la couleur seule : il a toujours un
// libellé, que la vue affiche avec une icône (brief §3).
import { nombre } from './format.js'

const MOINS = '−'
const PLUS = '+'
const ESPACE = ' '

/** Ce que veut dire une hausse : `mauvaise` (jetons d'entrée), `bonne` (taux de cache), `neutre` (volume). */
export const SENS = { MAUVAISE: 'mauvaise', BONNE: 'bonne', NEUTRE: 'neutre' }

function jugement(delta, sens) {
  if (delta === 0 || sens === SENS.NEUTRE) return 'neutre'
  const hausse = delta > 0
  return (hausse && sens === SENS.BONNE) || (!hausse && sens === SENS.MAUVAISE) ? 'favorable' : 'defavorable'
}

export const LIBELLE_JUGEMENT = { favorable: 'favorable', defavorable: 'défavorable', neutre: '', indisponible: '' }

/**
 * @param {number|null} actuel
 * @param {number|null} precedent
 * @param {{sens?: string, mode?: 'relatif'|'points', decimales?: number}} options  `points` : un taux, écart en points
 *   (`decimales` : combien de chiffres après la virgule pour les points, 0 par défaut — un taux de quota
 *   de 1,2 % qui passe à 1,9 % est un écart de 0,7 point, pas de 1)
 * @returns {{texte: string, jugement: string, libelle: string, delta: number|null}}
 */
export function ecart(actuel, precedent, { sens = SENS.NEUTRE, mode = 'relatif', decimales = 0 } = {}) {
  const indisponible = { texte: 'n/d', jugement: 'indisponible', libelle: '', delta: null }
  if (actuel === null || actuel === undefined || precedent === null || precedent === undefined) return indisponible

  if (mode === 'points') {
    const delta = (actuel - precedent) * 100
    const arrondi = Number(delta.toFixed(decimales))
    const j = jugement(arrondi, sens)
    const signe = arrondi > 0 ? PLUS : arrondi < 0 ? MOINS : ''
    return { texte: `${signe}${nombre(Math.abs(arrondi), decimales)}${ESPACE}point${Math.abs(arrondi) > 1 ? 's' : ''}`, jugement: j, libelle: LIBELLE_JUGEMENT[j], delta: arrondi }
  }

  if (precedent === 0) return actuel === 0 ? { texte: '0 %', jugement: 'neutre', libelle: '', delta: 0 } : indisponible
  const delta = (actuel - precedent) / precedent
  const arrondi = Number((delta * 100).toFixed(0))
  const j = jugement(arrondi, sens)
  const signe = arrondi > 0 ? PLUS : arrondi < 0 ? MOINS : ''
  return { texte: `${signe}${nombre(Math.abs(arrondi))}${ESPACE}%`, jugement: j, libelle: LIBELLE_JUGEMENT[j], delta: arrondi }
}
