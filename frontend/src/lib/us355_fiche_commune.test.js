// [US-355] La fiche commune, la fiche catalogue et l'écran Cultures sur le socle.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import {
  carnetDeCulture, nombreDeRecoltes, ligneDeRecolte, emplacementDeFiche, etapeDeFiche, friseDeFiche, phraseOrigine,
  espacementDe, rotationDe, resoudreSelection, etatDeCatalogue, enteteDeFiche, libelleDuBoutonNoter, ONGLETS,
} from './ficheCommune.js'
import {
  groupeDeLigne, lignesAuPotager, lignesAPlacer, groupesAuPotager, motDeCultures, ongletsCultures, lignesCatalogue,
  groupesDuCatalogue, motDuCatalogue, repondALaRecherche, famillesDesLignes, detailDeLigne, joursDeRetard,
} from './culturesSocle.js'
import { executerAction, normaliserMot } from './motDeGaston.js'

const ici = dirname(fileURLToPath(import.meta.url))
const source = (rel) => readFileSync(join(ici, rel), 'utf8')

// ── Le carnet de la culture (CA2) ───────────────────────────────────────────────────────────────

const evenements = [
  { id: 6, date: '2026-11-21', type_action: 'recolte', culture: 'chou de bruxelles', variete: 'Long Island', quantite: 1.2, unite: 'kg', commentaire: 'Les pommes du bas, bien fermes.', parcelle: 'Planche centrale', rang: 3 },
  { id: 5, date: '2026-11-14', type_action: 'paillage', culture: 'chou de bruxelles', variete: 'Long Island', commentaire: 'Feuilles de chêne broyées', parcelle: 'Planche centrale' },
  { id: 4, date: '2026-11-06', type_action: 'observation', culture: 'chou de bruxelles', variete: 'Long Island', commentaire: 'Feuilles jaunies du bas retirées' },
  { id: 3, date: '2026-11-05', type_action: 'observation', culture: 'chou de bruxelles', variete: 'Long Island', commentaire: '' },
  { id: 2, date: '2026-08-01', type_action: 'perte', culture: 'chou de bruxelles', variete: 'Long Island', quantite: 2, unite: 'plants', commentaire: 'Hernie suspectée' },
  { id: 1, date: '2026-07-03', type_action: 'plantation', culture: 'chou de bruxelles', variete: 'Autre variété', quantite: 12, unite: 'plants' },
]

test('[CA2] le carnet : récoltes, gestes et notes, du plus récent au plus ancien', () => {
  const l = carnetDeCulture(evenements)
  assert.deepEqual(l.map((x) => x.type), ['recolte', 'geste', 'note', 'geste', 'geste'])
  assert.equal(l[0].titre, 'Récolte · 1,2 kg')
  assert.equal(l[0].texte, 'Les pommes du bas, bien fermes.')
  assert.equal(l[0].date, '21 novembre')
})

test('[CA2] une note sans texte n’est pas listée ; une perte se dit en rouge avec sa quantité', () => {
  const l = carnetDeCulture(evenements)
  assert.equal(l.filter((x) => x.type === 'note').length, 1)
  const perte = l.find((x) => x.perte)
  assert.match(perte.titre, /^Perte/)
  assert.match(perte.titre, /2 plants/)
  assert.equal(perte.detail, 'Hernie suspectée')
})

test('[CA2] une fiche ouverte sur une variété ne montre que le carnet de cette variété', () => {
  const l = carnetDeCulture(evenements, { variete: 'long island' })
  assert.equal(l.length, 4)
  assert.equal(nombreDeRecoltes(evenements, { variete: 'Long Island' }), 1)
})

test('[CA1] le total récolté et le nombre de récoltes', () => {
  assert.equal(ligneDeRecolte({ recolte: { quantite: 2.9, unite: 'kg' } }, 4), '2,9 kg récoltés · 4 récoltes')
  assert.equal(ligneDeRecolte({ recolte: { quantite: 1, unite: 'kg' } }, 1), '1 kg récoltés · 1 récolte')
  assert.equal(ligneDeRecolte({ recolte: null }, 0), null)
})

