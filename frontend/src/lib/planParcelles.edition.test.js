// [US-230] La carte « Caractéristiques » en édition — ce que la lib décide, et
// ce qu'elle refuse de décider.
//
// Le cœur de l'US tient en trois garanties, et ce sont celles-ci que les tests
// tiennent :
//   - **E4 / CA14** : seuls les champs touchés partent. Un champ non transmis
//     n'écrase rien, et c'est ce qui rend deux modifications concurrentes sûres
//     par construction.
//   - **CA6** : un champ vidé part à `null`, jamais à `""` ni à `false`.
//     « Je ne sais pas » n'est pas « non ».
//   - **CA3** : aucun vocabulaire fermé n'est écrit ici. Les listes viennent du
//     serveur ; sans elles, la lib ne propose rien plutôt que d'inventer.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  saisieDeParcelle, valeursInitiales, chargeUtile, avertissementsBascule,
  messageConfirmation, CHAMP_API, CHOIX_NON_RENSEIGNE, TEXTE_LARGEUR_CALCULEE,
  SAISIE_DEDUITE, SAISIE_LISTE, SAISIE_NOMBRE, SAISIE_OUI_NON, SAISIE_TEXTE,
} from './planParcelles.js'

/** Les vocabulaires tels que `GET /plan` les sert (US-230 / CA3). */
const VOCABULAIRES = {
  abri: {
    ferme: true,
    options: [
      { valeur: 'aucun', libelle: 'Aucun' }, { valeur: 'voile', libelle: 'Voile' },
      { valeur: 'chassis', libelle: 'Châssis' }, { valeur: 'tunnel', libelle: 'Tunnel' },
      { valeur: 'serre', libelle: 'Serre' },
    ],
  },
  type_sol: {
    ferme: true,
    options: [
      { valeur: 'Argileux', libelle: 'Argileux' }, { valeur: 'Limoneux', libelle: 'Limoneux' },
      { valeur: 'Sableux', libelle: 'Sableux' }, { valeur: 'Humifère', libelle: 'Humifère' },
      { valeur: 'Calcaire', libelle: 'Calcaire' },
    ],
  },
  exposition: {
    ferme: false,
    options: [
      { valeur: 'Sud', libelle: 'Sud' }, { valeur: 'Est', libelle: 'Est' },
      { valeur: 'Ouest', libelle: 'Ouest' }, { valeur: 'Nord', libelle: 'Nord' },
      { valeur: 'Mi-ombre', libelle: 'Mi-ombre' },
    ],
  },
}

function planche(extra = {}) {
  return {
    id: 1, nom: 'planche_centrale', superficie_m2: 12, longueur_m: 6, largeur_m: 2,
    nb_rangs: 7, exposition: 'Sud', type_sol: null, abri: 'aucun', paillage: true,
    est_pepiniere: false, actif: true, cultures: [], disposition: {},
    ...extra,
  }
}

const par = (champs) => Object.fromEntries(champs.map((c) => [c.cle, c]))

// ── E1, E2 — la même carte, les bons types de saisie ─────────────────────────

test('[E1] la carte en édition porte les mêmes champs, dans le même ordre', () => {
  const p = planche()
  const lecture = ['nom', 'superficie', 'longueur', 'largeur', 'nb_rangs',
                   'exposition', 'type_sol', 'abri', 'paillage', 'pepiniere', 'statut']
  assert.deepEqual(saisieDeParcelle(p, VOCABULAIRES).map((c) => c.cle), lecture)
})

test('[E2] chaque champ porte son type de saisie', () => {
  const c = par(saisieDeParcelle(planche(), VOCABULAIRES))
  assert.equal(c.nom.type, SAISIE_TEXTE)
  for (const cle of ['superficie', 'longueur', 'nb_rangs']) {
    assert.equal(c[cle].type, SAISIE_NOMBRE, cle)
  }
  for (const cle of ['exposition', 'type_sol', 'abri']) {
    assert.equal(c[cle].type, SAISIE_LISTE, cle)
  }
  for (const cle of ['paillage', 'pepiniere', 'statut']) {
    assert.equal(c[cle].type, SAISIE_OUI_NON, cle)
  }
})

