// [US-354] Tableau de bord, Stocks (avec Récoltes par saison) et Journal sur le socle.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import {
  aFaireAujourdhui, recoltesPossibles, meteoTroisJours, gelAnnonce, dernieresNotes, motDuTableauDeBord,
  contexteTableauDeBord,
} from './accueilSocle.js'
import {
  joursDuJournal, titreDuGroupe, libelleAutres, libelleSansTexte, motDuJournal, repondALaRecherche, debutDuBilan,
  quantiteRecoltes,
} from './journalSocle.js'
import {
  quatreChiffres, lignesDeStock, groupesParParcelle, saisonsDepuis, barresParAnnee, culturesDeLAnnee, libelleSaison,
  anneesAChercher, kgEnLettres, motDesStocks, godetsEnAttente, quantiteEnTerre,
} from './stocksSocle.js'

const ici = dirname(fileURLToPath(import.meta.url))
const source = (rel) => readFileSync(join(ici, rel), 'utf8')

// ── Tableau de bord ────────────────────────────────────────────────────────────────────────────

const plan = {
  date_ref_effective: '2026-11-23',
  taches_du_jour: {
    a_confirmer: [
      { parcelle_id: 1, parcelle: 'Planche centrale', rang: 6, culture: 'fève', variete: 'Aguadulce', etape: 'levee', etape_libelle: 'Levée', etapes: {} },
      { parcelle_id: 2, parcelle: 'Bac à salades', rang: null, culture: 'épinard', variete: null, etape: 'levee', etape_libelle: 'Levée', etapes: {} },
    ],
    a_liberer: [
      { parcelle_id: 3, parcelle: 'Serre', rang: null, culture: 'tomate', variete: 'cerise', fin_le: '2026-10-30', etapes: { numeros_rangs: [3] } },
    ],
    a_placer: [],
  },
  parcelles: [
    { id: 1, nom: 'Planche centrale', cultures: [
      { culture: 'chou de bruxelles', variete: null, numeros_rangs: [3], etapes: { etape: 'en_recolte' } },
      { culture: 'fève', variete: 'Aguadulce', numeros_rangs: [6], etapes: { etape: 'levee' } },
    ] },
    { id: 9, nom: 'Serre', est_pepiniere: true, cultures: [{ culture: 'tomate', etapes: { etape: 'en_recolte' } }] },
  ],
}

test('[CA1] « À faire aujourd’hui » : les étapes dues puis les rangs à libérer, avec leur pastille', () => {
  const lignes = aFaireAujourdhui(plan)
  assert.equal(lignes.length, 3)
  assert.deepEqual(lignes.map((l) => l.type), ['due', 'due', 'liberer'])
  assert.equal(lignes[0].etape, 'levee')
  assert.equal(lignes[0].du, true)
  assert.match(lignes[2].titre, /^Libérer le rang 3 · Serre$/)
  assert.match(lignes[2].detail, /terminée le 30 oct\./)
})

test('[CA1] « Récoltes possibles » : les cultures en récolte, hors pépinière, l’emplacement en sous-titre', () => {
  const lignes = recoltesPossibles(plan)
  assert.equal(lignes.length, 1)
  assert.equal(lignes[0].detail, 'Planche centrale · rang 3')
  assert.equal(lignes[0].etape, 'en_recolte')
})

// `GET /meteo` : le niveau supérieur dit AUJOURD'HUI (23/11) ; `previsions` COMMENCE À DEMAIN.
const meteo = {
  temp_actuelle: 8, label: 'Couvert', emoji: '☁️', temp_max: 8, temp_min: 3,
  previsions: [
    { date: '2026-11-24', temp_max: 7, temp_min: 1, emoji: '🌧️' },
    { date: '2026-11-25', temp_max: 4, temp_min: -2, emoji: '❄️' },
    { date: '2026-11-28', temp_max: 4, temp_min: -2, emoji: '❄️' },
  ],
}

