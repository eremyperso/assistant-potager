// [US-222] Le **niveau 2 du zoom d'information** : une parcelle, agrandie.
//
// Le wireframe v4 (21/09/2026) pose quatre niveaux et un objet par niveau — le
// potager entier (Vue plan), une parcelle (onglet Parcelles), une culture, son
// calendrier. « Un niveau agrandit l'objet du niveau précédent et ajoute ce que
// ce niveau ne pouvait pas porter. Il ne le reformate jamais. »
//
// Ce module ne dessine donc RIEN de neuf : il regroupe les rangs déjà calculés
// par `planVue.js` (US-198, US-200, US-227, US-228) sous une tuile par culture,
// et compose les textes propres à ce niveau — occupation en rangs, en-tête de
// détail, ligne d'index. Les places, les longueurs, les phases et les pistes
// viennent telles quelles du niveau 1 [CA2] : un rang porte les mêmes places
// prises et restantes aux deux niveaux, parce que c'est le **même objet**.
//
// Aucune lecture ici non plus [CA1] : tout sort de la réponse de `GET /plan`.
import {
  rangsDeLaCarte, superficieTexte, dimensionsTexte, phraseNbRangs, phraseLongueur,
  capitaliser, nombre, MENTION_SANS_RANGS, MENTION_SANS_LONGUEUR,
  TYPE_PEPINIERE_INCONNU,
} from './planVue.js'
import { expositionAffichable } from './plan.js'
// [US-231 / R3] La teinte d'une famille — identité stable, jamais jugement.
import { teinteFamille } from './familles.js'

/** [D1, D3, D4] Le tiret d'occupation — une absence dite, jamais un zéro inventé. */
export const TIRET_OCCUPATION = '—'

/** Occupation telle qu'elle s'écrit sans place : « 4/5 », ou « — » faute de dénominateur. */
export function occupationCourte(parcelle) {
  const disposition = parcelle?.disposition ?? {}
  if (parcelle?.est_pepiniere) return TIRET_OCCUPATION
  if (disposition.rangs_declares == null) return TIRET_OCCUPATION
  return `${disposition.rangs_occupes ?? 0}/${disposition.rangs_declares}`
}

/**
 * [D5, D11] L'occupation en toutes lettres, sous le nom de la parcelle.
 *
 * Le dépassement se dit comme au niveau 1 (US-200 / V10), mot pour mot : c'est
 * la même phrase qui doit se retrouver d'un niveau à l'autre, pas une variante.
 */
export function occupationDetail(parcelle) {
  const disposition = parcelle?.disposition ?? {}
  if (parcelle?.est_pepiniere) return null
  const occupes = disposition.rangs_occupes ?? 0
  const declares = disposition.rangs_declares
  if (declares == null) return `${occupes} rang${occupes > 1 ? 's' : ''} occupé${occupes > 1 ? 's' : ''}`
  if ((disposition.depassement ?? 0) > 0) {
    return `${occupes} rangs occupés pour ${declares} déclaré${declares > 1 ? 's' : ''}`
  }
  return `${occupes} rang${occupes > 1 ? 's' : ''} occupé${occupes > 1 ? 's' : ''} sur ${declares}`
}

/**
 * [D1, D3, D4] Le sous-titre d'une ligne d'index : ce que la parcelle EST, en
 * une ligne. Une pépinière compte ses lots (US-208), jamais ses rangs (D3) ;
 * une parcelle sans culture se dit « libre » plutôt que « 0 culture ».
 */
export function sousTitreListe(parcelle) {
  const surface = parcelle?.superficie_m2 ? ` · ${superficieTexte(parcelle)}` : ''
  if (parcelle?.est_pepiniere) {
    const lots = parcelle?.disposition?.nb_lots_en_cours ?? 0
    const type = parcelle?.type_pepiniere || TYPE_PEPINIERE_INCONNU
    return `pépinière ${type} · ${lots} lot${lots > 1 ? 's' : ''}`
  }
  const n = parcelle?.cultures?.length ?? 0
  if (n === 0) return `libre${surface}`
  return `${n} culture${n > 1 ? 's' : ''}${surface}`
}

/** [D1, D2, D4] Une ligne de l'index de gauche — un texte, jamais un dessin. */
export function ligneListeParcelle(parcelle) {
  const disposition = parcelle?.disposition ?? {}
  const pepiniere = Boolean(parcelle?.est_pepiniere)
  return {
    id: parcelle?.id,
    nom: parcelle?.nom || '',
    sousTitre: sousTitreListe(parcelle),
    occupation: occupationCourte(parcelle),
    // [D2] Seul le dépassement garde une teinte : dans l'activité Plan, la
    // couleur dit la phase et rien d'autre (RT4).
    depassement: pepiniere ? 0 : disposition.depassement ?? 0,
    pepiniere,
    libre: !pepiniere && (parcelle?.cultures?.length ?? 0) === 0,
    // [D4] Le manque est dit dans l'index aussi, pas seulement dans le détail.
    mention: !pepiniere && disposition.rangs_declares == null ? MENTION_SANS_RANGS : null,
    // [US-229 / C8] La pastille « Informations à compléter » : un point, pas une
    // couleur d'état. Elle dit qu'il reste une caractéristique à dire, jamais
    // que la parcelle va mal.
    aCompleter: parcelleACompleter(parcelle),
  }
}

