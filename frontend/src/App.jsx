import { useState, useCallback } from 'react'
import { useTheme } from './hooks/useTheme.js'
import TopBar    from './components/TopBar.jsx'
import BottomNav from './components/BottomNav.jsx'
import Plan      from './views/Plan.jsx'
import Stocks    from './views/Stocks.jsx'
import Pepiniere from './views/Pepiniere.jsx'
import Historique from './views/Historique.jsx'
import Stats     from './views/Stats.jsx'

const VIEWS = {
  plan:       { title: 'Plan des parcelles', Component: Plan      },
  stocks:     { title: 'Stocks cultures',    Component: Stocks    },
  pepiniere:  { title: 'Pépinière',          Component: Pepiniere },
  historique: { title: 'Historique',         Component: Historique },
  stats:      { title: 'Statistiques',       Component: Stats     },
}

export default function App() {
  useTheme() // applique dark/light au chargement

  const [activeTab, setActiveTab] = useState('plan')
  const [refreshKey, setRefreshKey] = useState(0)
  const [loading, setLoading]     = useState(false)

  const handleRefresh = useCallback(() => {
    setLoading(true)
    setRefreshKey(k => k + 1)
    setTimeout(() => setLoading(false), 800)
  }, [])

  const { title, Component } = VIEWS[activeTab]

  return (
    <div className="flex flex-col h-dvh max-w-md mx-auto bg-gray-50 dark:bg-gray-950">
      <TopBar title={title} onRefresh={handleRefresh} loading={loading} />

      <main className="flex-1 overflow-y-auto p-3">
        <Component refresh={refreshKey} />
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} />
    </div>
  )
}
