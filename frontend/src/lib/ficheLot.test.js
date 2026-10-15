// [US-216] Règles d'affichage de la fiche d'un lot — exécuté par `npm test`.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  LEVEE_DISPONIBLE, dateEnClair, periodeEnClair, joursDepuisSemis, estTermine, estCloture,
  estDormant, etatDuLot, bandeauEtat, echeanceEnClair, gestesDuLot, gestePrincipal, phraseSolde,
  tracabilite, incoherenceEnClair, tauxLevee, phraseComparaison, teinteTaux, valeurInitialeCompteur,
  borner, lireNombre, gesteDeLevee, gestePrepare, badgeEtat, phraseLotSansGeste, deLaCulture,
  suggestionsVisibles, placeEnClair, gesteMiseEnTerreIci,
} from './ficheLot.js'
import { phraseADicter } from './gestes.js'

/** Le lot 128 du scénario : 48 graines semées le 1er septembre, rien repiqué. */
const lot = (champs = {}) => ({
  lot_id: 'semis-7', semis_id: 7, numero_lot: 128, culture: 'Chou', variete: 'frisé',
  date_semis: '2026-09-01', graines_semees: 48, graines_en_germination: 48,
  plants_obtenus: 0, nb_mises_en_godet: 0, stock_residuel_godet: 0,
  nb_plantes: 0, nb_vendus: 0, nb_pertes_godet: 0,
  sans_semis_rattache: false, cloture: false,
  echeances: { date_reference: '2026-09-19', raisons: [] },
  action_suggeree: null,
  ...champs,
})

const codes = (l, opts) => gestesDuLot(l, opts).map((g) => g.code)

const enRetard = {
  date_reference: '2026-09-19', raisons: [],
  repiquage: { etat: 'en_retard', retard_jours: 6, du: '2026-09-11', au: '2026-09-13' },
  mise_en_terre: {}, endurcissement: {}, dormance: { est_dormant: false },
}

// ── Dates ────────────────────────────────────────────────────────────────────
test('dateEnClair : le 1er prend « 1er », jamais d\'année', () => {
  assert.equal(dateEnClair('2026-09-01'), '1er septembre')
  assert.equal(dateEnClair('2026-09-13'), '13 septembre')
  assert.equal(dateEnClair(null), null)
})

test('periodeEnClair : le mois n\'est dit qu\'une fois, ou deux quand il change', () => {
  assert.equal(periodeEnClair('2026-09-11', '2026-09-13'), 'entre le 11 et le 13 septembre')
  assert.equal(periodeEnClair('2026-08-28', '2026-09-03'), 'entre le 28 août et le 3 septembre')
  assert.equal(periodeEnClair('2026-09-11', '2026-09-11'), 'le 11 septembre')
})

test('joursDepuisSemis : depuis la date de référence de l\'API', () => {
  assert.equal(joursDepuisSemis(lot()), 18)
  assert.equal(joursDepuisSemis(lot({ date_semis: null })), null)
})

// ── État ─────────────────────────────────────────────────────────────────────
test('lot en cours, terminé, clôturé, dormant', () => {
  assert.equal(etatDuLot(lot()), 'en_cours')
  const fini = lot({ graines_en_germination: 0, plants_obtenus: 40, nb_plantes: 40 })
  assert.equal(estTermine(fini), true)
  assert.equal(etatDuLot(fini), 'termine')
  assert.equal(bandeauEtat(fini).texte, 'Lot terminé')
  const clos = lot({ cloture: true, date_cloture: '2026-09-10', graines_en_germination: 0 })
  assert.equal(estCloture(clos), true)
  assert.equal(bandeauEtat(clos).texte, 'Lot clôturé le 10 septembre')
  const dormant = lot({ echeances: { dormance: { est_dormant: true, jours_sans_geste: 75, libelle: 'Dormant — rien depuis 75 j' } } })
  assert.equal(estDormant(dormant), true)
  assert.equal(etatDuLot(dormant), 'dormant')
})

test('un lot terminé ou clôturé n\'a aucun geste (CA13)', () => {
  assert.deepEqual(gestesDuLot(lot({ graines_en_germination: 0, plants_obtenus: 40, nb_plantes: 40 })), [])
  assert.deepEqual(gestesDuLot(lot({ cloture: true, stock_residuel_godet: 0, graines_en_germination: 0 })), [])
})

