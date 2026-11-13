// [US-327] Le plan du potager vu du dessus — tout ce qui se CALCULE pour le dessiner.
//
// Aucune lecture ici, aucun React (CA2) : la vue `PlanDessus.jsx` lit `GET /plan` une
// fois (CA1) et passe la réponse à ces fonctions. Rien n'est recalculé de ce que le
// serveur sait déjà : la géométrie vient d'US-326, la répartition en rangs et les parts
// d'un rang partagé d'US-198 / US-326, l'étape d'US-320, les compteurs des filtres du
// service du plan (CA4). Ici, seulement : où poser chaque chose, à quelle taille, avec
// quel libellé, et comment le nommer pour un lecteur d'écran.
//
// Conventions de la géométrie (US-326) : `x_m`, `y_m` = coin haut-gauche de la parcelle
// dans l'emprise du potager, en mètres ; la longueur court selon x, la largeur selon y ;
// la rotation tourne la parcelle autour de son centre. Rangs « dans la longueur » : des
// bandes horizontales empilées ; « en travers » : des bandes verticales côte à côte.

import { segmentDeLigne, libelleAccessible, VARIANTE_A_CONFIRMER, ETAPE_EN_RECOLTE } from './etapes.js'
import { symboleDeCulture } from './pictosCultures.js'

// ── Filtres (P8, CA4) ───────────────────────────────────────────────────────────

export const FILTRE_TOUT = 'tout'
export const FILTRE_A_CONFIRMER = 'a_confirmer'
export const FILTRE_EN_RECOLTE = 'en_recolte'
export const FILTRE_RANGS_LIBRES = 'rangs_libres'

const FILTRES = Object.freeze([
  Object.freeze({ cle: FILTRE_TOUT, libelle: 'Tout' }),
  Object.freeze({ cle: FILTRE_A_CONFIRMER, libelle: 'À confirmer', unite: ['culture à confirmer', 'cultures à confirmer'] }),
  Object.freeze({ cle: FILTRE_EN_RECOLTE, libelle: 'En récolte', unite: ['culture en récolte', 'cultures en récolte'] }),
  Object.freeze({ cle: FILTRE_RANGS_LIBRES, libelle: 'Rangs libres', unite: ['rang libre', 'rangs libres'] }),
])

/**
 * [P8, CA4] Les quatre filtres. Le compteur vient du serveur (`filtres_plan`), jamais
 * d'un comptage de l'écran ; seul « À confirmer » l'écrit (maquette), tous le disent
 * aux lecteurs d'écran.
 */
export function filtresDuPlan(plan) {
  const compteurs = plan?.filtres_plan || {}
  return FILTRES.map((f) => {
    if (f.cle === FILTRE_TOUT) return { cle: f.cle, texte: f.libelle, nomAccessible: 'Tout afficher' }
    const n = Number(compteurs[f.cle] ?? 0)
    const unite = n > 1 ? f.unite[1] : f.unite[0]
    return {
      cle: f.cle,
      compteur: n,
      texte: f.cle === FILTRE_A_CONFIRMER ? `${f.libelle} · ${n}` : f.libelle,
      nomAccessible: `${f.libelle} : ${n} ${unite}`,
    }
  })
}

/** [P8] Un segment hors filtre s'estompe ; rien ne disparaît. */
export function estEstompe(filtre, segment) {
  if (!filtre || filtre === FILTRE_TOUT || !segment) return false
  if (filtre === FILTRE_RANGS_LIBRES) return !segment.libre
  if (segment.libre) return true
  if (filtre === FILTRE_A_CONFIRMER) return !segment.aConfirmer
  if (filtre === FILTRE_EN_RECOLTE) return !segment.enRecolte
  return false
}

// ── Emprise, échelle, orientation (P1, P9, P11) ─────────────────────────────────

/** Marge laissée autour des parcelles quand l'emprise n'est pas posée, en mètres. */
export const MARGE_EMPRISE_M = 1
/** Bornes de l'échelle, en pixels par mètre : sous le plancher, le plan défile (CA5). */
export const ECHELLE_MIN = 18
export const ECHELLE_MAX = 40
/** La barre d'échelle mesure toujours cinq mètres (P9). */
export const LONGUEUR_ECHELLE_M = 5

