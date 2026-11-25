// [US-352] Les pièces du socle — `npm test`.
//
// Ce qui se vérifie ici : les jetons de la maquette dans les deux thèmes (CA1, CA1b), la pastille
// « En godet » et la correspondance des stades de pépinière (CA2b), les noms et textes des
// pastilles (CA2, CA4, CA8), le calendrier de l'année (CA3), l'appui long de 380 ms (CA4), la note
// du carnet (CA5), le recensement de Kalam (CA6) et la légende commune (CA7).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  ETAPES, etape, etapeDuStade, ETAPE_DU_STADE, etatPastille, nomPastille, texteInfobulleEtape,
  entreesLegende, VARIANTE_PLEIN, VARIANTE_PREVU, VARIANTE_A_CONFIRMER, VARIANTE_LIBRE, PICTO_GODET,
} from './etapes.js'
import {
  GESTES_MOIS, moisDeFrise, moisDeChaine, texteMois, casesCalendrier, classeGeste, RIEN_A_FAIRE,
} from './calendrierAnnee.js'
import {
  creerAppuiLong, positionBulle, DELAI_APPUI_LONG_MS, TOLERANCE_DEPLACEMENT_PX,
} from './infobulle.js'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const lire = (chemin) => readFileSync(join(SRC, chemin), 'utf8')
const css = lire('index.css')
const tailwind = readFileSync(new URL('../../tailwind.config.js', import.meta.url), 'utf8')

/** Les déclarations `--nom: valeur` d'un bloc CSS, repéré par son sélecteur d'ouverture. */
function bloc(selecteur, marque) {
  const re = new RegExp(`${selecteur.replace('.', '\\.')}\\s*\\{([\\s\\S]*?)\\n\\s*\\}`, 'g')
  for (const m of css.matchAll(re)) if (m[1].includes(marque)) return m[1]
  throw new Error(`${selecteur} / ${marque} introuvable`)
}
const jeton = (b, nom) => {
  const m = b.match(new RegExp(`${nom}:\\s*([^;]+);`))
  assert.ok(m, `${nom} absent`)
  return m[1].trim().toUpperCase()
}

// ── CA1 : tokens clairs ─────────────────────────────────────────────────────────

test('[CA1] les tokens clairs de la maquette : dû, autre jour, carnet, pépinière, sol', () => {
  const clair = bloc(':root', '--ink:')
  assert.equal(jeton(clair, '--due'), '#D9822B')
  assert.equal(jeton(clair, '--ink'), '#2B3A63')
  assert.equal(jeton(clair, '--paper'), '#FBF8EF')
  assert.equal(jeton(clair, '--pep'), '#5B4690')
  for (const nom of ['--due-bg', '--due-bd', '--due-tx', '--amb-bg', '--amb-bd', '--amb-tx',
    '--paper-bd', '--pep-soft', '--soil']) jeton(clair, nom)
  assert.equal(jeton(clair, '--btn'), '#4A7C22')
})

test('[CA1] les couleurs sont exposées à Tailwind', () => {
  for (const nom of ['due', 'due-bg', 'amb-bg', 'amb-tx', 'ink', 'paper', 'paper-bd', 'pep', 'pep-soft', 'soil']) {
    assert.match(tailwind, new RegExp(`['"]?${nom}['"]?:\\s*'var\\(--${nom}\\)'`), nom)
  }
})

// ── CA1b : mode sombre ──────────────────────────────────────────────────────────

test('[CA1b] le mode sombre porte les jetons de la maquette, branchés sur .dark', () => {
  const sombre = bloc('.dark', '--bg:')
  const attendu = {
    '--bg': '#11160F', '--surface': '#1A2117', '--card-alt': '#232C1F', '--border': '#323D2C',
    '--border-soft': '#283224', '--brand': '#7DB548', '--brand-deep': '#B5DB82', '--brand-soft': '#22311A',
    '--brand-text': '#A8D072', '--txt': '#E6ECDD', '--txt2': '#AEB9A3', '--txt3': '#8C9882',
    '--header-from': '#16260D', '--header-to': '#264212',
  }
  for (const [nom, v] of Object.entries(attendu)) assert.equal(jeton(sombre, nom), v, nom)
})

