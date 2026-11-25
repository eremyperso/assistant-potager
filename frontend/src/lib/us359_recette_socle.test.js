// [US-359] Recette du socle, nettoyage, guide et aide de la vue — `npm test`.
//
// Ce qui se vérifie ici : les composants remplacés ont disparu (CA3), le guide décrit la navigation
// d'aujourd'hui dans ses deux copies (CA4), l'aide de la vue ouvre la section propre à chaque vue (CA5),
// et le corpus dit où sont les exports et comment ajouter une culture du catalogue (CA6).
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { AIDE_PAR_VUE, SECTION_GUIDE, aideDeLaVue, barreAvecAide } from './aideDesVues.js'
import { entreesMenu, barreEffective } from './coquille.js'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const RACINE = join(SRC, '..', '..')
const lire = (chemin) => readFileSync(join(SRC, chemin), 'utf8')
const lireRacine = (chemin) => readFileSync(join(RACINE, chemin), 'utf8')
const GUIDES = ['docs/MANUEL/guide assistant.md', 'data/connaissance/guide user/guide assistant.md']

function sources(dossier, sortie = []) {
  for (const nom of readdirSync(dossier)) {
    const chemin = join(dossier, nom)
    if (statSync(chemin).isDirectory()) sources(chemin, sortie)
    else if (/\.(jsx?|css)$/.test(nom) && !/\.test\.js$/.test(nom)) sortie.push(chemin)
  }
  return sortie
}

// ── CA3 : les composants remplacés ont disparu ───────────────────────────────────────────────────────

test('[CA3] les composants et le hook remplacés n’existent plus', () => {
  for (const f of [
    'components/BoutonCompagnon.jsx', 'components/DateRefPicker.jsx', 'components/BarreActivitePlan.jsx',
    'components/ModalPersonnaliserDashboard.jsx', 'hooks/useDashboardWidgets.js',
  ]) assert.equal(existsSync(join(SRC, f)), false, f)
})

test('[CA3] plus aucun import ne vise un composant retiré', () => {
  const retires = /\b(BoutonCompagnon|DateRefPicker|BarreActivitePlan|ModalPersonnaliserDashboard|useDashboardWidgets)\b/
  const restes = sources(SRC).filter((f) => retires.test(readFileSync(f, 'utf8')))
  assert.deepEqual(restes, [])
})

test('[CA3] MonthStrip reste parce qu’il sert encore (fiche calendrier) ; CarteProposition est la ligne de la carte', () => {
  assert.match(lire('components/FicheCalendrier.jsx'), /<MonthStrip/)
  assert.match(lire('components/CarteAEnregistrer.jsx'), /import CarteProposition from/)
  assert.match(lire('components/CarteProposition.jsx'), /en LIGNE de la carte/)
})

// ── CA5 : l'aide de la vue ──────────────────────────────────────────────────────────────────────────

test('[CA5] chaque vue qui a une barre d’outils a son aide, avec sa section du guide', () => {
  for (const vue of Object.keys(AIDE_PAR_VUE)) {
    const a = aideDeLaVue(vue)
    assert.ok(a.titre && a.section && a.question, vue)
    assert.ok(a.points.length >= 2, vue)
  }
  for (const vue of ['stats', 'plan-vue', 'cultures', 'pepiniere', 'stocks', 'journal']) {
    assert.ok(aideDeLaVue(vue), vue)
  }
  assert.equal(aideDeLaVue('inconnue'), null)
})

test('[CA5] « Aide de la vue » est la dernière entrée du menu ⋯, après les exports', () => {
  const ouvrir = () => {}
  const barre = barreAvecAide(barreEffective('stocks', { menu: { exporterCsv: () => {}, exporterJson: () => {} } }), 'stocks', ouvrir)
  assert.deepEqual(entreesMenu(barre.menu).map((e) => e.id), ['csv', 'json', 'separateur', 'aide'])
  // Une vue sans export a quand même son aide : le menu ne contient qu'elle, sans séparateur.
  const seule = barreAvecAide(barreEffective('plan-vue', {}), 'plan-vue', ouvrir)
  assert.deepEqual(entreesMenu(seule.menu).map((e) => e.id), ['aide'])
})

test('[CA5] sans barre (tableau de bord) ou sans aide, la barre est rendue telle quelle', () => {
  assert.equal(barreAvecAide(barreEffective('bord', {}), 'bord', () => {}), null)
  const barre = barreEffective('plan-vue', {})
  assert.equal(barreAvecAide(barre, 'vue-sans-aide', () => {}), barre)
})

