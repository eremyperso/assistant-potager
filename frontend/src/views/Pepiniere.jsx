import { useState, useEffect } from 'react'
import { Sprout, X, CheckCircle, ShoppingBag } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import CultureFilter from '../components/CultureFilter.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import MetricStrip from '../components/MetricStrip.jsx'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(dateStr) {
  if (!dateStr) return '—'
  const [y, m, d] = dateStr.split('-')
  return `${d}/${m}/${y}`
}

function tauxMeta(taux) {
  if (taux == null) return { label: '—', textVar: 'var(--g-sec)', bgVar: 'var(--g-brd)' }
  if (taux >= 80)  return { label: `Réussite ${taux}%`, textVar: 'var(--g-acc)', bgVar: 'var(--g-acc-dim)' }
  if (taux >= 50)  return { label: `Réussite ${taux}%`, textVar: 'var(--g-amb)', bgVar: 'var(--g-amb-dim)' }
  return           { label: `Réussite ${taux}%`, textVar: 'var(--g-red)', bgVar: 'var(--g-red-dim)' }
}

function stockAccentVar(restants, total) {
  if (total === 0) return 'var(--g-sec)'
  const ratio = restants / total
  if (ratio > 0.4)  return 'var(--g-acc)'
  if (ratio > 0.15) return 'var(--g-amb)'
  return 'var(--g-red)'
}

// ── ArcCounter SVG ────────────────────────────────────────────────────────────

