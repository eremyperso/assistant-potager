import { RefreshCw, Moon, Sun } from 'lucide-react'
import { useTheme } from '../hooks/useTheme.js'

export default function TopBar({ title, onRefresh, loading }) {
  const { theme, toggle } = useTheme()

  return (
    <header className="flex items-center justify-between px-4 bg-g-sur border-b border-g-brd" style={{ height: 54, flexShrink: 0 }}>
      <span className="text-xl font-bold text-g-pri font-serif tracking-tight leading-none">{title}</span>
      <div className="flex items-center gap-4 text-g-sec">
        <button
          onClick={onRefresh}
          disabled={loading}
          aria-label="Actualiser"
          className="hover:text-g-acc transition-colors disabled:opacity-40"
        >
          <RefreshCw size={17} className={loading ? 'animate-spin' : ''} />
        </button>
        <button onClick={toggle} aria-label="Basculer thème" className="hover:text-g-acc transition-colors">
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>
    </header>
  )
}
