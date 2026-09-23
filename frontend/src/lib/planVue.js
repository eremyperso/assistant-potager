// [US-200] Règles de rendu de la Vue plan — longueurs de trait, segments de
// poquet, libellés de rang, en-têtes de carte et pied de vue.
//
// Aucune de ces fonctions ne connaît React : elles ne manipulent que la charge
// utile de `GET /plan`, sur le modèle de `plan.js` et `pepiniere.js`, pour être
// vérifiables par `npm test` (`node --test`).
//
// ⚠️ Rien n'est recalculé ici de ce que le serveur a déjà décidé : la
// répartition en rangs (US-198), la phase du moment (US-194) et les totaux
// arrivent tels quels. Cette lib ne fait que de la **mise en forme** — la
// longueur d'un trait est du dessin, pas de l'agronomie
// (`docs/domaines/plan-et-rangs.md`, « Il ne dessine rien »).
import { formatUnite } from './plan.js'
import { phase as lirePhase, PHASE_LIBRE } from './phases.js'

/** [V3] Plancher d'un trait : sous 12 %, un rang ne se voit ni ne se vise. */
export const PLANCHER_PCT = 12
/** [V3, A2] Plafond : le rang le plus fourni fait la largeur, jamais plus. */
export const PLAFOND_PCT = 100
/** [V4] Au-delà de douze poquets, on n'en dessine plus : on l'écrit. */
export const MAX_SEGMENTS = 12

/** [V4] Les trois modes d'implantation, tels que `repartition_rangs.py` les nomme. */
export const MODE_RANG = 'rang'
export const MODE_SURFACE = 'surface'
export const MODE_POQUET = 'poquet'

/** [US-228 / P2] Sept repères proportionnels, sans équivalence en plants. */
export const MAX_FENTES = 7
/** [P3] Une seule place prise reste visible : 8 % de remplissage au minimum. */
export const PLANCHER_REMPLISSAGE_PCT = 8

/** [P1, P6, P7, P9] Les quatre dessins possibles d'un rang. */
export const PISTE_PLACES = 'places'
export const PISTE_LIGNE = 'ligne'
export const PISTE_DEGRADE = 'degrade'
export const PISTE_LIBRE = 'libre'

/** [V9] Ce qu'une carte dit quand son dénominateur manque — jamais « 0 rang ». */
export const MENTION_SANS_RANGS = 'nombre de rangs non renseigné'

/** [P12] Ce qu'une carte dit quand la longueur manque — jamais « 0 place ». */
export const MENTION_SANS_LONGUEUR =
  'longueur non renseignée : les places ne peuvent pas être calculées'

/** [V8] US-208 n'ayant pas encore livré le type de pépinière, il est « non renseigné ». */
export const TYPE_PEPINIERE_INCONNU = 'type non renseigné'

// ── Mise en forme élémentaire ────────────────────────────────────────────────

/**
 * Un nombre tel qu'il s'écrit en français : virgule décimale, pas de zéro
 * inutile. `44.5 → « 44,5 »`, `8 → « 8 »`.
 */
export function nombre(valeur, decimales = 1) {
  if (valeur == null || Number.isNaN(Number(valeur))) return ''
  const n = Number(valeur)
  const facteur = 10 ** decimales
  const texte = Number.isInteger(n) ? String(n) : String(Math.round(n * facteur) / facteur)
  return texte.replace('.', ',')
}

/**
 * [V6] La quantité d'un rang telle qu'elle s'écrit à côté du trait : « 8 plants »,
 * « 2 m² », « 5 poquets ». C'est elle qui rend l'échelle inoffensive (wireframe
 * v3) — un trait ne se lit jamais sans son chiffre.
 */
export function quantiteTexte(quantite, unite) {
  const q = nombre(quantite)
  if (!q) return ''
  const u = formatUnite(unite)
  return u ? `${q} ${u}` : q
}

/** Abréviations du rendu à 375 px [CA6] — le mot complet reste dans le nom accessible. */
const UNITES_COURTES = Object.freeze({
  plants: 'pl.', plant: 'pl.', pieds: 'pl.', pied: 'pl.',
  poquets: 'poq.', poquet: 'poq.',
  graines: 'gr.', graine: 'gr.',
})

export function uniteCourte(unite) {
  const u = formatUnite(unite)
  return UNITES_COURTES[(u || '').trim().toLowerCase()] || u
}

export function quantiteTexteCourt(quantite, unite) {
  const q = nombre(quantite)
  if (!q) return ''
  const u = uniteCourte(unite)
  return u ? `${q} ${u}` : q
}

