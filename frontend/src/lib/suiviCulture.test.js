// [US-322] Le suivi d'une culture — `npm test`.
//
// Ce qui se vérifie ici : chaque bloc S1 → S10 dit ce que le serveur sait, et rien
// quand il ne sait pas (CA2) ; l'origine distingue ses trois cas (CA3) ; « Noter la
// levée » sur mobile quand l'étape est à confirmer (Gherkin 2) ; le composant n'a qu'une
// lecture et cache « Noter » en lecture seule (CA4, CA6) ; Photo désactivée (CA5).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  enTete, localisation, lignePlace, etapeCourante, bandeauAConfirmer, libelleNoter, texteRecolte,
  frise, origine, notes, contexteNoter, nomEvenement, ETAT_FAITE, ETAT_COURANTE, ETAT_A_VENIR,
  EVENEMENT_OUVRIR_COMPAGNON,
} from './suiviCulture.js'

const etapes = (etape, statut = 'validee', { aConfirmer = false, date = '2026-10-20' } = {}) => ({
  serie_id: 1, etape, etape_statut: statut, etape_date: date, a_confirmer: aConfirmer,
  etapes: [
    { code: 'plantee', statut: 'validee', date: '2026-06-10' },
    { code: 'en_recolte', statut: etape === 'en_recolte' ? statut : 'prevue', date: '2026-10-20' },
    { code: 'terminee', statut: 'prevue', date: '2026-12-15' },
  ],
})

// Gherkin 1 : le chou de Bruxelles du rang 3, venu du lot #18.
const CHOU = {
  parcelle_id: 2, parcelle: 'Planche centrale', culture: 'chou de Bruxelles', variete: 'Groninger',
  quantite: 12, unite: 'plants', date_ref_effective: '2026-11-12', rangs: [3],
  place: { pieds: 12, places: 20, espacement_cm: 30, longueur_m: 6, metres_occupes: 3.6, metres_libres: 2.4, depassement_pieds: 0 },
  etapes: etapes('en_recolte'),
  recolte: { quantite: 2.9, unite: 'kg' },
  origine: { type: 'pepiniere', numero_lot: 18, date_semis: '2026-04-02', godets: 14, plantes: 12, date_plantation: '2026-06-10' },
  notes: [
    { id: 3, date: '2026-11-08', texte: 'Bien fermés', dictee: true },
    { id: 2, date: '2026-10-20', texte: 'Première récolte', dictee: null },
    { id: 1, date: '2026-09-14', texte: '', dictee: null },
  ],
}

// Gherkin 2 : la levée des fèves est prévue aujourd'hui.
const FEVE = {
  ...CHOU, culture: 'fève', variete: 'Aguadulce', quantite: 40, rangs: [6], place: null, recolte: null, notes: [],
  origine: { type: 'semis_direct', date: '2026-11-02' },
  etapes: {
    serie_id: 4, etape: 'levee', etape_statut: 'prevue', etape_date: '2026-11-12', a_confirmer: true,
    etapes: [
      { code: 'semee', statut: 'validee', date: '2026-11-02' },
      { code: 'levee', statut: 'prevue', date: '2026-11-12' },
      { code: 'en_recolte', statut: 'prevue', date: '2027-05-10' },
      { code: 'terminee', statut: 'prevue', date: null },
    ],
  },
}

test('[US-322 / S1] En-tête : emoji, nom, variété et quantité', () => {
  assert.deepEqual(enTete(CHOU), { emoji: '🥬', titre: 'Chou de Bruxelles', sousTitre: 'Groninger · 12 plants' })
  assert.equal(enTete({ culture: 'ail', quantite: 1, unite: 'plants' }).sousTitre, '1 plant')
  assert.equal(enTete({ culture: 'radis', quantite: 2.5, unite: 'm' }).sousTitre, '2,5 m')
  assert.equal(enTete(null), null)
})

test('[US-322 / S2] Localisation : parcelle et rangs, ou « pas encore placée »', () => {
  assert.deepEqual(localisation(CHOU), { texte: 'Planche centrale, rang 3', lien: true })
  assert.equal(localisation({ parcelle: 'P', rangs: [5, 3, 4] }).texte, 'P, rangs 3 à 5')
  assert.equal(localisation({ parcelle: 'P', rangs: [1, 4] }).texte, 'P, rangs 1 et 4')
  assert.equal(localisation({ parcelle: 'P', rangs: [] }).texte, 'P')
  assert.deepEqual(localisation({ parcelle: null }), { texte: 'pas encore placée', lien: false })
})

test('[US-322 / S3] La ligne de place, et « ⚠ +N » en dépassement ; absente sinon', () => {
  assert.equal(lignePlace(CHOU).texte, '12 pieds · 3,6 m sur 6 m · tous les 30 cm · 2,4 m libres')
  assert.equal(lignePlace(CHOU).depassement, null)
  const trop = lignePlace({ place: { ...CHOU.place, pieds: 23, depassement_pieds: 3, metres_libres: 0 } })
  assert.equal(trop.depassement, '⚠ +3')
  assert.doesNotMatch(trop.texte, /libres/)
  assert.match(trop.nomAccessible, /dépassement de 3 pieds/)
  assert.equal(lignePlace(FEVE), null)
})

test('[US-322 / S4] Étape courante : « depuis le … », ou « prévue le … »', () => {
  assert.deepEqual(etapeCourante(CHOU), { cle: 'en_recolte', prevue: false, texte: 'depuis le 20 octobre' })
  assert.deepEqual(etapeCourante(FEVE), { cle: 'levee', prevue: true, texte: 'prévue le 12 novembre' })
  assert.equal(etapeCourante({ etapes: null }), null)
  assert.equal(etapeCourante({ etapes: { etape: 'inconnue' } }), null)
})

