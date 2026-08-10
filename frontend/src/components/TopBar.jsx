import { useState, useEffect } from 'react'
import { RefreshCw, Moon, Sun, LogOut, Send, Users, Leaf } from 'lucide-react'
import { useTheme } from '../hooks/useTheme.js'
import { useAuth } from '../context/AuthContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { api } from '../lib/api.js'
import { NAV, NAV_OF } from '../navigation.js'
import LierTelegram from './LierTelegram.jsx'
import PotagerMenu from './PotagerMenu.jsx'
import GestionMembres from './GestionMembres.jsx'

/**
 * Bandeau supérieur [US-053 / CA1].
 *
 * Porte la navigation principale à partir de 900px de large ; en dessous, la
 * navigation passe dans la barre d'onglets basse (`BottomNav`) et seul le
 * bandeau d'identité + actions reste ici.
 *
 * Les actions transverses (potager actif, actualisation, thème, Telegram,
 * membres, déconnexion) sont conservées telles quelles : leur regroupement en
 * menus « Potager » et « Compte » relève de US-054 / US-055.
 */
export default function TopBar({ view, onGo, onRefresh, loading }) {
  const { theme, toggle } = useTheme()
  const { logout } = useAuth()
  const { potagerActif } = usePotager()
  const [version, setVersion] = useState(null)
  const [showLierTelegram, setShowLierTelegram] = useState(false)
  const [showGestionMembres, setShowGestionMembres] = useState(false)

  useEffect(() => {
    api.health().then((h) => setVersion(h?.version)).catch(() => {})
  }, [])

  const navId = NAV_OF[view]

  return (
    <header
      className="shrink-0 text-header-txt"
      style={{ background: 'linear-gradient(100deg, var(--header-from), var(--header-to))' }}
    >
      <div className="max-w-[1352px] mx-auto flex items-center gap-3.5 h-[58px] px-4 nav:px-6">
        {/* Identité + potager actif */}
        <div className="flex items-center gap-2.5 min-w-0 shrink">
          <div className="w-8 h-8 rounded-[10px] bg-header-glass flex items-center justify-center shrink-0">
            <Leaf size={19} />
          </div>
          <span className="font-serif text-[17.5px] font-bold tracking-tight whitespace-nowrap hidden min-[1340px]:inline">
            Mon Potager
          </span>
          {/* [US-054] Menu déroulant de bascule/adhésion — reste le seul accès
              permanent au code d'invitation (cf. US-048 / CA4). */}
          <PotagerMenu />
        </div>

        {/* Navigation principale — desktop uniquement [CA1] */}
        <nav className="hidden nav:flex items-center gap-1" aria-label="Navigation principale">
          {NAV.map(({ id, label, Icon }) => {
            const on = id === navId
            return (
              <button
                key={id}
                onClick={() => onGo(id)}
                aria-current={on ? 'page' : undefined}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-[10px] text-[13.5px] whitespace-nowrap transition-colors ${
                  on ? 'bg-header-glass font-bold' : 'font-medium text-header-dim hover:text-header-txt'
                }`}
              >
                <Icon size={16} strokeWidth={on ? 2 : 1.7} />
                {label}
              </button>
            )
          })}
        </nav>

        {/* Actions transverses */}
        <div className="flex items-center gap-1.5 ml-auto shrink-0">
          {version && <span className="text-[11px] font-medium text-header-dim hidden sm:inline">v{version}</span>}
          <button
            onClick={onRefresh}
            disabled={loading}
            aria-label="Actualiser"
            className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center disabled:opacity-40"
          >
            <RefreshCw size={17} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={toggle}
            aria-label="Basculer thème"
            className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center"
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>
          <button
            onClick={() => setShowLierTelegram(true)}
            aria-label="Relier Telegram"
            className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center"
          >
            <Send size={16} />
          </button>
          {potagerActif?.role === 'owner' && (
            <button
              onClick={() => setShowGestionMembres(true)}
              aria-label="Gérer les membres"
              className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center"
            >
              <Users size={17} />
            </button>
          )}
          <button
            onClick={logout}
            aria-label="Se déconnecter"
            className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center"
          >
            <LogOut size={17} />
          </button>
        </div>
      </div>

      {showLierTelegram && <LierTelegram onClose={() => setShowLierTelegram(false)} />}
      {showGestionMembres && <GestionMembres onClose={() => setShowGestionMembres(false)} />}
    </header>
  )
}
