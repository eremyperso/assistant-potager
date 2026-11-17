// Vue Dérives [US-315] : mise en forme des réponses de `/admin/pilotage/derives` et comparaison de deux
// versions. Les médianes, P95 et taux viennent de l'API ; l'écran ne calcule que l'écart entre deux
// versions choisies (le choix n'existe que sur l'écran) et décide de le mettre en évidence.
import { entier, euro, nombre, pourcent } from './format.js'
import { ecart, SENS } from './ecart.js'
import { libelleCanal } from './cout.js'

/** [CA7] Les lignes sans version d'application. */
export const LIBELLE_SANS_VERSION = 'avant suivi des versions'
export const libelleVersion = (version) => (version === null || version === undefined ? LIBELLE_SANS_VERSION : version)

/** Le type de la courbe quand rien n'est choisi [CA2]. */
export const TYPE_PAR_DEFAUT = 'agent'

/** [CA6] Ce que la vue dit de la provenance. */
export const CONSEIL_MESURE = "Pour une comparaison propre, filtrez la provenance sur « mesure » : une campagne rejouée sur le même jeu de phrases isole l'effet de la version."

/** Les types d'appel proposés pour la courbe : ceux qui ont des appels mesurés, `agent` en premier. */
export function typesDisponibles(derives) {
  const types = new Set(derives.par_version_et_type.map((l) => l.appel_type))
  types.add(derives.courbe.appel_type)
  types.add(TYPE_PAR_DEFAUT)
  return [...types].sort((a, b) => (a === TYPE_PAR_DEFAUT ? -1 : b === TYPE_PAR_DEFAUT ? 1 : a.localeCompare(b)))
}

export const periodeSansAppel = (derives) => derives.versions.length === 0

// ── CA1 : tableau par version et par type ──────────────────────────────────────────────────────

export const COLONNES_VERSION_TYPE = [
  { id: 'type', libelle: "Type d'appel" },
  { id: 'appels', libelle: 'Appels' },
  { id: 'entree_mediane', libelle: 'Entrée, médiane' },
  { id: 'entree_p95', libelle: 'Entrée, P95' },
  { id: 'sortie_mediane', libelle: 'Sortie, médiane' },
  { id: 'cache', libelle: 'Taux de cache' },
]

export function lignesVersionType(derives) {
  return derives.par_version_et_type.map((l) => ({
    cle: `${l.version}|${l.appel_type}`,
    titre: libelleVersion(l.version),
    mono: l.version !== null,
    faible: l.echantillon_faible,
    cellules: {
      type: l.appel_type,
      appels: entier(l.appels),
      entree_mediane: entier(l.entree_mediane),
      entree_p95: entier(l.entree_p95),
      sortie_mediane: entier(l.sortie_mediane),
      cache: pourcent(l.taux_cache, 0),
    },
  }))
}

// ── CA2 : courbe par jour ──────────────────────────────────────────────────────────────────────

/** La médiane des jetons d'entrée par appel, jour par jour ; un repère à la première apparition de
 *  chaque version qui tombe dans la période. */
export function modeleCourbe(derives) {
  const c = derives.courbe
  const points = c.points.map((p) => {
    const [, m, j] = p.split('-').map(Number)
    return { cle: p, libelle: `${j}/${m}` }
  })
  const valeurs = c.valeurs.map((v) => v ?? 0)
  const reperes = c.reperes
    .map((r) => ({ index: c.points.indexOf(r.date), libelle: r.version }))
    .filter((r) => r.index >= 0)
  return {
    modele: {
      mode: 'total', pas: 'jour', points, cache: [],
      series: [{ cle: 'mediane', libelle: `médiane des jetons d'entrée, type ${c.appel_type}`, valeurs, total: valeurs.reduce((a, b) => a + b, 0) }],
      total: valeurs,
    },
    reperes,
    sansAppel: c.valeurs.every((v) => v === null),
  }
}

// ── CA3 : par version et par canal ─────────────────────────────────────────────────────────────

export const COLONNES_VERSION_CANAL = [
  { id: 'canal', libelle: 'Canal' },
  { id: 'echanges', libelle: 'Échanges' },
  { id: 'appels_mediane', libelle: 'Appels / échange, médiane' },
  { id: 'appels_p95', libelle: 'Appels / échange, P95' },
  { id: 'entree', libelle: 'Entrée / échange, médiane' },
  { id: 'cout', libelle: 'Coût / échange, médian' },
]

const decimal = (v) => (v === null || v === undefined ? '—' : nombre(v, Number.isInteger(v) ? 0 : 1))

export function lignesVersionCanal(derives) {
  return derives.par_version_et_canal.map((l) => ({
    cle: `${l.version}|${l.canal}`,
    titre: libelleVersion(l.version),
    mono: l.version !== null,
    faible: l.echantillon_faible,
    cellules: {
      canal: libelleCanal(l.canal),
      echanges: entier(l.echanges),
      appels_mediane: decimal(l.appels_par_echange_mediane),
      appels_p95: decimal(l.appels_par_echange_p95),
      entree: entier(l.entree_par_echange_mediane),
      cout: l.cout_par_echange_mediane_micro_eur === null ? '—' : euro(l.cout_par_echange_mediane_micro_eur),
    },
  }))
}

