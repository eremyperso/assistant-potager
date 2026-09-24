// [US-200 / CA2] Les règles de rendu de la Vue plan — `npm test` (`node --test`).
//
// Ce qui se vérifie ici : les longueurs et leur plancher / plafond (V3, A2), les
// segments de poquet et le « ×N » (V4), les libellés de rang et le regroupement
// d'une culture sur plusieurs rangs (V6, V12), les rangs libres (V7), la carte
// pépinière (V8), la donnée manquante (V9, A6), le dépassement (V10), l'en-tête
// (V11), le pied de vue (V14) et la lisibilité en niveaux de gris (V16, CA10).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PLANCHER_PCT, PLAFOND_PCT, MAX_SEGMENTS, MENTION_SANS_RANGS, TYPE_PEPINIERE_INCONNU,
  nombre, quantiteTexte, quantiteTexteCourt, capitaliser, cleUnite, arrondiPair,
  maximaParUnite, segmentsPoquet, longueurRang, rangsDeLaCarte, libelleRang,
  libelleRangCourt, nomAccessibleRang, totalLigne, superficieTexte, compteurRangs, carteDeParcelle,
  piedDeVue, vueDuPlan, palettePhases, gabarit, TAILLES, indicateursParcelle,
  // [US-228] La piste des places.
  MAX_FENTES, PLANCHER_REMPLISSAGE_PCT, MENTION_SANS_LONGUEUR,
  PISTE_PLACES, PISTE_LIGNE, PISTE_DEGRADE, PISTE_LIBRE,
  pisteDuRang, resteDuRang, sousLibelleRang, sousLibelleLibre, dimensionsTexte, phraseLongueur,
} from './planVue.js'
import { PHASES } from './phases.js'
import { symboleDeCulture, estTomateAnanas } from './pictosCultures.js'

test('[US-228] les symboles reprennent les cultures de la maquette et leur repli', () => {
  for (const [culture, symbole] of [
    ['Tomate', '🍅'], ['Tomate cœur de bœuf', '🍅'], ['Tomate cerise', '🍅'],
    ['Courgette', '🥒'], ['Concombre', '🥒'], ['Aubergine', '🍆'],
    ['Poivron', '🫑'], ['Potiron', '🎃'], ['Pâtisson', '🎃'],
    ['Carotte', '🥕'], ['Rutabaga', '🥔'], ['', '🌱'], ['inconnue', '🌱'],
  ]) assert.equal(symboleDeCulture(culture), symbole)
  assert.equal(symboleDeCulture(' Tomates ', 'cerise'), '🍅')
  assert.equal(symboleDeCulture('courgettes', 'jaune'), '🥒')
})

test('[US-228] seule la tomate ananas reçoit le pictogramme jaune', () => {
  for (const [culture, variete] of [['tomate', 'ananas'], [' Tomates ', ' ANANAS '], ['tomate ananas', ''], ['tomate', 'ananas bio']]) {
    assert.equal(estTomateAnanas(culture, variete), true)
    assert.equal(symboleDeCulture(culture, variete), '🍅')
  }
  for (const [culture, variete] of [['tomate', 'cerise'], ['tomate', 'jaune'], ['ananas', ''], ['courgette', 'ananas'], ['tomate', 'ananasette'], ['', '']]) {
    assert.equal(estTomateAnanas(culture, variete), false)
  }
})

// ── Fabriques de charge utile, dans la forme exacte de `GET /plan` ───────────

const ligne = (culture, variete, quantite, unite, mode, numeros, phase = 'en_place') => ({
  culture, variete, nb_plants: quantite, unite,
  mode_implantation: mode, rangs: numeros.length,
  quantite_par_rang: quantite / numeros.length,
  numeros_rangs: numeros, phase,
})

const disposition = (declares, cultures, lots = null) => {
  const occupes = cultures.reduce((s, c) => s + c.numeros_rangs.length, 0)
  const rangs = cultures.flatMap((c) =>
    c.numeros_rangs.map((n) => ({ numero: n, libre: false, culture: c.culture, variete: c.variete, unite: c.unite })))
  for (let n = occupes + 1; n <= (declares ?? 0); n++) {
    rangs.push({ numero: n, libre: true, culture: null, variete: null, unite: null })
  }
  return {
    rangs_declares: declares, rangs_occupes: occupes,
    rangs_libres: declares == null ? null : Math.max(0, declares - occupes),
    depassement: declares == null ? 0 : Math.max(0, occupes - declares),
    rangs, mode_numerotation: 'ordre_installation', nb_lots_en_cours: lots,
  }
}

const parcelle = (nom, superficie, declares, cultures, extra = {}) => ({
  id: 1, nom, superficie_m2: superficie, nb_rangs: declares, ordre: 1,
  est_pepiniere: false, cultures,
  disposition: disposition(declares, cultures, extra.lots ?? null),
  ...extra,
})

