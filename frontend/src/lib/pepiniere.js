import { estTermine, estCloture, estDormant, gestesDuLot, gestePrincipal, dateEnClair, joursDepuisSemis } from './ficheLot.js'

// [US-061] Règles d'affichage d'un lot de pépinière.
// Isolées de la vue pour être vérifiables : le déroulé de référence du CA2 doit
// donner exactement les valeurs du tableau de l'US, dénominateur variable compris.

/** [CA11] Code couleur du taux de germination : vert ≥ 80 %, ambre 50–79 %, rouge en dessous. */
export function tauxTint(taux) {
  if (taux == null) return 'blue'
  if (taux >= 80) return 'brand'
  if (taux >= 50) return 'amber'
  return 'red'
}

/**
 * [CA2] Les quantités et les trois pourcentages d'un lot.
 *
 * Le dénominateur des barres Godet et Terre change de nature au cours de la vie
 * du lot : tant qu'il reste des graines à lever, il vaut le nombre de graines
 * semées ; une fois la germination close, il vaut le nombre de plants réellement
 * obtenus. Un lot sans semis rattaché n'a jamais eu de graines connues : il se
 * calcule d'emblée sur ses plants.
 *
 * [CA5] `germination` vaut `null` — la frise ne remplit alors rien — quand aucune
 * graine semée n'est connue, plutôt que d'afficher un 0 % trompeur.
 */
export function stades(lot) {
  const S = lot.graines_semees ?? 0
  const P = lot.plants_obtenus ?? 0
  const T = lot.nb_plantes ?? 0
  const G = lot.stock_residuel_godet ?? 0
  const V = lot.nb_vendus ?? 0
  const L = lot.nb_pertes_godet ?? 0

  const close = lot.sans_semis_rattache || lot.etat_germination === 'close'
  const D = close ? P : (S || P)
  const part = (n) => (D > 0 ? Math.round((n / D) * 100) : 0)

  // [CA?] La frise représente l'avancement de chaque phase — combien en est
  // sorti —, pas un taux de réussite ni un stock restant. Une phase encore
  // ouverte (des graines pas toutes soldées, du stock godet non écoulé) se
  // remplit au fil de ce qui en est sorti ; une phase close (plus rien en
  // attente) est pleine même si rien n'en est jamais sorti par ailleurs.
  const closeGodet = P > 0 && G === 0

  return {
    S, P, T, G, V, L,
    germination: lot.sans_semis_rattache || S <= 0 ? null : Math.round((P / S) * 100),
    germinationAvancement: close ? 100 : part(P),
    godet: closeGodet ? 100 : part(T + V + L),
    terre: part(T),
  }
}

/**
 * Stade courant du lot, index de la frise à trois segments de la maquette :
 * 0 Germination, 1 Godet, 2 Terre.
 *
 * Un lot est « en germination » tant qu'aucun plant n'a été mis en godet, et
 * passe en « Terre » lorsqu'il n'a plus de godet disponible mais des plants en
 * place — c'est-à-dire quand il n'y a plus rien à repiquer.
 */
export function stadeCourant(lot, st = stades(lot)) {
  if (st.P === 0) return 0
  if (st.G === 0 && st.T > 0) return 2
  return 1
}

/**
 * Segment de la frise portant la pastille de position — distinct de
 * `stadeCourant` (le badge de tête, qui répond à « qu'est-ce qu'il me reste à
 * faire ? » et reste sur Godet tant que du stock y est disponible).
 *
 * La pastille répond à une autre question : « où en est-on allé le plus
 * loin ? ». Si de la mise en terre a déjà eu lieu, elle y est — même s'il
 * reste du stock en godet à écouler ; ce stock restant continue simplement à
 * se voir dans le remplissage de la barre Godet, qui reste sous les 100 %.
 * Même raisonnement entre Germination et Godet.
 */
export function stadeAvancement(lot, st = stades(lot)) {
  if (st.T > 0) return 2
  if (st.P > 0) return 1
  return 0
}