/** Première lettre en capitale, sans toucher au reste — les noms viennent en minuscules. */
export function capitaliser(mot) {
  const m = (mot || '').trim()
  return m ? m[0].toUpperCase() + m.slice(1) : ''
}

/**
 * Clé de comparaison d'une unité : `m2` et `m²` sont la même unité, la casse ne
 * compte pas. C'est elle qui borne la comparaison des traits [V3].
 */
export function cleUnite(unite) {
  return formatUnite(unite || '').trim().toLowerCase()
}

// ── Longueur d'un trait ──────────────────────────────────────────────────────

/**
 * [V3] Quantité par rang la plus forte de la parcelle, **par unité**. Un trait
 * de plants ne se compare jamais à un trait de m² : chaque unité a son propre
 * maximum, sans quoi le dessin promettrait une précision qui n'existe pas.
 */
export function maximaParUnite(cultures = []) {
  const maxima = {}
  for (const c of cultures) {
    if (!c?.numeros_rangs?.length) continue
    const cle = cleUnite(c.unite)
    const q = Number(c.quantite_par_rang) || 0
    if (q > (maxima[cle] ?? 0)) maxima[cle] = q
  }
  return maxima
}

/**
 * [V4] Segments d'un rang en poquets : un segment par poquet, douze au plus.
 * Au-delà, douze segments et « ×18 » écrit à côté — on ne compte pas à l'écran.
 */
export function segmentsPoquet(quantite) {
  const n = Math.max(1, Math.round(Number(quantite) || 0))
  return { segments: Math.min(MAX_SEGMENTS, n), exces: n > MAX_SEGMENTS ? `×${n}` : null }
}

/**
 * [V3, V4, A2] Longueur du trait d'un rang, en pourcentage de la largeur utile.
 *
 * - modes *rang* et *surface* : part de la quantité du rang dans le rang le plus
 *   fourni de la parcelle **à unité égale**, plancher 12 %, plafond 100 % ;
 * - mode *poquet* : la longueur est celle des segments — douze segments font la
 *   largeur entière, un seul poquet en fait donc un douzième. Le plancher ne
 *   s'y applique pas : un segment est visible par construction, l'allonger
 *   ferait croire à plus de poquets qu'il n'y en a.
 */
export function longueurRang(ligne, maxima = {}) {
  if (!ligne) return 0
  const quantite = Number(ligne.quantite_par_rang) || 0
  if (ligne.mode_implantation === MODE_POQUET) {
    return (segmentsPoquet(quantite).segments / MAX_SEGMENTS) * PLAFOND_PCT
  }
  const max = maxima[cleUnite(ligne.unite)] ?? 0
  if (max <= 0 || quantite <= 0) return PLANCHER_PCT
  const brut = (quantite / max) * PLAFOND_PCT
  return Math.min(PLAFOND_PCT, Math.max(PLANCHER_PCT, arrondiPair(brut)))
}

/**
 * Arrondi à l'entier, **les demis vers le pair**. C'est l'arrondi des deux
 * exemples de référence du wireframe v3 et du Gherkin de l'US : 3 plants sur 8
 * font 38 % (37,5 → 38) et 5 sur 8 font 62 % (62,5 → 62). `Math.round`, qui
 * pousse tous les demis vers le haut, allongerait systématiquement les traits
 * d'un demi-point — invisible à l'œil, mais faux au test de référence.
 */
export function arrondiPair(valeur) {
  const bas = Math.floor(valeur)
  const reste = valeur - bas
  if (reste > 0.5) return bas + 1
  if (reste < 0.5) return bas
  return bas % 2 === 0 ? bas : bas + 1
}

// ── La piste des places [US-228 / P1 à P9] ───────────────────────────────────

/**
 * [P7] Un semis en ligne se mesure en mètres, pas en pieds : c'est la seule
 * unité qui remplit une piste sans qu'aucune place n'y soit comptée (US-199).
 */
export function estSemisEnLigne(unite) {
  return cleUnite(unite) === 'ml'
}

/**
 * [P1 à P9] Le dessin d'un rang : combien de fentes, combien de pleines, et
 * jusqu'où va le remplissage coloré.
 *
 * Quatre variantes, et le serveur seul décide laquelle s'applique — rien n'est
 * recalculé ici (RT7) : les places, les prises et le dépassement viennent de
 * `GET /plan` (US-227).
 *
 * - `places`  : sept repères pour la proportion occupée [P1, P2, P3, P4]
 * - `ligne`   : un semis en ligne, rempli à la part semée [P7]
 * - `degrade` : places non calculables — la longueur relative d'US-200 [P6, P8]
 * - `libre`   : tout en creux, pointillé [P9]
 */