test('[CA1b] sombre : dû, autre jour, encre, papier, pépinière, sol', () => {
  const sombre = bloc('.dark', '--ink:')
  assert.equal(jeton(sombre, '--ink'), '#B9C8F2')
  assert.equal(jeton(sombre, '--paper'), '#24211A')
  assert.equal(jeton(sombre, '--pep'), '#C7B8F0')
  assert.equal(jeton(sombre, '--soil'), '#3B3326')
  for (const nom of ['--due-bg', '--due-bd', '--due-tx', '--amb-bg', '--amb-bd', '--amb-tx']) jeton(sombre, nom)
})

test('[CA1b] les boutons pleins gardent le vert #4A7C22 en sombre', () => {
  assert.match(css, /\.dark \.bg-brand\s*\{[^}]*background-color:\s*var\(--btn\)/)
  assert.doesNotMatch(lire('components/ui/Btn.jsx'), /dark:text-bg/)
})

test('[CA1b] les cases du calendrier ne changent pas en sombre', () => {
  const sombre = bloc('.dark', '--bg:')
  for (const f of ['semee', 'levee', 'croissance', 'fleur', 'recolte', 'terminee']) {
    assert.doesNotMatch(sombre, new RegExp(`--etape-${f}:`), f)
  }
})

// ── CA2b : « En godet » et les stades de la pépinière ───────────────────────────

test('[CA2b] « En godet » : #CDE9A6 comme Levé, pictogramme godet', () => {
  const e = etape('en_godet')
  assert.equal(e.libelle, 'En godet')
  assert.equal(e.famille, 'levee')
  assert.equal(e.picto, PICTO_GODET)
})

test('[CA2b] les stades de la pépinière se lisent dans le langage d’étape', () => {
  assert.equal(etapeDuStade('levee'), 'levee')
  assert.equal(etapeDuStade('godet'), 'en_godet')
  assert.equal(etapeDuStade('endurcissement'), 'croissance')
  assert.equal(etapeDuStade('pret'), 'plantee')
  assert.equal(etapeDuStade('terminee'), 'terminee')
  assert.equal(etapeDuStade('inconnu'), null)
  for (const cle of Object.values(ETAPE_DU_STADE)) assert.ok(etape(cle), cle)
})

test('[CA7] « En godet » n’entre pas dans la légende du potager', () => {
  assert.ok(!entreesLegende().some((e) => e.cle === 'en_godet'))
  assert.equal(ETAPES.length, 8)
})

// ── CA2, CA4, CA8 : pastille ────────────────────────────────────────────────────

test('[CA2] les états d’une pastille se déduisent de la variante', () => {
  assert.deepEqual(etatPastille(VARIANTE_PLEIN), { prevue: false, due: false })
  assert.deepEqual(etatPastille(VARIANTE_PREVU), { prevue: true, due: false })
  assert.deepEqual(etatPastille(VARIANTE_A_CONFIRMER), { prevue: true, due: true })
  assert.deepEqual(etatPastille(VARIANTE_LIBRE), { prevue: false, due: false })
})

test('[CA8] le nom accessible : « Levé, prévu, dû »', () => {
  assert.equal(nomPastille('levee', { prevue: true, due: true }), 'Levé, prévu, dû')
  assert.equal(nomPastille('croissance'), 'En croissance')
  assert.equal(nomPastille('levee', { prevue: true }), 'Levé, prévu')
  assert.equal(nomPastille('inconnue'), '')
})

test('[Gherkin 1, CA4] l’infobulle de la levée prévue, due aujourd’hui', () => {
  assert.equal(texteInfobulleEtape('levee', { prevue: true, due: true }), 'Levé · prévu, à confirmer · dû aujourd’hui')
  assert.equal(texteInfobulleEtape('en_recolte'), 'En récolte')
})

test('[CA2] la pastille : 40 px / 30 px, point de 11 px, hachuré à −45° avec filet', () => {
  assert.match(css, /\.pastille-etape\s*\{[^}]*width:\s*40px;\s*height:\s*40px/)
  assert.match(css, /\.pastille-etape\.petite\s*\{[^}]*width:\s*30px/)
  assert.match(css, /\.pastille-etape > svg\s*\{[^}]*width:\s*21px/)
  assert.match(css, /\.pastille-etape\.petite > svg\s*\{[^}]*width:\s*16px/)
  assert.match(css, /\.pastille-point\s*\{[^}]*width:\s*11px[^}]*height:\s*11px/)
  assert.match(css, /\.etape-prevue\s*\{[^}]*-45deg[^}]*\}/)
  assert.match(css, /--etape-filet:\s*#6B7B55/i)
})

