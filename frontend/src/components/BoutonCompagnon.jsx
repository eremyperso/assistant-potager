// [US-271 / CA1] Gaston, le bouton flottant qui ouvre le panneau du compagnon, depuis n'importe quel écran.
//
// Deux états visibles, ceux de la maquette « Compagnon.html » : REPLIÉ (Gaston dépasse du bord droit,
// un chevron invite à le déplier) et PRÉSENT (l'avatar rond en bas à droite, sa main qui salue, sa
// pastille « en ligne », un petit bouton pour le replier). Le troisième état, le chat ouvert, est le
// panneau (`PanneauCompagnon`).
//
// Il se pose par la STRUCTURE DE PAGE (voir `App.jsx` : une ancre de hauteur nulle juste au-dessus de la
// règle des temps et de la barre d'onglets), pas par des valeurs magiques : il ne recouvre jamais la
// navigation basse. Les tailles et les décalages de la maquette (desktop / mobile) sont dans `index.css`
// (classes `gst-*`) ; sans survol sur mobile, un petit signe toutes les 6 s remplace l'animation.
import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { GastonComplet, VisageGaston, MainGaston } from './Gaston.jsx'
import { BULLE_PRESENT, GASTON, libellePastille } from '../lib/compagnon.js'

const DUREE_BULLE_MS = 8000
const CLE_BULLE = 'potager_compagnon_bulle_vue'

/** La bulle d'accueil ne s'affiche qu'une fois par session, quelques secondes. */
function useBulleDAccueil(visible) {
  const [bulle, setBulle] = useState(false)
  useEffect(() => {
    if (!visible) return undefined
    let dejaVue = false
    try { dejaVue = sessionStorage.getItem(CLE_BULLE) === '1' } catch { /* sans stockage : on la montre */ }
    if (dejaVue) return undefined
    try { sessionStorage.setItem(CLE_BULLE, '1') } catch { /* idem */ }
    setBulle(true)
    const t = setTimeout(() => setBulle(false), DUREE_BULLE_MS)
    return () => clearTimeout(t)
  }, [visible])
  return bulle
}

/** [US-272 / CA5] La pastille des messages non lus, posée sur l'avatar (ou sur l'onglet replié). */
function Pastille({ n }) {
  const libelle = libellePastille(n)
  if (!libelle) return null
  return (
    <span className="gst-nonlus" aria-label={`${n} message${n > 1 ? 's' : ''} non lu${n > 1 ? 's' : ''}`} role="status">
      {libelle}
    </span>
  )
}

export default function BoutonCompagnon({ etat, nonLus = 0, onOuvrir, onReplier, onDeplier }) {
  const bulle = useBulleDAccueil(etat === 'present')

  if (etat === 'replie') {
    return (
      <div className="gst-tab">
        <GastonComplet className="gst-tab-sv" />
        <button type="button" className="gst-chev" onClick={onDeplier} aria-label={`Déplier ${GASTON.nom}`} title={`Déplier ${GASTON.nom}`}>
          <ChevronLeft size={18} strokeWidth={2.4} aria-hidden="true" />
        </button>
        <Pastille n={nonLus} />
      </div>
    )
  }

  return (
    <div className="gst-pres">
      {bulle && <div className="gst-bulle" role="status">{BULLE_PRESENT}</div>}
      <button type="button" className="gst-av" onClick={onOuvrir} aria-label={nonLus > 0 ? `Parler au compagnon (${nonLus} non lu${nonLus > 1 ? 's' : ''})` : 'Parler au compagnon'} title={`Parler à ${GASTON.nom}`}>
        <VisageGaston />
      </button>
      <MainGaston />
      <i className="gst-dot" aria-hidden="true" />
      <Pastille n={nonLus} />
      <button type="button" className="gst-min" onClick={onReplier} aria-label={`Replier ${GASTON.nom}`} title="Replier">
        <ChevronRight size={12} strokeWidth={3} aria-hidden="true" />
      </button>
    </div>
  )
}
