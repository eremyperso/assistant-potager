// [US-242 / CA11] L'onglet « Lots » en journal de saison : statut, gestes datés, fenêtre,
// positions, bilan. Les lots ont la forme exacte de `GET /pepiniere/lots`.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  FILTRES, filtreInitial, statutLot, lotsVisibles, comptesFiltres, groupesParMois, partsDuLot,
  barreDuLot, tauxDuLot, etatEnUneLigne, gestesDates, gestesNonDates, journalDuLot, fenetre,
  position, moisDeLaFenetre, frise, bilanDesLots, echeanceFiche, identiteFiche, jourDeReference,
  quantiteNonDite,
} from './lotsJournal.js'

const REF = '2026-10-19'
const ech = (o = {}) => ({
  date_reference: REF, raisons: [], repiquage: {}, mise_en_terre: {}, endurcissement: {},
  dormance: { est_dormant: false }, ...o,
})
const lot = (numero, o = {}) => ({
  lot_id: `semis-${numero}`, semis_id: numero, numero_lot: numero, culture: 'Tomate', variete: null,
  date_semis: '2026-09-01', graines_semees: 10, plants_obtenus: 0, nb_mises_en_godet: 0,
  date_derniere_mise_en_godet: null, nb_plantes: 0, nb_vendus: 0, nb_pertes_godet: 0,
  stock_residuel_godet: 0, graines_non_soldees: 10, graines_en_germination: 10, date_dernier_geste: null,
  date_deplacement: null, cloture: false, date_cloture: null, nb_leves: null, date_derniere_levee: null,
  levee_terminee: false, sans_semis_rattache: false, emplacement: { nom: 'SERRE', type_pepiniere: 'chaude' },
  echeances: ech(), ...o,
})

// Lot n° 4 de la maquette : tomate jaune, semée le 21 sept., 3 mises en godet, déplacée, levée notée.
const lot4 = lot(4, {
  variete: 'jaune', date_semis: '2026-09-21', graines_semees: 20, plants_obtenus: 15, nb_mises_en_godet: 3,
  date_derniere_mise_en_godet: '2026-10-09', stock_residuel_godet: 15, graines_non_soldees: 5,
  graines_en_germination: 0, date_deplacement: '2026-10-12', nb_leves: 18, date_derniere_levee: '2026-10-18',
  levee_terminee: true, date_dernier_geste: '2026-10-18',
  emplacement: { nom: 'serre extérieure', type_pepiniere: null },
  echeances: ech({ mise_en_terre: { etat: 'a_venir', du: '2026-11-02', au: '2026-11-16', dans_jours: 14 } }),
})
// Lot n° 7 : chou frisé, 90 godets prêts, mise en terre à faire.
const lot7 = lot(7, {
  culture: 'Chou', variete: 'frisé', graines_semees: 100, plants_obtenus: 100, nb_mises_en_godet: 1,
  date_derniere_mise_en_godet: '2026-09-20', stock_residuel_godet: 90, nb_pertes_godet: 10,
  graines_non_soldees: 0, graines_en_germination: 0, date_dernier_geste: '2026-10-15',
  echeances: ech({ mise_en_terre: { etat: 'atteinte', du: '2026-10-13', au: '2026-10-27' } }),
})
// Lot n° 1 : tout planté.
const lot1 = lot(1, {
  date_semis: '2026-03-15', graines_semees: 10, plants_obtenus: 10, nb_mises_en_godet: 2,
  date_derniere_mise_en_godet: '2026-10-09', nb_plantes: 10, graines_non_soldees: 0, graines_en_germination: 0,
  date_dernier_geste: '2026-10-09',
  sorties_datees: [{ nature: 'plantation', date: '2026-06-15', quantite: 10, parcelle: 'planche_centrale', id: 31 }],
})
// Le même lot lu sans le détail daté des sorties (API d'avant US-242) : la plantation reste comptée, sans date.
const lot1Compte = { ...lot1, sorties_datees: [] }
// Lot n° 6 : clôturé sans levée.
const lot6 = lot(6, {
  variete: 'jaune', date_semis: '2026-03-25', graines_semees: 5, cloture: true, date_cloture: '2026-10-15',
  graines_non_soldees: 0, graines_en_germination: 0, date_dernier_geste: '2026-10-15',
})
// Lot n° 3 : carotte, délai non renseigné, 1 levé sur 50.
const lot3 = lot(3, {
  culture: 'Carotte', date_semis: '2026-09-16', graines_semees: 50, nb_leves: 1, levee_terminee: true,
  date_derniere_levee: '2026-10-18', graines_non_soldees: 50, graines_en_germination: 0, date_dernier_geste: '2026-10-18',
  echeances: ech({ raisons: ['délai semis → godet non renseigné pour la culture « carotte »'] }),
})
// Lot n° 9 : laitue, quantité non dite.
const lot9 = lot(9, {
  culture: 'Laitue', variete: "d'hiver", date_semis: '2026-10-13', graines_semees: 0,
  graines_non_soldees: 0, graines_en_germination: 0, date_dernier_geste: '2026-10-13',
})
const TOUS = [lot9, lot4, lot1, lot7, lot3, lot6]