/** La planche centrale du Gherkin : 5 rangs, 4 occupés, les trois formes. */
const CENTRALE = [
  ligne('tomate', 'noire de Crimée', 8, 'plants', 'rang', [1]),
  ligne('tomate', 'cerise', 5, 'plants', 'rang', [2]),
  ligne('courgette', '', 3, 'plants', 'rang', [3], 'en_recolte'),
  ligne('carotte', '', 2, 'm²', 'surface', [4], 'semee'),
]

// ── Mise en forme élémentaire ────────────────────────────────────────────────

test('[V6] un nombre s’écrit en français, sans zéro inutile', () => {
  assert.equal(nombre(44.5), '44,5')
  assert.equal(nombre(8), '8')
  assert.equal(nombre(null), '')
})

test('[V6] la quantité est toujours écrite avec son unité', () => {
  assert.equal(quantiteTexte(8, 'plants'), '8 plants')
  // `m2` est la saisie du bot (clavier téléphone) ; l’écran écrit le symbole.
  assert.equal(quantiteTexte(2, 'm2'), '2 m²')
})

test('[CA6] à l’étroit, l’unité s’abrège — le mot complet reste ailleurs', () => {
  assert.equal(quantiteTexteCourt(8, 'plants'), '8 pl.')
  assert.equal(quantiteTexteCourt(5, 'poquets'), '5 poq.')
  assert.equal(quantiteTexteCourt(2, 'm²'), '2 m²')
})

test('[V3] m² et m2 sont la MÊME unité pour la comparaison des traits', () => {
  assert.equal(cleUnite('m2'), cleUnite('m²'))
  assert.equal(capitaliser('tomate'), 'Tomate')
})

test('[V3] les demis vont vers le pair — 37,5 → 38 et 62,5 → 62', () => {
  assert.equal(arrondiPair(37.5), 38)
  assert.equal(arrondiPair(62.5), 62)
  assert.equal(arrondiPair(62.6), 63)
})

// ── V3 / A2 : la longueur d’un trait ─────────────────────────────────────────

test('[V3] chaque unité a son propre maximum dans la parcelle', () => {
  const maxima = maximaParUnite(CENTRALE)
  assert.equal(maxima['plants'], 8)
  assert.equal(maxima['m²'], 2)
})

test('[V3, Gherkin] 8 plants font 100 %, 5 en font 62 %, 3 en font 38 %', () => {
  const maxima = maximaParUnite(CENTRALE)
  assert.equal(longueurRang(CENTRALE[0], maxima), 100)
  assert.equal(longueurRang(CENTRALE[1], maxima), 62)
  assert.equal(longueurRang(CENTRALE[2], maxima), 38)
})

test('[V3, Gherkin] le seul rang en m² est à lui seul son maximum : pleine longueur', () => {
  assert.equal(longueurRang(CENTRALE[3], maximaParUnite(CENTRALE)), PLAFOND_PCT)
})

test('[V3] plancher à 12 % : un trait minuscule reste visible et visable', () => {
  const lignes = [ligne('poireau', '', 200, 'plants', 'rang', [1]), ligne('radis', '', 1, 'plants', 'rang', [2])]
  assert.equal(longueurRang(lignes[1], maximaParUnite(lignes)), PLANCHER_PCT)
})

test('[A2] plafond à 100 % : jamais de dépassement de trait', () => {
  const l = ligne('tomate', '', 8, 'plants', 'rang', [1])
  assert.equal(longueurRang(l, { plants: 2 }), PLAFOND_PCT)
})

// ── V4 : les poquets ─────────────────────────────────────────────────────────

test('[V4] un segment par poquet, et douze segments font la largeur entière', () => {
  assert.deepEqual(segmentsPoquet(5), { segments: 5, exces: null })
  const l = ligne('courge', '', 12, 'poquets', 'poquet', [1])
  assert.equal(longueurRang(l, maximaParUnite([l])), PLAFOND_PCT)
})

test('[V4, Gherkin] au-delà de douze poquets : douze segments et « ×18 »', () => {
  assert.deepEqual(segmentsPoquet(18), { segments: MAX_SEGMENTS, exces: '×18' })
})

test('[V4] un poquet seul fait un douzième — le plancher ne l’allonge pas', () => {
  const l = ligne('courge', '', 1, 'poquets', 'poquet', [1])
  assert.equal(Math.round(longueurRang(l, maximaParUnite([l]))), 8)
})

// ── V6 / V12 : les libellés ──────────────────────────────────────────────────

test('[V6] le libellé porte culture, variété et quantité — aucun survol requis', () => {
  const rangs = rangsDeLaCarte(parcelle('planche-centrale', 12, 5, CENTRALE))
  assert.equal(rangs[0].libelle, 'Tomate noire de Crimée · 8 plants')
  assert.equal(rangs[3].libelle, 'Carotte · 2 m²')
})

