// [US-316 / CA10] La vue « Seuils » : mise en forme, état, prévisualisation, historique.
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  badgeEtat, brouillonDe, corpsModification, depuis, duree, envoisPeriodiques, formaterEcart, formaterValeur, libelleCanaux,
  lignesHistorique, lireSaisie, nbAlertesOuvertes, previsualisation, regleEnClair, uniteDuSaisie,
} from './seuils.js'

const NBSP = ' '
// Les chiffres sont à la française avec une espace insécable : on compare avec des espaces ordinaires.
const propre = (v) => (typeof v === 'string' ? v.replace(/ | /g, ' ') : v)
const egal = (reel, attendu) => assert.equal(propre(reel), propre(attendu))
const corresp = (reel, motif) => assert.match(propre(reel), motif)
const MED = {
  id: 1, indicateur: 'jetons_entree_mediane', libelle: "Jetons d'entrée médians par appel (agent)", unite: 'jetons',
  comparaison: 'ecart_7j', valeur: 20, fenetre_jours: 1, gravite: 'moyenne', actif: true, etat: 'franchi',
  valeur_courante: 8900, valeur_courante_texte: '8 900 jetons', reference: 6000, ecart_courant: 48.3,
}

test('formaterValeur : chaque unité à la française', () => {
  egal(formaterValeur('jetons', 8900), `8${NBSP}900${NBSP}jetons`)
  egal(formaterValeur('eur', 5), `5,00${NBSP}€`)
  egal(formaterValeur('pourcent', 12.5), `12,5${NBSP}%`)
  egal(formaterValeur('ms', 15000), `15${NBSP}000${NBSP}ms`)
  egal(formaterValeur('nombre', 10), '10')
  egal(formaterValeur('eur', null), '—')
})

test('formaterEcart : signé, sans décimale', () => {
  egal(formaterEcart(48.3), `+48${NBSP}%`)
  egal(formaterEcart(-4.6), `−5${NBSP}%`)
})

test("badgeEtat : l'état s'écrit, avec la valeur mesurée et l'écart", () => {
  egal(badgeEtat(MED).libelle, `Franchi · 8 900 jetons (+48${NBSP}%)`)
  egal(badgeEtat({ ...MED, etat: 'norme', comparaison: 'fixe' }).libelle, 'Dans la norme · 8 900 jetons')
  egal(badgeEtat({ ...MED, etat: 'nodata', valeur_courante_texte: null }).libelle, 'Pas assez de données')
  assert.deepEqual(badgeEtat({ ...MED, actif: false }), { etat: 'inactif', libelle: 'Inactif' })
})

test('lireSaisie : nombre à la française, jamais de valeur approximative', () => {
  egal(lireSaisie('7 500'), 7500)
  egal(lireSaisie('0,5'), 0.5)
  egal(lireSaisie(`1${NBSP}200,25`), 1200.25)
  assert.ok(Number.isNaN(lireSaisie('')))
  assert.ok(Number.isNaN(lireSaisie('abc')))
  assert.ok(Number.isNaN(lireSaisie('-3')))
  assert.ok(Number.isNaN(lireSaisie('1,2,3')))
})

test('regleEnClair : la règle se relit pour une définition en cours de saisie', () => {
  egal(regleEnClair(MED, { comparaison: 'ecart_7j', valeur: 20, fenetre_jours: 1 }), `plus de 20${NBSP}% au-dessus de la moyenne des 7 jours précédents`)
  egal(regleEnClair({ ...MED, unite: 'eur', indicateur: 'cout_jour' }, { comparaison: 'fixe', valeur: 5, fenetre_jours: 1 }), `plus de 5,00${NBSP}€ aujourd'hui`)
  corresp(regleEnClair(MED, { comparaison: 'fixe', valeur: 7500, fenetre_jours: 3 }), /sur les 3 derniers jours/)
  corresp(regleEnClair({ ...MED, indicateur: 'cout_mois_projete', unite: 'eur' }, { comparaison: 'fixe', valeur: 100, fenetre_jours: 1 }), /mois en cours/)
})

test('previsualisation : dit si la valeur saisie franchirait le seuil maintenant', () => {
  const franchi = previsualisation(MED, { comparaison: 'ecart_7j', valeur: 20 })
  egal(franchi.franchi, true)
  corresp(franchi.texte, /^Franchi avec cette valeur · \+48/)
  egal(previsualisation(MED, { comparaison: 'ecart_7j', valeur: 60 }).franchi, false)
  const fixe = previsualisation(MED, { comparaison: 'fixe', valeur: 7500 })
  egal(fixe.franchi, true)
  corresp(fixe.texte, /8 900 jetons > 7 500 jetons/)
  egal(previsualisation(MED, { comparaison: 'fixe', valeur: 9500 }).franchi, false)
})

