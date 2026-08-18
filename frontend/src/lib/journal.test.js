// [US-063] Composition de la phrase d'événement et regroupement par jour du
// Journal — exécuté par `npm test` (`node --test`, sans dépendance de test
// supplémentaire), comme `plan.test.js` (US-060).
//
// La conformité visuelle à la maquette relève du rapport de validation aux trois
// résolutions, pas de ces tests : ils couvrent la logique de composition, qui est
// la partie exposée aux cas tordus (champs absents, élision, singulier/pluriel).
import test from 'node:test'
import assert from 'node:assert/strict'
import { phraseEvenement, libelleAction, libelleJour, grouperParJour } from './journal.js'

/** Événement minimal : seuls les champs utiles au scénario sont renseignés. */
const ev = (champs) => ({
  date: '2026-08-18', type_action: 'recolte', culture: null, variete: null,
  quantite: null, unite: null, nb_plants_godets: null, parcelle: null,
  ...champs,
})

// ── CA1 — patron <action> de <quantité> <unité> <godets> de <culture> <variété> ──

test('[CA1] la phrase suit le patron complet', () => {
  assert.equal(
    phraseEvenement(ev({ type_action: 'recolte', quantite: 1.2, unite: 'kg', culture: 'Courgette', variete: 'Jaune' })),
    'Récolte de 1,2 kg de courgette Jaune',
  )
})

test('[CA1] la décimale est écrite à la française', () => {
  assert.match(phraseEvenement(ev({ quantite: 0.8, unite: 'kg', culture: 'Tomate' })), /0,8 kg/)
})

test('[CA1] la variété garde sa casse, la culture passe en minuscule', () => {
  // « Cœur de bœuf » est un nom propre de variété, pas un mot de la phrase.
  assert.equal(
    phraseEvenement(ev({ quantite: 0.8, unite: 'kg', culture: 'Tomate', variete: 'Cœur de bœuf' })),
    'Récolte de 0,8 kg de tomate Cœur de bœuf',
  )
})

test('[CA1] « de » s’élide devant une voyelle', async (t) => {
  await t.test('culture', () => {
    assert.equal(
      phraseEvenement(ev({ type_action: 'plantation', quantite: 3, unite: 'pieds', culture: 'Aubergine' })),
      "Plantation de 3 pieds d'aubergine",
    )
  })

  await t.test('voyelle accentuée', () => {
    assert.match(phraseEvenement(ev({ culture: 'Échalote' })), /d'échalote$/)
  })

  await t.test('le « h » reste aspiré — pas d’élision', () => {
    assert.match(phraseEvenement(ev({ culture: 'Haricot' })), /de haricot$/)
  })
})

// ── CA1 — chaque segment absent est omis, jamais comblé ──────────────────────

test('[CA1] un événement sans quantité ni culture se réduit à son action', () => {
  assert.equal(phraseEvenement(ev({ type_action: 'arrosage' })), 'Arrosage')
})

test('[CA1] un événement sans quantité garde culture et action', () => {
  assert.equal(phraseEvenement(ev({ type_action: 'semis', culture: 'Mâche' })), 'Semis de mâche')
})

test('[CA1] une quantité sans unité n’invente pas d’unité', () => {
  assert.equal(phraseEvenement(ev({ quantite: 5, culture: 'Radis' })), 'Récolte de 5 de radis')
})

test('[CA1] une quantité nulle est affichée, pas confondue avec une absence', () => {
  // 0 est une valeur, `null` une absence : `if (quantite)` aurait avalé le zéro.
  assert.match(phraseEvenement(ev({ quantite: 0, unite: 'kg', culture: 'Tomate' })), /de 0 kg/)
})

// ── CA1 — le compte d’un lot godet vient de nb_plants_godets ─────────────────

test('[CA1] une mise en godet tire son compte de nb_plants_godets', () => {
  // `quantite` est nul sur un vrai `mise_en_godet` (cf. creer_evenement_godet) :
  // sans ce champ, la phrase perdait toute quantité.
  assert.equal(
    phraseEvenement(ev({ type_action: 'mise_en_godet', quantite: null, nb_plants_godets: 20, culture: 'Courgette', variete: 'Verte' })),
    'Mise en godet de 20 godets de courgette Verte',
  )
})

test('[CA1] un seul godet reste au singulier', () => {
  assert.match(
    phraseEvenement(ev({ type_action: 'mise_en_godet', nb_plants_godets: 1, culture: 'Tomate' })),
    /de 1 godet de tomate$/,
  )
})

// ── Libellés d’action ────────────────────────────────────────────────────────

test('les libellés d’action couvrent les types hors filtre', () => {
  assert.equal(libelleAction('desherbage'), 'Désherbage')
  assert.equal(libelleAction('perte_godet'), 'Perte de godets')
  assert.equal(libelleAction('observation'), 'Note')
})

test('un type d’action inconnu reste lisible plutôt que brut', () => {
  assert.equal(libelleAction('nouvelle_action'), 'Nouvelle action')
  assert.equal(libelleAction(null), 'Action')
})

// ── CA1 — regroupement par jour ──────────────────────────────────────────────

const LE_18 = new Date('2026-08-18T12:00:00')

test('[CA1] le bandeau nomme aujourd’hui et hier', () => {
  assert.equal(libelleJour('2026-08-18', LE_18), "Aujourd'hui · 18 août")
  assert.equal(libelleJour('2026-08-17', LE_18), 'Hier · 17 août')
})

test('[CA1] les jours plus anciens portent leur nom de jour capitalisé', () => {
  assert.equal(libelleJour('2026-08-12', LE_18), 'Mercredi 12 août')
})

test('[CA1] les événements d’une même journée sont regroupés', () => {
  const groupes = grouperParJour([
    ev({ date: '2026-08-18', culture: 'Courgette' }),
    ev({ date: '2026-08-18', culture: 'Tomate' }),
    ev({ date: '2026-08-17', culture: 'Fraise' }),
  ], LE_18)

  assert.equal(groupes.length, 2)
  assert.equal(groupes[0].label, "Aujourd'hui · 18 août")
  assert.equal(groupes[0].items.length, 2)
  assert.equal(groupes[1].items.length, 1)
})

test('[CA4] le regroupement ne réordonne pas la page reçue', () => {
  // L'API renvoie déjà la page triée ; regrouper ne doit ni trier ni fusionner
  // deux blocs séparés du même jour, sous peine de désaligner la pagination.
  const groupes = grouperParJour([
    ev({ date: '2026-08-18' }),
    ev({ date: '2026-08-17' }),
    ev({ date: '2026-08-18' }),
  ], LE_18)

  assert.deepEqual(groupes.map((g) => g.items.length), [1, 1, 1])
})

test('[CA1] une page vide ne produit aucun groupe', () => {
  assert.deepEqual(grouperParJour([], LE_18), [])
})
