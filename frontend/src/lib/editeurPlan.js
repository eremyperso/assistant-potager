// [US-333] L'éditeur du plan — tout ce qui se calcule, sans React (CA6).
//
// Poser, déplacer, dimensionner, tourner, orienter : l'aimantation, les rotations, les cotes, le
// contrôle de surface, la charge d'« Enregistrer » et l'annulation vivent ici, couverts par `npm test`.
// Le composant (`EditeurPlan.jsx`) ne fait que dessiner l'état et relayer les gestes.
//
// Règles (US-333) : E1 aimantation à 50 cm, parcelles alignées sur l'angle du potager, quatre formes
// seulement ; E2 une parcelle posée prend ses dimensions connues, sinon un carré de sa superficie ;
// E3 une forme NOUVELLE passe par Gaston ; E4 « Retirer du plan » efface la position, pas la
// parcelle ; E5 rien n'est écrit avant « Enregistrer » ; E6 les rangs ne descendent pas sous les rangs
// occupés ; E7 pas d'édition sur mobile.
import { dimensionsDeParcelle, estPlacee, formeDeParcelle, SENS_TRAVERS } from './planDessus.js'
import { peutEnregistrer } from './gestes.js'

/** [E1] L'aimantation, en mètres. */
export const PAS_AIMANT_M = 0.5
/** Les dimensions et positions bornées (celles du serveur, `geometrie.py`). */
export const COTE_MIN_M = 0.5
export const COTE_MAX_M = 200
export const POSITION_MAX_M = 2000
/** [E1] En deçà de cet écart, une rotation se recolle sur l'angle du potager. */
export const SEUIL_ALIGNEMENT_DEG = 5
/** Le pas d'une rotation à la poignée. */
export const PAS_ROTATION_DEG = 5
/** [CA7] Sous cette largeur de conteneur, l'éditeur n'est pas proposé (E7). */
export const LARGEUR_MIN_EDITEUR_PX = 720
export const PROFONDEUR_ANNULATION = 100

/** [E1] Les quatre formes d'une parcelle nouvelle, pas de dessin libre. */
export const FORMES_NOUVELLES = Object.freeze([
  { id: 'planche', libelle: 'Planche', article: 'une', longueur: 4, largeur: 1.2 },
  { id: 'bac', libelle: 'Bac', article: 'un', longueur: 2, largeur: 1 },
  { id: 'pepiniere', libelle: 'Pépinière', article: 'une', longueur: 2, largeur: 1.2 },
  { id: 'serre', libelle: 'Serre', article: 'une', longueur: 4, largeur: 3 },
])

/** [CA5] La rose des vents : huit directions, dans l'ordre des aiguilles ; `nord` dit où est le nord du plan. */
export const DIRECTIONS = Object.freeze([
  { id: 'n', libelle: 'Nord', nord: 'en haut du plan', angle: 0 },
  { id: 'ne', libelle: 'Nord-est', nord: 'en haut à droite du plan', angle: 45 },
  { id: 'e', libelle: 'Est', nord: 'à droite du plan', angle: 90 },
  { id: 'se', libelle: 'Sud-est', nord: 'en bas à droite du plan', angle: 135 },
  { id: 's', libelle: 'Sud', nord: 'en bas du plan', angle: 180 },
  { id: 'so', libelle: 'Sud-ouest', nord: 'en bas à gauche du plan', angle: 225 },
  { id: 'o', libelle: 'Ouest', nord: 'à gauche du plan', angle: 270 },
  { id: 'no', libelle: 'Nord-ouest', nord: 'en haut à gauche du plan', angle: 315 },
])

const nombre = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const arrondi = (v, d = 2) => Math.round(v * 10 ** d) / 10 ** d
const borne = (v, mini, maxi) => Math.min(maxi, Math.max(mini, v))
const copie = (o) => JSON.parse(JSON.stringify(o))

/** « 3,5 » — le séparateur décimal d'ici. */
export const texteMetres = (v) => String(arrondi(v, 2)).replace('.', ',')
/** « −2,5° » : un angle signé, dans ]−180 ; 180]. */
export function texteAngle(deg) {
  let a = ((deg % 360) + 360) % 360
  if (a > 180) a -= 360
  return `${a < 0 ? '−' : ''}${String(arrondi(Math.abs(a), 1)).replace('.', ',')}°`
}

