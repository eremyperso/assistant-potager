// [US-180, US-183] Niveau de confiance — pastille, puce, fiches — `npm test`.
//
// Ce qui se vérifie ici : le CHOIX de l'action (US-180 / CA1, CA2 ; US-183 / CA4),
// les états de la tuile (US-180 / CA3, CA7), le repli des règles gagnées
// (maquette gelée), la récolte en fourchette (CA5) et l'accessibilité (CA8, CA15).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  confianceDeTuile, meilleureCandidate, actionsDeFiche, reglesVisibles, libelleEtoiles,
  etoilesAffichables, libelleAction, meteoIndeterminee, recolteLisible, dateLongue,
  CLE_PHASE_PAR_ACTION, LIBELLE_ACTION, LIBELLE_ENREGISTRER, LIBELLE_NIVEAU, NIVEAU_COURT,
  ETAT_CONFIANCE, ETAT_RIEN_A_FAIRE, ETAT_SANS_CALENDRIER, ETAT_INDISPONIBLE,
} from './confiance.js'
import { PRIORITE_PHASES, TIRET } from './calendrier.js'

// ── Graines ──────────────────────────────────────────────────────────────────

const motif = (regle, etat, libelle, points, points_max) => ({
  regle, regle_libelle: regle, etat, libelle, points, points_max,
})

const GAGNEES = [
  motif('R1', 'gagne', 'Dans la fenêtre conseillée pour ta zone', 40, 40),
  motif('R2', 'gagne', 'La dernière gelée moyenne est passée', 20, 20),
  motif('R3', 'gagne', 'Aucun gel annoncé sur la quinzaine', 20, 20),
  motif('R4', 'gagne', 'Nuits douces sur la semaine', 10, 10),
  motif('R5', 'gagne', 'La récolte tient dans la saison', 10, 10),
]

const evaluation = (action, etoiles, score, champs = {}) => ({
  culture: 'tomate', action, action_libelle: action, etoiles, score,
  score_max_atteignable: 100, motifs: GAGNEES, avertissements: [],
  recolte_attendue: { min: '2027-07-04', max: '2027-07-24' },
  ...champs,
})

const reponse = (cultures) => ({ date: '2027-05-05', cultures })

const entree = (candidates, { a_calendrier = true, actions = candidates } = {}) => ({
  culture: 'tomate', culture_connue: true, a_calendrier, candidates, actions,
})

// ── US-180 / CA1, CA2 — l'action de la tuile ─────────────────────────────────

test('[US-180 / CA1] la tuile porte la candidate rendue par le moteur', () => {
  const lu = confianceDeTuile(reponse({ tomate: entree([evaluation('plantation', 3, 100)]) }), 'tomate')
  assert.equal(lu.etat, ETAT_CONFIANCE)
  assert.equal(lu.confiance.action, 'plantation')
})

test('[US-180 / CA2] deux phases candidates : le meilleur score l’emporte, quel que soit l’ordre reçu', () => {
  const gagnante = meilleureCandidate([evaluation('semis_pepiniere', 1, 40), evaluation('semis_pleine_terre', 3, 90)])
  assert.equal(gagnante.action, 'semis_pleine_terre')
})

test('[US-180 / CA2] à score égal, c’est la règle de priorité de la frise qui tranche', () => {
  const egalite = (a, b) => meilleureCandidate([evaluation(a, 2, 70), evaluation(b, 2, 70)]).action
  assert.equal(egalite('semis_pleine_terre', 'plantation'), 'plantation')
  assert.equal(egalite('plantation', 'semis_pleine_terre'), 'plantation')
  assert.equal(egalite('semis_pepiniere', 'semis_pleine_terre'), 'semis_pleine_terre')
})

