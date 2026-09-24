// [US-222 / CA15] La composition du niveau 2, vérifiée sur les cas que la
// Vue plan connaît déjà : culture sur un rang, sur deux rangs, en surface, en
// poquets, parcelle sans nombre de rangs, dépassement, pépinière, parcelle libre.
//
// [CA2] Le test central est celui de la **réconciliation des deux niveaux** :
// pour un même jeu de données, un rang doit porter les mêmes places et la même
// longueur relative dans la Vue plan et dans l'onglet Parcelles. C'est la
// garantie qu'il n'existe pas deux dessins de la même chose.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  occupationCourte, occupationDetail, sousTitreListe, ligneListeParcelle,
  enteteDetail, detailDeParcelle, abriTexte, bandeauOccupation, ligneEtat,
  caracteristiquesDeParcelle, parcelleACompleter, aideCompagnon,
  TIRET_OCCUPATION, NON_RENSEIGNE, MENTION_LARGEUR_DEDUITE,
} from './planParcelles.js'

const ligne = (culture, quantite, unite, mode, numeros, extra = {}) => ({
  culture, variete: '', nb_plants: quantite, unite,
  mode_implantation: mode, numeros_rangs: numeros,
  quantite_par_rang: Math.round((quantite / Math.max(numeros.length, 1)) * 10) / 10,
  phase: 'en_place', famille: 'Solanacées', ...extra,
})

const rang = (numero, extra = {}) => ({ numero, libre: false, ...extra })

/** Une planche de 5 rangs, 4 occupés : le cas courant des deux niveaux. */
function plancheCentrale() {
  return {
    id: 1, nom: 'planche-centrale', superficie_m2: 12, longueur_m: 6,
    largeur_m: 2, exposition: 'sud', abri: 'aucun', paillage: true,
    est_pepiniere: false, has_observations: true, nb_observations: 3,
    cultures: [
      ligne('tomate cerise', 5, 'plants', 'rang', [2]),
      ligne('carotte', 60, 'graines', 'rang', [3, 4]),
    ],
    disposition: {
      rangs_declares: 5, rangs_occupes: 4, depassement: 0,
      rangs: [
        rang(1, { libre: true, longueur_m: 6, capacite_exemple: '12 tomates' }),
        rang(2, { quantite_par_rang: 5, places: 12, places_prises: 5, places_restantes: 7, espacement_rang_cm: 50 }),
        rang(3, { quantite_par_rang: 30, places: 120, places_prises: 30, places_restantes: 90 }),
        rang(4, { quantite_par_rang: 30, places: 120, places_prises: 30, places_restantes: 90 }),
        rang(5, { libre: true, longueur_m: 6, capacite_exemple: '12 tomates' }),
      ],
    },
  }
}

// [CA2, amendement du 24/09/2026] Les deux tests de RÉCONCILIATION des niveaux
// sont retirés avec les tuiles : il n'existe plus deux dessins d'un rang à
// garantir identiques. La garantie est devenue plus forte — il n'en existe
// qu'un, celui de la Vue plan (`planVue.js`, US-200 / US-228), et c'est lui
// seul que `planVue.test.js` couvre.

test('[D1, Gherkin] l’occupation se dit en rangs, dans la liste comme dans le détail', () => {
  const p = plancheCentrale()
  assert.equal(occupationCourte(p), '4/5')
  assert.equal(occupationDetail(p), '4 rangs occupés sur 5')
  assert.equal(sousTitreListe(p), '2 cultures · 12 m²')
})

// ── [US-222, amendement du 24/09/2026] Le bandeau remplace les tuiles ────────
//
// La fiche parcelle ne porte plus le détail des cultures : ni tuile, ni frise,
// ni confiance, ni rang libre actionnable. Ce qui reste est un bandeau —
// l'occupation en rangs, les cases, les NOMS des cultures — et un chemin vers
// le Plan. Les tests de tuiles d'US-222 sont retirés avec les tuiles.

test('[D5b] le bandeau dit l’occupation, les cases et les seuls NOMS des cultures', () => {
  const b = bandeauOccupation(plancheCentrale())
  assert.equal(b.occupation, '4 rangs occupés sur 5')
  assert.deepEqual(b.cases.map((c) => c.numero), [1, 2, 3, 4, 5])
  assert.deepEqual(b.cases.filter((c) => c.libre).map((c) => c.numero), [1, 5])
  // [CA6 amendé] Le nom, et rien de plus : ni quantité, ni variété, ni unité.
  assert.deepEqual(b.cultures, ['Tomate cerise', 'Carotte'])
  assert.equal(b.libre, false)
})