// ── En-tête, emplacement, étape (CA1) ───────────────────────────────────────────────────────────

const suivi = {
  culture: 'fève', variete: 'Aguadulce', quantite: 40, unite: 'graines', parcelle_id: 1, parcelle: 'Planche centrale', rangs: [6],
  est_pepiniere: false,
  etapes: {
    etape: 'levee', etape_statut: 'prevue', etape_date: '2026-11-23', a_confirmer: true,
    etapes: [
      { code: 'semee', statut: 'validee', date: '2026-11-02' },
      { code: 'levee', statut: 'prevue', date: '2026-11-23' },
      { code: 'en_recolte', statut: 'prevue', date: null },
      { code: 'terminee', statut: 'prevue', date: null },
    ],
  },
  date_ref_effective: '2026-11-23',
}

test('[CA1] l’emplacement : « Planche centrale · rang 6 » avec « Voir au plan → »', () => {
  const e = emplacementDeFiche(suivi, {})
  assert.equal(e.texte, 'Planche centrale · rang 6')
  assert.equal(e.lien, 'Voir au plan →')
  assert.equal(e.place, true)
})

test('[CA1] sans place : « Pas encore placé » avec « Placer sur le plan → »', () => {
  const e = emplacementDeFiche(null, { culture: 'fraisier' })
  assert.deepEqual([e.place, e.texte, e.lien], [false, 'Pas encore placé', 'Placer sur le plan →'])
})

test('[CA1] l’étape due se dit prévue, en orange ; sans étape, « Aucune étape notée »', () => {
  const due = etapeDeFiche(suivi)
  assert.equal(due.due, true)
  assert.equal(due.prevue, true)
  assert.match(due.texte, /prévue aujourd’hui/)
  const aucune = etapeDeFiche(null)
  assert.equal(aucune.aucune, true)
  assert.equal(aucune.texte, 'Aucune étape notée')
})

test('[CA1] « Noter la levée » quand l’étape est prévue, « Noter » sinon', () => {
  assert.equal(libelleDuBoutonNoter(suivi), 'Noter la levée')
  assert.equal(libelleDuBoutonNoter(null), 'Noter')
})

test('[CA1] l’en-tête : emoji, nom, « variété · quantité » ; sans suivi, ce que l’écran savait', () => {
  const t = enteteDeFiche(null, { culture: 'fraisier', variete: 'Mara des bois', quantiteTexte: '12 godets' })
  assert.equal(t.titre, 'Fraisier')
  assert.equal(t.sousTitre, 'Mara des bois · 12 godets')
})

test('[CA2] la frise : réalisées datées, la prévue dit « prévu », les suivantes sont grisées sans date', () => {
  const f = friseDeFiche(suivi)
  assert.deepEqual(f.map((x) => x.etat), ['faite', 'courante', 'a_venir', 'a_venir'])
  assert.equal(f[0].date, '2 novembre')
  assert.equal(f[1].date, 'prévu')
  assert.equal(f[2].date, '')
})

test('[CA2] l’origine tient en une phrase', () => {
  assert.equal(phraseOrigine({ type: 'pepiniere', titre: 'Pépinière · lot #18', detail: 'semé le 2 juin' }), 'Pépinière · lot #18, semé le 2 juin')
  assert.equal(phraseOrigine({ type: 'semis_direct', titre: 'Semis direct', detail: '' }), 'Semis direct')
  assert.equal(phraseOrigine(null), null)
})

// ── L'onglet Référence (CA3) ────────────────────────────────────────────────────────────────────

test('[CA3] l’espacement et la rotation sont dits tels que le référentiel les porte', () => {
  const f = { famille: 'Brassicacées', delai_retour_annees: 4, espacement: '60 cm entre plants, 60 cm entre rangs' }
  assert.equal(espacementDe(f), '60 cm entre plants, 60 cm entre rangs')
  assert.equal(rotationDe(f), 'Brassicacées : pas de la même famille à cet endroit avant 4 ans')
  assert.equal(espacementDe({}), null)
  assert.equal(rotationDe({}), null)
  assert.match(rotationDe({ famille: 'Alliacées' }), /non renseigné/)
})

