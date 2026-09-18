import { CalendarDays } from 'lucide-react'
import { Modal, Btn, BlocConfiance } from './ui'
import { libelleAction, dateLongue } from '../lib/confiance.js'

/**
 * [US-180 / CA5] « Pourquoi ce niveau ? » — ouverte depuis la pastille de
 * confiance d'une tuile du Plan (maquette gelée du 18/09/2026, `PourquoiPanel`).
 *
 * Le bloc « règle de confiance » est celui de la fiche calendrier (US-183) :
 * même composant, même lecture groupée, donc le même niveau et les mêmes
 * motifs pour la même culture au même instant. Les deux silences de la tuile
 * (rien à faire / aucun calendrier) se lisent dans la fiche calendrier, que la
 * frise de la tuile ouvre.
 *
 * `onOuvrirFiche` : un passage explicite vers la fiche calendrier — retour
 * terrain du 18/09/2026, la frise seule ne suffisait pas à la faire trouver.
 */
export default function FicheConfiance({ culture, confiance, dateRef, onOuvrirFiche, onClose }) {
  const nom = culture ? culture.charAt(0).toUpperCase() + culture.slice(1) : ''
  const sousTitre = [nom, libelleAction(confiance.action).toLowerCase(), dateRef && `au ${dateLongue(dateRef)}`]
    .filter(Boolean).join(' · ')
  const note = (confiance.avertissements || []).join(' ') || null
  return (
    <Modal
      title="Pourquoi ce niveau ?"
      sub={sousTitre}
      onClose={onClose}
      disposition="basse"
      foot={
        <div className="flex items-center justify-end gap-2 flex-wrap">
          {onOuvrirFiche && (
            <Btn kind="soft" icon={CalendarDays} onClick={onOuvrirFiche}>Voir la fiche calendrier</Btn>
          )}
          <Btn onClick={onClose}>Fermer</Btn>
        </div>
      }
    >
      <BlocConfiance confiance={confiance} note={note} />
    </Modal>
  )
}
