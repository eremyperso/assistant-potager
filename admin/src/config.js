// Configuration de build : seul fichier à lire `import.meta.env` (les modules de `lib/` restent
// testables sous Node). En production l'API est la même origine que l'application (`/pilotage/`
// est servie par FastAPI) ; en développement, l'API locale.
export const URL_API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8001' : '')

/** « dev » ou « prod » — affiché dans l'en-tête (brief §4.1). */
export function environnement(hote = window.location.hostname) {
  return /^(localhost|127\.|dev\.)/.test(hote) ? 'dev' : 'prod'
}
