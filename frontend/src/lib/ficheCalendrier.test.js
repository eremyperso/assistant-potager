// [US-183] Fiche calendrier d'une culture — `npm test`.
//
// Ce qui se vérifie ici : la fenêtre en clair (CA5), les séries en terre (CA8,
// CA9, CA10, pré-position du CA2), la bascule conseillé / recalé de la frise
// (CA11), l'attribution (CA16) et le budget de lectures (CA13, par la source).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  fenetreLisible, fenetreDeAction, plageCourte, carteDeSerie, seriesDeCulture,
  friseDeFiche, attributionDeFiche,
} from './ficheCalendrier.js'
import { TIRET } from './calendrier.js'

const source = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')

// ── Graines (valeurs de TEST, reprises des états de la maquette) ─────────────

const calendriers = (champs = {}) => ({
  zone_climatique: 'oceanique', zone_climatique_origine: 'jardinier',
  attributions: ['Wind River Greens (CC BY 4.0)', 'Wind River Greens (CC BY 4.0)'],
  cultures: {
    tomate: {
      culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
      mois: { semis_pepiniere: [2, 3], semis_pleine_terre: [], plantation: [4, 5], recolte: [7, 8, 9] },
      duree_recolte: '100 à 120 j',
    },
    ail: {
      culture_connue: true, renseigne: false, itineraire: null, itineraire_standard: true,
      mois: { semis_pepiniere: [], semis_pleine_terre: [], plantation: [], recolte: [] },
      duree_recolte: TIRET,
    },
  },
  projections: [],
  ...champs,
})

const projection = (champs = {}) => ({
  parcelle_id: 2, parcelle_nom: 'Parcelle 2', culture: 'Courgette', variete: '',
  etat: 'a_venir', motif: null,
  origine: { action: 'semis', date: '2026-04-12', contexte: 'pleine_terre' },
  plantation_reelle: null,
  levee_attendue: { debut: '2026-04-22', fin: '2026-04-22' },
  recolte_attendue: { debut: '2026-07-16', fin: '2026-07-26' },
  recolte_reelle: null,
  jours_restants: { min: 31, max: 41 },
  retard_jours: null, series_suivantes: 0,
  mois: { semis_pepiniere: [], semis_pleine_terre: [4], plantation: [], croissance: [5, 6], recolte: [7] },
  ...champs,
})

// ── CA5 — fenêtre en clair ──────────────────────────────────────────────────

test('[CA5] une fenêtre s’écrit « avril à juin », un mois seul se nomme, une absence est un tiret', () => {
  assert.equal(fenetreLisible([4, 5, 6]), 'avril à juin')
  assert.equal(fenetreLisible([5]), 'mai')
  assert.equal(fenetreLisible([11, 12, 1, 2]), 'novembre à février')
  assert.equal(fenetreLisible([]), TIRET)
  assert.equal(fenetreLisible(undefined), TIRET)
})

test('[CA5] la fenêtre de l’action choisie est lue dans le calendrier de la zone', () => {
  assert.equal(fenetreDeAction(calendriers(), 'tomate', 'plantation'), 'avril à mai')
  assert.equal(fenetreDeAction(calendriers(), 'tomate', 'semis_pepiniere'), 'février à mars')
  assert.equal(fenetreDeAction(calendriers(), 'tomate', 'semis_pleine_terre'), TIRET)
  assert.equal(fenetreDeAction(null, 'tomate', 'plantation'), TIRET)
})

// ── CA8, CA9 — une série en terre ───────────────────────────────────────────

test('[CA8] une série projetée : parcelle, origine, levée, récolte et reste à courir', () => {
  const s = carteDeSerie(projection())
  assert.equal(s.parcelle, 'Parcelle 2')
  assert.equal(s.origine, 'semis')
  assert.equal(s.origineLisible, 'Semée en place le 12 avril')
  assert.equal(s.levee, '22 avril')
  assert.equal(s.recolteLibelle, '1ʳᵉ récolte attendue')
  assert.equal(s.recolte, '16 – 26 juillet')
  assert.equal(s.reste, '31 à 41 jours')
  assert.equal(s.ecart, null)
  assert.equal(s.raisonSansProjection, null)
})

test('[CA8] l’origine dit la filière, ou la plantation', () => {
  const pep = carteDeSerie(projection({ origine: { action: 'semis', date: '2026-03-01', contexte: 'pepiniere' } }))
  assert.equal(pep.origineLisible, 'Semée en pépinière le 1er mars')
  const plant = carteDeSerie(projection({ origine: { action: 'plantation', date: '2025-10-20', contexte: null } }))
  assert.equal(plant.origine, 'plantation')
  assert.equal(plant.origineLisible, 'Plantée le 20 octobre')
  const nue = carteDeSerie(projection({ origine: { action: 'semis', date: '2026-04-12', contexte: null } }))
  assert.equal(nue.origineLisible, 'Semée le 12 avril')
})

