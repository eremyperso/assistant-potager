// [US-355 / CA4-CA6, CA8] L'écran Cultures sur le socle : « Au potager » (les cultures en place, rangées par ce
// qui demande une action) et « Catalogue » (les espèces à ajouter, rangées par prochaine fenêtre de semis), avec
// le Mot de Gaston de chacun. Sans React et sans lecture : la vue passe `GET /plan` et `GET /cultures/vue`.
//
// Aucune règle d'étape, de fenêtre ou de confiance n'est recalculée ici (CA9) : l'étape, `a_confirmer`,
// `a_liberer`, la fenêtre (`fenetre_etat`, `fenetre_geste`, `fenetre_mois`) et les comptes viennent du serveur.
// Ce fichier range, nomme et met en phrases.
import { nomCulture } from './planDessus.js'
import { symboleDeCulture } from './pictosCultures.js'
import { jourCourt } from './aujourdhui.js'
import { libelleEtape, ETAPE_EN_RECOLTE, ETAPE_CROISSANCE, ETAPE_FLEUR, ETAPE_TERMINEE } from './etapes.js'
import { nomEvenement } from './suiviCulture.js'
import { friseDeLigne, libelleFenetre, normaliser, FENETRE_MAINTENANT, FENETRE_BIENTOT, FENETRE_PLUS_TARD } from './cultures.js'
import { normaliserMot } from './motDeGaston.js'
import { avecArticle } from './pepiniereSocle.js'
import { deLaCulture } from './ficheLot.js'
import { MOIS_NOMS } from './calendrier.js'
import { normaliserRecherche } from './planSocle.js'

export const ONGLET_POTAGER = 'potager'
export const ONGLET_CATALOGUE = 'catalogue'

/** Un retard se dit à partir d'une semaine (CA5 : « 2 semaines de retard »). */
export const SEUIL_RETARD_JOURS = 7

const pluriel = (n, un, plusieurs) => (n > 1 ? plusieurs : un)
const JOUR_MS = 86400000
const majuscule = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s)

/** Les onglets d'en-tête : « Au potager · 25 », « Catalogue · 109 » (les comptes sont ceux de la lecture). */
export function ongletsCultures({ nbPotager = 0, nbCatalogue = 0 } = {}) {
  return [
    { id: ONGLET_POTAGER, label: `Au potager · ${nbPotager}` },
    { id: ONGLET_CATALOGUE, label: `Catalogue · ${nbCatalogue}` },
  ]
}

/** La ligne de contexte sous le titre, selon l'onglet. */
export const CONTEXTE_ONGLET = Object.freeze({
  [ONGLET_POTAGER]: 'De la serre au châssis, à leur étape du jour',
  [ONGLET_CATALOGUE]: 'Semer, comparer, ajouter',
})

// ── Au potager (CA4) ────────────────────────────────────────────────────────────────────────────

export const GROUPE_A_CONFIRMER = 'a_confirmer'
export const GROUPE_A_PLACER = 'a_placer'
export const GROUPE_EN_RECOLTE = 'en_recolte'
export const GROUPE_EN_CROISSANCE = 'en_croissance'
export const GROUPE_SEME_PLANTE = 'seme_plante'
export const GROUPE_TERMINE = 'termine'

/** Les groupes, dans l'ordre de la maquette : ce qui demande une action d'abord. */
export const GROUPES = Object.freeze([
  Object.freeze({ cle: GROUPE_A_CONFIRMER, titre: 'À confirmer' }),
  Object.freeze({ cle: GROUPE_A_PLACER, titre: 'À placer' }),
  Object.freeze({ cle: GROUPE_EN_RECOLTE, titre: 'En récolte' }),
  Object.freeze({ cle: GROUPE_EN_CROISSANCE, titre: 'En croissance' }),
  Object.freeze({ cle: GROUPE_SEME_PLANTE, titre: 'Semé ou planté' }),
  Object.freeze({ cle: GROUPE_TERMINE, titre: 'Terminé · rang à libérer' }),
])

