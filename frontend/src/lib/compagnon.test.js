// [US-271] Parler au compagnon depuis la PWA — `npm test`.
//
// Ce qui se vérifie ici, côté écran : les deux modes (CA1), l'état et les boutons d'une carte
// (CA2), le rangement des messages spontanés dans le fil (CA3), les erreurs dites en clair (CA4),
// et — par lecture du source — le respect de la règle de mise en page (CA5) : container queries
// dans le panneau, breakpoints seulement pour la structure de page.
//
// Le volet serveur (modes, cartes, confirmation atomique, isolation) est couvert par
// `tests/test_us270_api_compagnon.py` et `tests/test_us271_compagnon_panneau.py`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  MODES, MODE_DEFAUT, modeValide, modeDe, messageErreur, TEXTE_RESEAU, carteDefinitivementFermee,
  etatCarte, boutonsCarte, carteApresIssue, carteFermee, filDepuisHistorique, ajouterEchange,
  ajouterErreur, ajouterPhrase, cleDePhrase, remplacerCarte, cartesEnAttente, remplacerLesAnciennes, peutEnvoyer,
  texteACorriger, aEnregistre, LONGUEUR_MAX, ETATS, ETAT_PAR_DEFAUT, etatSuivant, lireEtat, ecrireEtat, CLE_ETAT, GASTON,
  ACCUEIL, SUGGESTIONS, questionDeSuggestion, filApresRecommencer, BULLE_PRESENT,
  MODE_ANALYSE, peutApprofondir, peutApprofondirEntree, analyseBornee,
} from './compagnon.js'

const lire = (chemin) => readFileSync(new URL(chemin, import.meta.url), 'utf8')

const CARTE = {
  id: 7, nature: 'geste', etat: 'en_attente', confirmable: true, resume: 'semis · radis', lignes: ['semis · radis'],
  phrase: 'j’ai semé des radis sur la planche sud 2 rangs', items: [], avertissements: [],
}

// ── CA1 : deux modes ────────────────────────────────────────────────────────

test('[CA1] le panneau a deux modes, Normal d’abord', () => {
  assert.deepEqual(MODES.map((m) => m.id), ['normal', 'support'])
  assert.equal(MODE_DEFAUT, 'normal')
  assert.equal(modeDe('support').libelle, 'Support')
  assert.equal(modeDe('inconnu').id, 'normal')
  assert.equal(modeValide('support'), true)
  assert.equal(modeValide('extra'), false)   // Extra viendra avec US-274
})

test('[CA1] le mode Support dit qu’il n’écrit rien', () => {
  assert.match(modeDe('support').aide, /Rien n’est écrit/)
})

// ── CA2 : cartes et boutons ─────────────────────────────────────────────────

test('[CA2] une carte de geste à confirmer a Confirmer, Corriger, Abandonner', () => {
  assert.deepEqual(boutonsCarte(CARTE).map((b) => b.id), ['confirmer', 'corriger', 'abandonner'])
  assert.equal(etatCarte(CARTE).libelle, 'À confirmer')
  assert.ok(boutonsCarte(CARTE).every((b) => b.actif))
})

test('[CA2] pendant un envoi, aucun bouton n’est actif (pas de double clic)', () => {
  assert.ok(boutonsCarte(CARTE, true).every((b) => !b.actif))
})

test('[CA2] une commande ne se confirme pas ici : Confirmer est inactif et la carte le dit', () => {
  const commande = { ...CARTE, nature: 'commande', confirmable: false, phrase: null }
  const boutons = boutonsCarte(commande)
  assert.equal(boutons.find((b) => b.id === 'confirmer').actif, false)
  assert.equal(boutons.some((b) => b.id === 'corriger'), false)
  assert.match(etatCarte(commande).libelle, /Telegram/)
  assert.ok(boutons.find((b) => b.id === 'abandonner').actif)   // on peut la laisser tomber
})

test('[US-289] une commande à exécuteur de service se confirme ici ; une confirmée relit les écrans', () => {
  const commande = { ...CARTE, nature: 'commande', confirmable: true, phrase: null }
  assert.equal(boutonsCarte(commande).find((b) => b.id === 'confirmer').actif, true)
  assert.equal(etatCarte(commande).libelle, 'À confirmer')
  const issue = { carte: { ...commande, etat: 'confirmee' }, texte: '✅ Parcelle « Sud » mise à jour', enregistres: [], erreur: null }
  assert.equal(aEnregistre(issue), true)
  assert.deepEqual(boutonsCarte(carteApresIssue(commande, issue)), [])
})

