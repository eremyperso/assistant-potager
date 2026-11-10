// [US-301] Régler la voix de son compagnon dans la PWA — `npm test`.
//
// La logique (capacité de dictée, voix cochée, un extrait à la fois, retour d'enregistrement)
// se vérifie sans écran ; la mise en page (container queries, aucune alerte pour la liste de
// secours, section câblée dans « Mon compagnon ») par lecture du source, comme pour US-271.
// Le volet serveur (US-300) est couvert par `tests/test_us300_preferences_vocales.py`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  capaciteDictee, voixAffichees, alerteCatalogue, appliquerChangement, issueEnregistrement,
  extraitSuivant, sectionVisible, REGLAGES_PAR_DEFAUT, TEXTE_ENREGISTRE, TEXTE_ERREUR_RESEAU,
  TEXTE_MODE_VOCAL_ETEINT, DUREE_RETOUR_MS, texteEmpechementDictee,
  MESSAGE_CONNEXION_NON_SECURISEE, MESSAGE_DICTEE_NON_SUPPORTEE, SILENCE_WAV,
} from './voix.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')
const SECTION = lire('../components/SectionVoix.jsx')
const MODALE = lire('../components/ModalMonCompagnon.jsx')
const API = lire('./api.js')

const VOIX = [
  { id: 'voice_592', nom: 'Marie', genre: 'female' },
  { id: 'voice_3137', nom: 'Manon', genre: 'female' },
  { id: 'voice_589', nom: 'Léa', genre: 'female' },
  { id: 'voice_3141', nom: 'Camille', genre: 'female' },
]
const CAPABLE = { isSecureContext: true, MediaRecorder: class {}, mediaDevices: {} }

// ── CA1 : l'interrupteur « Mode vocal », éteint par défaut ──────────────────────────────

test('CA1 — le mode vocal est éteint par défaut, la lecture automatique active', () => {
  assert.equal(REGLAGES_PAR_DEFAUT.mode_vocal, false)
  assert.equal(REGLAGES_PAR_DEFAUT.lecture_auto, true)
})

test('CA1 — éteint, ni liste de voix ni lecture automatique : seul l’interrupteur est là', () => {
  const v = sectionVisible({ ...REGLAGES_PAR_DEFAUT }, capaciteDictee(CAPABLE))
  assert.equal(v.interrupteurMode, true)
  assert.equal(v.listeDesVoix, false)
  assert.equal(v.interrupteurLecture, false)
  assert.equal(v.avertissementDictee, null)
})

test('CA1 — la section propose l’interrupteur « Mode vocal » (role switch)', () => {
  assert.match(SECTION, /libelle="Mode vocal"/)
  assert.match(SECTION, /role="switch"/)
  assert.match(SECTION, /aria-checked=\{actif\}/)
})

// ── CA2 : la liste des voix, la voix choisie cochée ─────────────────────────────────────

test('CA2 — allumé, la liste des voix apparaît avec le nom de chacune', () => {
  const v = sectionVisible({ mode_vocal: true, voix_id: 'voice_592', lecture_auto: true }, capaciteDictee(CAPABLE))
  assert.equal(v.listeDesVoix, true)
  assert.deepEqual(voixAffichees({ voix: VOIX }, 'voice_592').map((x) => x.nom), ['Marie', 'Manon', 'Léa', 'Camille'])
})

test('CA2 — la voix choisie est la seule cochée', () => {
  const affichees = voixAffichees({ voix: VOIX }, 'voice_589')
  assert.deepEqual(affichees.filter((x) => x.cochee).map((x) => x.nom), ['Léa'])
})

test('CA2 — sans catalogue, aucune voix (et pas d’exception)', () => {
  assert.deepEqual(voixAffichees(null, 'voice_592'), [])
  assert.deepEqual(voixAffichees({ voix: [] }, null), [])
})

