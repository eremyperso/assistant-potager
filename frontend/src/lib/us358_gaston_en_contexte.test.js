// [US-358] Gaston s'ouvre déjà renseigné — `npm test`.
//
// Ce qui se vérifie ici : la phrase d'ouverture et les suggestions se déduisent du contexte SANS
// modèle (CA2, CA3), « Pas encore » passe par une proposition à confirmer (CA4), le sujet d'une porte
// s'affiche sans jamais partir au serveur (CA6), la pastille de Noter et le bandeau disent la même
// culture (CA7), et chaque porte du CA1 est câblée.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  PHRASE_SANS_CONTEXTE, PHRASE_AJOUT, VARIETES_MAX, phraseOuverture, suggestionsDe, propositionDeReport,
  situationDEtape, sujetCatalogue, sujetSemer, sujetLot, sujetCulture, sujetAjout,
} from './ouvertureGaston.js'
import { RACCOURCI, SORTE } from './noter.js'
import {
  barreDeContexte, contexteAEnvoyer, ouvertureDuPanneau, pastilleNoter, ouvrirGastonSur, EVENEMENT_OUVRIR_COMPAGNON,
} from './contexteCompagnon.js'
import { phraseSemer, tuilesASemer, motDeSemer, motDuParcours } from './pepiniereSocle.js'
import { executerAction, normaliserMot } from './motDeGaston.js'
import { phraseAjouter } from './ficheCommune.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')
const SEMIS = [{ code: 'semee' }, { code: 'levee' }, { code: 'en_recolte' }, { code: 'terminee' }]
const PLANT = [{ code: 'plantee' }, { code: 'en_recolte' }, { code: 'terminee' }]
const culture = (nom, etapes) => ({ parcelleId: 2, parcelle: 'Planche centrale', rang: 6, culture: nom, etapes })
const FEVE_DUE = culture('fève', { serie_id: 7, etape: 'levee', a_confirmer: true, etapes: SEMIS })
const CHOU_RECOLTE = culture('chou de Bruxelles', { serie_id: 9, etape: 'en_recolte', a_confirmer: false, etapes: PLANT })
const libelles = (entree) => suggestionsDe(entree).map((s) => s.libelle)

// ── CA2 : la phrase d'ouverture, sans appel réseau ─────────────────────────────────────────────────────

test('[CA2] sans contexte : « Je vous écoute : une récolte, un semis, une observation, ou une culture à ajouter… »', () => {
  assert.equal(PHRASE_SANS_CONTEXTE, 'Je vous écoute : une récolte, un semis, une observation, ou une culture à ajouter…')
  assert.equal(phraseOuverture({}), PHRASE_SANS_CONTEXTE)
  assert.equal(phraseOuverture({ contexte: null, sujet: null }), PHRASE_SANS_CONTEXTE)
})

test('[CA2] culture à étape due : « Vous êtes sur fève. Dites ce que vous voyez, ou touchez une suggestion. »', () => {
  assert.equal(phraseOuverture({ contexte: FEVE_DUE }), 'Vous êtes sur fève. Dites ce que vous voyez, ou touchez une suggestion.')
})

test('[CA2] culture sans étape due : « Vous êtes sur chou de Bruxelles, en récolte. Une récolte, une observation ? »', () => {
  assert.equal(phraseOuverture({ contexte: CHOU_RECOLTE }),
    'Vous êtes sur chou de Bruxelles, en récolte. Une récolte, une observation ?')
})

test('[CA2] une culture terminée dit son état et propose de libérer le rang', () => {
  const c = culture('fève', { serie_id: 7, etape: 'terminee', etapes: PLANT })
  assert.match(phraseOuverture({ contexte: c }), /^Vous êtes sur fève, terminé\./)
})

test('[CA2] espèce du catalogue : la phrase de l’action est pré-écrite dans le champ, l’ouverture dit de l’envoyer', () => {
  const ligne = { culture: 'céleri-rave', nom: 'Céleri-rave', brut: { varietes: ['Monarch', 'Prinz'] } }
  const sujet = sujetCatalogue(ligne)
  const phrase = phraseAjouter('Céleri-rave', 'le céleri-rave')
  assert.equal(phrase, 'Ajouter le céleri-rave à mon potager')
  const ouverture = ouvertureDuPanneau({ contexte: null, sujet, champ: phrase })
  assert.equal(ouverture.champ.texte, 'Ajouter le céleri-rave à mon potager')
  assert.match(phraseOuverture({ contexte: null, sujet, champ: phrase }), /^Vous voulez ajouter le céleri-rave à votre potager\./)
})

