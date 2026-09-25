import { useState } from 'react'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import { api } from '../lib/api.js'
import FicheCulture from '../components/FicheCulture.jsx'
import { Btn } from '../components/ui'

/**
 * Page de contrôle visuel de la fiche culture [US-207], hors navigation
 * applicative. Rejoue les états de la maquette gelée du 25/09/2026 avec des
 * réponses d'API simulées, dans la forme exacte de `GET /cultures/{culture}/fiche`,
 * `GET /plan/calendriers` et `GET /plan/confiances/candidates`.
 * `?etat=courgette|tomate_fermee|depuis_rang|sans_calendrier|hors_referentiel|echec`.
 */

const R = (regle, etat) => ({ regle, etat })
const calendrier = (cultures) => ({ zone_climatique: 'oceanique', attributions: ['Wind River Greens (CC BY 4.0)'], cultures, projections: [] })
const mois = (m) => ({ semis_pepiniere: [], semis_pleine_terre: [], plantation: [], recolte: [], ...m })

const ATTRIBUT = (cle, libelle, affichage) => ({ cle, libelle, affichage, valeur: affichage, source_code: 'wrg', attribution: 'Wind River Greens · CC BY 4.0' })
const DUREE = (etape, libelle, affichage) => ({ etape, libelle, jours_min: null, jours_max: null, mention: null, affichage, attribution: 'Wind River Greens · CC BY 4.0' })

const FICHE_COURGETTE = {
  culture: 'courgette', nom_culture: 'Courgette', fiche_absente: false,
  famille: 'Cucurbitacées', famille_attribution: 'Wind River Greens · CC BY 4.0', delai_retour_annees: 3,
  type_organe_recolte: 'reproducteur', itineraires_connus: ['standard'],
  attributs: [
    ATTRIBUT('exposition', 'Exposition', 'plein soleil'),
    ATTRIBUT('besoin_eau', 'Besoin en eau', 'élevé'),
    ATTRIBUT('rusticite_min', 'Rusticité minimale', 'non renseignée'),
    ATTRIBUT('profondeur_semis', 'Profondeur de semis', '2 – 3 cm'),
  ],
  durees: [
    DUREE('levee', 'Levée', '6 – 10 jours'),
    DUREE('recolte', 'Semis → 1ʳᵉ récolte', '55 – 65 jours'),
    DUREE('repiquage', 'Délai avant plantation', 'non renseignée'),
    DUREE('plantation_recolte', 'Plantation → 1ʳᵉ récolte', '45 – 55 jours'),
  ],
  varietes_cultivees: [
    { variete: 'ronde-de-nice', nom_variete: 'Ronde de Nice', parcelles: [
      { parcelle_id: 2, nom_parcelle: 'Parcelle 2', phase: 'en_recolte', phase_depuis: '2026-07-10', phase_depuis_nature: 'recolte' },
      { parcelle_id: 4, nom_parcelle: 'Parcelle 4', phase: 'en_recolte', phase_depuis: '2026-07-18', phase_depuis_nature: 'recolte' },
    ], lots_pepiniere: [] },
  ],
  associations: [
    { autre_partie: 'maïs', autre_est_famille: false, nature: 'favorable', niveau_preuve: 'etabli', motif: 'ombrage léger', formulation: null, source_code: 'wrg', attribution: 'Wind River Greens · CC BY 4.0' },
    { autre_partie: 'pomme de terre', autre_est_famille: false, nature: 'defavorable', niveau_preuve: 'etabli', motif: 'compétition racinaire', formulation: null, source_code: 'wrg', attribution: 'Wind River Greens · CC BY 4.0' },
    { autre_partie: 'œillet d’Inde', autre_est_famille: false, nature: 'favorable', niveau_preuve: 'traditionnel', motif: 'répulsif à nématodes', formulation: null, source_code: 'wrg', attribution: 'Wind River Greens · CC BY 4.0' },
  ],
  associations_connues: true,
  bioagresseurs: [
    { nom_commun_fr: 'Oïdium', nom_scientifique: 'Erysiphe cichoracearum', categorie: 'champignon', code_eppo: 'ERYSCI', frequence: 9, periode_risque: 'juillet → septembre', local: false, source_code: 'eppo', attribution: 'EPPO' },
    { nom_commun_fr: 'Limace', nom_scientifique: 'Deroceras reticulatum', categorie: 'mollusque', code_eppo: null, frequence: 7, periode_risque: null, local: false, source_code: 'wrg', attribution: 'Wind River Greens · CC BY 4.0' },
  ],
  bioagresseurs_total: 2, bioagresseurs_connus: true,
  attributions: ['Wind River Greens · CC BY 4.0', 'EPPO'],
}