test('[US-180 / CA2] la règle de priorité est IMPORTÉE de la frise, jamais recopiée', () => {
  const source = readFileSync(new URL('./confiance.js', import.meta.url), 'utf8')
  assert.match(source, /import \{[^}]*PRIORITE_PHASES[^}]*\} from '\.\/calendrier\.js'/)
  for (const cle of Object.values(CLE_PHASE_PAR_ACTION)) {
    assert.ok(PRIORITE_PHASES.includes(cle), `${cle} absente de PRIORITE_PHASES`)
  }
})

// ── US-180 / CA3, CA7 — les états de la tuile ────────────────────────────────

test('[maquette] hors saison, la tuile porte quand même le niveau du geste le mieux noté', () => {
  // La tomate en septembre : aucune candidate, mais deux gestes évalués.
  const e = entree([], { actions: [evaluation('semis_pepiniere', 1, 30), evaluation('plantation', 2, 50)] })
  const lu = confianceDeTuile(reponse({ tomate: e }), 'tomate')
  assert.equal(lu.etat, ETAT_CONFIANCE)
  assert.equal(lu.confiance.action, 'plantation')
})

test('[maquette] la tuile et la fiche retiennent le même geste', () => {
  const e = entree([evaluation('plantation', 3, 90)], {
    actions: [evaluation('semis_pepiniere', 2, 60), evaluation('plantation', 3, 90)],
  })
  assert.equal(confianceDeTuile(reponse({ tomate: e }), 'tomate').confiance.action,
    meilleureCandidate(actionsDeFiche(e)).action)
})

test('[US-180 / CA3] une réponse sans aucune action évaluée ne montre aucune pastille', () => {
  const lu = confianceDeTuile(reponse({ tomate: entree([], { actions: [] }) }), 'tomate')
  assert.equal(lu.etat, ETAT_RIEN_A_FAIRE)
  assert.equal(lu.confiance, null)
})

test('[US-180 / CA3] sans calendrier pour la zone : un état distinct, sans niveau', () => {
  const lu = confianceDeTuile(reponse({ ail: entree([], { a_calendrier: false }) }), 'ail')
  assert.equal(lu.etat, ETAT_SANS_CALENDRIER)
  assert.equal(lu.confiance, null)
})

test('[US-180 / CA7] lecture en échec ou culture absente : rien, et aucune valeur de repli', () => {
  for (const cas of [null, undefined, {}, reponse({})]) {
    const lu = confianceDeTuile(cas, 'tomate')
    assert.equal(lu.etat, ETAT_INDISPONIBLE)
    assert.equal(lu.confiance, null)
  }
})

// ── US-183 / CA4 — le sélecteur de la fiche ─────────────────────────────────

test('[US-183 / CA4] le sélecteur ne propose que les actions qui ont une fenêtre, dans l’ordre du geste', () => {
  const e = entree([], { actions: [evaluation('plantation', 3, 100), evaluation('semis_pepiniere', 1, 30)] })
  assert.deepEqual(actionsDeFiche(e).map((a) => a.action), ['semis_pepiniere', 'plantation'])
  assert.deepEqual(actionsDeFiche(null), [])
})

test('[US-183 / CA4] l’action pré-sélectionnée est la mieux notée, même hors fenêtre de la semaine', () => {
  // La tomate au 15 août : aucune candidate pour la tuile, mais la fiche propose
  // quand même ses deux gestes, pré-positionnée sur le mieux noté.
  const e = entree([], { actions: [evaluation('semis_pepiniere', 1, 20), evaluation('plantation', 1, 30)] })
  assert.equal(meilleureCandidate(actionsDeFiche(e)).action, 'plantation')
})

test('[US-183 / CA6] le bouton d’enregistrement nomme le geste', () => {
  assert.equal(LIBELLE_ENREGISTRER.plantation, 'Enregistrer la plantation')
  assert.equal(LIBELLE_ENREGISTRER.semis_pleine_terre, 'Enregistrer le semis')
  assert.equal(LIBELLE_ENREGISTRER.semis_pepiniere, 'Enregistrer le semis')
})

