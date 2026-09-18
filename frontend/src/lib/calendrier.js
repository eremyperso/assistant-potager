// [US-176] Calendrier cultural de l'écran Plan — lecture de `GET /plan/calendriers`.
//
// Ce fichier portait jusqu'ici une **table provisoire** de fenêtres « semis /
// plantation / récolte », identique pour tous les potagers (US-060, CA8 à CA11).
// Elle devait disparaître « avec US-068 » ; US-068 n'ayant créé aucun écran,
// c'est **US-176 qui l'a soldée** : plus aucune valeur horticole n'est embarquée
// dans l'interface. Tout vient du référentiel serveur, lu pour le potager
// consulté — sa zone climatique, ses corrections faites au bot.
//
// Ce qui reste ici n'est qu'une mise en forme, sans aucune donnée :
//   - la liste des cultures à demander en UNE lecture groupée (CA11) ;
//   - la conversion des mois 1..12 du serveur en index 0-based de `MonthStrip` ;
//   - le mode dégradé (CA6, CA12) : frise neutre et durée en tiret, jamais une
//     valeur de repli.
//
// [US-070] Le recalage sur les événements réels de la parcelle est projeté par
// le serveur (`projections`) ; sa mise en forme vit en fin de fichier.

export const TIRET = '—'

/** Cultures distinctes de l'écran, dans l'ordre d'apparition — la requête groupée. */
export function culturesDuPlan(parcelles) {
  const vues = new Set()
  for (const p of parcelles || []) {
    for (const c of p.cultures || []) {
      if (c.culture) vues.add(c.culture)
    }
  }
  return [...vues]
}

/** Mois 1..12 du référentiel → index 0-based ; une valeur hors bornes est ignorée. */
const versIndex = (mois) =>
  (mois || []).filter((m) => Number.isInteger(m) && m >= 1 && m <= 12).map((m) => m - 1)

/**
 * [US-176 / CA3, CA3bis] Les quatre phases du référentiel (US-068), dans l'ordre
 * du geste — et l'UNIQUE endroit où leur teinte et leur libellé sont écrits :
 * la légende, la frise et son libellé accessible en dérivent.
 *
 * `serveur` est la clé de `mois` dans `GET /plan/calendriers`
 * (`calendrier_cultural.PHASES`), `cle` celle de la frise côté interface.
 *
 * ⚠️ `bg-brand-soft` n'est porté par AUCUNE phase : il est réservé à l'état
 * « en croissance » d'US-070 / CA7, qui se lit entre deux phases et ne doit se
 * confondre avec aucune.
 */
export const PHASES_REFERENTIEL = Object.freeze([
  Object.freeze({ cle: 'pepiniere', serveur: 'semis_pepiniere', libelle: 'Semis en pépinière', teinte: 'bg-blue' }),
  Object.freeze({ cle: 'pleineTerre', serveur: 'semis_pleine_terre', libelle: 'Semis en pleine terre', teinte: 'bg-violet' }),
  Object.freeze({ cle: 'plantation', serveur: 'plantation', libelle: 'Plantation', teinte: 'bg-brand' }),
  Object.freeze({ cle: 'rec', serveur: 'recolte', libelle: 'Récolte', teinte: 'bg-amber' }),
])

/** [US-070 / CA7] Teinte réservée à « en croissance » — aucune phase ne la prend. */
export const TEINTE_EN_CROISSANCE_RESERVEE = 'bg-brand-soft'

/**
 * [US-070 / CA7] L'état « en croissance » d'une frise RECALÉE : entre la levée
 * et la première récolte attendue. Ce n'est pas une phase du référentiel — il
 * n'existe que devant une culture en place — et il passe APRÈS toutes les
 * phases dans la règle de priorité : le serveur ne le fait de toute façon
 * chevaucher aucun geste.
 */
export const ETAT_CROISSANCE = Object.freeze({
  cle: 'croissance', serveur: 'croissance', libelle: 'En croissance', teinte: TEINTE_EN_CROISSANCE_RESERVEE,
})

/**
 * [US-176 / CA3bis] Règle de priorité DÉCLARÉE, quand deux phases tombent le
 * même mois (semis en pleine terre et plantation du concombre en mai) : le geste
 * le plus AVANCÉ l'emporte — récolte, puis plantation, puis semis en pleine
 * terre, puis semis en pépinière. C'est la règle historique de la frise
 * (« récolte prioritaire ») prolongée aux quatre phases. La phase écartée n'est
 * pas perdue pour autant : `phasesDuMois` la nomme dans le libellé du mois.
 */
export const PRIORITE_PHASES = Object.freeze(['rec', 'plantation', 'pleineTerre', 'pepiniere'])