/**
 * [D5, US-181] L'abri tel qu'il se lit : « Plein air » quand le jardinier a
 * déclaré n'en avoir aucun, le nom de l'abri sinon, et `null` quand la question
 * n'a jamais été posée — une absence de donnée ne devient pas une déclaration.
 */
export function abriTexte(abri) {
  const v = (abri || '').trim()
  if (!v) return null
  return v.toLowerCase() === 'aucun' ? 'Plein air' : capitaliser(v)
}

/**
 * [D5 amendé] « Pleine terre · sans abri · active » — ce que la parcelle est,
 * d'un coup d'œil. Une valeur jamais renseignée ne devient pas une déclaration :
 * un abri inconnu ne dit ni « sans abri » ni le contraire, il se tait.
 */
export function ligneEtat(parcelle) {
  const segments = []
  if (parcelle?.est_pepiniere) {
    const lots = parcelle?.disposition?.nb_lots_en_cours ?? 0
    segments.push(`Pépinière ${parcelle?.type_pepiniere || TYPE_PEPINIERE_INCONNU}`)
    segments.push(`${lots} lot${lots > 1 ? 's' : ''}`)
  } else {
    segments.push('Pleine terre')
    const abri = abriTexte(parcelle?.abri)
    if (abri) segments.push(abri === 'Plein air' ? 'sans abri' : `sous ${abri.toLowerCase()}`)
  }
  segments.push(parcelle?.actif === false ? 'inactive' : 'active')
  return segments.join(' · ')
}

/**
 * [D5] L'en-tête du détail : le nom, les pastilles de ce que la parcelle est,
 * l'occupation en rangs — et les deux mentions de donnée manquante, qui ne se
 * remplacent jamais par une valeur inventée (US-200 / V9, US-225 / P12).
 */
export function enteteDetail(parcelle) {
  const disposition = parcelle?.disposition ?? {}
  const pepiniere = Boolean(parcelle?.est_pepiniere)
  const sansNbRangs = !pepiniere && disposition.rangs_declares == null
  const sansLongueur = !pepiniere && parcelle?.longueur_m == null

  return {
    nom: parcelle?.nom || '',
    // [D5 amendé] La ligne d'état : ce que la parcelle EST, en une ligne de
    // teinte secondaire. Les pastilles de superficie, dimensions, exposition,
    // abri et paillage sont retirées — la carte « Caractéristiques » les dit
    // juste en dessous, en mieux (US-229 / C2, C3).
    etat: ligneEtat(parcelle),
    superficie: parcelle?.superficie_m2 ? superficieTexte(parcelle) : null,
    // [US-225] Longueur de rang et largeur déduite, ou la mention de l'absence.
    dimensions: pepiniere ? null : dimensionsTexte(parcelle),
    exposition: expositionAffichable(parcelle?.exposition),
    // [US-181, livrée] Abri ou plein air, et paillage. `null` en base veut dire
    // « jamais renseigné », ce qui n'est PAS « plein air » : la pastille est
    // alors omise, comme l'exposition « NULL » d'US-060 / CA4.
    abri: abriTexte(parcelle?.abri),
    // [US-229] `paillage` est un BOOLÉEN en base (migration_v49) : la pastille
    // affichait « Paillage true ». Elle dit désormais oui ou non, et disparaît
    // quand la question n'a jamais été posée (C4).
    paillage: parcelle?.paillage == null ? null : (parcelle.paillage ? 'oui' : 'non'),
    occupation: occupationDetail(parcelle),
    depassement: pepiniere ? 0 : disposition.depassement ?? 0,
    pepiniere,
    typePepiniere: parcelle?.type_pepiniere || TYPE_PEPINIERE_INCONNU,
    nbLots: disposition.nb_lots_en_cours ?? 0,
    sansNbRangs,
    mention: sansNbRangs ? MENTION_SANS_RANGS : null,
    phrase: sansNbRangs ? phraseNbRangs(parcelle) : null,
    sansLongueur,
    mentionLongueur: sansLongueur ? MENTION_SANS_LONGUEUR : null,
    phraseLongueur: sansLongueur ? phraseLongueur(parcelle) : null,
    nbObservations: parcelle?.nb_observations ?? 0,
    hasObservations: Boolean(parcelle?.has_observations),
  }
}

/**
 * [CA13, US-222 amendé] Le détail entier d'une parcelle, prêt à rendre.
 *
 * ⚠️ Depuis l'amendement du 24/09/2026, il ne porte PLUS de tuiles de culture
 * ni de rangs libres actionnables : la fiche a un **bandeau d'occupation** et
 * renvoie au Plan. Ce qu'elle porte à la place est ce que le Plan ne peut pas
 * porter — les caractéristiques, la rotation, le journal du sol.
 */
