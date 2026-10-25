// Règle des temps : logique pure de la réglette de date — `npm test`.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ajouterJours, construireRegle, ecartEnJours, estToucheAujourdhui, graduations, indexDepuisDefilement,
  indexDuJour, jourDeIndex, libelleCourt, libelleLong, mentionDuJour, pasDuClavier, versDateRef,
} from './regleTemps.js'

const AUJ = '2026-10-25'

test('la réglette court du 1er du mois, 24 mois avant, jusqu\'à aujourd\'hui compris', () => {
  const r = construireRegle(AUJ)
  assert.equal(r.debut, '2024-10-01')
  assert.equal(r.fin, AUJ)
  assert.equal(r.n, ecartEnJours('2024-10-01', AUJ) + 1)
  assert.equal(jourDeIndex(r, 0), '2024-10-01')
  assert.equal(jourDeIndex(r, r.n - 1), AUJ)
})

test('le début passe correctement l\'année (janvier moins deux mois)', () => {
  assert.equal(construireRegle('2026-01-15', 2).debut, '2025-11-01')
})

test('un jour retrouve son index, ramené dans les bornes', () => {
  const r = construireRegle(AUJ)
  assert.equal(indexDuJour(r, '2024-10-01'), 0)
  assert.equal(indexDuJour(r, AUJ), r.n - 1)
  assert.equal(indexDuJour(r, '2020-01-01'), 0)
  assert.equal(indexDuJour(r, '2030-01-01'), r.n - 1)
  assert.equal(indexDuJour(r, null), r.n - 1)
})

test('aujourd\'hui s\'écrit null dans la date de référence, les autres jours en ISO', () => {
  const r = construireRegle(AUJ)
  assert.equal(versDateRef(r, r.n - 1), null)
  assert.equal(versDateRef(r, r.n), null)
  assert.equal(versDateRef(r, r.n - 2), '2026-10-24')
  assert.equal(versDateRef(r, 0), '2024-10-01')
})

test('le défilement se lit en jours entiers, sans dépasser la réglette', () => {
  const r = construireRegle(AUJ)
  assert.equal(indexDepuisDefilement(r, 0, 10), 0)
  assert.equal(indexDepuisDefilement(r, 24, 10), 2)
  assert.equal(indexDepuisDefilement(r, 26, 10), 3)
  assert.equal(indexDepuisDefilement(r, -50, 10), 0)
  assert.equal(indexDepuisDefilement(r, 1e9, 10), r.n - 1)
})

test('les libellés sont en français, le 1er s\'écrit « 1er »', () => {
  assert.equal(libelleLong('2026-10-19'), 'Lun. 19 oct. 2026')
  assert.equal(libelleCourt('2026-10-19'), 'lun. 19 oct.')
  assert.equal(libelleCourt('2026-11-01'), 'dim. 1er nov.')
  assert.equal(libelleLong('2026-03-07'), 'Sam. 7 mars 2026')
})

test('« historique » dès qu\'on lit un jour passé, rien sur aujourd\'hui', () => {
  assert.equal(mentionDuJour('2026-10-24', AUJ), 'historique')
  assert.equal(mentionDuJour(AUJ, AUJ), '')
})

test('un trait par jour : le 1er du mois porte son nom, le lundi est plus long', () => {
  const r = construireRegle('2026-02-10', 1)   // du 1er janvier 2026 au 10 février
  const g = graduations(r)
  assert.equal(g.length, r.n)
  assert.deepEqual(g[0], { i: 0, type: 'mois', etiquette: 'janv. 2026' })
  const fevrier = g[ecartEnJours(r.debut, '2026-02-01')]
  assert.deepEqual(fevrier, { i: 31, type: 'mois', etiquette: 'févr.' })
  const lundi = g[ecartEnJours(r.debut, '2026-01-05')]   // un lundi
  assert.equal(lundi.type, 'semaine')
  assert.equal(g[ecartEnJours(r.debut, '2026-01-06')].type, 'jour')
})

test('le clavier saute d\'un jour, d\'une semaine avec Maj, et ignore le reste', () => {
  assert.equal(pasDuClavier('ArrowRight'), 1)
  assert.equal(pasDuClavier('ArrowLeft'), -1)
  assert.equal(pasDuClavier('ArrowLeft', true), -7)
  assert.equal(pasDuClavier('ArrowRight', true), 7)
  assert.equal(pasDuClavier('a'), null)
  assert.equal(estToucheAujourdhui('t'), true)
  assert.equal(estToucheAujourdhui('Home'), true)
  assert.equal(estToucheAujourdhui('x'), false)
})

test('ajouterJours traverse les fins de mois et d\'année', () => {
  assert.equal(ajouterJours('2026-12-31', 1), '2027-01-01')
  assert.equal(ajouterJours('2026-03-01', -1), '2026-02-28')
})
