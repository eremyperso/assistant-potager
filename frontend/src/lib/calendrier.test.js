// [US-176] Frise de l'écran Plan lue depuis `GET /plan/calendriers` — `npm test`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  culturesDuPlan, friseDeCulture, zoneAffichable, attributionsAffichables, couleurDuMois,
  couleurDuMoisReferentiel, phasesDuMois, PHASES_REFERENTIEL, PRIORITE_PHASES,
  TEINTE_EN_CROISSANCE_RESERVEE, FRISE_DEGRADEE, TIRET,
} from './calendrier.js'

const reponse = (cultures, champs = {}) => ({
  zone_climatique: 'mediterraneen', zone_climatique_origine: 'jardinier',
  attributions: [], cultures, ...champs,
})

const entree = (champs) => ({
  culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
  mois: { semis_pepiniere: [], semis_pleine_terre: [], plantation: [], recolte: [] }, duree_recolte: TIRET,
  ...champs,
})

test('[CA1/CA3] les quatre fenêtres du référentiel colorent la frise, plantation comprise', () => {
  const cal = reponse({ tomate: entree({ mois: { semis_pepiniere: [2, 3], semis_pleine_terre: [], plantation: [5, 6], recolte: [7, 8] } }) })
  const f = friseDeCulture(cal, 'tomate')
  assert.deepEqual(f.pepiniere, [1, 2])       // février, mars
  assert.deepEqual(f.plantation, [4, 5])      // mai, juin
  assert.deepEqual(f.rec, [6, 7])
  assert.deepEqual(f.pleineTerre, [])
  assert.equal('plant' in f, false)
  assert.equal(f.degrade, false)
})

test('[CA3] la plantation est lue, jamais reconstituée du semis en pépinière', () => {
  const aubergine = entree({ mois: { semis_pepiniere: [3], semis_pleine_terre: [], plantation: [], recolte: [] } })
  assert.deepEqual(friseDeCulture(reponse({ aubergine }), 'aubergine').plantation, [])
  // Une réponse antérieure à la phase (sans clé `plantation`) ne plante rien non plus.
  const ancienne = entree({ mois: { semis_pepiniere: [3], semis_pleine_terre: [], recolte: [] } })
  assert.deepEqual(friseDeCulture(reponse({ a: ancienne }), 'a').plantation, [])
})

test('[CA3/CA6] une culture qui n’a que sa plantation n’est pas dégradée', () => {
  const fraise = entree({ mois: { semis_pepiniere: [], semis_pleine_terre: [], plantation: [5, 6], recolte: [] } })
  assert.equal(friseDeCulture(reponse({ fraise }), 'fraise').degrade, false)
})

test('[CA3bis] quatre teintes distinctes, aucune ne prend celle réservée à « en croissance »', () => {
  const teintes = PHASES_REFERENTIEL.map((p) => p.teinte)
  assert.equal(new Set(teintes).size, 4)
  assert.equal(teintes.includes(TEINTE_EN_CROISSANCE_RESERVEE), false)
  assert.deepEqual(PHASES_REFERENTIEL.map((p) => p.serveur), ['semis_pepiniere', 'semis_pleine_terre', 'plantation', 'recolte'])
})

test('[CA3bis] la règle de priorité est déclarée et couvre chaque phase une fois', () => {
  assert.deepEqual([...PRIORITE_PHASES].sort(), PHASES_REFERENTIEL.map((p) => p.cle).sort())
  // Concombre en mai : semis en pleine terre ET plantation → la plantation l’emporte.
  const concombre = { pepiniere: [3], pleineTerre: [4], plantation: [4], rec: [6, 7] }
  const c = couleurDuMoisReferentiel(concombre)
  assert.deepEqual([3, 4, 6, 0].map(c), ['bg-blue', 'bg-brand', 'bg-amber', 'bg-card-alt'])
  assert.equal(couleurDuMoisReferentiel({ pleineTerre: [2] })(2), 'bg-violet')
})

