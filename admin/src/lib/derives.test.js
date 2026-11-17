// [US-315] La vue Dérives affiche les chiffres de l'API, à l'unité près, sur un jeu FIXE :
// `fixtures/derives_fixe.json` (vérifié côté Python par tests/test_us313_315_contrat_vues.py).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import {
  lignesVersionType, modeleCourbe, lignesVersionCanal, versionsParDefaut, comparer, ecartRelatif, typesDisponibles,
  libelleVersion, LIBELLE_SANS_VERSION, CONSEIL_MESURE, periodeSansAppel, COLONNES_VERSION_TYPE, COLONNES_VERSION_CANAL,
} from './derives.js'
import { entier } from './format.js'

const F = JSON.parse(readFileSync(fileURLToPath(new URL('./fixtures/derives_fixe.json', import.meta.url)), 'utf8'))
const D = F.derives
const NBSP = ' '

// ── CA1 — tableau par version et par type ───────────────────────────────────────────────────────
test("CA1 : nombre d'appels, médiane et P95 d'entrée, médiane de sortie, taux de cache par version et par type", () => {
  assert.deepEqual(COLONNES_VERSION_TYPE.map((c) => c.id), ['type', 'appels', 'entree_mediane', 'entree_p95', 'sortie_mediane', 'cache'])
  const lignes = lignesVersionType(D)
  assert.equal(lignes.length, D.par_version_et_type.length)
  const v128 = lignes.find((l) => l.cle === '3.128.0|agent')
  assert.deepEqual(v128.cellules, {
    type: 'agent', appels: '22', entree_mediane: entier(8900), entree_p95: entier(8900), sortie_mediane: '120', cache: `45${NBSP}%`,
  })
})

test('CA1 : les versions viennent de la plus récente à la plus ancienne, « avant suivi » en dernier', () => {
  assert.deepEqual(D.versions, ['3.128.0', '3.127.0', null])
  assert.deepEqual(lignesVersionType(D).map((l) => l.titre), ['3.128.0', '3.128.0', '3.127.0', LIBELLE_SANS_VERSION])
})

// ── CA2 — courbe avec repères ───────────────────────────────────────────────────────────────────
test('CA2 : la courbe est la médiane par jour du type choisi, et un repère marque chaque version', () => {
  const c = modeleCourbe(D)
  assert.equal(c.modele.points.length, 7)
  assert.deepEqual(c.modele.series[0].valeurs, [0, 6000, 6000, 6000, 8900, 8900, 8900])
  assert.deepEqual(c.reperes, [{ index: 1, libelle: '3.127.0' }, { index: 4, libelle: '3.128.0' }])
  assert.equal(c.sansAppel, false)
  assert.match(c.modele.series[0].libelle, /type agent/)
})

test('CA2 : le type par défaut est « agent » et la liste des types le met en premier', () => {
  assert.equal(D.courbe.appel_type, 'agent')
  assert.deepEqual(typesDisponibles(D), ['agent', 'question'])
})

test('CA2 : un type sans appel mesuré donne une courbe vide, pas un zéro', () => {
  const c = modeleCourbe({ ...D, courbe: { ...D.courbe, appel_type: 'voix', valeurs: D.courbe.valeurs.map(() => null), reperes: [] } })
  assert.equal(c.sansAppel, true)
})

// ── CA3 — par version et par canal ──────────────────────────────────────────────────────────────
test('CA3 : appels par échange (médiane, P95), entrée médiane par échange et coût médian par échange', () => {
  assert.deepEqual(COLONNES_VERSION_CANAL.map((c) => c.id), ['canal', 'echanges', 'appels_mediane', 'appels_p95', 'entree', 'cout'])
  const pwa128 = lignesVersionCanal(D).find((l) => l.cle === '3.128.0|pwa')
  assert.equal(pwa128.cellules.echanges, '13')
  assert.equal(pwa128.cellules.appels_mediane, '2')
  assert.equal(pwa128.cellules.entree, entier(17800))
  assert.equal(pwa128.cellules.cout, `0,009${NBSP}€`)
})

test('CA3 : un coût absent est un tiret', () => {
  const sans = { ...D, par_version_et_canal: [{ ...D.par_version_et_canal[0], cout_par_echange_mediane_micro_eur: null }] }
  assert.equal(lignesVersionCanal(sans)[0].cellules.cout, '—')
})

// ── CA4 — comparaison côte à côte ───────────────────────────────────────────────────────────────
test('CA4 (Gherkin) : 6 000 contre 8 900 jetons → écart +48 %, mis en évidence', () => {
  const { a, b } = versionsParDefaut(D, 'agent')
  assert.deepEqual([a, b], ['3.127.0', '3.128.0'])
  const r = comparer(D, a, b, 'agent')
  const ligne = r.lignes.find((l) => l.id === 'entree_mediane')
  assert.equal(ligne.a, entier(6000))
  assert.equal(ligne.b, entier(8900))
  assert.equal(ligne.ecart.texte, `+48${NBSP}%`)
  assert.equal(ligne.enEvidence, true)
  assert.equal(ligne.ecart.jugement, 'defavorable')
  assert.equal(r.auMoinsUneEnEvidence, true)
})

