import { TileNav } from './ui'
import { navEntry } from '../navigation.js'

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

  return (
    <div className="bg-surface border-b border-border">
      <div className={`max-w-[1320px] mx-auto px-4 nav:px-6 pt-5 ${nav.subnav ? 'pb-3.5' : 'pb-5'}`}>
        <h1 className="font-serif text-[27px] font-bold text-txt tracking-tight leading-tight">
          {nav.title}
        </h1>
        {sousTitre && <p className="text-[13.5px] text-txt2 mt-1 first-letter:uppercase">{sousTitre}</p>}

        {nav.subnav && (
          <div className="mt-3.5">
            <TileNav items={nav.subnav} active={view} onPick={onGo} />
          </div>
        )}
      </div>
    </div>
  )
}
