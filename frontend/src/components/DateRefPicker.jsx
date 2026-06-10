// [US-031 CA5-CA11] Sélecteur de date de référence.
// Bouton stylisé qui déclenche showPicker() (Chrome 99+, Safari, Firefox 101+)
// avec fallback click() pour compatibilité maximale.
import { useRef } from 'react'
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
  const inputRef = useRef(null)
  const isPast   = Boolean(dateRef)

  function openPicker() {
    if (!inputRef.current) return
    try {
      // showPicker() : Chrome 99+, Firefox 101+, Safari 16+
      inputRef.current.showPicker()
    } catch {
      // Fallback : focus + clic simulé (navigateurs plus anciens)
      inputRef.current.focus()
      inputRef.current.click()
    }
  }

  return (
    <div className="flex items-center gap-1.5 mb-3">
      {/* Bouton visuel — clic déclenche showPicker() [CA6 / CA7 / CA9 / CA10] */}
      <button
        type="button"
        onClick={openPicker}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors cursor-pointer ${
          isPast
            ? 'bg-amber-50 border-amber-300 text-amber-700 dark:bg-amber-950 dark:border-amber-700 dark:text-amber-300'
            : 'bg-white border-gray-200 text-gray-500 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-400'
        }`}
        aria-label={isPast ? `Date de référence : ${fmtFR(dateRef)}` : 'Choisir une date de référence'}
      >
        <Calendar size={13} aria-hidden="true" />
        <span>{fmtFR(dateRef)}</span>
      </button>

      {/* Input date réel — caché mais accessible [CA9] */}
      <input
        ref={inputRef}
        type="date"
        max={todayISO()}
        value={dateRef || ''}
        onChange={e => setDateRef(e.target.value || null)}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
      />

      {/* Reset "Aujourd'hui" [CA8] */}
      {isPast && (
        <button
          type="button"
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
