// [US-216] La fiche d'un lot — règles d'affichage, sans React.
//
// Le composant `FicheLot` ne décide de rien : il lit ce que ce module calcule.
// Quels gestes pour quel état du lot, quelles quantités proposées, quel taux et
// quelle comparaison à la moyenne : tout est ici, vérifiable par `npm test`
// (CA15).
//
// Trois règles tiennent tout l'écran :
//   * **Aucune écriture.** Un geste est PRÉPARÉ (`BoutonGeste`, US-196/US-224) et
//     confirmé au compagnon. Le compteur de levée est une aide à la saisie.
//   * **Sans donnée, pas de valeur** (RT2) : un tiret veut dire « aucun geste de
//     ce type », jamais zéro ; une échéance incalculable dit pourquoi.
//   * **Rien n'est recalculé** : échéances, action suggérée et dormance viennent
//     de l'API (US-214), recopiées telles quelles.

/**
 * [CA8, CA10] Le geste de levée (US-212) n'existe pas encore côté serveur : tant
 * qu'il n'est pas livré, la fiche ne propose ni « Noter la levée » ni le compteur.
 * US-212 passe cette constante à `true` — et ajoute `levee` aux gestes ouverts
 * (`file_gestes.GESTES_OUVERTS_PWA`) dans la même livraison.
 */
export const LEVEE_DISPONIBLE = false

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

/** « 2026-09-01 » → « 1er septembre » (jamais d'année : la fiche parle de la saison en cours). */
export function dateEnClair(iso) {
  if (!iso) return null
  const [y, m, j] = String(iso).slice(0, 10).split('-').map(Number)
  if (!y || !m || !j) return null
  return `${j === 1 ? '1er' : j} ${MOIS[m - 1]}`
}

/** « entre le 11 et le 13 septembre » — « le 11 septembre » pour un seul jour. */
export function periodeEnClair(du, au) {
  const a = dateEnClair(du)
  const b = dateEnClair(au)
  if (!a || !b) return null
  if (du === au) return `le ${a}`
  const [, m1] = du.slice(0, 10).split('-').map(Number)
  const [, m2, j2] = au.slice(0, 10).split('-').map(Number)
  const [, , j1] = du.slice(0, 10).split('-').map(Number)
  const debut = m1 === m2 ? `${j1 === 1 ? '1er' : j1}` : a
  return `entre le ${debut} et le ${j2 === 1 ? '1er' : j2} ${MOIS[m2 - 1]}`
}

