// [US-312] La vue Consommation affiche les chiffres de l'API, à l'unité près (CA10), sur un jeu FIXE :
// `fixtures/consommation_fixe.json` est la réponse réelle des routes (vérifiée côté Python par
// tests/test_us312_contrat_consommation.py).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import {
  chiffresCles, periodeSansAppel, blocAudio, lignesTableau, grouperAutres, modeleGraphique,
  tableauGraphique, echelle, sommeSerie, CLE_AUTRES, MAX_SERIES, DIMENSIONS, estLigneAudio,
} from './consommation.js'
import { entier, abrege } from './format.js'

const F = JSON.parse(readFileSync(fileURLToPath(new URL('./fixtures/consommation_fixe.json', import.meta.url)), 'utf8'))
const NBSP = ' '

// ── CA1 — bandeau de chiffres clés ────────────────────────────────────────────────────────────
test('CA1/CA10 : chaque chiffre clé est celui de la synthèse, à l\'unité près', () => {
  const m = F.synthese.mesures
  const cles = Object.fromEntries(chiffresCles(F.synthese).map((c) => [c.id, c]))
  assert.equal(cles.appels.valeur, m.appels)
  assert.equal(cles.jetons_entree.valeur, m.jetons_entree)
  assert.equal(cles.jetons_sortie.valeur, m.jetons_sortie)
  assert.equal(cles.taux_cache.valeur, m.taux_cache)
  assert.equal(cles.mediane.valeur, m.jetons_entree_mediane_par_appel)
  // ce qui est affiché se relit à l'unité près
  assert.equal(cles.appels.texte, entier(m.appels))
  assert.equal(cles.jetons_sortie.texte, entier(m.jetons_sortie))
  assert.equal(cles.mediane.texte, entier(m.jetons_entree_mediane_par_appel))
  assert.equal(Number(cles.jetons_entree.texte.replace(/\D/g, '')), m.jetons_entree)
})

test('CA1 : cinq chiffres clés, chacun avec son écart à la période précédente', () => {
  const cles = chiffresCles(F.synthese)
  assert.deepEqual(cles.map((c) => c.id), ['appels', 'jetons_entree', 'jetons_sortie', 'taux_cache', 'mediane'])
  const p = F.synthese.mesures_precedentes
  assert.ok(cles.every((c) => typeof c.ecart.texte === 'string'))
  // 11 appels contre 3 : +267 %, neutre (un volume n'est ni bon ni mauvais)
  assert.equal(cles[0].ecart.texte, `+267${NBSP}%`)
  assert.equal(cles[0].ecart.jugement, 'neutre')
  // plus de jetons d'entrée qu'avant : défavorable, et dit en toutes lettres
  assert.ok(F.synthese.mesures.jetons_entree > p.jetons_entree)
  assert.equal(cles[1].ecart.jugement, 'defavorable')
  assert.equal(cles[1].ecart.libelle, 'défavorable')
})

test('CA7 : sans filtre, la synthèse ne compte pas les mesures ni les tests', () => {
  assert.equal(F.synthese.mesures.appels, 11)
  assert.equal(F.synthese_avec_mesures.mesures.appels, 13)
  assert.deepEqual(F.synthese.periode.provenances, ['usage', 'fond'])
})

// ── CA2, CA3, CA8 — graphique ─────────────────────────────────────────────────────────────────
test('CA2 : le graphique sépare la part servie par le cache', () => {
  const g = modeleGraphique(F.serie_entree, F.serie_cache, '')
  assert.equal(g.mode, 'total')
  const [horsCache, cache] = g.series            // maquette : hors cache dessous, cache dessus
  assert.deepEqual(g.series.map((x) => x.libelle), ['hors cache', 'servi par le cache'])
  assert.equal(sommeSerie(cache.valeurs), F.synthese.mesures.jetons_cache)
  assert.equal(sommeSerie(cache.valeurs) + sommeSerie(horsCache.valeurs), F.synthese.mesures.jetons_entree)
})

test('CA8 : un jour sans appel apparaît à zéro, pas comme un trou', () => {
  const g = modeleGraphique(F.serie_entree, F.serie_cache, '')
  const i = g.points.findIndex((p) => p.cle === '2026-11-05')
  assert.ok(i >= 0, 'le 5 novembre est un point du graphique')
  assert.equal(g.total[i], 0)
  assert.ok(g.series.every((s) => s.valeurs[i] === 0))
  assert.equal(g.points.length, 7)
})

test('CA3 : ventilé par modèle, une pile par modèle et le cache en pointillé', () => {
  const g = modeleGraphique(F.serie_entree_par_modele, F.serie_cache, 'modele')
  assert.equal(g.mode, 'ventile')
  assert.deepEqual(g.series.map((s) => s.cle).sort(), ['mistral/ministral', 'mistral/small'])
  assert.equal(sommeSerie(g.series.flatMap((s) => s.valeurs)), F.synthese.mesures.jetons_entree)
  assert.equal(sommeSerie(g.cache), F.synthese.mesures.jetons_cache)
})

test('CA3 : cinq teintes au plus, les suivantes regroupées en « Autres » sans perdre un jeton', () => {
  const sept = Array.from({ length: 7 }, (_, i) => ({ cle: `m${i}`, libelle: `m${i}`, valeurs: [i + 1, 10], total: i + 11 }))
  const g = grouperAutres(sept)
  assert.equal(MAX_SERIES, 5)
  assert.equal(g.length, MAX_SERIES + 1)            // cinq séries + « Autres »
  assert.equal(g.at(-1).cle, CLE_AUTRES)
  assert.deepEqual(g.at(-1).valeurs, [6 + 7, 20])
  assert.equal(sommeSerie(g.flatMap((s) => s.valeurs)), sommeSerie(sept.flatMap((s) => s.valeurs)))
  assert.equal(grouperAutres(sept.slice(0, 5)).length, 5)   // cinq séries : rien n'est regroupé
})

