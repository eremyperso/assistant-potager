import { useState, useCallback } from 'react'
import { api } from '../lib/api.js'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import TopBar from '../components/TopBar.jsx'
import PageHeader from '../components/PageHeader.jsx'
import BottomNav from '../components/BottomNav.jsx'
import { Placeholder } from '../components/ui'
import { AppContextProvider } from '../context/AppContext.jsx'
import { NavigationProvider } from '../context/NavigationContext.jsx'
import { VUE_PAR_DEFAUT, navEntry, vueDeSection } from '../navigation.js'
import BandesFixes from '../components/BandesFixes.jsx'
import BoutonNoter from '../components/BoutonNoter.jsx'
import { CoquilleProvider, useDeclarerEcran } from '../context/CoquilleContext.jsx'
import { etatReplie } from '../lib/coquille.js'
import { InfobulleEtapes, PastilleEtape } from '../components/ui'
import { useMedia } from '../hooks/useMedia.js'

/**
 * Page de contrôle visuel de la coquille applicative [US-053, US-054, US-055].
 *
 * Monte la vraie navigation (TopBar, PotagerMenu, AccountMenu, PageHeader,
 * tuiles, BottomNav) sans dépendre du backend : chaque section rend un
 * Placeholder, la liste des potagers et l'identité du compte sont simulées, ce
 * qui permet de valider la structure isolément.
 * Non référencée par la navigation applicative.
 *
 * [US-353] Monte aussi les bandes fixes (mot de Gaston, barre d'outils, règle des temps) : la vue
 * factice déclare un mot et une barre, la bande de contenu défile seule et l'en-tête se resserre.
 * `?mot=0` : Gaston n'a rien à dire, aucun bloc n'est rendu.
 *
 * Deux paramètres d'URL pilotent les cas à contrôler [US-055] :
 * - `?role=owner|editor|lecteur` — rôle sur le potager actif, qui conditionne
 *   l'affichage de « Gérer les membres » dans le menu Compte
 * - `?telegram=0|1` — état de la liaison Telegram affiché dans ce même menu
 *
 * Les modales « Relier Telegram » et « Gérer les membres » sont elles aussi
 * simulées (génération de code, retrait de membre) pour pouvoir contrôler leur
 * rendu sans session réelle.
 */

const POTAGERS_DEMO = [
  { id: 1, nom: 'Potager de démonstration', actif: true, role: 'owner', nb_parcelles: 5, nb_membres: 3 },
  { id: 2, nom: 'Jardin partagé des Coteaux', actif: false, role: 'editor', nb_parcelles: 12, nb_membres: 8 },
  { id: 3, nom: 'Balcon', actif: false, role: 'lecteur', nb_parcelles: 1, nb_membres: 1 },
]

// bot_username [US-091] : identifiant factice pour contrôler visuellement le
// deep-link + QR du panneau d'activation sans dépendre de la config serveur.
const MOI_DEMO = { id: 1, nom: 'Rémy Eremy', email: 'remy@eremy.fr', bot_username: 'AssistantPotagerDemo_bot' }

const ROLES_DEMO = ['owner', 'editor', 'lecteur']

// Copie mutable : `retirerMembre` doit pouvoir faire disparaître un membre le
// temps de la session de contrôle visuel, sans toucher au tableau source.
let membresDemo = [
  { user_id: 1, nom: 'Rémy Eremy', email: 'remy@eremy.fr', role: 'owner' },
  { user_id: 2, nom: 'Claire Bertin', email: 'claire.bertin@gmail.com', role: 'editor' },
  { user_id: 3, nom: null, email: 'p.menard@gmail.com', role: 'lecteur' },
]

/**
 * Substitue les données de démonstration aux appels réels.
 *
 * Appelé au rendu de cette page uniquement, jamais à l'import du module :
 * `api` est partagé par toute l'application, et le patcher au chargement
 * remplacerait les vrais potagers de l'utilisateur par ceux de la démo.
 * `main.jsx` charge d'ailleurs cette page en `lazy()` pour la même raison.
 */
