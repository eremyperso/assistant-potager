import { useState, useCallback, useLayoutEffect, useEffect, useRef } from 'react'
import { useTheme } from './hooks/useTheme.js'
import { AppContextProvider } from './context/AppContext.jsx'
import { AuthContextProvider, useAuth } from './context/AuthContext.jsx'
import { setTokens } from './lib/api.js'
import { PotagerContextProvider, usePotager } from './context/PotagerContext.jsx'
import TopBar    from './components/TopBar.jsx'
import BottomNav from './components/BottomNav.jsx'
import { InfobulleEtapes } from './components/ui'  // [US-352 / CA4] survol et appui long de 380 ms
import PageHeader from './components/PageHeader.jsx'
import { Placeholder } from './components/ui'
import { VUE_PAR_DEFAUT, NAV_OF, vueDeSection } from './navigation.js'
import { NavigationProvider } from './context/NavigationContext.jsx'
import { consommerIntentionAdresse } from './lib/intentions.js'
import BasculePotagerIntention from './components/BasculePotagerIntention.jsx'
import MessageIntention from './components/MessageIntention.jsx'
import BandeauFile from './components/BandeauFile.jsx'  // [US-224]
import { FileGestesProvider } from './context/FileGestesContext.jsx'  // [US-224]
import { NotificationsProvider } from './context/NotificationsContext.jsx'  // retour d'action
import BandesFixes from './components/BandesFixes.jsx'  // [US-353] mot de Gaston, barre d'outils, règle des temps
import BoutonNoter from './components/BoutonNoter.jsx'  // [US-353] le seul bouton rond vers Gaston
import PanneauPartage from './components/PanneauPartage.jsx'  // [US-353 / CA12]
import { CoquilleProvider, useCoquille } from './context/CoquilleContext.jsx'  // [US-353]
import { estCompact, occupantAFermer } from './lib/coquille.js'  // [US-353 / CA11]
import PanneauCompagnon from './components/PanneauCompagnon.jsx'  // [US-271]
import { GastonDefs } from './components/Gaston.jsx'  // [US-271]
import { useMedia } from './hooks/useMedia.js'  // [US-271]
import { useNonLusCompagnon } from './hooks/useNonLusCompagnon.js'  // [US-272]
import { etatInitial, ecrireEtat, etatSuivant, PARAM_OUVRIR } from './lib/compagnon.js'  // [US-271, US-292]
import Dashboard from './views/Dashboard.jsx'
import PlanDessus from './views/PlanDessus.jsx'  // [US-327] remplace la Vue plan d'US-200
import { EVENEMENT_OUVRIR_COMPAGNON, EVENEMENT_SELECTION_PLAN, ouvertureDuPanneau } from './lib/contexteCompagnon.js'  // [US-322, US-323, US-325]
import { VUE_PLAN } from './lib/noter.js'  // [US-324]
import Cultures  from './views/Cultures.jsx'  // [US-205]
import Stocks    from './views/Stocks.jsx'
import Pepiniere from './views/Pepiniere.jsx'
import Journal    from './views/Journal.jsx'
import Stats     from './views/Stats.jsx'
import Auth      from './views/Auth.jsx'
import VerifyEmail from './views/VerifyEmail.jsx'
import ReinitialiserMotDePasse from './views/ReinitialiserMotDePasse.jsx'
import Onboarding from './views/Onboarding.jsx'
import ConsentementConnecteur from './views/ConsentementConnecteur.jsx'  // [US-290]
import { capterDemandeAdresse, demandeEnAttente } from './lib/connecteurIa.js'  // [US-290]

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

