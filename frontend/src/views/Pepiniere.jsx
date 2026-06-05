import { useState, useEffect } from 'react'
import { Sprout } from 'lucide-react'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

export default function Pepiniere({ refresh }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  async function load() {
    setLoading(true); setError(null)
    try   { setData(await api.godets()) }
    catch (e) { setError(e.message) }
    finally   { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh])

  if (loading) return <LoadingSkeleton lines={3} />
  if (error)   return <ApiError message={error} onRetry={load} />
  if (!data?.length) return (
    <div className="flex flex-col items-center gap-2 mt-12 text-gray-400">
      <Sprout size={32} />
      <p className="text-sm">Aucun godet en pépinière.</p>
    </div>
  )

  return (
    <div className="space-y-2">
      {/* US-026 — Vue pépinière complète à implémenter */}
      <p className="text-xs text-gray-400 text-center mt-2 mb-4">Vue pépinière complète — US-026</p>
      {data.map((g, i) => (
        <div key={i} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100 capitalize">{g.culture}</span>
            <span className="text-xs bg-primary-light text-primary-dark px-2 py-0.5 rounded-full font-medium">
              {g.stock_residuel_godet} restants
            </span>
          </div>
          {g.variete && <p className="text-xs text-gray-400 mt-0.5">{g.variete}</p>}
        </div>
      ))}
    </div>
  )
}
