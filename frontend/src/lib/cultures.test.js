// [US-205 / CA14] Écran Cultures — tri, filtres, recherche, libellé de fenêtre.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  libelleFenetre, sousTitreCarte, presenceCarte, correspondRecherche, visibleDansOnglet,
  famillesDisponibles, comparerConfiance, comparerAlpha, grouperParFamille, listeFiltree,
  autresDansToutes, nombreFiltresActifs, nomAccessibleCarte, friseDeLigne,
  TRI_ALPHA, TRI_FAMILLE, TRI_CONFIANCE,
} from './cultures.js'

const L = (over = {}) => ({
  culture: 'tomate', nom_culture: 'Tomate', hors_referentiel: false, famille: 'Solanacée',
  au_potager: true, a_calendrier: true, mois_zone: {}, mois_actifs: [], nb_varietes: 1,
  varietes: ['cerise'], nb_parcelles: 1, repartition_phases: {}, phase_plus_avancee: 'en_recolte',
  nb_lots_pepiniere: 0, etoiles: 1, confiance_equivalent: 'faible',
  fenetre_etat: 'plus_tard', fenetre_geste: 'semis_pepiniere', fenetre_mois: [2, 3],
  suggestion: false, ...over,
})

test('libelleFenetre [CA5] — « maintenant » en gras', () => {
  const r = libelleFenetre(L({ fenetre_etat: 'maintenant', fenetre_geste: 'semis_pleine_terre', fenetre_mois: [4, 5, 6] }))
  assert.deepEqual(r, { gras: true, texte: 'Semer en place maintenant' })
})

test('libelleFenetre [CA5] — « bientôt » en minuscule avec la plage de mois', () => {
  const r = libelleFenetre(L({ fenetre_etat: 'bientot', fenetre_geste: 'plantation', fenetre_mois: [10, 11] }))
  assert.deepEqual(r, { gras: false, texte: 'bientôt : planter octobre → novembre' })
})

test('libelleFenetre [CA5] — « prochaine fenêtre » sinon', () => {
  const r = libelleFenetre(L({ fenetre_etat: 'plus_tard', fenetre_geste: 'semis_pepiniere', fenetre_mois: [1, 2] }))
  assert.deepEqual(r, { gras: false, texte: 'prochaine fenêtre : semer en pépinière janvier → février' })
})

test('libelleFenetre [CA6] — null sans calendrier pour la zone', () => {
  assert.equal(libelleFenetre(L({ a_calendrier: false, fenetre_etat: 'aucune', fenetre_geste: null })), null)
})

test('sousTitreCarte [CA5] — variétés et famille au potager', () => {
  assert.equal(sousTitreCarte(L({ nb_varietes: 2 })), '2 variétés · Solanacée')
})

test('sousTitreCarte [CA5] — famille seule, culture absente du potager', () => {
  assert.equal(sousTitreCarte(L({ au_potager: false })), 'Solanacée')
})

test('sousTitreCarte [CA8] — hors référentiel', () => {
  assert.equal(sousTitreCarte(L({ hors_referentiel: true })), 'hors référentiel')
})

test('presenceCarte [CA5] — phase la plus avancée et parcelles', () => {
  assert.deepEqual(presenceCarte(L({ phase_plus_avancee: 'en_recolte', nb_parcelles: 3, nb_lots_pepiniere: 1 })),
    { phase: 'en_recolte', texte: '3 parcelles · 1 lot' })
})

test('presenceCarte [CA3, CA21] — en pépinière seule, aucune ligne en terre', () => {
  assert.deepEqual(presenceCarte(L({ phase_plus_avancee: null, nb_parcelles: 0, nb_lots_pepiniere: 2 })),
    { phase: 'en_pepiniere', texte: '2 lots' })
})

test('presenceCarte [CA5, CA7] — null sans présence : la carte affiche « pas au potager »', () => {
  assert.equal(presenceCarte(L({ phase_plus_avancee: null, nb_lots_pepiniere: 0 })), null)
})

test('correspondRecherche [CA4] — nom de culture, insensible aux accents et à la casse', () => {
  assert.equal(correspondRecherche(L({ nom_culture: 'Épinard' }), 'epinard', 'toutes'), true)
})

test('correspondRecherche [CA4] — variétés cherchées seulement dans « Au potager »', () => {
  const ligne = L({ nom_culture: 'Tomate', varietes: ['noire de Crimée'] })
  assert.equal(correspondRecherche(ligne, 'crimee', 'potager'), true)
  assert.equal(correspondRecherche(ligne, 'crimee', 'toutes'), false)
})

test('visibleDansOnglet [CA7] — une suggestion apparaît dans « Au potager » bien que non présente', () => {
  assert.equal(visibleDansOnglet(L({ au_potager: false, suggestion: true }), 'potager'), true)
  assert.equal(visibleDansOnglet(L({ au_potager: false, suggestion: false }), 'potager'), false)
  assert.equal(visibleDansOnglet(L({ au_potager: false }), 'toutes'), true)
})

test('famillesDisponibles [CA3] — dédoublonnées et triées en français', () => {
  assert.deepEqual(famillesDisponibles([L({ famille: 'Cucurbitacée' }), L({ famille: 'Amaranthacée' }), L({ famille: null })]),
    ['Amaranthacée', 'Cucurbitacée'])
})