test('[CA2, CA8] le composant : role img, aria-label, data-tip, aucune couleur en dur', () => {
  const src = lire('components/ui/EtapeCulture.jsx')
  const pastille = src.slice(src.indexOf('export function PastilleEtape'))
  assert.match(pastille, /role="img"/)
  assert.match(pastille, /aria-label=\{nom\}/)
  assert.match(pastille, /data-tip=/)
  assert.doesNotMatch(src, /#[0-9a-fA-F]{3,8}\b/)
  assert.match(pastille, /PuceEtape/)
})

// ── CA3 : calendrier de l'année ─────────────────────────────────────────────────

test('[CA3] cinq gestes aux couleurs des étapes', () => {
  assert.deepEqual(GESTES_MOIS.map((g) => g.cle), ['semis', 'levee', 'croissance', 'floraison', 'recolte'])
  assert.deepEqual(GESTES_MOIS.map((g) => classeGeste(g.cle)),
    ['etape-semee', 'etape-levee', 'etape-croissance', 'etape-fleur', 'etape-recolte'])
  assert.equal(classeGeste(null), '')
})

test('[CA3] une frise du référentiel donne douze mois ; la récolte l’emporte, la croissance ne peint que les vides', () => {
  const mois = moisDeFrise({ pepiniere: [1, 2], pleineTerre: [3], plantation: [4], rec: [4, 5], croissance: [4, 5, 6] })
  assert.equal(mois.length, 12)
  assert.deepEqual(mois.slice(0, 8), [null, 'semis', 'semis', 'semis', 'recolte', 'recolte', 'croissance', null])
})

test('[CA3] la forme historique (semis, plant, rec) se lit aussi', () => {
  const mois = moisDeFrise({ semis: [2], plant: [3], rec: [6] })
  assert.equal(mois[2], 'semis')
  assert.equal(mois[3], 'levee')
  assert.equal(mois[6], 'recolte')
  assert.equal(mois[0], null)
})

test('[CA3] la chaîne de la maquette se lit mois par mois', () => {
  const mois = moisDeChaine('..slcfp.....')
  assert.deepEqual(mois.slice(0, 7), [null, null, 'semis', 'levee', 'croissance', 'floraison', 'recolte'])
})

test('[CA4] l’infobulle d’une case : « nov. (ce mois-ci) · récolte »', () => {
  assert.equal(texteMois(10, 'recolte', { courant: true }), 'nov. (ce mois-ci) · récolte')
  assert.equal(texteMois(0, null), `janv. · ${RIEN_A_FAIRE}`)
  assert.equal(texteMois(4, 'recolte', { autres: ['semis', 'recolte'] }), 'mai · semis, récolte')
})

test('[CA3] les cases : le mois courant est repéré, chaque case a son infobulle', () => {
  const cases = casesCalendrier(moisDeChaine('..slcfp.....'), { moisCourant: 6 })
  assert.equal(cases.length, 12)
  assert.equal(cases.filter((c) => c.courant).length, 1)
  assert.equal(cases[6].info, 'juil. (ce mois-ci) · récolte')
  assert.ok(cases.every((c) => c.info.includes('·')))
})

test('[CA3] le calendrier : douze cases de 9 px, gouttière de 2 px, mois courant cerclé', () => {
  assert.match(css, /\.cal-annee\s*\{[^}]*repeat\(12[^}]*gap:\s*2px/)
  assert.match(css, /\.cal-annee > i\s*\{[^}]*height:\s*9px/)
  assert.match(css, /\.cal-annee > i\.maintenant\s*\{[^}]*box-shadow/)
})

test('[CA3] Cultures et la fiche Référence utilisent le calendrier commun, plus MonthStrip', () => {
  assert.doesNotMatch(lire('components/CarteCulture.jsx'), /MonthStrip/)
  assert.match(lire('components/CarteCulture.jsx'), /CalendrierAnnee/)
  assert.doesNotMatch(lire('components/FicheCulture.jsx'), /MonthStrip/)
  assert.match(lire('components/FicheCulture.jsx'), /CalendrierAnnee/)
})

// ── CA4 : appui long de 380 ms ──────────────────────────────────────────────────

/** Une horloge de test : on avance le temps à la main. */
function horlogeFausse() {
  let t = 0
  let id = 0
  const taches = new Map()
  return {
    setTimeout: (fn, ms) => { taches.set(++id, { fn, a: t + ms }); return id },
    clearTimeout: (i) => { taches.delete(i) },
    now: () => t,
    avancer(ms) {
      t += ms
      for (const [i, tache] of [...taches]) if (tache.a <= t) { taches.delete(i); tache.fn() }
    },
  }
}

test('[CA4] l’appui long se déclenche à 380 ms, pas avant', () => {
  assert.equal(DELAI_APPUI_LONG_MS, 380)
  const h = horlogeFausse()
  const vus = []
  const m = creerAppuiLong({ surDeclenche: (c) => vus.push(c), horloge: h })
  m.debut('pastille', 10, 10)
  h.avancer(379)
  assert.deepEqual(vus, [])
  h.avancer(1)
  assert.deepEqual(vus, ['pastille'])
})

test('[CA4] un relâchement avant 380 ms ne montre rien', () => {
  const h = horlogeFausse()
  const vus = []
  const m = creerAppuiLong({ surDeclenche: (c) => vus.push(c), horloge: h })
  m.debut('pastille', 0, 0)
  h.avancer(200)
  m.fin()
  h.avancer(1000)
  assert.deepEqual(vus, [])
  assert.equal(m.avaleLeClic(), false)
})

test('[CA4] un doigt qui défile n’est pas un appui long', () => {
  const h = horlogeFausse()
  const vus = []
  const m = creerAppuiLong({ surDeclenche: (c) => vus.push(c), horloge: h })
  m.debut('rang', 0, 0)
  m.deplacement(2, 3)
  h.avancer(380)
  assert.equal(vus.length, 1)
  const n = creerAppuiLong({ surDeclenche: (c) => vus.push(c), horloge: h })
  n.debut('rang', 0, 0)
  n.deplacement(TOLERANCE_DEPLACEMENT_PX + 1, 0)
  h.avancer(380)
  assert.equal(vus.length, 1)
})

test('[CA4] un appui long n’ouvre pas ce qui est dessous : le clic qui suit est avalé', () => {
  const h = horlogeFausse()
  const m = creerAppuiLong({ surDeclenche: () => {}, horloge: h })
  m.debut('case', 0, 0)
  h.avancer(380)
  m.fin()
  assert.equal(m.avaleLeClic(), true)
  h.avancer(5000)
  assert.equal(m.avaleLeClic(), false)
})

test('[CA4] la bulle se retire quelques instants après le relâchement', () => {
  const h = horlogeFausse()
  let fins = 0
  const m = creerAppuiLong({ surDeclenche: () => {}, surFin: () => { fins += 1 }, horloge: h })
  m.debut('case', 0, 0)
  h.avancer(380)
  m.fin()
  assert.equal(fins, 0)
  h.avancer(900)
  assert.equal(fins, 1)
})

test('[CA4] la bulle reste dans l’écran, au-dessus de la cible ou en dessous près du bord haut', () => {
  const haut = positionBulle({ left: 100, top: 100, width: 40, height: 40, bottom: 140 }, { largeurBulle: 120, largeurEcran: 375 })
  assert.equal(haut.sous, false)
  assert.ok(haut.y < 100)
  const bord = positionBulle({ left: 0, top: 4, width: 20, height: 20, bottom: 24 }, { largeurBulle: 120, largeurEcran: 375 })
  assert.equal(bord.sous, true)
  assert.ok(bord.x >= 8 + 60)
})

test('[CA4] l’infobulle est montée une fois, l’appui long avale le clic', () => {
  const src = lire('components/ui/InfobulleEtapes.jsx')
  assert.match(src, /creerAppuiLong/)
  assert.match(src, /addEventListener\('click', surClic, true\)/)
  assert.match(src, /e\.pointerType === 'mouse'/)
  assert.match(lire('App.jsx'), /<InfobulleEtapes \/>/)
})

// ── CA5 : note du carnet ────────────────────────────────────────────────────────

test('[CA5, Gherkin 2] la note : papier crème, encre bleue, Kalam 16,5 px', () => {
  assert.match(css, /\.note-carnet\s*\{[^}]*background:\s*var\(--paper\)[^}]*border:\s*1px solid var\(--paper-bd\)/)
  assert.match(css, /\.note-carnet-texte\s*\{[^}]*Kalam[^}]*font-size:\s*16\.5px[^}]*color:\s*var\(--ink\)/)
  assert.match(css, /\.note-carnet-meta\s*\{[^}]*font-size:\s*11\.5px/)
  const src = lire('components/ui/NoteCarnet.jsx')
  assert.match(src, /'Dicté' : 'Écrit'/)
  assert.match(src, /filter\(Boolean\)\.join\(' · '\)/)
})

