import { useState, useCallback, useLayoutEffect, useRef } from 'react'
import { useTheme } from './hooks/useTheme.js'
import { AppContextProvider } from './context/AppContext.jsx'
import { AuthContextProvider, useAuth } from './context/AuthContext.jsx'
import { setTokens } from './lib/api.js'
import { PotagerContextProvider, usePotager } from './context/PotagerContext.jsx'
import TopBar    from './components/TopBar.jsx'
import BottomNav from './components/BottomNav.jsx'
import PageHeader from './components/PageHeader.jsx'
import { Placeholder } from './components/ui'
import { VUE_PAR_DEFAUT } from './navigation.js'
import { NavigationProvider } from './context/NavigationContext.jsx'
import { consommerIntentionAdresse } from './lib/intentions.js'
import BasculePotagerIntention from './components/BasculePotagerIntention.jsx'
import MessageIntention from './components/MessageIntention.jsx'
import BandeauFile from './components/BandeauFile.jsx'  // [US-224]
import { FileGestesProvider } from './context/FileGestesContext.jsx'  // [US-224]
import Dashboard from './views/Dashboard.jsx'
import Plan      from './views/Plan.jsx'
import PlanVue   from './views/PlanVue.jsx'  // [US-200]
import Cultures  from './views/Cultures.jsx'  // [US-205]
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

// [US-090 / CA3] Retour de la fédération Google : /auth/callback#access_token=…
// Le résultat arrive dans le fragment d'URL, jamais dans la query string — le
// fragment n'est pas envoyé au serveur et n'apparaît donc ni dans les logs
// d'accès ni dans l'en-tête Referer. Consommé une seule fois, à l'initialisation
// de App, puis effacé de la barre d'adresse : ni jeton ni code de message ne
// subsiste dans l'historique de navigation.
function consommerRetourOAuth() {
  if (window.location.pathname !== '/auth/callback') return null

  const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const access_token = params.get('access_token')
  if (access_token) setTokens({ access_token, refresh_token: params.get('refresh_token') })

  window.history.replaceState({}, '', '/')
  return {
    connecte: Boolean(access_token),
    erreur: params.get('erreur'),
    info: params.get('info'),
  }
}

// Évalué une seule fois, au chargement du module. L'opération n'est PAS
// idempotente — elle efface le fragment — et React.StrictMode invoque deux fois
// les initialisateurs de `useState` en développement : passer la fonction à
// `useState` ferait perdre le résultat du premier appel, seul à voir le fragment.
const RETOUR_OAUTH = consommerRetourOAuth()

// [US-195 / CA5, CA6] L'intention portée par l'adresse (`/?vue=pepiniere&lot=128`)
// est lue UNE fois, au chargement du module, et aussitôt effacée de la barre
// d'adresse : recharger la page ne la rejoue pas. Elle attend ici que la
// connexion soit faite — c'est ce qui la fait survivre à l'écran d'authentification
// (CA6). Lue à la RACINE seulement : les chemins de vérification d'e-mail, de
// réinitialisation de mot de passe et de retour OAuth ne sont jamais interceptés.
const INTENTION_ADRESSE = consommerIntentionAdresse()

// Écrans de la navigation à deux niveaux [US-053].
// Les sections dont le contenu relève d'un lot ultérieur sont rendues en
// `Placeholder` explicite plutôt qu'en lien mort [CA6].
const VIEWS = {
  // [US-076] Le widget météo est réel ; les trois autres restent en
  // `Placeholder` à l'intérieur même de la vue (cf. `views/Dashboard.jsx`).
  bord: (props) => <Dashboard {...props} />,
  stats: (props) => <Stats {...props} />,
  plan: (props) => <Plan {...props} />,
  // [US-200] L'écran d'attente d'US-053 laisse place à la Vue plan : une carte
  // par parcelle, un trait par rang. Le glisser-déposer annoncé par le
  // Placeholder n'est PAS revenu — la V1 retenue (wireframe v3) est en lecture
  // seule, la saisie reste au compagnon.
  'plan-vue': (props) => <PlanVue {...props} />,
  'plan-rot': () => (
    <Placeholder
      title="Rotation des cultures"
      body="Historique des familles cultivées par parcelle sur trois ans, avec alerte en cas de retour trop rapide d'une même famille."
    />
  ),
  // [US-205] L'écran d'attente d'US-053 laisse place à l'écran Cultures : une
  // carte par culture, au potager ou dans tout le référentiel.
  cultures: (props) => <Cultures {...props} />,
  pepiniere: (props) => <Pepiniere {...props} />,
  stocks: (props) => <Stocks {...props} />,
  journal: (props) => <Journal {...props} />,
}

