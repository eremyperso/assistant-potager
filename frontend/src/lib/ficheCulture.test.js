// [US-207 / CA14] Fiche culture — composition de la section « Maintenant » et
// des autres sections, sans React — `npm test`.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  sectionMaintenant, etatAuPotager, lignesReferentiel, groupesVoisinages,
  badgeContexte, sourcesDeFiche,
} from './ficheCulture.js'

const R = (regle, etat) => ({ regle, etat })

test('sectionMaintenant [CA4] — "illisible" quand la confiance n’a pas pu être lue', () => {
  assert.deepEqual(sectionMaintenant({ confianceLue: false }), { etat: 'illisible' })
})

test('sectionMaintenant [CA4] — "sans_calendrier" sans fenêtre pour la zone', () => {
  assert.deepEqual(
    sectionMaintenant({ entree: { a_calendrier: false, actions: [] }, confianceLue: true }),
    { etat: 'sans_calendrier' },
  )
})

test('sectionMaintenant [CA4] — geste ouvert avec sa récolte attendue quand la fenêtre est ouverte', () => {
  const entree = {
    a_calendrier: true,
    actions: [{
      action: 'semis_pleine_terre', etoiles: 3, score: 100,
      motifs: [R('R1', 'gagne'), R('R2', 'gagne')],
      recolte_attendue: { min: '2026-07-16', max: '2026-07-26' },
    }],
  }
  const calendriers = { cultures: { courgette: { mois: { semis_pleine_terre: [4, 5, 6] } } } }
  const r = sectionMaintenant({ entree, calendriers, culture: 'courgette', confianceLue: true })
  assert.equal(r.etat, 'ouverte')
  assert.equal(r.geste, 'Semer en place')
  assert.equal(r.etoiles, 3)
  assert.match(r.recolteAttendue, /juillet/)
})

test('sectionMaintenant [CA4] — geste fermé sans récolte attendue quand la fenêtre n’est pas ouverte', () => {
  const entree = {
    a_calendrier: true,
    actions: [{ action: 'semis_pepiniere', etoiles: 1, score: 10, motifs: [R('R1', 'perdu')] }],
  }
  const r = sectionMaintenant({ entree, calendriers: {}, culture: 'tomate', confianceLue: true })
  assert.equal(r.etat, 'fermee')
  assert.equal(r.recolteAttendue, null)
})

test('etatAuPotager [CA4] — "Pas au potager" sans aucune variété cultivée', () => {
  assert.equal(etatAuPotager([]), 'Pas au potager')
})

test('etatAuPotager [CA4] — assemble parcelles et lots de toutes les variétés', () => {
  const varietes = [
    { variete: 'cerise', parcelles: [{ parcelle_id: 1, phase: 'en_recolte' }], lots_pepiniere: [] },
    { variete: 'coeur-de-boeuf', parcelles: [{ parcelle_id: 2, phase: 'en_recolte' }], lots_pepiniere: [{ numero: 1 }] },
  ]
  assert.equal(etatAuPotager(varietes), 'En récolte sur 2 parcelles · 1 lot en pépinière')
})

test('etatAuPotager [CA4] — une variété seulement en pépinière compte son lot sans parcelle', () => {
  const varietes = [{ variete: 'cerise', parcelles: [], lots_pepiniere: [{ numero: 128 }] }]
  assert.equal(etatAuPotager(varietes), '1 lot en pépinière')
})

test('lignesReferentiel [CA6] — assemble famille, attributs et durées, "non renseigné" restant au serveur', () => {
  const fiche = {
    famille: 'Solanacées', delai_retour_annees: 4,
    attributs: [{ cle: 'exposition', libelle: 'Exposition', affichage: 'plein soleil' }],
    durees: [{ etape: 'levee', libelle: 'Levée', affichage: 'non renseignée' }],
    type_organe_recolte: 'reproducteur',
  }
  const lignes = lignesReferentiel(fiche)
  assert.deepEqual(lignes[0], { cle: 'famille', libelle: 'Famille · délai de retour', valeur: 'Solanacées · retour 4 ans' })
  assert.equal(lignes.find((l) => l.cle === 'exposition').valeur, 'plein soleil')
  assert.equal(lignes.find((l) => l.cle === 'levee').valeur, 'non renseignée')
  assert.equal(lignes.find((l) => l.cle === 'organe').valeur, 'Reproducteur')
})

test('lignesReferentiel [CA6] — famille absente rend "non renseigné" sans planter une valeur devinée', () => {
  const lignes = lignesReferentiel({ famille: null, attributs: [], durees: [], type_organe_recolte: null })
  assert.equal(lignes[0].valeur, null)
  assert.equal(lignes.find((l) => l.cle === 'organe').valeur, null)
})

test('groupesVoisinages [CA22] — sépare les quatre groupes, la pratique traditionnelle à part', () => {
  const associations = [
    { autre_partie: 'basilic', nature: 'favorable', niveau_preuve: 'etabli' },
    { autre_partie: 'fenouil', nature: 'defavorable', niveau_preuve: 'etabli' },
    { autre_partie: 'oeillet d’Inde', nature: 'favorable', niveau_preuve: 'traditionnel' },
    { autre_partie: 'pomme de terre', nature: 'defavorable', niveau_preuve: 'traditionnel' },
  ]
  const g = groupesVoisinages(associations)
  assert.deepEqual(g.favorablesEtablis.map((a) => a.autre_partie), ['basilic'])
  assert.deepEqual(g.defavorablesEtablis.map((a) => a.autre_partie), ['fenouil'])
  assert.deepEqual(g.favorablesTrad.map((a) => a.autre_partie), ['oeillet d’Inde'])
  assert.deepEqual(g.defavorablesTrad.map((a) => a.autre_partie), ['pomme de terre'])
})

test('badgeContexte [CA20] — absent sans parcelle d’origine', () => {
  assert.equal(badgeContexte(), null)
  assert.equal(badgeContexte({}), null)
})

test('badgeContexte [CA20] — « depuis <parcelle> · rang N » avec une parcelle et un rang', () => {
  assert.equal(badgeContexte({ nomParcelle: 'planche-centrale', rang: 2 }), 'depuis planche-centrale · rang 2')
})

test('badgeContexte [CA20] — sans rang, la parcelle seule', () => {
  assert.equal(badgeContexte({ nomParcelle: 'planche-centrale' }), 'depuis planche-centrale')
})

test('sourcesDeFiche [CA21] — joint les attributions dédoublonnées', () => {
  assert.equal(sourcesDeFiche({ attributions: ['Wind River Greens', 'EPPO'] }), 'Wind River Greens · EPPO')
})

test('sourcesDeFiche [CA21] — null sans aucune source', () => {
  assert.equal(sourcesDeFiche({ attributions: [] }), null)
})