test('previsualisation : sans mesure ou sans valeur lisible, on ne juge pas', () => {
  egal(previsualisation({ ...MED, ecart_courant: null }, { comparaison: 'ecart_7j', valeur: 20 }).franchi, null)
  egal(previsualisation(MED, { comparaison: 'fixe', valeur: NaN }).franchi, null)
})

test("corpsModification : seulement ce qui a changé, rien sinon", () => {
  const b = brouillonDe(MED)
  egal(corpsModification(MED, b), null)
  assert.deepEqual(corpsModification(MED, { ...b, valeur: 30, gravite: 'haute' }), { valeur: 30, gravite: 'haute' })
  assert.deepEqual(corpsModification(MED, { ...b, comparaison: 'fixe', fenetre_jours: 3 }), { comparaison: 'fixe', fenetre_jours: 3 })
})

test('uniteDuSaisie : un écart se saisit en pourcentage', () => {
  egal(uniteDuSaisie('jetons', 'ecart_7j'), '%')
  egal(uniteDuSaisie('jetons', 'fixe'), 'jetons')
  egal(uniteDuSaisie('eur', 'fixe'), '€')
})

test('duree : minutes, heures, jours', () => {
  const t = (s) => `2026-11-12T${s}:00`
  egal(duree(t('18:40'), t('19:05')), `25${NBSP}min`)
  egal(duree(t('07:12'), t('08:22')), `1${NBSP}h${NBSP}10`)
  egal(duree(t('21:00'), t('23:59').replace('12T', '12T')), `2${NBSP}h${NBSP}59`)
  egal(duree('2026-11-10T09:00:00', '2026-11-12T13:00:00'), `2${NBSP}j${NBSP}4${NBSP}h`)
  egal(depuis('2026-11-12T09:05:00', '2026-11-12T14:32:00'), `9${NBSP}h${NBSP}05 (5${NBSP}h${NBSP}27)`)
})

test('libelleCanaux : Telegram, e-mail, ou aucun', () => {
  egal(libelleCanaux(['email', 'telegram']), 'e-mail, Telegram')
  egal(libelleCanaux([]), 'Aucun')
})

test("lignesHistorique : début, valeur (et écart), durée, canaux — jamais de contenu de message", () => {
  const lignes = lignesHistorique([
    { id: 2, libelle: 'Taux d’erreur', valeur_texte: '4,1 %', ecart_texte: null, declenchee_le: '2026-11-10T18:40:00', resolue_le: '2026-11-10T19:05:00', canaux_notifies: ['email', 'telegram'] },
    { id: 1, libelle: MED.libelle, valeur_texte: '8 900 jetons', ecart_texte: '+48 %', declenchee_le: '2026-11-12T09:05:00', resolue_le: null, canaux_notifies: [] },
  ], new Date('2026-11-12T14:32:00'))
  egal(lignes[0].cellules.duree, `25${NBSP}min`)
  egal(lignes[0].cellules.debut, `10 nov., 18${NBSP}h${NBSP}40`)
  egal(lignes[1].cellules.valeur, '8 900 jetons (+48 %)')
  egal(lignes[1].cellules.duree, `en cours (5${NBSP}h${NBSP}27)`)
  egal(lignes[1].cellules.canaux, 'Aucun')
  assert.deepEqual(Object.keys(lignes[0].cellules), ['debut', 'valeur', 'duree', 'canaux'])
})

test('nbAlertesOuvertes : la pastille ne compte que les alertes ouvertes', () => {
  egal(nbAlertesOuvertes({ alertes_ouvertes: [{}, {}] }), 2)
  egal(nbAlertesOuvertes({}), 0)
  egal(nbAlertesOuvertes(null), 0)
})

test('envoisPeriodiques : reflète la configuration, en lecture seule', () => {
  const [resume, bilan] = envoisPeriodiques({ resume_quotidien: true, resume_heure: 8, bilan_hebdomadaire: false }, { telegram: true, email: false })
  egal(resume.actif, true)
  egal(resume.detail, `Telegram, chaque jour à 8${NBSP}h`)
  egal(bilan.actif, false)
  egal(bilan.canalJoignable, false)
  egal(bilan.variable, 'PILOTAGE_BILAN_HEBDO')
})
