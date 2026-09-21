// [US-194] Phase du moment d'une culture en place — `npm test`.
//
// Ce qui se vérifie ici : la correspondance phase → libellé → teinte écrite UNE
// fois (CA10), la lisibilité en niveaux de gris par le MOT (CA10 / RT4), le
// vocabulaire d'une levée ATTENDUE (CA5), la légende (CA9) et le fait qu'aucune
// phase ne soit recalculée côté front (CA1).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  PHASES, PHASE_LIBRE, PHASE_SEMEE, PHASE_EN_PLACE, PHASE_EN_RECOLTE,
  DEPUIS_LEVEE_ATTENDUE, DEPUIS_SEMIS, DEPUIS_PLANTATION, DEPUIS_RECOLTE,
  phase, libellePhase, teintePhase, depuisLisible, libelleComplet, aUnePhase,
  entreesLegende,
} from './phases.js'
import { PHASES_REFERENTIEL, TEINTE_EN_CROISSANCE_RESERVEE } from './calendrier.js'

// ── CA9 : les trois phases, leurs teintes, leur cohérence avec la frise ──────

test('[CA9] les trois phases du cycle, dans l’ordre', () => {
  assert.deepEqual(PHASES.map((p) => p.cle), [PHASE_SEMEE, PHASE_EN_PLACE, PHASE_EN_RECOLTE])
})

test('[CA9] « en place » reprend la teinte RÉSERVÉE à « en croissance »', () => {
  assert.equal(phase(PHASE_EN_PLACE).pastille, TEINTE_EN_CROISSANCE_RESERVEE)
})

test('[CA9] « semée » reprend la famille du semis en pleine terre', () => {
  const pleineTerre = PHASES_REFERENTIEL.find((p) => p.cle === 'pleineTerre')
  assert.equal(phase(PHASE_SEMEE).pastille, pleineTerre.teinte)
})

test('[CA9] « en récolte » reprend la famille de la récolte', () => {
  const recolte = PHASES_REFERENTIEL.find((p) => p.cle === 'rec')
  assert.equal(phase(PHASE_EN_RECOLTE).pastille, recolte.teinte)
})

test('[CA9] aucune teinte n’est partagée par deux phases', () => {
  const teintes = PHASES.map((p) => p.pastille)
  assert.equal(new Set(teintes).size, teintes.length)
})

test('[CA9] les teintes sont des tokens sémantiques, jamais une couleur en dur', () => {
  for (const p of [...PHASES, PHASE_LIBRE]) {
    assert.match(p.pastille, /^bg-[a-z-]+$/, p.cle)
    assert.doesNotMatch(`${p.teinte} ${p.pastille}`, /#[0-9a-f]{3,6}|rgb\(/i, p.cle)
  }
})

// ── CA10 : la correspondance est écrite une fois, et le mot porte le sens ────

test('[CA10] une clé inconnue ou absente n’a pas de phase — jamais un repli', () => {
  assert.equal(phase('en_fleur'), null)
  assert.equal(phase(undefined), null)
  assert.equal(libellePhase('en_fleur'), '')
  assert.equal(teintePhase(null), '')
  assert.equal(aUnePhase({ phase: 'en_fleur' }), false)
  assert.equal(aUnePhase({}), false)
  assert.equal(aUnePhase({ phase: PHASE_SEMEE }), true)
})

test('[CA10] chaque phase porte un MOT : lisible en niveaux de gris', () => {
  for (const p of [...PHASES, PHASE_LIBRE]) {
    assert.ok(p.libelle.trim().length > 0, p.cle)
    assert.ok(p.court.trim().length > 0, p.cle)
  }
})

test('[CA1, CA10] la pastille ne recalcule aucune phase : elle lit le serveur', () => {
  const source = readFileSync(new URL('../components/ui/PastillePhase.jsx', import.meta.url), 'utf8')
  // Aucune date, aucun délai de levée, aucune comparaison de jours dans le composant.
  assert.doesNotMatch(source, /levee|date_semis|Date\.now|new Date/)
})

test('[CA1, CA10] la lib ne dérive aucune phase d’une date', () => {
  const source = readFileSync(new URL('./phases.js', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /new Date|Date\.now|date_semis|date_recolte/)
})

// ── CA5 : une levée attendue reste attendue ─────────────────────────────────

test('[CA5] une levée attendue n’est jamais présentée comme constatée', () => {
  const ligne = { phase: PHASE_EN_PLACE, phase_depuis: '2026-09-20', phase_depuis_nature: DEPUIS_LEVEE_ATTENDUE }
  assert.equal(depuisLisible(ligne), 'depuis la levée attendue du 20 septembre')
})

test('[CA5] une plantation, un semis et une récolte sont des dates constatées', () => {
  for (const nature of [DEPUIS_SEMIS, DEPUIS_PLANTATION, DEPUIS_RECOLTE]) {
    const ligne = { phase: PHASE_EN_RECOLTE, phase_depuis: '2026-07-16', phase_depuis_nature: nature }
    assert.equal(depuisLisible(ligne), 'depuis le 16 juillet')
  }
})

test('[CA5] sans date, aucun complément n’est inventé', () => {
  assert.equal(depuisLisible({ phase: PHASE_SEMEE }), '')
  assert.equal(depuisLisible({ phase: PHASE_SEMEE, phase_depuis: null }), '')
})

// ── Libellé complet : mot, date, nombre de séries ───────────────────────────

test('le libellé complet nomme la phase, sa date, puis ses séries', () => {
  assert.equal(
    libelleComplet({ phase: PHASE_EN_RECOLTE, phase_depuis: '2026-07-16', phase_depuis_nature: DEPUIS_RECOLTE, nb_series: 1 }),
    'En récolte · depuis le 16 juillet',
  )
})

test('⚖️ plusieurs séries sont COMPTÉES à côté, jamais moyennées', () => {
  assert.equal(
    libelleComplet({ phase: PHASE_EN_PLACE, phase_depuis: '2026-06-06', phase_depuis_nature: DEPUIS_LEVEE_ATTENDUE, nb_series: 2 }),
    'En place · depuis la levée attendue du 6 juin · 2 séries',
  )
})

test('une ligne sans phase n’a pas de libellé', () => {
  assert.equal(libelleComplet({ nb_series: 3 }), '')
})

// ── CA9 : la légende ────────────────────────────────────────────────────────

test('[CA9] la légende montre les trois phases, et « libre » en option', () => {
  assert.deepEqual(entreesLegende().map((p) => p.cle), [PHASE_SEMEE, PHASE_EN_PLACE, PHASE_EN_RECOLTE])
  assert.deepEqual(
    entreesLegende({ avecLibre: true }).map((p) => p.cle),
    [PHASE_SEMEE, PHASE_EN_PLACE, PHASE_EN_RECOLTE, 'libre'],
  )
})

test('[CA9] la légende ne peut pas être modifiée par un écran', () => {
  const entrees = entreesLegende()
  entrees.push({ cle: 'ailleurs' })
  assert.equal(entreesLegende().length, 3)
  assert.throws(() => { PHASES[0].libelle = 'Autre' }, TypeError)
})
