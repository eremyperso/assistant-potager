// [US-330] Le détail d'une parcelle dans le Plan — ce que la lib décide, sans React.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  ongletsDeParcelle, ongletValide, sousTitreDetail, geometrieDetail, resumeEnPlace,
  parcellesDeListe, parcelleParId, pictoParcelle, AFFICHAGES,
  ONGLET_EN_PLACE, ONGLET_LOTS, ONGLET_ENTRETIEN,
} from './parcelleDansPlan.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf-8')

const planche = (extra = {}) => ({
  id: 2, nom: 'Planche centrale', superficie_m2: 60, nb_rangs: 8, est_pepiniere: false,
  geometrie: { forme: 'planche', placee: true, longueur_m: 12, largeur_m: 5, sens_rangs: 'longueur' },
  disposition: { rangs_declares: 8, rangs_occupes: 7 }, cultures: [], ordre: 1,
  ...extra,
})

test('[D1] « Planche · 60 m² · 8 rangs » ; une pépinière compte ses lots', () => {
  assert.equal(sousTitreDetail(planche()), 'Planche · 60 m² · 8 rangs')
  assert.equal(sousTitreDetail(planche({ superficie_m2: null, nb_rangs: null })), 'Planche')
  const pep = planche({
    est_pepiniere: true, type_pepiniere: 'froide',
    disposition: { lots_en_cours: [{}, {}, {}] },
  })
  assert.equal(sousTitreDetail(pep), 'Pépinière froide · 3 lots')
})

test('[D2] « Sur le plan : 12 × 5 m, rangs dans la longueur » ; sans place, on le dit', () => {
  assert.deepEqual(geometrieDetail(planche()), { placee: true, texte: 'Sur le plan : 12 × 5 m, rangs dans la longueur' })
  assert.equal(geometrieDetail(planche({ geometrie: { placee: false } })).placee, false)
})

test('[D3 à D6] quatre onglets ; une pépinière a Lots, pas de Rotation', () => {
  assert.deepEqual(ongletsDeParcelle(planche()).map((o) => o.label), ['En place', 'Caractéristiques', 'Rotation', 'Entretien'])
  assert.deepEqual(ongletsDeParcelle(planche({ est_pepiniere: true })).map((o) => o.label), ['Lots', 'Caractéristiques', 'Entretien'])
})

test('[CA6] un onglet inexistant pour cette parcelle retombe sur le premier', () => {
  assert.equal(ongletValide(planche(), ONGLET_ENTRETIEN), ONGLET_ENTRETIEN)
  assert.equal(ongletValide(planche({ est_pepiniere: true }), 'rotation'), ONGLET_LOTS)
  assert.equal(ongletValide(planche(), 'nimporte'), ONGLET_EN_PLACE)
})

test('[D3] « 7 rangs occupés sur 8 · 1 à confirmer »', () => {
  assert.equal(resumeEnPlace(planche(), [{ aConfirmer: true }, { aConfirmer: false }]), '7 rangs occupés sur 8 · 1 à confirmer')
  assert.equal(resumeEnPlace(planche(), []), '7 rangs occupés sur 8')
})

test('[CA4] la liste inclut les parcelles non placées, dans l’ordre du chemin', () => {
  const plan = { parcelles: [
    planche({ id: 5, nom: 'Bac', ordre: 2, geometrie: { forme: 'bac', placee: false } }),
    planche({ id: 2, ordre: 1 }),
  ] }
  const liste = parcellesDeListe(plan)
  assert.deepEqual(liste.map((l) => l.id), [2, 5])
  assert.equal(liste[1].placee, false)
  assert.deepEqual(AFFICHAGES.map((a) => a.label), ['Plan', 'Liste'])
})

test('[CA5] une parcelle absente du plan est introuvable, pas une erreur', () => {
  assert.equal(parcelleParId({ parcelles: [planche()] }, 2).nom, 'Planche centrale')
  assert.equal(parcelleParId({ parcelles: [planche()] }, 99), null)
  assert.equal(parcelleParId({ parcelles: [] }, null), null)
})

test('[D1] le pictogramme suit la forme', () => {
  assert.equal(pictoParcelle(planche({ geometrie: { forme: 'bac' } })), '🪴')
  assert.equal(pictoParcelle({ est_pepiniere: true }), '🌿')
})

// ── Câblage : le Plan est l'écran des parcelles ──────────────────────────────

test('[CA1] l’écran Plan rend le détail ; l’ancien écran Parcelles est supprimé', () => {
  const plan = lire('../views/PlanDessus.jsx')
  assert.match(plan, /<DetailParcelle/)
  assert.match(plan, /useEtatEcran\('plan-vue'/)       // [CA6] état exact
  assert.match(plan, /<ListeParcelles/)                // [CA4] bascule Plan | Liste
  assert.throws(() => lire('../views/Plan.jsx'))
  assert.doesNotMatch(lire('../App.jsx'), /views\/Plan\.jsx/)
})

test('[CA3] Rotation et Entretien réutilisent les cartes d’US-231 et d’US-232', () => {
  const detail = lire('../components/DetailParcelle.jsx')
  assert.match(detail, /<CarteRotation/)
  assert.match(detail, /<CarteSol/)
  assert.match(detail, /<CarteCaracteristiques/)
  assert.match(detail, /Vue détaillée dans la tuile Rotation \(à venir\)/)
})

test('[CA2] « Noter » ouvre Gaston sur la parcelle ; « Ajuster sur le plan » est réservé à l’ordinateur', () => {
  const detail = lire('../components/DetailParcelle.jsx')
  assert.match(detail, /onNoter/)
  assert.match(detail, /ordinateur && !lectureSeule/)
  assert.match(lire('../views/PlanDessus.jsx'), /ouvrirGastonAvec\(\{ parcelleId: parcelleOuverte\.id/)
})

test('[US-331 / CA2, CA3] la grille se modifie par PATCH /parcelles ; « Compléter » passe en saisie', () => {
  const detail = lire('../components/DetailParcelle.jsx')
  assert.match(detail, /await api\.modifierParcelle\(/)
  assert.match(detail, /Compléter/)
  assert.match(detail, /!lectureSeule && \(\s*edition/)   // pas de « Modifier » en lecture seule
})
