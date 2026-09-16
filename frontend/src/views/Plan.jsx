// [US-060] Écran Plan — portage de `ScreenPlan` (`web-screens.jsx`, maquette
// 2026) sur les données réelles de `GET /plan`. La pile de cartes autonomes
// laisse place au **maître-détail** de la maquette : la liste des parcelles à
// gauche, la fiche de celle qui est sélectionnée à droite.
//
// Les fonctions que la maquette ne connaît pas (date de référence, filtre
// culture, bandeau de métriques, observations à deux niveaux, pastille
// végétatif/reproducteur, badge « Libre ») sont **conservées et logées** dans
// cette mise en page, jamais abandonnées au passage.
import { useState, useEffect, useMemo } from 'react'
import { MapPin, Leaf } from 'lucide-react'
import { api } from '../lib/api.js'
import {
  culturesDuPlan, friseDeCulture, zoneAffichable, attributionsAffichables, TIRET,
  projectionDeTuile, friseRecalee, resteLisible, reperesLisibles,
} from '../lib/calendrier.js'
import {
  occTint, pctDe, totalPlants, formatUnite, expositionAffichable, moisDeLaDate,
  filtrerParcelles, parcelleSelectionnee,
} from '../lib/plan.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import CultureFilter from '../components/CultureFilter.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import MetricStrip from '../components/MetricStrip.jsx'
import { ObservationIcon, ObservationPanel } from '../components/Observations.jsx'
import { useObservations } from '../hooks/useObservations.js'
import { ObservationsUIProvider } from '../context/ObservationsUIContext.jsx'
import {
  Card, CardHead, Badge, ProgressBar, SectionLabel, Tip, MonthStrip, MonthStripLegend,
} from '../components/ui'

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Classes en toutes lettres : Tailwind ne génère rien pour `text-${tint}`. */
const OCC_TXT = { red: 'text-red', amber: 'text-amber', brand: 'text-brand' }

const occTxtCls = (pct) => OCC_TXT[occTint(pct)]

/** [CA13] Pastille du modèle de stock — végétatif (vert) vs reproducteur (ambre). */
function PastilleOrgane({ typeOrgane }) {
  const vegetatif = typeOrgane === 'végétatif'
  return (
    <span
      aria-hidden="true"
      className={`w-2.5 h-2.5 rounded-full shrink-0 ${vegetatif ? 'bg-brand' : 'bg-amber'}`}
    />
  )
}

// ── Ligne de la liste des parcelles ──────────────────────────────────────────

/**
 * [CA2] Tuile d'emplacement, nom serif, « N cultures · X m² », taux à droite.
 * L'icône d'épingle porte la couleur du taux ; c'est le **fond de la tuile** qui
 * bascule à la sélection, pas la couleur de l'icône.
 */
function ParcelleRow({ parcelle, selected, onSelect }) {
  const pct = pctDe(parcelle)
  const libre = parcelle.cultures.length === 0

  return (
    <button
      onClick={onSelect}
      aria-pressed={selected}
      className={`text-left w-full flex items-center gap-[11px] px-3 py-[11px] rounded-xl border transition-colors ${
        selected ? 'bg-brand-soft border-brand' : 'bg-card border-border shadow-card'
      }`}
    >
      <div
        className={`w-[34px] h-[34px] rounded-[10px] flex items-center justify-center shrink-0 ${
          selected ? 'bg-card' : 'bg-card-alt'
        }`}
      >
        <MapPin size={17} className={occTxtCls(pct)} aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-serif text-[14.5px] font-semibold text-txt truncate">{parcelle.nom}</div>
        <div className="text-[11.5px] text-txt3 mt-px truncate">
          {parcelle.cultures.length} culture{parcelle.cultures.length > 1 ? 's' : ''}
          {parcelle.superficie_m2 ? ` · ${parcelle.superficie_m2} m²` : ''}
        </div>
      </div>
      {/* [CA14] Une parcelle sans culture reste identifiable dès la liste. */}
      {libre && <Badge className="shrink-0">Libre</Badge>}
      <span className={`text-[12.5px] font-bold shrink-0 ${occTxtCls(pct)}`}>{pct}%</span>
    </button>
  )
}

// ── Tuile de culture ─────────────────────────────────────────────────────────