// ── CA4, CA5 : comparaison de deux versions ────────────────────────────────────────────────────

/** Les deux versions proposées par défaut : les deux plus récentes ayant des appels du type, la plus
 *  ancienne à gauche. `null` quand il y en a moins de deux. */
export function versionsParDefaut(derives, appelType) {
  const avecAppels = derives.versions.filter((v) => v !== null
    && derives.par_version_et_type.some((l) => l.version === v && l.appel_type === appelType))
  if (avecAppels.length < 2) return null
  return { a: avecAppels[1], b: avecAppels[0] }
}

/** L'écart relatif brut (0,483 pour +48,3 %) ; `null` sans base de comparaison. */
export function ecartRelatif(avant, apres) {
  if (avant === null || avant === undefined || apres === null || apres === undefined || avant === 0) return null
  return (apres - avant) / avant
}

/**
 * Compare deux versions pour un type d'appel : les indicateurs de taille d'appel, puis, par canal, ceux
 * d'un échange. Un écart est mis en évidence au-delà de `seuil_ecart` (20 %) SAUF quand l'un des deux
 * échantillons est faible (moins de `seuil_echantillon` appels ou échanges) : le chiffre reste affiché,
 * marqué « échantillon faible », jamais souligné [CA5].
 */
export function comparer(derives, a, b, appelType) {
  const ligneType = (v) => derives.par_version_et_type.find((l) => l.version === v && l.appel_type === appelType) || null
  const A = ligneType(a), B = ligneType(b)
  const seuil = derives.seuil_ecart
  const lignes = []

  const ajouter = ({ id, libelle, avant, apres, format, sens, faible, mettreEnEvidence = true }) => {
    const rel = ecartRelatif(avant, apres)
    lignes.push({
      id, libelle, a: format(avant), b: format(apres),
      ecart: ecart(apres, avant, { sens }),
      faible,
      enEvidence: mettreEnEvidence && !faible && rel !== null && Math.abs(rel) > seuil,
    })
  }

  if (A && B) {
    const faible = A.echantillon_faible || B.echantillon_faible
    ajouter({ id: 'appels', libelle: 'Appels', avant: A.appels, apres: B.appels, format: entier, sens: SENS.NEUTRE, faible, mettreEnEvidence: false })
    ajouter({ id: 'entree_mediane', libelle: "Jetons d'entrée, médiane par appel", avant: A.entree_mediane, apres: B.entree_mediane, format: entier, sens: SENS.MAUVAISE, faible })
    ajouter({ id: 'entree_p95', libelle: "Jetons d'entrée, P95", avant: A.entree_p95, apres: B.entree_p95, format: entier, sens: SENS.MAUVAISE, faible })
    ajouter({ id: 'sortie_mediane', libelle: 'Jetons de sortie, médiane', avant: A.sortie_mediane, apres: B.sortie_mediane, format: entier, sens: SENS.MAUVAISE, faible })
    ajouter({ id: 'cache', libelle: 'Taux de cache', avant: A.taux_cache, apres: B.taux_cache, format: (v) => pourcent(v, 0), sens: SENS.BONNE, faible })
  }

  const canaux = [...new Set(derives.par_version_et_canal.filter((l) => l.version === a || l.version === b).map((l) => l.canal))].sort()
  for (const canal of canaux) {
    const ligneCanal = (v) => derives.par_version_et_canal.find((l) => l.version === v && l.canal === canal) || null
    const CA = ligneCanal(a), CB = ligneCanal(b)
    if (!CA || !CB) continue
    const faible = CA.echantillon_faible || CB.echantillon_faible
    const nom = libelleCanal(canal)
    ajouter({ id: `appels_echange_${canal}`, libelle: `Appels par échange, médiane · ${nom}`, avant: CA.appels_par_echange_mediane, apres: CB.appels_par_echange_mediane, format: decimal, sens: SENS.MAUVAISE, faible })
    ajouter({ id: `entree_echange_${canal}`, libelle: `Jetons d'entrée par échange, médiane · ${nom}`, avant: CA.entree_par_echange_mediane, apres: CB.entree_par_echange_mediane, format: entier, sens: SENS.MAUVAISE, faible })
    if (CA.cout_par_echange_mediane_micro_eur !== null && CB.cout_par_echange_mediane_micro_eur !== null) {
      ajouter({ id: `cout_echange_${canal}`, libelle: `Coût par échange, médian · ${nom}`, avant: CA.cout_par_echange_mediane_micro_eur, apres: CB.cout_par_echange_mediane_micro_eur, format: euro, sens: SENS.MAUVAISE, faible })
    }
  }
  return { lignes, sansDonnees: lignes.length === 0, auMoinsUneEnEvidence: lignes.some((l) => l.enEvidence) }
}
