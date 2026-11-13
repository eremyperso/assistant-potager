// [US-329] Le plan sur mobile, dans l'ordre du chemin — `npm test`.
//
// Ce qui se vérifie ici : la bascule par largeur de CONTENEUR (CA1), le mini-plan qui réutilise
// le dessin d'US-327 (CA2), l'échelle du mini-plan, l'ordre du chemin (P6), une ligne par
// culture et par rang, rangs libres (M5), parcelle non placée listée (CA4), lots de pépinière
// sans « Noter » (M6, Gherkin), défilement avec focus et annonce (CA5), relecture après Gaston (CA6).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  estCheminMobile, echelleMiniPlan, parcellesDuChemin, lignesDeParcelle, lotsDuChemin, etatDeLigne,
  idCarteChemin, LARGEUR_CHEMIN_PX, HAUTEUR_MINI_PLAN_MAX_PX, TEXTE_LEGENDE_MOBILE, TEXTE_LOTS_PEPINIERE,
  hauteurMaxMiniPlan, HAUTEUR_MINI_PLAN_MIN_PX, PART_HAUTEUR_ECRAN_MINI_PLAN,
  CRANS_ZOOM_AGRANDI, CRAN_ZOOM_INITIAL, cranZoomSuivant, echelleAgrandie,
} from './planMobile.js'
import { ECHELLE_MIN, ECHELLE_MAX } from './planDessus.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')
const geo = (x, L = 12, l = 5) => ({
  forme: 'planche', placee: x != null, x_m: x, y_m: x == null ? null : 1, longueur_m: L, largeur_m: l,
  rotation_deg: 0, sens_rangs: 'longueur',
})

const CENTRALE = {
  id: 2, nom: 'Planche centrale', ordre: 2, est_pepiniere: false, nb_rangs: 3, geometrie: geo(9),
  cultures: [
    { culture: 'chou de Bruxelles', variete: 'Groninger', etapes: {
      etape: 'en_recolte', etape_libelle: 'En récolte', etape_statut: 'validee', etape_date: '2026-10-20', a_confirmer: false } },
    { culture: 'fève', variete: null, etapes: {
      etape: 'levee', etape_libelle: 'Levé', etape_statut: 'prevue', etape_date: '2026-11-12', a_confirmer: true } },
  ],
  disposition: { rangs_declares: 3, rangs: [
    { numero: 1, libre: false, culture: 'chou de Bruxelles', variete: 'Groninger', part: 1 },
    { numero: 2, libre: true },
    { numero: 3, libre: false, culture: 'fève', variete: null, part: 1 },
  ] },
}
const CHASSIS = {
  id: 1, nom: 'Châssis', ordre: 1, est_pepiniere: true, type_pepiniere: 'froide', geometrie: geo(1, 2, 1),
  disposition: { lots_en_cours: [
    { lot_id: 's1', numero_lot: 12, culture: 'laitue', variete: 'Batavia', quantite: 24, unite: 'godets', stade: 'godet' },
    { lot_id: 's2', numero_lot: 13, culture: 'chou', variete: null, quantite: 40, unite: 'graines', stade: 'semis' },
    { lot_id: 's3', numero_lot: 14, culture: 'oignon', variete: null, quantite: 10, unite: 'godets', stade: 'godet' },
  ] },
}
const CARRE = { id: 3, nom: 'Carré', ordre: 3, est_pepiniere: false, nb_rangs: null, geometrie: geo(null),
  cultures: [{ culture: 'ail', variete: null, etapes: null }], disposition: { rangs: [] } }
const PLAN = { parcelles: [CARRE, CENTRALE, CHASSIS] }