export function pisteDuRang(rang) {
  const vide = {
    variante: PISTE_DEGRADE, fentes: 0, pleines: 0,
    remplissage: 0, exces: null, legende: null,
  }
  if (!rang) return vide

  // [P9] Un rang libre n'a pas de places : elles dépendraient de ce qu'on y
  // mettrait. La piste est entièrement en creux.
  if (rang.libre) return { ...vide, variante: PISTE_LIBRE, fentes: MAX_FENTES }

  // [P7] La part semée est calculée par le serveur (US-227 / R15), plafonnée à 1.
  if (estSemisEnLigne(rang.unite)) {
    const part = Math.min(1, Math.max(0, Number(rang.partSemee) || 0))
    return {
      variante: PISTE_LIGNE,
      fentes: MAX_FENTES,
      pleines: part > 0 ? Math.max(1, Math.round(part * MAX_FENTES)) : 0,
      remplissage: part > 0 ? Math.max(PLANCHER_REMPLISSAGE_PCT, Math.round(part * PLAFOND_PCT)) : 0,
      exces: null,
      legende: null,
    }
  }

  // [P6, P8] Places non calculables, ou semis en surface : la piste retombe sur
  // la longueur relative d'US-200 / V3, sans aucune place en creux. Un écran du
  // premier jour est donc exactement l'écran d'US-200 (CA9).
  const places = Number(rang.places) || 0
  if (rang.mode === MODE_SURFACE || places <= 0) {
    return { ...vide, remplissage: rang.longueur ?? 0 }
  }

  const prises = Math.max(0, Number(rang.placesPrises) || 0)
  const exces = Number(rang.depassementPlaces) || 0
  return {
    variante: PISTE_PLACES,
    fentes: MAX_FENTES,
    pleines: prises > 0 ? Math.min(MAX_FENTES, Math.max(1, Math.round(prises / places * MAX_FENTES))) : 0,
    // [P3] Une seule place prise sur vingt-quatre ferait un filet invisible :
    // le plancher de lisibilité la montre, et le chiffre de droite dit le vrai.
    remplissage: prises > 0
      ? Math.min(PLAFOND_PCT, Math.max(PLANCHER_REMPLISSAGE_PCT, Math.round((prises / places) * PLAFOND_PCT)))
      : 0,
    // [P4] Le dépassement est un signalement : la piste est pleine, « +N » en
    // pastille, et la quantité déclarée reste écrite telle quelle.
    exces: exces > 0 ? exces : null,
    legende: null,
  }
}

/**
 * [P5] La colonne de reste, à droite de la piste : « reste **15** plants »,
 * « **4** en trop » en teinte d'alerte, « **8** places ? » en mode dégradé, ou
 * rien du tout — un semis en ligne et un rang libre n'ont pas de reste.
 */
export function resteDuRang(rang, piste = pisteDuRang(rang)) {
  if (!rang || rang.libre || piste.variante === PISTE_LIGNE) return null

  if (piste.variante === PISTE_PLACES) {
    if (piste.exces) return { prefixe: '', valeur: String(piste.exces), unite: 'en trop', alerte: true }
    const restantes = Math.max(0, Number(rang.placesRestantes) || 0)
    return {
      prefixe: 'reste',
      valeur: String(restantes),
      unite: formatUnite(rang.unite) || 'places',
      alerte: false,
    }
  }

  // [P6] Mode dégradé : la quantité, suivie du point d'interrogation qui dit
  // que les places, elles, ne sont pas connues.
  const quantite = nombre(rang.quantite)
  return quantite ? { prefixe: '', valeur: quantite, unite: 'places ?', alerte: false } : null
}

/**
 * [P10] La seconde ligne du libellé : la quantité avec son unité et, si elle est
 * connue, l'espacement sur le rang — que le composant fait précéder du
 * pictogramme de cote, le même que celui de l'en-tête de carte (P11).
 */
export function sousLibelleRang(rang) {
  if (!rang || rang.libre) return null
  const quantite = estSemisEnLigne(rang.unite)
    ? `${nombre(rang.quantite)} m semés`
    : quantiteTexte(rang.quantite, rang.unite)
  return { quantite, espacement: rang.espacement ? `${nombre(rang.espacement)} cm` : null }
}

