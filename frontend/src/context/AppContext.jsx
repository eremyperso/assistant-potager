// [US-031 CA1-CA4] Contexte global — date de référence persistée en localStorage.
import { createContext, useContext, useState } from 'react'

const AppContext = createContext(null)

const LS_KEY = 'potager_date_ref'

function readLS() {
  try { return localStorage.getItem(LS_KEY) || null }
  catch { return null }
}

export function AppContextProvider({ children }) {
  const [dateRef, setDateRefState] = useState(readLS)

  function setDateRef(v) {
    setDateRefState(v)
    try {
      if (v) localStorage.setItem(LS_KEY, v)
      else   localStorage.removeItem(LS_KEY)
    } catch {}
  }

  return (
    <AppContext.Provider value={{ dateRef, setDateRef }}>
      {children}
    </AppContext.Provider>
  )
}

export function useDateRef() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useDateRef doit être utilisé dans AppContextProvider')
  return ctx
}
