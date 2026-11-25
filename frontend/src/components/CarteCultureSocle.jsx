import { MapPin } from 'lucide-react'
import { CalendrierAnnee, PastilleEtape } from './ui'
import { moisDeFrise } from '../lib/calendrierAnnee.js'

const BASE = 'flex min-h-[44px] w-full flex-col gap-2.5 rounded-[14px] border border-border bg-card p-3.5 text-left shadow-card transition-colors hover:border-txt3/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand'

/** Les douze mois de l'espèce ; sans frise (espèce hors référentiel), la bande reste vide et atténuée. */
function Mois({ frise, moisCourant }) {
  if (!frise) return null
  return <CalendrierAnnee mois={moisDeFrise(frise)} frise={frise} moisCourant={moisCourant} />
}

/**
 * [US-355 / CA4] Une culture au potager : la pastille d'étape (orange quand elle est due), l'emoji, le nom, la
 * variété, l'état, les douze mois de l'espèce et l'emplacement. Une culture « à placer » n'a pas d'étape : une
 * pastille grise « pas encore placé » prend sa place. La carte ouvre la fiche commune.
 */
export function CarteAuPotager({ l, moisCourant, onOuvrir }) {
  const aPlacer = !l.etape
  return (
    <button
      type="button" onClick={onOuvrir} data-groupe={l.groupe}
      aria-label={`${l.titre}${l.variete ? ` ${l.variete}` : ''}, ${l.detail}, ${l.lieu} : ouvrir la fiche`}
      className={`${BASE} ${aPlacer ? 'border-dashed' : ''}`}
    >
      <span className="flex items-start gap-2.5">
        {aPlacer ? (
          <span role="img" aria-label="Aucune étape notée" className="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-[9px] bg-card-alt text-txt3">
            <MapPin size={16} aria-hidden="true" />
          </span>
        ) : (
          <PastilleEtape etape={l.etape} prevue={l.prevue} due={l.due} petite className="shrink-0" />
        )}
        <span className="min-w-0 flex-1">
          <b className="block truncate text-[14px] font-semibold text-txt">
            <span aria-hidden="true" className="mr-1.5">{l.emoji}</span>{l.titre}
            {l.variete && <span className="font-normal text-txt2"> · {l.variete}</span>}
          </b>
          <small className={`block truncate text-[12.5px] ${l.due ? 'font-semibold text-due-tx' : 'text-txt2'}`}>{l.detail}</small>
        </span>
      </span>
      <Mois frise={l.frise} moisCourant={moisCourant} />
      <span className="text-[12px] text-txt2">{l.lieu}</span>
    </button>
  )
}

/**
 * [US-355 / CA6] Une espèce du catalogue : l'emoji, le nom, le nombre de variétés et la famille, les douze mois, et la
 * prochaine fenêtre de semis — ou la parcelle quand la culture est déjà au potager. La carte ouvre la fiche catalogue.
 */
export function CarteCatalogue({ k, moisCourant, onOuvrir }) {
  const pied = k.auPotager
    ? `Au potager${k.lieux.length ? ` · ${k.lieux.join(', ')}` : ''}`
    : (k.fenetre?.texte || 'Aucune fenêtre connue pour votre zone')
  return (
    <button
      type="button" onClick={onOuvrir}
      aria-label={`${k.nom}, ${k.sousTitre}, ${pied} : ouvrir la fiche`}
      className={BASE}
    >
      <span className="flex items-start gap-2.5">
        <span aria-hidden="true" className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-[10px] bg-card-alt text-[20px]">{k.emoji}</span>
        <span className="min-w-0 flex-1">
          <b className="block truncate text-[14px] font-semibold text-txt">{k.nom}</b>
          <small className="block truncate text-[12.5px] text-txt2">{k.sousTitre}</small>
        </span>
        {k.auPotager && (
          <span className="shrink-0 rounded-full bg-brand-soft px-2.5 py-0.5 text-[11.5px] font-semibold text-brand-deep">Au potager</span>
        )}
      </span>
      <Mois frise={k.brut?.a_calendrier ? k.frise : null} moisCourant={moisCourant} />
      <span className={`text-[12px] ${k.fenetre?.gras && !k.auPotager ? 'font-bold text-txt' : 'text-txt2'}`}>{pied}</span>
    </button>
  )
}
