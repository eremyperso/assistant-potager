// [US-302] Dicter une phrase au compagnon — la logique du bouton 🎤, sans navigateur (CA11).
//
// États, format d'enregistrement, durée maximale, messages d'empêchement : tout ce qui se décide
// se vérifie ici. Le branchement `getUserMedia` / `MediaRecorder` (hooks/useDictee.js) et le pied
// du panneau (PanneauCompagnon.jsx) sont vérifiés par lecture de leur source.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  ETAT, etatSuivant, affichageMicro, choisirTypeMime, extensionDictee, formaterDuree, dureeAtteinte,
  issueErreurMicro, noteErreurTranscription, issueTranscription, inscrireLecture, arreterLectures,
  capaciteDictee, TYPES_MIME_DICTEE, DUREE_DICTEE_MAX_S_DEFAUT, MESSAGE_MICRO_ABSENT,
  MESSAGE_CONNEXION_NON_SECURISEE, MESSAGE_DICTEE_NON_SUPPORTEE, TEXTE_MICRO_REFUSE,
  TEXTE_RIEN_ENTENDU, TEXTE_TROP_LONG, TEXTE_DICTEE_INDISPONIBLE, TEXTE_LIMITE_DICTEES,
  TEXTE_DUREE_MAX, LONGUEUR_MAX_DICTEE, EVENEMENT_PREFERENCES_VOIX,
} from './voix.js'
import { ajouterPhrase, LONGUEUR_MAX } from './compagnon.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')
const PANNEAU = lire('../components/PanneauCompagnon.jsx')
const HOOK = lire('../hooks/useDictee.js')
const SECTION = lire('../components/SectionVoix.jsx')
const API = lire('./api.js')
const CSS = lire('../index.css')

const enregistreur = (acceptes) => ({ isTypeSupported: (t) => acceptes.includes(t) })

// ── CA1 : le 🎤 n'existe qu'en mode vocal ────────────────────────────────────────────────

test('CA1 — mode vocal éteint : pas de 🎤, clavier seul', () => {
  const a = affichageMicro(ETAT.PRET, { modeVocal: false })
  assert.equal(a.bouton, false)
  assert.equal(a.saisie, true)
  assert.equal(a.envoiActif, true)
})

test('CA1 — mode vocal allumé : 🎤 à côté d’Envoyer, actif', () => {
  const a = affichageMicro(ETAT.PRET, { modeVocal: true })
  assert.equal(a.bouton, true)
  assert.equal(a.boutonActif, true)
  assert.equal(a.libelle, 'Dicter un message')
})

