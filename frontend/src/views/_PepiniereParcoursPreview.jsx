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
 * Page de contrôle visuel de l'onglet « Ma pépinière » [US-218 / CA27], hors
 * navigation applicative. Monte le VRAI écran Pépinière avec un bloc `parcours` dans
 * la forme exacte de `GET /pepiniere/lots` (US-240). `hf` rejoue les données de la
 * maquette haute fidélité (Jardin de Bretagne, 19 oct. 2026). Un geste déposé
 * n'écrit rien : la notification de dépôt s'affiche comme dans l'application.
 *
 * `?etat=…` (voir ETATS) · bouton de thème en haut.
 */

const REF = '2026-10-19'
const SERRE = { id: 2, nom: 'SERRE', superficie_m2: 10, type_pepiniere: 'chaude' }
const EXT = { id: 4, nom: 'serre extérieure', superficie_m2: null, type_pepiniere: null }
const CHASSIS = { id: 3, nom: 'Châssis froid', superficie_m2: 1.2, type_pepiniere: 'froide' }

const ech = (o = {}) => ({
  jours: null, en_retard: false, du: null, au: null, debut_regle: null, raison: null, libelle: null, endurcissement: null, ...o,
})
const q = (o = {}) => ({ graines: null, leves: null, godets: null, unite: 'graines', ...o })
const identite = (numero, culture, variete, semis) => ({ id: `semis-${numero}`, numero, culture, variete, date_semis: semis })

/** Une étiquette ; `rang/total` pour un lot coupé. */
const etq = (numero, culture, variete, semis, stade, emplacement_id, etat, o = {}, rang = 1, total = 1) => ({
  id: `semis-${numero}:${stade}:${emplacement_id}`, lot: identite(numero, culture, variete, semis),
  fragment: { rang, total }, stade, emplacement_id, etat, quantites: q(o.quantites),
  echeance: ech(o.echeance), mention: o.mention ?? null, soldable_par_levee_terminee: Boolean(o.soldable),
})

const ETQ_HF = [
  etq(8, 'poireau', null, '2026-08-15', 'levee', 2, 'levee_en_cours', { quantites: { graines: 20 }, mention: '80 déjà repiqués', soldable: true }),
  etq(3, 'carotte', null, '2026-09-16', 'levee', 2, 'duree_inconnue', { quantites: { leves: 1 }, echeance: { raison: 'délai semis → godet non renseigné pour la carotte' } }),
  etq(9, 'laitue', "d'hiver", '2026-10-13', 'levee', 2, 'duree_inconnue', { echeance: { raison: 'délai semis → godet non renseigné pour la laitue' } }),
  etq(7, 'chou', 'frisé', '2026-09-01', 'pret', 2, 'a_sortir', { quantites: { godets: 90, unite: 'godets' }, echeance: { jours: 0, du: '2026-10-13', au: '2026-10-27', debut_regle: '2026-09-01' } }),
  etq(4, 'tomate', 'jaune', '2026-09-21', 'levee', 4, 'levee_en_cours', { quantites: { leves: 3 }, mention: '15 déjà en godet', soldable: true }, 1, 2),
  etq(4, 'tomate', 'jaune', '2026-09-21', 'godet', 4, 'sortir_bientot', { quantites: { godets: 15, unite: 'godets' }, mention: 'déplacés le 12 oct.', echeance: { jours: 14, du: '2026-11-02', au: '2026-11-16', debut_regle: '2026-09-21', libelle: 'endurcir dès le 26 oct.' } }, 2, 2),
  etq(5, 'chou', 'frisé', '2026-10-09', 'godet', 4, 'en_cours', { quantites: { godets: 48, unite: 'godets' }, echeance: { jours: 32, du: '2026-11-20', au: '2026-12-04', debut_regle: '2026-10-09', libelle: 'endurcir dès le 13 nov.' } }),
]