/**
 * [P9] Ce qu'un rang libre dit sous son libellé : sa longueur et, s'il y a dans
 * la parcelle une culture à l'espacement renseigné, ce que ce rang en porterait
 * — « 12 m · ex. 24 tomates ». Jamais d'exemple sans culture de référence.
 */
export function sousLibelleLibre(rang) {
  if (!rang?.libre) return null
  const morceaux = []
  if (rang.longueurM) morceaux.push(`${nombre(rang.longueurM)} m`)
  const exemple = rang.capaciteExemple
  if (exemple?.nombre && exemple?.culture) {
    const pluriel = exemple.nombre > 1 && !/s$/i.test(exemple.culture) ? 's' : ''
    morceaux.push(`ex. ${exemple.nombre} ${exemple.culture}${pluriel}`)
  }
  return morceaux.join(' · ') || null
}

// ── Rangs d'une carte ────────────────────────────────────────────────────────

/**
 * [V12, A5] Libellé d'un rang. Le premier rang d'une culture porte tout —
 * culture, variété si connue, quantité et unité ; les rangs suivants de la même
 * culture sont regroupés visuellement et n'en gardent que la quantité.
 */
export function libelleRang(rang) {
  if (!rang) return ''
  if (rang.libre) return 'libre'
  const quantite = quantiteTexte(rang.quantite, rang.unite)
  if (rang.suite) return quantite
  const nom = [capitaliser(rang.culture), rang.variete].filter(Boolean).join(' ')
  return [nom, quantite].filter(Boolean).join(' · ')
}

/** [CA6] Le même libellé à 375 px : la variété saute, l'unité s'abrège. */
export function libelleRangCourt(rang) {
  if (!rang) return ''
  if (rang.libre) return 'libre'
  const quantite = quantiteTexteCourt(rang.quantite, rang.unite)
  if (rang.suite) return quantite
  return [capitaliser(rang.culture), quantite].filter(Boolean).join(' · ')
}

/**
 * [US-200, retour de terrain] Ce qui réconcilie l'écran avec la base, sur le
 * premier rang d'une ligne posée sur plusieurs rangs : « 70 graines sur
 * 4 rangs ».
 *
 * La quantité par rang est un quotient ARRONDI (R3) : 70 ÷ 4 donne 18, et
 * quatre rangs de 18 se relisent 72. Sans le total, l'écran se contredit sans
 * le dire. Vide pour une ligne sur un seul rang — le libellé porte déjà tout.
 */
export function totalLigne(rang) {
  // Sur le PREMIER rang de la ligne seulement : répété sur chacun, il ferait
  // croire à autant de lignes distinctes de 18 plants.
  if (!rang || rang.libre || rang.suite || (rang.nbRangsLigne ?? 0) < 2) return ''
  const total = quantiteTexte(rang.quantiteTotale, rang.unite)
  if (!total) return ''
  return `${total} sur ${rang.nbRangsLigne} rangs`
}

/**
 * [CA10, V16] Le nom accessible d'un rang dit TOUT : « Rang 2, tomate cerise,
 * 5 plants, en place ». Le trait est décoratif, la couleur ne porte rien seule —
 * ce texte est ce qu'entend un lecteur d'écran et ce que lit un œil en niveaux
 * de gris.
 */
export function nomAccessibleRang(rang) {
  if (!rang) return ''
  const morceaux = [`Rang ${rang.numero}`]
  if (rang.libre) {
    morceaux.push('libre')
    // [CA10, P9] La longueur et la capacité d'exemple se disent aussi : elles
    // sont tout ce qu'un rang libre a d'information.
    const sous = sousLibelleLibre(rang)
    if (sous) morceaux.push(sous.replace('ex.', 'par exemple'))
    return morceaux.join(', ')
  }
  const nom = [rang.culture, rang.variete].filter(Boolean).join(' ')
  if (nom) morceaux.push(nom)
  const quantite = estSemisEnLigne(rang.unite)
    ? `${nombre(rang.quantite)} mètres semés`
    : quantiteTexte(rang.quantite, rang.unite)
  if (quantite) morceaux.push(quantite)
  // [CA10] « 9 plants sur 24 places, 15 restantes » — ce que le dessin montre
  // est dit en toutes lettres, parce que la piste est décorative (aria-hidden).
  if (rang.places) {
    morceaux.push(`sur ${rang.places} places`)
    if ((rang.depassementPlaces ?? 0) > 0) morceaux.push(`${rang.depassementPlaces} en trop`)
    else morceaux.push(`${rang.placesRestantes ?? 0} restantes`)
  }
  // Une ligne sur plusieurs rangs dit son total : « 18 graines » lu quatre fois
  // ne fait pas 70 sans lui.
  const total = totalLigne(rang)
  if (total) morceaux.push(`${total} au total`)
  if (rang.exces) morceaux.push(`${rang.exces.replace('×', '')} poquets`)
  const p = lirePhase(rang.phase)
  if (p) morceaux.push(p.court)
  return morceaux.join(', ')
}

