// [US-355 / CA4-CA6, CA8] Écran Cultures sur le socle commun : deux onglets d'en-tête, « Au potager · n » (ce qui demande
// une action d'abord) et « Catalogue · n » (les espèces à semer, rangées par prochaine fenêtre).
//
// Il ne calcule aucune règle (CA9) : l'étape, « à confirmer », « à libérer », la fenêtre de semis et les comptes viennent
// de `GET /plan` et de `GET /cultures/vue` ; `lib/culturesSocle.js` range, nomme et met en phrases. Toucher une carte
// ouvre la fiche commune ou la fiche catalogue, dans le panneau partagé (`hooks/useFiches.jsx`).
import { useEffect, useMemo, useState } from 'react'
import { Sprout, BookOpen, ChevronDown, HelpCircle, Mic } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { useIntention, useEtatEcran } from '../context/NavigationContext.jsx'
import { useDeclarerEcran } from '../context/CoquilleContext.jsx'
import { useFiches } from '../hooks/useFiches.jsx'
import { ouvrirGastonSur } from '../lib/contexteCompagnon.js'
import { sujetAjout } from '../lib/ouvertureGaston.js'  // [US-358]
import { peutEnregistrer } from '../lib/gestes.js'
import { GESTES_MOIS, classeGeste } from '../lib/calendrierAnnee.js'
import {
  ONGLET_POTAGER, ONGLET_CATALOGUE, ongletsCultures, CONTEXTE_ONGLET, lignesAuPotager, lignesAPlacer,
  repondALaRecherche, famillesDesLignes, groupesAuPotager, motDeCultures, lignesCatalogue, repondAuCatalogue,
  groupesDuCatalogue, motDuCatalogue,
} from '../lib/culturesSocle.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import FeuilleFiltres, { GroupeChoix } from '../components/FeuilleFiltres.jsx'
import { EnTeteSection } from '../components/SectionSocle.jsx'
import { CarteAuPotager, CarteCatalogue } from '../components/CarteCultureSocle.jsx'

const ICONES_ONGLETS = { [ONGLET_POTAGER]: Sprout, [ONGLET_CATALOGUE]: BookOpen }
const TOUTES = 'Toutes'

/** Une colonne, puis deux à partir de 700 px de conteneur (CA4). */
function Grille({ children }) {
  return (
    <div className="@container/cultures">
      <div className="grid grid-cols-1 gap-3 @[700px]/cultures:grid-cols-2">{children}</div>
    </div>
  )
}

/** [CA4] La légende du calendrier : repliable, « Survolez un mois » ou « Appui long sur un mois » : son geste. */
function LegendeCalendrier() {
  const [ouverte, setOuverte] = useState(false)
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <button
          type="button" aria-expanded={ouverte} onClick={() => setOuverte((o) => !o)}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded-[10px] border border-border bg-card px-2.5 text-[12.5px] font-semibold text-txt2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
        >
          <HelpCircle size={15} aria-hidden="true" />Légende du calendrier
          <ChevronDown size={14} aria-hidden="true" className={ouverte ? 'rotate-180' : ''} />
        </button>
        <span className="text-[11.5px] text-txt3">
          <span className="[@media(hover:hover)]:hidden">Appui long sur un mois</span>
          <span className="hidden [@media(hover:hover)]:inline">Survolez un mois</span> : son geste
        </span>
      </div>
      {ouverte && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Légende du calendrier">
          {GESTES_MOIS.map((g) => (
            <li key={g.cle}><span className={`puce-etape petite ${classeGeste(g.cle)}`}>{g.libelle}</span></li>
          ))}
          <li>
            <span className="puce-etape petite bg-card text-txt" style={{ boxShadow: 'inset 0 0 0 1.5px var(--txt)' }}>cadre = ce mois-ci</span>
          </li>
        </ul>
      )}
    </div>
  )
}