/**
 * [CA7] Nom serif + variété italique, quantité à droite, ligne « famille ·
 * durée », puis la frise des douze mois.
 *
 * [US-176] Frise et durée lues dans le référentiel du potager consulté
 * (`GET /plan/calendriers`). Une culture sans calendrier pour sa zone s'affiche
 * en **mode dégradé** — frise neutre, durée en tiret — plutôt qu'avec des
 * valeurs par défaut qui auraient l'air d'un conseil (CA6).
 */
function CultureTile({ c, parcelleId, moisRef, calendriers }) {
  const obs = useObservations(
    `culture-row:${parcelleId}:${c.culture}:${c.variete || ''}`,
    { parcelleId, culture: c.culture, variete: c.variete },
  )

  const frise = friseDeCulture(calendriers, c.culture)
  // [US-070] Une culture en place se lit sur SON calendrier, recalé sur le
  // semis réel ; sans recalage possible (CA11), la frise conseillée reste.
  const projection = projectionDeTuile(calendriers, parcelleId, c.culture, c.variete)
  const recalee = friseRecalee(projection)
  const reste = resteLisible(projection)
  const reperes = reperesLisibles(projection)
  // [US-067 / CA5, CA6, CA8] Famille lue depuis GET /plan (culture_config →
  // familles_botaniques côté serveur). [US-176 / CA7] Elle ne dépend plus de la
  // présence d'un calendrier : une culture sans frise garde sa famille. Repli
  // `null` — pas "Autres" (US-060/CA9).
  const famille = c.famille ?? null

  return (
    <div className="bg-card-alt rounded-xl p-[13px]">
      <div className="flex items-baseline gap-1.5 mb-[3px]">
        <PastilleOrgane typeOrgane={c.type_organe} />
        <span className="font-serif text-[15.5px] font-semibold text-txt capitalize">{c.culture}</span>
        {c.variete && (
          <span className="font-serif italic text-[12.5px] text-txt3 truncate">{c.variete}</span>
        )}
        {/* [US-039 / CA15] Observations du couple culture + variété. */}
        {c.has_observations && (
          <ObservationIcon onClick={obs.toggle} active={obs.open} size={15} count={c.nb_observations} />
        )}
        {/* [CA18] La quantité est affichée avec son unité de saisie : une culture
            semée en m² reste en m², jamais convertie en nombre de plants. */}
        <span className="ml-auto text-[15px] font-bold text-brand shrink-0">
          {c.nb_plants}
          <span className="text-[11px] font-semibold text-txt3"> {formatUnite(c.unite)}</span>
        </span>
      </div>
      <div className={`text-[11.5px] text-txt3 ${reperes.length ? 'mb-1' : 'mb-2.5'}`}>
        {famille || TIRET} ·{' '}
        {/* [US-070 / CA3, CA12] Le reste à courir remplace la durée conseillée ;
            une récolte dépassée est dite, jamais masquée. */}
        {reste
          ? <span className={projection.etat === 'recolte_depassee' ? 'font-semibold text-amber' : 'font-semibold text-txt2'}>{reste}</span>
          : frise.duree}
        {/* [US-176 / CA5] Un itinéraire autre que « standard » est nommé. */}
        {frise.itineraire && <span className="italic"> · {frise.itineraire}</span>}
      </div>
      {reperes.length > 0 && (
        <div className="text-[11px] text-txt3 mb-2.5">
          {reperes.join(' · ').replace(/^./, (l) => l.toUpperCase())}
        </div>
      )}
      {/* [US-176 / CA3, CA3bis] Quatre phases du référentiel ; la plantation est
          lue, jamais reconstituée du semis en pépinière. [US-070 / CA7] Recalée,
          la frise suit la culture : semis, plantation, en croissance, récolte. */}
      {recalee ? (
        <MonthStrip
          pepiniere={recalee.pepiniere}
          pleineTerre={recalee.pleineTerre}
          plantation={recalee.plantation}
          croissance={recalee.croissance}
          rec={recalee.rec}
          moisCourant={moisRef}
        />
      ) : (
        <MonthStrip
          pepiniere={frise.pepiniere}
          pleineTerre={frise.pleineTerre}
          plantation={frise.plantation}
          rec={frise.rec}
          moisCourant={moisRef}
        />
      )}
      {c.has_observations && obs.open && <ObservationPanel items={obs.items} loading={obs.loading} />}
    </div>
  )
}

