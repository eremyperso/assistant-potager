// Calendrier cultural standard — table de correspondance **provisoire** portée
// côté interface, sur le modèle de `familles.js` [US-060, CA8 à CA11].
//
// Ce que cette table est : les fenêtres **conseillées génériques** d'une culture
// — semis, plantation, récolte — et sa durée de culture indicative. Ce sont des
// valeurs standard, identiques pour tout le monde.
//
// Ce qu'elle n'est pas, et ne doit jamais devenir :
//   - un calendrier **réel** recalé sur les événements de la parcelle ;
//   - un calendrier **local**, tenant compte de la zone climatique du potager ;
//   - un référentiel **corrigeable** par le jardinier ;
//   - une distinction semis en pépinière / semis en pleine terre.
// Ces quatre points relèvent en totalité de `docs/EPIC_CALENDRIER_CULTURAL.md`
// (US-068 référentiel, US-069 contexte de semis, US-070 recalage sur le réel).
//
// **Ce fichier est destiné à être supprimé par US-068**, qui déplace le
// référentiel en base. Ne pas y ajouter d'entrée sans se demander si la donnée
// n'a pas déjà sa place côté serveur.
//
// Origine des valeurs : les dix cultures de `WCULTURES` (`web-tokens.jsx` de la
// maquette 2026) sont reprises **à l'identique** ; les autres suivent les
// calendriers de semis courants pour la France métropolitaine, sur le même
// vocabulaire de cultures que `familles.js` pour que les deux tables se
// répondent. Une culture absente d'ici s'affiche en mode dégradé — frise neutre,
// famille et durée en tiret : **aucune valeur horticole n'est inventée à la
// volée** (CA9).

