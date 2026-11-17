// [US-311] La coquille : formats, périodes, filtres dans l'adresse, navigation, client, écarts.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

import { nombre, entier, pourcent, compact, euro, heure, jourIso, jourCourt } from './format.js'
import { bornes, nbJours, PERIODES, estVueDuJour } from './periode.js'
import {
  depuisRecherche, versRecherche, versParametresApi, nombreFiltresActifs, perimetreParDefaut,
  pourListeDeModeles, FILTRES_DEFAUT, choixDeProvenance, provenanceDuChoix, CHOIX_PROVENANCE,
} from './filtres.js'
import { VUES, vueDepuisFragment, VUE_DEFAUT } from './navigation.js'
import { creerClient, ErreurApi, CLE_ACCES, CLE_RAFRAICHISSEMENT } from './client.js'
import { ecart, SENS } from './ecart.js'
import { rafraichissementAutomatique, INTERVALLE_MS, mentionAge } from './rafraichissement.js'

const NBSP = ' '

// ── Formats français ──────────────────────────────────────────────────────────────────────────
test('format : espace insécable entre milliers, virgule décimale, symbole après', () => {
  assert.equal(entier(1204), `1${NBSP}204`)
  assert.equal(entier(14820), `14${NBSP}820`)
  assert.equal(pourcent(0.684), `68,4${NBSP}%`)
  assert.equal(euro(42_000), `0,042${NBSP}€`)
  assert.equal(euro(1_500_000), `1,50${NBSP}€`)
  assert.equal(compact(2_310_000), `2,31${NBSP}M`)
  assert.equal(compact(814), '814')
  assert.equal(nombre(-4), '−4')
})

test('format : une valeur absente se lit « — », jamais « 0 » ni « NaN »', () => {
  for (const f of [entier, pourcent, compact, euro]) assert.equal(f(null), '—')
})

test('format : l\'heure et le jour sont ceux du navigateur, pas ceux d\'UTC', () => {
  assert.equal(heure(new Date(2026, 10, 10, 14, 32)), `14${NBSP}h${NBSP}32`)
  assert.equal(jourIso(new Date(2026, 10, 10, 23, 59)), '2026-11-10')
  assert.equal(jourCourt('2026-11-09'), 'lun. 9 nov.')
})

// ── Périodes ──────────────────────────────────────────────────────────────────────────────────
const AUJOURDHUI = new Date(2026, 10, 10, 9, 0)

test('période : cinq choix, dont aujourd\'hui, 7, 30, 90 jours et une personnalisée', () => {
  assert.deepEqual(PERIODES.map((p) => p.id), ['aujourdhui', '7j', '30j', '90j', 'perso'])
})

test('période : les bornes sont des dates incluses', () => {
  assert.deepEqual(bornes({ periode: 'aujourdhui' }, AUJOURDHUI), { depuis: '2026-11-10', jusqu_a: '2026-11-10' })
  assert.deepEqual(bornes({ periode: '7j' }, AUJOURDHUI), { depuis: '2026-11-04', jusqu_a: '2026-11-10' })
  assert.deepEqual(bornes({ periode: '90j' }, AUJOURDHUI), { depuis: '2026-08-13', jusqu_a: '2026-11-10' })
  assert.equal(nbJours('2026-11-04', '2026-11-10'), 7)
})

test('période : une personnalisée invalide retombe sur 7 jours', () => {
  assert.deepEqual(bornes({ periode: 'perso', depuis: '2026-11-10', jusqu_a: '2026-11-01' }, AUJOURDHUI),
    bornes({ periode: '7j' }, AUJOURDHUI))
  assert.deepEqual(bornes({ periode: 'perso', depuis: '2026-10-01', jusqu_a: '2026-10-15' }, AUJOURDHUI),
    { depuis: '2026-10-01', jusqu_a: '2026-10-15' })
})

// ── Filtres dans l'adresse [CA4] ──────────────────────────────────────────────────────────────
test('filtres : le défaut ne laisse aucune trace dans l\'adresse', () => {
  assert.equal(versRecherche(FILTRES_DEFAUT), '')
  assert.deepEqual(depuisRecherche(''), FILTRES_DEFAUT)
})

