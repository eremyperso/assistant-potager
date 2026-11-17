import { useCallback, useState } from 'react'

// Même clé que l'application des jardiniers (même origine) : le thème choisi suit.
const lire = () => { try { return localStorage.getItem('theme') || 'light' } catch { return 'light' } }

function appliquer(theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  try { localStorage.setItem('theme', theme) } catch { /* préférence non gardée */ }
}

appliquer(lire())

export function useTheme() {
  const [theme, setTheme] = useState(lire)
  const basculer = useCallback(() => {
    const suivant = theme === 'dark' ? 'light' : 'dark'
    appliquer(suivant)
    setTheme(suivant)
  }, [theme])
  return { theme, basculer }
}
