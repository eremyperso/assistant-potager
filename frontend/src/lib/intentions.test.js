// [US-195] Navigation contextuelle — `npm test`.
//
// Ce que le CA11 demande de couvrir, un test par point : clés reconnues, valeurs
// invalides, clé inconnue, intention par l'adresse, retrait de l'adresse,
// conservation à travers la connexion, restitution d'un état de niveau, et
// priorité de l'intention sur cet état.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  INTENTIONS, CLE_VUE, CLE_POTAGER,
  clesDe, vuesAvecIntention, validerIntention,
  lireIntentionAdresse, adresseSansIntention, adresseAvecIntention, consommerIntentionAdresse,
  creerMemoireEcrans, etatInitial,
} from './intentions.js'

// ── CA2 : les intentions reconnues, et elles seules ─────────────────────────

test('[CA2] les cinq vues du tableau, avec exactement leurs clés', () => {
  assert.deepEqual(vuesAvecIntention().sort(), ['cultures', 'journal', 'pepiniere', 'plan', 'plan-vue'])
  assert.deepEqual(clesDe('plan'), ['parcelle'])
  assert.deepEqual(clesDe('plan-vue'), ['parcelle'])
  assert.deepEqual(clesDe('cultures'), ['culture'])
  assert.deepEqual(clesDe('pepiniere'), ['onglet', 'emplacement', 'lot'])
  assert.deepEqual(clesDe('journal'), ['date', 'culture'])
})

test('[CA2] une vue hors du tableau n’a pas d’intention', () => {
  assert.deepEqual(clesDe('stocks'), [])
  assert.equal(validerIntention('stocks', { culture: 'tomate' }), null)
  assert.equal(validerIntention('bord', { parcelle: 3 }), null)
})

test('[CA2] une clé inconnue est ignorée, les autres passent', () => {
  assert.deepEqual(validerIntention('plan', { parcelle: 7, couleur: 'rouge' }), { parcelle: 7 })
})

test('[CA2] une intention entièrement inconnue rend null, pas un objet vide', () => {
  assert.equal(validerIntention('plan', { couleur: 'rouge' }), null)
  assert.equal(validerIntention('plan', {}), null)
  assert.equal(validerIntention('plan', null), null)
})

test('[CA2] une valeur invalide est écartée comme une clé inconnue', () => {
  assert.equal(validerIntention('plan', { parcelle: 'nord' }), null)      // identifiant attendu
  assert.equal(validerIntention('plan', { parcelle: -1 }), null)
  assert.equal(validerIntention('plan', { parcelle: 1.5 }), null)
  assert.equal(validerIntention('journal', { date: '19/09/2026' }), null) // ISO attendu
  assert.equal(validerIntention('cultures', { culture: '   ' }), null)
})

test('[CA2] une valeur valide est normalisée sans être réinterprétée', () => {
  assert.deepEqual(validerIntention('plan', { parcelle: '12' }), { parcelle: 12 })
  assert.deepEqual(validerIntention('journal', { date: ' 2026-09-19 ' }), { date: '2026-09-19' })
  assert.deepEqual(validerIntention('pepiniere', { lot: '128' }), { lot: '128' })
})

// ── CA5 : l’intention par l’adresse ─────────────────────────────────────────

test('[CA5] une adresse d’intention est lue et validée', () => {
  assert.deepEqual(
    lireIntentionAdresse({ pathname: '/', search: '?vue=pepiniere&lot=128' }),
    { vue: 'pepiniere', intention: { lot: '128' }, potager: null },
  )
})

test('[CA5] une vue inconnue dans l’adresse n’est pas une intention', () => {
  assert.equal(lireIntentionAdresse({ pathname: '/', search: '?vue=admin&lot=1' }), null)
  assert.equal(lireIntentionAdresse({ pathname: '/', search: '?lot=128' }), null)
  assert.equal(lireIntentionAdresse({ pathname: '/', search: '' }), null)
})

test('[CA5] les trois entrées existantes ne sont JAMAIS interceptées', () => {
  // US-057 (mot de passe), US-044 (vérification d’e-mail), US-090 (retour OAuth).
  assert.equal(lireIntentionAdresse({ pathname: '/reinitialiser-mot-de-passe', search: '?token=abc&vue=plan' }), null)
  assert.equal(lireIntentionAdresse({ pathname: '/verifier-email', search: '?token=abc' }), null)
  assert.equal(lireIntentionAdresse({ pathname: '/auth/callback', search: '?vue=plan' }), null)
})

test('[CA5] l’adresse est nettoyée de tout ce qui relève de l’intention', () => {
  assert.equal(
    adresseSansIntention({ pathname: '/', search: '?vue=pepiniere&lot=128&potager=4' }),
    '/',
  )
})

test('[CA5] le nettoyage laisse intacts les paramètres qui ne sont pas à nous', () => {
  assert.equal(
    adresseSansIntention({ pathname: '/', search: '?vue=plan&parcelle=3&utm=mail', hash: '#bas' }),
    '/?utm=mail#bas',
  )
})

test('[CA5] l’adresse est lue UNE fois puis effacée : recharger ne rejoue rien', () => {
  const appels = []
  const fenetre = {
    location: { pathname: '/', search: '?vue=pepiniere&lot=128', hash: '' },
    history: { replaceState: (_e, _t, url) => appels.push(url) },
  }
  const lue = consommerIntentionAdresse(fenetre)
  assert.deepEqual(lue.intention, { lot: '128' })
  assert.deepEqual(appels, ['/'])

  // Ce que verrait un rechargement, l’adresse ayant été nettoyée.
  assert.equal(lireIntentionAdresse({ pathname: '/', search: '' }), null)
})