const nombreOuNull = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/** Le rectangle englobant d'une parcelle tournée, en mètres (pour l'emprise déduite). */
function boiteTournee({ x, y, w, h, rotation }) {
  const a = ((rotation || 0) * Math.PI) / 180
  const cos = Math.abs(Math.cos(a))
  const sin = Math.abs(Math.sin(a))
  const bw = w * cos + h * sin
  const bh = w * sin + h * cos
  const cx = x + w / 2
  const cy = y + h / 2
  return { x1: cx - bw / 2, y1: cy - bh / 2, x2: cx + bw / 2, y2: cy + bh / 2 }
}

/**
 * [P1, P11] L'emprise du potager, en mètres. Celle posée sur le potager (US-326) fait
 * foi ; sinon, celle qui contient toutes les parcelles placées, plus une marge — et
 * l'en-tête le dit (`posee: false`).
 */
export function empriseDuPlan(plan, formes = formesDuPlan(plan)) {
  const g = plan?.potager_geometrie || {}
  const L = nombreOuNull(g.emprise_longueur_m)
  const l = nombreOuNull(g.emprise_largeur_m)
  if (L && l) return { longueur: L, largeur: l, posee: true }
  if (!formes.length) return { longueur: 0, largeur: 0, posee: false }
  const boites = formes.map(boiteTournee)
  return {
    longueur: Math.ceil(Math.max(...boites.map((b) => b.x2)) + MARGE_EMPRISE_M),
    largeur: Math.ceil(Math.max(...boites.map((b) => b.y2)) + MARGE_EMPRISE_M),
    posee: false,
  }
}

/**
 * [CA5] Pixels par mètre : le plan remplit la largeur disponible, borné. Sous le
 * plancher, il garde sa taille et défile dans son cadre — jamais la page.
 */
export function echelle(emprise, largeurDispoPx) {
  if (!emprise?.longueur || !largeurDispoPx) return ECHELLE_MIN
  const u = Math.floor(largeurDispoPx / emprise.longueur)
  return Math.max(ECHELLE_MIN, Math.min(ECHELLE_MAX, u))
}

const NORD = Object.freeze({
  n: [0, 'en haut'], ne: [45, 'en haut à droite'], e: [90, 'à droite'], se: [135, 'en bas à droite'],
  s: [180, 'en bas'], so: [225, 'en bas à gauche'], o: [270, 'à gauche'], no: [315, 'en haut à gauche'],
})

/**
 * [P9] La rose des vents : l'angle dont tourner l'aiguille du nord, et la phrase qui
 * le dit. `null` quand le nord n'a pas été posé — on ne suppose pas qu'il est en haut.
 */
export function roseDesVents(plan) {
  const cle = (plan?.potager_geometrie?.orientation_nord || '').toLowerCase()
  const entree = NORD[cle]
  if (!entree) return null
  return { angle: entree[0], nomAccessible: `Rose des vents : nord ${entree[1]} du plan` }
}

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
  'septembre', 'octobre', 'novembre', 'décembre']

/** « 12 novembre » d'une date ISO, sans fuseau (la date de référence est un jour). */
export function jourEnLettres(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  if (!m) return ''
  return `${Number(m[3])} ${MOIS[Number(m[2]) - 1]}`
}

const metres = (v) => (Number.isInteger(v) ? String(v) : String(Math.round(v * 10) / 10).replace('.', ','))

/** [P11] L'en-tête du plan : « Au 12 novembre », le fond utilisé, l'emprise. */
export function enteteDuPlan(plan, emprise) {
  const dimension = emprise?.longueur
    ? `${metres(emprise.longueur)} × ${metres(emprise.largeur)} m${emprise.posee ? '' : ' (déduite des parcelles)'}`
    : ''
  return {
    titre: `Au ${jourEnLettres(plan?.date_ref_effective)}`,
    // US-335 apportera la photo ; d'ici là, le fond est toujours la grille neutre.
    fond: 'Fond masqué · grille',
    dimension,
  }
}

// ── Les parcelles et leurs rangs (P1 à P7) ──────────────────────────────────────

export const SENS_LONGUEUR = 'longueur'
export const SENS_TRAVERS = 'travers'
export const DIR_H = 'h'
export const DIR_V = 'v'

