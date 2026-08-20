// [US-063] Composition de la phrase d'un événement du journal.
//
// La maquette affiche une phrase toute faite (« Récolte de 1,2 kg de courgettes »)
// et une heure. Le modèle réel n'a ni l'une ni l'autre : `Evenement` stocke des
// champs séparés, et l'heure n'existe nulle part — `parse_date()` tronque à
// `%Y-%m-%d`, `GET /historique` re-tronque via `str(e.date)[:10]`. La phrase est
// donc reconstruite ici selon le patron :
//
//     <action> de <quantité> <unité> <nb_plants_godets> de <culture> <variété>
//
// Chaque segment absent de la donnée est omis, jamais comblé : « Arrosage » tout
// court est une phrase valide, « Arrosage de — de — » n'en serait pas une.
//
// Isolé dans `lib/` plutôt que dans la vue pour être testable sans rendu React
// (`npm test`, `node --test`) — même parti pris que `lib/plan.js` (US-060).

/** Libellés au SINGULIER — les libellés de catégorie du filtre sont au pluriel
 *  (« Récoltes »), ce qui ne se dit pas dans une phrase d'événement. Couvre les
 *  16 `ACTIONS_VALIDES` de `utils/validation.py`, pas seulement les types
 *  filtrables : le journal restitue tout ce qui a été enregistré. */
export const ACTION_LABEL = {
  recolte: 'Récolte',
  semis: 'Semis',
  plantation: 'Plantation',
  repiquage: 'Repiquage',
  mise_en_godet: 'Mise en godet',
  arrosage: 'Arrosage',
  desherbage: 'Désherbage',
  paillage: 'Paillage',
  fertilisation: 'Fertilisation',
  traitement: 'Traitement',
  taille: 'Taille',
  tuteurage: 'Tuteurage',
  perte: 'Perte',
  perte_godet: 'Perte de godets',
  vendu: 'Vente',
  observation: 'Note',
}

/** Libellé d'une action, y compris pour un type jamais rencontré (repli neutre). */
export function libelleAction(typeAction) {
  if (ACTION_LABEL[typeAction]) return ACTION_LABEL[typeAction]
  const brut = (typeAction || '').replace(/_/g, ' ').trim()
  return brut ? brut.charAt(0).toUpperCase() + brut.slice(1) : 'Action'
}

const fmtQuantite = (v) => String(v).replace('.', ',')

/** Élision « de » → « d' » devant une voyelle. Le « h » est laissé de côté :
 *  il est aspiré dans la plupart des noms de cultures (haricot → « de haricot »). */
function avecDe(mot) {
  return /^[aeiouyàâäéèêëîïôöûü]/i.test(mot) ? `d'${mot}` : `de ${mot}`
}

/**
 * Phrase lisible d'un événement, à partir des champs renvoyés par `/historique`.
 *
 * `nb_plants_godets` est un segment à part entière et non un repli de `quantite` :
 * une mise en godet ne renseigne pas `quantite` (cf. `creer_evenement_godet`), son
 * compte réel ne vit que dans ce champ. Sans lui, tous les lots godet
 * s'affichaient sans la moindre quantité.
 */
export function phraseEvenement(e) {
  const segments = [libelleAction(e.type_action)]

  const quantites = []
  if (e.quantite != null) {
    quantites.push(`${fmtQuantite(e.quantite)}${e.unite ? ` ${e.unite}` : ''}`)
  }
  if (e.nb_plants_godets != null) {
    quantites.push(`${e.nb_plants_godets} godet${e.nb_plants_godets > 1 ? 's' : ''}`)
  }
  if (quantites.length) segments.push(avecDe(quantites.join(' ')))

  if (e.culture) {
    // Culture en minuscule (elle est stockée capitalisée) pour qu'elle se fonde
    // dans la phrase ; la variété garde sa casse d'origine — c'est un nom propre
    // (« Cœur de bœuf »), pas un mot de la phrase.
    const culture = [e.culture.toLowerCase(), e.variete].filter(Boolean).join(' ')
    segments.push(avecDe(culture))
  }

  return segments.join(' ')
}

/** Libellé du bandeau de journée : « Aujourd'hui · 18 août », « Hier · 17 août »,
 *  sinon « Mardi 12 août ». `aujourdhui` est injectable pour rendre le test
 *  indépendant de la date d'exécution. */
export function libelleJour(iso, aujourdhui = new Date()) {
  const d = new Date(`${iso}T00:00:00`)
  const today = new Date(aujourdhui)
  today.setHours(0, 0, 0, 0)
  const hier = new Date(today)
  hier.setDate(hier.getDate() - 1)

  const court = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long' }).format(d)
  if (d.toDateString() === today.toDateString()) return `Aujourd'hui · ${court}`
  if (d.toDateString() === hier.toDateString()) return `Hier · ${court}`

  const jour = new Intl.DateTimeFormat('fr-FR', { weekday: 'long' }).format(d)
  return `${jour.charAt(0).toUpperCase()}${jour.slice(1)} ${court}`
}

/** Regroupe les événements consécutifs d'une même journée. L'API renvoyant déjà
 *  la page triée par date décroissante, un simple parcours suffit — aucun tri ni
 *  appel serveur supplémentaire (le regroupement est un habillage de la page). */
export function grouperParJour(evenements, aujourdhui = new Date()) {
  const groupes = []
  for (const e of evenements) {
    const label = libelleJour(e.date, aujourdhui)
    const dernier = groupes[groupes.length - 1]
    if (dernier && dernier.label === label) dernier.items.push(e)
    else groupes.push({ label, items: [e] })
  }
  return groupes
}
