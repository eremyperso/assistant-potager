import { LayoutGrid, BarChart2, Sprout, List, AreaChart } from 'lucide-react'

const TABS = [
  { id: 'plan',       label: 'Plan',      Icon: LayoutGrid },
  { id: 'stocks',     label: 'Stocks',    Icon: BarChart2  },
  { id: 'pepiniere',  label: 'Pépinière', Icon: Sprout     },
  { id: 'historique', label: 'Historique',Icon: List       },
  { id: 'stats',      label: 'Stats',     Icon: AreaChart  },
]

export default function BottomNav({ active, onChange }) {
  return (
    <nav
      className="flex border-t border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      aria-label="Navigation principale"
    >
      {TABS.map(({ id, label, Icon }) => {
        const isActive = active === id
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            aria-label={label}
            aria-current={isActive ? 'page' : undefined}
            className={`flex flex-1 flex-col items-center gap-1 py-2 text-[10px] font-medium transition-colors
              ${isActive
                ? 'text-primary'
                : 'text-gray-400 dark:text-gray-600 hover:text-gray-600 dark:hover:text-gray-400'
              }`}
          >
            <Icon size={20} />
            {label}
          </button>
        )
      })}
    </nav>
  )
}