test('[CA6 amendé] deux lignes de la même culture ne font qu’un nom dans le bandeau', () => {
  const p = plancheCentrale()
  p.cultures = [
    ligne('carotte', 30, 'graines', 'rang', [1]),
    ligne('carotte', 30, 'graines', 'rang', [2]),
  ]
  assert.deepEqual(bandeauOccupation(p).cultures, ['Carotte'])
})

test('[US-222 amendé] le détail ne porte plus ni tuile ni rang libre', () => {
  const detail = detailDeParcelle(plancheCentrale())
  assert.equal(detail.tuiles, undefined)
  assert.equal(detail.rangsLibres, undefined)
  assert.equal(detail.premierRangLibre, undefined)
  assert.ok(detail.bandeau)
})

test('[D4, CA13] une parcelle sans nombre de rangs dessine ses cultures sans rang libre', () => {
  const p = plancheCentrale()
  p.disposition = { rangs_declares: null, rangs_occupes: 2, depassement: 0, rangs: [] }
  const detail = detailDeParcelle(p)
  assert.equal(occupationCourte(p), TIRET_OCCUPATION)
  // Sans nombre de rangs déclaré, le bandeau ne montre QUE les rangs occupés :
  // il n'invente aucune case libre (D4).
  assert.equal(detail.bandeau.cases.filter((c) => c.libre).length, 0)
  // [D4] La mention vit désormais dans le BANDEAU, là où l'occupation se dit.
  assert.equal(detail.bandeau.mention, 'nombre de rangs non renseigné')
  assert.equal(detail.entete.mention, 'nombre de rangs non renseigné')
  assert.ok(detail.entete.phrase.includes('planche-centrale'))
  assert.equal(ligneListeParcelle(p).mention, 'nombre de rangs non renseigné')
})

test('[D11] le dépassement se dit mot pour mot comme au niveau 1', () => {
  const p = plancheCentrale()
  p.disposition.rangs_declares = 5
  p.disposition.rangs_occupes = 6
  p.disposition.depassement = 1
  assert.equal(occupationDetail(p), '6 rangs occupés pour 5 déclarés')
  assert.equal(ligneListeParcelle(p).depassement, 1)
})

test('[D3] une pépinière se compte en lots, jamais en rangs', () => {
  const p = plancheCentrale()
  p.est_pepiniere = true
  p.disposition = { rangs_declares: null, rangs_occupes: 0, depassement: 0, nb_lots_en_cours: 3, rangs: [] }
  p.type_pepiniere = 'chaude'
  assert.equal(sousTitreListe(p), 'pépinière chaude · 3 lots')
  assert.equal(occupationCourte(p), TIRET_OCCUPATION)
  assert.equal(occupationDetail(p), null)
  assert.equal(enteteDetail(p).mention, null)
  // [D3] Une pépinière n'a pas de bandeau d'occupation : ni cases, ni rangs.
  assert.deepEqual(bandeauOccupation(p).cases, [])
  assert.equal(ligneEtat(p), 'Pépinière chaude · 3 lots · active')
})

test('[CA13] une parcelle libre le dit — et renvoie au Plan, sans rang actionnable', () => {
  const p = plancheCentrale()
  p.cultures = []
  p.disposition.rangs_occupes = 0
  p.disposition.rangs = [1, 2, 3, 4, 5].map((n) => rang(n, { libre: true, longueur_m: 6 }))
  const detail = detailDeParcelle(p)
  assert.equal(detail.libre, true)
  assert.deepEqual(detail.bandeau.cultures, [])
  assert.equal(detail.bandeau.cases.length, 5)
  assert.equal(sousTitreListe(p), 'libre · 12 m²')
  assert.equal(occupationCourte(p), '0/5')
})

test('[D5] l’en-tête porte les pastilles sans inventer les données absentes', () => {
  const e = enteteDetail(plancheCentrale())
  assert.equal(e.superficie, '12 m²')
  assert.equal(e.exposition, 'sud')
  assert.equal(e.abri, 'Plein air')
  assert.equal(e.paillage, 'oui')
  assert.ok(e.dimensions.startsWith('rangs de 6 m'))
  assert.equal(e.mentionLongueur, null)

  const sansRien = enteteDetail({ nom: 'planche-est', cultures: [], disposition: {} })
  assert.equal(sansRien.superficie, null)
  assert.equal(sansRien.abri, null)
  assert.equal(sansRien.dimensions, null)
  assert.ok(sansRien.mentionLongueur)
})

test('abriTexte distingue « non renseigné » de « plein air »', () => {
  assert.equal(abriTexte(null), null)
  assert.equal(abriTexte('aucun'), 'Plein air')
  assert.equal(abriTexte('serre'), 'Serre')
})

