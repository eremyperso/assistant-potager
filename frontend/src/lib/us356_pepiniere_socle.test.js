// [US-356] La Pépinière posée sur le socle — `npm test`.
//
// Ce qui se vérifie ici : les trois onglets et leurs lignes de contexte (CA1), le Parcours en colonnes
// par stade et emplacement (CA2, CA3), la carte de lot et ses alertes (CA4), les mots de Gaston
// (CA5, CA8, CA10), les groupes de « Semer » et leurs motifs (CA6, CA7), le registre des Lots (CA9) et,
// par lecture des sources, la pose sur la coquille et la fiche du lot au format commun (CA11).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import {
  ongletPepiniere, ongletsPepiniere, ongletDeLIntention, CONTEXTE_ONGLET, etapeDuStadePepiniere, enteteGroupe,
  colonnesParStade, alertesDesLots, statutPepiniere, comptesRegistre, carteLot, motDuParcours, motDesLots,
  motDeSemer, tuilesASemer, motifEcarte, ecartees, prochainesOuvertures, jourCourt, fenetreEnClair, avecArticle,
  bilanRegistre, lotsDuRegistre, rangeesParMoisDeSemis, matriceRegistre, carteLotDuRegistre, ligneRegistre, stadeDuLot, emplacementDuLot,
  gestesDeLaFiche, COLONNES_REGISTRE, colonneRegistreInitiale,
} from './pepiniereSocle.js'
import { kanban } from './parcours.js'
import { NAV } from '../navigation.js'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const lire = (chemin) => readFileSync(join(SRC, chemin), 'utf8')
const VUE = lire('views/Pepiniere.jsx')

const AUJOURDHUI = '2026-11-23'

const lotBase = (extra) => ({
  lot_id: 'semis-1', numero_lot: 1, culture: 'oignon blanc', variete: 'de Paris', date_semis: '2026-10-20',
  graines_semees: 30, graines_non_soldees: 30, stock_residuel_godet: 0, nb_leves: null, parcelle: 'Châssis froid', type_pepiniere: 'froide', ...extra,
})
const etiquette = (lot, extra) => ({
  id: `etq-${lot.lot_id}`, stade: 'levee', emplacement_id: 3, etat: 'levee_en_cours',
  lot: { id: lot.lot_id, numero: lot.numero_lot, culture: lot.culture, variete: lot.variete, date_semis: lot.date_semis },
  quantites: { graines: 30, unite: 'graines', godets: 0 }, echeance: { en_retard: false }, ...extra,
})

const OIGNON = lotBase({ lot_id: 'semis-57', numero_lot: 57, note: 'Arrosé par le dessous.' })
const CHOU = lotBase({ lot_id: 'semis-64', numero_lot: 64, culture: 'chou-fleur', variete: 'Merveille', date_semis: '2026-11-21', parcelle: null })
const LAITUE = lotBase({ lot_id: 'semis-59', numero_lot: 59, culture: 'laitue', variete: 'Reine de mai', date_semis: '2026-11-12', graines_non_soldees: 0, stock_residuel_godet: 24, nb_mises_en_godet: 1 })
const FINI = lotBase({ lot_id: 'semis-44', numero_lot: 44, culture: 'laitue', variete: "d'hiver", cloture: true, nb_plantes: 10, graines_non_soldees: 0, date_semis: '2026-09-02' })
const LOTS = [OIGNON, CHOU, LAITUE, FINI]
const PARCOURS = {
  pepinieres: [{ id: 3, nom: 'Châssis froid', type_pepiniere: 'froide', superficie_m2: 2, nb_lots: 2 }],
  sans_emplacement: { nb_lots: 1 },
  etiquettes: [
    etiquette(OIGNON, { echeance: { en_retard: true } }),
    etiquette(CHOU, { emplacement_id: null }),
    etiquette(LAITUE, { stade: 'godet', quantites: { godets: 24, graines: 24 } }),
  ],
  dormants: [],
}

// ── CA1 : les trois onglets ───────────────────────────────────────────────────────────────────────

