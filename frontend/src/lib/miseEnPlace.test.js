// [US-334] Mettre en place le plan — `npm test` : l'encart (M1, M2, M5), la première ouverture (M4),
// l'emprise proposée d'après la superficie dite (M3), la pose d'un coup, les sorties de l'assistant (CA3).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  encartMiseEnPlace, estPremiereOuverture, empriseProposee, texteProposition, dispositionEnRangees, ETAPES,
  ENCART_INITIAL, ENCART_PARTIEL, ADRESSE_PLAN, ADRESSE_PLAN_EDITEUR,
} from './miseEnPlace.js'
import { etatInitial, definirEmprise, orienter, poser, chargeEnregistrement, empriseDe, modifie, retirer } from './editeurPlan.js'
import { lireIntentionAdresse, validerIntention } from './intentions.js'

const parcelle = (id, nom, extra = {}, placee = false) => ({
  id, nom, superficie_m2: 12, ordre: id, geometrie: { placee, ...(placee ? { x_m: 1, y_m: 1, longueur_m: 4, largeur_m: 3 } : {}) }, ...extra,
})
const vierge = () => ({
  potager_geometrie: { emprise_longueur_m: null, emprise_largeur_m: null, angle_deg: 0, orientation_nord: null },
  parcelles: [parcelle(1, 'Planche nord'), parcelle(2, 'Planche sud'), parcelle(3, 'Bac')],
})

// ── L'encart (M1, M2, M5) ─────────────────────────────────────────────────────

test('M1 / CA1 — aucune parcelle posée : « Mettre en place le plan », la durée, le bouton', () => {
  const e = encartMiseEnPlace(vierge())
  assert.equal(e.type, ENCART_INITIAL)
  assert.equal(e.titre, 'Mettre en place le plan')
  assert.equal(e.duree, 'environ 5 minutes')
  assert.equal(e.libelleBouton, 'Mettre en place le plan')
  assert.equal(e.nombre, 3)
})

test('CA1 — un potager sans aucune parcelle : pas d’encart, l’invitation à créer la première reste celle de l’écran', () => {
  assert.equal(encartMiseEnPlace({ parcelles: [] }), null)
  assert.equal(encartMiseEnPlace(null), null)
})

test('M2 / CA2 — placement partiel : « N parcelles à placer », au singulier comme au pluriel', () => {
  const plan = vierge()
  plan.parcelles[0] = parcelle(1, 'Planche nord', {}, true)
  let e = encartMiseEnPlace(plan)
  assert.equal(e.type, ENCART_PARTIEL)
  assert.equal(e.titre, '2 parcelles à placer')
  assert.equal(e.duree, null)
  plan.parcelles[1] = parcelle(2, 'Planche sud', {}, true)
  e = encartMiseEnPlace(plan)
  assert.equal(e.titre, '1 parcelle à placer')
  assert.match(e.texte, /^Cette parcelle n’est pas encore dessinée/)
})

test('M5 — toutes posées : l’encart se masque ; une parcelle retirée ou créée sans position le rouvre', () => {
  const plan = vierge()
  plan.parcelles = plan.parcelles.map((p) => parcelle(p.id, p.nom, {}, true))
  assert.equal(encartMiseEnPlace(plan), null)
  plan.parcelles.push(parcelle(4, 'Créée par Telegram'))                      // CA5 : arrive « À placer »
  assert.equal(encartMiseEnPlace(plan).titre, '1 parcelle à placer')
  plan.parcelles.pop()
  plan.parcelles[0] = parcelle(1, 'Planche nord')                              // retirée du plan
  assert.equal(encartMiseEnPlace(plan).titre, '1 parcelle à placer')
})

test('M1 — l’encart ne compte pas les parcelles inactives (elles restent grisées sur le plan)', () => {
  const plan = vierge()
  plan.parcelles = [parcelle(1, 'A', {}, true)]
  plan.parcelles_inactives = [parcelle(9, 'Ancienne')]
  assert.equal(encartMiseEnPlace(plan), null)
})

// ── La première ouverture (M4) ────────────────────────────────────────────────

test('M4 — l’assistant se déroule sur un potager vierge, dans l’ordre emprise → nord → fond → pose', () => {
  assert.deepEqual(ETAPES.map((e) => e.id), ['emprise', 'nord', 'fond', 'pose'])
  assert.equal(estPremiereOuverture(vierge()), true)
})

test('M4 — il ne se redéroule plus dès qu’une emprise, un nord ou une parcelle posée existe', () => {
  let p = vierge(); p.potager_geometrie.emprise_longueur_m = 20
  assert.equal(estPremiereOuverture(p), false)
  p = vierge(); p.potager_geometrie.orientation_nord = 'n'
  assert.equal(estPremiereOuverture(p), false)
  p = vierge(); p.parcelles[0] = parcelle(1, 'Planche nord', {}, true)
  assert.equal(estPremiereOuverture(p), false)
  assert.equal(estPremiereOuverture({ parcelles: [] }), false)                  // rien à poser, rien à guider
})

// ── M3 : les dimensions dites sont reprises ──────────────────────────────────