function ArcCounter({ total, restants }) {
  const r = 19, cx = 24, cy = 24
  const circ  = 2 * Math.PI * r
  const pct   = total > 0 ? restants / total : 0
  const color = stockAccentVar(restants, total)

  return (
    <div style={{ position: 'relative', width: 48, height: 48, flexShrink: 0 }}>
      <svg width="48" height="48" viewBox="0 0 48 48">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--g-brd)" strokeWidth="4" />
        {pct > 0 && (
          <circle
            cx={cx} cy={cy} r={r}
            fill="none" stroke={color} strokeWidth="4"
            strokeDasharray={`${pct * circ} ${circ}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        )}
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 14, fontWeight: 800, color, lineHeight: 1 }}>{restants}</span>
        <span style={{ fontSize: 8, color: 'var(--g-sec)', lineHeight: 1.4 }}>dispo</span>
      </div>
    </div>
  )
}

// ── Carte culture ─────────────────────────────────────────────────────────────

function CultureCard({ g, epuise, onClick }) {
  const enGermination = g.statut === 'en_germination'
  const stock  = g.stock_residuel_godet ?? 0
  const total  = g.nb_plants_godets    ?? 0
  const tm     = tauxMeta(g.taux_reussite)
  const accent = enGermination ? 'var(--g-mid)' : stockAccentVar(stock, total)

  let comment
  if (enGermination) {
    comment = `${g.graines_en_germination} ${g.unite_germination || 'graines'} semées, pas encore repiquées en godet.`
  } else if (epuise) {
    comment = `${total} plants entièrement plantés — lot clôturé.`
  } else {
    comment = `${total} plants en godet · ${g.nb_plantes ?? 0} planté${(g.nb_plantes ?? 0) > 1 ? 's' : ''} · ${stock} en attente de mise en place.`
    if (g.graines_en_germination > 0) {
      comment += ` (+${g.graines_en_germination} ${g.unite_germination || 'graines'} en germination)`
    }
  }

  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-2xl border border-g-brd overflow-hidden flex active:scale-[0.98] transition-transform mb-2"
      style={{ background: 'var(--g-card)' }}
    >
      {/* Barre accent gauche */}
      <div style={{ width: 5, flexShrink: 0, background: accent }} />

      {/* Corps */}
      <div className="flex-1 p-3.5 flex flex-col gap-2.5">

        {/* Ligne haute : nom + variété + arc */}
        <div className="flex items-start gap-3">
          <div className="flex-1 flex flex-col gap-1.5">
            <div className="flex items-baseline gap-1.5 flex-wrap">
              <span className="text-[20px] font-semibold font-serif tracking-tight capitalize leading-tight" style={{ color: 'var(--g-pri)' }}>
                {g.culture}
              </span>
              {g.variete && (
                <span className="text-[14px] italic" style={{ color: 'var(--g-sec)', fontFamily: 'inherit' }}>
                  {g.variete}
                </span>
              )}
            </div>

            {/* Badge taux / germination */}
            <span
              className="self-start text-[12px] font-semibold rounded-lg px-2 py-0.5"
              style={enGermination
                ? { color: 'var(--g-mid)', background: 'var(--g-brd)' }
                : { color: tm.textVar, background: tm.bgVar }}
            >
              {enGermination ? '🌱 En germination' : tm.label}
            </span>

            {/* Badge ventes */}
            {(g.nb_vendus ?? 0) > 0 && (
              <span
                className="self-start text-[12px] font-semibold rounded-lg px-2 py-0.5"
                style={{ color: 'var(--g-amb)', background: 'var(--g-amb-dim)' }}
              >
                🏷️ {g.nb_vendus} pied{g.nb_vendus > 1 ? 's' : ''} vendu{g.nb_vendus > 1 ? 's' : ''}
              </span>
            )}
          </div>

          {enGermination ? (
            <div style={{ width: 48, height: 48, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--g-mid)', lineHeight: 1 }}>{g.graines_en_germination}</span>
              <span style={{ fontSize: 8, color: 'var(--g-sec)', lineHeight: 1.4 }}>{g.unite_germination || 'graines'}</span>
            </div>
          ) : (
            <ArcCounter total={total} restants={stock} />
          )}
        </div>

        {/* Zone commentaire */}
        <div
          className="rounded-xl px-3 py-2 text-sm italic leading-relaxed"
          style={{ background: 'var(--g-sur)', color: 'var(--g-sec)' }}
        >
          {comment}
        </div>
      </div>
    </button>
  )
}

// ── Panneau de détail cycle de vie ────────────────────────────────────────────

function TimelineRow({ icon, bgVar, isLast, children }) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center text-base shrink-0"
          style={{ background: bgVar }}
        >
          {icon}
        </div>
        {!isLast && <div className="w-px flex-1 bg-g-brd mt-1 min-h-6" />}
      </div>
      <div className="pb-4 flex-1 min-w-0">{children}</div>
    </div>
  )
}

function DetailSheet({ godet, onClose }) {
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
    if ((detail.ventes ?? []).length > 0) {
      detail.ventes.forEach(v => rows.push({ type: 'vente', data: v }))
    }
    if ((detail.pertes_godet ?? []).length > 0) {
      detail.pertes_godet.forEach(p => rows.push({ type: 'perte_godet', data: p }))
    }
    return rows
  }

  const tm = tauxMeta(detail?.taux_germination)

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end max-w-sm mx-auto">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div
        className="relative rounded-t-2xl max-h-[85vh] flex flex-col shadow-2xl"
        style={{ background: 'var(--g-sur)' }}
      >
        {/* En-tête */}
        <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-g-brd shrink-0">
          <div>
            <h2 className="text-base font-bold font-serif capitalize" style={{ color: 'var(--g-pri)' }}>{titre}</h2>
            <p className="text-[12px] mt-0.5" style={{ color: 'var(--g-sec)' }}>Cycle de vie complet</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full flex items-center justify-center"
            style={{ background: 'var(--g-card)', color: 'var(--g-sec)' }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Contenu */}
        <div className="overflow-y-auto px-4 pt-4 pb-6">
          {loading && <LoadingSkeleton lines={3} />}
          {error   && <p className="text-sm" style={{ color: 'var(--g-red)' }}>{error}</p>}
          {detail  && (() => {
            const rows = buildRows(detail)
            return (
              <div>
                {rows.map((row, i) => {
                  const isLast = i === rows.length - 1

                  if (row.type === 'semis') return (
                    <TimelineRow key={`semis-${row.data.id}`} icon="🌱" bgVar="var(--g-acc-dim)" isLast={isLast}>
                      <p className="text-sm font-semibold" style={{ color: 'var(--g-pri)' }}>
                        Semis <span className="font-normal" style={{ color: 'var(--g-sec)' }}>#{row.data.id}</span>
                      </p>
                      <p className="text-sm" style={{ color: 'var(--g-sec)' }}>
                        {row.data.nb_graines} {row.data.unite || 'graines'}
                        {row.data.parcelle && <span style={{ color: 'var(--g-mid)' }}> · {row.data.parcelle}</span>}
                      </p>
                      <p className="text-[12px] mt-0.5" style={{ color: 'var(--g-sec)' }}>{fmt(row.data.date)}</p>
                    </TimelineRow>
                  )

                  if (row.type === 'semis_absent') return (
                    <TimelineRow key="semis-absent" icon="🌱" bgVar="var(--g-brd)" isLast={isLast}>
                      <p className="text-sm italic" style={{ color: 'var(--g-sec)' }}>Semis non lié</p>
                    </TimelineRow>
                  )

                  if (row.type === 'godet') return (
                    <TimelineRow key={`godet-${row.data.id}`} icon="🪴" bgVar="var(--g-acc-dim)" isLast={isLast}>
                      <p className="text-sm font-semibold" style={{ color: 'var(--g-pri)' }}>
                        Lot godet <span className="font-normal" style={{ color: 'var(--g-sec)' }}>#{row.data.id}</span>
                        {row.total > 1 && <span className="ml-1 text-[12px]" style={{ color: 'var(--g-sec)' }}>· {row.idx + 1}/{row.total}</span>}
                      </p>
                      <p className="text-sm" style={{ color: 'var(--g-sec)' }}>
                        {row.data.nb_plants} plant{row.data.nb_plants > 1 ? 's' : ''}
                        {row.data.nb_graines_lot != null && <span> sur {row.data.nb_graines_lot} graines</span>}
                      </p>
                      <p className="text-[12px] mt-0.5" style={{ color: 'var(--g-sec)' }}>{fmt(row.data.date)}</p>
                    </TimelineRow>
                  )

                  if (row.type === 'taux') return (
                    <div
                      key="taux"
                      className="mb-3 rounded-xl px-3 py-2.5 flex items-center justify-between"
                      style={{ background: 'var(--g-card)' }}
                    >
                      <span className="text-sm" style={{ color: 'var(--g-sec)' }}>Taux de germination</span>
                      <span
                        className="text-sm font-bold px-2.5 py-0.5 rounded-lg"
                        style={{ color: tm.textVar, background: tm.bgVar }}
                      >
                        {row.val}%
                      </span>
                    </div>
                  )

                  if (row.type === 'plantation') return (
                    <TimelineRow key={`plant-${row.data.id}`} icon="🌿" bgVar="var(--g-acc-dim)" isLast={isLast}>
                      <p className="text-sm font-semibold" style={{ color: 'var(--g-pri)' }}>
                        Plantation <span className="font-normal" style={{ color: 'var(--g-sec)' }}>#{row.data.id}</span>
                      </p>
                      <p className="text-sm" style={{ color: 'var(--g-sec)' }}>
                        {row.data.quantite} plant{row.data.quantite > 1 ? 's' : ''}
                        {row.data.parcelle && <span> → <span className="font-medium capitalize" style={{ color: 'var(--g-pri)' }}>{row.data.parcelle}</span></span>}
                      </p>
                      {row.data.source_godet_ids.length > 0 && (
                        <p className="text-[12px] mt-0.5" style={{ color: 'var(--g-sec)' }}>
                          Lots : #{row.data.source_godet_ids.join(', #')}
                        </p>
                      )}
                      <p className="text-[12px] mt-0.5" style={{ color: 'var(--g-sec)' }}>{fmt(row.data.date)}</p>
                    </TimelineRow>
                  )

                  if (row.type === 'plantation_absent') return (
                    <TimelineRow key="plant-absent" icon="🌿" bgVar="var(--g-brd)" isLast={isLast}>
                      <p className="text-sm italic" style={{ color: 'var(--g-sec)' }}>Pas encore planté</p>
                    </TimelineRow>
                  )

                  if (row.type === 'vente') return (
                    <TimelineRow key={`vente-${row.data.id}`} icon="🏷️" bgVar="var(--g-amb-dim)" isLast={isLast}>
                      <p className="text-sm font-semibold" style={{ color: 'var(--g-pri)' }}>
                        Vente <span className="font-normal" style={{ color: 'var(--g-sec)' }}>#{row.data.id}</span>
                      </p>
                      <p className="text-sm" style={{ color: 'var(--g-sec)' }}>
                        {row.data.quantite} pied{row.data.quantite > 1 ? 's' : ''} vendu{row.data.quantite > 1 ? 's' : ''}
                      </p>
                      <p className="text-[12px] mt-0.5" style={{ color: 'var(--g-sec)' }}>{fmt(row.data.date)}</p>
                    </TimelineRow>
                  )

                  if (row.type === 'perte_godet') return (
                    <TimelineRow key={`perte-${row.data.id}`} icon="💀" bgVar="var(--g-red-dim)" isLast={isLast}>
                      <p className="text-sm font-semibold" style={{ color: 'var(--g-pri)' }}>
                        Perte pépinière <span className="font-normal" style={{ color: 'var(--g-sec)' }}>#{row.data.id}</span>
                      </p>
                      <p className="text-sm" style={{ color: 'var(--g-red)' }}>
                        {row.data.quantite} plant{row.data.quantite > 1 ? 's' : ''} perdu{row.data.quantite > 1 ? 's' : ''}
                      </p>
                      <p className="text-[12px] mt-0.5" style={{ color: 'var(--g-sec)' }}>{fmt(row.data.date)}</p>
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
  const { dateRef } = useDateRef()
  const [data, setData]              = useState(null)
  const [loading, setLoading]        = useState(true)
  const [error, setError]            = useState(null)
  const [selectedGodet, setSelected] = useState(null)
  const [search, setSearch]          = useState('')  // [CA19] local, non persisté

  async function load() {
    setLoading(true); setError(null)
    try   { setData(await api.godets(dateRef)) }
    catch (e) { setError(e.message) }
    finally   { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh, dateRef])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error)   return <ApiError message={error} onRetry={load} />

  const enAttente  = data?.en_attente  ?? []
  const toutPlante = data?.tout_plante ?? []
  const tous       = [...enAttente, ...toutPlante]

  if (!tous.length) return (
    <>
      <div className="flex items-center gap-2 mb-3">
        <DateRefPicker />
        <CultureFilter value={search} onChange={setSearch} className="relative flex-1" />
      </div>
      <div className="flex flex-col items-center gap-2 mt-12 text-g-sec">
        <Sprout size={36} />
        <p className="text-base">Aucun godet en pépinière.</p>
      </div>
    </>
  )

  // [CA18] Filtre culture côté client
  const q = search.toLowerCase()
  const filteredAttente = q ? enAttente.filter(g => (g.culture || '').toLowerCase().includes(q) || (g.variete || '').toLowerCase().includes(q)) : enAttente
  const filteredPlante  = q ? toutPlante.filter(g => (g.culture || '').toLowerCase().includes(q) || (g.variete || '').toLowerCase().includes(q)) : toutPlante
  const filteredTous    = [...filteredAttente, ...filteredPlante]

  const totalDispo  = filteredAttente.reduce((acc, g) => acc + (g.stock_residuel_godet ?? 0), 0)
  const tauxValues  = filteredTous.map(g => g.taux_reussite).filter(t => t != null)
  const tauxMoyen   = tauxValues.length
    ? Math.round(tauxValues.reduce((a, b) => a + b, 0) / tauxValues.length)
    : null
  const nomsToutPlante = filteredPlante.map(c => c.variete ? `${c.culture} (${c.variete})` : c.culture)
  const totalVendus    = filteredTous.reduce((acc, g) => acc + (g.nb_vendus ?? 0), 0)

  return (
    <>
      <div>
        {/* [CA14] Filtres combinés côte à côte */}
        <div className="flex items-center gap-2 mb-3">
          <DateRefPicker />
          <CultureFilter value={search} onChange={setSearch} className="relative flex-1" />
        </div>

        {/* Strip 3 métriques */}
        <MetricStrip metrics={[
          { value: totalDispo,                              label: 'godets dispo',  color: 'var(--g-pri)' },
          { value: tauxMoyen != null ? `${tauxMoyen}%` : '—', label: 'réussite moy.', color: 'var(--g-acc)' },
          { value: filteredTous.length,                      label: 'cultures',      color: 'var(--g-pri)' },
        ]}/>

        {/* Cartes en attente */}
        {filteredAttente.map((g, i) => (
          <CultureCard key={`att-${i}`} g={g} epuise={false} onClick={() => setSelected(g)} />
        ))}

        {/* Cartes tout planté */}
        {filteredPlante.map((g, i) => (
          <CultureCard key={`ep-${i}`} g={g} epuise={true} onClick={() => setSelected(g)} />
        ))}

        {/* Alerte cultures entièrement plantées */}
        {toutPlante.length > 0 && (
          <div
            className="flex items-center gap-2 rounded-2xl px-3 py-2.5 text-sm mb-2"
            style={{ background: 'var(--g-acc-dim)', border: '1px solid var(--g-acc)', color: 'var(--g-acc)' }}
          >
            <CheckCircle size={14} className="shrink-0" />
            <span>
              <span className="font-semibold">{toutPlante.length}</span> culture{toutPlante.length > 1 ? 's' : ''} entièrement plantée{toutPlante.length > 1 ? 's' : ''} : {nomsToutPlante.join(', ')}
            </span>
          </div>
        )}

        {/* Bandeau récap ventes */}
        {totalVendus > 0 && (
          <div
            className="flex items-center gap-2 rounded-2xl px-3 py-2.5 text-sm mb-2"
            style={{ background: 'var(--g-amb-dim)', border: '1px solid var(--g-amb)', color: 'var(--g-amb)' }}
          >
            <ShoppingBag size={14} className="shrink-0" />
            <span>
              <span className="font-semibold">{totalVendus}</span> pied{totalVendus > 1 ? 's' : ''} vendu{totalVendus > 1 ? 's' : ''} cette saison
            </span>
          </div>
        )}
      </div>

      {/* Panneau de détail */}
      {selectedGodet && (
        <DetailSheet godet={selectedGodet} onClose={() => setSelected(null)} />
      )}
    </>
  )
}