test('[CA1] trois onglets : Parcours, Semer · n, Lots · n', () => {
  assert.deepEqual(ongletsPepiniere({ nbSemer: 3, nbLots: 18 }).map((o) => [o.id, o.label]),
    [['parcours', 'Parcours'], ['semer', 'Semer · 3'], ['lots', 'Lots · 18']])
})

test('[CA1] la ligne de contexte change avec l’onglet', () => {
  assert.equal(CONTEXTE_ONGLET.parcours, 'Châssis froid et serre chaude, lot par lot')
  assert.equal(CONTEXTE_ONGLET.semer, 'Le bon moment pour semer')
  assert.equal(CONTEXTE_ONGLET.lots, 'Le registre de la saison, lot par lot')
})

test('[CA1] les adresses et les liens du Plan ouvrent le bon onglet', () => {
  assert.equal(ongletPepiniere('lots'), 'lots')
  assert.equal(ongletPepiniere('semer'), 'semer')
  assert.equal(ongletPepiniere('aujourdhui'), 'parcours')
  assert.equal(ongletDeLIntention({ onglet: 'lots' }), 'lots')
  assert.equal(ongletDeLIntention({ emplacement: 'Serre' }), 'parcours')
  assert.equal(ongletDeLIntention({ onglet: 'calendrier' }), 'parcours')
  assert.equal(ongletDeLIntention(null), null)
})

test('[CA1] le titre « Ma pépinière » ; l’en-tête déclaré par la vue porte les onglets', () => {
  assert.equal(NAV.find((n) => n.id === 'pepiniere').title, 'Ma pépinière')
  assert.match(VUE, /entete: \{\s*contexte: CONTEXTE_ONGLET\[onglet\]/)
  assert.match(VUE, /onglets: ongletsPepiniere\(\{ nbSemer, nbLots: tousLots\.length \}\)/)
  assert.match(lire('components/PageHeader.jsx'), /declaration\?\.entete/)
})

// ── CA2, CA3 : le Parcours ────────────────────────────────────────────────────────────────────────

test('[CA3] les stades se lisent par la correspondance d’étape : En levée → Levé, En godet → En godet…', () => {
  assert.equal(etapeDuStadePepiniere('levee'), 'levee')
  assert.equal(etapeDuStadePepiniere('godet'), 'en_godet')
  assert.equal(etapeDuStadePepiniere('endurcissement'), 'croissance')
  assert.equal(etapeDuStadePepiniere('pret'), 'plantee')
})

test('[CA3, Gherkin 1] un stade à la fois, les lots groupés par emplacement avec leur compte', () => {
  const k = kanban(PARCOURS)
  const colonnes = colonnesParStade(k)
  assert.deepEqual(colonnes.map((c) => c.cle), ['levee', 'godet', 'endurcissement', 'pret'])
  const levee = colonnes[0]
  assert.equal(levee.total, 2)
  assert.deepEqual(levee.groupes.map((g) => [g.ligne.nom, g.etiquettes.length]), [['Châssis froid', 1], ['Sans emplacement', 1]])
  const tete = enteteGroupe(levee.groupes[0].ligne, 1)
  assert.equal(tete.texte, 'Châssis froid · 1')
  assert.equal(tete.couleur, '#5A8CC8')
  assert.equal(enteteGroupe(levee.groupes[1].ligne, 1).sousTitre, 'à ranger')
})

test('[CA2, CA3] ordinateur : matrice avec son titre ; mobile : pager aimanté à points', () => {
  const o = lire('components/OngletParcours.jsx')
  assert.match(o, /Le parcours du plant · emplacement × stade/)
  assert.match(o, /grid-cols-\[150px_repeat\(4,minmax\(0,1fr\)\)\]/)
  assert.match(o, /<PagerAimante/)
  assert.match(o, /fond-chaude/)
  assert.match(o, /trame-sans-emplacement/)
  const p = lire('components/PagerAimante.jsx')
  assert.match(p, /snap-x snap-mandatory/)
  assert.match(p, /w-\[18px\] bg-brand/)   // le point courant, allongé, en vert
  assert.match(p, /role="tablist"/)
})

// ── CA4 : la carte de lot ─────────────────────────────────────────────────────────────────────────

test('[CA4] la carte : emoji, nom, « #57 », « variété · quantité · semé le 20 oct. », la note', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  const c = carteLot({ lot: OIGNON, etiquette: PARCOURS.etiquettes[0], alerte: alertes.get('semis-57') })
  assert.equal(c.nom, 'Oignon blanc')
  assert.equal(c.numero, '#57')
  assert.match(c.meta, /^de Paris · 30 graines · semé le 20 oct\.?$/)
  assert.equal(c.note, 'Arrosé par le dessous.')
  assert.ok(c.emoji)
})

