// [US-327] Plan vu du dessus — `npm test`.
//
// Ce qui se vérifie ici (CA2) : position et taille à l'échelle (P1), segments d'un rang
// au prorata de leur part, rang libre et reste libre (P2), libellé selon la place (P3),
// variantes d'étape (P4), forme de la parcelle (P5), lots de pépinière (P6), parcelle
// inactive (P7), filtres et compteurs du serveur (P8, CA4), rose et échelle (P9), plan
// par zones (P10), en-tête (P11), nom accessible et ordre de tabulation (CA3).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  filtresDuPlan, estEstompe, empriseDuPlan, echelle, roseDesVents, enteteDuPlan, jourEnLettres,
  formeDeParcelle, dimensionsDeParcelle, estPlacee, rangsDeParcelle, lotsDePepiniere, formeDuPlan,
  formesDuPlan, parcellesAPlacer, tuilesParZones, modeDuPlan, modeLibelle, tailleSegment, lotAvecNom,
  selectionDeSegment, nomCulture,
  FILTRE_TOUT, FILTRE_A_CONFIRMER, FILTRE_EN_RECOLTE, FILTRE_RANGS_LIBRES,
  ECHELLE_MIN, ECHELLE_MAX, MODE_PLAN, MODE_ZONES, MODE_VIDE, DIR_H, DIR_V,
  LIBELLE_VERTICAL, LIBELLE_COMPLET, LIBELLE_EMOJI_PICTO, LIBELLE_PICTO, LIBELLE_RIEN,
  MESSAGE_RANG_LIBRE,
} from './planDessus.js'

const etapes = (etape, { prevue = false, aConfirmer = false } = {}) => ({
  etape, etape_statut: prevue ? 'prevue' : 'validee', a_confirmer: aConfirmer, a_liberer: false,
})
const geo = (x, y, L, l, extra = {}) => ({
  forme: 'planche', placee: x != null, a_placer: x == null, x_m: x, y_m: y, longueur_m: L, largeur_m: l,
  rotation_deg: 0, sens_rangs: 'longueur', ...extra,
})

// Gherkin « Lire le potager » : la planche centrale, 12 × 5 m, à 9 m du bord, rangs dans
// la longueur ; son rang 3 porte du chou de Bruxelles (0,6) et du chou kale (0,4).
const CENTRALE = {
  id: 2, nom: 'Planche centrale', ordre: 2, est_pepiniere: false,
  geometrie: geo(9, 1, 12, 5),
  cultures: [
    { culture: 'chou de Bruxelles', variete: 'Groninger', etapes: etapes('en_recolte') },
    { culture: 'chou kale', variete: null, etapes: etapes('en_recolte') },
    { culture: 'fève', variete: 'Aguadulce', etapes: etapes('levee', { prevue: true, aConfirmer: true }) },
    { culture: 'ail', variete: null, etapes: etapes('plantee') },
  ],
  disposition: {
    rangs_declares: 6,
    rangs: [
      { numero: 3, libre: false, culture: 'chou de Bruxelles', variete: 'Groninger', part: 0.6 },
      { numero: 3, libre: false, culture: 'chou kale', variete: null, part: 0.4 },
      { numero: 4, libre: false, culture: 'ail', variete: null, part: 0.5 },
      { numero: 6, libre: false, culture: 'fève', variete: 'Aguadulce', part: 1 },
      { numero: 1, libre: true }, { numero: 2, libre: true }, { numero: 5, libre: true },
    ],
  },
}
const SERRE = {
  id: 1, nom: 'Serre', ordre: 1, est_pepiniere: true, type_pepiniere: 'chaude',
  geometrie: geo(1, 1, 6, 4, { forme: 'serre' }),
  disposition: { lots_en_cours: [
    { lot_id: 'semis-18', numero_lot: 18, culture: 'chou de Bruxelles', variete: null },
    { lot_id: 'semis-3', numero_lot: null, culture: 'tomate', variete: 'Cerise' },
  ] },
}
const NON_PLACEE = { id: 3, nom: 'Carré', ordre: 3, superficie_m2: 4, geometrie: geo(null, null, null, null), disposition: { rangs: [] }, cultures: [] }
const INACTIVE = { id: 9, nom: 'Haricots', ordre: 0, actif: false, geometrie: geo(19, 11, 3.5, 3) }
const PLAN = {
  date_ref_effective: '2026-11-12',
  parcelles: [CENTRALE, SERRE, NON_PLACEE],
  parcelles_inactives: [INACTIVE],
  potager_geometrie: { emprise_longueur_m: 25, emprise_largeur_m: 15, orientation_nord: 'n', angle_deg: 0 },
  filtres_plan: { a_confirmer: 3, en_recolte: 2, rangs_libres: 1 },
}

