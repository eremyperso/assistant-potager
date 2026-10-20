// [US-220 / CA8] La carte « À semer » : un niveau par type de pépinière, en mots.
import test from 'node:test'
import assert from 'node:assert/strict'
import { niveauxParPepiniere } from './pepiniere.js'

const niveau = (type, etoiles) => ({
  pepiniere: { type, libelle: `pépinière ${type}`, nom: type === 'chaude' ? 'serre' : 'châssis' },
  etoiles, affichage: '★'.repeat(etoiles), score: null,
})

test('[US-220 / CA8] deux types : un niveau chacun, écrit en mots puis en étoiles', () => {
  const tomate = { culture: 'tomate', confiance: { etoiles: 3, par_pepiniere: [niveau('chaude', 3), niveau('froide', 2)] } }
  assert.deepEqual(niveauxParPepiniere(tomate), [
    'pépinière chaude : confiance élevée ★★★',
    'pépinière froide : confiance moyenne ★★☆',
  ])
})

test('[US-220 / CA8] une seule évaluation, ou une API d\'avant US-220 : rien de plus', () => {
  assert.deepEqual(niveauxParPepiniere({ culture: 'tomate', confiance: { etoiles: 3, par_pepiniere: [] } }), [])
  assert.deepEqual(niveauxParPepiniere({ culture: 'mâche', fenetre: 'août – oct.' }), [])
  assert.deepEqual(niveauxParPepiniere(null), [])
})

test('[US-220 / CA8] un type sans score ne s\'invente pas d\'étoiles', () => {
  const c = { confiance: { par_pepiniere: [niveau('chaude', 3), { ...niveau('froide', 1), etoiles: null }] } }
  assert.deepEqual(niveauxParPepiniere(c), ['pépinière chaude : confiance élevée ★★★'])
})
