// [US-327 / CA8, US-322] Page de contrôle visuel du plan vu du dessus, hors navigation.
//
// Rejoue la VRAIE vue sur une réponse simulée de `GET /plan` (et de `GET /plan/suivi`
// pour le suivi d'US-322) : potager complet, parcelle en travers, rang partagé,
// pépinière, parcelle inactive, aucune parcelle placée (zones), filtres, thème sombre.
//
// ⚠️ Valeurs de DÉMONSTRATION, d'après la maquette « Plan - Pistes » (12 novembre) :
// elles n'engagent aucune agronomie. Chargée en `lazy()` par `main.jsx` — un import
// statique contaminerait l'application réelle avec ces données.
import { useState } from 'react'
import { api } from '../lib/api.js'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import { AppContextProvider } from '../context/AppContext.jsx'
import { NavigationProvider } from '../context/NavigationContext.jsx'
import { FileGestesProvider } from '../context/FileGestesContext.jsx'
import { useTheme } from '../hooks/useTheme.js'
import PlanDessus from './PlanDessus.jsx'
import { Btn } from '../components/ui'

const DATE_REF = '2026-11-12'

const SEQ_SEMIS = ['semee', 'levee', 'en_recolte', 'terminee']
const SEQ_PLANT = ['plantee', 'en_recolte', 'terminee']

/** Les étapes d'une ligne, dans la forme de `cultures[].etapes` (US-320). */
function etapes(courante, { prevue = false, aConfirmer = false, date = '2026-10-20', semis = false } = {}) {
  const seq = semis ? SEQ_SEMIS : SEQ_PLANT
  const i = seq.indexOf(courante)
  return {
    serie_id: 1, etape: courante, etape_libelle: courante,
    etape_statut: prevue ? 'prevue' : 'validee', etape_date: date, etape_source: 'jardinier',
    a_confirmer: aConfirmer, a_liberer: false, rappel_le: null,
    etapes: seq.map((code, j) => ({
      code, libelle: code,
      statut: j < i ? 'validee' : j === i ? (prevue ? 'prevue' : 'validee') : 'prevue',
      date: j < i ? '2026-09-02' : j === i ? date : j === i + 1 ? '2026-12-15' : null,
      source: null,
    })),
  }
}

const culture = (nom, variete, quantite, e) => ({
  culture: nom, variete, nb_plants: quantite, unite: 'plants', type_organe: 'végétatif',
  surface_m2_par_plant: null, espacement_rang_cm: 40, famille: null, nb_observations: 0,
  has_observations: false, mode_implantation: 'rang', rangs: 1, quantite_par_rang: quantite,
  date_installation: '2026-09-02', numeros_rangs: [], phase: 'en_place', phase_depuis: null,
  phase_depuis_nature: null, nb_series: 1, etapes: e,
})

/** Un rang de `disposition.rangs` : culture, part (fraction) — ou libre. */
const rang = (numero, nom = null, variete = null, part = 1) => (nom
  ? { numero, libre: false, culture: nom, variete, unite: 'plants', part, part_m: null, part_source: part === 1 ? 'rang_entier' : 'jardinier' }
  : { numero, libre: true, culture: null, variete: null, unite: null })

function parcelle(id, nom, ordre, geometrie, { declares = null, rangs = [], cultures = [], pepiniere = null, lots = [] } = {}) {
  const occupes = new Set(rangs.filter((r) => !r.libre).map((r) => r.numero))
  return {
    id, nom, ordre, actif: true, exposition: null, ensoleillement: null, superficie_m2: geometrie.longueur_m * geometrie.largeur_m,
    type_sol: null, abri: null, paillage: null, nb_rangs: declares, longueur_m: geometrie.longueur_m, largeur_m: geometrie.largeur_m,
    largeur_deduite: false, largeur_incoherente: false, est_pepiniere: Boolean(pepiniere), type_pepiniere: pepiniere,
    cultures, occupation_pct: null, has_observations: false, nb_observations: 0,
    disposition: {
      rangs_declares: declares, rangs_occupes: occupes.size,
      rangs_libres: declares == null ? null : declares - occupes.size, depassement: 0,
      rangs, mode_numerotation: 'positions', nb_lots_en_cours: pepiniere ? lots.length : null,
      lots_en_cours: pepiniere ? lots : null,
    },
    sol: { interventions: [], total: 0 }, rotation: null, a_liberer: [],
    geometrie: {
      forme: geometrie.forme, placee: geometrie.x_m != null, a_placer: geometrie.x_m == null,
      x_m: geometrie.x_m ?? null, y_m: geometrie.y_m ?? null, longueur_m: geometrie.longueur_m,
      largeur_m: geometrie.largeur_m, rotation_deg: geometrie.rotation_deg ?? 0, sens_rangs: geometrie.sens_rangs ?? 'longueur',
      superficie_posee_m2: geometrie.longueur_m * geometrie.largeur_m, ecart_superficie: null,
    },
  }
}