/**
 * Badge de germination de la maquette : un seul libellé, `Germination N %`,
 * coloré par le taux.
 *
 * La distinction « en cours » / « close » n'est plus rendue — un taux de
 * germination est un taux de germination, et le doubler d'un « Réussite N % »
 * pour la même valeur n'apprenait rien. Seules les deux situations où le taux
 * n'existe pas gardent un libellé propre.
 */
export function phaseGermination(lot, st = stades(lot)) {
  if (lot.sans_semis_rattache) {
    return {
      tint: 'violet',
      label: 'Germination inconnue',
      aide: "Aucun semis n'est rattaché à ce lot : son taux de germination ne peut pas être établi.",
    }
  }
  if (lot.etat_germination === 'indeterminee') {
    return {
      tint: 'amber',
      label: 'Germination indéterminée',
      aide: "Nombre de graines d'origine non déclaré sur au moins une mise en godet — le taux ne peut pas être établi.",
    }
  }
  const taux = st.germination ?? lot.taux_germination ?? 0
  return {
    tint: tauxTint(taux),
    label: `Germination ${taux} %`,
    aide: 'Part des graines semées ayant effectivement donné un plant.',
  }
}

/** Jours écoulés depuis le semis — `null` si le lot n'a pas de date de semis. */
export function joursDepuis(dateISO, aujourdhui = new Date()) {
  if (!dateISO) return null
  const d = new Date(`${dateISO}T00:00:00`)
  if (Number.isNaN(d.getTime())) return null
  return Math.max(0, Math.floor((aujourdhui - d) / 86400000))
}

/**
 * [US-208 / CA6] L'emplacement d'un lot et le type de sa pépinière.
 * « Serre · pépinière chaude », « Châssis · type non renseigné » — le type
 * absent est écrit, jamais supposé (RT2). Un lot sans emplacement connu reste
 * « Pépinière » : il n'a pas de pépinière dont on puisse dire le type.
 */
export function emplacementLot(lot) {
  // [US-210 / CA5] L'emplacement COURANT, calculé par l'API (godets localisés, sinon semis).
  const emp = lot?.emplacement
  const nom = emp ? emp.nom : lot?.parcelle
  const typePep = emp ? emp.type_pepiniere : lot?.type_pepiniere
  if (!nom) return emp ? 'Emplacement non renseigné' : 'Pépinière'
  const type = typePep ? `pépinière ${typePep}` : 'type non renseigné'
  return `${nom} · ${type}`
}

/**
 * [US-209 / CA10, CA11] Le numéro court d'un lot, tel qu'on l'écrit sur l'étiquette :
 * « #128 ». Le lot « godets sans semis rattaché » n'en a pas — il n'affiche rien.
 */
export function libelleNumeroLot(lot) {
  return lot?.numero_lot != null ? `#${lot.numero_lot}` : null
}

/**
 * [US-209 / CA11] Lit ce que le jardinier tape dans « Aller au lot n° » : « 128 »,
 * « #128 », « n° 128 », « lot 128 ». Retourne l'entier, ou null si ce n'est pas un numéro.
 */
export function lireNumeroLot(saisie) {
  const m = /^\s*(?:lot\s*)?(?:n\s*[°º.]?\s*)?#?\s*(\d{1,6})\s*$/i.exec(String(saisie ?? ''))
  return m ? Number(m[1]) : null
}

/** [US-209 / CA11] Le message d'un numéro inconnu — identique pour le champ et l'adresse. */
export const messageLotInconnu = (numero) => `Aucun lot n° ${numero} dans ce potager`

// ── [US-215] L'onglet « Aujourd'hui » ────────────────────────────────────────
//
// Ce qu'il y a à faire, lot par lot, du plus urgent au plus calme. Les échéances,
// l'action suggérée et le rang d'urgence viennent de l'API (US-214) : ce module
// n'en recalcule aucun, il met en forme (RT7, CA15).

