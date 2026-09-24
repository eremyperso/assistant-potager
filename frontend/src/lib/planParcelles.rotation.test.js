// [US-231] La carte « Rotation » — ce que l'écran en fait, et ce qu'il n'en
// fait PAS.
//
// Le test central est celui de la **non-duplication** [CA1] : aucune de ces
// assertions ne recalcule une alerte, un conseil ou un délai de retour. Toutes
// vérifient que le module transporte ce que `app/services/rotation.py` a dit,
// et qu'il ne comble aucun silence — une année vide reste vide, une famille
// inconnue reste inconnue.
import test from 'node:test'
import assert from 'node:assert/strict'
import { rotationDeParcelle, aUneRotation, LIBELLE_CONSEILLE } from './planParcelles.js'
import {
  teinteFamille, indexTeinteFamille, TEINTE_FAMILLE_INCONNUE, NB_TEINTES_FAMILLE,
} from './familles.js'

/** Une colonne de campagne dans la forme EXACTE du service. */
const campagne = (annee, familles = []) => ({ annee, familles })

const famille = (nom, cultures, extra = {}) => ({
  famille: nom, famille_id: extra.famille_id ?? 1, inconnue: false, cultures, ...extra,
})

/** La réponse du service pour la planche du Gherkin : Solanacées 2025 et 2026. */
const rotationGherkin = () => ({
  campagne_a_venir: 2027,
  campagnes: [
    campagne(2024),
    campagne(2025, [famille('Solanacées', ['tomate'], { famille_id: 7 })]),
    campagne(2026, [famille('Solanacées', ['poivron'], { famille_id: 7 })]),
  ],
  conseil: {
    annee: 2027,
    familles: [{
      famille: 'Apiacées', famille_id: 3, delai_retour_annees: 2,
      derniere_campagne: null, cultures: ['carotte'],
    }],
    mention: null,
  },
  alertes: [{
    famille: 'Solanacées', famille_id: 7, annees: 2, annee_a_eviter: 2027,
    message: 'Solanacées deux années de suite sur cette parcelle. À éviter en 2027.',
  }],
  cultures_sans_famille: [],
  mention_familles_inconnues: null,
  aucun_antecedent: false,
  mention_aucun_antecedent: null,
})

const planche = (rotation = rotationGherkin(), extra = {}) => ({
  id: 1, nom: 'planche_centrale', est_pepiniere: false, rotation, ...extra,
})

// ── R1, R4 : quatre colonnes, la dernière conseillée ────────────────────────

test('[US-231 / R1] quatre colonnes : trois campagnes puis la campagne à venir', () => {
  const carte = rotationDeParcelle(planche())
  assert.deepEqual(carte.colonnes.map((c) => c.annee), [2024, 2025, 2026, 2027])
})

test('[US-231 / R4] la colonne de l’année à venir est celle du conseil', () => {
  const carte = rotationDeParcelle(planche())
  const derniere = carte.colonnes.at(-1)
  assert.equal(derniere.conseil, true)
  assert.equal(derniere.libelle, LIBELLE_CONSEILLE)
  assert.equal(derniere.vignettes[0].famille, 'Apiacées')
  // [CA8] Rien d'actionnable dans la colonne de conseil : ce sont des familles
  // possibles, pas des gestes à faire.
  assert.deepEqual(derniere.vignettes[0].cultures, [])
  assert.match(derniere.vignettes[0].note, /jamais cultivée ici/)
  // Les trois colonnes d'historique, elles, ne sont pas en pointillés.
  assert.deepEqual(carte.colonnes.slice(0, 3).map((c) => c.conseil), [false, false, false])
})

test('[US-231 / R2] une vignette porte le nom de la famille et ses cultures', () => {
  const carte = rotationDeParcelle(planche())
  const vignette = carte.colonnes[1].vignettes[0]
  assert.equal(vignette.famille, 'Solanacées')
  assert.deepEqual(vignette.cultures, ['Tomate'])
  assert.equal(vignette.inconnue, false)
})

test('[US-231 / R2] plusieurs familles la même année = plusieurs vignettes', () => {
  const rotation = rotationGherkin()
  rotation.campagnes[2].familles = [
    famille('Apiacées', ['carotte'], { famille_id: 3 }),
    famille('Solanacées', ['tomate'], { famille_id: 7 }),
  ]
  const carte = rotationDeParcelle(planche(rotation))
  assert.deepEqual(
    carte.colonnes[2].vignettes.map((v) => v.famille), ['Apiacées', 'Solanacées'],
  )
})

// ── R5, R6, R7 : ce qui se dit sous la grille ───────────────────────────────

test('[US-231 / R5] l’alerte de répétition est transportée telle quelle', () => {
  const carte = rotationDeParcelle(planche())
  assert.equal(carte.alertes.length, 1)
  assert.equal(
    carte.alertes[0].message,
    'Solanacées deux années de suite sur cette parcelle. À éviter en 2027.',
  )
})