// ── Échéance ─────────────────────────────────────────────────────────────────
test('échéance en retard : datée, en clair, en alerte (CA4)', () => {
  const e = echeanceEnClair(lot({ echeances: enRetard }))
  assert.equal(e.texte, 'En retard de 6 jours — repiquage attendu entre le 11 et le 13 septembre')
  // La maquette figée sépare le titre du détail.
  assert.equal(e.titre, 'En retard de 6 jours')
  assert.equal(e.detail, 'Repiquage attendu entre le 11 et le 13 septembre.')
  assert.equal(e.ton, 'retard')
  assert.equal(e.alerte, true)
})

test('échéance incalculable : la raison, aucun conseil inventé (CA4)', () => {
  const raison = 'délai semis → godet non renseigné pour la culture « chou »'
  const e = echeanceEnClair(lot({ echeances: { date_reference: '2026-09-19', raisons: [raison], repiquage: {}, mise_en_terre: {}, endurcissement: {}, dormance: {} } }))
  // « Échéance non calculée », et la raison — aucun conseil inventé.
  assert.equal(e.titre, 'Échéance non calculée')
  assert.equal(e.detail, 'Délai semis → godet non renseigné pour la culture « chou ».')
  assert.equal(e.ton, 'na')
  assert.equal(e.alerte, false)
  assert.deepEqual(e.raisons, [raison])
})

test('échéance à venir et mise en terre atteinte', () => {
  const avenir = echeanceEnClair(lot({ echeances: { repiquage: { etat: 'a_venir', dans_jours: 4, du: '2026-09-23', au: '2026-09-25' }, mise_en_terre: {}, endurcissement: {}, dormance: {}, raisons: [] } }))
  assert.equal(avenir.titre, 'Repiquage dans 4 jours')
  assert.equal(avenir.detail, 'Attendu entre le 23 et le 25 septembre.')
  assert.equal(avenir.alerte, false)
  const terre = echeanceEnClair(lot({ stock_residuel_godet: 12, graines_en_germination: 0, plants_obtenus: 12, nb_mises_en_godet: 1, echeances: { repiquage: {}, mise_en_terre: { etat: 'atteinte', du: '2026-10-01', au: '2026-10-08' }, endurcissement: {}, dormance: {}, raisons: [] } }))
  assert.equal(terre.titre, 'Mise en terre à faire')
  assert.equal(terre.detail, 'Attendue entre le 1er et le 8 octobre.')
})

// ── Gestes ───────────────────────────────────────────────────────────────────
test('devant la barquette : le bouton principal est « Repiquer en godet » (Gherkin)', () => {
  const l = lot({ echeances: enRetard, action_suggeree: { code: 'repiquer', libelle: 'Repiquer en godet' } })
  const gestes = gestesDuLot(l)
  assert.equal(gestes[0].code, 'repiquer')
  assert.equal(gestePrincipal(gestes).libelle, 'Repiquer en godet')
  assert.equal(gestes[0].lotId, 7)
  assert.equal(gestes[0].action, 'mise_en_godet')
})

test('les gestes pertinents pour l\'état du lot (CA8)', () => {
  // des graines en germination : repiquer, perte
  assert.deepEqual(codes(lot()), ['repiquer', 'declarer_perte'])
  // des godets seulement : mettre en terre, perte
  const godets = lot({ graines_en_germination: 0, plants_obtenus: 12, nb_mises_en_godet: 1, stock_residuel_godet: 12 })
  assert.deepEqual(codes(godets), ['mettre_en_terre', 'declarer_perte'])
  // les deux
  const mixte = lot({ plants_obtenus: 12, nb_mises_en_godet: 1, stock_residuel_godet: 12, graines_en_germination: 20 })
  assert.deepEqual(codes(mixte), ['repiquer', 'mettre_en_terre', 'declarer_perte'])
})

test('l\'action suggérée passe devant les autres', () => {
  const mixte = lot({
    plants_obtenus: 12, nb_mises_en_godet: 1, stock_residuel_godet: 12, graines_en_germination: 20,
    action_suggeree: { code: 'mettre_en_terre' },
  })
  const gestes = gestesDuLot(mixte)
  assert.equal(gestes[0].code, 'mettre_en_terre')
  assert.equal(gestes[0].principal, true)
  assert.equal(gestes.filter((g) => g.principal).length, 1)
})

test('lot sans semis rattaché : ni Repiquer ni Noter la levée (Gherkin)', () => {
  const l = lot({
    sans_semis_rattache: true, semis_id: null, graines_semees: 0, graines_en_germination: 0,
    plants_obtenus: 20, nb_mises_en_godet: 1, stock_residuel_godet: 20,
  })
  const c = codes(l, { levee: true })
  assert.ok(!c.includes('repiquer') && !c.includes('noter_levee'))
  assert.deepEqual(c, ['mettre_en_terre', 'declarer_perte'])
  assert.equal(gestesDuLot(l)[0].lotId, null)
})

