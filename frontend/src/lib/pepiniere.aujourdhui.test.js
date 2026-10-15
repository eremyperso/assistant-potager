// [US-215] L'onglet « Aujourd'hui » — règles de mise en forme, `npm test` (CA15).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ongletsPepiniere, ongletInitial, pastillePepiniere, superficieEnClair, echeanceCourte,
  cartesReponses, retardsNommes, lotsDuJour, filtrerLots, basculerFiltre, quantiteLigne,
  sousTitreLigne, boutonDeLigne, FILTRES_BANDEAU,
} from './pepiniere.js'

const ech = (o = {}) => ({
  date_reference: '2026-09-19',
  repiquage: { etat: null }, mise_en_terre: { etat: null }, endurcissement: { etat: null },
  dormance: { est_dormant: false }, raisons: [], ...o,
})
const lot = (o = {}) => ({
  lot_id: o.numero_lot ?? 1, numero_lot: 1, semis_id: 10, culture: 'Chou', variete: null,
  date_semis: '2026-09-01', graines_semees: 48, graines_en_germination: 48, plants_obtenus: 0,
  stock_residuel_godet: 0, nb_mises_en_godet: 0, emplacement: { nom: 'Serre' },
  echeances: ech(), action_suggeree: null, rang_urgence: 1, ...o,
})

// Le scénario du Gherkin : 128 en retard de 6 j, 131 à repiquer, 119 en endurcissement.
const L128 = lot({ numero_lot: 128, lot_id: 128, culture: 'Chou frisé', rang_urgence: 1,
  echeances: ech({ repiquage: { etat: 'en_retard', retard_jours: 6 } }), action_suggeree: { code: 'repiquer' } })
const L131 = lot({ numero_lot: 131, lot_id: 131, culture: 'Tomate cerise', rang_urgence: 2,
  echeances: ech({ repiquage: { etat: 'a_repiquer' } }), action_suggeree: { code: 'repiquer' } })
const L119 = lot({ numero_lot: 119, lot_id: 119, culture: 'Poireau', rang_urgence: 3, graines_en_germination: 0,
  stock_residuel_godet: 41, nb_mises_en_godet: 1, plants_obtenus: 44,
  echeances: ech({ endurcissement: { etat: 'en_cours', jour: 3, sur: 7 }, mise_en_terre: { etat: 'a_venir', dans_jours: 4 } }),
  action_suggeree: { code: 'mettre_en_terre' } })
const L103 = lot({ numero_lot: 103, lot_id: 103, culture: 'Basilic', rang_urgence: 4, graines_en_germination: 0,
  stock_residuel_godet: 6, nb_mises_en_godet: 1, plants_obtenus: 14,
  echeances: ech({ dormance: { est_dormant: true, jours_sans_geste: 70 } }), action_suggeree: { code: 'cloturer' } })

test('CA1 — Aujourd’hui puis Lots ; aucun onglet non livré', () => {
  assert.deepEqual(ongletsPepiniere({ nbPepinieres: 3 }).map((o) => o.cle), ['aujourdhui', 'lots'])
  const livres = { calendrier: true, emplacements: true }
  assert.deepEqual(ongletsPepiniere({ nbPepinieres: 1, livres }).map((o) => o.cle), ['aujourdhui', 'lots', 'calendrier'])
  assert.deepEqual(ongletsPepiniere({ nbPepinieres: 2, livres }).map((o) => o.cle).at(-1), 'emplacements')
})

test('CA1 — un onglet demandé mais non livré ouvre Aujourd’hui', () => {
  const onglets = ongletsPepiniere({ nbPepinieres: 2 })
  assert.equal(ongletInitial('emplacements', onglets), 'aujourdhui')
  assert.equal(ongletInitial('lots', onglets), 'lots')
  assert.equal(ongletInitial(undefined, onglets), 'aujourdhui')
})

test('CA2 — pastille d’une pépinière unique, type absent dit tel quel', () => {
  assert.equal(pastillePepiniere([{ nom: 'Serre', superficie_m2: 2.5, type_pepiniere: 'chaude' }]), 'SERRE · 2,5 m² · pépinière chaude')
  assert.equal(pastillePepiniere([{ nom: 'Serre', superficie_m2: null, type_pepiniere: null }]), 'SERRE · type non renseigné')
  assert.equal(pastillePepiniere([{ nom: 'A' }, { nom: 'B' }]), null)
  assert.equal(pastillePepiniere([]), null)
  assert.equal(superficieEnClair(3), '3 m²')
})

test('CA5 — échéances courtes', () => {
  assert.deepEqual(echeanceCourte(L128), { texte: 'Repiquage +6 j', ton: 'retard' })
  assert.equal(echeanceCourte(lot({ echeances: ech({ repiquage: { etat: 'a_venir', dans_jours: 3 } }) })).texte, 'Repiquage dans 3 j')
  assert.equal(echeanceCourte(L119).texte, 'Endurcissement J+3 sur 7')
  assert.equal(echeanceCourte(lot({ echeances: ech({ endurcissement: { etat: 'froide' } }) })).texte, 'En pépinière froide')
  assert.equal(echeanceCourte(L103).texte, 'Dormant')
  assert.equal(echeanceCourte(lot({ echeances: ech({ mise_en_terre: { etat: 'depassee', retard_jours: 2 } }) })).ton, 'retard')
})

