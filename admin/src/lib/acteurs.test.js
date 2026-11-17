// [US-319] La vue « Potagers et jardiniers » : tri, bandeau, lignes, fiches.
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  TRIS, aucunAppel, chiffresBandeau, lignesJardiniers, lignesPartage, lignesPotagers, lignesRepartition, modeleCout,
  resumeEchange, texteIssues, trier,
} from './acteurs.js'

const propre = (v) => (typeof v === 'string' ? v.replace(/[  ]/g, ' ') : v)
const egal = (reel, attendu) => assert.equal(propre(reel), propre(attendu))

const base = { echanges: 0, jetons_entree: 0, jetons_sortie: 0, part_cout: null, canaux: [], taux_echec: null, dernier_appel: null, usage_eleve: false }
const LIGNES = [
  { ...base, id: 1, libelle: 'Moulin', membres: 1, appels: 3, cout_micro_eur: 200_000, echanges: 3, dernier_appel: '2026-11-10', part_cout: 0.2 },
  { ...base, id: 2, libelle: 'Garenne', membres: 2, appels: 9, cout_micro_eur: 900_000, echanges: 8, dernier_appel: '2026-11-17', part_cout: 0.9, usage_eleve: true, canaux: ['pwa', 'telegram'], taux_echec: 0.125, jetons_entree: 12000, jetons_sortie: 800 },
  { ...base, id: 3, libelle: 'Vide', membres: 1, appels: 0, cout_micro_eur: null },
  { ...base, id: 4, libelle: 'Alpha', membres: 1, appels: 3, cout_micro_eur: 200_000, echanges: 1, dernier_appel: '2026-11-12' },
]

test('trier : coût, appels, échanges, dernier appel ; libellé en cas d\'égalité ; entrée intacte', () => {
  const copie = JSON.stringify(LIGNES)
  assert.deepEqual(trier(LIGNES, 'cout').map((l) => l.libelle), ['Garenne', 'Alpha', 'Moulin', 'Vide'])
  assert.deepEqual(trier(LIGNES, 'appels').map((l) => l.libelle), ['Garenne', 'Alpha', 'Moulin', 'Vide'])
  assert.deepEqual(trier(LIGNES, 'echanges').map((l) => l.libelle), ['Garenne', 'Moulin', 'Alpha', 'Vide'])
  assert.deepEqual(trier(LIGNES, 'dernier').map((l) => l.libelle), ['Garenne', 'Alpha', 'Moulin', 'Vide'])
  assert.equal(JSON.stringify(LIGNES), copie)
  assert.deepEqual(TRIS.map((t) => t.id), ['cout', 'appels', 'echanges', 'dernier'])
})

test('trier : un coût nul passe avant un coût non chiffré, les tâches automatiques restent en dernier', () => {
  const lignes = [{ ...base, id: null, libelle: 'Tâches automatiques', appels: 99, cout_micro_eur: 9_000_000, automatique: true },
    { ...base, id: 1, libelle: 'A', appels: 1, cout_micro_eur: null }, { ...base, id: 2, libelle: 'B', appels: 1, cout_micro_eur: 0 }]
  assert.deepEqual(trier(lignes, 'cout').map((l) => l.libelle), ['B', 'A', 'Tâches automatiques'])
})

test('lignesPotagers : coût, part, jetons, échec, dernier appel, canaux, usage élevé', () => {
  const [garenne, , , vide] = lignesPotagers(LIGNES, 'cout')
  assert.equal(garenne.titre, 'Garenne')
  assert.equal(garenne.usageEleve, true)
  egal(garenne.cellules.cout, '0,900 €')
  egal(garenne.cellules.part, '90,0 %')
  egal(garenne.cellules.jetons, '12 000 / 800')
  egal(garenne.cellules.echec, '12,5 %')
  egal(garenne.cellules.canaux, 'Application, Telegram')
  egal(garenne.cellules.dernier, '17 nov.')
  assert.equal(vide.note, 'Aucun appel sur la période')   // [CA1] un potager sans appel figure, à zéro
  egal(vide.cellules.cout, '—')
  egal(vide.cellules.appels, '0')
})

