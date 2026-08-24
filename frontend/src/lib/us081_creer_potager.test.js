// [US-081] Créer un potager additionnel depuis la PWA — volet frontend,
// exécuté par `npm test` (`node --test`, sans dépendance de test supplémentaire,
// même approche que us064_dette_alias.test.js).
//
// Verrouille mécaniquement ce qui est vérifiable sans moteur de rendu : présence
// du point d'entrée (CA1), composition de la modale (CA2, CA3, CA6),
// réutilisation du design system et règle projet des container queries.
// L'apparence elle-même relève de la validation visuelle du QA.
//
// [Refonte visuelle 2026] CA8 (miroir dans « Tous mes potagers ») retiré avec
// l'entrée elle-même : la liste des potagers en tête de `PotagerMenu` remplit
// déjà ce rôle, et `PotagerSelector.jsx` (Lot D, jamais migré au design
// system) a été supprimé plutôt que laissé orphelin.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')
const lireSrc = (chemin) => readFileSync(join(SRC, chemin), 'utf8')

const MODALE = lireSrc('components/ModalCreerPotager.jsx')
const MENU = lireSrc('components/PotagerMenu.jsx')
const CONTEXTE = lireSrc('context/PotagerContext.jsx')
const API = lireSrc('lib/api.js')

// ── CA1 — Entrée dans le menu potager ──────────────────────────────────────

test("[CA1] PotagerMenu propose « Créer un nouveau potager »", () => {
  assert.match(MENU, /label="Créer un nouveau potager"/)
  assert.match(MENU, /ModalCreerPotager/)
})

test("[CA1] l'entrée est placée après la liste des potagers et avant « Rejoindre un potager »", () => {
  const liste = MENU.indexOf('potagers.map(')
  const creer = MENU.indexOf('label="Créer un nouveau potager"')
  const rejoindre = MENU.indexOf('label="Rejoindre un potager"')
  assert.ok(liste !== -1 && creer !== -1 && rejoindre !== -1)
  assert.ok(liste < creer, "l'entrée doit venir après la liste des potagers")
  assert.ok(creer < rejoindre, "l'entrée doit précéder Rejoindre un potager")
})

test("[CA1] l'entrée ne dépend d'aucun rôle, contrairement à « Modifier le potager »", () => {
  // « Modifier le potager » est gardé par `potagerActif.role === 'owner'` (US-074) ;
  // créer SON propre potager ne dépend d'aucun rôle sur le potager courant.
  const garde = MENU.indexOf("potagerActif.role === 'owner'")
  const creer = MENU.indexOf('label="Créer un nouveau potager"')
  assert.ok(garde === -1 || creer < garde, "l'entrée de création ne doit pas être sous la garde owner")
})

// ── CA2 — Modale légère : nom + ville, rien d'autre ────────────────────────

test('[CA2] la modale demande un nom requis et réutilise VilleSearch', () => {
  assert.match(MODALE, /id="creer-potager-nom"/)
  assert.match(MODALE, /required/)
  assert.match(MODALE, /<VilleSearch/)
})

test('[CA2] aucune étape parcelles ni cultures', () => {
  assert.equal(/parcelle/i.test(MODALE.replace(/\/\/.*|\/\*[\s\S]*?\*\//g, '')), false)
  assert.equal(/culture/i.test(MODALE.replace(/\/\/.*|\/\*[\s\S]*?\*\//g, '')), false)
})

test('[CA2] la modale réutilise le design system, sans formulaire ad hoc', () => {
  assert.match(MODALE, /from '\.\/ui'/)
  for (const composant of ['Modal', 'Field', 'VilleSearch', 'Btn']) {
    assert.match(MODALE, new RegExp(`\\b${composant}\\b`), `${composant} doit être réutilisé`)
  }
})

// ── CA3 — Case « en faire mon potager actif », cochée par défaut ────────────

test('[CA3] la case de bascule existe et est cochée par défaut', () => {
  assert.match(MODALE, /En faire mon potager actif dès maintenant/)
  assert.match(MODALE, /useState\(true\)/)
  assert.match(MODALE, /type="checkbox"/)
})

test("[CA3, CA4] le choix de bascule est transmis jusqu'à l'API", () => {
  assert.match(MODALE, /creerPotager\([\s\S]*?basculer[\s\S]*?\)/)
  assert.match(CONTEXTE, /async function creerPotager\(nom, ville, latitude, longitude, activer = true\)/)
  assert.match(API, /creerPotager: \(nom, ville, latitude, longitude, activer = true\)/)
  assert.match(API, /activer \}/)
})

// ── CA5 — Bascule ⇒ rechargement, sinon simple rafraîchissement ─────────────

test('[CA5] rechargement complet seulement quand la bascule a bien eu lieu', () => {
  const bloc = CONTEXTE.slice(CONTEXTE.indexOf('async function creerPotager'))
  assert.match(bloc, /if \(cree\.actif\)[\s\S]*window\.location\.reload\(\)/)
  assert.match(bloc, /recharger\(\{ silencieux: true \}\)/)
})

// ── CA6 — Encart « saison ≠ potager » ──────────────────────────────────────

test('[CA6] la modale rappelle que démarrer une saison ne crée pas un potager', () => {
  assert.match(MODALE, /<InfoBanner/)
  assert.match(MODALE, /clôture de saison/)
  assert.match(MODALE, /Ce n'est pas un nouveau potager/)
})

// ── CA7 — Nom vide refusé, nom en double signalé sans bloquer ──────────────

test('[CA7] un nom vide ou composé d\'espaces ne part jamais au serveur', () => {
  assert.match(MODALE, /const nomNettoye = nom\.trim\(\)/)
  assert.match(MODALE, /if \(loading \|\| !nomNettoye\) return/)
  assert.match(MODALE, /disabled=\{loading \|\| !nomNettoye\}/)
})

test('[CA7] un nom déjà utilisé déclenche un avertissement, pas un blocage', () => {
  assert.match(MODALE, /const doublon = /)
  assert.match(MODALE, /potagers\.some\(/)
  // L'avertissement ne doit pas conditionner l'envoi du formulaire.
  assert.equal(/!doublon/.test(MODALE), false, 'le doublon ne doit jamais bloquer la création')
  assert.equal(/doublon \&\& \(loading/.test(MODALE), false)
})

// ── Règle projet — container queries, pas de breakpoints d'écran ────────────

test('[CLAUDE.md] la modale, utilisée dans deux layouts, s\'adapte en container query', () => {
  assert.match(MODALE, /@container\/creer/)
  assert.match(MODALE, /@\[\d+px\]\/creer:/)
  const breakpoints = MODALE.match(/\b(sm|md|lg|xl|2xl):/g) || []
  assert.deepEqual(breakpoints, [], `breakpoints Tailwind interdits ici : ${breakpoints.join(', ')}`)
})
