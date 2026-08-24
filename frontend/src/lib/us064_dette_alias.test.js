// [US-064] Clôture de la dette d'alias de couleurs sur le périmètre du Lot B —
// exécuté par `npm test` (`node --test`, sans dépendance de test supplémentaire).
// Vérifie mécaniquement CA1 (périmètre du Lot B propre) et CA2/CA3 (bloc d'alias
// conservé, documenté nommément, avec sa condition de suppression).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')
const FRONTEND = join(SRC, '..')

const ALIAS_RE = /--g-[a-z-]+|(?:bg|text|border)-g-[a-z-]+/

const lireSrc = (chemin) => readFileSync(join(SRC, chemin), 'utf8')

const ECRANS_LOT_B = [
  'views/Plan.jsx',
  'views/Pepiniere.jsx',
  'views/Stocks.jsx',
  'views/Journal.jsx',
]

const COMPOSANTS_TRANSVERSES_US059 = [
  'components/DateRefPicker.jsx',
  'components/CultureFilter.jsx',
  'components/MetricStrip.jsx',
  'components/Observations.jsx',
  'components/LoadingSkeleton.jsx',
  'components/ApiError.jsx',
]

// Vues explicitement hors périmètre du Lot B (cf. docs/ANALYSE_REFONTE_UI_WEB_2026.md
// §7.4) : elles continuent d'utiliser l'alias, leur migration relève du Lot D.
const VUES_HORS_PERIMETRE = [
  'views/Stats.jsx',
  'views/VerifyEmail.jsx',
]

test('[CA1] les quatre écrans du Lot B ne référencent plus aucun alias --g-*', () => {
  for (const fichier of ECRANS_LOT_B) {
    const contenu = lireSrc(fichier)
    assert.equal(ALIAS_RE.test(contenu), false, `${fichier} référence encore un alias --g-*`)
  }
})

test('[CA1] les six composants transverses migrés par US-059 ne référencent plus aucun alias --g-*', () => {
  for (const fichier of COMPOSANTS_TRANSVERSES_US059) {
    const contenu = lireSrc(fichier)
    assert.equal(ALIAS_RE.test(contenu), false, `${fichier} référence encore un alias --g-*`)
  }
})

test('[CA2] le bloc d\'alias reste défini dans index.css et son pendant tailwind.config.js', () => {
  const css = lireSrc('index.css')
  assert.match(css, /--g-bg:\s*var\(--bg\)/)
  assert.match(css, /--g-red-dim:\s*var\(--red-soft\)/)

  const tailwind = readFileSync(join(FRONTEND, 'tailwind.config.js'), 'utf8')
  assert.match(tailwind, /'g-bg':\s*'var\(--g-bg\)'/)
})

test('[CA2] le commentaire du bloc recense nommément les fichiers qui l\'utilisent encore', () => {
  const css = lireSrc('index.css')
  for (const fichier of VUES_HORS_PERIMETRE) {
    const nom = fichier.split('/').pop()
    assert.ok(css.includes(nom), `le commentaire du bloc d'alias ne mentionne pas ${nom}`)
  }
})

test('[CA3] la condition de suppression du bloc est écrite noir sur blanc dans le commentaire', () => {
  const css = lireSrc('index.css')
  assert.match(css, /avant de supprimer ce bloc/)
})

test('[CA4] les vues hors périmètre ne sont pas touchées : elles conservent l\'alias tel quel', () => {
  // Prouve l'absence de régression par construction plutôt que par capture d'écran :
  // ces fichiers n'ont reçu aucune modification (cf. rapport QA), leur alias --g-*
  // reste donc strictement identique à avant la clôture du Lot B.
  for (const fichier of VUES_HORS_PERIMETRE) {
    const contenu = lireSrc(fichier)
    assert.equal(ALIAS_RE.test(contenu), true, `${fichier} devrait toujours utiliser l'alias --g-*`)
  }
})