/** Frise neutre : aucune fenêtre, durée en tiret, aucun itinéraire nommé. */
export const FRISE_DEGRADEE = Object.freeze({
  pepiniere: [], pleineTerre: [], plantation: [], rec: [], duree: TIRET, itineraire: null, degrade: true,
})

/**
 * [CA1, CA3-CA6, CA12] Ce que la tuile d'une culture affiche.
 *
 * `calendriers` est la réponse de `GET /plan/calendriers`, ou `null` quand sa
 * lecture a échoué : dans ce cas, comme pour une culture absente ou sans
 * fenêtre pour la zone, la frise est neutre — aucune valeur n'est empruntée.
 * `itineraire` n'est renseigné que s'il n'est pas « standard » (CA5).
 */
export function friseDeCulture(calendriers, culture) {
  const entree = calendriers?.cultures?.[culture]
  if (!entree) return FRISE_DEGRADEE
  const mois = entree.mois || {}
  // [CA3] La plantation est LUE (`mois.plantation`), jamais reconstituée du
  // semis en pépinière et du délai de repiquage : absente, elle reste vide.
  const phases = Object.fromEntries(
    PHASES_REFERENTIEL.map(({ cle, serveur }) => [cle, versIndex(mois[serveur])]),
  )
  return {
    ...phases,
    duree: entree.duree_recolte || TIRET,
    itineraire: entree.itineraire && !entree.itineraire_standard ? entree.itineraire : null,
    degrade: PHASES_REFERENTIEL.every(({ cle }) => phases[cle].length === 0),
  }
}

/**
 * [US-176 / CA3bis] Libellés de TOUTES les phases d'un mois (index 0-based),
 * dans l'ordre du geste — y compris celles que la règle de priorité n'a pas
 * peintes : un mois ne perd jamais une phase en silence.
 */
export function phasesDuMois(frise, i) {
  return [...PHASES_REFERENTIEL, ETAT_CROISSANCE]
    .filter(({ cle }) => (frise?.[cle] || []).includes(i)).map((p) => p.libelle)
}

// ── [US-070] Calendrier recalé sur les événements réels ─────────────────────
//
// Le serveur projette (`projections` de `GET /plan/calendriers`) ; ici, rien que
// de la mise en forme. Le vocabulaire reste au CONDITIONNEL — « attendue » — et
// une fourchette reste une fourchette : aucune date unique n'est fabriquée.

export const MOIS_NOMS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

const minuscule = (v) => (v || '').trim().toLowerCase()

/**
 * [US-070 / CA1] Projection d'une tuile du Plan (parcelle × culture × variété),
 * ou `null` : même clé que le regroupement de l'occupation côté serveur.
 */
export function projectionDeTuile(calendriers, parcelleId, culture, variete) {
  return (calendriers?.projections || []).find((p) =>
    p.parcelle_id === parcelleId
    && minuscule(p.culture) === minuscule(culture)
    && minuscule(p.variete) === minuscule(variete),
  ) || null
}

/**
 * [US-070 / CA7, CA11] Frise recalée, dans la forme de `friseDeCulture` plus
 * `croissance` — ou `null` quand la projection n'a pas pu recaler : la tuile
 * garde alors la frise conseillée (plantation comprise), jamais une frise vide
 * inventée.
 */
export function friseRecalee(projection) {
  const mois = projection?.mois
  if (!mois) return null
  return {
    ...Object.fromEntries(
      [...PHASES_REFERENTIEL, ETAT_CROISSANCE].map(({ cle, serveur }) => [cle, versIndex(mois[serveur])]),
    ),
    degrade: false,
  }
}

/** « 2026-07-16 » → « 16 juillet » — sans fuseau : la date du serveur est un jour. */
export function jourLisible(iso) {
  const [, m, j] = String(iso || '').split('-').map(Number)
  if (!m || !j || m < 1 || m > 12) return ''
  return `${j === 1 ? '1er' : j} ${MOIS_NOMS[m - 1]}`
}

/** Une fourchette de dates, jamais présentée comme une date certaine (CA3). */
function plageLisible(plage) {
  if (!plage) return null
  return plage.debut === plage.fin
    ? `vers le ${jourLisible(plage.debut)}`
    : `entre le ${jourLisible(plage.debut)} et le ${jourLisible(plage.fin)}`
}

const jours = (n) => `${n} jour${n > 1 ? 's' : ''}`

/**
 * [US-070 / CA3, CA5, CA12] Où en est la culture, en une ligne : remplace la
 * durée conseillée de la tuile. `null` sans recalage — la durée du référentiel
 * reste affichée (CA11).
 */