test('[CA1] « Une culture absente du catalogue ? » : aucun contexte, phrase d’ouverture d’ajout', () => {
  const sujet = sujetAjout()
  assert.equal(phraseOuverture({ contexte: null, sujet }), PHRASE_AJOUT)
  assert.deepEqual(suggestionsDe({ contexte: null, sujet }), [])
  assert.equal(barreDeContexte(null, sujet).retirable, false)
})

test('[CA2] un lot, une culture sans place, une parcelle : où l’on est', () => {
  const lot = sujetLot({ numero: 12, culture: 'laitue', emplacement: 'Pépinière froide · pépinière froide' })
  assert.match(phraseOuverture({ sujet: lot }), /^Vous êtes sur le lot n° 12, laitue\./)
  assert.match(phraseOuverture({ sujet: sujetCulture('fève') }), /^Vous êtes sur fève\./)
  assert.match(phraseOuverture({ contexte: { parcelleId: 5, parcelle: 'Serre' } }), /^Vous êtes sur Serre\./)
})

// ── CA3 : les suggestions selon le contexte (fonction pure) ─────────────────────────────────────────────

test('[CA3] aucun contexte : Récolte, Semis, Observation — envoyés comme message', () => {
  assert.deepEqual(libelles({}), ['Récolte', 'Semis', 'Observation'])
  assert.ok(suggestionsDe({}).every((s) => s.sorte === SORTE.ENVOYER))
})

test('[CA3] étape due : « J’ai vu la levée », « Pas encore »', () => {
  assert.deepEqual(libelles({ contexte: FEVE_DUE }), ['J’ai vu la levée', 'Pas encore'])
  const [vu, pas] = suggestionsDe({ contexte: FEVE_DUE })
  assert.equal(vu.sorte, SORTE.ENVOYER)
  assert.equal(vu.raccourci, RACCOURCI.ETAPE_LEVEE)
  assert.equal(pas.sorte, SORTE.PAS_ENCORE)
})

test('[CA3] étape prévue : l’étape suivante, « Pas encore »', () => {
  const c = culture('fève', { serie_id: 7, etape: 'semee', a_confirmer: false, etapes: SEMIS })
  assert.equal(situationDEtape(c).sorte, 'prevue')
  assert.deepEqual(libelles({ contexte: c }), ['J’ai vu la levée', 'Pas encore'])
})

test('[CA3] en récolte : « Récolte » (attend la quantité), « Note » (pré-écrit le champ)', () => {
  const [recolte, note] = suggestionsDe({ contexte: CHOU_RECOLTE })
  assert.deepEqual([recolte.libelle, note.libelle], ['Récolte', 'Note'])
  assert.equal(recolte.sorte, SORTE.SAISIR)
  assert.equal(note.sorte, SORTE.REDIGER)
  assert.equal(note.debut, 'Note : ')
})

test('[CA3] terminé : « Libérer le rang », « Note »', () => {
  const c = culture('fève', { serie_id: 7, etape: 'terminee', etapes: PLANT })
  assert.deepEqual(libelles({ contexte: c }), ['Libérer le rang', 'Note'])
  assert.equal(suggestionsDe({ contexte: c })[0].raccourci, RACCOURCI.RANG_LIBERE)
})

test('[CA3] espèce du catalogue : rien avant la réponse de Gaston, puis les variétés du catalogue', () => {
  const sujet = sujetCatalogue({ culture: 'céleri-rave', nom: 'Céleri-rave', brut: { varietes: ['Monarch', 'Prinz'] } })
  assert.deepEqual(suggestionsDe({ sujet, repondu: false }), [])
  assert.deepEqual(libelles({ sujet, repondu: true }), ['Monarch', 'Prinz'])
  const beaucoup = sujetCatalogue({ culture: 'tomate', nom: 'Tomate', brut: { varietes: Array.from({ length: 20 }, (_, i) => `V${i}`) } })
  assert.equal(suggestionsDe({ sujet: beaucoup, repondu: true }).length, VARIETES_MAX)
})

// ── CA4 : « Pas encore » propose, il n'écrit pas ─────────────────────────────────────────────────────

test('[CA4] « Pas encore » : une proposition à confirmer visant la série et l’étape (US-320)', () => {
  const p = propositionDeReport(FEVE_DUE)
  assert.deepEqual([p.serieId, p.etape], [7, 'levee'])
  assert.match(p.texte, /la levée de fève/)
  assert.match(p.texte, /Rien n’est enregistré avant Confirmer/)
  assert.equal(propositionDeReport(culture('fève', null)), null)
})

