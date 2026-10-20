// [US-218 / CA26] La lib de l'onglet « Ma pépinière » : rangement, libellés, grand
// chiffre, règle, fragments liés, onglet de stade par défaut, gestes (même règle que
// la fiche du lot). Les données ont la forme exacte du bloc `parcours` (US-240).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ONGLETS_PEPINIERE, ongletInitial, kanban, caseVide, resumeLigne, ongletStadeParDefaut,
  compteursBarre, basculerCompteur, miseEnEvidence, enteteEtiquette, grandChiffre,
  quantitesEtiquette, datesEtiquette, regleEtiquette, repereFragment, fragmentsLies, lienFragment,
  lienAutreOnglet, nomAccessible, phraseDuree, gestesEtiquette, bandeSemer, phraseReplies,
  gesteSemer, gestesDormant, resteDormant, pastillePepiniere, pepiniereChoisie, periodeCourte,
  dateCourte, phraseProchaineOuverture, ecartJours, fragmentsDuLot,
  indexColonne, etiquettesDuLot, etiquetteOuverte, cleLigneDe, metaBandeau, ligneFragment, bilanLot,
} from './parcours.js'
import { gestesDuLot } from './ficheLot.js'

const REF = '2026-10-19'
const ech = (o = {}) => ({ jours: null, en_retard: false, du: null, au: null, debut_regle: null, raison: null, libelle: null, endurcissement: null, ...o })
const etq = (numero, stade, emplacement_id, etat, o = {}) => ({
  id: `semis-${numero}:${stade}:${emplacement_id}`,
  lot: { id: `semis-${numero}`, numero, culture: o.culture ?? 'chou', variete: o.variete ?? null, date_semis: o.semis ?? '2026-10-01' },
  fragment: o.fragment ?? { rang: 1, total: 1 }, stade, emplacement_id, etat,
  quantites: { graines: null, leves: null, godets: null, unite: 'graines', ...o.q },
  echeance: ech(o.e), mention: o.mention ?? null, soldable_par_levee_terminee: Boolean(o.soldable),
})
const lot = (numero, o = {}) => ({
  lot_id: `semis-${numero}`, semis_id: numero, numero_lot: numero, culture: 'chou', variete: null,
  graines_non_soldees: 0, stock_residuel_godet: 0, plants_obtenus: 0, nb_mises_en_godet: 0,
  echeances: { dormance: { est_dormant: false } }, action_suggeree: null, ...o,
})

const RETARD = etq(28, 'levee', 3, 'repiquer_retard', { q: { graines: 24, leves: 18 }, e: { jours: 6, en_retard: true, du: '2026-10-11', au: '2026-10-13', debut_regle: '2026-10-01' } })
const T1 = etq(23, 'levee', 2, 'levee_en_cours', { culture: 'tomate', variete: 'cerise', q: { graines: 4 }, mention: '12 déjà en godet', soldable: true, fragment: { rang: 1, total: 2 } })
const T2 = etq(23, 'godet', 3, 'en_cours', { culture: 'tomate', variete: 'cerise', q: { godets: 12, unite: 'godets' }, fragment: { rang: 2, total: 2 }, e: { jours: 20 } })
const PRET = etq(7, 'pret', 2, 'a_sortir', { variete: 'frisé', q: { godets: 90, unite: 'godets' }, e: { jours: 0, du: '2026-10-13', au: '2026-10-27', debut_regle: '2026-09-01' } })
const SANS = etq(31, 'godet', null, 'en_cours', { culture: 'basilic', q: { godets: 6, unite: 'godets' } })
const PARCOURS = {
  pepinieres: [
    { id: 2, nom: 'Serre chaude', type_pepiniere: 'chaude', superficie_m2: 10, nb_lots: 1, nb_etiquettes: 2, nb_alertes: 0, prochaine_sortie: null },
    { id: 3, nom: 'Châssis froid', type_pepiniere: 'froide', superficie_m2: null, nb_lots: 2, nb_etiquettes: 2, nb_alertes: 1, prochaine_sortie: { lot_numero: 24, culture: 'poireau', du: '2026-10-23' } },
    { id: 5, nom: 'Véranda', type_pepiniere: null, superficie_m2: null, nb_lots: 0, nb_etiquettes: 0, nb_alertes: 0, prochaine_sortie: null },
  ],
  sans_emplacement: { nb_lots: 1, nb_etiquettes: 1, nb_alertes: 0, prochaine_sortie: null },
  etiquettes: [RETARD, T1, T2, PRET, SANS],
  compteurs: {
    a_repiquer: { total: 1, retard: true }, a_sortir: { total: 1, retard: false }, endurcit: { total: 0, retard: false },
    a_semer: { total: 1, retard: false }, dormants: { total: 2, retard: false },
  },
}

