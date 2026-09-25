// [US-205] Écran Cultures — une carte par culture, au potager ou dans tout le
// référentiel. Portage de la maquette gelée « Cultures — écran et fiche »
// (25/09/2026) sur `GET /cultures/vue` (US-204) : cet écran ne calcule aucune
// règle, il met en forme (`lib/cultures.js`, CA14).
//
// [CA9] L'état exact (onglet, recherche, tri, filtres, défilement) survit à
// l'ouverture puis à la fermeture de la fiche culture parce que celle-ci est
// un simple état local de CE composant : la grille ne se démonte jamais
// pendant qu'elle est ouverte.
import { useEffect, useMemo, useState } from 'react'
import { Filter as FilterIcon, HelpCircle, ChevronRight, RefreshCw, AlertTriangle, MapPin, Cloud } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { Card, SearchField, Select, InfoBanner } from '../components/ui'
import DateRefPicker from '../components/DateRefPicker.jsx'
import { CarteCulture, CarteCultureSquelette } from '../components/CarteCulture.jsx'
import FicheCulture from '../components/FicheCulture.jsx'
import { MOIS_NOMS } from '../lib/calendrier.js'
import {
  TRI_CONFIANCE, TRI_ALPHA, TRI_FAMILLE, TRI_PAR_DEFAUT,
  famillesDisponibles, listeFiltree, grouperParFamille, autresDansToutes,
  nombreFiltresActifs, visibleDansOnglet,
} from '../lib/cultures.js'

const capitale = (s) => s.charAt(0).toUpperCase() + s.slice(1)
const TRI_OPTIONS = [
  { value: TRI_CONFIANCE, label: 'Confiance ↓' },
  { value: TRI_ALPHA, label: 'A → Z' },
  { value: TRI_FAMILLE, label: 'Par famille' },
]
const MOIS_OPTIONS = [{ value: '', label: 'Tous les mois' }, ...MOIS_NOMS.map((m, i) => ({ value: String(i + 1), label: capitale(m) }))]

/** [CA3] Pastilles de famille — « Toutes familles » plus une par famille disponible. */
function PastillesFamilles({ familles, valeur, onChange }) {
  return (
    <div role="group" aria-label="Filtrer par famille" className="flex flex-wrap gap-1.5">
      <button
        type="button" aria-pressed={!valeur} onClick={() => onChange(null)}
        className={`min-h-[32px] px-3 rounded-full border text-[12.5px] font-semibold whitespace-nowrap ${
          !valeur ? 'bg-brand-soft border-brand text-brand-text' : 'bg-card border-border text-txt2'
        }`}
      >
        Toutes familles
      </button>
      {familles.map((f) => (
        <button
          key={f} type="button" aria-pressed={valeur === f} onClick={() => onChange(valeur === f ? null : f)}
          className={`min-h-[32px] px-3 rounded-full border text-[12.5px] font-semibold whitespace-nowrap ${
            valeur === f ? 'bg-brand-soft border-brand text-brand-text' : 'bg-card border-border text-txt2'
          }`}
        >
          {f}
        </button>
      ))}
    </div>
  )
}

/** [CA11] Légende de la frise et zone climatique — une fois pour l'écran. */
function Legende({ vue }) {
  return (
    <div className="flex flex-wrap items-center gap-x-[18px] gap-y-2 bg-card border border-border rounded-xl px-4 py-2.5 text-[12.5px] text-txt2">
      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-blue" />Semis</span>
      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-brand" />Plantation</span>
      <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-amber" />Récolte</span>
      <span className="flex items-center gap-1.5">
        <span aria-hidden="true" className="w-2.5 h-2.5 rounded-sm outline outline-[1.5px] outline-offset-[1.5px] outline-txt" />
        Mois de référence
      </span>
      <span className="w-px h-4 bg-border hidden sm:block" aria-hidden="true" />
      <span>Confiance du meilleur geste ce jour</span>
      <span className="w-px h-4 bg-border hidden sm:block" aria-hidden="true" />
      <span className="flex items-center gap-1.5">
        <MapPin size={14} className="text-txt3" aria-hidden="true" />
        {vue?.zone_climatique ? `Zone ${vue.zone_climatique}, déduite de la ville du potager` : 'Zone climatique inconnue'}
      </span>
      {vue?.attributions?.length > 0 && (
        <span className="text-txt3">Calendriers : {vue.attributions.join(' · ')}</span>
      )}
    </div>
  )
}

/** [CA10] Grille en container queries — 1/2/3 colonnes, jamais 4. */
function Grille({ children }) {
  return (
    <div className="@container/cultures-grid">
      <div className="grid grid-cols-1 gap-3.5 @[520px]/cultures-grid:grid-cols-2 @[900px]/cultures-grid:grid-cols-3">
        {children}
      </div>
    </div>
  )
}

