// [US-031 CA5-CA11] Sélecteur de date de référence.
// Utilise un <input type="date"> natif (mobile-friendly) superposé sur un bouton stylisé.
import { Calendar, X } from 'lucide-react'
import { useDateRef } from '../context/AppContext.jsx'

const todayISO = () => new Date().toISOString().slice(0, 10)

function fmtFR(iso) {
  if (!iso) return "Aujourd'hui"
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

export default function DateRefPicker() {
  const { dateRef, setDateRef } = useDateRef()
  const isPast = Boolean(dateRef)

  return (
    <div className="flex items-center gap-1.5 mb-3">
      {/* Bouton + input natif superposé */}
      <div className="relative inline-flex items-center">
        {/* Couche visuelle [CA6 / CA10] */}
        <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium select-none cursor-pointer transition-colors ${
          isPast
            ? 'bg-amber-50 border-amber-300 text-amber-700 dark:bg-amber-950 dark:border-amber-700 dark:text-amber-300'
            : 'bg-white border-gray-200 text-gray-500 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-400'
        }`}>
          <Calendar size={13} aria-hidden="true" />
          <span>{fmtFR(dateRef)}</span>
        </div>
        {/* Input transparent sur toute la surface [CA7 / CA9] */}
        <input
          type="date"
          max={todayISO()}
          value={dateRef || ''}
          onChange={e => setDateRef(e.target.value || null)}
          className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
          aria-label="Date de référence"
        />
      </div>

      {/* Bouton reset "Aujourd'hui" [CA8] */}
      {isPast && (
        <button
          onClick={() => setDateRef(null)}
          title="Revenir à aujourd'hui"
          className="p-1 rounded text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-200 transition-colors"
          aria-label="Revenir à aujourd'hui"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}
