import { useState, useEffect } from 'react'
import { Sprout } from 'lucide-react'
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

// ── Tuile résumé ──────────────────────────────────────────────────────────────

function MetricTile({ label, value }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-4">
      <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{label}</p>
    </div>
  )
}

// ── Carte godet ───────────────────────────────────────────────────────────────

function GodotCard({ g, epuise }) {
  const taux  = g.taux_reussite
  const stock = g.stock_residuel_godet ?? 0
  const total = g.nb_plants_godets    ?? 0
  const pct   = total > 0 ? Math.min(100, Math.round((stock / total) * 100)) : 0

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-4">

      {/* Ligne 1 : culture + variété chip + badge "Tout planté" */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="text-base font-bold text-gray-900 dark:text-gray-100 capitalize">
            {g.culture}
          </span>
          {g.variete && (
            <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded-full">
              {g.variete}
            </span>
          )}
        </div>
        {epuise && (
          <span className="text-[10px] font-semibold bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 px-2 py-0.5 rounded-full shrink-0">
            Tout planté
          </span>
        )}
      </div>

      {/* Ligne 2 : stock restant · plantés / total */}
      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
        <span className="font-medium text-gray-800 dark:text-gray-200">
          {stock} godet{stock > 1 ? 's' : ''} restant{stock > 1 ? 's' : ''}
        </span>
        <span className="mx-2 text-gray-300">·</span>
        <span>{g.nb_plantes} planté{(g.nb_plantes ?? 0) > 1 ? 's' : ''} / {total}</span>
      </p>

      {/* Ligne 3 : barre stock restant (gauche) + taux (droite) */}
      <div className="flex items-end gap-3 mt-3">
        <div className="flex-1 min-w-0">
          <p className="text-[10px] text-gray-400 mb-1">Stock restant</p>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className="h-2 rounded-full bg-blue-400 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className={`text-2xl font-bold leading-none ${tauxColor(taux)}`}>
            {taux != null ? `${taux}%` : '—'}
          </p>
          <p className="text-[10px] text-gray-400 mt-0.5">succès</p>
        </div>
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

  if (loading) return <LoadingSkeleton lines={4} />
  if (error)   return <ApiError message={error} onRetry={load} />

  const enAttente  = data?.en_attente  ?? []
  const toutPlante = data?.tout_plante ?? []
  const tous       = [...enAttente, ...toutPlante]

  if (!tous.length) return (
    <div className="flex flex-col items-center gap-2 mt-12 text-gray-400">
      <Sprout size={32} />
      <p className="text-sm">Aucun godet en pépinière.</p>
    </div>
  )

  // CA1 — métriques résumé (basées sur les godets en attente)
  const totalGodets = enAttente.reduce((acc, g) => acc + (g.stock_residuel_godet ?? 0), 0)
  const tauxValues  = tous.map(g => g.taux_reussite).filter(t => t != null)
  const tauxMoyen   = tauxValues.length
    ? Math.round(tauxValues.reduce((a, b) => a + b, 0) / tauxValues.length)
    : null

  // Noms des cultures tout plantées pour le pied
  const nomsToutPlante = toutPlante.map(c =>
    c.variete ? `${c.culture} (${c.variete})` : c.culture
  )

  return (
    <div className="space-y-3">

      {/* CA1 — Tuiles résumé */}
      <div className="grid grid-cols-2 gap-2">
        <MetricTile label="Godets en stock"       value={totalGodets} />
        <MetricTile label="Taux de réussite moy." value={tauxMoyen != null ? `${tauxMoyen}%` : '—'} />
      </div>

      {/* CA2 + CA3 — Toutes les cartes (en attente + tout planté) */}
      <div className="space-y-2">
        {enAttente.map((g, i) => (
          <GodotCard key={`att-${i}`} g={g} epuise={false} />
        ))}
        {toutPlante.map((g, i) => (
          <GodotCard key={`ep-${i}`}  g={g} epuise={true}  />
        ))}
      </div>

      {/* CA5 — Pied de page simple */}
      {toutPlante.length > 0 && (
        <p className="text-xs text-gray-500 dark:text-gray-400 text-center capitalize">
          <span className="font-medium">{toutPlante.length}</span> culture{toutPlante.length > 1 ? 's' : ''} entièrement plantée{toutPlante.length > 1 ? 's' : ''} : {nomsToutPlante.join(', ')}
        </p>
      )}

    </div>
  )
}
