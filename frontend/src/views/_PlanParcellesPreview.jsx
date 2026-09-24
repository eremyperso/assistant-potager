// [US-222 / CA16] Page de contrôle visuel de l'onglet **Parcelles** — le niveau
// 2 du zoom —, hors navigation applicative, sur le modèle de `/vue-plan`
// (US-200 / CA11) et de `/fiche-calendrier` (US-183 / CA18).
//
// Rejoue la VRAIE vue sur une réponse simulée de `GET /plan`, dans sa forme
// exacte, pour que les cas qu'un potager réel ne présente pas tous en même
// temps se vérifient d'un coup d'œil : parcelle pleine, parcelle avec rang
// libre, parcelle sans nombre de rangs, dépassement, pépinière chaude avec une
// plantation, parcelle libre, lecture seule, 375 px avec le sélecteur
// horizontal, thème sombre.
//
// ⚠️ Valeurs de DÉMONSTRATION : elles servent au contrôle visuel, elles
// n'engagent aucune agronomie. Chargée en `lazy()` par `main.jsx` — un import
// statique contaminerait l'application réelle avec ces données.
import { useState } from 'react'
import { api } from '../lib/api.js'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import { AppContextProvider } from '../context/AppContext.jsx'
import { NavigationProvider } from '../context/NavigationContext.jsx'
import { useTheme } from '../hooks/useTheme.js'
import Plan from './Plan.jsx'
import { Btn } from '../components/ui'

const DATE_REF = '2026-09-23'

/** Une ligne de culture dans la forme exacte de `GET /plan` (US-194, US-198). */
const ligne = (culture, variete, quantite, unite, mode, numeros, phase, espacement = null) => ({
  culture, variete, nb_plants: quantite, unite,
  type_organe: culture === 'tomate' ? 'reproducteur' : 'végétatif',
  surface_m2_par_plant: null, famille: null,
  nb_observations: 0, has_observations: false,
  espacement_rang_cm: espacement,
  mode_implantation: mode,
  rangs: numeros.length,
  quantite_par_rang: Math.round((quantite / Math.max(numeros.length, 1)) * 10) / 10,
  date_installation: '2026-05-02',
  numeros_rangs: numeros,
  phase, phase_depuis: '2026-06-01', phase_depuis_nature: 'plantation', nb_series: 1,
})

/**
 * La disposition d'une parcelle, telle que `repartition_du_plan` la rend —
 * places comprises (US-227 / R10 à R16). Les formules sont recopiées ici parce
 * que cette page simule la RÉPONSE du serveur, pas parce que le front
 * calculerait quoi que ce soit : la vraie vue, elle, les reçoit toutes faites.
 */
const disposition = (declares, cultures, { lots = null, longueur = null } = {}) => {
  const occupes = cultures.reduce((s, c) => s + c.numeros_rangs.length, 0)
  const rangs = []
  let exemple = null
  for (const c of cultures) {
    const espacement = c.espacement_rang_cm
    const surface = c.mode_implantation === 'surface'
    const places = longueur && espacement && !surface
      ? Math.max(1, Math.floor((longueur * 100) / espacement))
      : null
    const prises = places == null ? null : Math.min(places, Math.round(c.quantite_par_rang))
    if (places && exemple == null) exemple = { nombre: places, culture: c.culture }
    for (const n of c.numeros_rangs) {
      rangs.push({
        numero: n, libre: false, culture: c.culture, variete: c.variete, unite: c.unite,
        espacement_rang_cm: espacement ?? null,
        quantite_par_rang: c.quantite_par_rang,
        places,
        places_prises: prises,
        places_restantes: places == null ? null : Math.max(0, places - Math.round(c.quantite_par_rang)),
        depassement_places: places == null ? null : Math.max(0, Math.round(c.quantite_par_rang) - places),
      })
    }
  }
  for (let n = occupes + 1; n <= (declares ?? 0); n++) {
    rangs.push({
      numero: n, libre: true, culture: null, variete: null, unite: null,
      longueur_m: longueur, capacite_exemple: exemple,
    })
  }
  return {
    rangs_declares: declares,
    rangs_occupes: occupes,
    rangs_libres: declares == null ? null : Math.max(0, declares - occupes),
    depassement: declares == null ? 0 : Math.max(0, occupes - declares),
    rangs,
    mode_numerotation: 'ordre_installation',
    nb_lots_en_cours: lots,
  }
}

/**
 * [US-232] Une intervention de sol, dans la forme exacte de `GET /plan` —
 * `sol.interventions` (S2, S3). Valeurs de démonstration : elles n'engagent
 * aucune agronomie, elles éprouvent le RENDU.
 */
