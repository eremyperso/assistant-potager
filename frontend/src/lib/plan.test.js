// [US-060] Règles d'affichage de l'écran Plan — exécuté par `npm test`
// (`node --test`, sans dépendance de test supplémentaire).
//
// Ce fichier couvre le volet **logique** de l'US : sélection maître-détail,
// filtre, unités, mois de référence et métadonnées horticoles. La conformité
// visuelle à la maquette relève du rapport de validation aux trois résolutions,
// pas de ces tests.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  occTint, pctDe, estEnPlants, totalPlants, formatUnite, expositionAffichable, moisDeLaDate,
  filtrerParcelles, parcelleSelectionnee,
} from './plan.js'

/** Parcelle minimale : seuls les champs utiles au scénario sont renseignés. */
const parcelle = (champs) => ({
  id: 1, nom: 'Parcelle', exposition: null, superficie_m2: null,
  cultures: [], occupation_pct: null, has_observations: false, nb_observations: 0,
  ...champs,
})

const culture = (champs) => ({
  culture: 'tomate', variete: null, nb_plants: 0, unite: 'plants',
  type_organe: 'reproducteur', has_observations: false, nb_observations: 0,
  ...champs,
})

// ── CA12 — code couleur d'occupation ─────────────────────────────────────────

test('[CA12] le code couleur d’occupation garde ses seuils', async (t) => {
  await t.test('sous 55 % : vert (marque)', () => {
    assert.equal(occTint(0), 'brand')
    assert.equal(occTint(54), 'brand')
  })

  await t.test('de 55 à 79 % : ambre', () => {
    assert.equal(occTint(55), 'amber')
    assert.equal(occTint(79), 'amber')
  })

  await t.test('à partir de 80 % : rouge — scénario « parcelle occupée à 85 % »', () => {
    assert.equal(occTint(80), 'red')
    assert.equal(occTint(85), 'red')
  })

  await t.test('une parcelle sans superficie déclarée se lit comme 0 %', () => {
    assert.equal(pctDe(parcelle({ occupation_pct: null })), 0)
    assert.equal(pctDe(parcelle({ occupation_pct: 62 })), 62)
  })
})

// ── CA6 / CA18 — unités ──────────────────────────────────────────────────────

test('[CA6] le total de plants n’agrège que les cultures comptées en plants', async (t) => {
  await t.test('plants et pieds comptent, m² et graines non', () => {
    assert.equal(estEnPlants('plants'), true)
    assert.equal(estEnPlants('Pieds'), true)
    assert.equal(estEnPlants('m²'), false)
    assert.equal(estEnPlants('graines'), false)
    assert.equal(estEnPlants(null), false)
  })

  await t.test('scénario « carotte semée sur 2 m² » : la carotte n’entre pas dans le total', () => {
    const cultures = [
      culture({ culture: 'tomate', nb_plants: 14, unite: 'plants' }),
      culture({ culture: 'carotte', nb_plants: 2, unite: 'm²' }),
      culture({ culture: 'betterave', nb_plants: 42, unite: 'graines' }),
    ]
    assert.equal(totalPlants(cultures), 14)
  })

  await t.test('aucune culture en plants : total nul, jamais une conversion', () => {
    assert.equal(totalPlants([culture({ nb_plants: 2, unite: 'm²' })]), 0)
    assert.equal(totalPlants([]), 0)
  })

  await t.test('la surface saisie « m2 » par le bot est bien une surface', () => {
    assert.equal(estEnPlants('m2'), false)
    assert.equal(totalPlants([culture({ nb_plants: 2, unite: 'm2' })]), 0)
  })
})

test('[CA18] la quantité est affichée avec son unité de saisie', async (t) => {
  await t.test('« m2 » s’écrit « m² » à l’écran, sans changer de valeur', () => {
    assert.equal(formatUnite('m2'), 'm²')
    assert.equal(formatUnite('M2'), 'm²')
  })

  await t.test('les autres unités sont rendues telles quelles', () => {
    assert.equal(formatUnite('plants'), 'plants')
    assert.equal(formatUnite('graines'), 'graines')
    assert.equal(formatUnite('m²'), 'm²')
  })
})

// ── CA4 — pastilles de caractéristiques ──────────────────────────────────────