const PARCELLES = [
  parcelle(1, 'Serre', 1, { forme: 'serre', x_m: 1, y_m: 1, longueur_m: 6, largeur_m: 4 }, {
    declares: 4,
    rangs: [rang(1, 'laitue', 'Batavia'), rang(2, 'mâche', null, 0.6), rang(2, 'épinard', 'Géant d’hiver', 0.4), rang(3, 'tomate', 'Cerise', 0.5), rang(4)],
    cultures: [
      culture('laitue', 'Batavia', 12, etapes('en_recolte', { date: '2026-10-28' })),
      culture('mâche', null, 40, etapes('levee', { semis: true, date: '2026-11-04' })),
      culture('épinard', 'Géant d’hiver', 30, etapes('levee', { semis: true, prevue: true, aConfirmer: true, date: DATE_REF })),
      culture('tomate', 'Cerise', 3, etapes('en_recolte', { date: '2026-08-10' })),
    ],
  }),
  parcelle(2, 'Planche centrale', 2, { forme: 'planche', x_m: 9, y_m: 1, longueur_m: 12, largeur_m: 5 }, {
    declares: 8,
    rangs: [
      rang(1, 'poireau', 'Bleu de Solaise'), rang(2, 'poireau', 'Carentan'),
      rang(3, 'chou de Bruxelles', 'Groninger', 0.6), rang(3, 'chou kale', 'Nero di Toscana', 0.4),
      rang(4, 'ail', 'Blanc'), rang(5, 'échalote', 'Jersey', 0.5), rang(6, 'fève', 'Aguadulce'), rang(7, 'phacélie', null), rang(8),
    ],
    cultures: [
      culture('poireau', 'Bleu de Solaise', 60, etapes('plantee', { date: '2026-07-02' })),
      culture('poireau', 'Carentan', 50, etapes('en_recolte', { date: '2026-10-15' })),
      culture('chou de Bruxelles', 'Groninger', 12, etapes('en_recolte', { date: '2026-10-20' })),
      culture('chou kale', 'Nero di Toscana', 9, etapes('en_recolte', { date: '2026-10-20' })),
      culture('ail', 'Blanc', 45, etapes('plantee', { date: '2026-10-25' })),
      culture('échalote', 'Jersey', 30, etapes('plantee', { date: '2026-10-25' })),
      culture('fève', 'Aguadulce', 40, etapes('levee', { semis: true, prevue: true, aConfirmer: true, date: DATE_REF })),
      culture('phacélie', null, 1, etapes('levee', { semis: true, date: '2026-09-20' })),
    ],
  }),
  // Tournée de 90° : 9 m de long posés dans la hauteur du plan (centre en 23 ; 5,5).
  parcelle(3, 'Planche est', 3, { forme: 'planche', x_m: 18.5, y_m: 4.5, longueur_m: 9, largeur_m: 2, rotation_deg: 90 }, {
    declares: 3,
    rangs: [rang(1, 'carotte', 'Nantaise'), rang(2, 'navet', 'Boule d’or'), rang(3, 'radis noir', null, 0.6)],
    cultures: [
      culture('carotte', 'Nantaise', 200, etapes('en_recolte', { semis: true })),
      culture('navet', 'Boule d’or', 80, etapes('levee', { semis: true, date: '2026-10-01' })),
      culture('radis noir', null, 40, etapes('semee', { semis: true, prevue: false, date: '2026-10-30' })),
    ],
  }),
  parcelle(4, 'Bac à salades', 4, { forme: 'bac', x_m: 12, y_m: 7.5, longueur_m: 5, largeur_m: 1.5, sens_rangs: 'travers' }, {
    declares: 5,
    rangs: [rang(1, 'laitue', 'Batavia blonde'), rang(2, 'roquette', null), rang(3, 'mâche', 'Verte de Cambrai'), rang(4), rang(5)],
    cultures: [
      culture('laitue', 'Batavia blonde', 8, etapes('plantee', { date: '2026-10-10' })),
      culture('roquette', null, 30, etapes('en_recolte', { semis: true })),
      culture('mâche', 'Verte de Cambrai', 40, etapes('semee', { semis: true, date: '2026-11-02' })),
    ],
  }),
  parcelle(5, 'Planche ombre', 7, { forme: 'planche', x_m: 1, y_m: 7, longueur_m: 9, largeur_m: 3 }, {
    declares: 4,
    rangs: [rang(1, 'mâche', 'Coquille'), rang(2, 'épinard', 'Monstrueux de Viroflay'), rang(3, 'persil', 'Frisé', 0.5), rang(4)],
    cultures: [
      culture('mâche', 'Coquille', 60, etapes('levee', { semis: true, date: '2026-10-12' })),
      culture('épinard', 'Monstrueux de Viroflay', 50, etapes('en_recolte', { semis: true })),
      culture('persil', 'Frisé', 10, etapes('en_recolte', { date: '2026-09-15' })),
    ],
  }),
  parcelle(6, 'Butte', 5, { forme: 'butte', x_m: 12, y_m: 10, longueur_m: 6, largeur_m: 4.5 }, {
    declares: 3,
    rangs: [rang(1, 'pomme de terre', 'Charlotte'), rang(2, 'topinambour', null, 0.5), rang(3)],
    cultures: [
      culture('pomme de terre', 'Charlotte', 20, etapes('en_recolte', { date: '2026-07-20' })),
      culture('topinambour', null, 6, etapes('plantee', { date: '2026-04-02' })),
    ],
  }),
  parcelle(7, 'Châssis', 6, { forme: 'pepiniere', x_m: 1, y_m: 11.5, longueur_m: 5, largeur_m: 2 }, {
    pepiniere: 'froide',
    lots: [
      { lot_id: 'semis-51', numero_lot: 51, culture: 'chou pommé', variete: 'Cœur de bœuf' },
      { lot_id: 'semis-42', numero_lot: 42, culture: 'fraisier', variete: 'Mara des bois' },
      { lot_id: 'semis-57', numero_lot: 57, culture: 'oignon', variete: 'Blanc de Paris' },
    ],
  }),
]

