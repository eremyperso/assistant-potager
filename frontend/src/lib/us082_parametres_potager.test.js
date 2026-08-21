// [US-082] Écran « Paramètres du potager » — volet frontend, exécuté par
// `npm test` (`node --test`, même approche que us081_creer_potager.test.js).
//
// Verrouille mécaniquement ce qui est vérifiable sans moteur de rendu :
// remplacement de l'entrée de menu (CA1), composition de l'écran (CA2, CA3,
// CA4, CA5), lecture seule pour un rôle non-owner (CA6), consommation du
// nouvel endpoint (CA7), et la règle projet des container queries.
// L'apparence elle-même relève de la validation visuelle du QA.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')
const lireSrc = (chemin) => readFileSync(join(SRC, chemin), 'utf8')

const MENU = lireSrc('components/PotagerMenu.jsx')
const ECRAN = lireSrc('views/ParametresPotager.jsx')
const MEMBRES = lireSrc('components/GestionMembres.jsx')
const API = lireSrc('lib/api.js')

// ── CA1 — PotagerMenu : un seul point d'accès, sans garde de rôle ──────────

test('[CA1] « Modifier le potager » a disparu de PotagerMenu au profit de « Paramètres du potager »', () => {
  assert.equal(/label="Modifier le potager"/.test(MENU), false)
  assert.match(MENU, /label="Paramètres du potager"/)
  assert.match(MENU, /import ParametresPotager from '\.\.\/views\/ParametresPotager\.jsx'/)
})

test("[CA1, CA6] l'entrée « Paramètres du potager » ne dépend d'aucun rôle — l'écran gère lui-même la lecture seule", () => {
  const bloc = MENU.slice(MENU.indexOf('label="Paramètres du potager"') - 200, MENU.indexOf('label="Paramètres du potager"') + 50)
  assert.equal(/role === 'owner'/.test(bloc), false)
})

test("[CA1] une seule modale ouverte pour ce point d'entrée : plus aucune référence à ModalModifierPotager dans PotagerMenu", () => {
  assert.equal(/ModalModifierPotager/.test(MENU), false)
})

// ── CA2 — En-tête identité ───────────────────────────────────────────────

test("[CA2] l'écran affiche nom (sous-titre du Modal), ville ou mention explicite, état, rôle et compteurs", () => {
  assert.match(ECRAN, /sub=\{nomAffiche\}/)
  assert.match(ECRAN, /Localisation non renseignée/)
  assert.match(ECRAN, /libelleRole\(role\)/)
  assert.match(ECRAN, /LIBELLE_ETAT\[etat\]/)
  assert.match(ECRAN, /nbParcelles/)
  assert.match(ECRAN, /nbMembres/)
})

// ── CA3 — Section Identité, réservée à l'owner ──────────────────────────────

test('[CA3] la section Identité réutilise Field + VilleSearch et repose sur modifierPotager (PATCH déjà livré)', () => {
  assert.match(ECRAN, /<Field[\s\S]*?id="parametres-potager-nom"/)
  assert.match(ECRAN, /<VilleSearch/)
  assert.match(ECRAN, /modifierPotager\(potagerId,/)
})

test("[CA3, CA6] l'édition est conditionnée à `estOwner`, la lecture seule à l'alternative", () => {
  assert.match(ECRAN, /estOwner \?[\s\S]*?<form onSubmit=\{handleSubmit\}/)
})

// ── CA4 — Section Membres, réutilisée sans duplication ──────────────────────

test('[CA4] la section Membres réutilise GestionMembres en mode embarqué', () => {
  assert.match(ECRAN, /import GestionMembres from '\.\.\/components\/GestionMembres\.jsx'/)
  assert.match(ECRAN, /<GestionMembres embedded potagerId=\{potagerId\} moiId=\{moiId\} lectureSeule=\{!estOwner\} \/>/)
})

test('[CA4] GestionMembres expose bien les props `embedded` et `lectureSeule` sans dupliquer sa logique', () => {
  assert.match(MEMBRES, /function GestionMembres\(\{ moiId, onClose, embedded = false, lectureSeule = false, potagerId: potagerIdProp \}\)/)
  // Une seule implémentation de la liste des membres et de l'invitation.
  assert.equal((MEMBRES.match(/api\.listerMembres/g) || []).length, 1)
  assert.equal((MEMBRES.match(/api\.creerInvitation/g) || []).length, 1)
})

test('[CA6] en lecture seule, GestionMembres masque le retrait et l\'encart d\'invitation', () => {
  assert.match(MEMBRES, /!lectureSeule && m\.role !== 'owner'/)
  assert.match(MEMBRES, /\{!lectureSeule && \(\s*<div className="bg-brand-soft/)
})

// ── CA5 — Zone sensible : archiver/désarchiver (US-083), rien pour les autres rôles ─

test("[CA5] la zone sensible n'apparaît que pour l'owner", () => {
  assert.match(ECRAN, /\{estOwner && \(\s*<Card bg="bg-red-soft">/)
})

test('[CA5] la zone sensible propose exactement une action selon l\'état — jamais les deux à la fois', () => {
  assert.match(ECRAN, /!estArchive \?[\s\S]*?Archiver ce potager[\s\S]*?:[\s\S]*?Désarchiver ce potager/)
})

// ── CA6 — Explication pour un membre non-owner ──────────────────────────────

test("[CA6] un membre non-owner reçoit une explication explicite en une phrase", () => {
  assert.match(ECRAN, /!estOwner &&[\s\S]*?<InfoBanner/)
  assert.match(ECRAN, /Seul le propriétaire du potager peut modifier ces réglages\./)
})

// ── CA7 — Nouvel endpoint GET /potagers/{id} ────────────────────────────────

test('[CA7] api.js expose GET /potagers/{id} et ParametresPotager le consomme', () => {
  assert.match(API, /potager: \(potagerId\) => get\(`\/potagers\/\$\{potagerId\}`\)/)
  assert.match(ECRAN, /api\.potager\(potagerId\)/)
})

// ── Règle projet — container queries, pas de breakpoints d'écran ────────────

test("[CLAUDE.md] l'écran, ouvert depuis un menu, s'adapte en container query", () => {
  assert.match(ECRAN, /@container\/parametres/)
  const breakpoints = ECRAN.match(/\b(sm|md|lg|xl|2xl):/g) || []
  assert.deepEqual(breakpoints, [], `breakpoints Tailwind interdits ici : ${breakpoints.join(', ')}`)
})
