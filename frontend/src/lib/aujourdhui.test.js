// [US-328] « Aujourd'hui au potager » — `npm test`.
//
// Ce qui se vérifie ici : les listes du serveur mises en forme (A2-A4), listes vides (CA1),
// comptes repris tels quels (CA2), « À placer » lots + sans parcelle (CA3), la proposition
// de placement envoyée à Gaston (CA4, CA5, Gherkin), la météo absente sans erreur (CA6), les
// boutons du mobile (CA7), et à la lecture des sources : glisser-déposer au clavier (CA4).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  tachesDuPlan, ligneAConfirmer, ligneALiberer, carteAPlacer, meteoDuJour, dateDuJour, jourCourt,
  jourDeSemaine, propositionDePlacement, annonceCarteEnMain, boutonsMobile, quantiteEnLettres,
  LISTES, LISTE_A_CONFIRMER, LISTE_A_LIBERER, LISTE_A_PLACER, AIDE_AUJOURDHUI,
} from './aujourdhui.js'
import { ouvertureDuPanneau, ouvrirGastonPourPlacer } from './contexteCompagnon.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')

const FEVE = {
  parcelle_id: 1, parcelle: 'Planche haricots', rang: 3, culture: 'fève', variete: null,
  etape: 'levee', etape_libelle: 'Levé', etape_date: '2026-11-12',
}
const EPINARD = { ...FEVE, rang: null, culture: 'épinard', variete: 'Géant d’hiver' }
const TOMATE = { parcelle_id: 2, parcelle: 'Bac', rang: null, culture: 'tomate cerise', variete: null, fin_le: '2026-10-30' }
const LOT = {
  origine: 'lot', lot_id: 's42', numero_lot: 42, culture: 'fraisiers', variete: 'Mara des bois',
  quantite: 12, unite: 'plants', pepiniere: 'Châssis',
}
const COURGE = { origine: 'sans_parcelle', lot_id: null, numero_lot: null, culture: 'courge', variete: null, quantite: 3, unite: 'plants' }
const PLAN = { taches_du_jour: { a_confirmer: [FEVE, EPINARD], a_liberer: [TOMATE], a_placer: [LOT, COURGE] } }

test('[Gherkin] Ce qui m’attend aujourd’hui : 2 à confirmer, 1 à libérer', () => {
  const t = tachesDuPlan(PLAN)
  assert.deepEqual(t[LISTE_A_CONFIRMER].map((l) => l.nom), ['Fève', 'Épinard Géant d’hiver'])
  assert.deepEqual(t[LISTE_A_LIBERER].map((l) => l.nom), ['Tomate cerise'])
})

test('[CA1] A2 à A4 dans l’ordre, chaque liste vide le dit', () => {
  assert.deepEqual(LISTES.map((l) => l.cle), [LISTE_A_CONFIRMER, LISTE_A_LIBERER, LISTE_A_PLACER])
  assert.equal(LISTES[0].vide, 'Rien à confirmer')
  const vide = tachesDuPlan({})
  assert.deepEqual(Object.values(vide).map((l) => l.length), [0, 0, 0])
  assert.match(AIDE_AUJOURDHUI, /Glissez sur un rang libre du plan/)
})

test('[A2] une ligne à confirmer : emoji, nom, parcelle · rang, étape prévue, pastille', () => {
  const l = ligneAConfirmer(FEVE)
  assert.equal(l.lieu, 'Planche haricots · R3')
  assert.equal(l.detail, 'Prévu : Levé')
  assert.equal(l.pastille, 'À confirmer')
  assert.ok(l.emoji)
  assert.deepEqual(l.selection, { parcelleId: 1, parcelle: 'Planche haricots', culture: 'fève', variete: null, rang: 3, cle: 'fève||3' })
  assert.equal(ligneAConfirmer(EPINARD).lieu, 'Planche haricots')
})

test('[A3] une ligne à libérer porte sa date de fin', () => {
  assert.equal(ligneALiberer(TOMATE).detail, 'Terminée le 30 oct.')
  assert.match(ligneALiberer(TOMATE).nomAccessible, /rang à libérer/)
  assert.equal(ligneALiberer({ ...TOMATE, fin_le: null }).detail, 'Terminée')
})

test('[A4, CA3] À placer : lots prêts et cultures sans parcelle, avec origine', () => {
  const [lot, courge] = tachesDuPlan(PLAN)[LISTE_A_PLACER]
  assert.equal(lot.origine, 'Lot #42 · Châssis')
  assert.equal(lot.quantite, '12 plants')
  assert.equal(lot.variete, 'Mara des bois')
  assert.equal(courge.origine, 'Dite à Gaston, sans parcelle')
  assert.notEqual(lot.cle, courge.cle)
  assert.equal(carteAPlacer({ ...LOT, numero_lot: null, pepiniere: null }).origine, 'Lot')
})

