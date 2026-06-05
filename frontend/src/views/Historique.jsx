import { useState, useEffect, useRef } from 'react'
import { Search, Calendar, ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Palette badges action (CA6) ───────────────────────────────────────────────

const BADGE = {
  recolte:        'bg-teal-100  text-teal-700  dark:bg-teal-900  dark:text-teal-300',
  semis:          'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
  plantation:     'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  arrosage:       'bg-blue-100  text-blue-700  dark:bg-blue-900  dark:text-blue-300',
  perte:          'bg-red-100   text-red-700   dark:bg-red-900   dark:text-red-300',
  desherbage:     'bg-gray-100  text-gray-600  dark:bg-gray-700  dark:text-gray-400',
  mise_en_godet:  'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
}

const CHIPS = [
  { label: 'Tous',      value: null },
  { label: 'Récolte',   value: 'recolte' },
  { label: 'Semis',     value: 'semis' },
  { label: 'Plantation',value: 'plantation' },
  { label: 'Arrosage',  value: 'arrosage' },
  { label: 'Perte',     value: 'perte' },
  { label: 'Godet',     value: 'mise_en_godet' },
]

const PAGE_SIZE = 20

// ── Ligne événement ───────────────────────────────────────────────────────────

function EventRow({ e }) {
  const badgeCls = BADGE[e.type_action] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
  const dateStr  = e.date ? e.date.slice(5) : '?'    // MM-DD

  return (
    <div className="flex items-start gap-3 p-3 border-b border-gray-50 dark:border-gray-700 last:border-0">
      <span className="text-xs text-gray-400 min-w-[38px] mt-0.5 shrink-0">{dateStr}</span>
      <div className="flex-1 min-w-0">
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${badgeCls}`}>
          {e.type_action?.replace('_', ' ')}
        </span>
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mt-0.5 capitalize truncate">
          {[e.culture, e.variete].filter(Boolean).join(' · ')}
        </p>
        {e.parcelle && <p className="text-[11px] text-gray-400">{e.parcelle}</p>}
      </div>
      {e.quantite != null && (
        <span className="text-xs text-gray-500 shrink-0 mt-0.5">
          {e.quantite} {e.unite || ''}
        </span>
      )}
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Historique({ refresh }) {
  const [data, setData]         = useState({ total: 0, evenements: [] })
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [actionFilter, setAction] = useState(null)
  const [cultureFilter, setCulture] = useState('')
  const [fromDate, setFrom]     = useState('')
  const [toDate, setTo]         = useState('')
  const [page, setPage]         = useState(0)
  const [showDates, setShowDates] = useState(false)
  const debounceRef = useRef(null)

  async function load(pg = page) {
    setLoading(true); setError(null)
    try {
      const params = { limit: PAGE_SIZE, offset: pg * PAGE_SIZE }
      if (actionFilter) params.action = actionFilter
      if (fromDate)     params.from   = fromDate
      if (toDate)       params.to     = toDate
      setData(await api.historique(params))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Rechargement côté serveur quand les filtres serveur changent
  useEffect(() => {
    setPage(0)
    load(0)
  }, [refresh, actionFilter, fromDate, toDate])

  useEffect(() => { load(page) }, [page])

  function handleCultureChange(val) {
    setCulture(val)
  }

  const evenements = data.evenements || []
  const total      = data.total || 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  // Filtre culture côté client sur les données chargées
  const q = cultureFilter.toLowerCase()
  const filtered = q
    ? evenements.filter(e => (e.culture || '').toLowerCase().includes(q) || (e.variete || '').toLowerCase().includes(q))
    : evenements

  return (
    <div>
      {/* Chips filtre action (CA4) */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-2 scrollbar-hide">
        {CHIPS.map(chip => {
          const active = actionFilter === chip.value
          return (
            <button
              key={chip.label}
              onClick={() => setAction(chip.value)}
              className={`shrink-0 text-[11px] font-medium px-3 py-1.5 rounded-full border transition-colors ${
                active
                  ? 'bg-primary text-white border-primary'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700'
              }`}
            >
              {chip.label}
            </button>
          )
        })}
      </div>

      {/* Filtre culture + bouton période */}
      <div className="flex gap-2 mb-2">
        <div className="relative flex-1">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Filtrer par culture…"
            value={cultureFilter}
            onChange={e => handleCultureChange(e.target.value)}
            className="w-full pl-7 pr-3 py-1.5 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <button
          onClick={() => setShowDates(v => !v)}
          className={`flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${
            showDates || fromDate || toDate
              ? 'bg-primary text-white border-primary'
              : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-700'
          }`}
        >
          <Calendar size={13} />
          Période
        </button>
      </div>

      {/* Sélecteur dates (CA5) */}
      {showDates && (
        <div className="flex gap-2 mb-2">
          <input
            type="date"
            value={fromDate}
            onChange={e => { setFrom(e.target.value); setPage(0) }}
            className="flex-1 px-2 py-1.5 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <span className="text-xs text-gray-400 self-center">→</span>
          <input
            type="date"
            value={toDate}
            onChange={e => { setTo(e.target.value); setPage(0) }}
            className="flex-1 px-2 py-1.5 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-primary"
          />
          {(fromDate || toDate) && (
            <button
              onClick={() => { setFrom(''); setTo(''); setPage(0) }}
              className="text-xs text-red-400 px-1"
            >✕</button>
          )}
        </div>
      )}

      {/* Liste événements */}
      {loading ? (
        <LoadingSkeleton lines={6} />
      ) : error ? (
        <ApiError message={error} onRetry={() => load(page)} />
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-3 mt-12 text-gray-400">
          <Clock size={32} />
          <p className="text-sm">Aucun événement enregistré.</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700">
          {filtered.map((e, i) => <EventRow key={e.id ?? i} e={e} />)}
        </div>
      )}

      {/* Pagination (CA2) */}
      {!loading && !error && totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 px-1">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="p-2 rounded-lg border border-gray-200 dark:border-gray-700 disabled:opacity-30 text-gray-600 dark:text-gray-400"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-xs text-gray-500">
            Page {page + 1} / {totalPages}
            <span className="text-gray-400 ml-1">({total} événements)</span>
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="p-2 rounded-lg border border-gray-200 dark:border-gray-700 disabled:opacity-30 text-gray-600 dark:text-gray-400"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