export function detailDeParcelle(parcelle, vocabulaires = {}) {
  const entete = enteteDetail(parcelle)
  const bandeau = bandeauOccupation(parcelle)
  return {
    id: parcelle?.id,
    entete,
    // [D5b] L'occupation en rangs et les noms des cultures — le seul reste des
    // cultures dans cette fiche.
    bandeau,
    // [US-229 / C1] La carte « Caractéristiques », entre le bandeau et la
    // colonne Rotation / Sol et entretien.
    caracteristiques: caracteristiquesDeParcelle(parcelle),
    // [US-230 / E1] La MÊME carte, en édition : même ordre, mêmes champs.
    saisie: saisieDeParcelle(parcelle, vocabulaires),
    aideCompagnon: aideCompagnon(parcelle),
    // [US-231 / R1, R8] La carte « Rotation », juste après « Caractéristiques » —
    // `null` pour une pépinière, dont la rotation n'a pas de sens.
    rotation: rotationDeParcelle(parcelle),
    libre: bandeau.libre,
  }
}

// ── [US-229] La carte « Caractéristiques » ───────────────────────────────────
//
// Le niveau 2 agrandissait la parcelle sans jamais dire ce qu'elle EST : ses
// champs se devinaient à travers des pastilles d'en-tête. Or les trois dernières
// livraisons (US-197 nombre de rangs, US-225 longueur, US-181 abri et paillage)
// ont ajouté des données dont l'ABSENCE dégrade d'autres écrans — « nombre de
// rangs non renseigné », confiance abaissée — sans jamais montrer où la
// corriger. Cette carte rassemble ces champs et **nomme l'absence**.
//
// Rien de neuf n'est stocké : chaque champ se lit sur une colonne existante de
// `parcelles`, sauf la largeur, qui se DÉDUIT côté serveur
// (`utils.parcelles.largeur_deduite`) et n'est jamais recalculée ici [CA2, CA3].

/** [C3] Ce qui se dit à la place d'une valeur absente — jamais un tiret discret. */
export const NON_RENSEIGNE = 'Non renseigné'

/** [C5] Ce qu'une largeur absente explique d'elle-même. */
export const MENTION_LARGEUR_DEDUITE = 'déduite de la superficie et de la longueur'

/** [C5] Le suffixe qui dit qu'une valeur n'a pas été déclarée, mais calculée. */
export const SUFFIXE_DEDUITE = 'déduite'

/** [C8] Le titre accessible de la pastille de l'index. */
export const TITRE_A_COMPLETER = 'Informations à compléter'

/**
 * [C7] Les phrases que le compagnon sait VRAIMENT entendre, telles que le corpus
 * les documente (`parcelles-et-plan.md`). On n'en invente aucune : le type de
 * sol, l'exposition et la superficie n'ont pas de phrase dédiée aujourd'hui —
 * ils retombent donc sur l'exemple générique plutôt que sur une commande que le
 * compagnon refuserait. L'édition depuis le web arrive avec US-230.
 */
const EXEMPLES = {
  nb_rangs: (nom) => `${nom} a 5 rangs`,
  longueur: (nom) => `${nom} fait 12 mètres de long`,
  abri: (nom) => `${nom} est sous serre`,
  paillage: (nom) => `${nom} est paillée`,
}

const EXEMPLE_GENERIQUE = (nom) => `${nom} fait 12 mètres de long`

/**
 * [C2, C3, C4, C5, C6, C9, C10] Les caractéristiques d'une parcelle, dans
 * l'ordre de la maquette, chacune sachant dire qu'elle manque.
 *
 * Un champ porte :
 * - `valeur`   : le texte à rendre — `NON_RENSEIGNE` quand rien n'est connu ;
 * - `suffixe`  : la précision en petit (« déduite ») ;
 * - `aide`     : ce qui explique l'absence, quand il y a quelque chose à dire ;
 * - `manquant` : l'état d'alerte douce [C3], qui compte aussi pour la pastille.
 */
