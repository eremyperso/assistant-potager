// [US-304] Écouter la réponse de Gaston au haut-parleur — `npm test`.
//
// CA10 : la règle de lecture automatique (dictée ? réglage ? message spontané ?) et l'état
// « une lecture à la fois » vivent dans `lib/voix.js`, vérifiés ici sans écran. Le câblage du
// panneau (▶ sous les réponses, 🎤 qui arrête la lecture, déverrouillage du son dans le geste) se
// vérifie par lecture du source, comme pour US-271 et US-302. Le volet serveur est couvert par
// `tests/test_us304_lecture_reponse.py`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  lectureAutomatique, porteLecture, boutonLecture, lectureSuivante, noteErreurLecture,
  creerCacheLectures, gastonParle, inscrireLecture, arreterLectures, ETAT_LECTURE_INITIAL,
  LIBELLE_ECOUTER, LIBELLE_ARRETER, LIBELLE_ANNULER, TEXTE_LECTURE_INDISPONIBLE,
  TEXTE_LIMITE_LECTURES, TEXTE_ECOUTER, TEXTE_EN_LECTURE, TEXTE_PREPARATION,
} from './voix.js'
import { ajouterEchange, filDepuisHistorique, fusionnerEtat } from './compagnon.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')
const PANNEAU = lire('../components/PanneauCompagnon.jsx')
const HOOK = lire('../hooks/useLecture.js')
const DICTEE = lire('../hooks/useDictee.js')
const API = lire('./api.js')
const APP = lire('../App.jsx')

const BASE = { modeVocal: true, lectureAuto: true, dictee: true, echangeId: 7 }
const avec = (...evenements) => evenements.reduce(lectureSuivante, ETAT_LECTURE_INITIAL)

// ── CA1 : la lecture se demande par identifiant d'échange ────────────────────
test('US-304 CA1 : POST /compagnon/voix/lecture/{echange_id}, sans texte envoyé', () => {
  assert.match(API, /lectureVoix: \(echangeId\) => postUrlAudio\(`\/compagnon\/voix\/lecture\/\$\{encodeURIComponent\(echangeId\)\}`\)/)
  assert.match(API, /async function postUrlAudio\(path\)[\s\S]*method: 'POST'[\s\S]*err\.statut = res\.status/)
})

test('US-304 CA1 : les réponses du fil portent leur échange (nouvelles et historique)', () => {
  const fil = ajouterEchange([], 'quand planter l’ail ?', { texte: 'En octobre.', vers: 'savoir', echange_id: 42 })
  assert.equal(fil.at(-1).echangeId, 42)
  const histo = filDepuisHistorique({ echanges: [{ jardinier: 'gel ?', compagnon: 'Samedi.', ts: 't', echange_id: 9 }] })
  assert.equal(histo.find((e) => e.role === 'compagnon').echangeId, 9)
})

// ── CA2, CA3, CA7 : la règle de lecture automatique ───────────────────────────
test('US-304 CA2 : phrase dictée, lecture automatique active → lue sans autre geste', () => {
  assert.equal(lectureAutomatique(BASE), true)
})

test('US-304 CA3 : une phrase tapée n’est jamais lue automatiquement', () => {
  assert.equal(lectureAutomatique({ ...BASE, dictee: false }), false)
})

test('US-304 CA3 : lecture automatique coupée, une phrase dictée ne l’est pas non plus', () => {
  assert.equal(lectureAutomatique({ ...BASE, lectureAuto: false }), false)
})

test('US-304 CA3 : sans mode vocal ou sans échange, rien n’est lu', () => {
  assert.equal(lectureAutomatique({ ...BASE, modeVocal: false }), false)
  assert.equal(lectureAutomatique({ ...BASE, echangeId: null }), false)
  assert.equal(lectureAutomatique({ ...BASE, echangeId: undefined }), false)
})

test('US-304 CA7 : un message spontané n’est jamais lu automatiquement', () => {
  assert.equal(lectureAutomatique({ ...BASE, spontane: true }), false)
})