// ── CA6 : Kalam est réservée au jardinier ───────────────────────────────────────

function fichiers(dossier, sortie = []) {
  for (const nom of readdirSync(dossier)) {
    const chemin = join(dossier, nom)
    if (statSync(chemin).isDirectory()) fichiers(chemin, sortie)
    else if (/\.(jsx|css)$/.test(nom)) sortie.push(chemin)
  }
  return sortie
}

/**
 * Les usages RESTANTS de `font-hand` / Kalam, par fichier. Ce sont des chiffres de la pépinière
 * (« J34 », « 105 j », nombres de lots) et des aperçus : aucun n'est le nom de Gaston, un titre de
 * carte, « Mode Support » ou la règle des temps. Ils sortent avec la refonte de la pépinière
 * (US-356) ; ce recensement échoue si un NOUVEL usage apparaît.
 */
const KALAM_TOLERE = {
  'components/FicheLot.jsx': 'US-356',
  'components/RegleTemps.jsx': 'US-353',
  'views/_PepiniereLotsPreview.jsx': 'aperçu',
  'views/_PepiniereParcoursPreview.jsx': 'aperçu',
}

test('[CA6] recensement de font-hand : aucun usage hors de la liste tolérée', () => {
  const trouves = []
  for (const f of fichiers(SRC)) {
    const rel = f.slice(SRC.length).replace(/\\/g, '/')
    const texte = readFileSync(f, 'utf8')
    // `font-hand` est la seule porte de Kalam dans les composants ; index.css est contrôlé à part.
    if (/font-hand/.test(texte)) trouves.push(rel)
  }
  const inattendus = trouves.filter((f) => !(f in KALAM_TOLERE) && f !== 'index.css' && f !== 'components/ui/NoteCarnet.jsx')
  assert.deepEqual(inattendus, [])
})