/** Le groupe d'une ligne du plan : le serveur dit « à confirmer » et « à libérer », l'étape dit le reste. */
export function groupeDeLigne(c) {
  const e = c?.etapes
  if (e?.a_confirmer) return GROUPE_A_CONFIRMER
  if (e?.a_liberer || e?.etape === ETAPE_TERMINEE) return GROUPE_TERMINE
  if (e?.etape === ETAPE_EN_RECOLTE) return GROUPE_EN_RECOLTE
  if (e?.etape === ETAPE_CROISSANCE || e?.etape === ETAPE_FLEUR) return GROUPE_EN_CROISSANCE
  return GROUPE_SEME_PLANTE
}

const joursEntre = (de, a) => Math.floor((Date.parse(`${a}T12:00:00Z`) - Date.parse(`${de}T12:00:00Z`)) / JOUR_MS)

/** Les jours de retard d'une étape due : l'écart entre sa date prévue et le jour de lecture. */
export function joursDeRetard(e, aujourdhui) {
  if (!e?.a_confirmer || !e.etape_date || !aujourdhui) return 0
  return Math.max(0, joursEntre(String(e.etape_date).slice(0, 10), aujourdhui))
}

/** « Levée prévue aujourd'hui · en retard », « En récolte depuis le 20 oct. », « Terminé le 30 oct. · rang à libérer ». */
export function detailDeLigne(c, aujourdhui) {
  const e = c?.etapes
  if (!e?.etape) return 'Aucune étape notée'
  const date = e.etape_date ? jourCourt(String(e.etape_date).slice(0, 10)) : ''
  const prevue = e.etape_statut === 'prevue' || e.etape_statut === 'non_notee'
  if (e.a_confirmer) {
    const quand = String(e.etape_date).slice(0, 10) === aujourdhui ? 'aujourd’hui' : `le ${date}`
    const retard = joursDeRetard(e, aujourdhui) > 0 ? ' · en retard' : ''
    return `${nomEvenement(e.etape)} prévue ${quand}${retard}`
  }
  if (e.a_liberer || e.etape === ETAPE_TERMINEE) return `Terminé${date ? ` le ${date}` : ''} · rang à libérer`
  const nom = libelleEtape(e.etape)
  if (!date) return nom
  return prevue ? `${nom} prévu le ${date}` : `${nom} depuis le ${date}`
}

/** « Planche centrale · rang 3 » : le plus petit rang occupé quand la culture en tient plusieurs. */
const lieuDeLigne = (parcelle, rangs) => {
  const r = (rangs || []).filter(Number.isInteger)
  return [parcelle, r.length ? `rang ${Math.min(...r)}` : ''].filter(Boolean).join(' · ')
}

/** Les lignes de `GET /cultures/vue`, indexées par nom de culture normalisé. */
const indexDeLaVue = (vue) => new Map((vue?.cultures || []).map((l) => [normaliser(l.culture), l]))

/**
 * Les cultures en place d'une ligne chacune, avec leur groupe, leur emplacement, leur état dit en mots et la frise
 * conseillée de leur espèce (celle de `GET /cultures/vue`). Les pépinières n'y sont pas : leurs lots se lisent dans
 * la Pépinière, et ce qui attend une place est dans « À placer ».
 */
export function lignesAuPotager(plan, vue, aujourdhui = null) {
  const index = indexDeLaVue(vue)
  const jour = aujourdhui || plan?.date_ref_effective || null
  const lignes = []
  for (const p of plan?.parcelles || []) {
    if (p.est_pepiniere) continue
    for (const c of p.cultures || []) {
      const espece = index.get(normaliser(c.culture)) || null
      const rangs = (c.numeros_rangs || []).filter(Number.isInteger)
      const e = c.etapes || null
      const prevue = e?.etape_statut === 'prevue' || e?.etape_statut === 'non_notee'
      lignes.push({
        cle: `p-${p.id}-${c.culture}-${c.variete || ''}`,
        culture: c.culture,
        variete: c.variete || '',
        groupe: groupeDeLigne(c),
        etape: e?.etape || null,
        prevue: Boolean(e?.etape) && prevue,
        due: Boolean(e?.a_confirmer),
        retard: joursDeRetard(e, jour),
        emoji: symboleDeCulture(c.culture, c.variete || ''),
        titre: nomCulture(c.culture, null),
        detail: detailDeLigne(c, jour),
        lieu: lieuDeLigne(p.nom, rangs),
        famille: espece?.famille || '',
        frise: espece ? friseDeLigne(espece) : null,
        parcelleId: p.id,
        parcelle: p.nom,
        rang: rangs.length ? Math.min(...rangs) : null,
        etapes: e,
        quantiteTexte: c.nb_plants != null ? `${c.nb_plants} ${c.nb_plants > 1 ? 'plants' : 'plant'}` : '',
        selection: { parcelleId: p.id, parcelle: p.nom, culture: c.culture, variete: c.variete || null, rang: rangs.length ? Math.min(...rangs) : null },
      })
    }
  }
  return lignes
}

