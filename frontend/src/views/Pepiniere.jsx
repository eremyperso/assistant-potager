import { useState, useEffect } from 'react'
import { Sprout, CheckCircle, RefreshCw } from 'lucide-react'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Helpers ───────────────────────────────────────────────────────────────────

function tauxColor(taux) {
  if (taux == null) return 'text-gray-400'
  if (taux >= 80)   return 'text-green-500'
  if (taux >= 50)   return 'text-orange-500'
  return 'text-red-500'
}

function ProgressBar({ value, max }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  return (
    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-2">
      <div
        className="h-1.5 rounded-full bg-teal-500 transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ── Tuile résumé ──────────────────────────────────────────────────────────────

function MetricTile({ label, value, sub }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
      <p className="text-2xl font-semibold text-primary">{value}</p>
      <p className="text-xs text-gray-400 mt-0.5">{label}</p>
      {sub && <p className="text-[10px] text-gray-300 mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Carte godet ───────────────────────────────────────────────────────────────

function GodotCard({ g }) {
  const taux   = g.taux_reussite
  const stock  = g.stock_residuel_godet
  const total  = g.nb_plants_godets

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3">
      {/* En-tête */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 capitalize">
            {g.culture}
          </p>
          {g.variete && (
            <p className="text-xs text-gray-400">{g.variete}</p>
          )}
        </div>
        {/* Grand chiffre taux — CA3 */}
        {taux != null ? (
          <span className={`text-2xl font-bold shrink-0 ${tauxColor(taux)}`}>
            {taux}%
          </span>
        ) : (
          <span className="text-2xl font-bold text-gray-300 shrink-0">—</span>
        )}
      </div>

      {/* Détails stock */}
      <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
        <span>{stock} plant{stock > 1 ? 's' : ''} restant{stock > 1 ? 's' : ''}</span>
        <span className="text-gray-400">
          {g.nb_plantes} planté{g.nb_plantes > 1 ? 's' : ''} / {total} repiqués
          {g.nb_graines_semees ? ` (${g.nb_graines_semees} graines)` : ''}
        </span>
      </div>

      {/* Barre stock restant — CA3 */}
      <ProgressBar value={stock} max={total} />
    </div>
  )
}

// ── Encart "Tout planté" ──────────────────────────────────────────────────────

function ToutPlanteAlert({ cultures }) {
  if (!cultures?.length) return null
  const noms = cultures
    .map(c => c.variete ? `${c.culture} (${c.variete})` : c.culture)
    .join(', ')
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-3 flex gap-2 items-start bg-gray-50 dark:bg-gray-800/50">
      <CheckCircle size={16} className="text-green-500 mt-0.5 shrink-0" />
      <div>
        <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">Tout planté ✓</p>
        <p className="text-xs text-gray-500 dark:text-gray-400 capitalize mt-0.5">{noms}</p>
      </div>
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

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

  // CA6 — loading skeleton
  if (loading) return <LoadingSkeleton lines={4} />

  // CA6 — erreur API
  if (error) return <ApiError message={error} onRetry={load} />

  // CA6 — pépinière vide
  const enAttente  = data?.en_attente  ?? []
  const toutPlante = data?.tout_plante ?? []

  if (!enAttente.length && !toutPlante.length) return (
    <div className="flex flex-col items-center gap-2 mt-12 text-gray-400">
      <Sprout size={32} />
      <p className="text-sm">Aucun godet en pépinière.</p>
    </div>
  )

  // CA1 — métriques résumé
  const totalGodets = enAttente.reduce((acc, g) => acc + g.stock_residuel_godet, 0)
  const tauxValues  = enAttente.map(g => g.taux_reussite).filter(t => t != null)
  const tauxMoyen   = tauxValues.length
    ? Math.round(tauxValues.reduce((a, b) => a + b, 0) / tauxValues.length)
    : null

  return (
    <div className="space-y-3">

      {/* CA1 — Tuiles résumé */}
      <div className="grid grid-cols-2 gap-2">
        <MetricTile
          label="Plants en godet"
          value={totalGodets}
          sub={`${enAttente.length} variété${enAttente.length > 1 ? 's' : ''}`}
        />
        <MetricTile
          label="Taux réussite moyen"
          value={tauxMoyen != null ? `${tauxMoyen}%` : '—'}
          sub="germination"
        />
      </div>

      {/* CA2 + CA3 — Liste des godets en attente */}
      {enAttente.length > 0 && (
        <div className="space-y-2">
          {enAttente.map((g, i) => (
            <GodotCard key={i} g={g} />
          ))}
        </div>
      )}

      {/* CA5 — Encart "Tout planté" */}
      <ToutPlanteAlert cultures={toutPlante} />

    </div>
  )
}