test('[E3] la largeur n’est pas saisissable : sa case le dit', () => {
  const c = par(saisieDeParcelle(planche(), VOCABULAIRES))
  assert.equal(c.largeur.type, SAISIE_DEDUITE)
  assert.equal(c.largeur.texte, TEXTE_LARGEUR_CALCULEE)
  assert.equal(c.largeur.valeur, undefined)
  // Et elle ne part jamais à l'écriture.
  assert.equal('largeur' in CHAMP_API, false)
})

test('[CA5] les bornes de la maquette sont des repères de frappe, pas la règle', () => {
  const c = par(saisieDeParcelle(planche(), VOCABULAIRES))
  assert.deepEqual([c.nb_rangs.min, c.nb_rangs.max], [1, 99])
  assert.deepEqual([c.longueur.min, c.longueur.max], [0.5, 200])
  // La lib ne VALIDE rien : elle ne porte aucune fonction de contrôle.
  assert.equal(typeof c.nb_rangs.valider, 'undefined')
})

// ── CA3 — aucun vocabulaire écrit ici ────────────────────────────────────────

test('[CA3] sans vocabulaire servi, la lib ne propose rien plutôt que d’inventer', () => {
  const c = par(saisieDeParcelle(planche({ type_sol: null, abri: null }), {}))
  assert.deepEqual(c.type_sol.options, [])
  assert.deepEqual(c.abri.options, [])
})

test('[E2] une valeur déjà enregistrée hors liste reste offerte', () => {
  const c = par(saisieDeParcelle(planche({ exposition: 'plein soleil' }), VOCABULAIRES))
  assert.equal(c.exposition.valeur, 'plein soleil')
  assert.ok(c.exposition.options.some((o) => o.valeur === 'plein soleil'))
})

test('[US-181] « aucun » reste une option, à côté du « non renseigné »', () => {
  const c = par(saisieDeParcelle(planche({ abri: 'aucun' }), VOCABULAIRES))
  assert.equal(c.abri.valeur, 'aucun')
  assert.equal(c.abri.nonRenseignable, true)
})

// ── US-229 / C6, C9 — ce qui ne se vide pas, ce qui disparaît ────────────────

test('[C6] pépinière et statut n’acceptent pas « non renseigné »', () => {
  const c = par(saisieDeParcelle(planche(), VOCABULAIRES))
  assert.ok(!c.pepiniere.nonRenseignable)
  assert.ok(!c.statut.nonRenseignable)
  assert.equal(c.paillage.nonRenseignable, true)
})

test('[C9] une pépinière n’a ni longueur, ni largeur, ni rangs à saisir', () => {
  const cles = saisieDeParcelle(planche({ est_pepiniere: true }), VOCABULAIRES).map((c) => c.cle)
  for (const absent of ['longueur', 'largeur', 'nb_rangs']) {
    assert.ok(!cles.includes(absent), absent)
  }
})

// ── E4, CA14 — un seul appel, et seulement ce qui a changé ───────────────────

test('[E4] seuls les champs touchés partent', () => {
  const p = planche()
  const initiales = valeursInitiales(p, VOCABULAIRES)
  const saisies = { ...initiales, type_sol: 'Argileux', nb_rangs: '8' }

  assert.deepEqual(chargeUtile(initiales, saisies, p), { type_sol: 'Argileux', nb_rangs: 8 })
})

test('[CA14] une saisie qui ne change rien n’envoie rien', () => {
  const p = planche()
  const initiales = valeursInitiales(p, VOCABULAIRES)
  assert.deepEqual(chargeUtile(initiales, { ...initiales }, p), {})
})

test('[CA14] deux modifications concurrentes ne s’écrasent pas', () => {
  // Deux jardiniers ouvrent la MÊME parcelle. L'un corrige le sol, l'autre les
  // rangs. Comme chacun n'envoie que son champ, aucun des deux ne renvoie —
  // donc n'écrase — la valeur que l'autre vient d'écrire.
  const p = planche()
  const initiales = valeursInitiales(p, VOCABULAIRES)
  const premier = chargeUtile(initiales, { ...initiales, type_sol: 'Sableux' }, p)
  const second = chargeUtile(initiales, { ...initiales, nb_rangs: '9' }, p)

  assert.deepEqual(Object.keys(premier), ['type_sol'])
  assert.deepEqual(Object.keys(second), ['nb_rangs'])
})

