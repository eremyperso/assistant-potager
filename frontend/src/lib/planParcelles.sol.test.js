// [US-232 / CA4, CA5, CA10] La carte « Sol et entretien » de la fiche parcelle.
//
// Ce qui est vérifié ici est la COMPOSITION : la carte ne lit rien, elle met en
// forme ce que `GET /plan` a servi. Le filtre — quels gestes sont « sol et
// entretien » — n'est PAS ici : il est dans le domaine (CA2), et c'est
// `tests/test_us232_journal_sol_parcelle.py` qui le couvre.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  carteSol, dateIntervention, libelleIntervention, AUCUNE_INTERVENTION_SOL,
} from './planParcelles.js'

const DATE_REF = '2026-09-23'
const GESTES = ['paillage', 'amendement', 'desherbage', 'binage']

const ev = (id, date, type_action, extra = {}) => ({
  id, date, type_action,
  quantite: null, unite: null, rang: null, culture: null,
  commentaire: null, traitement: null, ...extra,
})

const parcelle = (interventions, total = interventions.length) => ({
  id: 1, nom: 'planche_centrale',
  sol: { interventions, total },
})

// ── S2 : la date ─────────────────────────────────────────────────────────────

test('[S2] la date se dit en jour et mois ; l’année n’apparaît que hors campagne', () => {
  assert.equal(dateIntervention('2026-09-12', DATE_REF), '12 sept.')
  assert.equal(dateIntervention('2026-01-03', DATE_REF), '3 janv.')
  // Hors de la campagne en cours : l'année est écrite.
  assert.equal(dateIntervention('2025-11-08', DATE_REF), '8 nov. 2025')
  // La campagne est celle de la date de RÉFÉRENCE de l'écran, jamais celle de
  // l'horloge : consulter le plan au 15/06/2025 change ce qui porte une année.
  assert.equal(dateIntervention('2025-11-08', '2025-06-15'), '8 nov.')
  assert.equal(dateIntervention(null, DATE_REF), '')
})

// ── S3 : le libellé ──────────────────────────────────────────────────────────

test('[S3] le libellé reprend le geste, sa précision, sa quantité et son rang', () => {
  assert.equal(
    libelleIntervention(ev(1, '2026-09-12', 'paillage', { commentaire: 'de tonte', rang: 1 })),
    'Paillage de tonte sur R1',
  )
  assert.equal(
    libelleIntervention(ev(2, '2026-08-30', 'amendement', { commentaire: 'compost mûr', quantite: 2, unite: 'brouettes' })),
    'Amendement compost mûr, 2 brouettes',
  )
})

test('[S3] rien n’est comblé : un geste sans précision est une ligne valide', () => {
  assert.equal(libelleIntervention(ev(3, '2026-07-04', 'binage')), 'Binage')
  assert.equal(libelleIntervention(ev(4, '2026-07-04', 'desherbage')), 'Désherbage')
  // Un type inconnu de la table n'est ni masqué ni renommé en « Action ».
  assert.equal(libelleIntervention(ev(5, '2026-07-04', 'travail_du_sol')), 'Travail du sol')
})

test('[S3] la précision peut venir du champ `traitement` autant que du commentaire', () => {
  assert.equal(
    libelleIntervention(ev(6, '2026-05-02', 'amendement', { traitement: 'fumier composté' })),
    'Amendement fumier composté',
  )
})

// ── S5, S6, CA10 : les trois états ───────────────────────────────────────────

test('[S6, CA10] aucune intervention : la carte le DIT et garde sa ligne d’aide', () => {
  const carte = carteSol(parcelle([]), { dateRef: DATE_REF, gestesSol: GESTES })
  assert.equal(carte.vide, true)
  assert.equal(carte.message, AUCUNE_INTERVENTION_SOL)
  assert.equal(carte.toutVoir, false)
  // [S7] La phrase garde le nom RÉEL de la parcelle, même vide.
  assert.equal(carte.aide.phrase, 'paillage parcelle planche_centrale')
})