test('[CA8] une récolte attendue dépassée sans récolte notée est dite, jamais cachée', () => {
  const s = carteDeSerie(projection({ etat: 'recolte_depassee', retard_jours: 12 }))
  assert.equal(s.ecart, 'Récolte attendue il y a 12 jours, aucune récolte notée')
  assert.equal(s.reste, null)
})

test('[CA8] une récolte commencée remplace l’attendue par la date constatée', () => {
  const s = carteDeSerie(projection({ etat: 'en_recolte', recolte_reelle: { premiere: '2026-07-18', derniere: '2026-07-30' } }))
  assert.equal(s.recolteLibelle, '1ʳᵉ récolte constatée')
  assert.equal(s.recolte, '18 juillet')
})

test('[CA9] une série sans projection est listée avec ses tirets et la raison', () => {
  const s = carteDeSerie(projection({
    etat: 'sans_recalage', motif: 'contexte_inconnu',
    levee_attendue: null, recolte_attendue: null, jours_restants: null, mois: null,
  }))
  assert.equal(s.levee, null)
  assert.equal(s.recolte, null)
  assert.equal(s.reste, null)
  assert.match(s.raisonSansProjection, /filière connue/)
  // Un motif inconnu garde la raison de la maquette, jamais un silence.
  assert.match(carteDeSerie(projection({ etat: 'sans_recalage', motif: 'autre' })).raisonSansProjection, /Durée inconnue/)
})

test('[CA9] les autres séries d’une même parcelle sont signalées (US-070 / CA10)', () => {
  assert.equal(carteDeSerie(projection({ series_suivantes: 2 })).autresSeries, 2)
})

test('[CA9] une plage à cheval sur deux mois garde ses deux mois', () => {
  assert.equal(plageCourte({ debut: '2026-06-28', fin: '2026-07-05' }), '28 juin – 5 juillet')
  assert.equal(plageCourte(null), null)
})

// ── CA2, CA8, CA10 — toutes les séries de la culture ────────────────────────

test('[Gherkin: Deux séries en terre] les deux sont listées, la plus ancienne en tête', () => {
  const cal = calendriers({
    projections: [
      projection({ parcelle_id: 3, parcelle_nom: 'Parcelle 3', culture: 'haricot', origine: { action: 'semis', date: '2026-05-30', contexte: 'pleine_terre' } }),
      projection({ parcelle_id: 1, parcelle_nom: 'Parcelle 1', culture: 'haricot', origine: { action: 'semis', date: '2026-05-02', contexte: 'pleine_terre' } }),
      projection({ culture: 'tomate' }),
    ],
  })
  const series = seriesDeCulture(cal, 'haricot')
  assert.deepEqual(series.map((s) => s.parcelle), ['Parcelle 1', 'Parcelle 3'])
})

test('[CA1] la fiche est au niveau CULTURE : toutes les variétés, sans égard à la casse', () => {
  const cal = calendriers({
    projections: [
      projection({ culture: 'Tomate', variete: 'Cœur de bœuf' }),
      projection({ culture: 'tomate', variete: 'Cerise', parcelle_id: 4 }),
    ],
  })
  assert.equal(seriesDeCulture(cal, 'tomate').length, 2)
})

test('[CA2] ouverte depuis une tuile, la série de CETTE parcelle est mise en avant', () => {
  const cal = calendriers({ projections: [projection({ parcelle_id: 1 }), projection({ parcelle_id: 2 })] })
  const series = seriesDeCulture(cal, 'courgette', 2)
  assert.deepEqual(series.map((s) => s.enAvant), [false, true])
  assert.ok(seriesDeCulture(cal, 'courgette').every((s) => !s.enAvant))
})

test('[CA10] rien en terre : aucune série — la partie 2 n’a pas lieu d’être', () => {
  assert.deepEqual(seriesDeCulture(calendriers(), 'courgette'), [])
  assert.deepEqual(seriesDeCulture(null, 'courgette'), [])
})

// ── CA11 — la frise dit ce qu'elle montre ───────────────────────────────────

test('[Gherkin: Rien en terre, frise conseillée] la frise est celle de la zone, et le dit', () => {
  const f = friseDeFiche(calendriers(), 'tomate', [])
  assert.equal(f.recalee, false)
  assert.equal(f.titre, 'Calendrier conseillé pour la zone océanique')
  assert.deepEqual(f.frise.plantation, [3, 4])
})

test('[CA11] une série en terre recale la frise sur la plus ancienne, et le dit', () => {
  const cal = calendriers({ projections: [projection()] })
  const f = friseDeFiche(cal, 'courgette', seriesDeCulture(cal, 'courgette'))
  assert.equal(f.recalee, true)
  assert.equal(f.titre, 'Calendrier recalé sur la série de Parcelle 2')
  assert.deepEqual(f.frise.croissance, [4, 5])
})