test('[CA1] « Météo · 3 jours » : trois jours, le jour de gel repéré', () => {
  const jours = meteoTroisJours(meteo)
  assert.equal(jours.length, 3)
  assert.equal(jours[0].nom, 'Aujourd’hui')
  assert.equal(jours[2].gel, true)
  assert.equal(jours[2].libelle, '4° / -2°')
  assert.equal(jours[0].gel, false)
})

test('[CA1] « Aujourd’hui » dit la journée d’AUJOURD’HUI, pas celle de demain ; les jours suivent', () => {
  const jours = meteoTroisJours(meteo)
  assert.equal(jours[0].libelle, '8° / 3°')            // temp_max / temp_min du niveau supérieur de GET /meteo
  assert.equal(jours[0].cle, '2026-11-23')             // la veille du premier jour de `previsions`
  assert.deepEqual(jours.map((j) => j.nom), ['Aujourd’hui', 'Mardi', 'Mercredi'])
  assert.equal(jours[1].libelle, '7° / 1°')
})

test('[CA1] sans localisation la météo ne dit rien (la vue invite à la renseigner)', () => {
  assert.deepEqual(meteoTroisJours({ localisation_manquante: true }), [])
  assert.equal(gelAnnonce({ localisation_manquante: true }), null)
})

test('[CA1] « Dernières notes » : deux notes avec texte, la plus récente d’abord ; une note sans texte n’y est pas', () => {
  const evs = [
    { id: 1, type_action: 'observation', date: '2026-11-23', culture: 'fève', commentaire: '  ' },
    { id: 2, type_action: 'observation', date: '2026-11-23', culture: 'fève', commentaire: 'Les fèves pointent.' },
    { id: 3, type_action: 'recolte', date: '2026-11-21', culture: 'chou', commentaire: 'ignorée' },
    { id: 4, type_action: 'observation', date: '2026-11-21', culture: 'chou de bruxelles', commentaire: 'Bien fermes.' },
    { id: 5, type_action: 'observation', date: '2026-11-20', culture: 'ail', commentaire: 'Trop ancienne.' },
  ]
  const notes = dernieresNotes(evs, '2026-11-23')
  assert.equal(notes.length, 2)
  assert.equal(notes[0].texte, 'Les fèves pointent.')
  assert.equal(notes[0].date, 'aujourd’hui')
  assert.match(notes[1].date, /^sam\. 21 nov\.$/)
})

test('[CA3] le mot : gel annoncé > levées dues > rien', () => {
  const gel = motDuTableauDeBord({ meteo, plan })
  assert.match(gel.texte, /^\*\*Gel annoncé mercredi \(−2 °C\)\.\*\*/)
  assert.match(gel.texte, /Deux cultures attendent votre œil\./)
  assert.deepEqual(gel.actions.map((a) => a.libelle), ['Voir les levées', 'Noter'])
  const levees = motDuTableauDeBord({ meteo: { previsions: [{ date: '2026-11-23', temp_min: 3, temp_max: 8 }] }, plan })
  assert.match(levees.texte, /^\*\*2 étapes attendent votre œil\.\*\*/)
  assert.equal(motDuTableauDeBord({ meteo: null, plan: { taches_du_jour: { a_confirmer: [] } } }), null)
})

test('[CA3] le gel n’est dit que dans les trois prochains jours', () => {
  const loin = { previsions: [
    { date: '2026-11-23', temp_min: 3 }, { date: '2026-11-24', temp_min: 2 }, { date: '2026-11-25', temp_min: 1 },
    { date: '2026-11-26', temp_min: -3 },
  ] }
  assert.equal(gelAnnonce(loin), null)
})

test('la ligne de contexte : « lundi 23 novembre · 8 °C, couvert »', () => {
  assert.equal(contexteTableauDeBord('2026-11-23', meteo), 'lundi 23 novembre · 8 °C, couvert')
})