test('[US-289] une commande confirmée mais refusée par le service est fermée, avec la raison', () => {
  const commande = { ...CARTE, nature: 'commande', confirmable: true, phrase: null }
  const issue = { carte: { ...commande, etat: 'echouee', confirmable: false }, texte: '❌ rangs invalides', enregistres: [], erreur: 'rangs invalides' }
  const apres = carteApresIssue(commande, issue)
  assert.equal(etatCarte(apres).id, 'echouee')
  assert.deepEqual(boutonsCarte(apres), [])
  assert.equal(apres.erreur, 'rangs invalides')
  assert.equal(aEnregistre(issue), false)
})

test('[US-289] « vas-y » dit dans le panneau met la carte existante à jour sans la dupliquer', () => {
  const commande = { ...CARTE, nature: 'commande', confirmable: true, phrase: null }
  const fil = [{ cle: 'c1', role: 'compagnon', texte: 'Voici', cartes: [commande] }]
  const reponse = { texte: '✅ Fait', vers: 'decision', propositions: [{ ...commande, etat: 'confirmee' }] }
  const apres = ajouterEchange(fil, 'vas-y', reponse)
  assert.equal(apres[0].cartes[0].etat, 'confirmee')
  assert.deepEqual(apres[apres.length - 1].cartes, [])
})

test('[CA2][Gherkin] une carte confirmée affiche « ✅ Confirmé » et n’a plus de bouton', () => {
  const issue = { carte: { ...CARTE, etat: 'confirmee' }, texte: '✅ Confirmé', enregistres: [{ event_id: 1, resume: 'arrosage · serre' }], erreur: null }
  const apres = carteApresIssue(CARTE, issue)
  assert.equal(etatCarte(apres).libelle, '✅ Confirmé')
  assert.deepEqual(boutonsCarte(apres), [])
  assert.equal(aEnregistre(issue), true)
})

test('[CA2] un refus d’écriture laisse la carte en attente, avec le motif', () => {
  const issue = { carte: { ...CARTE }, texte: '❌ Parcelle introuvable', enregistres: [], erreur: 'Parcelle introuvable' }
  const apres = carteApresIssue(CARTE, issue)
  assert.equal(etatCarte(apres).id, 'erreur')
  assert.equal(etatCarte(apres).finale, false)      // on peut corriger ou abandonner
  assert.equal(aEnregistre(issue), false)
})

test('[CA2] abandonné, expiré, remplacé : états finaux nommés', () => {
  for (const [etat, motif] of [['abandonnee', /Abandonné/], ['perimee', /Expiré/], ['remplacee', /Remplacé/]]) {
    const e = etatCarte({ ...CARTE, etat })
    assert.match(e.libelle, motif)
    assert.equal(e.finale, true)
  }
})

test('[CA2] « Corriger » ramène la phrase d’origine dans la saisie', () => {
  assert.equal(texteACorriger(CARTE), CARTE.phrase)
  assert.equal(texteACorriger(null), '')
})

// ── CA3 : messages spontanés rangés dans le panneau ─────────────────────────

test('[CA3] les messages spontanés ouvrent le fil, avant la conversation', () => {
  const fil = filDepuisHistorique({
    spontanes: [{ id: 3, texte: 'Les tomates ont soif.', envoye_le: '2026-11-05T07:00:00', genre: 'signal', themes: ['arrosage'] }],
    echanges: [{ jardinier: 'bonjour', compagnon: 'réponse : salut', ts: '2026-11-05T08:00:00Z' }],
    cartes: [CARTE],
  })
  assert.deepEqual(fil.map((e) => e.role), ['spontane', 'jardinier', 'compagnon', 'compagnon'])
  assert.equal(fil[0].texte, 'Les tomates ont soif.')
  assert.equal(fil[3].cartes[0].id, 7)               // les cartes en cours ferment le fil
})

test('[CA3] un historique vide donne un fil vide', () => {
  assert.deepEqual(filDepuisHistorique({}), [])
  assert.deepEqual(filDepuisHistorique(null), [])
})

