// [US-333] L'éditeur du plan — `npm test` (CA6 : aimantation, rotations, cotes, charge d'Enregistrer).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  aimanter, aimanterRotation, normaliserAngle, texteAngle, texteMetres, etatInitial, poser, deplacer, decaler,
  redimensionner, tourner, definirSens, definirRangs, retirer, orienter, annuler, refaire, selectionner,
  cotes, ecartSurface, alignerFiche, erreurRangs, erreurs, modifie, chargeEnregistrement, resumeModifications,
  demandeDeCreation, demandeDeDuplication, peutModifierLePlan, posees, aPlacer, directionDuNord, estAlignee,
  surfacePosee, DIRECTIONS, FORMES_NOUVELLES, synchroniser,
} from './editeurPlan.js'

const plan = () => ({
  potager_geometrie: { emprise_longueur_m: 20, emprise_largeur_m: 14, angle_deg: -2.5, orientation_nord: 'n' },
  parcelles: [
    { id: 1, nom: 'Planche centrale', superficie_m2: 69, nb_rangs: 8, disposition: { rangs_occupes: 3, rangs_declares: 8 },
      geometrie: { placee: true, x_m: 2, y_m: 2, longueur_m: 12, largeur_m: 5, rotation_deg: 0, sens_rangs: 'longueur', forme: 'planche' } },
    { id: 2, nom: 'Planche haricots', superficie_m2: 20, geometrie: { placee: false, forme: 'planche' } },
    { id: 3, nom: 'Bac', superficie_m2: 2, longueur_m: 2, largeur_m: 1, geometrie: { placee: false, longueur_m: 2, largeur_m: 1 } },
  ],
})

test('E1 — l’aimantation recolle sur la grille de 50 cm', () => {
  assert.equal(aimanter(1.26), 1.5)
  assert.equal(aimanter(1.24), 1)
  assert.equal(aimanter(0.1), 0)
  assert.equal(aimanter(7.75), 8)
})

test('E1 — une rotation proche de l’angle du potager se recolle sur lui, sinon au pas de 5°', () => {
  assert.equal(aimanterRotation(3), 0)
  assert.equal(aimanterRotation(357), 0)
  assert.equal(aimanterRotation(32), 30)
  assert.equal(aimanterRotation(-90), 270)
  assert.equal(normaliserAngle(360), 0)
})

test('les nombres et angles se disent à la française', () => {
  assert.equal(texteMetres(3.5), '3,5')
  assert.equal(texteAngle(-2.5), '−2,5°')
  assert.equal(texteAngle(357.5), '−2,5°')
  assert.equal(texteAngle(90), '90°')
})

test('l’état initial sépare les parcelles posées de celles « À placer »', () => {
  const e = etatInitial(plan())
  assert.deepEqual(posees(e).map((p) => p.id), [1])
  assert.deepEqual(aPlacer(e).map((p) => p.id), [2, 3])
  assert.equal(modifie(e), false)
  assert.equal(chargeEnregistrement(e), null)
  assert.equal(e.potager.angle, -2.5)
})

test('E2 — poser une parcelle « À placer » : dimensions connues, sinon un carré déduit de la superficie', () => {
  let e = etatInitial(plan())
  e = poser(e, 3, 5.1, 4.9)                       // le bac connaît ses dimensions : 2 × 1
  const bac = e.parcelles.find((p) => p.id === 3)
  assert.deepEqual([bac.x, bac.y, bac.w, bac.h, bac.placee], [5, 5, 2, 1, true])
  e = poser(e, 2, 9, 9)                           // les haricots : 20 m² → un carré de 4,5 m aimanté
  const h = e.parcelles.find((p) => p.id === 2)
  assert.equal(h.w, h.h)
  assert.equal(Math.round(h.w * 2) / 2, h.w)
  assert.equal(e.selection, 2)
})

test('E1 — déplacer et décaler s’aimantent ; le clavier avance de 50 cm', () => {
  let e = etatInitial(plan())
  e = deplacer(e, 1, 3.3, 2.8)
  assert.deepEqual([e.parcelles[0].x, e.parcelles[0].y], [3.5, 3])
  e = decaler(e, 1, 1, -1)
  assert.deepEqual([e.parcelles[0].x, e.parcelles[0].y], [4, 2.5])
})

