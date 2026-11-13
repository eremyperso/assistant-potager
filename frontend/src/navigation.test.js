import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Layers } from 'lucide-react'
import { NAV, NAV_OF, VUE_PAR_DEFAUT, sousOngletsActifs, vueDeSection } from './navigation.js'

const plan = () => NAV.find((n) => n.id === 'plan')

// ── US-223 / CA1 : l'ordre du zoom ───────────────────────────────────────────

test('le Plan n’a plus de tuiles : ni « Plan », ni « Rotation · à venir »', () => {
  assert.equal(plan().subnav, undefined)
  assert.deepEqual(sousOngletsActifs('plan'), [])
  assert.equal(plan().Icon, Layers)                // l'icône des plans superposés
})

test('la vue plan reste rattachée à la section Plan, l’ancienne Rotation n’existe plus', () => {
  assert.equal(NAV_OF['plan-vue'], 'plan')
  assert.equal(NAV_OF['plan-rot'], undefined)
  assert.equal(NAV_OF.plan, undefined)
})

test('une mémoire qui pointe l’ancienne Rotation retombe sur le Plan', () => {
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
  // [US-330] Une mémoire qui pointe l'ancien onglet Parcelles retombe sur le Plan.
  assert.equal(vueDeSection('plan', { plan: 'plan' }), 'plan-vue')
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

// ── [US-325] « Noter » au centre de la barre basse ───────────────────────────
import { NOTER, NAV_MOBILE, NAV_MOBILE_PLUS, barreBasse } from './navigation.js'
import { readFileSync as lireFichier } from 'node:fs'

test('[US-325 / CA1, P1] la barre basse : Accueil, Plan, Noter, Pépinière, puis Plus (Cultures, Stocks, Journal)', () => {
  assert.deepEqual([...NAV_MOBILE], ['bord', 'plan', 'noter', 'pepiniere'])
  assert.deepEqual([...NAV_MOBILE_PLUS], ['cultures', 'stocks', 'journal'])
  const { principales, secondaires } = barreBasse()
  assert.deepEqual(principales.map((e) => e.shortLabel), ['Accueil', 'Plan', 'Noter', 'Pépinière'])
  assert.deepEqual(secondaires.map((e) => e.label), ['Cultures', 'Stocks', 'Journal'])
  // Toutes les sections restent atteignables depuis le téléphone.
  const atteintes = [...principales, ...secondaires].filter((e) => !e.action).map((e) => e.id).sort()
  assert.deepEqual(atteintes, NAV.map((n) => n.id).sort())
})

test('[US-325 / CA2] « Noter » est une action, jamais une section ni une vue', () => {
  assert.equal(NOTER.action, true)
  assert.equal(NOTER.label, 'Noter, avec Gaston')
  assert.equal(NAV.some((n) => n.id === NOTER.id), false)
  assert.equal(NOTER.id in NAV_OF, false)
})

test('[US-325 / CA4] la navigation de bureau ne change pas', () => {
  assert.deepEqual(NAV.map((n) => n.id), ['bord', 'plan', 'cultures', 'pepiniere', 'stocks', 'journal'])
})

test('[US-325 / CA2, CA5] le bouton : 44 px, aria-label, focus visible, jamais aria-current ; masqué en lecture seule', () => {
  const src = lireFichier(new URL('./components/BottomNav.jsx', import.meta.url), 'utf8')
  const bouton = src.slice(src.indexOf('onClick={noter}'), src.indexOf('{NOTER.shortLabel}'))
  assert.match(bouton, /min-h-\[44px\] min-w-\[44px\]/)
  assert.match(bouton, /aria-label=\{NOTER\.label\}/)
  assert.match(bouton, /focus-visible:outline/)
  assert.doesNotMatch(bouton, /aria-current/)
  assert.match(src, /if \(!ecrire\) return null/)
})