test('[CA6] le libellé court laisse tomber la variété et abrège l’unité', () => {
  const rangs = rangsDeLaCarte(parcelle('planche-centrale', 12, 5, CENTRALE))
  assert.equal(rangs[0].libelleCourt, 'Tomate · 8 pl.')
})

test('[retour de terrain] une ligne sur plusieurs rangs dit son TOTAL, pas seulement sa part', () => {
  // 70 graines sur 4 rangs : la part d’un rang est arrondie à 18, et quatre
  // rangs de 18 se relisent 72. Le total est le seul chiffre qui se recoupe.
  const semis = [ligne('tomate', '', 70, 'graines', 'rang', [1, 2, 3, 4], 'semee')]
  const rangs = rangsDeLaCarte(parcelle('planche centrale', 12, 7, semis))
  assert.equal(rangs[0].total, '70 graines sur 4 rangs')
  assert.match(rangs[0].nomAccessible, /70 graines sur 4 rangs au total/)
})

test('[retour de terrain] une ligne sur UN rang n’a pas de total à répéter', () => {
  const rangs = rangsDeLaCarte(parcelle('planche-centrale', 12, 5, CENTRALE))
  assert.equal(rangs[0].total, '')
  assert.equal(totalLigne(rangs[4]), '')
})

test('[A5] tous les rangs portent leur numéro, y compris ceux d’une même culture', () => {
  const poireau = [ligne('poireau', '', 18, 'plants', 'rang', [1, 2, 3])]
  const rangs = rangsDeLaCarte(parcelle('planche', 7, 5, poireau))
  assert.deepEqual(rangs.map((r) => r.numeroCourt), ['R1', 'R2', 'R3', 'R4', 'R5'])
})

test('[V12] une culture sur plusieurs rangs est groupée, les suivants n’ont que la quantité', () => {
  const poireau = [ligne('poireau', '', 18, 'plants', 'rang', [1, 2, 3])]
  const rangs = rangsDeLaCarte(parcelle('planche', 7, 5, poireau))
  assert.equal(rangs[0].suite, false)
  assert.equal(rangs[0].libelle, 'Poireau · 6 plants')
  assert.equal(rangs[1].suite, true)
  assert.equal(rangs[1].libelle, '6 plants')
  assert.equal(rangs[2].libelle, '6 plants')
})

// ── V7 : le rang libre ───────────────────────────────────────────────────────

test('[V7] le rang non occupé est dessiné, porte le mot « libre » et pleine longueur', () => {
  const rangs = rangsDeLaCarte(parcelle('planche-centrale', 12, 5, CENTRALE))
  assert.equal(rangs.length, 5)
  assert.equal(rangs[4].libre, true)
  assert.equal(libelleRang(rangs[4]), 'libre')
  assert.equal(libelleRangCourt(rangs[4]), 'libre')
  assert.equal(rangs[4].longueur, PLAFOND_PCT)
  assert.equal(rangs[4].phase, null)
})

test('[V2] les rangs viennent du rang 1 au dernier, dans l’ordre', () => {
  const rangs = rangsDeLaCarte(parcelle('planche-centrale', 12, 5, CENTRALE))
  assert.deepEqual(rangs.map((r) => r.numero), [1, 2, 3, 4, 5])
})

// ── V16 / CA10 : la couleur ne porte jamais seule ───────────────────────────

test('[CA10] le nom accessible d’un rang dit tout — numéro, culture, quantité, phase', () => {
  const rangs = rangsDeLaCarte(parcelle('planche-centrale', 12, 5, CENTRALE))
  assert.equal(nomAccessibleRang(rangs[1]), 'Rang 2, tomate cerise, 5 plants, en place')
})

// [V16, retour de terrain] Le MOT n'est plus peint sur chaque rang — la
// pastille de `RangPlan` porte la phase par sa forme autant que par sa teinte,
// et la légende donne les mots une fois pour l'écran. Ce qui reste non
// négociable, et que ce test tient, c'est que le mot soit toujours dans le nom
// accessible de la ligne : un lecteur d'écran ne voit aucune forme.
test('[V16] la phase reste dite en toutes lettres dans le nom accessible', () => {
  const rangs = rangsDeLaCarte(parcelle('planche-centrale', 12, 5, CENTRALE))
  for (const r of rangs.filter((x) => !x.libre)) {
    assert.match(nomAccessibleRang(r), /semée|en place|en récolte/)
  }
})

test('[CA10] un rang libre se nomme « Rang 5, libre »', () => {
  const rangs = rangsDeLaCarte(parcelle('planche-centrale', 12, 5, CENTRALE))
  assert.equal(nomAccessibleRang(rangs[4]), 'Rang 5, libre')
})