// ── P1 : position, taille, échelle ─────────────────────────────────────────────

test('[US-327 / P1] Gherkin — la planche est posée à sa place, à l’échelle', () => {
  const f = formeDuPlan(CENTRALE)
  assert.deepEqual([f.x, f.y, f.w, f.h, f.rotation, f.dir], [9, 1, 12, 5, 0, DIR_H])
  assert.equal(f.estimee, false)
})

test('[US-327 / P1] L’emprise posée fait foi ; sinon celle des parcelles, avec marge', () => {
  assert.deepEqual(empriseDuPlan(PLAN), { longueur: 25, largeur: 15, posee: true })
  const sans = { ...PLAN, potager_geometrie: {} }
  const e = empriseDuPlan(sans)
  assert.equal(e.posee, false)
  // La parcelle la plus à droite finit à 22,5 m (19 + 3,5), la plus basse à 14 m : + 1 m de marge.
  assert.deepEqual([e.longueur, e.largeur], [24, 15])
})

test('[US-327 / P1] L’emprise déduite tient compte de la rotation', () => {
  const tournee = { ...PLAN, potager_geometrie: {}, parcelles_inactives: [],
    parcelles: [{ ...CENTRALE, geometrie: geo(0, 0, 10, 2, { rotation_deg: 90 }) }] }
  const e = empriseDuPlan(tournee)
  // centre (5 ; 1), tournée : 2 de large, 10 de haut → x2 = 6, y2 = 6 ; + 1 m
  assert.deepEqual([e.longueur, e.largeur], [7, 7])
})

test('[US-327 / CA5] L’échelle remplit la largeur, bornée ; sous le plancher, le plan défile', () => {
  assert.equal(echelle({ longueur: 25 }, 750), 30)
  assert.equal(echelle({ longueur: 25 }, 300), ECHELLE_MIN)
  assert.equal(echelle({ longueur: 25 }, 5000), ECHELLE_MAX)
  assert.equal(echelle(null, 800), ECHELLE_MIN)
})

test('[US-327 / P1] Dimensions manquantes : déduites de la superficie, signalées estimées', () => {
  assert.deepEqual(dimensionsDeParcelle({ geometrie: { longueur_m: 4 }, superficie_m2: 6 }), { w: 4, h: 1.5, estimee: true })
  assert.deepEqual(dimensionsDeParcelle({ geometrie: {}, superficie_m2: 9 }), { w: 3, h: 3, estimee: true })
  assert.deepEqual(dimensionsDeParcelle({ geometrie: {}, longueur_m: 5, largeur_m: 2 }), { w: 5, h: 2, estimee: false })
  assert.deepEqual(dimensionsDeParcelle({ geometrie: {} }), { w: 1, h: 1, estimee: true })
})

// ── P2 : rangs et segments ────────────────────────────────────────────────────

test('[US-327 / P2] Gherkin — le rang 3 porte deux segments de 60 % et 40 %', () => {
  const rangs = rangsDeParcelle(CENTRALE)
  assert.equal(rangs.length, 6)
  const r3 = rangs[2]
  assert.deepEqual(r3.segments.map((s) => [s.culture, s.part]), [['chou de Bruxelles', 0.6], ['chou kale', 0.4]])
  assert.ok(r3.segments.every((s) => s.etape === 'en_recolte'))
})

test('[US-327 / P2] Un rang libre est un seul segment libre ; une part partielle laisse un reste libre', () => {
  const rangs = rangsDeParcelle(CENTRALE)
  assert.deepEqual(rangs[0].segments.map((s) => [s.libre, s.part]), [[true, 1]])
  const r4 = rangs[3].segments
  assert.deepEqual(r4.map((s) => [s.libre, s.part]), [[false, 0.5], [true, 0.5]])
})