// ── CA4, CA7 : le ▶ sous les réponses ────────────────────────────────────────
test('US-304 CA4 : mode vocal actif, chaque réponse rattachée à un échange porte le ▶', () => {
  assert.equal(porteLecture({ role: 'compagnon', texte: 'Oui.', echangeId: 3 }, true), true)
  assert.equal(porteLecture({ role: 'compagnon', texte: 'Oui.', echangeId: 3, resume: true }, true), true)
})

test('US-304 CA4 : pas de ▶ sans mode vocal, sans échange, ni sous une phrase du jardinier', () => {
  assert.equal(porteLecture({ role: 'compagnon', texte: 'Oui.', echangeId: 3 }, false), false)
  assert.equal(porteLecture({ role: 'compagnon', texte: 'Ce qui attend votre réponse :', echangeId: null }, true), false)
  assert.equal(porteLecture({ role: 'jardinier', texte: 'gel ?', echangeId: 3 }, true), false)
  assert.equal(porteLecture({ role: 'erreur', texte: 'Pas de réseau', echangeId: 3 }, true), false)
  assert.equal(porteLecture({ role: 'compagnon', texte: '', echangeId: 3 }, true), false)
})

test('US-304 CA7 : un message spontané porte le ▶ seulement s’il est rattaché à un échange', () => {
  assert.equal(porteLecture({ role: 'spontane', texte: 'Gel samedi.', echangeId: null }, true), false)
  assert.equal(porteLecture({ role: 'spontane', texte: 'Gel samedi.', echangeId: 5 }, true), true)
  const fil = filDepuisHistorique({ spontanes: [{ id: 1, texte: 'Gel samedi.' }] })
  assert.equal(porteLecture(fil[0], true), false)
  const relu = fusionnerEtat([], { spontanes: [{ id: 2, texte: 'Pluie.', echange_id: 11 }] })
  assert.equal(relu[0].echangeId, 11)
})

test('US-304 CA4, CA12 : ▶ « Écouter la réponse », ⏹ « Arrêter la lecture » pendant la lecture', () => {
  const repos = boutonLecture(ETAT_LECTURE_INITIAL, 3)
  assert.equal(repos.libelle, LIBELLE_ECOUTER)
  assert.equal(repos.libelle, 'Écouter la réponse')
  assert.equal(repos.texte, TEXTE_ECOUTER)
  assert.equal(repos.enLecture, false)

  const prepa = boutonLecture(avec({ type: 'appui', echangeId: 3 }), 3)
  assert.equal(prepa.chargement, true)
  assert.equal(prepa.libelle, LIBELLE_ANNULER)
  assert.equal(prepa.texte, TEXTE_PREPARATION)

  const lit = boutonLecture(avec({ type: 'appui', echangeId: 3 }, { type: 'pret', echangeId: 3 }), 3)
  assert.equal(lit.enLecture, true)
  assert.equal(lit.libelle, LIBELLE_ARRETER)
  assert.equal(lit.libelle, 'Arrêter la lecture')
  assert.equal(lit.texte, TEXTE_EN_LECTURE)
})

test('US-304 CA4 : appuyer sur ⏹ arrête la lecture', () => {
  const lit = avec({ type: 'appui', echangeId: 3 }, { type: 'pret', echangeId: 3 })
  const apres = lectureSuivante(lit, { type: 'appui', echangeId: 3 })
  assert.equal(apres.enCours, null)
})

// ── CA5 : une seule lecture à la fois ─────────────────────────────────────────
test('US-304 CA5 : ▶ sur une autre réponse arrête la première', () => {
  const premiere = avec({ type: 'appui', echangeId: 1 }, { type: 'pret', echangeId: 1 })
  const seconde = lectureSuivante(premiere, { type: 'appui', echangeId: 2 })
  assert.equal(seconde.enCours, 2)
  assert.equal(boutonLecture(seconde, 1).enLecture, false)
  // La fin (ou le chargement tardif) de la première ne touche pas à la seconde.
  assert.equal(lectureSuivante(seconde, { type: 'fin', echangeId: 1 }).enCours, 2)
  assert.equal(lectureSuivante(seconde, { type: 'pret', echangeId: 1 }).chargement, true)
  assert.equal(lectureSuivante(seconde, { type: 'erreur', echangeId: 1, note: 'x' }).enCours, 2)
})