export function caracteristiquesDeParcelle(parcelle) {
  const pepiniere = Boolean(parcelle?.est_pepiniere)
  const champs = []
  const ajouter = (cle, label, valeur, opts = {}) => {
    const absent = valeur == null && !opts.toujoursRenseigne
    champs.push({
      cle,
      label,
      valeur: absent ? NON_RENSEIGNE : valeur,
      suffixe: absent ? null : (opts.suffixe ?? null),
      aide: absent ? (opts.aide ?? null) : null,
      manquant: absent,
    })
  }

  ajouter('nom', 'Nom', (parcelle?.nom || '').trim() || null)
  ajouter('superficie', 'Superficie',
    parcelle?.superficie_m2 ? `${nombre(parcelle.superficie_m2)} m²` : null)

  // [C9] Une pépinière n'a ni longueur utile, ni largeur, ni rangs qui aient un
  // sens : ces trois champs sont RETIRÉS de la grille, pas rendus en état
  // manquant — et leur absence ne fait donc pas apparaître la pastille C8.
  if (!pepiniere) {
    ajouter('longueur', 'Longueur',
      parcelle?.longueur_m ? `${nombre(parcelle.longueur_m)} m` : null)
    // [C5, CA2] La largeur n'est JAMAIS présentée comme déclarée, et aucune
    // division n'est refaite ici : le serveur l'a déduite, l'écran la relit.
    const largeur = parcelle?.largeur_m
    const deductible = Boolean(parcelle?.superficie_m2) && Boolean(parcelle?.longueur_m)
    ajouter('largeur', 'Largeur',
      deductible && largeur != null ? `${nombre(largeur, 2)} m` : null, {
        // [US-225 / CA7] Une largeur absurde reste affichée telle quelle : on
        // dit qu'elle est à vérifier, on ne corrige aucune des deux valeurs.
        suffixe: parcelle?.largeur_incoherente
          ? `${SUFFIXE_DEDUITE}, à vérifier`
          : SUFFIXE_DEDUITE,
        aide: MENTION_LARGEUR_DEDUITE,
      })
    ajouter('nb_rangs', 'Nombre de rangs',
      parcelle?.nb_rangs == null ? null : String(parcelle.nb_rangs))
  }

  ajouter('exposition', 'Exposition',
    capitaliser(expositionAffichable(parcelle?.exposition) || '') || null)
  ajouter('type_sol', 'Type de sol', capitaliser((parcelle?.type_sol || '').trim()) || null)
  // [C4, US-181] « Aucun » est une déclaration du jardinier, `NULL` est un
  // silence : les deux ne se confondent jamais.
  ajouter('abri', 'Abri', parcelle?.abri == null ? null : (abriTexte(parcelle.abri) || null))
  ajouter('paillage', 'Paillage',
    parcelle?.paillage == null ? null : (parcelle.paillage ? 'Oui' : 'Non'))
  // [C6] Deux booléens qui ont toujours une valeur : ils ne manquent jamais et
  // ne comptent pas dans la pastille.
  ajouter('pepiniere', 'Pépinière', pepiniere ? 'Oui' : 'Non', { toujoursRenseigne: true })
  // [C10] Une parcelle inactive n'est pas une parcelle cassée : la carte est
  // rendue entière, et c'est le statut qui le dit.
  ajouter('statut', 'Statut', parcelle?.actif === false ? 'Inactive' : 'Active',
    { toujoursRenseigne: true })

  return champs
}

// ── [US-230] La même carte, en édition ───────────────────────────────────────
//
// US-229 nommait ce qui manque et s'arrêtait là : le seul chemin de correction
// restait la phrase dite au compagnon, une phrase par champ. Un jardinier qui
// découvre quatre champs vides sur une planche devait en dicter quatre.
//
// Ce bloc rend la carte modifiable **sur place** : même bloc, même ordre, mêmes
// champs — un bouton bascule, rien ne se déplace [E1]. Il ne décide RIEN :
//   - les bornes (1 à 99 rangs, 0,5 à 200 m) et les vocabulaires fermés
//     viennent du serveur ou n'existent pas ici [CA3] ; les attributs `min`,
//     `max` et `step` posés sur les champs sont un **confort de frappe**,
//     jamais la règle — c'est l'API qui refuse [CA5] ;
//   - la largeur ne se saisit pas : elle se déduit [E3] ;
//   - rien n'est écrit champ par champ : un seul appel porte le lot [E4].

/** [E2] Les quatre façons de saisir une caractéristique. */
export const SAISIE_TEXTE = 'texte'
export const SAISIE_NOMBRE = 'nombre'
export const SAISIE_LISTE = 'liste'
export const SAISIE_OUI_NON = 'ouiNon'
/** [E3] La largeur : affichée en édition, jamais saisissable. */
export const SAISIE_DEDUITE = 'deduite'

/** [E2] Le choix qui remet la valeur à `NULL` — distinct de « Non » et d'« Aucun ». */
export const CHOIX_NON_RENSEIGNE = ''
export const LIBELLE_NON_RENSEIGNE = 'Non renseigné'

/** [E3] Ce que la case de la largeur dit à la place d'un champ. */
export const TEXTE_LARGEUR_CALCULEE = 'Calculée : superficie ÷ longueur'

/**
 * [CA1] Les noms des champs côté API. La largeur n'y est pas : elle se déduit.
 * L'ordre d'affichage non plus : il se règle dans la Vue plan (US-202).
 */
export const CHAMP_API = {
  nom: 'nom',
  superficie: 'superficie_m2',
  longueur: 'longueur_m',
  nb_rangs: 'nb_rangs',
  exposition: 'exposition',
  type_sol: 'type_sol',
  abri: 'abri',
  paillage: 'paillage',
  pepiniere: 'est_pepiniere',
  statut: 'actif',
}

const OUI_NON = [
  { valeur: 'oui', libelle: 'Oui' },
  { valeur: 'non', libelle: 'Non' },
]

/** Une liste de vocabulaire servie par `GET /plan`, ou rien plutôt qu'une liste inventée. */
function options(vocabulaires, cle) {
  return vocabulaires?.[cle]?.options ?? []
}

/**
 * [E2, E3] Le descripteur de saisie de chaque champ de la carte, dans l'ordre
 * de la lecture — c'est le **même** bloc qui bascule, pas un formulaire.
 *
 * `valeur` est la valeur d'origine du champ, dans la forme que la saisie
 * manipule : une chaîne. `CHOIX_NON_RENSEIGNE` (chaîne vide) y dit « rien »,
 * et c'est ce qui deviendra `null` à l'enregistrement [CA6].
 *
 * `nonRenseignable` marque les champs qui peuvent retourner au silence. Ni la
 * pépinière ni le statut ne le peuvent : ce sont des booléens qui ont toujours
 * une valeur (US-229 / C6).
 */