// ── CA1 ─────────────────────────────────────────────────────────────────────
test('CA1 — deux onglets, « Ma pépinière » puis « Lots »', () => {
  assert.deepEqual(ONGLETS_PEPINIERE.map((o) => o.libelle), ['Ma pépinière', 'Lots'])
})
test('CA1 — les anciens onglets ouvrent le parcours, « lots » reste « lots »', () => {
  for (const ancien of ['aujourdhui', 'calendrier', 'emplacements', undefined, 'n importe']) {
    assert.equal(ongletInitial(ancien), 'parcours')
  }
  assert.equal(ongletInitial('lots'), 'lots')
})

// ── CA3 ─────────────────────────────────────────────────────────────────────
test('CA3 — une seule pépinière : sa pastille ; type absent dit tel quel', () => {
  assert.equal(pastillePepiniere([{ nom: 'Serre', superficie_m2: 2.5, type_pepiniere: 'chaude' }]), 'SERRE · 2,5 m² · pépinière chaude')
  assert.equal(pastillePepiniere([{ nom: 'Serre', type_pepiniere: null }]), 'SERRE · type non renseigné')
  assert.equal(pastillePepiniere(PARCOURS.pepinieres), null)
})
test('CA3 — le filtre se pose par identifiant ou par nom (intention du Plan)', () => {
  assert.equal(pepiniereChoisie(PARCOURS, '3').nom, 'Châssis froid')
  assert.equal(pepiniereChoisie(PARCOURS, 'chassis FROID').id, 3)
  assert.equal(pepiniereChoisie(PARCOURS, 'inconnue'), null)
})

// ── CA4 ─────────────────────────────────────────────────────────────────────
test('CA4 — les compteurs disent le total et le retard ; à zéro, éteints', () => {
  const c = compteursBarre(PARCOURS.compteurs)
  assert.deepEqual(c.map((x) => x.cle), ['a_repiquer', 'a_sortir', 'endurcit', 'a_semer', 'dormants'])
  assert.equal(c[0].alerte, true)
  assert.equal(c[2].actif, false)
  assert.equal(c[4].texte, 'dormants')
})
test('CA4 — un compteur met en évidence ses étiquettes ; un second appui retire l’effet', () => {
  assert.equal(miseEnEvidence(RETARD, 'a_repiquer'), true)
  assert.equal(miseEnEvidence(PRET, 'a_repiquer'), false)
  assert.equal(miseEnEvidence(PRET, null), null)
  assert.equal(basculerCompteur('a_sortir', 'a_sortir'), null)
  assert.equal(basculerCompteur(null, 'a_sortir'), 'a_sortir')
})

