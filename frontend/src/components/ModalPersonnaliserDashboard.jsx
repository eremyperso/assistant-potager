// [US-077] Modale « Personnaliser l'affichage » — cases à cocher pour
// afficher/masquer les widgets du Tableau de bord (US-076). Aucune maquette
// Claude Design dédiée : composée avec `Modal` (US-055) et une case à cocher
// dans le style déjà utilisé pour les CGU (`Auth.jsx`, `accent-brand`).
import { SlidersHorizontal } from 'lucide-react'
import { Modal } from './ui'
import { useDashboardWidgets, WIDGETS_CATALOGUE } from '../hooks/useDashboardWidgets.js'

export default function ModalPersonnaliserDashboard({ onClose }) {
  const { visible, toggle } = useDashboardWidgets()

  return (
    <Modal
      title="Personnaliser l'affichage"
      icon={SlidersHorizontal}
      sub="Choisissez les widgets visibles sur votre Tableau de bord"
      onClose={onClose}
      width={380}
      foot="Au moins un widget doit rester affiché."
    >
      <div className="flex flex-col gap-1">
        {WIDGETS_CATALOGUE.map((w) => {
          const coche = visible.includes(w.id)
          // [CA4] Le dernier widget encore coché ne peut pas être décoché.
          const verrouille = coche && visible.length === 1
          return (
            <label
              key={w.id}
              className={`flex items-center gap-3 px-2.5 py-2.5 rounded-xl ${
                verrouille ? 'opacity-60' : 'cursor-pointer hover:bg-card-alt'
              }`}
            >
              <input
                type="checkbox"
                checked={coche}
                disabled={verrouille}
                onChange={() => toggle(w.id)}
                className="w-4 h-4 accent-brand shrink-0"
              />
              <span className="text-[13.5px] text-txt">{w.label}</span>
            </label>
          )
        })}
      </div>
    </Modal>
  )
}
