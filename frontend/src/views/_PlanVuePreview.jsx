// [US-200 / CA11] Page de contrôle visuel de la Vue plan, hors navigation
// applicative — sur le modèle de `/fiche-calendrier` (US-183 / CA18).
//
// Rejoue la VRAIE vue sur une réponse simulée de `GET /plan`, dans sa forme
// exacte, pour que les cas qu'un potager réel ne présente pas tous en même
// temps se vérifient d'un coup d'œil : carte normale, les trois formes, poquets
// au-delà de douze, rang libre, parcelle sans nombre de rangs (avec et sans
// culture), dépassement, pépinière avec une plantation, cultures non
// localisées, thème sombre.
//
// ⚠️ Valeurs de DÉMONSTRATION : elles servent au contrôle visuel, elles
// n'engagent aucune agronomie. Chargée en `lazy()` par `main.jsx` — un import
// statique contaminerait l'application réelle avec ces données.
import { useState } from 'react'
import { api } from '../lib/api.js'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import { AppContextProvider } from '../context/AppContext.jsx'
import { useTheme } from '../hooks/useTheme.js'
import PlanVue from './PlanVue.jsx'
import { Btn } from '../components/ui'

const DATE_REF = '2026-09-23'

/** Une ligne de culture dans la forme exacte de `GET /plan` (US-194, US-198). */
const ligne = (culture, variete, quantite, unite, mode, numeros, phase, espacement = null) => ({
  culture, variete, nb_plants: quantite, unite,
  type_organe: 'végétatif', surface_m2_par_plant: null, famille: null,
  nb_observations: 0, has_observations: false,
  espacement_rang_cm: espacement,
  mode_implantation: mode,
  rangs: numeros.length,
  quantite_par_rang: Math.round((quantite / numeros.length) * 10) / 10,
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
    const ligneSemee = c.unite === 'ml'
    const places = longueur && espacement && !surface && !ligneSemee
      ? Math.max(1, Math.floor((longueur * 100) / espacement))
      : null
    const prises = places == null ? null : Math.min(places, Math.round(c.quantite_par_rang))
    if (places && exemple == null) exemple = { nombre: places, culture: c.culture }
    for (const n of c.numeros_rangs) {
      rangs.push({
        numero: n, libre: false, culture: c.culture, variete: c.variete, unite: c.unite,
        espacement_rang_cm: espacement ?? null,
        places,
        places_prises: prises,
        places_restantes: places == null ? null : Math.max(0, places - Math.round(c.quantite_par_rang)),
        depassement_places: places == null ? null : Math.max(0, Math.round(c.quantite_par_rang) - places),
        ...(ligneSemee && longueur ? {
          part_semee: Math.min(1, c.quantite_par_rang / longueur),
          metres_restants: Math.max(0, longueur - c.quantite_par_rang),
          depassement_metres: Math.max(0, c.quantite_par_rang - longueur),
        } : {}),
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

const parcelle = (id, nom, superficie, declares, cultures, extra = {}) => {
  const longueur = extra.longueur ?? null
  // [US-225 / CA6] La largeur ne se déclare pas : le serveur la DÉDUIT de la
  // superficie, et signale celle qui ne tient pas debout (CA7).
  const largeur = longueur && superficie ? Math.round((superficie / longueur) * 100) / 100 : null
  return {
    id, nom, superficie_m2: superficie, exposition: 'sud', abri: null, paillage: null,
    nb_rangs: declares, ordre: id, est_pepiniere: false,
    longueur_m: longueur,
    largeur_m: largeur,
    largeur_deduite: largeur != null,
    largeur_incoherente: largeur != null && largeur < 0.2,
    cultures, occupation_pct: null, has_observations: false, nb_observations: 0,
    disposition: disposition(declares, cultures, extra),
    ...extra,
  }
}

// ── Le plan de démonstration ─────────────────────────────────────────────────

// Carte de référence du Gherkin : 12 m², 4 rangs sur 5, les trois formes et un
// rang libre. 8 plants font 100 %, 5 en font 62 %, 3 en font 38 %, et les 2 m²
// de carotte sont à eux seuls leur maximum — donc pleine longueur.
const CENTRALE = [
  // [US-228] La piste de référence du Gherkin : 24 places, 9 prises, 15 restantes.
  ligne('tomate', 'noire de Crimée', 9, 'plants', 'rang', [1], 'en_place', 50),
  // [P3] Une seule place prise sur vingt-quatre : le plancher de lisibilité.
  ligne('tomate', 'cerise', 1, 'plants', 'rang', [2], 'en_place', 50),
  // [P2] 240 places à 5 cm : seize fentes, un pictogramme pour quinze graines.
  ligne('carotte', '', 60, 'graines', 'rang', [3], 'semee', 5),
  // [P7] Semis en ligne : 3 m sur 12, sans places ni colonne de reste.
  ligne('carotte', 'de Colmar', 3, 'ml', 'rang', [4], 'semee', 5),
  // [P8] Semis en surface : la trame d'US-200 et le mode dégradé.
  ligne('épinard', '', 2, 'm²', 'surface', [5], 'semee'),
  // [P6] Espacement inconnu dans une parcelle mesurée : mode dégradé, lui aussi.
  ligne('mâche', '', 24, 'plants', 'rang', [6], 'semee'),
]

// Poquets, dont un rang au-delà de douze : douze segments et « ×18 ».
const COURGES = [
  ligne('courge', 'butternut', 4, 'poquets', 'poquet', [1], 'en_place'),
  ligne('potiron', '', 3, 'poquets', 'poquet', [2], 'en_recolte'),
  ligne('haricot', 'à rames', 18, 'poquets', 'poquet', [3], 'en_place'),
]

const OMBRE = [
  // [P4] Le rang surchargé du Gherkin : 22 places, 26 pieds, « +4 ».
  ligne('tomate', 'cœur de bœuf', 26, 'plants', 'rang', [1], 'en_recolte', 40),
  // [P7] Un semis en ligne plus long que le rang : la piste est pleine.
  ligne('radis', '', 11, 'ml', 'rang', [2], 'semee', 4),
  ligne('laitue', '', 12, 'plants', 'rang', [3], 'en_recolte', 30),
]

// [V10] Dépassement : 6 rangs occupés pour 5 déclarés, aucune ligne masquée.
// [V12] Le poireau est posé sur trois rangs : ils sont groupés et les deux
// suivants n'affichent plus que la quantité.
const SERREE = [
  ligne('poireau', '', 18, 'plants', 'rang', [1, 2, 3], 'en_place'),
  ligne('salade', '', 6, 'plants', 'rang', [4], 'en_place'),
  ligne('radis', '', 1, 'm²', 'surface', [5], 'semee'),
  ligne('betterave', '', 9, 'plants', 'rang', [6], 'en_place'),
]

// [V9] Sans nombre de rangs : les cultures restent dessinées, aucun rang libre.
const EST = [ligne('courgette', '', 3, 'plants', 'rang', [1], 'en_place')]

// [V8] Pépinière : des lots, pas des rangs de semis — mais la plantation de
// basilic qui y a été faite reste dessinée en rang, sous le compte des lots.
const SERRE = [ligne('basilic', '', 6, 'plants', 'rang', [1], 'en_place')]

const PLAN = {
  date_ref_effective: DATE_REF,
  total: 7,
  parcelles: [
    // [P1, P9, P11] Mesurée : places partout où l'espacement est connu, rangs
    // libres avec leur capacité d'exemple, dimensions en en-tête.
    parcelle(1, 'planche-centrale', 69, 8, CENTRALE, { longueur: 12 }),
    parcelle(2, 'planche-courges', 8, 3, COURGES),
    parcelle(3, 'planche-ombre', 27, 5, OMBRE, { longueur: 9 }),
    parcelle(4, 'planche-serrée', 7, 5, SERREE),
    // [P6, P12] Sans longueur : mode dégradé partout, « N places ? », et les
    // deux mentions d'absence cumulées.
    parcelle(5, 'planche-est', null, null, EST),
    parcelle(6, 'planche-nord', null, null, []),
    // [P11, US-225 / CA7] 5 m² annoncés longs de 100 m : 5 cm de large. La
    // largeur incohérente est dite, jamais corrigée.
    parcelle(8, 'planche-salade', 5, 2,
      [ligne('laitue', '', 4, 'plants', 'rang', [1], 'en_place', 30)],
      { longueur: 100 }),
    { ...parcelle(7, 'SERRE', 2.5, null, SERRE, { lots: 3 }), est_pepiniere: true },
  ],
  // [V17] Une culture dont la parcelle n'a jamais été dite.
  non_localisees: [
    { culture: 'tomate', variete: 'green zebra', nb_plants: 4, unite: 'plants', mode_implantation: 'rang' },
  ],
  totaux: {
    superficie_totale_m2: 39.5,
    rangs_declares: 18,
    rangs_occupes: 16,
    occupation_rangs_pct: 89,
    parcelles_sans_nb_rangs: 3,
    // [P14, RT13] Un compte de parcelles — jamais un total de places.
    parcelles_sans_longueur: 4,
    rangs_libres_par_parcelle: [
      { parcelle_id: 1, parcelle: 'planche-centrale', rangs_libres: 1 },
      { parcelle_id: 2, parcelle: 'planche-courges', rangs_libres: 0 },
      { parcelle_id: 3, parcelle: 'planche-ombre', rangs_libres: 2 },
      { parcelle_id: 4, parcelle: 'planche-serrée', rangs_libres: 0 },
      { parcelle_id: 5, parcelle: 'planche-est', rangs_libres: null },
      { parcelle_id: 6, parcelle: 'planche-nord', rangs_libres: null },
      { parcelle_id: 7, parcelle: 'SERRE', rangs_libres: null },
      { parcelle_id: 8, parcelle: 'planche-salade', rangs_libres: 1 },
    ],
  },
}

/** Plan vide — l'état « aucune parcelle » du CA8. */
const PLAN_VIDE = {
  date_ref_effective: DATE_REF, total: 0, parcelles: [], non_localisees: [],
  totaux: { superficie_totale_m2: 0, rangs_declares: 0, rangs_occupes: 0,
    occupation_rangs_pct: null, parcelles_sans_nb_rangs: 0, parcelles_sans_longueur: 0,
    rangs_libres_par_parcelle: [] },
}

/**
 * [CA9] Le premier jour : aucune parcelle n'a de nombre de rangs. L'écran reste
 * pleinement lisible — chaque culture a son trait, chaque carte sa mention.
 */
const PLAN_PREMIER_JOUR = {
  ...PLAN,
  parcelles: PLAN.parcelles
    .filter((p) => !p.est_pepiniere)
    .map((p) => ({
      ...p, nb_rangs: null, longueur_m: null, largeur_m: null,
      largeur_deduite: false, largeur_incoherente: false,
      disposition: disposition(null, p.cultures),
    })),
  totaux: { ...PLAN.totaux, rangs_declares: 0, rangs_occupes: 0, occupation_rangs_pct: null,
    parcelles_sans_nb_rangs: 6, parcelles_sans_longueur: 6,
    rangs_libres_par_parcelle: PLAN.totaux.rangs_libres_par_parcelle.map((l) => ({ ...l, rangs_libres: null })) },
}

const ETATS = {
  complet: { titre: 'Plan complet', plan: PLAN },
  premier_jour: { titre: 'Premier jour (aucun nombre de rangs)', plan: PLAN_PREMIER_JOUR },
  vide: { titre: 'Aucune parcelle', plan: PLAN_VIDE },
  erreur: { titre: 'Échec de lecture', plan: null },
}

/** Données simulées — au rendu de cette page seulement, jamais à l'import. */
function simulerApi(etat) {
  api.potagers = async () => ({ potagers: [{ id: 1, nom: 'Potager de démonstration', actif: true, role: 'owner' }] })
  api.moi = async () => ({ id: 1, nom: 'Démonstration', email: 'demo@potager.test' })
  api.plan = async () => {
    if (!etat.plan) throw new Error('Le plan est indisponible pour le moment.')
    return etat.plan
  }
}

export default function PlanVuePreview() {
  const demande = new URLSearchParams(window.location.search).get('etat')
  const { theme, toggle } = useTheme()
  const [cle, setCle] = useState(ETATS[demande] ? demande : 'complet')

  const etat = ETATS[cle]
  simulerApi(etat)

  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <AppContextProvider>
          <div className="min-h-dvh bg-bg p-4 flex flex-col gap-3">
            <h1 className="font-serif text-2xl font-bold text-txt">Vue plan — US-200 / US-228</h1>
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
            <PlanVue key={cle} refresh={0} />
          </div>
        </AppContextProvider>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