test('[CA4] une exposition inexploitable est omise, pas affichée telle quelle', async (t) => {
  await t.test('une exposition renseignée est rendue telle quelle', () => {
    assert.equal(expositionAffichable('Nord'), 'Nord')
    assert.equal(expositionAffichable(' Sud-ouest '), 'Sud-ouest')
  })

  await t.test('la chaîne « NULL » d’une saisie ancienne ne devient pas une pastille', () => {
    assert.equal(expositionAffichable('NULL'), null)
    assert.equal(expositionAffichable('null'), null)
    assert.equal(expositionAffichable(''), null)
    assert.equal(expositionAffichable(null), null)
  })
})

// ── CA10 — mois mis en évidence ──────────────────────────────────────────────

test('[CA10] la frise suit la date de référence, pas l’horloge du navigateur', async (t) => {
  await t.test('scénario « date de référence reculée au 15 mars » : mars (index 2)', () => {
    assert.equal(moisDeLaDate('2026-03-15'), 2)
  })

  await t.test('les bornes de l’année sont justes', () => {
    assert.equal(moisDeLaDate('2026-01-01'), 0)
    assert.equal(moisDeLaDate('2026-12-31'), 11)
  })

  await t.test('date absente ou illisible : repli sur le mois courant de MonthStrip', () => {
    assert.equal(moisDeLaDate(null), undefined)
    assert.equal(moisDeLaDate(''), undefined)
    assert.equal(moisDeLaDate('pas-une-date'), undefined)
    assert.equal(moisDeLaDate('2026-13-01'), undefined)
  })
})

// ── CA16 — filtre culture ────────────────────────────────────────────────────

test('[CA16] le filtre porte sur le nom de parcelle comme sur ses cultures', async (t) => {
  const serre = parcelle({
    id: 3, nom: 'Serre',
    cultures: [culture({ culture: 'tomate', variete: 'Cerise' }), culture({ culture: 'basilic' })],
  })
  const maison = parcelle({
    id: 2, nom: 'Maison',
    cultures: [culture({ culture: 'fraise' })],
  })

  await t.test('recherche vide : la liste est rendue telle quelle', () => {
    assert.deepEqual(filtrerParcelles([serre, maison], ''), [serre, maison])
  })

  await t.test('une parcelle retenue par son nom garde toutes ses cultures', () => {
    const res = filtrerParcelles([serre, maison], 'serre')
    assert.equal(res.length, 1)
    assert.equal(res[0].cultures.length, 2)
  })

  await t.test('une parcelle retenue par une culture ne montre que les cultures filtrées', () => {
    const res = filtrerParcelles([serre, maison], 'tomate')
    assert.deepEqual(res.map((p) => p.nom), ['Serre'])
    assert.deepEqual(res[0].cultures.map((c) => c.culture), ['tomate'])
  })

  await t.test('le filtre porte aussi sur la variété', () => {
    const res = filtrerParcelles([serre, maison], 'cerise')
    assert.deepEqual(res.map((p) => p.nom), ['Serre'])
  })

  await t.test('aucune correspondance : liste vide', () => {
    assert.deepEqual(filtrerParcelles([serre, maison], 'topinambour'), [])
  })
})

// ── CA1 / CA16 — sélection maître-détail ─────────────────────────────────────

test('[CA1] une seule parcelle sélectionnée, la première à l’ouverture', async (t) => {
  const liste = [parcelle({ id: 1, nom: 'Planche' }), parcelle({ id: 3, nom: 'Serre' })]

  await t.test('aucune sélection mémorisée : la première de la liste', () => {
    assert.equal(parcelleSelectionnee(liste, null).id, 1)
  })

  await t.test('sélection explicite : la parcelle choisie', () => {
    assert.equal(parcelleSelectionnee(liste, 3).id, 3)
  })

  await t.test('[CA16] filtre excluant la sélection : la première encore listée', () => {
    assert.equal(parcelleSelectionnee([liste[0]], 3).id, 1)
  })

  await t.test('liste vide : aucun détail à afficher', () => {
    assert.equal(parcelleSelectionnee([], 3), null)
  })
})

// ── CA8 / CA9 — calendrier cultural : soldés par US-176 ──────────────────────
// La table provisoire a été supprimée ; la frise se lit désormais dans le
// référentiel serveur. Tests : `lib/calendrier.test.js`.