test('[US-327 / P2] Une part inconnue se partage le reste à égalité', () => {
  const p = { ...CENTRALE, disposition: { rangs_declares: 1, rangs: [
    { numero: 1, libre: false, culture: 'a', part: null }, { numero: 1, libre: false, culture: 'b', part: null },
  ] }, cultures: [] }
  assert.deepEqual(rangsDeParcelle(p)[0].segments.map((s) => s.part), [0.5, 0.5])
})

test('[US-327 / P2] Un rang occupé au-delà du nombre déclaré est dessiné quand même (R7)', () => {
  const p = { ...CENTRALE, disposition: { rangs_declares: 1, rangs: [
    { numero: 1, libre: false, culture: 'ail', part: 1 }, { numero: 2, libre: false, culture: 'ail', part: 1 },
  ] } }
  assert.equal(rangsDeParcelle(p).length, 2)
  assert.deepEqual(rangsDeParcelle({ ...CENTRALE, disposition: {} }), [])
})

test('[US-327 / P2] Rangs en travers : bandes verticales', () => {
  assert.equal(formeDuPlan({ ...CENTRALE, geometrie: geo(0, 0, 5, 1.5, { sens_rangs: 'travers' }) }).dir, DIR_V)
})

// ── P3, P4 : libellé et état d'un segment ─────────────────────────────────────

test('[US-327 / P3] Le libellé suit la place : complet, emoji + picto, picto, rien, vertical', () => {
  assert.equal(modeLibelle(120, 20, DIR_H), LIBELLE_COMPLET)
  assert.equal(modeLibelle(60, 20, DIR_H), LIBELLE_EMOJI_PICTO)
  assert.equal(modeLibelle(20, 14, DIR_H), LIBELLE_PICTO)
  assert.equal(modeLibelle(10, 10, DIR_H), LIBELLE_RIEN)
  assert.equal(modeLibelle(20, 120, DIR_V), LIBELLE_VERTICAL)
  assert.equal(modeLibelle(20, 60, DIR_V), LIBELLE_PICTO)
})

test('[US-327 / P3] La taille d’un segment : sa part sur la longueur, une hauteur de rang', () => {
  const f = formeDuPlan(CENTRALE)
  const s = f.rangs[2].segments[0]
  const t = tailleSegment(f, s, 40)
  assert.equal(Math.round(t.largeur), Math.round(0.6 * (12 * 40 - 10)))
  assert.equal(Math.round(t.hauteur), Math.round((5 * 40 - 10 - 5 * 2) / 6))
  const v = tailleSegment({ ...f, dir: DIR_V }, s, 40)
  assert.equal(Math.round(v.hauteur), Math.round(0.6 * (5 * 40 - 10)))
})

test('[US-327 / P4] Une étape prévue à confirmer : variante et drapeau', () => {
  const feve = rangsDeParcelle(CENTRALE)[5].segments[0]
  assert.equal(feve.variante, 'a_confirmer')
  assert.equal(feve.aConfirmer, true)
  assert.equal(feve.emoji.length > 0, true)
})

test('[US-327 / CA3] Le nom accessible dit tout, dans l’ordre de la maquette', () => {
  const feve = rangsDeParcelle(CENTRALE)[5].segments[0]
  assert.equal(feve.nomAccessible, 'Fève Aguadulce, Levé, prévu, à confirmer, Planche centrale rang 6')
  assert.equal(rangsDeParcelle(CENTRALE)[0].segments[0].nomAccessible, 'Planche centrale, rang 1 : libre')
})

test('[US-327 / CA3] Ordre de tabulation : parcelle par parcelle (ordre du chemin), rang par rang', () => {
  const formes = formesDuPlan(PLAN)
  assert.deepEqual(formes.map((f) => f.nom), ['Haricots', 'Serre', 'Planche centrale'])
  assert.deepEqual(formeDuPlan(CENTRALE).rangs.map((r) => r.numero), [1, 2, 3, 4, 5, 6])
})

test('[US-327] Une culture sans étape reste dessinée, sans état inventé', () => {
  const p = { ...CENTRALE, cultures: [] }
  const s = rangsDeParcelle(p)[2].segments[0]
  assert.equal(s.etape, null)
  assert.match(s.nomAccessible, /étape inconnue/)
})