/**
 * [V2, V7, V12] Les rangs d'une carte, du rang 1 au dernier, prêts à dessiner.
 *
 * Construits depuis `cultures[].numeros_rangs` — la répartition d'US-198 — et
 * avec les quantités propres à `disposition.rangs`, qui ne porte pas la phase : deux
 * lignes ne se distinguant que par la nature du geste (semis / plantation) y
 * seraient indiscernables. Les rangs libres, eux, viennent de la disposition,
 * seule à connaître le dénominateur déclaré.
 */
export function rangsDeLaCarte(parcelle) {
  const cultures = parcelle?.cultures ?? []
  const maxima = maximaParUnite(cultures)
  const rangs = []
  // [US-227] Les places, elles, vivent sur `disposition.rangs` — seul endroit
  // où le serveur les calcule. La ligne de culture dit QUOI, la disposition dit
  // COMBIEN il en tient : l'index rapproche les deux sans rien recalculer.
  const places = new Map((parcelle?.disposition?.rangs ?? []).map((r) => [r.numero, r]))

  for (const c of cultures) {
    const numeros = c?.numeros_rangs ?? []
    const mode = c.mode_implantation || MODE_RANG
    const longueur = longueurRang(c, maxima)
    const { segments, exces } =
      mode === MODE_POQUET ? segmentsPoquet(c.quantite_par_rang) : { segments: 0, exces: null }

    numeros.forEach((numero, i) => {
      const chiffres = places.get(numero) ?? {}
      const rang = {
        numero,
        numeroCourt: `R${numero}`,
        libre: false,
        // [V12] Rang suivant d'une culture posée sur plusieurs rangs : groupé
        // avec le précédent, libellé réduit à la quantité.
        suite: i > 0 && numeros[i - 1] === numero - 1,
        dernierDuGroupe: numeros[i + 1] !== numero + 1,
        culture: c.culture || '',
        variete: c.variete || '',
        quantite: chiffres.quantite_par_rang ?? c.quantite_par_rang,
        // [US-200, retour de terrain] Le TOTAL réel de la ligne, à côté de la
        // part d'un rang. Sans lui, l'écran ne se recoupe pas : une ligne de
        // 70 graines sur 4 rangs affiche « 18 graines » quatre fois, et le
        // jardinier recompose 72. La quantité par rang est arrondie (R3) — le
        // total, lui, est celui de la base.
        quantiteTotale: c.nb_plants,
        nbRangsLigne: numeros.length,
        unite: c.unite,
        mode,
        longueur,
        segments,
        exces,
        // [US-227 / CA2] Tels quels, jamais recalculés (RT7).
        places: chiffres.places ?? null,
        placesPrises: chiffres.places_prises ?? null,
        placesRestantes: chiffres.places_restantes ?? null,
        depassementPlaces: chiffres.depassement_places ?? null,
        espacement: chiffres.espacement_rang_cm ?? c.espacement_rang_cm ?? null,
        partSemee: chiffres.part_semee ?? null,
        metresRestants: chiffres.metres_restants ?? null,
        phase: c.phase ?? null,
        phase_depuis: c.phase_depuis ?? null,
        phase_depuis_nature: c.phase_depuis_nature ?? null,
        nb_series: c.nb_series ?? null,
      }
      rang.libelle = libelleRang(rang)
      rang.libelleCourt = libelleRangCourt(rang)
      rang.total = totalLigne(rang)
      rang.piste = pisteDuRang(rang)
      rang.reste = resteDuRang(rang, rang.piste)
      rang.sousLibelle = sousLibelleRang(rang)
      rang.nomAccessible = nomAccessibleRang(rang)
      rangs.push(rang)
    })
  }

  // [V7] Les rangs libres : trait pointillé, mot « libre ». Ils n'existent que
  // si le nombre de rangs est déclaré — sans dénominateur, aucun rang libre (V9).
  for (const r of parcelle?.disposition?.rangs ?? []) {
    if (!r.libre) continue
    const rang = {
      longueurM: r.longueur_m ?? null,
      capaciteExemple: r.capacite_exemple ?? null,
      numero: r.numero,
      numeroCourt: `R${r.numero}`,
      libre: true,
      total: '',
      quantiteTotale: null,
      nbRangsLigne: 0,
      suite: false,
      dernierDuGroupe: true,
      culture: '',
      variete: '',
      quantite: null,
      unite: null,
      mode: null,
      longueur: PLAFOND_PCT,
      segments: 0,
      exces: null,
      phase: null,
    }
    rang.libelle = libelleRang(rang)
    rang.libelleCourt = libelleRangCourt(rang)
    rang.piste = pisteDuRang(rang)
    rang.reste = null
    rang.sousLibelle = null
    rang.sousLibelleLibre = sousLibelleLibre(rang)
    rang.nomAccessible = nomAccessibleRang(rang)
    rangs.push(rang)
  }

  return rangs.sort((a, b) => a.numero - b.numero)
}

