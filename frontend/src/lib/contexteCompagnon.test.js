// [US-323] Ce que le jardinier a sous les yeux, transmis à Gaston — `npm test`.
//
// Ce qui se vérifie ici : la priorité culture → parcelle → potager (C1), le libellé de la barre
// (C2, C3), l'absence de barre d'une conversation libre (C6), des identifiants seulement à
// l'envoi (C4), les parcelles de « Préciser » sans pépinière (C3), et le câblage du panneau.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  EVENEMENT_OUVRIR_COMPAGNON, TEXTE_TOUT_LE_POTAGER, normaliserContexte, ouvertureDuPanneau,
  barreDeContexte, contexteAEnvoyer, parcellesAPreciser, contexteIntrouvable, ouvrirGastonAvec,
} from './contexteCompagnon.js'
import { contexteNoter } from './suiviCulture.js'

const CHOU = { parcelleId: 2, parcelle: 'Planche centrale', culture: 'chou de Bruxelles', variete: 'Groninger', rang: 3 }
const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')

test('[US-323 / C2] Gherkin 1 — « À propos de : Chou de Bruxelles · Planche centrale, rang 3 »', () => {
  const barre = barreDeContexte(CHOU)
  assert.equal(barre.aPropos, true)
  assert.equal(barre.texte, 'Chou de Bruxelles · Planche centrale, rang 3')
  assert.ok(barre.emoji)
  assert.equal(barre.retirable, true)
  assert.equal(barre.preciser, false)
})

test('[US-323 / C1] la parcelle quand aucune culture n’est choisie, sans rang si inconnu', () => {
  const barre = barreDeContexte({ parcelleId: 5, parcelle: 'Serre' })
  assert.equal(barre.texte, 'Serre')
  assert.equal(barre.emoji, '📍')
})

test('[US-323 / C3] Gherkin 2 — sans contexte : « Tout le potager » et « Préciser »', () => {
  const barre = barreDeContexte(null)
  assert.equal(barre.texte, TEXTE_TOUT_LE_POTAGER)
  assert.equal(barre.preciser, true)
  assert.equal(barre.retirable, false)
  assert.equal(barre.aPropos, false)
})

test('[US-323 / C4] une culture sans parcelle n’est pas un contexte', () => {
  assert.equal(normaliserContexte({ culture: 'fève' }), null)
  assert.equal(normaliserContexte({ parcelleId: 3, parcelle: 'Nord', variete: 'x' }).variete, null)
  assert.equal(normaliserContexte({ ...CHOU, rang: 0 }).rang, null)
})

test('[US-323 / C4] à l’envoi, des identifiants seulement — jamais le libellé', () => {
  assert.deepEqual(contexteAEnvoyer(CHOU), { parcelle_id: 2, culture: 'chou de Bruxelles', variete: 'Groninger', rang: 3 })
  assert.deepEqual(contexteAEnvoyer({ parcelleId: 5, parcelle: 'Serre' }), { parcelle_id: 5 })
  assert.equal(contexteAEnvoyer(null), undefined)
  assert.ok(!JSON.stringify(contexteAEnvoyer(CHOU)).includes('Planche centrale'))
})

test('[US-323 / C6] le visage de Gaston ouvre une conversation libre ; « Noter » ouvre la barre', () => {
  assert.deepEqual(ouvertureDuPanneau(undefined), { barre: false, contexte: null })
  assert.deepEqual(ouvertureDuPanneau({}), { barre: false, contexte: null })
  assert.deepEqual(ouvertureDuPanneau({ contexte: null }), { barre: true, contexte: null })
  assert.equal(ouvertureDuPanneau({ contexte: CHOU }).contexte.culture, 'chou de Bruxelles')
})

