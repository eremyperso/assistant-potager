// [US-329] Le plan sur mobile, dans l'ordre du chemin.
//
// Un seul écran : un mini-plan pour se repérer (le dessin d'US-327 réduit, CA2), puis les
// parcelles dans l'ordre où le jardinier les longe — `Parcelle.ordre`, arbitrage P6 — avec une
// ligne par culture et par rang. Tout se calcule ici depuis la même lecture `GET /plan` ; le
// composant ne fait qu'afficher. Pas de modification du plan sur mobile.
import { formeDuPlan, estPlacee, nomCulture, ECHELLE_MIN, ECHELLE_MAX } from './planDessus.js'
import { segmentDeLigne, libelleEtape, VARIANTE_A_CONFIRMER, VARIANTE_PREVU } from './etapes.js'
import { symboleDeCulture } from './pictosCultures.js'
import { jourCourt, quantiteEnLettres } from './aujourdhui.js'

/** [CA1] Sous cette largeur de CONTENEUR (pas d'écran), l'écran Plan passe en chemin mobile. */
export const LARGEUR_CHEMIN_PX = 720

/**
 * [M2] La hauteur maximale par défaut du mini-plan, quand la hauteur d'écran est inconnue.
 * L'échelle se règle d'abord sur la LARGEUR disponible ; cette hauteur n'est qu'un garde-fou
 * pour les terrains très allongés (un plafond de 200 px rendait un plan carré illisible).
 */
export const HAUTEUR_MINI_PLAN_MAX_PX = 450

/** Plancher du garde-fou, sur un écran très bas (paysage). */
export const HAUTEUR_MINI_PLAN_MIN_PX = 280

/** Part de la hauteur d'écran que le mini-plan peut occuper : le début de la liste reste visible. */
export const PART_HAUTEUR_ECRAN_MINI_PLAN = 0.55

/** [M2] La hauteur maximale du mini-plan pour un écran de cette hauteur (px). */
export function hauteurMaxMiniPlan(hauteurEcranPx) {
  if (!hauteurEcranPx || hauteurEcranPx <= 0) return HAUTEUR_MINI_PLAN_MAX_PX
  return Math.max(HAUTEUR_MINI_PLAN_MIN_PX, Math.round(hauteurEcranPx * PART_HAUTEUR_ECRAN_MINI_PLAN))
}

export const TEXTE_LEGENDE_MOBILE = 'Touchez une parcelle pour y aller · modification sur ordinateur'
export const TEXTE_LOTS_PEPINIERE = 'Les lots se suivent et se notent dans Ma pépinière'
export const TEXTE_LIBRE = 'Libre'

/** [CA1] L'écran se lit-il en chemin mobile à cette largeur de conteneur ? */
export const estCheminMobile = (largeurPx) => largeurPx > 0 && largeurPx < LARGEUR_CHEMIN_PX

/**
 * [M2] L'échelle du mini-plan : toute l'emprise dans la largeur, sous la hauteur maximale
 * (`hauteurMaxPx`, par défaut `HAUTEUR_MINI_PLAN_MAX_PX`).
 */
export function echelleMiniPlan(emprise, largeurPx, hauteurMaxPx = HAUTEUR_MINI_PLAN_MAX_PX) {
  if (!emprise?.longueur || !emprise?.largeur || !largeurPx) return 0
  return Math.min(largeurPx / emprise.longueur, hauteurMaxPx / emprise.largeur)
}

/**
 * [Agrandir] Les crans de zoom du plan agrandi, en pixels par mètre : ce sont les bornes du plan
 * complet (`ECHELLE_MIN`/`ECHELLE_MAX`) et un cran intermédiaire. On part du plus petit : le plan
 * entier ou presque, noms visibles, qu'on déplace au doigt (le pinch n'est pas géré).
 */
export const CRANS_ZOOM_AGRANDI = Object.freeze([ECHELLE_MIN, 28, ECHELLE_MAX])
export const CRAN_ZOOM_INITIAL = 0

/** Le cran après un « + » (`delta` = 1) ou un « − » (`delta` = -1), borné aux crans existants. */
export function cranZoomSuivant(cran, delta) {
  const dernier = CRANS_ZOOM_AGRANDI.length - 1
  const courant = Number.isInteger(cran) ? cran : CRAN_ZOOM_INITIAL
  return Math.max(0, Math.min(dernier, courant + delta))
}

/** L'échelle (px/m) du plan agrandi à ce cran. */
export const echelleAgrandie = (cran) => CRANS_ZOOM_AGRANDI[cranZoomSuivant(cran, 0)]

const capitaliser = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : '')

/** « En récolte depuis le 20 oct. », « Levé prévu le 14 nov. » */
export function etatDeLigne(etapes) {
  if (!etapes?.etape) return ''
  const libelle = etapes.etape_libelle || libelleEtape(etapes.etape)
  if (!etapes.etape_date) return libelle
  const jour = jourCourt(etapes.etape_date)
  return etapes.etape_statut === 'prevue' ? `${libelle} prévu le ${jour}` : `${libelle} depuis le ${jour}`
}

