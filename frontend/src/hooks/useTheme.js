import { useState, useEffect, useCallback } from 'react'

// État partagé entre tous les appels de useTheme() : sans ce singleton, chaque
// composant (App, TopBar, Stats...) avait son propre useState local et ne se
// synchronisait jamais avec les autres tant qu'il n'était pas remonté — un
// toggle déclenché depuis TopBar changeait bien les variables CSS (classe
// .dark globale) mais pas le booléen `theme` lu ailleurs (ex: Stats.jsx).

let currentTheme = localStorage.getItem('theme') || 'light'
const listeners = new Set()

function applyTheme(theme) {
  const root = document.documentElement
  if (theme === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
  localStorage.setItem('theme', theme)
}

applyTheme(currentTheme)

function setGlobalTheme(theme) {
  currentTheme = theme
  applyTheme(theme)
  listeners.forEach(fn => fn(theme))
}

export function useTheme() {
  const [theme, setTheme] = useState(currentTheme)

  useEffect(() => {
    listeners.add(setTheme)
    return () => listeners.delete(setTheme)
  }, [])

  const toggle = useCallback(() => {
    setGlobalTheme(currentTheme === 'dark' ? 'light' : 'dark')
  }, [])

  return { theme, toggle }
}
