import { useState, useEffect, useRef } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ─── constantes ───────────────────────────────────────────────────────────────
const WD = ['D', 'L', 'M', 'M', 'J', 'V', 'S']
const MO = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']

// ─── composants utilitaires ───────────────────────────────────────────────────

function GraphZone({ icon, title, subtitle, children }) {
  return (
    <section style={{
      background: 'var(--g-card)',
      border: '1px solid var(--g-brd)',
      borderRadius: 18,
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '12px 14px',
        background: 'var(--g-sur)',
        borderBottom: '0.5px solid var(--g-brd)',
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 10,
          background: 'var(--g-acc-dim)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 16, fontWeight: 600, color: 'var(--g-pri)',
            fontFamily: 'Lora, Georgia, serif', lineHeight: 1.2,
          }}>
            {title}
          </div>
          {subtitle && (
            <div style={{ fontSize: 12, color: 'var(--g-sec)', fontStyle: 'italic', marginTop: 1 }}>
              {subtitle}
            </div>
          )}
        </div>
      </div>
      <div style={{ padding: '12px 12px 14px' }}>{children}</div>
    </section>
  )
}

function StatTile({ value, unit, label, color, bg }) {
  return (
    <div style={{
      flex: 1,
      background: bg || 'var(--g-card)',
      border: '1px solid var(--g-brd)',
      borderRadius: 13,
      padding: '11px 4px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
        <span style={{
          fontSize: 23, fontWeight: 700,
          color: color || 'var(--g-pri)',
          letterSpacing: '-0.6px', lineHeight: 1,
        }}>
          {value}
        </span>
        {unit && (
          <span style={{ fontSize: 12, color: color || 'var(--g-sec)', fontWeight: 600 }}>
            {unit}
          </span>
        )}
      </div>
      <span style={{ fontSize: 11, color: 'var(--g-sec)', textAlign: 'center', lineHeight: 1.25 }}>
        {label}
      </span>
    </div>
  )
}

function Segmented({ options, value, onChange }) {
  return (
    <div style={{
      display: 'flex', gap: 3,
      background: 'var(--g-sur)',
      border: '1px solid var(--g-brd)',
      borderRadius: 11,
      padding: 3,
    }}>
      {options.map(o => {
        const on = o.v === value
        return (
          <button
            key={o.v}
            onClick={() => onChange(o.v)}
            style={{
              flex: 1, padding: '8px 4px', borderRadius: 8,
              border: 'none', cursor: 'pointer',
              fontSize: 14, fontWeight: on ? 700 : 500,
              background: on ? 'var(--g-acc)' : 'transparent',
              color: on ? 'var(--g-bg)' : 'var(--g-sec)',
              transition: 'all .15s',
            }}
          >
            {o.l}
          </button>
        )
      })}
    </div>
  )
}

function WeatherChart({ data }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const onWheel = (e) => {
      if (e.deltaY !== 0) {
        e.preventDefault()
        el.scrollLeft += e.deltaY
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const n      = data.length
  const perDay = 44
  const plotW  = n * perDay
  const TT = 22, TB = 150   // zone température (y haut / y bas)
  const PT = 196, PB = 250  // zone précipitations (y haut / y bas)
  const H  = 300

  const dlo   = Math.min(...data.map(d => d.tmin)) - 2
  const dhi   = Math.max(...data.map(d => d.tmax)) + 2
  const pmax  = Math.max(6, ...data.map(d => d.precip))

  const x  = i => perDay * (i + 0.5)
  const ty = v => TT + (1 - (v - dlo) / (dhi - dlo)) * (TB - TT)
  const py = v => PB - (v / pmax) * (PB - PT)

  const ticks = [Math.round(dhi), Math.round((dlo + dhi) / 2), Math.round(dlo)]
  const bw    = perDay * 0.46
  const pbw   = perDay * 0.34

  return (
    <div style={{ display: 'flex', alignItems: 'stretch' }}>
      {/* axe Y fixe */}
      <svg
        width="28"
        viewBox={`0 0 28 ${H}`}
        style={{ flexShrink: 0, overflow: 'visible' }}
      >
        {ticks.map((t, k) => (
          <text key={k} x="26" y={ty(t) + 3.5} textAnchor="end" fontSize="11" fill="var(--g-sec)">
            {t}°
          </text>
        ))}
        <text x="26" y={PT + 2}          textAnchor="end" fontSize="10" fill="var(--g-sec)">{Math.round(pmax)}</text>
        <text x="26" y={PB + 2}          textAnchor="end" fontSize="10" fill="var(--g-sec)">0</text>
        <text
          x="26" y={(PT + PB) / 2}
          textAnchor="end" fontSize="9" fill="var(--g-sec)" opacity="0.7"
          transform={`rotate(-90 26 ${(PT + PB) / 2})`}
        >
          mm
        </text>
      </svg>

      {/* zone scrollable */}
      <div ref={scrollRef} style={{ flex: 1, overflowX: 'auto', overflowY: 'hidden' }}>
        <svg width={plotW} viewBox={`0 0 ${plotW} ${H}`} style={{ display: 'block' }}>
          <defs>
            <linearGradient id="wx-bgrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   style={{ stopColor: 'var(--g-amb)' }}/>
              <stop offset="100%" style={{ stopColor: 'var(--g-rain)' }}/>
            </linearGradient>
          </defs>

          {/* grille horizontale */}
          {ticks.map((t, k) => (
            <line
              key={k}
              x1="0" y1={ty(t)} x2={plotW} y2={ty(t)}
              stroke="var(--g-brd)" strokeWidth="1"
              strokeDasharray={k === ticks.length - 1 ? '0' : '2 3'}
              opacity="0.6"
            />
          ))}

          {/* barres temp min–max */}
          {data.map((p, i) => (
            <rect
              key={i}
              x={x(i) - bw / 2}
              y={ty(p.tmax)}
              width={bw}
              height={Math.max(2, ty(p.tmin) - ty(p.tmax))}
              rx={bw / 2}
              fill="url(#wx-bgrad)"
            />
          ))}

          {/* étiquettes temp */}
          {data.map((p, i) => (
            <g key={i}>
              <text x={x(i)} y={ty(p.tmax) - 7}  textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--g-amb)">{p.tmax}</text>
              <text x={x(i)} y={ty(p.tmin) + 14} textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--g-rain-line)">{p.tmin}</text>
            </g>
          ))}

          {/* ligne de base précipitations */}
          <line x1="0" y1={PB} x2={plotW} y2={PB} stroke="var(--g-brd)" strokeWidth="1"/>

          {/* barres précipitations */}
          {data.map((p, i) => p.precip > 0 && (
            <g key={i}>
              <rect
                x={x(i) - pbw / 2} y={py(p.precip)}
                width={pbw} height={PB - py(p.precip)}
                rx="2" fill="var(--g-rain)"
              />
              <text x={x(i)} y={py(p.precip) - 4} textAnchor="middle" fontSize="10" fontWeight="600" fill="var(--g-rain-line)">
                {p.precip}
              </text>
            </g>
          ))}

          {/* axe X : jour semaine + numéro + mois */}
          {data.map((p, i) => {
            const dt = new Date(p.date + 'T12:00:00')
            const showMonth = i === 0 || dt.getDate() === 1
            return (
              <g key={i}>
                <text x={x(i)} y={264} textAnchor="middle" fontSize="10" fill="var(--g-sec)" opacity="0.7">
                  {WD[dt.getDay()]}
                </text>
                <text x={x(i)} y={278} textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--g-mid)">
                  {dt.getDate()}
                </text>
                {showMonth && (
                  <text x={x(i)} y={292} textAnchor="middle" fontSize="10" fontWeight="700" fill="var(--g-acc)">
                    {MO[dt.getMonth()]}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}

// ─── vue principale ───────────────────────────────────────────────────────────

export default function Stats({ refresh }) {
  const { dateRef } = useDateRef()

  const [statsData, setStatsData]   = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState(null)

  const [meteo, setMeteo]           = useState(null)
  const [meteoLoading, setMeteoLoading] = useState(true)
  const [meteoError, setMeteoError] = useState(null)
  const [days, setDays]             = useState(7)

  async function loadStats() {
    setStatsLoading(true); setStatsError(null)
    try   { setStatsData(await api.stats(dateRef)) }
    catch (e) { setStatsError(e.message) }
    finally   { setStatsLoading(false) }
  }

  async function loadMeteo() {
    setMeteoLoading(true); setMeteoError(null)
    try   { setMeteo(await api.meteoHistory(days)) }
    catch (e) { setMeteoError(e.message) }
    finally   { setMeteoLoading(false) }
  }

  useEffect(() => { loadStats() }, [refresh, dateRef])
  useEffect(() => { loadMeteo() }, [days])

  // ─── KPIs météo ─────────────────────────────────────────────────────────────
  const jours    = meteo?.jours || []
  const tmaxP    = jours.length ? Math.max(...jours.map(d => d.temp_max))          : null
  const tminP    = jours.length ? Math.min(...jours.map(d => d.temp_min))          : null
  const totPluie = jours.reduce((s, d) => s + (d.precipitations || 0), 0)
  const joursPluie = jours.filter(d => d.precipitations > 0).length

  const rangeLabel = (() => {
    if (!jours.length) return ''
    const fmt = iso => {
      const dt = new Date(iso + 'T12:00:00')
      return `${dt.getDate()} ${MO[dt.getMonth()]}`
    }
    return `${fmt(jours[0].date)} – ${fmt(jours[jours.length - 1].date)}`
  })()

  // données adaptées au format du graphique
  const chartData = jours.map(d => ({
    date:   d.date,
    tmax:   d.temp_max,
    tmin:   d.temp_min,
    precip: Math.round((d.precipitations || 0) * 10) / 10,
  }))

  // graphique stocks existant
  const stockChart = (statsData?.stock_par_culture || []).slice(0, 8).map(c => ({
    name:   c.culture?.slice(0, 6) || '?',
    plants: c.nb_plants || 0,
  }))

  return (
    <div className="space-y-3">
      <DateRefPicker className="flex items-center gap-1.5 mb-1" />

      {/* ─── Graphique météo ─── */}
      <GraphZone
        icon={
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
            stroke="var(--g-acc)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 18H9.5a3.5 3.5 0 0 1 0-7 4.5 4.5 0 0 1 8.7 1.2A3 3 0 0 1 17 18z"/>
            <line x1="9"  y1="20.5" x2="9"  y2="22"/>
            <line x1="13" y1="20.5" x2="13" y2="22"/>
          </svg>
        }
        title="Météo"
        subtitle={rangeLabel ? `Températures & précipitations · ${rangeLabel}` : 'Températures & précipitations'}
      >
        {meteoLoading ? (
          <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--g-sec)' }}>Chargement…</span>
          </div>
        ) : meteoError ? (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <span style={{ fontSize: 13, color: 'var(--g-red)' }}>{meteoError}</span>
            <button
              onClick={loadMeteo}
              style={{
                display: 'block', margin: '8px auto 0',
                fontSize: 13, color: 'var(--g-acc)',
                background: 'none', border: 'none', cursor: 'pointer',
              }}
            >
              Réessayer
            </button>
          </div>
        ) : (
          <>
            {/* KPI tiles */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <StatTile value={tmaxP ?? '—'} unit="°" label="max"      color="var(--g-amb)"/>
              <StatTile value={tminP ?? '—'} unit="°" label="min"      color="var(--g-rain-line)"/>
              <StatTile
                value={Math.round(totPluie * 10) / 10}
                unit="mm" label="pluie"
                color="var(--g-rain)" bg="var(--g-rain-dim)"
              />
              <StatTile value={joursPluie} unit="j" label="j. pluie"/>
            </div>

            {/* légende */}
            <div style={{ display: 'flex', gap: 14, paddingInline: 2, marginBottom: 8 }}>
              {[
                { c: 'var(--g-amb)',       l: 'max' },
                { c: 'var(--g-rain-line)', l: 'min' },
                { c: 'var(--g-rain)',      l: 'précip.' },
              ].map(({ c, l }) => (
                <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 3, background: c }}/>
                  <span style={{ fontSize: 12, color: 'var(--g-sec)' }}>{l}</span>
                </div>
              ))}
            </div>

            {/* graphique */}
            {chartData.length > 0 && <WeatherChart data={chartData}/>}

            {/* hint défilement */}
            {days > 7 && (
              <div style={{
                textAlign: 'center', marginTop: 4,
                fontSize: 11, color: 'var(--g-sec)', fontStyle: 'italic',
              }}>
                ← glissez pour faire défiler →
              </div>
            )}

            {/* sélecteur période */}
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '0.5px solid var(--g-brd)' }}>
              <Segmented
                value={days}
                onChange={setDays}
                options={[
                  { v: 7,  l: '7 jours'  },
                  { v: 14, l: '14 jours' },
                  { v: 30, l: '30 jours' },
                ]}
              />
            </div>
          </>
        )}
      </GraphZone>

      {/* ─── Tuiles résumé cultures ─── */}
      {statsLoading ? (
        <LoadingSkeleton lines={3} />
      ) : statsError ? (
        <ApiError message={statsError} onRetry={loadStats} />
      ) : statsData && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-g-card border border-g-brd rounded-2xl p-4">
              <p className="text-4xl font-bold tracking-tight leading-none" style={{ color: 'var(--g-acc)' }}>
                {statsData.total_evenements}
              </p>
              <p className="text-[13px] mt-2" style={{ color: 'var(--g-sec)' }}>Événements total</p>
            </div>
            <div className="bg-g-card border border-g-brd rounded-2xl p-4">
              <p className="text-4xl font-bold tracking-tight leading-none" style={{ color: 'var(--g-pri)' }}>
                {statsData.arrosages?.nb || 0}
              </p>
              <p className="text-[13px] mt-2" style={{ color: 'var(--g-sec)' }}>Arrosages</p>
            </div>
          </div>

          {/* graphique plants par culture */}
          {stockChart.length > 0 && (
            <div className="bg-g-card border border-g-brd rounded-2xl p-4">
              <p className="text-sm font-medium mb-3" style={{ color: 'var(--g-sec)' }}>Plants par culture</p>
              <ResponsiveContainer width="100%" height={150}>
                <BarChart data={stockChart} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 10 }}
                    cursor={{ fill: 'var(--g-acc-dim)' }}
                  />
                  <Bar dataKey="plants" fill="var(--g-acc)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  )
}
