import { useState } from 'react'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import { AppContextProvider } from '../context/AppContext.jsx'
import { NavigationProvider } from '../context/NavigationContext.jsx'
import { FileGestesProvider } from '../context/FileGestesContext.jsx'
import { RelectureAuRetourProvider } from '../hooks/useRelectureAuRetour.jsx'
import { api } from '../lib/api.js'
import { useTheme } from '../hooks/useTheme.js'
import FicheLot from '../components/FicheLot.jsx'
import Pepiniere from './Pepiniere.jsx'
import { Btn } from '../components/ui'

/**
 * Page de contrôle visuel de la fiche d'un lot [US-216], hors navigation
 * applicative. Rejoue les états de la v2 (§ 3 panneau, § 3c terrain) avec des lots
 * dans la forme exacte de `GET /pepiniere/lots/{numero}`, sans rien écrire : un geste
 * déposé est simplement noté dans la console.
 *
 * `?etat=germination|retard|endurcissement|froide|dormant|termine|cloture|sans_semis|
 *  lecture_seule|compteur` · `&forme=panneau|modale` · `&theme=sombre`
 *
 * `?vue=ecran` monte le VRAI écran Pépinière (liste + panneau « Lot sélectionné ») dans la
 * coquille de l'application — barre du haut, zone qui défile — avec des lots simulés : de
 * quoi vérifier que la fin de la fiche (« Détail du lot ») reste atteignable à chaque
 * résolution.
 *
 * 375 px = largeur de la fenêtre du navigateur (modale plein écran) ; le panneau
 * desktop se juge sur une fenêtre d'au moins 1100 px.
 */

const ECH_VIDE = { etat: null, du: null, au: null, dans_jours: null, retard_jours: null, libelle: null, periode: null, raison: null }
const ECH = (date_reference, plus = {}) => ({
  date_reference,
  repiquage: ECH_VIDE,
  mise_en_terre: ECH_VIDE,
  endurcissement: { etat: null, jour: null, sur: null, termine: false, libelle: null, raison: null },
  dormance: { est_dormant: false, jours_sans_geste: 4, seuil_jours: 60, libelle: null },
  raisons: [],
  ...plus,
})

const BASE = {
  lot_id: 'semis-7', semis_id: 7, numero_lot: 128, culture: 'chou', variete: 'frisé',
  date_semis: '2026-09-01', date_derniere_mise_en_godet: null, parcelle: 'Serre',
  emplacement: { parcelle_id: 2, nom: 'Serre', type_pepiniere: 'chaude', origine: 'semis' },
  graines_semees: 48, unite: 'graines', graines_soldees: 0, graines_en_germination: 48,
  plants_obtenus: 0, nb_mises_en_godet: 0, nb_plantes: 0, nb_vendus: 0, nb_pertes_godet: 0,
  stock_residuel_godet: 0, etat_germination: 'en_cours', taux_germination: 0,
  incoherence_saisie: false, sans_semis_rattache: false, cloture: false, date_cloture: null,
  famille: 'Brassicacées', action_suggeree: null,
  echeances: ECH('2026-09-19'),
}

const EN_GODET = {
  graines_soldees: 48, graines_en_germination: 0, plants_obtenus: 40, nb_mises_en_godet: 1,
  stock_residuel_godet: 40, etat_germination: 'close', taux_germination: 83,
  date_derniere_mise_en_godet: '2026-09-14',
}