test('[CA3] un échange ajoute la phrase puis la réponse avec ses cartes', () => {
  const fil = ajouterEchange([], 'j’ai arrosé la serre', {
    texte: 'Voici ce que j’ai compris.', vers: 'geste', propositions: [CARTE], avertissements: ['Rotation : …'],
  })
  assert.deepEqual(fil.map((e) => e.role), ['jardinier', 'compagnon'])
  assert.equal(fil[1].cartes[0].id, 7)
  assert.deepEqual(fil[1].avertissements, ['Rotation : …'])
  assert.equal(cartesEnAttente(fil).length, 1)
})

test('[CA3] une réponse de savoir porte de quoi la noter 👍/👎', () => {
  const fil = ajouterEchange([], 'quand semer les poireaux ?', { texte: 'En mars.', vers: 'question', routage_log_id: 12, etage: 'savoir' })
  assert.equal(fil[1].routageLogId, 12)
  assert.equal(fil[1].etage, 'savoir')
})

test('[CA2] remplacer une carte la met à jour partout, sans toucher les autres', () => {
  const autre = { ...CARTE, id: 8 }
  let fil = ajouterEchange([], 'x', { texte: 't', propositions: [CARTE, autre] })
  fil = remplacerCarte(fil, { ...CARTE, etat: 'confirmee' })
  assert.equal(fil[1].cartes[0].etat, 'confirmee')
  assert.equal(fil[1].cartes[1].etat, 'en_attente')
})

test('[CA2] une nouvelle proposition de geste ferme l’ancienne, comme le fait le serveur', () => {
  let fil = ajouterEchange([], 'x', { texte: 't', propositions: [CARTE] })
  const nouvelle = { ...CARTE, id: 9 }
  fil = ajouterEchange(fil, 'non, 4 rangs', { texte: 't', propositions: [nouvelle] })
  fil = remplacerLesAnciennes(fil, [nouvelle])
  assert.equal(fil[1].cartes[0].etat, 'remplacee')
  assert.equal(fil[3].cartes[0].etat, 'en_attente')
  assert.deepEqual(cartesEnAttente(fil).map((c) => c.id), [9])
})

// ── CA4 : erreurs en clair ──────────────────────────────────────────────────

test('[CA4] une coupure réseau est dite, et dit que rien n’est parti', () => {
  const e = new TypeError('Failed to fetch')
  assert.equal(messageErreur(e), TEXTE_RESEAU)
  assert.match(TEXTE_RESEAU, /rien n’a été enregistré/)
  assert.equal(messageErreur(new Error('Load failed')), TEXTE_RESEAU)
})

test('[CA4] une proposition déjà traitée reprend le message du serveur (où et quand)', () => {
  const e = Object.assign(new Error('Cette proposition a déjà été confirmée à 14 h 02, dans Telegram : je ne refais rien.'), { statut: 409, code: 'deja_traitee' })
  assert.match(messageErreur(e), /dans Telegram/)
  assert.equal(carteDefinitivementFermee(e), true)
})

test('[CA4] une proposition introuvable ou expirée est dite, sans code technique', () => {
  const e = Object.assign(new Error('Proposition introuvable'), { statut: 404 })
  assert.match(messageErreur(e), /expiré|remplacé/)
  assert.doesNotMatch(messageErreur(e), /404/)
  assert.equal(carteDefinitivementFermee(e), true)
})

test('[CA4] une erreur serveur brute n’est jamais montrée telle quelle', () => {
  const e = Object.assign(new Error('Erreur API 500 sur /compagnon/messages'), { statut: 500 })
  assert.doesNotMatch(messageErreur(e), /500|API/)
  assert.match(messageErreur(e), /Rien n’a été enregistré/)
  assert.match(messageErreur(null), /Rien n’a été enregistré/)
})

test('[CA4] le modèle indisponible reprend le message de repli du serveur', () => {
  const e = Object.assign(new Error('Le service est surchargé'), { statut: 503 })
  assert.equal(messageErreur(e), 'Le service est surchargé')
  assert.match(messageErreur(Object.assign(new Error(''), { statut: 503 })), /indisponible/)
})

test('[CA4] un lecteur qui tente d’enregistrer reçoit le refus du serveur', () => {
  const e = Object.assign(new Error('Action réservée aux éditeurs'), { statut: 403 })
  assert.equal(messageErreur(e), 'Action réservée aux éditeurs')
})

test('[CA4] l’erreur entre dans le fil, après la phrase du jardinier', () => {
  const fil = ajouterErreur([], new TypeError('Failed to fetch'), 'j’ai arrosé')
  assert.deepEqual(fil.map((e) => e.role), ['jardinier', 'erreur'])
  assert.equal(fil[1].texte, TEXTE_RESEAU)
})