test('[CA1] deux onglets : Suivi et Référence', () => {
  assert.deepEqual(ONGLETS.map((o) => o.label), ['Suivi', 'Référence'])
})

test('[CA1] la place d’une culture se retrouve dans le plan ; ailleurs vaut mieux que « pas placée »', () => {
  const plan = {
    parcelles: [
      { id: 2, nom: 'Serre', est_pepiniere: true, cultures: [{ culture: 'fève', variete: 'Aguadulce' }] },
      { id: 1, nom: 'Planche centrale', cultures: [{ culture: 'fève', variete: 'Aguadulce', numeros_rangs: [6, 5] }] },
    ],
  }
  assert.deepEqual(resoudreSelection(plan, { culture: 'Fève' }), { parcelleId: 1, parcelle: 'Planche centrale', variete: 'Aguadulce', rang: 5 })
  assert.equal(resoudreSelection(plan, { culture: 'fève', parcelle: 'Planche est' }).parcelleId, 1)
  assert.equal(resoudreSelection(plan, { culture: 'tomate' }), null)
})

// ── La fiche catalogue (CA7) ────────────────────────────────────────────────────────────────────

test('[CA7] la pilule et le bouton de la fiche catalogue', () => {
  assert.deepEqual(etatDeCatalogue({ au_potager: false }), { pilule: 'Pas encore au potager', dans: false, bouton: 'Ajouter à mon potager' })
  assert.deepEqual(etatDeCatalogue({ au_potager: true }), { pilule: 'Au potager', dans: true, bouton: 'Ouvrir la culture en place' })
})

// ── Cultures · Au potager (CA4, CA5) ────────────────────────────────────────────────────────────

const planCultures = {
  date_ref_effective: '2026-11-23',
  taches_du_jour: { a_placer: [{ origine: 'lot', culture: 'fraisier', variete: 'Mara des bois', quantite: 12, unite: 'godets', numero_lot: 42, lot_id: 9 }] },
  parcelles: [
    { id: 1, nom: 'Planche centrale', cultures: [
      { culture: 'fève', variete: 'Aguadulce', nb_plants: 40, numeros_rangs: [6], etapes: { etape: 'levee', etape_statut: 'prevue', etape_date: '2026-11-23', a_confirmer: true } },
      { culture: 'chou de bruxelles', variete: 'Long Island', nb_plants: 10, numeros_rangs: [3], etapes: { etape: 'en_recolte', etape_statut: 'validee', etape_date: '2026-10-20' } },
      { culture: 'poireau', variete: 'Carentan', numeros_rangs: [2], etapes: { etape: 'croissance', etape_statut: 'validee', etape_date: '2026-07-20' } },
      { culture: 'ail', variete: 'Rose de Lautrec', numeros_rangs: [4], etapes: { etape: 'plantee', etape_statut: 'validee', etape_date: '2026-10-25' } },
    ] },
    { id: 4, nom: 'Serre', cultures: [
      { culture: 'épinard', variete: 'Géant d’hiver', numeros_rangs: [2], etapes: { etape: 'levee', etape_statut: 'prevue', etape_date: '2026-11-09', a_confirmer: true } },
      { culture: 'tomate', variete: 'Sweet 100', numeros_rangs: [3], etapes: { etape: 'terminee', etape_statut: 'validee', etape_date: '2026-10-30', a_liberer: true } },
    ] },
    { id: 9, nom: 'Châssis froid', est_pepiniere: true, cultures: [{ culture: 'laitue', variete: 'Reine de mai' }] },
  ],
}
const vue = {
  effectif_toutes: 109,
  cultures: [
    { culture: 'fève', nom_culture: 'fève', famille: 'Fabacées', au_potager: true, a_calendrier: true, mois_zone: { semis_pleine_terre: [10, 11], recolte: [5, 6] }, nb_varietes: 1, varietes: ['Aguadulce'] },
    { culture: 'céleri-rave', nom_culture: 'céleri-rave', famille: 'Apiacées', au_potager: false, a_calendrier: true, nb_varietes: 2, varietes: ['Monarch', 'Prinz'], fenetre_etat: 'bientot', fenetre_geste: 'semis_pepiniere', fenetre_mois: [3] },
    { culture: 'aubergine', nom_culture: 'aubergine', famille: 'Solanacées', au_potager: false, a_calendrier: true, nb_varietes: 1, varietes: ['Black Beauty'], fenetre_etat: 'bientot', fenetre_geste: 'semis_pepiniere', fenetre_mois: [2, 3] },
    { culture: 'courgette', nom_culture: 'courgette', famille: 'Cucurbitacées', au_potager: false, a_calendrier: true, nb_varietes: 2, varietes: [], fenetre_etat: 'plus_tard', fenetre_geste: 'semis_pepiniere', fenetre_mois: [4] },
    { culture: 'kiwano', nom_culture: 'kiwano', famille: '', au_potager: false, a_calendrier: false, hors_referentiel: true, nb_varietes: 0, varietes: [], fenetre_etat: 'aucune' },
  ],
}