function AppInner({ intentionAdresse }) {
  useTheme()

  const [view, setView] = useState(() =>
    intentionAdresse?.vue && VIEWS[intentionAdresse.vue] ? intentionAdresse.vue : VUE_PAR_DEFAUT
  )
  const [refreshKey, setRefreshKey] = useState(0)
  const [loading, setLoading]     = useState(false)

  const handleRefresh = useCallback(() => {
    setLoading(true)
    setRefreshKey(k => k + 1)
    setTimeout(() => setLoading(false), 800)
  }, [])

  const renderView = VIEWS[view] ?? VIEWS[VUE_PAR_DEFAUT]
  const vueValide = useCallback((id) => Boolean(VIEWS[id]), [])

  // [US-195 / CA9] La position de défilement fait partie de l'état exact d'un
  // écran. Le conteneur qui défile est UNIQUE et survit au changement de vue :
  // sans mémoire, on arriverait sur l'écran suivant à la hauteur du précédent.
  // Relevée juste avant de quitter, rendue juste après avoir affiché — en
  // mémoire de page, jamais persistée.
  const mainRef = useRef(null)
  const defilements = useRef(new Map())

  const changerVue = useCallback((id) => {
    if (!VIEWS[id]) return
    defilements.current.set(view, mainRef.current?.scrollTop ?? 0)
    setView(id)
  }, [view])

  useLayoutEffect(() => {
    if (mainRef.current) mainRef.current.scrollTop = defilements.current.get(view) ?? 0
  }, [view])

  return (
    <NavigationProvider
      vue={view}
      onVue={changerVue}
      vueValide={vueValide}
      intentionInitiale={intentionAdresse}
    >
      <BasculePotagerIntention intentionAdresse={intentionAdresse} />
      <FileGestesProvider>
      <div className="flex flex-col h-dvh bg-bg">
        <TopBar view={view} onGo={changerVue} onRefresh={handleRefresh} loading={loading} />

        <main ref={mainRef} className="flex-1 overflow-y-auto min-h-0">
          <PageHeader view={view} onGo={changerVue} />
          <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-4 pb-7">
            <MessageIntention />
            {/* [US-224 / CA22] Le compte de la file, sur tous les écrans — une
                file invisible serait une file oubliée. */}
            <BandeauFile />
            {renderView({ refresh: refreshKey })}
          </div>
        </main>

        <BottomNav view={view} onGo={changerVue} />
      </div>
      </FileGestesProvider>
    </NavigationProvider>
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
      <AppInner intentionAdresse={INTENTION_ADRESSE} />
    </AppContextProvider>
  )
}

function AppGate({ retourOAuth }) {
  const { isAuthenticated } = useAuth()
  // [US-090 / CA3, CA11] Un retour Google en échec ramène ici, sur l'écran de
  // connexion, avec de quoi expliquer ce qui s'est passé ; un retour réussi a
  // déjà posé les jetons et traverse cette porte sans s'arrêter.
  if (!isAuthenticated) return <Auth retourOAuth={retourOAuth} />

  return (
    <PotagerContextProvider>
      <PotagerGate />
    </PotagerContextProvider>
  )
}

export default function App() {
  const [token, setToken] = useState(getVerificationToken)
  const [resetToken, setResetToken] = useState(getResetPasswordToken)
  // Consommé à l'import, donc avant le montage de AuthContextProvider : les
  // jetons éventuels sont déjà en place quand celui-ci lit l'état de session.
  const [retourOAuth] = useState(RETOUR_OAUTH)

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
      <AppGate retourOAuth={retourOAuth} />
    </AuthContextProvider>
  )
}