test('[V4] le compte réel des poquets entre dans le nom accessible', () => {
  const haricot = [ligne('haricot', 'à rames', 18, 'poquets', 'poquet', [1])]
  const rangs = rangsDeLaCarte(parcelle('planche', 8, 3, haricot))
  assert.match(rangs[0].nomAccessible, /18 poquets/)
})

// ── V11 / V10 : l’en-tête de carte ───────────────────────────────────────────

test('[V11, Gherkin] l’en-tête dit « 12 m² » et « 4 rangs sur 5 »', () => {
  const carte = carteDeParcelle(parcelle('planche-centrale', 12, 5, CENTRALE))
  assert.equal(carte.superficie, '12 m²')
  assert.equal(carte.compteur, '4 rangs sur 5')
})

test('[V11] une superficie jamais déclarée se dit, elle ne vaut pas zéro', () => {
  assert.equal(superficieTexte({ superficie_m2: null }), 'superficie non renseignée')
})

test('[V10] dépassement : « 6 rangs occupés pour 5 déclarés », aucune ligne masquée', () => {
  const serree = [
    ligne('poireau', '', 18, 'plants', 'rang', [1, 2, 3]),
    ligne('salade', '', 6, 'plants', 'rang', [4]),
    ligne('radis', '', 1, 'm²', 'surface', [5], 'semee'),
    ligne('betterave', '', 9, 'plants', 'rang', [6]),
  ]
  const carte = carteDeParcelle(parcelle('planche-serrée', 7, 5, serree))
  assert.equal(carte.compteur, '6 rangs occupés pour 5 déclarés')
  assert.equal(carte.depassement, 1)
  assert.equal(carte.rangs.length, 6)
})

test('[V11] sans dénominateur, l’en-tête compte les rangs occupés, sans « sur N »', () => {
  assert.equal(compteurRangs({ rangs_occupes: 1, rangs_declares: null }), '1 rang occupé')
})

// ── V9 / A6 : la donnée manquante ────────────────────────────────────────────

test('[V9, Gherkin] sans nombre de rangs : les cultures restent, aucun rang libre', () => {
  const carte = carteDeParcelle(parcelle('planche-est', null, null, [ligne('courgette', '', 3, 'plants', 'rang', [1])]))
  assert.equal(carte.rangs.length, 1)
  assert.equal(carte.rangs.some((r) => r.libre), false)
  assert.equal(carte.mention, MENTION_SANS_RANGS)
  assert.match(carte.phrase, /planche-est a 5 rangs/)
  assert.equal(carte.vide, false)
})

test('[V9, CA9] sans nombre de rangs NI culture : carte en pointillé, sans dessin', () => {
  const carte = carteDeParcelle(parcelle('planche-nord', null, null, []))
  assert.equal(carte.vide, true)
  assert.equal(carte.rangs.length, 0)
  assert.equal(carte.mention, MENTION_SANS_RANGS)
})

test('[V9] une parcelle ne disparaît jamais du Plan', () => {
  const plan = { parcelles: [parcelle('planche-nord', null, null, [])], totaux: {} }
  assert.equal(vueDuPlan(plan).cartes.length, 1)
})

// ── V8 : la pépinière ────────────────────────────────────────────────────────

test('[V8, Gherkin] la pépinière porte son type et ses lots, et aucun rang libre', () => {
  const serre = parcelle('SERRE', 2.5, null, [ligne('basilic', '', 6, 'plants', 'rang', [1])], {
    est_pepiniere: true, lots: 3,
  })
  const carte = carteDeParcelle(serre)
  assert.equal(carte.pepiniere, true)
  assert.equal(carte.typePepiniere, TYPE_PEPINIERE_INCONNU)
  assert.equal(carte.nbLots, 3)
  assert.equal(carte.compteur, null)
  // La mention « nombre de rangs non renseigné » ne s’applique pas : une
  // pépinière ne se compte pas en rangs.
  assert.equal(carte.mention, null)
})

test('[V8] une plantation faite dans la pépinière reste dessinée en rang', () => {
  const serre = parcelle('SERRE', 2.5, 2, [ligne('basilic', '', 6, 'plants', 'rang', [1])], {
    est_pepiniere: true, lots: 3,
  })
  const carte = carteDeParcelle(serre)
  assert.equal(carte.rangs.length, 1)
  assert.equal(carte.rangs[0].culture, 'basilic')
})

// ── V14 : le pied de vue ─────────────────────────────────────────────────────

