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
 * Page de contrôle visuel de l'onglet « Lots » en journal de saison [US-242], hors
 * navigation applicative. Monte le VRAI écran Pépinière, ouvert sur « Lots », avec les
 * neuf lots de la maquette HF (Jardin de Bretagne, 19 oct. 2026) dans la forme exacte
 * de `GET /pepiniere/lots`. `?etat=vide` : aucun lot.
 */

const REF = '2026-10-19'
const SERRE = { id: 2, nom: 'SERRE', type_pepiniere: 'chaude' }
const EXT = { id: 4, nom: 'serre extérieure', type_pepiniere: null }

const ech = (o = {}) => ({
  date_reference: REF, raisons: [], repiquage: {}, mise_en_terre: {}, endurcissement: {},
  dormance: { est_dormant: false }, ...o,
})
const lot = (numero, culture, variete, semis, o = {}) => ({
  lot_id: `semis-${numero}`, semis_id: numero, numero_lot: numero, culture, variete, date_semis: semis,
  famille: 'Solanacées', unite: 'graines', graines_semees: 10, plants_obtenus: 0, nb_mises_en_godet: 0,
  date_derniere_mise_en_godet: null, nb_plantes: 0, nb_vendus: 0, nb_pertes_godet: 0, stock_residuel_godet: 0,
  graines_non_soldees: 10, graines_en_germination: 10, date_dernier_geste: semis, date_deplacement: null,
  cloture: false, date_cloture: null, nb_leves: null, date_derniere_levee: null, levee_terminee: false,
  sans_semis_rattache: false, parcelle: 'SERRE', type_pepiniere: 'chaude', emplacement: { ...SERRE, origine: 'semis' },
  echeances: ech(), action_suggeree: null, ou_mettre: null, ...o,
})
const OU = {
  suggestions: [
    { parcelle_id: 11, parcelle: 'planche racines', places_libres: 10, exposition: { libelle: 'plein soleil, comme la culture le demande' } },
    { parcelle_id: 12, parcelle: 'tubercule', places_libres: 40, exposition: { libelle: 'mi-ombre, pour une culture de plein soleil', comparaison: 'differe' } },
    { parcelle_id: 13, parcelle: 'planche_salade', places_libres: 8, exposition: { libelle: 'ensoleillement non renseigné' } },
  ],
  plants_non_calcules: '58 places libres pour 90 godets',
}