export const FORMES = Object.freeze(['planche', 'bac', 'butte', 'serre', 'pepiniere'])

/** [P5] La forme qui choisit le fond : la forme posée, sinon serre / pépinière / planche. */
export function formeDeParcelle(p) {
  const f = p?.geometrie?.forme
  if (FORMES.includes(f)) return f
  if (p?.est_pepiniere) return 'pepiniere'
  return 'planche'
}

/**
 * [P1] Position et taille d'une parcelle en mètres. La longueur et la largeur sont
 * celles d'US-326 ; à défaut, celles de la fiche (la largeur peut y être déduite), et
 * en dernier recours un carré de la superficie — signalé `estimee`, dessiné en pointillé.
 */
export function dimensionsDeParcelle(p) {
  const g = p?.geometrie || {}
  let w = nombreOuNull(g.longueur_m) ?? nombreOuNull(p?.longueur_m)
  let h = nombreOuNull(g.largeur_m) ?? nombreOuNull(p?.largeur_m)
  let estimee = false
  if (!w || !h) {
    const s = nombreOuNull(p?.superficie_m2)
    if (w && s) h = s / w
    else if (h && s) w = s / h
    else if (s) { w = Math.sqrt(s); h = w }
    else { w = w || 1; h = h || 1 }
    estimee = true
  }
  return { w, h, estimee }
}

/** Une parcelle placée sur le plan (P1) ? Les deux coordonnées, ou rien (G6). */
export const estPlacee = (p) => Boolean(p?.geometrie?.placee)

function ligneDeRang(p, rang) {
  return (p?.cultures || []).find((c) =>
    c.culture === rang.culture && (c.variete || null) === (rang.variete || null)) || null
}

function capitaliser(mot) {
  return mot ? mot.charAt(0).toUpperCase() + mot.slice(1) : ''
}

/** « Fève Aguadulce » : la culture, capitalisée, puis la variété telle qu'écrite. */
export function nomCulture(culture, variete) {
  return [capitaliser(culture || ''), variete || ''].filter(Boolean).join(' ')
}

/** Tolérance d'arrondi des parts (le serveur arrondit au centième). */
const EPSILON_PART = 0.02

/**
 * [P2, US-326 / G4] Les segments d'un rang : une culture par segment, de longueur sa
 * part (fraction). Une part inconnue se partage ce qui reste à égalité ; ce qui reste
 * encore au bout est un segment libre.
 */
function segmentsDuRang(p, entrees, numero, nomParcelle) {
  if (entrees.every((e) => e.libre)) {
    return [segmentLibre(numero, 1, nomParcelle)]
  }
  const cultures = entrees.filter((e) => !e.libre)
  const connues = cultures.filter((e) => typeof e.part === 'number')
  const somme = connues.reduce((s, e) => s + e.part, 0)
  const muettes = cultures.length - connues.length
  const partMuette = muettes ? Math.max(0, 1 - somme) / muettes : 0
  const segments = cultures.map((e) => segmentCulture(p, e, typeof e.part === 'number' ? e.part : partMuette, numero, nomParcelle))
  const total = segments.reduce((s, x) => s + x.part, 0)
  if (total < 1 - EPSILON_PART) segments.push(segmentLibre(numero, 1 - total, nomParcelle))
  return segments
}

function segmentLibre(numero, part, nomParcelle) {
  return {
    cle: `libre-${numero}-${part}`,
    libre: true,
    part,
    numero,
    nomAccessible: `${nomParcelle}, rang ${numero} : libre`,
  }
}

function segmentCulture(p, entree, part, numero, nomParcelle) {
  const ligne = ligneDeRang(p, entree)
  const etat = segmentDeLigne(ligne)
  const nom = nomCulture(entree.culture, entree.variete)
  const etat_lu = etat ? libelleAccessible(etat.etape, etat.variante) : 'étape inconnue'
  return {
    cle: `${entree.culture}|${entree.variete || ''}|${numero}`,
    libre: false,
    part,
    numero,
    culture: entree.culture,
    variete: entree.variete || null,
    nom: capitaliser(entree.culture || ''),
    emoji: symboleDeCulture(entree.culture, entree.variete || ''),
    etape: etat?.etape ?? null,
    variante: etat?.variante ?? null,
    aConfirmer: etat?.variante === VARIANTE_A_CONFIRMER,
    enRecolte: etat?.etape === ETAPE_EN_RECOLTE,
    // [CA3] Le nom accessible dit tout : culture, étape et état, parcelle et rang.
    nomAccessible: `${nom}, ${etat_lu}, ${nomParcelle} rang ${numero}`,
  }
}

