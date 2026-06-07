import { useState, useEffect } from 'react'
import { Search, Leaf, Sprout } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Helpers ──────────────────────────────────────────────────────────────────

const BADGE_CLS = {
  'végétatif':    'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  'reproducteur': 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
}

function TypeBadge({ type }) {
  if (!type || type === 'inconnu') return null
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${BADGE_CLS[type] || 'bg-gray-100 text-gray-500'}`}>
      {type}
    </span>
  )
}

function fmt(n, unite) {
  if (!n) return '—'
  return `${n} ${unite || ''}`.trim()
}

// ── Ligne culture ─────────────────────────────────────────────────────────────

function CultureRow({ c }) {
  const recolte = c.type_organe === 'reproducteur' && c.rendement_total > 0
    ? `${c.rendement_total} ${c.unite_rendement || ''}`
    : null

  return (
    <div className="flex items-center gap-2 py-2 border-b border-gray-50 dark:border-gray-700 last:border-0">
      <div className="flex-1 min-w-0">
        <span className="text-[12px] font-medium text-gray-900 dark:text-gray-100 capitalize">{c.culture}</span>
        <TypeBadge type={c.type_organe} />
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

// ── Section cultures ──────────────────────────────────────────────────────────

function Section({ title, cultures, colorCls }) {
  if (!cultures.length) return null
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3 mb-3">
      <div className="flex items-center gap-1.5 mb-2">
        <span className={`text-xs font-semibold ${colorCls}`}>{title}</span>
        <span className="text-[10px] text-gray-400 ml-auto">{cultures.length} cultures</span>
      </div>
      {/* En-tête colonnes */}
      <div className="flex text-[10px] text-gray-400 pb-1 border-b border-gray-100 dark:border-gray-700 mb-1">
        <span className="flex-1">Culture</span>
        <span className="shrink-0">Plants · Récolté · Perdu</span>
      </div>
      {cultures.map((c, i) => <CultureRow key={i} c={c} />)}
    </div>
  )
}

// ── Semis pleine terre ────────────────────────────────────────────────────────

function SemisPleineTerrSection({ semis, search }) {
  const filtered = search
    ? semis.filter(s => s.culture.toLowerCase().includes(search))
    : semis
  if (!filtered.length) return null

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3 mb-3">
      <div className="flex items-center gap-1.5 mb-2">
        <Sprout size={13} className="text-teal-600 dark:text-teal-400" />
        <span className="text-xs font-semibold text-teal-700 dark:text-teal-400">Semis en pleine terre</span>
        <span className="text-[10px] text-gray-400 ml-auto">{filtered.length} culture{filtered.length > 1 ? 's' : ''}</span>
      </div>
      <div className="flex text-[10px] text-gray-400 pb-1 border-b border-gray-100 dark:border-gray-700 mb-1">
        <span className="flex-1">Culture</span>
        <span className="shrink-0">Quantité · Parcelle</span>
      </div>
      {filtered.map((s, i) => (
        <div key={i} className="flex items-center gap-2 py-2 border-b border-gray-50 dark:border-gray-700 last:border-0">
          <div className="flex-1 min-w-0">
            <span className="text-[12px] font-medium text-gray-900 dark:text-gray-100 capitalize">{s.culture}</span>
            <TypeBadge type={s.type_organe} />
          </div>
          <div className="text-right shrink-0 space-y-0.5">
            <p className="text-[12px] font-semibold text-gray-800 dark:text-gray-200">
              {s.total_seme} <span className="font-normal text-gray-400">{s.unite}</span>
            </p>
            <p className="text-[10px] text-teal-600 dark:text-teal-400 capitalize">
              {s.parcelles.join(', ')}
            </p>
          </div>
        </div>
      ))}
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
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [search, setSearch]   = useState('')

  async function load() {
    setLoading(true); setError(null)
    try   { setData(await api.stats()) }
    catch (e) { setError(e.message) }
    finally   { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error)   return <ApiError message={error} onRetry={load} />

  const stocks = data?.stock_par_culture || []

  if (!stocks.length) return (
    <div className="flex flex-col items-center gap-3 mt-16 text-gray-400">
      <Leaf size={36} />
      <p className="text-sm">Aucun stock enregistré.</p>
    </div>
  )

  const q = search.toLowerCase()
  const filtered = q ? stocks.filter(c => c.culture.toLowerCase().includes(q)) : stocks

  const vegetatifs    = filtered.filter(c => c.type_organe === 'végétatif')
  const reproducteurs = filtered.filter(c => c.type_organe === 'reproducteur')
  const autres        = filtered.filter(c => c.type_organe !== 'végétatif' && c.type_organe !== 'reproducteur')

  return (
    <div>
      {/* Résumé */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-primary-light dark:bg-green-950 rounded-xl p-2 text-center">
          <p className="text-xl font-semibold text-primary">{stocks.length}</p>
          <p className="text-[10px] text-primary-dark dark:text-green-400">cultures</p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-2 text-center border border-gray-100 dark:border-gray-700">
          <p className="text-xl font-semibold text-gray-800 dark:text-gray-200">
            {stocks.reduce((s, c) => s + (c.stock_plants || 0), 0)}
          </p>
          <p className="text-[10px] text-gray-400">plants actifs</p>
        </div>
        <div className="bg-red-50 dark:bg-red-950 rounded-xl p-2 text-center border border-red-100 dark:border-red-900">
          <p className="text-xl font-semibold text-red-500">
            {stocks.reduce((s, c) => s + (c.plants_perdus || 0), 0)}
          </p>
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

      {/* Sections plantations */}
      <Section
        title="🥬 Cultures végétatives"
        cultures={vegetatifs}
        colorCls="text-green-700 dark:text-green-400"
      />
      <Section
        title="🍅 Cultures reproductrices"
        cultures={reproducteurs}
        colorCls="text-orange-600 dark:text-orange-400"
      />
      {autres.length > 0 && (
        <Section
          title="🌱 Autres"
          cultures={autres}
          colorCls="text-gray-600 dark:text-gray-400"
        />
      )}

      {filtered.length === 0 && search && (
        <p className="text-sm text-gray-400 text-center mt-8">Aucune culture pour "{search}".</p>
      )}

      {/* Semis pleine terre */}
      <SemisPleineTerrSection semis={data?.semis_pleine_terre ?? []} search={q} />

      {/* Graphe */}
      <Chart cultures={stocks} />
    </div>
  )
}
