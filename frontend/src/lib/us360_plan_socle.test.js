// [US-360] Le Plan posé sur le socle — `npm test`.
//
// Ce qui se vérifie ici : le mot de Gaston du Plan (CA5), le bandeau qui suit la règle des temps
// (CA2), la recherche « Parcelle ou culture » (CA1), l'infobulle d'un rang à l'appui long (Gherkin 2,
// CA3), et, par lecture des sources, la pose de l'écran sur la coquille (CA1, CA3, CA4, CA6).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import {
  bandeauDuPlan, motDuPlan, parcellesTrouvees, normaliserRecherche, infobulleRang, PLACEHOLDER_RECHERCHE_PLAN,
} from './planSocle.js'
import { enteteDuPlan, jourEnLettres } from './planDessus.js'
import { tachesDuPlan, boutonsMobile } from './aujourdhui.js'
import { calculerMot, MAX_PHRASES } from './motDeGaston.js'
import { NAV } from '../navigation.js'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const lire = (chemin) => readFileSync(join(SRC, chemin), 'utf8')
const VUE = lire('views/PlanDessus.jsx')
const MOBILE = lire('components/PlanMobile.jsx')
const DESSIN = lire('components/PlanDessin.jsx')

const A_LIBERER = [
  { parcelle_id: 1, parcelle: 'Serre', culture: 'tomate cerise', variete: null, rang: 3, fin_le: '2026-10-30' },
  { parcelle_id: 2, parcelle: 'Tubercules', culture: 'pomme de terre', variete: null, rang: 1, fin_le: '2026-10-28' },
  { parcelle_id: 3, parcelle: 'Planche haricots', culture: 'haricot', variete: null, rang: 1, fin_le: '2026-10-25' },
]
const A_CONFIRMER = [
  { parcelle_id: 4, parcelle: 'Planche centrale', culture: 'fève', variete: null, rang: 6, etape_libelle: 'Levée' },
]
const PLAN = (taches, extra = {}) => ({
  date_ref_effective: '2026-11-23',
  taches_du_jour: { a_confirmer: [], a_liberer: [], a_placer: [], ...taches },
  parcelles: [],
  ...extra,
})

// ── CA5 : le mot de Gaston du Plan ───────────────────────────────────────────────────────────

test('[CA5] « 3 rangs à libérer : tomate cerise, pomme de terre, haricot. » → Voir les rangs, Noter', () => {
  const mot = motDuPlan({ taches: tachesDuPlan(PLAN({ a_liberer: A_LIBERER })) })
  assert.match(mot.texte, /^\*\*3 rangs à libérer\*\* : tomate cerise, pomme de terre, haricot\.$/)
  assert.deepEqual(mot.actions.map((a) => a.libelle), ['Voir les rangs', 'Noter'])
  assert.equal(mot.actions[0].vue, 'cultures')
  assert.equal(mot.actions[1].noter, true)
})

test('[CA5] un seul rang : le singulier', () => {
  const mot = motDuPlan({ taches: tachesDuPlan(PLAN({ a_liberer: A_LIBERER.slice(0, 1) })) })
  assert.match(mot.texte, /^\*\*1 rang à libérer\*\* : tomate cerise\.$/)
})

test('[CA5] l’engrais vert n’est dit que si la lecture du plan en porte un, jamais inventé', () => {
  const taches = tachesDuPlan(PLAN({ a_liberer: A_LIBERER }))
  const sans = motDuPlan({ taches })
  assert.doesNotMatch(sans.texte, /engrais vert/)
  const avec = motDuPlan({ taches, engraisVert: { libelle: 'seigle' } })
  assert.match(avec.texte, /Un engrais vert de seigle peut encore y être semé cette semaine\.$/)
})

test('[CA5] deux phrases au plus (contrat du mot, US-353 / CA6)', () => {
  const mot = motDuPlan({ taches: tachesDuPlan(PLAN({ a_liberer: A_LIBERER })), engraisVert: { libelle: 'seigle' } })
  assert.ok(mot.texte.split(/(?<=[.!?…])\s+/).length <= MAX_PHRASES)
})

test('[CA5] rien à libérer : la règle commune (étapes à confirmer), sinon rien à dire', () => {
  const dues = motDuPlan({ taches: tachesDuPlan(PLAN({ a_confirmer: A_CONFIRMER })) })
  assert.match(dues.texte, /étape à confirmer|prévue, à confirmer/)
  assert.equal(motDuPlan({ taches: tachesDuPlan(PLAN({})) }), null)
})

test('[CA5] le mot est calculé sans modèle : mêmes données, même mot', () => {
  const taches = tachesDuPlan(PLAN({ a_liberer: A_LIBERER }))
  assert.deepEqual(motDuPlan({ taches }), motDuPlan({ taches }))
  assert.equal(calculerMot('plan-vue', { taches }, { 'plan-vue': motDuPlan }).actions.length, 2)
})