// ── CA8-CA10, CA17 ──────────────────────────────────────────────────────────
test('CA8 — quatre colonnes dans l’ordre, avec leur compteur d’étiquettes et leur alerte', () => {
  const { colonnes } = kanban(PARCOURS)
  assert.deepEqual(colonnes.map((c) => c.libelle), ['En levée', 'En godet', 'Endurcissement', 'Prêt à sortir'])
  assert.deepEqual(colonnes.map((c) => c.total), [2, 2, 0, 1])
  assert.equal(colonnes[0].alerte, true)
})
test('CA9 — une ligne par pépinière, vides comprises, puis « Sans emplacement »', () => {
  const { lignes } = kanban(PARCOURS)
  assert.deepEqual(lignes.map((l) => l.nom), ['Serre chaude', 'Châssis froid', 'Véranda', 'Sans emplacement'])
  assert.equal(lignes[2].cases.levee.length, 0)
  assert.equal(lignes[3].cases.godet[0].lot.numero, 31)
})
test('CA10 — sans étiquette sans emplacement, pas de ligne « Sans emplacement »', () => {
  const { lignes } = kanban({ ...PARCOURS, sans_emplacement: null })
  assert.equal(lignes.at(-1).nom, 'Véranda')
})
test('CA3 — le filtre ne garde que la ligne choisie (et retire « Sans emplacement »)', () => {
  const { lignes, colonnes } = kanban(PARCOURS, { filtre: 3 })
  assert.deepEqual(lignes.map((l) => l.nom), ['Châssis froid'])
  assert.deepEqual(colonnes.map((c) => c.total), [1, 1, 0, 0])
})
test('CA17 — dans une case, l’ordre de l’API est conservé', () => {
  const a = etq(1, 'levee', 2, 'levee_en_cours')
  const b = etq(2, 'levee', 2, 'repiquer_retard', { e: { jours: 3, en_retard: true } })
  const { lignes } = kanban({ pepinieres: [{ id: 2, nom: 'S' }], etiquettes: [a, b] })
  assert.deepEqual(lignes[0].cases.levee.map((e) => e.lot.numero), [1, 2])
})
test('CA9 — case vide : « vide », et « Prêt à sortir » dit le prochain départ', () => {
  const [, chassis, veranda] = kanban(PARCOURS).lignes
  assert.equal(caseVide('godet', chassis), 'vide')
  assert.equal(caseVide('pret', chassis), 'Rien à sortir aujourd\'hui. Prochain : Poireau #24, le 23 oct.')
  assert.equal(caseVide('pret', veranda), 'vide')
})
test('CA9 — l’en-tête de ligne dit lots, étiquettes et alertes', () => {
  assert.equal(resumeLigne(PARCOURS.pepinieres[1]), '2 lots · 2 étiquettes · 1 alerte')
  assert.equal(resumeLigne(PARCOURS.pepinieres[0]), '10 m² · 1 lot · 2 étiquettes')
})
test('CA11 — aucune mesure de place : ni pourcentage, ni plaque, ni alvéole', () => {
  const texte = JSON.stringify(kanban(PARCOURS).lignes.map(resumeLigne))
  assert.doesNotMatch(texte, /%|plaque|alvéole/)
})

// ── CA12 ────────────────────────────────────────────────────────────────────
test('CA12 — en-têtes d’état en mot, teintés', () => {
  assert.deepEqual(enteteEtiquette(RETARD), { libelle: 'Repiquer — retard', ton: 'retard' })
  assert.equal(enteteEtiquette(etq(1, 'pret', 2, 'sortir_retard')).libelle, 'Sortir — retard')
  assert.equal(enteteEtiquette(etq(1, 'godet', 2, 'sortir_bientot')).ton, 'bientot')
  assert.equal(enteteEtiquette(etq(1, 'endurcissement', 3, 'endurcit_sur_place')).libelle, 'S’endurcit sur place')
  assert.equal(enteteEtiquette(etq(1, 'godet', 2, 'duree_inconnue')).libelle, 'Durée ?')
  assert.equal(enteteEtiquette(T1).libelle, 'Levée en cours')
  assert.equal(enteteEtiquette(T1, { levee_terminee: true }).libelle, 'Levée terminée')
  assert.equal(enteteEtiquette(T2).libelle, 'En cours')
})
test('CA12 — le grand chiffre : retard, compte à rebours, J n/7, ?, ou rien', () => {
  assert.deepEqual(grandChiffre(RETARD), { texte: '+6 j' })
  assert.deepEqual(grandChiffre(T2), { texte: '20 j' })
  assert.deepEqual(grandChiffre(etq(1, 'endurcissement', 2, 'endurcir', { e: { endurcissement: { jour: 3, sur: 7 } } })), { texte: 'J3', apres: '/7' })
  assert.deepEqual(grandChiffre(etq(1, 'levee', 2, 'duree_inconnue')), { texte: '?' })
  assert.deepEqual(grandChiffre(PRET, REF), { avant: 'reste', texte: '8 j' })
  assert.equal(grandChiffre(T1), null)   // A33 : pas d'échéance attendue
})
test('CA12 — quantités en clair, mention comprise', () => {
  assert.deepEqual(quantitesEtiquette(RETARD), { principal: '24 graines', detail: '18 levées' })
  assert.deepEqual(quantitesEtiquette(T1), { principal: '4 graines', detail: '12 déjà en godet' })
  assert.deepEqual(quantitesEtiquette(etq(3, 'levee', 2, 'duree_inconnue', { q: { leves: 1 } })), { principal: '1 plant levé', detail: null })
  assert.equal(quantitesEtiquette(etq(9, 'levee', 2, 'duree_inconnue')).principal, 'quantité non dite')
})
test('CA12 — ligne de dates en clair, raison quand l’échéance manque', () => {
  assert.equal(datesEtiquette(RETARD), 'semé le 1er oct. · repiquage prévu du 11 au 13 oct.')
  assert.equal(datesEtiquette(PRET), 'fourchette du 13 au 27 oct. · semé le 1er oct.')
  const inconnu = etq(3, 'levee', 2, 'duree_inconnue', { e: { raison: 'délai semis → godet non renseigné pour la carotte' } })
  assert.equal(datesEtiquette(inconnu), 'semé le 1er oct. · délai semis → godet non renseigné pour la carotte')
})
test('CA12 — périodes et dates courtes', () => {
  assert.equal(periodeCourte('2026-11-20', '2026-12-04'), 'du 20 nov. au 4 déc.')
  assert.equal(dateCourte('2026-09-01'), '1er sept.')
  assert.equal(ecartJours('2026-10-01', '2026-10-19'), 18)
})

