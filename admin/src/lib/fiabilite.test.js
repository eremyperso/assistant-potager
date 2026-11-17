// [US-314] La vue Fiabilité affiche les chiffres de l'API, à l'unité près, sur un jeu FIXE :
// `fixtures/fiabilite_fixe.json` (vérifié côté Python par tests/test_us313_315_contrat_vues.py).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import {
  chiffresCles, periodeSansAppel, texteLatenceEchecs, modeleGraphiqueIssues, lignesIssues, COLONNES_ISSUES,
  descriptionCellule, heureEchec, lignesEchecs, COLONNES_ECHECS, NOTE_LATENCE,
} from './fiabilite.js'
import { pourcent, millisecondes } from './format.js'

const F = JSON.parse(readFileSync(fileURLToPath(new URL('./fixtures/fiabilite_fixe.json', import.meta.url)), 'utf8'))
const NBSP = ' '

// ── CA1 — bandeau ──────────────────────────────────────────────────────────────────────────────
test("CA1 : taux de succès, de quota, d'erreur et latences P50 et P95 sont ceux de l'API", () => {
  const c = Object.fromEntries(chiffresCles(F.fiabilite).map((x) => [x.id, x]))
  const m = F.fiabilite.mesures
  assert.deepEqual(Object.keys(c), ['succes', 'quota', 'erreur', 'p50', 'p95'])
  assert.equal(c.succes.valeur, m.taux_succes)
  assert.equal(c.quota.valeur, m.taux_quota)
  assert.equal(c.erreur.valeur, m.taux_erreur)
  assert.equal(c.p50.valeur, m.latence_p50_ms)
  assert.equal(c.p95.valeur, m.latence_p95_ms)
  assert.equal(c.succes.texte, pourcent(m.taux_succes, 1))
  assert.equal(c.p50.texte, millisecondes(900))
})

test('CA1 (Gherkin) : 30 appels ok sur 43 → 69,8 %', () => {
  const m = { ...F.fiabilite.mesures, taux_succes: 30 / 43 }
  assert.equal(chiffresCles({ ...F.fiabilite, mesures: m })[0].texte, `69,8${NBSP}%`)
})

test('CA1 : chaque chiffre a son écart à la période précédente, en points pour un taux', () => {
  const c = Object.fromEntries(chiffresCles(F.fiabilite).map((x) => [x.id, x]))
  // 92,6 % contre 100 % : −7,4 points, défavorable pour un taux de succès
  assert.equal(c.succes.ecart.texte, `−7,4${NBSP}points`)
  assert.equal(c.succes.ecart.jugement, 'defavorable')
  // quota 3,7 % contre 0 % : +3,7 points, défavorable
  assert.equal(c.quota.ecart.texte, `+3,7${NBSP}points`)
  assert.equal(c.quota.ecart.jugement, 'defavorable')
  // latence : 900 ms contre 800 ms, +13 %, défavorable
  assert.equal(c.p50.ecart.texte, `+13${NBSP}%`)
  assert.equal(c.p50.ecart.libelle, 'défavorable')
})

test('CA1 : un petit écart de taux garde sa décimale', () => {
  const m = { ...F.fiabilite.mesures, taux_quota: 0.019 }
  const p = { ...F.fiabilite.mesures_precedentes, taux_quota: 0.012 }
  assert.equal(chiffresCles({ ...F.fiabilite, mesures: m, mesures_precedentes: p })[1].ecart.texte, `+0,7${NBSP}point`)
})

test('CA1 : sans appel, les valeurs sont indisponibles et la vue est vide', () => {
  const vide = { ...F.fiabilite, mesures: { ...F.fiabilite.mesures, appels: 0, taux_succes: null, latence_p50_ms: null } }
  assert.equal(periodeSansAppel(vide), true)
  assert.equal(chiffresCles(vide)[0].texte, '—')
  assert.equal(periodeSansAppel(F.fiabilite), false)
})

// ── CA2 — graphique par jour ────────────────────────────────────────────────────────────────────
test('CA2 : toute issue présente en base est affichée, y compris voix_inconnue', () => {
  const g = modeleGraphiqueIssues(F.serie_issues)
  assert.deepEqual(g.series.map((s) => s.cle).sort(), Object.keys(F.fiabilite.mesures.issues).sort())
  assert.ok(g.series.some((s) => s.cle === 'voix_inconnue'))
  assert.equal(g.mode, 'empile')
  assert.equal(g.points.length, 7)
})

test("CA2 : une issue que l'écran ne connaît pas est affichée telle quelle, sans regroupement", () => {
  const serie = {
    pas: 'jour', points: ['2026-11-10'], total: [28],
    series: [1, 2, 3, 4, 5, 6, 7].map((n) => ({ cle: n === 7 ? 'issue_de_demain' : `i${n}`, total: 8 - n, valeurs: [8 - n] })),
  }
  const g = modeleGraphiqueIssues(serie)
  assert.equal(g.series.length, 7)
  assert.ok(g.series.some((s) => s.libelle === 'issue_de_demain'))
  assert.ok(!g.series.some((s) => s.libelle === 'Autres'))
})

test("CA2 : la somme des piles est le nombre d'appels de la période", () => {
  const g = modeleGraphiqueIssues(F.serie_issues)
  assert.equal(g.total.reduce((a, b) => a + b, 0), F.fiabilite.mesures.appels)
})