const ETQ_PLUS = [
  etq(28, 'chou', 'frisé', '2026-10-01', 'levee', 3, 'repiquer_retard', { quantites: { graines: 24, leves: 18 }, echeance: { jours: 6, en_retard: true, du: '2026-10-11', au: '2026-10-13', debut_regle: '2026-10-01' } }),
  etq(22, 'laitue', 'Merveille d’hiver', '2026-09-05', 'endurcissement', 3, 'endurcit_sur_place', { quantites: { godets: 24, unite: 'godets' }, echeance: { jours: 9, du: '2026-10-28', au: '2026-11-08', debut_regle: '2026-09-05' } }),
  etq(56, 'courgette', 'jaune', '2026-09-10', 'endurcissement', 2, 'endurcir', { quantites: { godets: 20, unite: 'godets' }, echeance: { jours: 3, du: '2026-10-22', au: '2026-10-30', endurcissement: { jour: 3, sur: 7 }, libelle: 'sortir les godets quelques heures' } }),
  etq(31, 'basilic', 'grand vert', '2026-09-20', 'godet', null, 'en_cours', { quantites: { godets: 6, unite: 'godets' }, echeance: { jours: 20, du: '2026-11-08', au: '2026-11-20', debut_regle: '2026-09-20' } }),
]

const DORMANTS = [
  { lot: identite(49, 'navet', 'jaune', '2026-04-10'), emplacement_id: 2, jours_sans_geste: 126, dernier_geste: '2026-06-15', reste: { graines: 20, godets: 10, unite: 'graines' }, a_des_godets: true },
  { lot: identite(18, 'tomate', 'cœur de bœuf', '2026-03-12'), emplacement_id: 4, jours_sans_geste: 201, dernier_geste: '2026-04-01', reste: { graines: 5, godets: null, unite: 'graines' }, a_des_godets: false },
]

/** Le lot de `lots[]` d'une étiquette : ce que la fiche et les gestes lisent. */
function lotDe(e, extra = {}) {
  const godets = e.quantites.godets ?? 0
  const graines = e.quantites.graines ?? (e.stade === 'levee' ? (e.quantites.leves ?? 30) : 0)
  return {
    lot_id: e.lot.id, semis_id: e.lot.numero, numero_lot: e.lot.numero, culture: e.lot.culture, variete: e.lot.variete,
    date_semis: e.lot.date_semis, parcelle: 'Serre', emplacement: { parcelle_id: e.emplacement_id, nom: 'Serre' },
    graines_semees: 50, unite: 'graines', graines_non_soldees: graines, graines_en_germination: graines,
    plants_obtenus: godets, nb_mises_en_godet: godets ? 1 : 0, nb_plantes: 0, nb_vendus: 0, nb_pertes_godet: 0,
    stock_residuel_godet: godets, nb_leves: e.quantites.leves, levee_terminee: e.etat === 'levee_en_cours' && e.lot.numero === 4,
    sans_semis_rattache: false, cloture: false, famille: 'Démo', rang_urgence: 1,
    action_suggeree: e.etat === 'repiquer_retard' ? { code: 'repiquer', libelle: 'Repiquer' }
      : e.stade === 'pret' ? { code: 'mettre_en_terre', libelle: 'Mettre en terre' } : null,
    echeances: { dormance: { est_dormant: false }, repiquage: {}, mise_en_terre: {}, endurcissement: {}, raisons: [] },
    ou_mettre: e.stade === 'pret' ? { suggestions: [
      { parcelle_id: 11, parcelle: 'planche racines', rangs_libres: 1, places_libres: 10, exposition: { parcelle: 'plein soleil' } },
      { parcelle_id: 12, parcelle: 'tubercule', rangs_libres: 2, places_libres: 40, exposition: { parcelle: 'mi-ombre' } },
      { parcelle_id: 13, parcelle: 'planche_salade', rangs_libres: 1, places_libres: 8, exposition: { parcelle: 'mi-ombre' } },
    ] } : null,
    ...extra,
  }
}

