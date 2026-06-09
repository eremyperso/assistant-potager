import { useState, useEffect } from 'react'
import { Sprout, X, CheckCircle } from 'lucide-react'
import { api } from '../lib/api.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(dateStr) {
  if (!dateStr) return '—'
  const [y, m, d] = dateStr.split('-')
  return `${d}/${m}/${y}`
}

function tauxMeta(taux) {
  if (taux == null) return { label: '—', badge: 'text-stone-400 dark:text-zinc-500 bg-stone-100 dark:bg-zinc-800' }
  if (taux >= 80) return {
    label: `Réussite ${taux}%`,
    badge: 'text-green-800 dark:text-green-400 bg-green-100 dark:bg-green-950/50',
  }
  if (taux >= 50) return {
    label: `Réussite ${taux}%`,
    badge: 'text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-950/50',
  }
  return {
    label: `Réussite ${taux}%`,
    badge: 'text-red-700 dark:text-red-400 bg-red-100 dark:bg-red-950/50',
  }
}

function arcColor(pct) {
  if (pct === 0)   return { light: '#D4CBBD', dark: '#3F3F46' }
  if (pct > 0.5)   return { light: '#2E6B3F', dark: '#4ADE80' }
  if (pct > 0.25)  return { light: '#B45309', dark: '#FBBF24' }
  return { light: '#B91C1C', dark: '#F87171' }
}

// ── ArcCounter SVG ────────────────────────────────────────────────────────────

function ArcCounter({ total, restants, isDark }) {
  const r = 17, cx = 22, cy = 22
  const circ = 2 * Math.PI * r
  const pct   = total > 0 ? restants / total : 0
  const color = arcColor(pct)
  const stroke = isDark ? color.dark : color.light
  const track  = isDark ? '#3F3F46' : '#E7E2D8'

  return (
    <div style={{ position: 'relative', width: 44, height: 44, flexShrink: 0 }}>
      <svg width="44" height="44" viewBox="0 0 44 44">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={track} strokeWidth="4" />
        {pct > 0 && (
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={stroke} strokeWidth="4"
            strokeDasharray={`${pct * circ} ${circ}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${cx} ${cy})`} />
        )}
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 13, fontWeight: 800, color: stroke, lineHeight: 1 }}>{restants}</span>
        <span style={{ fontSize: 7, lineHeight: 1.4, letterSpacing: '0.2px', color: isDark ? '#71717A' : '#A8A29E' }}>dispo</span>
      </div>
    </div>
  )
}

// ── Strip 3 métriques ─────────────────────────────────────────────────────────

