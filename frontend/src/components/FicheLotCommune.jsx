// [US-356 / CA11] La fiche du lot, au format de la fiche commune : une feuille sur mobile, le panneau
// droit sur ordinateur (c'est la page qui la pose, voir `Pepiniere.jsx`).
//
// « Lot #57 · Oignon blanc », variété · quantité, le stade en puce, l'emplacement et son type, l'alerte
// orange, **Noter** (Gaston sur ce lot) et **Voir au Parcours**, « Gestes datés » en frise, « Carnet du
// lot » en Kalam (la note du jardinier — seule chose écrite de sa main). Les fonctions de la fiche d'US-216
// (repiquer, mettre en terre, clôturer, ranger, déplacer, tracabilité) restent joignables par
// « Toutes les actions du lot », qui ouvre la fiche complète.
//
// Aucun calcul ici : stade, emplacement, alerte et gestes viennent de `lib/pepiniereSocle.js`.
import { Pencil, ListChecks, Map as IconeCarte } from 'lucide-react'
import { PuceEtape, PastilleEtape } from './ui/EtapeCulture.jsx'
import { NoteCarnet, IconeLot } from './ui'
import {
  stadeDuLot, libelleStadeLot, emplacementDuLot, quantiteDuLot, gestesDeLaFiche, TEXTE_ALERTE,
} from '../lib/pepiniereSocle.js'
import { etapeDuStade } from '../lib/etapes.js'
import { symboleDeCulture } from '../lib/pictosCultures.js'
import { dateCourte } from '../lib/parcours.js'

const majuscule = (t) => (t ? t[0].toUpperCase() + t.slice(1) : t)

export default function FicheLotCommune({
  lot, parcours, alerte = null, onNoter, onVoirParcours, onVoirLots = null, onglet = 'lots', onToutesLesActions, ecriture = true,
}) {
  // [US-358] Le lien suit l'onglet d'où l'on vient : depuis Parcours on va aux Lots, depuis Lots au Parcours.
  const versLots = onglet !== 'lots' && onVoirLots
  const stade = stadeDuLot(lot, parcours)
  const etape = etapeDuStade(stade)
  const lieu = emplacementDuLot(lot, parcours)
  const gestes = gestesDeLaFiche(lot)
  const titre = `Lot ${lot.numero_lot != null ? `#${lot.numero_lot}` : ''} · ${majuscule(lot.culture ?? '')}`.replace('Lot  ·', 'Lot ·')
  const sousTitre = [lot.variete, quantiteDuLot(lot, parcours)].filter(Boolean).join(' · ')

  return (
    <article className="@container/fiche flex min-h-0 flex-col gap-3 px-5 pb-6 pt-1" aria-label={titre}>
      <header className="flex items-center gap-3">
        <span aria-hidden="true" className="grid h-[52px] w-[52px] shrink-0 place-items-center rounded-[16px] bg-card-alt text-[28px]">
          {symboleDeCulture(lot.culture, lot.variete)}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-serif text-[21px] font-semibold leading-tight text-txt"><IconeLot size={18} className="mr-1.5 inline align-[-2px]" />{titre}</h2>
          {sousTitre && <p className="text-[13px] text-txt2">{sousTitre}</p>}
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-txt2">
        {etape ? <PuceEtape etape={etape} /> : <span>{libelleStadeLot(stade)}</span>}
        <span>{lieu.texte}</span>
      </div>

      {alerte && (
        <p role="status" className="rounded-[12px] bg-due-bg px-3 py-2 text-[13px] font-bold text-due-tx">
          {alerte.texte ?? TEXTE_ALERTE[alerte.code]?.(alerte.jours)}
        </p>
      )}

      <div className="flex gap-2">
        {ecriture && (
          <button
            type="button" onClick={onNoter}
            className="inline-flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-full bg-brand px-3.5 text-[13px] font-semibold text-white hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand dark:text-bg"
          >
            <Pencil size={15} aria-hidden="true" />Noter
          </button>
        )}
        <button
          type="button" onClick={versLots ? onVoirLots : onVoirParcours}
          className="inline-flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-full border-[1.5px] border-brand bg-card px-3.5 text-[13px] font-semibold text-brand-text hover:bg-brand-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
        >
          {versLots ? <IconeLot size={15} aria-hidden="true" /> : <IconeCarte size={15} aria-hidden="true" />}
          {versLots ? 'Voir dans Lots' : 'Voir au Parcours'}
        </button>
      </div>

      <section aria-label="Gestes datés">
        <h3 className="mb-1.5 text-[12px] font-bold uppercase tracking-[.05em] text-txt2">Gestes datés</h3>
        {gestes.length === 0 ? (
          <p className="text-[12.5px] text-txt3">Aucun geste daté pour ce lot.</p>
        ) : (
          <ol className="flex flex-col">
            {gestes.map((g, i) => (
              <li key={`${g.code}-${g.date}-${i}`} className="flex items-center gap-2.5 border-t border-border-soft py-2 first:border-t-0">
                <PastilleEtape etape={stade === 'terminee' ? 'terminee' : 'levee'} petite />
                <span className="min-w-0 flex-1 text-[13px] text-txt">
                  {g.titre}{g.detail && <small className="block text-[12px] text-txt2">{g.detail}</small>}
                </span>
                <time className="shrink-0 text-[12px] font-semibold text-txt2">{g.date}</time>
              </li>
            ))}
          </ol>
        )}
      </section>

      {lot.note && (
        <section aria-label="Carnet du lot">
          <h3 className="mb-1.5 text-[12px] font-bold uppercase tracking-[.05em] text-txt2">Carnet du lot</h3>
          <NoteCarnet texte={lot.note} date={lot.date_semis ? dateCourte(lot.date_semis) : undefined} />
        </section>
      )}

      <button
        type="button" onClick={onToutesLesActions}
        className="inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-xl border border-border bg-card px-3 text-[13px] font-semibold text-txt hover:border-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
      >
        <ListChecks size={15} aria-hidden="true" />Toutes les actions du lot
      </button>
    </article>
  )
}
