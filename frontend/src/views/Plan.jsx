import { useState, useEffect } from 'react'
import { MapPin, Sun, Cloud, Leaf } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import CultureFilter from '../components/CultureFilter.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'

// ── Helpers ──────────────────────────────────────────────────────────────────

function occAccent(pct) {
  if (pct >= 80) return 'var(--g-red)'
  if (pct >= 55) return 'var(--g-amb)'
  return 'var(--g-acc)'
}

function occTextCls(pct) {
  if (pct >= 80) return 'text-g-red'
  if (pct >= 55) return 'text-g-amb'
  return 'text-g-acc'
}

function ExpositionIcon({ exposition }) {
  if (!exposition) return null
  const e = (exposition || '').toLowerCase()
  const Icon = e.includes('ombre') ? Cloud : Sun
  return <Icon size={13} className="text-g-amb" aria-hidden="true" />
}

// ── Carte parcelle ────────────────────────────────────────────────────────────

function ParcellCard({ parcelle }) {
  const { nom, exposition, superficie_m2, cultures, occupation_pct } = parcelle
  const libre    = cultures.length === 0
  const accent   = occAccent(occupation_pct ?? 0)
  const textCls  = occTextCls(occupation_pct ?? 0)
  const pct      = occupation_pct ?? 0

  return (
    <div
      className="bg-g-card border border-g-brd rounded-2xl overflow-hidden flex mb-3"
      style={{ flexShrink: 0 }}
    >
      {/* Barre accent gauche */}
      <div style={{ width: 5, flexShrink: 0, background: accent }} />

      {/* Corps */}
      <div className="flex-1 p-3.5">

        {/* En-tête : nom + compteur cultures */}
        <div className="flex items-start justify-between gap-2 mb-1">
          <div className="flex items-center gap-2">
            <MapPin size={15} className="text-g-acc flex-shrink-0 mt-0.5" aria-hidden="true" />
            <span className="text-[19px] font-semibold text-g-pri font-serif tracking-tight leading-tight">
              {nom}
            </span>
          </div>
          {!libre ? (
            <div className="text-right flex-shrink-0">
              <span className={`text-[28px] font-bold leading-none tracking-tight ${textCls}`}>
                {cultures.length}
              </span>
              <div className="text-[11px] text-g-sec mt-0.5">cultures</div>
            </div>
          ) : (
            <span className="text-sm font-medium px-2 py-0.5 rounded-full bg-g-acc-dim text-g-mid">
              Libre
            </span>
          )}
        </div>

        {/* Expo + surface */}
        {(exposition || superficie_m2) && (
          <div className="flex items-center gap-2 mb-3 pl-6 text-[13px] text-g-sec">
            <ExpositionIcon exposition={exposition} />
            {exposition && <span>{exposition}</span>}
            {superficie_m2 && <span>· {superficie_m2} m²</span>}
          </div>
        )}

        {/* Séparateur */}
        {!libre && <div className="h-px bg-g-brd mb-3" />}

        {/* Liste des cultures */}
        {!libre && (
          <div className="space-y-2.5">
            {cultures.map((c, i) => (
              <div key={i} className="flex items-center gap-2.5">
                <div
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ background: c.type_organe === 'végétatif' ? 'var(--g-acc)' : 'var(--g-amb)' }}
                />
                <span className="flex-1 text-base text-g-pri font-serif font-medium capitalize leading-snug">
                  {c.culture}
                  {c.variete && (
                    <span className="italic text-g-sec ml-1.5 text-[15px]">{c.variete}</span>
                  )}
                </span>
                {c.nb_plants > 0 && (
                  <span className="text-[15px] text-g-mid font-semibold">{c.nb_plants}</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Barre de progression */}
        {pct > 0 && (
          <div className="mt-3.5">
            <div className="h-1.5 bg-g-brd rounded-full overflow-hidden mb-1.5">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${pct}%`, background: accent }}
              />
            </div>
            <span className="text-[12px] text-g-sec">{pct}% de la surface occupée</span>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Plan({ refresh }) {
  const { dateRef } = useDateRef()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [search, setSearch]   = useState('')  // [CA17-CA19] filtre local, non persisté

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.plan(dateRef))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [refresh, dateRef])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error)   return <ApiError message={error} onRetry={load} />

  const parcelles = data?.parcelles ?? []
  const q = search.toLowerCase()

  // [CA18] Filtre côté client
  const filtered = q
    ? parcelles.map(p => ({
        ...p,
        cultures: p.cultures.filter(c =>
          (c.culture || '').toLowerCase().includes(q) ||
          (c.variete  || '').toLowerCase().includes(q)
        ),
      })).filter(p => p.nom.toLowerCase().includes(q) || p.cultures.length > 0)
    : parcelles

  const nbActives  = filtered.filter(p => p.cultures.length > 0).length
  const nbCultures = filtered.reduce((s, p) => s + p.cultures.length, 0)

  return (
    <div>
      {/* [CA5+CA17] Filtres combinés côte à côte */}
      <div className="flex items-center gap-2 mb-3">
        <DateRefPicker />
        <CultureFilter value={search} onChange={setSearch} className="relative flex-1" />
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-3 mt-12 text-g-sec">
          <Leaf size={36} />
          <p className="text-base">{search ? 'Aucune culture correspondante.' : 'Aucune parcelle enregistrée.'}</p>
        </div>
      ) : (
        <>
          {/* Métriques */}
          <div className="flex gap-2 mb-3">
            <div className="flex-1 bg-g-acc-dim border border-g-brd rounded-2xl p-3.5 text-center">
              <p className="text-4xl font-bold text-g-acc leading-none tracking-tight">{nbActives}</p>
              <p className="text-[12px] text-g-mid mt-1.5">parcelles actives</p>
            </div>
            <div className="flex-1 bg-g-card border border-g-brd rounded-2xl p-3.5 text-center">
              <p className="text-4xl font-bold text-g-pri leading-none tracking-tight">{nbCultures}</p>
              <p className="text-[12px] text-g-sec mt-1.5">cultures en place</p>
            </div>
          </div>

          {/* Légende */}
          <div className="flex gap-4 mb-3 text-[13px] text-g-sec">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-g-acc inline-block" />
              végétatif
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-g-amb inline-block" />
              reproducteur
            </span>
          </div>

          {/* Cartes */}
          {filtered.map((p, i) => <ParcellCard key={i} parcelle={p} />)}
        </>
      )}
    </div>
  )
}
