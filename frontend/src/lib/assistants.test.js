// [US-294] Logique pure de l'écran « Assistants connectés ». Lancement : `npm test`.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  AIDE_ASSISTANTS, assistantsDits, dateCourte, DUREES_JETON, libelleOutil, lienGeste, potagersDits,
  libelleAnciennes, repartirConnexions, revocable, TEXTE_AUCUNE_ACTIVE,
} from './assistants.js'

test('[CA7] l’aide rappelle que les données suivent la politique de l’éditeur', () => {
  assert.match(AIDE_ASSISTANTS.texte, /politique de l’éditeur/)
})

test('[CA1] les potagers se disent, ceux fermés aux assistants sont signalés', () => {
  assert.equal(potagersDits([{ nom: 'Les Mésanges' }, { nom: 'Le Verger', interdit: true }]), 'Les Mésanges, Le Verger (interdit)')
  assert.equal(potagersDits([]), 'aucun potager')
})

test('[CA1] une date absente se dit « jamais », une date serveur sans fuseau est lue en UTC', () => {
  assert.equal(dateCourte(null), 'jamais')
  assert.equal(dateCourte('pas une date'), 'jamais')
  assert.match(dateCourte('2026-11-07T14:03:00', 'fr-FR'), /2026/)
})

test('[CA2] une connexion déjà révoquée n’est plus révocable', () => {
  assert.equal(revocable({ statut: 'active' }), true)
  assert.equal(revocable({ statut: 'expiree' }), true)
  assert.equal(revocable({ statut: 'revoquee' }), false)
})

// ── [US-297] Ranger les anciennes connexions ────────────────────────────────
test('[US-297 CA1] seules les actives sont listées d’emblée, dans l’ordre du serveur', () => {
  const { actives, anciennes } = repartirConnexions([
    { id: 4, statut: 'revoquee' }, { id: 3, statut: 'active' }, { id: 2, statut: 'expiree' }, { id: 1, statut: 'active' },
  ])
  assert.deepEqual(actives.map((c) => c.id), [3, 1])
  assert.deepEqual(anciennes.map((c) => c.id), [4, 2])
})

test('[US-297 CA4] rien n’est perdu : toute connexion est dans l’un des deux groupes', () => {
  const connexions = [{ id: 1, statut: 'active' }, { id: 2, statut: 'revoquee' }, { id: 3, statut: 'expiree' }]
  const { actives, anciennes } = repartirConnexions(connexions)
  assert.equal(actives.length + anciennes.length, connexions.length)
  assert.equal(anciennes[0], connexions[1]) // même objet : aucune copie altérée
})

test('[US-297 CA2] sans historique, aucune ancienne connexion ; une liste absente est vide', () => {
  assert.deepEqual(repartirConnexions([{ id: 1, statut: 'active' }]).anciennes, [])
  assert.deepEqual(repartirConnexions(), { actives: [], anciennes: [] })
})

test('[US-297 CA2, CA3] le lien dit le nombre replié, « Masquer » déplié', () => {
  assert.equal(libelleAnciennes(3, false), 'Anciennes connexions (3)')
  assert.equal(libelleAnciennes(3, true), 'Masquer les anciennes connexions')
})

test('[US-297 CA5] sans connexion active, la liste vide le dit', () => {
  assert.equal(TEXTE_AUCUNE_ACTIVE, 'Aucun assistant n’a accès à vos potagers en ce moment.')
})

test('[US-297 CA6] une connexion révoquée rejoint les anciennes et le compteur augmente', () => {
  const avant = [{ id: 2, statut: 'active' }, { id: 1, statut: 'revoquee' }]
  const apres = avant.map((c) => (c.id === 2 ? { ...c, statut: 'revoquee' } : c))
  assert.equal(repartirConnexions(avant).anciennes.length, 1)
  assert.equal(repartirConnexions(apres).anciennes.length, 2)
  assert.equal(repartirConnexions(apres).actives.length, 0)
})

test('[CA3] un outil inconnu garde son nom, jamais une chaîne vide', () => {
  assert.equal(libelleOutil('confirmer_proposition'), 'Confirmer une proposition')
  assert.equal(libelleOutil('lire_la_meteo'), 'lire la meteo')
  assert.equal(libelleOutil(undefined), '')
})

test('[CA3] l’écriture confirmée renvoie vers le Journal ce jour-là, le reste vers rien', () => {
  assert.equal(lienGeste({ geste: { id: 9, date: '2026-11-07' } }), '/?vue=journal&date=2026-11-07')
  assert.equal(lienGeste({ geste: null }), null)
  assert.equal(lienGeste({}), null)
})

test('[CA4] les durées proposées restent dans les bornes du serveur (1 à 365 jours)', () => {
  for (const { jours } of DUREES_JETON) assert.ok(jours >= 1 && jours <= 365)
})

test('[CA5] les assistants d’un membre se disent avec leur portée', () => {
  assert.equal(
    assistantsDits([{ client: 'ChatGPT', portee: 'lecture' }, { client: 'Claude', portee: 'ecriture' }]),
    'ChatGPT (lecture), Claude (lecture + écriture)',
  )
  assert.equal(assistantsDits([]), '')
})