// ── CA2 : le bandeau suit la règle des temps ───────────────────────────────────────────────────

test('[CA2] « Au 23 novembre », puis « Au 12 novembre » quand on remonte la saison', () => {
  const emprise = { longueur: 25, largeur: 15, posee: true }
  assert.equal(bandeauDuPlan(enteteDuPlan({ date_ref_effective: '2026-11-23' }, emprise)).date, 'Au 23 novembre')
  assert.equal(bandeauDuPlan(enteteDuPlan({ date_ref_effective: '2026-11-12' }, emprise)).date, 'Au 12 novembre')
  assert.equal(jourEnLettres('2026-11-23'), '23 novembre')
})

test('[CA2] le bandeau porte le fond et l’emprise « 25 × 15 m » ; le fond ne prétend pas être une photo avant US-335', () => {
  const b = bandeauDuPlan(enteteDuPlan({ date_ref_effective: '2026-11-23' }, { longueur: 25, largeur: 15, posee: true }))
  assert.equal(b.dimension, '25 × 15 m')
  assert.ok(b.fond.length > 0)
  assert.equal(b.texte, `Au 23 novembre · ${b.fond}`)
})

// ── CA1 : la recherche « Parcelle ou culture » ─────────────────────────────────────────────────

test('[CA1] le texte indicatif de la recherche', () => {
  assert.equal(PLACEHOLDER_RECHERCHE_PLAN, 'Parcelle ou culture')
})

const PARCELLES = {
  parcelles: [
    { id: 1, nom: 'Planche centrale', cultures: [{ culture: 'fève', variete: 'Aguadulce' }, { culture: 'ail' }] },
    { id: 2, nom: 'Serre', cultures: [{ culture: 'tomate cerise' }] },
    { id: 3, nom: 'Châssis', disposition: { lots_en_cours: [{ culture: 'chou pommé', variete: 'Cœur de bœuf' }] } },
  ],
}

test('[CA1] la recherche trouve une parcelle par son nom, une culture ou une variété, sans accent ni casse', () => {
  assert.deepEqual([...parcellesTrouvees(PARCELLES, 'FEVE')], [1])
  assert.deepEqual([...parcellesTrouvees(PARCELLES, 'serre')], [2])
  assert.deepEqual([...parcellesTrouvees(PARCELLES, 'aguadulce')], [1])
  assert.deepEqual([...parcellesTrouvees(PARCELLES, 'chassis')], [3])
  assert.deepEqual([...parcellesTrouvees(PARCELLES, 'coeur')].length, 0)   // « Cœur » : la ligature n'est pas un accent
  assert.deepEqual([...parcellesTrouvees(PARCELLES, 'chou')], [3])
})

test('[CA1] une recherche vide ne retient rien : tout reste affiché', () => {
  assert.equal(parcellesTrouvees(PARCELLES, ''), null)
  assert.equal(parcellesTrouvees(PARCELLES, '   '), null)
  assert.equal(normaliserRecherche('  Fève  Rouge '), 'feve rouge')
})

// ── Gherkin 2, CA3 : l'appui long donne l'étape sans ouvrir la fiche ──────────────────────────────

test('[Gherkin 2] « Fève · Levé, prévu » à l’appui long sur le rang de la fève', () => {
  assert.equal(infobulleRang({ nom: 'Fève', etape: 'levee', prevu: true }), 'Fève · Levé, prévu')
  assert.equal(infobulleRang({ nom: 'Chou', etape: 'en_recolte' }), 'Chou · En récolte')
  assert.equal(infobulleRang({ libre: true }), 'Rang libre')
})