const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`

/**
 * [CA3] « 18 j » depuis le semis — `null` si le lot n'a pas de date de semis.
 * La date de référence est celle de l'API (`echeances.date_reference`), pas l'horloge :
 * la fiche et la liste disent la même chose le même jour.
 */
export function joursDepuisSemis(lot, aujourdhui = null) {
  const ref = aujourdhui ?? lot?.echeances?.date_reference
  if (!lot?.date_semis || !ref) return null
  const d = (iso) => Date.UTC(...String(iso).slice(0, 10).split('-').map((v, i) => (i === 1 ? Number(v) - 1 : Number(v))))
  const jours = Math.round((d(ref) - d(lot.date_semis)) / 86400000)
  return jours >= 0 ? jours : null
}

// ── État du lot ──────────────────────────────────────────────────────────────

export const aDesGodets = (lot) => (lot?.stock_residuel_godet ?? 0) > 0
export const aDesGraines = (lot) => (lot?.graines_en_germination ?? 0) > 0

/** [CA13] Clôturé par un geste : plus rien n'y est à faire, définitivement. */
export const estCloture = (lot) => Boolean(lot?.cloture)

/**
 * [CA13] Terminé : tout est mis en terre, vendu, perdu — ou clôturé. Un lot qui n'a
 * jamais rien eu (ni godet ni graine connue) n'est pas « terminé », il est vide.
 */
export function estTermine(lot) {
  if (estCloture(lot)) return true
  if (aDesGodets(lot) || aDesGraines(lot)) return false
  return (lot?.plants_obtenus ?? 0) > 0 || (lot?.graines_semees ?? 0) > 0
}

export const estDormant = (lot) => Boolean(lot?.echeances?.dormance?.est_dormant)

/** `cloture` | `termine` | `dormant` | `en_cours` — l'état dont la fiche tire son bandeau. */
export function etatDuLot(lot) {
  if (estCloture(lot)) return 'cloture'
  if (estTermine(lot)) return 'termine'
  if (estDormant(lot)) return 'dormant'
  return 'en_cours'
}

/** [CA13] La phrase du bandeau d'un lot sans geste ; `null` pour un lot en cours. */
export function bandeauEtat(lot) {
  const etat = etatDuLot(lot)
  if (etat === 'cloture') {
    const jour = dateEnClair(lot.date_cloture)
    return { texte: jour ? `Lot clôturé le ${jour}` : 'Lot clôturé', ton: 'neutre' }
  }
  if (etat === 'termine') return { texte: 'Lot terminé', ton: 'neutre' }
  return null
}

// ── Échéance ─────────────────────────────────────────────────────────────────

/**
 * [CA4] L'échéance du lot, en clair et datée — un TITRE et un DÉTAIL, comme la
 * maquette figée du 14/10/2026 : « En retard de 6 jours » puis « Repiquage attendu
 * entre le 11 et le 13 septembre. ».
 *
 * Retourne `{ titre, detail, ton, texte, alerte, raisons }`. `ton` vaut `retard`
 * (teinte d'alerte ambre), `info` ou `na` (rien à calculer, ou lot dormant : teinte
 * neutre). `texte` est la même chose sur une ligne. Une échéance incalculable donne
 * ses raisons, telles que l'API les écrit — aucun conseil agronomique rédigé ici (RT2).
 */
export function echeanceEnClair(lot) {
  const vide = { titre: null, detail: null, ton: 'info', texte: null, alerte: false, raisons: [] }
  const e = lot?.echeances
  if (!e) return vide
  const raisons = Array.isArray(e.raisons) ? e.raisons : []
  if (estTermine(lot)) return { ...vide, raisons }

  const rep = e.repiquage ?? {}
  const terre = e.mise_en_terre ?? {}
  const endu = e.endurcissement ?? {}
  const dorm = e.dormance ?? {}
  const periodeRep = periodeEnClair(rep.du, rep.au)
  const periodeTerre = periodeEnClair(terre.du, terre.au)

  const fait = (titre, detail, ton = 'info') => ({
    titre,
    detail,
    ton,
    texte: detail ? `${titre} — ${detail.charAt(0).toLowerCase()}${detail.slice(1).replace(/\.$/, '')}` : titre,
    alerte: ton === 'retard',
    raisons,
  })

  if (dorm.est_dormant) {
    const depuis = dateEnClair(dorm.dernier_geste)
    return fait(
      `Dormant depuis ${pluriel(dorm.jours_sans_geste, 'jour')}`,
      depuis
        ? `Aucun geste depuis le ${depuis} : ni repiqué, ni planté, ni perdu.`
        : 'Aucun geste récent : ni repiqué, ni planté, ni perdu.',
      'na',
    )
  }
  if (rep.etat === 'en_retard') {
    return fait(`En retard de ${pluriel(rep.retard_jours, 'jour')}`, `Repiquage attendu ${periodeRep}.`, 'retard')
  }
  if (terre.etat === 'depassee') {
    return fait(`En retard de ${pluriel(terre.retard_jours, 'jour')}`, `Mise en terre attendue ${periodeTerre}.`, 'retard')
  }
  if (rep.etat === 'a_repiquer') return fait('À repiquer', `Repiquage attendu ${periodeRep}.`)
  if (endu.etat === 'en_cours') {
    return fait(
      `Endurcissement, jour ${endu.jour} sur ${endu.sur}`,
      periodeTerre ? `Mise en terre attendue ${periodeTerre}.` : null,
    )
  }
  if (endu.etat === 'froide') {
    return fait('En pépinière froide', periodeTerre ? `Mise en terre attendue ${periodeTerre}.` : null)
  }
  if (terre.etat === 'atteinte') return fait('Mise en terre à faire', `Attendue ${periodeTerre}.`)
  if (rep.etat === 'a_venir') {
    return fait(`Repiquage dans ${pluriel(rep.dans_jours, 'jour')}`, `Attendu ${periodeRep}.`)
  }
  if (terre.etat === 'a_venir') {
    return fait(`Mise en terre dans ${pluriel(terre.dans_jours, 'jour')}`, `Attendue ${periodeTerre}.`)
  }
  if (raisons.length > 0) {
    const detail = raisons.map((r) => `${r.charAt(0).toUpperCase()}${r.slice(1)}.`).join(' ')
    return fait('Échéance non calculée', detail, 'na')
  }
  return { ...vide, raisons }
}

/**
 * [CA3] Le badge d'état de la barre du haut : `[libellé, teinte]`, teintes du design
 * system. « En plaque » tant qu'aucun plant n'est en godet, « En godet » ensuite.
 */
export function badgeEtat(lot, { lecture = false } = {}) {
  if (lecture) return ['Lecture seule', 'violet']
  const etat = etatDuLot(lot)
  if (etat === 'cloture') return ['Lot clôturé', 'brand']
  if (etat === 'termine') return ['Lot terminé', 'brand']
  if (etat === 'dormant') return ['Dormant', 'amber']
  if ((lot?.nb_mises_en_godet ?? 0) > 0 || aDesGodets(lot)) return ['En godet', 'amber']
  return ['En plaque', 'blue']
}

/**
 * [CA13] La phrase d'un lot sans geste : terminé (« Lot terminé le 30 mai : tout est
 * mis en terre, vendu ou perdu ») ou clôturé. `null` pour un lot en cours. La date est
 * celle du dernier geste du lot — la seule que l'API donne.
 */
export function phraseLotSansGeste(lot) {
  const etat = etatDuLot(lot)
  if (etat === 'cloture') {
    const jour = dateEnClair(lot.date_cloture)
    return {
      titre: jour ? `Lot clôturé le ${jour}` : 'Lot clôturé',
      suite: 'Tout ce qui restait a été soldé. Plus aucun geste à faire.',
    }
  }
  if (etat === 'termine') {
    const jour = dateEnClair(lot.date_dernier_geste)
    return {
      titre: jour ? `Lot terminé le ${jour}` : 'Lot terminé',
      suite: 'Tout est mis en terre, vendu ou perdu. Plus aucun geste à faire.',
    }
  }
  return null
}

/**
 * « du chou », « de la tomate », « de l'ail » — pour « la moyenne du chou dans ce
 * potager ». Le genre n'est pas dans le référentiel : une courte liste de cultures
 * féminines courantes, le masculin sinon (et l'élision devant une voyelle).
 */
const FEMININES = new Set([
  'tomate', 'courgette', 'laitue', 'carotte', 'betterave', 'aubergine', 'fraise', 'courge',
  'salade', 'pomme de terre', 'endive', 'framboise', 'mâche', 'mache', 'chicorée', 'blette',
  'bette', 'capucine', 'citrouille', 'menthe', 'ciboulette', 'roquette', 'coriandre',
  'patate douce', 'poire', 'pomme', 'cerise', 'rhubarbe', 'sauge', 'aneth', 'pastèque',
  'tétragone', 'oseille', 'échalote', 'echalote', 'ciboule', 'févérole', 'feverole', 'fève', 'feve',
])

export function deLaCulture(nom) {
  const c = String(nom ?? '').trim().toLowerCase()
  if (!c) return 'de la culture'
  if (/^[aeiouyàâäéèêëîïôöùûüh]/.test(c)) return `de l'${c}`
  return FEMININES.has(c) ? `de la ${c}` : `du ${c}`
}