test('[CA4] le groupe d’une ligne vient de ce que dit le serveur : à confirmer, à libérer, puis l’étape', () => {
  const g = (etapes) => groupeDeLigne({ etapes })
  assert.equal(g({ a_confirmer: true, etape: 'levee' }), 'a_confirmer')
  assert.equal(g({ a_liberer: true, etape: 'en_recolte' }), 'termine')
  assert.equal(g({ etape: 'en_recolte' }), 'en_recolte')
  assert.equal(g({ etape: 'fleur' }), 'en_croissance')
  assert.equal(g({ etape: 'semee' }), 'seme_plante')
})

test('[CA4] les groupes, dans l’ordre de la maquette : ce qui demande une action d’abord', () => {
  const lignes = [...lignesAuPotager(planCultures, vue), ...lignesAPlacer(planCultures, vue)]
  const g = groupesAuPotager(lignes)
  assert.deepEqual(g.map((x) => x.cle), ['a_confirmer', 'a_placer', 'en_recolte', 'en_croissance', 'seme_plante', 'termine'])
  assert.equal(g[0].lignes.length, 2)
  assert.equal(lignes.length, 7)   // les lots de pépinière n'y sont pas : ils se lisent dans la Pépinière
})

test('[CA4] l’état d’une carte se dit en mots, en orange quand il est dû', () => {
  const l = lignesAuPotager(planCultures, vue)
  const feve = l.find((x) => x.culture === 'fève')
  assert.equal(feve.detail, 'Levée prévue aujourd’hui')
  assert.equal(feve.due, true)
  assert.equal(feve.lieu, 'Planche centrale · rang 6')
  assert.equal(feve.famille, 'Fabacées')
  const epinard = l.find((x) => x.culture === 'épinard')
  assert.equal(epinard.detail, 'Levée prévue le 9 nov. · en retard')
  assert.equal(l.find((x) => x.culture === 'tomate').detail, 'Terminé le 30 oct. · rang à libérer')
  assert.equal(l.find((x) => x.culture === 'chou de bruxelles').detail, 'En récolte depuis le 20 oct.')
})

test('[CA4] une culture sans place n’a ni étape ni emplacement', () => {
  const [a] = lignesAPlacer(planCultures, vue)
  assert.equal(a.detail, 'À placer · aucune étape notée')
  assert.equal(a.lieu, 'Pas encore placé')
  assert.equal(a.etape, null)
  assert.equal(a.selection.parcelleId, null)
  assert.equal(a.selection.origineTexte, 'Pépinière · lot #42')
  assert.equal(a.selection.quantiteTexte, '12 godets')
})

test('[CA4] les onglets d’en-tête portent les comptes de la lecture', () => {
  assert.deepEqual(ongletsCultures({ nbPotager: 25, nbCatalogue: 109 }).map((o) => o.label), ['Au potager · 25', 'Catalogue · 109'])
})

