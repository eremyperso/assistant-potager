// [US-083] Archiver et désarchiver un potager — volet frontend, exécuté par
// `npm test` (`node --test`, même approche que us081/us082).
//
// Verrouille mécaniquement : la double confirmation (CA3), le masquage par
// défaut des archivés + bascule d'affichage dans PotagerMenu (CA6), le
// bandeau permanent de consultation (CA7), et le fait que le désarchivage ne
// rebascule jamais le potager actif (CA8). Le rendu visuel (badges, bandeau,
// positionnement) relève de la validation visuelle du QA.
//
// [Refonte visuelle 2026] `PotagerSelector.jsx` (Lot D, jamais migré au
// design system) a été supprimé avec son unique point d'entrée (« Tous mes
// potagers ») — la vérification CA6 ne porte plus que sur PotagerMenu.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')
const lireSrc = (chemin) => readFileSync(join(SRC, chemin), 'utf8')

const MENU = lireSrc('components/PotagerMenu.jsx')
const ECRAN = lireSrc('views/ParametresPotager.jsx')
const MODALE_ARCHIVER = lireSrc('components/ModalArchiverPotager.jsx')
const API = lireSrc('lib/api.js')

// ── CA1 — Endpoints exposés côté client ─────────────────────────────────────

test('[CA1] api.js expose les deux endpoints archiver/desarchiver', () => {
  assert.match(API, /archiverPotager: \(potagerId\) => post\(`\/potagers\/\$\{potagerId\}\/archiver`\)/)
  assert.match(API, /desarchiverPotager: \(potagerId\) => post\(`\/potagers\/\$\{potagerId\}\/desarchiver`\)/)
})

// ── CA3 — Double confirmation avant archivage ───────────────────────────────

test("[CA3] la modale d'archivage exige deux étapes avant d'appeler l'API", () => {
  assert.match(MODALE_ARCHIVER, /useState\('expliquer'\)/)
  assert.match(MODALE_ARCHIVER, /setEtape\('confirmer'\)/)
  assert.match(MODALE_ARCHIVER, /api\.archiverPotager\(potagerId\)/)
  // Le premier bouton (étape 'expliquer') avance d'étape, il n'appelle jamais l'API directement.
  const etapeUn = MODALE_ARCHIVER.slice(MODALE_ARCHIVER.indexOf("etape === 'expliquer'"), MODALE_ARCHIVER.indexOf("setEtape('confirmer')") + 20)
  assert.equal(/api\.archiverPotager/.test(etapeUn), false)
})

test('[CA3] le texte d\'avertissement imposé par l\'US est repris mot pour mot', () => {
  assert.match(
    MODALE_ARCHIVER,
    /Ce potager passera en lecture seule\. Personne ne pourra plus y\s+enregistrer d'événement\. Tu pourras le désarchiver plus tard\./,
  )
})

// ── CA5 — Zone sensible : les deux actions réellement câblées ──────────────

test('[CA5] archiver ouvre la double confirmation, désarchiver agit directement', () => {
  assert.match(ECRAN, /setModaleArchiver\(true\)/)
  assert.match(ECRAN, /<ModalArchiverPotager/)
  assert.match(ECRAN, /handleDesarchiver/)
  assert.match(ECRAN, /api\.desarchiverPotager\(potagerId\)/)
})

test("[CA8] désarchiver ne recharge jamais la page entière — pas de rebascule du potager actif", () => {
  const bloc = ECRAN.slice(ECRAN.indexOf('async function handleDesarchiver'), ECRAN.indexOf('async function handleDesarchiver') + 400)
  assert.equal(/window\.location\.reload/.test(bloc), false)
  assert.match(bloc, /recharger\(\{ silencieux: true \}\)/)
})

// ── CA6 — Masquage par défaut + bascule d'affichage, PotagerMenu ────────────

for (const [nom, source] of [['PotagerMenu', MENU]]) {
  test(`[CA6] ${nom} masque les archivés par défaut et propose une bascule d'affichage`, () => {
    assert.match(source, /voirArchives/)
    assert.match(source, /etat === 'archive'/)
  })

  test(`[CA6] ${nom} n'essaie jamais d'activer un potager archivé (ouvre Paramètres à la place)`, () => {
    // Le rendu des potagers archivés ne doit jamais appeler basculerVers/handleSelect.
    const debut = source.indexOf('archives.map(')
    const bloc = source.slice(debut, debut + 500)
    assert.equal(/basculerVers\(p\.id\)|handleSelect\(p\.id\)/.test(bloc), false)
    assert.match(bloc, /setParametresPotagerId\(p\.id\)/)
  })
}

// ── CA7 — Bandeau permanent + consultation via potagerId explicite ─────────

test('[CA7] ParametresPotager accepte un potagerId explicite, distinct du potager actif', () => {
  assert.match(ECRAN, /function ParametresPotager\(\{ potagerId: potagerIdProp, onClose \}\)/)
  assert.match(ECRAN, /const estPotagerActif = potagerId === potagerActif\?\.id/)
})

test('[CA7] un bandeau permanent « lecture seule » s\'affiche sur un potager archivé', () => {
  assert.match(ECRAN, /estArchive &&[\s\S]*?<InfoBanner[\s\S]*?title="Potager archivé — lecture seule"/)
})

test('[CA7] GestionMembres est interrogée sur le potager consulté, jamais implicitement le potager actif', () => {
  assert.match(ECRAN, /<GestionMembres embedded potagerId=\{potagerId\}/)
})

// ── Règle projet — pas de breakpoints d'écran dans la nouvelle modale ───────

test('[CLAUDE.md] ModalArchiverPotager ne dépend d\'aucun breakpoint Tailwind', () => {
  const breakpoints = MODALE_ARCHIVER.match(/\b(sm|md|lg|xl|2xl):/g) || []
  assert.deepEqual(breakpoints, [], `breakpoints Tailwind interdits ici : ${breakpoints.join(', ')}`)
})