test('filtres : l\'adresse se relit à l\'identique (aller-retour)', () => {
  const filtres = { periode: 'perso', depuis: '2026-10-01', jusqu_a: '2026-10-15',
    provenance: ['mesure', 'test'], canal: 'pwa', modele: 'mistral/mistral-small-2603' }
  assert.deepEqual(depuisRecherche(versRecherche(filtres)), filtres)
})

test('filtres : une valeur inconnue ou piégée retombe sur le défaut', () => {
  const lu = depuisRecherche('?periode=n_importe_quoi&provenance=usage,pirate&canal=fax&depuis=x')
  assert.equal(lu.periode, '7j')
  assert.deepEqual(lu.provenance, ['usage'])
  assert.equal(lu.canal, '')
  assert.equal(depuisRecherche('?periode=perso&depuis=2026-11-10&jusqu_a=2026-11-01').periode, '7j')
})

test('filtres : paramètres de l\'API — le défaut (usage + fond) n\'est pas envoyé', () => {
  assert.deepEqual(versParametresApi(FILTRES_DEFAUT, AUJOURDHUI), { depuis: '2026-11-04', jusqu_a: '2026-11-10' })
  const filtre = { ...FILTRES_DEFAUT, provenance: ['mesure'], canal: 'pwa', modele: 'm' }
  assert.deepEqual(versParametresApi(filtre, AUJOURDHUI),
    { depuis: '2026-11-04', jusqu_a: '2026-11-10', provenance: 'mesure', canal: 'pwa', modele: 'm' })
})

test('filtres : le rappel de périmètre dépend de la seule provenance', () => {
  assert.equal(perimetreParDefaut(FILTRES_DEFAUT), true)
  assert.equal(perimetreParDefaut({ ...FILTRES_DEFAUT, provenance: ['mesure'] }), false)
  assert.equal(nombreFiltresActifs({ ...FILTRES_DEFAUT, provenance: ['mesure'], canal: 'pwa' }), 2)
  assert.equal(nombreFiltresActifs(FILTRES_DEFAUT), 0)
})

test('filtres : la liste des modèles ignore le filtre de modèle et regarde toutes les provenances', () => {
  const params = pourListeDeModeles({ ...FILTRES_DEFAUT, modele: 'm' }, AUJOURDHUI)
  assert.equal(params.modele, undefined)
  assert.equal(params.provenance, 'usage,fond,mesure,test,historique')
})

// ── Sélecteur de provenance (maquette d'US-318) ─────────────────────────────────────────────
test("provenance : un seul choix, qui retombe sur le filtre de l'API", () => {
  assert.deepEqual(CHOIX_PROVENANCE.map((c) => c.libelle), ['usage, fond', 'mesure', 'test', 'historique', 'toutes'])
  assert.deepEqual(provenanceDuChoix('defaut'), [])
  assert.deepEqual(provenanceDuChoix('mesure'), ['mesure'])
  assert.equal(provenanceDuChoix('toutes').length, 5)
  assert.deepEqual(provenanceDuChoix('n_importe_quoi'), [])
  for (const choix of CHOIX_PROVENANCE) assert.equal(choixDeProvenance(provenanceDuChoix(choix.id)), choix.id)
  assert.equal(choixDeProvenance(['usage', 'mesure']), 'autre')
})

// ── Navigation ────────────────────────────────────────────────────────────────────────────────
test('navigation : six vues, Consommation par défaut', () => {
  assert.deepEqual(VUES.map((v) => v.libelle), ['Consommation', 'Coût', 'Fiabilité', 'Dérives', 'Potagers', 'Seuils'])
  assert.deepEqual(VUES.map((v) => v.court), ['Conso', 'Coût', 'Fiabilité', 'Dérives', 'Potagers', 'Seuils'])   // barre basse
  assert.equal(VUES.find((v) => v.id === 'potagers').libelleLong, 'Potagers et jardiniers')            // bandeau
  assert.equal(vueDepuisFragment(''), VUE_DEFAUT)
  assert.equal(vueDepuisFragment('#/seuils'), 'seuils')
  assert.equal(vueDepuisFragment('#/inconnue'), VUE_DEFAUT)
})