export function resteLisible(projection) {
  if (!projection || projection.etat === 'sans_recalage') return null
  const { etat, jours_restants: r, recolte_reelle: reelle, retard_jours: retard } = projection
  if (etat === 'en_recolte') return `en récolte depuis le ${jourLisible(reelle?.premiere)}`
  if (etat === 'recolte_depassee') {
    return `récolte attendue il y a ${jours(retard)}, aucune récolte notée`
  }
  if (!r) return null
  if (etat === 'recolte_attendue') {
    return r.max > 0 ? `récolte attendue d'ici ${jours(r.max)}` : 'récolte attendue dès maintenant'
  }
  return r.min === r.max
    ? `récolte attendue dans ${jours(r.min)}`
    : `récolte attendue dans ${r.min} à ${jours(r.max)}`
}

/**
 * [US-070 / CA1, CA2, CA4, CA9, CA10] Repères de la tuile, dans l'ordre du
 * cycle : origine réelle, plantation, levée et récolte attendues, séries
 * suivantes, prochaine plage de semis. Rien pour ce qui n'est pas connu.
 */
export function reperesLisibles(projection) {
  if (!projection?.origine) return []
  const p = projection
  const reperes = []
  const filiere = { pepiniere: ' en pépinière', pleine_terre: ' en pleine terre' }[p.origine.contexte] || ''
  if (p.origine.action === 'semis') reperes.push(`semé le ${jourLisible(p.origine.date)}${filiere}`)
  if (p.plantation_reelle) reperes.push(`planté le ${jourLisible(p.plantation_reelle)}`)
  if (p.etat !== 'sans_recalage') {
    if (p.levee_attendue && p.etat === 'a_venir') reperes.push(`levée attendue ${plageLisible(p.levee_attendue)}`)
    if (p.recolte_attendue && p.etat !== 'en_recolte') {
      reperes.push(`1re récolte attendue ${plageLisible(p.recolte_attendue)}`)
    }
  }
  if (p.series_suivantes > 0) {
    // « autre », pas « plus récente » : deux semis du même jour sont deux séries.
    reperes.push(p.series_suivantes === 1 ? 'une autre série en place' : `${p.series_suivantes} autres séries en place`)
  }
  if (p.prochaine_plage_semis) reperes.push(`semis encore possible : ${p.prochaine_plage_semis.affichage}`)
  return reperes
}

/**
 * [CA8] Libellé de la zone lue par le potager et de son origine, une seule fois
 * pour l'écran — `null` quand le calendrier n'a pas pu être lu.
 */
export function zoneAffichable(calendriers) {
  if (!calendriers?.zone_climatique) return null
  const origines = {
    jardinier: 'choisie pour ce potager',
    localisation: 'déduite de la localisation',
    defaut: 'appliquée par défaut',
  }
  const noms = { oceanique: 'océanique', mediterraneen: 'méditerranéen' }
  let origine = origines[calendriers.zone_climatique_origine] || null
  // [US-193 / CA7, CA8] Même libellé que le bot : l'altitude retenue accompagne
  // une zone déduite de la localisation (« 1 326 m »).
  if (calendriers.zone_climatique_origine === 'localisation' && typeof calendriers.zone_altitude === 'number') {
    const metres = String(Math.round(calendriers.zone_altitude)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
    origine = `${origine}, ${metres} m`
  }
  return {
    zone: noms[calendriers.zone_climatique] || calendriers.zone_climatique,
    origine,
  }
}

/** [CA9] Attributions des valeurs affichées, dédoublonnées — une ligne pour l'écran. */
export function attributionsAffichables(calendriers) {
  return [...new Set((calendriers?.attributions || []).filter(Boolean))]
}

/**
 * [US-060, US-176 / CA14] Teinte d'un mois (index 0-based) de la frise
 * HISTORIQUE (`semis` / `plant` / `rec`), récolte prioritaire — inchangée pour
 * les autres écrans et l'aperçu du design system.
 */
export function couleurDuMois({ semis = [], plant = [], rec = [] }) {
  return (i) => {
    if (rec.includes(i)) return 'bg-amber'
    if (plant.includes(i)) return 'bg-brand'
    if (semis.includes(i)) return 'bg-blue'
    return 'bg-card-alt'
  }
}

/**
 * [US-176 / CA3bis] Teinte d'un mois de la frise du RÉFÉRENTIEL : la phase la
 * mieux placée dans `PRIORITE_PHASES`, lue dans `PHASES_REFERENTIEL`.
 */
export function couleurDuMoisReferentiel(frise) {
  const teintes = Object.fromEntries(PHASES_REFERENTIEL.map(({ cle, teinte }) => [cle, teinte]))
  return (i) => {
    const gagnante = PRIORITE_PHASES.find((cle) => (frise?.[cle] || []).includes(i))
    if (gagnante) return teintes[gagnante]
    // [US-070 / CA7] « En croissance » ne passe qu'après toutes les phases.
    return (frise?.croissance || []).includes(i) ? ETAT_CROISSANCE.teinte : 'bg-card-alt'
  }
}