test('[CA11] une série qui ne se projette pas laisse la frise conseillée', () => {
  const cal = calendriers({ projections: [projection({ culture: 'tomate', etat: 'sans_recalage', mois: null })] })
  const f = friseDeFiche(cal, 'tomate', seriesDeCulture(cal, 'tomate'))
  assert.equal(f.recalee, false)
})

test('[Gherkin: Aucun calendrier] sans fenêtre, la frise est neutre et le titre le dit', () => {
  const f = friseDeFiche(calendriers(), 'ail', [])
  assert.equal(f.frise.degrade, true)
  assert.equal(f.titre, 'Aucune fenêtre connue pour cette zone')
})

test('[CA14] calendrier illisible : frise neutre, sans valeur de repli', () => {
  const f = friseDeFiche(null, 'tomate', [])
  assert.equal(f.frise.degrade, true)
  assert.equal(f.recalee, false)
})

// ── CA16 — attribution ──────────────────────────────────────────────────────

test('[CA16] l’attribution du référentiel apparaît une seule fois', () => {
  assert.equal(attributionDeFiche(calendriers()), 'Wind River Greens (CC BY 4.0)')
  assert.equal(attributionDeFiche(null), null)
})

// ── CA13, CA2, CA1 — branchement, vérifié par la source ─────────────────────

test('[CA13] la fiche ne lit que ce que l’écran d’origine ne lui a pas donné', () => {
  const fiche = source('../components/FicheCalendrier.jsx')
  assert.match(fiche, /calendriersFournis === undefined \? api\.calendriersPlan\(/)
  assert.match(fiche, /confiancesFournies === undefined \? api\.confiancesPlan\(/)
  // Deux appels d'API au plus dans tout le composant.
  assert.equal((fiche.match(/api\.\w+\(/g) || []).length, 2)
})

// ⚠️ [US-222, amendement du 24/09/2026] La fiche parcelle ne porte plus de
// tuiles de culture : la frise, la pastille de confiance et l'ouverture de la
// fiche calendrier depuis une tuile ont quitté `Plan.jsx`. Régression ASSUMÉE
// et annoncée dans `PATCH_NOTES.md` — elles reviennent avec la fiche culture
// (US-206, US-207). Ce que ces tests garantissaient est donc vérifié là où le
// chemin existe encore : Stocks, et le composant lui-même.

test('[CA13, CA2] la fiche reçoit ce que l’écran a déjà chargé — aucune lecture de plus', () => {
  const stocks = source('../views/Stocks.jsx')
  const bloc = stocks.slice(stocks.indexOf('<FicheCalendrier'), stocks.indexOf('/>', stocks.indexOf('<FicheCalendrier')))
  assert.ok(bloc.includes('dateRef='), 'prop absente : dateRef=')
  // L'onglet Parcelles, lui, n'ouvre plus la fiche : il n'a plus de tuile d'où
  // l'ouvrir, et ne lit donc plus ni calendrier ni confiance.
  const plan = source('../views/Plan.jsx')
  assert.doesNotMatch(plan, /<FicheCalendrier/)
  assert.doesNotMatch(plan, /api\.calendriersPlan|api\.confiancesPlan/)
})

test('[CA1] depuis Stocks, chaque ligne ET chaque carte portent la puce qui ouvre la fiche', () => {
  const stocks = source('../views/Stocks.jsx')
  assert.equal((stocks.match(/<PuceFiche /g) || []).length, 2)
  assert.match(stocks, /<FicheCalendrier/)
})

test('[CA12] le composant de frise partagé n’est pas modifié par cette US', () => {
  assert.doesNotMatch(source('../components/ui/MonthStrip.jsx'), /US-183/)
})

test('[CA15] la fiche se ferme au clavier (Échap, dans le Modal partagé)', () => {
  assert.match(source('../components/ui/Modal.jsx'), /e\.key === 'Escape'/)
})

test('[CA2, retour terrain 18/09] chaque ligne de Stocks garde une entrée VISIBLE vers la fiche', () => {
  // Sans geste d'actualité, la pastille d'étoiles se tait mais la puce
  // « calendrier » la remplace : jamais une ligne sans porte d'entrée.
  const stocks = source('../views/Stocks.jsx')
  assert.match(stocks, /<PuceConfiance[\s\S]*?onClick=/)
})

test('[retour terrain 18/09] « Pourquoi ce niveau ? » mène explicitement à la fiche calendrier', () => {
  // Le chemin vit dans le composant de confiance lui-même : il est donc
  // conservé pour tous les écrans qui le rendront, fiche culture comprise.
  assert.match(source('../components/FicheConfiance.jsx'), /Voir la fiche calendrier/)
})