const INACTIVE = {
  id: 9, nom: 'Planche haricots', actif: false, ordre: 8, est_pepiniere: false, type_pepiniere: null,
  geometrie: { forme: 'planche', placee: true, a_placer: false, x_m: 19, y_m: 11, longueur_m: 3.5, largeur_m: 3, rotation_deg: 0, sens_rangs: 'longueur', superficie_posee_m2: 10.5, ecart_superficie: null },
}

const A_PLACER = parcelle(8, 'Carré aromates', 9, { forme: 'bac', x_m: null, y_m: null, longueur_m: 2, largeur_m: 2 }, {
  declares: 2, rangs: [rang(1, 'thym', null), rang(2)],
  cultures: [culture('thym', null, 4, etapes('plantee', { date: '2026-05-01' }))],
})

const PLAN = {
  parcelles: [...PARCELLES, A_PLACER],
  parcelles_inactives: [INACTIVE],
  total: 8,
  date_ref_effective: DATE_REF,
  non_localisees: [],
  potager_geometrie: { emprise_longueur_m: 25, emprise_largeur_m: 15, angle_deg: 0, orientation_nord: 'n' },
  filtres_plan: { a_confirmer: 2, en_recolte: 8, rangs_libres: 5 },
  totaux: {}, vocabulaires: {}, gestes_sol: [],
}

