// [US-353] La coquille commune — `npm test`.
//
// Ce qui se vérifie ici : le contrat et la règle commune du Mot de Gaston (CA6, CA7), la barre
// d'outils et son menu ⋯ (CA8, CA9), le bouton date et la règle des temps (CA10), le resserrement
// au défilement (CA11), le panneau partagé (CA12), la navigation (CA1, CA2, CA5) et la
// suppression du médaillon, de `DateRefPicker` et de `BarreActivitePlan` (CA4, D3).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import {
  nettoyerTexte, normaliserAction, normaliserMot, signauxDeEtat, motCommun, calculerMot, executerAction,
  momentDeJournee, MAX_PHRASES, MAX_ACTIONS, PRIORITE_COMMUNE,
} from './motDeGaston.js'
import {
  estCompact, SEUIL_COMPACT_PX, barreEffective, controlesPresents, entreesMenu, boutonDate, entreePlus,
  formePanneau, LARGEUR_PANNEAU_PX, DECALAGE_NOTER_PX, ORDRE_BARRE, aUneBarre, OCCUPANTS_PANNEAU,
} from './coquille.js'
import { barreBasse, NAV, NAV_OF } from '../navigation.js'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const lire = (chemin) => readFileSync(join(SRC, chemin), 'utf8')
const css = lire('index.css')

// ── CA6 : le contrat du Mot de Gaston ───────────────────────────────────────────

test('[CA6] deux phrases au plus', () => {
  assert.equal(MAX_PHRASES, 2)
  assert.equal(nettoyerTexte('Une. Deux ! Trois ? Quatre.'), 'Une. Deux !')
  assert.equal(nettoyerTexte('  Gel   annoncé\n samedi.  '), 'Gel annoncé samedi.')
})

test('[CA6] sans rien à dire, le bloc n’est pas rendu : mot nul', () => {
  assert.equal(normaliserMot(null), null)
  assert.equal(normaliserMot({ texte: '   ', actions: [{ libelle: 'Oui' }] }), null)
  assert.equal(normaliserMot({ actions: [] }), null)
  const src = lire('components/MotDeGaston.jsx')
  assert.match(src, /if \(!mot\) return null/)
})

test('[CA6] une à trois actions, une seule principale (la première par défaut)', () => {
  assert.equal(MAX_ACTIONS, 3)
  const mot = normaliserMot({
    texte: 'Bonjour.', actions: [{ libelle: 'A' }, { libelle: 'B' }, { libelle: 'C' }, { libelle: 'D' }, { libelle: '' }],
  })
  assert.deepEqual(mot.actions.map((a) => a.libelle), ['A', 'B', 'C'])
  assert.deepEqual(mot.actions.map((a) => a.principale), [true, false, false])
  const choisie = normaliserMot({ texte: 'Ok.', actions: [{ libelle: 'A' }, { libelle: 'B', principale: true }] })
  assert.deepEqual(choisie.actions.map((a) => a.principale), [false, true])
})

test('[CA6] une action écrit (ouvre Gaston) ou navigue (change de vue), jamais les deux', () => {
  assert.deepEqual(normaliserAction({ libelle: 'Noter', noter: true, vue: 'cultures' }), { libelle: 'Noter', noter: true })
  assert.deepEqual(normaliserAction({ libelle: 'Voir', vue: 'plan-vue', intention: { x: 1 } }), { libelle: 'Voir', vue: 'plan-vue', intention: { x: 1 } })
  assert.equal(normaliserAction({ libelle: '' }), null)
  const appels = []
  const sortie = { ouvrirGaston: (c) => appels.push(['gaston', c]), aller: (v, i) => appels.push(['aller', v, i]) }
  assert.equal(executerAction({ libelle: 'N', noter: true, contexte: { culture: 'fève' } }, sortie), 'noter')
  assert.equal(executerAction({ libelle: 'V', vue: 'cultures' }, sortie), 'aller')
  assert.equal(executerAction({ libelle: 'rien' }, sortie), null)
  assert.deepEqual(appels, [['gaston', { culture: 'fève' }], ['aller', 'cultures', undefined]])
})

test('[CA6] fond brand-soft, visage de 40 px, pilules de 34 px, × de 30 px', () => {
  const src = lire('components/MotDeGaston.jsx')
  assert.match(src, /bg-brand-soft/)
  assert.match(src, /h-10 w-10/)
  assert.match(src, /min-h-\[34px\]/)
  assert.match(src, /h-\[30px\] w-\[30px\]/)
  assert.match(src, /momentDeJournee\(\)/)
})