test('Noter la levée n\'existe qu\'une fois US-212 livrée (CA8)', () => {
  assert.equal(LEVEE_DISPONIBLE, false)
  assert.ok(!codes(lot()).includes('noter_levee'))
  assert.ok(codes(lot(), { levee: true }).includes('noter_levee'))
  assert.ok(!codes(lot({ levee_terminee: true }), { levee: true }).includes('noter_levee'))
})

test('Déplacer demande au moins deux pépinières (CA8)', () => {
  assert.ok(!codes(lot()).includes('deplacer'))
  assert.ok(!codes(lot(), { nbPepinieres: 1 }).includes('deplacer'))
  assert.ok(codes(lot(), { nbPepinieres: 2 }).includes('deplacer'))
})

test('Clôturer : un lot dormant seulement, et il dit ce qu\'il solde (CA8)', () => {
  assert.ok(!codes(lot()).includes('cloturer'))
  const dormant = lot({
    plants_obtenus: 12, nb_mises_en_godet: 1, stock_residuel_godet: 12, graines_en_germination: 20,
    echeances: { dormance: { est_dormant: true } }, action_suggeree: { code: 'cloturer' },
  })
  const g = gestesDuLot(dormant)
  assert.equal(g[0].code, 'cloturer')
  assert.equal(g[0].action, 'cloture_lot')
  assert.deepEqual(g[0].solde, { godets: 12, graines: 20 })
  assert.equal(phraseSolde(g[0].solde), 'Solde définitivement le lot : 12 godets et 20 graines non levées.')
})

test('quantités proposées : godets pour une mise en terre, levés pour un repiquage (CA9)', () => {
  const l = lot({ plants_obtenus: 12, nb_mises_en_godet: 1, stock_residuel_godet: 12, nb_leves: 40 })
  const par = Object.fromEntries(gestesDuLot(l).map((g) => [g.code, g]))
  assert.equal(par.mettre_en_terre.quantite, 12)
  assert.equal(par.repiquer.quantite, 40)
  assert.equal(par.declarer_perte.quantite, null)   // une perte se déclare, elle ne se propose pas
})

test('gestePrepare garde le contrat de BoutonGeste', () => {
  const g = gestesDuLot(lot())[0]
  assert.deepEqual(Object.keys(gestePrepare(g)).sort(), ['action', 'culture', 'lotId', 'numeroLot', 'quantite', 'unite', 'variete'])
})

// ── Traçabilité ──────────────────────────────────────────────────────────────
test('un tiret veut dire « aucun geste de ce type », jamais zéro (CA5)', () => {
  const t = Object.fromEntries(tracabilite(lot()).map((l) => [l.cle, l.valeur]))
  assert.equal(t.semees, 48)
  assert.equal(t.leves, null)
  assert.equal(t.repiques, null)
  assert.equal(t.pertes, null)
  assert.equal(t.vendus, null)
  assert.equal(t.en_terre, null)
  assert.equal(t.godets, null)
  assert.equal(t.germination, 48)
})

test('godets restants à zéro après repiquage : un vrai zéro', () => {
  const l = lot({ plants_obtenus: 12, nb_mises_en_godet: 1, nb_plantes: 12, stock_residuel_godet: 0, graines_en_germination: 0 })
  const t = Object.fromEntries(tracabilite(l).map((x) => [x.cle, x.valeur]))
  assert.equal(t.godets, 0)
  assert.equal(t.germination, 0)
  assert.equal(t.en_terre, 12)
})

test('une incohérence de saisie reste visible (CA5)', () => {
  assert.equal(incoherenceEnClair(lot()), null)
  assert.match(incoherenceEnClair(lot({ incoherence_saisie: true, plants_obtenus: 60, unite: 'graines' })), /60 plants pour 48 graines/)
})

// ── Compteur ─────────────────────────────────────────────────────────────────
test('taux et comparaison à la moyenne (Gherkin)', () => {
  assert.equal(tauxLevee(40, 48), 83)
  assert.equal(
    phraseComparaison({ taux: 83, moyenne: 75, culture: 'Chou' }),
    '83 % — au-dessus de la moyenne du chou dans ce potager, 75 %',
  )
  assert.equal(
    phraseComparaison({ taux: 60, moyenne: 75, culture: 'Chou' }),
    '60 % — en dessous de la moyenne du chou dans ce potager, 75 %',
  )
  assert.equal(phraseComparaison({ taux: 75, moyenne: 75, culture: 'Chou' }), '75 % — dans la moyenne du chou dans ce potager, 75 %')
})