/**
 * [P2] Les rangs d'une parcelle, du premier au dernier, chacun avec ses segments.
 * Le nombre de rangs est celui déclaré ; un rang occupé au-delà (dépassement, R7) est
 * dessiné quand même — aucune culture n'est cachée.
 */
export function rangsDeParcelle(p) {
  const d = p?.disposition || {}
  const parNumero = new Map()
  for (const r of d.rangs || []) {
    if (!parNumero.has(r.numero)) parNumero.set(r.numero, [])
    parNumero.get(r.numero).push(r)
  }
  const numeros = [...parNumero.keys()]
  const dernier = Math.max(d.rangs_declares || 0, ...(numeros.length ? numeros : [0]))
  const rangs = []
  for (let n = 1; n <= dernier; n += 1) {
    const entrees = parNumero.get(n) || [{ numero: n, libre: true }]
    rangs.push({ numero: n, segments: segmentsDuRang(p, entrees, n, p.nom) })
  }
  return rangs
}

/** [P6] Les lots d'une pépinière, en vignettes ; toucher l'un ouvre sa fiche (US-216). */
export function lotsDePepiniere(p) {
  const nature = p?.type_pepiniere ? `pépinière ${p.type_pepiniere}` : 'pépinière'
  return ((p?.disposition || {}).lots_en_cours || []).map((l) => ({
    cle: l.lot_id || `${l.numero_lot}`,
    numero: l.numero_lot ?? null,
    emoji: symboleDeCulture(l.culture, l.variete || ''),
    nom: capitaliser(l.culture || ''),
    nomAccessible: `${l.numero_lot != null ? `Lot n° ${l.numero_lot}, ` : ''}${nomCulture(l.culture, l.variete)}, ${nature} : ouvrir dans Ma pépinière`,
    // US-195 / US-216 : l'adresse d'un lot est son numéro court.
    intention: { onglet: 'parcours', lot: l.numero_lot != null ? String(l.numero_lot) : (l.lot_id || null) },
  }))
}

/**
 * [P1-P7] Une parcelle prête à dessiner : position, taille, rotation, forme, sens des
 * rangs, rangs et segments (ou lots), statut actif.
 */
export function formeDuPlan(p, { actif = true } = {}) {
  const g = p?.geometrie || {}
  const { w, h, estimee } = dimensionsDeParcelle(p)
  const pepiniere = Boolean(p?.est_pepiniere)
  return {
    id: p.id,
    nom: p.nom,
    ordre: p.ordre ?? 0,
    x: nombreOuNull(g.x_m) ?? 0,
    y: nombreOuNull(g.y_m) ?? 0,
    w,
    h,
    estimee,
    rotation: nombreOuNull(g.rotation_deg) ?? 0,
    dir: g.sens_rangs === SENS_TRAVERS ? DIR_V : DIR_H,
    forme: formeDeParcelle(p),
    actif,
    pepiniere,
    typePepiniere: p?.type_pepiniere || null,
    rangs: pepiniere || !actif ? [] : rangsDeParcelle(p),
    lots: pepiniere && actif ? lotsDePepiniere(p) : [],
  }
}

/** Toutes les parcelles placées, actives puis inactives (P7), dans l'ordre du chemin. */
export function formesDuPlan(plan) {
  const actives = (plan?.parcelles || []).filter(estPlacee).map((p) => formeDuPlan(p))
  const inactives = (plan?.parcelles_inactives || []).filter(estPlacee).map((p) => formeDuPlan(p, { actif: false }))
  return [...actives, ...inactives].sort((a, b) => a.ordre - b.ordre)
}

/** [P10] Les parcelles actives qui n'ont pas encore de place sur le plan. */
export function parcellesAPlacer(plan) {
  return (plan?.parcelles || []).filter((p) => !estPlacee(p)).map((p) => ({ id: p.id, nom: p.nom }))
}