test('US-304 CA5 : la lecture automatique remplace toujours la lecture en cours', () => {
  const lit = avec({ type: 'appui', echangeId: 1 }, { type: 'pret', echangeId: 1 })
  assert.equal(lectureSuivante(lit, { type: 'auto', echangeId: 1 }).enCours, 1)
  assert.equal(lectureSuivante(lit, { type: 'auto', echangeId: 4 }).enCours, 4)
})

test('US-304 CA5 : la fin de la lecture ou un arrêt ne laisse rien en cours', () => {
  const lit = avec({ type: 'appui', echangeId: 1 }, { type: 'pret', echangeId: 1 })
  assert.equal(lectureSuivante(lit, { type: 'fin', echangeId: 1 }).enCours, null)
  assert.equal(lectureSuivante(lit, { type: 'arret' }).enCours, null)
  assert.equal(lectureSuivante(ETAT_LECTURE_INITIAL, { type: 'arret' }), ETAT_LECTURE_INITIAL)
})

test('US-304 CA5 : le 🎤 arrête la lecture avant d’ouvrir le micro (registre partagé)', () => {
  let arretees = 0
  inscrireLecture(() => { arretees += 1 })
  assert.equal(arreterLectures(), 1)
  assert.equal(arretees, 1)
  assert.equal(arreterLectures(), 0)
  // La dictée appelle `arreterLectures` avant `getUserMedia` ; la lecture s'y inscrit dès le ▶.
  assert.ok(DICTEE.indexOf('arreterLectures()') < DICTEE.indexOf('await navigator.mediaDevices.getUserMedia'))
  assert.match(HOOK, /desinscrire\.current = inscrireLecture\(/)
})

test('US-304 CA5 : fermer le panneau ou changer de page arrête la lecture', () => {
  assert.match(HOOK, /return \(\) => \{ vivant\.current = false; couper\(\) \}/)
  assert.match(PANNEAU, /if \(vuePrecedente\.current !== vue\) arreterLecture\(\)/)
  assert.match(APP, /vue=\{view\}/)
})

test('US-304 CA5 : ▶ inactif pendant que le micro est ouvert', () => {
  assert.match(PANNEAU, /microOuvert=\{ecoute \|\| dictee\.etat === ETAT_DICTEE\.DEMANDE\}/)
  assert.match(PANNEAU, /disabled=\{bloque\}/)
})

// ── CA6 : cache de session, invalidé par un changement de voix ────────────────
test('US-304 CA6 : un MP3 déjà lu se réécoute sans nouvel appel', () => {
  const cache = creerCacheLectures(() => {})
  cache.voix('voice_592')
  assert.equal(cache.lire(3), null)
  cache.garder(3, 'blob:a')
  assert.equal(cache.lire(3), 'blob:a')
  assert.equal(cache.taille, 1)
})

test('US-304 CA6 : changer de voix invalide le cache (et libère les MP3)', () => {
  const liberes = []
  const cache = creerCacheLectures((url) => liberes.push(url))
  cache.voix('voice_592')
  cache.garder(3, 'blob:a')
  cache.garder(4, 'blob:b')
  assert.equal(cache.voix('voice_592'), false)
  assert.equal(cache.voix('voice_3137'), true)
  assert.equal(cache.lire(3), null)
  assert.deepEqual(liberes.sort(), ['blob:a', 'blob:b'])
})

test('US-304 CA6 : un MP3 demandé avec l’ancienne voix n’est pas gardé', () => {
  const liberes = []
  const cache = creerCacheLectures((url) => liberes.push(url))
  cache.voix('voice_592')
  cache.voix('voice_3137')
  assert.equal(cache.garder(3, 'blob:vieux', 'voice_592'), false)
  assert.equal(cache.lire(3), null)
  assert.deepEqual(liberes, ['blob:vieux'])
})

test('US-304 CA6 : le cache vit le temps de la page, pas du panneau', () => {
  // Créé au niveau du module, hors du composant : rouvrir le panneau le retrouve plein.
  assert.match(HOOK, /^const cache = creerCacheLectures\(\)$/m)
  assert.match(HOOK, /cache\.voix\(voixId \?\? null\)/)
})

// ── CA8, CA9 : échecs ─────────────────────────────────────────────────────────
test('US-304 CA8 : synthèse indisponible → « Lecture indisponible pour le moment » à côté du ▶', () => {
  assert.equal(noteErreurLecture({ statut: 503 }), TEXTE_LECTURE_INDISPONIBLE)
  assert.equal(noteErreurLecture(new Error('réseau')), 'Lecture indisponible pour le moment')
  const etat = avec({ type: 'appui', echangeId: 3 }, { type: 'erreur', echangeId: 3, note: TEXTE_LECTURE_INDISPONIBLE })
  const b = boutonLecture(etat, 3)
  assert.equal(b.texte, TEXTE_LECTURE_INDISPONIBLE)
  assert.equal(b.libelle, LIBELLE_ECOUTER)        // le ▶ reste là pour réessayer
  assert.equal(boutonLecture(etat, 4).note, null) // les autres réponses ne sont pas touchées
  // Réessayer efface la note.
  assert.equal(lectureSuivante(etat, { type: 'appui', echangeId: 3 }).notes[3], undefined)
})

test('US-304 CA9 : plafond atteint → « Limite de lectures du jour atteinte »', () => {
  assert.equal(noteErreurLecture({ statut: 429 }), TEXTE_LIMITE_LECTURES)
  assert.equal(TEXTE_LIMITE_LECTURES, 'Limite de lectures du jour atteinte')
})

// ── CA2, CA11 : iPhone, iPad, mode silencieux ─────────────────────────────────
test('US-304 CA2 : le tap sur 🎤 arrête la lecture PUIS déverrouille le son', () => {
  assert.match(PANNEAU, /appuyerDictee\(\)\s*\n\s*deverrouillerSon\(\)/)
  assert.equal((PANNEAU.match(/onClick=\{appuyerMicro\}/g) ?? []).length, 2)
  assert.doesNotMatch(PANNEAU, /onClick=\{dictee\.appuyer\}/)
})

test('US-304 CA2, CA11 : un seul élément <audio> pour la page, déverrouillé dans le geste ▶', () => {
  assert.match(HOOK, /let lecteur = null/)
  assert.match(HOOK, /if \(type === 'appui'\) deverrouillerSon\(\)/)
  assert.match(HOOK, /a\.src = SILENCE_WAV/)
})

test('US-304 CA11 : lecture refusée par le navigateur → pas d’erreur affichée', () => {
  assert.match(HOOK, /e\?\.name === 'NotAllowedError' \|\| e\?\.name === 'AbortError'\) finir\(\{ type: 'arret' \}\)/)
})

