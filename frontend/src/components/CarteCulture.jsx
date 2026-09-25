// [US-205] La carte de l'écran Cultures — une par culture, au potager ou dans
// tout le référentiel. Aucune quantité (le rôle de Stocks) : nom, famille ou
// variétés, confiance du meilleur geste, frise conseillée de la zone, présence
// au potager et libellé de fenêtre. Toute la mise en forme vit dans
// `lib/cultures.js` (CA14) : ce composant assemble, il ne calcule rien.
import { useState } from 'react'
import { MonthStrip } from './ui/MonthStrip.jsx'
import { PastillePhase } from './ui/PastillePhase.jsx'
import { Etoiles } from './ui/RegleConfiance.jsx'
import {
  libelleFenetre, sousTitreCarte, presenceCarte, friseDeLigne, normaliser, nomAccessibleCarte,
} from '../lib/cultures.js'

/** [CA5, CA7] Pied gauche : phase + parcelles/lots, ou « pas au potager »/suggestion en pointillé. */
function Presence({ ligne, enSuggestion }) {
  const p = presenceCarte(ligne)
  if (p) {
    return (
      <span className="flex items-center gap-1.5 flex-wrap min-w-0">
        <PastillePhase ligne={{ phase: p.phase }} />
        <span className="text-[12px] text-txt2 whitespace-nowrap">· {p.texte}</span>
      </span>
    )
  }
  const suggestion = enSuggestion
  return (
    <span
      className={`inline-flex items-center text-[12px] font-semibold rounded-full px-2.5 py-[3px] whitespace-nowrap border border-dashed ${
        suggestion ? 'border-brand text-brand-text' : 'border-txt3 text-txt2'
      }`}
    >
      {suggestion ? 'suggestion — pas au potager' : 'pas au potager'}
    </span>
  )
}

/** [CA5] Confiance courte : étoiles + mot, ou tiret si le référentiel n'a pas d'évaluation. */
function ConfianceCourte({ ligne }) {
  return (
    <span className="flex items-center gap-1.5 shrink-0">
      <Etoiles etoiles={ligne.etoiles} taille={13} />
      <span className="text-[11.5px] font-semibold text-txt2">{ligne.confiance_equivalent}</span>
    </span>
  )
}

/**
 * [CA7] La mise en avant « suggestion — pas au potager » n'a de sens que dans
 * l'onglet « Au potager » (une culture suggérée s'y trouve en carte pointillée
 * parmi des cultures présentes) ; dans « Toutes », c'est une carte du
 * référentiel comme une autre — `enSuggestion` par défaut à `ligne.suggestion`,
 * mais l'écran le force à `false` hors de cet onglet.
 */
export function CarteCulture({ ligne, meteoDisponible = true, enSuggestion = ligne.suggestion, onOpen }) {
  const [aideOuverte, setAideOuverte] = useState(false)
  // [CA12] Confiance indisponible : la fenêtre reste dite, seule l'étoile disparaît.
  const fl = libelleFenetre(ligne)
  const sousTitre = sousTitreCarte(ligne)
  const aria = nomAccessibleCarte(ligne, { meteoDisponible })
  const frise = friseDeLigne(ligne)

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={aria}
      onClick={onOpen}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen() } }}
      className={`@container/carte-culture min-h-[44px] flex flex-col gap-[11px] rounded-[14px] px-[15px] pt-3.5 pb-3 cursor-pointer text-left transition-colors ${
        enSuggestion
          ? 'bg-transparent border border-dashed border-brand'
          : 'bg-card border border-border shadow-card hover:border-txt3/40'
      }`}
    >
      <div className="flex items-start gap-2.5">
        <div className="flex-1 min-w-0">
          <div className="font-serif text-[16.5px] font-semibold text-txt leading-tight truncate">{ligne.nom_culture}</div>
          {sousTitre && (
            <div className={`text-[12px] mt-0.5 truncate ${ligne.hors_referentiel ? 'text-txt2' : 'font-serif italic text-txt3'}`}>
              {sousTitre}
            </div>
          )}
        </div>
        {ligne.hors_referentiel ? null : !ligne.a_calendrier ? (
          <span className="text-[11.5px] font-semibold text-txt3 border border-dashed border-border rounded-md px-[7px] py-0.5 whitespace-nowrap">
            pas de calendrier
          </span>
        ) : ligne.etoiles && meteoDisponible ? (
          <ConfianceCourte ligne={ligne} />
        ) : (
          <span className="text-[13px] text-txt3" aria-hidden="true">—</span>
        )}
      </div>

      {ligne.hors_referentiel ? (
        <div className="text-[12px] text-txt3 bg-card-alt rounded-lg px-[10px] py-2 leading-[1.45]">
          Inconnue du référentiel : ni calendrier ni confiance.
        </div>
      ) : (
        <div className={ligne.a_calendrier ? '' : 'opacity-55'}>
          <MonthStrip {...frise} moisCourant={undefined} />
        </div>
      )}

      <div className="flex items-center justify-between gap-x-2.5 gap-y-1.5 flex-wrap mt-auto">
        <Presence ligne={ligne} enSuggestion={enSuggestion} />
        {fl ? (
          <span className={`text-[12px] ${fl.gras ? 'font-bold text-txt' : 'text-txt2'}`}>{fl.texte}</span>
        ) : !ligne.a_calendrier && !ligne.hors_referentiel ? (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setAideOuverte((v) => !v) }}
            aria-expanded={aideOuverte}
            className="text-[12px] font-semibold text-brand-text underline underline-offset-[3px]"
          >
            compléter
          </button>
        ) : null}
      </div>

      {aideOuverte && (
        <div onClick={(e) => e.stopPropagation()} className="text-[12px] text-txt2 bg-card-alt rounded-[9px] px-[11px] py-[9px] leading-[1.5] cursor-default">
          Aucune fenêtre n’est connue pour {ligne.nom_culture.toLowerCase()}. Dis au compagnon :{' '}
          <code className="font-mono text-[11.5px] text-txt bg-card rounded px-1.5 py-px">
            /calendrier fenetre {normaliser(ligne.nom_culture)} …
          </code>
        </div>
      )}
    </div>
  )
}

/** [CA12] Six cartes squelettes pendant le chargement — jamais des tirets qui se remplissent. */
export function CarteCultureSquelette() {
  const b = (w, h, mt = 0) => <div style={{ width: w, height: h, marginTop: mt }} className="rounded bg-card-alt" />
  return (
    <div aria-hidden="true" className="bg-card border border-border rounded-[14px] p-[15px] flex flex-col gap-2">
      {b('45%', 15)}
      {b('30%', 10, 7)}
      {b('100%', 9, 16)}
      <div className="flex items-center justify-between mt-4">
        {b('38%', 20)}
        {b('32%', 12)}
      </div>
    </div>
  )
}

export default CarteCulture
