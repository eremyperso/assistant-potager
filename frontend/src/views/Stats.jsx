import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

export default function Stats({ refresh }) {
  const { dateRef } = useDateRef()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  async function load() {
    setLoading(true); setError(null)
    try   { setData(await api.stats(dateRef)) }
    catch (e) { setError(e.message) }
    finally   { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh, dateRef])

  if (loading) return <LoadingSkeleton lines={3} />
  if (error)   return <ApiError message={error} onRetry={load} />
  if (!data)   return <p className="text-base text-g-sec text-center mt-8">Aucune donnée.</p>

  const chartData = (data.stock_par_culture || []).slice(0, 8).map(c => ({
    name:   c.culture?.slice(0, 6) || '?',
    plants: c.nb_plants || 0,
  }))

  return (
    <div className="space-y-3">
      {/* [CA16] Sélecteur date */}
      <DateRefPicker className="flex items-center gap-1.5 mb-1" />

      {/* Tuiles résumé */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-g-card border border-g-brd rounded-2xl p-4">
          <p className="text-4xl font-bold tracking-tight leading-none" style={{ color: 'var(--g-acc)' }}>
            {data.total_evenements}
          </p>
          <p className="text-[13px] mt-2" style={{ color: 'var(--g-sec)' }}>Événements total</p>
        </div>
        <div className="bg-g-card border border-g-brd rounded-2xl p-4">
          <p className="text-4xl font-bold tracking-tight leading-none" style={{ color: 'var(--g-pri)' }}>
            {data.arrosages?.nb || 0}
          </p>
          <p className="text-[13px] mt-2" style={{ color: 'var(--g-sec)' }}>Arrosages</p>
        </div>
      </div>

      {/* Graphique stocks par culture */}
      {chartData.length > 0 && (
        <div className="bg-g-card border border-g-brd rounded-2xl p-4">
          <p className="text-sm font-medium mb-3" style={{ color: 'var(--g-sec)' }}>Plants par culture</p>
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 10 }}
                cursor={{ fill: 'var(--g-acc-dim)' }}
              />
              <Bar dataKey="plants" fill="var(--g-acc)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-[12px] text-center mt-1" style={{ color: 'var(--g-sec)' }}>
            US-028 — graphiques avancés à implémenter
          </p>
        </div>
      )}
    </div>
  )
}
