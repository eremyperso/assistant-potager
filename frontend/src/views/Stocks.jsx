// [US-073] Écran Stocks — vue transverse unique des cultures (au potager, en
// pépinière, en semis pleine terre), groupée par famille botanique — portage de
// `ScreenStocks` (`web-screens.jsx`, maquette 2026, gel du 15/08/2026) sur la
// donnée réelle exposée par `GET /stats/varietes` (US-072).
//
// Remplace intégralement l'ancien écran à 3 sections empilées (US-062, caduque) :
// la maquette gelée n'affiche aucun calendrier (`MonthStrip`, contrairement au
// prototype `ScreenCultures` antérieur) et fait de la famille botanique le seul
// regroupement principal — l'état (potager/pépinière/semis) devient un badge par
// ligne, cf. docs/BRIEF_REFONTE_STOCKS_TRANSVERSE.md.
import { useState, useEffect, useMemo } from 'react'
import { Leaf, Sprout, Scale, AlertTriangle, FileDown, FileJson, ChevronRight } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import { ObservationIcon, ObservationPanel } from '../components/Observations.jsx'
import { useObservations } from '../hooks/useObservations.js'
import { ObservationsUIProvider } from '../context/ObservationsUIContext.jsx'
import {
  Card, Badge, Tip, SearchField, Select, Btn, GroupHead, useGroups, Modal,
} from '../components/ui'
import { ChevronDown } from 'lucide-react'

/**
 * `SummaryBar` de la maquette (`web-parts.jsx`) : une seule carte, les repères en
 * ligne séparés par un filet vertical — pas une grille de tuiles `Stat` bordées
 * (ni `MetricStrip`, qui l'enveloppe). Même parti pris que `Reperes` dans
 * `Pepiniere.jsx` : la maquette ne met pas de tuiles `Stat` sur cet écran non plus.
 */
function SummaryBar({ items }) {
  return (
    <Card pad="p-3.5">
      <div className="flex items-center flex-wrap gap-y-2">
        {items.map(({ icon: Icon, tint = 'brand', value, unit, label, tip }, i) => (
          <div key={label} className={`flex items-center gap-1.5 px-4 ${i > 0 ? 'border-l border-border' : ''}`}>
            <Icon size={16} className={`text-${tint} shrink-0`} />
            <span className="text-[13px] text-txt2 whitespace-nowrap">
              <strong className="text-txt font-bold">{value}</strong>{unit ? ` ${unit}` : ''} {label}
            </span>
            {tip && <Tip text={tip} />}
          </div>
        ))}
      </div>
    </Card>
  )
}

/** Colonnes partagées par l'en-tête de colonnes, l'en-tête de famille et chaque
 * ligne de variété — c'est ce qui garde les totaux alignés sous les bonnes
 * colonnes (vue tableau, grand écran). */
const TABLE_COLS = 'grid grid-cols-[minmax(0,2fr)_150px_90px_84px_74px_74px_120px]'

// ── Constantes de référence — mêmes libellés que le calcul serveur (US-072) ────

const ETAT_CONFIG = {
  potager: { l: 'Au potager', t: 'brand' },
  pep:     { l: 'En pépinière', t: 'amber' },
  semis:   { l: 'Semis pleine terre', t: 'blue' },
}

const ORIGINE_LABELS = {
  'pépinière':          'Pépinière',
  'pied_acheté':        'Pied acheté',
  'semis_pleine_terre': 'Semis pleine terre',
  'non_localisé':       'Non localisé',
}

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

// ── Helpers ──────────────────────────────────────────────────────────────────

function iniOf(nom) {
  const c = (nom || '').normalize('NFD').replace(/\p{Diacritic}/gu, '')[0]
  return c ? c.toUpperCase() : '?'
}

/** [US-036] Le rendement pesé peut être exprimé en g (sous 1 kg cumulé) ou en kg
 * (au-delà) — voir `_best_g` côté serveur. Toujours affiché en kg à cet écran. */