test('[CA3bis] un mois ne perd jamais une phase en silence', () => {
  const concombre = { pepiniere: [3], pleineTerre: [4], plantation: [4], rec: [] }
  assert.deepEqual(phasesDuMois(concombre, 4), ['Semis en pleine terre', 'Plantation'])
  assert.deepEqual(phasesDuMois(concombre, 0), [])
  assert.deepEqual(phasesDuMois(FRISE_DEGRADEE, 4), [])
})

test('[CA3] une fenêtre à cheval sur l’année colore les deux bouts', () => {
  const cal = reponse({ mache: entree({ mois: { semis_pepiniere: [], semis_pleine_terre: [], recolte: [11, 12, 1, 2] } }) })
  assert.deepEqual(friseDeCulture(cal, 'mache').rec, [10, 11, 0, 1])
})

test('[CA4] durée semis → récolte en forme de lecture, tiret sinon', () => {
  assert.equal(friseDeCulture(reponse({ t: entree({ duree_recolte: '70 à 90 jours' }) }), 't').duree, '70 à 90 jours')
  assert.equal(friseDeCulture(reponse({ t: entree({ duree_recolte: null }) }), 't').duree, TIRET)
})

test('[CA5] un itinéraire non standard est nommé, le standard ne l’est pas', () => {
  assert.equal(friseDeCulture(reponse({ t: entree() }), 't').itineraire, null)
  const hiver = entree({ itineraire: "culture d'hiver", itineraire_standard: false })
  assert.equal(friseDeCulture(reponse({ t: hiver }), 't').itineraire, "culture d'hiver")
})

test('[CA6] trois cas du mode dégradé : absente, sans fenêtre, autre zone', () => {
  assert.equal(friseDeCulture(reponse({}), 'ail'), FRISE_DEGRADEE)
  const vide = entree({ renseigne: false })
  assert.equal(friseDeCulture(reponse({ ail: vide }), 'ail').degrade, true)
  assert.equal(friseDeCulture(reponse({ ail: { ...vide, culture_connue: false, itineraire: null } }), 'ail').duree, TIRET)
})

test('[CA12] lecture en échec : frise neutre, aucune valeur de repli', () => {
  const f = friseDeCulture(null, 'tomate')
  assert.deepEqual([f.pepiniere, f.pleineTerre, f.plantation, f.rec, f.duree], [[], [], [], [], TIRET])
  assert.equal(zoneAffichable(null), null)
  assert.deepEqual(attributionsAffichables(null), [])
})

test('[CA8] zone et origine lisibles', () => {
  assert.deepEqual(zoneAffichable(reponse({}, { zone_climatique: 'continental', zone_climatique_origine: 'localisation' })),
    { zone: 'continental', origine: 'déduite de la localisation' })
  assert.equal(zoneAffichable(reponse({})).zone, 'méditerranéen')
})

test('[CA9] attributions dédoublonnées', () => {
  assert.deepEqual(attributionsAffichables(reponse({}, { attributions: ['WRG', 'WRG'] })), ['WRG'])
})

test('[CA11] une seule liste de cultures pour la lecture groupée', () => {
  const parcelles = [
    { cultures: [{ culture: 'tomate' }, { culture: 'ail' }] },
    { cultures: [{ culture: 'tomate' }] }, { cultures: [] },
  ]
  assert.deepEqual(culturesDuPlan(parcelles), ['tomate', 'ail'])
})

test('[CA13] la table provisoire a disparu du frontend', () => {
  const source = readFileSync(new URL('./calendrier.js', import.meta.url), 'utf-8')
  assert.equal(/plant:\s*\[/.test(source), false)
  assert.equal(/const CALENDRIER\s*=/.test(source), false)
})

test('[CA14] la frise historique se colore exactement comme avant', () => {
  const c = couleurDuMois({ semis: [2, 3], plant: [4, 5], rec: [5, 6] })
  assert.deepEqual([2, 4, 5, 6, 0].map(c), ['bg-blue', 'bg-brand', 'bg-amber', 'bg-amber', 'bg-card-alt'])
})