/** [E1] La valeur recollée sur la grille de 50 cm. */
export function aimanter(valeur, pas = PAS_AIMANT_M) {
  return arrondi(Math.round(valeur / pas) * pas, 2)
}

/** Un angle ramené dans [0, 360[. */
export const normaliserAngle = (deg) => arrondi(((deg % 360) + 360) % 360, 1)

/** [E1] Une rotation recollée sur l'alignement (0) quand elle en est proche, sinon au pas de 5°. */
export function aimanterRotation(deg) {
  const a = normaliserAngle(deg)
  const ecart = Math.min(a, 360 - a)
  if (ecart <= SEUIL_ALIGNEMENT_DEG) return 0
  return normaliserAngle(Math.round(a / PAS_ROTATION_DEG) * PAS_ROTATION_DEG)
}

// ── L'état de l'éditeur ──────────────────────────────────────────────────────

function parcelleEditable(p) {
  const g = p.geometrie || {}
  const { w, h, estimee } = dimensionsDeParcelle(p)
  const placee = estPlacee(p)
  return {
    id: p.id,
    nom: p.nom,
    forme: formeDeParcelle(p),
    placee,
    x: placee ? nombre(g.x_m) ?? 0 : null,
    y: placee ? nombre(g.y_m) ?? 0 : null,
    w: arrondi(w),
    h: arrondi(h),
    estimee,
    rotation: nombre(g.rotation_deg) ?? 0,
    sens: g.sens_rangs === SENS_TRAVERS ? SENS_TRAVERS : 'longueur',
    nbRangs: nombre(p.nb_rangs) ?? nombre(p.disposition?.rangs_declares),
    rangsOccupes: nombre(p.disposition?.rangs_occupes) ?? 0,
    superficieFiche: nombre(p.superficie_m2),
    alignerFiche: false,
    pepiniere: Boolean(p.est_pepiniere),
  }
}

/**
 * L'état de départ, lu dans `GET /plan` : les parcelles ACTIVES (une parcelle inactive reste grisée
 * sur le plan, elle ne se modifie pas ici), la géométrie du potager, aucune modification.
 */
export function etatInitial(plan, selection = null) {
  const parcelles = (plan?.parcelles || []).map(parcelleEditable)
  const g = plan?.potager_geometrie || {}
  const potager = {
    nord: g.orientation_nord || null,
    angle: nombre(g.angle_deg) ?? 0,
    emprise: { longueur: nombre(g.emprise_longueur_m), largeur: nombre(g.emprise_largeur_m) },
  }
  const base = { parcelles, potager }
  return {
    ...base,
    origine: copie(base),
    selection: parcelles.some((p) => p.id === selection) ? selection : null,
    passe: [],
    futur: [],
  }
}

/**
 * Une parcelle née (confirmée par Gaston) ou disparue (supprimée, rendue inactive) pendant l'édition :
 * elle entre dans l'éditeur, ou en sort, sans toucher aux modifications en cours.
 */
export function synchroniser(etat, plan) {
  const neuf = etatInitial(plan)
  const connues = new Set(etat.parcelles.map((p) => p.id))
  const presentes = new Set(neuf.parcelles.map((p) => p.id))
  const ajoutees = neuf.parcelles.filter((p) => !connues.has(p.id))
  const gardees = etat.parcelles.filter((p) => presentes.has(p.id))
  if (!ajoutees.length && gardees.length === etat.parcelles.length) return etat
  return {
    ...etat,
    parcelles: [...gardees, ...ajoutees],
    origine: {
      ...etat.origine,
      parcelles: [...etat.origine.parcelles.filter((p) => presentes.has(p.id)), ...copie(ajoutees)],
    },
    selection: presentes.has(etat.selection) ? etat.selection : null,
    passe: [], futur: [],
  }
}