// ── CA13 ────────────────────────────────────────────────────────────────────
test('CA13 — la règle : jours écoulés, fourchette, date de référence', () => {
  const r = regleEtiquette(RETARD, REF)
  assert.equal(r.type, 'jours')
  assert.equal(r.ecoule, 100)            // la référence dépasse la fourchette : elle borne la piste
  assert.equal(r.du, Math.round((10 / 18) * 1000) / 10)
  assert.equal(r.ref, r.ecoule)
})
test('CA13 — sept cases en endurcissement ; pas de règle sans fourchette', () => {
  assert.deepEqual(regleEtiquette(etq(1, 'endurcissement', 2, 'endurcir', { e: { endurcissement: { jour: 3, sur: 7 } } }), REF), { type: 'sept', jour: 3, sur: 7 })
  assert.equal(regleEtiquette(etq(1, 'levee', 2, 'duree_inconnue'), REF), null)
  assert.equal(regleEtiquette(T1, REF), null)
})

// ── CA14, CA15 ──────────────────────────────────────────────────────────────
test('CA14 — retard de repiquage : « Repiquer » en principal, deux gestes au plus', () => {
  const g = gestesEtiquette(RETARD, lot(28, { graines_non_soldees: 24, nb_leves: 18, action_suggeree: { code: 'repiquer' } }))
  assert.deepEqual(g.map((x) => x.libelle), ['Repiquer', 'Noter la levée'])
  assert.equal(g[0].principal, true)
  assert.equal(g[0].ariaLabel, 'Repiquer le lot 28')
  assert.equal(g[1].ouvreFiche, true)
})
test('CA14 — graines restantes d’un lot repiqué : « Noter la levée (terminée) » d’abord (A33)', () => {
  const g = gestesEtiquette(T1, lot(23, { graines_non_soldees: 4, stock_residuel_godet: 12, nb_mises_en_godet: 1 }))
  assert.equal(g[0].libelle, 'Noter la levée (terminée)')
  assert.ok(!g.some((x) => x.code === 'mettre_en_terre'))
})
test('CA14 — « Mettre en terre » seulement sur un fragment qui a des godets, quantité du fragment', () => {
  const l = lot(23, { graines_non_soldees: 4, stock_residuel_godet: 12, nb_mises_en_godet: 1 })
  const g = gestesEtiquette(T2, l)
  assert.deepEqual(g.map((x) => x.code), ['mettre_en_terre'])
  assert.equal(g[0].quantite, 12)
})
test('CA10 — sans emplacement : « Ranger dans… » dépose un déplacement sans destination', () => {
  const g = gestesEtiquette(SANS, lot(31, { culture: 'basilic', stock_residuel_godet: 6, nb_mises_en_godet: 1 }))
  const ranger = g.find((x) => x.code === 'ranger')
  assert.equal(ranger.libelle, 'Ranger dans…')
  assert.equal(ranger.action, 'deplacement')
  assert.equal(ranger.parcelleId, undefined)
})
test('CA15 — « Durée ? » : la phrase à dicter (US-213), selon le stade', () => {
  assert.equal(phraseDuree(etq(3, 'levee', 2, 'duree_inconnue', { culture: 'Carotte' })), '/calendrier duree carotte semis-godet 10-15')
  assert.equal(phraseDuree(etq(3, 'godet', 2, 'duree_inconnue', { culture: 'carotte' })), '/calendrier duree carotte repiquage 10-15')
  assert.equal(phraseDuree(RETARD), null)
})

