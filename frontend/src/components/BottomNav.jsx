import { useState } from 'react'
import { MoreHorizontal } from 'lucide-react'
import { NAV_OF, NOTER, barreBasse } from '../navigation.js'
import { entreePlus } from '../lib/coquille.js'
import BoutonNoter from './BoutonNoter.jsx'

/**
 * Barre d'onglets basse [US-053 / CA1, US-325, US-353 / CA2].
 *
 * Visible uniquement sous 900 px : au-delà, la navigation principale remonte dans le bandeau
 * supérieur. Accueil, Plan, **Noter** (rond de 62 px en dégradé, qui déborde de 30 px), Pépinière,
 * puis « Plus ». L'onglet actif a une **pastille verte de 56 × 30** derrière l'icône. Quand la vue
 * active est rangée sous « Plus » (Cultures, Stocks, Journal), ce bouton prend son nom, son icône
 * et la pastille.
 *
 * « Noter » est une ACTION, jamais l'onglet courant (voir `BoutonNoter`).
 */
export default function BottomNav({ view, onGo, selection = null, nonLus = 0 }) {
  const [plusOuvert, setPlusOuvert] = useState(false)

  const { principales, secondaires } = barreBasse()
  const navId = NAV_OF[view]
  const rangee = entreePlus(navId, secondaires)

  const aller = (id) => {
    setPlusOuvert(false)
    onGo(id)
  }

  const PlusIcone = rangee?.Icon ?? MoreHorizontal
  const plusActif = Boolean(rangee)

  return (
    <div className="shrink-0 relative nav:hidden z-20">
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
        className="flex border-t border-border bg-surface"
        style={{ paddingBottom: 'max(18px, env(safe-area-inset-bottom, 0px))' }}
        aria-label="Navigation principale"
      >
        {principales.map((entree) => {
          if (entree.id === NOTER.id) {
            return <BoutonNoter key={NOTER.id} variante="barre" selection={selection} nonLus={nonLus} onGo={onGo} />
          }
          const { id, shortLabel, label, Icon } = entree
          const on = id === navId
          return (
            <button
              key={id}
              onClick={() => aller(id)}
              aria-label={label}
              aria-current={on ? 'page' : undefined}
              className={`flex flex-1 flex-col items-center gap-[3px] pt-2 text-[10.5px] transition-colors ${
                on ? 'font-bold text-brand-deep' : 'font-medium text-txt3'
              }`}
            >
              <span className={`bn-ind ${on ? 'actif' : ''}`}>
                <Icon size={21} strokeWidth={on ? 2 : 1.7} className={on ? 'text-brand' : 'text-txt3'} />
              </span>
              {shortLabel}
            </button>
          )
        })}

        <button
          onClick={() => setPlusOuvert((o) => !o)}
          aria-label={rangee ? `${rangee.label}, plus de sections` : 'Plus de sections'}
          aria-expanded={plusOuvert}
          aria-current={rangee ? 'page' : undefined}
          className={`flex flex-1 flex-col items-center gap-[3px] pt-2 text-[10.5px] transition-colors ${
            plusActif || plusOuvert ? 'font-bold text-brand-deep' : 'font-medium text-txt3'
          }`}
        >
          <span className={`bn-ind ${plusActif || plusOuvert ? 'actif' : ''}`}>
            <PlusIcone size={21} strokeWidth={plusActif ? 2 : 1.7} className={plusActif || plusOuvert ? 'text-brand' : 'text-txt3'} />
          </span>
          {rangee ? rangee.shortLabel : 'Plus'}
        </button>
      </nav>
    </div>
  )
}
