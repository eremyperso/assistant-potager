// [US-313] La vue Coût affiche les chiffres de l'API, à l'unité près, sur un jeu FIXE :
// `fixtures/cout_fixe.json` est la réponse réelle des routes (vérifiée côté Python par
// tests/test_us313_315_contrat_vues.py).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import {
  chiffresCles, avertissementNonChiffres, texteGrille, modeleGraphiqueCout, aucunCout, lignesEchanges,
  lignesPotagers, lirePrix, marge, lirePrixGarde, garderPrix, CLE_PRIX, DEFINITION_ACTIF, MENTION_TARIF,
  DIMENSIONS_COUT, libelleCanal,
} from './cout.js'
import { euro } from './format.js'

const F = JSON.parse(readFileSync(fileURLToPath(new URL('./fixtures/cout_fixe.json', import.meta.url)), 'utf8'))
const NBSP = ' '

const stockage = () => {
  const m = new Map()
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) }
}

// ── CA1 — bandeau ──────────────────────────────────────────────────────────────────────────────
test("CA1 : le coût de la période, du mois, la projection et le coût par jardinier actif sont ceux de l'API", () => {
  const c = Object.fromEntries(chiffresCles(F.cout).map((x) => [x.id, x]))
  assert.deepEqual(Object.keys(c), ['periode', 'mois', 'projection', 'par_actif'])
  assert.equal(c.periode.valeur, F.cout.cout_micro_eur)
  assert.equal(c.mois.valeur, F.cout.mois.cout_micro_eur)
  assert.equal(c.projection.valeur, F.cout.mois.projection_fin_de_mois_micro_eur)
  assert.equal(c.par_actif.valeur, F.cout.cout_par_jardinier_actif_micro_eur)
  assert.equal(c.periode.texte, euro(F.cout.cout_micro_eur))
  assert.equal(c.par_actif.note, '4 jardiniers actifs')
})

test('CA1 : la projection se lit comme « moyenne des 7 derniers jours prolongée »', () => {
  const m = F.cout.mois
  // jour de référence du jeu : le 10 ; novembre a 30 jours → 20 jours restants
  assert.equal(m.projection_fin_de_mois_micro_eur, Math.round(m.cout_micro_eur + (m.cout_7_jours_micro_eur / 7) * 20))
  assert.match(chiffresCles(F.cout)[2].note, /7 derniers jours/)
})

test('CA1 : sans coût chiffré, le chiffre est un tiret, pas un zéro inventé', () => {
  const sans = { ...F.cout, cout_micro_eur: null, appels: 3, mois: { ...F.cout.mois, cout_micro_eur: null, projection_fin_de_mois_micro_eur: null }, cout_par_jardinier_actif_micro_eur: null }
  const c = chiffresCles(sans)
  assert.deepEqual(c.map((x) => x.texte), ['—', '—', '—', '—'])
  assert.equal(c[0].note, 'aucun appel chiffré')
})

test('CA1 (Gherkin) : 4 jardiniers actifs pour 1,20 € → 0,30 € par jardinier actif', () => {
  const g = { ...F.cout, cout_micro_eur: 1_200_000, jardiniers_actifs: 4, cout_par_jardinier_actif_micro_eur: 300_000 }
  assert.equal(chiffresCles(g)[3].texte, `0,300${NBSP}€`)
  assert.equal(chiffresCles(g)[0].texte, `1,20${NBSP}€`)
})

// ── CA2, CA9 — définition et mention ────────────────────────────────────────────────────────────
test('CA2 : la définition du jardinier actif est écrite', () => {
  assert.match(DEFINITION_ACTIF, /au moins une ligne de provenance « usage » sur la période/)
})

test('CA9 : la mention « coût estimé au tarif public, hors palier gratuit » est écrite', () => {
  assert.equal(MENTION_TARIF, 'Coût estimé au tarif public, hors palier gratuit.')
})