/**
 * Les cultures qui n'ont pas encore de place : les cartes « À placer » que le serveur donne déjà au Plan
 * (`taches_du_jour.a_placer`), sans étape ni emplacement.
 */
export function lignesAPlacer(plan, vue) {
  const index = indexDeLaVue(vue)
  return ((plan?.taches_du_jour || {}).a_placer || []).map((c) => {
    const espece = index.get(normaliser(c.culture)) || null
    const quantite = c.quantite != null ? `${c.quantite} ${c.unite || 'plants'}` : ''
    const origine = c.origine === 'lot'
      ? `Pépinière · lot${c.numero_lot != null ? ` #${c.numero_lot}` : ''}`
      : 'Dite à Gaston, sans parcelle'
    return {
      cle: c.origine === 'lot' ? `a-lot-${c.lot_id ?? c.numero_lot}` : `a-${c.culture}-${c.variete || ''}`,
      culture: c.culture,
      variete: c.variete || '',
      groupe: GROUPE_A_PLACER,
      etape: null,
      prevue: false,
      due: false,
      retard: 0,
      emoji: symboleDeCulture(c.culture, c.variete || ''),
      titre: nomCulture(c.culture, null),
      detail: 'À placer · aucune étape notée',
      lieu: 'Pas encore placé',
      famille: espece?.famille || '',
      frise: espece ? friseDeLigne(espece) : null,
      parcelleId: null,
      parcelle: '',
      rang: null,
      etapes: null,
      quantiteTexte: quantite,
      selection: { parcelleId: null, culture: c.culture, variete: c.variete || null, quantiteTexte: quantite, origineTexte: origine },
    }
  })
}

/** La recherche « Culture ou variété » de la barre d'outils (la parcelle aussi : on cherche où est la fève). */
export function repondALaRecherche(l, recherche) {
  const q = normaliserRecherche(recherche)
  if (!q) return true
  return [l.culture, l.variete, l.parcelle].some((c) => normaliserRecherche(c).includes(q))
}

/** Les familles que le filtre propose, par ordre alphabétique. */
export function famillesDesLignes(lignes) {
  return [...new Set((lignes || []).map((l) => l.famille).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'fr'))
}

/** Les groupes non vides, dans l'ordre de la maquette : `[{ cle, titre, lignes }]` (le titre sans le compte). */
export function groupesAuPotager(lignes) {
  return GROUPES
    .map((g) => ({ ...g, lignes: (lignes || []).filter((l) => l.groupe === g.cle) }))
    .filter((g) => g.lignes.length > 0)
}

// ── Le Mot de Gaston de Cultures · Au potager (CA5) ─────────────────────────────────────────────

/**
 * « **3 levées à confirmer.** L'épinard (Serre) a 2 semaines de retard : un coup d'œil aujourd'hui ? »
 * → *Confirmer la fève* (Gaston sur la première étape due). Rien tant qu'aucune étape n'est due.
 */