/** Index de mois 0-based (0 = janvier), comme `Date.getMonth()` et `MonthStrip`. */
const CALENDRIER = {
  // ── Les dix cultures de la maquette, valeurs reprises telles quelles ──
  tomate: { duree: '70-90 j', semis: [2, 3], plant: [4, 5], rec: [6, 7, 8, 9] },
  courgette: { duree: '50-60 j', semis: [3, 4], plant: [4, 5], rec: [5, 6, 7, 8, 9] },
  oignon: { duree: '120-150 j', semis: [1, 2], plant: [2, 3], rec: [6, 7] },
  betterave: { duree: '90-110 j', semis: [3, 4, 5], plant: [], rec: [7, 8, 9] },
  basilic: { duree: '60-70 j', semis: [3, 4], plant: [4, 5], rec: [6, 7, 8, 9] },
  butternut: { duree: '110-130 j', semis: [3, 4], plant: [5], rec: [8, 9] },
  fraise: { duree: 'vivace', semis: [], plant: [7, 8], rec: [4, 5] },
  concombre: { duree: '55-70 j', semis: [3], plant: [4, 5], rec: [6, 7, 8] },
  aubergine: { duree: '100-120 j', semis: [1, 2], plant: [4], rec: [7, 8, 9] },
  blette: { duree: '60-80 j', semis: [3, 4], plant: [4, 5], rec: [6, 7, 8, 9] },

  // ── Solanacées ──
  poivron: { duree: '100-120 j', semis: [1, 2], plant: [4], rec: [6, 7, 8, 9] },
  piment: { duree: '100-120 j', semis: [1, 2], plant: [4], rec: [6, 7, 8, 9] },
  'pomme de terre': { duree: '90-120 j', semis: [], plant: [2, 3, 4], rec: [6, 7, 8] },

  // ── Cucurbitacées ──
  courge: { duree: '110-130 j', semis: [3, 4], plant: [4, 5], rec: [8, 9] },
  potiron: { duree: '110-130 j', semis: [3, 4], plant: [4, 5], rec: [8, 9] },
  potimarron: { duree: '100-120 j', semis: [3, 4], plant: [4, 5], rec: [7, 8, 9] },
  cornichon: { duree: '55-70 j', semis: [3, 4], plant: [4, 5], rec: [6, 7, 8] },
  melon: { duree: '100-120 j', semis: [2, 3], plant: [4], rec: [6, 7, 8] },
  pasteque: { duree: '110-130 j', semis: [2, 3], plant: [4], rec: [7, 8] },

  // ── Alliacées ──
  echalote: { duree: '120-150 j', semis: [], plant: [1, 2], rec: [5, 6] },
  ail: { duree: '180-240 j', semis: [], plant: [1, 9, 10], rec: [5, 6] },
  poireau: { duree: '150-180 j', semis: [1, 2, 3], plant: [4, 5, 6], rec: [8, 9, 10, 11] },
  ciboulette: { duree: 'vivace', semis: [2, 3], plant: [3, 4], rec: [3, 4, 5, 6, 7, 8, 9] },

  // ── Chénopodiacées ──
  epinard: { duree: '40-60 j', semis: [2, 3, 7, 8], plant: [], rec: [4, 5, 9, 10] },

  // ── Lamiacées ──
  menthe: { duree: 'vivace', semis: [3, 4], plant: [3, 4], rec: [4, 5, 6, 7, 8, 9] },
  thym: { duree: 'vivace', semis: [3, 4], plant: [3, 4], rec: [3, 4, 5, 6, 7, 8, 9] },
  romarin: { duree: 'vivace', semis: [3, 4], plant: [3, 4], rec: [3, 4, 5, 6, 7, 8, 9] },

  // ── Rosacées ──
  framboise: { duree: 'vivace', semis: [], plant: [9, 10, 1], rec: [5, 6, 7, 8] },

  // ── Apiacées ──
  carotte: { duree: '70-120 j', semis: [2, 3, 4, 5, 6], plant: [], rec: [5, 6, 7, 8, 9, 10] },
  persil: { duree: '70-90 j', semis: [2, 3, 4, 5], plant: [], rec: [5, 6, 7, 8, 9, 10] },
  celeri: { duree: '120-150 j', semis: [1, 2], plant: [4, 5], rec: [8, 9, 10] },
  panais: { duree: '150-180 j', semis: [2, 3, 4], plant: [], rec: [9, 10, 11] },
  fenouil: { duree: '90-110 j', semis: [4, 5, 6], plant: [5, 6], rec: [7, 8, 9] },

  // ── Brassicacées ──
  chou: { duree: '90-150 j', semis: [3, 4, 5], plant: [5, 6], rec: [8, 9, 10, 11] },
  radis: { duree: '25-35 j', semis: [2, 3, 4, 5, 6, 7, 8], plant: [], rec: [3, 4, 5, 6, 7, 8, 9] },
  navet: { duree: '60-80 j', semis: [2, 3, 7, 8], plant: [], rec: [5, 6, 9, 10] },
  roquette: { duree: '30-45 j', semis: [2, 3, 4, 7, 8], plant: [], rec: [4, 5, 6, 9, 10] },

  // ── Astéracées ──
  salade: { duree: '45-70 j', semis: [1, 2, 3, 4, 5, 6, 7], plant: [3, 4, 5, 6, 7, 8], rec: [4, 5, 6, 7, 8, 9, 10] },
  laitue: { duree: '45-70 j', semis: [1, 2, 3, 4, 5, 6, 7], plant: [3, 4, 5, 6, 7, 8], rec: [4, 5, 6, 7, 8, 9, 10] },
  mache: { duree: '60-90 j', semis: [7, 8, 9], plant: [], rec: [9, 10, 11, 0, 1] },
  artichaut: { duree: 'vivace', semis: [], plant: [3, 4], rec: [5, 6, 8, 9] },

  // ── Fabacées ──
  haricot: { duree: '55-75 j', semis: [4, 5, 6], plant: [], rec: [6, 7, 8, 9] },
  pois: { duree: '80-100 j', semis: [1, 2, 3], plant: [], rec: [4, 5, 6] },
  feve: { duree: '120-150 j', semis: [1, 9, 10], plant: [], rec: [4, 5] },

  // ── Poacées ──
  mais: { duree: '90-120 j', semis: [3, 4], plant: [4, 5], rec: [7, 8] },
}

/**
 * Minuscules sans accent, pour retrouver « Céleri » comme `celeri`.
 *
 * Volontairement dupliqué de `familles.js` plutôt qu'importé : ce fichier-là
 * disparaît avec US-067 et celui-ci avec US-068, à des moments différents — une
 * dépendance entre les deux ferait tomber le calendrier le jour où la famille
 * passe en base.
 */
const normalise = (s) =>
  (s || '').trim().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')

/**
 * Fenêtres conseillées standard d'une culture, ou `null` si elle est absente de
 * la table — le `null` est significatif : c'est lui qui déclenche l'affichage
 * dégradé du CA9 (frise neutre, famille et durée en tiret).
 *
 * Le rapprochement est un **appariement exact** sur le nom normalisé, comme
 * `familleDe` : « petit pois » ou « haricot grimpant » ne trouvent pas leur
 * genre, et c'est assumé tant que la donnée n'est pas en base.
 */
export function calendrierDe(culture) {
  return CALENDRIER[normalise(culture)] || null
}

export default calendrierDe