/** Les parcelles posées, puis celles « À placer ». */
export const posees = (etat) => etat.parcelles.filter((p) => p.placee)
export const aPlacer = (etat) => etat.parcelles.filter((p) => !p.placee)
export const parcelleDe = (etat, id) => etat.parcelles.find((p) => p.id === id) || null

/** [E5] Applique une modification en gardant l'état d'avant, pour l'annulation (Ctrl+Z). */
function modifier(etat, fabrique) {
  const base = { parcelles: etat.parcelles, potager: etat.potager }
  const apres = fabrique(copie(base))
  if (!apres || JSON.stringify(apres) === JSON.stringify(base)) return etat
  return {
    ...etat,
    ...apres,
    passe: [...etat.passe, base].slice(-PROFONDEUR_ANNULATION),
    futur: [],
  }
}

function surParcelle(etat, id, f) {
  return modifier(etat, (b) => {
    const p = b.parcelles.find((q) => q.id === id)
    if (!p) return null
    f(p)
    return b
  })
}

/** Annuler la dernière action (Ctrl+Z). */
export function annuler(etat) {
  if (!etat.passe.length) return etat
  const precedent = etat.passe[etat.passe.length - 1]
  return {
    ...etat,
    ...copie(precedent),
    passe: etat.passe.slice(0, -1),
    futur: [{ parcelles: etat.parcelles, potager: etat.potager }, ...etat.futur],
  }
}

/** Rétablir l'action annulée (Ctrl+Maj+Z / Ctrl+Y). */
export function refaire(etat) {
  if (!etat.futur.length) return etat
  const [suivant, ...reste] = etat.futur
  return {
    ...etat,
    ...copie(suivant),
    passe: [...etat.passe, { parcelles: etat.parcelles, potager: etat.potager }],
    futur: reste,
  }
}

export const selectionner = (etat, id) => (etat.selection === id ? etat : { ...etat, selection: id })

/** [E2] Une parcelle de « À placer » posée à (x, y) : ses dimensions connues, sinon un carré de sa superficie. */
export function poser(etat, id, x, y) {
  const apres = surParcelle(etat, id, (p) => {
    if (p.estimee) {   // dimensions déduites de la superficie : recollées sur la grille, jamais sous 50 cm
      p.w = Math.max(COTE_MIN_M, aimanter(p.w))
      p.h = Math.max(COTE_MIN_M, aimanter(p.h))
    }
    p.x = borne(aimanter(x), 0, POSITION_MAX_M)
    p.y = borne(aimanter(y), 0, POSITION_MAX_M)
    p.placee = true
    p.rotation = 0           // alignée sur l'angle du potager
    p.estimee = false
  })
  return apres === etat ? etat : { ...apres, selection: id }
}

/** [E1] Déplacer : le coin haut-gauche se recolle sur la grille. */
export function deplacer(etat, id, x, y) {
  return surParcelle(etat, id, (p) => {
    if (!p.placee) return
    p.x = borne(aimanter(x), 0, POSITION_MAX_M)
    p.y = borne(aimanter(y), 0, POSITION_MAX_M)
  })
}

/** Un pas du clavier : 50 cm. */
export const decaler = (etat, id, dx, dy) => {
  const p = parcelleDe(etat, id)
  return p?.placee ? deplacer(etat, id, p.x + dx * PAS_AIMANT_M, p.y + dy * PAS_AIMANT_M) : etat
}

/** [E1] Dimensionner : longueur et largeur recollées sur la grille, jamais sous 50 cm. */
export function redimensionner(etat, id, { w, h }) {
  return surParcelle(etat, id, (p) => {
    if (w != null) p.w = borne(aimanter(w) || COTE_MIN_M, COTE_MIN_M, COTE_MAX_M)
    if (h != null) p.h = borne(aimanter(h) || COTE_MIN_M, COTE_MIN_M, COTE_MAX_M)
    p.estimee = false
  })
}

/** [E1] Tourner : recollée sur l'angle du potager de près, sinon au pas de 5°. */
export function tourner(etat, id, deg) {
  return surParcelle(etat, id, (p) => { p.rotation = aimanterRotation(deg) })
}

