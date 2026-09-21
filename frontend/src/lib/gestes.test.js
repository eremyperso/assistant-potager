// [US-196] Geste préparé dans la PWA, confirmé au compagnon — `npm test`.
//
// Ce qui se vérifie ici, côté écran : la règle de date (CA14), la table
// action de confiance → geste (CA13), la phrase à dicter (CA9), le masquage
// pour un membre en lecture seule (CA11), et — par lecture du source — le fait
// que la PWA n'écrit toujours rien : un seul appel réseau, `preparerGeste`,
// et aucun écran ne le fabrique lui-même.
//
// Le volet serveur (validation, expiration, usage unique, autre compte, autre
// potager, zéro jeton) est couvert par `tests/test_us196_geste_prerempli.py`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  corpsIntention, dateDuGeste, gesteDeActionConfiance, MENTION_DATE_RAMENEE,
  peutEnregistrer, phraseADicter,
} from './gestes.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')

// ── CA14 : un geste ne se date jamais dans le futur ─────────────────────────

test('[CA14] une date de référence à venir est ramenée au jour, et on le dit', () => {
  const { date, ramenee } = dateDuGeste('2026-10-15', '2026-09-21')
  assert.equal(date, '2026-09-21')
  assert.equal(ramenee, true)
})

test('[CA14] une date de référence passée est conservée, sans mention', () => {
  const { date, ramenee } = dateDuGeste('2026-09-10', '2026-09-21')
  assert.equal(date, '2026-09-10')
  assert.equal(ramenee, false)
})

test('[CA14] la date du jour est conservée, sans mention', () => {
  const { date, ramenee } = dateDuGeste('2026-09-21', '2026-09-21')
  assert.equal(date, '2026-09-21')
  assert.equal(ramenee, false)
})

test('[CA14] sans date de référence, le jour — et rien à signaler', () => {
  const { date, ramenee } = dateDuGeste(null, '2026-09-21')
  assert.equal(date, '2026-09-21')
  assert.equal(ramenee, false)
})

test('[CA14] la mention est une phrase, pas un code', () => {
  assert.match(MENTION_DATE_RAMENEE, /aujourd/i)
})

// ── CA13 : les actions du moteur de confiance deviennent des gestes ─────────

test('[CA13] « semer en pépinière », « semer en place », « planter »', () => {
  assert.deepEqual(gesteDeActionConfiance('semis_pepiniere'),
    { action: 'semis', contexteSemis: 'pepiniere' })
  assert.deepEqual(gesteDeActionConfiance('semis_pleine_terre'),
    { action: 'semis', contexteSemis: 'pleine_terre' })
  assert.deepEqual(gesteDeActionConfiance('plantation'),
    { action: 'plantation', contexteSemis: null })
})

test('[CA13] une action inconnue n’est pas préparable — jamais un geste par défaut', () => {
  assert.equal(gesteDeActionConfiance('autre_chose'), null)
  assert.equal(gesteDeActionConfiance(undefined), null)
})

test('[CA13] la fiche ne rend le bouton que pour une action qui a un geste', () => {
  const src = lire('../components/FicheCalendrier.jsx')
  assert.match(src, /onEnregistrer && gesteDeActionConfiance\(a\.action\)/)
})

// ── CA9 : la phrase à dicter ────────────────────────────────────────────────
//
// Les gabarits eux-mêmes sont passés dans le parseur déterministe côté Python
// (`test_us196_gabarit_de_phrase_reconnu_sans_appel_modele`) : c'est là qu'ils
// font foi. Ici, on vérifie que la phrase MONTRÉE avant l'appel est bien celle
// que le serveur reconstruira — même ordre, même vocabulaire.

test('[CA9] semis en pépinière', () => {
  assert.equal(
    phraseADicter({ action: 'semis', culture: 'Tomate', contexteSemis: 'pepiniere' }),
    'semis de tomate en pépinière',
  )
})

test('[CA9] semis en pleine terre, sur une parcelle', () => {
  assert.equal(
    phraseADicter({
      action: 'semis', culture: 'épinard',
      contexteSemis: 'pleine_terre', parcelle: 'Carré nord',
    }),
    'semis de épinard en pleine terre parcelle carré nord',
  )
})

