import { useState, useEffect } from 'react'
import { Leaf, Sprout, ShoppingBag } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import CultureFilter from '../components/CultureFilter.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Badges d'origine ──────────────────────────────────────────────────────────

const ORIGINE_CONFIG = {
  'pépinière':          { label: 'Pépinière',         bg: 'var(--g-acc-dim)', text: 'var(--g-acc)' },
  'pied_acheté':        { label: 'Pied acheté',        bg: 'var(--g-amb-dim)', text: 'var(--g-amb)' },
  'semis_pleine_terre': { label: 'Semis pleine terre', bg: 'var(--g-brd)',     text: 'var(--g-mid)' },
}

function OrigineBadge({ origine }) {
  const cfg = ORIGINE_CONFIG[origine]
  if (!cfg) return null
  return (
    <span
      className="text-[11px] font-medium px-2 py-0.5 rounded-full"
      style={{ background: cfg.bg, color: cfg.text }}
    >
      {cfg.label}
    </span>
  )
}

// ── Ligne culture au potager ──────────────────────────────────────────────────

function CultureRow({ c }) {
  const recolte = c.type_organe === 'reproducteur' && c.rendement_total > 0
    ? `${c.rendement_total} ${c.unite_rendement || ''}`
    : null

  return (
    <div className="flex items-center gap-2 py-2.5 border-b border-g-brd last:border-0">
      <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
        <span className="text-base font-medium capitalize" style={{ color: 'var(--g-pri)' }}>{c.culture}</span>
        <OrigineBadge origine={c.origine} />
      </div>
      <div className="text-right shrink-0 space-y-0.5">
        <p className="text-base font-semibold" style={{ color: 'var(--g-pri)' }}>
          {c.stock_plants} <span className="font-normal text-sm" style={{ color: 'var(--g-sec)' }}>{c.unite}</span>
        </p>
        {recolte && (
          <p className="text-[12px]" style={{ color: 'var(--g-acc)' }}>↑ {recolte}</p>
        )}
        {c.plants_perdus > 0 && (
          <p className="text-[12px]" style={{ color: 'var(--g-red)' }}>↓ {c.plants_perdus} perdus</p>
        )}
      </div>
    </div>
  )
}

// ── Ligne semis pleine terre ──────────────────────────────────────────────────

function SemisRow({ s }) {
  return (
    <div className="flex items-center gap-2 py-2.5 border-b border-g-brd last:border-0">
      <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
        <span className="text-base font-medium capitalize" style={{ color: 'var(--g-pri)' }}>{s.culture}</span>
        <OrigineBadge origine="semis_pleine_terre" />
      </div>
      <div className="text-right shrink-0">
        <p className="text-base font-semibold" style={{ color: 'var(--g-pri)' }}>
          {s.total_seme} <span className="font-normal text-sm" style={{ color: 'var(--g-sec)' }}>{s.unite}</span>
        </p>
      </div>
    </div>
  )
}

// ── Ligne godet (pépinière disponible) ───────────────────────────────────────

function GodetRow({ g }) {
  const sorties = []
  if (g.nb_plantes      > 0) sorties.push(`${g.nb_plantes} plantés`)
  if (g.nb_vendus       > 0) sorties.push(`${g.nb_vendus} vendus`)
  if (g.nb_pertes_godet > 0) sorties.push(`${g.nb_pertes_godet} perdus`)

  return (
    <div className="flex items-center gap-2 py-2.5 border-b border-g-brd last:border-0">
      <div className="flex-1 min-w-0">
        <span className="text-base font-medium capitalize" style={{ color: 'var(--g-pri)' }}>{g.culture}</span>
        {g.variete && (
          <span className="text-[13px] ml-1.5" style={{ color: 'var(--g-sec)' }}>{g.variete}</span>
        )}
        {sorties.length > 0 && (
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--g-sec)' }}>
            {g.nb_plants_godets} repiqués · {sorties.join(' · ')}
          </p>
        )}
      </div>
      <div className="text-right shrink-0">
        <p className="text-base font-semibold" style={{ color: 'var(--g-acc)' }}>
          {g.stock_residuel_godet ?? g.nb_plants_godets} <span className="font-normal text-sm" style={{ color: 'var(--g-sec)' }}>plants</span>
        </p>
        {g.taux_reussite != null && (
          <p className="text-[12px]" style={{ color: 'var(--g-sec)' }}>{g.taux_reussite}% germination</p>
        )}
      </div>
    </div>
  )
}

// ── Section générique ─────────────────────────────────────────────────────────

function Section({ icon, title, count, titleColor, children }) {
  return (
    <div className="bg-g-card border border-g-brd rounded-2xl p-3.5 mb-3">
      <div className="flex items-center gap-1.5 mb-3">
        {icon}
        <span className="text-sm font-semibold" style={{ color: titleColor }}>{title}</span>
        <span className="text-[12px] ml-auto" style={{ color: 'var(--g-sec)' }}>
          {count} culture{count > 1 ? 's' : ''}
        </span>
      </div>
      <div className="flex text-[12px] pb-1.5 border-b border-g-brd mb-1" style={{ color: 'var(--g-sec)' }}>
        <span className="flex-1">Culture</span>
        <span className="shrink-0">Stock</span>
      </div>
      {children}
    </div>
  )
}

// ── Graphe comparatif ─────────────────────────────────────────────────────────