test('[CA3] les rangs du plan réduit, du plan à l’échelle et les pastilles des cartes portent leur infobulle', () => {
  assert.equal((DESSIN.match(/data-tip=\{infobulleDuSegment\(segment\)\}/g) ?? []).length, 3)
  assert.match(MOBILE, /data-tip=\{infobulleRang\(\{ nom: ligne\.nom/)
})

// ── CA3 : le plan mobile ─────────────────────────────────────────────────────────────────────────────

test('[CA3] « 3 à confirmer » et « 3 à libérer » ouvrent la fiche de la première culture concernée', () => {
  const taches = tachesDuPlan(PLAN({
    a_confirmer: [A_CONFIRMER[0], A_CONFIRMER[0], A_CONFIRMER[0]], a_liberer: A_LIBERER,
  }))
  const boutons = boutonsMobile(taches)
  assert.deepEqual(boutons.map((b) => b.texte), ['3 à confirmer', '3 à libérer'])
  assert.equal(boutons[0].premiere.selection.culture, 'fève')
  assert.equal(boutons[1].premiere.selection.culture, 'tomate cerise')
  assert.match(MOBILE, /onClick=\{\(\) => onOuvrir\?\.\(b\.premiere\.selection\)\}/)
})

test('[CA3] le plan mobile : bandeau, rose des vents, « ? Légende ⌄ » et son appui long, chemin, pépinière', () => {
  assert.match(MOBILE, /data-bandeau-plan/)
  assert.match(MOBILE, /<RoseDesVents rose=\{rose\} petite \/>/)
  assert.match(MOBILE, /<LegendeCommune sujet="un rang ou une pastille" \/>/)
  assert.match(MOBILE, /Dans l’ordre du chemin/)
  assert.match(MOBILE, /Ma pépinière/)
  assert.match(MOBILE, /Détail/)
  assert.match(MOBILE, /trouvees\.has\(p\.id\)/)
})

// ── CA1, CA4, CA6 : la pose sur la coquille ─────────────────────────────────────────────────────────

test('[CA1] le titre « Plan des parcelles » et les onglets Plan / Rotation · à venir sont dans l’en-tête de page', () => {
  const plan = NAV.find((n) => n.id === 'plan')
  assert.equal(plan.title, 'Plan des parcelles')
  assert.deepEqual(plan.subnav.map((t) => [t.label, Boolean(t.disabled)]), [['Plan', false], ['Rotation · à venir', true]])
  assert.doesNotMatch(VUE, /<h2[^>]*>\s*\{mode === MODE_ZONES \? 'Plan par zones' : entete\.titre\}/)
})

test('[CA1, CA5] l’écran déclare son mot et sa barre (date + recherche) à la coquille', () => {
  assert.match(VUE, /useDeclarerEcran\(\{\s*mot,\s*barre: \{ recherche: \{ placeholder: PLACEHOLDER_RECHERCHE_PLAN/)
  assert.match(VUE, /motDuPlan\(\{ taches, engraisVert: data\?\.engrais_vert \}\)/)
})

test('[CA4] sur ordinateur, la fiche s’ouvre dans le panneau droit partagé, qui réduit le plan', () => {
  assert.match(VUE, /ouvrirPanneau\(\{ cle: 'fiche', titre: titrePanneau, contenu: <HotePanneau \/> \}\)/)
  assert.match(VUE, /createPortal\(/)
  // Le panneau ne fait pas basculer le plan en mobile : sa largeur est rendue au conteneur.
  assert.match(VUE, /\(bureau && occupantPartage \? LARGEUR_PANNEAU_PX : 0\)/)
  // Plus de panneau interne de 360 px.
  assert.doesNotMatch(VUE, /w-\[360px\]/)
  assert.doesNotMatch(VUE, /<aside/)
})

test('[CA4] sous 900 px la mise en page mobile reste (D7), et la fiche passe par la feuille', () => {
  assert.match(VUE, /const mobile = !bureau \|\| estCheminMobile\(largeurEffective\)/)
  assert.match(VUE, /useMedia\('\(min-width: 900px\)'\)/)
  assert.match(VUE, /\{!panneauDroit && feuilleDetail\}/)
  assert.match(VUE, /\{!panneauDroit && feuilleSuivi\}/)
})

test('[CA4] la légende complète reste sous le plan à l’échelle ; la rose des vents et l’échelle sont dessinées', () => {
  assert.match(VUE, /<LegendeEtapes \/>/)
  assert.match(VUE, /<RoseDesVents rose=\{rose\} \/>/)
  assert.match(VUE, /<EchellePlan u=\{u\} \/>/)
})

test('[CA6] l’éditeur du plan, le détail de parcelle et le retrait avec Gaston restent joignables', () => {
  assert.match(VUE, /Modifier le plan/)
  assert.match(VUE, /<EditeurPlan/)
  assert.match(VUE, /onDetail=\{\(p\) => ouvrirParcelle\(\{ id: p\.id, nom: p\.nom \}\)\}/)
  assert.match(VUE, /ouvrirGastonPourPlan\(\{/)
  assert.match(VUE, /onAjuster=\{peutEditer \? \(\) => ouvrirEditeur\(parcelleOuverte\.id\) : undefined\}/)
})

test('[CA4] une parcelle qui ne répond pas à la recherche s’estompe, rien ne disparaît du plan à l’échelle', () => {
  assert.match(VUE, /estompee=\{Boolean\(trouvees\) && !trouvees\.has\(forme\.id\)\}/)
  assert.match(lire('index.css'), /\.parcelle-plan\.estompee \{ opacity: \.3; \}/)
})

test('[CA4] le mode sombre assombrit le fond du plan (jeton --plan-fond sombre)', () => {
  const css = lire('index.css')
  assert.match(css, /--plan-fond:\s*#F0F2EA/)
  assert.match(css, /--plan-fond:\s*#1A2213/)
})