// ── Les gestes ───────────────────────────────────────────────────────────────

/** Les codes d'action suggérée (US-214) → le code de geste de la fiche. */
const GESTE_DE_SUGGESTION = Object.freeze({
  repiquer: 'repiquer',
  noter_levee: 'noter_levee',
  mettre_en_terre: 'mettre_en_terre',
  cloturer: 'cloturer',
})

/**
 * [CA8, CA9] Les gestes pertinents pour l'état du lot, l'**action suggérée** en
 * premier et en principal.
 *
 * Chaque geste porte de quoi préparer le geste pré-rempli : `action` (le
 * vocabulaire du serveur), `quantite` et `unite` proposées quand elles sont
 * connues, `lotId` (le semis du lot). Ce qui manque, le compagnon le demande.
 *
 * @param lot  Un lot tel que `GET /pepiniere/lots[/{numero}]` le rend.
 * @param opts `nbPepinieres` (nombre de pépinières du potager, `null` si inconnu),
 *             `levee` (le geste de levée est-il livré ? — `LEVEE_DISPONIBLE`).
 */
export function gestesDuLot(lot, { nbPepinieres = null, levee = LEVEE_DISPONIBLE } = {}) {
  if (!lot || estTermine(lot)) return []   // [CA13] un lot terminé n'a aucun geste

  const sansSemis = Boolean(lot.sans_semis_rattache)
  const godets = lot.stock_residuel_godet ?? 0
  const graines = lot.graines_en_germination ?? 0
  const reste = godets > 0 || graines > 0
  const base = {
    lotId: sansSemis ? null : (lot.semis_id ?? null),
    numeroLot: lot.numero_lot ?? null,   // sert à la phrase à dicter : « … du lot 128 »
    culture: lot.culture,
    variete: lot.variete ?? null,
  }
  const gestes = []

  // [CA8] Le lot « godets sans semis rattaché » n'a ni Repiquer ni Noter la levée.
  if (!sansSemis && graines > 0) {
    gestes.push({
      ...base, code: 'repiquer', libelle: 'Repiquer en godet', action: 'mise_en_godet',
      // Les levés sont proposés quand US-212 les a comptés ; sinon le compagnon demande.
      quantite: lot.nb_leves ?? null, unite: 'plants',
    })
    if (levee && lot.levee_terminee !== true) {
      gestes.push({ ...base, code: 'noter_levee', libelle: 'Noter la levée', action: 'levee', quantite: null, unite: null })
    }
  }
  if (godets > 0) {
    gestes.push({
      ...base, code: 'mettre_en_terre', libelle: 'Mettre en terre', action: 'plantation',
      quantite: godets, unite: 'plants',
    })
  }
  if (reste) {
    gestes.push({
      ...base, code: 'declarer_perte', libelle: 'Déclarer une perte', action: 'perte_godet',
      quantite: null, unite: 'plants',
    })
  }
  // [CA8] Déplacer : au moins deux pépinières, sinon il n'y a nulle part où aller.
  if (reste && nbPepinieres != null && nbPepinieres >= 2) {
    gestes.push({ ...base, code: 'deplacer', libelle: 'Déplacer', action: 'deplacement', quantite: null, unite: null })
  }
  // [CA8] Clôturer : un lot dormant seulement ; il solde tout, définitivement.
  if (estDormant(lot) && reste) {
    gestes.push({
      ...base, code: 'cloturer', libelle: 'Clôturer', action: 'cloture_lot',
      quantite: null, unite: null, solde: { godets, graines },
    })
  }

  // L'action suggérée passe devant, et seule elle est « principale ».
  const suggere = GESTE_DE_SUGGESTION[lot.action_suggeree?.code]
  const ordonnes = [...gestes].sort((a, b) => (b.code === suggere) - (a.code === suggere))
  return ordonnes.map((g, i) => ({ ...g, principal: i === 0 && g.code === suggere }))
}