test('CA1 — filtres et statuts', () => {
  assert.deepEqual(FILTRES.map((f) => f.cle), ['en_cours', 'a_regler', 'termine', 'tous'])
  assert.equal(filtreInitial('nimporte'), 'tous')
  assert.equal(filtreInitial('termine'), 'termine')
  assert.equal(statutLot(lot1), 'termine')
  assert.equal(statutLot(lot6), 'termine')
  assert.equal(statutLot(lot3), 'a_regler')
  assert.equal(statutLot(lot9), 'a_regler')
  assert.equal(statutLot(lot4), 'en_cours')
  assert.equal(statutLot(lot7), 'en_cours')
  assert.deepEqual(comptesFiltres(TOUS), { en_cours: 2, a_regler: 2, termine: 2, tous: 6 })
  assert.ok(quantiteNonDite(lot9))
  assert.ok(!quantiteNonDite({ ...lot9, sans_semis_rattache: true }))
})

test('CA1, CA8 — visibles : filtre, recherche, tri par date de semis', () => {
  assert.deepEqual(lotsVisibles(TOUS).map((l) => l.numero_lot), [1, 6, 7, 3, 4, 9])
  assert.deepEqual(lotsVisibles(TOUS, { filtre: 'a_regler' }).map((l) => l.numero_lot), [3, 9])
  assert.deepEqual(lotsVisibles(TOUS, { q: 'jaune' }).map((l) => l.numero_lot), [6, 4])
  assert.deepEqual(lotsVisibles(TOUS, { q: '#7' }).map((l) => l.numero_lot), [7])
  assert.deepEqual(lotsVisibles(TOUS, { q: 'carot' }).map((l) => l.numero_lot), [3])
})

test('CA3 — groupes par mois de semis', () => {
  const g = groupesParMois(lotsVisibles(TOUS))
  assert.deepEqual(g.map((x) => [x.mois, x.lots.length]), [['Mars', 2], ['Septembre', 3], ['Octobre', 1]])
  assert.equal(groupesParMois([lot(1, { date_semis: null })])[0].mois, 'Sans date')
})

test('Parts et barre : levés à repiquer, non levées soldées', () => {
  assert.deepEqual(partsDuLot(lot4), { parts: { pl: 0, go: 15, le: 3, ge: 0, vd: 0, pe: 0, nl: 2 }, base: 20 })
  assert.deepEqual(partsDuLot(lot7).parts, { pl: 0, go: 90, le: 0, ge: 0, vd: 0, pe: 10, nl: 0 })
  assert.deepEqual(partsDuLot(lot6).parts, { pl: 0, go: 0, le: 0, ge: 0, vd: 0, pe: 0, nl: 5 })
  assert.deepEqual(partsDuLot(lot3).parts.le, 1)
  assert.equal(partsDuLot(lot3).parts.nl, 49)
  assert.deepEqual(barreDuLot(lot4).map((s) => [s.cle, s.largeur]), [['go', 75], ['le', 15], ['nl', 10]])
  assert.deepEqual(barreDuLot(lot9), [])
})

