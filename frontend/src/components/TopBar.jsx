import { RefreshCw, Moon, Sun, Leaf } from 'lucide-react'
import { useTheme } from '../hooks/useTheme.js'
import { NAV, NAV_OF } from '../navigation.js'
import PotagerMenu from './PotagerMenu.jsx'
import AccountMenu from './AccountMenu.jsx'

/**
 * Bandeau supérieur [US-053 / CA1].
 *
 * Porte la navigation principale à partir de 900px de large ; en dessous, la
 * navigation passe dans la barre d'onglets basse (`BottomNav`) et seul le
 * bandeau d'identité + actions reste ici.
 *
 * Les actions transverses sont regroupées dans deux menus déroulants — potager
 * actif (US-054) à gauche, compte (US-055) à droite. Ne restent en icônes
 * directes que le thème et, en desktop seulement, l'actualisation manuelle
 * (doublée dans le menu Compte en mobile) [US-055 / CA4, CA5].
 */
export default function TopBar({ view, onGo, onRefresh, loading }) {
  const { theme, toggle } = useTheme()

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
          {/* [CA4] Sous 900px, l'actualisation passe dans le menu Compte : seuls
              le thème et l'avatar restent visibles en permanence. */}
          <button
            onClick={onRefresh}
            disabled={loading}
            aria-label="Actualiser"
            className="w-[34px] h-[34px] rounded-[10px] hidden nav:flex items-center justify-center disabled:opacity-40"
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
          <AccountMenu onRefresh={onRefresh} loading={loading} />
        </div>
      </div>
    </header>
  )
}
