// Familles botaniques — table de correspondance portée depuis `FAM_OF`
// (`web-tokens.jsx` de la maquette 2026), qui groupe ses écrans par famille.
//
// PROVISOIRE, et c'est le maillon faible du regroupement : la famille botanique
// n'existe nulle part côté serveur. `CultureConfig` ne porte aucune métadonnée
// horticole aujourd'hui.
//
// **Ce fichier est destiné à être supprimé par US-067**
// (`backlog/US-067_famille-botanique-culture-config.md`), qui déplace la famille
// dans `culture_config` — pré-remplie et corrigeable depuis le bot. Ne pas y
// ajouter d'entrée sans se demander si la donnée n'a pas déjà sa place en base.
//
// Le rapprochement est un **appariement exact** sur le nom de culture normalisé :
// une culture absente de la table tombe dans « Autres » plutôt que de faire
// échouer le regroupement, et un nom composé (« petit pois », « haricot
// grimpant ») ne trouve pas son genre. C'est assumé tant que la donnée n'est pas
// en base — mieux vaut un groupe « Autres » visible qu'un classement deviné.

const FAMILLES = {
  tomate: 'Solanacée', aubergine: 'Solanacée', poivron: 'Solanacée', piment: 'Solanacée',
  'pomme de terre': 'Solanacée',
  courgette: 'Cucurbitacée', courge: 'Cucurbitacée', butternut: 'Cucurbitacée',
  potiron: 'Cucurbitacée', potimarron: 'Cucurbitacée', concombre: 'Cucurbitacée',
  cornichon: 'Cucurbitacée', melon: 'Cucurbitacée', pasteque: 'Cucurbitacée',
  oignon: 'Alliacée', echalote: 'Alliacée', ail: 'Alliacée', poireau: 'Alliacée',
  ciboulette: 'Alliacée',
  betterave: 'Chénopodiacée', blette: 'Chénopodiacée', epinard: 'Chénopodiacée',
  basilic: 'Lamiacée', menthe: 'Lamiacée', thym: 'Lamiacée', romarin: 'Lamiacée',
  fraise: 'Rosacée', framboise: 'Rosacée',
  carotte: 'Apiacée', persil: 'Apiacée', celeri: 'Apiacée', panais: 'Apiacée', fenouil: 'Apiacée',
  chou: 'Brassicacée', radis: 'Brassicacée', navet: 'Brassicacée', roquette: 'Brassicacée',
  salade: 'Astéracée', laitue: 'Astéracée', mache: 'Astéracée', artichaut: 'Astéracée',
  haricot: 'Fabacée', pois: 'Fabacée', feve: 'Fabacée',
  mais: 'Poacée',
}

/**
 * Minuscules sans accent, pour retrouver « Céleri » comme `celeri`.
 *
 * `\p{Diacritic}` plutôt qu'une plage `U+0300–U+036F` écrite en clair : cette
 * plage ne contient que des caractères combinants, invisibles dans le fichier
 * source et corrompus au moindre ré-encodage.
 */
const normalise = (s) =>
  (s || '').trim().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')

export function familleDe(culture) {
  return FAMILLES[normalise(culture)] || 'Autres'
}

export default familleDe