test('CA6 — taux : levée si notée, germination sinon, rien sans base', () => {
  assert.deepEqual(tauxDuLot(lot4), { valeur: 90, libelle: 'levée, terminée', sur: 20 })
  assert.deepEqual(tauxDuLot(lot7), { valeur: 100, libelle: 'germination', sur: 100 })
  assert.deepEqual(tauxDuLot(lot6), { valeur: 0, libelle: 'germination', sur: 5 })
  assert.equal(tauxDuLot(lot9), null)
  assert.equal(tauxDuLot(lot(2)), null)   // semé, rien obtenu, pas clôturé : pas de taux
})

test('CA5 — où il en est, en une ligne', () => {
  assert.equal(etatEnUneLigne(lot4), '15 godets · 3 levés à repiquer · sortie dans 14 j')
  assert.equal(etatEnUneLigne(lot7), '90 godets · mise en terre à faire')
  assert.equal(etatEnUneLigne(lot1), 'tout planté · 10 sur 10')
  assert.equal(etatEnUneLigne(lot6), 'clôturé le 15 oct. · aucune levée')
  assert.equal(etatEnUneLigne(lot3), 'délai non renseigné · 1 levé à repiquer')
  assert.equal(etatEnUneLigne(lot9), 'quantité semée non dite')
})

test('CA3, CA9 — gestes datés, sans date inventée', () => {
  assert.deepEqual(gestesDates(lot4).map((g) => [g.code, g.date]), [
    ['S', '2026-09-21'], ['G', '2026-10-09'], ['D', '2026-10-12'], ['L', '2026-10-18'],
  ])
  assert.equal(gestesDates(lot4)[1].detail, '3 mises en godet en tout · 15 plants')
  assert.equal(gestesDates(lot4)[2].detail, 'vers serre extérieure')
  assert.equal(gestesDates(lot4)[3].titre, 'Levée notée, terminée')
  // Le dernier geste sans autre geste ce jour-là : « type non transmis ».
  assert.deepEqual(gestesDates(lot7).map((g) => g.code), ['S', 'G', 'X'])
  assert.deepEqual(gestesDates(lot6).map((g) => g.code), ['S', 'C'])
  assert.equal(gestesDates(lot9)[0].detail, 'quantité non dite')
  // La plantation du 15 juin garde sa date et sa parcelle, et n'est plus « sans date ».
  assert.deepEqual(gestesDates(lot1).map((g) => [g.code, g.date]), [['S', '2026-03-15'], ['T', '2026-06-15'], ['G', '2026-10-09']])
  assert.deepEqual(gestesDates(lot1)[1], { code: 'T', date: '2026-06-15', titre: 'Mis en terre', detail: '10 plants · planche_centrale' })
  assert.deepEqual(gestesNonDates(lot1), [])
  assert.deepEqual(gestesNonDates(lot1Compte), [{ code: 'T', titre: 'Mis en terre', detail: '10 plants' }])
  assert.deepEqual(gestesNonDates(lot4), [])
  // Un reste non couvert reste compté sans date : 4 plantés dont 3 datés.
  assert.deepEqual(
    gestesNonDates({ nb_plantes: 4, sorties_datees: [{ nature: 'plantation', date: '2026-06-15', quantite: 3 }] }),
    [{ code: 'T', titre: 'Mis en terre', detail: '1 plant' }],
  )
})