test('[V14] trois chiffres : surface, rangs occupés sur déclarés, rangs libres', () => {
  const pied = piedDeVue({
    superficie_totale_m2: 39.5, rangs_declares: 18, rangs_occupes: 16,
    occupation_rangs_pct: 89, parcelles_sans_nb_rangs: 3,
    rangs_libres_par_parcelle: [
      { parcelle: 'planche-centrale', rangs_libres: 1 },
      { parcelle: 'planche-courges', rangs_libres: 0 },
      { parcelle: 'planche-ombre', rangs_libres: 2 },
      { parcelle: 'planche-est', rangs_libres: null },
    ],
  })
  assert.equal(pied.surface, '39,5 m²')
  assert.equal(pied.rangs, '16 rangs occupés sur 18 déclarés — 89 %')
  assert.equal(pied.libres, 'Libre : planche-centrale (1 rang), planche-ombre (2 rangs)')
  assert.equal(pied.sansNbRangs, '3 parcelles sans nombre de rangs')
})

test('[CA9] au premier jour, le pied compte les parcelles sans nombre de rangs', () => {
  const pied = piedDeVue({ superficie_totale_m2: 0, rangs_declares: 0, rangs_occupes: 0,
    occupation_rangs_pct: null, parcelles_sans_nb_rangs: 6, rangs_libres_par_parcelle: [] })
  assert.equal(pied.rangs, '0 rangs occupés sur 0 déclarés')
  assert.equal(pied.libres, 'Aucun rang libre')
  assert.equal(pied.sansNbRangs, '6 parcelles sans nombre de rangs')
})

// ── V1 / V17 : l’écran entier ────────────────────────────────────────────────

test('[V1] les cartes viennent dans l’ordre déclaré, puis par nom', () => {
  const plan = {
    parcelles: [
      { ...parcelle('zèbre', 1, 1, []), id: 3, ordre: 2 },
      { ...parcelle('abri', 1, 1, []), id: 2, ordre: 1 },
      { ...parcelle('sans-ordre', 1, 1, []), id: 4, ordre: null },
    ],
    totaux: {},
  }
  assert.deepEqual(vueDuPlan(plan).cartes.map((c) => c.nom), ['abri', 'zèbre', 'sans-ordre'])
})

test('[V17] les cultures non localisées forment une dernière carte, sans rang', () => {
  const plan = {
    parcelles: [], totaux: {},
    non_localisees: [{ culture: 'tomate', variete: 'green zebra', nb_plants: 4, unite: 'plants', mode_implantation: 'rang' }],
  }
  const vue = vueDuPlan(plan)
  assert.equal(vue.nonLocalisees.length, 1)
  assert.equal(vue.nonLocalisees[0].libelle, 'Tomate green zebra · 4 plants')
  assert.match(vue.phraseNonLocalisees, /compagnon/)
})

test('[CA1] la vue se construit de la SEULE charge utile de GET /plan', () => {
  const vue = vueDuPlan({ parcelles: [parcelle('planche-centrale', 12, 5, CENTRALE)], totaux: {}, date_ref_effective: '2026-09-23' })
  assert.equal(vue.dateRef, '2026-09-23')
  assert.equal(vue.cartes[0].rangs.length, 5)
})

test('[CA8] un plan absent ne fait pas tomber la vue, il la rend vide', () => {
  const vue = vueDuPlan(null)
  assert.deepEqual(vue.cartes, [])
  assert.deepEqual(vue.nonLocalisees, [])
})

// ── CA4 : palette et taille en paramètre ─────────────────────────────────────

test('[V16] chaque phase a une FORME propre — la couleur ne porte pas seule', () => {
  // C'est ce qui autorise `RangPlan` à retirer le mot de chaque rang : trois
  // formes distinctes se lisent encore en niveaux de gris.
  const formes = PHASES.map((p) => p.forme)
  assert.equal(new Set(formes).size, PHASES.length)
})

test('[CA4, V5] la teinte d’un trait vient de la PHASE, jamais de la famille', () => {
  const palette = palettePhases()
  assert.notEqual(palette.trait('semee'), palette.trait('en_recolte'))
  // Une phase inconnue retombe sur la teinte « libre », jamais sur un vert de repli.
  assert.equal(palette.trait(null), palette.libre)
})

test('[CA4, US-222] deux gabarits, pour que l’onglet Parcelles agrandisse sans redessiner', () => {
  assert.notEqual(gabarit('grande').trait, gabarit('normale').trait)
  assert.equal(gabarit('inconnue'), TAILLES.normale)
})

// ══════════════════════════════════════════════════════════════════════════════
// [US-228] La piste des places — P1 à P15
// ══════════════════════════════════════════════════════════════════════════════

/** Une ligne de culture qui porte son espacement (US-226). */
const ligneEspacee = (culture, quantite, unite, mode, numeros, espacement, phase = 'en_place') => ({
  ...ligne(culture, '', quantite, unite, mode, numeros, phase),
  espacement_rang_cm: espacement,
})