// ── En-tête et carte ─────────────────────────────────────────────────────────

/** [V11] « 12 m² », ou la mention explicite d'une superficie jamais déclarée. */
export function superficieTexte(parcelle) {
  return parcelle?.superficie_m2 ? `${nombre(parcelle.superficie_m2)} m²` : 'superficie non renseignée'
}

/**
 * [V11, V10] Le compteur de rangs de l'en-tête : « 4 rangs sur 5 » d'ordinaire,
 * « 6 rangs occupés pour 5 déclarés » en dépassement — aucune culture n'est
 * masquée, c'est la carte qui porte l'écart —, et le nombre seul quand le
 * dénominateur manque [V9].
 */
export function compteurRangs(disposition) {
  const occupes = disposition?.rangs_occupes ?? 0
  const declares = disposition?.rangs_declares
  if (declares == null) return `${occupes} rang${occupes > 1 ? 's' : ''} occupé${occupes > 1 ? 's' : ''}`
  if ((disposition?.depassement ?? 0) > 0) {
    return `${occupes} rangs occupés pour ${declares} déclaré${declares > 1 ? 's' : ''}`
  }
  return `${occupes} rang${occupes > 1 ? 's' : ''} sur ${declares}`
}

/**
 * [V9, A6] La phrase à dire au compagnon pour déclarer le nombre de rangs
 * manquant. L'écran ne propose jamais de corriger la donnée lui-même : la
 * saisie reste au compagnon (`parcelles-et-plan.md`, « Dire combien de rangs »).
 */
export function phraseNbRangs(parcelle) {
  return `Dites au compagnon : « ${parcelle?.nom || 'la parcelle'} a 5 rangs ».`
}

/**
 * [P12] La phrase à dire pour déclarer la longueur manquante — la forme exacte
 * que la grammaire du compagnon reconnaît (US-225 / CA3), avec le nom de la
 * parcelle dedans. L'écran ne propose jamais de saisir la valeur lui-même.
 */
export function phraseLongueur(parcelle) {
  return `Dites au compagnon : « ${parcelle?.nom || 'la parcelle'} a des rangs de 12 m ».`
}

/**
 * [P11] Les dimensions de l'en-tête : « rangs de 12 m · largeur 5,75 m déduite ».
 *
 * La largeur ne se déclare pas (US-225 / CA6) : elle se déduit de la superficie
 * et l'en-tête le dit. Incohérente (CA7) — une planche de 5 m² annoncée longue
 * de 100 m —, elle est remplacée par la mention de l'incohérence, **jamais par
 * un chiffre corrigé** : l'écran ne sait pas laquelle des deux valeurs est fausse.
 */
export function dimensionsTexte(parcelle) {
  if (!parcelle?.longueur_m) return null
  const longueur = `rangs de ${nombre(parcelle.longueur_m)} m`
  if (parcelle.largeur_incoherente) return `${longueur} · largeur incohérente, à vérifier`
  if (parcelle.largeur_m == null) return longueur
  return `${longueur} · largeur ${nombre(parcelle.largeur_m, 2)} m déduite`
}

