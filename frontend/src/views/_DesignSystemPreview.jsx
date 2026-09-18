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
  BlocConfiance,
  Etoiles,
  PastilleConfiance,
  PuceConfiance,
  SelecteurAction,
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

      <ConfiancePreview />

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

// ── [US-180, US-183] Bloc « règle de confiance » — états de la maquette gelée ──
// ⚠️ Valeurs de DÉMONSTRATION, reprises des états de la maquette du 18/09/2026 :
// elles servent au contrôle visuel et n'engagent aucune agronomie.
const R = (regle, etat, libelle, points, points_max) => ({ regle, etat, libelle, points, points_max })
const DEMO_COURGETTE = {
  action: 'semis_pleine_terre', etoiles: 2, score: 70, avertissements: [],
  motifs: [
    R('R1', 'gagne', 'Dans la fenêtre conseillée pour ta zone', 40, 40),
    R('R2', 'indetermine', 'Sensibilité au gel inconnue pour cette culture', 0, 20),
    R('R3', 'gagne', 'Aucun gel annoncé sur 14 jours', 20, 20),
    R('R4', 'perdu', 'Nuits fraîches : levée lente probable', 0, 10),
    R('R5', 'gagne', 'La récolte arriverait avant la fin de saison', 10, 10),
  ],
}
const DEMO_TOMATE = {
  action: 'plantation', etoiles: 3, score: 100, avertissements: [],
  motifs: [
    R('R1', 'gagne', 'Dans la fenêtre conseillée pour ta zone', 40, 40),
    R('R2', 'gagne', 'Dernière gelée moyenne passée', 20, 20),
    R('R3', 'gagne', 'Aucun gel annoncé sur 14 jours', 20, 20),
    R('R4', 'gagne', 'Nuits douces sur les 7 prochains jours', 10, 10),
    R('R5', 'gagne', 'La récolte arriverait avant la fin de saison', 10, 10),
  ],
}
const DEMO_NON_LOCALISE = {
  ...DEMO_COURGETTE,
  avertissements: ["Sans météo, la troisième étoile est hors d'atteinte : 70 points possibles sur 100"],
  motifs: [
    R('R1', 'gagne', 'Dans la fenêtre conseillée pour ta zone', 40, 40),
    R('R2', 'gagne', 'Dernière gelée moyenne passée', 20, 20),
    R('R3', 'indetermine', 'Météo indisponible : localise ton potager pour la prendre en compte', 0, 20),
    R('R4', 'indetermine', 'Météo indisponible', 0, 10),
    R('R5', 'gagne', 'La récolte arriverait avant la fin de saison', 10, 10),
  ],
}

function ConfiancePreview() {
  const [action, setAction] = useState('plantation')
  const titre = 'text-[11.5px] font-bold uppercase tracking-wider text-txt3'
  return (
    <section className="flex flex-col gap-3">
      <h2 className={titre}>Bloc « règle de confiance » [US-180, US-183]</h2>
      <div className="grid gap-3 md:grid-cols-3">
        {[
          ['Deux étoiles — une règle perdue, une indéterminée', DEMO_COURGETTE, null],
          ['Trois étoiles — aucune perte', DEMO_TOMATE, null],
          ['Deux étoiles — potager non localisé', DEMO_NON_LOCALISE, DEMO_NON_LOCALISE.avertissements[0]],
        ].map(([t, c, note]) => (
          <div key={t} className="flex flex-col gap-2">
            <div className="text-[12px] text-txt2">{t}</div>
            <BlocConfiance confiance={c} note={note} />
          </div>
        ))}
      </div>

      <h2 className={titre}>Sélecteur d'action [US-183]</h2>
      <Card>
        <SelecteurAction
          actions={[{ ...DEMO_COURGETTE, action: 'semis_pepiniere', etoiles: 2 }, DEMO_TOMATE]}
          value={action}
          onChange={setAction}
        />
      </Card>

      <h2 className={titre}>Pastille de tuile et puce de Stocks [US-180, US-183]</h2>
      <Card>
        {[['courgette', 'Cucurbitacée · 95 j', DEMO_COURGETTE], ['tomate', 'Solanacée · —', DEMO_TOMATE], ['ail', 'Alliacée · —', null]].map(([nom, ligne, c]) => (
          <div key={nom} className="bg-card-alt rounded-xl p-[13px] mb-2 last:mb-0">
            <div className="font-serif text-[15.5px] font-semibold text-txt capitalize">{nom}</div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11.5px] text-txt3">{ligne}</span>
              {c
                ? <PastilleConfiance confiance={c} onClick={() => {}} />
                : <span className="ml-auto text-[11px] font-semibold text-txt3 shrink-0">— pas de calendrier</span>}
            </div>
            <div className="flex gap-1.5 flex-wrap mt-2">
              <PuceConfiance confiance={c} sansCalendrier={!c} onClick={() => {}} />
              <PuceConfiance confiance={null} onClick={() => {}} />
            </div>
          </div>
        ))}
        <div className="flex items-center gap-2 mt-3 text-[11.5px] text-txt2">
          <Etoiles etoiles={2} taille={11} />confiance de la semaine — appuyer ouvre le détail des règles
        </div>
      </Card>
    </section>
  )
}
