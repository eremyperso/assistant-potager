// [US-201 / CA9] La correspondance « élément appuyé → destination et intention ».
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CHOIX_AJOUT, destinationRang, destinationNonLocalisee, destinationFicheParcelle,
  destinationPepiniere, destinationJournal,
} from './planVue.js'

const carte = { id: 7, nom: 'planche-ombre', pepiniere: false }
const occupe = { numero: 2, libre: false, culture: 'tomate', variete: 'cerise' }
const libre = { numero: 5, libre: true, culture: '' }

test('[CA1, I2] un rang occupé ouvre la fiche de sa culture, la parcelle en contexte', () => {
  assert.deepEqual(destinationRang(occupe, carte, { role: 'viewer' }), {
    type: 'culture', culture: 'tomate', parcelleId: 7, nomParcelle: 'planche-ombre', rang: 2,
  })
})

test('[CA3, I3] un rang libre propose d’ajouter une culture à qui peut écrire', () => {
  for (const role of ['owner', 'editor']) {
    assert.deepEqual(destinationRang(libre, carte, { role }), {
      type: 'ajout', parcelleId: 7, nomParcelle: 'planche-ombre', rang: 5,
    })
  }
})

test('[CA3, RT11] un rang libre n’est pas actionnable en lecture seule ni sans rôle connu', () => {
  assert.equal(destinationRang(libre, carte, { role: 'viewer' }), null)
  assert.equal(destinationRang(libre, carte, {}), null)
  assert.equal(destinationRang(libre, carte), null)
})

test('[I3] les deux choix sont Semer en place (pleine terre) et Planter', () => {
  assert.deepEqual(CHOIX_AJOUT.map((c) => c.libelle), ['Semer en place', 'Planter'])
  assert.deepEqual(CHOIX_AJOUT[0].geste, { action: 'semis', contexteSemis: 'pleine_terre' })
  assert.deepEqual(CHOIX_AJOUT[1].geste, { action: 'plantation', contexteSemis: null })
})

test('[CA7] une culture non localisée ouvre sa fiche, sans contexte de parcelle', () => {
  assert.deepEqual(destinationNonLocalisee({ culture: 'courgette' }), {
    type: 'culture', culture: 'courgette', parcelleId: null, nomParcelle: '', rang: null,
  })
  assert.equal(destinationNonLocalisee({ culture: '' }), null)
})

test('[CA4, I4] « Fiche parcelle → » ouvre l’onglet Parcelles sur cette parcelle', () => {
  assert.deepEqual(destinationFicheParcelle(carte), { type: 'aller', vue: 'plan', intention: { parcelle: 7 } })
})

test('[CA4, I5] une seule pépinière : l’onglet « Aujourd’hui »', () => {
  const serre = { id: 1, nom: 'serre', pepiniere: true }
  assert.deepEqual(destinationPepiniere(serre, [carte, serre]), {
    type: 'aller', vue: 'pepiniere', intention: { onglet: 'aujourdhui', emplacement: 'serre' },
  })
})

test('[CA4, I5] plusieurs pépinières : l’onglet « Emplacements », sur celle appuyée', () => {
  const serre = { id: 1, nom: 'serre', pepiniere: true }
  const chassis = { id: 2, nom: 'châssis froid', pepiniere: true }
  assert.deepEqual(destinationPepiniere(serre, [carte, serre, chassis]), {
    type: 'aller', vue: 'pepiniere', intention: { onglet: 'emplacements', emplacement: 'serre' },
  })
})

test('[CA4, I6] « Journal du jour » filtre sur la date de référence', () => {
  assert.deepEqual(destinationJournal('2026-09-24'), {
    type: 'aller', vue: 'journal', intention: { date: '2026-09-24' },
  })
})