test('[US-322 / S5] Gherkin 2 — le bandeau « à confirmer » ; absent sinon', () => {
  assert.equal(bandeauAConfirmer(FEVE), 'Levée prévue aujourd’hui : à confirmer en notant')
  const hier = { ...FEVE, etapes: { ...FEVE.etapes, etape_date: '2026-11-10' } }
  assert.equal(bandeauAConfirmer(hier), 'Levée prévue le 10 novembre : à confirmer en notant')
  assert.equal(bandeauAConfirmer(CHOU), null)
})

test('[US-322 / S6] Gherkin 2 — « Noter la levée » sur mobile, « Noter » sinon', () => {
  assert.equal(libelleNoter(FEVE, { compact: true }), 'Noter la levée')
  assert.equal(libelleNoter(FEVE), 'Noter')
  assert.equal(libelleNoter(CHOU, { compact: true }), 'Noter')
  // [US-323] le rang, quand la culture n'en occupe qu'un
  assert.deepEqual(contexteNoter(CHOU), { culture: 'chou de Bruxelles', variete: 'Groninger', parcelleId: 2, parcelle: 'Planche centrale', rang: 3,
    // [US-324] l'étape, pour choisir les pastilles de « Noter »
    ...(CHOU.etapes && { etapes: CHOU.etapes }) })
  assert.equal(EVENEMENT_OUVRIR_COMPAGNON, 'potager:ouvrir-compagnon')
})

test('[US-322 / S7] Gherkin 1 — « 2,9 kg récoltés », absent sans récolte', () => {
  assert.equal(texteRecolte(CHOU), '2,9 kg récoltés')
  assert.equal(texteRecolte(FEVE), null)
})

test('[US-322 / S8] La frise : faites datées, courante, la prochaine avec sa date', () => {
  const f = frise(FEVE)
  assert.deepEqual(f.map((x) => [x.nom, x.etat, x.date]), [
    ['Semis', ETAT_FAITE, '2 novembre'],
    ['Levée', ETAT_COURANTE, 'prévue le 12 novembre'],
    ['Récolte', ETAT_A_VENIR, 'prévue le 10 mai'],
    ['Fin de culture', ETAT_A_VENIR, ''],
  ])
  assert.equal(f[1].aConfirmer, true)
  assert.equal(frise({ etapes: null }), null)
  const nonNotee = { etapes: { ...FEVE.etapes, etape: 'en_recolte', etapes: [
    { code: 'semee', statut: 'validee', date: '2026-11-02' }, { code: 'levee', statut: 'non_notee', date: '2026-11-12' },
    { code: 'en_recolte', statut: 'validee', date: '2026-12-01' },
  ] } }
  assert.equal(frise(nonNotee)[1].date, 'non notée')
  assert.equal(nomEvenement('inconnue'), '')
})

test('[US-322 / S9, CA3] L’origine distingue pépinière (lot), achat et semis direct', () => {
  assert.deepEqual(origine(CHOU), {
    type: 'pepiniere', titre: 'Pépinière · lot #18',
    detail: 'semé le 2 avril · 14 godets · 12 plantés le 10 juin', numeroLot: 18,
  })
  assert.deepEqual(origine({ origine: { type: 'achat', texte: 'jardinerie' } }),
    { type: 'achat', titre: 'Achat', detail: 'jardinerie', numeroLot: null })
  assert.equal(origine({ origine: { type: 'achat', texte: null, date_plantation: '2026-04-03' } }).detail, 'planté le 3 avril')
  assert.deepEqual(origine(FEVE), { type: 'semis_direct', titre: 'Semis direct', detail: 'semé en place le 2 novembre', numeroLot: null })
  assert.equal(origine({ origine: { type: 'pepiniere', numero_lot: null } }).titre, 'Pépinière')
  assert.equal(origine({ origine: null }), null)
})

test('[US-322 / S10] Notes datées, dans l’ordre du serveur ; une note vide est écartée', () => {
  assert.deepEqual(notes(CHOU), [
    { id: 3, date: '8 novembre', texte: 'Bien fermés', dictee: true },
    { id: 2, date: '20 octobre', texte: 'Première récolte', dictee: false },
  ])
  assert.equal(notes(FEVE), null)
})

// ── Le composant ─────────────────────────────────────────────────────────────

const composant = readFileSync(new URL('../components/SuiviCulture.jsx', import.meta.url), 'utf8')

test('[US-322 / CA2] Les blocs S1 → S10 dans l’ordre de la maquette', () => {
  const ordre = ['S1 —', 'S2 + S3', 'S4 —', 'S5 —', 'S6 —', 'S7 —', 'S8 —', 'S9 —', 'S10 —']
  const positions = ordre.map((b) => composant.indexOf(`{/* ${b}`))
  assert.ok(positions.every((p) => p >= 0), positions.join(','))
  assert.deepEqual([...positions].sort((a, b) => a - b), positions)
})

test('[US-322 / CA5, CA6] Photo désactivée et annoncée ; « Noter » réservé à qui peut écrire', () => {
  assert.match(composant, /disabled aria-disabled="true" aria-label="Photo, bientôt disponible"/)
  assert.match(composant, /\{ecrire && \(/)
  assert.match(composant, /peutEnregistrer\(role\)/)
})

test('[US-322 / CA1] Échap et Fermer referment le suivi', () => {
  assert.match(composant, /e\.key === 'Escape'/)
  assert.match(composant, /aria-label="Fermer le suivi"/)
})