test('lignesJardiniers : e-mail, potagers, inscription ; la ligne automatique n\'a pas de fiche', () => {
  const l = lignesJardiniers([
    { ...base, id: 1, libelle: 'a@exemple.fr', potagers: 2, inscrit_le: '2026-01-05', appels: 4, cout_micro_eur: 1000, automatique: false },
    { ...base, id: null, libelle: 'Tâches automatiques', potagers: null, inscrit_le: null, appels: 2, cout_micro_eur: 500, automatique: true },
  ], 'cout')
  egal(l[0].cellules.potagers, '2'); egal(l[0].cellules.inscrit, '5 janv.')
  assert.equal(l[1].cle, 'automatique'); assert.equal(l[1].automatique, true); egal(l[1].cellules.potagers, '—')
  assert.equal(l[1].note, 'Appels de fond, sans jardinier')
})

test('chiffresBandeau : potagers, jardiniers, médiane, P95, premier décile', () => {
  const c = chiffresBandeau({
    potagers_existants: 5, potagers_actifs: 3, jardiniers_inscrits: 4, jardiniers_actifs: 3,
    cout_median_par_jardinier_micro_eur: 400_000, cout_p95_par_jardinier_micro_eur: 600_000, part_cout_premier_decile: 0.545,
  })
  assert.deepEqual(c.map((x) => x.id), ['potagers', 'jardiniers', 'mediane', 'p95', 'decile'])
  egal(c[0].texte, '5'); egal(c[0].note, '3 actifs sur la période')
  egal(c[2].texte, '0,400 €'); egal(c[3].texte, '0,600 €'); egal(c[4].texte, '54,5 %')
})

test('chiffresBandeau : sans jardinier actif, rien d\'inventé', () => {
  const c = chiffresBandeau({ potagers_existants: 2, potagers_actifs: 0, jardiniers_inscrits: 1, jardiniers_actifs: 0,
    cout_median_par_jardinier_micro_eur: null, cout_p95_par_jardinier_micro_eur: null, part_cout_premier_decile: null })
  egal(c[2].texte, '—'); egal(c[4].texte, '—'); egal(c[2].note, 'aucun jardinier actif')
})

test('fiche : graphique à une série, vide quand rien n\'a été appelé', () => {
  const g = { pas: 'jour', points: ['2026-11-16', '2026-11-17'], appels: [0, 9], cout_micro_eur: [0, 900_000] }
  const m = modeleCout(g)
  assert.equal(m.series.length, 1); assert.deepEqual(m.series[0].valeurs, [0, 900_000]); assert.equal(m.points[1].libelle, '17 nov.')
  assert.equal(aucunAppel(g), false)
  assert.equal(aucunAppel({ ...g, appels: [0, 0] }), true)
  assert.deepEqual(modeleCout({ ...g, cout_micro_eur: [null, null] }).series[0].valeurs, [0, 0])
})

test('fiche : part de chaque membre, rôle en français, tâches automatiques', () => {
  const l = lignesPartage([
    { id: 1, libelle: 'a@exemple.fr', role: 'owner', appels: 6, cout_micro_eur: 600_000, part: 0.667, automatique: false },
    { id: null, libelle: 'Tâches automatiques', role: null, appels: 1, cout_micro_eur: 100_000, part: 0.111, automatique: true },
  ])
  egal(l[0].cellules.role, 'propriétaire'); egal(l[0].cellules.part, '66,7 %'); egal(l[1].cellules.role, '—')
})

test('fiche : répartition par type et par canal', () => {
  const t = lignesRepartition([{ cle: 'agent', libelle: 'agent', appels: 8, cout_micro_eur: 800_000, part: 0.8 }])
  assert.equal(t[0].mono, true); egal(t[0].cellules.cout, '0,800 €')
  const c = lignesRepartition([{ cle: 'pwa', libelle: 'pwa', appels: 1, cout_micro_eur: null, part: null }], true)
  assert.equal(c[0].titre, 'Application'); egal(c[0].cellules.cout, '—'); egal(c[0].cellules.part, '—')
})

test('fiche : issues et coût d\'un échange', () => {
  egal(texteIssues({ ok: 12, erreur: 2 }), 'ok 12 · erreur 2')
  egal(texteIssues({}), 'aucun appel')
  egal(resumeEchange({ nb: 0 }).texte, '—')
  const r = resumeEchange({ nb: 8, cout_micro_eur: { mediane: 100_000 }, appels: { mediane: 1 } })
  egal(r.texte, '0,100 €'); egal(r.note, '8 échanges · 1 appel médian')
})