test('CA2 — le catalogue n’est lu qu’une fois le mode vocal allumé', () => {
  assert.match(SECTION, /if \(!modeVocal \|\| catalogue\) return/)
  // Maquette : de vrais boutons radio dans un fieldset nommé « Voix de Gaston », la ligne entière cliquable.
  assert.match(SECTION, /<fieldset/)
  assert.match(SECTION, /<legend[^>]*>Voix de Gaston<\/legend>/)
  assert.match(SECTION, /type="radio"/)
  assert.match(SECTION, /name="voix-gaston"/)
  assert.doesNotMatch(SECTION, /role="radio"/)
})

// ── CA3 : ▶ par voix, un seul extrait à la fois, iPhone ─────────────────────────────────

test('CA3 — lancer un autre extrait arrête le précédent ; relancer le même l’arrête', () => {
  assert.equal(extraitSuivant(null, 'voice_592'), 'voice_592')
  assert.equal(extraitSuivant('voice_592', 'voice_3137'), 'voice_3137')
  assert.equal(extraitSuivant('voice_592', 'voice_592'), null)
})

test('CA3 — le tap sur ▶ déverrouille le son avant tout aller-retour réseau', () => {
  const ordre = SECTION.indexOf('new Audio(SILENCE_WAV)')
  assert.ok(ordre > 0, 'un élément audio est créé avec un silence dans le geste')
  assert.ok(SECTION.indexOf('audio.play().catch') > ordre)
  assert.ok(SECTION.indexOf('await api.extraitVoix') > SECTION.indexOf('audio.play().catch'),
    'play() précède le chargement de l’extrait')
})

test('CA3 — le silence de déverrouillage est un WAV valide de 0,1 s', () => {
  const brut = Buffer.from(SILENCE_WAV.split(',')[1], 'base64')
  assert.equal(brut.toString('ascii', 0, 4), 'RIFF')
  assert.equal(brut.toString('ascii', 8, 12), 'WAVE')
  assert.equal(brut.readUInt32LE(4), brut.length - 8)
  assert.equal(brut.readUInt32LE(40), brut.length - 44)
  assert.equal(brut.readUInt32LE(24), 8000)
})

test('CA3 — un bouton ▶ par voix, nommé pour les lecteurs d’écran', () => {
  assert.match(SECTION, /Écouter l’extrait de \$\{v\.nom\}/)
  assert.match(SECTION, /Arrêter l’extrait/)
  assert.match(SECTION, /<Play /)
})

test('CA3 — l’extrait est une URL d’objet révoquée à l’arrêt', () => {
  assert.match(API, /URL\.createObjectURL\(await res\.blob\(\)\)/)
  assert.match(SECTION, /URL\.revokeObjectURL/)
  assert.match(API, /extraitVoix:\s+\(voixId\) => getUrlAudio\(`\/compagnon\/voix\/catalogue\/\$\{encodeURIComponent\(voixId\)\}\/extrait`\)/)
})

// ── CA4 : lecture automatique ────────────────────────────────────────────────────────────

test('CA4 — l’interrupteur « Lire les réponses après une dictée » règle lecture_auto', () => {
  assert.match(SECTION, /libelle="Lire les réponses après une dictée"/)
  assert.match(SECTION, /changer\(\{ lecture_auto: v \}\)/)
  const v = sectionVisible({ mode_vocal: true, voix_id: null, lecture_auto: false }, capaciteDictee(CAPABLE))
  assert.equal(v.interrupteurLecture, true)
})

// ── CA5 : enregistrement immédiat, retour « Enregistré », retour arrière ────────────────

test('CA5 — un changement s’applique tout de suite puis se confirme par « Enregistré »', () => {
  const avant = { mode_vocal: false, voix_id: 'voice_592', lecture_auto: true }
  assert.deepEqual(appliquerChangement(avant, { mode_vocal: true }), { ...avant, mode_vocal: true })
  const ok = issueEnregistrement(true, avant, { mode_vocal: true, voix_id: 'voice_592', lecture_auto: true })
  assert.equal(ok.message, TEXTE_ENREGISTRE)
  assert.equal(ok.message, 'Enregistré')
  assert.equal(ok.erreur, false)
  assert.equal(ok.reglages.mode_vocal, true)
})

