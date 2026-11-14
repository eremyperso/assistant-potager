// [US-334 / M3, CA3] La dernière étape de l'assistant « Premier potager » : mettre en place le plan
// maintenant, ou plus tard. Plein écran comme l'activation du compagnon (US-091), jamais bloquant.
//
// « Maintenant » ouvre le Plan sur l'éditeur, qui reprend la superficie dite à l'assistant ; « Plus tard »
// ouvre le Plan, par zones, surmonté de l'encart. Sur un petit écran la mise en place se fait sur
// ordinateur : l'écran le dit et ne propose que d'entrer dans le potager.
import { Map as IconePlan } from 'lucide-react'
import LogoMark from './brand/LogoMark.jsx'
import { Btn } from './ui'
import { useMedia } from '../hooks/useMedia.js'
import { ADRESSE_PLAN, ADRESSE_PLAN_EDITEUR, DUREE_MISE_EN_PLACE, TEXTE_SUR_ORDINATEUR } from '../lib/miseEnPlace.js'

/** Les parcelles créées, dites à l'assistant : « Planche nord · 12 m² ». */
export function resumeParcelles(parcelles) {
  return (parcelles || []).map((p) => (p.surface ? `${p.nom} · ${p.surface} m²` : p.nom))
}

export default function ProposerMiseEnPlace({ parcelles = [], onChoisir = (adresse) => window.location.assign(adresse) }) {
  const ordinateur = useMedia('(min-width: 720px)')
  const lignes = resumeParcelles(parcelles)
  return (
    <div className="@container/plan h-dvh bg-bg flex flex-col overflow-y-auto" data-proposer-mise-en-place>
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-10">
        <div className="w-full max-w-[420px]">
          <div className="flex justify-center mb-6"><LogoMark /></div>
          <div className="text-center mb-6">
            <div className="w-14 h-14 rounded-2xl bg-brand-soft flex items-center justify-center mx-auto mb-4">
              <IconePlan size={26} className="text-brand" aria-hidden="true" />
            </div>
            <h1 className="font-serif text-[24px] @[380px]/plan:text-[26px] font-bold text-txt tracking-tight leading-[1.15]">
              Mettre en place le plan
            </h1>
            <p className="text-[13.5px] text-txt2 mt-2.5 leading-relaxed">
              Posez vos parcelles sur le terrain, indiquez le nord : le plan montre enfin où est quoi,
              à l’échelle. {ordinateur ? `Comptez ${DUREE_MISE_EN_PLACE}.` : TEXTE_SUR_ORDINATEUR}
            </p>
          </div>

          {lignes.length > 0 && (
            <ul aria-label="Parcelles à placer" className="mb-6 flex flex-col gap-1.5">
              {lignes.map((l) => (
                <li key={l} className="rounded-[10px] border border-dashed border-border px-3 py-2 text-[13px] text-txt">{l}</li>
              ))}
            </ul>
          )}

          <div className="flex flex-col gap-2">
            {ordinateur && (
              <Btn type="button" kind="primary" onClick={() => onChoisir(ADRESSE_PLAN_EDITEUR)}>
                Mettre en place le plan
              </Btn>
            )}
            <button type="button" onClick={() => onChoisir(ADRESSE_PLAN)}
              className="mx-auto mt-2 text-[12.5px] font-semibold text-txt3 hover:text-txt">
              {ordinateur ? 'Plus tard' : 'Entrer dans mon potager'}
            </button>
          </div>
          <p className="text-[11px] text-txt3 text-center mt-4 leading-relaxed">
            Tant que le plan n’est pas posé, le Plan reste affiché par zones, avec un rappel pour le mettre en place.
          </p>
        </div>
      </div>
    </div>
  )
}
