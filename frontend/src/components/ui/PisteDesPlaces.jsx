import { TraitRang } from './TraitRang.jsx'
import { symboleDeCulture, estTomateAnanas } from '../../lib/pictosCultures.js'
import {
  PISTE_LIBRE, PISTE_LIGNE, PISTE_PLACES, palettePhases, gabarit,
} from '../../lib/planVue.js'

/**
 * [P10, P11] Le pictogramme de cote — le MÊME symbole sur le rang (espacement
 * entre deux pieds) et dans l'en-tête de carte (longueur du rang), pour que le
 * jardinier relie l'un à l'autre d'un coup d'œil.
 */
export function IconeCote({ taille = 12, className = '' }) {
  return (
    <svg
      width={taille * 1.55} height={taille} viewBox="0 0 28 18" aria-hidden="true"
      fill="none" stroke="currentColor" strokeWidth="2.4"
      strokeLinecap="round" strokeLinejoin="round" className={className}
    >
      <path d="M2 2v14M26 2v14M6 9h16M9 6 6 9l3 3M19 6l3 3-3 3" />
    </svg>
  )
}

export function PictoCulture({ culture, variete = '', taille = 17 }) {
  return (
    <span
      aria-hidden="true"
      data-picto-culture={culture}
      style={{ width: taille, height: taille, fontSize: taille }}
      className="inline-flex shrink-0 items-center justify-center leading-none"
    >
      {estTomateAnanas(culture, variete) ? (
        <svg width={taille} height={taille} viewBox="0 0 24 24" aria-hidden="true" data-tomate-jaune="true">
          <path d="M12 7C5 3 1 9 2 15c1 5 5 7 10 7s9-2 10-7c1-6-3-12-10-8Z" fill="#F5C518" stroke="#D89C09" strokeWidth="0.8" />
          <path d="M5 12c0-2 2-3 4-3" fill="none" stroke="#FFE87A" strokeWidth="2" strokeLinecap="round" />
          <path d="m12 8-6-4 2 5-4 1 6 1 2-2 3 3 1-3 4-3-6 1 1-4-3 3Z" fill="#4B963C" />
          <path d="M12 8V3" stroke="#38762E" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      ) : symboleDeCulture(culture, variete)}
    </span>
  )
}

export function MarqueLibre({ taille = 12 }) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"
      aria-hidden="true" className="shrink-0 text-txt3">
      <path d="M12 21v-7.2M12 13.8c0-3.2 2.2-5.4 5.4-5.4 0 3.2-2.2 5.4-5.4 5.4zM12 13.8c0-2.8-1.9-4.7-4.7-4.7 0 2.8 1.9 4.7 4.7 4.7z" />
    </svg>
  )
}

function Repere({ taille, plein, culture, variete }) {
  return (
    <span
      aria-hidden="true"
      data-repere={plein ? 'plein' : 'creux'}
      className="inline-flex shrink-0 items-center justify-center"
      style={{ width: taille, height: taille }}
    >
      {plein ? <PictoCulture culture={culture} variete={variete} taille={taille} /> : <MarqueLibre taille={taille} />}
    </span>
  )
}

/**
 * La piste des places d'un rang [US-228 / P1 à P9].
 *
 * Un rail de largeur fixe, avec sept pictogrammes proportionnels. Aucun
 * repère ne vaut un nombre de plants ; la quantité écrite fait foi. Le fond
 * suit la proportion reçue du serveur, avec un plancher de lisibilité.
 *
 * ⚠️ **Purement décorative** (CA10) : `aria-hidden`, aucun texte. Tout ce
 * qu'elle montre est dit par le nom accessible de la ligne qui la porte.
 *
 * [P6, P8] Places non calculables ou semis en surface : la piste retombe sur
 * `TraitRang` — le trait d'US-200 n'est pas supprimé, il devient le **mode
 * dégradé** de la piste, et l'écran du premier jour reste celui d'US-200 (CA9).
 *
 * [CA4] `palette` et `taille` sont des paramètres, comme pour `TraitRang` :
 * l'onglet Parcelles (US-222) et l'onglet Rotation reprendront ce composant
 * sans second dessin.
 */
export function PisteDesPlaces({
  piste,
  culture = '',
  variete = '',
  phase = null,
  mode = undefined,
  longueur = 100,
  segments = 0,
  palette = palettePhases(),
  taille = 'normale',
}) {
  const g = gabarit(taille)

  // [P6, P8] Le mode dégradé : exactement le dessin d'US-200, sans place en creux.
  if (!piste || (piste.variante !== PISTE_PLACES && piste.variante !== PISTE_LIGNE
                 && piste.variante !== PISTE_LIBRE)) {
    return (
      <TraitRang
        mode={mode} longueur={longueur} segments={segments}
        phase={phase} palette={palette} taille={taille}
      />
    )
  }

  const libre = piste.variante === PISTE_LIBRE
  const fentes = Math.max(1, piste.fentes)

  return (
    <div
      aria-hidden="true"
      className={`relative w-full ${g.piste} rounded-full overflow-hidden ${
        // [P9] Un rang libre : pas de fond, une bordure pointillée — c'est de la
        // place, pas une culture.
        libre ? 'border border-dashed border-txt3/60' : 'bg-card-alt'
      }`}
    >
      {/* [P1, P3] Le remplissage s'arrête à la dernière place prise ; sous 8 %
          il resterait invisible, et le plancher de lisibilité le montre. */}
      {!libre && piste.remplissage > 0 && (
        <span
          className={`absolute inset-y-0 left-0 rounded-full ${palette.fond(phase)}`}
          style={{ width: `${piste.remplissage}%` }}
        />
      )}

      <span className={`absolute inset-0 flex items-center ${palette.encre(phase)}`}>
        {Array.from({ length: fentes }, (_, index) => (
          <span key={index} className="flex-1 flex items-center justify-center min-w-0">
            {(index < piste.pleines || piste.variante !== PISTE_LIGNE) && (
              <Repere taille={g.picto} plein={index < piste.pleines} culture={culture} variete={variete} />
            )}
          </span>
        ))}
      </span>

      {/* [P4] Le dépassement : la piste est pleine, « +N » se pose dessus. Rien
          n'est corrigé — la quantité déclarée reste écrite dans le libellé. */}
      {piste.exces > 0 && (
        <span className="absolute right-1 top-1/2 -translate-y-1/2 rounded-full bg-red-soft
                         px-1.5 text-[10px] font-bold leading-[14px] text-red">
          +{piste.exces}
        </span>
      )}
    </div>
  )
}

export default PisteDesPlaces
