// [US-031 CA5-CA11] Sélecteur de date de référence.
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
      {/* Bouton + input natif superposé */}
      <div className="relative inline-flex items-center">
        <div className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border text-sm font-medium select-none cursor-pointer transition-colors ${
          isPast
            ? 'bg-g-amb-dim border-g-amb text-g-amb'
            : 'bg-g-card border-g-brd text-g-sec'
        }`}>
          <Calendar size={14} aria-hidden="true" />
          <span>{fmtFR(dateRef)}</span>
        </div>
        <input
          type="date"
          max={todayISO()}
          value={dateRef || ''}
          onChange={e => setDateRef(e.target.value || null)}
          className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
          aria-label="Date de référence"
        />
      </div>

      {/* Bouton reset [CA8] */}
      {isPast && (
        <button
          onClick={() => setDateRef(null)}
          title="Revenir à aujourd'hui"
          className="p-1 rounded text-g-amb hover:text-g-pri transition-colors"
          aria-label="Revenir à aujourd'hui"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}