export default function Cultures({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId, potagerActif } = usePotager()
  const { ouvrirCulture, ouvrirCatalogue } = useFiches()

  const [vue, setVue] = useState(null)
  const [plan, setPlan] = useState(null)
  const [planEchoue, setPlanEchoue] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filtresOuverts, setFiltresOuverts] = useState(false)

  // [CA1] Les liens des autres vues (« Voir la culture ») ouvrent la fiche commune de cette culture.
  const intention = useIntention('cultures', (recue) => { if (recue.culture) ouvrirCulture({ culture: recue.culture }) })
  const [etat, setEtat] = useEtatEcran('cultures', { onglet: ONGLET_POTAGER, q: '', famille: TOUTES }, intention)
  const onglet = etat.onglet === ONGLET_CATALOGUE ? ONGLET_CATALOGUE : ONGLET_POTAGER

  async function charger() {
    setLoading(true)
    setError(null)
    const [v, p] = await Promise.allSettled([api.vueCultures(dateRef, potagerId, { confiance: false }), api.plan(dateRef, potagerId)])
    if (v.status === 'rejected') setError(v.reason?.message || 'Lecture impossible')
    setVue(v.status === 'fulfilled' ? v.value : null)
    setPlan(p.status === 'fulfilled' ? p.value : null)
    setPlanEchoue(p.status === 'rejected')
    setLoading(false)
  }
  useEffect(() => { charger() }, [refresh, dateRef, potagerId])   // eslint-disable-line react-hooks/exhaustive-deps

  const jourLu = plan?.date_ref_effective || dateRef || new Date().toISOString().slice(0, 10)
  const moisCourant = Number(String(jourLu).slice(5, 7)) || new Date().getMonth() + 1
  const moisZero = moisCourant - 1

  const lignesPotager = useMemo(() => lignesAuPotager(plan, vue, jourLu), [plan, vue, jourLu])
  const aPlacer = useMemo(() => lignesAPlacer(plan, vue), [plan, vue])
  const toutesPotager = useMemo(() => [...lignesPotager, ...aPlacer], [lignesPotager, aPlacer])
  const catalogue = useMemo(() => lignesCatalogue(vue, lignesPotager), [vue, lignesPotager])

  const familles = useMemo(
    () => famillesDesLignes(onglet === ONGLET_POTAGER ? toutesPotager : catalogue),
    [onglet, toutesPotager, catalogue],
  )
  const famille = familles.includes(etat.famille) ? etat.famille : TOUTES
  const nombreFiltres = famille !== TOUTES ? 1 : 0

  const potagerFiltre = useMemo(
    () => toutesPotager.filter((l) => repondALaRecherche(l, etat.q) && (famille === TOUTES || l.famille === famille)),
    [toutesPotager, etat.q, famille],
  )
  const catalogueFiltre = useMemo(
    () => catalogue.filter((k) => repondAuCatalogue(k, etat.q) && (famille === TOUTES || k.famille === famille)),
    [catalogue, etat.q, famille],
  )
  const groupesPotager = useMemo(() => groupesAuPotager(potagerFiltre), [potagerFiltre])
  const groupesCatalogue = useMemo(() => groupesDuCatalogue(catalogueFiltre, moisCourant), [catalogueFiltre, moisCourant])

  // Les Mots de Gaston : calculés sur TOUTE la lecture, pas sur ce que la recherche laisse voir.
  const mot = useMemo(
    () => (onglet === ONGLET_POTAGER ? motDeCultures(lignesPotager) : motDuCatalogue(catalogue, moisCourant)),
    [onglet, lignesPotager, catalogue, moisCourant],
  )

  useDeclarerEcran({
    entete: {
      contexte: CONTEXTE_ONGLET[onglet],
      onglets: ongletsCultures({ nbPotager: toutesPotager.length, nbCatalogue: vue?.effectif_toutes ?? catalogue.length })
        .map((o) => ({ ...o, icon: ICONES_ONGLETS[o.id] })),
      actif: onglet,
      onChoisir: (id) => setEtat({ onglet: id }),
    },
    mot,
    barre: {
      date: onglet === ONGLET_POTAGER,   // [CA6] « Pas de bouton date » dans le Catalogue
      recherche: { placeholder: onglet === ONGLET_POTAGER ? 'Culture ou variété' : 'Espèce ou variété', valeur: etat.q, onChange: (q) => setEtat({ q }) },
      filtre: { nombre: nombreFiltres, onOuvrir: () => setFiltresOuverts(true) },
    },
  }, [onglet, JSON.stringify(mot), etat.q, nombreFiltres, toutesPotager.length, vue?.effectif_toutes])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error) return <ApiError message={error} onRetry={charger} />

  const ecrire = peutEnregistrer(potagerActif?.role)

  let corps
  if (onglet === ONGLET_POTAGER) {
    if (planEchoue) {
      corps = <ApiError message="Les cultures du potager n’ont pas pu être lues." onRetry={charger} />
    } else if (toutesPotager.length === 0) {
      corps = (
        <p className="px-1 py-6 text-center text-[13px] text-txt2">
          Rien n’est au potager en ce moment. Le Catalogue dit ce qu’on peut semer.{' '}
          <button type="button" onClick={() => setEtat({ onglet: ONGLET_CATALOGUE })} className="font-semibold text-brand-text underline">Voir le Catalogue</button>
        </p>
      )
    } else if (groupesPotager.length === 0) {
      corps = <p className="px-1 py-6 text-center text-[13px] text-txt2">Aucune culture ne correspond.</p>
    } else {
      corps = (
        <>
          <LegendeCalendrier />
          {groupesPotager.map((g) => (
            <section key={g.cle} aria-label={g.titre}>
              <EnTeteSection titre={`${g.titre} · ${g.lignes.length}`} />
              <Grille>
                {g.lignes.map((l) => (
                  <CarteAuPotager key={l.cle} l={l} moisCourant={moisZero} onOuvrir={() => ouvrirCulture(l.selection)} />
                ))}
              </Grille>
            </section>
          ))}
        </>
      )
    }
  } else if (groupesCatalogue.length === 0) {
    corps = <p className="px-1 py-6 text-center text-[13px] text-txt2">Aucune espèce ne correspond.</p>
  } else {
    const enPlace = (k) => lignesPotager.find((l) => l.culture === k.culture)?.selection ?? null
    corps = (
      <>
        {groupesCatalogue.map((g) => (
          <section key={g.cle} aria-label={g.titre}>
            <EnTeteSection titre={`${g.titre} · ${g.lignes.length}`} />
            <Grille>
              {g.lignes.map((k) => (
                <CarteCatalogue
                  key={k.cle} k={k} moisCourant={moisZero}
                  onOuvrir={() => ouvrirCatalogue(k, { enPlace: k.auPotager ? enPlace(k) : null })}
                />
              ))}
            </Grille>
          </section>
        ))}
        {ecrire && (
          <button
            type="button" onClick={() => ouvrirGastonSur({ sujet: sujetAjout() })}
            className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-[10px] border border-border bg-card px-4 text-[13.5px] font-semibold text-txt"
          >
            <Mic size={16} aria-hidden="true" />Une culture absente du catalogue ? Dites-la à Gaston
          </button>
        )}
      </>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {corps}
      {filtresOuverts && (
        <FeuilleFiltres
          onFermer={() => setFiltresOuverts(false)} peutEffacer={nombreFiltres > 0}
          onEffacer={() => setEtat({ famille: TOUTES })}
        >
          <GroupeChoix
            titre="Famille"
            options={[TOUTES, ...familles].map((f) => ({ valeur: f, libelle: f }))}
            valeur={famille} onChoisir={(f) => setEtat({ famille: f })}
          />
        </FeuilleFiltres>
      )}
    </div>
  )
}
