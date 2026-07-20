import { useState, useCallback } from 'react'
import { useTheme } from './hooks/useTheme.js'
import { AppContextProvider } from './context/AppContext.jsx'
import { AuthContextProvider, useAuth } from './context/AuthContext.jsx'
import { PotagerContextProvider, usePotager } from './context/PotagerContext.jsx'
import TopBar    from './components/TopBar.jsx'
import BottomNav from './components/BottomNav.jsx'
import Plan      from './views/Plan.jsx'
import Stocks    from './views/Stocks.jsx'
import Pepiniere from './views/Pepiniere.jsx'
import Historique from './views/Historique.jsx'
import Stats     from './views/Stats.jsx'
import Auth      from './views/Auth.jsx'
import AucunPotager from './views/AucunPotager.jsx'

const VIEWS = {
  plan:       { title: 'Plan des parcelles', Component: Plan      },
  stocks:     { title: 'Stocks cultures',    Component: Stocks    },
  pepiniere:  { title: 'Pépinière',          Component: Pepiniere },
  historique: { title: 'Historique',         Component: Historique },
  stats:      { title: 'Statistiques',       Component: Stats     },
}

function AppInner() {
  useTheme()

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
    <div className="flex flex-col h-dvh max-w-md mx-auto bg-g-bg">
      <TopBar title={title} onRefresh={handleRefresh} loading={loading} />

      <main className="flex-1 overflow-y-auto px-3 pt-3 pb-2">
        <Component refresh={refreshKey} />
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} />
    </div>
  )
}

function PotagerGate() {
  const { aucunPotager, loading } = usePotager()
  if (loading) return null
  if (aucunPotager) return <AucunPotager />

  return (
    <AppContextProvider>
      <AppInner />
    </AppContextProvider>
  )
}

function AppGate() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Auth />

  return (
    <PotagerContextProvider>
      <PotagerGate />
    </PotagerContextProvider>
  )
}

export default function App() {
  return (
    <AuthContextProvider>
      <AppGate />
    </AuthContextProvider>
  )
}