const intervention = (id, date, type_action, extra = {}) => ({
  id, date, type_action,
  quantite: null, unite: null, rang: null, culture: null,
  commentaire: null, traitement: null, ...extra,
})

const parcelle = (id, nom, superficie, declares, cultures, extra = {}) => {
  const longueur = extra.longueur ?? null
  const largeur = longueur && superficie ? Math.round((superficie / longueur) * 100) / 100 : null
  return {
    id, nom, superficie_m2: superficie, exposition: 'sud',
    // [US-229] `paillage` est un BOOLÉEN et `abri` un mot du vocabulaire fermé
    // d'US-181 : la simulation suit la forme EXACTE de `GET /plan`, sinon la
    // carte « Caractéristiques » se contrôlerait sur des valeurs qui n'existent
    // pas. `type_sol` (US-058) et `actif` (US-009) complètent la réponse.
    abri: 'aucun', paillage: true, type_sol: 'Limoneux', actif: true,
    nb_rangs: declares, ordre: id, est_pepiniere: false,
    longueur_m: longueur,
    largeur_m: largeur,
    largeur_deduite: largeur != null,
    largeur_incoherente: largeur != null && largeur < 0.2,
    cultures, occupation_pct: null, has_observations: false, nb_observations: 0,
    disposition: disposition(declares, cultures, extra),
    // [US-232 / S6] Sans intervention : la carte le DIT, elle n'est pas masquée.
    sol: extra.sol ?? { interventions: [], total: 0 },
    // [US-231 / R8] `null` pour une pépinière : la carte n'est pas rendue.
    rotation: extra.rotation ?? null,
    ...extra,
  }
}

/**
 * [US-231] Le bloc « Rotation » d'une parcelle, dans la forme EXACTE de
 * `GET /plan` — telle que `app/services/rotation.py` la rend. Les alertes et le
 * conseil sont RECOPIÉS ici parce que cette page simule la RÉPONSE du serveur,
 * jamais parce que l'écran les calculerait : la vraie carte les reçoit faits.
 */
const rotation = ({ campagnes, conseil = [], alertes = [], sansFamille = [],
                    mentionConseil = null }) => {
  const annees = [2024, 2025, 2026]
  return {
    campagne_a_venir: 2027,
    campagnes: annees.map((annee) => ({
      annee, familles: (campagnes[annee] ?? []).map((f) => ({
        famille: f.inconnue ? 'Famille non renseignée' : f.famille,
        famille_id: f.inconnue ? null : f.id, inconnue: Boolean(f.inconnue),
        cultures: f.cultures,
      })),
    })),
    conseil: {
      annee: 2027, mention: mentionConseil,
      familles: conseil.map((f) => ({
        famille: f.famille, famille_id: f.id, delai_retour_annees: f.delai,
        derniere_campagne: f.derniere ?? null, cultures: f.cultures,
      })),
    },
    alertes: alertes.map((a) => ({
      famille: a.famille, famille_id: a.id, annees: a.annees, annee_a_eviter: 2027,
      message: `${a.famille} ${a.annees === 3 ? 'trois' : 'deux'} années de suite `
        + 'sur cette parcelle. À éviter en 2027.',
    })),
    cultures_sans_famille: sansFamille,
    mention_familles_inconnues: sansFamille.length === 0 ? null
      : `Famille botanique non renseignée pour ${sansFamille.join(', ')} : `
        + `${sansFamille.length > 1 ? 'ces cultures n’entrent' : 'cette culture n’entre'} `
        + 'ni dans l’alerte de répétition ni dans le conseil.',
    aucun_antecedent: annees.every((a) => (campagnes[a] ?? []).length === 0),
    mention_aucun_antecedent: annees.some((a) => (campagnes[a] ?? []).length > 0)
      ? null : 'Aucune culture enregistrée sur cette parcelle avant 2026.',
  }
}

const SOLANACEES = { id: 7, famille: 'Solanacées' }
const APIACEES = { id: 3, famille: 'Apiacées' }
const FABACEES = { id: 5, famille: 'Fabacées' }
const CUCURBITACEES = { id: 9, famille: 'Cucurbitacées' }

// [Gherkin, R5] Deux années de Solanacées de suite : l'alerte le dit.
const ROTATION_CENTRALE = rotation({
  campagnes: {
    2024: [{ ...APIACEES, cultures: ['carotte'] }],
    2025: [{ ...SOLANACEES, cultures: ['tomate'] }],
    2026: [{ ...SOLANACEES, cultures: ['tomate', 'poivron'] },
           { ...APIACEES, cultures: ['carotte'] }],
  },
  conseil: [{ ...FABACEES, delai: 3, cultures: ['haricot'] },
            { ...CUCURBITACEES, delai: 4, derniere: 2021, cultures: ['courge'] }],
  alertes: [{ ...SOLANACEES, annees: 2 }],
})

