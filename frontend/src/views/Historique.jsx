import { useState, useEffect } from 'react'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

const BADGE = {
  recolte:     'bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300',
  semis:       'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
  plantation:  'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  arrosage:    'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  perte:       'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
}

export default function Historique({ refresh }) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  async function load() {
    setLoading(true); setError(null)
    try   { setData(await api.historique({ limit: 20 })) }
    catch (e) { setError(e.message) }
    finally   { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh])

  if (loading) return <LoadingSkeleton lines={5} />
  if (error)   return <ApiError message={error} onRetry={load} />

  const events = Array.isArray(data) ? data : (data.evenements || [])
  if (!events.length) return <p className="text-sm text-gray-400 text-center mt-8">Aucun événement enregistré.</p>

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
      {/* US-027 — filtres à implémenter */}
      {events.map((e, i) => {
        const badgeCls = BADGE[e.type_action] || 'bg-gray-100 text-gray-600'
        const dateStr  = e.date ? e.date.slice(0, 10) : '?'
        return (
          <div key={i} className="flex items-start gap-3 p-3">
            <span className="text-xs text-gray-400 min-w-[52px] mt-0.5">{dateStr.slice(5)}</span>
            <div className="flex-1 min-w-0">
              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${badgeCls}`}>
                {e.type_action}
              </span>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mt-0.5 capitalize truncate">
                {[e.culture, e.variete].filter(Boolean).join(' · ')}
              </p>
              {e.parcelle && <p className="text-xs text-gray-400">{e.parcelle}</p>}
            </div>
            {e.quantite && (
              <span className="text-xs text-gray-500 shrink-0">
                {e.quantite} {e.unite || ''}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