// ── CA16, CA21, CA22, CA24 ──────────────────────────────────────────────────
test('CA12, CA16 — fragments : repère, liens réciproques', () => {
  assert.equal(repereFragment(T1), '1/2')
  assert.equal(repereFragment(RETARD), null)
  assert.deepEqual(fragmentsLies(PARCOURS.etiquettes, T1).map((e) => e.id), [T2.id])
  assert.deepEqual(fragmentsLies(PARCOURS.etiquettes, RETARD), [])
  assert.equal(lienFragment(T1, T2), '#23 · voir 2/2 ›')
  assert.equal(lienFragment(T2, T1), '#23 · voir 1/2 ‹')
})
test('CA22 — téléphone : le fragment d’un autre onglet de stade est nommé avec son lieu', () => {
  assert.equal(lienAutreOnglet(T2, PARCOURS.pepinieres), '12 godets en godet · Châssis froid ›')
})
test('CA21 — l’onglet de stade par défaut : le premier en alerte, sinon le premier non vide', () => {
  assert.equal(ongletStadeParDefaut(kanban(PARCOURS).colonnes), 'levee')
  const sansAlerte = kanban({ pepinieres: PARCOURS.pepinieres, etiquettes: [PRET] }).colonnes
  assert.equal(ongletStadeParDefaut(sansAlerte), 'pret')
  assert.equal(ongletStadeParDefaut(kanban({ pepinieres: [] }).colonnes), 'levee')
})
test('CA24 — chaque étiquette a un nom accessible complet', () => {
  assert.equal(nomAccessible(T1), 'Lot 23, tomate cerise, fragment 1 sur 2, en levée, 4 graines, Levée en cours')
})

// ── CA5-CA7 : la bande ──────────────────────────────────────────────────────
test('CA5 — une tuile par culture à semer : reste, part écoulée, fenêtre, variétés', () => {
  const b = bandeSemer({ a_semer: [{ culture: 'laitue d’hiver', periode: '1er sept.–31 oct.', jours_restants: 12, part_ecoulee: 0.8, varietes_en_stock: ['Merveille d’hiver'] }] })
  assert.deepEqual(b.tuiles[0], {
    culture: 'laitue d’hiver', nom: 'Laitue d’hiver', reste: 'reste 12 j', part: 80,
    fenetre: 'fenêtre 1er sept.–31 oct.', varietes: ['Merveille d’hiver'], niveaux: [],
  })
  assert.equal(b.calendrier, null)
})
test('CA6 — « + Semer » : semis en pépinière, variété seulement si une seule est en stock', () => {
  assert.deepEqual(gesteSemer({ culture: 'laitue', varietes: ['Merveille'] }), { action: 'semis', culture: 'laitue', contexteSemis: 'pepiniere', variete: 'Merveille' })
  assert.equal(gesteSemer({ culture: 'épinard', varietes: ['a', 'b'] }).variete, null)
})
test('CA7 — cultures sans graines repliées en une phrase', () => {
  assert.equal(phraseReplies(['mâche', 'oignon blanc']), 'Aussi dans leur fenêtre, sans graines en stock : mâche, oignon blanc')
  assert.equal(phraseReplies([]), null)
})
test('CA7 / maquette HF — rien à semer : le calendrier des six mois ; rien du tout : pas de bande', () => {
  const calendrier = { zone: 'océanique', prochaine_ouverture: { date: '2027-02-01', jours: 105 }, mois: [{ mois: '2026-10', s_ouvrent: [] }] }
  assert.equal(bandeSemer({ calendrier_semis: calendrier }).calendrier, calendrier)
  assert.equal(phraseProchaineOuverture(calendrier), 'Prochaine ouverture le 1er février.')
  assert.equal(bandeSemer({}), null)
})

