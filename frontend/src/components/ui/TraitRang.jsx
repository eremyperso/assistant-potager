import { MODE_POQUET, MODE_SURFACE, MAX_SEGMENTS, palettePhases, gabarit } from '../../lib/planVue.js'

/**
 * Le trait d'un rang du Plan [US-200 / V3, V4, V5, V7].
 *
 * Quatre variantes, et c'est la **forme** qui porte le mode d'implantation :
 * trait plein (rang), trait tramé à 45° (semis en surface), trait segmenté
 * (poquets, douze segments au plus), trait pointillé (rang libre). La couleur
 * ne dit que la phase, et jamais seule — le mot est écrit par `RangPlan` (V16).
 *
 * ⚠️ **Purement décoratif** (CA10) : `aria-hidden`, aucun texte. Tout ce que le
 * trait montre est dit par le nom accessible de la ligne qui le porte.
 *
 * [CA4] `palette` et `taille` sont des paramètres : l'onglet Rotation reprendra
 * ce composant avec sa propre palette, l'onglet Parcelles (US-222) avec le
 * gabarit agrandi — sans qu'aucun des deux ait à le modifier.
 */
export function TraitRang({
  mode,
  longueur = 100,
  segments = 0,
  libre = false,
  phase = null,
  palette = palettePhases(),
  taille = 'normale',
  className = '',
}) {
  const g = gabarit(taille)

  // [V7] Rang libre : pointillé, aucune teinte de phase — c'est de la place,
  // pas une culture. Pleine longueur : la place libre n'a pas de quantité.
  if (libre) {
    return (
      <div
        aria-hidden="true"
        className={`${g.trait} w-full rounded-full border border-dashed border-txt3 ${className}`}
      />
    )
  }

  // [V4] Poquets : un segment par poquet, douze au plus — douze segments font
  // la largeur entière, un poquet seul en fait donc un douzième.
  if (mode === MODE_POQUET) {
    const n = Math.max(1, segments)
    return (
      <div aria-hidden="true" className={`${g.trait} w-full ${className}`}>
        {/* La longueur est celle des segments, pas l'inverse : chacun se partage
            équitablement la part occupée, quelle que soit la largeur de la
            colonne — un écart en pixels fixes les ferait disparaître dans la
            légende, qui est étroite. */}
        <span
          className="flex h-full gap-[2px]"
          style={{ width: `${(n / MAX_SEGMENTS) * 100}%` }}
        >
          {Array.from({ length: n }, (_, i) => (
            <span key={i} className={`block h-full flex-1 rounded-full ${palette.trait(phase)}`} />
          ))}
        </span>
      </div>
    )
  }

  // [V3] Rang et surface : la longueur est la part de la quantité dans le rang
  // le plus fourni de la parcelle, à unité égale. Le plafond est tenu par la lib.
  return (
    <div aria-hidden="true" className={`${g.trait} w-full ${className}`}>
      <span
        className={`block h-full rounded-full relative ${palette.trait(phase)} ${
          mode === MODE_SURFACE ? 'trame-surface' : ''
        }`}
        style={{ width: `${longueur}%` }}
      />
    </div>
  )
}

export default TraitRang