/** [barre flottante] Rangs ↔ / ↕ : le sens des rangs. */
export function definirSens(etat, id, sens) {
  return surParcelle(etat, id, (p) => { p.sens = sens === SENS_TRAVERS ? SENS_TRAVERS : 'longueur' })
}

/** [E6] Le nombre de rangs ; le refus se dit par `erreurRangs`, la saisie reste en place. */
export function definirRangs(etat, id, valeur) {
  return surParcelle(etat, id, (p) => {
    const n = valeur === '' || valeur == null ? null : Math.round(Number(valeur))
    p.nbRangs = n != null && Number.isFinite(n) && n > 0 ? n : null
  })
}

/** [E4] Retirer du plan : la position s'efface, la parcelle reste et revient dans « À placer ». */
export function retirer(etat, id) {
  const apres = surParcelle(etat, id, (p) => { p.placee = false; p.x = null; p.y = null })
  return apres === etat ? etat : { ...apres, selection: null }
}

/** [CA5] Le nord : « Nord en haut du plan » ou toute autre des huit directions. */
export function orienter(etat, direction) {
  if (!DIRECTIONS.some((d) => d.id === direction)) return etat
  return modifier(etat, (b) => { b.potager.nord = direction; return b })
}

export const directionDuNord = (etat) => DIRECTIONS.find((d) => d.id === etat.potager.nord) || null

// ── Cotes, surface, rangs ────────────────────────────────────────────────────

/** [CA2] « aligné sur le potager » : la parcelle suit l'angle du plan. */
export const estAlignee = (p) => normaliserAngle(p.rotation) === 0

/** Les cotes affichées autour de la parcelle : « 12 m », « 5 m », « −2,5° · aligné sur le potager ». */
export function cotes(p, etat) {
  const angle = estAlignee(p) ? etat.potager.angle : p.rotation
  return {
    longueur: `${texteMetres(p.w)} m`,
    largeur: `${texteMetres(p.h)} m`,
    angle: `${texteAngle(angle)}${estAlignee(p) ? ' · aligné sur le potager' : ' · de travers'}`,
  }
}

/** La surface posée, au dixième. */
export const surfacePosee = (p) => arrondi(p.w * p.h, 1)

/**
 * [CA4] Le contrôle de cohérence : « Surface posée 60 m², fiche parcelle 69 m² ». Il propose d'aligner
 * la fiche, il ne le fait jamais seul. Rien quand la fiche est vide, alignée, ou déjà alignée ici.
 */
export function ecartSurface(p) {
  if (!p.placee || p.superficieFiche == null || p.alignerFiche) return null
  const posee = surfacePosee(p)
  if (Math.abs(posee - p.superficieFiche) <= 0.05) return null
  return {
    posee,
    fiche: p.superficieFiche,
    texte: `Surface posée ${texteMetres(posee)} m², fiche parcelle ${texteMetres(p.superficieFiche)} m²`,
    action: `Mettre la fiche à ${texteMetres(posee)} m²`,
  }
}

/** [CA4] « Mettre la fiche à 60 m² » : l'alignement est demandé, écrit à « Enregistrer ». */
export function alignerFiche(etat, id) {
  return surParcelle(etat, id, (p) => { p.alignerFiche = true })
}

/** [E6] Le refus de descendre sous les rangs occupés, avec son explication. */
export function erreurRangs(p) {
  if (p.nbRangs == null || p.nbRangs >= p.rangsOccupes) return null
  const s = p.rangsOccupes > 1 ? 's' : ''
  return `${p.rangsOccupes} rang${s} occupé${s} : on ne peut pas descendre à ${p.nbRangs}.`
}

/** « Enregistrer » est possible quand quelque chose a changé et que rien n'est refusé. */
export const erreurs = (etat) => etat.parcelles.map(erreurRangs).filter(Boolean)

// ── Enregistrer (E5, CA3) ────────────────────────────────────────────────────

/** [E5] Quelque chose a-t-il changé depuis le chargement ? */
export function modifie(etat) {
  return JSON.stringify({ parcelles: etat.parcelles, potager: etat.potager }) !== JSON.stringify(etat.origine)
}

/**
 * [CA3] La charge d'`POST /plan/edition` : les seules parcelles modifiées, avec les seuls champs qui ont
 * changé, et l'orientation du potager si elle l'a. `null` quand rien n'a changé.
 */