export function saisieDeParcelle(parcelle, vocabulaires = {}) {
  const pepiniere = Boolean(parcelle?.est_pepiniere)
  const champs = [
    { cle: 'nom', type: SAISIE_TEXTE, valeur: parcelle?.nom ?? '', maxLength: 255, requis: true },
    {
      cle: 'superficie', type: SAISIE_NOMBRE, unite: 'm²',
      valeur: texteNombre(parcelle?.superficie_m2), min: 0, step: 0.1, nonRenseignable: true,
    },
  ]

  // [US-229 / C9] Une pépinière n'a ni longueur, ni largeur, ni rangs qui aient
  // un sens : les trois champs sont RETIRÉS, en lecture comme en édition.
  if (!pepiniere) {
    champs.push(
      {
        cle: 'longueur', type: SAISIE_NOMBRE, unite: 'm',
        valeur: texteNombre(parcelle?.longueur_m),
        // [CA5] Repères de frappe recopiés de la maquette. La règle, elle, est
        // au point d'écriture : un navigateur qui les ignore reçoit le même
        // refus que le compagnon.
        min: 0.5, max: 200, step: 0.1, nonRenseignable: true,
      },
      // [E3] La largeur ne se saisit pas. Sa case le DIT, en teinte secondaire,
      // à la place du champ — elle ne devient pas un champ grisé.
      { cle: 'largeur', type: SAISIE_DEDUITE, texte: TEXTE_LARGEUR_CALCULEE },
      {
        cle: 'nb_rangs', type: SAISIE_NOMBRE,
        valeur: texteNombre(parcelle?.nb_rangs), min: 1, max: 99, step: 1,
        nonRenseignable: true,
      },
    )
  }

  champs.push(
    // [E2, CA3] Les propositions viennent du serveur. La valeur déjà
    // enregistrée y est ajoutée si elle n'y figure pas : une liste d'aide ne
    // doit pas faire disparaître ce que le jardinier avait déclaré.
    champListe('exposition', expositionAffichable(parcelle?.exposition),
               options(vocabulaires, 'exposition')),
    champListe('type_sol', (parcelle?.type_sol || '').trim() || null,
               options(vocabulaires, 'type_sol')),
    // [US-181] « aucun » EST une déclaration : elle reste une option de la
    // liste, à côté du « Non renseigné » qui, lui, remet à `NULL`.
    champListe('abri', (parcelle?.abri || '').trim() || null,
               options(vocabulaires, 'abri')),
    {
      cle: 'paillage', type: SAISIE_OUI_NON, nonRenseignable: true,
      valeur: parcelle?.paillage == null ? CHOIX_NON_RENSEIGNE : (parcelle.paillage ? 'oui' : 'non'),
      options: OUI_NON,
    },
    // [US-229 / C6] Deux booléens qui ont toujours une valeur : pas de
    // « Non renseigné » dans leur liste.
    {
      cle: 'pepiniere', type: SAISIE_OUI_NON, valeur: pepiniere ? 'oui' : 'non',
      options: OUI_NON,
    },
    {
      cle: 'statut', type: SAISIE_OUI_NON,
      valeur: parcelle?.actif === false ? 'non' : 'oui',
      options: [
        { valeur: 'oui', libelle: 'Active' },
        { valeur: 'non', libelle: 'Inactive' },
      ],
    },
  )

  return champs
}

/**
 * Un champ de liste : ses options, et la valeur d'origine ramenée à CELLE d'une
 * option. Sans cela, « sud » en base face à « Sud » dans la liste ouvrirait la
 * saisie sur « Non renseigné », et un simple « Enregistrer » effacerait une
 * exposition que le jardinier n'a jamais touchée.
 */
function champListe(cle, valeur, servies) {
  const liste = avecValeurCourante(servies, valeur)
  return {
    cle, type: SAISIE_LISTE, nonRenseignable: true,
    valeur: valeurDeListe(liste, valeur), options: liste,
  }
}

/** Une valeur numérique telle qu'un champ de saisie la porte — jamais « null ». */
function texteNombre(valeur) {
  return valeur == null ? CHOIX_NON_RENSEIGNE : String(valeur)
}

/** [E2] La valeur déjà enregistrée reste offerte, même hors de la liste servie. */
function avecValeurCourante(liste, valeur) {
  if (!valeur) return liste
  if (correspondante(liste, valeur)) return liste
  return [...liste, { valeur, libelle: capitaliser(valeur) }]
}

/**
 * L'option qui DIT la même chose que la valeur enregistrée, quelle que soit sa
 * casse : « sud » en base et « Sud » dans la liste sont la même exposition. La
 * saisie doit s'ouvrir sur l'option occupée, sinon un simple « Enregistrer »
 * effacerait une valeur que le jardinier n'a pas touchée.
 */
function correspondante(liste, valeur) {
  const v = String(valeur).trim().toLowerCase()
  return liste.find((o) => String(o.valeur).toLowerCase() === v) ?? null
}

/** La valeur d'une liste telle que le `<select>` doit l'avoir : celle d'une option. */
function valeurDeListe(liste, valeur) {
  if (!valeur) return CHOIX_NON_RENSEIGNE
  return correspondante(liste, valeur)?.valeur ?? valeur
}

