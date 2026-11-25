import { useState, useEffect, useCallback } from 'react'
import { Archive, Settings, X } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { useCoquille } from '../context/CoquilleContext.jsx'
import { api } from '../lib/api.js'
import { TileNav } from './ui'
import { navEntry } from '../navigation.js'
import ParametresPotager from '../views/ParametresPotager.jsx'

/**
 * En-tête de page [US-053 / CA2, CA3, US-353 / CA5] : titre en Lora (25 px sur mobile, 28 px sur
 * ordinateur), une ligne de contexte, et les onglets de sous-vue pour les sections qui en déclarent
 * (Tableau de bord, Plan, Cultures) : tuiles de 84 × 64 sur ordinateur, pastilles compactes de 36 px
 * sur mobile ; un onglet peut être désactivé (« Rotation · à venir »).
 *
 * L'en-tête ne contient NI export NI aide (ils sont dans le menu ⋯ de la barre d'outils). Quand le
 * contenu a défilé de plus de 8 px (`compact`, CA11), il se resserre : titre en 18 px, ligne de
 * contexte masquée, tuiles masquées sur ordinateur.
 */
export default function PageHeader({ view, onGo, compact = false }) {
  const { potagerId, setPotagerId } = usePotager()
  const [potagerDetail, setPotagerDetail] = useState(null)
  const nav = navEntry(view)
  // [US-356 / CA1] Une vue peut déclarer SON en-tête : la ligne de contexte qui change avec l'onglet, et
  // ses onglets (« Parcours », « Semer · 3 », « Lots · 18 »). Sans déclaration, ceux de la navigation.
  const { declaration } = useCoquille()
  const entete = declaration?.entete
  const sousTitre = entete?.contexte ?? (typeof nav.sub === 'function' ? nav.sub() : nav.sub)
  const onglets = entete?.onglets ?? nav.subnav
  const ongletActif = entete?.actif ?? view
  const choisirOnglet = entete?.onChoisir ?? onGo
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

      <div className={`max-w-[1320px] mx-auto px-4 nav:px-6 transition-[padding] duration-200 ${
        compact ? 'py-2.5' : `pt-[18px] nav:pt-[22px] ${onglets ? 'pb-3.5' : 'pb-3.5 nav:pb-4'}`
      }`}>
        <h1 className={`font-serif font-bold leading-[1.15] tracking-[-.01em] text-txt transition-[font-size] duration-200 ${
          compact ? 'text-[18px]' : 'text-[25px] nav:text-[28px]'
        }`}>
          {nav.title}
        </h1>
        {sousTitre && !compact && <p className="mt-[3px] text-[13px] text-txt2 first-letter:uppercase">{sousTitre}</p>}

        {onglets && (
          <div className={compact ? 'mt-2' : 'mt-3'}>
            <TileNav items={onglets} active={ongletActif} onPick={choisirOnglet} compact={compact} />
          </div>
        )}
      </div>

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