test('[CA5] une adresse sans intention ne touche pas à la barre d’adresse', () => {
  let touche = false
  const fenetre = {
    location: { pathname: '/', search: '?utm=mail', hash: '' },
    history: { replaceState: () => { touche = true } },
  }
  assert.equal(consommerIntentionAdresse(fenetre), null)
  assert.equal(touche, false)
})

// ── CA6 : l’intention survit à la connexion ─────────────────────────────────

test('[CA6] l’intention lue avant la connexion est rendue à l’appelant, pas perdue', () => {
  // Le module la lit AU CHARGEMENT — avant tout écran — et la rend : c’est
  // l’appelant (`App.jsx`) qui la garde en mémoire de page pendant que l’écran
  // d’authentification s’intercale. Rien n’est écrit ni relu depuis l’adresse.
  const fenetre = {
    location: { pathname: '/', search: '?vue=pepiniere&lot=128', hash: '' },
    history: { replaceState: () => {} },
  }
  const gardee = consommerIntentionAdresse(fenetre)
  assert.deepEqual(gardee, { vue: 'pepiniere', intention: { lot: '128' }, potager: null })
  // Après connexion, elle est toujours exploitable telle quelle.
  assert.deepEqual(validerIntention(gardee.vue, gardee.intention), { lot: '128' })
})

// ── CA7 : l’intention peut nommer un potager ────────────────────────────────

test('[CA7] le potager est lu à part, et n’est jamais une clé de vue', () => {
  const lue = lireIntentionAdresse({ pathname: '/', search: '?vue=plan&parcelle=3&potager=4' })
  assert.equal(lue.potager, 4)
  assert.deepEqual(lue.intention, { parcelle: 3 })
  assert.ok(!Object.keys(INTENTIONS).some((v) => clesDe(v).includes(CLE_POTAGER)))
})

test('[CA7] une intention se remet dans l’adresse pour survivre au rechargement', () => {
  const url = adresseAvecIntention({ vue: 'pepiniere', intention: { lot: '128' }, potager: 4 })
  assert.equal(url, `/?${CLE_VUE}=pepiniere&lot=128&${CLE_POTAGER}=4`)
  // Aller-retour : ce qu’on remet est exactement ce qu’on relit.
  assert.deepEqual(
    lireIntentionAdresse({ pathname: '/', search: url.slice(1) }),
    { vue: 'pepiniere', intention: { lot: '128' }, potager: 4 },
  )
})

// ── CA9 : la mémoire des niveaux ────────────────────────────────────────────

test('[CA9] un écran quitté puis rouvert est rendu dans son état exact', () => {
  const memoire = creerMemoireEcrans()
  memoire.ecrire('pepiniere', { q: 'tom', tri: 'Ancien → Récent', defilement: 420 })
  assert.deepEqual(memoire.lire('pepiniere'), { q: 'tom', tri: 'Ancien → Récent', defilement: 420 })
})

test('[CA9] la mémoire est par écran : deux vues ne se mélangent pas', () => {
  const memoire = creerMemoireEcrans()
  memoire.ecrire('plan', { parcelle: 3 })
  memoire.ecrire('plan-vue', { parcelle: 7 })
  assert.deepEqual(memoire.lire('plan'), { parcelle: 3 })
  assert.deepEqual(memoire.lire('plan-vue'), { parcelle: 7 })
  assert.equal(memoire.lire('journal'), null)
})

test('[CA9] la mémoire est une COPIE : muter l’objet rendu ne la corrompt pas', () => {
  const memoire = creerMemoireEcrans()
  const etat = { q: 'tom' }
  memoire.ecrire('pepiniere', etat)
  etat.q = 'courge'
  assert.deepEqual(memoire.lire('pepiniere'), { q: 'tom' })
})

test('[CA9] l’état mémorisé complète les valeurs par défaut', () => {
  assert.deepEqual(
    etatInitial({ defauts: { q: '', tri: 'Récent → Ancien' }, memorise: { q: 'tom' } }),
    { q: 'tom', tri: 'Récent → Ancien' },
  )
})

test('[CA9, CA1] une intention reçue l’emporte TOUJOURS sur l’état mémorisé', () => {
  assert.deepEqual(
    etatInitial({
      defauts: { search: '', parcelle: null },
      memorise: { search: 'tom', parcelle: 3 },
      intention: { parcelle: 7 },
    }),
    { search: 'tom', parcelle: 7 },
  )
})

test('[CA9] sans mémoire ni intention, les valeurs par défaut sont rendues telles quelles', () => {
  assert.deepEqual(etatInitial({ defauts: { q: '' } }), { q: '' })
  assert.deepEqual(etatInitial(), {})
})

// ── CA9, CA10 : ce qui ne doit PAS être fait ────────────────────────────────

test('[CA9] rien n’est persisté : ni localStorage, ni sessionStorage, ni cookie', () => {
  // On cherche un USAGE (`localStorage.setItem(...)`), pas la mention du mot
  // dans un commentaire qui explique justement qu'on n'en veut pas.
  const source = readFileSync(new URL('./intentions.js', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /(localStorage|sessionStorage|document\.cookie)\s*[.[=]/)
})

test('[CA10] aucun routeur, et le bouton Retour reste intact', () => {
  const lib = readFileSync(new URL('./intentions.js', import.meta.url), 'utf8')
  const coquille = readFileSync(new URL('../App.jsx', import.meta.url), 'utf8')
  // `pushState` empilerait une entrée d’historique ; seul `replaceState` est utilisé.
  assert.doesNotMatch(lib, /pushState|react-router|createBrowserRouter/)
  assert.doesNotMatch(coquille, /pushState|react-router|createBrowserRouter/)
})