test('[CA1, CA2] le Tableau de bord est figé sur quatre sections, sans placeholder ni personnalisation', () => {
  const src = source('../views/Dashboard.jsx')
  for (const t of ['À faire aujourd’hui', 'Récoltes possibles', 'Météo · 3 jours', 'Dernières notes du carnet']) {
    assert.ok(src.includes(t), t)
  }
  assert.doesNotMatch(src, /Placeholder|useDashboardWidgets|ModalPersonnaliserDashboard|ConseilPotager/)
  assert.match(src, /@\[700px\]\/dash:grid-cols-2/)
  // Aucune barre d'outils déclarée (CA1) : la vue ne déclare que son mot et sa ligne de contexte.
  assert.doesNotMatch(src, /barre:/)
})

test('[CA2] la personnalisation du tableau de bord est retirée', async () => {
  const { existsSync } = await import('node:fs')
  assert.equal(existsSync(join(ici, '../components/ModalPersonnaliserDashboard.jsx')), false)
  assert.equal(existsSync(join(ici, '../hooks/useDashboardWidgets.js')), false)
})

// ── Stocks ─────────────────────────────────────────────────────────────────────────────────────

// Le Plan dit ce qui est en terre, par parcelle ; /stats/varietes dit les récoltes. Les godets et les graines en
// pépinière sont dans /stats/varietes (état « pep ») mais ne sont PAS des stocks.
const planStocks = {
  parcelles: [
    { id: 1, nom: 'Planche centrale', ordre: 1, cultures: [
      { culture: 'poireau', variete: '', nb_plants: 50, unite: 'plants', famille: 'Alliacées', numeros_rangs: [3], etapes: { etape: 'plantee' } },
      { culture: 'carotte', variete: '', nb_plants: 2.5, unite: 'm²', famille: 'Apiacées', etapes: { etape: 'semee' } },
    ] },
    { id: 2, nom: 'Planche racines', ordre: 2, cultures: [
      { culture: 'poireau', variete: '', nb_plants: 30, unite: 'plants', famille: 'Alliacées', etapes: { etape: 'plantee' } },
    ] },
    { id: 3, nom: 'Bac', ordre: 3, cultures: [
      { culture: 'tomate', variete: '', nb_plants: 10, unite: 'plants', etapes: { etape: 'terminee', a_liberer: true } },
    ] },
    { id: 9, nom: 'Serre', ordre: 4, est_pepiniere: true, cultures: [{ culture: 'chou', nb_plants: 40, unite: 'plants' }] },
  ],
}

const varietes = [
  { culture: 'poireau', variete: 'Variété non précisée', etat: 'potager', stock_actuel: 80, rendement_total: 4.1, unite_rendement: 'kg', plants_perdus: 2 },
  { culture: 'poireau', variete: 'Variété non précisée', etat: 'pep', stock_actuel: 20, unite: 'graines', plants_perdus: 0 },
  { culture: 'chou pommé', variete: 'Cœur de bœuf', etat: 'pep', stock_actuel: 14, plants_perdus: 5 },
  { culture: 'carotte', variete: 'Variété non précisée', etat: 'semis', stock_actuel: 3, nb_recoltes: 0, plants_perdus: 1 },
]

test('[CA4] les Stocks ne montrent que ce qui est EN TERRE : ni pépinière, ni godets, ni culture terminée', () => {
  const l = lignesDeStock(planStocks, varietes)
  assert.deepEqual(l.map((x) => `${x.parcelle}|${x.culture}`), ['Planche centrale|poireau', 'Planche centrale|carotte', 'Planche racines|poireau'])
  assert.ok(!l.some((x) => x.culture === 'chou' || x.culture === 'tomate'))
})

test('[CA4] une ligne par culture ET par parcelle : « 50 plants », « 2,5 m² », planté / semé en terre', () => {
  const [pBis, carotte, pRacines] = lignesDeStock(planStocks, varietes)
  assert.equal(pBis.droite, '50 plants')
  assert.equal(pRacines.droite, '30 plants')
  assert.equal(carotte.droite, '2,5 m²')
  assert.match(pBis.detail, /^planté/)
  assert.equal(carotte.detail, 'semé en terre')
  assert.equal(quantiteEnTerre(1, 'plants'), '1 plant')
})