// ── Maquette gelée — règles repliées ────────────────────────────────────────

test('[maquette] les règles perdues et indéterminées restent visibles, les gagnées se replient', () => {
  const motifs = [
    motif('R1', 'gagne', 'Dans la fenêtre', 40, 40),
    motif('R2', 'indetermine', 'Sensibilité au gel inconnue', 0, 20),
    motif('R4', 'perdu', 'Nuits fraîches', 0, 10),
  ]
  assert.deepEqual(reglesVisibles(motifs).map((m) => m.regle), ['R2', 'R4'])
  assert.deepEqual(reglesVisibles(motifs, true).map((m) => m.regle), ['R1', 'R2', 'R4'])
  assert.deepEqual(reglesVisibles(GAGNEES), [])
})

// ── CA5, CA7 — la fiche ─────────────────────────────────────────────────────

test('[US-183 / CA7] météo indéterminée : la fiche invite à localiser le potager', () => {
  const sansMeteo = evaluation('plantation', 2, 70, {
    motifs: [motif('R1', 'gagne', 'Dans la fenêtre', 40, 40), motif('R3', 'indetermine', 'Météo indisponible', 0, 20)],
  })
  assert.equal(meteoIndeterminee(sansMeteo), true)
  assert.equal(meteoIndeterminee(evaluation('plantation', 3, 100)), false)
})

test('[US-183 / CA5] récolte en fourchette, mois factorisé quand il est commun, ou un tiret', () => {
  assert.equal(recolteLisible(evaluation('plantation', 3, 100)), 'entre le 4 et le 24 juillet')
  assert.equal(recolteLisible(evaluation('plantation', 3, 100, { recolte_attendue: { min: '2027-06-28', max: '2027-07-05' } })),
    'entre le 28 juin et le 5 juillet')
  assert.equal(recolteLisible(evaluation('plantation', 3, 100, { recolte_attendue: { min: null, max: null } })), TIRET)
  assert.equal(recolteLisible(null), TIRET)
})

test('[US-183] la date de référence s’écrit en toutes lettres dans l’en-tête', () => {
  assert.equal(dateLongue('2026-06-15'), '15 juin 2026')
  assert.equal(dateLongue('2026-05-01'), '1er mai 2026')
  assert.equal(dateLongue(null), '')
})

// ── US-180 / CA8, US-183 / CA15 — accessibilité ─────────────────────────────

test('[CA8] les étoiles ont un équivalent textuel qui nomme le niveau', () => {
  assert.equal(libelleEtoiles(1), '1 étoile sur 3 — Confiance faible')
  assert.equal(libelleEtoiles(2), '2 étoiles sur 3 — Confiance moyenne')
  assert.equal(libelleEtoiles(3), '3 étoiles sur 3 — Confiance élevée')
})

test('[CA8] les étoiles vides sont rendues : le niveau se lit sans couleur', () => {
  assert.equal(etoilesAffichables(1), '★☆☆')
  assert.equal(etoilesAffichables(2), '★★☆')
  assert.equal(etoilesAffichables(3), '★★★')
})

test('[maquette] les libellés de niveau sont ceux de la maquette gelée', () => {
  assert.deepEqual({ ...LIBELLE_NIVEAU }, { 1: 'Confiance faible', 2: 'Confiance moyenne', 3: 'Confiance élevée' })
  assert.deepEqual({ ...NIVEAU_COURT }, { 1: 'faible', 2: 'moyenne', 3: 'élevée' })
})

test('[US-180 / CA1] chaque action a son libellé à l’infinitif, et rien n’est inventé', () => {
  assert.deepEqual(Object.keys(LIBELLE_ACTION), ['semis_pepiniere', 'semis_pleine_terre', 'plantation'])
  assert.equal(libelleAction('semis_pepiniere'), 'Semer en pépinière')
  assert.equal(libelleAction('recolte'), '')
})