// [US-290] Demande de connexion d'un assistant IA (/connecteur-ia?demande=…) : captée
// AVANT le retour Google ci-dessous, gardée le temps de la connexion du jardinier.
const DEMANDE_CONNECTEUR = capterDemandeAdresse()

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
  // [US-200] L'écran d'attente d'US-053 laisse place à la Vue plan : une carte
  // par parcelle, un trait par rang. Le glisser-déposer annoncé par le
  // Placeholder n'est PAS revenu — la V1 retenue (wireframe v3) est en lecture
  // seule, la saisie reste au compagnon.
  // [US-327] La Vue plan devient le plan vu du dessus : les parcelles à leur place,
  // à l'échelle, chaque rang découpé en segments par étape (US-320, US-321, US-326).
  'plan-vue': (props) => <PlanDessus {...props} />,
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
  // [US-271 / CA1] Gaston, le compagnon : replié, présent ou chat ouvert, depuis n'importe quel écran.
  // Replié / présent sont retenus d'une visite à l'autre ; le chat ne se rouvre pas tout seul.
  const [compagnon, setCompagnon] = useState(() => etatInitial(window.localStorage, window.location.search))
  useEffect(() => {
    // [US-292 / CA10] `?compagnon=ouvrir` n'ouvre le panneau qu'une fois : retiré de l'adresse.
    const params = new URLSearchParams(window.location.search)
    if (!params.has(PARAM_OUVRIR)) return
    params.delete(PARAM_OUVRIR)
    const reste = params.toString()
    window.history.replaceState(null, '', window.location.pathname + (reste ? `?${reste}` : '') + window.location.hash)
  }, [])
  const agirCompagnon = useCallback((action) => setCompagnon((e) => {
    const suivant = etatSuivant(e, action)
    ecrireEtat(window.localStorage, suivant)
    return suivant
  }), [])
  // [US-353 / CA12] Structure de page : un panneau droit de 400 px à partir de 900 px ; en dessous,
  // une feuille montante, et Gaston en plein écran.
  const bureau = useMedia('(min-width: 900px)')
  const coquille = useCoquille()
  // [US-272 / CA5] La pastille des messages non lus, relue tant que le chat est fermé.
  const { nonLus: nonLusCompagnon, marquerVu: marquerCompagnonVu } = useNonLusCompagnon(compagnon === 'chat')
  // [US-322 / S6, US-323 / C1, C6] « Noter » ouvre Gaston avec ce que le jardinier a sous les yeux
  // (barre de contexte) ; le visage de Gaston ouvre une conversation libre, sans barre.
  const [ouverture, setOuverture] = useState({ barre: false, contexte: null, sujet: null, champ: null })
  useEffect(() => {
    const ouvrir = (e) => {
      setOuverture(ouvertureDuPanneau(e.detail))
      agirCompagnon('ouvrir')
    }
    window.addEventListener(EVENEMENT_OUVRIR_COMPAGNON, ouvrir)
    return () => window.removeEventListener(EVENEMENT_OUVRIR_COMPAGNON, ouvrir)
  }, [agirCompagnon])
  // [US-358 / CA6] Retirer le contexte (×) retire aussi le sujet affiché : le message suivant part sans contexte.
  const changerContexte = useCallback((contexte) => setOuverture({ barre: true, contexte, sujet: null, champ: null }), [])
  // [US-325 / CA3] La sélection courante de l'écran Plan : pastille et contexte du bouton « Noter ».
  const [selectionPlan, setSelectionPlan] = useState(null)
  useEffect(() => {
    const suivre = (e) => setSelectionPlan(e.detail?.contexte ?? null)
    window.addEventListener(EVENEMENT_SELECTION_PLAN, suivre)
    return () => window.removeEventListener(EVENEMENT_SELECTION_PLAN, suivre)
  }, [])

  // [US-353 / CA12] Un seul occupant du panneau à la fois : ouvrir Gaston referme la fiche, et
  // ouvrir une fiche referme Gaston.
  const gastonOuvert = compagnon === 'chat'
  const { occupant: occupantFiche, fermerPanneau } = coquille
  // [US-358] Le dernier venu l'emporte : Noter depuis une fiche ouvre Gaston ET doit fermer la fiche, pas
  // Gaston. Les deux règles ne sont donc plus indépendantes (elles se fermaient l'une l'autre dans le même rendu).
  const avantPanneau = useRef({ gastonOuvert: false, occupant: null })
  useEffect(() => {
    const aFermer = occupantAFermer({ gastonOuvert, occupant: occupantFiche }, avantPanneau.current)
    avantPanneau.current = { gastonOuvert, occupant: occupantFiche }
    if (aFermer === 'fiche') fermerPanneau()
    else if (aFermer === 'gaston') agirCompagnon('fermer')
  }, [gastonOuvert, occupantFiche, fermerPanneau, agirCompagnon])
  // [US-355 / CA1] Une fiche ouverte (commune ou catalogue) ne survit pas au changement de vue : le panneau est celui de l'écran.
  useEffect(() => { if (occupantFiche?.commune) fermerPanneau() }, [view])   // eslint-disable-line react-hooks/exhaustive-deps

  // [US-353 / CA11] Seule la bande de contenu défile ; au-delà de 8 px, l'en-tête se resserre.
  const [compact, setCompact] = useState(false)
  const surDefilement = useCallback((e) => setCompact(estCompact(e.currentTarget.scrollTop)), [])
  const remonter = useCallback(() => {
    mainRef.current?.scrollTo?.({ top: 0, behavior: 'smooth' })
  }, [])

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

  // [US-223 / CA4] Dernière vue visitée par section, en mémoire de page : revenir
  // au Plan rouvre le sous-onglet quitté ; une nouvelle session repart de l'entrée.
  const dernieres = useRef({ [NAV_OF[view]]: view })

  const changerVue = useCallback((id) => {
    if (!VIEWS[id]) return
    defilements.current.set(view, mainRef.current?.scrollTop ?? 0)
    dernieres.current[NAV_OF[id]] = id
    setView(id)
  }, [view])

  // Un appui sur une section de la navigation principale (TopBar, BottomNav) —
  // distinct d'un appui sur un sous-onglet, qui ouvre exactement son identifiant.
  const changerSection = useCallback((navId) => {
    changerVue(vueDeSection(navId, dernieres.current))
  }, [changerVue])

  useLayoutEffect(() => {
    if (mainRef.current) mainRef.current.scrollTop = defilements.current.get(view) ?? 0
  }, [view])

  // Le chat de Gaston (maquette « Compagnon.html »), dans le panneau partagé : un geste confirmé relit
  // l'écran courant.
  const panneauGaston = (plein) => (
    <PanneauCompagnon
      plein={plein}
      vue={view}
      onFermer={() => agirCompagnon('fermer')}
      onEnregistre={handleRefresh}
      onVu={marquerCompagnonVu}
      barreContexte={ouverture.barre}
      contexte={ouverture.contexte}
      sujet={ouverture.sujet}
      champ={ouverture.champ}
      onContexte={changerContexte}
      noter={ouverture.barre && !ouverture.placement}
      placement={ouverture.placement}
      onRetourPlan={() => { agirCompagnon('fermer'); changerVue(VUE_PLAN) }}
    />
  )

  return (
    <NavigationProvider
      vue={view}
      onVue={changerVue}
      vueValide={vueValide}
      intentionInitiale={intentionAdresse}
    >
      <BasculePotagerIntention intentionAdresse={intentionAdresse} />
      <FileGestesProvider>
      <NotificationsProvider>
      <div className="flex flex-col h-dvh bg-bg">
        <TopBar view={view} onGo={changerSection} onRefresh={handleRefresh} loading={loading} />

        <div className="flex min-h-0 flex-1">
          {/* [US-353 / CA11] Les bandes fixes (en-tête, mot de Gaston, barre d'outils) ne défilent
              pas ; seul le contenu défile. Le conteneur `page` sert les container queries de la
              barre d'outils (Filtrer se réduit à son icône sous 520 px). */}
          <div className="@container/page flex min-w-0 flex-1 flex-col">
            <div className="relative z-[2] shrink-0 bg-bg shadow-[0_1px_0_var(--border),0_6px_10px_-8px_rgba(22,33,12,.18)]">
              <PageHeader view={view} onGo={changerVue} compact={compact} />
              <BandesFixes view={view} compact={compact} onRemonter={remonter} />
            </div>

            <main ref={mainRef} onScroll={surDefilement} className="min-h-0 flex-1 overflow-y-auto">
              <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-4 pb-28 nav:pb-24">
                <MessageIntention />
                {/* [US-224 / CA22] Le compte de la file, sur tous les écrans — une
                    file invisible serait une file oubliée. */}
                <BandeauFile />
                {renderView({ refresh: refreshKey })}
              </div>
            </main>
          </div>

          {/* [US-353 / CA12] Panneau droit de 400 px sur ordinateur : un seul occupant, Gaston ou la
              fiche déclarée par la vue. Sur mobile, il est rendu plus bas (feuille ou plein écran). */}
          {bureau && (gastonOuvert || occupantFiche) && (
            <PanneauPartage
              bureau occupant={gastonOuvert ? 'gaston' : occupantFiche.cle}
              titre={gastonOuvert ? 'Gaston' : occupantFiche.titre}
              onFermer={gastonOuvert ? () => agirCompagnon('fermer') : fermerPanneau}
            >
              {gastonOuvert ? panneauGaston(false) : occupantFiche.contenu}
            </PanneauPartage>
          )}
        </div>

        <BottomNav
          view={view} onGo={changerSection} nonLus={nonLusCompagnon}
          selection={NAV_OF[view] === 'plan' ? selectionPlan : null}
        />

        {/* [US-353 / CA3] Sur ordinateur, le même bouton rond en bas à droite : décalé à gauche du
            panneau ouvert, absent tant que Gaston est ouvert. */}
        {bureau && (
          <BoutonNoter
            variante="bureau" nonLus={nonLusCompagnon} onGo={changerSection}
            selection={NAV_OF[view] === 'plan' ? selectionPlan : null}
            panneauOuvert={Boolean(occupantFiche)} gastonOuvert={gastonOuvert}
          />
        )}

        {!bureau && (gastonOuvert || occupantFiche) && (
          <PanneauPartage
            bureau={false} occupant={gastonOuvert ? 'gaston' : occupantFiche.cle}
            titre={gastonOuvert ? 'Gaston' : occupantFiche.titre}
            onFermer={gastonOuvert ? () => agirCompagnon('fermer') : fermerPanneau}
          >
            {gastonOuvert ? panneauGaston(true) : occupantFiche.contenu}
          </PanneauPartage>
        )}
        <GastonDefs />
        <InfobulleEtapes />
      </div>
      </NotificationsProvider>
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
      <CoquilleProvider>
        <AppInner intentionAdresse={INTENTION_ADRESSE} />
      </CoquilleProvider>
    </AppContextProvider>
  )
}

function AppGate({ retourOAuth }) {
  const { isAuthenticated } = useAuth()
  // [US-290 / CA2] Une demande de connexion d'assistant IA en attente passe avant
  // l'application : connexion d'abord (e-mail ou Google), puis consentement.
  const [demandeConnecteur, setDemandeConnecteur] = useState(() => demandeEnAttente(DEMANDE_CONNECTEUR))
  // [US-090 / CA3, CA11] Un retour Google en échec ramène ici, sur l'écran de
  // connexion, avec de quoi expliquer ce qui s'est passé ; un retour réussi a
  // déjà posé les jetons et traverse cette porte sans s'arrêter.
  if (!isAuthenticated) return <Auth retourOAuth={retourOAuth} />
  if (demandeConnecteur) {
    return <ConsentementConnecteur demande={demandeConnecteur} onAbandon={() => setDemandeConnecteur(null)} />
  }

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
