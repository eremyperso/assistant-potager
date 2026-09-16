// [US-070] Calendrier recalé sur les événements réels — mise en forme des
// `projections` de `GET /plan/calendriers`. Le calcul est testé côté serveur
// (tests/test_us070_calendrier_recale.py) ; ici, seulement ce qui s'affiche.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  projectionDeTuile, friseRecalee, resteLisible, reperesLisibles, jourLisible,
  couleurDuMoisReferentiel, phasesDuMois, ETAT_CROISSANCE, PHASES_REFERENTIEL,
  TEINTE_EN_CROISSANCE_RESERVEE,
} from './calendrier.js'

const moisVides = { semis_pepiniere: [], semis_pleine_terre: [], plantation: [], croissance: [], recolte: [] }

/** La courgette du Gherkin : semée en pleine terre le 12 avril, consultée le 15 juin. */
const courgette = (champs = {}) => ({
  parcelle_id: 1, culture: 'courgette', variete: '', etat: 'a_venir', motif: null,
  origine: { action: 'semis', date: '2026-04-12', contexte: 'pleine_terre' },
  plantation_reelle: null, decalage_plantation_jours: null,
  levee_attendue: { debut: '2026-04-22', fin: '2026-04-22' },
  recolte_attendue: { debut: '2026-07-16', fin: '2026-07-16' },
  recolte_reelle: null, jours_restants: { min: 31, max: 31 }, retard_jours: null,
  series_suivantes: 0, prochaine_plage_semis: null,
  mois: { ...moisVides, semis_pleine_terre: [4], croissance: [5, 6], recolte: [7, 8, 9, 10] },
  ...champs,
})

test('[CA1] la projection se retrouve par parcelle, culture et variété', () => {
  const calendriers = { projections: [courgette(), courgette({ parcelle_id: 2, variete: 'Ronde de Nice' })] }
  assert.equal(projectionDeTuile(calendriers, 1, 'Courgette', null).parcelle_id, 1)
  assert.equal(projectionDeTuile(calendriers, 2, 'courgette', 'ronde de nice').variete, 'Ronde de Nice')
  assert.equal(projectionDeTuile(calendriers, 2, 'courgette', ''), null)
  assert.equal(projectionDeTuile(null, 1, 'courgette', ''), null)
})

test('[CA7] quatre états sur la frise : semis, en croissance, récolte, rien de prévu', () => {
  const f = friseRecalee(courgette())
  assert.deepEqual(f.pleineTerre, [3])          // avril
  assert.deepEqual(f.croissance, [4, 5])        // mai, juin
  assert.deepEqual(f.rec, [6, 7, 8, 9])         // juillet → octobre
  const c = couleurDuMoisReferentiel(f)
  assert.deepEqual([3, 4, 5, 6, 0].map(c), ['bg-violet', TEINTE_EN_CROISSANCE_RESERVEE, TEINTE_EN_CROISSANCE_RESERVEE, 'bg-amber', 'bg-card-alt'])
})

test('[CA7] « en croissance » a sa teinte, distincte de toutes les phases, et passe après elles', () => {
  assert.equal(ETAT_CROISSANCE.teinte, TEINTE_EN_CROISSANCE_RESERVEE)
  assert.equal(PHASES_REFERENTIEL.some((p) => p.teinte === ETAT_CROISSANCE.teinte), false)
  // Un mois à la fois planté et en croissance se peint en plantation, et nomme les deux.
  const frise = { plantation: [4], croissance: [4] }
  assert.equal(couleurDuMoisReferentiel(frise)(4), 'bg-brand')
  assert.deepEqual(phasesDuMois(frise, 4), ['Plantation', 'En croissance'])
})

test('[CA11] sans recalage, aucune frise inventée : la conseillée reste', () => {
  const plant = courgette({ etat: 'sans_recalage', motif: 'plantation_sans_semis', mois: null, jours_restants: null })
  assert.equal(friseRecalee(plant), null)
  assert.equal(friseRecalee(null), null)
  assert.equal(resteLisible(plant), null)
})

test('[CA3] la durée restante est dite en jours, au conditionnel', () => {
  assert.equal(resteLisible(courgette()), 'récolte attendue dans 31 jours')
  assert.equal(resteLisible(courgette({ jours_restants: { min: 25, max: 45 } })), 'récolte attendue dans 25 à 45 jours')
  assert.equal(resteLisible(courgette({ etat: 'recolte_attendue', jours_restants: { min: 0, max: 15 } })), "récolte attendue d'ici 15 jours")
  assert.equal(resteLisible(courgette({ etat: 'recolte_attendue', jours_restants: { min: 0, max: 0 } })), 'récolte attendue dès maintenant')
})

test('[CA5] une récolte réelle remplace l’attendu', () => {
  const reelle = courgette({ etat: 'en_recolte', recolte_reelle: { premiere: '2026-07-08', derniere: '2026-07-08' }, jours_restants: null })
  assert.equal(resteLisible(reelle), 'en récolte depuis le 8 juillet')
  assert.equal(reperesLisibles(reelle).some((r) => r.includes('attendue')), false)
})

test('[CA12] une récolte attendue dépassée est dite, jamais masquée', () => {
  const depassee = courgette({ etat: 'recolte_depassee', retard_jours: 15, jours_restants: null })
  assert.equal(resteLisible(depassee), 'récolte attendue il y a 15 jours, aucune récolte notée')
})

test('[CA2/CA4/CA9/CA10] repères dans l’ordre du cycle, fourchette gardée', () => {
  const tomate = courgette({
    culture: 'tomate',
    origine: { action: 'semis', date: '2026-03-15', contexte: 'pepiniere' },
    plantation_reelle: '2026-05-10',
    levee_attendue: null,
    recolte_attendue: { debut: '2026-07-13', fin: '2026-08-02' },
    series_suivantes: 1,
    prochaine_plage_semis: { affichage: 'mai → juin' },
  })
  assert.deepEqual(reperesLisibles(tomate), [
    'semé le 15 mars en pépinière',
    'planté le 10 mai',
    '1re récolte attendue entre le 13 juillet et le 2 août',
    'une autre série en place',
    'semis encore possible : mai → juin',
  ])
  assert.deepEqual(reperesLisibles(courgette()).slice(1, 3),
    ['levée attendue vers le 22 avril', '1re récolte attendue vers le 16 juillet'])
})

test('[CA11] une plantation sans semis connu dit sa date, sans rien projeter', () => {
  const plant = courgette({ etat: 'sans_recalage', origine: { action: 'plantation', date: '2026-05-10', contexte: null }, plantation_reelle: '2026-05-10', mois: null })
  assert.deepEqual(reperesLisibles(plant), ['planté le 10 mai'])
})

test('jourLisible : 1er du mois, date absente sans plantage', () => {
  assert.equal(jourLisible('2026-06-01'), '1er juin')
  assert.equal(jourLisible(null), '')
})

test('[CA8] la date de référence part avec la lecture du calendrier', () => {
  const plan = readFileSync(new URL('../views/Plan.jsx', import.meta.url), 'utf-8')
  assert.match(plan, /calendriersPlan\(noms, potagerId, dateRef\)/)
  const api = readFileSync(new URL('./api.js', import.meta.url), 'utf-8')
  assert.match(api, /p\.append\('date_ref', dateRef\)/)
})