test('[CA9] plantation sans filière — la tournure de semis ne s’y invite pas', () => {
  assert.equal(
    phraseADicter({ action: 'plantation', culture: 'tomate', contexteSemis: 'pepiniere' }),
    'plantation de tomate',
  )
})

test('[CA9] la phrase ne porte jamais de date — la grammaire présume « aujourd’hui »', () => {
  const phrase = phraseADicter({ action: 'semis', culture: 'tomate', contexteSemis: 'pepiniere' })
  assert.doesNotMatch(phrase, /\d/)
})

test('[CA9] la phrase est copiable, et le bouton la propose à côté', () => {
  const src = lire('../components/BoutonGeste.jsx')
  assert.match(src, /Ou dites au compagnon/)
  assert.match(src, /clipboard\?\.writeText\(phrase\)/)
})

// ── CA11 : un membre en lecture seule ne voit aucun bouton ──────────────────

test('[CA11] seuls propriétaire et éditeur peuvent enregistrer', () => {
  assert.equal(peutEnregistrer('owner'), true)
  assert.equal(peutEnregistrer('editor'), true)
  assert.equal(peutEnregistrer('lecteur'), false)
})

test('[CA11] un rôle inconnu ou pas encore chargé ne donne aucun droit', () => {
  assert.equal(peutEnregistrer(null), false)
  assert.equal(peutEnregistrer(undefined), false)
  assert.equal(peutEnregistrer('visiteur'), false)
})

test('[CA11] le bouton ne se rend pas du tout — pas un bouton désactivé', () => {
  const src = lire('../components/BoutonGeste.jsx')
  assert.match(src, /if \(!peutEnregistrer\(potagerActif\?\.role\)\) return null/)
})

// ── CA1, CA2 : la PWA prépare, elle n’écrit pas ─────────────────────────────

test('[CA1] le corps envoyé au serveur n’invente aucun champ', () => {
  const corps = corpsIntention({
    action: 'semis', culture: 'tomate', parcelleId: 3,
    contexteSemis: 'pepiniere', date: '2026-09-19', ecran: 'plan', potagerId: 1,
  })
  assert.deepEqual(corps, {
    action: 'semis', culture: 'tomate', variete: null, quantite: null, unite: null,
    parcelle_id: 3, rang: null, lot_id: null, date: '2026-09-19',
    contexte_semis: 'pepiniere', ecran: 'plan', potager_id: 1,
  })
})

test('[CA1] ce que l’écran ne sait pas reste null — le compagnon le demandera', () => {
  const corps = corpsIntention({ action: 'plantation' })
  assert.equal(corps.parcelle_id, null)
  assert.equal(corps.quantite, null)
  assert.equal(corps.culture, null)
})

test('[CA9] un seul composant appelle l’API — aucun écran ne fabrique son appel', () => {
  for (const vue of ['../views/Plan.jsx', '../views/Stocks.jsx', '../components/FicheCalendrier.jsx']) {
    assert.doesNotMatch(lire(vue), /preparerGeste/, `${vue} ne doit pas appeler l'API directement`)
  }
  assert.match(lire('../components/BoutonGeste.jsx'), /api\.preparerGeste/)
})

test('[CA2] `preparerGeste` est le SEUL point d’écriture ajouté au client API', () => {
  const src = lire('./api.js')
  const occurrences = src.match(/preparerGeste/g) || []
  assert.equal(occurrences.length, 1)
  assert.match(src, /preparerGeste: \(corps\) => post\('\/gestes\/intentions', corps\)/)
})

// ── US-224 / CA21 : le dépôt d’abord, l’activation ensuite ──────────────────
// Inverse d’US-196 / CA10, et c’est tout l’objet d’US-224 : on prépare sa
// journée devant l’écran, on active son compagnon une fois. Un dépôt bloqué
// faute de compagnon était un geste à refaire — le détour que l’US supprime.

test('[US-224 / CA21] le dépôt ne dépend plus d’un contrôle de liaison préalable', () => {
  const src = lire('../components/BoutonGeste.jsx')
  assert.doesNotMatch(src, /api\.moi\(\)/, 'plus de contrôle de liaison avant le dépôt')
  assert.doesNotMatch(src, /if \(!moi\?\.telegram_lie\)/)
  assert.match(src, /api\.preparerGeste/)
})