test('[CA1] sous 720 px de conteneur, le chemin mobile', () => {
  assert.equal(LARGEUR_CHEMIN_PX, 720)
  assert.equal(estCheminMobile(375), true)
  assert.equal(estCheminMobile(719), true)
  assert.equal(estCheminMobile(720), false)
  assert.equal(estCheminMobile(0), false)
  // Container query : la vue mesure son conteneur, aucune media query ne décide de la bascule.
  const vue = lire('../views/PlanDessus.jsx')
  assert.match(vue, /estCheminMobile\(largeurRacine/)
  // (chaînes littérales : Tailwind lit aussi ce fichier, un motif échappé y deviendrait une classe)
  assert.ok(vue.includes('className="' + '@' + 'container'))
})

test('[CA2] le mini-plan réutilise le dessin d’US-327, en variante réduite', () => {
  const mobile = lire('../components/PlanMobile.jsx')
  assert.ok(mobile.includes('<ParcellePlan key={forme.id} forme={forme} u={u} mini'))
  assert.doesNotMatch(mobile, /<svg|<rect/)
  assert.match(lire('../components/PlanDessin.jsx'), /if \(mini\) \{/)
})

test('[M2] l’échelle du mini-plan : la largeur, sous la hauteur maximale', () => {
  assert.equal(echelleMiniPlan({ longueur: 20, largeur: 10 }, 340), 17)
  assert.equal(echelleMiniPlan({ longueur: 10, largeur: 10 }, 340), 34)
  assert.equal(echelleMiniPlan({ longueur: 10, largeur: 45 }, 340), HAUTEUR_MINI_PLAN_MAX_PX / 45)
  assert.equal(echelleMiniPlan(null, 340), 0)
})

test('[M2] un plan presque carré occupe la largeur de l’écran, plus le plafond de 200 px', () => {
  // 21 × 23 m sur 343 px : ~16,3 px/m (et non ~8,7 avec l'ancien plafond), soit ~343 × 375 px
  const u = echelleMiniPlan({ longueur: 21, largeur: 23 }, 343, hauteurMaxMiniPlan(812))
  assert.ok(Math.abs(u - 343 / 21) < 1e-9)
  assert.ok(u * 23 < hauteurMaxMiniPlan(812))
})

test('[M2] un terrain haut et étroit est borné par la hauteur maximale', () => {
  const hMax = hauteurMaxMiniPlan(812)
  const u = echelleMiniPlan({ longueur: 10, largeur: 40 }, 343, hMax)
  assert.equal(u, hMax / 40)
  assert.ok(u * 40 <= hMax)
})

test('[M2] la hauteur maximale suit l’écran, avec un plancher et un repli', () => {
  assert.equal(hauteurMaxMiniPlan(812), Math.round(812 * PART_HAUTEUR_ECRAN_MINI_PLAN))
  assert.equal(hauteurMaxMiniPlan(300), HAUTEUR_MINI_PLAN_MIN_PX)
  assert.equal(hauteurMaxMiniPlan(0), HAUTEUR_MINI_PLAN_MAX_PX)
  assert.equal(hauteurMaxMiniPlan(undefined), HAUTEUR_MINI_PLAN_MAX_PX)
})

test('[M2] le cadre du mini-plan est centré et réglé sur la hauteur d’écran', () => {
  const mobile = lire('../components/PlanMobile.jsx')
  assert.ok(mobile.includes('className="relative mx-auto"'))
  assert.ok(mobile.includes('hauteurMaxMiniPlan('))
})

test('[Agrandir] les crans de zoom : bornes du plan complet, jamais hors des crans', () => {
  assert.deepEqual([...CRANS_ZOOM_AGRANDI], [ECHELLE_MIN, 28, ECHELLE_MAX])
  assert.equal(echelleAgrandie(CRAN_ZOOM_INITIAL), ECHELLE_MIN)
  assert.equal(cranZoomSuivant(0, 1), 1)
  assert.equal(cranZoomSuivant(2, 1), 2)
  assert.equal(cranZoomSuivant(0, -1), 0)
  assert.equal(cranZoomSuivant(undefined, 1), 1)
  assert.equal(echelleAgrandie(99), ECHELLE_MAX)
  assert.equal(echelleAgrandie(-4), ECHELLE_MIN)
})

test('[Agrandir] le mini-plan ouvre le plan agrandi, qui renvoie la parcelle choisie à la liste', () => {
  const mobile = lire('../components/PlanMobile.jsx')
  assert.ok(mobile.includes('aria-label="Agrandir le plan"'))
  assert.ok(mobile.includes('<PlanAgrandi'))
  // fermer d'abord, défiler ensuite : la fenêtre rend le focus au bouton en se fermant
  assert.ok(mobile.includes('setAgrandi(false)') && mobile.includes('setTimeout(() => allerA(forme), 0)'))
  const agrandi = lire('../components/PlanAgrandi.jsx')
  assert.ok(agrandi.includes('disposition="plein_mobile"'))
  assert.ok(agrandi.includes('onParcelle={choisir} onSegment={choisir}'))
  assert.ok(agrandi.includes("touchAction: 'pan-x pan-y'"))
  assert.doesNotMatch(agrandi, /<svg|<rect/)
})

test('[P6, CA4] l’ordre du chemin, parcelle non placée comprise', () => {
  const chemin = parcellesDuChemin(PLAN)
  assert.deepEqual(chemin.map((p) => p.nom), ['Châssis', 'Planche centrale', 'Carré'])
  assert.equal(chemin[2].placee, false)
  assert.equal(chemin[1].sousTitre, '3 rangs')
  assert.equal(chemin[2].sousTitre, 'Rangs non déclarés')
})

test('[M5, Gherkin] une ligne par rang : « R1 … R3 », libres en « Libre »', () => {
  const lignes = lignesDeParcelle(CENTRALE)
  assert.deepEqual(lignes.map((l) => l.rang), ['R1', 'R2', 'R3'])
  assert.equal(lignes[0].detail, 'En récolte depuis le 20 oct. · Groninger')
  assert.equal(lignes[1].libre, true)
  assert.equal(lignes[1].nom, 'Libre')
  assert.equal(lignes[2].aConfirmer, true)
  assert.deepEqual(lignes[2].selection, { parcelleId: 2, parcelle: 'Planche centrale', culture: 'fève', variete: null, rang: 3, cle: 'fève||3' })
})

test('[M5] une parcelle sans rangs déclarés garde ses cultures', () => {
  const [ail] = lignesDeParcelle(CARRE)
  assert.equal(ail.rang, '—')
  assert.equal(ail.nom, 'Ail')
})

test('[M5] états en lettres', () => {
  assert.equal(etatDeLigne({ etape: 'levee', etape_libelle: 'Levé', etape_statut: 'prevue', etape_date: '2026-11-14' }), 'Levé prévu le 14 nov.')
  assert.equal(etatDeLigne({ etape: 'plantee', etape_libelle: 'Planté' }), 'Planté')
  assert.equal(etatDeLigne(null), '')
})

test('[CA3] lignes de 54 px, sans défilement horizontal', () => {
  const mobile = lire('../components/PlanMobile.jsx')
  assert.ok(mobile.split('min-h-[54px]').length - 1 >= 3)
  assert.match(mobile, /truncate/)
  assert.doesNotMatch(mobile, /overflow-x-auto|whitespace-nowrap/)
})

test('[M6, Gherkin] une pépinière froide : ses trois lots et « Ma pépinière », sans Noter', () => {
  const [chassis] = parcellesDuChemin(PLAN)
  assert.equal(chassis.sousTitre, 'pépinière froide')
  assert.equal(chassis.lots.length, 3)
  assert.deepEqual(chassis.lignes, [])
  const [laitue, chou] = lotsDuChemin(CHASSIS)
  assert.equal(laitue.detail, '24 godets · en godet')
  assert.equal(chou.detail, '40 graines · semé')
  assert.deepEqual(laitue.intention, { onglet: 'parcours', lot: '12' })
  const mobile = lire('../components/PlanMobile.jsx')
  assert.match(mobile, /Ma pépinière/)
  assert.doesNotMatch(mobile, /Noter/)
  assert.equal(TEXTE_LOTS_PEPINIERE, 'Les lots se suivent et se notent dans Ma pépinière')
})

test('[CA5] toucher le mini-plan défile, met le focus et annonce', () => {
  const mobile = lire('../components/PlanMobile.jsx')
  assert.match(mobile, /scrollIntoView/)
  assert.match(mobile, /el\.focus\?\.\(/)
  assert.match(mobile, /annoncer\?\.\(/)
  assert.match(mobile, /tabIndex=\{-1\}/)
  assert.equal(idCarteChemin(4), 'chemin-parcelle-4')
  assert.match(TEXTE_LEGENDE_MOBILE, /modification sur ordinateur/)
})

test('[CA6] au retour de Gaston, l’écran se relit une fois', () => {
  // `refresh` (App.handleRefresh, appelé par onEnregistre du panneau) relance l'unique lecture.
  assert.ok(lire('../views/PlanDessus.jsx').includes('useEffect(() => { load() }, [load, refresh])'))
})