function ligneDeCulture(p, culture, variete) {
  return (p?.cultures || []).find((c) => c.culture === culture && (c.variete || null) === (variete || null)) || null
}

/** [M5] Une ligne de culture : « R3 », étape, emoji + nom, état · variété, « À confirmer ». */
function ligneCulture(p, { culture, variete, numero, cle }) {
  const ligne = ligneDeCulture(p, culture, variete)
  const etat = segmentDeLigne(ligne)
  const rang = numero ? `R${numero}` : '—'
  const detail = [etatDeLigne(ligne?.etapes), variete].filter(Boolean).join(' · ')
  const nom = capitaliser(culture || '')
  const aConfirmer = etat?.variante === VARIANTE_A_CONFIRMER
  return {
    cle: `${p.id}-${cle}`,
    libre: false,
    rang,
    emoji: symboleDeCulture(culture, variete || ''),
    nom,
    detail,
    etape: etat?.etape ?? null,
    variante: etat?.variante ?? null,
    prevu: etat?.variante === VARIANTE_PREVU,
    aConfirmer,
    nomAccessible: `${numero ? `Rang ${numero}` : 'Sans rang'}, ${nomCulture(culture, variete)}, ${detail || 'étape inconnue'}`
      + `${aConfirmer ? ', à confirmer' : ''} : ouvrir son suivi`,
    selection: {
      parcelleId: p.id, parcelle: p.nom, culture, variete: variete || null, rang: numero || null,
      cle: `${culture}|${variete || ''}|${numero ?? ''}`,
    },
  }
}

/** [M5] Les lignes d'une parcelle : une par culture et par rang, les rangs libres en « Libre ». */
export function lignesDeParcelle(p) {
  const forme = formeDuPlan(p)
  const lignes = []
  for (const rang of forme.rangs) {
    for (const s of rang.segments) {
      if (s.libre) {
        lignes.push({
          cle: `${p.id}-${s.cle}`, libre: true, rang: `R${rang.numero}`, nom: TEXTE_LIBRE,
          nomAccessible: `Rang ${rang.numero} : libre`,
        })
      } else {
        lignes.push(ligneCulture(p, { culture: s.culture, variete: s.variete, numero: rang.numero, cle: s.cle }))
      }
    }
  }
  // Une parcelle sans rangs déclarés garde ses cultures : aucune n'est cachée.
  if (!forme.rangs.length) {
    for (const c of p.cultures || []) {
      lignes.push(ligneCulture(p, { culture: c.culture, variete: c.variete, numero: null, cle: `${c.culture}|${c.variete || ''}` }))
    }
  }
  return lignes
}

const STADES = { godet: 'en godet', semis: 'semé' }

/** [M6] Les lots d'une pépinière : n°, emoji, nom, variété, quantité, stade ; vers leur fiche. */
export function lotsDuChemin(p) {
  const lots = [...((p?.disposition || {}).lots_en_cours || [])]
    .sort((a, b) => (a.numero_lot ?? Infinity) - (b.numero_lot ?? Infinity))
  return lots.map((l) => {
    const nom = capitaliser(l.culture || '')
    const quantite = quantiteEnLettres(l.quantite, l.unite)
    const stade = STADES[l.stade] || ''
    return {
      cle: l.lot_id || String(l.numero_lot),
      numero: l.numero_lot ?? null,
      emoji: symboleDeCulture(l.culture, l.variete || ''),
      nom,
      variete: l.variete || '',
      detail: [quantite, stade].filter(Boolean).join(' · '),
      nomAccessible: [l.numero_lot != null ? `Lot n° ${l.numero_lot}` : 'Lot', nomCulture(l.culture, l.variete), quantite, stade]
        .filter(Boolean).join(', ') + ' : ouvrir dans Ma pépinière',
      intention: { onglet: 'parcours', lot: l.numero_lot != null ? String(l.numero_lot) : (l.lot_id || null) },
    }
  })
}

const rangsEnLettres = (n) => (n ? `${n} rang${n > 1 ? 's' : ''}` : 'Rangs non déclarés')

/**
 * [M5, M6, CA4] Les parcelles actives dans l'ordre du chemin (`ordre`, puis nom) — placées ou
 * non : une parcelle sans place sur le plan est listée à son rang d'ordre, pas dessinée.
 */
export function parcellesDuChemin(plan) {
  return [...(plan?.parcelles || [])]
    .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0) || String(a.nom).localeCompare(String(b.nom), 'fr'))
    .map((p) => {
      const pepiniere = Boolean(p.est_pepiniere)
      return {
        id: p.id,
        nom: p.nom,
        placee: estPlacee(p),
        pepiniere,
        sousTitre: pepiniere
          ? `pépinière${p.type_pepiniere ? ` ${p.type_pepiniere}` : ''}`
          : rangsEnLettres(p.nb_rangs),
        lignes: pepiniere ? [] : lignesDeParcelle(p),
        lots: pepiniere ? lotsDuChemin(p) : [],
      }
    })
}

/** L'identifiant DOM de la carte d'une parcelle, cible du défilement depuis le mini-plan. */
export const idCarteChemin = (id) => `chemin-parcelle-${id}`