export function motDeCultures(lignes) {
  const dues = (lignes || []).filter((l) => l.due)
  if (!dues.length) return null
  const n = dues.length
  const toutesLevees = dues.every((l) => l.etape === 'levee')
  const nom = toutesLevees ? pluriel(n, 'levée', 'levées') : pluriel(n, 'étape', 'étapes')
  const enRetard = [...dues].sort((a, b) => b.retard - a.retard)[0]
  const phraseRetard = enRetard.retard >= SEUIL_RETARD_JOURS
    ? `${majuscule(avecArticle(enRetard.culture))}${enRetard.parcelle ? ` (${enRetard.parcelle})` : ''} a ${Math.floor(enRetard.retard / 7)} ${pluriel(Math.floor(enRetard.retard / 7), 'semaine', 'semaines')} de retard : un coup d’œil aujourd’hui ?`
    : 'Un coup d’œil aujourd’hui ?'
  const premiere = dues[0]
  return normaliserMot({
    texte: `**${n} ${nom} ${pluriel(n, 'à confirmer', 'à confirmer')}.** ${phraseRetard}`,
    actions: [{
      libelle: `Confirmer ${avecArticle(premiere.culture)}`,
      noter: true,
      principale: true,
      // [US-358 / CA1] La culture et l'étape due arrivent par `contexte` ; la phrase est prête dans le champ.
      phrase: premiere.etape === 'levee' ? `J’ai vu la levée ${deLaCulture(String(premiere.culture).toLowerCase())}` : undefined,
      contexte: {
        parcelleId: premiere.parcelleId, parcelle: premiere.parcelle, culture: premiere.culture,
        variete: premiere.variete || null, rang: premiere.rang, etapes: premiere.etapes,
      },
    }],
  })
}

// ── Catalogue (CA6) ─────────────────────────────────────────────────────────────────────────────

/** « Prochaine fenêtre : semer en pépinière février → mars » ; « Semer en place maintenant » pour une fenêtre ouverte. */
export function fenetreDuCatalogue(ligne) {
  const f = libelleFenetre(ligne)
  if (!f) return null
  if (f.gras) return { gras: true, texte: f.texte }
  return { gras: false, texte: f.texte.replace(/^(bientôt|prochaine fenêtre)\s*:\s*/, 'Prochaine fenêtre : ') }
}

/** Le mois (1-12) où la prochaine fenêtre s'ouvre, ou null. */
const debutDeFenetre = (l) => (l.fenetre_mois || []).find((m) => Number.isInteger(m) && m >= 1 && m <= 12) ?? null

/** Combien de mois séparent le mois courant du début de la fenêtre (0 = ce mois-ci), en bouclant sur l'année. */
const ecartDeMois = (mois, courant) => (mois - courant + 12) % 12

export const GROUPE_CAT_MAINTENANT = 'maintenant'
export const GROUPE_CAT_BIENTOT = 'bientot'
export const GROUPE_CAT_PLUS_TARD = 'plus_tard'
export const GROUPE_CAT_SANS_FENETRE = 'sans_fenetre'
export const GROUPE_CAT_AU_POTAGER = 'au_potager'

/** Les espèces du catalogue : une carte chacune, avec sa fenêtre dite, son calendrier et ses parcelles. */
export function lignesCatalogue(vue, lignesPotager = []) {
  const parcelles = new Map()
  for (const l of lignesPotager) {
    const cle = normaliser(l.culture)
    if (!parcelles.has(cle)) parcelles.set(cle, [])
    if (l.parcelle && !parcelles.get(cle).includes(l.parcelle)) parcelles.get(cle).push(l.parcelle)
  }
  return (vue?.cultures || []).map((l) => {
    const lieux = parcelles.get(normaliser(l.culture)) || []
    return {
      cle: `k-${l.culture}`,
      culture: l.culture,
      nom: nomCulture(l.nom_culture || l.culture, null),
      emoji: symboleDeCulture(l.culture, ''),
      famille: l.famille || '',
      nbVarietes: l.nb_varietes || 0,
      sousTitre: [l.nb_varietes > 0 ? `${l.nb_varietes} ${pluriel(l.nb_varietes, 'variété', 'variétés')}` : '', l.famille].filter(Boolean).join(' · '),
      frise: friseDeLigne(l),
      auPotager: Boolean(l.au_potager),
      lieux,
      fenetre: fenetreDuCatalogue(l),
      etatFenetre: l.fenetre_etat,
      gesteFenetre: l.fenetre_geste,
      debut: debutDeFenetre(l),
      brut: l,
    }
  })
}

/** La recherche « Espèce ou variété » de la barre d'outils. */
export function repondAuCatalogue(k, recherche) {
  const q = normaliserRecherche(recherche)
  if (!q) return true
  return [k.culture, k.nom, k.famille, ...(k.brut?.varietes || [])].some((c) => normaliserRecherche(c).includes(q))
}