test('[CA4] alertes : « Pas levé après 36 j », « Sans emplacement » ; un lot terminé n’en a pas', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  assert.equal(alertes.get('semis-57').texte, 'Pas levé après 34 j')
  assert.equal(alertes.get('semis-64').texte, 'Sans emplacement')
  assert.equal(alertes.has('semis-59'), false)
  assert.equal(alertes.has('semis-44'), false)
})

test('[CA4] plus de « Durée ? » sur les cartes ; la note du jardinier est la seule écriture manuscrite', () => {
  const carte = lire('components/CarteLot.jsx')
  assert.doesNotMatch(carte, /Durée \?/)
  assert.doesNotMatch(carte, /font-hand/)
  assert.match(carte, /note-carnet-texte/)
  assert.match(carte, /bg-due-bg/)
})

// ── CA5, CA10 : les mots de Gaston du Parcours et des Lots ───────────────────────────────────────

test('[CA5] « 2 lots à régler : l’oignon blanc n’a pas levé après 34 jours, le chou-fleur attend un emplacement. »', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  const mot = motDuParcours({ lots: LOTS, alertes })
  assert.match(mot.texte, /^\*\*2 lots à régler\*\* : l’oignon blanc n’a pas levé après 34 jours, le chou-fleur attend un emplacement\.$/)
  assert.deepEqual(mot.actions.map((a) => a.libelle), ['Ranger le chou-fleur', 'Voir les lots'])
  assert.equal(mot.actions[0].noter, true)
  assert.deepEqual(mot.actions[1].intention, { onglet: 'lots', filtreLots: 'a_regler' })
})

test('[CA5, CA10] rien à régler : pas de mot', () => {
  assert.equal(motDuParcours({ lots: [LAITUE], alertes: new Map() }), null)
  assert.equal(motDesLots({ lots: [LAITUE], alertes: new Map() }), null)
})

test('[CA10] le mot des Lots : les lots à régler, sans action (le tableau montre la colonne « À régler »)', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  assert.match(motDesLots({ lots: LOTS, alertes }).texte, /2 lots à régler/)
  assert.deepEqual(motDesLots({ lots: LOTS, alertes }).actions, [])
})

test('articles des cultures', () => {
  assert.match(avecArticle('oignon blanc'), /^l.oignon blanc$/)
  assert.equal(avecArticle('chou-fleur'), 'le chou-fleur')
  assert.equal(avecArticle('mâche'), 'la mâche')
})

// ── CA6, CA7, CA8 : Semer ────────────────────────────────────────────────────────────────────────────

const SEMER = {
  a_semer: [
    { culture: 'oignon blanc', du: '2026-09-01', au: '2026-11-30', jours_restants: 7, part_ecoulee: 0.85, varietes_en_stock: ['de Paris'], confiance: { pepiniere: { libelle: 'pépinière froide' } } },
    { culture: 'laitue', du: '2026-09-15', au: '2026-12-01', jours_restants: 8, part_ecoulee: 0.7, varietes_en_stock: ['Merveille d’hiver', 'Rouge grenobloise'] },
    { culture: 'fève', du: '2026-10-01', au: '2026-12-15', jours_restants: 22, part_ecoulee: 0.45, varietes_en_stock: ['Aguadulce'] },
  ],
  a_semer_ecartees: [
    { culture: 'mache', motif: 'graines_epuisees', lot_numero: null },
    { culture: 'laitue', motif: 'lot_en_cours', lot_numero: 59 },
    { culture: 'mystere', motif: 'inconnu' },
  ],
  prochaines_ouvertures: [
    { culture: 'poireau d’été', date: '2027-01-01', jours: 39 },
    { culture: 'tomate', date: '2027-02-01', jours: 70 },
  ],
}