test('[US-323 / C3] « Préciser » propose les parcelles du potager, hors pépinières, dans l’ordre', () => {
  const plan = { parcelles: [
    { id: 3, nom: 'Serre à semis', est_pepiniere: true, ordre: 1 },
    { id: 2, nom: 'Planche sud', est_pepiniere: false, ordre: 3 },
    { id: 1, nom: 'Planche centrale', est_pepiniere: false, ordre: 2 },
  ] }
  assert.deepEqual(parcellesAPreciser(plan), [
    { parcelleId: 1, parcelle: 'Planche centrale' }, { parcelleId: 2, parcelle: 'Planche sud' },
  ])
  assert.deepEqual(parcellesAPreciser(null), [])
})

test('[US-323 / CA2] un 404 « Contexte introuvable » se dit autrement qu’une proposition disparue', () => {
  const e = Object.assign(new Error('Contexte introuvable'), { statut: 404 })
  assert.equal(contexteIntrouvable(e), true)
  assert.equal(contexteIntrouvable(Object.assign(new Error('Proposition introuvable'), { statut: 404 })), false)
})

test('[US-323] le suivi ouvre Gaston sur sa culture, avec le rang s’il est unique', () => {
  const suivi = { culture: 'chou de Bruxelles', variete: 'Groninger', parcelle_id: 2, parcelle: 'Planche centrale', rangs: [3] }
  assert.equal(contexteNoter(suivi).rang, 3)
  assert.equal(contexteNoter({ ...suivi, rangs: [2, 3] }).rang, undefined)
  const recus = []
  const cible = { dispatchEvent: (e) => recus.push(e) }
  ouvrirGastonAvec(contexteNoter(suivi), cible)
  assert.equal(recus[0].type, EVENEMENT_OUVRIR_COMPAGNON)
  assert.equal(recus[0].detail.contexte.parcelleId, 2)
})

test('[US-323 / CA1] le panneau porte la barre et envoie le contexte ; App distingue les deux ouvertures', () => {
  const panneau = lire('../components/PanneauCompagnon.jsx')
  assert.match(panneau, /barreContexte && <BarreContexte/)
  assert.match(panneau, /contexteAEnvoyer\(contexte\)/)
  assert.match(panneau, /aria-label="Retirer le contexte"/)
  const app = lire('../App.jsx')
  assert.match(app, /onOuvrir=\{ouvrirConversationLibre\}/)
  assert.match(app, /ouvertureDuPanneau\(e\.detail\)/)
})

// ── [US-325] la pastille du bouton « Noter » et la sélection du plan ─────────
import { pastilleNoter, publierSelection, EVENEMENT_SELECTION_PLAN } from './contexteCompagnon.js'

test('[US-325] Gherkin 1 — la fève choisie : la pastille porte son emoji ; sinon épingle ou micro', () => {
  const feve = pastilleNoter({ parcelleId: 2, parcelle: 'Planche centrale', culture: 'fève' })
  assert.equal(feve.sorte, 'culture')
  assert.ok(feve.emoji)
  assert.deepEqual(pastilleNoter({ parcelleId: 5, parcelle: 'Serre' }), { sorte: 'parcelle', emoji: '📍' })
  assert.deepEqual(pastilleNoter(null), { sorte: 'micro', emoji: '' })
  assert.equal(pastilleNoter({ parcelleId: 9, parcelle: 'Serre à semis', pepiniere: true }).sorte, 'pepiniere')
})

test('[US-325 / CA3] le plan publie sa sélection ; la coquille ne la lit que sur l’écran Plan', () => {
  const recus = []
  publierSelection({ parcelleId: 2, parcelle: 'Planche centrale', culture: 'fève' }, { dispatchEvent: (e) => recus.push(e) })
  publierSelection(undefined, { dispatchEvent: (e) => recus.push(e) })
  assert.equal(recus[0].type, EVENEMENT_SELECTION_PLAN)
  assert.equal(recus[0].detail.contexte.culture, 'fève')
  assert.equal(recus[1].detail.contexte, null)
  const app = lire('../App.jsx')
  assert.match(app, /selection=\{NAV_OF\[view\] === 'plan' \? selectionPlan : null\}/)
  assert.match(lire('../views/PlanDessus.jsx'), /publierSelection\(choix \?\? /)
})
