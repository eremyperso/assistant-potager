// Contrôle visuel de la règle des temps — /regle-temps, sans backend.
// [US-353 / CA10] Reproduit la coquille (App.jsx) : la barre d'outils porte le bouton date et la
// règle des temps s'ouvre JUSTE SOUS elle. Le bandeau de contrôle relit `dateRef`.
import { AppContextProvider, useDateRef } from '../context/AppContext.jsx'
import BarreOutils from '../components/BarreOutils.jsx'
import RegleTemps from '../components/RegleTemps.jsx'
import { barreEffective } from '../lib/coquille.js'

function Page() {
  const { dateRef } = useDateRef()
  return (
    <div className="flex flex-col h-dvh bg-bg">
      <div className="@container/page shrink-0 bg-bg px-4 nav:px-6 pb-3 pt-4 max-w-[1320px] w-full mx-auto">
        <h1 className="font-serif text-[26px] font-bold text-txt">Règle des temps</h1>
        <div className="mt-3.5">
          <BarreOutils barre={barreEffective('cultures', { recherche: { placeholder: 'Rechercher', valeur: '', onChange: () => {} } })} />
          <RegleTemps />
        </div>
      </div>
      <main className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-2 pb-7">
          <span data-testid="date-ref" className="text-[12.5px] text-txt2">
            dateRef = <b>{dateRef ?? 'null (aujourd’hui)'}</b>
          </span>
        </div>
      </main>
      <div className="shrink-0 h-[68px] bg-surface border-t border-border text-[11px] text-txt3 flex items-center justify-center">
        barre d’onglets (simulée)
      </div>
    </div>
  )
}

export default function RegleTempsPreview() {
  return (
    <AppContextProvider>
      <Page />
    </AppContextProvider>
  )
}
