import { RefreshCw, Moon, Sun } from 'lucide-react'
import { useTheme } from '../hooks/useTheme.js'

export default function TopBar({ title, onRefresh, loading }) {
  const { theme, toggle } = useTheme()

  return (
    <header className="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-900 border-b border-gray-100 dark:border-gray-800">
      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{title}</span>
      <div className="flex items-center gap-3 text-gray-400 dark:text-gray-500">
        <button
          onClick={onRefresh}
          disabled={loading}
          aria-label="Actualiser"
          className="hover:text-primary transition-colors disabled:opacity-40"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
        <button onClick={toggle} aria-label="Basculer thème" className="hover:text-primary transition-colors">
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  )
}
