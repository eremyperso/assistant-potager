import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import { AppContextProvider } from '../context/AppContext.jsx'
import { NavigationProvider } from '../context/NavigationContext.jsx'
import { FileGestesProvider } from '../context/FileGestesContext.jsx'
import { NotificationsProvider } from '../context/NotificationsContext.jsx'
import { api } from '../lib/api.js'
import { useTheme } from '../hooks/useTheme.js'
import Pepiniere from './Pepiniere.jsx'
import { Btn } from '../components/ui'

/**
 * Page de contrôle visuel de l'onglet « Aujourd'hui » [US-215 / CA16], hors navigation
 * applicative. Monte le VRAI écran Pépinière avec des lots dans la forme exacte de
 * `GET /pepiniere/lots` : en retard, à repiquer, en endurcissement, en pépinière
 * froide, dormant, sans échéance calculable. Un geste déposé n'écrit rien : la
 * notification de dépôt s'affiche comme dans l'application.
 *
 * `?etat=nominal|vide|une_pepiniere|lecture_seule|echec` · bouton de thème en haut.
 */

const ECH_VIDE = { etat: null, du: null, au: null, dans_jours: null, retard_jours: null, libelle: null, periode: null, raison: null }
const ECH = (plus = {}) => ({
  date_reference: '2026-09-19',
  repiquage: ECH_VIDE,
  mise_en_terre: ECH_VIDE,
  endurcissement: { etat: null, jour: null, sur: null, termine: false, libelle: null, raison: null },
  dormance: { est_dormant: false, jours_sans_geste: 4, seuil_jours: 60, libelle: null },
  raisons: [],
  ...plus,
})
const SERRE = { parcelle_id: 2, nom: 'Serre', type_pepiniere: 'chaude', origine: 'semis' }
const CHASSIS = { parcelle_id: 3, nom: 'Châssis froid', type_pepiniere: 'froide', origine: 'mise_en_godet' }

const lot = (n, o) => ({
  lot_id: `semis-${n}`, semis_id: n, numero_lot: n, variete: null, date_semis: '2026-09-01',
  date_derniere_mise_en_godet: null, parcelle: 'Serre', emplacement: SERRE,
  graines_semees: 48, unite: 'graines', graines_soldees: 0, graines_en_germination: 48,
  plants_obtenus: 0, nb_mises_en_godet: 0, nb_plantes: 0, nb_vendus: 0, nb_pertes_godet: 0,
  stock_residuel_godet: 0, etat_germination: 'en_cours', taux_germination: 0,
  incoherence_saisie: false, sans_semis_rattache: false, cloture: false, date_cloture: null,
  famille: 'Brassicacées', action_suggeree: null, echeances: ECH(), ...o,
})
const GODET = (n) => ({
  graines_soldees: 48, graines_en_germination: 0, plants_obtenus: n, nb_mises_en_godet: 1,
  stock_residuel_godet: n, etat_germination: 'close', taux_germination: 85,
})

const LOTS = [
  lot(128, { culture: 'chou', variete: 'frisé', rang_urgence: 1,
    echeances: ECH({ repiquage: { ...ECH_VIDE, etat: 'en_retard', retard_jours: 6, du: '2026-09-11', au: '2026-09-13' } }),
    action_suggeree: { code: 'repiquer', libelle: 'Repiquer' } }),
  lot(131, { culture: 'tomate', variete: 'cerise', date_semis: '2026-09-15', graines_semees: 60, graines_en_germination: 60, rang_urgence: 2,
    famille: 'Solanacées',
    echeances: ECH({ repiquage: { ...ECH_VIDE, etat: 'a_repiquer', du: '2026-09-18', au: '2026-09-22' } }),
    action_suggeree: { code: 'repiquer', libelle: 'Repiquer' } }),
  lot(119, { culture: 'poireau', variete: 'Bleu de Solaise', date_semis: '2026-07-20', ...GODET(41), rang_urgence: 3,
    famille: 'Amaryllidacées',
    echeances: ECH({ endurcissement: { etat: 'en_cours', jour: 3, sur: 7, termine: false }, mise_en_terre: { ...ECH_VIDE, etat: 'a_venir', dans_jours: 4, du: '2026-09-23', au: '2026-09-30' } }),
    action_suggeree: { code: 'mettre_en_terre', libelle: 'Mettre en terre' } }),
  lot(122, { culture: 'laitue', variete: "Merveille d'hiver", date_semis: '2026-08-25', ...GODET(24), rang_urgence: 4,
    emplacement: CHASSIS, famille: 'Astéracées',
    echeances: ECH({ endurcissement: { etat: 'froide' }, mise_en_terre: { ...ECH_VIDE, etat: 'a_venir', dans_jours: 7, du: '2026-09-26', au: '2026-10-03' } }) }),
  lot(135, { culture: 'mâche', date_semis: '2026-09-10', graines_semees: 100, graines_en_germination: 100, rang_urgence: 5,
    famille: 'Valérianacées',
    echeances: ECH({ raisons: ['délai semis → godet non renseigné pour la culture « mâche »'] }) }),
  lot(103, { culture: 'basilic', variete: 'grand vert', date_semis: '2026-06-12', ...GODET(6), rang_urgence: 6,
    emplacement: { ...SERRE, nom: 'Véranda', type_pepiniere: null }, famille: 'Lamiacées',
    echeances: ECH({ dormance: { est_dormant: true, jours_sans_geste: 70, seuil_jours: 60, dernier_geste: '2026-07-11' } }),
    action_suggeree: { code: 'cloturer', libelle: 'Clôturer' } }),
]

