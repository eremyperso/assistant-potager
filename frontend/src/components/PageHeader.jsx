import { useState, useEffect, useCallback } from 'react'
import { SlidersHorizontal, Archive, Settings, X } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { api } from '../lib/api.js'
import { Btn, TileNav, InfoBanner } from './ui'
import { navEntry } from '../navigation.js'
import ModalPersonnaliserDashboard from './ModalPersonnaliserDashboard.jsx'
import ParametresPotager from '../views/ParametresPotager.jsx'

/**
 * En-tête de page [US-053 / CA2, CA3] : titre, sous-titre descriptif, et
 * tuiles de sous-navigation pour les sections qui en déclarent.
 *
 * Les sections sans `subnav` (Cultures, Pépinière, Stocks, Journal)
 * n'affichent pas la zone de tuiles.
 */
export default function PageHeader({ view, onGo }) {
  const { potagerId, setPotagerId } = usePotager()
  const [potagerDetail, setPotagerDetail] = useState(null)
  const nav = navEntry(view)
  const sousTitre = typeof nav.sub === 'function' ? nav.sub() : nav.sub
  // [US-077 / CA1] `view` (pas `nav.id`) : la section "bord" couvre aussi
  // l'écran Statistiques (même `subnav`) — le bouton ne doit apparaître que
  // sur "Vue d'ensemble", pas sur "Statistiques".
  const [personnaliser, setPersonnaliser] = useState(false)
  // [US-083 / CA7] Réouvre Paramètres sur le potager consulté — seul chemin vers
  // « Zone sensible » (désarchiver) une fois qu'on n'est plus sur son potager actif.
  const [parametresOuvert, setParametresOuvert] = useState(false)

  // [US-083 / CA7] Charger les détails du potager consulté pour vérifier si archivé
  const chargerPotagerDetail = useCallback(() => {
    if (!potagerId) {
      setPotagerDetail(null)
      return
    }
    api.potager(potagerId).then(setPotagerDetail).catch(() => {})
  }, [potagerId])

  useEffect(() => { chargerPotagerDetail() }, [chargerPotagerDetail])

  const estArchive = potagerDetail?.etat === 'archive'

  return (
    <div className="bg-surface border-b border-border">
      {/* [US-083 / CA7] Bandeau permanent si un potager archivé est consulté */}
      {estArchive && (
        <div className="bg-amber-soft border-b border-amber px-4 nav:px-6 py-2.5">
          <div className="max-w-[1320px] mx-auto flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Archive size={16} className="text-amber" />
              <span className="text-[13px] font-medium text-amber-text">
                Potager archivé — lecture seule
              </span>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {/* [US-083 / CA1] Seul accès à la Zone sensible (désarchiver) une fois
                  qu'on consulte un potager qui n'est plus son potager actif. */}
              <button
                onClick={() => setParametresOuvert(true)}
                className="flex items-center gap-1.5 text-[13px] font-medium text-amber-text hover:text-amber transition-colors"
              >
                <Settings size={14} />
                Paramètres
              </button>
              <button
                onClick={() => setPotagerId(null)}
                aria-label="Fermer"
                className="text-amber-text hover:text-amber transition-colors"
              >
                <X size={16} />
              </button>
            </div>
          </div>
        </div>
      )}

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
      {parametresOuvert && (
        <ParametresPotager
          potagerId={potagerId}
          onClose={() => {
            setParametresOuvert(false)
            // [US-083 / CA1] Reflète immédiatement un désarchivage : le bandeau
            // doit disparaître sans attendre un changement de `potagerId`.
            chargerPotagerDetail()
          }}
        />
      )}
    </div>
  )
}
