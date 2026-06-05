import { useState, useEffect } from 'react'
import { MapPin } from 'lucide-react'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

export default function Plan({ refresh }) {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const d = await api.stats()
      setData(d)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [refresh])

  if (loading) return <LoadingSkeleton lines={3} />
  if (error)   return <ApiError message={error} onRetry={load} />
  if (!data)   return <p className="text-sm text-gray-400 text-center mt-8">Aucune parcelle enregistrée.</p>

  return (
    <div className="space-y-3">
      {/* US-024 — Vue plan complète à implémenter */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-4">
        <div className="flex items-center gap-2 mb-1">
          <MapPin size={14} className="text-primary" />
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Plan des parcelles</span>
        </div>
        <p className="text-xs text-gray-400">Vue complète à implémenter dans US-024</p>
        <p className="text-xs text-gray-500 mt-2">{data.total_evenements} événements en base</p>
      </div>
    </div>
  )
}
