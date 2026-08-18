import { useState, useCallback } from 'react'
import { useTheme } from './hooks/useTheme.js'
import { AppContextProvider } from './context/AppContext.jsx'
import { AuthContextProvider, useAuth } from './context/AuthContext.jsx'
import { PotagerContextProvider, usePotager } from './context/PotagerContext.jsx'
import TopBar    from './components/TopBar.jsx'
import BottomNav from './components/BottomNav.jsx'
import PageHeader from './components/PageHeader.jsx'
import { Placeholder } from './components/ui'
import { VUE_PAR_DEFAUT } from './navigation.js'
import Dashboard from './views/Dashboard.jsx'
import Plan      from './views/Plan.jsx'
import Stocks    from './views/Stocks.jsx'
import Pepiniere from './views/Pepiniere.jsx'
import Journal    from './views/Journal.jsx'
import Stats     from './views/Stats.jsx'
import Auth      from './views/Auth.jsx'
import VerifyEmail from './views/VerifyEmail.jsx'
import ReinitialiserMotDePasse from './views/ReinitialiserMotDePasse.jsx'
import Onboarding from './views/Onboarding.jsx'

// [US-044 / CA10] Lien de vérification reçu par e-mail : /verifier-email?token=...
// Pas de librairie de routage dans ce projet — détection manuelle du chemin,
// indépendante de AuthContext (l'utilisateur n'est pas encore connecté ici).
function getVerificationToken() {
  if (window.location.pathname !== '/verifier-email') return null
  return new URLSearchParams(window.location.search).get('token')
}

// [US-057 / CA2] Lien de réinitialisation reçu par e-mail : /reinitialiser-mot-de-passe?token=...
function getResetPasswordToken() {
  if (window.location.pathname !== '/reinitialiser-mot-de-passe') return null
  return new URLSearchParams(window.location.search).get('token')
}

// Écrans de la navigation à deux niveaux [US-053].
// Les sections dont le contenu relève d'un lot ultérieur sont rendues en
// `Placeholder` explicite plutôt qu'en lien mort [CA6].
const VIEWS = {
  // [US-076] Le widget météo est réel ; les trois autres restent en
  // `Placeholder` à l'intérieur même de la vue (cf. `views/Dashboard.jsx`).
  bord: (props) => <Dashboard {...props} />,
  stats: (props) => <Stats {...props} />,
  plan: (props) => <Plan {...props} />,
  'plan-vue': () => (
    <Placeholder
      title="Vue plan à l'échelle"
      body="Représentation en plan des planches et des rangs, avec placement des cultures par glisser-déposer."
    />
  ),
  'plan-rot': () => (
    <Placeholder
      title="Rotation des cultures"
      body="Historique des familles cultivées par parcelle sur trois ans, avec alerte en cas de retour trop rapide d'une même famille."
    />
  ),
  cultures: () => (
    <Placeholder
      title="Mes cultures"
      body="Fiches par culture et par variété : famille botanique, durée, exposition, besoin en eau et calendrier cultural sur douze mois."
    />
  ),
  pepiniere: (props) => <Pepiniere {...props} />,
  stocks: (props) => <Stocks {...props} />,
  journal: (props) => <Journal {...props} />,
}

function AppInner() {
  useTheme()

  const [view, setView] = useState(VUE_PAR_DEFAUT)
  const [refreshKey, setRefreshKey] = useState(0)
  const [loading, setLoading]     = useState(false)

  const handleRefresh = useCallback(() => {
    setLoading(true)
    setRefreshKey(k => k + 1)
    setTimeout(() => setLoading(false), 800)
  }, [])

  const renderView = VIEWS[view] ?? VIEWS[VUE_PAR_DEFAUT]

  return (
    <div className="flex flex-col h-dvh bg-bg">
      <TopBar view={view} onGo={setView} onRefresh={handleRefresh} loading={loading} />

      <main className="flex-1 overflow-y-auto min-h-0">
        <PageHeader view={view} onGo={setView} />
        <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-4 pb-7">
          {renderView({ refresh: refreshKey })}
        </div>
      </main>

      <BottomNav view={view} onGo={setView} />
    </div>
  )
}

function PotagerGate() {
  const { aucunPotager, loading } = usePotager()
  if (loading) return null
  // [US-058 / CA1] Assistant en 4 étapes — déclenché automatiquement pour un
  // compte sans potager, et seule porte d'entrée pour « Créer un potager »
  // (US-048/US-054), qu'il remplace.
  if (aucunPotager) return <Onboarding />

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
  const [token, setToken] = useState(getVerificationToken)
  const [resetToken, setResetToken] = useState(getResetPasswordToken)

  if (token) {
    return (
      <VerifyEmail
        token={token}
        onDone={() => {
          window.history.replaceState({}, '', '/')
          setToken(null)
        }}
      />
    )
  }

  if (resetToken) {
    return (
      <ReinitialiserMotDePasse
        token={resetToken}
        onDone={() => {
          window.history.replaceState({}, '', '/')
          setResetToken(null)
        }}
      />
    )
  }

  return (
    <AuthContextProvider>
      <AppGate />
    </AuthContextProvider>
  )
}