// ── Panneau de détail de la parcelle sélectionnée ────────────────────────────

function DetailParcelle({ parcelle, moisRef, calendriers }) {
  const { id, nom, superficie_m2, cultures, has_observations, nb_observations } = parcelle
  const exposition = expositionAffichable(parcelle.exposition)
  const pct = pctDe(parcelle)
  const libre = cultures.length === 0
  const obs = useObservations(`parcelle:${id}`, { parcelleId: id })

  // [CA6] Total restreint aux cultures effectivement comptées en plants.
  const nbPlants = totalPlants(cultures)
  const zone = zoneAffichable(calendriers)
  const attributions = attributionsAffichables(calendriers)

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-serif text-[24px] font-semibold text-brand-text tracking-tight">{nom}</span>
          {/* [CA14] Badge « Libre » également porté par le panneau de détail. */}
          {libre && <Badge>Libre</Badge>}
          {/* [US-039 / CA15] Observations de la parcelle. */}
          {has_observations && (
            <ObservationIcon onClick={obs.toggle} active={obs.open} count={nb_observations} />
          )}
        </div>

        {/* [CA4] Pastilles de caractéristiques. La pastille « Sol » de la maquette
            est omise : le type de sol n'existe pas en base (colonne posée par
            US-058, non livrée) et n'est pas remplacé par un texte de substitution. */}
        {(superficie_m2 || exposition) && (
          <div className="flex gap-[7px] mt-2.5 flex-wrap">
            {superficie_m2 && <Badge tint="brand">{superficie_m2} m²</Badge>}
            {exposition && <Badge tint="amber">Exposition {exposition}</Badge>}
          </div>
        )}

        {has_observations && obs.open && <ObservationPanel items={obs.items} loading={obs.loading} />}

        {/* [CA5] Occupation de la surface, sous un séparateur. */}
        <div className="mt-4 pt-3.5 border-t border-border-soft">
          <div className="flex items-center justify-between gap-2 mb-[7px]">
            <span className="text-[12.5px] text-txt2 flex items-center gap-1.5">
              Occupation de la surface
              <Tip text="Part de la parcelle réellement plantée, calculée depuis les densités de chaque culture en place." />
            </span>
            <span className={`text-[13px] font-bold ${occTxtCls(pct)}`}>{pct} %</span>
          </div>
          <ProgressBar pct={pct} label={`Occupation de ${nom}`} />
        </div>
      </Card>

      {/* [CA14] Une parcelle libre n'affiche pas une carte « Cultures en place » vide. */}
      {!libre && (
        <Card>
          <CardHead
            icon={Leaf}
            title="Cultures en place"
            sub={`${cultures.length} culture${cultures.length > 1 ? 's' : ''}${
              nbPlants > 0 ? ` · ${nbPlants} plants` : ''
            }`}
            right={
              <MonthStripLegend
                variante="referentiel"
                avecCroissance={cultures.some((c) => friseRecalee(projectionDeTuile(calendriers, id, c.culture, c.variete)))}
              />
            }
          />
          {/* [CA7] Paliers de la maquette (`.wcult-grid`) : une colonne, deux à
              partir de 640 px de carte, trois à partir de 1400 px — largeur du
              conteneur, jamais de l'écran (règle « Responsive » de CLAUDE.md). */}
          <div className="grid gap-3 @[640px]/card:grid-cols-2 @[1400px]/card:grid-cols-3">
            {cultures.map((c, i) => (
              <CultureTile
                key={`${c.culture}-${c.variete || ''}-${i}`}
                c={c} parcelleId={id} moisRef={moisRef} calendriers={calendriers}
              />
            ))}
          </div>
          {/* [CA13] Légende de la pastille du modèle de stock, absente de la
              maquette mais clé de lecture du calcul de stock de l'application. */}
          <div className="flex gap-4 mt-3.5 pt-3 border-t border-border-soft text-[11.5px] text-txt2">
            <span className="flex items-center gap-1.5">
              <PastilleOrgane typeOrgane="végétatif" />végétatif
            </span>
            <span className="flex items-center gap-1.5">
              <PastilleOrgane typeOrgane="reproducteur" />reproducteur
            </span>
          </div>
          {/* [US-176 / CA8, CA9] Zone lue et attribution : une fois pour toutes
              les tuiles, jamais répétées sur chacune. */}
          {(zone || attributions.length > 0) && (
            <div className="mt-2.5 text-[11px] text-txt3 flex flex-col gap-1">
              {zone && (
                <span>
                  Calendrier de la zone <span className="font-semibold text-txt2">{zone.zone}</span>
                  {zone.origine ? ` (${zone.origine})` : ''} — pour la changer, dites au bot
                  « /calendrier zone ».
                </span>
              )}
              {attributions.length > 0 && <span>Source : {attributions.join(' · ')}</span>}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Plan({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId } = usePotager()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')      // [CA16] filtre local, non persisté
  const [selId, setSelId] = useState(null)
  const [calendriers, setCalendriers] = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      // [US-083 / CA7] Si on consulte un potager archivé, passer son ID
      const plan = await api.plan(dateRef, potagerId)
      // [US-176 / CA11, CA12] Calendrier de toutes les cultures en UNE lecture,
      // attendue avant d'afficher l'écran (pas de frise qui clignote). Son échec
      // ne bloque rien : les frises passent en mode dégradé, sans repli.
      const noms = culturesDuPlan(plan?.parcelles)
      let cal = null
      if (noms.length > 0) {
        try {
          cal = await api.calendriersPlan(noms, potagerId, dateRef)
        } catch (e) {
          console.warn('[US-176] Calendrier cultural indisponible', e)
        }
      }
      setCalendriers(cal)
      setData(plan)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [refresh, dateRef, potagerId])

  const parcelles = data?.parcelles ?? []

  // [CA16] Filtre culture, conservé d'US-031 (cf. `lib/plan.js`).
  const filtered = useMemo(() => filtrerParcelles(parcelles, search), [parcelles, search])

  // [CA1/CA16] Une seule parcelle sélectionnée ; la première de la liste à
  // l'ouverture, et la première encore listée quand le filtre exclut celle qui
  // l'était.
  const selection = parcelleSelectionnee(filtered, selId)

  const moisRef = moisDeLaDate(data?.date_ref_effective)

  const nbActives = filtered.filter((p) => p.cultures.length > 0).length
  const nbCultures = filtered.reduce((s, p) => s + p.cultures.length, 0)

  if (loading) return <LoadingSkeleton lines={4} />
  if (error) return <ApiError message={error} onRetry={load} />

  return (
    <ObservationsUIProvider>
      <div className="flex flex-col gap-3.5">
        {/* [CA16] Sélecteur de date de référence + filtre culture, composants US-059. */}
        <div className="flex items-center gap-2">
          <DateRefPicker />
          <CultureFilter value={search} onChange={setSearch} className="relative flex-1 min-w-0" />
        </div>

        {filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-3 mt-12 text-txt3">
            <Leaf size={36} />
            <p className="text-base">
              {search ? 'Aucune culture correspondante.' : 'Aucune parcelle enregistrée.'}
            </p>
          </div>
        ) : (
          <>
            {/* [CA16] Bandeau de métriques conservé. */}
            <MetricStrip
              metrics={[
                { value: nbActives, label: 'parcelles actives', tone: 'brand' },
                { value: nbCultures, label: 'cultures en place', tone: 'txt' },
              ]}
            />

            {/* [CA3] Bascule pilotée par la largeur du **conteneur** : une seule
                colonne sous 900 px, puis liste calée à 290 px et détail fluide,
                les deux alignés en haut. */}
            <div className="@container/plan">
              <div className="grid gap-4 items-start @[900px]/plan:grid-cols-[290px_1fr]">
                <aside>
                  <SectionLabel>Mes parcelles · {filtered.length}</SectionLabel>
                  <div className="flex flex-col gap-[7px]">
                    {filtered.map((p) => (
                      <ParcelleRow
                        key={p.id}
                        parcelle={p}
                        selected={selection?.id === p.id}
                        onSelect={() => setSelId(p.id)}
                      />
                    ))}
                  </div>
                </aside>

                {selection && (
                  // La sélection remonte le composant à neuf : les panneaux
                  // d'observations d'une parcelle ne survivent pas au passage à
                  // la suivante.
                  <DetailParcelle key={selection.id} parcelle={selection} moisRef={moisRef} calendriers={calendriers} />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </ObservationsUIProvider>
  )
}