test('sans moyenne rendue, la phrase se réduit au taux', () => {
  assert.equal(phraseComparaison({ taux: 83, moyenne: null, culture: 'Chou' }), '83 %')
  assert.equal(phraseComparaison({ taux: null }), null)
  assert.equal(tauxLevee(null, 48), null)
  assert.equal(tauxLevee(10, 0), null)
})

test('teinte du taux : celle du badge de la liste', () => {
  assert.equal(teinteTaux(83), 'brand')
  assert.equal(teinteTaux(60), 'amber')
  assert.equal(teinteTaux(30), 'red')
  assert.equal(teinteTaux(null), 'blue')
})

test('le compteur démarre au dernier comptage, borné aux graines semées (CA10)', () => {
  // Aucun comptage : le champ est vide, aucun zéro n'est supposé.
  assert.equal(valeurInitialeCompteur(lot()), null)
  assert.equal(valeurInitialeCompteur(lot({ nb_leves: 30 })), 30)
  assert.equal(valeurInitialeCompteur(lot({ nb_leves: 90 })), 48)
})

test('saisie du compteur : entier, jamais négatif, jamais au-delà des graines', () => {
  assert.equal(borner(-3, 48), 0)
  assert.equal(borner('40', 48), 40)
  assert.equal(borner(99, 48), 48)
  assert.equal(borner('abc', 48), 0)
  assert.equal(lireNombre('40'), 40)
  assert.equal(lireNombre(' 40 plants '), 40)
  assert.equal(lireNombre('quarante'), null)
})

test('le geste de levée porte le nombre et le lot — rien n\'est écrit (CA10)', () => {
  const g = gesteDeLevee(lot(), { leves: 40, termine: true })
  assert.equal(g.action, 'levee')
  assert.equal(g.quantite, 40)
  assert.equal(g.lotId, 7)
  assert.equal(g.terminee, true)
})

test("la phrase à dicter d'un geste de lot dit le lot, pas le nom d'action du serveur (CA9)", async () => {
  const { phraseADicter } = await import('./gestes.js')
  const g = gestesDuLot(lot({ plants_obtenus: 12, nb_mises_en_godet: 1, stock_residuel_godet: 12, graines_en_germination: 0 }))
  const terre = g.find((x) => x.code === 'mettre_en_terre')
  assert.equal(phraseADicter(gestePrepare(terre)), 'plantation 12 plants du lot 128')
  assert.equal(phraseADicter({ action: 'mise_en_godet', numeroLot: 128, quantite: 30 }), 'mise en godet 30 plants du lot 128')
  assert.equal(phraseADicter({ action: 'cloture_lot', numeroLot: 128 }), 'cloture du lot 128')
  // Sans numéro de lot, la phrase historique est inchangée.
  assert.equal(phraseADicter({ action: 'semis', culture: 'Tomate', contexteSemis: 'pepiniere' }), 'semis de tomate en pépinière')
})

test('le lot dormant : titre, détail daté, ton neutre (maquette figée)', () => {
  const l = lot({
    plants_obtenus: 14, nb_mises_en_godet: 1, stock_residuel_godet: 6, graines_en_germination: 0,
    echeances: { dormance: { est_dormant: true, jours_sans_geste: 70, dernier_geste: '2026-07-11' }, raisons: [] },
  })
  const e = echeanceEnClair(l)
  assert.equal(e.titre, 'Dormant depuis 70 jours')
  assert.equal(e.detail, 'Aucun geste depuis le 11 juillet : ni repiqué, ni planté, ni perdu.')
  assert.equal(e.ton, 'na')
})

test("badge d'état : En plaque, En godet, Dormant, Lot terminé, Lecture seule", () => {
  assert.deepEqual(badgeEtat(lot()), ['En plaque', 'blue'])
  assert.deepEqual(badgeEtat(lot({ nb_mises_en_godet: 1, plants_obtenus: 12, stock_residuel_godet: 12, graines_en_germination: 0 })), ['En godet', 'amber'])
  assert.deepEqual(badgeEtat(lot({ echeances: { dormance: { est_dormant: true } } })), ['Dormant', 'amber'])
  assert.deepEqual(badgeEtat(lot({ graines_en_germination: 0, plants_obtenus: 40, nb_plantes: 40 })), ['Lot terminé', 'brand'])
  assert.deepEqual(badgeEtat(lot(), { lecture: true }), ['Lecture seule', 'violet'])
})

