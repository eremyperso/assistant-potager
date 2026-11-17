/* Service worker de la PWA d'administration « Pilotage » [US-311 / CA1, CA2, CA7].
 *
 * Portée : /pilotage/ UNIQUEMENT (le fichier est servi depuis ce chemin). Il ne met en cache que la
 * coquille de l'application (page, scripts, styles, icônes) pour qu'elle s'ouvre hors ligne.
 *
 * Il ne met JAMAIS en cache une réponse de `/admin/...` (ni de `/auth/...`) : ce sont des chiffres
 * d'exploitation et des jetons, qui ne doivent pas survivre dans le navigateur. Hors ligne,
 * l'application s'ouvre et dit qu'elle n'a pas de données.
 *
 * `strategie()` est une fonction pure, testée seule (public/sw.test.js).
 */
const VERSION = 'pilotage-v1'
const CACHE = `${VERSION}-coquille`

/** 'ignorer' : le navigateur gère seul (réseau). 'navigation' : page, réseau d'abord.
 *  'ressource' : script, style ou icône de la coquille, cache d'abord puis mise à jour. */
function strategie(url, methode, mode, portee) {
  if (methode !== 'GET') return 'ignorer'
  const cible = new URL(url)
  const base = new URL(portee)
  if (cible.origin !== base.origin) return 'ignorer'
  if (!cible.pathname.startsWith(base.pathname)) return 'ignorer'
  // Ceinture et bretelles : même sous la portée, jamais d'API ni d'authentification.
  if (/\/(admin|auth)\//.test(cible.pathname)) return 'ignorer'
  return mode === 'navigate' ? 'navigation' : 'ressource'
}

if (typeof self !== 'undefined' && typeof self.addEventListener === 'function') {
  self.addEventListener('install', (evenement) => {
    evenement.waitUntil(
      caches.open(CACHE)
        .then((cache) => cache.addAll([self.registration.scope, `${self.registration.scope}manifest.webmanifest`]))
        .then(() => self.skipWaiting()),
    )
  })

  self.addEventListener('activate', (evenement) => {
    evenement.waitUntil(
      caches.keys()
        .then((noms) => Promise.all(noms.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
        .then(() => self.clients.claim()),
    )
  })

  self.addEventListener('fetch', (evenement) => {
    const requete = evenement.request
    const choix = strategie(requete.url, requete.method, requete.mode, self.registration.scope)
    if (choix === 'ignorer') return

    if (choix === 'navigation') {
      evenement.respondWith(
        fetch(requete)
          .then((reponse) => {
            const copie = reponse.clone()
            caches.open(CACHE).then((cache) => cache.put(self.registration.scope, copie))
            return reponse
          })
          .catch(() => caches.match(self.registration.scope)),
      )
      return
    }

    evenement.respondWith(
      caches.match(requete).then((enCache) => {
        const reseau = fetch(requete)
          .then((reponse) => {
            if (reponse.ok) {
              const copie = reponse.clone()
              caches.open(CACHE).then((cache) => cache.put(requete, copie))
            }
            return reponse
          })
          .catch(() => enCache)
        return enCache || reseau
      }),
    )
  })
}

// Exposé pour le test unitaire (Node) ; sans effet dans le navigateur.
if (typeof module !== 'undefined') module.exports = { strategie, CACHE }
