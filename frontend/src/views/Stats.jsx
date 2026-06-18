import { useState, useEffect, useRef } from 'react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import { useTheme } from '../hooks/useTheme.js'
import DateRefPicker from '../components/DateRefPicker.jsx'
import CultureFilter from '../components/CultureFilter.jsx'

// ─── constantes ───────────────────────────────────────────────────────────────
const WD = ['D', 'L', 'M', 'M', 'J', 'V', 'S']
const MO = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const ACT_MO = ['Janv', 'Févr', 'Mars', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sept', 'Oct', 'Nov', 'Déc']
const CS = 12, CG = 2, CST = 14, MH = 16   // dimensions cases heatmap activité

// ─── 5 paliers de chaleur (couleurs dark / light) ─────────────────────────────
const HEAT = [
  { max: 20, dark: '#3E9E46', light: '#347D2C', label: 'frais',       range: '< 20°'  },
  { max: 24, dark: '#8EC452', light: '#5FA02E', label: 'doux',        range: '20–23°' },
  { max: 28, dark: '#E2B53C', light: '#C2941A', label: 'chaud',       range: '24–27°' },
  { max: 31, dark: '#E07B2E', light: '#C2691A', label: 'très chaud',  range: '28–30°' },
  { max: 99, dark: '#D6493B', light: '#B2362A', label: 'caniculaire', range: '≥ 31°'  },
]
function heatColor(t, isDark) {
  const cat = HEAT.find(h => t < h.max) || HEAT[HEAT.length - 1]
  return isDark ? cat.dark : cat.light
}

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

function HeatScale() {
  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 8, marginBottom: 7, paddingInline: 2,
      }}>
        <span style={{ fontSize: 12, color: 'var(--g-sec)' }}>Niveau de chaleur (max du jour)</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--g-sec)', flexShrink: 0 }}>
          <span style={{ display: 'inline-block', width: 11, height: 11, borderRadius: 3, background: 'var(--g-rain)' }}/>
          précip. (mm)
        </span>
      </div>
      <div style={{ display: 'flex', gap: 3 }}>
        {HEAT.map((h, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <div style={{
              width: '100%', height: 13, borderRadius: 4,
              background: `var(--heat-${i}, ${h.dark})`,
            }}/>
            <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--g-sec)', lineHeight: 1 }}>{h.range}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function WeatherChart({ data, isDark }) {
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
          {/* dégradé par barre : couleur du palier min (bas/matin) → max (haut/pic) */}
          <defs>
            {data.map((p, i) => (
              <linearGradient key={i} id={`wx-heat-${i}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor={heatColor(p.tmax, isDark)}/>
                <stop offset="100%" stopColor={heatColor(p.tmin, isDark)}/>
              </linearGradient>
            ))}
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

          {/* barres temp min–max avec dégradé dynamique par palier */}
          {data.map((p, i) => (
            <rect
              key={i}
              x={x(i) - bw / 2}
              y={ty(p.tmax)}
              width={bw}
              height={Math.max(2, ty(p.tmin) - ty(p.tmax))}
              rx={bw / 2}
              fill={`url(#wx-heat-${i})`}
            />
          ))}

          {/* étiquettes temp colorées par palier */}
          {data.map((p, i) => (
            <g key={i}>
              <text x={x(i)} y={ty(p.tmax) - 7}  textAnchor="middle" fontSize="11" fontWeight="700" fill={heatColor(p.tmax, isDark)}>{p.tmax}</text>
              <text x={x(i)} y={ty(p.tmin) + 14} textAnchor="middle" fontSize="11" fontWeight="700" fill={heatColor(p.tmin, isDark)}>{p.tmin}</text>
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

function actColor(n, isDark) {
  if (n <= 0) return 'var(--g-brd)'
  if (n === 1) return isDark ? '#253D18' : '#C5DCAA'
  if (n === 2) return isDark ? '#3D6020' : '#9DC45A'
  if (n === 3) return isDark ? '#5A8A2E' : '#72A838'
  if (n === 4) return isDark ? '#78B040' : '#4A8828'
  return 'var(--g-acc)'
}

function ActivityHeatmap({ jours, annee, dateRef, isDark }) {
  const scrollRef = useRef(null)

  const today = new Date()
  const yEnd = dateRef
    ? new Date(dateRef + 'T12:00:00')
    : (today.getFullYear() === annee ? today : new Date(annee, 11, 31))
  const yStart = new Date(annee, 0, 1)

  // Aligner sur lundi (Mon=0)
  const startDow = (yStart.getDay() + 6) % 7
  const origin = new Date(yStart)
  origin.setDate(origin.getDate() - startDow)

  const weeks = []
  for (let cur = new Date(origin); cur <= yEnd; cur.setDate(cur.getDate() + 7)) {
    const week = []
    for (let di = 0; di < 7; di++) {
      const dt = new Date(cur)
      dt.setDate(dt.getDate() + di)
      const inRange = dt >= yStart && dt <= yEnd
      const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
      week.push({ inRange, count: inRange ? (jours[key] || 0) : -1, month: dt.getMonth() })
    }
    weeks.push(week)
  }

  const seen = new Set()
  const monthLabels = []
  weeks.forEach((w, wi) => {
    const first = w.find(d => d.inRange)
    if (first && !seen.has(first.month)) {
      seen.add(first.month)
      monthLabels.push({ label: ACT_MO[first.month], x: wi * CST })
    }
  })

  const svgW = weeks.length * CST
  const svgH = MH + 7 * CST - CG
  const total = Object.values(jours).reduce((s, v) => s + v, 0)
  const active = Object.values(jours).filter(v => v > 0).length

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <StatTile value={total} label="actions totales" color="var(--g-acc)" bg="var(--g-acc-dim)"/>
        <StatTile value={active} label="jours actifs"/>
        <StatTile value={active ? (total / active).toFixed(1) : 0} label="moy./j. actif" color="var(--g-amb)"/>
      </div>

      <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
        {/* labels jour */}
        <div style={{ flexShrink: 0, paddingTop: MH + CG, display: 'flex', flexDirection: 'column', gap: CG }}>
          {['L', 'M', 'M', 'J', 'V', 'S', 'D'].map((l, i) => (
            <div key={i} style={{ height: CS, width: 12, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
              {i % 2 === 0 && <span style={{ fontSize: 9, color: 'var(--g-sec)' }}>{l}</span>}
            </div>
          ))}
        </div>
        {/* grille scrollable */}
        <div ref={scrollRef} style={{ flex: 1, overflowX: 'auto' }}>
          <svg width={svgW} height={svgH} style={{ display: 'block' }}>
            {monthLabels.map(({ label, x }) => (
              <text key={label} x={x} y={12} fontSize="10" fontWeight="600" fill="var(--g-acc)">{label}</text>
            ))}
            {weeks.map((week, wi) =>
              week.map((day, di) => day.inRange ? (
                <rect key={`${wi}-${di}`} x={wi * CST} y={MH + di * CST} width={CS} height={CS} rx={3} fill={actColor(day.count, isDark)}/>
              ) : null)
            )}
          </svg>
        </div>
      </div>

      {/* légende avec valeurs */}
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {[0, 1, 2, 3, 4, 5].map(v => (
            <div key={v} style={{ width: CS, height: CS, borderRadius: 3, flexShrink: 0, background: actColor(v, isDark) }}/>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {['0', '1', '2', '3', '4', '5+'].map((l, i) => (
            <div key={i} style={{ width: CS, textAlign: 'center', fontSize: 9, color: 'var(--g-sec)', flexShrink: 0 }}>{l}</div>
          ))}
        </div>
        <span style={{ fontSize: 10, color: 'var(--g-sec)', fontStyle: 'italic' }}>nombre d'actions par jour</span>
      </div>
    </div>
  )
}

// ─── vue principale ───────────────────────────────────────────────────────────

export default function Stats({ refresh }) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const { dateRef } = useDateRef()

  const [meteo, setMeteo]           = useState(null)
  const [meteoLoading, setMeteoLoading] = useState(true)
  const [meteoError, setMeteoError] = useState(null)
  const [days, setDays]             = useState(7)

  const [search, setSearch]         = useState('')   // filtre commun (cohérence avec les autres onglets)

  const [activite, setActivite]         = useState(null)
  const [activiteLoading, setActiviteLoading] = useState(true)
  const [activiteError, setActiviteError]     = useState(null)
  const activiteAnnee = dateRef
    ? new Date(dateRef + 'T12:00:00').getFullYear()
    : new Date().getFullYear()

  async function loadMeteo() {
    setMeteoLoading(true); setMeteoError(null)
    try   { setMeteo(await api.meteoHistory(days)) }
    catch (e) { setMeteoError(e.message) }
    finally   { setMeteoLoading(false) }
  }

  async function loadActivite() {
    setActiviteLoading(true); setActiviteError(null)
    try   { setActivite(await api.activite(activiteAnnee, dateRef)) }
    catch (e) { setActiviteError(e.message) }
    finally   { setActiviteLoading(false) }
  }

  useEffect(() => { loadMeteo() }, [days])
  useEffect(() => { loadActivite() }, [refresh, dateRef, activiteAnnee])

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

  return (
    <div className="space-y-3">
      {/* [filtre commun] cohérent avec Plan/Pépinière/etc. */}
      <div className="flex items-center gap-2 mb-1">
        <DateRefPicker />
        <CultureFilter value={search} onChange={setSearch} className="relative flex-1" />
      </div>

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
              <StatTile value={tmaxP ?? '—'} unit="°" label="max"      color={tmaxP != null ? heatColor(tmaxP, isDark) : 'var(--g-sec)'}/>
              <StatTile value={tminP ?? '—'} unit="°" label="min"      color={tminP != null ? heatColor(tminP, isDark) : 'var(--g-sec)'}/>
              <StatTile
                value={Math.round(totPluie * 10) / 10}
                unit="mm" label="pluie"
                color="var(--g-rain)" bg="var(--g-rain-dim)"
              />
              <StatTile value={joursPluie} unit="j" label="j. pluie"/>
            </div>

            {/* légende paliers de chaleur */}
            <div style={{ marginBottom: 10 }}>
              <HeatScale/>
            </div>

            {/* graphique */}
            {chartData.length > 0 && <WeatherChart data={chartData} isDark={isDark}/>}

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

      {/* ─── Activité potager ─── */}
      <GraphZone
        icon={
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
            stroke="var(--g-acc)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8"  y1="2" x2="8"  y2="6"/>
            <line x1="3"  y1="10" x2="21" y2="10"/>
            <polyline points="8 14 10 16 14 12"/>
          </svg>
        }
        title="Activité potager"
        subtitle={`Intensité quotidienne des actions · ${activiteAnnee}`}
      >
        {activiteLoading ? (
          <div style={{ height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--g-sec)' }}>Chargement…</span>
          </div>
        ) : activiteError ? (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <span style={{ fontSize: 13, color: 'var(--g-red)' }}>{activiteError}</span>
            <button
              onClick={loadActivite}
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
          <ActivityHeatmap
            jours={activite?.jours || {}}
            annee={activiteAnnee}
            dateRef={dateRef}
            isDark={isDark}
          />
        )}
      </GraphZone>
    </div>
  )
}