test('lot terminé ou clôturé : une phrase, avec sa date', () => {
  const fini = lot({ graines_en_germination: 0, plants_obtenus: 40, nb_plantes: 40, date_dernier_geste: '2026-05-30' })
  assert.deepEqual(phraseLotSansGeste(fini), {
    titre: 'Lot terminé le 30 mai',
    suite: 'Tout est mis en terre, vendu ou perdu. Plus aucun geste à faire.',
  })
  const clos = lot({ cloture: true, date_cloture: '2026-09-10', graines_en_germination: 0 })
  assert.equal(phraseLotSansGeste(clos).titre, 'Lot clôturé le 10 septembre')
  assert.equal(phraseLotSansGeste(lot()), null)
})

test("« la moyenne du chou / de la tomate / de l'ail » : genre et élision", () => {
  assert.equal(deLaCulture('Chou'), 'du chou')
  assert.equal(deLaCulture('tomate'), 'de la tomate')
  assert.equal(deLaCulture('Ail'), "de l'ail")
  assert.equal(phraseComparaison({ taux: 60, moyenne: 82, culture: 'Tomate' }), '60 % — en dessous de la moyenne de la tomate dans ce potager, 82 %')
})

test("deux points d'écart à la moyenne : « dans la moyenne »", () => {
  assert.equal(phraseComparaison({ taux: 77, moyenne: 75, culture: 'Chou' }), '77 % — dans la moyenne du chou dans ce potager, 75 %')
  assert.equal(phraseComparaison({ taux: 78, moyenne: 75, culture: 'Chou' }), '78 % — au-dessus de la moyenne du chou dans ce potager, 75 %')
})

test('la traçabilité reprend les libellés de la maquette, la moyenne en sous-libellé', () => {
  const t = tracabilite(lot({ nb_leves: 40, moyenne_levee_culture: 75 }))
  const par = Object.fromEntries(t.map((x) => [x.cle, x]))
  assert.equal(par.semees.sub, 'prélevées au stock')
  assert.equal(par.taux_levee.valeur, 83)
  assert.equal(par.taux_levee.sub, 'moyenne du chou ici : 75 %')
  assert.deepEqual(t.map((x) => x.libelle), [
    'Graines semées', 'Levés', 'Taux de levée', 'Repiqués en godet', 'Pertes déclarées',
    'Vendus', 'Mis en terre', 'Godets restants', 'Encore en germination',
  ])
})

// ── [US-217] Où les mettre ──────────────────────────────────────────────────

const sugg = (n) => ({ suggestions: Array.from({ length: n }, (_, i) => ({ parcelle_id: i + 1, parcelle: `P${i}`, rangs_libres: 1 })) })

test('[US-217 / CA6] trois suggestions, puis toutes', () => {
  assert.equal(suggestionsVisibles(sugg(5)).length, 3)
  assert.equal(suggestionsVisibles(sugg(5), true).length, 5)
  assert.deepEqual(suggestionsVisibles(null), [])
})

test('[US-217] places quand connues, rangs libres sinon, jamais les deux', () => {
  assert.equal(placeEnClair({ rangs_libres: 2, places_libres: 48 }, 'Chou'), '48 places de chou')
  assert.equal(placeEnClair({ rangs_libres: 2, places_libres: null }), '2 rangs libres')
  assert.equal(placeEnClair({ rangs_libres: 1 }), '1 rang libre')
  assert.equal(placeEnClair({ rangs_libres: null }), 'rangs libres inconnus')
})

test('[US-217 / CA7] mettre en terre ici : parcelle, godets, rang seulement si position connue', () => {
  const l = lot({ stock_residuel_godet: 40, graines_en_germination: 0 })
  const g = gesteMiseEnTerreIci(l, { parcelle_id: 3, parcelle: 'Nord', premier_rang_libre: null })
  assert.equal(g.action, 'plantation')
  assert.equal(g.quantite, 40)
  assert.equal(g.parcelleId, 3)
  assert.equal(g.rang, null)
  assert.equal(gesteMiseEnTerreIci(l, { parcelle_id: 3, parcelle: 'Nord', premier_rang_libre: 4 }).rang, 4)
  // [CA8] Sans parcelle : le compagnon la demandera.
  assert.equal(gesteMiseEnTerreIci(l, null).parcelleId, null)
  assert.equal(phraseADicter({ ...g, parcelle: g.parcelleNom }), 'plantation 40 plants du lot 128 parcelle nord')
  // Lot sans godet : aucun geste.
  assert.equal(gesteMiseEnTerreIci(lot(), null), null)
})