test('[CA4] la recherche trouve la culture, la variété ou la parcelle ; les familles passent dans Filtrer', () => {
  const l = lignesAuPotager(planCultures, vue)
  assert.equal(l.filter((x) => repondALaRecherche(x, 'serre')).length, 2)
  assert.equal(l.filter((x) => repondALaRecherche(x, 'AGUADULCE')).length, 1)
  assert.deepEqual(famillesDesLignes(l), ['Fabacées'])
})

test('[CA5] le Mot de Cultures : étapes à confirmer, le retard, et la première à confirmer', () => {
  const mot = motDeCultures(lignesAuPotager(planCultures, vue))
  assert.match(mot.texte, /^\*\*2 levées à confirmer\.\*\*/)
  assert.match(mot.texte, /L’épinard \(Serre\) a 2 semaines de retard : un coup d’œil aujourd’hui \?/)
  assert.equal(mot.actions[0].libelle, 'Confirmer la fève')
  assert.equal(mot.actions[0].noter, true)
  assert.equal(mot.actions[0].contexte.parcelleId, 1)
  assert.equal(motDeCultures([{ due: false }]), null)
})

test('[CA5] un retard se dit à partir d’une semaine', () => {
  assert.equal(joursDeRetard({ a_confirmer: true, etape_date: '2026-11-09' }, '2026-11-23'), 14)
  assert.equal(joursDeRetard({ a_confirmer: false, etape_date: '2026-11-09' }, '2026-11-23'), 0)
  const mot = motDeCultures([{ due: true, etape: 'levee', culture: 'fève', retard: 3, parcelle: 'X', parcelleId: 1 }])
  assert.doesNotMatch(mot.texte, /retard/)
})

test('[CA2] une étape sans date ne casse pas la phrase', () => {
  assert.equal(detailDeLigne({ etapes: { etape: 'croissance', etape_statut: 'validee' } }, '2026-11-23'), 'En croissance')
  assert.equal(detailDeLigne({ etapes: null }, '2026-11-23'), 'Aucune étape notée')
})

// ── Cultures · Catalogue (CA6, CA8) ─────────────────────────────────────────────────────────────

test('[CA6] le catalogue : par prochaine fenêtre de semis, puis « Déjà au potager »', () => {
  const k = lignesCatalogue(vue, lignesAuPotager(planCultures, vue))
  const g = groupesDuCatalogue(k, 11)
  assert.deepEqual(g.map((x) => x.cle), ['bientot', 'plus_tard', 'sans_fenetre', 'au_potager'])
  assert.equal(g[0].titre, 'À semer d’ici mars')
  assert.deepEqual(g[0].lignes.map((x) => x.nom), ['Aubergine', 'Céleri-rave'])   // février avant mars
  assert.equal(g[1].titre, 'Plus tard dans la saison')
  assert.equal(g[3].lignes[0].lieux[0], 'Planche centrale')
})

test('[CA6] une carte du catalogue : variétés, famille, fenêtre', () => {
  const k = lignesCatalogue(vue, [])
  const cel = k.find((x) => x.culture === 'céleri-rave')
  assert.equal(cel.sousTitre, '2 variétés · Apiacées')
  assert.equal(cel.fenetre.texte, 'Prochaine fenêtre : semer en pépinière mars')
  assert.equal(k.find((x) => x.culture === 'kiwano').sousTitre, '')
})

test('[CA8] le Mot du Catalogue : la prochaine espèce à semer → « Ajouter le céleri-rave »', () => {
  const k = lignesCatalogue(vue, [])
  const mot = motDuCatalogue(k.filter((x) => x.culture !== 'aubergine'), 11)
  assert.equal(mot.texte, '**Le céleri-rave se sème en mars**, en pépinière.')
  assert.equal(mot.actions[0].libelle, 'Ajouter le céleri-rave')
  assert.equal(mot.actions[0].phrase, 'Ajouter le céleri-rave à mon potager')
  assert.equal(motDuCatalogue(k.filter((x) => x.etatFenetre === 'plus_tard'), 11), null)
})