const ETATS = {
  germination: {
    titre: 'En germination',
    lot: {
      ...BASE,
      action_suggeree: { code: 'noter_levee', libelle: 'Noter la levée' },
      echeances: ECH('2026-09-19', {
        repiquage: { ...ECH_VIDE, etat: 'a_venir', du: '2026-09-23', au: '2026-09-25', dans_jours: 4, libelle: 'Repiquage dans 4 j' },
      }),
    },
  },
  retard: {
    titre: 'En retard de repiquage',
    lot: {
      ...BASE,
      action_suggeree: { code: 'repiquer', libelle: 'Repiquer en godet' },
      echeances: ECH('2026-09-19', {
        repiquage: { ...ECH_VIDE, etat: 'en_retard', du: '2026-09-11', au: '2026-09-13', retard_jours: 6, libelle: 'Repiquage en retard de 6 j' },
      }),
    },
  },
  endurcissement: {
    titre: 'En endurcissement',
    lot: {
      ...BASE, ...EN_GODET,
      action_suggeree: { code: 'mettre_en_terre', libelle: 'Mettre en terre' },
      echeances: ECH('2026-09-19', {
        mise_en_terre: { ...ECH_VIDE, etat: 'a_venir', du: '2026-09-26', au: '2026-10-03', dans_jours: 7 },
        endurcissement: { etat: 'en_cours', jour: 3, sur: 7, termine: false, libelle: 'Endurcissement J+3/7', raison: null },
      }),
    },
  },
  froide: {
    titre: 'En godet, pépinière froide',
    lot: {
      ...BASE, ...EN_GODET,
      emplacement: { parcelle_id: 3, nom: 'Châssis froid', type_pepiniere: 'froide', origine: 'deplacement' },
      action_suggeree: null,
      echeances: ECH('2026-09-19', {
        mise_en_terre: { ...ECH_VIDE, etat: 'a_venir', du: '2026-10-05', au: '2026-10-12', dans_jours: 16 },
        endurcissement: { etat: 'froide', jour: null, sur: null, termine: false, libelle: 'en pépinière froide', raison: null },
      }),
    },
  },
  dormant: {
    titre: 'Dormant',
    lot: {
      ...BASE, ...EN_GODET, date_semis: '2026-06-01',
      action_suggeree: { code: 'cloturer', libelle: 'Clôturer le lot' },
      echeances: ECH('2026-09-19', {
        mise_en_terre: { ...ECH_VIDE, etat: 'depassee', du: '2026-07-10', au: '2026-07-20', retard_jours: 61 },
        dormance: { est_dormant: true, jours_sans_geste: 75, seuil_jours: 60, libelle: 'Dormant — rien depuis 75 j', dernier_geste: '2026-07-06' },
      }),
    },
  },
  termine: {
    titre: 'Terminé',
    lot: {
      ...BASE, ...EN_GODET, stock_residuel_godet: 0, nb_plantes: 36, nb_pertes_godet: 4,
      date_dernier_geste: '2026-05-30',
      echeances: ECH('2026-09-19'),
    },
  },
  cloture: {
    titre: 'Clôturé',
    lot: {
      ...BASE, ...EN_GODET, stock_residuel_godet: 0, cloture: true, date_cloture: '2026-09-10',
      echeances: ECH('2026-09-19'),
    },
  },
  sans_semis: {
    titre: 'Sans semis rattaché',
    lot: {
      ...BASE, lot_id: 'sans-semis-tomate', semis_id: null, numero_lot: null, culture: 'tomate', variete: null,
      date_semis: null, sans_semis_rattache: true, parcelle: null, emplacement: null,
      graines_semees: 0, graines_en_germination: 0, plants_obtenus: 20, nb_mises_en_godet: 1,
      stock_residuel_godet: 20, etat_germination: 'indeterminee', taux_germination: null,
      echeances: ECH('2026-09-19', { raisons: ['date de semis inconnue'] }),
    },
  },
  lecture_seule: {
    titre: 'Lecture seule',
    role: 'viewer',
    lot: {
      ...BASE,
      action_suggeree: { code: 'repiquer', libelle: 'Repiquer en godet' },
      echeances: ECH('2026-09-19', {
        repiquage: { ...ECH_VIDE, etat: 'en_retard', du: '2026-09-11', au: '2026-09-13', retard_jours: 6 },
      }),
    },
  },
  compteur: {
    titre: 'Compteur ouvert',
    compteur: true,
    lot: {
      ...BASE, nb_leves: 40, moyenne_levee_culture: 75,
      action_suggeree: { code: 'noter_levee', libelle: 'Noter la levée' },
      echeances: ECH('2026-09-19', {
        repiquage: { ...ECH_VIDE, etat: 'a_venir', du: '2026-09-23', au: '2026-09-25', dans_jours: 4 },
      }),
    },
  },
}

/** Données simulées — au rendu de cette page seulement, jamais à l'import. */
function simulerApi(role) {
  api.potagers = async () => ({ potagers: [{ id: 1, nom: 'Potager de démonstration', actif: true, role }] })
  api.moi = async () => ({ id: 1, nom: 'Démonstration', email: 'demo@potager.test' })
  api.lireFileGestes = async () => ({ gestes: [], recents: [] })
  api.preparerGeste = async (corps) => {
    console.info('[US-216] geste préparé', corps)
    return { phrase: `${corps.action} (démo)`, compagnon_actif: true, lien: null, en_attente: 1 }
  }
}