/** Les valeurs d'origine, prêtes à être comparées à la saisie [CA8]. */
export function valeursInitiales(parcelle, vocabulaires = {}) {
  return Object.fromEntries(
    saisieDeParcelle(parcelle, vocabulaires)
      .filter((c) => c.type !== SAISIE_DEDUITE)
      .map((c) => [c.cle, c.valeur]),
  )
}

/**
 * [E4, CA14] Le corps de l'unique appel d'enregistrement : **seuls** les champs
 * que le jardinier a touchés. Un champ non modifié n'est pas transmis, et
 * n'écrase donc pas ce qu'un autre a pu écrire entre-temps.
 *
 * [CA6] Un champ vidé part à `null` — jamais à `""`, jamais à `false` : « je ne
 * sais pas » n'est pas « non ».
 */
export function chargeUtile(initiales, saisies, parcelle) {
  const pepiniere = Boolean(parcelle?.est_pepiniere)
  const charge = {}
  for (const [cle, valeur] of Object.entries(saisies)) {
    if (!(cle in CHAMP_API)) continue
    if (valeur === initiales[cle]) continue
    // [C9] Les trois champs retirés d'une pépinière ne partent jamais.
    if (pepiniere && ['longueur', 'nb_rangs'].includes(cle)) continue
    charge[CHAMP_API[cle]] = valeurApi(cle, valeur)
  }
  return charge
}

function valeurApi(cle, valeur) {
  const brut = typeof valeur === 'string' ? valeur.trim() : valeur
  if (brut === CHOIX_NON_RENSEIGNE || brut == null) return null
  if (cle === 'nom') return brut
  if (['superficie', 'longueur'].includes(cle)) return Number(String(brut).replace(',', '.'))
  if (cle === 'nb_rangs') return Number(brut)
  // [E2] Trois booléens, dont deux qui savent aussi ne rien valoir.
  if (['paillage', 'pepiniere'].includes(cle)) return brut === 'oui'
  if (cle === 'statut') return brut === 'oui'
  return brut
}

/**
 * [E8, E9] Ce qu'une bascule change AILLEURS, dit avant d'enregistrer — une
 * phrase, jamais une fenêtre de confirmation : le jardinier sait ce qu'il fait,
 * il a seulement besoin de savoir ce que cela entraîne.
 */
export function avertissementsBascule(initiales, saisies) {
  const avis = []
  if (saisies.pepiniere !== initiales.pepiniere) {
    avis.push(
      saisies.pepiniere === 'oui'
        ? 'Cette parcelle sera traitée comme une pépinière : ses semis sortiront du calcul des semis en pleine terre, et ses rangs disparaîtront de sa fiche.'
        : 'Cette parcelle cessera d’être une pépinière : ses semis rentreront dans le calcul des semis en pleine terre, et ses rangs réapparaîtront sur sa fiche.',
    )
  }
  if (saisies.statut !== initiales.statut) {
    avis.push(
      saisies.statut === 'non'
        ? 'Passée en inactive, elle sortira du plan et les gestes qui lui sont rattachés repasseront en « Non localisé ».'
        : 'Repassée en active, elle réapparaîtra dans le plan. Les gestes délocalisés ne lui reviennent pas d’eux-mêmes.',
    )
  }
  return avis
}

/** [E6] Le message bref qui confirme CE QUI a changé, jamais « Enregistré ». */
export function messageConfirmation(modifications = []) {
  if (modifications.length === 0) return 'Aucun changement à enregistrer.'
  if (modifications.length === 1) return `Enregistré — ${modifications[0].toLowerCase()}.`
  return `Enregistré — ${modifications.length} caractéristiques mises à jour.`
}

/** [C8] Reste-t-il une caractéristique à dire sur cette parcelle ? */
export function parcelleACompleter(parcelle) {
  return caracteristiquesDeParcelle(parcelle).some((c) => c.manquant)
}

/**
 * [C7] La ligne d'aide sous la grille : la phrase à dire au compagnon, bâtie
 * avec le NOM RÉEL de la parcelle et, quand un seul champ manque, avec ce
 * champ-là. `phrase` est ce que le bouton de copie place dans le presse-papiers
 * [CA8] ; l'écran l'introduit par « Ou dites au compagnon : ».
 */
export function aideCompagnon(parcelle) {
  const nom = (parcelle?.nom || '').trim() || 'la parcelle'
  const manquants = caracteristiquesDeParcelle(parcelle).filter((c) => c.manquant)
  const seul = manquants.length === 1 ? manquants[0].cle : null
  const exemple = seul ? EXEMPLES[seul] : null
  return {
    phrase: exemple ? exemple(nom) : EXEMPLE_GENERIQUE(nom),
    champ: exemple ? seul : null,
  }
}

// ── [US-222, amendement du 24/09/2026] Le bandeau d'occupation ───────────────
//
// La maquette `Parcelle - Fiche.html` retire les tuiles de culture du niveau 2 :
// dessiner les rangs aux deux niveaux, c'était deux dessins du même objet qu'il
// fallait ensuite garantir identiques. **Le rang vit dans le Plan, la parcelle
// vit dans sa fiche.** Ce qui reste ici est un bandeau : combien de rangs sont
// occupés, lesquels, par quelles cultures — et un chemin vers le Plan.

