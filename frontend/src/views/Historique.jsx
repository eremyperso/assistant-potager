import { useState, useEffect, useRef } from 'react'
import { Search, Calendar, ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Palette badges action ─────────────────────────────────────────────────────

const BADGE = {
  recolte:       { bg: 'var(--g-acc-dim)', text: 'var(--g-acc)'  },
  semis:         { bg: 'var(--g-amb-dim)', text: 'var(--g-amb)'  },
  plantation:    { bg: 'var(--g-acc-dim)', text: 'var(--g-mid)'  },
  arrosage:      { bg: '#DBEAFE',          text: '#1D4ED8'        },
  perte:         { bg: 'var(--g-red-dim)', text: 'var(--g-red)'  },
  desherbage:    { bg: 'var(--g-brd)',     text: 'var(--g-sec)'  },
  mise_en_godet: { bg: 'var(--g-amb-dim)', text: 'var(--g-mid)'  },
}
const BADGE_DARK = {
  arrosage: { bg: '#1E3A5F', text: '#60A5FA' },
}

const CHIPS = [
  { label: 'Tous',       value: null           },
  { label: 'Récolte',    value: 'recolte'      },
  { label: 'Semis',      value: 'semis'        },
  { label: 'Plantation', value: 'plantation'   },
  { label: 'Arrosage',   value: 'arrosage'     },
  { label: 'Perte',      value: 'perte'        },
  { label: 'Godet',      value: 'mise_en_godet'},
]

const PAGE_SIZE = 20

// ── Ligne événement ───────────────────────────────────────────────────────────

function EventRow({ e }) {
  const badge  = BADGE[e.type_action] || { bg: 'var(--g-brd)', text: 'var(--g-sec)' }
  const dateStr = e.date ? e.date.slice(5) : '?'  // MM-DD

  return (
    <div className="flex items-start gap-3 p-3.5 border-b border-g-brd last:border-0">
      <span className="text-[13px] min-w-[42px] mt-0.5 shrink-0 tabular-nums" style={{ color: 'var(--g-sec)' }}>
        {dateStr}
      </span>
      <div className="flex-1 min-w-0">
        <span
          className="text-[11px] font-medium px-2 py-0.5 rounded-full inline-block"
          style={{ background: badge.bg, color: badge.text }}
        >
          {e.type_action?.replace('_', ' ')}
        </span>
        <p className="text-base font-medium mt-0.5 capitalize truncate" style={{ color: 'var(--g-pri)' }}>
          {[e.culture, e.variete].filter(Boolean).join(' · ')}
        </p>
        {e.parcelle && <p className="text-[13px]" style={{ color: 'var(--g-sec)' }}>{e.parcelle}</p>}
      </div>
      {e.quantite != null && (
        <span className="text-sm shrink-0 mt-0.5 tabular-nums" style={{ color: 'var(--g-mid)' }}>
          {e.quantite} {e.unite || ''}
        </span>
      )}
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Historique({ refresh }) {
  const { dateRef } = useDateRef()
  const [data, setData]           = useState({ total: 0, evenements: [] })
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [actionFilter, setAction] = useState(null)
  const [cultureFilter, setCulture] = useState('')
  const [fromDate, setFrom]       = useState('')
  const [toDate, setTo]           = useState('')
  const [page, setPage]           = useState(0)
  const [showDates, setShowDates] = useState(false)

  async function load(pg = page) {
    setLoading(true); setError(null)
    try {
      const params = { limit: PAGE_SIZE, offset: pg * PAGE_SIZE }
      if (actionFilter) params.action   = actionFilter
      if (fromDate)     params.from     = fromDate
      if (dateRef)      params.date_ref = dateRef
      else if (toDate)  params.to       = toDate
      setData(await api.historique(params))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { setPage(0); load(0) }, [refresh, actionFilter, fromDate, toDate, dateRef])
  useEffect(() => { load(page) }, [page])

  const evenements = data.evenements || []
  const total      = data.total || 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const q = cultureFilter.toLowerCase()
  const filtered = q
    ? evenements.filter(e => (e.culture || '').toLowerCase().includes(q) || (e.variete || '').toLowerCase().includes(q))
    : evenements

  return (
    <div>
      {/* [CA15] Sélecteur date de référence */}
      <DateRefPicker className="flex items-center gap-1.5 mb-3" />

      {/* Chips filtre action */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3">
        {CHIPS.map(chip => {
          const active = actionFilter === chip.value
          return (
            <button
              key={chip.label}
              onClick={() => setAction(chip.value)}
              className="shrink-0 text-sm font-medium px-3.5 py-1.5 rounded-full border transition-colors"
              style={active
                ? { background: 'var(--g-acc)', color: 'var(--g-bg)', borderColor: 'var(--g-acc)' }
                : { background: 'var(--g-card)', color: 'var(--g-sec)', borderColor: 'var(--g-brd)' }
              }
            >
              {chip.label}
            </button>
          )
        })}
      </div>

      {/* Filtre culture + bouton période */}
      <div className="flex gap-2 mb-2">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--g-sec)' }} />
          <input
            type="text"
            placeholder="Filtrer par culture…"
            value={cultureFilter}
            onChange={e => setCulture(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm rounded-xl border border-g-brd bg-g-card focus:outline-none focus:ring-1 focus:ring-g-acc"
            style={{ color: 'var(--g-pri)' }}
          />
        </div>
        <button
          onClick={() => setShowDates(v => !v)}
          className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-xl border transition-colors"
          style={showDates || fromDate || toDate
            ? { background: 'var(--g-acc)', color: 'var(--g-bg)', borderColor: 'var(--g-acc)' }
            : { background: 'var(--g-card)', color: 'var(--g-sec)', borderColor: 'var(--g-brd)' }
          }
        >
          <Calendar size={14} />
          Période
        </button>
      </div>

      {/* Sélecteur dates */}
      {showDates && (
        <div className="flex gap-2 mb-3">
          <input
            type="date"
            value={fromDate}
            onChange={e => { setFrom(e.target.value); setPage(0) }}
            className="flex-1 px-2.5 py-2 text-sm rounded-xl border border-g-brd bg-g-card focus:outline-none focus:ring-1 focus:ring-g-acc"
            style={{ color: 'var(--g-pri)' }}
          />
          <span className="text-sm self-center" style={{ color: 'var(--g-sec)' }}>→</span>
          <input
            type="date"
            value={toDate}
            onChange={e => { setTo(e.target.value); setPage(0) }}
            className="flex-1 px-2.5 py-2 text-sm rounded-xl border border-g-brd bg-g-card focus:outline-none focus:ring-1 focus:ring-g-acc"
            style={{ color: 'var(--g-pri)' }}
          />
          {(fromDate || toDate) && (
            <button
              onClick={() => { setFrom(''); setTo(''); setPage(0) }}
              className="text-sm px-1"
              style={{ color: 'var(--g-red)' }}
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
        <div className="flex flex-col items-center gap-3 mt-12 text-g-sec">
          <Clock size={36} />
          <p className="text-base">Aucun événement enregistré.</p>
        </div>
      ) : (
        <div className="bg-g-card border border-g-brd rounded-2xl">
          {filtered.map((e, i) => <EventRow key={e.id ?? i} e={e} />)}
        </div>
      )}

      {/* Pagination */}
      {!loading && !error && totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 px-1">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="p-2 rounded-xl border border-g-brd disabled:opacity-30"
            style={{ color: 'var(--g-sec)' }}
          >
            <ChevronLeft size={18} />
          </button>
          <span className="text-sm" style={{ color: 'var(--g-sec)' }}>
            Page {page + 1} / {totalPages}
            <span className="ml-1 text-[12px]">({total} événements)</span>
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="p-2 rounded-xl border border-g-brd disabled:opacity-30"
            style={{ color: 'var(--g-sec)' }}
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}
    </div>
  )
}
