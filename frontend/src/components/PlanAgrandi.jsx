// Le plan agrandi sur mobile : le mini-plan d'US-329 trop petit pour toucher une parcelle, en plein écran.
//
// Même dessin que le plan complet (`ParcellePlan` non réduit : noms et segments lisibles), dans un
// cadre qui défile dans les deux sens — la modale occupe l'écran, aucun conflit avec le défilement
// de la page. Zoom par boutons + / − (pas de pinch). Toucher une parcelle (son nom ou l'un de ses
// segments) la choisit : l'appelant ferme la fenêtre et fait défiler la liste jusqu'à sa carte.
import { useState } from 'react'
import { Map as IconePlan, Minus, Plus } from 'lucide-react'
import Modal from './ui/Modal.jsx'
import { ParcellePlan, EchellePlan } from './PlanDessin.jsx'
import {
  CRAN_ZOOM_INITIAL, CRANS_ZOOM_AGRANDI, cranZoomSuivant, echelleAgrandie,
} from '../lib/planMobile.js'

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'
const BOUTON = `inline-flex h-11 w-11 items-center justify-center rounded-full border border-border bg-card text-txt
  disabled:opacity-40 ${FOCUS}`

export const TEXTE_AIDE_AGRANDI = 'Touchez une parcelle pour voir sa carte'

export default function PlanAgrandi({ formes, emprise, angle = 0, onChoisir, onClose }) {
  const [cran, setCran] = useState(CRAN_ZOOM_INITIAL)
  const u = echelleAgrandie(cran)
  const actives = formes.filter((f) => f.actif)
  const choisir = (forme) => onChoisir?.(forme)

  return (
    <Modal title="Plan du potager" sub={TEXTE_AIDE_AGRANDI} icon={IconePlan} onClose={onClose}
      width={720} disposition="plein_mobile" bodyClassName="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-end gap-2 border-b border-border px-3 py-2">
        <span className="mr-auto text-[12px] text-txt2" aria-live="polite">Zoom {cran + 1}/{CRANS_ZOOM_AGRANDI.length} · glissez pour vous déplacer</span>
        <button type="button" className={BOUTON} aria-label="Zoom arrière" disabled={cran <= 0}
          onClick={() => setCran((c) => cranZoomSuivant(c, -1))}><Minus size={18} aria-hidden="true" /></button>
        <button type="button" className={BOUTON} aria-label="Zoom avant" disabled={cran >= CRANS_ZOOM_AGRANDI.length - 1}
          onClick={() => setCran((c) => cranZoomSuivant(c, 1))}><Plus size={18} aria-hidden="true" /></button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-3 min-[600px]:max-h-[70vh]" tabIndex={-1}
        style={{ touchAction: 'pan-x pan-y' }}>
        <div className="plan-cadre plan-grille relative rounded-xl"
          style={{ width: emprise.longueur * u, height: emprise.largeur * u, backgroundSize: `${u}px ${u}px` }}>
          <div className="absolute inset-0" style={angle ? { transform: `rotate(${angle}deg)` } : undefined}>
            {actives.map((forme) => (
              <ParcellePlan key={forme.id} forme={forme} u={u}
                onParcelle={choisir} onSegment={choisir} onRangLibre={choisir} />
            ))}
          </div>
          <EchellePlan u={u} />
        </div>
      </div>
    </Modal>
  )
}
