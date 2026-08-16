import { useState } from 'react'
import { MoreHorizontal } from 'lucide-react'
import { NAV, NAV_OF, NAV_MOBILE_VISIBLE } from '../navigation.js'

/**
 * Barre d'onglets basse [US-053 / CA1].
 *
 * Visible uniquement sous 900px : au-delà, la navigation principale remonte
 * dans le bandeau supérieur. Les entrées au-delà des 4 premières sont
 * regroupées sous un bouton « Plus ».
 */
export default function BottomNav({ view, onGo }) {
  const [plusOuvert, setPlusOuvert] = useState(false)

  const principales = NAV.slice(0, NAV_MOBILE_VISIBLE)
  const secondaires = NAV.slice(NAV_MOBILE_VISIBLE)
  const navId = NAV_OF[view]
  const dansSecondaires = secondaires.some((n) => n.id === navId)

  const aller = (id) => {
    setPlusOuvert(false)
    onGo(id)
  }

  return (
    <div className="shrink-0 relative nav:hidden">
      {plusOuvert && (
        <>
          {/* Zone de fermeture au clic — limitée à ce qui est AU-DESSUS de la barre
              d'onglets (`bottom-full`), sinon elle absorberait les clics sur les
              onglets eux-mêmes et il faudrait cliquer deux fois pour changer de section. */}
          <div
            className="absolute bottom-full left-0 right-0 h-screen z-10"
            onClick={() => setPlusOuvert(false)}
            aria-hidden="true"
          />
          <div className="absolute bottom-full left-0 right-0 z-20 p-2.5 bg-surface border-t border-border shadow-[0_-12px_30px_rgba(0,0,0,.14)]">
            {secondaires.map(({ id, label, Icon }) => {
              const on = id === navId
              return (
                <button
                  key={id}
                  onClick={() => aller(id)}
                  aria-current={on ? 'page' : undefined}
                  className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm text-left transition-colors ${
                    on ? 'bg-brand-soft text-brand-text font-bold' : 'text-txt2 font-medium'
                  }`}
                >
                  <Icon size={19} className={on ? 'text-brand' : 'text-txt3'} />
                  {label}
                </button>
              )
            })}
          </div>
        </>
      )}

      <nav
        className="flex bg-surface border-t border-border"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
        aria-label="Navigation principale"
      >
        {principales.map(({ id, shortLabel, label, Icon }) => {
          const on = id === navId
          return (
            <button
              key={id}
              onClick={() => aller(id)}
              aria-label={label}
              aria-current={on ? 'page' : undefined}
              className={`flex flex-1 flex-col items-center gap-1 pt-2.5 pb-1.5 text-[10px] transition-colors ${
                on ? 'text-brand-text font-bold' : 'text-txt3 font-medium'
              }`}
            >
              <Icon size={21} strokeWidth={on ? 2 : 1.7} className={on ? 'text-brand' : 'text-txt3'} />
              {shortLabel}
            </button>
          )
        })}

        <button
          onClick={() => setPlusOuvert((o) => !o)}
          aria-label="Plus de sections"
          aria-expanded={plusOuvert}
          className={`flex flex-1 flex-col items-center gap-1 pt-2.5 pb-1.5 text-[10px] transition-colors ${
            dansSecondaires || plusOuvert ? 'text-brand-text font-bold' : 'text-txt3 font-medium'
          }`}
        >
          <MoreHorizontal
            size={21}
            strokeWidth={dansSecondaires || plusOuvert ? 2.4 : 2}
            className={dansSecondaires || plusOuvert ? 'text-brand' : 'text-txt3'}
          />
          Plus
        </button>
      </nav>
    </div>
  )
}
