// [US-060] Règles d'affichage de l'écran Plan, isolées du rendu pour être
// vérifiables par `npm test` (`node --test`), sur le modèle de `pepiniere.js`.
// Aucune de ces fonctions ne connaît React : elles ne manipulent que la charge
// utile de `GET /plan`.

/**
 * [CA12] Code couleur d'occupation, inchangé depuis l'écran précédent : vert
 * sous 55 %, ambre de 55 à 79 %, rouge à partir de 80 %. Mêmes seuils que le
 * repli automatique de `ProgressBar`, qui colore donc la barre sans qu'on ait à
 * lui passer de teinte.
 */
export function occTint(pct) {
  return pct >= 80 ? 'red' : pct >= 55 ? 'amber' : 'brand'
}

/** Une parcelle sans superficie déclarée n'a pas de taux : elle se lit comme 0 %. */
export function pctDe(parcelle) {
  return parcelle?.occupation_pct ?? 0
}

/**
 * [CA6] Unités qui comptent réellement des plants. Une culture suivie en m² ou
 * en graines n'est jamais additionnée au total de plants de la parcelle, ni
 * convertie pour l'y faire entrer.
 */
const UNITES_PLANTS = new Set(['plant', 'plants', 'pied', 'pieds'])

export function estEnPlants(unite) {
  return UNITES_PLANTS.has((unite || '').trim().toLowerCase())
}

/**
 * [CA18] Unité telle qu'elle s'écrit à l'écran. Les événements dictés au bot
 * enregistrent la surface en `m2` (saisie vocale, clavier téléphone) ; la tuile
 * de culture affiche le symbole correct. C'est une **mise en forme**, pas une
 * conversion : la valeur et l'unité de saisie restent les mêmes.
 */
export function formatUnite(unite) {
  return (unite || '').trim().toLowerCase() === 'm2' ? 'm²' : unite
}

/**
 * [CA4] Exposition réellement affichable. Certaines parcelles portent la chaîne
 * « NULL » là où la valeur est en réalité absente (saisie ancienne) : la
 * pastille est alors omise, comme celle du type de sol, plutôt que d'afficher
 * « Exposition NULL » au jardinier.
 */
export function expositionAffichable(exposition) {
  const v = (exposition || '').trim()
  return v && !['null', 'none', 'aucune', '-'].includes(v.toLowerCase()) ? v : null
}

/** [CA6] Total de plants d'une parcelle — les autres unités n'y entrent pas. */
export function totalPlants(cultures = []) {
  return cultures.reduce((s, c) => s + (estEnPlants(c.unite) ? c.nb_plants || 0 : 0), 0)
}

/**
 * [CA10] Mois à mettre en évidence sur les frises — celui de la date de
 * référence de l'écran, jamais celui de l'horloge du navigateur. Rend
 * `undefined` sur une date absente ou illisible, ce qui laisse `MonthStrip`
 * retomber sur le mois courant.
 *
 * Découpage de la chaîne `AAAA-MM-JJ` plutôt que `new Date(...)` : la forme
 * courte est interprétée en UTC par le moteur JS, ce qui décale d'un mois une
 * date du 1er ou du 31 selon le fuseau du poste.
 */
export function moisDeLaDate(iso) {
  if (!iso) return undefined
  const mois = Number(String(iso).split('-')[1])
  return Number.isInteger(mois) && mois >= 1 && mois <= 12 ? mois - 1 : undefined
}

/**
 * [CA16] Filtre culture, conservé d'US-031 : il porte à la fois sur le nom de
 * la parcelle et sur les cultures et variétés qu'elle contient. Une parcelle
 * retenue par son **nom** garde toutes ses cultures ; une parcelle retenue par
 * une de ses cultures ne montre que celles qui correspondent.
 */
export function filtrerParcelles(parcelles = [], recherche = '') {
  const q = (recherche || '').trim().toLowerCase()
  if (!q) return parcelles

  return parcelles
    .map((p) => {
      if (p.nom.toLowerCase().includes(q)) return p
      return {
        ...p,
        cultures: p.cultures.filter(
          (c) =>
            (c.culture || '').toLowerCase().includes(q) ||
            (c.variete || '').toLowerCase().includes(q),
        ),
      }
    })
    .filter((p) => p.nom.toLowerCase().includes(q) || p.cultures.length > 0)
}

/**
 * [CA1/CA16] Parcelle affichée dans le panneau de détail : celle qui est
 * sélectionnée si elle figure encore dans la liste, la première sinon.
 *
 * Calculé à chaque rendu plutôt que corrigé après coup : quand le filtre exclut
 * la parcelle sélectionnée, le détail bascule sur la première encore listée sans
 * passer par un état transitoire où l'écran n'affiche rien.
 */
export function parcelleSelectionnee(parcelles = [], selId) {
  return parcelles.find((p) => p.id === selId) ?? parcelles[0] ?? null
}