test('comparerConfiance [CA2] — étoiles d’abord, une culture sans étoile jamais devant une étoilée', () => {
  const a = L({ nom_culture: 'A', etoiles: null, fenetre_etat: 'maintenant' })
  const b = L({ nom_culture: 'B', etoiles: 1, fenetre_etat: 'plus_tard' })
  assert.equal(comparerConfiance(a, b) > 0, true)  // a (sans étoile) passe après b
})

test('comparerConfiance [CA2] — à étoiles égales, la fenêtre départage', () => {
  const a = L({ nom_culture: 'A', etoiles: 2, fenetre_etat: 'bientot' })
  const b = L({ nom_culture: 'B', etoiles: 2, fenetre_etat: 'maintenant' })
  assert.equal(comparerConfiance(a, b) > 0, true)  // b (maintenant) avant a (bientôt)
})

test('comparerConfiance [CA12] — confiance indisponible : aucune étoile ne départage plus', () => {
  const a = L({ nom_culture: 'A', etoiles: 3 })
  const b = L({ nom_culture: 'B', etoiles: 1 })
  assert.equal(comparerConfiance(a, b, { meteoDisponible: false }), a.nom_culture.localeCompare(b.nom_culture, 'fr'))
})

test('grouperParFamille [CA20] — groupes triés, hors référentiel en dernier', () => {
  const g = grouperParFamille([
    L({ nom_culture: 'Tomate', famille: 'Solanacée' }),
    L({ nom_culture: 'Verveine', famille: null, hors_referentiel: true }),
    L({ nom_culture: 'Ail', famille: 'Alliacée' }),
  ])
  assert.deepEqual(g.map((x) => x.famille), ['Alliacée', 'Solanacée', 'Hors référentiel'])
})

test('listeFiltree [CA2, CA3] — filtre famille et mois, tri confiance par défaut', () => {
  const lignes = [
    L({ nom_culture: 'Tomate', famille: 'Solanacée', mois_actifs: [4, 5], etoiles: 1 }),
    L({ nom_culture: 'Carotte', famille: 'Apiacée', mois_actifs: [3, 4], etoiles: 2 }),
  ]
  const r = listeFiltree(lignes, { onglet: 'toutes', mois: 4, tri: TRI_CONFIANCE })
  assert.deepEqual(r.map((l) => l.nom_culture), ['Carotte', 'Tomate'])
  const r2 = listeFiltree(lignes, { onglet: 'toutes', famille: 'Apiacée', tri: TRI_ALPHA })
  assert.deepEqual(r2.map((l) => l.nom_culture), ['Carotte'])
})

test('autresDansToutes [CA4] — cultures qui correspondent hors du sous-ensemble courant', () => {
  const toutes = [L({ culture: 'poireau', nom_culture: 'Poireau', au_potager: false })]
  assert.equal(autresDansToutes(toutes, [], 'poireau'), 1)
  assert.equal(autresDansToutes(toutes, [], ''), 0)
})

test('nombreFiltresActifs [CA19] — famille, mois, tri autre que le défaut', () => {
  assert.equal(nombreFiltresActifs({ famille: null, mois: null, tri: TRI_CONFIANCE }), 0)
  assert.equal(nombreFiltresActifs({ famille: 'Solanacée', mois: 4, tri: TRI_ALPHA }), 3)
})

test('nomAccessibleCarte [CA13] — culture, phase, confiance et fenêtre', () => {
  const r = nomAccessibleCarte(L({
    nom_culture: 'Tomate', phase_plus_avancee: 'en_recolte', nb_parcelles: 2,
    etoiles: 2, confiance_equivalent: 'moyenne',
    fenetre_etat: 'plus_tard', fenetre_geste: 'semis_pepiniere', fenetre_mois: [1, 2],
  }))
  assert.equal(r, 'Tomate, en récolte, confiance moyenne, 2 étoiles sur 3, prochaine fenêtre : semer en pépinière janvier → février')
})

test('nomAccessibleCarte [CA7] — suggestion, pas au potager', () => {
  const r = nomAccessibleCarte(L({
    nom_culture: 'Épinard', au_potager: false, suggestion: true, phase_plus_avancee: null, nb_lots_pepiniere: 0,
    etoiles: 3, confiance_equivalent: 'élevée', fenetre_etat: 'maintenant', fenetre_geste: 'semis_pleine_terre', fenetre_mois: [8, 9],
  }))
  assert.equal(r, 'Épinard, suggestion — pas au potager, confiance élevée, 3 étoiles sur 3, Semer en place maintenant')
})

test('nomAccessibleCarte [CA6] — pas de calendrier', () => {
  const r = nomAccessibleCarte(L({
    nom_culture: 'Ail', a_calendrier: false, fenetre_etat: 'aucune', fenetre_geste: null,
    phase_plus_avancee: 'en_place', nb_parcelles: 2, etoiles: null,
  }))
  assert.equal(r, 'Ail, en place, pas de calendrier')
})

test('friseDeLigne [CA5] — mois 1..12 du serveur convertis en index 0-based', () => {
  const frise = friseDeLigne(L({ mois_zone: { semis_pleine_terre: [4, 5], recolte: [7, 8] } }))
  assert.deepEqual(frise.pleineTerre, [3, 4])
  assert.deepEqual(frise.rec, [6, 7])
  assert.deepEqual(frise.pepiniere, [])
})