/**
 * [D5b] Le bandeau sous l'en-tête : l'occupation en rangs, les cases, les NOMS
 * des cultures présentes — et rien de plus. Ni quantité, ni variété, ni frise,
 * ni confiance : elles se lisent dans le Plan et dans la fiche culture.
 */
export function bandeauOccupation(parcelle) {
  const disposition = parcelle?.disposition ?? {}
  const pepiniere = Boolean(parcelle?.est_pepiniere)
  const rangs = pepiniere ? [] : rangsDeLaCarte(parcelle)
  const noms = []
  for (const c of parcelle?.cultures ?? []) {
    const nom = capitaliser(c.culture || '')
    if (nom && !noms.includes(nom)) noms.push(nom)
  }
  const sansNbRangs = !pepiniere && disposition.rangs_declares == null
  return {
    occupation: occupationDetail(parcelle),
    depassement: pepiniere ? 0 : disposition.depassement ?? 0,
    // [D5b] Une case par rang, occupée ou libre — le dessin le plus court qui
    // dise l'occupation, sans redevenir une grille de tuiles.
    cases: rangs.map((r) => ({ numero: r.numero, libre: Boolean(r.libre) })),
    cultures: noms,
    libre: !pepiniere && noms.length === 0,
    pepiniere,
    // [D4] Une parcelle sans nombre de rangs porte sa mention ICI.
    mention: sansNbRangs ? MENTION_SANS_RANGS : null,
  }
}

// ── [US-232] La carte « Sol et entretien » ───────────────────────────────────
//
// Ces gestes sont déjà enregistrés — un paillage, un apport de compost, un
// binage sont des événements rattachés à une parcelle. Cette carte n'invente
// aucun enregistrement : elle donne à lire, à l'échelle de la planche, ce que
// le journal noie dans l'ordre du temps, toutes parcelles confondues.
//
// La LISTE des gestes retenus n'est pas ici : elle est dans le domaine
// (`app/services/evenements.GESTES_SOL`), servie par `GET /plan`, et c'est la
// même qui part filtrer le Journal [CA2].

/** [S6] Ce que dit une parcelle dont le sol n'a jamais rien reçu. */
export const AUCUNE_INTERVENTION_SOL = 'Rien d’enregistré sur le sol de cette parcelle'

/** [S3] Les gestes de sol, au singulier, tels qu'une ligne les nomme. */
export const LIBELLE_GESTE_SOL = {
  paillage: 'Paillage',
  amendement: 'Amendement',
  desherbage: 'Désherbage',
  binage: 'Binage',
}

const MOIS_COURTS = [
  'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
  'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.',
]

/**
 * [S2] La date d'une intervention : jour et mois. L'année n'apparaît que si
 * l'intervention n'est PAS de la campagne en cours — celle de la date de
 * référence de l'écran, jamais celle de l'horloge du navigateur.
 */
export function dateIntervention(iso, dateRef) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''))
  if (!m) return ''
  const [, annee, mois, jour] = m
  const court = `${Number(jour)} ${MOIS_COURTS[Number(mois) - 1] ?? ''}`.trim()
  const campagne = /^(\d{4})/.exec(String(dateRef || ''))?.[1]
  return campagne && annee === campagne ? court : `${court} ${annee}`
}

/**
 * [S3] Le libellé d'une intervention : le geste tel qu'il a été enregistré,
 * avec sa précision quand elle existe et son rang quand l'événement en porte
 * un. Rien n'est comblé — « Binage » tout court est une ligne valide.
 */
export function libelleIntervention(ev) {
  const geste = LIBELLE_GESTE_SOL[ev?.type_action]
    || capitaliser((ev?.type_action || '').replace(/_/g, ' ')) || 'Intervention'
  const precision = (ev?.commentaire || ev?.traitement || '').trim()
  let texte = precision ? `${geste} ${precision}` : geste
  if (ev?.quantite != null) {
    texte += `, ${nombre(ev.quantite)}${ev.unite ? ` ${ev.unite}` : ''}`
  }
  // [S3] Le rang, quand l'événement en porte un — la parcelle entière sinon.
  if (ev?.rang != null) texte += ` sur R${ev.rang}`
  return texte
}

/**
 * [S1, S5, S6, S7] La carte entière, prête à rendre.
 *
 * `toutVoir` n'est vrai que s'il RESTE quelque chose à voir : la carte montre
 * les huit dernières, et le lien vers le Journal n'apparaît qu'au-delà.
 * `filtre` est ce que ce lien emporte — la parcelle et la liste des gestes,
 * celle-là même que le serveur a servie [CA2].
 */