test('CA5 — une erreur réseau le dit et remet l’état précédent', () => {
  const avant = { mode_vocal: false, voix_id: 'voice_592', lecture_auto: true }
  const ko = issueEnregistrement(false, avant)
  assert.equal(ko.message, TEXTE_ERREUR_RESEAU)
  assert.equal(ko.erreur, true)
  assert.deepEqual(ko.reglages, avant)
})

test('CA5 — chaque changement part au serveur sans bouton « Enregistrer »', () => {
  assert.match(SECTION, /api\.enregistrerPreferencesVoix\(changement\)/)
  assert.match(SECTION, /role="status"/)
  assert.doesNotMatch(SECTION, /Enregistrer</)
  assert.match(API, /enregistrerPreferencesVoix:\s+\(reglages\) => put\('\/compagnon\/voix\/preferences', reglages\)/)
})

// ── CA6 : navigateur sans enregistrement ou page hors HTTPS ─────────────────────────────

test('CA6 — hors connexion sécurisée, la section le dit en clair', () => {
  const c = capaciteDictee({ ...CAPABLE, isSecureContext: false })
  assert.equal(c.possible, false)
  assert.ok(c.message.startsWith('La dictée demande une connexion sécurisée'))
  assert.equal(MESSAGE_CONNEXION_NON_SECURISEE, 'La dictée demande une connexion sécurisée')
})

test('CA6 — sans MediaRecorder, la section le dit en clair', () => {
  for (const env of [{ ...CAPABLE, MediaRecorder: undefined }, { ...CAPABLE, mediaDevices: undefined }]) {
    const c = capaciteDictee(env)
    assert.equal(c.possible, false)
    assert.equal(c.message, MESSAGE_DICTEE_NON_SUPPORTEE)
  }
  assert.equal(MESSAGE_DICTEE_NON_SUPPORTEE, 'Ce navigateur ne permet pas la dictée')
})

test('CA6 — la connexion non sécurisée est dite avant le navigateur', () => {
  assert.equal(capaciteDictee({ isSecureContext: false }).message, MESSAGE_CONNEXION_NON_SECURISEE)
})

test('CA6 — navigateur capable : aucun message', () => {
  assert.deepEqual(capaciteDictee(CAPABLE), { possible: true, message: null })
})

test('CA6 — le message n’apparaît que mode vocal allumé, et la lecture reste réglable', () => {
  const impossible = capaciteDictee({ isSecureContext: false })
  assert.equal(sectionVisible({ ...REGLAGES_PAR_DEFAUT }, impossible).avertissementDictee, null)
  const allume = sectionVisible({ mode_vocal: true, voix_id: null, lecture_auto: true }, impossible)
  assert.equal(allume.avertissementDictee, MESSAGE_CONNEXION_NON_SECURISEE)
  assert.equal(allume.interrupteurLecture, true)
  assert.equal(allume.listeDesVoix, true)
})

test('CA6 — sans navigateur (rendu serveur), pas d’exception', () => {
  assert.equal(capaciteDictee().possible, false)
})

// ── CA7 : la liste de secours sans alerte ───────────────────────────────────────────────

test('CA7 — le catalogue de secours s’affiche comme les autres, sans alerte', () => {
  assert.equal(alerteCatalogue({ voix: VOIX, liste_de_secours: true }), null)
  assert.deepEqual(voixAffichees({ voix: VOIX, liste_de_secours: true }, 'voice_592').length, 4)
  assert.doesNotMatch(SECTION, /catalogue\??\.liste_de_secours/, 'le composant ne lit même pas le drapeau')
  assert.doesNotMatch(SECTION, /role="alert"/)
})

