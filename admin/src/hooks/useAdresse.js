import { useCallback, useEffect, useState } from 'react'
import { depuisRecherche, versRecherche } from '../lib/filtres.js'
import { vueDepuisFragment, versFragment } from '../lib/navigation.js'

/** Filtres (requête) et vue (fragment) lus dans l'adresse et réécrits à chaque changement
 *  [US-311 / CA4] : l'adresse se copie, se met en favori, survit au rechargement. */
export function useAdresse() {
  const [filtres, setFiltres] = useState(() => depuisRecherche(window.location.search))
  const [vue, setVue] = useState(() => vueDepuisFragment(window.location.hash))

  const ecrire = useCallback((f, v) => {
    const adresse = `${window.location.pathname}${versRecherche(f)}${versFragment(v)}`
    window.history.replaceState(null, '', adresse)
  }, [])

  useEffect(() => {
    const relire = () => {
      setFiltres(depuisRecherche(window.location.search))
      setVue(vueDepuisFragment(window.location.hash))
    }
    window.addEventListener('popstate', relire)
    window.addEventListener('hashchange', relire)
    return () => {
      window.removeEventListener('popstate', relire)
      window.removeEventListener('hashchange', relire)
    }
  }, [])

  const changerFiltres = useCallback((suite) => {
    const f = typeof suite === 'function' ? suite(filtres) : suite
    setFiltres(f)
    ecrire(f, vue)
  }, [ecrire, filtres, vue])

  const changerVue = useCallback((v) => {
    setVue(v)
    ecrire(filtres, v)
  }, [ecrire, filtres])

  return { filtres, vue, changerFiltres, changerVue }
}