/** Lots simulés de l'écran complet — dans la forme exacte de `GET /pepiniere/lots`. */
function simulerEcran() {
  // Un lot par état de la page, numérotés à la suite : de quoi remplir la liste.
  const uniques = Object.values(ETATS)
    .filter((e) => e.lot.numero_lot != null)
    .map((e, i) => ({
      ...e.lot, numero_lot: 128 + i, lot_id: `semis-${128 + i}`, semis_id: 7 + i,
      stock_residuel_godet: e.lot.stock_residuel_godet ?? 0,
    }))
  api.pepiniereLots = async () => ({
    lots: uniques, total: uniques.length, date_ref_effective: '2026-09-19', resume: {},
    pepinieres: [{ id: 2, nom: 'Serre' }, { id: 3, nom: 'Châssis froid' }],
  })
  api.pepiniereLot = async (numero) => {
    const l = uniques.find((x) => x.numero_lot === Number(numero))
    if (!l) { const e = new Error('404'); e.statut = 404; throw e }
    return l
  }
  api.godetsDetail = async () => ({ semis: [], godets: [], plantations: [], deplacements: [], ventes: [], pertes_godet: [] })
}

/** La coquille de l'application, en réduit : barre du haut de 58 px, puis la zone qui défile. */
function EcranComplet() {
  simulerApi('owner')
  simulerEcran()
  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <AppContextProvider>
          <NavigationProvider vue="pepiniere" onVue={() => {}}>
            <FileGestesProvider>
              <div className="flex flex-col h-dvh bg-bg">
                <div className="h-[58px] shrink-0 bg-brand text-white flex items-center px-6 font-serif font-bold">Potager</div>
                <main className="flex-1 overflow-y-auto min-h-0">
                  <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-4 pb-7">
                    <Pepiniere refresh={0} />
                  </div>
                </main>
              </div>
            </FileGestesProvider>
          </NavigationProvider>
        </AppContextProvider>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}

export default function FicheLotPreview() {
  return new URLSearchParams(window.location.search).get('vue') === 'ecran' ? <EcranComplet /> : <Etats />
}

function Etats() {
  const params = new URLSearchParams(window.location.search)
  const { theme, toggle } = useTheme()
  const [cle, setCle] = useState(ETATS[params.get('etat')] ? params.get('etat') : 'retard')
  const [forme, setForme] = useState(params.get('forme') === 'panneau' ? 'panneau' : 'modale')
  const [ouverte, setOuverte] = useState(true)
  const e = ETATS[cle]
  simulerApi(e.role ?? 'owner')

  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <AppContextProvider>
          <NavigationProvider vue="pepiniere" onVue={() => {}}>
            <FileGestesProvider>
              <RelectureAuRetourProvider relire={() => {}}>
                <div className="min-h-dvh bg-bg p-4 flex flex-col gap-3">
                  <h1 className="font-serif text-2xl font-bold text-txt">Fiche d’un lot — US-216</h1>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(ETATS).map(([k, v]) => (
                      <Btn key={k} small kind={k === cle ? 'primary' : 'ghost'} onClick={() => { setCle(k); setOuverte(true) }}>
                        {v.titre}
                      </Btn>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Btn small kind={forme === 'modale' ? 'primary' : 'ghost'} onClick={() => setForme('modale')}>Fenêtre</Btn>
                    <Btn small kind={forme === 'panneau' ? 'primary' : 'ghost'} onClick={() => setForme('panneau')}>Panneau</Btn>
                    <Btn small kind="soft" onClick={() => setOuverte(true)} disabled={ouverte}>Rouvrir</Btn>
                    <Btn small kind="soft" onClick={toggle}>Thème {theme === 'dark' ? 'clair' : 'sombre'}</Btn>
                  </div>
                  {ouverte && (
                    <div className={forme === 'panneau' ? 'max-w-[460px]' : ''}>
                      <FicheLot
                        key={`${cle}-${forme}`}
                        lot={e.lot} forme={forme} nbPepinieres={2} dateRef="2026-09-19"
                        // La page montre le compteur : le geste de levée y est forcé (US-212 pas livrée).
                        leveeDisponible compteurInitial={Boolean(e.compteur)}
                        onClose={() => setOuverte(false)}
                        onOuvrirDetail={() => console.info('[US-216] Détail du lot')}
                        onOuvrirCulture={(c) => console.info('[US-216] Fiche culture', c)}
                      />
                    </div>
                  )}
                </div>
              </RelectureAuRetourProvider>
            </FileGestesProvider>
          </NavigationProvider>
        </AppContextProvider>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
