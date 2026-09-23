// [US-228 / CA3, A27] Culture → pictogramme, table de PRÉSENTATION isolée.
//
// Sur le modèle de l'ancienne `familles.js` : une table de correspondance que
// l'on peut compléter sans toucher au dessin, et dont l'absence n'empêche
// jamais le rendu — une culture inconnue retombe sur la forme neutre.
//
// La Vue plan utilise désormais les emoji de la maquette validée. Les anciennes
// silhouettes restent disponibles pour les autres consommateurs de cette API.
//
// Aucune agronomie ici : c'est une silhouette, pas une identification. Deux
// cultures peuvent partager la même — une courgette et un concombre sont deux
// formes allongées, et personne ne lit un rang en regardant sa silhouette : le
// nom est écrit à gauche, la quantité à droite.

/** Les huit silhouettes du jeu, plus la neutre. Le dessin vit dans le composant. */
export const PICTO_ROND = 'rond'
export const PICTO_LONG = 'long'
export const PICTO_RACINE = 'racine'
export const PICTO_FEUILLE = 'feuille'
export const PICTO_BULBE = 'bulbe'
export const PICTO_GOUSSE = 'gousse'
export const PICTO_COTELE = 'cotele'
export const PICTO_GRAPPE = 'grappe'
export const PICTO_NEUTRE = 'neutre'

/** Normalisation d'un nom de culture — sans accent, sans pluriel, en minuscules. */
function cle(nom) {
  return (nom || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase()
    .replace(/s$/, '')
}

/**
 * La table. Une entrée par culture courante ; le reste passe par les racines de
 * mots ci-dessous, et ce qui échappe aux deux prend la forme neutre.
 */
const TABLE = Object.freeze({
  tomate: PICTO_ROND, 'pomme de terre': PICTO_ROND, navet: PICTO_ROND,
  potiron: PICTO_COTELE, courge: PICTO_COTELE, patisson: PICTO_COTELE,
  courgette: PICTO_LONG, concombre: PICTO_LONG, aubergine: PICTO_LONG,
  poivron: PICTO_ROND, piment: PICTO_LONG, melon: PICTO_ROND, pasteque: PICTO_ROND,
  carotte: PICTO_RACINE, radi: PICTO_RACINE, betterave: PICTO_RACINE,
  panai: PICTO_RACINE, rutabaga: PICTO_RACINE, celeri: PICTO_RACINE,
  laitue: PICTO_FEUILLE, salade: PICTO_FEUILLE, mache: PICTO_FEUILLE,
  epinard: PICTO_FEUILLE, chou: PICTO_FEUILLE, blette: PICTO_FEUILLE,
  roquette: PICTO_FEUILLE, basilic: PICTO_FEUILLE, persil: PICTO_FEUILLE,
  oignon: PICTO_BULBE, ail: PICTO_BULBE, echalote: PICTO_BULBE,
  poireau: PICTO_BULBE, fenouil: PICTO_BULBE,
  haricot: PICTO_GOUSSE, poi: PICTO_GOUSSE, feve: PICTO_GOUSSE, lentille: PICTO_GOUSSE,
  fraise: PICTO_GRAPPE, framboise: PICTO_GRAPPE, groseille: PICTO_GRAPPE,
  cassi: PICTO_GRAPPE, rai: PICTO_GRAPPE,
})

/** Les mots qui suffisent à décider quand le nom complet n'est pas dans la table. */
const RACINES = Object.freeze([
  ['tomate', PICTO_ROND], ['courge', PICTO_COTELE], ['chou', PICTO_FEUILLE],
  ['haricot', PICTO_GOUSSE], ['oignon', PICTO_BULBE], ['salade', PICTO_FEUILLE],
])

/**
 * [CA3] La silhouette d'une culture, toujours définie : une culture absente de
 * la table prend la forme neutre — jamais de trou dans le dessin.
 */
export function pictoDeCulture(nom) {
  const k = cle(nom)
  if (!k) return PICTO_NEUTRE
  if (TABLE[k]) return TABLE[k]
  const racine = RACINES.find(([mot]) => k.includes(mot))
  return racine ? racine[1] : PICTO_NEUTRE
}

export default pictoDeCulture

const SYMBOLES = Object.freeze({
  tomate: '🍅', courgette: '🥒', concombre: '🥒',
  aubergine: '🍆', poivron: '🫑', potiron: '🎃', patisson: '🎃', courge: '🎃',
  carotte: '🥕', rutabaga: '🥔', 'pomme de terre': '🥔',
  laitue: '🥬', salade: '🥬', epinard: '🥬', mache: '🥬', chou: '🥬',
  oignon: '🧅', ail: '🧄', haricot: '🫘', poi: '🫛', fraise: '🍓',
})

export function symboleDeCulture(nom, variete = '') {
  const culture = cle(nom)
  const complet = `${culture} ${cle(variete)}`.trim()
  const correspondance = Object.keys(SYMBOLES).find(mot => complet === mot || complet.startsWith(`${mot} `))
  return correspondance ? SYMBOLES[correspondance] : '🌱'
}

export function estTomateAnanas(nom = '', variete = '') {
  const normaliser = texte => (texte || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase()
  const culture = normaliser(nom)
  return /^tomates?(?:\s|$)/.test(culture)
    && /(?:^|\s)ananas(?:\s|$)/.test(`${culture} ${normaliser(variete)}`)
}