/** [CA8] Le geste à mettre en avant, ou `null` si l'action suggérée n'a pas de bouton ici. */
export const gestePrincipal = (gestes) => gestes.find((g) => g.principal) ?? null

/** [CA11] Combien de boutons de geste sont posés — de quoi dimensionner l'écran de terrain. */
export const nbGestes = (lot, opts) => gestesDuLot(lot, opts).length

/** La phrase sous « Clôturer » : ce que le geste solde, dit avant d'appuyer. */
export function phraseSolde({ godets = 0, graines = 0 } = {}) {
  const morceaux = []
  if (godets > 0) morceaux.push(pluriel(godets, 'godet'))
  if (graines > 0) morceaux.push(pluriel(graines, 'graine') + (graines > 1 ? ' non levées' : ' non levée'))
  return morceaux.length
    ? `Solde définitivement le lot : ${morceaux.join(' et ')}.`
    : 'Solde définitivement le lot.'
}

// ── Traçabilité ──────────────────────────────────────────────────────────────

/**
 * [CA5] Les lignes de traçabilité. Un tiret signifie « aucun geste de ce type »,
 * jamais zéro — sauf pour ce qui se compte par différence (godets restants, graines
 * encore en germination), où zéro est un vrai résultat.
 */
export function tracabilite(lot) {
  const ligne = (cle, libelle, valeur, { tiret = false, sub = null } = {}) => ({
    cle, libelle, sub, valeur: tiret || valeur == null ? null : valeur,
  })
  const sansSemis = Boolean(lot?.sans_semis_rattache)
  const aGodets = (lot?.nb_mises_en_godet ?? 0) > 0
  const leves = lot?.nb_leves ?? null
  const taux = tauxLevee(leves, lot?.graines_semees)
  return [
    ligne('semees', 'Graines semées', lot?.graines_semees, {
      tiret: sansSemis || !(lot?.graines_semees > 0), sub: 'prélevées au stock',
    }),
    ligne('leves', 'Levés', leves, { tiret: leves == null }),
    {
      cle: 'taux_levee', libelle: 'Taux de levée', valeur: taux, unite: '%',
      sub: taux != null && lot?.moyenne_levee_culture != null
        ? `moyenne ${deLaCulture(lot.culture)} ici : ${lot.moyenne_levee_culture} %` : null,
    },
    ligne('repiques', 'Repiqués en godet', lot?.plants_obtenus, { tiret: !aGodets }),
    ligne('pertes', 'Pertes déclarées', lot?.nb_pertes_godet, { tiret: !(lot?.nb_pertes_godet > 0) }),
    ligne('vendus', 'Vendus', lot?.nb_vendus, { tiret: !(lot?.nb_vendus > 0) }),
    ligne('en_terre', 'Mis en terre', lot?.nb_plantes, { tiret: !(lot?.nb_plantes > 0) }),
    ligne('godets', 'Godets restants', lot?.stock_residuel_godet, { tiret: !aGodets }),
    ligne('germination', 'Encore en germination', lot?.graines_en_germination, { tiret: sansSemis || !(lot?.graines_semees > 0) }),
  ]
}

