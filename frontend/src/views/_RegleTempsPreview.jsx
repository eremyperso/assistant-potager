// Contrôle visuel de la règle des temps — /regle-temps, sans backend.
// Reproduit la disposition de la coquille (App.jsx) : contenu qui défile, puis
// la réglette, puis la barre basse. Le bandeau de contrôle relit `dateRef`.
import { AppContextProvider, useDateRef } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import RegleTemps from '../components/RegleTemps.jsx'

function Page() {
  const { dateRef } = useDateRef()
  return (
    <div className="flex flex-col h-dvh bg-bg">
      <main className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-4 pb-7 flex flex-col gap-3">
          <h1 className="font-serif text-[26px] font-bold text-txt">Règle des temps</h1>
          <div className="flex items-center gap-3 flex-wrap">
            <DateRefPicker />
            <span data-testid="date-ref" className="text-[12.5px] text-txt2">
              dateRef = <b>{dateRef ?? 'null (aujourd’hui)'}</b>
            </span>
          </div>
        </div>
      </main>
      <RegleTemps />
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