/**
 * Les groupes du catalogue, rangés par prochaine fenêtre de semis : « À semer maintenant », « À semer d'ici
 * mars » (les fenêtres qui s'ouvrent bientôt), « Plus tard dans la saison », « Sans fenêtre pour votre zone »,
 * puis « Déjà au potager ». `moisCourant` : 1-12, le mois de la date de lecture.
 */
export function groupesDuCatalogue(lignes, moisCourant) {
  const hors = (lignes || []).filter((k) => !k.auPotager)
  const parDebut = (a, b) => ecartDeMois(a.debut ?? moisCourant, moisCourant) - ecartDeMois(b.debut ?? moisCourant, moisCourant)
    || a.nom.localeCompare(b.nom, 'fr')
  const alpha = (a, b) => a.nom.localeCompare(b.nom, 'fr')
  const maintenant = hors.filter((k) => k.etatFenetre === FENETRE_MAINTENANT).sort(alpha)
  const bientot = hors.filter((k) => k.etatFenetre === FENETRE_BIENTOT).sort(parDebut)
  const plusTard = hors.filter((k) => k.etatFenetre === FENETRE_PLUS_TARD).sort(parDebut)
  const sans = hors.filter((k) => ![FENETRE_MAINTENANT, FENETRE_BIENTOT, FENETRE_PLUS_TARD].includes(k.etatFenetre)).sort(alpha)
  const derniere = bientot.length ? bientot[bientot.length - 1].debut : null
  const groupes = [
    { cle: GROUPE_CAT_MAINTENANT, titre: 'À semer maintenant', lignes: maintenant },
    { cle: GROUPE_CAT_BIENTOT, titre: derniere ? `À semer d’ici ${MOIS_NOMS[derniere - 1]}` : 'À semer bientôt', lignes: bientot },
    { cle: GROUPE_CAT_PLUS_TARD, titre: 'Plus tard dans la saison', lignes: plusTard },
    { cle: GROUPE_CAT_SANS_FENETRE, titre: 'Sans fenêtre pour votre zone', lignes: sans },
    { cle: GROUPE_CAT_AU_POTAGER, titre: 'Déjà au potager', lignes: (lignes || []).filter((k) => k.auPotager).sort(alpha) },
  ]
  return groupes.filter((g) => g.lignes.length > 0)
}

/** « en mars », « de février à mars » : la plage de mois d'une fenêtre. */
function plageEnLettres(mois) {
  const m = (mois || []).filter((x) => Number.isInteger(x) && x >= 1 && x <= 12)
  if (!m.length) return ''
  const debut = MOIS_NOMS[m[0] - 1]
  const fin = MOIS_NOMS[m[m.length - 1] - 1]
  return debut === fin ? `en ${debut}` : `de ${debut} à ${fin}`
}

/** « en pépinière », « en place » : où le geste de la fenêtre se fait. */
function ouLeGeste(geste) {
  if (/pepiniere/.test(geste || '')) return 'en pépinière'
  if (/pleine_terre/.test(geste || '')) return 'en place'
  return ''
}

/**
 * « **Le céleri-rave se sème en mars**, en pépinière. » → *Ajouter le céleri-rave* (Gaston reçoit la demande et
 * répond par une proposition à confirmer : rien n'est écrit). Rien tant qu'aucune espèce n'est à semer bientôt.
 */
export function motDuCatalogue(lignes, moisCourant) {
  const prochaine = groupesDuCatalogue(lignes, moisCourant)
    .find((g) => g.cle === GROUPE_CAT_MAINTENANT || g.cle === GROUPE_CAT_BIENTOT)?.lignes[0]
  if (!prochaine) return null
  const nom = avecArticle(prochaine.culture)
  const quand = prochaine.etatFenetre === FENETRE_MAINTENANT ? 'maintenant' : plageEnLettres(prochaine.brut?.fenetre_mois)
  const ou = ouLeGeste(prochaine.gesteFenetre)
  return normaliserMot({
    texte: `**${majuscule(nom)} se sème ${quand}**${ou ? `, ${ou}` : ''}.`,
    actions: [{
      libelle: `Ajouter ${nom}`,
      noter: true,
      principale: true,
      contexte: null,
      phrase: `Ajouter ${nom} à mon potager`,
      sujet: { type: 'catalogue', culture: prochaine.culture, texte: `${prochaine.nom} · catalogue`, varietes: prochaine.brut?.varietes || [] },
    }],
  })
}