function toKg(valeur, unite) {
  if (!valeur) return 0
  return unite === 'g' ? valeur / 1000 : valeur
}

const fmtKg = (v) => (Math.round(v * 100) / 100).toString().replace('.', ',')

function csvEscape(v) {
  const s = String(v ?? '')
  return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function downloadBlob(filename, content, mime) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const EXPORT_HEADERS = ['Culture', 'Variété', 'Famille', 'État', 'Origine', 'Parcelles', 'Unités', 'En place', 'Vendu', 'Perdu', 'Récolté (kg)']

function toExportRow(d) {
  return {
    culture:   d.culture,
    variete:   d.variete,
    famille:   d.fam,
    etat:      ETAT_CONFIG[d.etat]?.l ?? d.etat,
    origine:   ORIGINE_LABELS[d.origine] ?? d.origine,
    parcelles: d.parcelles.join(' | '),
    unites:    `${d.total_entre} ${d.unite}`,
    en_place:  d.stock_actuel,
    vendu:     d.vendu ?? '',
    perdu:     d.plants_perdus,
    recolte_kg: fmtKg(toKg(d.rendement_total, d.unite_rendement)),
  }
}

/** [CA1-CA3] Exports générés côté navigateur à partir des lignes déjà chargées et
 * actuellement visibles — jamais de nouvel appel serveur, jamais l'intégralité du
 * potager si un filtre est actif. */
function exportCSV(rows, dateRefEffective) {
  const lignes = rows.map(toExportRow)
  const csv = [
    EXPORT_HEADERS.join(';'),
    ...lignes.map((r) => Object.values(r).map(csvEscape).join(';')),
  ].join('\n')
  downloadBlob(`stocks-potager-${dateRefEffective}.csv`, '﻿' + csv, 'text/csv;charset=utf-8')
}

function exportJSON(rows, dateRefEffective) {
  const json = JSON.stringify(rows.map(toExportRow), null, 2)
  downloadBlob(`stocks-potager-${dateRefEffective}.json`, json, 'application/json')
}

// ── Cellule de métrique (reprend `SuiviNum` de la maquette) ────────────────────

function Metric({ value, unit, tint, sub, align = 'right' }) {
  const zero = !value
  const tone = zero ? 'text-txt3' : tint ? `text-${tint}` : 'text-txt'
  return (
    <div className={align === 'right' ? 'text-right' : ''}>
      <span className={`text-[14px] tabular-nums ${zero ? 'font-medium' : 'font-bold'} ${tone}`}>
        {zero ? '—' : String(value).replace('.', ',')}
        {!zero && unit && <em className="not-italic text-[11px] font-semibold text-txt3 ml-0.5">{unit}</em>}
      </span>
      {sub && <div className="text-[10.5px] text-txt3 mt-0.5">{sub}</div>}
    </div>
  )
}

// ── Lien + modale « N récolte(s) » (CA12-CA14) ──────────────────────────────────

function RecLink({ d, onOpen, dim }) {
  if (!d.nb_recoltes_poids) return <span className="text-[10.5px] text-txt3">non pesé</span>
  return (
    <button
      onClick={() => onOpen(d)}
      className={`bg-transparent border-none p-0 cursor-pointer font-sans font-semibold text-brand-text underline decoration-border underline-offset-2 ${dim ? 'text-[10.5px]' : 'text-[11.5px]'}`}
    >
      {d.nb_recoltes_poids} récolte{d.nb_recoltes_poids > 1 ? 's' : ''}
    </button>
  )
}

/** [CA13/CA14] Historique chronologique des récoltes pesées d'une variété précise,
 * isolée côté client depuis `GET /historique` (filtré par culture + action=recolte
 * côté serveur — la variété n'est pas un paramètre de cet endpoint). */
function ModalRecoltes({ d, onClose }) {
  const [evenements, setEvenements] = useState(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true); setError(null)
    api.historique({ culture: d.culture, action: 'recolte', limit: 100 })
      .then((res) => {
        setTotal(res.total)
        const varieteMatch = (v) => (v || 'Variété non précisée') === d.variete
        const pesees = (res.evenements || [])
          .filter((e) => varieteMatch(e.variete) && ['kg', 'g', 'mg'].includes((e.unite || '').toLowerCase()))
          .map((e) => ({ date: e.date, kg: e.unite === 'kg' ? e.quantite : e.quantite / (e.unite === 'mg' ? 1000000 : 1000) }))
          .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
        setEvenements(pesees)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [d.culture, d.variete])

  const cumule = (evenements || []).reduce((s, e) => s + e.kg, 0)
  // [CA14] `/historique` plafonne à 100 événements par page (toutes actions de
  // récolte de la culture, avant isolement de la variété) — au-delà, le total
  // affiché ci-dessous ne peut pas être garanti complet pour cette variété.
  const possiblementTronque = total > 100

  return (
    <Modal
      icon={Scale}
      title={`Récoltes — ${d.culture}`}
      sub={`${d.variete} · ${d.parcelles.join(' · ') || 'sans parcelle'}`}
      onClose={onClose}
      width={430}
      foot={!loading && !error && (
        <div className="flex items-baseline justify-between">
          <span className="text-[12.5px] text-txt2">
            {evenements.length} récolte{evenements.length > 1 ? 's' : ''} pesée{evenements.length > 1 ? 's' : ''}
          </span>
          <span className="font-serif text-[18px] font-bold text-txt">
            {fmtKg(cumule)}<em className="not-italic text-[12px] text-txt3 ml-1">kg</em>
          </span>
        </div>
      )}
    >
      {loading && <LoadingSkeleton lines={3} />}
      {error && <p className="text-sm text-red">{error}</p>}
      {!loading && !error && (
        <div>
          {possiblementTronque && (
            <div className="flex items-start gap-2 mb-3 rounded-xl px-3 py-2.5 bg-amber-soft text-amber text-[12px]">
              <AlertTriangle size={15} className="shrink-0 mt-0.5" />
              <span>
                Cette culture compte plus de 100 événements — l'historique ci-dessous peut être incomplet
                pour cette variété plutôt que d'afficher un total tronqué en silence.
              </span>
            </div>
          )}
          {evenements.length === 0 && (
            <p className="text-sm italic text-txt3">Aucune récolte pesée enregistrée pour cette variété.</p>
          )}
          {evenements.map((e, i) => {
            const max = Math.max(...evenements.map((x) => x.kg), 0.01)
            return (
              <div key={i} className="grid grid-cols-[86px_1fr_62px] items-center gap-2.5 py-2 border-b border-border-soft last:border-0">
                <span className="text-[12.5px] text-txt2">{e.date}</span>
                <span className="relative h-[7px] rounded bg-brand-soft">
                  <span className="absolute inset-y-0 left-0 rounded bg-brand" style={{ width: `${(e.kg / max) * 100}%` }} />
                </span>
                <span className="text-right text-[13.5px] font-bold tabular-nums text-txt">
                  {fmtKg(e.kg)}<em className="not-italic text-[10.5px] text-txt3 ml-0.5">kg</em>
                </span>
              </div>
            )
          })}
          <p className="mt-3.5 text-[12px] leading-relaxed text-txt3">
            Seules les récoltes pesées apparaissent ici. Une cueillette notée sans poids reste dans le journal
            mais ne compte pas dans le total.
          </p>
        </div>
      )}
    </Modal>
  )
}

// ── Ligne culture — tableau (grand écran) ───────────────────────────────────────

function StockTableRow({ d, onOpenRec }) {
  const obs = useObservations(`stocks:${d.culture}:${d.variete}`, { culture: d.culture })
  return (
    <div>
      <div className={`${TABLE_COLS} items-start gap-2.5 px-3 py-2.5 border-b border-border-soft`}>
        <div className="min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="font-serif text-[15.5px] font-semibold text-txt leading-tight">{d.culture}</span>
            <span className="font-serif italic text-[12.5px] text-txt3 leading-tight">{d.variete}</span>
            {d.has_observations && <ObservationIcon onClick={obs.toggle} active={obs.open} count={d.nb_observations} />}
          </div>
          <div className="flex gap-1.5 flex-wrap mt-1.5">
            <Badge tint={ETAT_CONFIG[d.etat].t}>{ETAT_CONFIG[d.etat].l}</Badge>
            <span className="inline-flex items-center text-[10.5px] font-bold uppercase tracking-wide text-txt2 bg-card-alt border border-border rounded px-1.5 py-0.5">
              {ORIGINE_LABELS[d.origine] ?? d.origine}
            </span>
          </div>
        </div>
        <div className="text-[12px] text-txt2 leading-relaxed">
          {d.parcelles.length > 0 ? d.parcelles.map((p) => <div key={p}>{p}</div>) : <span className="text-txt3">—</span>}
        </div>
        <Metric value={d.total_entre} sub={d.unite} />
        <Metric value={d.stock_actuel} />
        {d.vendu != null ? <Metric value={d.vendu} tint="violet" /> : <div />}
        <Metric value={d.plants_perdus} tint="red" />
        <Metric
          value={fmtKg(toKg(d.rendement_total, d.unite_rendement))}
          unit="kg"
          tint="amber"
          sub={<RecLink d={d} onOpen={onOpenRec} dim />}
        />
      </div>
      {d.has_observations && obs.open && <ObservationPanel items={obs.items} loading={obs.loading} />}
    </div>
  )
}

// ── Carte culture (petit écran) ──────────────────────────────────────────────

function StockCard({ d, onOpenRec }) {
  const obs = useObservations(`stocks:${d.culture}:${d.variete}`, { culture: d.culture })
  const recKg = fmtKg(toKg(d.rendement_total, d.unite_rendement))
  return (
    <Card pad="p-3.5">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0 flex items-baseline gap-1.5 flex-wrap">
          <span className="font-serif text-[16px] font-semibold text-txt">{d.culture}</span>
          <span className="font-serif italic text-[12.5px] text-txt3">{d.variete}</span>
        </div>
        {d.has_observations && <ObservationIcon onClick={obs.toggle} active={obs.open} count={d.nb_observations} />}
      </div>
      <div className="flex gap-1.5 flex-wrap my-2">
        <Badge tint={ETAT_CONFIG[d.etat].t}>{ETAT_CONFIG[d.etat].l}</Badge>
        <span className="inline-flex items-center text-[10.5px] font-bold uppercase tracking-wide text-txt2 bg-card-alt border border-border rounded px-1.5 py-0.5">
          {ORIGINE_LABELS[d.origine] ?? d.origine}
        </span>
      </div>
      <div className="text-[12px] text-txt2 mb-2.5">
        {d.parcelles.length > 0 ? d.parcelles.join(' · ') : 'Pépinière'}
      </div>
      <div className="grid grid-cols-5 gap-1.5 border-t border-border-soft pt-2.5">
        {[
          ['Unités', d.total_entre, null],
          ['En place', d.stock_actuel, null],
          ['Vendu', d.vendu, 'violet'],
          ['Perdu', d.plants_perdus, 'red'],
          ['Récolté', recKg, 'amber'],
        ].map(([l, v, t]) => {
          const absent = l === 'Vendu' && d.vendu == null
          return (
            <div key={l}>
              <div className="text-[9.5px] font-bold uppercase tracking-wide text-txt3">{l}</div>
              {absent ? (
                <div className="text-[15px]">&nbsp;</div>
              ) : (
                <div className={`text-[15px] ${!v ? 'font-medium text-txt3' : `font-bold ${t ? `text-${t}` : 'text-txt'}`}`}>
                  {v ? String(v).replace('.', ',') : '—'}
                  {l === 'Récolté' && v ? <em className="not-italic text-[10.5px] text-txt3"> kg</em> : ''}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <div className="flex items-center justify-between gap-2 mt-2.5 pt-2.5 border-t border-border-soft">
        <span className="text-[11.5px] text-txt3">
          {d.nb_recoltes_poids ? `${d.nb_recoltes_poids} récolte${d.nb_recoltes_poids > 1 ? 's' : ''} pesée${d.nb_recoltes_poids > 1 ? 's' : ''}` : 'aucune récolte pesée'}
        </span>
        {d.nb_recoltes_poids > 0 && (
          <button
            onClick={() => onOpenRec(d)}
            className="inline-flex items-center gap-1 bg-transparent border-none p-0 cursor-pointer font-sans text-[12.5px] font-semibold text-brand-text"
          >
            Détail des récoltes<ChevronRight size={14} />
          </button>
        )}
      </div>
      {d.has_observations && obs.open && <ObservationPanel items={obs.items} loading={obs.loading} />}
    </Card>
  )
}

// ── En-tête de famille — vue tableau, avec totaux (CA8) ─────────────────────────
// Équivalent de `famRow` dans la maquette : contrairement à `GroupHead` (utilisé
// tel quel pour les cartes, ci-dessous), cet en-tête porte aussi le nombre de
// parcelles distinctes et les 5 totaux du groupe, alignés sous les colonnes du
// tableau — il remplace `GroupHead` dans la vue grand écran plutôt que de s'y
// ajouter, sinon les totaux flotteraient sans en-tête de colonnes au-dessus.

function FamilleHeaderTable({ label, items, open, onToggle }) {
  const sum = (k) => items.reduce((s, d) => s + (d[k] || 0), 0)
  const nParcelles = new Set(items.flatMap((d) => d.parcelles)).size
  const recKg = fmtKg(items.reduce((s, d) => s + toKg(d.rendement_total, d.unite_rendement), 0))
  return (
    <button
      onClick={onToggle}
      aria-expanded={open}
      className={`w-full text-left ${TABLE_COLS} items-center gap-2.5 pt-3.5 pb-2 border-b border-border`}
    >
      <span className="flex items-center gap-2 min-w-0">
        <ChevronDown size={15} strokeWidth={2.2} className={`text-txt3 shrink-0 transition-transform duration-200 ${open ? '' : '-rotate-90'}`} />
        <Leaf size={18} className="text-brand shrink-0" />
        <span className="font-serif text-[19px] font-semibold text-txt tracking-tight truncate">{label}</span>
        <span className="text-[13px] text-txt3 shrink-0">({items.length})</span>
      </span>
      <span className="text-[11.5px] text-txt3">{nParcelles} parcelle{nParcelles > 1 ? 's' : ''}</span>
      <Metric value={sum('total_entre')} />
      <Metric value={sum('stock_actuel')} />
      <Metric value={sum('vendu')} tint="violet" />
      <Metric value={sum('plants_perdus')} tint="red" />
      <Metric value={recKg} unit="kg" tint="amber" />
    </button>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

const ORIGINE_OPTIONS = ['Toutes origines', 'Pépinière', 'Pied acheté', 'Semis pleine terre', 'Non localisé']

export default function Stocks({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId } = usePotager()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [q, setQ] = useState('')
  const [fam, setFam] = useState('Toutes')
  const [letter, setLetter] = useState(null)
  const [origineFiltre, setOrigineFiltre] = useState('Toutes origines')
  const [rec, setRec] = useState(null)
  const [isOpen, toggle] = useGroups()

  async function load() {
    setLoading(true); setError(null)
    try { setData(await api.statsVarietes(dateRef, potagerId)) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh, dateRef, potagerId])

  // [US-067 / CA5, CA6, CA8] La famille vient de GET /stats/varietes
  // (culture_config → familles_botaniques côté serveur), plus de familles.js.
  const varietes = useMemo(() => (data?.varietes ?? []).map((d) => ({ ...d, fam: d.famille || 'Autres' })), [data])

  const fams = useMemo(() => [...new Set(varietes.map((d) => d.fam))].sort((a, b) =>
    a === 'Autres' ? 1 : b === 'Autres' ? -1 : a.localeCompare(b)), [varietes])

  const base = useMemo(() => varietes.filter((d) => fam === 'Toutes' || d.fam === fam), [varietes, fam])
  const activeLetters = useMemo(() => new Set(base.map((d) => iniOf(d.culture))), [base])

  const list = useMemo(() => {
    const q2 = q.toLowerCase()
    return base.filter((d) => {
      if (q2 && !`${d.culture} ${d.variete}`.toLowerCase().includes(q2)) return false
      if (letter && iniOf(d.culture) !== letter) return false
      if (origineFiltre !== 'Toutes origines' && (ORIGINE_LABELS[d.origine] ?? d.origine) !== origineFiltre) return false
      return true
    })
  }, [base, q, letter, origineFiltre])

  const dateRefEffective = data?.date_ref_effective || new Date().toISOString().slice(0, 10)

  // [CA4] Le bandeau reflète tout le potager à la date de référence, indépendamment
  // des filtres de recherche/famille/lettre/origine — même parti pris que la maquette.
  const uniteAuPotager = varietes.filter((d) => d.etat === 'potager').reduce((s, d) => s + (d.stock_actuel || 0), 0)
  const godetsAReplanter = varietes.filter((d) => d.etat === 'pep').reduce((s, d) => s + (d.stock_actuel || 0), 0)
  const kgRecoltes = varietes.reduce((s, d) => s + toKg(d.rendement_total, d.unite_rendement), 0)
  const unitesPerdues = varietes.reduce((s, d) => s + (d.plants_perdus || 0), 0)

  if (loading) return <LoadingSkeleton lines={4} />
  if (error) return <ApiError message={error} onRetry={load} />

  const filtres = (
    <div className="@container/filtres flex items-center gap-2 flex-wrap">
      <SearchField
        value={q}
        onChange={setQ}
        placeholder="Rechercher une culture, une variété…"
        className="relative basis-full order-last min-w-0 @[34rem]/filtres:basis-0 @[34rem]/filtres:flex-1 @[34rem]/filtres:order-none"
      />
      <DateRefPicker />
      <Select
        value={origineFiltre}
        options={ORIGINE_OPTIONS}
        onChange={setOrigineFiltre}
        aria-label="Filtrer par origine"
      />
      <span className="flex gap-1.5 ml-auto">
        <Btn small icon={FileDown} onClick={() => exportCSV(list, dateRefEffective)} title="Exporter en CSV">CSV</Btn>
        <Btn small icon={FileJson} onClick={() => exportJSON(list, dateRefEffective)} title="Exporter en JSON">JSON</Btn>
      </span>
    </div>
  )

  if (!varietes.length) return (
    <div className="flex flex-col gap-3.5">
      {filtres}
      <div className="flex flex-col items-center gap-2 mt-12 text-txt3">
        <Leaf size={36} />
        <p className="text-base">Aucun stock enregistré.</p>
      </div>
    </div>
  )

  return (
    <ObservationsUIProvider>
      <div className="flex flex-col gap-3.5">
        {filtres}

        <SummaryBar
          items={[
            { icon: Leaf, value: uniteAuPotager, label: 'unités au potager', tip: 'Pieds, gousses ou godets réellement en place à la date de référence.' },
            { icon: Sprout, tint: 'amber', value: godetsAReplanter, label: 'godets à replanter' },
            { icon: Scale, tint: 'amber', value: fmtKg(kgRecoltes), unit: 'kg', label: 'récoltés en 2026' },
            { icon: AlertTriangle, tint: 'red', value: unitesPerdues, label: 'unités perdues', tip: 'Pieds ou godets déclarés perdus : non germés, arrachés, malades.' },
          ]}
        />

        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10.5px] font-bold uppercase tracking-wide text-txt3 mr-1 flex items-center gap-1">
            Famille
            <Tip text="La famille botanique est le regroupement principal de cet écran : c'est elle qui commande les rotations de culture." />
          </span>
          {['Toutes', ...fams].map((f) => {
            const on = f === fam
            const n = f === 'Toutes' ? varietes.length : varietes.filter((d) => d.fam === f).length
            return (
              <button
                key={f}
                onClick={() => { setFam(f); setLetter(null) }}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12.5px] cursor-pointer border ${
                  on ? 'bg-brand border-brand text-white dark:text-bg font-bold' : 'bg-card border-border text-txt2 font-medium'
                }`}
              >
                {f}<span className="opacity-70">{n}</span>
              </button>
            )
          })}
        </div>

        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-[10.5px] font-bold uppercase tracking-wide text-txt3 mr-1">Lettre</span>
          <button
            onClick={() => setLetter(null)}
            title="Toutes les lettres"
            className={`min-w-[26px] h-6 rounded-md text-[11.5px] font-bold cursor-pointer border ${
              letter === null ? 'bg-card border-border text-txt' : 'border-transparent text-txt3'
            }`}
          >
            Tout
          </button>
          {ALPHABET.map((L) => {
            const active = activeLetters.has(L)
            const on = letter === L
            return (
              <button
                key={L}
                disabled={!active}
                onClick={() => setLetter(on ? null : L)}
                className={`w-6 h-6 rounded-md text-[12px] border-none ${active ? 'cursor-pointer' : 'cursor-default'} ${
                  on ? 'bg-brand text-white dark:text-bg font-bold' : active ? 'text-brand-text font-bold' : 'text-txt3 opacity-35'
                }`}
              >
                {L}
              </button>
            )
          })}
        </div>

        {/* [CA9/CA10] `@container/wsui` : bascule tableau ↔ cartes pilotée par la
            largeur du conteneur, jamais par un breakpoint d'écran — mêmes deux
            branches que `wsui-table`/`wsui-cards` dans la maquette, l'une des
            deux toujours masquée par `hidden`/`block` selon le container. */}
        <div className="@container/wsui">
          {!list.length ? (
            <p className="text-center text-[13px] text-txt3 py-8">Aucune culture pour ce filtre.</p>
          ) : (
            <>
              {/* Tableau — grand écran */}
              <div className="hidden @[56rem]/wsui:block">
                <div className={`${TABLE_COLS} gap-2.5 px-3 pb-1.5 border-b-2 border-txt2 text-[10.5px] font-bold uppercase tracking-wide text-txt3`}>
                  <div>Culture / variété · origine</div><div>Parcelles</div>
                  <div className="text-right">Unités</div><div className="text-right">En place</div>
                  <div className="text-right">Vendu</div><div className="text-right">Perdu</div>
                  <div className="text-right">Récolté</div>
                </div>
                {fams.filter((f) => fam === 'Toutes' || f === fam).map((f) => {
                  const items = list.filter((d) => d.fam === f)
                  if (!items.length) return null
                  return (
                    <div key={f}>
                      <FamilleHeaderTable label={f} items={items} open={isOpen(f)} onToggle={() => toggle(f)} />
                      {isOpen(f) && items.map((d, i) => <StockTableRow key={`${d.culture}-${d.variete}-${i}`} d={d} onOpenRec={setRec} />)}
                    </div>
                  )
                })}
              </div>
              {/* Cartes — petit écran */}
              <div className="@[56rem]/wsui:hidden flex flex-col gap-3.5">
                {fams.filter((f) => fam === 'Toutes' || f === fam).map((f) => {
                  const items = list.filter((d) => d.fam === f)
                  if (!items.length) return null
                  return (
                    <div key={f}>
                      <GroupHead
                        label={f}
                        count={items.length}
                        open={isOpen(f)}
                        onToggle={() => toggle(f)}
                        right={`${items.reduce((s, d) => s + (d.stock_actuel || 0), 0)} en place`}
                      />
                      {isOpen(f) && (
                        <div className="flex flex-col gap-2.5">
                          {items.map((d, i) => <StockCard key={`${d.culture}-${d.variete}-${i}`} d={d} onOpenRec={setRec} />)}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>

      {rec && <ModalRecoltes d={rec} onClose={() => setRec(null)} />}
    </ObservationsUIProvider>
  )
}
