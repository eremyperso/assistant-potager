// [US-031 CA17-CA19] Champ de recherche culture — local par écran, non persisté.
import { Search } from 'lucide-react'

export default function CultureFilter({ value, onChange, placeholder = 'Filtrer par culture…', className = 'relative mb-3' }) {
  return (
    <div className={className}>
      <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary"
      />
    </div>
  )
}