// ── P5, P6, P7 ────────────────────────────────────────────────────────────────

test('[US-327 / P5] La forme choisit le fond : posée, sinon pépinière, sinon planche', () => {
  assert.equal(formeDeParcelle({ geometrie: { forme: 'butte' } }), 'butte')
  assert.equal(formeDeParcelle({ geometrie: { forme: 'inconnue' }, est_pepiniere: true }), 'pepiniere')
  assert.equal(formeDeParcelle({}), 'planche')
})

test('[US-327 / P6] Une pépinière affiche ses lots, sans rangs ; le lot ouvre sa fiche', () => {
  const f = formeDuPlan(SERRE)
  assert.equal(f.rangs.length, 0)
  assert.equal(f.lots.length, 2)
  assert.deepEqual(f.lots[0].intention, { onglet: 'parcours', lot: '18' })
  assert.match(f.lots[0].nomAccessible, /Lot n° 18, Chou de Bruxelles, pépinière chaude : ouvrir dans Ma pépinière/)
  assert.equal(f.lots[1].intention.lot, 'semis-3')
  assert.deepEqual(lotsDePepiniere({ disposition: {} }), [])
  assert.equal(lotAvecNom({ w: 8 }, 40), true)   // (320 − 20) / 3 = 100 px > 90
  assert.equal(lotAvecNom({ w: 6 }, 18), false)
})

test('[US-327 / P7] Une parcelle inactive reste sur le plan, sans rang', () => {
  const f = formesDuPlan(PLAN).find((x) => x.nom === 'Haricots')
  assert.equal(f.actif, false)
  assert.deepEqual(f.rangs, [])
})

// ── P8 : filtres ──────────────────────────────────────────────────────────────

test('[US-327 / P8, CA4] Gherkin — « À confirmer · 3 » : le compteur du serveur', () => {
  const f = filtresDuPlan(PLAN)
  assert.deepEqual(f.map((x) => x.texte), ['Tout', 'À confirmer · 3', 'En récolte', 'Rangs libres'])
  assert.equal(f[2].nomAccessible, 'En récolte : 2 cultures en récolte')
  assert.equal(f[3].nomAccessible, 'Rangs libres : 1 rang libre')
  assert.equal(filtresDuPlan({})[1].texte, 'À confirmer · 0')
})

test('[US-327 / P8] Gherkin — hors filtre, un segment s’estompe ; rien ne disparaît', () => {
  const segs = formeDuPlan(CENTRALE).rangs.flatMap((r) => r.segments)
  const visibles = (filtre) => segs.filter((s) => !estEstompe(filtre, s)).map((s) => s.culture || 'libre')
  assert.equal(visibles(FILTRE_TOUT).length, segs.length)
  assert.deepEqual(visibles(FILTRE_A_CONFIRMER), ['fève'])
  assert.deepEqual(visibles(FILTRE_EN_RECOLTE), ['chou de Bruxelles', 'chou kale'])
  assert.ok(visibles(FILTRE_RANGS_LIBRES).every((x) => x === 'libre'))
  assert.equal(estEstompe(FILTRE_A_CONFIRMER, null), false)
})

// ── P9, P11 : rose, échelle, en-tête ──────────────────────────────────────────

test('[US-327 / P9] La rose suit le nord du potager ; sans nord posé, aucune rose', () => {
  assert.deepEqual(roseDesVents(PLAN), { angle: 0, nomAccessible: 'Rose des vents : nord en haut du plan' })
  assert.equal(roseDesVents({ potager_geometrie: { orientation_nord: 'NE' } }).angle, 45)
  assert.equal(roseDesVents({ potager_geometrie: { orientation_nord: 'o' } }).nomAccessible, 'Rose des vents : nord à gauche du plan')
  assert.equal(roseDesVents({ potager_geometrie: {} }), null)
})

test('[US-327 / P11] En-tête : « Au 12 novembre », fond, emprise', () => {
  const e = enteteDuPlan(PLAN, empriseDuPlan(PLAN))
  assert.deepEqual(e, { titre: 'Au 12 novembre', fond: 'Fond masqué · grille', dimension: '25 × 15 m' })
  assert.match(enteteDuPlan(PLAN, { longueur: 22.5, largeur: 9, posee: false }).dimension, /22,5 × 9 m \(déduite des parcelles\)/)
  assert.equal(jourEnLettres('2026-01-03'), '3 janvier')
  assert.equal(jourEnLettres(null), '')
})

