// [US-290] La demande de connexion d'un assistant IA survit à la connexion du jardinier.
// Exécuté par `npm test` (`node --test`) : un faux sessionStorage tient lieu de navigateur.
import test from 'node:test'
import assert from 'node:assert/strict'

const memoire = new Map()
globalThis.window = {
  sessionStorage: {
    getItem: (k) => (memoire.has(k) ? memoire.get(k) : null),
    setItem: (k, v) => memoire.set(k, String(v)),
    removeItem: (k) => memoire.delete(k),
  },
}

const {
  CLE_DEMANDE, capterDemandeAdresse, demandeEnAttente, oublierDemande,
  potagersPreselectionnes, ecriturePossible,
} = await import('./connecteurIa.js')

function histoireEspionne() {
  const appels = []
  return { appels, replaceState: (...args) => appels.push(args) }
}

test('[US-290] capte la demande de /connecteur-ia, la garde et nettoie l’adresse', () => {
  memoire.clear()
  const histoire = histoireEspionne()
  const demande = capterDemandeAdresse({ pathname: '/connecteur-ia', search: '?demande=abc.def.ghi' }, histoire)
  assert.equal(demande, 'abc.def.ghi')
  assert.equal(memoire.get(CLE_DEMANDE), 'abc.def.ghi')
  assert.deepEqual(histoire.appels, [[{}, '', '/']])
})

test('[US-290] ignore toute autre adresse', () => {
  const histoire = histoireEspionne()
  assert.equal(capterDemandeAdresse({ pathname: '/auth/callback', search: '' }, histoire), null)
  assert.deepEqual(histoire.appels, [])
})

test('[US-290] retrouve la demande après un retour Google, puis l’oublie', () => {
  memoire.clear()
  memoire.set(CLE_DEMANDE, 'gardee')
  assert.equal(demandeEnAttente(null), 'gardee')
  assert.equal(demandeEnAttente('adresse'), 'adresse')
  oublierDemande()
  assert.equal(demandeEnAttente(null), null)
})

test('[US-290] coche d’office le potager actif, sinon l’unique potager', () => {
  assert.deepEqual(potagersPreselectionnes([{ id: 1 }, { id: 2, actif: true }]), [2])
  assert.deepEqual(potagersPreselectionnes([{ id: 7 }]), [7])
  assert.deepEqual(potagersPreselectionnes([{ id: 1 }, { id: 2 }]), [])
})

test('[US-290] n’ouvre l’écriture que sur un potager où l’on n’est pas lecteur', () => {
  const potagers = [{ id: 1, role: 'owner' }, { id: 2, role: 'lecteur' }]
  assert.equal(ecriturePossible(potagers, [2]), false)
  assert.equal(ecriturePossible(potagers, [1, 2]), true)
  assert.equal(ecriturePossible(potagers, []), false)
})
