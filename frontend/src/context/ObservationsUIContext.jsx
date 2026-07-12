import { createContext, useContext, useState } from 'react'

/**
 * [US-039] Un seul panneau d'observations ouvert à la fois sur un écran donné
 * (Plan ou Stocks) — ouvrir un nouveau bloc referme automatiquement le précédent.
 */
const ObservationsUIContext = createContext(null)

export function ObservationsUIProvider({ children }) {
  const [openKey, setOpenKey] = useState(null)
  return (
    <ObservationsUIContext.Provider value={{ openKey, setOpenKey }}>
      {children}
    </ObservationsUIContext.Provider>
  )
}

export function useObservationsUI() {
  const ctx = useContext(ObservationsUIContext)
  if (!ctx) throw new Error('useObservationsUI doit être utilisé dans un <ObservationsUIProvider>')
  return ctx
}
