// Retour d'action de la PWA après le dépôt d'un geste — `npm test`.
//
// Le dépôt n'écrit rien : la notification ne doit jamais dire « enregistré ».
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { notificationDepot, notificationEchec, resumeGeste } from './notificationsGeste.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')
const geste = { action: 'semis', culture: 'Tomate', parcelleNom: 'Serre' }

test('le résumé du geste ignore ce qui manque', () => {
  assert.equal(resumeGeste(geste), 'semis — Tomate — Serre')
  assert.equal(resumeGeste({ action: 'récolte' }), 'récolte')
  assert.equal(resumeGeste(null), '')
})

test('un dépôt réussi dit « préparé » et « rien n’est encore enregistré »', () => {
  const n = notificationDepot({ en_attente: 1 }, geste)
  assert.equal(n.tone, 'brand')
  assert.equal(n.titre, 'Geste préparé')
  assert.match(n.message, /rien n’est encore enregistré/)
  assert.match(n.message, /1 geste en attente/)
  assert.doesNotMatch(n.titre, /enregistré/)
})

test('le compte est au pluriel au-delà d’un geste', () => {
  assert.match(notificationDepot({ en_attente: 3 }, geste).message, /3 gestes en attente/)
})

test('un doublon est signalé en avertissement, pas en erreur', () => {
  const n = notificationDepot({ doublon: true, en_attente: 2 }, geste)
  assert.equal(n.tone, 'amber')
  assert.match(n.titre, /identique/)
})

test('un échec reste en rouge et propose de réessayer', () => {
  const relancer = () => {}
  const n = notificationEchec(new Error('Action non ouverte.'), relancer)
  assert.equal(n.tone, 'red')
  assert.equal(n.message, 'Action non ouverte.')
  assert.equal(n.action.libelle, 'Réessayer')
  assert.equal(n.action.onClick, relancer)
})

test('un échec réseau est traduit en phrase, pas en « Failed to fetch »', () => {
  const n = notificationEchec(new TypeError('Failed to fetch'), null)
  assert.match(n.message, /injoignable/)
  assert.equal(n.action, null)
})

test('le bouton de geste notifie le dépôt ET l’échec', () => {
  const src = lire('../components/BoutonGeste.jsx')
  assert.match(src, /notifier\(notificationDepot\(res, geste\)\)/)
  assert.match(src, /notifier\(notificationEchec\(e, lancer\)\)/)
})

test('le fournisseur de notifications enveloppe l’application', () => {
  assert.match(lire('../App.jsx'), /<NotificationsProvider>/)
})