test('[CA4] la récolte est celle du carnet ; sur deux parcelles elle est dite « toutes parcelles »', () => {
  const [pBis, carotte] = lignesDeStock(planStocks, varietes)
  assert.equal(pBis.detail, 'planté · récolté 4,1 kg (toutes parcelles)')
  assert.equal(pBis.etape, 'plantee')
  assert.equal(carotte.recolteKg, 0)
})

test('[CA4] une ligne ouvre la fiche AVEC sa parcelle : elle ne dit plus « Pas encore placé »', () => {
  const [pBis] = lignesDeStock(planStocks, varietes)
  assert.equal(pBis.selection.parcelle, 'Planche centrale')
  assert.equal(pBis.selection.parcelleId, 1)
  assert.equal(pBis.selection.rang, 3)
})

test('[CA4] les quatre chiffres : plants en terre, cultures en place, kg de l’année, unités perdues hors pépinière', () => {
  const c = quatreChiffres(lignesDeStock(planStocks, varietes), 44.7, 2026, varietes)
  assert.equal(c.plants, 80)
  assert.equal(c.surface, 2.5)
  assert.equal(c.cultures, 3)
  assert.equal(c.kg, 44.7)
  assert.equal(c.kgLibelle, 'récoltés en 2026')
  assert.equal(c.perdues, 3)
  assert.equal(kgEnLettres(44.7), '44,7 kg')
})

test('[CA4] les lignes sont rangées sous leur PARCELLE, dans l’ordre du plan', () => {
  const g = groupesParParcelle(lignesDeStock(planStocks, varietes))
  assert.deepEqual(g.map((x) => x.titre), ['Planche centrale · 2 cultures', 'Planche racines · 1 culture'])
  assert.deepEqual(g[0].lignes.map((x) => x.culture), ['carotte', 'poireau'])
})

const lectures = [
  { annee: 2023, total_general_kg: 0, cultures: [] },
  { annee: 2024, total_general_kg: 31.2, cultures: [{ culture: 'tomate', total: 12 }, { culture: 'courge', total: 19.2 }] },
  { annee: 2025, total_general_kg: 52.8, cultures: [
    { culture: 'tomate', total: 18.4 }, { culture: 'pomme de terre', total: 15 }, { culture: 'courge', total: 8 },
    { culture: 'haricot', total: 5 }, { culture: 'ail', total: 3 }, { culture: 'fève', total: 2.4 }, { culture: 'radis', total: 1 },
  ] },
  { annee: 2026, total_general_kg: 44.7, cultures: [{ culture: 'pomme de terre', total: 21 }, { culture: 'chou', total: 23.7 }] },
]

test('[CA5] une barre par année qui a des récoltes, proportionnelle au maximum', () => {
  const s = saisonsDepuis(lectures)
  assert.deepEqual(s.map((x) => x.annee), [2024, 2025, 2026])
  const b = barresParAnnee(s)
  assert.equal(b[1].pct, 100)
  assert.ok(Math.abs(b[0].pct - (31.2 / 52.8) * 100) < 1e-9)
  assert.equal(b[2].libelle, '44,7 kg')
})

test('[CA5, Gherkin] 2025 : la tomate en tête avec 18,4 kg, le reste en « Autres »', () => {
  const s = saisonsDepuis(lectures).find((x) => x.annee === 2025)
  const c = culturesDeLAnnee(s)
  assert.equal(c[0].nom, 'tomate')
  assert.equal(c[0].libelle, '18,4 kg')
  assert.equal(c[c.length - 1].nom, 'Autres')
  assert.equal(c.length, 6)
})

test('[CA5] « Saison 2026 : du 1er janvier au 23 novembre » ; une saison close va au 31 décembre', () => {
  assert.equal(libelleSaison(2026, '2026-11-23'), 'Saison 2026 : du 1er janvier au 23 novembre')
  assert.equal(libelleSaison(2025, '2026-11-23'), 'Saison 2025 : du 1er janvier au 31 décembre')
  assert.deepEqual(anneesAChercher(2026, 3), [2024, 2025, 2026])
})