test('[CA1] la phrase du jardinier est dans le fil dès l’envoi, avant toute réponse', () => {
  const cleJ = cleDePhrase()
  const fil = ajouterPhrase([], 'cette planche fait 20 m²', cleJ)
  assert.deepEqual(fil.map((e) => [e.role, e.texte]), [['jardinier', 'cette planche fait 20 m²']])
  assert.equal(fil[0].cle, cleJ)
})

test('[CA1] la réponse reprend la phrase déjà affichée : elle n’est pas dupliquée', () => {
  const cleJ = cleDePhrase()
  const avant = ajouterPhrase([], 'quand semer les poireaux ?', cleJ)
  const fil = ajouterEchange(avant, 'quand semer les poireaux ?', { texte: 'En mars.', vers: 'question' }, cleJ)
  assert.deepEqual(fil.map((e) => e.role), ['jardinier', 'compagnon'])
  assert.equal(fil[0].cle, cleJ)
})

test('[CA1] l’erreur reprend elle aussi la phrase déjà affichée', () => {
  const cleJ = cleDePhrase()
  const avant = ajouterPhrase([], 'j’ai arrosé', cleJ)
  const fil = ajouterErreur(avant, new TypeError('Failed to fetch'), 'j’ai arrosé', cleJ)
  assert.deepEqual(fil.map((e) => e.role), ['jardinier', 'erreur'])
})

test('[CA1] si le fil a été remis à zéro pendant l’attente, la réponse remet la phrase', () => {
  // « Recommencer » pendant que Gaston réfléchit : la bulle d’avant l’envoi n’existe plus.
  const cleJ = cleDePhrase()
  const fil = ajouterEchange([], 'x', { texte: 'ok', vers: 'question' }, cleJ)
  assert.deepEqual(fil.map((e) => e.role), ['jardinier', 'compagnon'])
  assert.equal(fil[0].cle, cleJ)
})

test('[CA4] une carte fermée par le serveur garde la raison, dite par le serveur', () => {
  const e = Object.assign(new Error('Cette proposition a déjà été abandonnée à 9 h 15, dans l’application : je ne refais rien.'), { statut: 409 })
  const fermee = carteFermee(CARTE, e)
  assert.equal(etatCarte(fermee).id, 'abandonnee')
  assert.match(fermee.note, /abandonnée/)
})

// ── Saisie ──────────────────────────────────────────────────────────────────

test('on n’envoie ni un message vide, ni pendant un envoi, ni un roman', () => {
  assert.equal(peutEnvoyer('   ', false), false)
  assert.equal(peutEnvoyer('bonjour', true), false)
  assert.equal(peutEnvoyer('bonjour', false), true)
  assert.equal(peutEnvoyer('x'.repeat(LONGUEUR_MAX + 1), false), false)
})

// ── CA5 : container queries dans le panneau, breakpoints pour la page ───────