const RESUME = {
  a_repiquer: { lots: 2, plants: 108 },
  a_endurcir: { lots: 1 },
  prets_pour_le_plan: { lots: 1, plants: 6, rangs_libres_par_parcelle: [{ parcelle_id: 5, parcelle: 'Buttes nord', rangs_libres: 2 }] },
  a_semer: { cultures: [{ culture: 'mâche', fenetre: 'août – oct.' }, { culture: 'épinard', fenetre: 'sept. – oct.' }], total: 2 },
}

function simuler(etat) {
  const role = etat === 'lecture_seule' ? 'viewer' : 'owner'
  api.potagers = async () => ({ potagers: [{ id: 1, nom: 'Potager de démonstration', actif: true, role }] })
  api.moi = async () => ({ id: 1, nom: 'Démonstration', email: 'demo@potager.test' })
  api.lireFileGestes = async () => ({ gestes: [], recents: [] })
  api.preparerGeste = async (corps) => {
    console.info('[US-215] geste déposé', corps)
    return { phrase: `${corps.action} (démo)`, compagnon_actif: true, lien: null, en_attente: 2 }
  }
  const une = [{ id: 2, nom: 'Serre', superficie_m2: 2.5, type_pepiniere: 'chaude' }]
  const deux = [...une, { id: 3, nom: 'Châssis froid', superficie_m2: 1.2, type_pepiniere: 'froide' }]
  api.pepiniereLots = async () => {
    if (etat === 'echec') throw new Error('Le serveur ne répond pas.')
    if (etat === 'vide') {
      return { lots: [], total: 0, resume: { a_semer: RESUME.a_semer }, pepinieres: une }
    }
    return { lots: LOTS, total: LOTS.length, resume: RESUME, pepinieres: etat === 'une_pepiniere' ? une : deux }
  }
  api.pepiniereLot = async (numero) => {
    const l = LOTS.find((x) => x.numero_lot === Number(numero))
    if (!l) { const e = new Error('404'); e.statut = 404; throw e }
    return l
  }
  api.godetsDetail = async () => ({ semis: [], godets: [], plantations: [], deplacements: [], ventes: [], pertes_godet: [] })
}

const ETATS = ['nominal', 'une_pepiniere', 'vide', 'lecture_seule', 'echec']

export default function PepiniereAujourdhuiPreview() {
  const etat = new URLSearchParams(window.location.search).get('etat') ?? 'nominal'
  simuler(etat)
  const { theme, toggle } = useTheme()
  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <AppContextProvider>
          <NavigationProvider vue="pepiniere" onVue={() => {}}>
            <FileGestesProvider>
              <NotificationsProvider>
                <div className="flex flex-col h-dvh bg-bg">
                  <div className="shrink-0 bg-brand text-white flex flex-wrap items-center gap-2 px-4 py-2 font-serif font-bold">
                    US-215 — Aujourd’hui
                    {ETATS.map((e) => (
                      <a key={e} href={`?etat=${e}`} className={`font-sans text-[12px] px-2 py-1 rounded ${e === etat ? 'bg-white text-brand' : 'text-white/90'}`}>{e}</a>
                    ))}
                    <Btn small kind="soft" onClick={toggle}>Thème {theme === 'dark' ? 'clair' : 'sombre'}</Btn>
                  </div>
                  <main className="flex-1 overflow-y-auto min-h-0">
                    <div className="max-w-[1320px] mx-auto px-4 nav:px-6 pt-4 pb-7">
                      <Pepiniere refresh={0} />
                    </div>
                  </main>
                </div>
              </NotificationsProvider>
            </FileGestesProvider>
          </NavigationProvider>
        </AppContextProvider>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