test('CA10 — échéance incalculable : la ligne dit pourquoi', () => {
  const e = echeanceCourte(lot({ echeances: ech({ raisons: ['délai semis → godet non renseigné pour la culture « chou »'] }) }))
  assert.equal(e.texte, 'Délai non renseigné')
  assert.equal(e.ton, 'na')
  assert.match(e.raison, /non renseigné/)
})

test('CA3, CA4 — quatre cartes, « rien » à zéro, alerte quand un lot est en retard', () => {
  const resume = {
    a_repiquer: { lots: 2, plants: 108 }, a_endurcir: { lots: 1 },
    prets_pour_le_plan: { lots: 1, plants: 41, rangs_libres_par_parcelle: [{ parcelle: 'Nord', rangs_libres: 2 }] },
    a_semer: { cultures: [{ culture: 'mâche', fenetre: 'sept.' }], total: 1 },
  }
  const cartes = cartesReponses(resume, [L128, L131, L119])
  assert.deepEqual(cartes.map((c) => c.cle), ['a_repiquer', 'a_endurcir', 'prets_pour_le_plan', 'a_semer'])
  assert.equal(cartes[0].valeur, '2 lots')
  assert.equal(cartes[0].alerte, true)
  assert.match(cartes[0].detail, /chou frisé \+6 j/)
  assert.match(cartes[1].detail, /poireau J\+3\/7/)
  assert.equal(cartes[2].detail, 'Nord : 2 rangs libres')
  assert.equal(cartes[3].filtrable, false)
  assert.equal(cartes[3].cultures[0].culture, 'mâche')
  const vides = cartesReponses({}, [])
  assert.ok(vides.every((c) => c.valeur === 'rien'))
  assert.equal(vides[0].alerte, false)
})

test('CA3 — retards nommés dans l’ordre d’urgence', () => {
  assert.equal(retardsNommes([L131, L128]), 'chou frisé +6 j · tomate cerise à repiquer')
})

test('CA4 — filtres du bandeau, second appui retire', () => {
  const tous = [L128, L131, L119, L103]
  assert.deepEqual(filtrerLots(tous, { bandeau: 'a_repiquer' }).map((l) => l.numero_lot), [128, 131])
  assert.deepEqual(filtrerLots(tous, { bandeau: 'a_endurcir' }).map((l) => l.numero_lot), [119])
  assert.ok(FILTRES_BANDEAU.prets_pour_le_plan(L103))
  assert.equal(basculerFiltre(null, 'a_endurcir'), 'a_endurcir')
  assert.equal(basculerFiltre('a_endurcir', 'a_endurcir'), null)
})

test('CA5, CA6 — ordre d’urgence, dormants en fin, terminés et clôturés exclus', () => {
  const termine = lot({ numero_lot: 97, lot_id: 97, graines_en_germination: 0, plants_obtenus: 12, rang_urgence: 0 })
  const cloture = lot({ numero_lot: 90, lot_id: 90, cloture: true, rang_urgence: 0 })
  const dormantTot = { ...L103, rang_urgence: 0 }
  assert.deepEqual(lotsDuJour([L119, dormantTot, L131, termine, L128, cloture]).map((l) => l.numero_lot), [128, 131, 119, 103])
})

test('CA9 — recherche sur culture, variété, numéro ; filtre d’emplacement', () => {
  const tous = [L128, { ...L131, variete: 'Sweet 100', emplacement: { nom: 'Châssis' } }]
  assert.deepEqual(filtrerLots(tous, { q: 'sweet' }).map((l) => l.numero_lot), [131])
  assert.deepEqual(filtrerLots(tous, { q: '#128' }).map((l) => l.numero_lot), [128])
  assert.deepEqual(filtrerLots(tous, { q: 'chou' }).map((l) => l.numero_lot), [128])
  assert.deepEqual(filtrerLots(tous, { emplacement: 'chassis' }).map((l) => l.numero_lot), [131])
})

test('CA5 — sous-titre et quantité', () => {
  assert.equal(sousTitreLigne(L128), 'semé le 1er septembre · 18 j · Serre')
  assert.equal(sousTitreLigne(lot({ sans_semis_rattache: true, date_semis: null })), 'sans semis rattaché · Serre')
  assert.equal(quantiteLigne(L128), '48 semés')
  assert.equal(quantiteLigne({ ...L128, nb_leves: 40 }), '48 semés → 40 levés (83 %)')
  assert.equal(quantiteLigne(L119), '41 godets disponibles')
})

test('CA6, CA7, CA14 — bouton de l’action suggérée, principal si retard, lot nommé', () => {
  const b = boutonDeLigne(L128)
  assert.equal(b.libelle, 'Repiquer')
  assert.equal(b.ariaLabel, 'Repiquer le lot 128')
  assert.equal(b.principal, true)
  assert.equal(b.geste.action, 'mise_en_godet')
  assert.equal(b.ouvreFiche, false)
  const terre = boutonDeLigne(L119)
  assert.equal(terre.geste.action, 'plantation')
  assert.equal(terre.geste.quantite, 41)
  assert.equal(terre.principal, false)
  const clore = boutonDeLigne(L103)
  assert.equal(clore.geste.action, 'cloture_lot')
  assert.equal(clore.ariaLabel, 'Clôturer le lot 103')
  assert.equal(boutonDeLigne(lot({ action_suggeree: null })), null)
})