// [R7, CA5] Une culture sans famille : nommée, neutre, exclue du calcul.
const ROTATION_OMBRE = rotation({
  campagnes: {
    2025: [{ ...CUCURBITACEES, cultures: ['courge'] }],
    2026: [{ inconnue: true, cultures: ['topinambour'] }],
  },
  conseil: [{ ...SOLANACEES, delai: 3, cultures: ['tomate'] }],
  sansFamille: ['topinambour'],
})

// [R5] Répétition sur trois ans — le cas que l'on veut voir venir.
const ROTATION_SERREE = rotation({
  campagnes: {
    2024: [{ ...SOLANACEES, cultures: ['pomme de terre'] }],
    2025: [{ ...SOLANACEES, cultures: ['tomate'] }],
    2026: [{ ...SOLANACEES, cultures: ['aubergine'] }],
  },
  conseil: [{ ...FABACEES, delai: 3, cultures: ['haricot'] }],
  alertes: [{ ...SOLANACEES, annees: 3 }],
})

// [R6] Aucun antécédent : la phrase est dite, le conseil reste.
const ROTATION_NORD = rotation({
  campagnes: {},
  conseil: [{ ...SOLANACEES, delai: 3, cultures: ['tomate'] },
            { ...APIACEES, delai: 2, cultures: ['carotte'] }],
})

// [R4] Référentiel muet : aucun conseil formulable, et la carte le dit.
const ROTATION_EST = rotation({
  campagnes: { 2026: [{ inconnue: true, cultures: ['radi'] }] },
  sansFamille: ['radi'],
  mentionConseil: 'Aucun délai de retour n’est renseigné dans le référentiel : '
    + 'je ne formule pas de conseil pour 2027.',
})

// ── Le plan de démonstration ─────────────────────────────────────────────────

// [D7, D9, Gherkin] La planche de référence : le rang 2 porte la tomate cerise
// et son trait, et la carotte est posée sur DEUX rangs — une seule tuile.
const CENTRALE = [
  ligne('tomate', 'noire de Crimée', 9, 'plants', 'rang', [1], 'en_place', 50),
  ligne('tomate', 'cerise', 5, 'plants', 'rang', [2], 'en_place', 50),
  ligne('carotte', '', 60, 'graines', 'rang', [3, 4], 'semee', 5),
]

// [D7] Les autres modes d'implantation, qui traversent le niveau 2 tels quels.
const OMBRE = [
  ligne('épinard', '', 2, 'm²', 'surface', [1], 'semee'),
  ligne('courge', 'butternut', 4, 'poquets', 'poquet', [2], 'en_place'),
  ligne('laitue', '', 12, 'plants', 'rang', [3], 'en_recolte', 30),
]

// [D11] Dépassement : 6 rangs occupés pour 5 déclarés, aucune tuile masquée.
const SERREE = [
  ligne('poireau', '', 18, 'plants', 'rang', [1, 2, 3], 'en_place'),
  ligne('salade', '', 6, 'plants', 'rang', [4], 'en_place'),
  ligne('radis', '', 1, 'm²', 'surface', [5], 'semee'),
  ligne('betterave', '', 9, 'plants', 'rang', [6], 'en_place'),
]

// [D4] Sans nombre de rangs : la tuile est dessinée, aucun rang libre proposé.
const EST = [ligne('courgette', '', 3, 'plants', 'rang', [1], 'en_place')]

// [D3] Pépinière : des lots, pas des rangs de semis — mais la plantation de
// basilic qui y a été faite reste dessinée en rang.
const SERRE = [ligne('basilic', '', 6, 'plants', 'rang', [1], 'en_place')]

// [US-232 / S2, S3, S5, CA10] Le journal du sol de la planche de référence :
// plus de huit interventions — le lien « Tout voir » apparaît —, une précision,
// une quantité, un rang, et une intervention d'une campagne PASSÉE, qui porte
// donc son année.
const SOL_CENTRALE = {
  total: 11,
  interventions: [
    intervention(101, '2026-09-12', 'paillage', { commentaire: 'de tonte', rang: 1 }),
    intervention(102, '2026-08-30', 'amendement', { commentaire: 'compost mûr', quantite: 2, unite: 'brouettes' }),
    intervention(103, '2026-07-04', 'desherbage'),
    intervention(104, '2026-06-18', 'binage', { rang: 3 }),
    intervention(105, '2026-05-02', 'amendement', { traitement: 'fumier composté' }),
    intervention(106, '2026-04-11', 'paillage', { commentaire: 'paille' }),
    intervention(107, '2026-03-20', 'binage'),
    // [S2] Hors campagne en cours : l'année s'écrit.
    intervention(108, '2025-11-08', 'amendement', { commentaire: 'compost' }),
  ],
}

