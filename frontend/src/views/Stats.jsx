import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

export default function Stats({ refresh }) {
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

  if (loading) return <LoadingSkeleton lines={3} />
  if (error)   return <ApiError message={error} onRetry={load} />
  if (!data)   return <p className="text-sm text-gray-400 text-center mt-8">Aucune donnée.</p>

  const chartData = (data.stock_par_culture || []).slice(0, 8).map(c => ({
    name: c.culture?.slice(0, 6) || '?',
    plants: c.nb_plants || 0,
  }))

  return (
    <div className="space-y-3">
      {/* Tuiles résumé */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
          <p className="text-2xl font-medium text-primary">{data.total_evenements}</p>
          <p className="text-xs text-gray-400 mt-0.5">Événements total</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
          <p className="text-2xl font-medium text-gray-800 dark:text-gray-200">
            {data.arrosages?.nb || 0}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">Arrosages</p>
        </div>
      </div>

      {/* Graphique stocks par culture */}
      {chartData.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3">Plants par culture</p>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ fontSize: 11, borderRadius: 8 }}
                cursor={{ fill: '#E1F5EE' }}
              />
              <Bar dataKey="plants" fill="#1D9E75" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-gray-400 text-center mt-1">US-028 — graphiques avancés à implémenter</p>
        </div>
      )}
    </div>
  )
}
