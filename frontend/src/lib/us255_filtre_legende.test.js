// [US-255] Filtre de légende de la frise calendrier — `npm test`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { couleurDuMoisFiltre, couleurDuMoisReferentiel } from './calendrier.js'

// Courgette océanique (valeurs de TEST) : avril = 3, mai = 4, juin = 5…
const frise = {
  pepiniere: [3], pleineTerre: [3, 4, 5], plantation: [4], rec: [6, 7], croissance: [],
}
const mois = (couleur) => Array.from({ length: 12 }, (_, i) => couleur(i))

test('CA2/CA3 — le filtre colore tous les mois de la phase, priorité ignorée', () => {
  const m = mois(couleurDuMoisFiltre(frise, 'pleineTerre', 'bg-violet'))
  assert.deepEqual([3, 4, 5].map((i) => m[i]), ['bg-violet', 'bg-violet', 'bg-violet'])
  // Sans filtre, mai est peint en plantation : le filtre le rend au semis.
  assert.equal(couleurDuMoisReferentiel(frise)(4), 'bg-brand')
})

test('CA2 — les autres mois sont neutres', () => {
  const m = mois(couleurDuMoisFiltre(frise, 'pleineTerre', 'bg-violet'))
  assert.equal(m.filter((c) => c === 'bg-card-alt').length, 9)
})

test('CA10 — phase absente : frise entièrement neutre', () => {
  const m = mois(couleurDuMoisFiltre({ ...frise, plantation: [] }, 'plantation', 'bg-brand'))
  assert.ok(m.every((c) => c === 'bg-card-alt'))
})

test('CA1/CA4/CA5/CA7 — légende à bascule, état local, sans lecture réseau (par la source)', () => {
  const src = readFileSync(new URL('../components/ui/MonthStrip.jsx', import.meta.url), 'utf8')
  assert.match(src, /aria-pressed=\{choisi\}/)
  assert.match(src, /onChoisir\(choisi \? null : cle\)/)
  assert.match(src, /useState\(null\)/)
  assert.doesNotMatch(src, /localStorage|fetch\(|api\./)
})