/** [P11] Les quatre informations d'en-tête, sans inventer les mesures absentes. */
export function indicateursParcelle(parcelle) {
  const disposition = parcelle?.disposition ?? {}
  const sansSurface = !parcelle?.superficie_m2
  const indicateurs = [{
    cle: 'surface', titre: 'Superficie', alerte: sansSurface,
    texte: sansSurface ? '? m²' : superficieTexte(parcelle),
  }]
  if (parcelle?.est_pepiniere) return indicateurs
  const sansLongueur = !parcelle?.longueur_m
  const sansLargeur = parcelle?.largeur_m == null
  const incoherente = Boolean(parcelle?.largeur_incoherente)
  const sansRangs = disposition.rangs_declares == null
  const occupes = disposition.rangs_occupes ?? 0
  return [...indicateurs, {
    cle: 'longueur', titre: 'Longueur de rang', alerte: sansLongueur,
    texte: sansLongueur ? 'longueur ?' : `rangs de ${nombre(parcelle.longueur_m)} m`,
  }, {
    cle: 'largeur', titre: 'Largeur de la parcelle, déduite de la superficie et de la longueur',
    alerte: sansLargeur || incoherente,
    texte: incoherente ? 'largeur incohérente, à vérifier' : sansLargeur ? 'largeur ?' : `largeur ${nombre(parcelle.largeur_m, 2)} m`,
  }, {
    cle: 'rangs', titre: 'Nombre de rangs', alerte: sansRangs,
    texte: sansRangs ? `${compteurRangs(disposition)} · total ?`
      : `Total ${disposition.rangs_declares} rang${disposition.rangs_declares > 1 ? 's' : ''} (${occupes} occupé${occupes > 1 ? 's' : ''})`,
  }]
}

/** [V1, V8, V9, V10] Une carte de parcelle, prête à dessiner. */
export function carteDeParcelle(parcelle) {
  const disposition = parcelle?.disposition ?? {}
  const sansNbRangs = disposition.rangs_declares == null
  // [P12] Les deux absences se cumulent sans se répéter : une parcelle peut
  // n'avoir ni nombre de rangs ni longueur, et chacune a sa phrase.
  const sansLongueur = parcelle?.longueur_m == null
  const pepiniere = Boolean(parcelle?.est_pepiniere)
  // [V8] Une pépinière ne dessine pas ses semis : ils sont comptés en lots.
  // Une PLANTATION faite dans cette même pépinière reste un rang comme ailleurs.
  const rangs = pepiniere ? rangsDeLaCarte(parcelle).filter((r) => !r.libre) : rangsDeLaCarte(parcelle)

  return {
    id: parcelle?.id,
    nom: parcelle?.nom || '',
    superficie: superficieTexte(parcelle),
    indicateurs: indicateursParcelle(parcelle),
    compteur: pepiniere ? null : compteurRangs(disposition),
    depassement: disposition.depassement ?? 0,
    sansNbRangs,
    mention: sansNbRangs && !pepiniere ? MENTION_SANS_RANGS : null,
    phrase: sansNbRangs && !pepiniere ? phraseNbRangs(parcelle) : null,
    // [P11, P12] Les dimensions quand elles existent, la mention quand elles
    // manquent — une pépinière ne compte pas ses places (US-227 / R8).
    dimensions: pepiniere ? null : dimensionsTexte(parcelle),
    sansLongueur,
    mentionLongueur: sansLongueur && !pepiniere ? MENTION_SANS_LONGUEUR : null,
    phraseLongueur: sansLongueur && !pepiniere ? phraseLongueur(parcelle) : null,
    vide: sansNbRangs && !pepiniere && rangs.length === 0,
    pepiniere,
    typePepiniere: parcelle?.type_pepiniere || TYPE_PEPINIERE_INCONNU,
    nbLots: disposition.nb_lots_en_cours ?? 0,
    rangs,
  }
}

// ── Pied de vue ──────────────────────────────────────────────────────────────

/**
 * [V14] « Trois chiffres, pas un tableau de bord » : le total en m², les rangs
 * occupés sur déclarés avec leur pourcentage, les rangs libres parcelle par
 * parcelle, et le nombre de parcelles sans dénominateur.
 */
export function piedDeVue(totaux = {}) {
  const pct = totaux.occupation_rangs_pct
  const libres = (totaux.rangs_libres_par_parcelle ?? [])
    .filter((p) => (p.rangs_libres ?? 0) > 0)
    .map((p) => `${p.parcelle} (${p.rangs_libres} rang${p.rangs_libres > 1 ? 's' : ''})`)
  const sans = totaux.parcelles_sans_nb_rangs ?? 0
  // [P14, RT13] Le seul chiffre que les places ajoutent au pied de vue : un
  // COMPTE DE PARCELLES. Ni total de places, ni taux de remplissage.
  const sansLongueur = totaux.parcelles_sans_longueur ?? 0

  return {
    surface: `${nombre(totaux.superficie_totale_m2 ?? 0)} m²`,
    rangs:
      `${totaux.rangs_occupes ?? 0} rangs occupés sur ${totaux.rangs_declares ?? 0} déclarés` +
      (pct == null ? '' : ` — ${pct} %`),
    libres: libres.length ? `Libre : ${libres.join(', ')}` : 'Aucun rang libre',
    sansNbRangs: sans
      ? `${sans} parcelle${sans > 1 ? 's' : ''} sans nombre de rangs`
      : null,
    sansLongueur: sansLongueur
      ? `${sansLongueur} parcelle${sansLongueur > 1 ? 's' : ''} sans longueur`
      : null,
  }
}