// ── P10 : à placer, zones, vide ──────────────────────────────────────────────

test('[US-327 / P10] Une parcelle non placée n’est pas dessinée : elle est listée « À placer »', () => {
  assert.equal(estPlacee(NON_PLACEE), false)
  assert.ok(!formesDuPlan(PLAN).some((f) => f.id === 3))
  assert.deepEqual(parcellesAPlacer(PLAN), [{ id: 3, nom: 'Carré' }])
})

test('[US-327 / P10] Gherkin — aucune parcelle placée : les tuiles, dans l’ordre du chemin', () => {
  const sansPlace = (p) => ({ ...p, geometrie: { ...p.geometrie, placee: false } })
  const plan = { ...PLAN, parcelles: [CENTRALE, SERRE, NON_PLACEE].map(sansPlace), parcelles_inactives: [] }
  assert.equal(modeDuPlan(plan), MODE_ZONES)
  const tuiles = tuilesParZones(plan)
  assert.deepEqual(tuiles.map((t) => t.nom), ['Serre', 'Planche centrale', 'Carré'])
  assert.ok(tuiles.every((t) => t.largeurPx >= 140 && t.largeurPx <= 300))
  assert.equal(tuiles[1].hauteurPx, 150)   // 60 m² > 40
})

test('[US-327 / CA7] Aucun potager dessinable : mode vide ; sinon le plan', () => {
  assert.equal(modeDuPlan({ parcelles: [], parcelles_inactives: [] }), MODE_VIDE)
  assert.equal(modeDuPlan(null), MODE_VIDE)
  assert.equal(modeDuPlan(PLAN), MODE_PLAN)
})

// ── Interactions ──────────────────────────────────────────────────────────────

test('[US-327] Toucher un segment : la sélection que reçoit le suivi (US-322) ; un rang libre : rien', () => {
  const f = formeDuPlan(CENTRALE)
  const s = f.rangs[2].segments[0]
  assert.deepEqual(selectionDeSegment(f, s), {
    parcelleId: 2, parcelle: 'Planche centrale', culture: 'chou de Bruxelles', variete: 'Groninger', rang: 3, cle: s.cle,
  })
  assert.equal(selectionDeSegment(f, f.rangs[0].segments[0]), null)
  assert.match(MESSAGE_RANG_LIBRE, /dites-le à Gaston/)
  assert.equal(nomCulture('chou kale', null), 'Chou kale')
})

// ── CA1, CA2, CA6 : une lecture, aucun calcul dans la vue, l'ancienne Vue plan sortie ──

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')

test('[US-327 / CA1] La vue ne lit que GET /plan ; le suivi a sa propre lecture', () => {
  const vue = lire('../views/PlanDessus.jsx')
  const appels = [...vue.matchAll(/api\.(\w+)\(/g)].map((m) => m[1])
  // [US-328 / CA6] + la météo des prévisions existantes, pour l'en-tête « Aujourd'hui au potager ».
  assert.deepEqual([...new Set(appels)].sort(), ['meteo', 'plan'])
})

test('[US-327 / CA2] Aucune règle d’étape ni compteur dans la vue ou le dessin : tout vient de la lib', () => {
  for (const f of ['../views/PlanDessus.jsx', '../components/PlanDessin.jsx']) {
    const src = lire(f)
    assert.doesNotMatch(src, /a_confirmer|etape_statut|filtres_plan|disposition\.|\.part(?!\s*,)/, f)
  }
  assert.doesNotMatch(lire('../views/PlanDessus.jsx'), /#[0-9A-Fa-f]{6}/)
})

test('[US-327 / CA6] L’ancienne Vue plan a quitté l’écran ; le trait de rang reste pour le suivi', () => {
  const app = lire('../App.jsx')
  assert.doesNotMatch(app, /views\/PlanVue\.jsx/)
  assert.match(app, /'plan-vue': \(props\) => <PlanDessus/)
  const ui = lire('../components/ui/index.js')
  assert.doesNotMatch(ui, /export { (CartePlanParcelle|RangPlan)/)
  assert.match(ui, /TraitRang/)
})
