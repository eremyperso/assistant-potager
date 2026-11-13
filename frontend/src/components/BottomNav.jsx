import { useState } from 'react'
import { MoreHorizontal, Mic, Pencil } from 'lucide-react'
import { NAV_OF, NOTER, barreBasse } from '../navigation.js'
import { useNotifier } from '../context/NotificationsContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { peutEnregistrer } from '../lib/gestes.js'
import { ouvrirGastonAvec, pastilleNoter, TEXTE_PEPINIERE_NOTER } from '../lib/contexteCompagnon.js'

/**
 * Barre d'onglets basse [US-053 / CA1, US-325].
 *
 * Visible uniquement sous 900px : au-delà, la navigation principale remonte
 * dans le bandeau supérieur, inchangée. [US-325] Accueil, Plan, **Noter** au centre,
 * Pépinière, puis « Plus » (Cultures, Stocks, Journal — arbitrage P1).
 *
 * « Noter » est une ACTION, jamais l'onglet courant : il ouvre Gaston (US-324) avec la
 * sélection courante de l'écran Plan pour contexte (US-323), ou « Tout le potager ».
 */
export default function BottomNav({ view, onGo, selection = null }) {
  const [plusOuvert, setPlusOuvert] = useState(false)
  const { notifier } = useNotifier()
  // [US-324 / CA9] Un membre en lecture seule ne note rien : « Noter » ne lui est pas proposé.
  const { potagerActif } = usePotager()
  const ecrire = peutEnregistrer(potagerActif?.role)

  const { principales, secondaires } = barreBasse()
  const navId = NAV_OF[view]
  const dansSecondaires = secondaires.some((n) => n.id === navId)

  const aller = (id) => {
    setPlusOuvert(false)
    onGo(id)
  }

  const pastille = pastilleNoter(selection)
  const noter = () => {
    setPlusOuvert(false)
    if (pastille.sorte === 'pepiniere') {
      // [US-325] Sur une parcelle pépinière : les lots se notent dans Ma pépinière.
      notifier({ tone: 'blue', titre: TEXTE_PEPINIERE_NOTER, cle: 'noter-pepiniere' })
      onGo('pepiniere')
      return
    }
    ouvrirGastonAvec(selection)
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
        {principales.map((entree) => {
          if (entree.id === NOTER.id) {
            if (!ecrire) return null
            return (
              /* [US-325 / CA2, CA5] Mis en avant, jamais « courant » ; 44 px au pouce, focus visible. */
              <div key={NOTER.id} className="flex flex-1 justify-center">
                <button
                  type="button"
                  onClick={noter}
                  aria-label={NOTER.label}
                  title={NOTER.label}
                  className="relative -mt-3 flex min-h-[44px] min-w-[44px] flex-col items-center gap-0.5 rounded-2xl bg-brand px-3.5 pb-1.5 pt-2 text-[10px] font-bold text-white shadow-[0_6px_16px_rgba(22,33,12,.25)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand dark:text-bg"
                >
                  <Pencil size={19} strokeWidth={2.2} aria-hidden="true" />
                  {NOTER.shortLabel}
                  {/* La sélection courante : l'emoji de la culture, l'épingle d'une parcelle, le micro sinon. */}
                  <span
                    className="absolute -right-1.5 -top-1.5 flex h-[22px] min-w-[22px] items-center justify-center rounded-full border-2 border-surface bg-[var(--gst-bulle,#fff)] text-[12px] leading-none text-brand-text"
                    aria-hidden="true"
                    data-pastille={pastille.sorte}
                  >
                    {pastille.emoji || <Mic size={12} strokeWidth={2.4} />}
                  </span>
                </button>
              </div>
            )
          }
          const { id, shortLabel, label, Icon } = entree
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
