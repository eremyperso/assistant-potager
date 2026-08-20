import { useState } from 'react'
import { Sprout, Leaf, ShoppingBasket, MapPin, BarChart3, Home, Calendar, Layers } from 'lucide-react'
import { AppContextProvider } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import CultureFilter from '../components/CultureFilter.jsx'
import MetricStrip from '../components/MetricStrip.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import { ObservationIcon, ObservationPanel } from '../components/Observations.jsx'
import {
  Card,
  CardHead,
  Btn,
  Badge,
  Stat,
  ProgressBar,
  MonthStrip,
  SearchField,
  Select,
  TileNav,
  InfoBanner,
  Tip,
} from '../components/ui'

/**
 * Page de contrôle visuel du design system [US-052].
 * Sert à valider les composants isolément avant leur usage dans les écrans
 * (Lot B). Non référencée par la navigation applicative.
 */
export default function DesignSystemPreview() {
  return (
    <div className="min-h-dvh bg-bg p-4 flex flex-col gap-6">
      <h1 className="font-serif text-2xl font-bold text-txt">Design system — US-052</h1>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">InfoBanner</h2>
        <InfoBanner
          icon={Sprout}
          title="Votre saison est à mi-parcours"
          body="8 plants de butternut attendent d'être mis en terre."
          action={<Btn kind="soft" small>Voir</Btn>}
        />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">Btn — 4 variantes</h2>
        <div className="flex flex-wrap gap-2">
          <Btn kind="primary" icon={Sprout}>Primary</Btn>
          <Btn kind="ghost" icon={Leaf}>Ghost</Btn>
          <Btn kind="soft">Soft</Btn>
          <Btn kind="quiet">Quiet</Btn>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">Badge</h2>
        <div className="flex flex-wrap gap-2">
          <Badge tint="brand">brand</Badge>
          <Badge tint="amber">amber</Badge>
          <Badge tint="red">red</Badge>
          <Badge tint="blue">blue</Badge>
          <Badge tint="violet">violet</Badge>
          <Badge tint="brand" solid>solid</Badge>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">Stat</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Stat icon={MapPin} value={5} label="parcelles suivies" tip="Espaces de culture définis." />
          <Stat icon={Leaf} tint="blue" value={21} label="cultures en place" />
          <Stat icon={ShoppingBasket} tint="amber" value="11.6" unit="kg" label="récoltés en 2026" />
          <Stat icon={Sprout} tint="violet" value={61} label="plants en godet" />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">
          Card + CardHead + ProgressBar + MonthStrip
        </h2>
        <Card>
          <CardHead
            icon={ShoppingBasket}
            tint="amber"
            title="Récoltes de la saison"
            sub="Cumul par culture"
            right={<Btn kind="quiet" small>Détail</Btn>}
          />
          <div className="flex items-center justify-between mb-2">
            <span className="text-[12.5px] text-txt2 flex items-center gap-1.5">
              Occupation
              <Tip text="Part de la parcelle réellement plantée." />
            </span>
            <span className="text-[13px] font-bold text-amber">62 %</span>
          </div>
          <ProgressBar pct={62} label="Occupation de la parcelle" />
          <div className="mt-4">
            <MonthStrip semis={[2, 3]} plant={[4, 5]} rec={[6, 7, 8]} legend />
          </div>
        </Card>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">
          Card en grille (même composant, contexte étroit)
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {['Tomate', 'Courgette', 'Betterave'].map((n) => (
            <Card key={n}>
              <CardHead icon={Leaf} title={n} sub="Solanacée" right={<Badge tint="brand">14</Badge>} />
              <MonthStrip semis={[2, 3]} plant={[4]} rec={[6, 7, 8]} />
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">SearchField + Select</h2>
        <div className="flex flex-wrap gap-2">
          <SearchField wide placeholder="Rechercher une culture…" />
          <Select value="Toutes" options={['Toutes', 'Solanacée', 'Cucurbitacée']} onChange={() => {}} />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">TileNav</h2>
        <TileNav
          active="bord"
          onPick={() => {}}
          items={[
            { id: 'bord', label: "Vue d'ensemble", icon: Home },
            { id: 'stats', label: 'Statistiques', icon: BarChart3 },
            { id: 'rot', label: 'Rotation', icon: Calendar },
            { id: 'plan', label: 'Vue plan', icon: Layers, badge: 2 },
          ]}
        />
      </section>

      <TransversesPreview />
    </div>
  )
}

/**
 * Composants transverses aux quatre écrans de consultation [US-059].
 * Ils vivent hors de `components/ui/` parce qu'ils portent une logique métier
 * (date de référence persistée, filtre culture, observations chargées à la
 * demande), mais leur habillage vient désormais du design system — d'où leur
 * présence sur cette page de contrôle.
 */
function TransversesPreview() {
  const [search, setSearch] = useState('')
  const [obsOuvert, setObsOuvert] = useState(true)

  return (
    <AppContextProvider>
      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">
          US-059 — Filtres transverses (DateRefPicker + CultureFilter)
        </h2>
        <div className="flex items-center gap-2">
          <DateRefPicker />
          <CultureFilter value={search} onChange={setSearch} className="relative flex-1" />
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">
          US-059 — MetricStrip
        </h2>
        <MetricStrip
          metrics={[
            { value: 61, label: 'godets dispo', color: 'var(--txt)' },
            { value: '78%', label: 'réussite moy.', color: 'var(--brand)' },
            { value: 3, label: 'perdus', color: 'var(--red)' },
          ]}
        />
        <p className="text-[11.5px] text-txt3">Deux métriques sur trois zones (la troisième reste vide) :</p>
        <MetricStrip
          metrics={[
            { value: 5, label: 'parcelles actives', color: 'var(--brand)' },
            { value: 21, label: 'cultures en place', color: 'var(--txt)' },
          ]}
        />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">
          US-059 — Observations (icône + panneau)
        </h2>
        <Card>
          <div className="flex items-center gap-2">
            <span className="flex-1 text-[15px] font-semibold text-txt">Planche nord</span>
            <ObservationIcon onClick={() => setObsOuvert((v) => !v)} active={obsOuvert} count={3} />
          </div>
          {obsOuvert && (
            <ObservationPanel
              items={[
                { date: '12/04', texte: 'Quelques pucerons sur les jeunes pousses, à surveiller.' },
                { date: '03/05', texte: 'Sol encore lourd après les pluies.' },
                { date: '21/05', texte: 'Première fleur.' },
                { date: '02/06', texte: 'Paillage renouvelé.' },
              ]}
              loading={false}
            />
          )}
        </Card>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider text-txt3">
          US-059 — LoadingSkeleton + ApiError
        </h2>
        <LoadingSkeleton lines={2} />
        <ApiError message="Données indisponibles" onRetry={() => {}} />
      </section>
    </AppContextProvider>
  )
}
