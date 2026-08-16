// [US-031 CA5-CA11] Sélecteur de date de référence.
// [US-059 CA1] Migré sur les tokens sémantiques de la palette 2026.
import { Calendar, X } from 'lucide-react'
import { useDateRef } from '../context/AppContext.jsx'

const todayISO = () => new Date().toISOString().slice(0, 10)

function fmtFR(iso) {
  if (!iso) return "Aujourd'hui"
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

export default function DateRefPicker({ className = 'flex items-center gap-1.5' }) {
  const { dateRef, setDateRef } = useDateRef()
  const isPast = Boolean(dateRef)

  return (
    <div className={className}>
      <div className="relative inline-flex items-center">
        {/* décoration visuelle — l'input overlay intercepte les événements */}
        <div className={`flex items-center gap-1.5 px-3 h-[38px] rounded-[10px] border text-[13.5px] font-medium select-none cursor-pointer transition-colors ${
          isPast
            ? 'bg-amber-soft border-amber text-amber'
            : 'bg-card border-border text-txt3'
        }`}>
          <Calendar size={15} aria-hidden="true" />
          <span>{fmtFR(dateRef)}</span>
        </div>

        {/* overlay transparent — tap mobile natif + showPicker() pour desktop */}
        <input
          type="date"
          max={todayISO()}
          value={dateRef || ''}
          onChange={e => setDateRef(e.target.value || null)}
          onClick={e => { try { e.target.showPicker() } catch {} }}
          className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
          aria-label="Date de référence"
        />
      </div>

      {/* bouton reset [CA8] */}
      {isPast && (
        <button
          onClick={() => setDateRef(null)}
          title="Revenir à aujourd'hui"
          className="p-1 rounded text-amber hover:text-txt transition-colors"
          aria-label="Revenir à aujourd'hui"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}