test('[CA6] « Gaston · ce matin » : le moment de la journée', () => {
  assert.equal(momentDeJournee(new Date(2026, 10, 24, 8)), 'ce matin')
  assert.equal(momentDeJournee(new Date(2026, 10, 24, 15)), 'cet après-midi')
  assert.equal(momentDeJournee(new Date(2026, 10, 24, 21)), 'ce soir')
})

// ── CA7 : calculé sans modèle, règle commune ────────────────────────────────────

test('[CA7] priorité commune : gel > étape due > manque de donnée', () => {
  assert.deepEqual([...PRIORITE_COMMUNE], ['gel', 'etape_due', 'manque'])
  const tout = { gel: { jour: 'samedi', temperature: -2 }, etapesDues: 3, manques: ['la quantité semée'] }
  assert.match(motCommun(tout).texte, /^Gel annoncé samedi \(-2 °C\)\./)
  assert.match(motCommun({ ...tout, gel: null }).texte, /^3 étapes à confirmer\./)
  assert.match(motCommun({ ...tout, gel: null, etapesDues: 0 }).texte, /^Il me manque une information/)
  assert.equal(motCommun({}), null)
  assert.equal(motCommun({ gel: null, etapesDues: [], manques: [] }), null)
})

test('[CA7] une étape due isolée est nommée ; le gel reprend le texte du signal', () => {
  const un = motCommun({ etapesDues: [{ culture: 'Fève', etape: 'Levée' }] })
  assert.match(un.texte, /^Fève : levée prévue, à confirmer\./)
  const gel = motCommun({ gel: { texte: 'Gel annoncé samedi (−2 °C). Voilez la mâche.' } })
  assert.equal(gel.texte, 'Gel annoncé samedi (−2 °C). Voilez la mâche.')
  assert.equal(gel.actions.length, 2)
})

test('[CA7] les signaux de /compagnon/etat : le gel récent, non réagi', () => {
  const maintenant = Date.parse('2026-11-24T10:00:00Z')
  const etat = { spontanes: [
    { genre: 'gel', texte: 'Gel ce soir.', envoye_le: '2026-11-24T06:00:00Z', reagi: false },
    { genre: 'autre', texte: 'Hello', envoye_le: '2026-11-24T07:00:00Z', reagi: false },
  ] }
  assert.deepEqual(signauxDeEtat(etat, { maintenant }), { gel: { texte: 'Gel ce soir.' } })
  assert.deepEqual(signauxDeEtat({ spontanes: [{ ...etat.spontanes[0], reagi: true }] }, { maintenant }), { gel: null })
  assert.deepEqual(signauxDeEtat({ spontanes: [{ ...etat.spontanes[0], envoye_le: '2026-11-20T06:00:00Z' }] }, { maintenant }), { gel: null })
  assert.deepEqual(signauxDeEtat(null), { gel: null })
})

