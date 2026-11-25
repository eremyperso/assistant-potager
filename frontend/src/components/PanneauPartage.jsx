import { useEffect } from 'react'
import { X } from 'lucide-react'
import { LARGEUR_PANNEAU_PX, formePanneau } from '../lib/coquille.js'

/**
 * Panneau partagé [US-353 / CA12] : la fiche commune, la fiche catalogue, Récoltes par saison ou
 * Gaston — UN SEUL à la fois (`occupant`).
 *  - ordinateur : un panneau droit de 400 px à côté du contenu ;
 *  - mobile : une feuille montante (poignée, fond assombri, appui hors feuille = fermer) ; Gaston y
 *    est en plein écran.
 *
 * La bascule bureau / mobile est une STRUCTURE DE PAGE (`bureau` vient du breakpoint de la
 * coquille, `App.jsx`). `children` est le contenu de l'occupant ; Gaston gère sa propre en-tête et
 * son propre ×, les autres occupants reçoivent un × flottant.
 */
export default function PanneauPartage({ occupant, bureau, titre = 'Panneau', onFermer, children }) {
  const forme = formePanneau({ occupant, bureau })

  const gaston = occupant === 'gaston'
  useEffect(() => {
    // Gaston gère lui-même Échap (PanneauCompagnon) ; la feuille et le panneau d'une fiche se ferment ici.
    if (forme !== 'feuille' && !(forme === 'lateral' && !gaston)) return undefined
    const echap = (e) => { if (e.key === 'Escape') onFermer?.() }
    document.addEventListener('keydown', echap)
    return () => document.removeEventListener('keydown', echap)
  }, [forme, gaston, onFermer])

  if (!forme) return null

  const fermer = !gaston && (
    <button
      type="button" onClick={onFermer} aria-label="Fermer"
      className="absolute right-3 top-3 z-10 grid h-9 w-9 place-items-center rounded-full bg-card-alt text-txt2"
    >
      <X size={16} aria-hidden="true" />
    </button>
  )

  if (forme === 'lateral') {
    return (
      <aside
        aria-label={titre} data-occupant={occupant}
        className={`relative flex shrink-0 flex-col border-l border-border bg-surface ${gaston ? 'overflow-hidden' : 'overflow-y-auto'}`}
        style={{ width: LARGEUR_PANNEAU_PX }}
      >
        {fermer}
        {children}
      </aside>
    )
  }

  if (forme === 'plein-ecran') {
    return <div className="fixed inset-0 z-50" role="dialog" aria-label={titre} data-occupant={occupant}>{children}</div>
  }

  return (
    <div className="feuille-voile" onClick={onFermer} data-occupant={occupant}>
      <div className="feuille" role="dialog" aria-label={titre} onClick={(e) => e.stopPropagation()}>
        <div className="feuille-poignee" aria-hidden="true" />
        {fermer}
        {children}
      </div>
    </div>
  )
}