export default function Cultures({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId } = usePotager()

  const [vue, setVue] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState(false)

  const [onglet, setOnglet] = useState('potager')
  const [q, setQ] = useState('')
  const [tri, setTri] = useState(TRI_PAR_DEFAUT)
  const [famille, setFamille] = useState(null)
  const [mois, setMois] = useState(null)
  const [panneau, setPanneau] = useState(null)  // [CA18] 'filtres' | 'legende' | null, narrow uniquement
  const [cultureOuverte, setCultureOuverte] = useState(null)

  async function charger() {
    setChargement(true)
    setErreur(false)
    try {
      setVue(await api.vueCultures(dateRef, potagerId))
    } catch {
      setErreur(true)
    } finally {
      setChargement(false)
    }
  }

  useEffect(() => { charger() }, [refresh, dateRef, potagerId])  // eslint-disable-line react-hooks/exhaustive-deps

  const cultures = vue?.cultures || []
  const meteoDisponible = vue?.meteo_disponible !== false
  const auPotagerN = cultures.filter((c) => c.au_potager).length
  const toutesN = vue?.effectif_toutes ?? cultures.length

  const familles = useMemo(() => famillesDisponibles(cultures.filter((c) => visibleDansOnglet(c, onglet))), [cultures, onglet])
  const moisValeur = mois ? Number(mois) : null

  const liste = useMemo(
    () => listeFiltree(cultures, { onglet, recherche: q, famille, mois: moisValeur, tri, meteoDisponible }),
    [cultures, onglet, q, famille, moisValeur, tri, meteoDisponible],
  )
  const listeOnglet = useMemo(() => cultures.filter((c) => visibleDansOnglet(c, onglet)), [cultures, onglet])
  const autres = onglet === 'potager' ? autresDansToutes(cultures, listeOnglet, q) : 0
  const nActifs = nombreFiltresActifs({ famille, mois: moisValeur, tri })

  const toutEffacer = () => { setFamille(null); setMois(null); setTri(TRI_PAR_DEFAUT) }

  const auPotagerVide = onglet === 'potager' && !chargement && !erreur && auPotagerN === 0
  const suggestions = cultures.filter((c) => c.suggestion)

  let corps
  if (chargement) {
    corps = <Grille>{Array.from({ length: 6 }, (_, i) => <CarteCultureSquelette key={i} />)}</Grille>
  } else if (erreur) {
    corps = (
      <Card>
        <div className="flex items-center gap-3 flex-wrap">
          <AlertTriangle size={20} className="text-red shrink-0" />
          <div className="flex-1 min-w-[200px] text-[13.5px] text-txt leading-[1.5]">
            Les cultures n’ont pas pu être lues. Rien n’a été modifié.
          </div>
          <button
            onClick={charger}
            className="inline-flex items-center gap-1.5 text-[13.5px] font-semibold rounded-[10px] px-3.5 py-1.5 border border-border bg-card text-txt2"
          >
            <RefreshCw size={13} />Réessayer
          </button>
        </div>
      </Card>
    )
  } else if (auPotagerVide) {
    corps = (
      <div className="flex flex-col gap-3.5">
        <Card>
          <div className="font-serif text-[16px] font-semibold text-txt">Rien au potager en ce moment</div>
          <div className="text-[13px] text-txt2 mt-1 leading-[1.5]">
            Aucune culture n’est en place ni en pépinière{dateRef ? ` au ${dateRef}` : ''}. Voici ce dont la fenêtre est ouverte dans ta zone.
          </div>
          <button
            onClick={() => setOnglet('toutes')}
            className="mt-2.5 inline-flex items-center gap-1 text-[13px] font-semibold text-brand-text"
          >
            Voir les {toutesN} cultures du référentiel<ChevronRight size={14} strokeWidth={2} aria-hidden="true" />
          </button>
        </Card>
        {suggestions.length > 0 && (
          <Grille>{suggestions.map((c) => (
            <CarteCulture key={c.culture} ligne={c} meteoDisponible={meteoDisponible} onOpen={() => setCultureOuverte(c.culture)} />
          ))}</Grille>
        )}
      </div>
    )
  } else if (liste.length === 0) {
    corps = <div className="text-[13px] text-txt2 px-1 py-4">Aucune culture ne correspond{autres ? '' : ' à ces filtres'}.</div>
  } else if (tri === TRI_FAMILLE) {
    corps = (
      <div className="flex flex-col gap-[18px]">
        {grouperParFamille(liste).map((groupe) => (
          <div key={groupe.famille}>
            <div className="text-[11px] font-bold text-txt3 uppercase tracking-[.06em] mb-2">
              {groupe.famille} · {groupe.cultures.length}
            </div>
            <Grille>{groupe.cultures.map((c) => (
              <CarteCulture key={c.culture} ligne={c} meteoDisponible={meteoDisponible} onOpen={() => setCultureOuverte(c.culture)} />
            ))}</Grille>
          </div>
        ))}
      </div>
    )
  } else {
    corps = (
      <Grille>{liste.map((c) => (
        <CarteCulture key={c.culture} ligne={c} meteoDisponible={meteoDisponible} onOpen={() => setCultureOuverte(c.culture)} />
      ))}</Grille>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5 flex-wrap">
        <h1 className="font-serif text-[22px] sm:text-2xl font-semibold text-txt tracking-tight">Cultures</h1>
        <div role="tablist" aria-label="Périmètre" className="flex gap-1 bg-card-alt rounded-[11px] p-1 flex-1 sm:flex-none min-w-0">
          {[['potager', `Au potager · ${auPotagerN}`], ['toutes', `Toutes · ${toutesN}`]].map(([id, label]) => (
            <button
              key={id} role="tab" aria-selected={onglet === id} onClick={() => setOnglet(id)}
              className={`flex-1 sm:flex-none min-h-[36px] px-3.5 rounded-[8px] text-[13px] whitespace-nowrap ${
                onglet === id ? 'bg-card text-txt font-bold shadow-card' : 'text-txt2 font-medium'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* [CA18] Large : tout en ligne(s). Étroit (< sm) : une ligne + deux panneaux. */}
      <div className="hidden sm:flex items-center gap-2.5 flex-wrap">
        <DateRefPicker />
        <div className="flex-1 min-w-[200px] max-w-[340px]"><SearchField wide value={q} onChange={setQ} placeholder={onglet === 'potager' ? 'Culture ou variété…' : 'Rechercher une culture…'} /></div>
        <Select value={tri} options={TRI_OPTIONS} onChange={setTri} />
        <div aria-label="Filtrer par mois de semis ou de plantation"><Select value={mois || ''} options={MOIS_OPTIONS} onChange={(v) => setMois(v || null)} /></div>
      </div>
      <div className="hidden sm:block"><PastillesFamilles familles={familles} valeur={famille} onChange={setFamille} /></div>
      <div className="hidden sm:block"><Legende vue={vue} /></div>

      <div className="flex sm:hidden items-center gap-2">
        <DateRefPicker className="flex items-center gap-1" />
        <div className="flex-1 min-w-0"><SearchField wide value={q} onChange={setQ} placeholder="Rechercher…" /></div>
        <button
          type="button" onClick={() => setPanneau(panneau === 'filtres' ? null : 'filtres')}
          aria-expanded={panneau === 'filtres'} aria-label={`Filtres${nActifs ? `, ${nActifs} actifs` : ''}`}
          className={`min-w-[44px] h-[44px] px-2.5 rounded-[10px] border flex items-center justify-center gap-1 ${
            nActifs ? 'bg-brand-soft border-brand text-brand-text' : 'bg-card border-border text-txt2'
          }`}
        >
          <FilterIcon size={16} />{nActifs > 0 && <span className="text-[12.5px] font-bold">{nActifs}</span>}
        </button>
        <button
          type="button" onClick={() => setPanneau(panneau === 'legende' ? null : 'legende')}
          aria-expanded={panneau === 'legende'} aria-label="Légende"
          className={`w-[44px] h-[44px] rounded-[10px] border flex items-center justify-center ${
            panneau === 'legende' ? 'bg-brand-soft border-brand text-brand-text' : 'bg-card border-border text-txt2'
          }`}
        >
          <HelpCircle size={17} />
        </button>
      </div>
      {panneau === 'filtres' && (
        <div className="sm:hidden flex flex-col gap-2.5 bg-card border border-border rounded-xl p-3">
          <div className="flex gap-2 flex-wrap">
            <Select value={tri} options={TRI_OPTIONS} onChange={setTri} />
            <Select value={mois || ''} options={MOIS_OPTIONS} onChange={(v) => setMois(v || null)} />
          </div>
          <PastillesFamilles familles={familles} valeur={famille} onChange={setFamille} />
          {nActifs > 0 && (
            <button onClick={toutEffacer} className="self-start text-[12.5px] font-semibold text-brand-text">Tout effacer</button>
          )}
        </div>
      )}
      {panneau === 'legende' && <div className="sm:hidden"><Legende vue={vue} /></div>}

      {!meteoDisponible && !chargement && !erreur && (
        <InfoBanner
          tint="amber" icon={Cloud} title="Confiance indisponible"
          body="La météo du potager n’a pas pu être lue : aucune étoile n’est affichée. Frises et présence au potager restent à jour."
        />
      )}

      {autres > 0 && !chargement && !erreur && (
        <button
          onClick={() => setOnglet('toutes')}
          className="self-start inline-flex items-center gap-1.5 bg-card-alt border border-border rounded-[10px] px-3 py-2 text-[13px] font-semibold text-brand-text min-h-[40px]"
        >
          {autres} autre{autres > 1 ? 's' : ''} dans Toutes<ChevronRight size={15} strokeWidth={2} aria-hidden="true" />
        </button>
      )}

      {corps}

      {cultureOuverte && (
        <FicheCulture
          culture={cultureOuverte} dateRef={dateRef} potagerId={potagerId}
          ecran="cultures" onClose={() => setCultureOuverte(null)}
        />
      )}
    </div>
  )
}