test('US-304 CA2 : l’en-tête dit « Parle… » pendant la lecture', () => {
  assert.equal(gastonParle(ETAT_LECTURE_INITIAL), false)
  assert.equal(gastonParle(avec({ type: 'auto', echangeId: 1 })), false)
  assert.equal(gastonParle(avec({ type: 'auto', echangeId: 1 }, { type: 'pret', echangeId: 1 })), true)
  assert.match(PANNEAU, /Parle…/)
})

test('US-304 CA2, CA3 : le panneau lit après une phrase dictée, selon la règle pure', () => {
  assert.match(PANNEAU, /lectureAutomatique\(\{ modeVocal, lectureAuto, dictee, echangeId: reponse\.echange_id \}\)/)
  assert.match(PANNEAU, /setLectureAuto\(p\?\.lecture_auto !== false\)/)
})

// ── CA12 : rendu ──────────────────────────────────────────────────────────────
test('US-304 CA12 : ligne d’écoute de la maquette (30 px, zone tactile de 44 px, égaliseur)', () => {
  assert.match(PANNEAU, /h-\[30px\] w-\[30px\]/)
  assert.match(PANNEAU, /after:-inset-\[7px\]/)
  assert.match(PANNEAU, /className="voix-eq"/)
  assert.match(PANNEAU, /aria-label=\{b\.libelle\}/)
})