test("CA4 : sous 20 %, l'écart est affiché mais pas mis en évidence", () => {
  const proche = { ...D, par_version_et_type: D.par_version_et_type.map((l) => (l.version === '3.128.0' && l.appel_type === 'agent' ? { ...l, entree_mediane: 6600 } : l)) }
  const ligne = comparer(proche, '3.127.0', '3.128.0', 'agent').lignes.find((l) => l.id === 'entree_mediane')
  assert.equal(ligne.ecart.texte, `+10${NBSP}%`)
  assert.equal(ligne.enEvidence, false)
})

test("CA4 : exactement 20 % n'est pas « au-delà de 20 % »", () => {
  const pile = { ...D, par_version_et_type: D.par_version_et_type.map((l) => (l.version === '3.128.0' && l.appel_type === 'agent' ? { ...l, entree_mediane: 7200 } : l)) }
  assert.equal(comparer(pile, '3.127.0', '3.128.0', 'agent').lignes.find((l) => l.id === 'entree_mediane').enEvidence, false)
})

test("CA4 : un nombre d'appels qui diffère n'est jamais une dérive", () => {
  const r = comparer(D, '3.127.0', '3.128.0', 'agent')
  assert.equal(r.lignes.find((l) => l.id === 'appels').enEvidence, false)
})

test('CA4 : les échanges se comparent par canal quand les deux versions en ont', () => {
  const r = comparer(D, '3.127.0', '3.128.0', 'agent')
  const ids = r.lignes.map((l) => l.id)
  assert.ok(ids.includes('appels_echange_pwa') && ids.includes('entree_echange_pwa') && ids.includes('cout_echange_pwa'))
  assert.ok(!ids.includes('appels_echange_mcp'))       // 3.127.0 n'a pas de canal mcp
})

test("CA4 : l'écart relatif brut", () => {
  assert.equal(ecartRelatif(100, 150), 0.5)
  assert.equal(ecartRelatif(0, 10), null)
  assert.equal(ecartRelatif(null, 10), null)
})

// ── CA5 — échantillon faible ────────────────────────────────────────────────────────────────────
test('CA5 : moins de 20 appels → « échantillon faible », marqué dans le tableau', () => {
  const lignes = lignesVersionType(D)
  assert.equal(lignes.find((l) => l.cle === '3.128.0|question').faible, true)
  assert.equal(lignes.find((l) => l.cle === '3.128.0|agent').faible, false)
  assert.equal(D.seuil_echantillon, 20)
})

test("CA5 : une version à échantillon faible n'est jamais mise en évidence, même au-delà de 20 %", () => {
  const faible = { ...D, par_version_et_type: D.par_version_et_type.map((l) => (l.version === '3.128.0' && l.appel_type === 'agent' ? { ...l, appels: 5, echantillon_faible: true } : l)) }
  const r = comparer(faible, '3.127.0', '3.128.0', 'agent')
  const ligne = r.lignes.find((l) => l.id === 'entree_mediane')
  assert.equal(ligne.ecart.texte, `+48${NBSP}%`)         // l'écart reste lisible
  assert.equal(ligne.faible, true)
  assert.equal(ligne.enEvidence, false)
})

test("CA5 : les échanges d'un canal à échantillon faible ne sont pas mis en évidence non plus", () => {
  const ligne = comparer(D, '3.127.0', '3.128.0', 'agent').lignes.find((l) => l.id === 'appels_echange_pwa')
  assert.equal(ligne.faible, true)                      // 13 échanges en 3.128.0 < 20
  assert.equal(ligne.enEvidence, false)
})

// ── CA6 — mesure ────────────────────────────────────────────────────────────────────────────────
test('CA6 : la vue conseille de comparer en « mesure » et le dit', () => {
  assert.match(CONSEIL_MESURE, /provenance sur « mesure »/)
  assert.match(CONSEIL_MESURE, /même jeu de phrases/)
})

// ── CA7 — avant suivi ───────────────────────────────────────────────────────────────────────────
test('CA7 : les lignes sans version sont regroupées sous « avant suivi des versions »', () => {
  assert.equal(libelleVersion(null), 'avant suivi des versions')
  assert.equal(libelleVersion('3.127.0'), '3.127.0')
  const sans = lignesVersionType(D).find((l) => l.cle === 'null|agent')
  assert.equal(sans.titre, LIBELLE_SANS_VERSION)
  assert.equal(sans.mono, false)
})

test("CA7 : par défaut, « avant suivi » n'est pas proposé à la comparaison", () => {
  const { a, b } = versionsParDefaut(D, 'agent')
  assert.ok(a !== null && b !== null)
  assert.equal(versionsParDefaut({ ...D, versions: ['3.128.0'] }, 'agent'), null)
})

test('une période sans version est vide', () => {
  assert.equal(periodeSansAppel({ versions: [] }), true)
  assert.equal(periodeSansAppel(D), false)
})
