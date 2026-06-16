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
      className="flex border-t border-g-brd bg-g-sur"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)', flexShrink: 0 }}
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
            className={`flex flex-1 flex-col items-center gap-0.5 pt-2 pb-1.5 text-[10px] font-medium transition-colors ${
              isActive ? 'text-g-acc' : 'text-g-sec'
            }`}
          >
            <Icon size={22} strokeWidth={isActive ? 2.1 : 1.7} />
            {label}
          </button>
        )
      })}
    </nav>
  )
}