// ── CA19 : le tiroir ────────────────────────────────────────────────────────
test('CA19 — dormant sans godet : « Clôturer » seul (A37)', () => {
  const d = { lot: { id: 'semis-7', numero: 7 }, reste: { graines: 5, godets: null, unite: 'graines' }, a_des_godets: false }
  const l = lot(7, { graines_non_soldees: 5, echeances: { dormance: { est_dormant: true } } })
  assert.deepEqual(gestesDormant(d, l).map((g) => g.code), ['cloturer'])
  assert.equal(resteDormant(d), '5 graines non levées')
})
test('CA19 — dormant avec godets : « Mettre en terre » puis « Clôturer »', () => {
  const d = { lot: { id: 'semis-49', numero: 49 }, reste: { graines: 20, godets: 10, unite: 'graines' }, a_des_godets: true }
  const l = lot(49, { graines_non_soldees: 20, stock_residuel_godet: 10, echeances: { dormance: { est_dormant: true } } })
  assert.deepEqual(gestesDormant(d, l).map((g) => g.code), ['mettre_en_terre', 'cloturer'])
  assert.equal(resteDormant(d), '10 godets · 20 graines non levées')
})

// ── CA28 — amendements d'US-216 livrés avec cette US ────────────────────────
test('CA28 / US-216 CA19 — la fiche dit où est chaque partie d’un lot coupé', () => {
  assert.deepEqual(fragmentsDuLot(PARCOURS, 'semis-23'), ['4 graines en levée · Serre chaude', '12 godets · Châssis froid'])
  assert.deepEqual(fragmentsDuLot(PARCOURS, 'semis-28'), [])
})
test('CA28 / US-216 CA15 — la règle commune propose « Noter la levée (terminée) » sur un lot repiqué', () => {
  const g = gestesDuLot(lot(23, { graines_non_soldees: 4, nb_mises_en_godet: 1, stock_residuel_godet: 12 }))
  assert.equal(g.find((x) => x.code === 'noter_levee').libelle, 'Noter la levée (terminée)')
  assert.equal(gestesDuLot(lot(28, { graines_non_soldees: 24 })).find((x) => x.code === 'noter_levee').libelle, 'Noter la levée')
})

// ── Maquette HF, option B — la fiche en bandeau sous la rangée ──────────────
test('Bandeau — l’étiquette ouverte : celle demandée, sinon la première du lot, sinon aucune', () => {
  assert.equal(etiquetteOuverte(PARCOURS, 'semis-23', T2.id).id, T2.id)
  assert.equal(etiquetteOuverte(PARCOURS, 'semis-23', 'disparue').id, T1.id)
  assert.equal(etiquetteOuverte(PARCOURS, 'semis-999'), null)   // dormant : la fiche s'ouvre en fenêtre
  assert.deepEqual(etiquettesDuLot(PARCOURS, 'semis-23').map((e) => e.fragment.rang), [1, 2])
})
test('Bandeau — sous la rangée de l’étiquette, la pointe sur sa colonne', () => {
  assert.equal(cleLigneDe(T2), 'p3')
  assert.equal(cleLigneDe(SANS), 'sans')
  assert.equal(indexColonne(T1), 0)
  assert.equal(indexColonne(PRET), 3)
})
test('Bandeau — l’en-tête : semis, jour, lieu et type', () => {
  assert.deepEqual(metaBandeau({ date_semis: '2026-09-21' }, T1, PARCOURS.pepinieres, REF), {
    semis: 'semé le 21 sept.', jour: 'J28', lieu: 'Serre chaude (pépinière chaude)',
  })
  assert.equal(metaBandeau({}, SANS, PARCOURS.pepinieres, REF).lieu, 'sans emplacement')
})
test('Bandeau — une ligne par partie, sans répéter ce que dit l’autre', () => {
  assert.deepEqual(ligneFragment(T1, { levee_terminee: true }), { nombre: 4, texte: 'graines · levée terminée', rang: '1/2', stade: 'levee' })
  assert.deepEqual(ligneFragment(T2), { nombre: 12, texte: 'godets · en cours', rang: '2/2', stade: 'godet' })
  assert.equal(ligneFragment(RETARD).texte, 'graines')
})
test('Bandeau — le bilan : nombres du lot et parts de la barre', () => {
  const b = bilanLot({ graines_semees: 20, nb_leves: 18, stock_residuel_godet: 15, nb_plantes: 0, graines_non_soldees: 3 })
  assert.deepEqual(b.nombres.map((n) => n.valeur), [20, 18, 15, 0])
  assert.deepEqual(b.barre, { godet: 75, levee: 15, reste: 10 })
})