const ETATS = {
  courgette: {
    titre: 'Fenêtre ouverte, en récolte', culture: 'courgette', dateRef: '2026-09-18', parcelleId: null,
    fiche: FICHE_COURGETTE,
    calendriers: calendrier({ courgette: { culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
      mois: mois({ semis_pleine_terre: [4, 5, 6], recolte: [7, 8, 9, 10] }), duree_recolte: '55 – 65 j' } }),
    actions: [{ action: 'semis_pleine_terre', etoiles: 2, score: 70, motifs: [R('R1', 'gagne')], recolte_attendue: { min: '2026-11-05', max: '2026-11-15' } }],
  },
  tomate_fermee: {
    titre: 'Fenêtre fermée, séries en terre', culture: 'tomate', dateRef: '2026-09-18', parcelleId: null,
    fiche: { ...FICHE_COURGETTE, culture: 'tomate', nom_culture: 'Tomate', famille: 'Solanacées', delai_retour_annees: 4 },
    calendriers: calendrier({ tomate: { culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
      mois: mois({ semis_pepiniere: [2, 3], plantation: [4, 5], recolte: [7, 8, 9] }), duree_recolte: '—' } }),
    actions: [{ action: 'semis_pepiniere', etoiles: 1, score: 20, motifs: [R('R1', 'perdu')] }],
  },
  depuis_rang: {
    titre: 'Depuis un rang du Plan', culture: 'courgette', dateRef: '2026-09-18', parcelleId: 2,
    nomParcelle: 'planche-centrale', rang: 3,
    fiche: FICHE_COURGETTE,
    calendriers: calendrier({ courgette: { culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
      mois: mois({ semis_pleine_terre: [4, 5, 6], recolte: [7, 8, 9, 10] }), duree_recolte: '55 – 65 j' } }),
    actions: [{ action: 'semis_pleine_terre', etoiles: 2, score: 70, motifs: [R('R1', 'gagne')], recolte_attendue: { min: '2026-11-05', max: '2026-11-15' } }],
  },
  sans_calendrier: {
    titre: 'Sans calendrier pour la zone', culture: 'ail', dateRef: '2026-09-18', parcelleId: null,
    fiche: { ...FICHE_COURGETTE, culture: 'ail', nom_culture: 'Ail', varietes_cultivees: [], associations: [], associations_connues: false, bioagresseurs: [], bioagresseurs_total: 0, bioagresseurs_connus: false, durees: FICHE_COURGETTE.durees.map((d) => ({ ...d, affichage: 'non renseignée' })) },
    calendriers: calendrier({ ail: { culture_connue: true, renseigne: false, itineraire: null, itineraire_standard: true, mois: mois({}), duree_recolte: '—' } }),
    actions: [],
  },
  hors_referentiel: {
    titre: 'Hors référentiel', culture: 'verveine', dateRef: '2026-09-18', parcelleId: null,
    fiche: { culture: 'verveine', nom_culture: 'Verveine', fiche_absente: true, famille: null, famille_attribution: null,
      delai_retour_annees: null, type_organe_recolte: null, itineraires_connus: [], attributs: [], durees: [],
      varietes_cultivees: [{ variete: 'citronnee', nom_variete: 'Citronnée', parcelles: [
        { parcelle_id: 5, nom_parcelle: 'Parcelle 5', phase: 'en_place', phase_depuis: '2026-05-02', phase_depuis_nature: 'plantation' },
      ], lots_pepiniere: [] }],
      associations: [], associations_connues: false, bioagresseurs: [], bioagresseurs_total: 0, bioagresseurs_connus: false, attributions: [] },
    calendriers: calendrier({}),
    actions: [],
  },
  echec: {
    titre: 'Lecture échouée', culture: 'epinard', dateRef: '2026-09-18', parcelleId: null,
    fiche: null, echecFiche: true,
    calendriers: calendrier({ epinard: { culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
      mois: mois({ semis_pleine_terre: [8, 9, 10] }), duree_recolte: '45 j' } }),
    actions: [{ action: 'semis_pleine_terre', etoiles: 3, score: 90, motifs: [R('R1', 'gagne')], recolte_attendue: { min: '2026-11-01', max: '2026-11-10' } }],
  },
}

const confiancesDe = (e) => ({
  date: e.dateRef,
  cultures: { [e.culture]: { culture: e.culture, culture_connue: true, a_calendrier: e.actions.length > 0, candidates: e.actions, actions: e.actions } },
})

function simulerApi(e) {
  api.potagers = async () => ({ potagers: [{ id: 1, nom: 'Potager de démonstration', actif: true, role: 'owner' }] })
  api.moi = async () => ({ id: 1, nom: 'Démonstration', email: 'demo@potager.test' })
  api.ficheCulture = async () => {
    if (e.echecFiche) throw new Error('Erreur API 500 sur /cultures/.../fiche')
    return e.fiche
  }
  api.calendriersPlan = async () => e.calendriers
  api.confiancesPlan = async () => confiancesDe(e)
}

export default function FicheCulturePreview() {
  const initial = new URLSearchParams(window.location.search).get('etat')
  const [cle, setCle] = useState(ETATS[initial] ? initial : 'courgette')
  const [ouverte, setOuverte] = useState(true)
  const e = ETATS[cle]
  simulerApi(e)

  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <div className="min-h-dvh bg-bg p-4 flex flex-col gap-3">
          <h1 className="font-serif text-2xl font-bold text-txt">Fiche culture — US-207</h1>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ETATS).map(([k, v]) => (
              <Btn key={k} small kind={k === cle ? 'primary' : 'ghost'} onClick={() => { setCle(k); setOuverte(true) }}>{v.titre}</Btn>
            ))}
            <Btn small kind="soft" onClick={() => setOuverte(true)} disabled={ouverte}>Rouvrir</Btn>
          </div>
          {ouverte && (
            // `key` : changer d'état remonte la fiche, qui relit alors ses données simulées.
            <FicheCulture
              key={cle} culture={e.culture} dateRef={e.dateRef} potagerId={1}
              parcelleId={e.parcelleId ?? null} nomParcelle={e.nomParcelle ?? null} rang={e.rang ?? null}
              onClose={() => setOuverte(false)}
            />
          )}
        </div>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