test('[CA10] une seule intervention : ni message d’absence, ni « Tout voir »', () => {
  const carte = carteSol(
    parcelle([ev(1, '2026-09-12', 'paillage', { commentaire: 'de tonte' })]),
    { dateRef: DATE_REF, gestesSol: GESTES },
  )
  assert.equal(carte.vide, false)
  assert.equal(carte.lignes.length, 1)
  assert.equal(carte.toutVoir, false)
})

test('[S5, CA10] au-delà de huit, « Tout voir » apparaît et emporte le filtre', () => {
  const huit = Array.from({ length: 8 }, (_, i) => ev(i + 1, `2026-0${(i % 9) + 1}-01`, 'binage'))
  const carte = carteSol(parcelle(huit, 11), { dateRef: DATE_REF, gestesSol: GESTES })
  assert.equal(carte.lignes.length, 8)
  assert.equal(carte.total, 11)
  assert.equal(carte.toutVoir, true)
  // [CA2, CA8] Le filtre transporte la parcelle et la liste SERVIE — la carte
  // ne connaît aucune liste de gestes de son côté.
  assert.deepEqual(carte.filtre, {
    parcelle: 'planche_centrale',
    gestes: 'paillage,amendement,desherbage,binage',
  })
})

// ── Gherkin ──────────────────────────────────────────────────────────────────

test('[Gherkin] paillage et compost du plus récent au plus ancien, sans le semis', () => {
  // Le service a déjà écarté le semis (S4, CA5) et trié : la carte ne réordonne
  // rien, et c'est exactement ce qu'on vérifie ici.
  const carte = carteSol(parcelle([
    ev(1, '2026-09-12', 'paillage', { commentaire: 'de tonte', rang: 1 }),
    ev(2, '2026-08-30', 'amendement', { commentaire: 'compost mûr', quantite: 2, unite: 'brouettes' }),
  ]), { dateRef: DATE_REF, gestesSol: GESTES })
  assert.deepEqual(carte.lignes.map((l) => l.libelle), [
    'Paillage de tonte sur R1',
    'Amendement compost mûr, 2 brouettes',
  ])
  assert.deepEqual(carte.lignes.map((l) => l.date), ['12 sept.', '30 août'])
})

// ── CA1, CA3, CA7, CA9 : ce que l'écran a le droit de faire ──────────────────

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf-8')

test('[CA1, CA3] la carte ne déclenche aucune lecture : tout vient de `GET /plan`', () => {
  const lib = lire('./planParcelles.js')
  assert.doesNotMatch(lib, /api\./)
  const plan = lire('../views/Plan.jsx')
  // Une seule LECTURE dans tout l'écran — celle du plan. L'autre appel est
  // l'écriture d'US-230, déclenchée par le jardinier, jamais par un affichage.
  assert.deepEqual(plan.match(/await api\.\w+\(/g), [
    'await api.modifierParcelle(', 'await api.plan(',
  ])
})

test('[CA7, CA9] « Ajouter » PRÉPARE un geste : aucune écriture depuis la PWA', () => {
  const plan = lire('../views/Plan.jsx')
  const carte = plan.slice(plan.indexOf('function CarteSol'), plan.indexOf('function DetailParcelle'))
  // [CA7] Le geste porte la parcelle en contexte, et passe par `BoutonGeste` —
  // qui dépose dans la file (US-224) au lieu d'écrire.
  assert.match(carte, /<BoutonGeste[\s\S]*?action: 'paillage'[\s\S]*?parcelleId[\s\S]*?parcelleNom/)
  // [CA9] Aucune condition de rôle dans la carte : `BoutonGeste` ne rend rien
  // du tout en lecture seule, et la LISTE, elle, reste entière.
  assert.doesNotMatch(carte, /lectureSeule/)
})

test('[CA8] « Tout voir » ouvre le Journal filtré, sans recopier la liste des gestes', () => {
  const plan = lire('../views/Plan.jsx')
  assert.match(plan, /aller\('journal', \{\s*parcelle: selection\.nom,\s*gestes: \(data\?\.gestes_sol \?\? \[\]\)\.join\(','\),/)
  // La liste ne figure nulle part en dur dans le frontend [CA2].
  assert.doesNotMatch(lire('./planParcelles.js'), /'desherbage'.*'binage'|desherbage,binage/)
})