// [CA10] Une seule intervention : ni « Tout voir », ni message d'absence.
const SOL_OMBRE = {
  total: 1,
  interventions: [intervention(120, '2026-09-01', 'paillage', { commentaire: 'de tonte' })],
}

const PARCELLES = [
  parcelle(1, 'planche-centrale', 60, 6, CENTRALE, { longueur: 12, has_observations: true, nb_observations: 3, sol: SOL_CENTRALE, rotation: ROTATION_CENTRALE }),
  parcelle(2, 'planche-ombre', 27, 5, OMBRE, { longueur: 9, sol: SOL_OMBRE, rotation: ROTATION_OMBRE }),
  parcelle(3, 'planche-serrée', 7, 5, SERREE, { rotation: ROTATION_SERREE }),
  // [CA13] Parcelle libre : aucune culture, son premier rang est proposé.
  // [US-229 / C10] Parcelle INACTIVE : la carte est rendue entière, le statut
  // le dit. Une parcelle inactive n'est pas une parcelle cassée.
  parcelle(4, 'planche-nord', 10, 4, [], { longueur: 5, actif: false, rotation: ROTATION_NORD }),
  // [D4, US-229 / CA6] Ni nombre de rangs, ni longueur, ni rien d'autre : la
  // carte « Caractéristiques » est un mur d'états manquants et doit rester
  // lisible — et la parcelle porte la pastille de l'index (C8).
  parcelle(5, 'planche-est', null, null, EST, {
    exposition: null, abri: null, paillage: null, type_sol: null,
    rotation: ROTATION_EST,
  }),
  {
    ...parcelle(6, 'SERRE', 2.5, null, SERRE, { lots: 3 }),
    est_pepiniere: true, type_pepiniere: 'chaude',
  },
]

// [US-230 / CA3] Les listes fermées de la fiche viennent du domaine, servies
// par `GET /plan`. Recopiées ici telles que le serveur les rend — la page de
// contrôle simule le serveur, elle ne réinvente pas le vocabulaire.
const VOCABULAIRES = {
  abri: { ferme: true, options: [
    { valeur: 'aucun', libelle: 'Aucun' }, { valeur: 'voile', libelle: 'Voile' },
    { valeur: 'chassis', libelle: 'Châssis' }, { valeur: 'tunnel', libelle: 'Tunnel' },
    { valeur: 'serre', libelle: 'Serre' }] },
  type_sol: { ferme: true, options: [
    { valeur: 'Argileux', libelle: 'Argileux' }, { valeur: 'Limoneux', libelle: 'Limoneux' },
    { valeur: 'Sableux', libelle: 'Sableux' }, { valeur: 'Humifère', libelle: 'Humifère' },
    { valeur: 'Calcaire', libelle: 'Calcaire' }] },
  exposition: { ferme: false, options: [
    { valeur: 'Sud', libelle: 'Sud' }, { valeur: 'Est', libelle: 'Est' },
    { valeur: 'Ouest', libelle: 'Ouest' }, { valeur: 'Nord', libelle: 'Nord' },
    { valeur: 'Mi-ombre', libelle: 'Mi-ombre' }] },
}

const PLAN = {
  vocabulaires: VOCABULAIRES,
  // [US-232 / CA2] La liste du domaine, telle que le serveur la sert.
  gestes_sol: ['paillage', 'amendement', 'desherbage', 'binage'],
  date_ref_effective: DATE_REF,
  total: PARCELLES.length,
  parcelles: PARCELLES,
  non_localisees: [],
  totaux: {
    superficie_totale_m2: 106.5, rangs_declares: 20, rangs_occupes: 17,
    occupation_rangs_pct: 85, parcelles_sans_nb_rangs: 2, parcelles_sans_longueur: 3,
    rangs_libres_par_parcelle: [],
  },
}

const PLAN_VIDE = {
  vocabulaires: VOCABULAIRES,
  gestes_sol: ['paillage', 'amendement', 'desherbage', 'binage'],
  date_ref_effective: DATE_REF, total: 0, parcelles: [], non_localisees: [],
  totaux: { superficie_totale_m2: 0, rangs_declares: 0, rangs_occupes: 0,
    occupation_rangs_pct: null, parcelles_sans_nb_rangs: 0, parcelles_sans_longueur: 0,
    rangs_libres_par_parcelle: [] },
}

