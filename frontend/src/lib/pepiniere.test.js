// [US-061] Règles d'affichage d'un lot — exécuté par `npm test`
// (`node --test`, sans dépendance de test supplémentaire).
import test from 'node:test'
import assert from 'node:assert/strict'
import { stades, phaseGermination, tauxTint, stadeCourant, joursDepuis } from './pepiniere.js'

/** Lot minimal : seuls les champs pertinents au scénario sont renseignés. */
const lot = (champs) => ({
  graines_semees: 0,
  plants_obtenus: 0,
  nb_plantes: 0,
  stock_residuel_godet: 0,
  graines_en_germination: 0,
  nb_vendus: 0,
  nb_pertes_godet: 0,
  nb_mises_en_godet: 0,
  sans_semis_rattache: false,
  etat_germination: 'en_cours',
  taux_germination: null,
  ...champs,
})

const trois = (l) => { const s = stades(l); return [s.germination, s.godet, s.terre] }

test('[CA2] déroulé de référence — semis de 10 graines de tomate', async (t) => {
  await t.test('semis de 10 graines : 0 % partout', () => {
    assert.deepEqual(trois(lot({ graines_semees: 10, graines_en_germination: 10 })), [0, 0, 0])
  })

  await t.test('5 plants sur 5 graines : 50 / 50 / 0', () => {
    assert.deepEqual(trois(lot({
      graines_semees: 10, plants_obtenus: 5, stock_residuel_godet: 5, graines_en_germination: 5,
    })), [50, 50, 0])
  })

  await t.test('2 plants de plus sur les 5 graines restantes : 70 / 100 / 0', () => {
    assert.deepEqual(trois(lot({
      graines_semees: 10, plants_obtenus: 7, stock_residuel_godet: 7, etat_germination: 'close',
    })), [70, 100, 0])
  })

  await t.test('plantation de 5 godets : 70 / 29 / 71', () => {
    assert.deepEqual(trois(lot({
      graines_semees: 10, plants_obtenus: 7, nb_plantes: 5, stock_residuel_godet: 2,
      etat_germination: 'close',
    })), [70, 29, 71])
  })
})

test('[CA5] germination sans référence connue : aucun pourcentage, pas un 0 %', () => {
  const s = stades(lot({
    sans_semis_rattache: true, graines_semees: 12, plants_obtenus: 12, stock_residuel_godet: 12,
    etat_germination: 'close',
  }))
  assert.equal(s.germination, null)
  assert.equal(s.godet, 100)
  assert.equal(s.terre, 0)
})

test('[CA6] ventes et pertes : 3 plantés, 2 vendus, 1 perdu sur 7 plants', () => {
  const l = lot({
    graines_semees: 10, plants_obtenus: 7, nb_plantes: 3, stock_residuel_godet: 1,
    nb_vendus: 2, nb_pertes_godet: 1, etat_germination: 'close',
  })
  assert.deepEqual(trois(l), [70, 14, 43])
  const s = stades(l)
  // La décomposition affichée sous la frise doit refermer le total du lot.
  assert.equal(s.T + s.V + s.L + s.G, s.P)
})

test('[CA5] incohérence de saisie : le taux dépasse 100 % sans être borné', () => {
  const s = stades(lot({
    graines_semees: 10, plants_obtenus: 12, stock_residuel_godet: 12, etat_germination: 'close',
  }))
  assert.equal(s.germination, 120)
})

test('le badge affiche le taux de germination, et rien d’autre', () => {
  const enCours = lot({ graines_semees: 10, plants_obtenus: 5, graines_en_germination: 5 })
  assert.equal(phaseGermination(enCours).label, 'Germination 50 %')

  // Un lot clos porte le même libellé : « Réussite » a été retiré, il doublait la
  // même valeur sans rien apprendre.
  const close = lot({ graines_semees: 10, plants_obtenus: 7, etat_germination: 'close', taux_germination: 70 })
  assert.equal(phaseGermination(close).label, 'Germination 70 %')
})

test('[CA3] information manquante affichée comme telle, jamais comme un « en cours »', () => {
  const p = phaseGermination(lot({ graines_semees: 10, plants_obtenus: 5, etat_germination: 'indeterminee' }))
  assert.match(p.label, /indéterminée/)
  assert.doesNotMatch(p.label, /Germination \d/)
})

test('[CA11] code couleur du taux de germination, quel que soit l’état du lot', () => {
  assert.equal(tauxTint(80), 'brand')
  assert.equal(tauxTint(79), 'amber')
  assert.equal(tauxTint(50), 'amber')
  assert.equal(tauxTint(49), 'red')
  // Même code couleur sur un lot clos et sur un lot encore en germination.
  const teinte = (champs) => phaseGermination(lot(champs)).tint
  assert.equal(teinte({ graines_semees: 10, plants_obtenus: 4, etat_germination: 'close', taux_germination: 40 }), 'red')
  assert.equal(teinte({ graines_semees: 10, plants_obtenus: 9, graines_en_germination: 1 }), 'brand')
})

test('stade courant de la frise : Germination → Godet → Terre', () => {
  assert.equal(stadeCourant(lot({ graines_semees: 10, graines_en_germination: 10 })), 0)
  assert.equal(stadeCourant(lot({ plants_obtenus: 7, stock_residuel_godet: 7 })), 1)
  assert.equal(stadeCourant(lot({ plants_obtenus: 7, nb_plantes: 5, stock_residuel_godet: 2 })), 1)
  assert.equal(stadeCourant(lot({ plants_obtenus: 7, nb_plantes: 7 })), 2)
})

test('jours écoulés depuis le semis', () => {
  const ref = new Date('2026-08-12T09:00:00')
  assert.equal(joursDepuis('2026-08-02', ref), 10)
  assert.equal(joursDepuis(null, ref), null)
})