// ── CA3 — graphique par jour ────────────────────────────────────────────────────────────────────
test('CA3 : le graphique de coût a un pas par jour, ventilé, et la somme est le coût de la période', () => {
  for (const serie of [F.serie_par_modele, F.serie_par_canal]) {
    const g = modeleGraphiqueCout(serie)
    assert.equal(g.points.length, 7)
    assert.equal(g.mode, 'empile')
    const somme = g.series.reduce((a, s) => a + s.total, 0)
    assert.equal(somme, F.cout.cout_micro_eur)
  }
})

test('CA3 : au-delà de cinq séries, les suivantes sont regroupées en « Autres »', () => {
  const points = ['2026-11-09', '2026-11-10']
  const serie = { pas: 'jour', points, total: [21, 21], series: Array.from({ length: 7 }, (_, i) => ({ cle: `m${i}`, total: 7 - i, valeurs: [7 - i, 0] })) }
  const g = modeleGraphiqueCout(serie)
  assert.equal(g.series.length, 6)
  assert.equal(g.series[5].libelle, 'Autres')
  assert.equal(g.series[5].total, 2 + 1)
})

test('CA3 : un pas sans ligne chiffrée vaut zéro dans le graphique ; aucun coût du tout est détecté', () => {
  const g = modeleGraphiqueCout({ pas: 'jour', points: ['2026-11-09'], total: [null], series: [{ cle: 'm', total: null, valeurs: [null] }] })
  assert.deepEqual(g.total, [0])
  assert.equal(aucunCout({ series: [{ total: null }] }), true)
  assert.equal(aucunCout(F.serie_par_modele), false)
})

test('CA3 : trois ventilations au choix — modèle, type, canal', () => {
  assert.deepEqual(DIMENSIONS_COUT.map((d) => d.id), ['modele', 'appel_type', 'canal'])
})

// ── CA4 — coût d'un échange ─────────────────────────────────────────────────────────────────────
test("CA4 : médiane, P95 et maximum du coût d'un échange, et nombre médian d'appels, par canal", () => {
  const lignes = lignesEchanges(F.cout)
  assert.deepEqual(lignes.map((l) => l.cle), F.cout.echanges_par_canal.map((l) => l.canal))
  const pwa = lignes.find((l) => l.cle === 'pwa')
  const api = F.cout.echanges_par_canal.find((l) => l.canal === 'pwa')
  assert.equal(pwa.cellules.mediane, euro(api.cout_micro_eur.mediane))
  assert.equal(pwa.cellules.p95, euro(api.cout_micro_eur.p95))
  assert.equal(pwa.cellules.maximum, euro(api.cout_micro_eur.maximum))
  assert.equal(pwa.cellules.appels, '1')
  assert.equal(pwa.titre, libelleCanal('pwa'))
})

test('CA4 : un échange non chiffré est signalé sous sa ligne', () => {
  const telegram = lignesEchanges(F.cout).find((l) => l.cle === 'telegram')
  assert.equal(telegram.note, '1 échange non chiffré')
})

// ── CA5 — les 10 potagers les plus coûteux ──────────────────────────────────────────────────────
test('CA5 : les potagers sont classés avec coût, appels et part du total', () => {
  const lignes = lignesPotagers(F.potagers)
  assert.ok(lignes.length <= 10)
  assert.deepEqual(lignes.map((l) => l.titre), F.potagers.lignes.map((l) => l.libelle))
  const premier = F.potagers.lignes[0]
  assert.equal(lignes[0].cellules.cout, euro(premier.cout_micro_eur))
  assert.equal(lignes[0].cellules.appels, String(premier.appels))
  assert.match(lignes[0].cellules.part, /%$/)
  // les parts se somment à 100 % quand tous les potagers sont listés
  assert.ok(Math.abs(F.potagers.lignes.reduce((a, l) => a + l.part, 0) - 1) < 1e-9)
})