test('CA3 : le sélecteur propose modèle, type d\'appel et canal', () => {
  assert.deepEqual(DIMENSIONS.map((d) => d.libelle), ['Cache', 'Modèle', 'Type', 'Canal'])
  assert.deepEqual(DIMENSIONS.map((d) => d.id), ['', 'modele', 'appel_type', 'canal'])
})

test('CA9 : le tableau équivalent a une ligne par pas et les mêmes totaux que le graphique', () => {
  const g = modeleGraphique(F.serie_entree, F.serie_cache, '')
  const t = tableauGraphique(g)
  assert.equal(t.lignes.length, g.points.length)
  assert.equal(t.lignes[0].length, t.entetes.length)
  assert.equal(t.entetes.at(-1), 'dont cache')
  const jour5 = t.lignes.find((l) => l[0] === '5 nov.')
  assert.deepEqual(jour5.slice(1), ['0', '0', '0', '0'])
})

test('pas d\'une journée : le pas est l\'heure (24 points)', () => {
  const serie = { pas: 'heure', points: Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, '0')}h`), total: Array(24).fill(0), series: [] }
  const g = modeleGraphique(serie, { ...serie }, '')
  assert.equal(g.pas, 'heure')
  assert.equal(g.points[8].libelle, '08h')
})

test('échelle : graduations rondes qui couvrent le maximum', () => {
  assert.deepEqual(echelle(0).graduations, [0, 1])
  const e = echelle(37_000)
  assert.ok(e.max >= 37_000 && e.graduations.length <= 7)
  assert.deepEqual(echelle(8).graduations, [0, 2, 4, 6, 8])
})

// ── CA4, CA5 — tableaux ───────────────────────────────────────────────────────────────────────
test('CA4 : le tableau par type d\'appel donne appels, jetons, part et médiane, sans l\'audio', () => {
  const lignes = lignesTableau(F.par_type)
  assert.ok(!lignes.some((l) => l.cle === 'dictee' || l.cle === 'voix'))
  const agent = lignes.find((l) => l.cle === 'agent')
  const brut = F.par_type.lignes.find((l) => l.cle === 'agent')
  assert.equal(agent.appels, brut.appels)
  assert.equal(agent.jetonsEntree, brut.jetons_entree)
  assert.equal(agent.jetonsSortie, brut.jetons_sortie)
  assert.equal(agent.mediane, brut.jetons_entree_mediane_par_appel)
  assert.match(agent.texte.part, /%$/)
  assert.equal(agent.texte.jetonsEntree, entier(brut.jetons_entree))
})

test('CA4 : les parts du tableau sont celles de l\'API et somment à 100 % des jetons', () => {
  const somme = lignesTableau(F.par_type).reduce((a, l) => a + l.part, 0)
  assert.ok(Math.abs(somme - 1) < 1e-9)
})

test('CA5 : le tableau par modèle a les mêmes colonnes', () => {
  const l = lignesTableau(F.par_modele)
  assert.deepEqual(l.map((x) => x.cle).sort(), ['mistral/ministral', 'mistral/small', 'voxtral'].filter((k) => l.some((x) => x.cle === k)).sort())
  assert.deepEqual(Object.keys(l[0].texte), ['abrege', 'appels', 'jetonsEntree', 'jetonsSortie', 'part', 'mediane'])
})

// ── CA6 — audio à part ────────────────────────────────────────────────────────────────────────
test('CA6 : secondes de dictée et caractères de voix sont un bloc à part, jamais ajoutés aux jetons', () => {
  const audio = blocAudio(F.synthese, F.par_type)
  assert.deepEqual(audio.dictee, { appels: 2, secondes: 50 })
  assert.deepEqual(audio.voix, { appels: 1, caracteres: 1200 })
  assert.equal(F.synthese.mesures.jetons_entree, 8000 + 9000 + 500 + 7000 + 450 + 10000 + 6000 + 8500)
})

test('état vide : une période sans appel est repérée, sans erreur', () => {
  const vide = { mesures: { ...F.synthese.mesures, appels: 0 }, mesures_precedentes: F.synthese.mesures_precedentes }
  assert.equal(periodeSansAppel(vide), true)
  assert.equal(periodeSansAppel(F.synthese), false)
})

test('CA3 : ventilé, chaque série porte sa part du total (légende « modèle 95 % »)', () => {
  const g = modeleGraphique(F.serie_entree_par_modele, F.serie_cache, 'modele')
  const somme = g.series.reduce((a, s) => a + s.part, 0)
  assert.ok(Math.abs(somme - 1) < 1e-9)
  assert.ok(g.series.every((s) => !s.libelle.startsWith('mistral/')))   // préfixe retiré pour la légende
})

test("CA5 : un modèle d'audio (aucun jeton) n'est pas une ligne du tableau par modèle", () => {
  const brut = F.par_modele.lignes.find((l) => l.cle === 'voxtral')
  assert.ok(brut, "le jeu fixe contient un modèle d'audio")
  assert.equal(lignesTableau(F.par_modele).some((l) => l.cle === 'voxtral'), false)
  assert.equal(estLigneAudio(brut), true)
})

test("CA4 : la forme courte d'une ligne (carte du téléphone) est celle de la maquette", () => {
  const agent = lignesTableau(F.par_type).find((l) => l.cle === 'agent')
  assert.equal(agent.texte.abrege, abrege(agent.jetonsEntree))
  assert.equal(abrege(2_310_000), `2,31${NBSP}M`)
  assert.equal(abrege(615_000), `615${NBSP}k`)
  assert.equal(abrege(8140), `8${NBSP}140`)
})