// ── Client : connexion existante, aucune donnée sans accès ───────────────────────────────────
function stockage(initial = {}) {
  const m = new Map(Object.entries(initial))
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k), _m: m }
}
const reponse = (statut, corps) => ({
  ok: statut >= 200 && statut < 300, status: statut,
  json: async () => corps, clone() { return this },
})

test('client : réutilise le jeton du jardinier (mêmes clés) et appelle /auth/me sans toucher à /admin', async () => {
  const appels = []
  const client = creerClient({
    base: 'https://api', stockage: stockage({ [CLE_ACCES]: 'jeton-existant' }),
    fetchImpl: async (url, opts) => { appels.push([url, opts.headers.Authorization]); return reponse(200, { administrateur: false }) },
  })
  assert.equal(client.aUnJeton(), true)
  const moi = await client.moi()
  assert.equal(moi.administrateur, false)
  assert.deepEqual(appels, [['https://api/auth/me', 'Bearer jeton-existant']])
  assert.ok(appels.every(([url]) => !url.includes('/admin/')))
})

test('client : les paramètres vides ne sont pas envoyés', async () => {
  let vue
  const client = creerClient({ stockage: stockage({ [CLE_ACCES]: 'x' }), fetchImpl: async (url) => { vue = url; return reponse(200, {}) } })
  await client.appeler('/admin/pilotage/synthese', { depuis: '2026-11-01', canal: '', modele: undefined, provenance: null })
  assert.equal(vue, '/admin/pilotage/synthese?depuis=2026-11-01')
})

test('client : jeton expiré → un seul rafraîchissement puis la requête est rejouée', async () => {
  const s = stockage({ [CLE_ACCES]: 'vieux', [CLE_RAFRAICHISSEMENT]: 'r1' })
  let essais = 0
  const client = creerClient({
    stockage: s,
    fetchImpl: async (url, opts) => {
      if (url === '/auth/refresh') return reponse(200, { access_token: 'neuf', refresh_token: 'r2' })
      essais += 1
      return essais === 1 ? reponse(401, { detail: { code: 'token_expired' } }) : reponse(200, { ok: opts.headers.Authorization })
    },
  })
  assert.deepEqual(await client.appeler('/auth/me'), { ok: 'Bearer neuf' })
  assert.equal(s.getItem(CLE_ACCES), 'neuf')
})

test('client : session impossible à maintenir → jetons effacés et l\'appelant prévenu', async () => {
  const s = stockage({ [CLE_ACCES]: 'x' })
  let prevenu = false
  const client = creerClient({
    stockage: s, surSessionExpiree: () => { prevenu = true },
    fetchImpl: async () => reponse(401, { detail: { code: 'token_missing' } }),
  })
  await assert.rejects(client.appeler('/auth/me'), (e) => e instanceof ErreurApi && e.statut === 401)
  assert.equal(prevenu, true)
  assert.equal(client.aUnJeton(), false)
})

test('client : une API injoignable lève une erreur de statut 0 (hors ligne)', async () => {
  const client = creerClient({ stockage: stockage({ [CLE_ACCES]: 'x' }), fetchImpl: async () => { throw new TypeError('fetch failed') } })
  await assert.rejects(client.moi(), (e) => e.statut === 0)
})

test('client : 403 sur une route d\'administration est une erreur typée, pas une panne', async () => {
  const client = creerClient({ stockage: stockage({ [CLE_ACCES]: 'x' }), fetchImpl: async () => reponse(403, { detail: 'Réservé' }) })
  await assert.rejects(client.appeler('/admin/pilotage/synthese'), (e) => e.statut === 403 && e.message === 'Réservé')
})

test('client : la connexion enregistre les jetons sous les clés du jardinier', async () => {
  const s = stockage()
  const client = creerClient({ stockage: s, fetchImpl: async () => reponse(200, { access_token: 'a', refresh_token: 'r' }) })
  await client.connecter('admin@example.com', 'secret')
  assert.equal(s.getItem(CLE_ACCES), 'a')
  assert.equal(s.getItem(CLE_RAFRAICHISSEMENT), 'r')
})