test('[CA6] le nom de Gaston, le titre des cartes de proposition et « Mode Support » ne sont plus en Kalam', () => {
  const panneau = lire('components/PanneauCompagnon.jsx')
  assert.doesNotMatch(panneau, /font-hand/)
  assert.match(panneau, /font-serif[^>]*>\{GASTON\.nom\}/)
  assert.doesNotMatch(lire('components/CarteProposition.jsx'), /font-hand/)
})

test('[CA6] l’étiquette « auj. » de la règle des temps n’est plus en Kalam', () => {
  const m = css.match(/\.regle-auj::after\s*\{[^}]*\}/)
  assert.ok(m)
  assert.doesNotMatch(m[0], /Kalam/)
})

test('[CA6] dans index.css, Kalam n’écrit que la note du carnet et les restes de la pépinière', () => {
  const lignes = css.split('\n').filter((l) => /Kalam/.test(l) && !/^@import|^\s*\/\*|^\s*\*/.test(l))
  for (const l of lignes) assert.match(l, /note-carnet-texte|font-family:\s*Kalam/)
  assert.ok(lignes.some((l) => l.includes('note-carnet-texte')))
})

// ── CA7 : légende commune ───────────────────────────────────────────────────────

test('[CA7] légende commune : « ? Légende » repliable + « Appui long sur … : son étape »', () => {
  const src = lire('components/ui/LegendeCommune.jsx')
  assert.match(src, /aria-expanded=\{ouverte\}/)
  assert.match(src, /Légende/)
  assert.match(src, /Appui long sur \{sujet\} : son étape/)
  assert.match(src, /prevue/)
  assert.match(src, /à confirmer/)
})

// ── CA9 : page d'aperçu ─────────────────────────────────────────────────────────

test('[CA9] la page d’aperçu montre toutes les pièces, en clair et en sombre', () => {
  const src = lire('views/_EtapesPreview.jsx')
  for (const piece of ['PastilleEtape', 'PuceEtape', 'CalendrierAnnee', 'NoteCarnet', 'LegendeCommune', 'InfobulleEtapes']) {
    assert.ok(src.includes(piece), piece)
  }
  assert.match(src, /Thème sombre/)
})
