import { useState } from 'react'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import TopBar from '../components/TopBar.jsx'
import PageHeader from '../components/PageHeader.jsx'
import BottomNav from '../components/BottomNav.jsx'
import { Placeholder } from '../components/ui'
import { VUE_PAR_DEFAUT, navEntry } from '../navigation.js'

/**
 * Page de contrôle visuel de la coquille applicative [US-053].
 *
 * Monte la vraie navigation (TopBar, PageHeader, tuiles, BottomNav) sans
 * dépendre des données métier : chaque section rend un Placeholder, ce qui
 * permet de valider la structure de navigation isolément.
 * Non référencée par la navigation applicative.
 */
export default function ShellPreview() {
  const [view, setView] = useState(VUE_PAR_DEFAUT)
  const nav = navEntry(view)

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
