// [US-324] « Noter » avec Gaston — `npm test`.
//
// Ce qui se vérifie ici : les pastilles suivent le tableau de l'US (CA2), l'accueil selon ce
// qu'on a sous les yeux, « Pas encore » vise la série et l'étape (E7), « Retour au plan » après
// confirmation (CA5), le câblage du panneau (micro ouvert seul, CA1) et de la coquille.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  RACCOURCI, SORTE, VUE_PLAN, TEXTE_ACCUEIL_CULTURE, TEXTE_ACCUEIL_PARCELLE, TEXTE_ACCUEIL_POTAGER,
  raccourcisNoter, accueilNoter, reportDEtape, apresConfirmation,
} from './noter.js'
import { contexteAEnvoyer, normaliserContexte } from './contexteCompagnon.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')
const SEMIS = [{ code: 'semee' }, { code: 'levee' }, { code: 'en_recolte' }, { code: 'terminee' }]
const PLANT = [{ code: 'plantee' }, { code: 'en_recolte' }, { code: 'terminee' }]
const feve = (etapes) => ({ parcelleId: 2, parcelle: 'Planche centrale', culture: 'fève', etapes })
const libelles = (c) => raccourcisNoter(c).map((x) => x.libelle)

test('[US-324 / CA2] étape à confirmer : « Levée vue », « Pas encore »', () => {
  const c = feve({ serie_id: 7, etape: 'levee', a_confirmer: true, etapes: SEMIS })
  assert.deepEqual(libelles(c), ['Levée vue', 'Pas encore'])
  assert.equal(raccourcisNoter(c)[0].raccourci, RACCOURCI.ETAPE_LEVEE)
  assert.equal(raccourcisNoter(c)[1].sorte, SORTE.PAS_ENCORE)
})

test('[US-324 / CA2] en récolte : « Récolte » (attend la quantité), « Culture terminée »', () => {
  const c = feve({ serie_id: 7, etape: 'en_recolte', a_confirmer: false, etapes: PLANT })
  assert.deepEqual(libelles(c), ['Récolte', 'Culture terminée'])
  assert.equal(raccourcisNoter(c)[0].sorte, SORTE.SAISIR)
})

test('[US-324 / CA2] terminé ou à libérer : « Rang libéré »', () => {
  assert.deepEqual(libelles(feve({ etape: 'terminee', etapes: PLANT })), ['Rang libéré'])
  assert.deepEqual(libelles(feve({ etape: 'en_recolte', a_liberer: true, etapes: PLANT })), ['Rang libéré'])
})

test('[US-324 / CA2] autre étape : l’étape suivante', () => {
  assert.deepEqual(libelles(feve({ etape: 'semee', etapes: SEMIS })), ['Levée vue'])
  assert.deepEqual(libelles(feve({ etape: 'plantee', etapes: PLANT })), ['Récolte'])
})

test('[US-324 / CA2] parcelle ou potager : « Arrosé », « Paillé », « Désherbé »', () => {
  assert.deepEqual(libelles({ parcelleId: 5, parcelle: 'Serre' }), ['Arrosé', 'Paillé', 'Désherbé'])
  assert.deepEqual(libelles(null), ['Arrosé', 'Paillé', 'Désherbé'])
})

test('[US-324 / temps 2] l’accueil dit où la note ira', () => {
  assert.equal(accueilNoter(feve(null)), TEXTE_ACCUEIL_CULTURE)
  assert.equal(accueilNoter({ parcelleId: 5, parcelle: 'Serre' }), TEXTE_ACCUEIL_PARCELLE)
  assert.equal(accueilNoter(null), TEXTE_ACCUEIL_POTAGER)
})

test('[US-324 / CA2, E7] « Pas encore » vise la série et l’étape servies par le suivi', () => {
  assert.deepEqual(reportDEtape(feve({ serie_id: 7, etape: 'levee', a_confirmer: true })), { serieId: 7, etape: 'levee' })
  assert.equal(reportDEtape(feve(null)), null)
})

test('[US-324 / CA5] après confirmation : ce qui a changé, et « Retour au plan » depuis « Noter »', () => {
  assert.deepEqual(apresConfirmation({ annonce: 'Fève passe à « Levé » sur le plan.' }, { noter: true }),
    { texte: 'Fève passe à « Levé » sur le plan.', retourPlan: true })
  assert.equal(apresConfirmation({ annonce: null }, { noter: false }), null)
  assert.equal(apresConfirmation({ erreur: 'refus', annonce: 'x' }, { noter: true }), null)
  assert.equal(VUE_PLAN, 'plan-vue')
})

test('[US-323 / C4] l’étape aide à choisir les pastilles, elle ne part jamais au serveur', () => {
  const c = feve({ serie_id: 7, etape: 'levee', a_confirmer: true })
  assert.ok(normaliserContexte(c).etapes)
  assert.deepEqual(contexteAEnvoyer(c), { parcelle_id: 2, culture: 'fève' })
})

test('[US-324 / CA1, CA2, CA5] le panneau ouvre le micro seul et envoie le raccourci ; la coquille ramène au plan', () => {
  const panneau = lire('../components/PanneauCompagnon.jsx')
  assert.match(panneau, /microOuvertSeul\.current = true/)
  assert.match(panneau, /raccourci \|\| undefined/)
  assert.match(panneau, /api\.pasEncoreEtape\(report\.serieId, report\.etape\)/)
  assert.match(panneau, /TEXTE_RETOUR_PLAN/)
  const app = lire('../App.jsx')
  // [US-328] Un placement ouvre la barre de contexte sans l'accueil de « Noter ».
  assert.match(app, /noter=\{ouverture\.barre && !ouverture\.placement\}/)
  assert.match(app, /changerVue\(VUE_PLAN\)/)
})
