import { test } from 'node:test'
import assert from 'node:assert/strict'
import { NAV, NAV_OF, VUE_PAR_DEFAUT, sousOngletsActifs, vueDeSection } from './navigation.js'

const plan = () => NAV.find((n) => n.id === 'plan')

// ── US-223 / CA1 : l'ordre du zoom ───────────────────────────────────────────

test('CA1 — les sous-onglets du Plan suivent le zoom : Vue plan, Parcelles, Rotation', () => {
  assert.deepEqual(plan().subnav.map((t) => t.id), ['plan-vue', 'plan', 'plan-rot'])
  assert.deepEqual(plan().subnav.map((t) => t.label), ['Vue plan', 'Parcelles', 'Rotation · à venir'])
})

test('CA1 — les identifiants restent rattachés à la section Plan', () => {
  for (const id of ['plan', 'plan-vue', 'plan-rot']) assert.equal(NAV_OF[id], 'plan')
})

// ── CA2 : Rotation garde sa place, désactivée ────────────────────────────────

test('CA2 — Rotation est désactivée, les deux autres onglets ne le sont pas', () => {
  const [vue, parcelles, rotation] = plan().subnav
  assert.equal(rotation.disabled, true)
  assert.notEqual(vue.disabled, true)
  assert.notEqual(parcelles.disabled, true)
})

test('CA2 — la restitution ne rouvre jamais un onglet désactivé', () => {
  assert.deepEqual(sousOngletsActifs('plan'), ['plan-vue', 'plan'])
  assert.equal(vueDeSection('plan', { plan: 'plan-rot' }), 'plan-vue')
})

// ── CA3 : une seule constante d'entrée ───────────────────────────────────────

test("CA3 — le Plan s'ouvre sur la Vue plan (arbitrage A18)", () => {
  assert.equal(plan().entree, 'plan-vue')
  assert.equal(vueDeSection('plan'), 'plan-vue')
  assert.equal(vueDeSection('plan', {}), 'plan-vue')
})

// ── CA4 : le dernier sous-onglet est restitué ────────────────────────────────

test('CA4 — revenir au Plan rouvre le sous-onglet quitté', () => {
  assert.equal(vueDeSection('plan', { plan: 'plan' }), 'plan')
  assert.equal(vueDeSection('plan', { plan: 'plan-vue' }), 'plan-vue')
})

test('CA4 — une mémoire étrangère au Plan est ignorée', () => {
  assert.equal(vueDeSection('plan', { plan: 'journal' }), 'plan-vue')
  assert.equal(vueDeSection('plan', { cultures: 'cultures' }), 'plan-vue')
})

// ── CA7 : les autres activités ne changent pas ───────────────────────────────

test("CA7 — les sections gardent leur ordre et leur entrée", () => {
  assert.deepEqual(NAV.map((n) => n.id), ['bord', 'plan', 'cultures', 'pepiniere', 'stocks', 'journal'])
  for (const id of ['cultures', 'pepiniere', 'stocks', 'journal', 'bord']) {
    assert.equal(vueDeSection(id), id)
    assert.equal(vueDeSection(id, { [id]: 'stats' }), id, `${id} ne mémorise pas`)
  }
  assert.equal(VUE_PAR_DEFAUT, 'bord')
})

test('CA7 — le tableau de bord garde ses deux sous-onglets, dans leur ordre', () => {
  const bord = NAV.find((n) => n.id === 'bord')
  assert.deepEqual(bord.subnav.map((t) => t.id), ['bord', 'stats'])
})

test('une section inconnue retombe sur la vue par défaut', () => {
  assert.equal(vueDeSection('inconnue'), VUE_PAR_DEFAUT)
})