test('[US-224 / CA21] sans compagnon, l’application invite à l’activer APRÈS le dépôt', () => {
  const src = lire('../components/BoutonGeste.jsx')
  const iDepot = src.indexOf('api.preparerGeste')
  const iActivation = src.indexOf('setActivation(')
  assert.ok(iDepot > -1 && iActivation > iDepot, 'le geste est déposé avant toute invitation')
  assert.match(src, /if \(!res\?\.compagnon_actif\)/)
})

test('[US-224 / CA21] l’activation réutilise le parcours d’US-091, elle n’en crée pas un second', () => {
  const src = lire('../components/BoutonGeste.jsx')
  assert.match(src, /import \{ PanneauActivation, useCodeLiaison \} from '\.\/LierTelegram\.jsx'/)
})

test('[US-224 / CA21] refermer l’activation ne redépose PAS le geste', () => {
  // Il est déjà en file : le rejouer en créerait un second, silencieusement.
  const src = lire('../components/BoutonGeste.jsx')
  assert.doesNotMatch(src, /onClose=\{\(\) => \{ setActivation\(false\); lancer\(\) \}\}/)
  assert.match(src, /onClose=\{\(\) => setActivation\(null\)\}/)
})

test('[US-224 / CA4] un geste identique en attente est signalé, jamais refusé', () => {
  const src = lire('../components/BoutonGeste.jsx')
  assert.match(src, /depose\?\.doublon/)
  assert.match(src, /attend déjà/)
})

// ── CA12 : relecture unique au retour sur l’onglet ──────────────────────────

test('[CA12] le retour s’écoute par visibilitychange, jamais par sondage', () => {
  const src = lire('../hooks/useRelectureAuRetour.jsx')
  assert.match(src, /addEventListener\('visibilitychange'/)
  // Appel réel, pas la mention dans le commentaire d'en-tête.
  assert.doesNotMatch(src, /setInterval\(|setTimeout\(/)
})

test('[CA12] la relecture n’a lieu qu’une fois, et seulement si un geste est parti', () => {
  const src = lire('../hooks/useRelectureAuRetour.jsx')
  // Le drapeau est désarmé AVANT l'appel : deux retours d'onglet ne relisent
  // pas deux fois.
  assert.match(src, /arme\.current = false\s*\n\s*relireRef\.current\?\.\(\)/)
  assert.match(src, /if \(document\.visibilityState !== 'visible' \|\| !arme\.current\) return/)
})

test('[CA12] Plan et Stocks se relisent avec leur propre chargement', () => {
  for (const vue of ['../views/Plan.jsx', '../views/Stocks.jsx']) {
    assert.match(lire(vue), /<RelectureAuRetourProvider relire=\{load\}>/, vue)
  }
})

// ── CA13, CA15 : les deux points d’entrée de la fiche calendrier ────────────

test('[CA13] Plan et Stocks fournissent `onEnregistrer` — le bouton d’US-183 existe enfin', () => {
  assert.match(lire('../views/Plan.jsx'), /onEnregistrer=\{\(\) => setFicheCalendrier\(false\)\}/)
  assert.match(lire('../views/Stocks.jsx'), /onEnregistrer=\{\(\) => setFiche\(null\)\}/)
})

test('[CA13] la parcelle est pré-remplie quand la fiche vient d’une parcelle', () => {
  const src = lire('../components/FicheCalendrier.jsx')
  assert.match(src, /geste=\{\{ \.\.\.gesteDeActionConfiance\(a\.action\), culture, parcelleId \}\}/)
})

test('[CA15] le bouton reste actif hors fenêtre — la confiance conseille, elle n’interdit pas', () => {
  const src = lire('../components/FicheCalendrier.jsx')
  // Aucune condition de fenêtre ni de confiance ne garde le bouton : seuls
  // `onEnregistrer` (US-183 / CA6) et l'existence d'un geste le conditionnent.
  const ligne = src.split('\n').find((l) => l.includes('onEnregistrer && gesteDeActionConfiance'))
  assert.ok(ligne, 'le garde du bouton doit rester lisible sur une seule ligne')
  assert.doesNotMatch(ligne, /etoiles|dans_fenetre|sans_score|confiance/)
})