export function carteSol(parcelle, { dateRef = null, gestesSol = [] } = {}) {
  const sol = parcelle?.sol ?? {}
  const brutes = sol.interventions ?? []
  const total = sol.total ?? brutes.length
  const lignes = brutes.map((ev) => ({
    id: ev.id,
    date: dateIntervention(ev.date, dateRef),
    libelle: libelleIntervention(ev),
  }))
  const nom = (parcelle?.nom || '').trim()
  return {
    lignes,
    total,
    vide: lignes.length === 0,
    // [S6] L'absence est DITE, la carte n'est pas masquée.
    message: lignes.length === 0 ? AUCUNE_INTERVENTION_SOL : null,
    toutVoir: total > lignes.length,
    filtre: { parcelle: nom, gestes: gestesSol.join(',') },
    // [S7] La phrase à dire au compagnon, bâtie avec le nom RÉEL de la parcelle
    // — la même grammaire que celle du bouton (« paillage parcelle X »).
    aide: { phrase: `paillage parcelle ${nom || 'la parcelle'}` },
  }
}

// ── [US-231] La carte « Rotation » ───────────────────────────────────────────
//
// L'application savait déjà évaluer une rotation (US-163) — mais seulement à
// l'instant où l'on plante. Cette carte donne le même savoir à lire **à froid**,
// quand on prépare la saison : trois campagnes derrière, la campagne à venir
// devant, et ce qui s'y répète.
//
// Rien ne se calcule ici [CA1] : les colonnes, l'alerte de répétition, le
// conseil de l'année à venir et les mentions d'absence viennent tels quels de
// `app/services/rotation.py`, servis par `GET /plan`. Ce module ne fait que
// choisir les mots de mise en page — le titre d'une colonne, la teinte d'une
// vignette — et laisse au serveur le dernier mot sur le SENS.

/** [R4] Ce que porte en tête la colonne de l'année à venir. */
export const LIBELLE_CONSEILLE = 'Conseillé'

/** [R8] Une pépinière n'a pas de rotation : la carte n'est pas rendue. */
export function aUneRotation(parcelle) {
  return !parcelle?.est_pepiniere && Boolean(parcelle?.rotation)
}

/**
 * [R1, R2, R4, R5, R6, R7, CA5] La carte « Rotation », prête à rendre.
 *
 * Rend `null` quand la carte n'a pas lieu d'être (pépinière, ou bloc absent
 * d'une réponse plus ancienne) — l'écran n'invente pas une grille vide.
 *
 * Une colonne porte :
 * - `annee`      : l'année, en tête de colonne (ou de ligne à 375 px, R9) ;
 * - `libelle`    : `LIBELLE_CONSEILLE` pour la campagne à venir, sinon null ;
 * - `conseil`    : true pour la colonne en pointillés (R4) ;
 * - `vignettes`  : une par famille, teintée par son NOM (R3) ;
 * - `vide`       : l'année sans donnée, qui se dit vide et ne se saute pas (R6).
 */
export function rotationDeParcelle(parcelle) {
  if (!aUneRotation(parcelle)) return null
  const rotation = parcelle.rotation
  const colonnes = (rotation.campagnes ?? []).map((campagne) => ({
    annee: campagne.annee,
    libelle: null,
    conseil: false,
    vide: (campagne.familles ?? []).length === 0,
    vignettes: (campagne.familles ?? []).map((famille) => vignette(famille)),
  }))

  // [R4] La quatrième colonne : l'année à venir, en pointillés, « Conseillé ».
  const conseil = rotation.conseil ?? {}
  colonnes.push({
    annee: conseil.annee ?? rotation.campagne_a_venir,
    libelle: LIBELLE_CONSEILLE,
    conseil: true,
    vide: (conseil.familles ?? []).length === 0,
    // [CA8] Aucune culture nommée dans la colonne de conseil : ce sont des
    // familles possibles, pas des gestes à faire — rien n'y est actionnable.
    vignettes: (conseil.familles ?? []).map((famille) => ({
      ...vignette(famille),
      cultures: [],
      // La raison du feu vert, dite en clair plutôt que sous-entendue.
      note: famille.derniere_campagne == null
        ? `jamais cultivée ici · retour ${famille.delai_retour_annees} an${famille.delai_retour_annees > 1 ? 's' : ''}`
        : `dernière fois en ${famille.derniere_campagne} · retour ${famille.delai_retour_annees} an${famille.delai_retour_annees > 1 ? 's' : ''}`,
    })),
  })

  return {
    colonnes,
    // [R5] En teinte d'alerte, sous la grille — le seul endroit de la carte où
    // une couleur porte un jugement (R3).
    alertes: rotation.alertes ?? [],
    // [R6, R7] Les deux absences que la carte dit en une ligne, telles que le
    // service les formule : aucun antécédent, et famille non renseignée.
    mentionAucunAntecedent: rotation.mention_aucun_antecedent ?? null,
    mentionFamillesInconnues: rotation.mention_familles_inconnues ?? null,
    mentionConseil: conseil.mention ?? null,
  }
}

/** [R2, R3, R7] Une vignette de famille : son nom, ses cultures, sa teinte. */
function vignette(famille) {
  const inconnue = Boolean(famille.inconnue)
  return {
    famille: famille.famille,
    familleId: famille.famille_id ?? null,
    inconnue,
    cultures: (famille.cultures ?? []).map((c) => capitaliser(c)),
    // [R3] La teinte vient du NOM : la même famille garde la même couleur d'une
    // parcelle à l'autre et d'une année à l'autre, sans jamais porter de
    // jugement. Une lacune reste neutre.
    teinte: teinteFamille(famille.famille, { inconnue }),
    note: null,
  }
}