test('redimensionner : recollé sur la grille, jamais sous 50 cm', () => {
  let e = etatInitial(plan())
  e = redimensionner(e, 1, { w: 10.2, h: 0.1 })
  assert.deepEqual([e.parcelles[0].w, e.parcelles[0].h], [10, 0.5])
  assert.equal(surfacePosee(e.parcelles[0]), 5)
})

test('tourner, sens des rangs, cotes et alignement sur le potager', () => {
  let e = etatInitial(plan())
  assert.equal(estAlignee(e.parcelles[0]), true)
  assert.deepEqual(cotes(e.parcelles[0], e), { longueur: '12 m', largeur: '5 m', angle: '−2,5° · aligné sur le potager' })
  e = tourner(e, 1, 32)
  assert.equal(e.parcelles[0].rotation, 30)
  assert.match(cotes(e.parcelles[0], e).angle, /^30° · de travers$/)
  e = definirSens(e, 1, 'travers')
  assert.equal(e.parcelles[0].sens, 'travers')
})

test('E4 — retirer du plan efface la position, pas la parcelle', () => {
  let e = etatInitial(plan())
  e = retirer(e, 1)
  assert.equal(e.parcelles.length, 3)
  assert.deepEqual(aPlacer(e).map((p) => p.id), [1, 2, 3])
  assert.equal(e.selection, null)
  assert.deepEqual(chargeEnregistrement(e), { parcelles: [{ id: 1, x_m: null, y_m: null }] })
})

test('CA4 — le contrôle de surface propose d’aligner la fiche, il ne le fait jamais seul', () => {
  let e = etatInitial(plan())
  const ecart = ecartSurface(e.parcelles[0])
  assert.equal(ecart.texte, 'Surface posée 60 m², fiche parcelle 69 m²')
  assert.equal(ecart.action, 'Mettre la fiche à 60 m²')
  assert.equal(chargeEnregistrement(deplacer(e, 1, 3, 3)).parcelles[0].aligner_superficie, undefined)
  e = alignerFiche(e, 1)
  assert.equal(ecartSurface(e.parcelles[0]), null)
  assert.equal(chargeEnregistrement(e).parcelles[0].aligner_superficie, true)
})

test('E6 — descendre sous les rangs occupés est refusé avec l’explication', () => {
  let e = etatInitial(plan())
  e = definirRangs(e, 1, 2)
  assert.equal(erreurRangs(e.parcelles[0]), '3 rangs occupés : on ne peut pas descendre à 2.')
  assert.equal(erreurs(e).length, 1)
  e = definirRangs(e, 1, 4)
  assert.equal(erreurRangs(e.parcelles[0]), null)
  assert.equal(chargeEnregistrement(e).parcelles[0].nb_rangs, 4)
})

test('CA5 — la rose des vents fixe le nord, huit directions', () => {
  assert.equal(DIRECTIONS.length, 8)
  let e = etatInitial(plan())
  e = orienter(e, 'ne')
  assert.equal(directionDuNord(e).nord, 'en haut à droite du plan')
  assert.deepEqual(chargeEnregistrement(e), { parcelles: [], potager: { orientation_nord: 'ne' } })
  assert.equal(orienter(e, 'zz'), e)
})

test('E5 / CA3 — Enregistrer n’envoie que ce qui a changé, en une charge', () => {
  let e = etatInitial(plan())
  e = poser(e, 2, 9, 9)
  e = redimensionner(e, 1, { w: 11 })
  const charge = chargeEnregistrement(e)
  assert.equal(charge.parcelles.length, 2)
  const haricots = charge.parcelles.find((p) => p.id === 2)
  assert.deepEqual(Object.keys(haricots).sort(), ['id', 'largeur_m', 'longueur_m', 'x_m', 'y_m'])
  assert.deepEqual(charge.parcelles.find((p) => p.id === 1), { id: 1, longueur_m: 11 })
  assert.equal(resumeModifications(e), '2 parcelles modifiées')
  assert.equal(modifie(e), true)
})