function simulerApi() {
  const params = new URLSearchParams(window.location.search)
  const role = ROLES_DEMO.includes(params.get('role')) ? params.get('role') : 'owner'
  const telegramLie = params.get('telegram') !== '0'

  const potagers = POTAGERS_DEMO.map((p) => (p.actif ? { ...p, role } : p))
  api.potagers = async () => ({ potagers })
  api.moi = async () => ({ ...MOI_DEMO, telegram_lie: telegramLie })

  api.genererCodeLiaisonTelegram = async () => ({
    code: '4B7K92',
    expire_le: new Date(Date.now() + 9 * 60_000 + 42_000).toISOString(),
  })
  api.listerMembres = async () => ({ membres: membresDemo })
  api.creerInvitation = async (_potagerId, rolePropose) => ({
    code: 'K7QP2M4A',
    role_propose: rolePropose,
    expire_le: new Date(Date.now() + 6 * 86_400_000).toISOString(),
  })
  api.retirerMembre = async (_potagerId, membreUserId) => {
    membresDemo = membresDemo.filter((m) => m.user_id !== membreUserId)
    return { success: true }
  }
}

/** Une vue factice : elle DÉCLARE son mot et sa barre comme le fera chaque vue (US-354 et suivantes). */
function EcranDemo({ view }) {
  const sansMot = new URLSearchParams(window.location.search).get('mot') === '0'
  useDeclarerEcran({
    mot: sansMot ? null : {
      texte: 'Gel annoncé samedi (−2 °C). Voilez la mâche et les salades du bac vendredi soir.',
      actions: [{ libelle: 'Voir les cultures', vue: 'cultures' }, { libelle: 'Noter le voilage', noter: true, principale: true }],
    },
    barre: {
      recherche: { placeholder: 'Rechercher une culture…', valeur: '', onChange: () => {} },
      filtre: { nombre: 2, onOuvrir: () => {} },
      menu: { exporterCsv: () => {}, exporterJson: () => {}, aide: () => {} },
    },
  }, [view, sansMot])
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 24 }, (_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-xl border border-border bg-card p-3">
          <PastilleEtape etape="levee" prevue due={i % 3 === 0} />
          <span className="text-[13.5px] text-txt">Culture {i + 1} · vue « {view} »</span>
        </div>
      ))}
    </div>
  )
}

function Coquille({ view, setView }) {
  const bureau = useMedia('(min-width: 900px)')
  const [compact, setCompact] = useState(false)
  const surDefilement = useCallback((e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget
    setCompact((replie) => etatReplie(scrollTop, scrollHeight - clientHeight, replie))
  }, [])
  const aller = (id) => setView(vueDeSection(id))
  return (
    <div className="flex flex-col h-dvh bg-bg">
      <TopBar view={view} onGo={aller} onRefresh={() => {}} loading={false} />
      <div className="flex min-h-0 flex-1">
        <div className="@container/page flex min-w-0 flex-1 flex-col">
          <div className="relative z-[2] shrink-0 bg-bg shadow-[0_1px_0_var(--border),0_6px_10px_-8px_rgba(22,33,12,.18)]">
            <PageHeader view={view} onGo={setView} compact={compact} />
            <BandesFixes view={view} compact={compact} onRemonter={() => {}} />
          </div>
          <main onScroll={surDefilement} className="zone-defilement relative min-h-0 flex-1 overflow-y-auto">
            <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-4 pb-28 nav:pb-24">
              {view === 'bord'
                ? <Placeholder title={navEntry(view).title} body={`Vue « ${view} » — le tableau de bord n'a pas de barre d'outils.`} />
                : <EcranDemo view={view} />}
            </div>
          </main>
        </div>
      </div>
      <BottomNav view={view} onGo={aller} />
      {bureau && <BoutonNoter variante="bureau" onGo={aller} />}
      <InfobulleEtapes />
    </div>
  )
}

export default function ShellPreview() {
  const [view, setView] = useState(VUE_PAR_DEFAUT)

  // Avant le montage des providers enfants, qui appellent api.potagers().
  simulerApi()

  return (
    <AuthContextProvider>
      <PotagerContextProvider>
       {/* [US-223] La barre du Plan lit la date de référence et la navigation. */}
       <AppContextProvider>
        <NavigationProvider vue={view} onVue={setView}>
          <CoquilleProvider>
            <Coquille view={view} setView={setView} />
          </CoquilleProvider>
        </NavigationProvider>
       </AppContextProvider>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