/** [CA5] Une incohérence de saisie reste visible : la phrase, ou `null`. */
export function incoherenceEnClair(lot) {
  if (!lot?.incoherence_saisie) return null
  return `${lot.plants_obtenus} plants pour ${lot.graines_semees} ${lot.unite || 'graines'} semées — à vérifier`
}

// ── Le compteur de levée ─────────────────────────────────────────────────────

/** [CA10] Le taux de levée, arrondi, ou `null` quand il ne se calcule pas. */
export function tauxLevee(leves, graines) {
  if (leves == null || !(graines > 0)) return null
  return Math.round((leves / graines) * 100)
}

/**
 * [CA10] La comparaison à la moyenne de la culture — celle d'US-212, quand elle en
 * rend une. Sans moyenne, la phrase se réduit au taux : rien n'est inventé.
 */
export function phraseComparaison({ taux, moyenne = null, culture = null } = {}) {
  if (taux == null) return null
  if (moyenne == null) return `${taux} %`
  const nom = culture ? ` ${deLaCulture(culture)}` : ''
  // Deux points d'écart ne font pas une différence : la moyenne d'un petit nombre de lots bouge.
  const position = taux > moyenne + 2 ? 'au-dessus de' : taux < moyenne - 2 ? 'en dessous de' : 'dans'
  return `${taux} % — ${position} la moyenne${nom} dans ce potager, ${moyenne} %`
}

