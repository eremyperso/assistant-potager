// [US-205 / US-361] Ce que l'écran Cultures du socle emploie : libellé de fenêtre et frise de l'espèce.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { libelleFenetre, friseDeLigne, normaliser } from './cultures.js'

const L = (over = {}) => ({
  culture: 'tomate', nom_culture: 'Tomate', hors_referentiel: false, famille: 'Solanacée',
  au_potager: true, a_calendrier: true, mois_zone: {}, mois_actifs: [], nb_varietes: 1,
  varietes: ['cerise'], nb_parcelles: 1, repartition_phases: {}, phase_plus_avancee: 'en_recolte',
  nb_lots_pepiniere: 0,
  fenetre_etat: 'plus_tard', fenetre_geste: 'semis_pepiniere', fenetre_mois: [2, 3],
  ...over,
})

test('libelleFenetre [CA5] — « maintenant » en gras', () => {
  const r = libelleFenetre(L({ fenetre_etat: 'maintenant', fenetre_geste: 'semis_pleine_terre', fenetre_mois: [4, 5, 6] }))
  assert.deepEqual(r, { gras: true, texte: 'Semer en place maintenant' })
})

test('libelleFenetre [CA5] — « bientôt » en minuscule avec la plage de mois', () => {
  const r = libelleFenetre(L({ fenetre_etat: 'bientot', fenetre_geste: 'plantation', fenetre_mois: [10, 11] }))
  assert.deepEqual(r, { gras: false, texte: 'bientôt : planter octobre → novembre' })
})

test('libelleFenetre [CA5] — « prochaine fenêtre » sinon', () => {
  const r = libelleFenetre(L({ fenetre_etat: 'plus_tard', fenetre_geste: 'semis_pepiniere', fenetre_mois: [1, 2] }))
  assert.deepEqual(r, { gras: false, texte: 'prochaine fenêtre : semer en pépinière janvier → février' })
})

test('libelleFenetre [CA6] — null sans calendrier pour la zone', () => {
  assert.equal(libelleFenetre(L({ a_calendrier: false, fenetre_etat: 'aucune', fenetre_geste: null })), null)
})

test('friseDeLigne [CA5] — mois 1..12 du serveur convertis en index 0-based', () => {
  const frise = friseDeLigne(L({ mois_zone: { semis_pleine_terre: [4, 5], recolte: [7, 8] } }))
  assert.deepEqual(frise.pleineTerre, [3, 4])
  assert.deepEqual(frise.rec, [6, 7])
  assert.deepEqual(frise.pepiniere, [])
})

test('[US-361] normaliser — sans accents ni casse', () => {
  assert.equal(normaliser('Épinard Été'), 'epinard ete')
})

test('[US-361] l’ancien écran n’est plus : ni carte, ni tri par confiance, ni message de confiance indisponible', () => {
  const src = readFileSync(new URL('./cultures.js', import.meta.url), 'utf8')
  for (const mot of ['comparerConfiance', 'TRI_CONFIANCE', 'messageConfianceIndisponible', 'nomAccessibleCarte', 'sousTitreCarte', 'presenceCarte']) {
    assert.doesNotMatch(src, new RegExp(mot), mot)
  }
})