test('[CA6] une tuile par culture : « reste 7 j », la part écoulée, « 1er sept. → 30 nov. · pépinière froide », les variétés', () => {
  const [oignon] = tuilesASemer(SEMER)
  assert.equal(oignon.nom, 'Oignon blanc')
  assert.equal(oignon.reste, 'reste 7 j')
  assert.equal(oignon.part, 85)
  assert.equal(oignon.fenetre, '1er sept. → 30 nov. · pépinière froide')
  assert.deepEqual(oignon.varietes, ['de Paris'])
  assert.equal(jourCourt('2026-11-30'), '30 nov.')
  assert.equal(fenetreEnClair({ fenetre: 'septembre → octobre' }), 'septembre → octobre')
})

test('[CA6, CA7, Gherkin 2] les motifs d’écart : graines épuisées, lot en cours (#59) ; un motif inconnu n’est pas dit', () => {
  assert.equal(motifEcarte({ motif: 'graines_epuisees' }), 'Graines épuisées : à racheter')
  assert.equal(motifEcarte({ motif: 'lot_en_cours', lot_numero: 59 }), 'Un lot est déjà en cours (#59)')
  assert.equal(motifEcarte({ motif: 'lot_en_cours' }), 'Un lot est déjà en cours')
  assert.equal(motifEcarte({ motif: 'inconnu' }), null)
  assert.deepEqual(ecartees(SEMER).map((e) => [e.nom, e.motif]), [
    ['Mache', 'Graines épuisées : à racheter'], ['Laitue', 'Un lot est déjà en cours (#59)'],
  ])
})

test('[CA6] Bientôt : plusieurs prochaines ouvertures, avec « dans N j »', () => {
  assert.deepEqual(prochainesOuvertures(SEMER).map((o) => [o.nom, o.texte, o.dans]), [
    ['Poireau d’été', 'semis en pépinière à partir du 1er janv.', 'dans 39 j'],
    ['Tomate', 'semis en pépinière à partir du 1er févr.', 'dans 70 j'],
  ])
})

test('[CA8] « 3 cultures sont dans leur fenêtre et vous avez les graines. L’oignon blanc ferme dans 7 jours. »', () => {
  const mot = motDeSemer(SEMER)
  assert.match(mot.texte, /^\*\*3 cultures sont dans leur fenêtre\*\* et vous avez les graines\. L.oignon blanc ferme dans 7 jours\.$/)
  assert.match(mot.actions[0].libelle, /^Semer l.oignon blanc$/)
  assert.equal(mot.actions[0].noter, true)
})

test('[CA8] aucune fenêtre ouverte : le mot annonce la prochaine ouverture', () => {
  const mot = motDeSemer({ a_semer: [], prochaines_ouvertures: SEMER.prochaines_ouvertures })
  assert.match(mot.texte, /Aucune fenêtre n’est ouverte/)
  assert.match(mot.texte, /s’ouvre dans 39 jours/)
  assert.equal(motDeSemer({}), null)
})

test('[CA6] « Semer » en trois groupes, grille de trois colonnes dès 700 px de conteneur, bouton Semer', () => {
  const o = lire('components/OngletSemer.jsx')
  assert.match(o, /Fenêtre ouverte/)
  assert.match(o, /Fenêtre ouverte, mais rien à semer/)
  assert.match(o, /Bientôt/)
  assert.match(o, /@\[700px\]\/semer:grid-cols-3/)
  assert.match(o, /ouvrirGastonSur\(\{ sujet: sujetSemer\(t\), champ: phraseSemer\(t\) \}\)/)  // [US-358 / CA1]
  assert.match(o, /Fenêtre de semis ouverte · graines en stock · aucun lot de la culture en cours/)
  assert.match(o, /font-serif/)
  assert.doesNotMatch(o, /font-hand/)
})

// ── CA9 : le registre des Lots ─────────────────────────────────────────────────────────────────────