test('[D5 amendé] la ligne d’état dit ce que la parcelle EST, sans rien inventer', () => {
  assert.equal(ligneEtat(plancheCentrale()), 'Pleine terre · sans abri · active')
  assert.equal(ligneEtat({ abri: 'serre' }), 'Pleine terre · sous serre · active')
  // Un abri jamais renseigné ne devient pas une déclaration de plein air.
  assert.equal(ligneEtat({ abri: null }), 'Pleine terre · active')
  assert.equal(ligneEtat({ abri: 'aucun', actif: false }), 'Pleine terre · sans abri · inactive')
})

// ── [US-229] La carte « Caractéristiques » ───────────────────────────────────

/** Le champ `cle` de la grille d'une parcelle. */
const champ = (parcelle, cle) =>
  caracteristiquesDeParcelle(parcelle).find((c) => c.cle === cle)

/** Les clés de la grille, dans l'ordre où elles se rendent. */
const cles = (parcelle) => caracteristiquesDeParcelle(parcelle).map((c) => c.cle)

/** Une planche dont TOUT est renseigné — le cas de CA5. */
function plancheComplete() {
  return {
    id: 9, nom: 'planche_complete', superficie_m2: 12, longueur_m: 6,
    largeur_m: 2, largeur_deduite: true, largeur_incoherente: false,
    nb_rangs: 7, exposition: 'sud', type_sol: 'limoneux',
    abri: 'aucun', paillage: true, est_pepiniere: false, actif: true,
    cultures: [], disposition: { rangs_declares: 7, rangs_occupes: 0, rangs: [] },
  }
}

test('[US-229 / C2] les champs se rendent dans l’ordre de la maquette', () => {
  assert.deepEqual(cles(plancheComplete()), [
    'nom', 'superficie', 'longueur', 'largeur', 'nb_rangs',
    'exposition', 'type_sol', 'abri', 'paillage', 'pepiniere', 'statut',
  ])
})

test('[US-229 / CA5] une parcelle complète n’affiche aucun état manquant', () => {
  const p = plancheComplete()
  assert.equal(caracteristiquesDeParcelle(p).some((c) => c.manquant), false)
  assert.equal(parcelleACompleter(p), false)
  assert.equal(ligneListeParcelle(p).aCompleter, false)
})

test('[US-229 / C3] un champ absent est NOMMÉ, jamais masqué ni remplacé', () => {
  const p = { ...plancheComplete(), type_sol: null }
  const sol = champ(p, 'type_sol')
  assert.equal(sol.manquant, true)
  assert.equal(sol.valeur, NON_RENSEIGNE)
  // Le champ reste dans la grille : il n'est ni retiré, ni rempli d'un repli.
  assert.equal(cles(p).includes('type_sol'), true)
  assert.equal(parcelleACompleter(p), true)
  assert.equal(ligneListeParcelle(p).aCompleter, true)
})

test('[US-229 / C4] « Non renseigné » ne se confond ni avec « Non » ni avec « Aucun »', () => {
  const jamais = { ...plancheComplete(), paillage: null, abri: null }
  assert.equal(champ(jamais, 'paillage').valeur, NON_RENSEIGNE)
  assert.equal(champ(jamais, 'paillage').manquant, true)
  assert.equal(champ(jamais, 'abri').valeur, NON_RENSEIGNE)

  const declare = { ...plancheComplete(), paillage: false, abri: 'aucun' }
  assert.equal(champ(declare, 'paillage').valeur, 'Non')
  assert.equal(champ(declare, 'paillage').manquant, false)
  assert.equal(champ(declare, 'abri').valeur, 'Plein air')
  assert.equal(champ(declare, 'abri').manquant, false)
})

test('[US-229 / C5] la largeur est toujours dite DÉDUITE, jamais déclarée', () => {
  const large = champ(plancheComplete(), 'largeur')
  assert.equal(large.valeur, '2 m')
  assert.equal(large.suffixe, 'déduite')
  assert.equal(large.manquant, false)

  // Sans longueur, la largeur n'existe pas : état manquant et mention.
  const sansLongueur = { ...plancheComplete(), longueur_m: null, largeur_m: null }
  const manquante = champ(sansLongueur, 'largeur')
  assert.equal(manquante.manquant, true)
  assert.equal(manquante.aide, MENTION_LARGEUR_DEDUITE)
  assert.equal(manquante.suffixe, null)
})

test('[US-229 / C5, US-225 / CA7] une largeur incohérente est signalée, pas corrigée', () => {
  const p = { ...plancheComplete(), superficie_m2: 5, longueur_m: 100, largeur_m: 0.05, largeur_incoherente: true }
  const large = champ(p, 'largeur')
  assert.equal(large.valeur, '0,05 m')
  assert.match(large.suffixe, /à vérifier/)
})

