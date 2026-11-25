// [US-357] L'écran de Gaston refondu — `npm test`.
//
// Ce qui se vérifie ici : la carte « À enregistrer » (lignes, étapes, note en citation), la
// confirmation UNE PAR UNE par le chemin existant avec échec partiel (CA5, CA6), la méta de la
// bulle du jardinier et l'origine retenue des messages (CA4), et, par lecture des sources, la forme
// de l'écran (CA1-CA3, CA7-CA10) : ce que le rendu doit porter sans lancer un navigateur.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import {
  lignesDeCarte, decouperLigne, dateDite, citer, cartesAConfirmer, carteACorriger, carteEnAttente,
  confirmerEnSerie, issueEnEchec, metaBulle, retenirOrigine, origineDesPhrases, etapeDeAction, estNote,
  TITRE_CARTE, TEXTE_PHOTO_BIENTOT, CLE_ORIGINES, MAX_ORIGINES,
} from './carteAEnregistrer.js'
import { ajouterPhrase } from './compagnon.js'
import { barreDeContexte } from './contexteCompagnon.js'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const lire = (chemin) => readFileSync(join(SRC, chemin), 'utf8')
const PANNEAU = lire('components/PanneauCompagnon.jsx')
const CARTE = lire('components/CarteProposition.jsx')
const A_ENREGISTRER = lire('components/CarteAEnregistrer.jsx')
const css = lire('index.css')

const MAINTENANT = new Date(2026, 10, 23, 9, 0, 0)

const LEVEE = {
  id: 11, nature: 'geste', etat: 'en_attente', confirmable: true, phrase: 'Les fèves pointent sur tout le rang',
  lignes: ['levée · fève · rang 6 · 2026-11-23'],
  items: [{ action: 'levee', culture: 'fève', rang: 6, date: '2026-11-23' }],
}
const NOTE = {
  id: 12, nature: 'geste', etat: 'en_attente', confirmable: true, phrase: 'Les fèves pointent sur tout le rang',
  lignes: ['note · Les fèves pointent sur tout le rang, terre encore humide.'],
  items: [{ action: 'note', commentaire: 'Les fèves pointent sur tout le rang, terre encore humide.' }],
}

// ── CA5 : la carte « À enregistrer », ligne par ligne ───────────────────────────────────────

test('[CA5] le titre de la carte est « À enregistrer »', () => {
  assert.equal(TITRE_CARTE, 'À enregistrer')
})

test('[CA5, Gherkin 1] la levée : pastille Levé, « Levée » en tête, la date dite', () => {
  const [ligne] = lignesDeCarte(LEVEE, MAINTENANT)
  assert.equal(ligne.titre, 'Levée')
  assert.equal(ligne.reste, 'fève · rang 6 · aujourd’hui')
  assert.equal(ligne.etape, 'levee')
  assert.equal(ligne.prevue, false)
  assert.equal(ligne.note, false)
})

test('[CA5, Gherkin 1] la note au carnet : sa citation, sans pastille d’étape', () => {
  const [ligne] = lignesDeCarte(NOTE, MAINTENANT)
  assert.equal(ligne.titre, 'Note au carnet')
  assert.equal(ligne.note, true)
  assert.equal(ligne.etape, null)
  assert.match(ligne.citation, /^Les fèves pointent sur tout le rang/)
  assert.ok(ligne.citation.endsWith('…'))
})

test('[CA5] un événement prévu est hachuré (statut « prévu » de l’item)', () => {
  const carte = { ...LEVEE, items: [{ ...LEVEE.items[0], statut: 'prevu' }] }
  assert.equal(lignesDeCarte(carte, MAINTENANT)[0].prevue, true)
})

test('[CA5] une carte à plusieurs items donne une ligne par item', () => {
  const carte = {
    id: 20, etat: 'en_attente', confirmable: true,
    lignes: ['semis · radis · 2 rangs', 'récolte · salade · 1 kg'],
    items: [{ action: 'semis' }, { action: 'recolte' }],
  }
  const lignes = lignesDeCarte(carte, MAINTENANT)
  assert.deepEqual(lignes.map((l) => l.etape), ['semee', 'en_recolte'])
  assert.deepEqual(lignes.map((l) => l.cle), ['20-0', '20-1'])
})