test('CA6 — journal du lot : J+n, non datés, aujourd\'hui', () => {
  const j = journalDuLot(lot4, REF)
  assert.deepEqual(j.map((x) => x.jour), ['J0', 'J18', 'J21', 'J27', 'J28'])
  assert.equal(j[4].titre, "Aujourd'hui")
  assert.equal(j[4].detail, '1 j sans geste')
  const j1 = journalDuLot(lot1, REF)
  assert.deepEqual(j1.map((x) => x.jour), ['J0', 'J92', 'J208'])   // terminé : pas de ligne « aujourd'hui »
  assert.equal(j1[1].detail, '10 plants · planche_centrale')
  const jCompte = journalDuLot(lot1Compte, REF)
  assert.equal(jCompte[jCompte.length - 1].nonDate, true)   // sans détail daté : compté, « date non transmise »
  assert.equal(jCompte[jCompte.length - 1].jour, '?')
  assert.equal(journalDuLot(lot9, '2026-10-13').at(-1).detail, 'geste du jour')
})

test('CA4 — fenêtres : saison et récent, libellé calculé', () => {
  assert.deepEqual(fenetre('saison', REF), { debut: '2026-03-01', fin: '2026-11-30', libelle: 'Saison' })
  assert.deepEqual(fenetre('recent', REF), { debut: '2026-08-01', fin: '2026-11-30', libelle: 'Août → nov.' })
  // La saison s'étend pour contenir le jour de référence.
  assert.deepEqual(fenetre('saison', '2026-12-10'), { debut: '2026-03-01', fin: '2026-12-31', libelle: 'Saison' })
  assert.equal(fenetre('saison', '2026-01-05').debut, '2026-01-01')
  assert.deepEqual(fenetre('recent', '2027-01-15'), { debut: '2026-11-01', fin: '2027-02-28', libelle: 'Novembre → févr.' })
  const f = fenetre('recent', REF)
  assert.equal(position('2026-08-01', f), 0)
  assert.equal(position('2026-01-01', f), 0)
  assert.equal(position('2027-01-01', f), 100)
  assert.deepEqual(moisDeLaFenetre(f).map((m) => m.mois), ['août', 'sept.', 'oct.', 'nov.'])
})

test('CA3 — frise : trait, attente, fenêtre de mise en terre, pastilles décalées', () => {
  const f = fenetre('recent', REF)
  const fr = frise(lot4, f, REF, 3)
  assert.ok(fr.trait.largeur > 0)
  assert.ok(fr.attente)
  assert.ok(fr.fenetreTerre && fr.fenetreTerre.du === '2026-11-02')
  assert.deepEqual(fr.pastilles.map((p) => p.code), ['S', 'G', 'D', 'L'])
  // G (9 oct.) et D (12 oct.) sont à moins de 3 % : D se décale.
  assert.notEqual(fr.pastilles[2].niveau, 0)
  assert.equal(fr.pastilles[0].info, '21 sept. · semé')
  // Terminé : ni attente, ni fenêtre de mise en terre.
  const f1 = frise(lot1, f, REF)
  assert.equal(f1.attente, null)
  assert.equal(f1.fenetreTerre, null)
  // Semé avant la fenêtre : accroché au bord gauche, pâle.
  assert.deepEqual([f1.pastilles[0].gauche, f1.pastilles[0].pale], [0, true])
})

test('CA2 — bilan des lots visibles', () => {
  const b = bilanDesLots(TOUS, REF)
  assert.equal(b.semees, 185)
  assert.equal(b.go, 105)
  assert.equal(b.pl, 10)
  assert.equal(b.phrase, '105 plants attendent en godet')
  assert.equal(b.urgence, '90 godets de chou frisé à mettre en terre avant le 27 oct.')
  assert.ok(b.barre.some((s) => s.cle === 'go'))
  assert.equal(bilanDesLots([]).phrase, 'Aucun lot.')
  assert.equal(bilanDesLots([]).pourcent, null)
  assert.equal(bilanDesLots([lot1]).phrase, '10 plants mis en terre sur 1 lot.')
  assert.equal(bilanDesLots([lot9]).phrase, "Aucun plant obtenu pour l'instant.")
})

