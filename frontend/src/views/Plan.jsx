import { useState, useEffect } from 'react'
import { MapPin, Sun, Cloud, Leaf } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import CultureFilter from '../components/CultureFilter.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Helpers ──────────────────────────────────────────────────────────────────

const BADGE = {
  'végétatif':    'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  'reproducteur': 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
}

const DOT = {
  'végétatif':    'bg-green-500',
  'reproducteur': 'bg-orange-400',
}

function ExpositionIcon({ exposition }) {
  if (!exposition) return null
  const e = (exposition || '').toLowerCase()
  const Icon = e.includes('ombre') ? Cloud : Sun
  return <Icon size={12} className="text-amber-500" aria-hidden="true" />
}

function Badge({ type }) {
  if (!type) return null
  const cls = BADGE[type] || 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${cls}`}>
      {type}
    </span>
  )
}

function ProgressBar({ pct }) {
  if (pct === null || pct === undefined) return null
  const color = pct >= 80 ? 'bg-orange-400' : 'bg-primary'
  return (
    <div className="mt-2">
      <div className="h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[10px] text-gray-400 mt-1">{pct}% occupée</p>
    </div>
  )
}

// ── Carte parcelle ────────────────────────────────────────────────────────────

function ParcellCard({ parcelle }) {
  const { nom, exposition, superficie_m2, cultures, occupation_pct } = parcelle
  const libre = cultures.length === 0

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-4 mb-3">
      {/* En-tête */}
      <div className="flex items-start justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <MapPin size={14} className={libre ? 'text-gray-300' : 'text-primary'} aria-hidden="true" />
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{nom}</span>
        </div>
        {libre && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400">
            Libre
          </span>
        )}
      </div>

      {/* Méta */}
      {(exposition || superficie_m2) && (
        <div className="flex items-center gap-3 mb-3 text-[11px] text-gray-400">
          {exposition && (
            <span className="flex items-center gap-1">
              <ExpositionIcon exposition={exposition} />
              {exposition}
            </span>
          )}
          {superficie_m2 && <span>{superficie_m2} m²</span>}
        </div>
      )}

      {/* Cultures */}
      {!libre && (
        <div className="space-y-1.5">
          {cultures.map((c, i) => (
            <div key={i} className="flex items-center gap-2 py-1.5 border-b border-gray-50 dark:border-gray-700 last:border-0">
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${DOT[c.type_organe] || 'bg-gray-300'}`} />
              <div className="flex-1 min-w-0">
                <span className="text-[12px] font-medium text-gray-900 dark:text-gray-100 capitalize">
                  {c.culture}
                </span>
                {c.variete && (
                  <span className="text-[11px] text-gray-400 ml-1.5">{c.variete}</span>
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {c.nb_plants > 0 && (
                  <span className="text-[11px] text-gray-500">{c.nb_plants} plants</span>
                )}
                <Badge type={c.type_organe} />
              </div>
            </div>
          ))}
        </div>
      )}

      <ProgressBar pct={occupation_pct} />
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Plan({ refresh }) {
  const { dateRef } = useDateRef()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [search, setSearch]   = useState('')  // [CA17-CA19] filtre local, non persisté

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.plan(dateRef))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // [CA11] Recharge quand refresh ou dateRef change
  useEffect(() => { load() }, [refresh, dateRef])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error)   return <ApiError message={error} onRetry={load} />

  const parcelles = data?.parcelles ?? []
  const q = search.toLowerCase()

  // [CA18] Filtre côté client : parcelles dont au moins une culture match OU le nom de parcelle
  const filtered = q
    ? parcelles.map(p => ({
        ...p,
        cultures: p.cultures.filter(c =>
          (c.culture || '').toLowerCase().includes(q) ||
          (c.variete || '').toLowerCase().includes(q)
        ),
      })).filter(p => p.nom.toLowerCase().includes(q) || p.cultures.length > 0)
    : parcelles

  if (!filtered.length && !loading) {
    return (
      <>
        <div className="flex items-center gap-2 mb-3">
          <DateRefPicker className="flex items-center gap-1.5" />
          <CultureFilter value={search} onChange={setSearch} className="relative flex-1" />
        </div>
        <div className="flex flex-col items-center gap-3 mt-12 text-gray-400">
          <Leaf size={36} />
          <p className="text-sm">{search ? 'Aucune culture correspondante.' : 'Aucune parcelle enregistrée.'}</p>
          {!search && (
            <p className="text-xs text-center">
              Ajoutez une parcelle depuis le bot avec<br />
              <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">/parcelle ajouter nom</code>
            </p>
          )}
        </div>
      </>
    )
  }

  const nbActives  = filtered.filter(p => p.cultures.length > 0).length
  const nbCultures = filtered.reduce((s, p) => s + p.cultures.length, 0)

  return (
    <div>
      {/* [CA5+CA17] Filtres combinés côte à côte */}
      <div className="flex items-center gap-2 mb-3">
        <DateRefPicker className="flex items-center gap-1.5" />
        <CultureFilter value={search} onChange={setSearch} className="relative flex-1" />
      </div>

      {/* Résumé */}
      <div className="flex gap-2 mb-3">
        <div className="flex-1 bg-primary-light dark:bg-green-950 rounded-xl p-3 text-center">
          <p className="text-xl font-semibold text-primary">{nbActives}</p>
          <p className="text-[10px] text-primary-dark dark:text-green-400">parcelles actives</p>
        </div>
        <div className="flex-1 bg-gray-50 dark:bg-gray-800 rounded-xl p-3 text-center border border-gray-100 dark:border-gray-700">
          <p className="text-xl font-semibold text-gray-800 dark:text-gray-200">{nbCultures}</p>
          <p className="text-[10px] text-gray-400">cultures en place</p>
        </div>
      </div>

      {/* Légende */}
      <div className="flex gap-3 mb-3 text-[10px] text-gray-400">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500 inline-block" />végétatif</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-400 inline-block" />reproducteur</span>
      </div>

      {/* Cartes */}
      {filtered.map((p, i) => <ParcellCard key={i} parcelle={p} />)}
    </div>
  )
}