test('[CA8] une action de mot qui porte une phrase la transmet à Gaston ; rien n’est écrit ici', () => {
  const mot = normaliserMot({ texte: 'Bonjour.', actions: [{ libelle: 'Ajouter', noter: true, phrase: 'Ajouter le céleri-rave à mon potager' }] })
  const recu = []
  executerAction(mot.actions[0], { ouvrirGaston: (contexte, phrase) => recu.push([contexte, phrase]) })
  assert.deepEqual(recu, [[null, 'Ajouter le céleri-rave à mon potager']])
})

// ── Câblage (par la source) ─────────────────────────────────────────────────────────────────────

test('[CA1] les cinq vues ouvrent la même fiche : Tableau de bord, Plan, Cultures, Stocks, Journal', () => {
  for (const f of ['../views/Dashboard.jsx', '../views/Stocks.jsx', '../views/Journal.jsx', '../views/Cultures.jsx']) {
    const src = source(f)
    assert.match(src, /useFiches\(\)/, f)
    assert.doesNotMatch(src, /aller\('cultures', \{ culture/, f)
  }
  assert.match(source('../views/PlanDessus.jsx'), /<FicheCommune/)
  assert.doesNotMatch(source('../views/PlanDessus.jsx'), /<SuiviCulture/)
})

test('[CA1] la fiche est un occupant du panneau partagé, fermé au changement de vue', () => {
  const hook = source('../hooks/useFiches.jsx')
  assert.match(hook, /ouvrirPanneau\(/)
  assert.match(hook, /commune: true/)
  assert.match(source('../App.jsx'), /occupantFiche\?\.commune/)
})

test('[CA2, CA3] la fiche reprend le suivi et la fiche culture, sans les dupliquer', () => {
  const f = source('../components/FicheCommune.jsx')
  assert.match(f, /api\.suiviCulture\(/)
  assert.match(f, /api\.historique\(/)
  assert.match(f, /<ReferenceCulture/)
  const r = source('../components/ReferenceCulture.jsx')
  for (const s of ['SectionMaintenant', 'SectionReferentiel', 'SectionVarietes', 'SectionVoisinages', 'SectionBioagresseurs']) {
    assert.match(r, new RegExp(`<${s}`), s)
  }
  assert.match(r, /<FicheCalendrier/)
})

test('[CA3] une lecture échouée : un bandeau, et chaque section non lue le dit à sa place', () => {
  const r = source('../components/ReferenceCulture.jsx')
  assert.match(r, /MESSAGE_LECTURE_INCOMPLETE/)
  assert.equal((r.match(/<NonLue \/>/g) || []).length, 4)
})

test('[CA7] « Ajouter à mon potager » n’écrit rien : il ouvre Gaston, phrase pré-écrite (US-358)', () => {
  const f = source('../components/FicheCatalogue.jsx')
  assert.match(f, /ouvrirGastonSur\(\{ sujet: sujetCatalogue\(ligne\), champ: phraseAjouter/)
  assert.doesNotMatch(f, /api\.(creer|enregistrer|poster|ajouter)/i)
})

test('[CA9] aucune règle d’étape, de fenêtre ou de confiance n’est recalculée côté front', () => {
  for (const f of ['./culturesSocle.js', './ficheCommune.js']) {
    const src = source(f)
    assert.doesNotMatch(src, /fenetre_etat\s*=/, f)
    assert.doesNotMatch(src, /calculerEtape|etoiles\s*=|a_confirmer\s*=/, f)
  }
})

test('[CA6] le Catalogue n’a pas de bouton date ; Au potager le garde', () => {
  assert.match(source('../views/Cultures.jsx'), /date: onglet === ONGLET_POTAGER/)
})

test('[CA4] une colonne, puis deux à partir de 700 px de conteneur', () => {
  assert.match(source('../views/Cultures.jsx'), /@\[700px\]\/cultures:grid-cols-2/)
})
