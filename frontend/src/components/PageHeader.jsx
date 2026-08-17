import { useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { Btn, TileNav } from './ui'
import { navEntry } from '../navigation.js'
import ModalPersonnaliserDashboard from './ModalPersonnaliserDashboard.jsx'

/**
 * En-tête de page [US-053 / CA2, CA3] : titre, sous-titre descriptif, et
 * tuiles de sous-navigation pour les sections qui en déclarent.
 *
 * Les sections sans `subnav` (Cultures, Pépinière, Stocks, Journal)
 * n'affichent pas la zone de tuiles.
 */
export default function PageHeader({ view, onGo }) {
  const nav = navEntry(view)
  const sousTitre = typeof nav.sub === 'function' ? nav.sub() : nav.sub
  // [US-077 / CA1] `view` (pas `nav.id`) : la section "bord" couvre aussi
  // l'écran Statistiques (même `subnav`) — le bouton ne doit apparaître que
  // sur "Vue d'ensemble", pas sur "Statistiques".
  const [personnaliser, setPersonnaliser] = useState(false)

  return (
    <div className="bg-surface border-b border-border">
      <div className={`max-w-[1320px] mx-auto px-4 nav:px-6 pt-5 ${nav.subnav ? 'pb-3.5' : 'pb-5'}`}>
        <div className="flex items-center flex-wrap justify-between gap-3">
          <h1 className="font-serif text-[27px] font-bold text-txt tracking-tight leading-tight">
            {nav.title}
          </h1>
          {view === 'bord' && (
            <Btn small icon={SlidersHorizontal} onClick={() => setPersonnaliser(true)}>
              Personnaliser l'affichage
            </Btn>
          )}
        </div>
        {sousTitre && <p className="text-[13.5px] text-txt2 mt-1 first-letter:uppercase">{sousTitre}</p>}

        {nav.subnav && (
          <div className="mt-3.5">
            <TileNav items={nav.subnav} active={view} onPick={onGo} />
          </div>
        )}
      </div>

      {personnaliser && <ModalPersonnaliserDashboard onClose={() => setPersonnaliser(false)} />}
    </div>
  )
}