test('[CA7] calculé sans modèle : pure, sans réseau, une règle par vue', () => {
  const src = lire('lib/motDeGaston.js')
  assert.doesNotMatch(src, /fetch\(|api\./)
  const regles = { stocks: () => ({ texte: 'Quatorze godets attendent une place.', actions: [{ libelle: 'Oui, proposer', noter: true }] }) }
  assert.equal(calculerMot('stocks', {}, regles).actions[0].libelle, 'Oui, proposer')
  assert.equal(calculerMot('journal', {}, regles), null)               // règle commune : rien à dire
  assert.match(calculerMot('journal', { etapesDues: 2 }, regles).texte, /2 étapes/)
  assert.equal(calculerMot('stocks', {}, { stocks: () => { throw new Error('donnée absente') } }), null)
  assert.deepEqual(calculerMot('stocks', {}, regles), calculerMot('stocks', {}, regles))
})

test('[Gherkin 4] Gaston n’a rien à dire sur le Journal : aucun bloc', () => {
  assert.equal(calculerMot('journal', {}), null)
})

// ── CA8, CA9 : barre d'outils et menu ⋯ ─────────────────────────────────────────

test('[CA8] la barre : date, recherche, Filtrer, ⋯ — toujours dans cet ordre', () => {
  assert.deepEqual([...ORDRE_BARRE], ['date', 'recherche', 'filtre', 'menu'])
  const barre = barreEffective('stocks', {
    recherche: { placeholder: 'Rechercher' }, filtre: { nombre: 2 }, menu: { exporterCsv: () => {} },
  })
  assert.deepEqual(controlesPresents(barre), ['date', 'recherche', 'filtre', 'menu'])
})

test('[CA8] une vue peut retirer la date ou Filtrer ; rien ne s’y ajoute', () => {
  assert.deepEqual(controlesPresents(barreEffective('cultures', { date: false, recherche: { placeholder: 'x' } })), ['recherche'])
  assert.deepEqual(controlesPresents(barreEffective('cultures', { filtre: false })), ['date'])
  assert.deepEqual(controlesPresents(barreEffective('cultures', { bouton: { libelle: 'Ajout' }, autre: 1 })), ['date'])
})

test('[CA8] le tableau de bord n’a pas de barre ; les autres vues en ont une', () => {
  assert.equal(aUneBarre('bord'), false)
  assert.equal(barreEffective('bord', { recherche: { placeholder: 'x' } }), null)
  for (const v of ['stats', 'plan-vue', 'cultures', 'pepiniere', 'stocks', 'journal']) assert.equal(aUneBarre(v), true, v)
})

test('[CA8] contrôles de 40 px ; Filtrer se réduit à l’icône sous 520 px de conteneur', () => {
  const src = lire('components/BarreOutils.jsx')
  assert.match(src, /h-10 shrink-0/)
  assert.match(src, /@\[520px\]\/page:inline/)
  assert.match(src, /@\[520px\]\/page:w-auto/)
  assert.doesNotMatch(src, /(?:^|\s)(?:sm|md|lg|nav):/m)             // container query, pas de breakpoint d'écran
  assert.match(lire('App.jsx'), /@container\/page/)
})

test('[CA9] menu ⋯ : exports, séparateur, aide ; chaque entrée seulement si la vue la fournit', () => {
  const f = () => {}
  assert.deepEqual(entreesMenu({ exporterCsv: f, exporterJson: f, aide: f }).map((e) => e.id), ['csv', 'json', 'separateur', 'aide'])
  assert.deepEqual(entreesMenu({ exporterCsv: f }).map((e) => e.id), ['csv'])
  assert.deepEqual(entreesMenu({ aide: f }).map((e) => e.id), ['aide'])
  assert.deepEqual(entreesMenu({}), [])
  assert.deepEqual(entreesMenu(null), [])
  assert.equal(barreEffective('stocks', { menu: {} }).menu, null)
})

test('[CA9] « Pièces jointes » est supprimé (D10)', () => {
  const libelles = entreesMenu({ exporterCsv: () => {}, exporterJson: () => {}, aide: () => {}, piecesJointes: () => {} })
    .map((e) => e.libelle).filter(Boolean)
  assert.deepEqual(libelles, ['Exporter en CSV', 'Exporter en JSON', 'Aide de la vue'])
})

// ── CA10 : bouton date et règle des temps ───────────────────────────────────────

test('[CA10] « Aujourd’hui » ; sur un autre jour, ambre avec la date courte', () => {
  assert.deepEqual(boutonDate(null), { libelle: 'Aujourd’hui', ambre: false })
  assert.deepEqual(boutonDate('2026-11-12'), { libelle: '12 nov.', ambre: true })
  const src = lire('components/BarreOutils.jsx')
  assert.match(src, /border-amb-bd bg-amb-bg text-amb-tx/)
})

test('[CA10] la règle s’ouvre juste sous la barre d’outils, dans toutes les vues', () => {
  const bandes = lire('components/BandesFixes.jsx')
  assert.ok(bandes.indexOf('<BarreOutils') < bandes.indexOf('<RegleTemps'))
  assert.match(bandes, /barre\.date && regleOuverte/)
  assert.doesNotMatch(lire('App.jsx'), /<RegleTemps/)
})

test('[CA10] la tête de la règle : date longue en police système 14 px, « il y a 11 j », Aujourd’hui, ×', () => {
  const src = lire('components/RegleTemps.jsx')
  assert.doesNotMatch(src, /font-hand/)
  assert.match(src, /text-\[14px\] font-semibold/)
  assert.match(src, /libelleLong\(iso\)/)
  assert.match(src, /Aujourd'hui/)
  assert.match(src, /aria-label="Fermer la réglette"/)
  assert.match(src, /Jour précédent|sens < 0/)
})

test('[CA10] glissé avec inertie, molette, flèches (Maj = 7 jours), toucher un mois', () => {
  const src = lire('components/RegleTemps.jsx')
  assert.match(src, /const lancer = \(vitesse\)/)
  assert.match(src, /addEventListener\('wheel'/)
  assert.match(src, /pasDuClavier\(e\.key, e\.shiftKey\)/)
  assert.match(src, /onClick=\{\(\) => onMois\?\.\(i\)\}/)
})

test('[CA10, D3] DateRefPicker et BarreActivitePlan sont retirés', () => {
  assert.equal(existsSync(join(SRC, 'components/DateRefPicker.jsx')), false)
  assert.equal(existsSync(join(SRC, 'components/BarreActivitePlan.jsx')), false)
  for (const f of ['views/Cultures.jsx', 'views/Stocks.jsx', 'views/Stats.jsx', 'components/OngletLots.jsx',
    'components/OngletParcours.jsx', 'components/PageHeader.jsx']) {
    assert.doesNotMatch(lire(f), /DateRefPicker|BarreActivitePlan/, f)
  }
})

// ── CA11 : défilement ───────────────────────────────────────────────────────────

test('[CA11] au-delà de 8 px de défilement, l’en-tête se resserre', () => {
  assert.equal(SEUIL_COMPACT_PX, 8)
  assert.equal(estCompact(0), false)
  assert.equal(estCompact(8), false)
  assert.equal(estCompact(9), true)
})

test('[CA11] seule la bande de contenu défile ; l’en-tête, le mot et la barre restent fixes', () => {
  const app = lire('App.jsx')
  assert.match(app, /<main ref=\{mainRef\} onScroll=\{surDefilement\} className="min-h-0 flex-1 overflow-y-auto"/)
  assert.ok(app.indexOf('<PageHeader') < app.indexOf('<BandesFixes'))
  assert.ok(app.indexOf('<BandesFixes') < app.indexOf('<main'))
  assert.match(app, /onRemonter=\{remonter\}/)
  assert.match(lire('components/MotDeGaston.jsx'), /onClick=\{compact \? onRemonter : undefined\}/)
})

test('[CA11] compact : titre 18 px, ligne de contexte masquée, tuiles masquées sur ordinateur', () => {
  const src = lire('components/PageHeader.jsx')
  assert.match(src, /compact \? 'text-\[18px\]' : 'text-\[25px\] nav:text-\[28px\]'/)
  assert.match(src, /sousTitre && !compact/)
  assert.match(lire('components/ui/TileNav.jsx'), /compact \? 'nav:hidden'/)
  assert.match(lire('components/MotDeGaston.jsx'), /line-clamp-1/)
})

// ── CA12 : panneau partagé ──────────────────────────────────────────────────────

test('[CA12] un panneau droit de 400 px sur ordinateur, une feuille sur mobile, Gaston en plein écran', () => {
  assert.equal(LARGEUR_PANNEAU_PX, 400)
  assert.equal(formePanneau({ occupant: 'fiche', bureau: true }), 'lateral')
  assert.equal(formePanneau({ occupant: 'gaston', bureau: true }), 'lateral')
  assert.equal(formePanneau({ occupant: 'fiche', bureau: false }), 'feuille')
  assert.equal(formePanneau({ occupant: 'gaston', bureau: false }), 'plein-ecran')
  assert.equal(formePanneau({ occupant: null, bureau: true }), null)
  assert.deepEqual([...OCCUPANTS_PANNEAU], ['gaston', 'fiche', 'catalogue', 'recoltes'])
})

test('[CA12] la feuille : poignée, fond assombri, appui hors feuille = fermer', () => {
  const src = lire('components/PanneauPartage.jsx')
  assert.match(src, /feuille-poignee/)
  assert.match(src, /onClick=\{onFermer\}/)
  assert.match(src, /e\.stopPropagation\(\)/)
  assert.match(css, /\.feuille-voile\s*\{[^}]*background:\s*var\(--voile\)/)
  assert.match(css, /\.feuille-poignee\s*\{[^}]*width:\s*40px;\s*height:\s*5px/)
})

test('[CA12] un seul occupant à la fois : ouvrir Gaston referme la fiche, et inversement', () => {
  const app = lire('App.jsx')
  // [US-358] Le dernier venu l'emporte (deux règles indépendantes se fermaient l'une l'autre : « Noter » d'une fiche
  // ouvrait Gaston puis le refermait). Le comportement est testé dans us358_gaston_en_contexte.test.js.
  assert.match(app, /occupantAFermer\(\{ gastonOuvert, occupant: occupantFiche \}, avantPanneau\.current\)/)
  assert.match(app, /if \(aFermer === 'fiche'\) fermerPanneau\(\)/)
  assert.match(app, /else if \(aFermer === 'gaston'\) agirCompagnon\('fermer'\)/)
  assert.match(lire('context/CoquilleContext.jsx'), /useState\(null\)\s+\/\/ \{ cle, titre, contenu \}/)
})

// ── CA1, CA2, CA5 : navigation ──────────────────────────────────────────────────

test('[CA1] bandeau ordinateur : 60 px, six entrées, onglet actif en pastille blanche', () => {
  const src = lire('components/TopBar.jsx')
  assert.match(src, /h-\[60px\]/)
  assert.match(src, /bg-surface font-bold text-brand-deep/)
  assert.match(src, /text-brand/)
  assert.equal(NAV.length, 6)
  assert.match(css, /--header-from:\s*#2F5416;[\s\S]*--header-to:\s*#4E8226/)
  assert.match(css, /--header-from:\s*#16260D;[\s\S]*--header-to:\s*#264212/)
})

test('[CA2] barre basse : Accueil, Plan, Noter de 62 px qui déborde de 30 px, Pépinière, Plus', () => {
  const { principales } = barreBasse()
  assert.deepEqual(principales.map((e) => e.shortLabel), ['Accueil', 'Plan', 'Noter', 'Pépinière'])
  assert.match(css, /\.noter-rond\s*\{[^}]*width:\s*62px;\s*height:\s*62px;\s*margin-top:\s*-30px/)
  assert.match(css, /\.bn-ind\s*\{[^}]*width:\s*56px;\s*height:\s*30px/)
  assert.match(lire('components/BottomNav.jsx'), /bn-ind \$\{on \? 'actif' : ''\}/)
})

test('[CA2, Gherkin 1] sur Stocks, « Plus » prend son nom, son icône et la pastille', () => {
  const { secondaires } = barreBasse()
  const stocks = entreePlus(NAV_OF.stocks, secondaires)
  assert.equal(stocks.shortLabel, 'Stocks')
  assert.ok(stocks.Icon)
  assert.equal(entreePlus('plan', secondaires), null)
  assert.match(lire('components/BottomNav.jsx'), /rangee \? rangee\.shortLabel : 'Plus'/)
})

test('[CA3] Noter : pastille de 24 px (emoji de la culture, sinon micro), compteur de non-lus dessus', () => {
  assert.match(css, /\.noter-pastille\s*\{[^}]*width:\s*24px;\s*height:\s*24px/)
  const src = lire('components/BoutonNoter.jsx')
  assert.match(src, /pastille\.emoji \|\| <Mic/)
  assert.match(src, /noter-nonlus/)
  assert.equal(DECALAGE_NOTER_PX, LARGEUR_PANNEAU_PX + 28)
  assert.match(src, /if \(variante === 'bureau' && gastonOuvert\) return null/)
  assert.match(src, /right: panneauOuvert \? DECALAGE_NOTER_PX : 28/)
})

test('[CA4, D5] le médaillon flottant et sa bulle d’accueil sont supprimés', () => {
  assert.equal(existsSync(join(SRC, 'components/BoutonCompagnon.jsx')), false)
  assert.doesNotMatch(lire('App.jsx'), /BoutonCompagnon/)
  assert.doesNotMatch(css, /\.gst-tab|\.gst-pres|\.gst-bulle|\.gst-nonlus/)
})

test('[CA5] l’en-tête : Lora 25 px sur mobile, 28 px sur ordinateur, tuiles 84 × 64, pastilles de 36 px', () => {
  const tete = lire('components/PageHeader.jsx')
  assert.match(tete, /text-\[25px\] nav:text-\[28px\]/)
  assert.match(tete, /font-serif/)
  const tuiles = lire('components/ui/TileNav.jsx')
  assert.match(tuiles, /h-9/)
  assert.match(tuiles, /nav:h-16 nav:w-\[84px\]/)
  assert.doesNotMatch(tete, /Exporter|Aide de la vue|Personnaliser/)
})

test('[CA5] les onglets n’existent que pour le tableau de bord, le Plan et Cultures', () => {
  assert.deepEqual(NAV.filter((n) => n.subnav).map((n) => n.id), ['bord', 'plan', 'cultures'])
  const rotation = NAV.find((n) => n.id === 'plan').subnav.find((t) => t.id === 'plan-rot')
  assert.equal(rotation.label, 'Rotation · à venir')
  assert.equal(rotation.disabled, true)
})

test('[CA13] les vues non dessinées reçoivent la coquille : Statistiques a sa barre (date), son en-tête', () => {
  assert.equal(aUneBarre('stats'), true)
  assert.equal(NAV_OF.stats, 'bord')
  assert.deepEqual(controlesPresents(barreEffective('stats')), ['date'])
})
