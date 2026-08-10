import { Sprout, Leaf, ShoppingBasket, MapPin, BarChart3, Home, Calendar, Layers } from 'lucide-react'
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
    </div>
  )
}