test('CA1 — le panneau lit le mode vocal et suit la section « Voix »', () => {
  assert.match(PANNEAU, /api\.preferencesVoix\(\)/)
  assert.match(PANNEAU, /addEventListener\(EVENEMENT_PREFERENCES_VOIX/)
  assert.match(SECTION, /dispatchEvent\(new CustomEvent\(EVENEMENT_PREFERENCES_VOIX/)
  assert.equal(EVENEMENT_PREFERENCES_VOIX, 'potager:preferences-voix')
})

test('CA1 — le 🎤 vit dans la saisie, en vue réduite comme en plein écran', () => {
  assert.match(PANNEAU, /\{micro\.bouton && \(/)
  assert.doesNotMatch(PANNEAU, /plein && micro\.bouton/)
})

test('CA1 — Gaston occupé : le 🎤 attend sa réponse', () => {
  assert.equal(affichageMicro(ETAT.PRET, { modeVocal: true, occupe: true }).boutonActif, false)
})

// ── CA2 : premier appui → micro demandé → écoute ; second appui → arrêt ─────────────────────

test('CA2 — appui, micro accordé, écoute, second appui : transcription', () => {
  let e = ETAT.PRET
  e = etatSuivant(e, 'appui'); assert.equal(e, ETAT.DEMANDE)
  e = etatSuivant(e, 'micro_accorde'); assert.equal(e, ETAT.ECOUTE)
  e = etatSuivant(e, 'appui'); assert.equal(e, ETAT.TRANSCRIPTION)
  e = etatSuivant(e, 'transcrit'); assert.equal(e, ETAT.PRET)
})

test('CA2 — en écoute, le bouton devient ⏹ « Arrêter la dictée et envoyer »', () => {
  const a = affichageMicro(ETAT.ECOUTE, { modeVocal: true })
  assert.equal(a.libelle, 'Arrêter la dictée et envoyer')
  assert.equal(a.boutonActif, true)
  assert.equal(a.saisie, false)
})

test('CA2 — la durée écoulée s’affiche en m:ss', () => {
  assert.equal(formaterDuree(0), '0:00')
  assert.equal(formaterDuree(7.8), '0:07')
  assert.equal(formaterDuree(60), '1:00')
  assert.equal(formaterDuree(-3), '0:00')
})

test('CA2 — le bandeau d’écoute et le statut « Vous écoute… » de la maquette', () => {
  assert.match(PANNEAU, /Écoute… <b className="tabular-nums">\{formaterDuree\(dictee\.ecouleS\)\}<\/b>/)
  assert.match(PANNEAU, /Vous écoute…/)
  assert.match(PANNEAU, /TEXTE_INDICE_ECOUTE/)
})

// ── CA3 : arrêt seul à la durée maximale ────────────────────────────────────────────────

test('CA3 — 60 s par défaut, arrêt seul à la durée maximale', () => {
  assert.equal(DUREE_DICTEE_MAX_S_DEFAUT, 60)
  assert.equal(dureeAtteinte(59.9), false)
  assert.equal(dureeAtteinte(60), true)
  assert.equal(dureeAtteinte(30, 30), true)
})

test('CA3 — la durée maximale part en transcription avec sa mention', () => {
  assert.equal(etatSuivant(ETAT.ECOUTE, 'duree_max'), ETAT.TRANSCRIPTION)
  assert.equal(TEXTE_DUREE_MAX, 'Durée maximale atteinte.')
  assert.match(HOOK, /arreter\('duree_max'\)/)
  assert.match(PANNEAU, /dictee_duree_max_s/)
})

// ── CA4 : transcription, aucun nouvel enregistrement, micro libéré ──────────────────────

test('CA4 — pendant la transcription, un appui ne relance rien', () => {
  assert.equal(etatSuivant(ETAT.TRANSCRIPTION, 'appui'), ETAT.TRANSCRIPTION)
  const a = affichageMicro(ETAT.TRANSCRIPTION, { modeVocal: true })
  assert.equal(a.boutonActif, false)
  assert.equal(a.envoiActif, false)
  assert.equal(a.libelle, 'Transcription en cours')
})

test('CA4 — le micro est libéré dès l’arrêt et au démontage', () => {
  assert.match(HOOK, /rec\.onstop = \(\) => \{[\s\S]*?libererMicro\(\)/)
  assert.match(HOOK, /getTracks\?\.\(\)\.forEach\(\(piste\) => \{ try \{ piste\.stop\(\)/)
  assert.match(HOOK, /return \(\) => \{\s*vivant\.current = false[\s\S]*?libererMicro\(\)/)
})

// ── CA5 : l'envoi du fichier ────────────────────────────────────────────────────────────

test('CA5 — le fichier part en multipart, avec sa durée, sans Content-Type JSON', () => {
  assert.match(API, /transcrireDictee: \(audio, nomFichier, dureeS\)/)
  assert.match(API, /formulaire\.append\('audio', audio, nomFichier\)/)
  assert.match(API, /formulaire\.append\('duree_s'/)
  assert.match(API, /postFormulaire\('\/compagnon\/voix\/transcrire'/)
  assert.match(API, /const \{ 'Content-Type': _json, \.\.\.entetes \} = headers\(\)/)
})

// ── CA6 : la phrase part à Gaston comme une phrase tapée, marquée 🎤 ──────────────────────

test('CA6 — la phrase transcrite part aussitôt par l’envoi habituel', () => {
  assert.equal(issueTranscription(' j’ai semé 30 graines ').envoyer, true)
  assert.equal(issueTranscription(' j’ai semé 30 graines ').phrase, 'j’ai semé 30 graines')
  assert.match(PANNEAU, /onTexte: \(phrase\) => envoyer\(phrase, undefined, true\)/)
  assert.match(PANNEAU, /api\.messageCompagnon\(phrase, modeForce \?\? mode\)/)
})

test('CA6 — la bulle d’une phrase dictée est marquée du micro', () => {
  const [bulle] = ajouterPhrase([], 'quand planter l’ail ?', 'j1', true)
  assert.deepEqual(bulle, { cle: 'j1', role: 'jardinier', texte: 'quand planter l’ail ?', dictee: true })
  const [tapee] = ajouterPhrase([], 'quand planter l’ail ?', 'j2')
  assert.equal(tapee.dictee, undefined)
  assert.match(PANNEAU, /entree\.dictee && \([\s\S]*?aria-label="Phrase dictée"/)
})

// ── CA7 : rien entendu, trop long ───────────────────────────────────────────────────────

test('CA7 — transcription vide : « Je n’ai rien entendu, réessayez », rien n’est envoyé', () => {
  const issue = issueTranscription('   ')
  assert.equal(issue.envoyer, false)
  assert.deepEqual(issue.note, { ton: 'info', texte: TEXTE_RIEN_ENTENDU })
  assert.equal(TEXTE_RIEN_ENTENDU, 'Je n’ai rien entendu, réessayez.')
})

test('CA7 — plus de 1 000 caractères : « Message trop long, découpez-le »', () => {
  assert.equal(LONGUEUR_MAX_DICTEE, LONGUEUR_MAX)
  assert.equal(issueTranscription('a'.repeat(1000)).envoyer, true)
  const issue = issueTranscription('a'.repeat(1001))
  assert.equal(issue.envoyer, false)
  assert.equal(issue.note.texte, TEXTE_TROP_LONG)
  assert.equal(noteErreurTranscription({ statut: 422, code: 'message_trop_long' }).texte, TEXTE_TROP_LONG)
})

// ── CA8 : micro refusé, absent, hors HTTPS, sans MediaRecorder ──────────────────────────

test('CA8 — micro refusé : dit comment le réautoriser, le 🎤 reste pour réessayer', () => {
  for (const name of ['NotAllowedError', 'SecurityError', 'PermissionDeniedError']) {
    const issue = issueErreurMicro({ name })
    assert.equal(issue.evenement, 'micro_refuse')
    assert.equal(issue.note.texte, TEXTE_MICRO_REFUSE)
    assert.equal(etatSuivant(ETAT.DEMANDE, issue.evenement), ETAT.PRET)
  }
  assert.match(TEXTE_MICRO_REFUSE, /réglages du navigateur/)
  assert.match(TEXTE_MICRO_REFUSE, /Réglages › Safari › Micro/)
})

test('CA8 — micro absent : explication à la place du 🎤', () => {
  const issue = issueErreurMicro({ name: 'NotFoundError' })
  assert.equal(issue.indisponible, MESSAGE_MICRO_ABSENT)
  const etat = etatSuivant(ETAT.DEMANDE, issue.evenement)
  assert.equal(etat, ETAT.INDISPONIBLE)
  assert.equal(affichageMicro(etat, { modeVocal: true }).bouton, false)
  assert.equal(affichageMicro(etat, { modeVocal: true }).saisie, true)
})

test('CA8 — hors HTTPS ou sans MediaRecorder : la dictée est impossible, dite en clair', () => {
  assert.equal(capaciteDictee({ isSecureContext: false, MediaRecorder: class {}, mediaDevices: {} }).message,
    MESSAGE_CONNEXION_NON_SECURISEE)
  assert.equal(capaciteDictee({ isSecureContext: true, mediaDevices: {} }).message, MESSAGE_DICTEE_NON_SUPPORTEE)
  assert.match(HOOK, /if \(!capacite\.possible\) \{\s*setIndisponible\(capacite\.message\)/)
  assert.match(PANNEAU, /<MicOff[\s\S]*?\{dictee\.indisponible\}/)
})

test('CA8 — la saisie au clavier reste toujours disponible hors écoute et transcription', () => {
  for (const etat of [ETAT.PRET, ETAT.DEMANDE, ETAT.INDISPONIBLE]) {
    assert.equal(affichageMicro(etat, { modeVocal: true }).saisie, true)
  }
})

// ── CA9 : Voxtral indisponible, la saisie en cours est gardée ───────────────────────────

test('CA9 — Voxtral indisponible : « écrivez votre message »', () => {
  for (const statut of [503, 500, undefined]) {
    assert.equal(noteErreurTranscription({ statut }).texte, TEXTE_DICTEE_INDISPONIBLE)
  }
  assert.equal(TEXTE_DICTEE_INDISPONIBLE, 'La dictée est indisponible pour le moment, écrivez votre message.')
  assert.equal(etatSuivant(ETAT.TRANSCRIPTION, 'echec'), ETAT.PRET)
})

test('CA9 — une phrase dictée ne vide pas la saisie au clavier en cours', () => {
  assert.match(PANNEAU, /if \(!dictee\) setTexte\(''\)/)
  assert.match(PANNEAU, /if \(dictee\) setTexte\(\(t\) => t \|\| phrase\)/)
})

// ── CA10 : la lecture s'arrête avant que le micro s'ouvre ───────────────────────────────

test('CA10 — un appui sur 🎤 arrête toute lecture en cours', () => {
  const arrets = []
  inscrireLecture(() => arrets.push('a'))
  const desinscrire = inscrireLecture(() => arrets.push('b'))
  desinscrire()
  inscrireLecture(() => { throw new Error('déjà finie') })
  assert.equal(arreterLectures(), 2)
  assert.deepEqual(arrets, ['a'])
  assert.equal(arreterLectures(), 0)
})

test('CA10 — les lectures sont arrêtées AVANT la demande du micro', () => {
  const i = HOOK.indexOf('arreterLectures()')
  const j = HOOK.indexOf('getUserMedia(')
  assert.ok(i > 0 && j > i)
})

// ── CA11 : le format selon le navigateur ────────────────────────────────────────────────

test('CA11 — Opus en premier, puis MP4 (Safari), puis Ogg', () => {
  assert.deepEqual(TYPES_MIME_DICTEE, ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg'])
  assert.equal(choisirTypeMime(enregistreur(['audio/webm;codecs=opus', 'audio/mp4'])), 'audio/webm;codecs=opus')
  assert.equal(choisirTypeMime(enregistreur(['audio/mp4'])), 'audio/mp4')       // Safari, iPhone, iPad
  assert.equal(choisirTypeMime(enregistreur(['audio/ogg'])), 'audio/ogg')
})

test('CA11 — sans isTypeSupported ou sans format connu : le navigateur choisit', () => {
  assert.equal(choisirTypeMime({}), '')
  assert.equal(choisirTypeMime(undefined), '')
  assert.equal(choisirTypeMime(enregistreur([])), '')
  assert.equal(choisirTypeMime({ isTypeSupported: () => { throw new Error('x') } }), '')
})

test('CA11 — l’extension du fichier suit le format réellement produit', () => {
  assert.equal(extensionDictee('audio/webm;codecs=opus'), 'webm')
  assert.equal(extensionDictee('audio/mp4;codecs=mp4a.40.2'), 'mp4')
  assert.equal(extensionDictee('audio/ogg;codecs=opus'), 'ogg')
  assert.equal(extensionDictee(''), 'webm')
  assert.match(HOOK, /rec\.mimeType \|\| typeMime/)
})

// ── CA12 : plafond du jour ──────────────────────────────────────────────────────────────

test('CA12 — plafond atteint (429) : « Limite de dictées du jour atteinte »', () => {
  assert.deepEqual(noteErreurTranscription({ statut: 429 }), { ton: 'warn', texte: TEXTE_LIMITE_DICTEES })
  assert.equal(TEXTE_LIMITE_DICTEES, 'Limite de dictées du jour atteinte.')
})

// ── CA13 : maquette, zones tactiles ─────────────────────────────────────────────────────

test('CA13 — 44 px en plein écran, 38 px sur ordinateur, conteneur du panneau', () => {
  assert.match(PANNEAU, /const tailleRonde = plein \? 'h-11 w-11' : 'h-\[38px\] w-\[38px\]'/)
  assert.match(PANNEAU, /@container\/compagnon/)
})

test('CA13 — couleurs de la maquette : orange vif pour le micro ouvert, pas de rouge', () => {
  assert.match(CSS, /--gst-rec: #C2410C;/)
  assert.match(CSS, /--gst-alerte-texte: #8A3B0B;/)
  assert.match(CSS, /--gst-info-texte: #1F4E7A;/)
  assert.match(CSS, /prefers-reduced-motion: reduce\) \{\s*\.dicte-point/)
})