test('[CA2] les comptes sont ceux du serveur, jamais recomptés', () => {
  const src = lire('./aujourdhui.js')
  assert.doesNotMatch(src, /etapes\.a_confirmer|a_liberer\s*\)/)
})

test('[Gherkin, CA4, CA5] la proposition de placement : phrase, rang en contexte, part du rang', () => {
  const forme = { id: 7, nom: 'Planche haricots' }
  const p = propositionDePlacement(LOT, forme, { numero: 2, part: 1, libre: true })
  assert.equal(p.phrase, 'Placer 12 fraisiers Mara des bois · Planche haricots, rang 2')
  assert.deepEqual(p.contexte, { parcelleId: 7, parcelle: 'Planche haricots', rang: 2 })
  assert.deepEqual(p.placement, { culture: 'fraisiers', variete: 'Mara des bois', quantite: 12, unite: 'plants', numero_lot: 42, part: 1 })
  assert.equal(propositionDePlacement(COURGE, forme, { numero: 1, part: 0.4 }).placement.part, 0.4)
  assert.equal(propositionDePlacement(COURGE, forme, { numero: 1, part: 0.4 }).placement.numero_lot, null)
})

test('[CA4] le dépôt n’écrit rien : il ouvre Gaston avec la carte', () => {
  const recu = []
  const cible = { dispatchEvent: (e) => recu.push(e) }
  ouvrirGastonPourPlacer({ phrase: 'Placer 3 courge · Bac, rang 1', contexte: { parcelleId: 2, parcelle: 'Bac', rang: 1 }, placement: { culture: 'courge' } }, cible)
  const ouverture = ouvertureDuPanneau(recu[0].detail)
  assert.equal(ouverture.barre, true)
  assert.equal(ouverture.contexte.rang, 1)
  assert.equal(ouverture.placement.phrase, 'Placer 3 courge · Bac, rang 1')
  assert.deepEqual(ouverture.placement.carte, { culture: 'courge' })
  assert.ok(ouverture.placement.jeton)
  // Sans placement, la forme d'US-323 est inchangée.
  assert.equal('placement' in ouvertureDuPanneau({ contexte: null }), false)
})

test('[CA4] le glisser-déposer se fait au clavier et s’annonce', () => {
  assert.match(annonceCarteEnMain(carteAPlacer(LOT)), /Fraisiers, 12 plants en main : choisissez un rang libre/)
  const panneau = lire('../components/AujourdhuiPotager.jsx')
  assert.match(panneau, /draggable="true"/)
  assert.match(panneau, /aria-pressed=\{enMain/)
  const dessin = lire('../components/PlanDessin.jsx')
  assert.match(dessin, /onDrop=\{surDeposer\}/)
  assert.match(dessin, /déposer ici la carte en main/)
  const vue = lire('../views/PlanDessus.jsx')
  assert.match(vue, /e\.key === 'Escape'/)
  assert.match(vue, /ouvrirGastonPourPlacer\(propositionDePlacement/)
  // Le panneau envoie la proposition une fois la conversation chargée, une seule fois par jeton.
  const gaston = lire('../components/PanneauCompagnon.jsx')
  assert.match(gaston, /placementEnvoye\.current === placement\.jeton/)
})

test('[CA6] la météo : température et gel ; absente, la ligne disparaît', () => {
  const m = meteoDuJour({ temp_actuelle: 7.4, previsions: [{ date: '2026-11-13', temp_min: 2 }, { date: '2026-11-14', temp_min: -1 }] })
  assert.deepEqual({ t: m.temperature, a: m.alerte }, { t: '7°', a: 'gel possible samedi' })
  assert.equal(meteoDuJour(null), null)
  assert.equal(meteoDuJour({ localisation_manquante: true }), null)
  assert.equal(meteoDuJour({ previsions: [] }), null)
  assert.equal(meteoDuJour({ temp_max: 12, previsions: [{ date: '2026-11-14', temp_min: 3 }] }).alerte, null)
})

test('[A1] dates en lettres', () => {
  assert.equal(dateDuJour('2026-11-12'), 'jeudi 12 novembre')
  assert.equal(jourDeSemaine('2026-11-14'), 'samedi')
  assert.equal(jourCourt('2026-10-30'), '30 oct.')
  assert.equal(jourCourt(null), '')
  assert.equal(quantiteEnLettres(1.5, 'm²'), '1,5 m²')
  assert.equal(quantiteEnLettres(null), '')
})

test('[CA7] mobile : « N à confirmer » et « N à libérer » ouvrent la première culture', () => {
  const b = boutonsMobile(tachesDuPlan(PLAN))
  assert.deepEqual(b.map((x) => x.texte), ['2 à confirmer', '1 à libérer'])
  assert.equal(b[0].premiere.nom, 'Fève')
  assert.deepEqual(boutonsMobile(tachesDuPlan({})), [])
  assert.ok(lire('../components/PlanMobile.jsx').includes('min-h-[44px] rounded-full'))
})