function Chart({ cultures }) {
  const data = cultures.slice(0, 10).map(c => ({
    name:    c.culture.length > 7 ? c.culture.slice(0, 7) + '…' : c.culture,
    planté:  c.plants_plantes || 0,
    perdu:   c.plants_perdus  || 0,
    récolté: c.type_organe === 'reproducteur' ? (c.nb_recoltes || 0) : 0,
  }))

  if (!data.length) return null

  return (
    <div className="bg-g-card border border-g-brd rounded-2xl p-3.5 mb-3">
      <p className="text-sm font-medium mb-3" style={{ color: 'var(--g-sec)' }}>
        Comparatif semis / récolte / perte
        {cultures.length > 10 && <span className="text-[12px] ml-1" style={{ color: 'var(--g-sec)' }}>(10 premières)</span>}
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
          <XAxis dataKey="name" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} cursor={{ fill: 'var(--g-acc-dim)' }} />
          <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="planté"  fill="var(--g-acc)" radius={[3, 3, 0, 0]} />
          <Bar dataKey="récolté" fill="var(--g-mid)" radius={[3, 3, 0, 0]} />
          <Bar dataKey="perdu"   fill="var(--g-red)" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Stocks({ refresh }) {
  const { dateRef } = useDateRef()
  const [stats, setStats]     = useState(null)
  const [godets, setGodets]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [search, setSearch]   = useState('')  // [CA19] local, non persisté

  async function load() {
    setLoading(true); setError(null)
    try {
      const [s, g] = await Promise.all([api.stats(dateRef), api.godets(dateRef)])
      setStats(s)
      setGodets(g)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh, dateRef])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error)   return <ApiError message={error} onRetry={load} />

  const stocks    = stats?.stock_par_culture  ?? []
  const semis_pt  = stats?.semis_pleine_terre ?? []
  const enAttente = godets?.en_attente        ?? []

  if (!stocks.length && !semis_pt.length && !enAttente.length) return (
    <div className="flex flex-col items-center gap-3 mt-16 text-g-sec">
      <Leaf size={36} />
      <p className="text-base">Aucun stock enregistré.</p>
    </div>
  )

  const q             = search.toLowerCase()
  const filteredStocks = q ? stocks.filter(c  => c.culture.toLowerCase().includes(q)) : stocks
  const filteredSemis  = q ? semis_pt.filter(s => s.culture.toLowerCase().includes(q)) : semis_pt
  const filteredGodets = q ? enAttente.filter(g => g.culture.toLowerCase().includes(q)) : enAttente

  const totalPotager = filteredStocks.reduce((s, c) => s + (c.stock_plants || 0), 0)
  const totalPerdus  = filteredStocks.reduce((s, c) => s + (c.plants_perdus || 0), 0)
  const totalGodets  = filteredGodets.reduce((s, g) => s + (g.stock_residuel_godet || 0), 0)

  return (
    <div>
      {/* [CA13+CA17] Filtres combinés côte à côte */}
      <div className="flex items-center gap-2 mb-3">
        <DateRefPicker />
        <CultureFilter value={search} onChange={setSearch} placeholder="Rechercher une culture…" className="relative flex-1" />
      </div>

      {/* Métriques */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-g-acc-dim border border-g-brd rounded-2xl p-3 text-center">
          <p className="text-3xl font-bold tracking-tight leading-none" style={{ color: 'var(--g-acc)' }}>{totalPotager}</p>
          <p className="text-[11px] mt-1.5" style={{ color: 'var(--g-mid)' }}>au potager</p>
        </div>
        <div className="bg-g-card border border-g-brd rounded-2xl p-3 text-center">
          <p className="text-3xl font-bold tracking-tight leading-none" style={{ color: 'var(--g-mid)' }}>{totalGodets}</p>
          <p className="text-[11px] mt-1.5" style={{ color: 'var(--g-sec)' }}>à replanter</p>
        </div>
        <div className="bg-g-red-dim border border-g-brd rounded-2xl p-3 text-center">
          <p className="text-3xl font-bold tracking-tight leading-none" style={{ color: 'var(--g-red)' }}>{totalPerdus}</p>
          <p className="text-[11px] mt-1.5" style={{ color: 'var(--g-red)' }}>perdus</p>
        </div>
      </div>

      {/* Section 1 — Au potager */}
      {(filteredStocks.length > 0 || filteredSemis.length > 0) && (
        <Section
          icon={<Leaf size={14} style={{ color: 'var(--g-acc)' }} />}
          title="Au potager"
          count={filteredStocks.length + filteredSemis.length}
          titleColor="var(--g-acc)"
        >
          {filteredStocks.map((c, i) => <CultureRow key={i}    c={c} />)}
          {filteredSemis.map((s, i)   => <SemisRow  key={`s${i}`} s={s} />)}
        </Section>
      )}

      {/* Section 2 — En pépinière */}
      {filteredGodets.length > 0 && (
        <Section
          icon={<Sprout size={14} style={{ color: 'var(--g-mid)' }} />}
          title="En pépinière — prêt à replanter"
          count={filteredGodets.length}
          titleColor="var(--g-mid)"
        >
          {filteredGodets.map((g, i) => <GodetRow key={i} g={g} />)}
        </Section>
      )}

      {(filteredStocks.length === 0 && filteredSemis.length === 0 && filteredGodets.length === 0) && search && (
        <p className="text-base text-g-sec text-center mt-8">Aucune culture pour « {search} ».</p>
      )}

      {/* Graphe */}
      <Chart cultures={stocks} />
    </div>
  )
}