const ETATS = {
  complet: { titre: 'Plan complet', plan: PLAN, role: 'owner' },
  // [CA12] Lecture seule : le détail entier, sans les intentions du rang libre.
  lecture: { titre: 'Lecture seule', plan: PLAN, role: 'lecteur' },
  vide: { titre: 'Aucune parcelle', plan: PLAN_VIDE, role: 'owner' },
  // [CA14] Échec : le message et la relance, sans valeur de repli.
  erreur: { titre: 'Échec de lecture', plan: null, role: 'owner' },
  // [US-230 / E5] Refus d'une valeur : le message vient du domaine, nomme la
  // borne, et se place SOUS le champ fautif — les autres modifications restent
  // à l'écran, et la carte reste en édition.
  refus: {
    titre: 'Refus d’une valeur', plan: PLAN, role: 'owner',
    refus: { champ: 'nb_rangs', message: 'un nombre de rangs va de 1 à 99 (ex : rangs=5)' },
  },
  // [US-230 / CA13] Échec réseau pendant l'enregistrement : la saisie est
  // conservée, l'erreur est affichée, la relance est proposée.
  reseau: {
    titre: 'Échec d’enregistrement', plan: PLAN, role: 'owner',
    reseau: 'Le serveur est injoignable pour le moment.',
  },
}

/** Données simulées — au rendu de cette page seulement, jamais à l'import. */
function simulerApi(etat) {
  api.potagers = async () => ({
    potagers: [{ id: 1, nom: 'Potager de démonstration', actif: true, role: etat.role }],
  })
  api.moi = async () => ({ id: 1, nom: 'Démonstration', email: 'demo@potager.test' })
  api.plan = async () => {
    if (!etat.plan) throw new Error('Le plan est indisponible pour le moment.')
    return etat.plan
  }
  // [CA1] L'onglet ne lit rien de plus que la Vue plan pour son dessin : ces
  // deux réponses ne nourrissent que la frise et la confiance (US-176, US-180).
  api.calendriersPlan = async () => ({ zone: null, cultures: {} })
  api.confiancesPlan = async () => ({ date: DATE_REF, cultures: {} })
  api.lireFileGestes = async () => ({ gestes: [], nb_en_attente: 0 })
  // [US-230] L'écriture, simulée : succès, refus du domaine, ou panne réseau.
  api.modifierParcelle = async (id, champs) => {
    if (etat.reseau) throw new Error(etat.reseau)
    if (etat.refus) {
      const e = new Error(etat.refus.message)
      e.champ = etat.refus.champ
      throw e
    }
    const p = etat.plan.parcelles.find((x) => x.id === id)
    return { ...p, ...champs, modifications: Object.keys(champs).map((c) => `${c} mis à jour`) }
  }
}

export default function PlanParcellesPreview() {
  const demande = new URLSearchParams(window.location.search).get('etat')
  const { theme, toggle } = useTheme()
  const [cle, setCle] = useState(ETATS[demande] ? demande : 'complet')

  const etat = ETATS[cle]
  simulerApi(etat)

  return (
    <AuthContextProvider>
      {/* [US-230 / E10] Le rôle est lu par `PotagerContext` AU MONTAGE :
          sans clé ici, changer de scénario laissait le contexte sur le rôle
          précédent, et la lecture seule ne se vérifiait pas. */}
      <PotagerContextProvider key={cle}>
        <AppContextProvider>
          {/* [CA8, CA10] Les sorties de l'onglet sont réelles : ici elles
              s'arrêtent à la page de contrôle, qui affiche la vue visée. */}
          <NavigationProvider vue="plan" onVue={(v) => console.info('[preview] aller →', v)}>
            <div className="min-h-dvh bg-bg p-4 flex flex-col gap-3">
              <h1 className="font-serif text-2xl font-bold text-txt">
                Onglet Parcelles — US-222 (niveau 2 du zoom)
              </h1>
              <div className="flex flex-wrap gap-2">
                {Object.entries(ETATS).map(([k, v]) => (
                  <Btn key={k} small kind={k === cle ? 'primary' : 'ghost'} onClick={() => setCle(k)}>
                    {v.titre}
                  </Btn>
                ))}
                <Btn small kind="soft" onClick={toggle}>
                  Thème {theme === 'dark' ? 'clair' : 'sombre'}
                </Btn>
              </div>
              <Plan key={cle} refresh={0} />
            </div>
          </NavigationProvider>
        </AppContextProvider>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