test('Bilan — levés à repiquer et graines en germination ne se confondent pas', () => {
  // Courgette : 20 semées, levée terminée à 16 ; tomate : 20 semées, aucune levée notée.
  const courgette = lot(21, { graines_semees: 20, graines_non_soldees: 20, nb_leves: 16, levee_terminee: true })
  const tomate = lot(22, { graines_semees: 20, graines_non_soldees: 20 })
  assert.deepEqual(partsDuLot(tomate).parts, { pl: 0, go: 0, le: 0, ge: 20, vd: 0, pe: 0, nl: 0 })
  const b = bilanDesLots([courgette, tomate])
  assert.deepEqual(b.barre.map((s) => [s.cle, s.valeur, s.libelle]),
    [['le', 16, 'levés à repiquer'], ['ge', 20, 'en germination'], ['nl', 4, 'non levées']])
  assert.equal(b.phrase, "16 plants levés attendent d'être repiqués.")
})

test('CA6 — échéance de la fiche : ton et texte', () => {
  assert.equal(echeanceFiche(lot7).ton, 'pret')
  assert.equal(echeanceFiche(lot7).titre, 'Mise en terre à faire')
  assert.equal(echeanceFiche(lot4).ton, 'bien')
  assert.deepEqual(echeanceFiche(lot6), { ton: 'fin', titre: 'Clôturé le 15 octobre', detail: "aucune graine n'a levé" })
  assert.equal(echeanceFiche(lot1).titre, 'Tout planté')
  assert.equal(echeanceFiche(lot3).ton, 'na')
  assert.equal(echeanceFiche(lot9).titre, 'Durée ?')
})

test('Identité et jour de référence', () => {
  assert.deepEqual(identiteFiche(lot4, REF), {
    semis: 'semé le 21 septembre · 28 j', lieu: 'serre extérieure · type non renseigné', deplace: 'déplacé le 12 octobre',
  })
  assert.equal(identiteFiche(lot(1, { date_semis: null }), REF).semis, 'godets formés sans semis rattaché')
  assert.equal(jourDeReference('2026-09-01', TOUS), '2026-09-01')
  assert.equal(jourDeReference(null, TOUS), REF)
  assert.equal(jourDeReference(null, [], new Date(2026, 4, 3)), '2026-05-03')
})

test('US-242 — ventes et pertes datées, parcelle absente nommée', () => {
  const l = lot(11, {
    graines_semees: 10, plants_obtenus: 10, nb_mises_en_godet: 1, date_derniere_mise_en_godet: '2026-04-01',
    nb_plantes: 4, nb_vendus: 2, nb_pertes_godet: 1, stock_residuel_godet: 3,
    sorties_datees: [
      { nature: 'plantation', date: '2026-06-15', quantite: 4, parcelle: null },
      { nature: 'vente', date: '2026-06-20', quantite: 2, parcelle: null },
      { nature: 'perte', date: '2026-06-22', quantite: 1, parcelle: null },
    ],
  })
  assert.deepEqual(gestesDates(l).map((g) => [g.code, g.date, g.detail]), [
    ['S', '2026-09-01', '10 graines'],
    ['G', '2026-04-01', '10 plants'],
    ['T', '2026-06-15', '4 plants · parcelle non renseignée'],
    ['V', '2026-06-20', '2 plants'],
    ['P', '2026-06-22', '1 plant'],
  ].sort((a, b) => (a[1] < b[1] ? -1 : 1)))
  assert.deepEqual(gestesNonDates(l), [])
  // Un geste sans date n'est jamais placé : il reste compté.
  assert.equal(gestesDates({ ...l, sorties_datees: [{ nature: 'vente', date: null, quantite: 2 }] }).some((g) => g.code === 'V'), false)
})

test('US-242 — la frise place la mise en terre et prolonge le trait jusqu’à elle', () => {
  const f = fenetre('saison', REF)
  const fr = frise(lot1, f, REF)
  assert.deepEqual(fr.pastilles.map((p) => p.code), ['S', 'T', 'G'])
  assert.equal(fr.pastilles[1].info, '15 juin · mis en terre')
  assert.equal(fr.attente, null)
})