test('[CA9] le bilan : « 4 lots cette saison · 3 en cours dont 2 à régler · 1 terminé, 10 plants sortis »', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  const b = bilanRegistre(LOTS, alertes)
  assert.equal(b.tous, 4)
  assert.equal(b.enCours, 3)
  assert.equal(b.a_regler, 2)
  assert.equal(b.termine, 1)
  assert.equal(b.plantsSortis, 10)
  assert.equal(b.texte, '4 lots cette saison · 3 en cours dont 2 à régler · 1 terminé, 10 plants sortis vers le potager')
})

test('[CA9, Gherkin 3] « À régler 2 » : seuls les deux lots, rangés par mois de semis', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  assert.deepEqual(comptesRegistre(LOTS, alertes), { en_cours: 1, a_regler: 2, termine: 1, tous: 4 })
  const visibles = lotsDuRegistre(LOTS, alertes, { filtre: 'a_regler' })
  assert.deepEqual(visibles.map((l) => l.numero_lot), [64, 57])
  const rangees = rangeesParMoisDeSemis(visibles, AUJOURDHUI)
  assert.deepEqual(rangees.map((g) => [g.titre, g.lots.length]), [['Novembre', 1], ['Octobre', 1]])
  // Plus de colonne « Tous » : trois colonnes, chacune avec la couleur de sa pastille.
  assert.deepEqual(COLONNES_REGISTRE.map((f) => f.libelle), ['En cours', 'À régler', 'Terminés'])
  assert.ok(COLONNES_REGISTRE.every((c) => /^#[0-9A-F]{6}$/i.test(c.couleur)))
  assert.equal(colonneRegistreInitiale('tous'), 'en_cours')
  assert.equal(colonneRegistreInitiale('a_regler'), 'a_regler')
  assert.equal(statutPepiniere(FINI, alertes), 'termine')
})

test('[CA9] la matrice du registre : colonnes = état, rangées = mois de semis, chacune sa teinte', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  const m = matriceRegistre(LOTS, alertes, AUJOURDHUI)
  assert.deepEqual(m.colonnes.map((c) => [c.cle, c.total]), [['en_cours', 1], ['a_regler', 2], ['termine', 1]])
  assert.deepEqual(m.rangees.map((r) => [r.titre, r.total, r.sousTitre]), [
    ['Novembre', 2, 'semés ce mois-ci'], ['Octobre', 1, ''], ['Septembre et août', 1, ''],
  ])
  assert.equal(new Set(m.rangees.map((r) => r.couleur)).size, 3)
  const nov = m.rangees[0]
  assert.deepEqual(nov.cases.en_cours.map((l) => l.numero_lot), [59])
  assert.deepEqual(nov.cases.a_regler.map((l) => l.numero_lot), [64])
  assert.deepEqual(nov.cases.termine, [])     // « vide » à l'écran
  assert.equal(matriceRegistre(LOTS, alertes, AUJOURDHUI, { q: 'zzz' }).total, 0)
})

test('[CA9] « Plus tôt dans la saison » dit son étendue ; un lot sans date a sa rangée', () => {
  const tot = [lotBase({ lot_id: 'a', numero_lot: 1, date_semis: '2026-03-04' }), lotBase({ lot_id: 'b', numero_lot: 2, date_semis: '2026-07-18' }),
    lotBase({ lot_id: 'c', numero_lot: 3, date_semis: null })]
  const r = rangeesParMoisDeSemis(tot, AUJOURDHUI)
  assert.deepEqual(r.map((x) => [x.titre, x.sousTitre]), [['Plus tôt dans la saison', 'mars → juillet'], ['Sans date de semis', '']])
})

test('[CA4] la carte du registre est celle du Parcours : n°, quantité, frise des gestes datés', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  const c = carteLotDuRegistre(OIGNON, PARCOURS, alertes)
  assert.equal(c.numero, '#57')
  assert.ok(c.gestes.length >= 1 && c.gestes[0].titre === 'Semé')
  assert.equal(carteLot({ lot: OIGNON, etiquette: PARCOURS.etiquettes[0] }).gestes.length, c.gestes.length)
})

test('[CA9] la recherche du registre : n°, culture ou variété', () => {
  const alertes = new Map()
  assert.deepEqual(lotsDuRegistre(LOTS, alertes, { q: '#57' }).map((l) => l.numero_lot), [57])
  assert.deepEqual(lotsDuRegistre(LOTS, alertes, { q: 'reine' }).map((l) => l.numero_lot), [59])
})