// ── Écarts [US-312 / CA1] ─────────────────────────────────────────────────────────────────────
test('écart : +38 % de jetons d\'entrée est défavorable, et le dit en toutes lettres', () => {
  const e = ecart(2_310_000, 1_674_000, { sens: SENS.MAUVAISE })
  assert.equal(e.texte, `+38${NBSP}%`)
  assert.equal(e.jugement, 'defavorable')
  assert.equal(e.libelle, 'défavorable')
})

test('écart : le taux de cache se compare en points, une baisse est défavorable', () => {
  const e = ecart(0.58, 0.62, { sens: SENS.BONNE, mode: 'points' })
  assert.equal(e.texte, `−4${NBSP}points`)
  assert.equal(e.jugement, 'defavorable')
})

test('écart : un volume reste neutre, et sans période précédente l\'écart est « n/d »', () => {
  assert.equal(ecart(412, 368).jugement, 'neutre')
  assert.equal(ecart(412, 368).texte, `+12${NBSP}%`)
  assert.equal(ecart(5, 0).texte, 'n/d')
  assert.equal(ecart(null, 3).jugement, 'indisponible')
  assert.equal(ecart(0, 0).texte, `0${NBSP}%`)
})

// ── Rafraîchissement [CA5] ────────────────────────────────────────────────────────────────────
test('rafraîchissement : seulement la vue du jour, onglet visible, toutes les 60 secondes', () => {
  assert.equal(INTERVALLE_MS, 60_000)
  assert.equal(rafraichissementAutomatique({ periode: 'aujourdhui', visibilite: 'visible' }), true)
  assert.equal(rafraichissementAutomatique({ periode: 'aujourdhui', visibilite: 'hidden' }), false)
  assert.equal(rafraichissementAutomatique({ periode: '7j', visibilite: 'visible' }), false)
  assert.equal(estVueDuJour('7j'), false)
  assert.equal(mentionAge(new Date(), '14 h 32'), 'données de 14 h 32')
  assert.equal(mentionAge(null, ''), 'aucune donnée')
})

// ── Service worker [CA7] ──────────────────────────────────────────────────────────────────────
const sw = { module: { exports: {} }, URL }
vm.runInNewContext(readFileSync(fileURLToPath(new URL('../../public/sw.js', import.meta.url)), 'utf8'), sw)
const { strategie } = sw.module.exports
const PORTEE = 'https://potager.eremy.fr/pilotage/'

test('service worker : la coquille est mise en cache, jamais une réponse /admin/ ni /auth/', () => {
  assert.equal(strategie(`${PORTEE}assets/index-abc.js`, 'GET', 'no-cors', PORTEE), 'ressource')
  assert.equal(strategie(PORTEE, 'GET', 'navigate', PORTEE), 'navigation')
  assert.equal(strategie('https://potager.eremy.fr/admin/pilotage/synthese', 'GET', 'cors', PORTEE), 'ignorer')
  assert.equal(strategie(`${PORTEE}admin/pilotage/synthese`, 'GET', 'cors', PORTEE), 'ignorer')
  assert.equal(strategie('https://potager.eremy.fr/auth/me', 'GET', 'cors', PORTEE), 'ignorer')
})

test('service worker : hors portée, hors origine et hors GET, il ne touche à rien', () => {
  assert.equal(strategie('https://potager.eremy.fr/assets/app.js', 'GET', 'no-cors', PORTEE), 'ignorer')
  assert.equal(strategie('https://autre.example/pilotage/x.js', 'GET', 'no-cors', PORTEE), 'ignorer')
  assert.equal(strategie(`${PORTEE}assets/x.js`, 'POST', 'cors', PORTEE), 'ignorer')
})

test('manifeste : portée et départ limités à /pilotage/, installable', () => {
  const m = JSON.parse(readFileSync(fileURLToPath(new URL('../../public/manifest.webmanifest', import.meta.url)), 'utf8'))
  assert.equal(m.scope, '/pilotage/')
  assert.equal(m.start_url, '/pilotage/')
  assert.equal(m.display, 'standalone')
  assert.ok(m.icons.some((i) => i.sizes === '192x192') && m.icons.some((i) => i.sizes === '512x512'))
  assert.ok(m.icons.every((i) => i.src.startsWith('/pilotage/')))
})