function MetricStrip({ totalDispo, tauxMoyen, nbCultures }) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm dark:shadow-none border border-transparent dark:border-zinc-800 flex">
      {[
        { val: totalDispo,                    label: 'godets dispo',   cls: 'text-stone-900 dark:text-zinc-100' },
        { val: tauxMoyen != null ? `${tauxMoyen}%` : '—', label: 'réussite moy.', cls: 'text-green-800 dark:text-green-400' },
        { val: nbCultures,                    label: 'cultures',       cls: 'text-stone-900 dark:text-zinc-100' },
      ].map((m, i) => (
        <div key={m.label} className="flex-1 relative">
          {i > 0 && (
            <div className="absolute left-0 top-2.5 bottom-2.5 w-px bg-stone-100 dark:bg-zinc-800" />
          )}
          <div className="py-2.5 text-center">
            <div className={`text-[22px] font-bold tracking-tight leading-none ${m.cls}`}>{m.val}</div>
            <div className="text-[9px] text-stone-400 dark:text-zinc-500 mt-1">{m.label}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Carte culture ─────────────────────────────────────────────────────────────

function CultureCard({ g, epuise, onClick, isDark }) {
  const stock = g.stock_residuel_godet ?? 0
  const total = g.nb_plants_godets    ?? 0
  const tm    = tauxMeta(g.taux_reussite)

  // Commentaire contextuel généré depuis les données
  const comment = epuise
    ? `${total} plants entièrement plantés — lot clôturé.`
    : `${total} plants en godet · ${g.nb_plantes ?? 0} planté${(g.nb_plantes ?? 0) > 1 ? 's' : ''} · ${stock} en attente de mise en place.`

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-white dark:bg-zinc-900 rounded-2xl border border-transparent dark:border-zinc-800 p-3 flex flex-col gap-2 shadow-sm dark:shadow-none active:scale-[0.98] transition-transform"
    >
      {/* Ligne haute : nom + variété + taux + arc */}
      <div className="flex items-start gap-2.5">
        <div className="flex-1 flex flex-col gap-1.5">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="text-[13px] font-bold text-stone-900 dark:text-zinc-100 capitalize leading-none">
              {g.culture}
            </span>
            {g.variete && (
              <span className="text-[10px] italic text-stone-400 dark:text-zinc-500">
                {g.variete}
              </span>
            )}
          </div>
          <span className={`self-start text-[10px] font-semibold rounded-md px-1.5 py-0.5 ${tm.badge}`}>
            {tm.label}
          </span>
        </div>
        <ArcCounter total={total} restants={stock} isDark={isDark} />
      </div>

      {/* Zone commentaire */}
      <div className="bg-stone-50 dark:bg-zinc-800 rounded-lg px-2.5 py-1.5 text-[10px] italic text-stone-500 dark:text-zinc-500 leading-relaxed">
        {comment}
      </div>
    </button>
  )
}

// ── Panneau de détail cycle de vie ────────────────────────────────────────────

function TimelineRow({ icon, color, isLast, children }) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${color}`}>
          {icon}
        </div>
        {!isLast && <div className="w-px flex-1 bg-stone-200 dark:bg-zinc-700 mt-1 min-h-[1.5rem]" />}
      </div>
      <div className="pb-4 flex-1 min-w-0">{children}</div>
    </div>
  )
}

function DetailSheet({ godet, onClose, isDark }) {
  const [detail, setDetail]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    setLoading(true); setError(null)
    api.godetsDetail(godet.culture, godet.variete)
      .then(setDetail)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [godet.culture, godet.variete])

  const titre = godet.variete ? `${godet.culture} · ${godet.variete}` : godet.culture

  // Timeline items pour calculer isLast correctement
  const buildRows = (detail) => {
    const rows = []
    if (detail.semis.length > 0) {
      detail.semis.forEach(s => rows.push({ type: 'semis', data: s }))
    } else {
      rows.push({ type: 'semis_absent' })
    }
    detail.godets.forEach((g, i) => rows.push({ type: 'godet', data: g, idx: i, total: detail.godets.length }))
    if (detail.taux_germination != null) rows.push({ type: 'taux', val: detail.taux_germination })
    if (detail.plantations.length > 0) {
      detail.plantations.forEach(p => rows.push({ type: 'plantation', data: p }))
    } else {
      rows.push({ type: 'plantation_absent' })
    }
    return rows
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end max-w-sm mx-auto">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white dark:bg-zinc-900 rounded-t-2xl max-h-[85vh] flex flex-col shadow-2xl">

        {/* En-tête */}
        <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-stone-100 dark:border-zinc-800 shrink-0">
          <div>
            <h2 className="text-sm font-bold text-stone-900 dark:text-zinc-100 capitalize">{titre}</h2>
            <p className="text-[10px] text-stone-400 dark:text-zinc-500 mt-0.5">Cycle de vie complet</p>
          </div>
          <button onClick={onClose}
            className="w-7 h-7 rounded-full bg-stone-100 dark:bg-zinc-800 flex items-center justify-center text-stone-500 dark:text-zinc-400">
            <X size={13} />
          </button>
        </div>

        {/* Contenu */}
        <div className="overflow-y-auto px-4 pt-4 pb-6">
          {loading && <LoadingSkeleton lines={3} />}
          {error   && <p className="text-xs text-red-500">{error}</p>}
          {detail  && (() => {
            const rows = buildRows(detail)
            return (
              <div>
                {rows.map((row, i) => {
                  const isLast = i === rows.length - 1

                  if (row.type === 'semis') return (
                    <TimelineRow key={`semis-${row.data.id}`} icon="🌱" color="bg-emerald-100 dark:bg-emerald-900/60" isLast={isLast}>
                      <p className="text-xs font-semibold text-stone-800 dark:text-zinc-200">
                        Semis <span className="text-stone-400 dark:text-zinc-500 font-normal">#{row.data.id}</span>
                      </p>
                      <p className="text-xs text-stone-500 dark:text-zinc-400">
                        {row.data.nb_graines} graine{row.data.nb_graines > 1 ? 's' : ''}
                        {row.data.parcelle && <span className="text-stone-400 dark:text-zinc-500"> · {row.data.parcelle}</span>}
                      </p>
                      <p className="text-[10px] text-stone-400 dark:text-zinc-500 mt-0.5">{fmt(row.data.date)}</p>
                    </TimelineRow>
                  )

                  if (row.type === 'semis_absent') return (
                    <TimelineRow key="semis-absent" icon="🌱" color="bg-stone-100 dark:bg-zinc-800" isLast={isLast}>
                      <p className="text-xs text-stone-400 dark:text-zinc-500 italic">Semis non lié</p>
                    </TimelineRow>
                  )

                  if (row.type === 'godet') return (
                    <TimelineRow key={`godet-${row.data.id}`} icon="🪴" color="bg-teal-100 dark:bg-teal-900/60" isLast={isLast}>
                      <p className="text-xs font-semibold text-stone-800 dark:text-zinc-200">
                        Lot godet <span className="text-stone-400 dark:text-zinc-500 font-normal">#{row.data.id}</span>
                        {row.total > 1 && <span className="ml-1 text-[10px] text-stone-400 dark:text-zinc-500">· {row.idx + 1}/{row.total}</span>}
                      </p>
                      <p className="text-xs text-stone-500 dark:text-zinc-400">
                        {row.data.nb_plants} plant{row.data.nb_plants > 1 ? 's' : ''}
                        {row.data.nb_graines_lot != null && <span className="text-stone-400 dark:text-zinc-500"> sur {row.data.nb_graines_lot} graines</span>}
                      </p>
                      <p className="text-[10px] text-stone-400 dark:text-zinc-500 mt-0.5">{fmt(row.data.date)}</p>
                    </TimelineRow>
                  )

                  if (row.type === 'taux') return (
                    <div key="taux" className="mx-0 mt-0 mb-3 bg-stone-50 dark:bg-zinc-800 rounded-xl px-3 py-2 flex items-center justify-between">
                      <span className="text-[10px] text-stone-500 dark:text-zinc-500">Taux de germination</span>
                      <span className={`text-sm font-bold ${tauxMeta(row.val).badge} px-2 py-0.5 rounded-md`}>
                        {row.val}%
                      </span>
                    </div>
                  )

                  if (row.type === 'plantation') return (
                    <TimelineRow key={`plant-${row.data.id}`} icon="🌿" color="bg-green-100 dark:bg-green-900/60" isLast={isLast}>
                      <p className="text-xs font-semibold text-stone-800 dark:text-zinc-200">
                        Plantation <span className="text-stone-400 dark:text-zinc-500 font-normal">#{row.data.id}</span>
                      </p>
                      <p className="text-xs text-stone-500 dark:text-zinc-400">
                        {row.data.quantite} plant{row.data.quantite > 1 ? 's' : ''}
                        {row.data.parcelle && <span> → <span className="font-medium capitalize text-stone-700 dark:text-zinc-300">{row.data.parcelle}</span></span>}
                      </p>
                      {row.data.source_godet_ids.length > 0 && (
                        <p className="text-[10px] text-stone-400 dark:text-zinc-500 mt-0.5">
                          Lots : #{row.data.source_godet_ids.join(', #')}
                        </p>
                      )}
                      <p className="text-[10px] text-stone-400 dark:text-zinc-500 mt-0.5">{fmt(row.data.date)}</p>
                    </TimelineRow>
                  )

                  if (row.type === 'plantation_absent') return (
                    <TimelineRow key="plant-absent" icon="🌿" color="bg-stone-100 dark:bg-zinc-800" isLast={isLast}>
                      <p className="text-xs text-stone-400 dark:text-zinc-500 italic">Pas encore planté</p>
                    </TimelineRow>
                  )

                  return null
                })}
              </div>
            )
          })()}
        </div>
      </div>
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Pepiniere({ refresh }) {
  const [data, setData]              = useState(null)
  const [loading, setLoading]        = useState(true)
  const [error, setError]            = useState(null)
  const [selectedGodet, setSelected] = useState(null)
  const [isDark, setIsDark]          = useState(
    document.documentElement.classList.contains('dark')
  )

  // Sync isDark avec le thème Tailwind (toggle dans TopBar)
  useEffect(() => {
    const obs = new MutationObserver(() =>
      setIsDark(document.documentElement.classList.contains('dark'))
    )
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])

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
    <div className="flex flex-col items-center gap-2 mt-12 text-stone-400 dark:text-zinc-500">
      <Sprout size={32} />
      <p className="text-sm">Aucun godet en pépinière.</p>
    </div>
  )

  const totalDispo  = enAttente.reduce((acc, g) => acc + (g.stock_residuel_godet ?? 0), 0)
  const tauxValues  = tous.map(g => g.taux_reussite).filter(t => t != null)
  const tauxMoyen   = tauxValues.length
    ? Math.round(tauxValues.reduce((a, b) => a + b, 0) / tauxValues.length)
    : null
  const nomsToutPlante = toutPlante.map(c => c.variete ? `${c.culture} (${c.variete})` : c.culture)

  return (
    <>
      <div className="space-y-2 bg-stone-100 dark:bg-zinc-950 min-h-full px-0 py-0">

        {/* Strip 3 métriques */}
        <MetricStrip totalDispo={totalDispo} tauxMoyen={tauxMoyen} nbCultures={tous.length} />

        {/* Cartes en attente */}
        {enAttente.map((g, i) => (
          <CultureCard key={`att-${i}`} g={g} epuise={false} isDark={isDark}
            onClick={() => setSelected(g)} />
        ))}

        {/* Cartes tout planté */}
        {toutPlante.map((g, i) => (
          <CultureCard key={`ep-${i}`} g={g} epuise={true} isDark={isDark}
            onClick={() => setSelected(g)} />
        ))}

        {/* Alerte cultures entièrement plantées */}
        {toutPlante.length > 0 && (
          <div className="flex items-center gap-2 bg-emerald-50 dark:bg-green-950/40 border border-emerald-200 dark:border-green-800/50 rounded-xl px-3 py-2 text-[11px] text-emerald-800 dark:text-green-400">
            <CheckCircle size={13} className="shrink-0" />
            <span>
              <span className="font-semibold">{toutPlante.length}</span> culture{toutPlante.length > 1 ? 's' : ''} entièrement plantée{toutPlante.length > 1 ? 's' : ''} : {nomsToutPlante.join(', ')}
            </span>
          </div>
        )}

      </div>

      {/* Panneau de détail */}
      {selectedGodet && (
        <DetailSheet godet={selectedGodet} onClose={() => setSelected(null)} isDark={isDark} />
      )}
    </>
  )
}