export function chargeEnregistrement(etat) {
  const parcelles = []
  for (const p of etat.parcelles) {
    const o = etat.origine.parcelles.find((q) => q.id === p.id)
    if (!o) continue
    const champs = {}
    if (p.placee !== o.placee || p.x !== o.x || p.y !== o.y) {
      champs.x_m = p.placee ? p.x : null
      champs.y_m = p.placee ? p.y : null
    }
    if (p.placee) {
      if (p.w !== o.w || !o.placee) champs.longueur_m = p.w   // une parcelle qu'on pose écrit toujours ses dimensions
      if (p.h !== o.h || !o.placee) champs.largeur_m = p.h
      if (p.rotation !== o.rotation) champs.rotation_deg = p.rotation
      if (p.sens !== o.sens) champs.sens_rangs = p.sens
    }
    if (p.nbRangs !== o.nbRangs) champs.nb_rangs = p.nbRangs
    if (p.alignerFiche) champs.aligner_superficie = true
    if (Object.keys(champs).length) parcelles.push({ id: p.id, ...champs })
  }
  const potager = {}
  if (etat.potager.nord !== etat.origine.potager.nord) potager.orientation_nord = etat.potager.nord
  if (etat.potager.angle !== etat.origine.potager.angle) potager.angle_deg = etat.potager.angle
  if (!parcelles.length && !Object.keys(potager).length) return null
  return { parcelles, ...(Object.keys(potager).length && { potager }) }
}

/** « Enregistrer » : 3 parcelles modifiées. */
export function resumeModifications(etat) {
  const charge = chargeEnregistrement(etat)
  if (!charge) return 'Aucune modification'
  const n = charge.parcelles.length
  return `${n} parcelle${n > 1 ? 's' : ''} modifiée${n > 1 ? 's' : ''}${charge.potager ? ' · orientation' : ''}`
}

// ── Formes nouvelles et duplication (E3 → US-332) ────────────────────────────

/** [E3] La demande à Gaston pour une forme posée sur le plan : rien n'existe avant « Confirmer ». */
export function demandeDeCreation(forme, x, y, etat, { longueur, largeur, sens = 'longueur', nbRangs } = {}) {
  const modele = FORMES_NOUVELLES.find((f) => f.id === forme) || FORMES_NOUVELLES[0]
  const L = longueur ?? modele.longueur
  const l = largeur ?? modele.largeur
  const plan = {
    action: 'creer', forme: modele.id, longueur_m: L, largeur_m: l,
    x_m: borne(aimanter(x), 0, POSITION_MAX_M), y_m: borne(aimanter(y), 0, POSITION_MAX_M),
    sens_rangs: sens,
    ...(nbRangs && { nb_rangs: nbRangs }),
  }
  return { phrase: `Créer ${modele.article} ${modele.libelle.toLowerCase()} de ${texteMetres(L)} × ${texteMetres(l)} m`, plan }
}

/** « Dupliquer » : une forme nouvelle de mêmes dimensions, posée un mètre plus loin — elle passe par Gaston. */
export function demandeDeDuplication(etat, id) {
  const p = parcelleDe(etat, id)
  if (!p?.placee) return null
  return demandeDeCreation(
    FORMES_NOUVELLES.some((f) => f.id === p.forme) ? p.forme : 'planche', p.x + 1, p.y + 1, etat,
    { longueur: p.w, largeur: p.h, sens: p.sens, nbRangs: p.nbRangs },
  )
}

// ── Droits et disponibilité ──────────────────────────────────────────────────

/** [CA7, E7] L'éditeur est proposé à un membre éditeur, sur un conteneur de 720 px et plus. */
export const peutModifierLePlan = (role, largeurConteneurPx) =>
  peutEnregistrer(role) && Number(largeurConteneurPx) >= LARGEUR_MIN_EDITEUR_PX

/** Le texte de la confirmation à la sortie quand quelque chose a changé (E5). */
export const TEXTE_ABANDON = 'Abandonner les modifications du plan ? Rien n’a été enregistré.'
