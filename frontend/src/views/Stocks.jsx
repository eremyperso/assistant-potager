import { useState, useEffect } from 'react'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

export default function Stocks({ refresh }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  async function load() {
    setLoading(true); setError(null)
    try   { setData(await api.stats()) }
    catch (e) { setError(e.message) }
    finally   { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error)   return <ApiError message={error} onRetry={load} />
  if (!data?.stock_par_culture?.length) return (
    <p className="text-sm text-gray-400 text-center mt-8">Aucun stock enregistré.</p>
  )

  return (
    <div className="space-y-2">
      {/* US-025 — Vue stocks complète à implémenter */}
      <p className="text-xs text-gray-400 text-center mt-2 mb-4">Vue stocks complète — US-025</p>
      {data.stock_par_culture.slice(0, 5).map((c, i) => (
        <div key={i} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100 capitalize">{c.culture}</span>
            <span className="text-xs text-gray-500">{c.nb_plants} plants</span>
          </div>
        </div>
      ))}
    </div>
  )
}