const sansPlace = (p) => ({ ...p, geometrie: { ...p.geometrie, placee: false, a_placer: true, x_m: null, y_m: null } })
const PLAN_ZONES = { ...PLAN, parcelles: PLAN.parcelles.map(sansPlace), parcelles_inactives: [], potager_geometrie: { orientation_nord: null } }
const PLAN_NORD_EST = { ...PLAN, potager_geometrie: { ...PLAN.potager_geometrie, orientation_nord: 'ne', angle_deg: -2.5 } }
const PLAN_VIDE = { ...PLAN, parcelles: [], parcelles_inactives: [], filtres_plan: { a_confirmer: 0, en_recolte: 0, rangs_libres: 0 } }

/** [US-322] Le suivi du chou de Bruxelles (Gherkin : lot #18, en récolte, 2,9 kg, trois notes). */
const SUIVI = {
  parcelle_id: 2, parcelle: 'Planche centrale', est_pepiniere: false,
  culture: 'chou de Bruxelles', variete: 'Groninger', quantite: 12, unite: 'plants',
  date_ref_effective: DATE_REF, rangs: [3], position_source: 'jardinier',
  place: { pieds: 12, places: 12, espacement_cm: 60, longueur_m: 7.2, metres_occupes: 7.2, metres_libres: 0, depassement_pieds: 0 },
  etapes: etapes('en_recolte', { date: '2026-10-20' }),
  recolte: { quantite: 2.9, unite: 'kg' },
  origine: { type: 'pepiniere', numero_lot: 18, date_semis: '2026-04-02', godets: 14, plantes: 12, date_plantation: '2026-06-10' },
  notes: [
    { id: 3, date: '2026-11-08', texte: 'Premiers choux bien fermés en bas de tige.', dictee: true },
    { id: 2, date: '2026-10-20', texte: 'Première récolte, 600 g.', dictee: false },
    { id: 1, date: '2026-09-14', texte: 'Quelques chenilles de piéride, retirées à la main.', dictee: false },
  ],
}

const ETATS = {
  complet: { titre: 'Potager complet', plan: PLAN },
  nord: { titre: 'Nord en haut à droite, plan tourné', plan: PLAN_NORD_EST },
  zones: { titre: 'Aucune parcelle placée (zones)', plan: PLAN_ZONES },
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
  api.suiviCulture = async ({ culture: nom, variete }) => {
    if (nom === 'chou de Bruxelles') return SUIVI
    const p = PARCELLES.find((x) => x.cultures.some((c) => c.culture === nom && (c.variete || null) === (variete || null)))
    const c = p?.cultures.find((x) => x.culture === nom && (x.variete || null) === (variete || null))
    return {
      ...SUIVI, parcelle_id: p?.id, parcelle: p?.nom, culture: nom, variete, quantite: c?.nb_plants,
      rangs: p?.disposition.rangs.filter((r) => r.culture === nom).map((r) => r.numero) ?? [],
      etapes: c?.etapes, recolte: null, place: null,
      origine: { type: 'semis_direct', date: '2026-09-02' }, notes: [],
    }
  }
  api.lireFileGestes = async () => ({ gestes: [], recents: [] })
}

export default function PlanDessusPreview() {
  const demande = new URLSearchParams(window.location.search).get('etat')
  const { theme, toggle } = useTheme()
  const [cle, setCle] = useState(ETATS[demande] ? demande : 'complet')
  const etat = ETATS[cle]
  simulerApi(etat)
  const [sortie, setSortie] = useState(null)

  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <AppContextProvider>
          <NavigationProvider vue="plan-vue" onVue={(v) => setSortie(v)}>
          <FileGestesProvider>
          <div className="min-h-dvh bg-bg p-4 flex flex-col gap-3">
            <h1 className="font-serif text-2xl font-bold text-txt">Plan vu du dessus — US-327 / US-322</h1>
            <div className="flex flex-wrap gap-2">
              {Object.entries(ETATS).map(([k, v]) => (
                <Btn key={k} small kind={k === cle ? 'primary' : 'ghost'} onClick={() => setCle(k)}>{v.titre}</Btn>
              ))}
              <Btn small kind="soft" onClick={toggle}>Thème {theme === 'dark' ? 'clair' : 'sombre'}</Btn>
            </div>
            {sortie && <p role="status" className="text-[13px] text-txt2">Sortie demandée : {sortie}</p>}
            <PlanDessus key={cle} refresh={0} />
          </div>
          </FileGestesProvider>
          </NavigationProvider>
        </AppContextProvider>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