test('[US-231 / R6] une année sans donnée reste une colonne vide', () => {
  const carte = rotationDeParcelle(planche())
  assert.equal(carte.colonnes[0].vide, true)
  assert.deepEqual(carte.colonnes[0].vignettes, [])
  assert.equal(carte.colonnes[1].vide, false)
})

test('[US-231 / R6] aucun antécédent : la phrase est dite, le conseil reste', () => {
  const rotation = rotationGherkin()
  rotation.campagnes = [campagne(2024), campagne(2025), campagne(2026)]
  rotation.alertes = []
  rotation.aucun_antecedent = true
  rotation.mention_aucun_antecedent =
    'Aucune culture enregistrée sur cette parcelle avant 2026.'
  const carte = rotationDeParcelle(planche(rotation))
  assert.equal(
    carte.mentionAucunAntecedent,
    'Aucune culture enregistrée sur cette parcelle avant 2026.',
  )
  assert.equal(carte.colonnes.at(-1).vignettes.length, 1)
})

test('[US-231 / R7, CA5] une famille inconnue est nommée, neutre, et signalée', () => {
  const rotation = rotationGherkin()
  rotation.campagnes[2].familles = [{
    famille: 'Famille non renseignée', famille_id: null, inconnue: true,
    cultures: ['topinambour'],
  }]
  rotation.mention_familles_inconnues =
    'Famille botanique non renseignée pour topinambour : cette culture n’entre '
    + 'ni dans l’alerte de répétition ni dans le conseil.'
  const carte = rotationDeParcelle(planche(rotation))
  const vignette = carte.colonnes[2].vignettes[0]
  assert.equal(vignette.famille, 'Famille non renseignée')
  assert.equal(vignette.inconnue, true)
  // [R3] Une lacune n'a pas d'identité : elle reste neutre, jamais teintée.
  assert.deepEqual(vignette.teinte, TEINTE_FAMILLE_INCONNUE)
  assert.match(carte.mentionFamillesInconnues, /ni dans l’alerte/)
})

test('[US-231 / R4] un conseil non formulable dit ce qui manque', () => {
  const rotation = rotationGherkin()
  rotation.conseil = {
    annee: 2027, familles: [],
    mention: 'Aucun délai de retour n’est renseigné dans le référentiel : je ne '
      + 'formule pas de conseil pour 2027.',
  }
  const carte = rotationDeParcelle(planche(rotation))
  assert.equal(carte.colonnes.at(-1).vide, true)
  assert.match(carte.mentionConseil, /Aucun délai de retour/)
})

// ── R8 : la pépinière n'a pas de rotation ───────────────────────────────────

test('[US-231 / R8] une pépinière n’a pas de carte Rotation', () => {
  assert.equal(aUneRotation(planche(rotationGherkin(), { est_pepiniere: true })), false)
  assert.equal(rotationDeParcelle(planche(rotationGherkin(), { est_pepiniere: true })), null)
})

test('[US-231] une réponse sans bloc rotation ne fabrique pas de grille vide', () => {
  assert.equal(rotationDeParcelle({ id: 1, nom: 'NORD' }), null)
})

// ── R3 : la teinte identifie une famille, elle ne la juge pas ───────────────

test('[US-231 / R3] la même famille garde la même teinte partout', () => {
  const ici = teinteFamille('Solanacées')
  const ailleurs = teinteFamille('  solanacées ')
  assert.deepEqual(ici, ailleurs)
  assert.equal(ici.fond, `var(--fam-${ici.index}-soft)`)
})

test('[US-231 / R3] deux familles distinctes ne portent pas la même teinte', () => {
  assert.notEqual(indexTeinteFamille('Solanacées'), indexTeinteFamille('Apiacées'))
})

test('[US-231 / R3] la teinte reste dans la palette, et ne juge jamais', () => {
  for (const nom of ['Solanacées', 'Apiacées', 'Fabacées', 'Cucurbitacées',
    'Brassicacées', 'Astéracées', 'Liliacées', 'Chénopodiacées', 'Poacées']) {
    const index = indexTeinteFamille(nom)
    assert.ok(index >= 1 && index <= NB_TEINTES_FAMILLE, `${nom} → ${index}`)
    // Ni ambre ni rouge : ces deux teintes disent « attention » et « refus »
    // partout ailleurs dans l'application, et une famille n'est ni l'un ni
    // l'autre (RT4).
    const teinte = teinteFamille(nom)
    assert.equal(teinte.fond.includes('amber'), false)
    assert.equal(teinte.fond.includes('red'), false)
  }
})

test('[US-231 / R3] une famille sans nom ne reçoit aucune teinte', () => {
  assert.equal(indexTeinteFamille(''), null)
  assert.deepEqual(teinteFamille(null), TEINTE_FAMILLE_INCONNUE)
})