const plur = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`
const normaliser = (t) => String(t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase()

/**
 * [CA1] Les onglets livrés. « Calendrier » (US-218) et « Emplacements » (US-219)
 * n'apparaissent que livrés — jamais un onglet vide — et « Emplacements »
 * seulement à partir de deux pépinières. Chaque US passe son drapeau à `true`.
 */
export const ONGLETS_LIVRES = Object.freeze({ calendrier: false, emplacements: false })

export function ongletsPepiniere({ nbPepinieres = null, livres = ONGLETS_LIVRES } = {}) {
  const onglets = [{ cle: 'aujourdhui', libelle: 'Aujourd’hui' }, { cle: 'lots', libelle: 'Lots' }]
  if (livres.calendrier) onglets.push({ cle: 'calendrier', libelle: 'Calendrier' })
  if (livres.emplacements && (nbPepinieres ?? 0) >= 2) onglets.push({ cle: 'emplacements', libelle: 'Emplacements' })
  return onglets
}

/** [CA1] L'onglet à ouvrir : celui demandé s'il existe, « Aujourd'hui » sinon. */
export function ongletInitial(demande, onglets) {
  return onglets.some((o) => o.cle === demande) ? demande : 'aujourdhui'
}

/** « 2,5 m² » — `null` sans superficie. */
export function superficieEnClair(m2) {
  if (m2 == null || m2 === '' || Number.isNaN(Number(m2))) return null
  return `${String(Math.round(Number(m2) * 10) / 10).replace('.', ',')} m²`
}

/**
 * [CA2] La pastille d'une pépinière unique : « SERRE · 2,5 m² · pépinière chaude ».
 * `null` dès qu'il y en a zéro ou plusieurs. Le type absent est dit tel quel (RT2).
 */
export function pastillePepiniere(pepinieres) {
  if (!Array.isArray(pepinieres) || pepinieres.length !== 1) return null
  const p = pepinieres[0]
  const type = p.type_pepiniere ? `pépinière ${p.type_pepiniere}` : 'type non renseigné'
  return [String(p.nom ?? '').toUpperCase(), superficieEnClair(p.superficie_m2), type].filter(Boolean).join(' · ')
}

/** [CA5] Un lot « en cours » : ni terminé, ni clôturé. */
export const estEnCours = (lot) => Boolean(lot) && !estTermine(lot) && !estCloture(lot)

const etatRep = (lot) => lot?.echeances?.repiquage?.etat ?? null
const etatTerre = (lot) => lot?.echeances?.mise_en_terre?.etat ?? null
const etatEndu = (lot) => lot?.echeances?.endurcissement?.etat ?? null

/**
 * [CA4] Les trois filtres du bandeau — les règles du résumé d'US-214, lues sur
 * les échéances que l'API a déjà calculées.
 */
export const FILTRES_BANDEAU = Object.freeze({
  a_repiquer: (lot) => ['a_repiquer', 'en_retard'].includes(etatRep(lot)),
  a_endurcir: (lot) => etatEndu(lot) === 'en_cours',
  prets_pour_le_plan: (lot) => (lot?.stock_residuel_godet ?? 0) > 0
    && (['atteinte', 'depassee'].includes(etatTerre(lot)) || etatTerre(lot) == null),
})

/** [CA4] Un second appui sur la même carte retire le filtre. */
export const basculerFiltre = (courant, cle) => (courant === cle ? null : cle)

/**
 * [CA5] L'échéance courte d'une ligne : « Repiquage +6 j », « Repiquage dans 3 j »,
 * « Endurcissement J+3 sur 7 », « En pépinière froide », « Dormant ».
 * `{ texte, ton }` — ton `retard`, `info` ou `na`. Une échéance incalculable dit
 * pourquoi (CA10, « Délai non renseigné »), sans ordre inventé.
 */
export function echeanceCourte(lot) {
  const e = lot?.echeances
  if (!e) return { texte: 'Échéance non calculée', ton: 'na' }
  const rep = e.repiquage ?? {}
  const terre = e.mise_en_terre ?? {}
  const endu = e.endurcissement ?? {}
  if (e.dormance?.est_dormant) return { texte: 'Dormant', ton: 'na' }
  if (rep.etat === 'en_retard') return { texte: `Repiquage +${rep.retard_jours} j`, ton: 'retard' }
  if (terre.etat === 'depassee') return { texte: `Mise en terre +${terre.retard_jours} j`, ton: 'retard' }
  if (rep.etat === 'a_repiquer') return { texte: 'À repiquer', ton: 'info' }
  if (endu.etat === 'en_cours') return { texte: `Endurcissement J+${endu.jour} sur ${endu.sur}`, ton: 'info' }
  if (endu.etat === 'froide') return { texte: 'En pépinière froide', ton: 'info' }
  if (terre.etat === 'atteinte') return { texte: 'Mise en terre à faire', ton: 'info' }
  if (rep.etat === 'a_venir') return { texte: `Repiquage dans ${rep.dans_jours} j`, ton: 'info' }
  if (terre.etat === 'a_venir') return { texte: `Mise en terre dans ${terre.dans_jours} j`, ton: 'info' }
  const raisons = Array.isArray(e.raisons) ? e.raisons : []
  if (raisons.length) {
    const r = raisons[0]
    return { texte: /délai/i.test(r) ? 'Délai non renseigné' : `${r.charAt(0).toUpperCase()}${r.slice(1)}`, ton: 'na', raison: r }
  }
  return { texte: 'Aucune échéance', ton: 'na' }
}

const nomCourt = (l) => [l.culture, l.variete].filter(Boolean).join(' ').toLowerCase()

/**
 * [CA3] « chou frisé +6 j · tomate cerise à repiquer » — les lots à repiquer dans
 * l'ordre d'urgence, trois au plus.
 */
export function retardsNommes(lots, max = 3) {
  return (lots ?? [])
    .filter(FILTRES_BANDEAU.a_repiquer)
    .sort((a, b) => (a.rang_urgence ?? 1e9) - (b.rang_urgence ?? 1e9))
    .slice(0, max)
    .map((l) => {
      const r = l.echeances.repiquage
      return r.etat === 'en_retard' ? `${nomCourt(l)} +${r.retard_jours} j` : `${nomCourt(l)} à repiquer`
    })
    .join(' · ')
}

/**
 * [CA3, CA4] Les quatre cartes du bandeau, lues dans `resume` (US-214). Une carte
 * à zéro dit « rien » plutôt que de disparaître. Les trois premières filtrent ;
 * « À repiquer » prend la teinte d'alerte quand un lot est en retard.
 */
export function cartesReponses(resume, lots = []) {
  const r = resume ?? {}
  const rep = r.a_repiquer ?? { lots: 0, plants: 0 }
  const endu = r.a_endurcir ?? { lots: 0 }
  const prets = r.prets_pour_le_plan ?? { lots: 0, plants: 0, rangs_libres_par_parcelle: [] }
  const semer = r.a_semer ?? { cultures: [], total: 0 }
  const enRetard = (lots ?? []).some((l) => etatRep(l) === 'en_retard')
  const enduLots = (lots ?? []).filter(FILTRES_BANDEAU.a_endurcir)
  const rangs = (prets.rangs_libres_par_parcelle ?? [])
    .filter((p) => (p.rangs_libres ?? 0) > 0)
    .map((p) => `${p.parcelle} : ${p.rangs_libres} rang${p.rangs_libres > 1 ? 's libres' : ' libre'}`)
    .join(' · ')
  return [
    {
      cle: 'a_repiquer', titre: 'À repiquer', filtrable: true, alerte: enRetard,
      valeur: rep.lots ? plur(rep.lots, 'lot') : 'rien',
      detail: rep.lots
        ? [rep.plants ? `${rep.plants} semés` : null, retardsNommes(lots)].filter(Boolean).join(' · ')
        : null,
    },
    {
      cle: 'a_endurcir', titre: 'À endurcir', filtrable: true, alerte: false,
      valeur: endu.lots ? plur(endu.lots, 'lot') : 'rien',
      detail: enduLots.length
        ? enduLots.map((l) => `${nomCourt(l)} J+${l.echeances.endurcissement.jour}/${l.echeances.endurcissement.sur}`).join(' · ')
        : null,
    },
    {
      cle: 'prets_pour_le_plan', titre: 'Prêts pour le plan', filtrable: true, alerte: false,
      valeur: prets.plants ? plur(prets.plants, 'plant') : 'rien',
      detail: prets.plants ? (rangs || plur(prets.lots, 'lot')) : null,
    },
    {
      cle: 'a_semer', titre: 'À semer', filtrable: false, alerte: false,
      valeur: semer.total ? plur(semer.total, 'culture') : 'rien',
      cultures: semer.cultures ?? [],
      detail: null,
    },
  ]
}

/**
 * [CA5, CA6] Les lots en cours dans l'ordre d'urgence de l'API ; les dormants en
 * fin de liste (US-214 les y range déjà ; un lot sans rang passe après).
 */
export function lotsDuJour(lots) {
  return (lots ?? [])
    .filter(estEnCours)
    .sort((a, b) =>
      (estDormant(a) - estDormant(b))
      || ((a.rang_urgence ?? 1e9) - (b.rang_urgence ?? 1e9))
      || ((a.numero_lot ?? 1e9) - (b.numero_lot ?? 1e9)))
}

/** [CA4, CA9] Filtre du bandeau, recherche (culture, variété, numéro) et emplacement, cumulés. */
export function filtrerLots(lots, { q = '', emplacement = null, bandeau = null } = {}) {
  const q2 = normaliser(q).replace(/^#/, '')
  const emp = normaliser(emplacement)
  return (lots ?? []).filter((l) => {
    if (bandeau && FILTRES_BANDEAU[bandeau] && !FILTRES_BANDEAU[bandeau](l)) return false
    if (emp && normaliser(l.emplacement?.nom ?? l.parcelle) !== emp) return false
    if (!q2) return true
    return normaliser(l.culture).includes(q2) || normaliser(l.variete).includes(q2)
      || (l.numero_lot != null && String(l.numero_lot) === q2)
  })
}

/** [CA5] « semé le 1er septembre · 18 j · Serre ». */
export function sousTitreLigne(lot) {
  const lieu = lot?.emplacement?.nom ?? lot?.parcelle ?? 'emplacement non renseigné'
  if (lot?.sans_semis_rattache || !lot?.date_semis) return `sans semis rattaché · ${lieu}`
  const j = joursDepuisSemis(lot)
  return [`semé le ${dateEnClair(lot.date_semis)}`, j != null ? `${j} j` : null, lieu].filter(Boolean).join(' · ')
}

/**
 * [CA5] La quantité : les godets disponibles dès qu'il y en a ; sinon
 * « 48 semés → 40 levés (83 %) » quand la levée est notée (US-212), « 48 semés ».
 */
export function quantiteLigne(lot) {
  const godets = lot?.stock_residuel_godet ?? 0
  if (godets > 0) return `${plur(godets, 'godet')} disponible${godets > 1 ? 's' : ''}`
  const semes = lot?.graines_semees ?? 0
  if (!semes) return '—'
  if (lot?.nb_leves != null) {
    return `${semes} semés → ${lot.nb_leves} levés (${Math.round((lot.nb_leves / semes) * 100)} %)`
  }
  return `${semes} semés`
}

/**
 * [CA6, CA7, CA14] Le bouton d'une ligne : le geste de l'action suggérée, prêt à
 * déposer dans la file (US-224). « Noter la levée » n'est pas un dépôt : il ouvre
 * la fiche (`ouvreFiche`). `null` si l'action suggérée n'a pas de geste.
 * `principal` : la ligne est en retard. `ariaLabel` nomme le lot.
 */
export function boutonDeLigne(lot, opts = {}) {
  const g = gestePrincipal(gestesDuLot(lot, opts))
  if (!g) return null
  const libelle = g.code === 'repiquer' ? 'Repiquer' : g.libelle
  const nom = lot.numero_lot != null ? `le lot ${lot.numero_lot}` : `le lot de ${String(lot.culture ?? '').toLowerCase()}`
  return {
    geste: g,
    libelle,
    ariaLabel: `${libelle} ${nom}`,
    ouvreFiche: g.code === 'noter_levee',
    principal: echeanceCourte(lot).ton === 'retard',
  }
}
