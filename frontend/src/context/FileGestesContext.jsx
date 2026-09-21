// [US-224 / CA22] La file de gestes, vue de l'application.
//
// « L'application montre combien de gestes attendent, en permanence et sur tous
// les écrans concernés — une file invisible serait une file oubliée. » Un
// contexte, et non un chargement par vue : le compte doit être le même partout,
// et aucun écran ne doit avoir à penser à le demander.
//
// ⚠️ **Aucune interrogation périodique.** Le compte est relu à l'ouverture, au
// retour sur l'onglet (une fois par retour — le jardinier revient de Telegram
// où il vient peut-être de confirmer), et après un dépôt. Rien d'autre : un
// `setInterval` réveillerait le serveur toutes les N secondes pour un chiffre
// qui ne change qu'à l'initiative du jardinier.
//
// La file se CONSULTE et s'y RETIRE un geste (CA23) ; elle ne s'y confirme
// jamais — la confirmation reste au compagnon (arbitrage A16), et c'est ce qui
// empêche cette US d'ouvrir un second chemin d'écriture.
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api.js'

const ContexteFile = createContext(null)

const VIDE = { enAttente: [], sortis: [], nbEnAttente: 0, relancesActives: true }

export function FileGestesProvider({ children }) {
  const [file, setFile] = useState(VIDE)
  const [chargee, setChargee] = useState(false)

  const recharger = useCallback(async () => {
    try {
      const res = await api.lireFileGestes()
      setFile({
        enAttente: res?.en_attente ?? [],
        sortis: res?.sortis ?? [],
        nbEnAttente: res?.nb_en_attente ?? 0,
        relancesActives: res?.relances_actives !== false,
      })
    } catch {
      // Une file illisible n'est pas une erreur d'écran : le bandeau disparaît,
      // le reste de l'application continue. Le compte se rétablira au prochain
      // retour d'onglet.
      setFile(VIDE)
    } finally {
      setChargee(true)
    }
  }, [])

  useEffect(() => { recharger() }, [recharger])

  // [CA22] Une lecture par retour d'onglet, et une seule. Le jardinier revient
  // du compagnon : ce qu'il vient d'y confirmer doit avoir disparu du compte.
  useEffect(() => {
    const auRetour = () => { if (document.visibilityState === 'visible') recharger() }
    document.addEventListener('visibilitychange', auRetour)
    return () => document.removeEventListener('visibilitychange', auRetour)
  }, [recharger])

  const retirer = useCallback(async (id) => {
    await api.retirerGesteDeLaFile(id)
    await recharger()
  }, [recharger])

  // [CA18] Ce qui a été vidé a été vu : la trace peut partir. C'est l'écran qui
  // le sait, jamais le serveur — d'où cet acquittement explicite.
  const acquitterSortis = useCallback(async () => {
    try { await api.acquitterGestesSortis() } catch { /* sans conséquence */ }
    await recharger()
  }, [recharger])

  return (
    <ContexteFile.Provider value={{ ...file, chargee, recharger, retirer, acquitterSortis }}>
      {children}
    </ContexteFile.Provider>
  )
}

/**
 * La file du compte. Sans fournisseur au-dessus — une prévisualisation, un test
 * de composant isolé — rend une file vide plutôt qu'une erreur : un écran ne
 * doit jamais casser parce qu'il ignore qu'il existe une file.
 */
export function useFileGestes() {
  return useContext(ContexteFile) ?? {
    ...VIDE, chargee: false,
    recharger: async () => {}, retirer: async () => {}, acquitterSortis: async () => {},
  }
}