function lotsDe(etiquettes, dormants) {
  const vus = new Map()
  for (const e of etiquettes) {
    const l = vus.get(e.lot.id) ?? lotDe(e)
    if (e.stade !== 'levee') l.stock_residuel_godet = e.quantites.godets
    if (e.stade === 'levee') { l.graines_non_soldees = e.quantites.graines ?? e.quantites.leves ?? 30; l.graines_en_germination = l.graines_non_soldees }
    vus.set(e.lot.id, l)
  }
  const termines = [
    { lot_id: 'semis-1', numero_lot: 1, culture: 'tomate', variete: 'cœur de bœuf', stock_residuel_godet: 0, graines_non_soldees: 0, plants_obtenus: 12, cloture: false, nb_mises_en_godet: 1, echeances: { dormance: {} } },
    { lot_id: 'semis-6', numero_lot: 6, culture: 'tomate', variete: 'jaune', stock_residuel_godet: 0, graines_non_soldees: 0, plants_obtenus: 4, cloture: true, nb_mises_en_godet: 1, echeances: { dormance: {} } },
  ]
  const dorm = dormants.map((d) => lotDe(
    { lot: d.lot, emplacement_id: d.emplacement_id, stade: 'levee', etat: 'en_cours', quantites: { godets: d.reste.godets, graines: d.reste.graines } },
    { stock_residuel_godet: d.reste.godets ?? 0, graines_non_soldees: d.reste.graines ?? 0, echeances: { dormance: { est_dormant: true, jours_sans_geste: d.jours_sans_geste }, repiquage: {}, mise_en_terre: {}, endurcissement: {}, raisons: [] }, action_suggeree: { code: 'cloturer', libelle: 'Clôturer' } },
  ))
  return [...vus.values(), ...dorm, ...termines]
}

const ligne = (p, etiquettes) => {
  const siennes = etiquettes.filter((e) => e.emplacement_id === p.id)
  const prochaine = siennes.filter((e) => e.quantites.godets && e.stade !== 'pret' && e.echeance.du).sort((a, b) => a.echeance.du.localeCompare(b.echeance.du))[0]
  return {
    ...p, nb_lots: new Set(siennes.map((e) => e.lot.id)).size, nb_etiquettes: siennes.length,
    nb_alertes: siennes.filter((e) => e.echeance.en_retard).length,
    prochaine_sortie: prochaine ? { lot_numero: prochaine.lot.numero, culture: prochaine.lot.culture, du: prochaine.echeance.du } : null,
  }
}

const CALENDRIER = {
  zone: 'océanique',
  prochaine_ouverture: { date: '2027-02-01', jours: 105 },
  mois: [
    { mois: '2026-10', libelle: 'oct.', dans_jours: 0, s_ouvrent: [], encore_ouvertes: 0 },
    { mois: '2026-11', libelle: 'nov.', dans_jours: 13, s_ouvrent: [], encore_ouvertes: 0 },
    { mois: '2026-12', libelle: 'déc.', dans_jours: 43, s_ouvrent: [], encore_ouvertes: 0 },
    { mois: '2027-01', libelle: 'janv.', dans_jours: 74, s_ouvrent: [], encore_ouvertes: 0 },
    { mois: '2027-02', libelle: 'févr.', dans_jours: 105, s_ouvrent: ['aubergine', 'basilic', 'brocoli', 'capucine', 'chou', 'chou frisé', 'fenouil', 'persil', 'poireau', 'poivron', 'thym', 'tomate'], encore_ouvertes: 0 },
    { mois: '2027-03', libelle: 'mars', dans_jours: 133, s_ouvrent: ['concombre', 'melon', 'pastèque'], encore_ouvertes: 12 },
  ],
}

const A_SEMER = [
  { culture: 'laitue d’hiver', fenetre: 'sept. – oct.', periode: '1er sept.–31 oct.', jours_restants: 12, part_ecoulee: 0.8, varietes_en_stock: ['Merveille d’hiver'] },
  { culture: 'épinard', fenetre: 'août – oct.', periode: '1er août–31 oct.', jours_restants: 12, part_ecoulee: 0.87, varietes_en_stock: ['Géant d’hiver', 'Monstrueux de Viroflay'] },
]