/** Une parcelle mesurée, dont la disposition porte les places (US-227). */
const parcelleMesuree = (longueur, declares, cultures, chiffresParRang = {}, extra = {}) => {
  const p = parcelle('planche-centrale', 69, declares, cultures, { longueur_m: longueur, ...extra })
  p.disposition.rangs = p.disposition.rangs.map((r) => ({
    ...r,
    ...(r.libre
      ? { longueur_m: longueur, capacite_exemple: extra.exemple ?? null }
      : chiffresParRang[r.numero] ?? {}),
  }))
  return p
}

const chiffres = (places, prises, espacement) => ({
  places,
  places_prises: Math.min(places, prises),
  places_restantes: Math.max(0, places - prises),
  depassement_places: Math.max(0, prises - places),
  espacement_rang_cm: espacement,
})

test('[US-198 CA15] les quantités propres aux rangs remplacent la moyenne de ligne', () => {
  const cultures = [ligneEspacee('laitue', 16, 'plants', 'rang', [1, 2], 30)]
  const p = parcelleMesuree(4, 5, cultures, {
    1: { ...chiffres(13, 13, 30), quantite_par_rang: 13 },
    2: { ...chiffres(13, 3, 30), quantite_par_rang: 3 },
  })
  const rangs = rangsDeLaCarte(p).filter(rang => !rang.libre)
  assert.deepEqual(rangs.map(rang => rang.quantite), [13, 3])
  assert.deepEqual(rangs.map(rang => rang.sousLibelle.quantite), ['13 plants', '3 plants'])
  assert.deepEqual(rangs.map(rang => rang.reste.valeur), ['0', '10'])
  assert.match(rangs[1].nomAccessible, /3 plants/)
})

test('[US-198 CA15] une autre culture interrompt le regroupement visuel', () => {
  const cultures = [
    ligneEspacee('laitue', 34, 'plants', 'rang', [1, 3], 30),
    ligneEspacee('tomate', 3, 'plants', 'rang', [2], 50),
  ]
  const p = parcelleMesuree(4, 3, cultures, {
    1: { ...chiffres(13, 13, 30), quantite_par_rang: 13 },
    3: { ...chiffres(13, 21, 30), quantite_par_rang: 21 },
  })
  const rangs = rangsDeLaCarte(p)
  assert.deepEqual(rangs.map(rang => rang.culture), ['laitue', 'tomate', 'laitue'])
  assert.equal(rangs[2].suite, false)
  assert.equal(rangs[0].dernierDuGroupe, true)
  assert.equal(rangs[2].reste.valeur, '8')
  assert.equal(rangs[2].reste.alerte, true)
})

test('[P1, P5] un rang à moitié plein : 24 places, 9 prises, 15 restantes', () => {
  const cultures = [ligneEspacee('tomate', 9, 'plants', 'rang', [1], 50)]
  const p = parcelleMesuree(12, 2, cultures, { 1: chiffres(24, 9, 50) })
  const [rang] = rangsDeLaCarte(p)

  assert.equal(rang.piste.variante, PISTE_PLACES)
  assert.equal(rang.piste.fentes, 7)
  assert.equal(rang.piste.pleines, 3)
  assert.deepEqual(rang.reste, { prefixe: 'reste', valeur: '15', unite: 'plants', alerte: false })
  assert.equal(rang.sousLibelle.quantite, '9 plants')
  assert.equal(rang.sousLibelle.espacement, '50 cm')
})

test('[P2] sept repères proportionnels, sans équivalence en graines', () => {
  const cultures = [ligneEspacee('carotte', 60, 'graines', 'rang', [1], 5, 'semee')]
  const p = parcelleMesuree(12, 1, cultures, { 1: chiffres(240, 60, 5) })
  const [rang] = rangsDeLaCarte(p)

  assert.equal(rang.piste.fentes, MAX_FENTES)
  assert.equal(rang.piste.pleines, 2)
  assert.equal(rang.piste.legende, null)
  assert.equal(rang.sousLibelle.quantite, '60 graines')
  assert.equal(rang.reste.valeur, '180')
})

test('[P2] sept repères même pour deux places, du rang vide au dépassement', () => {
  for (const [prises, pleines] of [[0, 0], [1, 4], [2, 7], [3, 7]]) {
    const piste = pisteDuRang({ places: 2, placesPrises: prises })
    assert.equal(piste.fentes, 7)
    assert.equal(piste.pleines, pleines)
  }
})

test('[P3] une seule place prise reste visible — plancher de 8 %', () => {
  const cultures = [ligneEspacee('tomate', 1, 'plants', 'rang', [1], 50)]
  const p = parcelleMesuree(12, 1, cultures, { 1: chiffres(24, 1, 50) })
  const [rang] = rangsDeLaCarte(p)

  assert.equal(rang.piste.remplissage, PLANCHER_REMPLISSAGE_PCT)  // 4 % en brut
  assert.equal(rang.piste.pleines, 1)
})

