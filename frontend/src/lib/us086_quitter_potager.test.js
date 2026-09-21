// [US-086] Quitter un potager dont on est membre — volet frontend, exécuté par
// `npm test` (`node --test`, même approche que us082_parametres_potager.test.js).
//
// Verrouille ce qui est vérifiable sans moteur de rendu : l'endpoint consommé
// (CA1), l'emplacement de l'action dans la zone sensible pour tout membre
// non-owner (CA6), le contenu de la confirmation (CA6), le rechargement qui
// reflète l'invalidation du potager actif (CA4/CA8) et la règle projet des
// container queries. L'apparence elle-même relève de la validation visuelle du QA.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')
const lireSrc = (chemin) => readFileSync(join(SRC, chemin), 'utf8')

const ECRAN = lireSrc('views/ParametresPotager.jsx')
const MODALE = lireSrc('components/ModalQuitterPotager.jsx')
const API = lireSrc('lib/api.js')

// ── CA1 — Endpoint consommé ─────────────────────────────────────────────────

test('[CA1] api.js expose POST /potagers/{id}/quitter', () => {
  assert.match(API, /quitterPotager: \(potagerId\) => post\(`\/potagers\/\$\{potagerId\}\/quitter`\)/)
})

test('[CA1] la confirmation appelle api.quitterPotager sur le potager ciblé', () => {
  assert.match(MODALE, /await api\.quitterPotager\(potagerId\)/)
})

// ── CA6 — Dans la zone sensible, pour tout membre non-owner ─────────────────

test("[CA6] l'onglet « Zone sensible » n'est plus réservé à l'owner : il dépend seulement du rôle connu", () => {
  assert.match(ECRAN, /ONGLETS\.filter\(\(o\) => role \|\| o\.cle !== 'sensible'\)/)
  assert.equal(/estOwner \|\| o\.cle !== 'sensible'/.test(ECRAN), false)
})

test("[CA6] « Quitter ce potager » n'est proposé qu'à un membre non-owner (l'owner garde archiver/supprimer)", () => {
  assert.match(ECRAN, /\{!estOwner && role && \(\s*<Card bg="bg-red-soft">/)
  const bloc = ECRAN.slice(ECRAN.indexOf('{!estOwner && role && ('), ECRAN.indexOf('{modaleSupprimer && ('))
  assert.match(bloc, /Quitter ce potager/)
  assert.match(bloc, /setModaleQuitter\(true\)/)
  // Le bloc de l'owner (archiver/désarchiver/supprimer) ne contient pas « Quitter ».
  const blocOwner = ECRAN.slice(
    ECRAN.search(/\{estOwner && \(\s*<Card bg="bg-red-soft">/),
    ECRAN.indexOf('{!estOwner && role && ('),
  )
  assert.ok(blocOwner.includes('Archiver ce potager'))
  assert.equal(/Quitter ce potager/.test(blocOwner), false)
})

test('[CA6] la confirmation rappelle qu\'il faudra une nouvelle invitation pour revenir', () => {
  assert.match(MODALE, /il te faudra une nouvelle invitation/)
})

test('[CA5] la confirmation rassure : rien n\'est effacé, les contributions restent au potager', () => {
  assert.match(MODALE, /Tes événements, parcelles et photos restent dans le potager/)
})

test('[CA6] le départ est annulable avant confirmation', () => {
  assert.match(MODALE, /<Btn kind="ghost" onClick=\{onClose\} disabled=\{loading\}>Annuler<\/Btn>/)
})

test('[CA2] un refus du serveur (dernier owner) s\'affiche dans la confirmation, sans la refermer', () => {
  assert.match(MODALE, /catch \(e\) \{\s*setError\(e\.message\)\s*setLoading\(false\)/)
  assert.match(MODALE, /\{error && <p className="text-red/)
})

// ── CA4 / CA8 — Effet immédiat ──────────────────────────────────────────────

test('[CA4] le départ recharge l\'app : elle repart des potagers restants ou du parcours d\'adhésion', () => {
  const bloc = ECRAN.slice(ECRAN.indexOf('{modaleQuitter && ('), ECRAN.indexOf('{modaleArchiver && ('))
  assert.match(bloc, /onQuitte=\{\(\) => \{\s*setModaleQuitter\(false\)\s*window\.location\.reload\(\)/)
})

// ── CA type — Lisible de 375 px au desktop, règle projet ────────────────────

test('[CA type] la zone sensible du non-owner reprend l\'habillage de celle de l\'owner (fond rouge doux, action bordée de rouge)', () => {
  const bloc = ECRAN.slice(ECRAN.indexOf('{!estOwner && role && ('), ECRAN.indexOf('{modaleSupprimer && ('))
  assert.match(bloc, /bg="bg-red-soft"/)
  assert.match(bloc, /text-red border-red\/30/)
  assert.match(MODALE, /text-red border-red\/40/)
})

test('[CA type] ni la confirmation ni la carte n\'utilisent de breakpoint d\'écran (container queries / flux naturel)', () => {
  assert.equal(/\b(sm|md|lg|xl):/.test(MODALE), false)
  const bloc = ECRAN.slice(ECRAN.indexOf('{!estOwner && role && ('), ECRAN.indexOf('{modaleSupprimer && ('))
  assert.equal(/\b(sm|md|lg|xl):/.test(bloc), false)
})