// ── CA6 — la marge d'un abonnement ──────────────────────────────────────────────────────────────
test('CA6 : le prix se lit à la française', () => {
  assert.equal(lirePrix('3'), 3)
  assert.equal(lirePrix('2,50'), 2.5)
  assert.equal(lirePrix('2.5'), 2.5)
  assert.equal(lirePrix(` 3,00${NBSP}€ `), 3)
  assert.equal(lirePrix(''), null)
  assert.equal(lirePrix('abc'), null)
  assert.equal(lirePrix('-3'), null)
  assert.equal(lirePrix('3,456'), null)
})

test('CA6 (Gherkin) : à 3 € la marge se calcule pour le jardinier médian et pour le P95', () => {
  const m = marge(3, F.cout.par_jardinier)
  assert.equal(m.mediane.margeMicro, Math.round(3_000_000 - F.cout.par_jardinier.mensuel.mediane))
  assert.equal(m.p95.margeMicro, Math.round(3_000_000 - F.cout.par_jardinier.mensuel.p95))
  assert.equal(m.mediane.positive, true)
  assert.equal(m.mediane.texte, euro(m.mediane.margeMicro))
})

test('CA6 : un prix inférieur au coût est une perte, dite par son signe', () => {
  const m = marge(0.1, F.cout.par_jardinier)
  assert.equal(m.p95.positive, false)
  assert.ok(m.p95.margeMicro < 0)
  assert.match(m.p95.texte, /^−/)
})

test('CA6 : sans prix lisible ou sans jardinier actif, pas de marge', () => {
  assert.equal(marge(null, F.cout.par_jardinier), null)
  assert.equal(marge(3, { nb: 0, mensuel: { mediane: null, p95: null } }), null)
})

test("CA6 : le prix est gardé sur l'appareil seulement, et ne casse pas sans stockage", () => {
  const s = stockage()
  assert.equal(lirePrixGarde(s), '')
  garderPrix(s, '3,50')
  assert.equal(lirePrixGarde(s), '3,50')
  assert.equal(s.getItem(CLE_PRIX), '3,50')
  garderPrix(s, '')
  assert.equal(lirePrixGarde(s), '')
  const casse = { getItem() { throw new Error('refusé') }, setItem() { throw new Error('refusé') }, removeItem() { throw new Error('refusé') } }
  assert.equal(lirePrixGarde(casse), '')
  assert.doesNotThrow(() => garderPrix(casse, '3'))
})

// ── CA7, CA8 — non chiffrés, grille ─────────────────────────────────────────────────────────────
test('CA7 : « n appels non chiffrés » avec la liste des modèles concernés', () => {
  const a = avertissementNonChiffres(F.cout)
  assert.equal(a.titre, '1 appel non chiffré')
  assert.deepEqual(a.modeles.map((m) => m.modele), ['inconnu/modele'])
  assert.equal(avertissementNonChiffres({ ...F.cout, lignes_non_chiffrees: 0, modeles_non_chiffres: [] }), null)
  assert.equal(avertissementNonChiffres({ ...F.cout, lignes_non_chiffrees: 5, modeles_non_chiffres: [{ modele: 'a', appels: 5 }] }).titre, '5 appels non chiffrés')
})

test('CA8 : les montants ont la précision utile — millièmes sous 1 €, centimes au-dessus', () => {
  assert.equal(euro(42_000), `0,042${NBSP}€`)
  assert.equal(euro(1_200_000), `1,20${NBSP}€`)
  assert.equal(euro(0), `0,000${NBSP}€`)
})

test('CA8 : la version de grille dominante de la période est affichée', () => {
  assert.equal(texteGrille(F.cout), 'Grille tarifaire 2026-11-12')
  assert.match(texteGrille({ ...F.cout, versions_tarif: { a: 1, b: 2, c: 3 } }), /2 autres versions sur la période/)
  assert.match(texteGrille({ ...F.cout, tarif_version: null, versions_tarif: {} }), /aucune ligne chiffrée/)
})