test('[P4] rang surchargé : piste pleine, « +4 », et la quantité déclarée intacte', () => {
  const cultures = [ligneEspacee('tomate', 26, 'plants', 'rang', [1], 40, 'en_recolte')]
  const p = parcelleMesuree(9, 1, cultures, { 1: chiffres(22, 26, 40) })
  const [rang] = rangsDeLaCarte(p)

  assert.equal(rang.piste.exces, 4)
  assert.equal(rang.piste.pleines, rang.piste.fentes)
  assert.deepEqual(rang.reste, { prefixe: '', valeur: '4', unite: 'en trop', alerte: true })
  assert.equal(rang.sousLibelle.quantite, '26 plants')
})

test('[P6] mode dégradé : sans places, la longueur relative d’US-200 revient', () => {
  const cultures = [ligne('tomate', 'cerise', 8, 'plants', 'rang', [1])]
  const p = parcelle('planche-est', null, null, cultures)
  const [rang] = rangsDeLaCarte(p)

  assert.equal(rang.piste.variante, PISTE_DEGRADE)
  assert.equal(rang.piste.fentes, 0)
  assert.equal(rang.piste.remplissage, rang.longueur)
  assert.deepEqual(rang.reste, { prefixe: '', valeur: '8', unite: 'places ?', alerte: false })
})

test('[P7] semis en ligne : part semée, aucune place, aucun reste', () => {
  const cultures = [ligneEspacee('carotte', 3, 'ml', 'rang', [1], 5, 'semee')]
  const p = parcelleMesuree(9, 1, cultures, { 1: { places: null, part_semee: 1 / 3, metres_restants: 6 } })
  const [rang] = rangsDeLaCarte(p)

  assert.equal(rang.piste.variante, PISTE_LIGNE)
  assert.equal(rang.piste.remplissage, 33)
  assert.equal(rang.reste, null)
  assert.equal(rang.sousLibelle.quantite, '3 m semés')
})

test('[P7] un semis en ligne plus long que le rang remplit la piste, sans déborder', () => {
  const cultures = [ligneEspacee('radis', 11, 'ml', 'rang', [1], 4, 'semee')]
  const p = parcelleMesuree(9, 1, cultures, { 1: { places: null, part_semee: 1, metres_restants: 0 } })
  const [rang] = rangsDeLaCarte(p)

  assert.equal(rang.piste.remplissage, 100)
  assert.equal(rang.piste.pleines, MAX_FENTES)
})

test('[P8] un semis en surface n’a pas de places : la trame et le mode dégradé', () => {
  const cultures = [ligneEspacee('épinard', 2, 'm²', 'surface', [1], 30, 'semee')]
  const p = parcelleMesuree(12, 1, cultures, { 1: chiffres(40, 2, 30) })
  const [rang] = rangsDeLaCarte(p)

  assert.equal(rang.piste.variante, PISTE_DEGRADE)
})

test('[P9] rang libre : tout en creux, sa longueur et son exemple nommé', () => {
  const cultures = [ligneEspacee('tomate', 9, 'plants', 'rang', [1], 50)]
  const p = parcelleMesuree(12, 2, cultures, { 1: chiffres(24, 9, 50) },
    { exemple: { nombre: 24, culture: 'tomate' } })
  const libre = rangsDeLaCarte(p).find((r) => r.libre)

  assert.equal(libre.piste.variante, PISTE_LIBRE)
  assert.equal(libre.piste.pleines, 0)
  assert.equal(libre.sousLibelleLibre, '12 m · ex. 24 tomates')
  assert.equal(libre.reste, null)
})

test('[P9] jamais d’exemple sans culture de référence', () => {
  const cultures = [ligne('laitue', '', 6, 'plants', 'rang', [1])]
  const p = parcelleMesuree(12, 2, cultures, {})
  const libre = rangsDeLaCarte(p).find((r) => r.libre)

  assert.equal(libre.sousLibelleLibre, '12 m')
})

test('[P11] quatre indicateurs explicites, sans recalcul de largeur', () => {
  const complets = indicateursParcelle({ superficie_m2: 69, longueur_m: 12, largeur_m: 5.75,
    disposition: { rangs_occupes: 12, rangs_declares: 14, rangs_libres: 2 } })
  assert.deepEqual(complets.map(indicateur => indicateur.texte), ['69 m²', 'rangs de 12 m', 'largeur 5,75 m', 'Total 14 rangs (12 occupés)'])
  assert.ok(complets.every(indicateur => !indicateur.alerte))
  const manquants = indicateursParcelle({ superficie_m2: 18, disposition: { rangs_occupes: 3 } })
  assert.deepEqual(manquants.map(indicateur => indicateur.texte), ['18 m²', 'longueur ?', 'largeur ?', '3 rangs occupés · total ?'])
  assert.deepEqual(manquants.map(indicateur => indicateur.alerte), [false, true, true, true])
  assert.equal(indicateursParcelle({})[0].texte, '? m²')
  assert.equal(indicateursParcelle({ superficie_m2: 69, longueur_m: 12 })[2].texte, 'largeur ?')
  assert.equal(indicateursParcelle({ largeur_m: 0.05, largeur_incoherente: true })[2].texte, 'largeur incohérente, à vérifier')
  assert.equal(indicateursParcelle({ est_pepiniere: true }).length, 1)
})