// ── L'écran entier ───────────────────────────────────────────────────────────

/**
 * [V1, V17] La Vue plan telle qu'elle se dessine, depuis la seule lecture de
 * `GET /plan` [CA1].
 *
 * Les cartes viennent dans l'ordre déclaré (`ordre`, puis nom) ; les cultures
 * non localisées forment une **dernière carte**, sans rang ni numéro, avec la
 * phrase à dire pour les rattacher.
 */
export function vueDuPlan(plan) {
  const parcelles = [...(plan?.parcelles ?? [])].sort((a, b) => {
    const oa = a.ordre ?? Number.MAX_SAFE_INTEGER
    const ob = b.ordre ?? Number.MAX_SAFE_INTEGER
    return oa !== ob ? oa - ob : (a.nom || '').localeCompare(b.nom || '', 'fr')
  })

  const nonLocalisees = (plan?.non_localisees ?? []).map((c) => ({
    culture: c.culture || '',
    variete: c.variete || '',
    quantite: c.nb_plants,
    unite: c.unite,
    mode: c.mode_implantation || MODE_RANG,
    libelle: [
      [capitaliser(c.culture), c.variete].filter(Boolean).join(' '),
      quantiteTexte(c.nb_plants, c.unite),
    ].filter(Boolean).join(' · '),
  }))

  return {
    dateRef: plan?.date_ref_effective ?? null,
    cartes: parcelles.map(carteDeParcelle),
    nonLocalisees,
    phraseNonLocalisees:
      'Dites au compagnon : « la tomate est dans la planche nord » pour les rattacher.',
    pied: piedDeVue(plan?.totaux),
  }
}

// ── Palette et tailles [CA4] ─────────────────────────────────────────────────

/**
 * [CA4, V5] Palette d'un trait — la teinte vient de la PHASE, jamais de la
 * famille ni de la confiance. Elle est **passée en paramètre** aux composants
 * pour que l'onglet Rotation (hors périmètre) reprenne le même dessin avec la
 * sienne, sans toucher aux composants.
 */
export function palettePhases() {
  return {
    trait: (cle) => {
      const p = lirePhase(cle)
      return p ? `${p.pastille} ${p.contour}` : `${PHASE_LIBRE.pastille} ${PHASE_LIBRE.contour}`
    },
    // [US-228 / CA3, CA11] La piste prend la teinte DOUCE de la phase, le
    // pictogramme sa teinte FORTE : c'est la paire que le design system utilise
    // partout (pastilles, badges), et elle tient le contraste AA dans les deux
    // thèmes — un pictogramme de la couleur du remplissage s'y effacerait.
    fond: (cle) => (lirePhase(cle) ?? PHASE_LIBRE).teinte.split(' ')[0],
    encre: (cle) => (lirePhase(cle) ?? PHASE_LIBRE).teinte.split(' ')[1] || 'text-txt',
    libre: `${PHASE_LIBRE.pastille} ${PHASE_LIBRE.contour}`,
  }
}

/** [CA4, US-222] Deux gabarits : celui de la Vue plan, et l'agrandi de l'onglet Parcelles. */
export const TAILLES = Object.freeze({
  // [US-228 / CA4] `piste` et `picto` s'ajoutent au gabarit : la piste des places
  // est plus haute qu'un trait — elle porte des pictogrammes — et l'onglet
  // Parcelles (US-222) la reprendra agrandie sans toucher au composant.
  normale: Object.freeze({
    trait: 'h-[11px]', numero: 'text-[12px]', libelle: 'text-[14px]',
    piste: 'h-[22px]', picto: 14,
  }),
  grande: Object.freeze({
    trait: 'h-[15px]', numero: 'text-[13px]', libelle: 'text-[15px]',
    piste: 'h-[26px]', picto: 16,
  }),
})

export function gabarit(taille) {
  return TAILLES[taille] || TAILLES.normale
}