test('[CA5] une commande n’a ni item ni pastille : sa ligne en clair', () => {
  const carte = { id: 30, nature: 'commande', etat: 'en_attente', confirmable: false, lignes: ['/parcelle ajouter serre'], items: [] }
  const [ligne] = lignesDeCarte(carte, MAINTENANT)
  assert.equal(ligne.etape, null)
  assert.equal(ligne.titre, '')
  assert.equal(ligne.reste, '/parcelle ajouter serre')
})

test('les actions : étape franchie, note', () => {
  assert.equal(etapeDeAction('mise_en_godet'), 'en_godet')
  assert.equal(etapeDeAction('repiquage'), 'plantee')
  assert.equal(etapeDeAction('fin_culture'), 'terminee')
  assert.equal(etapeDeAction('arrosage'), null)
  assert.equal(estNote('observation'), true)
  assert.equal(estNote('recolte'), false)
})

test('les dates se disent : aujourd’hui, hier, demain, ou le jour et le mois', () => {
  assert.equal(dateDite('2026-11-23', MAINTENANT), 'aujourd’hui')
  assert.equal(dateDite('2026-11-22', MAINTENANT), 'hier')
  assert.equal(dateDite('2026-11-24', MAINTENANT), 'demain')
  assert.equal(dateDite('2026-11-05', MAINTENANT), '5 nov.')
  assert.equal(dateDite('mardi', MAINTENANT), 'mardi')
  assert.deepEqual(decouperLigne('semis', MAINTENANT), { titre: '', reste: 'semis' })
})

test('une citation longue est tronquée, une courte reste telle quelle', () => {
  assert.equal(citer('Terre humide'), 'Terre humide')
  assert.ok(citer('x'.repeat(100)).endsWith('…'))
  assert.equal(citer(''), '')
})

// ── CA6 : Confirmer, une par une, par le chemin existant ───────────────────────────────────

test('[CA6] seules les propositions en attente ET confirmables ici partent à la confirmation', () => {
  const finale = { ...LEVEE, id: 1, etat: 'confirmee' }
  const telegram = { id: 2, nature: 'commande', etat: 'en_attente', confirmable: false, lignes: ['/x'] }
  assert.deepEqual(cartesAConfirmer([finale, telegram, LEVEE, NOTE]).map((c) => c.id), [11, 12])
  assert.equal(carteEnAttente([finale]), false)
  assert.equal(carteEnAttente([finale, telegram]), true)
})

test('[CA6] « Corriger » reprend la phrase du premier geste encore en attente', () => {
  assert.equal(carteACorriger([{ ...LEVEE, etat: 'confirmee' }, NOTE]).id, 12)
  assert.equal(carteACorriger([{ id: 2, etat: 'en_attente', confirmable: false, phrase: null }]), null)
})

test('[CA6, Gherkin 2] les propositions sont confirmées l’une après l’autre, dans l’ordre', async () => {
  const appels = []
  const confirmer = async (carte) => {
    appels.push(carte.id)
    return { carte: { etat: 'confirmee' }, enregistres: [{}], erreur: null }
  }
  const vues = []
  const { confirmees, echec } = await confirmerEnSerie([LEVEE, NOTE], confirmer, (c, issue) => vues.push([c.id, issue.carte.etat]))
  assert.deepEqual(appels, [11, 12])
  assert.deepEqual(confirmees.map((c) => c.id), [11, 12])
  assert.equal(echec, null)
  assert.deepEqual(vues, [[11, 'confirmee'], [12, 'confirmee']])
})

test('[CA6, Gherkin 3] la note échoue : l’échec est dit sur sa ligne, la levée reste confirmée', async () => {
  const confirmer = async (carte) => {
    if (carte.id === 12) throw Object.assign(new Error('boom'), { statut: 500 })
    return { carte: { etat: 'confirmee' }, enregistres: [{}], erreur: null }
  }
  const dits = []
  const { confirmees, echec, restantes } = await confirmerEnSerie([LEVEE, NOTE], confirmer, (c, issue, erreur) => dits.push([c.id, Boolean(erreur)]))
  assert.deepEqual(confirmees.map((c) => c.id), [11])
  assert.equal(echec.carte.id, 12)
  assert.deepEqual(restantes, [])
  assert.deepEqual(dits, [[11, false], [12, true]])
})

