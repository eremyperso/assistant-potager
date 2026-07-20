import { useState, useEffect } from 'react'
import { RefreshCw, Moon, Sun, LogOut, Send } from 'lucide-react'
import { useTheme } from '../hooks/useTheme.js'
import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../lib/api.js'
import LierTelegram from './LierTelegram.jsx'

export default function TopBar({ title, onRefresh, loading }) {
  const { theme, toggle } = useTheme()
  const { logout } = useAuth()
  const [version, setVersion] = useState(null)
  const [showLierTelegram, setShowLierTelegram] = useState(false)

  useEffect(() => {
    api.health().then(h => setVersion(h?.version)).catch(() => {})
  }, [])

  return (
    <header className="flex items-center justify-between px-4 bg-g-sur border-b border-g-brd" style={{ height: 54, flexShrink: 0 }}>
      <span className="text-xl font-bold text-g-pri font-serif tracking-tight leading-none">{title}</span>
      <div className="flex items-center gap-4 text-g-sec">
        {version && (
          <span className="text-[11px] font-medium" style={{ color: 'var(--g-sec)' }}>
            v{version}
          </span>
        )}
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
        <button
          onClick={() => setShowLierTelegram(true)}
          aria-label="Relier Telegram"
          className="hover:text-g-acc transition-colors"
        >
          <Send size={16} />
        </button>
        <button onClick={logout} aria-label="Se déconnecter" className="hover:text-g-red transition-colors">
          <LogOut size={17} />
        </button>
      </div>
      {showLierTelegram && <LierTelegram onClose={() => setShowLierTelegram(false)} />}
    </header>
  )
}