test('[P11] le compteur présente le total et les rangs occupés', () => {
  for (const [declares, occupes, attendu] of [
    [7, 3, 'Total 7 rangs (3 occupés)'],
    [1, 1, 'Total 1 rang (1 occupé)'],
    [7, 0, 'Total 7 rangs (0 occupé)'],
    [2, 3, 'Total 2 rangs (3 occupés)'],
  ]) {
    const indicateur = indicateursParcelle({ disposition: { rangs_declares: declares, rangs_occupes: occupes } })
      .find(indicateur => indicateur.cle === 'rangs')
    assert.equal(indicateur.texte, attendu)
  }
})

test('[P11] l’en-tête dit la longueur et la largeur DÉDUITE', () => {
  assert.equal(
    dimensionsTexte({ longueur_m: 12, largeur_m: 5.75, largeur_deduite: true }),
    'rangs de 12 m · largeur 5,75 m déduite',
  )
  assert.equal(dimensionsTexte({ longueur_m: null }), null)
})

test('[P11, US-225 / CA7] une largeur incohérente est dite, jamais corrigée', () => {
  const texte = dimensionsTexte({ longueur_m: 100, largeur_m: 0.05, largeur_incoherente: true })
  assert.match(texte, /incohérente/)
  assert.doesNotMatch(texte, /0,05/)
})

test('[P12] la parcelle sans longueur porte sa mention ET sa phrase', () => {
  const carte = carteDeParcelle(
    parcelle('planche-est', 18, 3, [ligne('courgette', '', 3, 'plants', 'rang', [1])]),
  )
  assert.equal(carte.mentionLongueur, MENTION_SANS_LONGUEUR)
  assert.match(carte.phraseLongueur, /planche-est a des rangs de 12 m/)
  // [P12] Les deux absences se cumulent : ici le nombre de rangs, lui, est connu.
  assert.equal(carte.mention, null)
})

test('[P12] une pépinière ne réclame pas de longueur : elle n’a pas de places', () => {
  const carte = carteDeParcelle(parcelle('SERRE', 2.5, null, [], { est_pepiniere: true, lots: 3 }))
  assert.equal(carte.mentionLongueur, null)
  assert.equal(carte.dimensions, null)
})

test('[P14, RT13] le pied compte les parcelles sans longueur, et aucune place', () => {
  const pied = piedDeVue({
    superficie_totale_m2: 39.5, rangs_declares: 18, rangs_occupes: 16,
    occupation_rangs_pct: 89, parcelles_sans_nb_rangs: 3, parcelles_sans_longueur: 4,
    rangs_libres_par_parcelle: [],
  })

  assert.equal(pied.sansLongueur, '4 parcelles sans longueur')
  assert.equal(Object.keys(pied).some((c) => c.includes('place')), false)
  assert.equal(JSON.stringify(pied).includes('remplissage'), false)
})

test('[CA10] le nom accessible dit les places, jamais le seul dessin', () => {
  const cultures = [ligneEspacee('tomate', 9, 'plants', 'rang', [1], 50)]
  const p = parcelleMesuree(12, 2, cultures, { 1: chiffres(24, 9, 50) },
    { exemple: { nombre: 24, culture: 'tomate' } })
  const [rang, libre] = rangsDeLaCarte(p)

  assert.equal(rang.nomAccessible, 'Rang 1, tomate, 9 plants, sur 24 places, 15 restantes, en place')
  assert.equal(libre.nomAccessible, 'Rang 2, libre, 12 m · par exemple 24 tomates')
})

test('[CA10] un rang surchargé le dit aussi en toutes lettres', () => {
  const cultures = [ligneEspacee('tomate', 26, 'plants', 'rang', [1], 40, 'en_recolte')]
  const p = parcelleMesuree(9, 1, cultures, { 1: chiffres(22, 26, 40) })
  const [rang] = rangsDeLaCarte(p)

  assert.match(rang.nomAccessible, /sur 22 places, 4 en trop/)
})

test('[CA9] le premier jour, aucune piste de places — l’écran d’US-200 à l’identique', () => {
  const vue = vueDuPlan({ parcelles: [parcelle('planche-est', 18, 5, CENTRALE)], totaux: {} })
  for (const rang of vue.cartes[0].rangs) {
    assert.equal(rang.piste.variante, rang.libre ? PISTE_LIBRE : PISTE_DEGRADE)
  }
})