function parcoursDe({ pepinieres, etiquettes, dormants = [], aSemer = [], sansGraines = [], calendrier = null }) {
  const compte = (etats) => {
    const sel = etiquettes.filter((e) => etats.includes(e.etat))
    return { total: sel.length, retard: sel.some((e) => e.echeance.en_retard) }
  }
  const sans = ligne({ id: null }, etiquettes)
  return {
    stades: ['levee', 'godet', 'endurcissement', 'pret'],
    pepinieres: pepinieres.map((p) => ligne(p, etiquettes)),
    sans_emplacement: sans.nb_etiquettes ? sans : null,
    etiquettes,
    compteurs: {
      a_repiquer: compte(['repiquer_retard', 'a_repiquer']),
      a_sortir: compte(['sortir_retard', 'a_sortir', 'sortir_bientot']),
      endurcit: compte(['endurcir', 'endurcit_sur_place']),
      a_semer: { total: aSemer.length, retard: false },
      dormants: { total: dormants.length, retard: false },
    },
    a_semer: aSemer, a_semer_sans_graines: sansGraines.map((culture) => ({ culture })),
    source_stock_graines: 'cultures_en_cours', dormants,
    calendrier_semis: aSemer.length || sansGraines.length ? null : calendrier,
  }
}

function scenario(etat) {
  switch (etat) {
    case 'hf': return { pepinieres: [SERRE, EXT], etiquettes: ETQ_HF, calendrier: CALENDRIER }
    case 'une_pepiniere': return { pepinieres: [SERRE], etiquettes: ETQ_HF.filter((e) => e.emplacement_id === 2), aSemer: A_SEMER.slice(0, 1), sansGraines: ['mâche'] }
    case 'pepiniere_vide': return { pepinieres: [SERRE, CHASSIS, EXT], etiquettes: ETQ_HF.filter((e) => e.emplacement_id === 2), calendrier: CALENDRIER }
    case 'aucun_lot': return { pepinieres: [SERRE, CHASSIS], etiquettes: [], aSemer: A_SEMER, sansGraines: ['mâche', 'oignon blanc'] }
    case 'sans_semer': return { pepinieres: [SERRE, EXT], etiquettes: ETQ_HF, dormants: [], calendrier: CALENDRIER }
    default: return {
      pepinieres: [SERRE, CHASSIS, EXT], etiquettes: [...ETQ_HF, ...ETQ_PLUS], dormants: DORMANTS,
      aSemer: A_SEMER, sansGraines: ['mâche', 'oignon blanc'],
    }
  }
}

function simuler(etat) {
  const role = etat === 'lecture_seule' ? 'viewer' : 'owner'
  api.potagers = async () => ({ potagers: [{ id: 1, nom: 'Jardin de Bretagne', actif: true, role }] })
  api.moi = async () => ({ id: 1, nom: 'Démonstration', email: 'demo@potager.test' })
  api.lireFileGestes = async () => ({ gestes: [], recents: [] })
  api.meteo = async () => ({ ville: 'Saint-Malo', label: 'Bruine légère', previsions: [{ temp_min: 7, temp_max: 15 }] })
  api.preparerGeste = async (corps) => {
    console.info('[US-218] geste déposé', corps)
    return { phrase: `${corps.action} (démo)`, compagnon_actif: true, lien: null, en_attente: 2 }
  }
  const s = scenario(etat)
  const parcours = parcoursDe(s)
  const lots = lotsDe(s.etiquettes, s.dormants ?? [])
  api.pepiniereLots = async () => {
    if (etat === 'echec') throw new Error('Le serveur ne répond pas.')
    if (etat === 'chargement') return new Promise(() => {})
    return { lots, total: lots.length, date_ref_effective: REF, resume: {}, pepinieres: s.pepinieres, parcours }
  }
  api.pepiniereLot = async (numero) => {
    const l = lots.find((x) => x.numero_lot === Number(numero))
    if (!l) { const e = new Error('404'); e.statut = 404; throw e }
    return l
  }
  api.godetsDetail = async () => ({ semis: [], godets: [], plantations: [], deplacements: [], ventes: [], pertes_godet: [] })
}

const ETATS = ['nominal', 'hf', 'une_pepiniere', 'pepiniere_vide', 'aucun_lot', 'sans_semer', 'lecture_seule', 'chargement', 'echec']

export default function PepiniereParcoursPreview() {
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
                    US-218 — Ma pépinière
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