test('[CA5] le panneau se met en page par container queries, jamais par breakpoint d’écran', () => {
  const panneau = lire('../components/PanneauCompagnon.jsx')
  const carte = lire('../components/CarteProposition.jsx')
  for (const [nom, source] of [['PanneauCompagnon', panneau], ['CarteProposition', carte]]) {
    assert.match(source, /@container/, `${nom} doit porter un @container`)
    // Aucun préfixe de breakpoint d'écran sur les classes du composant (md:, lg:, nav:, min-[…]).
    const classes = source.match(/className=(?:"[^"]*"|\{`[^`]*`\})/g)?.join(' ') ?? ''
    assert.doesNotMatch(classes, /(?:^|\s)(?:sm|md|lg|xl|nav):|min-\[\d+px\]:/, `${nom} : breakpoint d’écran dans un composant`)
  }
})

test('[CA5] le bouton flottant est posé par la structure de page (App), pas par le panneau', () => {
  const app = lire('../App.jsx')
  assert.match(app, /BoutonCompagnon/)
  assert.match(app, /PanneauCompagnon/)
})

test('[CA1][CA2] la PWA ne confirme rien elle-même : un seul chemin d’écriture, l’API du compagnon', () => {
  for (const f of ['../components/PanneauCompagnon.jsx', '../components/CarteProposition.jsx']) {
    const source = lire(f)
    assert.doesNotMatch(source, /fetch\(/, `${f} ne doit pas appeler fetch directement`)
  }
  const api = lire('./api.js')
  assert.match(api, /confirmerProposition/)
})

// ── La maquette « Compagnon.html » : Gaston et ses trois états ──────────────

test('[CA1][maquette] trois états : replié, présent, chat ouvert — présent par défaut', () => {
  assert.deepEqual(ETATS, ['replie', 'present', 'chat'])
  assert.equal(ETAT_PAR_DEFAUT, 'present')
  assert.equal(GASTON.nom, 'Gaston')
})

test('[CA1][maquette] les passages d’un état à l’autre sont ceux de la maquette', () => {
  assert.equal(etatSuivant('present', 'ouvrir'), 'chat')          // l'avatar ouvre le chat
  assert.equal(etatSuivant('chat', 'fermer'), 'present')          // la croix revient à l'avatar
  assert.equal(etatSuivant('present', 'replier'), 'replie')       // le petit bouton replie
  assert.equal(etatSuivant('replie', 'deplier'), 'present')       // le chevron déplie
  assert.equal(etatSuivant('replie', 'replier'), 'replie')        // rien d'absurde : replier un replié
  assert.equal(etatSuivant('chat', 'replier'), 'chat')
  assert.equal(etatSuivant('present', 'inconnu'), 'present')
})

test('[CA1] replié ou présent sont retenus ; le chat ne se rouvre jamais tout seul', () => {
  const memoire = new Map()
  const stockage = { getItem: (k) => memoire.get(k) ?? null, setItem: (k, v) => memoire.set(k, v) }
  assert.equal(lireEtat(stockage), 'present')
  ecrireEtat(stockage, 'replie')
  assert.equal(lireEtat(stockage), 'replie')
  ecrireEtat(stockage, 'chat')                                    // refusé : pas retenu
  assert.equal(memoire.get(CLE_ETAT), 'replie')
  memoire.set(CLE_ETAT, 'chat')                                   // une valeur ancienne ou trafiquée
  assert.equal(lireEtat(stockage), 'present')
})

test('[CA1] sans stockage (navigation privée), le compagnon reste utilisable', () => {
  const casse = { getItem() { throw new Error('bloqué') }, setItem() { throw new Error('bloqué') } }
  assert.equal(lireEtat(casse), 'present')
  assert.doesNotThrow(() => ecrireEtat(casse, 'replie'))
  assert.equal(lireEtat(undefined), 'present')
})

test('[maquette] l’accueil et les raccourcis sont ceux de la maquette, dans chaque mode', () => {
  assert.match(ACCUEIL.normal, /Gaston, la carotte du potager/)
  assert.equal(SUGGESTIONS.normal.length, 4)
  assert.equal(questionDeSuggestion('🌱 Que semer cette semaine ?'), 'Que semer cette semaine ?')
  assert.match(ACCUEIL.support, /rien dans votre carnet/)
  assert.ok(SUGGESTIONS.support.length >= 3)
  assert.equal(BULLE_PRESENT, 'Besoin d’un coup de main ?')
})

test('[maquette] « Recommencer » ne laisse à l’écran que les cartes qui attendent encore', () => {
  assert.deepEqual(filApresRecommencer({ cartes: [] }), [])
  assert.deepEqual(filApresRecommencer(null), [])
  const fil = filApresRecommencer({ cartes: [CARTE] })
  assert.equal(fil.length, 1)
  assert.equal(fil[0].cartes[0].id, 7)
})

test('[maquette] l’en-tête du chat porte les trois boutons ronds : Support, Recommencer, Fermer', () => {
  const panneau = lire('../components/PanneauCompagnon.jsx')
  for (const libelle of ['Passer en mode Support', 'Recommencer', 'Fermer']) {
    assert.match(panneau, new RegExp(libelle), libelle)
  }
  assert.ok(panneau.includes('aria-pressed={support}'))               // le casque est un interrupteur
  assert.match(panneau, /Agent dédié/)                              // la mention du pied de la maquette
  assert.match(panneau, /Version bêta/)
})

test('[maquette] le bouton flottant a deux visages, replié (chevron) et présent (avatar, main, pastille)', () => {
  const bouton = lire('../components/BoutonCompagnon.jsx')
  assert.match(bouton, /gst-tab/)
  assert.match(bouton, /gst-pres/)
  assert.match(bouton, /gst-dot/)
  assert.match(bouton, /Parler au compagnon/)
  const css = lire('../index.css')
  assert.match(css, /prefers-reduced-motion/)                       // les animations se coupent à la demande
})

test('[CA5] le placement du chat (plein écran / carte flottante) est décidé par la page, pas par le panneau', () => {
  const app = lire('../App.jsx')
  assert.ok(app.includes("useMedia('(max-width: 639px)')"))
  assert.ok(app.includes('w-[380px]'))
  assert.ok(app.includes('h-[600px]'))
})

// ── [US-272] Deux fenêtres : l'état réel des cartes, la pastille des non-lus ─
import {
  fusionnerEtat, compterNonLus, vuDepuisEtat, lireVu, ecrireVu, CLE_VU, libellePastille,
  INTERVALLE_OUVERT_MS, INTERVALLE_FERME_MS,
} from './compagnon.js'

const FIL_AVEC_CARTE = () => [{ cle: 'c1', role: 'compagnon', texte: 'Voici', cartes: [{ ...CARTE }] }]

test('[US-272 / CA3] confirmée dans Telegram, la carte du panneau le dit', () => {
  const carte = { ...CARTE, etat: 'confirmee', traite_canal: 'telegram', etat_dit: '✅ Confirmé depuis Telegram à 14:32' }
  assert.equal(etatCarte(carte).libelle, '✅ Confirmé depuis Telegram à 14:32')
  assert.equal(etatCarte({ ...carte, traite_canal: 'pwa' }).libelle, '✅ Confirmé')
})

test('[US-272 / CA5] la relecture fait suivre à la carte son état réel', () => {
  const fil = fusionnerEtat(FIL_AVEC_CARTE(), {
    cartes: [], traitees: [{ ...CARTE, etat: 'confirmee', traite_canal: 'telegram', confirmable: false }], spontanes: [],
  })
  const carte = fil[0].cartes[0]
  assert.equal(carte.etat, 'confirmee')
  assert.deepEqual(boutonsCarte(carte), [])
})

test('[US-272 / CA5] une carte inchangée garde son erreur locale', () => {
  const fil = [{ cle: 'c1', role: 'compagnon', cartes: [{ ...CARTE, erreur: 'réseau' }] }]
  assert.equal(fusionnerEtat(fil, { cartes: [{ ...CARTE }], traitees: [], spontanes: [] })[0].cartes[0].erreur, 'réseau')
})

test('[US-272 / CA5] une carte née dans Telegram et un message spontané nouveaux s’ajoutent, une fois', () => {
  const etat = {
    cartes: [{ ...CARTE }, { ...CARTE, id: 9, nature: 'commande', confirmable: false }],
    traitees: [], spontanes: [{ id: 3, texte: 'Gel demain', envoye_le: '2026-11-06T18:00:00', genre: 'signal' }],
  }
  const une = fusionnerEtat(FIL_AVEC_CARTE(), etat)
  assert.deepEqual(une.flatMap((e) => e.cartes ?? []).map((c) => c.id), [7, 9])
  assert.equal(une.filter((e) => e.role === 'spontane').length, 1)
  assert.equal(fusionnerEtat(une, etat).length, une.length)
})

test('[US-272 / CA5] la pastille compte ce qui est arrivé depuis la dernière ouverture', () => {
  const etat = {
    spontanes: [{ id: 3 }, { id: 5 }],
    cartes: [{ ...CARTE, id: 8 }, { ...CARTE, id: 12 }],
    traitees: [{ ...CARTE, id: 14, etat: 'confirmee' }],
  }
  assert.equal(compterNonLus(etat, { spontane: 3, carte: 8 }), 2)
  assert.deepEqual(vuDepuisEtat(etat), { spontane: 5, carte: 14 })
  assert.equal(compterNonLus(etat, vuDepuisEtat(etat)), 0)
  assert.equal(compterNonLus(etat, null), 0)
  assert.equal(libellePastille(0), '')
  assert.equal(libellePastille(3), '3')
  assert.equal(libellePastille(12), '9+')
  assert.ok(INTERVALLE_OUVERT_MS < INTERVALLE_FERME_MS)
})

test('[US-272 / CA5] le « vu » survit à un stockage indisponible', () => {
  const memoire = new Map()
  const stockage = { getItem: (k) => memoire.get(k) ?? null, setItem: (k, v) => memoire.set(k, v) }
  ecrireVu(stockage, { spontane: 2, carte: 4 })
  assert.deepEqual(lireVu(stockage), { spontane: 2, carte: 4 })
  assert.ok(memoire.has(CLE_VU))
  const casse = { getItem: () => { throw new Error('privé') }, setItem: () => { throw new Error('privé') } }
  assert.equal(lireVu(casse), null)
  ecrireVu(casse, { spontane: 1, carte: 1 })
})

test('[US-272 / CA2] un 409 ferme la carte avec l’état que le serveur donne', () => {
  const err = Object.assign(new Error('Déjà laissé tomber depuis Telegram à 14:32 : rien n’est fait.'),
    { statut: 409, code: 'deja_traitee', etat: 'abandonnee' })
  const fermee = carteFermee(CARTE, err)
  assert.equal(fermee.etat, 'abandonnee')
  assert.match(fermee.note, /depuis Telegram/)
})

test('[US-272 / CA9] sans compagnon de terrain, l’invitation entre dans le fil', () => {
  const fil = filDepuisHistorique({ spontanes: [], echanges: [], cartes: [], invitation_telegram: 'Active-le' })
  assert.deepEqual(fil.map((e) => [e.role, e.texte]), [['spontane', 'Active-le']])
  assert.equal(filDepuisHistorique({ invitation_telegram: null }).length, 0)
})

test('[US-272 / CA5] la pastille et le potager de la carte sont posés par l’écran', () => {
  const bouton = lire('../components/BoutonCompagnon.jsx')
  const carte = lire('../components/CarteProposition.jsx')
  assert.match(bouton, /gst-nonlus/)
  assert.match(carte, /carte\.potager/)
})

// ── [US-273] « Approfondir » : une analyse en lecture seule ─────────────────

test('[US-273 / CA1] « Approfondir » demande le mode analyse, sans en faire un mode du panneau', () => {
  assert.equal(MODE_ANALYSE, 'analyse')
  assert.equal(modeValide(MODE_ANALYSE), false)
  assert.equal(MODES.length, 2)
})

test('[US-273 / CA1] le bouton de la saisie suit la règle d’« Envoyer »', () => {
  assert.equal(peutApprofondir('pourquoi si peu de tomates ?', false), true)
  assert.equal(peutApprofondir('   ', false), false)
  assert.equal(peutApprofondir('pourquoi ?', true), false)
})

test('[US-273 / CA1] « Approfondir » n’apparaît que sous la réponse à une question', () => {
  const question = ajouterEchange([], 'pourquoi mes tomates ont peu donné ?', { texte: 'Peut-être le mildiou.', vers: 'question' })[1]
  assert.equal(question.phrase, 'pourquoi mes tomates ont peu donné ?')
  assert.equal(peutApprofondirEntree(question), true)
  const geste = ajouterEchange([], 'j’ai arrosé', { texte: 'ok', vers: 'geste', propositions: [CARTE] })[1]
  assert.equal(peutApprofondirEntree(geste), false)
  const analyse = ajouterEchange([], 'x', { texte: 'Synthèse', vers: 'analyse', sources: [], borne: null })[1]
  assert.equal(peutApprofondirEntree(analyse), false)
  assert.equal(peutApprofondirEntree({ role: 'jardinier', texte: 'x' }), false)
})

test('[US-273 / CA3, CA4] une analyse garde ses sources et dit si elle a été coupée', () => {
  const entree = ajouterEchange([], 'pourquoi ?', {
    texte: 'Synthèse', vers: 'analyse', sources: ['Mildiou de la tomate'], borne: 'tours',
  })[1]
  assert.deepEqual(entree.sources, ['Mildiou de la tomate'])
  assert.equal(analyseBornee(entree), true)
  const entiere = ajouterEchange([], 'pourquoi ?', { texte: 'Synthèse', vers: 'analyse', sources: [], borne: null })[1]
  assert.equal(analyseBornee(entiere), false)
})

test('[US-273 / CA1] le panneau lance l’analyse par le mode « analyse » de l’API, sans autre chemin', () => {
  const panneau = lire('../components/PanneauCompagnon.jsx')
  assert.match(panneau, /MODE_ANALYSE/)
  assert.match(panneau, /Approfondir/)
  // Un seul endroit appelle l'API : `messageCompagnon`, avec le mode — pas de route d'écriture à part.
  assert.equal((panneau.match(/api\.messageCompagnon/g) ?? []).length, 1)
})