const LOTS = [
  lot(1, 'Tomate', 'cœur de bœuf', '2026-03-15', {
    plants_obtenus: 10, nb_mises_en_godet: 2, date_derniere_mise_en_godet: '2026-10-09', nb_plantes: 10,
    graines_non_soldees: 0, graines_en_germination: 0, date_dernier_geste: '2026-10-09',
    sorties_datees: [{ nature: 'plantation', date: '2026-06-15', quantite: 10, parcelle: 'planche_centrale', id: 31 }],
  }),
  lot(6, 'Tomate', 'jaune', '2026-03-25', {
    graines_semees: 5, cloture: true, date_cloture: '2026-10-15', graines_non_soldees: 0, graines_en_germination: 0,
    date_dernier_geste: '2026-10-15',
  }),
  lot(2, 'Tomate', 'ananas', '2026-05-10', {
    plants_obtenus: 9, nb_mises_en_godet: 1, date_derniere_mise_en_godet: '2026-06-02', nb_plantes: 9,
    graines_non_soldees: 0, graines_en_germination: 0, date_dernier_geste: '2026-06-02', levee_terminee: true,
    sorties_datees: [
      { nature: 'plantation', date: '2026-06-20', quantite: 7, parcelle: 'planche_centrale', id: 32 },
      { nature: 'plantation', date: '2026-06-28', quantite: 2, parcelle: 'planche_est', id: 33 },
    ],
  }),
  lot(8, 'Poireau', null, '2026-08-15', {
    famille: 'Amaryllidacées', graines_semees: 100, plants_obtenus: 80, nb_mises_en_godet: 2,
    date_derniere_mise_en_godet: '2026-10-17', nb_plantes: 80, graines_non_soldees: 20, graines_en_germination: 20,
    date_dernier_geste: '2026-10-17',
    sorties_datees: [
      { nature: 'plantation', date: '2026-10-10', quantite: 50, parcelle: 'planche_poireaux', id: 34 },
      { nature: 'plantation', date: '2026-10-17', quantite: 30, parcelle: 'planche_poireaux', id: 35 },
    ],
  }),
  lot(7, 'Chou', 'frisé', '2026-09-01', {
    famille: 'Brassicacées', graines_semees: 100, plants_obtenus: 100, nb_mises_en_godet: 1,
    date_derniere_mise_en_godet: '2026-09-20', stock_residuel_godet: 90, nb_pertes_godet: 10,
    graines_non_soldees: 0, graines_en_germination: 0, date_dernier_geste: '2026-10-15', ou_mettre: OU,
    echeances: ech({ mise_en_terre: { etat: 'atteinte', du: '2026-10-13', au: '2026-10-27' }, endurcissement: { etat: 'termine' } }),
  }),
  lot(3, 'Carotte', null, '2026-09-16', {
    famille: 'Apiacées', graines_semees: 50, nb_leves: 1, levee_terminee: true, date_derniere_levee: '2026-10-18',
    graines_non_soldees: 50, graines_en_germination: 0, date_dernier_geste: '2026-10-18',
    echeances: ech({ raisons: ['délai semis → godet non renseigné pour la culture « carotte »'] }),
  }),
  lot(4, 'Tomate', 'jaune', '2026-09-21', {
    graines_semees: 20, plants_obtenus: 15, nb_mises_en_godet: 3, date_derniere_mise_en_godet: '2026-10-09',
    stock_residuel_godet: 15, graines_non_soldees: 5, graines_en_germination: 0, date_deplacement: '2026-10-12',
    nb_leves: 18, date_derniere_levee: '2026-10-18', levee_terminee: true, date_dernier_geste: '2026-10-18',
    emplacement: { ...EXT, origine: 'deplacement' }, type_pepiniere: null,
    ou_mettre: { suggestions: OU.suggestions.slice(0, 2) },
    echeances: ech({ mise_en_terre: { etat: 'a_venir', du: '2026-11-02', au: '2026-11-16', dans_jours: 14 } }),
  }),
  lot(5, 'Chou', 'frisé', '2026-10-09', {
    famille: 'Brassicacées', graines_semees: 48, plants_obtenus: 48, nb_mises_en_godet: 3,
    date_derniere_mise_en_godet: '2026-10-14', stock_residuel_godet: 48, graines_non_soldees: 0,
    graines_en_germination: 0, date_dernier_geste: '2026-10-14', emplacement: { ...EXT, origine: 'godet' },
    echeances: ech({ mise_en_terre: { etat: 'a_venir', du: '2026-11-20', au: '2026-12-04', dans_jours: 32 } }),
  }),
  lot(9, 'Laitue', "d'hiver", '2026-10-13', {
    famille: 'Astéracées', graines_semees: 0, graines_non_soldees: 0, graines_en_germination: 0,
    echeances: ech({ raisons: ['délai semis → godet non renseigné pour la culture « laitue »'] }),
  }),
]

function simuler(etat) {
  const lots = etat === 'vide' ? [] : LOTS
  api.potagers = async () => ({ potagers: [{ id: 1, nom: 'Jardin de Bretagne', actif: true, role: 'owner' }] })
  api.moi = async () => ({ id: 1, nom: 'Démonstration', email: 'demo@potager.test' })
  api.lireFileGestes = async () => ({ gestes: [], recents: [] })
  api.meteo = async () => ({ ville: 'Saint-Malo', label: 'Bruine légère', previsions: [{ temp_min: 7, temp_max: 15 }] })
  api.pepiniereLots = async () => ({
    lots, total: lots.length, date_ref_effective: REF, resume: {}, pepinieres: [SERRE, EXT],
    parcours: { pepinieres: [], etiquettes: [], dormants: [], compteurs: {}, a_semer: [], sans_graines: [], calendrier: null },
  })
  api.pepiniereLot = async (numero) => {
    const l = lots.find((x) => x.numero_lot === Number(numero))
    if (!l) { const e = new Error('404'); e.statut = 404; throw e }
    return l
  }
  api.godetsDetail = async () => ({ semis: [], godets: [], plantations: [], deplacements: [], ventes: [], pertes_godet: [] })
}

export default function PepiniereLotsPreview() {
  const etat = new URLSearchParams(window.location.search).get('etat') ?? 'hf'
  simuler(etat)
  const { theme, toggle } = useTheme()
  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <AppContextProvider>
          <NavigationProvider vue="pepiniere" onVue={() => {}} intentionInitiale={{ vue: 'pepiniere', intention: { onglet: 'lots' } }}>
            <FileGestesProvider>
              <NotificationsProvider>
                <div className="flex flex-col h-dvh bg-bg">
                  <div className="shrink-0 bg-brand text-white flex flex-wrap items-center gap-2 px-4 py-2 font-serif font-bold">
                    US-242 — Lots, journal de saison
                    {['hf', 'vide'].map((e) => (
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
