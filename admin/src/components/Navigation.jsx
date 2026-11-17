import { BarChart3, Bell, Euro, ShieldCheck, Sprout, TrendingUp } from 'lucide-react'
import { VUES } from '../lib/navigation.js'

const ICONES = { consommation: BarChart3, cout: Euro, fiabilite: ShieldCheck, derives: TrendingUp, potagers: Sprout, seuils: Bell }

/** Pastille chiffrée sur « Seuils » quand des alertes sont ouvertes (maquette d'US-318) : le nombre
 *  et un libellé pour les lecteurs d'écran, jamais la couleur seule. */
function Pastille({ n, surFondBandeau }) {
  if (!n) return null
  return (
    <span aria-label={`${n} alerte${n > 1 ? 's' : ''} ouverte${n > 1 ? 's' : ''}`}
      className={`absolute grid h-[18px] min-w-[18px] place-items-center rounded-full bg-red px-[5px] text-[10.5px] font-extrabold text-white
        ${surFondBandeau ? 'right-0.5 top-0.5 shadow-[0_0_0_2px_var(--header-from)]' : '-right-1.5 -top-1 shadow-[0_0_0_2px_var(--surface)]'}`}>
      {n}
    </span>
  )
}

/** Navigation du bandeau, à partir de 900 px (`nav:`) — structure de page, donc breakpoint d'écran. */
export function NavigationBandeau({ vue, surChangement, alertesOuvertes = 0 }) {
  return (
    <nav aria-label="Vues" className="ml-2.5 hidden gap-1 nav:flex">
      {VUES.map((v) => {
        const Icone = ICONES[v.id]
        const actif = v.id === vue
        return (
          <button key={v.id} type="button" onClick={() => surChangement(v.id)} aria-current={actif ? 'page' : undefined}
            className={`relative flex items-center gap-1.5 whitespace-nowrap rounded-[10px] px-[11px] py-2 text-[13.5px] ${actif
              ? 'bg-header-glass font-bold text-header-txt' : 'font-medium text-header-dim hover:text-header-txt'}`}>
            <Icone size={16} aria-hidden="true" />
            {v.libelleLong}
            {v.id === 'seuils' ? <Pastille n={alertesOuvertes} surFondBandeau /> : null}
          </button>
        )
      })}
    </nav>
  )
}

/** Barre d'onglets basse, sous 900 px : six entrées courtes, pastille sur « Seuils ». */
export function BarreBasse({ vue, surChangement, alertesOuvertes = 0 }) {
  return (
    <nav aria-label="Vues"
      className="sticky bottom-0 z-20 flex border-t border-border bg-surface pb-[max(12px,var(--safe-bottom))] nav:hidden">
      {VUES.map((v) => {
        const Icone = ICONES[v.id]
        const actif = v.id === vue
        return (
          <button key={v.id} type="button" onClick={() => surChangement(v.id)} aria-label={v.libelle} aria-current={actif ? 'page' : undefined}
            className={`flex min-h-[56px] flex-1 flex-col items-center gap-[3px] pt-[9px] text-[10px] ${actif ? 'font-bold text-brand-text' : 'font-medium text-txt3'}`}>
            <span className="relative block">
              <Icone size={21} aria-hidden="true" className={actif ? 'text-brand' : ''} />
              {v.id === 'seuils' ? <Pastille n={alertesOuvertes} /> : null}
            </span>
            {v.court}
          </button>
        )
      })}
    </nav>
  )
}