// ── CA6 — « Non renseigné » écrit NULL ───────────────────────────────────────

test('[CA6] vider un champ l’envoie à null, jamais à "" ni à false', () => {
  const p = planche({ type_sol: 'Argileux', abri: 'serre', paillage: true })
  const initiales = valeursInitiales(p, VOCABULAIRES)
  const saisies = {
    ...initiales,
    type_sol: CHOIX_NON_RENSEIGNE, abri: CHOIX_NON_RENSEIGNE,
    paillage: CHOIX_NON_RENSEIGNE, nb_rangs: CHOIX_NON_RENSEIGNE,
    longueur: CHOIX_NON_RENSEIGNE,
  }

  const charge = chargeUtile(initiales, saisies, p)
  for (const champ of ['type_sol', 'abri', 'paillage', 'nb_rangs', 'longueur_m']) {
    assert.strictEqual(charge[champ], null, champ)
  }
})

test('[E2] « Non » reste une déclaration, distincte du silence', () => {
  const p = planche({ paillage: true })
  const initiales = valeursInitiales(p, VOCABULAIRES)
  assert.strictEqual(chargeUtile(initiales, { ...initiales, paillage: 'non' }, p).paillage, false)
  assert.strictEqual(
    chargeUtile(initiales, { ...initiales, paillage: CHOIX_NON_RENSEIGNE }, p).paillage, null,
  )
})

test('[CA6] les nombres partent en nombres, la virgule comprise', () => {
  const p = planche()
  const initiales = valeursInitiales(p, VOCABULAIRES)
  const charge = chargeUtile(initiales, { ...initiales, longueur: '8,5', superficie: '14' }, p)
  assert.strictEqual(charge.longueur_m, 8.5)
  assert.strictEqual(charge.superficie_m2, 14)
})

test('[CA1] les clés envoyées sont celles de l’API, la largeur exceptée', () => {
  const p = planche()
  const initiales = valeursInitiales(p, VOCABULAIRES)
  const charge = chargeUtile(initiales, {
    ...initiales, nom: 'Planche du milieu', pepiniere: 'oui', statut: 'non',
  }, p)
  assert.deepEqual(charge, { nom: 'Planche du milieu', est_pepiniere: true, actif: false })
})

// ── E8, E9 — ce qu’une bascule entraîne, dit avant d’enregistrer ─────────────

test('[E8] basculer en pépinière est annoncé, avec ses deux conséquences', () => {
  const p = planche()
  const initiales = valeursInitiales(p, VOCABULAIRES)
  const avis = avertissementsBascule(initiales, { ...initiales, pepiniere: 'oui' })
  assert.equal(avis.length, 1)
  assert.match(avis[0], /pleine terre/)
  assert.match(avis[0], /rangs/)
})

test('[E9] passer en inactive annonce la réaffectation des gestes', () => {
  const p = planche()
  const initiales = valeursInitiales(p, VOCABULAIRES)
  const avis = avertissementsBascule(initiales, { ...initiales, statut: 'non' })
  assert.match(avis[0], /Non localisé/)
})

test('[E8, E9] sans bascule, rien n’est annoncé', () => {
  const p = planche()
  const initiales = valeursInitiales(p, VOCABULAIRES)
  assert.deepEqual(avertissementsBascule(initiales, { ...initiales, nb_rangs: '8' }), [])
})

// ── E6 — la confirmation dit ce qui a changé ─────────────────────────────────

test('[E6] la confirmation nomme le changement quand il est seul', () => {
  assert.match(messageConfirmation(['Type de sol : argileux']), /type de sol : argileux/)
  assert.match(messageConfirmation(['Rangs : 8', 'Type de sol : argileux']), /2 caractéristiques/)
  assert.match(messageConfirmation([]), /Aucun changement/)
})
