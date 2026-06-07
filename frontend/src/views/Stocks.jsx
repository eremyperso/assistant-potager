import { useState, useEffect } from 'react'
import { Search, Leaf, Sprout, ShoppingBag } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Badges d'origine ──────────────────────────────────────────────────────────

const ORIGINE_CONFIG = {
  'pépinière':        { label: 'Pépinière',        cls: 'bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200' },
  'pied_acheté':      { label: 'Pied acheté',       cls: 'bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-200' },
  'semis_pleine_terre': { label: 'Semis pleine terre', cls: 'bg-lime-100 text-lime-800 dark:bg-lime-900 dark:text-lime-200' },
}

function OrigineBadge({ origine }) {
  const cfg = ORIGINE_CONFIG[origine]
  if (!cfg) return null
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${cfg.cls}`}>
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
    <div className="flex items-center gap-2 py-2 border-b border-gray-50 dark:border-gray-700 last:border-0">
      <div className="flex-1 min-w-0 flex items-center gap-1.5 flex-wrap">
        <span className="text-[12px] font-medium text-gray-900 dark:text-gray-100 capitalize">{c.culture}</span>
        <OrigineBadge origine={c.origine} />
      </div>
      <div className="text-right shrink-0 space-y-0.5">
        <p className="text-[12px] font-semibold text-gray-800 dark:text-gray-200">
          {c.stock_plants} <span className="font-normal text-gray-400">{c.unite}</span>
        </p>
        {recolte && (
          <p className="text-[10px] text-green-600 dark:text-green-400">↑ {recolte}</p>
        )}
        {c.plants_perdus > 0 && (
          <p className="text-[10px] text-red-400">↓ {c.plants_perdus} perdus</p>
        )}
      </div>
    </div>
  )
}

// ── Ligne semis pleine terre ──────────────────────────────────────────────────

function SemisRow({ s }) {
  return (
    <div className="flex items-center gap-2 py-2 border-b border-gray-50 dark:border-gray-700 last:border-0">
      <div className="flex-1 min-w-0 flex items-center gap-1.5 flex-wrap">
        <span className="text-[12px] font-medium text-gray-900 dark:text-gray-100 capitalize">{s.culture}</span>
        <OrigineBadge origine="semis_pleine_terre" />
      </div>
      <div className="text-right shrink-0">
        <p className="text-[12px] font-semibold text-gray-800 dark:text-gray-200">
          {s.total_seme} <span className="font-normal text-gray-400">{s.unite}</span>
        </p>
      </div>
    </div>
  )
}

// ── Ligne godet (pépinière disponible) ───────────────────────────────────────

function GodetRow({ g }) {
  return (
    <div className="flex items-center gap-2 py-2 border-b border-gray-50 dark:border-gray-700 last:border-0">
      <div className="flex-1 min-w-0">
        <span className="text-[12px] font-medium text-gray-900 dark:text-gray-100 capitalize">{g.culture}</span>
        {g.variete && (
          <span className="text-[10px] text-gray-400 ml-1.5">{g.variete}</span>
        )}
      </div>
      <div className="text-right shrink-0">
        <p className="text-[12px] font-semibold text-teal-600 dark:text-teal-400">
          {g.stock_residuel_godet} <span className="font-normal text-gray-400">plants</span>
        </p>
        {g.taux_reussite != null && (
          <p className="text-[10px] text-gray-400">{g.taux_reussite}% germination</p>
        )}
      </div>
    </div>
  )
}

// ── Section générique ─────────────────────────────────────────────────────────

function Section({ icon, title, count, colorCls, children }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3 mb-3">
      <div className="flex items-center gap-1.5 mb-2">
        {icon}
        <span className={`text-xs font-semibold ${colorCls}`}>{title}</span>
        <span className="text-[10px] text-gray-400 ml-auto">{count} culture{count > 1 ? 's' : ''}</span>
      </div>
      <div className="flex text-[10px] text-gray-400 pb-1 border-b border-gray-100 dark:border-gray-700 mb-1">
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
    name: c.culture.length > 7 ? c.culture.slice(0, 7) + '…' : c.culture,
    planté:  c.plants_plantes || 0,
    perdu:   c.plants_perdus  || 0,
    récolté: c.type_organe === 'reproducteur' ? (c.nb_recoltes || 0) : 0,
  }))

  if (!data.length) return null

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3 mb-3">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3">
        Comparatif semis / récolte / perte
        {cultures.length > 10 && <span className="text-[10px] text-gray-400 ml-1">(10 premières)</span>}
      </p>
      <ResponsiveContainer width="100%" height={150}>
        <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
          <XAxis dataKey="name" tick={{ fontSize: 9 }} />
          <YAxis tick={{ fontSize: 9 }} />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} cursor={{ fill: '#E1F5EE' }} />
          <Legend iconSize={8} wrapperStyle={{ fontSize: 10 }} />
          <Bar dataKey="planté"  fill="#1D9E75" radius={[3,3,0,0]} />
          <Bar dataKey="récolté" fill="#60B4E0" radius={[3,3,0,0]} />
          <Bar dataKey="perdu"   fill="#F87171" radius={[3,3,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Stocks({ refresh }) {
  const [stats, setStats]     = useState(null)
  const [godets, setGodets]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [search, setSearch]   = useState('')

  async function load() {
    setLoading(true); setError(null)
    try {
      const [s, g] = await Promise.all([api.stats(), api.godets()])
      setStats(s)
      setGodets(g)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error)   return <ApiError message={error} onRetry={load} />

  const stocks       = stats?.stock_par_culture   ?? []
  const semis_pt     = stats?.semis_pleine_terre  ?? []
  const enAttente    = godets?.en_attente         ?? []

  if (!stocks.length && !semis_pt.length && !enAttente.length) return (
    <div className="flex flex-col items-center gap-3 mt-16 text-gray-400">
      <Leaf size={36} />
      <p className="text-sm">Aucun stock enregistré.</p>
    </div>
  )

  const q            = search.toLowerCase()
  const filteredStocks  = q ? stocks.filter(c => c.culture.toLowerCase().includes(q)) : stocks
  const filteredSemis   = q ? semis_pt.filter(s => s.culture.toLowerCase().includes(q)) : semis_pt
  const filteredGodets  = q ? enAttente.filter(g => g.culture.toLowerCase().includes(q)) : enAttente

  const totalPotager = filteredStocks.reduce((s, c) => s + (c.stock_plants || 0), 0)
  const totalPerdus  = filteredStocks.reduce((s, c) => s + (c.plants_perdus || 0), 0)
  const totalGodets  = filteredGodets.reduce((s, g) => s + (g.stock_residuel_godet || 0), 0)

  return (
    <div>
      {/* Résumé */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-primary-light dark:bg-green-950 rounded-xl p-2 text-center">
          <p className="text-xl font-semibold text-primary">{totalPotager}</p>
          <p className="text-[10px] text-primary-dark dark:text-green-400">au potager</p>
        </div>
        <div className="bg-teal-50 dark:bg-teal-950 rounded-xl p-2 text-center border border-teal-100 dark:border-teal-900">
          <p className="text-xl font-semibold text-teal-600 dark:text-teal-400">{totalGodets}</p>
          <p className="text-[10px] text-teal-600 dark:text-teal-400">à replanter</p>
        </div>
        <div className="bg-red-50 dark:bg-red-950 rounded-xl p-2 text-center border border-red-100 dark:border-red-900">
          <p className="text-xl font-semibold text-red-500">{totalPerdus}</p>
          <p className="text-[10px] text-red-400">perdus</p>
        </div>
      </div>

      {/* Filtre */}
      <div className="relative mb-3">
        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Rechercher une culture…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-8 pr-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      {/* Section 1 — Au potager */}
      {(filteredStocks.length > 0 || filteredSemis.length > 0) && (
        <Section
          icon={<Leaf size={13} className="text-green-600 dark:text-green-400" />}
          title="Au potager"
          count={filteredStocks.length + filteredSemis.length}
          colorCls="text-green-700 dark:text-green-400"
        >
          {filteredStocks.map((c, i) => <CultureRow key={i} c={c} />)}
          {filteredSemis.map((s, i)  => <SemisRow   key={`s${i}`} s={s} />)}
        </Section>
      )}

      {/* Section 2 — En pépinière (prêt à replanter) */}
      {filteredGodets.length > 0 && (
        <Section
          icon={<Sprout size={13} className="text-teal-600 dark:text-teal-400" />}
          title="En pépinière — prêt à replanter"
          count={filteredGodets.length}
          colorCls="text-teal-700 dark:text-teal-400"
        >
          {filteredGodets.map((g, i) => <GodetRow key={i} g={g} />)}
        </Section>
      )}

      {(filteredStocks.length === 0 && filteredSemis.length === 0 && filteredGodets.length === 0) && search && (
        <p className="text-sm text-gray-400 text-center mt-8">Aucune culture pour "{search}".</p>
      )}

      {/* Graphe */}
      <Chart cultures={stocks} />
    </div>
  )
}