/**
 * [P10] Aucune parcelle placée : le plan par zones — une tuile par parcelle active,
 * dans l'ordre du chemin, de taille croissante avec la superficie (piste B).
 */
export function tuilesParZones(plan) {
  return (plan?.parcelles || [])
    .slice()
    .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0))
    .map((p) => {
      const forme = formeDuPlan(p)
      const aire = forme.w * forme.h
      return {
        ...forme,
        x: 0,
        y: 0,
        rotation: 0,
        dir: DIR_H,
        largeurPx: Math.round(Math.min(300, Math.max(140, aire * 4.4))),
        hauteurPx: aire > 40 ? 150 : 120,
      }
    })
}

/** Le mode de dessin : le plan, les zones (P10), ou rien du tout (CA7). */
export const MODE_PLAN = 'plan'
export const MODE_ZONES = 'zones'
export const MODE_VIDE = 'vide'

export function modeDuPlan(plan) {
  if (!(plan?.parcelles || []).length && !(plan?.parcelles_inactives || []).length) return MODE_VIDE
  return formesDuPlan(plan).length ? MODE_PLAN : MODE_ZONES
}

// ── Libellé d'un segment selon la place (P3) ───────────────────────────────────

export const LIBELLE_VERTICAL = 'vertical'
export const LIBELLE_COMPLET = 'complet'
export const LIBELLE_EMOJI_PICTO = 'emoji_picto'
export const LIBELLE_PICTO = 'picto'
export const LIBELLE_RIEN = 'rien'

/**
 * [P3] Ce que porte un segment selon sa taille à l'écran (seuils de la maquette) :
 * emoji + nom + pictogramme ; emoji + pictogramme ; pictogramme seul ; rien. En travers,
 * le nom s'écrit verticalement quand le segment est assez haut.
 */
export function modeLibelle(largeurPx, hauteurPx, dir) {
  if (dir === DIR_V && hauteurPx >= 110 && largeurPx >= 18) return LIBELLE_VERTICAL
  if (largeurPx >= 104 && hauteurPx >= 17) return LIBELLE_COMPLET
  if (largeurPx >= 44 && hauteurPx >= 15) return LIBELLE_EMOJI_PICTO
  if (largeurPx >= 17 && hauteurPx >= 14) return LIBELLE_PICTO
  return LIBELLE_RIEN
}

/** Marge intérieure d'une parcelle et écart entre rangs, en pixels (maquette). */
export const MARGE_PARCELLE_PX = 5
export const ECART_RANGS_PX = 2

/**
 * [P3] La taille d'un segment en pixels, pour choisir son libellé : sa part sur la
 * longueur du rang, la hauteur d'un rang sur l'autre axe.
 */
export function tailleSegment(forme, segment, u) {
  const iw = forme.w * u - 2 * MARGE_PARCELLE_PX
  const ih = forme.h * u - 2 * MARGE_PARCELLE_PX
  const n = Math.max(1, forme.rangs.length)
  if (forme.dir === DIR_V) {
    return { largeur: (iw - (n - 1) * ECART_RANGS_PX) / n, hauteur: segment.part * ih }
  }
  return { largeur: segment.part * iw, hauteur: (ih - (n - 1) * ECART_RANGS_PX) / n }
}

/** [P6] Le nom d'un lot s'écrit si la vignette a la place (un tiers de la parcelle). */
export function lotAvecNom(forme, u) {
  return (forme.w * u - 20) / 3 > 90
}

// ── Toucher un rang libre ───────────────────────────────────────────────────────

/** [Interactions] Le message d'un rang libre : le plan n'écrit rien (US-333). */
export const MESSAGE_RANG_LIBRE = 'Rang libre : glissez une culture « À placer », ou dites-le à Gaston'

/** La sélection d'une culture du plan, telle que le suivi (US-322) la reçoit. */
export function selectionDeSegment(forme, segment) {
  if (!segment || segment.libre) return null
  return {
    parcelleId: forme.id,
    parcelle: forme.nom,
    culture: segment.culture,
    variete: segment.variete,
    rang: segment.numero,
    cle: segment.cle,
    // [US-325] « Noter » sur une pépinière renvoie vers Ma pépinière.
    ...(forme.pepiniere && { pepiniere: true }),
  }
}