/** Teinte du taux, comme celle du badge de germination de la liste (US-061 / CA11). */
export function teinteTaux(taux) {
  if (taux == null) return 'blue'
  if (taux >= 80) return 'brand'
  if (taux >= 50) return 'amber'
  return 'red'
}

/**
 * [CA10] Le nombre de départ du compteur : le dernier comptage s'il existe, sinon
 * `null` — le champ est vide et « Envoyer » grisé, aucun zéro n'est supposé. Jamais
 * plus que les graines semées : on ne lève pas plus qu'on n'a semé.
 */
export function valeurInitialeCompteur(lot) {
  if (lot?.nb_leves == null) return null
  const max = lot?.graines_semees > 0 ? lot.graines_semees : null
  return max == null ? lot.nb_leves : Math.min(lot.nb_leves, max)
}

/** Borne la saisie d'un compteur : entier, entre 0 et `max` (illimité si `max` est nul). */
export function borner(valeur, max = null) {
  const n = Math.trunc(Number(valeur))
  if (!Number.isFinite(n) || n < 0) return 0
  return max != null && n > max ? max : n
}

/** Lit ce que le jardinier tape : « 40 », « 40 plants » → 40 ; autre chose → `null`. */
export function lireNombre(saisie) {
  const m = /^\s*(\d{1,6})\s*(?:plants?|graines?|levés?)?\s*$/i.exec(String(saisie ?? ''))
  return m ? Number(m[1]) : null
}

/** Le geste de levée à préparer à partir du compteur — jamais d'écriture ici. */
export function gesteDeLevee(lot, { leves, termine = false }) {
  return {
    action: 'levee',
    culture: lot.culture,
    variete: lot.variete ?? null,
    quantite: leves,
    unite: 'plants',
    lotId: lot.sans_semis_rattache ? null : (lot.semis_id ?? null),
    numeroLot: lot.numero_lot ?? null,
    terminee: termine,
  }
}

/** Le geste, au format de `BoutonGeste`, d'un des gestes de `gestesDuLot`. */
export function gestePrepare(g) {
  return {
    action: g.action, culture: g.culture, variete: g.variete,
    quantite: g.quantite, unite: g.unite, lotId: g.lotId, numeroLot: g.numeroLot ?? null,
  }
}

// ── [US-217] Où les mettre ───────────────────────────────────────────────────

/** [CA6] Trois suggestions, puis « voir toutes les parcelles ». */
export const NB_SUGGESTIONS_VISIBLES = 3

/** Les suggestions à afficher : les trois premières, ou toutes une fois dépliées. */
export function suggestionsVisibles(ouMettre, toutes = false) {
  const s = ouMettre?.suggestions ?? []
  return toutes ? s : s.slice(0, NB_SUGGESTIONS_VISIBLES)
}

/**
 * Ce qui reste dans la parcelle : en places quand US-227 les connaît, en rangs libres
 * sinon — jamais les deux côte à côte. Des rangs inconnus sont dits tels (CA3).
 */
export function placeEnClair(s, culture) {
  if (s?.places_libres) {
    const nom = culture ? ` de ${String(culture).toLowerCase()}` : ''
    return `${s.places_libres} place${s.places_libres > 1 ? 's' : ''}${nom}`
  }
  if (s?.rangs_libres == null) return 'rangs libres inconnus'
  return `${s.rangs_libres} rang${s.rangs_libres > 1 ? 's libres' : ' libre'}`
}

/**
 * [CA7] « Mettre en terre ici » : la plantation du lot, parcelle connue, godets
 * proposés. Le rang n'est pré-rempli que si sa position est connue (US-203).
 */
export function gesteMiseEnTerreIci(lot, s) {
  const g = gestesDuLot(lot, {}).find((x) => x.code === 'mettre_en_terre')
  if (!g) return null
  return {
    ...gestePrepare(g),
    parcelleId: s?.parcelle_id ?? null, parcelleNom: s?.parcelle ?? null,
    rang: s?.premier_rang_libre ?? null,
  }
}