// ── CA3, CA4 — tableaux ─────────────────────────────────────────────────────────────────────────
test("CA3/CA4 : les mêmes colonnes par modèle et par type d'appel", () => {
  assert.deepEqual(COLONNES_ISSUES.map((c) => c.libelle), ['Appels', 'Succès', 'Quota', 'Erreur', 'Délai', 'Autres', 'P50', 'P95'])
  for (const lignes of [lignesIssues(F.fiabilite.par_modele), lignesIssues(F.fiabilite.par_type)]) {
    for (const l of lignes) assert.deepEqual(Object.keys(l.cellules), COLONNES_ISSUES.map((c) => c.id))
  }
})

test("CA3 : chaque ligne reprend les décomptes de l'API", () => {
  const small = lignesIssues(F.fiabilite.par_modele).find((l) => l.cle === 'mistral/small')
  const api = F.fiabilite.par_modele.find((l) => l.cle === 'mistral/small')
  assert.equal(small.cellules.appels, String(api.appels))
  assert.equal(small.cellules.quota, String(api.quota))
  assert.equal(small.cellules.erreur, String(api.erreur))
  assert.equal(small.cellules.p95, millisecondes(api.latence_p95_ms))
})

test('CA3 : une issue hors des quatre connues tombe dans « Autres » et se nomme sous la ligne', () => {
  const voxtral = lignesIssues(F.fiabilite.par_modele).find((l) => l.cle === 'voxtral')
  assert.equal(voxtral.cellules.autres, '1')
  assert.equal(voxtral.note, 'voix_inconnue : 1')
  const small = lignesIssues(F.fiabilite.par_modele).find((l) => l.cle === 'mistral/small')
  assert.equal(small.cellules.autres, '—')
})

test("CA4 : les lignes du tableau par type se somment au nombre d'appels du bandeau", () => {
  const somme = F.fiabilite.par_type.reduce((a, l) => a + l.appels, 0)
  assert.equal(somme, F.fiabilite.mesures.appels)
})

// ── CA5 — grille heure × jour ───────────────────────────────────────────────────────────────────
test('CA5 : la grille couvre 7 jours × 24 heures par modèle', () => {
  const g = F.fiabilite.grille_quota
  assert.equal(g.jours.length, 7)
  for (const m of g.modeles) {
    assert.equal(m.cellules.length, 7)
    assert.ok(m.cellules.every((j) => j.length === 24))
  }
  const small = g.modeles.find((m) => m.modele === 'mistral/small')
  assert.equal(small.total, 2)
  assert.equal(small.cellules[6][14], 1)          // 10 nov., 14 h
  assert.equal(small.cellules[5][14], 1)          // 9 nov., 14 h
})

test('CA5 : chaque cellule a un texte lisible, pas seulement une teinte', () => {
  assert.equal(descriptionCellule('2026-11-10', 14, 1), 'mar. 10 nov., 14 h : 1 appel en quota')
  assert.equal(descriptionCellule('2026-11-10', 3, 0), 'mar. 10 nov., 3 h : aucun appel en quota')
  assert.equal(descriptionCellule('2026-11-10', 3, 4), 'mar. 10 nov., 3 h : 4 appels en quota')
})

// ── CA6 — derniers échecs ───────────────────────────────────────────────────────────────────────
test("CA6 : heure, type, modèle, issue, canal et latence — et rien d'autre", () => {
  assert.deepEqual(COLONNES_ECHECS.map((c) => c.id), ['type', 'modele', 'issue', 'canal', 'latence'])
  const lignes = lignesEchecs(F.fiabilite.derniers_echecs)
  assert.equal(lignes.length, 4)
  const voix = lignes[0]
  assert.deepEqual(voix.cellules, { type: 'voix', modele: 'voxtral', issue: 'voix_inconnue', canal: 'pwa', latence: `50${NBSP}ms` })
  assert.equal(voix.titre, '10 nov. 20 h 30')
})

test('CA6 (Gherkin) : la liste des derniers échecs nomme le type « voix » et le modèle concerné', () => {
  const voix = F.fiabilite.derniers_echecs.find((e) => e.issue === 'voix_inconnue')
  assert.equal(voix.appel_type, 'voix')
  assert.equal(voix.modele, 'voxtral')
})

test("CA6 : l'heure d'un échec se lit sans conversion de fuseau", () => {
  assert.equal(heureEchec({ cree_le: '2026-11-09T07:05:00', date: '2026-11-09' }), '9 nov. 7 h 05')
  assert.equal(heureEchec({ cree_le: null, date: '2026-11-09' }), '9 nov. 0 h 00')
})

// ── CA7 — latence ───────────────────────────────────────────────────────────────────────────────
test('CA7 : la latence des échecs est donnée à part, et la note dit que les autres sont sur les réussites', () => {
  assert.match(texteLatenceEchecs(F.fiabilite), /Latence des échecs : P50 2.000.ms/)
  assert.match(NOTE_LATENCE, /appels réussis seulement/)
  assert.equal(texteLatenceEchecs({ mesures: { latence_echecs_p50_ms: null } }), 'Aucun échec sur la période.')
})