// ── CA8 : container queries, câblage dans la fenêtre « Mon compagnon » ──────────────────

test('CA8 — la section vit dans le conteneur de la fenêtre, sans breakpoint de page', () => {
  assert.match(MODALE, /@container\/compagnon/)
  assert.match(MODALE, /import SectionVoix from '\.\/SectionVoix\.jsx'/)
  assert.match(MODALE, /<SectionVoix \/>/)
  assert.doesNotMatch(SECTION, /\b(sm|md|lg|xl):/, 'les breakpoints Tailwind sont réservés à la structure de page')
})

test('CA8 — les zones de toucher font au moins 32 px (bouton ▶ et interrupteur)', () => {
  // Maquette : interrupteur 50 × 30, ▶ de 44 px (fenêtre étroite) puis 40 px, ligne de voix de 56 px.
  assert.match(SECTION, /w-\[50px\] h-\[30px\]/)
  assert.match(SECTION, /w-11 h-11 @\[420px\]\/compagnon:w-10 @\[420px\]\/compagnon:h-10/)
  assert.match(SECTION, /min-h-\[56px\]/)
})

// ── API ─────────────────────────────────────────────────────────────────────────────────

test('API — les quatre appels de la voix pointent sur les routes d’US-300', () => {
  assert.match(API, /preferencesVoix:\s+\(\) => get\('\/compagnon\/voix\/preferences'\)/)
  assert.match(API, /catalogueVoix:\s+\(\) => get\('\/compagnon\/voix\/catalogue'\)/)
})

// ── CA8 : fidélité à la maquette « Compagnon - Voix » ────────────────────────────────────

test('CA8 — les textes de la maquette, mot pour mot', () => {
  assert.equal(TEXTE_ENREGISTRE, 'Enregistré')
  assert.equal(TEXTE_ERREUR_RESEAU, 'Non enregistré : pas de réseau')
  assert.equal(TEXTE_MODE_VOCAL_ETEINT, 'Activez-le pour dicter vos phrases à Gaston et écouter ses réponses.')
  assert.equal(DUREE_RETOUR_MS, 2000)
  assert.equal(
    texteEmpechementDictee(MESSAGE_CONNEXION_NON_SECURISEE),
    'La dictée demande une connexion sécurisée. La lecture des réponses reste disponible.')
  assert.equal(
    texteEmpechementDictee(MESSAGE_DICTEE_NON_SUPPORTEE),
    'Ce navigateur ne permet pas la dictée. La lecture des réponses reste disponible.')
})

test('CA8 — libellés et aides de la section', () => {
  assert.match(SECTION, /aide="Micro et lecture des réponses de Gaston\."/)
  assert.match(SECTION, /aide="Les phrases tapées ne sont jamais lues automatiquement\."/)
  assert.match(SECTION, /par défaut/)
  assert.match(SECTION, /\{TEXTE_MODE_VOCAL_ETEINT\}/)
})