test('[CA9] une ligne : n°, stade, culture · variété, emplacement · quantité · date, frise, alerte', () => {
  const alertes = alertesDesLots(LOTS, PARCOURS, AUJOURDHUI)
  const l = ligneRegistre(OIGNON, PARCOURS, alertes)
  assert.equal(l.numero, '#57')
  assert.equal(l.etape, 'levee')
  assert.equal(l.culture, 'Oignon blanc')
  assert.equal(l.variete, 'de Paris')
  assert.match(l.detail, /^Châssis froid · 30 graines · semé le 20 oct\.?$/)
  assert.equal(l.nbGestes, 1)
  assert.equal(l.alerte, 'Pas levé après 34 j')
  assert.equal(ligneRegistre(CHOU, PARCOURS, alertes).detail.startsWith('Sans emplacement'), true)
})

test('[CA9] tableau comme le Parcours (3 colonnes, « vide »), mobile en points ; pied « Registre sans geste… »', () => {
  const o = lire('components/OngletLots.jsx')
  assert.match(o, /<PagerAimante/)
  assert.match(o, /role="table"/)
  assert.match(o, /grid-cols-\[190px_repeat\(3,minmax\(0,1fr\)\)\]/)
  assert.match(o, /vide/)
  assert.match(o, /<CarteLot/)
  assert.doesNotMatch(o, /role="radiogroup"|FiltresSegmentes|'Tous'/)
  assert.match(o, /Registre sans geste : on agit depuis le Parcours ou par Noter\./)
  assert.doesNotMatch(o, /font-hand/)
})

// ── CA11 : la fiche du lot au format commun ─────────────────────────────────────────────────────────

test('[CA11] stade, emplacement et gestes datés d’un lot', () => {
  assert.equal(stadeDuLot(OIGNON, PARCOURS), 'levee')
  assert.equal(stadeDuLot(LAITUE, PARCOURS), 'godet')
  assert.equal(stadeDuLot(FINI, PARCOURS), 'terminee')
  assert.equal(emplacementDuLot(OIGNON, PARCOURS).texte, 'Châssis froid · pépinière froide')
  assert.equal(emplacementDuLot(CHOU, PARCOURS).texte, 'Sans emplacement · à ranger')
  assert.deepEqual(gestesDeLaFiche(OIGNON).map((g) => [g.titre, g.date]), [['Semé', '20 oct.']])
})

test('[CA11] la fiche : « Lot #57 · Oignon blanc », Noter et Voir au Parcours, Gestes datés, Carnet du lot, Toutes les actions', () => {
  const f = lire('components/FicheLotCommune.jsx')
  assert.match(f, /Lot \$\{lot\.numero_lot != null/)
  assert.match(f, /Noter/)
  assert.match(f, /Voir au Parcours/)
  assert.match(f, /Gestes datés/)
  assert.match(f, /Carnet du lot/)
  assert.match(f, /Toutes les actions du lot/)
  assert.match(f, /<NoteCarnet/)
  assert.doesNotMatch(f, /font-hand/)
})

test('[CA11] ordinateur : la fiche vit dans le panneau droit partagé (portail) ; mobile : une feuille ; les gestes d’US-216 restent joignables', () => {
  assert.match(VUE, /ouvrirPanneau\(\{ cle: 'fiche', titre: titreFiche, contenu: <HotePanneau \/> \}\)/)
  assert.match(VUE, /createPortal\(<div className="pt-12">\{contenuFiche\}<\/div>, hote\)/)
  assert.match(VUE, /disposition="basse"/)
  assert.match(VUE, /forme="modale"/)
  assert.match(VUE, /onToutesLesActions=\{\(\) => setToutes\(true\)\}/)
})

test('[CA12] les trois onglets suivent la date de la règle des temps (date_ref)', () => {
  assert.match(VUE, /api\.pepiniereLots\(dateRef, potagerId\)/)
  assert.match(VUE, /const aujourdhui = data\?\.date_ref_effective/)
})
