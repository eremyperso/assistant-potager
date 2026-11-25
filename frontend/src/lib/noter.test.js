// [US-324] « Noter » avec Gaston — `npm test`.
//
// Ce qui se vérifie ici : les pastilles suivent le tableau de l'US (CA2), l'accueil selon ce
// qu'on a sous les yeux, « Pas encore » vise la série et l'étape (E7), « Retour au plan » après
// confirmation (CA5), le câblage du panneau (micro ouvert seul, CA1) et de la coquille.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  RACCOURCI, SORTE, VUE_PLAN, reportDEtape, apresConfirmation,
} from './noter.js'
import { suggestionsDe, phraseOuverture, PHRASE_SANS_CONTEXTE } from './ouvertureGaston.js'
import { contexteAEnvoyer, normaliserContexte } from './contexteCompagnon.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')
const SEMIS = [{ code: 'semee' }, { code: 'levee' }, { code: 'en_recolte' }, { code: 'terminee' }]
const PLANT = [{ code: 'plantee' }, { code: 'en_recolte' }, { code: 'terminee' }]
const feve = (etapes) => ({ parcelleId: 2, parcelle: 'Planche centrale', culture: 'fève', etapes })
const libelles = (c) => suggestionsDe({ contexte: c }).map((x) => x.libelle)

test('[US-324 / CA2, US-358 / CA3] étape à confirmer : « J’ai vu la levée », « Pas encore »', () => {
  const c = feve({ serie_id: 7, etape: 'levee', a_confirmer: true, etapes: SEMIS })
  assert.deepEqual(libelles(c), ['J’ai vu la levée', 'Pas encore'])
  assert.equal(suggestionsDe({ contexte: c })[0].raccourci, RACCOURCI.ETAPE_LEVEE)
  assert.equal(suggestionsDe({ contexte: c })[1].sorte, SORTE.PAS_ENCORE)
})

test('[US-358 / CA3] en récolte : « Récolte » (attend la quantité), « Note »', () => {
  const c = feve({ serie_id: 7, etape: 'en_recolte', a_confirmer: false, etapes: PLANT })
  assert.deepEqual(libelles(c), ['Récolte', 'Note'])
  assert.equal(suggestionsDe({ contexte: c })[0].sorte, SORTE.SAISIR)
})

test('[US-358 / CA3] terminé ou à libérer : « Libérer le rang », « Note »', () => {
  assert.deepEqual(libelles(feve({ etape: 'terminee', etapes: PLANT })), ['Libérer le rang', 'Note'])
  assert.deepEqual(libelles(feve({ etape: 'en_recolte', a_liberer: true, etapes: PLANT })), ['Libérer le rang', 'Note'])
})

test('[US-358 / CA3] étape prévue : l’étape suivante, « Pas encore »', () => {
  assert.deepEqual(libelles(feve({ etape: 'semee', etapes: SEMIS })), ['J’ai vu la levée', 'Pas encore'])
  assert.deepEqual(libelles(feve({ etape: 'plantee', etapes: PLANT })), ['Récolte', 'Pas encore'])
})

test('[US-324 / CA2, US-358 / CA3] parcelle : gestes ; aucun contexte : Récolte, Semis, Observation', () => {
  assert.deepEqual(libelles({ parcelleId: 5, parcelle: 'Serre' }), ['Arrosé', 'Paillé', 'Désherbé'])
  assert.deepEqual(libelles(null), ['Récolte', 'Semis', 'Observation'])
})

test('[US-358 / CA2] l’ouverture dit où la note ira, sans modèle', () => {
  assert.equal(phraseOuverture({ contexte: null }), PHRASE_SANS_CONTEXTE)
  assert.match(phraseOuverture({ contexte: { parcelleId: 5, parcelle: 'Serre' } }), /^Vous êtes sur Serre\./)
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