test('[CA5] aucune route nouvelle : la comparaison lit GET /stats/rendement, une lecture par année', () => {
  const src = source('../views/Stocks.jsx')
  assert.match(src, /anneesAChercher\(annee\)\.map\(\(a\) => api\.rendement\(a, dateRef, potagerId\)/)
  assert.match(src, /cle: 'recoltes'/)
  assert.match(source('./stocksSocle.js'), /Tableau de bord › Statistiques/)
  assert.match(source('../components/RecoltesParSaison.jsx'), /MENTION_STATISTIQUES/)
})

test('[CA6] le mot : des godets attendent depuis plus de 3 semaines et un rang est libre', () => {
  const lots = [
    { lot_id: 1, culture: 'Chou pommé', stock_residuel_godet: 14, date_derniere_mise_en_godet: '2026-10-26' },
    { lot_id: 2, culture: 'Poireau', stock_residuel_godet: 5, date_derniere_mise_en_godet: '2026-11-18' },
    { lot_id: 3, culture: 'Ail', stock_residuel_godet: 0, date_derniere_mise_en_godet: '2026-09-01' },
  ]
  const avecRang = { parcelles: [{ nom: 'Serre', est_pepiniere: true, disposition: { rangs_libres: 4 } }, { nom: 'Planche haricots', disposition: { rangs_libres: 1 } }] }
  assert.equal(godetsEnAttente(lots, '2026-11-23').length, 1)
  const mot = motDesStocks({ lots, plan: avecRang, aujourdhui: '2026-11-23' })
  assert.match(mot.texte, /^\*\*14 godets de chou pommé\*\* attendent une place depuis 4 semaines\./)
  assert.match(mot.texte, /Planche haricots/)
  assert.equal(mot.actions[0].libelle, 'Oui, proposer')
  assert.equal(mot.actions[0].noter, true)
  // Sans rang libre, ou sans attente de plus de 3 semaines : rien.
  assert.equal(motDesStocks({ lots, plan: { parcelles: [] }, aujourdhui: '2026-11-23' }), null)
  assert.equal(motDesStocks({ lots: [lots[1]], plan: avecRang, aujourdhui: '2026-11-23' }), null)
})

test('[CA4] la tuile des kg est un bouton orangé « Comparer les saisons › » ; Filtrer porte famille et ordre alphabétique', () => {
  const src = source('../views/Stocks.jsx')
  assert.match(src, /Comparer les saisons ›/)
  assert.match(src, /<TuileKg /)
  assert.match(src, /font-serif text-\[20px\]/)
  assert.match(src, /Famille botanique/)
  assert.match(src, /Ordre alphabétique/)
  assert.match(src, /groupesParParcelle/)
  assert.doesNotMatch(src, /godets à replanter/)
  assert.match(src, /ouvrirCulture\(l\.selection\)/)
  assert.match(src, /exporterCsv/)
  assert.match(src, /exporterJson/)
})

// ── Journal ────────────────────────────────────────────────────────────────────────────────────

const aujourdhui = new Date('2026-11-23T10:00:00')
const evenements = [
  { id: 10, date: '2026-11-23', type_action: 'observation', culture: 'fève', variete: null, parcelle: 'Planche centrale', commentaire: 'Les fèves pointent sur tout le rang.' },
  { id: 11, date: '2026-11-23', type_action: 'observation', culture: 'mâche', parcelle: 'Bac à salades', commentaire: 'Limaces sur la mâche.' },
  { id: 12, date: '2026-11-23', type_action: 'observation', culture: 'ail', commentaire: '' },
  { id: 13, date: '2026-11-21', type_action: 'recolte', culture: 'chou de bruxelles', quantite: 1.2, unite: 'kg', parcelle: 'Planche centrale', rang: 3 },
  { id: 14, date: '2026-11-21', type_action: 'observation', culture: 'chou de bruxelles', commentaire: 'Bien fermes.' },
  { id: 15, date: '2026-11-19', type_action: 'paillage', parcelle: 'Planche ombre' },
  { id: 16, date: '2026-11-12', type_action: 'perte_godet', culture: 'fraisier', nb_plants_godets: 2, parcelle: 'Pépinière' },
]

test('[CA7, Gherkin] trois notes dont une sans texte : « 3 notes », la première en Kalam, « 1 sans texte », « + 1 autre »', () => {
  const jours = joursDuJournal(evenements.slice(0, 3), aujourdhui)
  assert.equal(jours.length, 1)
  const n = jours[0].notes
  assert.equal(titreDuGroupe(n.total), '3 notes')
  assert.equal(n.premiere.texte, 'Les fèves pointent sur tout le rang.')
  assert.equal(n.premiere.ou, 'Fève · Planche centrale')
  assert.equal(libelleSansTexte(n.sansTexte), '1 sans texte')
  assert.equal(libelleAutres(n.autres.length), '+ 1 autre')
  assert.equal(jours[0].gestes.length, 0)
})

test('[CA7] les gestes restent en ligne, la perte est marquée, une note sans texte n’est jamais listée', () => {
  const jours = joursDuJournal(evenements, aujourdhui)
  assert.deepEqual(jours.map((j) => j.label), ['Aujourd\'hui · 23 novembre', 'Samedi 21 novembre', 'Jeudi 19 novembre', 'Jeudi 12 novembre'])
  assert.equal(jours[1].gestes[0].recolte, true)
  assert.equal(jours[1].gestes[0].detail, 'Planche centrale · rang 3')
  assert.equal(jours[3].gestes[0].perte, true)
  assert.equal(jours[2].notes, null)
  assert.equal(jours[0].notes.autres.every((x) => x.texte), true)
})

test('[CA8] le mot du Journal : le bilan de la semaine, sans action', () => {
  const semaine = [
    { type_action: 'recolte', quantite: 1.2, unite: 'kg' },
    { type_action: 'paillage' },
    ...Array.from({ length: 6 }, () => ({ type_action: 'observation', commentaire: 'x' })),
  ]
  const mot = motDuJournal(semaine)
  assert.equal(mot.texte, 'Cette semaine : **1 récolte (1,2 kg)**, 1 paillage et 6 notes.')
  assert.deepEqual(mot.actions, [])
  assert.equal(motDuJournal([]), null)
})

test('[CA8, US-036] une récolte en pièces n’est jamais convertie en kg', () => {
  assert.deepEqual(quantiteRecoltes([{ quantite: 1.2, unite: 'kg' }, { quantite: 3, unite: 'pièces' }]), ['1,2 kg', '3 pièces'])
  assert.equal(debutDuBilan('2026-11-23'), '2026-11-17')
})

test('[CA7] la recherche « Culture, parcelle ou mot » couvre la culture, la parcelle et le texte de la note', () => {
  assert.equal(repondALaRecherche(evenements[0], 'feve'), true)
  assert.equal(repondALaRecherche(evenements[0], 'centrale'), true)
  assert.equal(repondALaRecherche(evenements[0], 'pointent'), true)
  assert.equal(repondALaRecherche(evenements[0], 'tomate'), false)
  assert.equal(repondALaRecherche(evenements[0], ''), true)
})

test('[CA7, CA9] le Journal déclare sa barre et son mot, suit la règle des temps, et lit le texte du jardinier', () => {
  const src = source('../views/Journal.jsx')
  assert.match(src, /placeholder: 'Culture, parcelle ou mot'/)
  assert.match(src, /date_ref/)
  assert.match(src, /uppercase/)
  assert.match(src, /note-carnet-texte/)
  assert.doesNotMatch(src, /font-hand/)
})

test('[CA7] l’API du Journal rend le texte des notes et le rang (lecture seule)', () => {
  const api = readFileSync(join(ici, '../../../app/api/main.py'), 'utf8')
  assert.match(api, /"commentaire": e\.commentaire/)
  assert.match(api, /"rang"\s+: e\.rang/)
})

test('[CA9] les trois vues suivent la date de la règle des temps', () => {
  assert.match(source('../views/Dashboard.jsx'), /api\.plan\(dateRef, potagerId\)/)
  assert.match(source('../views/Stocks.jsx'), /api\.statsVarietes\(dateRef, potagerId\)/)
  assert.match(source('../views/Journal.jsx'), /params\.date_ref = dateRef/)
})