test('[CA4] le panneau n’appelle le report qu’au « Confirmer », jamais à la suggestion', () => {
  const panneau = lire('../components/PanneauCompagnon.jsx')
  assert.equal((panneau.match(/api\.pasEncoreEtape\(/g) || []).length, 1)
  const confirmer = panneau.slice(panneau.indexOf('const confirmerReport'))
  assert.match(confirmer, /api\.pasEncoreEtape\(report\.serieId, report\.etape\)/)   // dans confirmerReport
  const toucher = panneau.slice(panneau.indexOf('const toucherPastille'), panneau.indexOf('const confirmerReport'))
  assert.doesNotMatch(toucher, /pasEncoreEtape/)
  assert.match(toucher, /setReport\(proposition\)/)
})

// ── CA6 : le contexte d'une porte est celui d'US-323 ───────────────────────────────────────────────────

test('[CA6] le sujet d’une porte s’affiche au bandeau, il ne part jamais au serveur', () => {
  const sujet = sujetCatalogue({ culture: 'céleri-rave', nom: 'Céleri-rave', brut: { varietes: [] } })
  const barre = barreDeContexte(null, sujet)
  assert.equal(barre.texte, 'Céleri-rave · catalogue')
  assert.equal(barre.retirable, true)
  assert.equal(contexteAEnvoyer(null), undefined)
  // Une culture + une parcelle : seuls les champs d'US-323 partent, l'étape et le sujet restent à l'écran.
  assert.deepEqual(contexteAEnvoyer({ ...FEVE_DUE, rang: 6 }), { parcelle_id: 2, culture: 'fève', rang: 6 })
})

test('[CA6] une porte sans parcelle : le lot, la tuile Semer, la culture sans place — jamais envoyés', () => {
  assert.equal(barreDeContexte(null, sujetLot({ numero: 12, culture: 'laitue', emplacement: 'Serre à semis' })).texte,
    'Lot n° 12 · Laitue · Serre à semis')
  assert.match(barreDeContexte(null, sujetSemer({ culture: 'oignon blanc', nom: 'Oignon blanc', fenetre: '1 sept. → 30 nov. · pépinière froide', varietes: ['de Paris'] })).texte,
    /^Oignon blanc · 1 sept\. → 30 nov\. · pépinière froide$/)
  assert.equal(barreDeContexte(null, sujetCulture('fève')).texte, 'Fève')
})

test('[CA6] retirer le contexte (×) retire aussi le sujet : le message suivant part sans contexte', () => {
  const app = lire('../App.jsx')
  assert.match(app, /setOuverture\(\{ barre: true, contexte, sujet: null, champ: null \}\)/)
  assert.match(app, /sujet=\{ouverture\.sujet\}/)
  assert.match(app, /champ=\{ouverture\.champ\}/)
})

test('[CA6] le panneau n’envoie le contexte que par `contexteAEnvoyer` (aucun champ nouveau)', () => {
  const panneau = lire('../components/PanneauCompagnon.jsx')
  assert.match(panneau, /barreContexte \? contexteAEnvoyer\(contexte\) : undefined/)
  assert.doesNotMatch(panneau, /sujet:\s*[a-z]+,\s*raccourci/)
})

// ── CA7 : la pastille de Noter et le bandeau montrent la même culture ──────────────────────────────────

test('[CA7] la pastille de Noter et le bandeau de contexte montrent la même culture', () => {
  for (const sel of [FEVE_DUE, CHOU_RECOLTE, culture('tomate cerise', null)]) {
    assert.equal(pastilleNoter(sel).emoji, barreDeContexte(sel).emoji, sel.culture)
    assert.equal(pastilleNoter(sel).sorte, 'culture')
  }
  assert.equal(pastilleNoter({ parcelleId: 5, parcelle: 'Serre' }).emoji, barreDeContexte({ parcelleId: 5, parcelle: 'Serre' }).emoji)
})

// ── CA1 : les portes ──────────────────────────────────────────────────────────────────────────────────

test('[CA1] « Semer » d’une tuile : « Semer l’oignon blanc de Paris en pépinière froide »', () => {
  assert.equal(phraseSemer({ culture: 'oignon blanc', varietes: ['de Paris'], type: 'pépinière froide' }),
    'Semer l’oignon blanc de Paris en pépinière froide')
  assert.equal(phraseSemer({ culture: 'oignon blanc', varietes: ['de Paris', 'rouge'], type: 'Pépinière froide' }),
    'Semer l’oignon blanc en pépinière froide')
  assert.equal(phraseSemer({ culture: 'mâche', varietes: [], type: '' }), 'Semer la mâche en pépinière')
  const [t] = tuilesASemer({ a_semer: [{ culture: 'oignon blanc', varietes_en_stock: ['de Paris'], confiance: { pepiniere: { libelle: 'pépinière froide' } } }] })
  assert.equal(t.type, 'pépinière froide')
})

test('[CA1] une action d’un Mot de Gaston porte son sujet et sa phrase jusqu’à Gaston', () => {
  const mot = motDeSemer({ a_semer: [{ culture: 'oignon blanc', jours_restants: 7, varietes_en_stock: ['de Paris'] }] })
  const action = mot.actions[0]
  assert.equal(action.libelle, 'Semer l’oignon blanc')
  assert.equal(action.phrase, 'Semer l’oignon blanc de Paris en pépinière')
  assert.equal(action.sujet.type, 'semer')
  const appels = []
  assert.equal(executerAction(action, { ouvrirGaston: (...a) => appels.push(a) }), 'noter')
  assert.deepEqual(appels[0], [null, action.phrase, action.sujet])
})

test('[CA1] « Ranger le chou-fleur » : le lot sans emplacement et sa phrase', () => {
  const lots = [{ lot_id: 4, culture: 'chou-fleur', numero_lot: 31 }]
  const mot = motDuParcours({ lots, alertes: new Map([[4, { code: 'sans_emplacement' }]]) })
  const ranger = mot.actions.find((a) => a.noter)
  assert.match(ranger.libelle, /^Ranger le chou-fleur$/)
  assert.equal(ranger.sujet.type, 'lot')
  assert.equal(ranger.sujet.numero, 31)
  assert.match(ranger.phrase, /^Ranger le chou-fleur$/)
})

test('[CA1] un Mot sans phrase ni sujet ouvre Gaston comme avant', () => {
  const mot = normaliserMot({ texte: 'Un mot.', actions: [{ libelle: 'Noter', noter: true }] })
  assert.equal(mot.actions[0].phrase, undefined)
  assert.equal(mot.actions[0].sujet, undefined)
})

test('[CA1] ouvrirGastonSur envoie contexte, sujet et phrase à la coquille', () => {
  const recus = []
  const cible = { dispatchEvent: (e) => recus.push(e) }
  globalThis.CustomEvent ??= class { constructor(type, init) { this.type = type; this.detail = init?.detail } }
  ouvrirGastonSur({ sujet: sujetAjout(), champ: 'Ajouter le céleri-rave à mon potager' }, cible)
  assert.equal(recus[0].type, EVENEMENT_OUVRIR_COMPAGNON)
  const ouverture = ouvertureDuPanneau(recus[0].detail)
  assert.equal(ouverture.barre, true)
  assert.equal(ouverture.contexte, null)
  assert.equal(ouverture.sujet.type, 'ajout')
  assert.equal(ouverture.champ.texte, 'Ajouter le céleri-rave à mon potager')
})

test('[CA1] chaque porte du cahier est câblée vers Gaston', () => {
  const fiche = lire('../components/FicheCommune.jsx')
  assert.match(fiche, /ouvrirGastonAvec\(\{ \.\.\.contexteNoter\(suivi\)/)          // Noter, Noter la levée
  assert.match(fiche, /ouvrirGastonSur\(\{ sujet: sujetCulture\(sel\.culture, sel\.variete\) \}\)/)   // culture sans place
  assert.match(lire('../components/FicheCatalogue.jsx'), /ouvrirGastonSur\(\{ sujet: sujetCatalogue\(ligne\), champ: phraseAjouter/)
  assert.match(lire('../views/Cultures.jsx'), /ouvrirGastonSur\(\{ sujet: sujetAjout\(\) \}\)/)
  assert.match(lire('../views/Pepiniere.jsx'), /onNoter=\{\(\) => ouvrirGastonSur\(\{ sujet: sujetLot\(/)
  assert.match(lire('../components/OngletSemer.jsx'), /ouvrirGastonSur\(\{ sujet: sujetSemer\(t\), champ: phraseSemer\(t\) \}\)/)
  assert.match(lire('../components/BandesFixes.jsx'), /ouvrirGaston: \(contexte, champ, sujet\) => ouvrirGastonSur\(\{ contexte, champ, sujet \}\)/)
  assert.match(lire('../components/BoutonNoter.jsx'), /ouvrirGastonAvec\(selection\)/)           // barre basse et bouton rond
})

// ── CA5, CA8 : l'ajout depuis le catalogue passe par le moteur existant ───────────────────────────────

test('[CA5] aucune ligne « Nouvelle culture » n’est fabriquée par le front : la carte vient du serveur', () => {
  for (const f of ['./carteAEnregistrer.js', '../components/CarteAEnregistrer.jsx', '../components/PanneauCompagnon.jsx']) {
    assert.doesNotMatch(lire(f), /Nouvelle culture/, f)
  }
})

test('[CA2] la phrase d’ouverture et les suggestions ne font aucun appel réseau', () => {
  const src = lire('./ouvertureGaston.js')
  assert.doesNotMatch(src, /fetch\(|api\.|import .*api\.js/)
})

test('[CA8] Telegram ne change pas : aucun fichier du bot ni du serveur n’est lu ici', () => {
  assert.doesNotMatch(lire('./ouvertureGaston.js'), /telegram/i)
})

// ── Panneau partagé : Noter depuis une fiche ouvre Gaston, il ne se referme pas (retour de recette 25/11) ───

import { occupantAFermer } from './coquille.js'

test('[CA1] Noter depuis une fiche : Gaston arrive, c’est la fiche qui se ferme', () => {
  const fiche = { cle: 'fiche' }
  // Avant : la fiche seule. Après : la fiche ET Gaston (Noter vient d'être touché).
  assert.equal(occupantAFermer({ gastonOuvert: true, occupant: fiche }, { gastonOuvert: false, occupant: fiche }), 'fiche')
})

test('[CA1] une fiche s’ouvre pendant que Gaston est ouvert : c’est Gaston qui se ferme', () => {
  assert.equal(occupantAFermer({ gastonOuvert: true, occupant: { cle: 'fiche' } }, { gastonOuvert: true, occupant: null }), 'gaston')
})

test('[CA1] aucun conflit : rien à fermer', () => {
  assert.equal(occupantAFermer({ gastonOuvert: true, occupant: null }, { gastonOuvert: false, occupant: null }), null)
  assert.equal(occupantAFermer({ gastonOuvert: false, occupant: { cle: 'fiche' } }, { gastonOuvert: false, occupant: null }), null)
})

test('[CA1] les deux arrivent dans le même rendu : Gaston l’emporte', () => {
  assert.equal(occupantAFermer({ gastonOuvert: true, occupant: { cle: 'f' } }, { gastonOuvert: false, occupant: null }), 'fiche')
})

test('[CA1] la coquille utilise cet arbitrage au lieu de deux règles indépendantes', () => {
  const app = lire('../App.jsx')
  assert.match(app, /occupantAFermer\(\{ gastonOuvert, occupant: occupantFiche \}, avantPanneau\.current\)/)
  assert.doesNotMatch(app, /if \(occupantFiche && gastonOuvert\) agirCompagnon\('fermer'\)/)
})

// ── Fiche d'un lot : le lien suit l'onglet d'où l'on vient (retour de recette 25/11) ───────────────────────

test('[CA1] la fiche d’un lot mène aux Lots depuis le Parcours, et au Parcours depuis les Lots', () => {
  const fiche = lire('../components/FicheLotCommune.jsx')
  assert.match(fiche, /const versLots = onglet !== 'lots' && onVoirLots/)
  assert.match(fiche, /onClick=\{versLots \? onVoirLots : onVoirParcours\}/)
  assert.match(fiche, /versLots \? 'Voir dans Lots' : 'Voir au Parcours'/)
  const vue = lire('../views/Pepiniere.jsx')
  assert.match(vue, /onglet=\{onglet\}/)
  // Le registre s'ouvre sur la colonne du lot, SANS filtrer par recherche (un seul lot laissait une page sans défilement) ;
  // le lot ouvert est amené en vue.
  assert.match(vue, /setEtat\(\{ onglet: 'lots', q: '', filtreLots: statutPepiniere\(fiche, alertes\) \}\)/)
  assert.match(lire('../components/OngletLots.jsx'), /querySelector\('\[data-lot-choisi\]'\)\?\.scrollIntoView/)
  assert.match(lire('../components/CarteLot.jsx'), /data-lot-choisi=\{choisie \? '' : undefined\}/)
})