test('[CA6] la série s’arrête à la première ligne qui échoue : la suivante n’est pas tentée', async () => {
  const appels = []
  const confirmer = async (carte) => {
    appels.push(carte.id)
    return carte.id === 11 ? { erreur: 'refusé', carte: { etat: 'en_attente' }, enregistres: [] } : { carte: { etat: 'confirmee' } }
  }
  const { echec, restantes } = await confirmerEnSerie([LEVEE, NOTE], confirmer)
  assert.deepEqual(appels, [11])
  assert.equal(echec.carte.id, 11)
  assert.deepEqual(restantes.map((c) => c.id), [12])
})

test('une issue sans carte confirmée, ou avec une erreur, est un échec', () => {
  assert.equal(issueEnEchec(null), true)
  assert.equal(issueEnEchec({ erreur: 'x', carte: { etat: 'confirmee' } }), true)
  assert.equal(issueEnEchec({ carte: { etat: 'en_attente' } }), true)
  assert.equal(issueEnEchec({ carte: { etat: 'confirmee' } }), false)
})

test('[CA6] aucune écriture sans Confirmer : une seule route d’écriture, appelée par le bouton', () => {
  // Le panneau n'appelle `confirmerProposition` qu'à travers `confirmerEnSerie`, lui-même lancé par `onConfirmer`.
  assert.equal((PANNEAU.match(/api\.confirmerProposition/g) ?? []).length, 1)
  assert.match(PANNEAU, /confirmerEnSerie\(cartes, \(carte\) => api\.confirmerProposition\(carte\.id\)/)
  // La carte n'appelle rien d'elle-même : un bouton « Confirmer » seulement.
  assert.doesNotMatch(A_ENREGISTRER, /api\./)
  assert.doesNotMatch(A_ENREGISTRER, /fetch\(/)
  assert.match(A_ENREGISTRER, /onClick=\{\(\) => onConfirmer\?\.\(aConfirmer\)\}/)
  assert.doesNotMatch(A_ENREGISTRER, /useEffect/)
  assert.doesNotMatch(CARTE, /useEffect|api\./)
})

test('[CA6] « Corriger » rend la main à la saisie, la carte restant dans le fil', () => {
  assert.match(PANNEAU, /const corrigerCarte = useCallback\(\(carte\) => \{[\s\S]*?setTexte\(texteACorriger\(carte\)\)[\s\S]*?saisie\.current\?\.focus\(\)/)
})

// ── CA4 : la méta de la bulle du jardinier ──────────────────────────────────────────────────────

test('[CA4] « Dicté · 0:06 » pour une dictée, « Écrit » sinon', () => {
  assert.equal(metaBulle({ dictee: true, dureeS: 6.4 }), 'Dicté · 0:06')
  assert.equal(metaBulle({ dictee: true }), 'Dicté')
  assert.equal(metaBulle({ dictee: false, dureeS: 6 }), 'Écrit')
  assert.equal(metaBulle(), 'Écrit')
})

test('[CA4] la bulle d’une dictée emporte sa durée dans le fil', () => {
  const fil = ajouterPhrase([], 'Les fèves pointent', 'j-1', true, 6.2)
  assert.equal(fil[0].dictee, true)
  assert.equal(fil[0].dureeS, 6.2)
  assert.equal(ajouterPhrase([], 'x', 'j-2', false)[0].dictee, undefined)
})

function stockageDeTest() {
  const m = new Map()
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v) }
}

test('[CA4] les messages déjà au fil gardent leur origine dictée ou écrite', () => {
  const stockage = stockageDeTest()
  retenirOrigine(stockage, 'Les fèves pointent sur tout le rang', { dictee: true, dureeS: 6.4 })
  retenirOrigine(stockage, 'Un message écrit', { dictee: false })
  const fil = [
    { cle: 'a', role: 'jardinier', texte: '  les fèves pointent   sur tout le rang ' },
    { cle: 'b', role: 'jardinier', texte: 'Un message écrit' },
    { cle: 'c', role: 'compagnon', texte: 'Les fèves pointent sur tout le rang' },
  ]
  const relu = origineDesPhrases(fil, stockage)
  assert.equal(relu[0].dictee, true)
  assert.equal(relu[0].dureeS, 6.4)
  assert.equal(relu[1].dictee, undefined)
  assert.equal(relu[2].dictee, undefined)
})

test('[CA4] sans stockage, ou stockage illisible : tout reste « Écrit », rien ne casse', () => {
  const fil = [{ cle: 'a', role: 'jardinier', texte: 'x' }]
  assert.deepEqual(origineDesPhrases(fil, null), fil)
  assert.deepEqual(origineDesPhrases(fil, { getItem: () => '{pas du json' }), fil)
  retenirOrigine(null, 'x', { dictee: true })
  retenirOrigine({ getItem: () => null, setItem: () => { throw new Error('plein') } }, 'x', { dictee: true })
})

test('[CA4] la mémoire des origines est bornée', () => {
  const stockage = stockageDeTest()
  for (let i = 0; i < MAX_ORIGINES + 15; i += 1) retenirOrigine(stockage, `phrase ${i}`, { dictee: true, dureeS: 3 })
  assert.equal(JSON.parse(stockage.getItem(CLE_ORIGINES)).length, MAX_ORIGINES)
})

// ── CA3 : le bandeau de contexte ──────────────────────────────────────────────────────────────

test('[CA3] « Fève · Planche centrale · rang 6 » ; sans contexte, rien à afficher', () => {
  const barre = barreDeContexte({ parcelleId: 1, parcelle: 'Planche centrale', culture: 'fève', rang: 6 })
  assert.equal(barre.texte, 'Fève · Planche centrale · rang 6')
  assert.equal(barre.retirable, true)
  assert.equal(barreDeContexte(null).retirable, false)
  assert.match(PANNEAU, /if \(!barre\.retirable\) return null/)
  assert.match(PANNEAU, /bg-card-alt/)
})

// ── CA2, CA4, CA7, CA8, CA9, CA10 : la forme de l’écran ───────────────────────────────────────

test('[CA2] l’en-tête : visage de 38 px cerclé brand, « Gaston » en Lora 17 px, sous-titre en brand-text', () => {
  assert.match(PANNEAU, /h-\[38px\] w-\[38px\][^"]*shadow-\[0_0_0_2px_var\(--brand\)\]/)
  assert.match(PANNEAU, /font-serif text-\[17px\][^"]*">\{GASTON\.nom\}/)
  assert.match(PANNEAU, /connaît votre potager et la météo/)
  assert.match(PANNEAU, /text-brand-text/)
  assert.doesNotMatch(PANNEAU, /font-hand/)
})

test('[CA4] bulle de Gaston : fond alt, coin bas-gauche à 5 px, 88 % ; bulle du jardinier : papier, coin bas-droit à 5 px, Kalam', () => {
  assert.match(PANNEAU, /max-w-\[88%\][^"]*self-start/)
  assert.match(PANNEAU, /rounded-bl-\[5px\] bg-card-alt/)
  assert.match(PANNEAU, /rounded-br-\[5px\] border border-paper-bd bg-paper/)
  // Kalam passe par `.note-carnet-texte` (seule porte, US-352 / CA6), jamais par `font-hand`.
  assert.match(PANNEAU, /note-carnet-texte/)
  assert.match(css, /\.note-carnet-texte\s*\{[^}]*Kalam/)
  assert.match(PANNEAU, /metaBulle\(\{ dictee: Boolean\(entree\.dictee\), dureeS: entree\.dureeS \}\)/)
})

test('[CA5] la carte : bord vert de 1,5 px, titre sur fond brand-soft, boutons de 40 px', () => {
  assert.match(A_ENREGISTRER, /border-\[1\.5px\] border-brand/)
  assert.match(A_ENREGISTRER, /bg-brand-soft[^"]*text-brand-deep">\{TITRE_CARTE\}/)
  assert.equal((A_ENREGISTRER.match(/min-h-\[40px\]/g) ?? []).length, 2)
  assert.match(A_ENREGISTRER, /Corriger/)
  assert.match(A_ENREGISTRER, /Confirmer/)
})

test('[CA5] les propositions d’un même tour tiennent dans UNE carte', () => {
  assert.match(PANNEAU, /<CarteAEnregistrer\s+cartes=\{cartes\}/)
  assert.equal((PANNEAU.match(/<CarteAEnregistrer/g) ?? []).length, 1)
  assert.match(A_ENREGISTRER, /cartes\.map\(\(carte\) => <CarteProposition key=\{carte\.id\} carte=\{carte\} \/>\)/)
})

test('[CA7] pilules de 34 px au-dessus de la saisie, « Photo · bientôt » désactivée et toujours en dernier', () => {
  assert.equal(TEXTE_PHOTO_BIENTOT, 'Photo · bientôt')
  assert.match(PANNEAU, /h-\[34px\] shrink-0/)
  const rangee = PANNEAU.slice(PANNEAU.indexOf('aria-label="Suggestions"'), PANNEAU.indexOf('Saisie : champ pilule'))
  assert.ok(rangee.indexOf('suggestions.map') < rangee.indexOf('TEXTE_PHOTO_BIENTOT'))
  assert.match(rangee, /disabled\s+className=[^>]*>\s*\{TEXTE_PHOTO_BIENTOT\}/)
})

test('[CA8] saisie : champ pilule de 44 px « Écrire à Gaston… », micro rond de 54 px en dégradé', () => {
  assert.match(PANNEAU, /flex h-11 min-w-0 flex-1 items-center rounded-full/)
  assert.match(PANNEAU, /const tailleRonde = 'h-\[54px\] w-\[54px\]'/)
  assert.match(PANNEAU, /linear-gradient\(145deg,#5E9A2E,#2F5416\)/)
})

test('[CA8] la saisie garde la dictée, ses notes et la ligne « Écouter »', () => {
  assert.match(PANNEAU, /\{modeVocal && dictee\.note && <NoteDictee note=\{dictee\.note\} \/>\}/)
  assert.match(PANNEAU, /\{micro\.bouton && \(/)
  assert.match(PANNEAU, /<LigneEcoute echangeId=/)
})

test('[CA9] les états existants gardent leur rendu : réflexion, Support, messages spontanés, mode analyse', () => {
  assert.match(PANNEAU, /'Gaston réfléchit'/)
  assert.match(PANNEAU, /Mode Support/)
  assert.match(PANNEAU, /Message de \$\{GASTON\.nom\}/)
  assert.match(PANNEAU, /TEXTE_ANALYSE_EN_COURS/)
})

test('[CA10] l’ancien style est retiré : plus d’avatar de bulle, de bord pointillé ni de titre en Kalam', () => {
  assert.doesNotMatch(PANNEAU, /function Avatar\(/)
  assert.doesNotMatch(PANNEAU, /<Avatar/)
  assert.doesNotMatch(CARTE, /border-dashed/)
  assert.doesNotMatch(CARTE, /font-hand|Geste compris|Plan proposé|Commande proposée/)
  assert.doesNotMatch(PANNEAU, /ml-\[42px\]|pl-\[42px\]/)
})

test('[CA10] CarteProposition est la ligne de la carte : pastille d’étape, plus de carte autonome', () => {
  assert.match(CARTE, /PastilleEtape/)
  assert.match(CARTE, /<li/)
  assert.match(CARTE, /carte\.potager/)
})

test('[CA1] Gaston est hébergé par le panneau partagé : plein écran sur mobile, 400 px sur ordinateur', () => {
  const app = lire('App.jsx')
  assert.match(app, /panneauGaston\(true\)/)
  assert.match(app, /panneauGaston\(false\)/)
  assert.match(lire('lib/coquille.js'), /LARGEUR_PANNEAU_PX = 400/)
  assert.match(lire('components/PanneauPartage.jsx'), /fixed inset-0/)
  // Le bouton Noter flottant est masqué tant que Gaston est ouvert.
  assert.match(app, /gastonOuvert=\{gastonOuvert\}/)
})