test('M3 — l’emprise proposée contient les parcelles et se déduit de la superficie dite', () => {
  const p = empriseProposee(vierge())
  assert.ok(p.longueur >= 6 && p.largeur >= 5, JSON.stringify(p))
  assert.ok(p.longueur * p.largeur >= 3 * 12 * 2)                               // le double de la surface cultivée
  assert.match(texteProposition(vierge(), p), /^Proposée d’après vos 3 parcelles : /)
  assert.equal(empriseProposee({ parcelles: [] }), null)
})

test('M3 — la longueur dite à l’assistant n’est jamais ignorée : le terrain la contient', () => {
  const plan = { parcelles: [parcelle(1, 'Longue', { longueur_m: 18, superficie_m2: 36 })] }
  assert.ok(empriseProposee(plan).longueur >= 20)                               // 18 m + 2 m de marge
})

// ── L'emprise dans l'éditeur ──────────────────────────────────────────────────

test('M4 — l’emprise validée par l’assistant part à « Enregistrer », jamais avant', () => {
  let e = etatInitial(vierge())
  assert.equal(modifie(e), false)
  e = definirEmprise(e, { longueur: 14, largeur: 9 })
  assert.deepEqual(empriseDe(e, { longueur: 1, largeur: 1 }), { longueur: 14, largeur: 9 })
  assert.deepEqual(chargeEnregistrement(e), { parcelles: [], potager: { emprise_longueur_m: 14, emprise_largeur_m: 9 } })
})

test('M4 — chaque étape peut être passée : sans emprise validée, l’écran garde la sienne et rien ne part', () => {
  const e = etatInitial(vierge())
  assert.deepEqual(empriseDe(e, { longueur: 8, largeur: 6 }), { longueur: 8, largeur: 6 })
  assert.equal(chargeEnregistrement(e), null)
})

test('une emprise hors bornes est refusée en silence côté état (le serveur la refuserait aussi)', () => {
  const e = etatInitial(vierge())
  assert.equal(definirEmprise(e, { longueur: 0, largeur: 9 }), e)
  assert.equal(definirEmprise(e, { longueur: 'x', largeur: 9 }), e)
  assert.equal(definirEmprise(e, { longueur: 5000, largeur: 9 }), e)
})

test('M4 — emprise, nord et pose partent dans une seule charge', () => {
  let e = etatInitial(vierge())
  e = definirEmprise(e, { longueur: 12, largeur: 8 })
  e = orienter(e, 'ne')
  e = poser(e, 1, 1, 1)
  const charge = chargeEnregistrement(e)
  assert.deepEqual(charge.potager, { orientation_nord: 'ne', emprise_longueur_m: 12, emprise_largeur_m: 8 })
  assert.equal(charge.parcelles.length, 1)
  assert.equal(retirer(e, 1).parcelles[0].placee, false)
})

// ── La pose d'un coup ─────────────────────────────────────────────────────────

test('la pose d’un coup range les parcelles rangée par rangée, dans l’emprise, sans chevauchement', () => {
  const parcelles = [
    { id: 1, w: 6, h: 2 }, { id: 2, w: 6, h: 3 }, { id: 3, w: 6, h: 2 },
  ]
  const places = dispositionEnRangees(parcelles, { longueur: 14, largeur: 10 })
  assert.deepEqual(places, [{ id: 1, x: 0, y: 0 }, { id: 2, x: 7, y: 0 }, { id: 3, x: 0, y: 4 }])
})

test('la pose d’un coup garde une parcelle plus large que le terrain sur sa propre rangée', () => {
  const places = dispositionEnRangees([{ id: 1, w: 30, h: 2 }, { id: 2, w: 3, h: 2 }], { longueur: 10, largeur: 10 })
  assert.deepEqual(places, [{ id: 1, x: 0, y: 0 }, { id: 2, x: 0, y: 3 }])
})

// ── Les sorties de l'assistant « Premier potager » (CA3) ─────────────────────

test('CA3 — « maintenant » ouvre le Plan et son éditeur, « plus tard » le Plan seul', () => {
  const maintenant = lireIntentionAdresse({ pathname: '/', search: ADRESSE_PLAN_EDITEUR.slice(1) })
  assert.equal(maintenant.vue, 'plan-vue')
  assert.deepEqual(maintenant.intention, { editeur: true })
  const plusTard = lireIntentionAdresse({ pathname: '/', search: ADRESSE_PLAN.slice(1) })
  assert.equal(plusTard.vue, 'plan-vue')
  assert.equal(plusTard.intention, null)
})

test('l’intention « editeur » n’accepte que « oui »', () => {
  assert.deepEqual(validerIntention('plan-vue', { editeur: 'oui' }), { editeur: true })
  assert.equal(validerIntention('plan-vue', { editeur: 'non' }), null)
  assert.equal(validerIntention('plan-vue', { editeur: '' }), null)
})

test('l’intention « editeur » survit à sa seconde validation (adresse puis coquille)', () => {
  const lue = lireIntentionAdresse({ pathname: '/', search: ADRESSE_PLAN_EDITEUR.slice(1) })
  assert.deepEqual(validerIntention('plan-vue', lue.intention), { editeur: true })
})
