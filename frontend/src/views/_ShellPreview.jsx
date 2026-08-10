import { useState } from 'react'
import { api } from '../lib/api.js'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import TopBar from '../components/TopBar.jsx'
import PageHeader from '../components/PageHeader.jsx'
import BottomNav from '../components/BottomNav.jsx'
import { Placeholder } from '../components/ui'
import { VUE_PAR_DEFAUT, navEntry } from '../navigation.js'

/**
 * Page de contrôle visuel de la coquille applicative [US-053, US-054].
 *
 * Monte la vraie navigation (TopBar, PotagerMenu, PageHeader, tuiles, BottomNav)
 * sans dépendre du backend : chaque section rend un Placeholder et la liste des
 * potagers est simulée, ce qui permet de valider la structure isolément.
 * Non référencée par la navigation applicative.
 */

const POTAGERS_DEMO = [
  { id: 1, nom: 'Potager de démonstration', actif: true, role: 'owner', nb_parcelles: 5, nb_membres: 3 },
  { id: 2, nom: 'Jardin partagé des Coteaux', actif: false, role: 'editor', nb_parcelles: 12, nb_membres: 8 },
  { id: 3, nom: 'Balcon', actif: false, role: 'lecteur', nb_parcelles: 1, nb_membres: 1 },
]

/**
 * Substitue les données de démonstration à l'appel réel.
 *
 * Appelé au rendu de cette page uniquement, jamais à l'import du module :
 * `api` est partagé par toute l'application, et le patcher au chargement
 * remplacerait les vrais potagers de l'utilisateur par ceux de la démo.
 * `main.jsx` charge d'ailleurs cette page en `lazy()` pour la même raison.
 */
function simulerApiPotagers() {
  api.potagers = async () => ({ potagers: POTAGERS_DEMO })
}

export default function ShellPreview() {
  const [view, setView] = useState(VUE_PAR_DEFAUT)
  const nav = navEntry(view)

  // Avant le montage des providers enfants, qui appellent api.potagers().
  simulerApiPotagers()

  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <div className="flex flex-col h-dvh bg-bg">
          <TopBar view={view} onGo={setView} onRefresh={() => {}} loading={false} />
          <main className="flex-1 overflow-y-auto min-h-0">
            <PageHeader view={view} onGo={setView} />
            <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-4 pb-7">
              <Placeholder
                title={nav.title}
                body={`Vue « ${view} » — contrôle visuel de la coquille de navigation.`}
              />
            </div>
          </main>
          <BottomNav view={view} onGo={setView} />
        </div>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
