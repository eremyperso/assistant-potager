// [US-085] Changer le rôle d'un membre et transférer la propriété — volet
// frontend, exécuté par `npm test` (`node --test`, même approche que
// us082_parametres_potager.test.js).
//
// Verrouille ce qui est vérifiable sans moteur de rendu : la règle de
// confirmation (CA7), l'emplacement de l'action dans la gestion des membres
// (CA9), la réutilisation de `RoleSelect` (CA type) et la règle projet des
// container queries. L'apparence elle-même relève de la validation visuelle du QA.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { confirmationChangementRole } from './roles.js'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')
const lireSrc = (chemin) => readFileSync(join(SRC, chemin), 'utf8')

const MEMBRES = lireSrc('components/GestionMembres.jsx')
const SELECT = lireSrc('components/ui/RoleSelect.jsx')
const API = lireSrc('lib/api.js')

// ── CA7 — Quand demander une confirmation ───────────────────────────────────

test('[CA7] nommer un propriétaire demande une confirmation, quel que soit le rôle de départ', () => {
  for (const ancienRole of ['editor', 'lecteur']) {
    assert.equal(confirmationChangementRole({ ancienRole, nouveauRole: 'owner', estMoi: false }), 'promotion')
  }
})

test("[CA7] un owner qui se rétrograde lui-même confirme : il perd le pouvoir de défaire sa décision", () => {
  for (const nouveauRole of ['editor', 'lecteur']) {
    assert.equal(confirmationChangementRole({ ancienRole: 'owner', nouveauRole, estMoi: true }), 'retrogradation')
  }
})

test('[CA7] une correction de rôle courante s\'applique sans détour', () => {
  assert.equal(confirmationChangementRole({ ancienRole: 'lecteur', nouveauRole: 'editor', estMoi: false }), null)
  assert.equal(confirmationChangementRole({ ancienRole: 'editor', nouveauRole: 'lecteur', estMoi: false }), null)
  // Rétrograder UN AUTRE owner : réversible en le re-promouvant, donc sans confirmation.
  assert.equal(confirmationChangementRole({ ancienRole: 'owner', nouveauRole: 'editor', estMoi: false }), null)
})

test('[CA7] redemander le rôle actuel ne déclenche rien', () => {
  assert.equal(confirmationChangementRole({ ancienRole: 'owner', nouveauRole: 'owner', estMoi: true }), null)
  assert.equal(confirmationChangementRole({ ancienRole: 'editor', nouveauRole: 'editor', estMoi: false }), null)
  assert.equal(confirmationChangementRole({ ancienRole: 'editor', nouveauRole: undefined, estMoi: false }), null)
})

test("[CA7] la confirmation rappelle ce que le nouvel owner pourra faire : archiver, supprimer, gérer les membres", () => {
  assert.match(MEMBRES, /deviendra propriétaire de ce potager/)
  assert.match(MEMBRES, /archiver ou supprimer le potager, gérer les membres/)
})

// ── CA9 — Dans la gestion des membres, à côté du retrait ────────────────────

test('[CA9] GestionMembres appelle le nouvel endpoint de changement de rôle', () => {
  assert.match(API, /modifierRoleMembre: \(potagerId, membreUserId, role\) =>/)
  assert.match(API, /patch\(`\/potagers\/\$\{potagerId\}\/membres\/\$\{membreUserId\}`, \{ role \}\)/)
  assert.match(MEMBRES, /api\.modifierRoleMembre\(potagerId, membre\.user_id, nouveauRole\)/)
})

test('[CA9] les trois rôles sont proposés, `owner` compris — contrairement à l\'invitation', () => {
  assert.match(MEMBRES, /const ROLES_ATTRIBUABLES = \[\s*\{ value: 'owner'/)
  assert.match(MEMBRES, /\.\.\.ROLES_INVITABLES/)
  // L'invitation, elle, ne propose toujours que editor et lecteur.
  assert.match(MEMBRES, /<RoleSelect value=\{rolePropose\} options=\{ROLES_INVITABLES\}/)
})

test('[CA9] en lecture seule (non-owner) le rôle reste un badge : aucun sélecteur proposé', () => {
  assert.match(MEMBRES, /lectureSeule \? \(\s*<Badge tint=\{teinteRole\(m\.role\)\}>/)
})

test('[CA9] le retrait reste proposé à côté du sélecteur, pour les membres non-owner', () => {
  assert.match(MEMBRES, /!lectureSeule && m\.role !== 'owner' && \(/)
  assert.match(MEMBRES, /handleRetirer\(m\.user_id\)/)
})

// ── CA type — RoleSelect réutilisé, lisible de 375 px au desktop ────────────

test('[CA type] le sélecteur de rôle d\'un membre réutilise RoleSelect en variante compacte', () => {
  assert.match(MEMBRES, /<RoleSelect\s+compact/)
  assert.match(SELECT, /compact = false/)
  // La variante compacte ne réclame plus 210 px et masque la description du déclencheur.
  assert.match(SELECT, /compact \? 'min-w-\[150px\]' : 'flex-1 min-w-\[210px\]'/)
  assert.match(SELECT, /!compact && <span/)
})

test('[CA type] la ligne de membre s\'adapte par container query, pas par breakpoint d\'écran', () => {
  assert.match(MEMBRES, /@container\/membres/)
  assert.match(MEMBRES, /@\[420px\]\/membres:order-none/)
  const ligne = MEMBRES.slice(MEMBRES.indexOf('@container/membres'), MEMBRES.indexOf('lectureSeule ? ('))
  assert.equal(/\b(sm|md|lg|xl):/.test(ligne), false)
})

test('[CA type] chaque sélecteur est nommé pour les lecteurs d\'écran (plusieurs à l\'écran)', () => {
  assert.match(MEMBRES, /ariaLabel=\{`Rôle de \$\{nomAffiche\(m\.nom, m\.email\)\}`\}/)
  assert.match(SELECT, /aria-label=\{ariaLabel\}/)
})

// ── CA6 / CA3 — Effet immédiat et refus serveur affiché ─────────────────────

test('[CA6] se rétrograder soi-même recharge l\'écran : le rôle affiché est celui du serveur', () => {
  assert.match(MEMBRES, /if \(membre\.user_id === moiId\) \{\s*window\.location\.reload\(\)/)
})

test('[CA3] le refus « dernier propriétaire » du serveur s\'affiche tel quel', () => {
  const bloc = MEMBRES.slice(MEMBRES.indexOf('async function appliquerChangementRole'), MEMBRES.indexOf('function copierCode'))
  assert.match(bloc, /catch \(e\) \{\s*setError\(e\.message\)/)
})

test('[CA9] le pied de la modale annonce que le propriétaire change aussi les rôles', () => {
  assert.match(MEMBRES, /Seul le propriétaire peut inviter, retirer un membre ou changer son rôle/)
})