test('[US-229 / C6] pépinière et statut ne manquent jamais et ne comptent pas', () => {
  const p = { ...plancheComplete(), est_pepiniere: false, actif: true }
  assert.equal(champ(p, 'pepiniere').valeur, 'Non')
  assert.equal(champ(p, 'pepiniere').manquant, false)
  assert.equal(champ(p, 'statut').valeur, 'Active')
  assert.equal(champ(p, 'statut').manquant, false)
  // Une parcelle servie sans le champ `actif` reste active, pas « manquante ».
  const sansActif = { ...plancheComplete() }
  delete sansActif.actif
  assert.equal(champ(sansActif, 'statut').valeur, 'Active')
  assert.equal(parcelleACompleter(sansActif), false)
})

test('[US-229 / C9] une pépinière retire rangs, longueur et largeur de la grille', () => {
  const p = {
    ...plancheComplete(), est_pepiniere: true,
    longueur_m: null, largeur_m: null, nb_rangs: null,
  }
  assert.deepEqual(cles(p), [
    'nom', 'superficie', 'exposition', 'type_sol', 'abri', 'paillage', 'pepiniere', 'statut',
  ])
  assert.equal(champ(p, 'pepiniere').valeur, 'Oui')
  // [C9] Leur absence ne doit PAS produire la pastille de l'index.
  assert.equal(parcelleACompleter(p), false)
  assert.equal(ligneListeParcelle(p).aCompleter, false)
})

test('[US-229 / C10] une parcelle inactive garde sa carte entière', () => {
  const p = { ...plancheComplete(), actif: false }
  assert.equal(champ(p, 'statut').valeur, 'Inactive')
  assert.equal(cles(p).length, 11)
  assert.equal(parcelleACompleter(p), false)
})

test('[US-229 / CA6] une parcelle dont tout manque reste lisible', () => {
  const p = {
    id: 3, nom: 'planche_est', superficie_m2: null, longueur_m: null,
    largeur_m: null, nb_rangs: null, exposition: null, type_sol: null,
    abri: null, paillage: null, est_pepiniere: false, actif: true,
    cultures: [], disposition: {},
  }
  const champs = caracteristiquesDeParcelle(p)
  assert.equal(champs.length, 11)
  // Le nom reste connu ; tout le reste se dit manquant, sauf les deux booléens.
  assert.deepEqual(
    champs.filter((c) => c.manquant).map((c) => c.cle),
    ['superficie', 'longueur', 'largeur', 'nb_rangs', 'exposition', 'type_sol', 'abri', 'paillage'],
  )
  assert.equal(champ(p, 'nom').valeur, 'planche_est')
  assert.equal(parcelleACompleter(p), true)
})

test('[US-229 / C7] la phrase compagnon porte le NOM RÉEL de la parcelle', () => {
  const p = { ...plancheComplete(), nom: 'planche_centrale', nb_rangs: null }
  const aide = aideCompagnon(p)
  // Un seul champ manque, et il se déclare : la phrase vise CE champ.
  assert.equal(aide.champ, 'nb_rangs')
  assert.equal(aide.phrase, 'planche_centrale a 5 rangs')
})

test('[US-229 / C7] plusieurs champs manquants : la phrase reste générique', () => {
  const p = { ...plancheComplete(), nom: 'planche_est', nb_rangs: null, type_sol: null }
  const aide = aideCompagnon(p)
  assert.equal(aide.champ, null)
  assert.match(aide.phrase, /^planche_est /)
})

test('[US-229 / C7] un champ que le compagnon ne sait pas écrire n’invente pas de commande', () => {
  // Le type de sol n'a aucune phrase dédiée aujourd'hui : on retombe sur
  // l'exemple générique plutôt que sur une commande qui serait refusée.
  const p = { ...plancheComplete(), nom: 'planche_salade', type_sol: null }
  const aide = aideCompagnon(p)
  assert.equal(aide.champ, null)
  assert.equal(aide.phrase.includes('type de sol'), false)
})

test('[US-229 / CA2] aucune division n’est refaite : la largeur vient du serveur', () => {
  // Le serveur n'a pas déduit de largeur (incohérence, arrondi) : l'écran ne
  // la calcule pas lui-même, il dit qu'elle manque.
  const p = { ...plancheComplete(), largeur_m: null }
  assert.equal(champ(p, 'largeur').manquant, true)
})

test('[US-229 / CA1] le détail porte la carte, sans lecture supplémentaire', () => {
  const d = detailDeParcelle(plancheComplete())
  assert.equal(d.caracteristiques.length, 11)
  assert.equal(d.aideCompagnon.phrase.includes('planche_complete'), true)
})

test('[US-229] la pastille d’en-tête dit le paillage en toutes lettres', () => {
  assert.equal(enteteDetail({ ...plancheComplete(), paillage: true }).paillage, 'oui')
  assert.equal(enteteDetail({ ...plancheComplete(), paillage: false }).paillage, 'non')
  assert.equal(enteteDetail({ ...plancheComplete(), paillage: null }).paillage, null)
})
