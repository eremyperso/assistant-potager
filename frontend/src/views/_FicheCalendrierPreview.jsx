import { useState } from 'react'
import { api } from '../lib/api.js'
import { AuthContextProvider } from '../context/AuthContext.jsx'
import { PotagerContextProvider } from '../context/PotagerContext.jsx'
import { AppContextProvider } from '../context/AppContext.jsx'
import Plan from './Plan.jsx'
import FicheCalendrier from '../components/FicheCalendrier.jsx'
import FicheConfiance from '../components/FicheConfiance.jsx'
import { Btn } from '../components/ui'

/**
 * Page de contrôle visuel de la fiche calendrier [US-183] et de « Pourquoi ce
 * niveau ? » [US-180], hors navigation applicative.
 *
 * Rejoue les quatre états de la maquette gelée du 18/09/2026 avec des réponses
 * d'API simulées, dans la forme exacte de `GET /plan/calendriers` et
 * `GET /plan/confiances/candidates`. `?etat=courgette|tomate|ail|courgette_nl`.
 *
 * ⚠️ Valeurs de DÉMONSTRATION (cas de référence de l'épic 5 et fenêtres de la
 * tomate océanique) : elles servent au contrôle visuel, elles n'engagent aucune
 * agronomie. Chargée en `lazy()` par `main.jsx`, comme `/shell`.
 *
 * `?vue=plan` monte le VRAI écran Plan sur ces données (tuile, pastille, frise,
 * « Pourquoi ce niveau ? », fiche) : le parcours de bout en bout se vérifie sans
 * session réelle.
 */

const R = (regle, etat, libelle, points, points_max) => ({ regle, regle_libelle: regle, etat, libelle, points, points_max })

const evaluation = (culture, action, score, etoiles, motifs, recolte, avertissements = []) => ({
  culture, action, action_libelle: action, etoiles, score, score_max_atteignable: 100,
  motifs, avertissements, recolte_attendue: recolte,
})

const COURGETTE_SERIE = {
  parcelle_id: 2, parcelle_nom: 'Parcelle 2', culture: 'courgette', variete: '', etat: 'a_venir', motif: null,
  origine: { action: 'semis', date: '2026-04-12', contexte: 'pleine_terre' }, plantation_reelle: null,
  levee_attendue: { debut: '2026-04-22', fin: '2026-04-22' },
  recolte_attendue: { debut: '2026-07-16', fin: '2026-07-26' }, recolte_reelle: null,
  jours_restants: { min: 31, max: 41 }, retard_jours: null, series_suivantes: 0,
  mois: { semis_pepiniere: [], semis_pleine_terre: [4], plantation: [], croissance: [5, 6], recolte: [7] },
}

const REGLES_COURGETTE = [
  R('R1', 'gagne', 'Dans la fenêtre conseillée pour ta zone', 40, 40),
  R('R2', 'indetermine', 'Sensibilité au gel inconnue pour cette culture', 0, 20),
  R('R3', 'gagne', 'Aucun gel annoncé sur 14 jours', 20, 20),
  R('R4', 'perdu', 'Nuits fraîches : levée lente probable', 0, 10),
  R('R5', 'gagne', 'La récolte arriverait avant la fin de saison', 10, 10),
]
const REGLES_NON_LOCALISE = [
  R('R1', 'gagne', 'Dans la fenêtre conseillée pour ta zone', 40, 40),
  R('R2', 'gagne', 'Dernière gelée moyenne passée', 20, 20),
  R('R3', 'indetermine', 'Météo indisponible : localise ton potager pour la prendre en compte', 0, 20),
  R('R4', 'indetermine', 'Météo indisponible', 0, 10),
  R('R5', 'gagne', 'La récolte arriverait avant la fin de saison', 10, 10),
]

const calendrier = (cultures, projections = []) => ({
  zone_climatique: 'oceanique', zone_climatique_origine: 'jardinier',
  attributions: ['Wind River Greens (CC BY 4.0)'], cultures, projections,
})
const mois = (m) => ({ semis_pepiniere: [], semis_pleine_terre: [], plantation: [], recolte: [], ...m })