test('CA8 — le titre est en Lora 18 px et « Enregistré » s’affiche à droite, 2 s', () => {
  assert.match(SECTION, /<h3 className="font-serif text-\[18px\]/)
  assert.match(SECTION, /ml-auto/)
  assert.match(SECTION, /setTimeout\(\(\) => setRetour\(null\), DUREE_RETOUR_MS\)/)
})

test('CA8 — voix cochée surlignée, ▶ plein devenant ⏹ pendant la lecture, égaliseur animé', () => {
  assert.match(SECTION, /v\.cochee \? 'bg-brand-soft'/)
  assert.match(SECTION, /bg-brand-deep border-brand-deep/)
  assert.match(SECTION, /<Egaliseur \/>/)
  const css = lire('../index.css')
  assert.match(css, /\.voix-eq i \{[^}]*animation: voix-eq/)
  assert.match(css, /prefers-reduced-motion[^}]*\.voix-eq i \{ animation: none/)
})

test('CA8 — encadré d’information bleu (dictée impossible), avertissement orange (non enregistré)', () => {
  assert.match(SECTION, /bg-blue-soft text-blue/)
  assert.match(SECTION, /bg-amber-soft text-amber/)
  assert.match(SECTION, /texteEmpechementDictee\(visible\.avertissementDictee\)/)
  assert.match(SECTION, /retour\.erreur \? 'text-amber' : 'text-brand-text'/)
})

// ── Défauts trouvés à la recette visuelle du 09/11 ───────────────────────────────────────

test('recette — le rond de l’interrupteur a une seule position à la fois (gauche OU droite)', () => {
  assert.match(SECTION, /actif \? 'left-\[23px\]' : 'left-\[3px\]'/)
  assert.doesNotMatch(SECTION, /absolute top-\[3px\] left-\[3px\]/, 'left-[3px] fixe écrase left-[23px] à l’état allumé')
})

test('recette — la fin de l’extrait n’est écoutée qu’une fois l’extrait réel chargé', () => {
  const src = SECTION.indexOf('audio.src = url')
  const fin = SECTION.indexOf("audio.addEventListener('ended'")
  assert.ok(src > 0 && fin > src, 'sinon le silence de déverrouillage (0,1 s) arrête la lecture avant son début')
})

// ── CA8 : la fenêtre « Mon compagnon » d'après la maquette « Compagnon - Voix » ──────────

const MODAL = lire('../components/ui/Modal.jsx')

test('maquette — en-tête : visage de Gaston, titre Lora 20 px, fermer rond (44 px, 40 px dès 600 px)', () => {
  assert.match(MODALE, /import \{ VisageGaston \} from '\.\/Gaston\.jsx'/)
  assert.match(MODALE, /<VisageGaston \/>/)
  assert.match(MODALE, /w-11 h-11 rounded-full bg-\[#FBF3D1\]/)
  assert.match(MODALE, /font-serif text-\[20px\] font-bold/)
  assert.match(MODALE, /w-11 h-11 min-\[600px\]:w-10 min-\[600px\]:h-10 rounded-full bg-card-alt/)
  assert.match(MODALE, /entete=\{false\}/)
  assert.doesNotMatch(MODALE, /icon=\{NotebookPen\}|sub="Ce qu'il retient de vous"/)
})

test('maquette — Niveau, Objectifs et Carnet sont des lignes repliées de 52 px, dépliables', () => {
  assert.match(MODALE, /function LigneRepliable/)
  assert.match(MODALE, /min-h-\[52px\]/)
  assert.match(MODALE, /aria-expanded=\{ouvert\}/)
  for (const id of ['niveau', 'objectifs', 'carnet']) assert.match(MODALE, new RegExp(`id="${id}"`))
  assert.match(MODALE, /useState\(null\)\s*\/\/ 'niveau'/, 'tout est replié à l’ouverture')
  assert.match(MODALE, /<ChevronRight/)
})

test('maquette — plus de pied de fenêtre ; la phrase d’accord vit dans le carnet', () => {
  assert.doesNotMatch(MODALE, /\bfoot=/)
  assert.match(MODALE, /Rien n'est retenu sans votre accord/)
})

test('maquette — plein écran sous 600 px, fenêtre centrée de 480 px au-delà (arrondi 20 px)', () => {
  assert.match(MODALE, /disposition="plein_mobile"/)
  assert.match(MODALE, /width=\{480\}/)
  assert.match(MODAL, /plein_mobile: \{/)
  assert.match(MODAL, /min-\[600px\]:rounded-\[20px\]/)
  assert.match(MODAL, /min-\[600px\]:max-w-\[var\(--modal-largeur-desktop\)\]/)
  assert.match(MODAL, /disposition === 'adaptative' \|\| disposition === 'plein_mobile'/)
})

test('maquette — l’en-tête respecte la zone sûre du téléphone', () => {
  assert.match(MODALE, /pt-\[max\(14px,env\(safe-area-inset-top\)\)\]/)
})