test('Ctrl+Z — annuler et rétablir la dernière action', () => {
  let e = etatInitial(plan())
  e = deplacer(e, 1, 6, 6)
  e = tourner(e, 1, 45)
  e = annuler(e)
  assert.equal(e.parcelles[0].rotation, 0)
  assert.equal(e.parcelles[0].x, 6)
  e = annuler(e)
  assert.equal(modifie(e), false)
  assert.equal(annuler(e), e)
  e = refaire(e)
  assert.equal(e.parcelles[0].x, 6)
  assert.equal(selectionner(e, e.selection), e)
})

test('E3 — une forme nouvelle devient une demande à Gaston, jamais une écriture', () => {
  const e = etatInitial(plan())
  assert.equal(FORMES_NOUVELLES.length, 4)
  const d = demandeDeCreation('planche', 4.2, 2.1, e, { longueur: 3.5, largeur: 3 })
  assert.equal(d.phrase, 'Créer une planche de 3,5 × 3 m')
  assert.deepEqual(d.plan, {
    action: 'creer', forme: 'planche', longueur_m: 3.5, largeur_m: 3, x_m: 4, y_m: 2, sens_rangs: 'longueur',
  })
  const dup = demandeDeDuplication(e, 1)
  assert.equal(dup.plan.longueur_m, 12)
  assert.deepEqual([dup.plan.x_m, dup.plan.y_m], [3, 3])
  assert.equal(demandeDeDuplication(e, 2), null)    // une parcelle « À placer » ne se duplique pas
})

test('CA7 / E7 — l’éditeur n’est proposé qu’à un éditeur, sur 720 px de conteneur et plus', () => {
  assert.equal(peutModifierLePlan('editor', 900), true)
  assert.equal(peutModifierLePlan('owner', 720), true)
  assert.equal(peutModifierLePlan('lecteur', 1200), false)
  assert.equal(peutModifierLePlan('editor', 600), false)
  assert.equal(peutModifierLePlan(undefined, 1200), false)
})

test('une parcelle confirmée par Gaston entre dans l’éditeur sans perdre les modifications en cours', () => {
  let e = etatInitial(plan())
  e = deplacer(e, 1, 6, 6)
  const nouveau = plan()
  nouveau.parcelles.push({ id: 9, nom: 'Planche 9', superficie_m2: 10.5,
    geometrie: { placee: true, x_m: 4, y_m: 2, longueur_m: 3.5, largeur_m: 3, forme: 'planche' } })
  const apres = synchroniser(e, nouveau)
  assert.deepEqual(posees(apres).map((p) => p.id), [1, 9])
  assert.equal(apres.parcelles[0].x, 6)                              // la modification en cours est gardée
  assert.deepEqual(chargeEnregistrement(apres).parcelles.map((p) => p.id), [1])   // la nouvelle n'est pas « modifiée »
  nouveau.parcelles = nouveau.parcelles.filter((p) => p.id !== 3)    // supprimée pendant ce temps
  assert.equal(synchroniser(apres, nouveau).parcelles.some((p) => p.id === 3), false)
  assert.equal(synchroniser(apres, nouveau).selection, null)
})

test('une parcelle qu’on pose écrit toujours ses dimensions, même connues de la fiche', () => {
  const e = poser(etatInitial(plan()), 3, 5, 5)           // le bac : 2 × 1 déjà connus
  assert.deepEqual(chargeEnregistrement(e).parcelles, [{ id: 3, x_m: 5, y_m: 5, longueur_m: 2, largeur_m: 1 }])
})

test('une fiche déjà incohérente (rangs occupés > rangs déclarés) ne bloque pas Enregistrer', () => {
  const p = plan()
  p.parcelles[0].nb_rangs = 2                      // 3 rangs occupés pour 2 déclarés : donnée existante
  let e = etatInitial(p)
  e = deplacer(e, 1, 6, 6)
  assert.equal(erreurs(e).length, 0)
  assert.equal(chargeEnregistrement(e).parcelles.length, 1)
  e = definirRangs(e, 1, 1)                        // mais descendre encore est refusé
  assert.equal(erreurs(e).length, 1)
})