test('[CA5] chaque aide renvoie à une section qui existe dans le guide, dans les deux copies', () => {
  for (const chemin of GUIDES) {
    const guide = lireRacine(chemin)
    assert.match(guide, new RegExp(`^## ${SECTION_GUIDE}$`, 'm'), chemin)
    const section = guide.slice(guide.indexOf(`## ${SECTION_GUIDE}`))
    for (const a of Object.values(AIDE_PAR_VUE)) {
      for (const nom of a.section.split(' et ')) {
        assert.ok(section.includes(`**${nom}`), `${chemin} : « ${nom} » absent de la section ${SECTION_GUIDE}`)
      }
    }
  }
})

test('[CA5] la coquille dessine l’aide : le menu ⋯ l’ouvre et « Demander à Gaston » pré-écrit la question', () => {
  const bandes = lire('components/BandesFixes.jsx')
  assert.match(bandes, /barreAvecAide\(barreEffective\(view, declaration\?\.barre\), view, \(\) => setAideOuverte\(true\)\)/)
  assert.match(bandes, /ouvrirGastonSur\(\{ champ: question \}\)/)
  assert.match(lire('components/AideVue.jsx'), /Demander à Gaston/)
})

// ── CA4 : le guide, dans ses deux copies ─────────────────────────────────────────────────────────────

test('[CA4] les deux copies du guide décrivent la navigation d’aujourd’hui', () => {
  for (const chemin of GUIDES) {
    const g = lireRacine(chemin)
    for (const motif of [
      /L'anatomie d'une page/, /Noter, seule porte vers Gaston/, /règle des temps/, /Le menu ⋯ de la barre d'outils/,
      /\*\*Suivi\*\*[^]*\*\*Référence\*\*/, /Cultures · Catalogue/, /Ajouter à mon potager/, /Récoltes par saison/,
      /Trois onglets : \*\*Parcours\*\*/, /Mode sombre/,
    ]) assert.match(g, motif, `${chemin} : ${motif}`)
  }
})

test('[CA4] les mentions du médaillon, de « Parcourir », des exports en ligne et de la personnalisation sont retirées', () => {
  for (const chemin of GUIDES) {
    const g = lireRacine(chemin)
    assert.doesNotMatch(g, /médaillon/i, chemin)
    assert.doesNotMatch(g, /Parcourir/, chemin)
    assert.doesNotMatch(g, /Personnaliser (le|mon) (tableau de bord|dashboard)/i, chemin)
    assert.doesNotMatch(g, /bouton « Exporter » (de|dans) la page/i, chemin)
    assert.doesNotMatch(g, /widget météo/i, chemin)
  }
})

test('[CA4] les deux copies portent la même section « Les écrans, un par un »', () => {
  const [a, b] = GUIDES.map((c) => {
    const g = lireRacine(c)
    const debut = g.indexOf('## 4.5 Les écrans, un par un')
    return g.slice(debut, g.indexOf('# PARTIE II', debut))
  })
  assert.ok(a.length > 1000)
  assert.equal(a, b)
})

// ── CA6 : la fiche doc_app et les questions de mesure ────────────────────────────────────────────────

test('[CA6] le corpus dit où sont les exports et comment ajouter une culture du catalogue', () => {
  const journal = lireRacine('data/connaissance/doc_app/journal-et-corrections.md')
  assert.match(journal, /menu « ⋯ » de la barre d'outils, sous « Exporter en CSV » et « Exporter en JSON »/)
  const cultures = lireRacine('data/connaissance/doc_app/cultures-familles-et-rotation.md')
  assert.match(cultures, /## Ajouter à mon potager une culture du catalogue/)
  assert.match(cultures, /Cultures\*\*, puis l'onglet \*\*Catalogue\*\*/)
  assert.doesNotMatch(cultures, /médaillon|Parcourir/)
  const questions = lireRacine('tests/corpus/us099_questions_fonctionnement.csv')
  assert.match(questions, /^où sont les exports \?,journal-et-corrections\.md#03/m)
  assert.match(questions, /^comment ajouter une culture du catalogue \?,cultures-familles-et-rotation\.md#05/m)
})

test('[CA6] la fiche de Gaston décrit les suggestions et la phrase prête d’US-358', () => {
  const f = lireRacine('data/connaissance/doc_app/compagnon-reponses-et-memoire.md')
  assert.match(f, /Vous êtes sur fève\. Dites ce que vous voyez/)
  assert.match(f, /\*\*J'ai vu la levée\*\* et \*\*Pas encore\*\*/)
  assert.match(f, /qui n'est écrit qu'à \*\*Confirmer\*\*/)
  assert.doesNotMatch(f, /Préciser\*\*, qui propose/)
})