const ETATS = {
  courgette: {
    titre: 'Tout renseigné, série en terre', culture: 'courgette', dateRef: '2026-06-15', parcelleId: 2,
    calendriers: calendrier({ courgette: { culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
      mois: mois({ semis_pleine_terre: [4, 5, 6], recolte: [7, 8, 9, 10] }), duree_recolte: '95 j' } }, [COURGETTE_SERIE]),
    actions: [evaluation('courgette', 'semis_pleine_terre', 70, 2, REGLES_COURGETTE, { min: '2026-09-18', max: '2026-09-28' })],
  },
  tomate: {
    titre: 'Rien en terre, deux actions', culture: 'tomate', dateRef: '2026-05-05',
    calendriers: calendrier({ tomate: { culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
      mois: mois({ semis_pepiniere: [2, 3], plantation: [4, 5], recolte: [7, 8, 9] }), duree_recolte: '—' } }),
    actions: [
      evaluation('tomate', 'semis_pepiniere', 50, 2, [
        R('R1', 'perdu', 'Hors fenêtre conseillée (février → mars pour ta zone)', 0, 40),
        R('R2', 'gagne', 'Semis en pépinière : gelée sans objet', 20, 20),
        R('R3', 'gagne', 'Aucun gel annoncé sur 14 jours', 20, 20),
        R('R4', 'gagne', 'Nuits douces sur les 7 prochains jours', 10, 10),
        R('R5', 'perdu', 'La récolte arriverait après la fin de la fenêtre de récolte', 0, 10),
      ], { min: null, max: null }),
      evaluation('tomate', 'plantation', 100, 3, [
        R('R1', 'gagne', 'Dans la fenêtre conseillée pour ta zone', 40, 40),
        R('R2', 'gagne', 'Dernière gelée moyenne passée', 20, 20),
        R('R3', 'gagne', 'Aucun gel annoncé sur 14 jours', 20, 20),
        R('R4', 'gagne', 'Nuits douces sur les 7 prochains jours', 10, 10),
        R('R5', 'gagne', 'La récolte arriverait avant la fin de saison', 10, 10),
      ], { min: '2026-07-04', max: '2026-07-24' }),
    ],
  },
  ail: {
    titre: 'Dégradé, sans calendrier', culture: 'ail', dateRef: '2026-06-15',
    calendriers: calendrier({ ail: { culture_connue: true, renseigne: false, itineraire: null, itineraire_standard: true,
      mois: mois({}), duree_recolte: '—' } }, [
      { parcelle_id: 1, parcelle_nom: 'Parcelle 1', culture: 'ail', variete: '', etat: 'sans_recalage', motif: 'referentiel_absent',
        origine: { action: 'plantation', date: '2025-10-20', contexte: null }, series_suivantes: 0, mois: null },
      { parcelle_id: 3, parcelle_nom: 'Parcelle 3', culture: 'ail', variete: '', etat: 'sans_recalage', motif: 'referentiel_absent',
        origine: { action: 'plantation', date: '2025-11-05', contexte: null }, series_suivantes: 0, mois: null },
    ]),
    actions: [],
  },
  courgette_nl: {
    titre: 'Potager non localisé', culture: 'courgette', dateRef: '2026-06-15', parcelleId: 2,
    calendriers: calendrier({ courgette: { culture_connue: true, renseigne: true, itineraire: 'standard', itineraire_standard: true,
      mois: mois({ semis_pleine_terre: [4, 5, 6], recolte: [7, 8, 9, 10] }), duree_recolte: '95 j' } }, [COURGETTE_SERIE]),
    actions: [evaluation('courgette', 'semis_pleine_terre', 70, 2, REGLES_NON_LOCALISE, { min: '2026-09-18', max: '2026-09-28' },
      ["Sans météo, la troisième étoile est hors d'atteinte : 70 points possibles sur 100"])],
  },
}

const confiancesDe = (e) => ({
  date: e.dateRef,
  cultures: { [e.culture]: { culture: e.culture, culture_connue: true, a_calendrier: e.actions.length > 0,
    candidates: e.actions.filter((a) => a.motifs[0].etat === 'gagne'), actions: e.actions } },
})

/** Données simulées — au rendu de cette page seulement, jamais à l'import (cf. `_ShellPreview`). */
function simulerApi(e) {
  api.potagers = async () => ({ potagers: [{ id: 1, nom: 'Potager de démonstration', actif: true, role: 'owner' }] })
  api.moi = async () => ({ id: 1, nom: 'Démonstration', email: 'demo@potager.test' })
  api.calendriersPlan = async () => e.calendriers
  api.confiancesPlan = async () => confiancesDe(e)
  api.plan = async () => ({
    date_ref_effective: e.dateRef,
    parcelles: [{
      id: e.parcelleId ?? 2, nom: 'Parcelle 2', superficie_m2: 12, exposition: 'sud', occupation_pct: 80,
      has_observations: false, nb_observations: 0,
      cultures: [{ culture: e.culture, variete: '', nb_plants: 6, unite: 'plants', type_organe: 'reproducteur',
        famille: 'Solanacée', has_observations: false, nb_observations: 0 }],
    }],
  })
}

export default function FicheCalendrierPreview() {
  const initial = new URLSearchParams(window.location.search).get('etat')
  const [cle, setCle] = useState(ETATS[initial] ? initial : 'courgette')
  const [ouverte, setOuverte] = useState('fiche')
  const e = ETATS[cle]
  simulerApi(e)

  if (new URLSearchParams(window.location.search).get('vue') === 'plan') {
    return (
      <AuthContextProvider>
        <PotagerContextProvider>
          <AppContextProvider>
            <div className="min-h-dvh bg-bg p-4"><Plan refresh={0} /></div>
          </AppContextProvider>
        </PotagerContextProvider>
      </AuthContextProvider>
    )
  }

  return (
    <AuthContextProvider>
      <PotagerContextProvider>
        <div className="min-h-dvh bg-bg p-4 flex flex-col gap-3">
          <h1 className="font-serif text-2xl font-bold text-txt">Fiche calendrier — US-183</h1>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ETATS).map(([k, v]) => (
              <Btn key={k} small kind={k === cle ? 'primary' : 'ghost'} onClick={() => { setCle(k); setOuverte('fiche') }}>{v.titre}</Btn>
            ))}
            <Btn small kind="soft" onClick={() => setOuverte('pourquoi')} disabled={e.actions.length === 0}>Pourquoi ce niveau ?</Btn>
          </div>
          {ouverte === 'fiche' && (
            // `key` : changer d'état remonte la fiche, qui relit alors ses données simulées.
            <FicheCalendrier key={cle} culture={e.culture} dateRef={e.dateRef} potagerId={1}
              parcelleId={e.parcelleId ?? null} onClose={() => setOuverte(null)} />
          )}
          {ouverte === 'pourquoi' && e.actions.length > 0 && (
            <FicheConfiance culture={e.culture} confiance={e.actions[e.actions.length - 1]}
              dateRef={e.dateRef} onClose={() => setOuverte(null)} />
          )}
        </div>
      </PotagerContextProvider>
    </AuthContextProvider>
  )
}
