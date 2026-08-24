// [US-061] Écran Pépinière — portage de `ScreenPep` (`web-screens.jsx`, maquette
// 2026) sur les données réelles par lot de semis exposées par `GET /pepiniere/lots`
// (US-065). La mise en forme suit la maquette ; les fonctions qu'elle ne connaît
// pas (date de référence, panneau de traçabilité, états de germination) sont
// conservées et logées dans ses composants plutôt que réinventées.
import { useState, useEffect, useMemo } from 'react'
import { Sprout, Leaf, BarChart3 } from 'lucide-react'
import { api } from '../lib/api.js'
import { familleDe } from '../lib/familles.js'
import { stades, phaseGermination, tauxTint, stadeCourant, stadeAvancement, joursDepuis } from '../lib/pepiniere.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import DateRefPicker from '../components/DateRefPicker.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import {
  Card, Badge, Tip, SearchField, Select, GroupHead, useGroups, InfoBanner, Modal,
} from '../components/ui'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(dateStr) {
  if (!dateStr) return '—'
  const [y, m, d] = dateStr.split('-')
  return `${d}/${m}/${y}`
}

const pluriel = (n, mot, suffixe = 's') => `${n} ${mot}${n > 1 ? suffixe : ''}`

/** Les trois stades de la frise, dans l'ordre — libellés et teintes de la maquette. */
const PEP_STADES = [
  { l: 'Germin.', bg: 'bg-blue', txt: 'text-blue', tint: 'blue' },
  { l: 'Godet', bg: 'bg-amber', txt: 'text-amber', tint: 'amber' },
  { l: 'Terre', bg: 'bg-brand', txt: 'text-brand', tint: 'brand' },
]

const TRIS = ['Récent → Ancien', 'Ancien → Récent', 'Culture A → Z']

// ── Frise des trois stades ────────────────────────────────────────────────────

/**
 * Trois segments côte à côte, comme `StageBar` dans la maquette : le stade
 * courant porte une pastille à la hauteur de son remplissage et voit son
 * libellé passer en gras coloré.
 *
 * Seule différence avec la maquette, qui est un prototype à données figées : les
 * remplissages sont les pourcentages réels du lot (règle du CA2), pas les
 * 100 / 62 / 0 codés en dur du prototype.
 */
function StageBar({ st, fills }) {
  // La pastille ne saute sur le stade d'avancement (`st`) que s'il a
  // réellement commencé (remplissage > 0). Sinon — un lot « sans semis
  // rattaché » qui n'a encore rien sorti de son godet, par exemple — elle
  // reste posée, avec sa couleur, sur le dernier stade qui, lui, est rempli :
  // sauter sur un segment à 0 % la placerait pile à la jonction des deux
  // segments, une position ambiguë entre les deux couleurs.
  let pastille = st
  while (pastille > 0 && (fills[pastille] ?? 0) <= 0) pastille -= 1

  return (
    <div>
      <div className="flex gap-[3px] items-center">
        {PEP_STADES.map((s, i) => {
          const fill = Math.max(0, Math.min(100, fills[i] ?? 0))
          return (
            <div key={s.l} className="flex-1 relative h-[5px] rounded-[3px] bg-card-alt">
              <div className={`absolute inset-y-0 left-0 rounded-[3px] ${s.bg}`} style={{ width: `${fill}%` }} />
              {/* Pastille de position, centrée sur le point d'avancement — y compris
                  à 0 % ou 100 %, bords compris : `box-content` ajoute la bordure de
                  2px de chaque côté au 9px de contenu (soit 13px au total), le
                  décalage de centrage doit donc être la moitié de 13, pas de 9 —
                  l'ancien -4.5px décalait la pastille hors du centre réel de la barre.
                  À 100 %, elle déborde du segment courant sur le suivant : les deux
                  divs de segment sont `relative` (donc positionnés), le suivant vient
                  après dans le DOM et peint par-dessus à z-index égal — sans `z-10`
                  la pastille se retrouve à moitié recouverte, coupée en croissant. */}
              {i === pastille && (
                <span
                  className={`absolute z-10 top-1/2 w-[9px] h-[9px] -mt-[6.5px] -ml-[6.5px] rounded-full border-2 border-card box-content ${s.bg}`}
                  style={{ left: `${fill}%` }}
                />
              )}
            </div>
          )
        })}
      </div>
      <div className="flex gap-[3px] mt-[5px]">
        {PEP_STADES.map((s, i) => (
          <span
            key={s.l}
            className={`flex-1 text-[9.5px] ${i === 0 ? 'text-left' : i === 2 ? 'text-right' : 'text-center'} ${
              i === st ? `font-bold ${s.txt}` : 'font-medium text-txt3'
            }`}
          >
            {s.l}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Compteur circulaire de plants disponibles ────────────────────────────────

/** `PlantDonut` de la maquette : anneau `brand` uni, piste à 22 % d'opacité. */
function PlantDonut({ restants, total, size = 54 }) {
  const pct = total > 0 ? Math.round((restants / total) * 100) : 0
  const c = size / 2, R = c - 5, SW = 5, C = 2 * Math.PI * R

  return (
    <svg width={size} height={size} className="shrink-0 block text-brand">
      <circle cx={c} cy={c} r={R} fill="none" stroke="currentColor" strokeOpacity=".22" strokeWidth={SW} />
      <circle
        cx={c} cy={c} r={R}
        fill="none" stroke="currentColor" strokeWidth={SW} strokeLinecap="round"
        strokeDasharray={`${(pct / 100) * C} ${C}`}
        transform={`rotate(-90 ${c} ${c})`}
      />
      <text x={c} y={c - 2} textAnchor="middle" dominantBaseline="middle" fontSize="15" fontWeight="700" fill="currentColor" letterSpacing="-.5">
        {restants}
      </text>
      <text x={c} y={c + 9} textAnchor="middle" dominantBaseline="middle" fontSize="8" fontWeight="600" fill="currentColor" opacity=".72">
        dispo
      </text>
    </svg>
  )
}

// ── Décomposition du lot ──────────────────────────────────────────────────────

/**
 * `PlantRatio` de la maquette : le total du lot, puis ce qui en est sorti, une
 * pastille carrée par destination.
 *
 * [CA6] Ventes et pertes figurent ici en clair — l'écart à 100 % des barres
 * reste explicable. Le prototype affichait « N semés » là où il énumérait en
 * réalité des plants ; sur données réelles, graines semées et plants obtenus ne
 * coïncident pas, les deux sont donc distingués.
 */
function PlantRatio({ st }) {
  const segs = [
    { k: 'terre', n: st.T, l: 'mis en terre', dot: 'bg-blue' },
    { k: 'vendus', n: st.V, l: 'vendus', dot: 'bg-violet' },
    { k: 'perdus', n: st.L, l: 'perdus', dot: 'bg-red' },
  ].filter((s) => s.n > 0)

  return (
    <div className="flex gap-2.5 flex-wrap items-center">
      {st.S > 0 && <span className="text-[11.5px] text-txt3">{st.S} semés</span>}
      <span className="text-[11.5px] text-txt3">{st.P} obtenus</span>
      {segs.map((s) => (
        <span key={s.k} className="inline-flex items-center gap-1 text-[11.5px] text-txt2">
          <span className={`w-[7px] h-[7px] rounded-[2px] shrink-0 ${s.dot}`} />
          <strong className="font-bold text-txt">{s.n}</strong> {s.l}
        </span>
      ))}
    </div>
  )
}

// ── Carte de lot ──────────────────────────────────────────────────────────────

function LotCard({ lot, onOpen }) {
  const st = stades(lot)
  const stade = stadeCourant(lot, st)
  const pastilleStade = stadeAvancement(lot, st)
  const ph = phaseGermination(lot, st)
  const jours = joursDepuis(lot.date_semis)

  return (
    <button
      onClick={onOpen}
      className="text-left bg-card border border-border rounded-[14px] shadow-card overflow-hidden flex flex-col active:scale-[0.99] transition-transform"
    >
      <div className="px-[13px] pt-[13px]">
        <Badge tint={PEP_STADES[stade].tint} solid>{stade === 0 ? 'Germination' : PEP_STADES[stade].l}</Badge>
        <div className="flex items-center gap-2.5 mt-2.5">
          <div className="flex-1 min-w-0">
            <div className="font-serif text-[16px] font-semibold text-txt truncate capitalize">{lot.culture}</div>
            <div className="font-serif italic text-[12.5px] text-txt2 truncate">
              {lot.variete || 'Variété non spécifiée'}
            </div>
          </div>
          <PlantDonut restants={st.G} total={st.P} />
        </div>
      </div>

      <div className="p-[13px] flex flex-col gap-[11px]">
        <div className="flex items-center justify-between gap-2">
          {/* [CA4] Un lot = un semis, identifié par sa date ; les godets sans semis
              parent forment une carte explicitement libellée comme telle. */}
          <span className="text-[12.5px] text-txt2">
            {lot.sans_semis_rattache ? 'Sans semis rattaché' : fmt(lot.date_semis)}
          </span>
          {jours != null && (
            <span
              className="text-[12.5px] font-semibold text-txt2 flex items-center gap-1.5"
              title="Nombre de jours écoulés depuis le semis de ce lot."
            >
              {jours} jours
              {/* Pastille « ? » de la maquette, rendue non focusable : la carte est
                  elle-même un bouton, et un `role="button"` imbriqué y serait invalide.
                  Le survol reste géré par `Tip`, le clavier par le `title` ci-dessus. */}
              <Tip text="Nombre de jours écoulés depuis le semis de ce lot.">
                <span
                  aria-hidden="true"
                  className="w-[15px] h-[15px] rounded-full border-[1.3px] border-current opacity-55 text-[9.5px] font-bold flex items-center justify-center leading-none"
                >
                  ?
                </span>
              </Tip>
            </span>
          )}
        </div>

        <StageBar st={pastilleStade} fills={[st.germinationAvancement, st.godet, st.terre]} />

        <PlantRatio st={st} />

        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Badge de germination de la maquette : `Germination N %`, coloré par le
              taux [CA11]. Une information manquante n'est jamais déguisée en taux. */}
          <Tip text={ph.aide}>
            <Badge tint={ph.tint}>{ph.label}</Badge>
          </Tip>
          {/* [CA5] Une incohérence de saisie est rendue visible, jamais bornée en silence. */}
          {lot.incoherence_saisie && (
            <Badge tint="red">⚠️ {st.P} plants pour {st.S} {lot.unite || 'graines'}</Badge>
          )}
          <span className="ml-auto text-[11.5px] text-txt3 truncate">{lot.parcelle || 'Pépinière'}</span>
        </div>
      </div>
    </button>
  )
}

// ── Panneau de détail : cycle de vie du lot ───────────────────────────────────

function TimelineRow({ icon, tint, isLast, children }) {
  const PASTILLE = {
    brand: 'bg-brand-soft', amber: 'bg-amber-soft', red: 'bg-red-soft', neutre: 'bg-border',
  }
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-base shrink-0 ${PASTILLE[tint]}`}>
          {icon}
        </div>
        {!isLast && <div className="w-px flex-1 bg-border mt-1 min-h-6" />}
      </div>
      <div className="pb-4 flex-1 min-w-0">{children}</div>
    </div>
  )
}

function buildRows(detail) {
  const rows = []
  if (detail.semis.length > 0) detail.semis.forEach(s => rows.push({ type: 'semis', data: s }))
  else rows.push({ type: 'semis_absent' })

  detail.godets.forEach((g, i) => rows.push({ type: 'godet', data: g, idx: i, total: detail.godets.length }))
  if (detail.taux_germination != null) rows.push({ type: 'taux', val: detail.taux_germination })

  if (detail.plantations.length > 0) detail.plantations.forEach(p => rows.push({ type: 'plantation', data: p }))
  else rows.push({ type: 'plantation_absent' })

  ;(detail.ventes ?? []).forEach(v => rows.push({ type: 'vente', data: v }))
  ;(detail.pertes_godet ?? []).forEach(p => rows.push({ type: 'perte_godet', data: p }))
  return rows
}

function DetailModal({ lot, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // [CA10] Le détail est ciblé sur le lot de la carte ouverte, pas sur l'agrégat
  // culture + variété.
  useEffect(() => {
    setLoading(true); setError(null)
    api.godetsDetail(lot.culture, lot.variete, {
      semisId: lot.semis_id,
      sansSemisRattache: lot.sans_semis_rattache,
    })
      .then(setDetail)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [lot.lot_id])

  const titre = lot.variete ? `${lot.culture} · ${lot.variete}` : lot.culture
  const sousTitre = lot.sans_semis_rattache
    ? 'Cycle de vie — godets sans semis rattaché'
    : `Cycle de vie — semis du ${fmt(lot.date_semis)}`

  return (
    <Modal title={titre} sub={sousTitre} icon={Sprout} onClose={onClose} width={520}>
      {loading && <LoadingSkeleton lines={3} />}
      {error && <p className="text-sm text-red">{error}</p>}
      {detail && (
        <div>
          {buildRows(detail).map((row, i, tous) => {
            const isLast = i === tous.length - 1

            if (row.type === 'semis') return (
              <TimelineRow key={`semis-${row.data.id}`} icon="🌱" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Semis <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-txt3">
                  {row.data.nb_graines} {row.data.unite || 'graines'}
                  {row.data.parcelle && <span className="text-brand-text"> · {row.data.parcelle}</span>}
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'semis_absent') return (
              <TimelineRow key="semis-absent" icon="🌱" tint="neutre" isLast={isLast}>
                <p className="text-sm italic text-txt3">Semis non lié</p>
              </TimelineRow>
            )

            if (row.type === 'godet') return (
              <TimelineRow key={`godet-${row.data.id}`} icon="🪴" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Lot godet <span className="font-normal text-txt3">#{row.data.id}</span>
                  {row.total > 1 && <span className="ml-1 text-[12px] text-txt3">· {row.idx + 1}/{row.total}</span>}
                </p>
                <p className="text-sm text-txt3">
                  {pluriel(row.data.nb_plants, 'plant')}
                  {row.data.nb_graines_lot != null && <span> sur {row.data.nb_graines_lot} graines</span>}
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'taux') return (
              <div key="taux" className="mb-3 rounded-xl px-3 py-2.5 flex items-center justify-between bg-card-alt">
                <span className="text-sm text-txt3">Taux de germination</span>
                <Badge tint={tauxTint(row.val)}>{row.val} %</Badge>
              </div>
            )

            if (row.type === 'plantation') return (
              <TimelineRow key={`plant-${row.data.id}`} icon="🌿" tint="brand" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Plantation <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-txt3">
                  {pluriel(row.data.quantite, 'plant')}
                  {row.data.parcelle && (
                    <span> → <span className="font-medium capitalize text-txt">{row.data.parcelle}</span></span>
                  )}
                </p>
                {row.data.source_godet_ids.length > 0 && (
                  <p className="text-[12px] mt-0.5 text-txt3">Lots : #{row.data.source_godet_ids.join(', #')}</p>
                )}
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'plantation_absent') return (
              <TimelineRow key="plant-absent" icon="🌿" tint="neutre" isLast={isLast}>
                <p className="text-sm italic text-txt3">Pas encore planté</p>
              </TimelineRow>
            )

            if (row.type === 'vente') return (
              <TimelineRow key={`vente-${row.data.id}`} icon="🏷️" tint="amber" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Vente <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-txt3">
                  {pluriel(row.data.quantite, 'pied')} vendu{row.data.quantite > 1 ? 's' : ''}
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            if (row.type === 'perte_godet') return (
              <TimelineRow key={`perte-${row.data.id}`} icon="💀" tint="red" isLast={isLast}>
                <p className="text-sm font-semibold text-txt">
                  Perte pépinière <span className="font-normal text-txt3">#{row.data.id}</span>
                </p>
                <p className="text-sm text-red">
                  {pluriel(row.data.quantite, 'plant')} perdu{row.data.quantite > 1 ? 's' : ''}
                </p>
                <p className="text-[12px] mt-0.5 text-txt3">{fmt(row.data.date)}</p>
              </TimelineRow>
            )

            return null
          })}
        </div>
      )}
    </Modal>
  )
}

// ── Bandeau de repères ────────────────────────────────────────────────────────

/**
 * Trois repères en ligne dans une carte, séparés par un filet vertical — la
 * maquette ne met pas de tuiles `Stat` sur cet écran.
 *
 * Repris tel quel : simple `flex-wrap`, sans seuil. Les repères passent à la
 * ligne d'eux-mêmes quand la place manque.
 */
function Reperes({ items }) {
  return (
    <Card pad="p-3.5">
      <div className="flex items-center flex-wrap gap-y-2">
        {items.map(({ icon: Icon, valeur, libelle, tone }, i) => (
          <div
            key={libelle}
            className={`flex items-center gap-[7px] px-4 ${i > 0 ? 'border-l border-border' : ''}`}
          >
            <Icon size={16} className={`${tone} shrink-0`} />
            <span className="text-[13px] text-txt2">
              <strong className="text-txt font-bold">{valeur}</strong> {libelle}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Pepiniere({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId } = usePotager()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lotOuvert, setLotOuvert] = useState(null)
  const [q, setQ] = useState('')            // local, non persisté
  const [tri, setTri] = useState(TRIS[0])
  const [isOpen, toggle] = useGroups()

  async function load() {
    setLoading(true); setError(null)
    try { setData(await api.pepiniereLots(dateRef, potagerId)) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [refresh, dateRef, potagerId])

  const tousLots = data?.lots ?? []

  // [CA13] Le filtre porte à la fois sur la culture et sur la variété ; la date
  // de référence, absente de la maquette, est conservée dans la barre de filtres.
  const groupes = useMemo(() => {
    const q2 = q.toLowerCase()
    const filtres = q2
      ? tousLots.filter(l =>
          (l.culture || '').toLowerCase().includes(q2) || (l.variete || '').toLowerCase().includes(q2))
      : tousLots

    const cle = (l) => l.date_semis || l.date_derniere_mise_en_godet || ''
    const tries = [...filtres].sort((a, b) =>
      tri === 'Récent → Ancien' ? cle(b).localeCompare(cle(a))
        : tri === 'Ancien → Récent' ? cle(a).localeCompare(cle(b))
          : (a.culture || '').localeCompare(b.culture || ''))

    const acc = []
    tries.forEach(l => {
      const f = familleDe(l.culture)
      const g = acc.find(x => x.nom === f)
      g ? g.items.push(l) : acc.push({ nom: f, items: [l] })
    })
    return acc
  }, [tousLots, q, tri])

  const lots = groupes.flatMap(g => g.items)

  // Les trois repères de la maquette, alimentés par les lots réels.
  const plantsDispo = lots.reduce((s, l) => s + (l.stock_residuel_godet ?? 0), 0)
  const tauxConnus = lots
    .filter(l => !l.sans_semis_rattache && l.taux_germination != null && l.nb_mises_en_godet > 0)
    .map(l => l.taux_germination)
  const germMoyenne = tauxConnus.length
    ? Math.round(tauxConnus.reduce((a, b) => a + b, 0) / tauxConnus.length)
    : 0

  // [CA12] Une culture n'est « entièrement plantée » que si tous ses lots le sont.
  const termine = (l) =>
    (l.stock_residuel_godet ?? 0) === 0 && (l.graines_en_germination ?? 0) === 0 && (l.plants_obtenus ?? 0) > 0
  const parCulture = new Map()
  lots.forEach(l => {
    const k = `${(l.culture || '').toLowerCase()}|${(l.variete || '').toLowerCase()}`
    const e = parCulture.get(k) ?? { nom: l.variete ? `${l.culture} (${l.variete})` : l.culture, tous: true }
    e.tous = e.tous && termine(l)
    parCulture.set(k, e)
  })
  const nomsTermines = [...parCulture.values()].filter(e => e.tous).map(e => e.nom)
  const totalVendus = lots.reduce((s, l) => s + (l.nb_vendus ?? 0), 0)

  const filtres = (
    // `@container/filtres` : sous 30rem, la recherche passe seule sur sa propre
    // ligne au lieu d'être écrasée entre la date de référence et le tri.
    <div className="@container/filtres flex items-center gap-2 flex-wrap">
      <DateRefPicker />
      <SearchField
        value={q}
        onChange={setQ}
        placeholder="Rechercher un lot, une variété…"
        className="relative basis-full order-last min-w-0 @[30rem]/filtres:basis-0 @[30rem]/filtres:flex-1 @[30rem]/filtres:order-none"
        aria-label="Filtrer par culture"
      />
      <Select value={tri} options={TRIS} onChange={setTri} aria-label="Trier les lots" />
    </div>
  )

  if (loading) return <LoadingSkeleton lines={4} />
  if (error) return <ApiError message={error} onRetry={load} />

  if (!tousLots.length) return (
    <div className="flex flex-col gap-3.5">
      {filtres}
      <div className="flex flex-col items-center gap-2 mt-12 text-txt3">
        <Sprout size={36} />
        <p className="text-base">Aucun godet en pépinière.</p>
      </div>
    </div>
  )

  return (
    <div className="flex flex-col gap-3.5">
      {filtres}

      <Reperes items={[
        { icon: Sprout, valeur: lots.length, libelle: 'lots actifs', tone: 'text-brand' },
        { icon: Leaf, valeur: plantsDispo, libelle: 'plants en godet', tone: 'text-brand' },
        { icon: BarChart3, valeur: `${germMoyenne} %`, libelle: 'germination', tone: 'text-blue' },
      ]} />

      <div className="flex flex-col gap-3.5">
        {groupes.map(g => (
          <div key={g.nom}>
            <GroupHead
              label={g.nom}
              count={g.items.length}
              right={`${g.items.reduce((s, l) => s + (l.stock_residuel_godet ?? 0), 0)} plants dispo`}
              open={isOpen(g.nom)}
              onToggle={() => toggle(g.nom)}
            />
            {isOpen(g.nom) && (
              // [CA9] `.wpep-grid` de la maquette, à l'identique : des fiches de
              // 230 px minimum et autant de colonnes que la largeur en contient.
              // Le dimensionnement est intrinsèque — ni breakpoint d'écran, ni
              // container query — donc la fiche garde sa largeur au lieu de
              // s'étirer, et `auto-fill` laisse les colonnes vides d'une rangée
              // incomplète plutôt que d'élargir les cartes présentes.
              <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(230px,1fr))]">
                {g.items.map(lot => (
                  <LotCard key={lot.lot_id} lot={lot} onOpen={() => setLotOuvert(lot)} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {(nomsTermines.length > 0 || totalVendus > 0) && (
        <div className="flex flex-col gap-2">
          {nomsTermines.length > 0 && (
            <InfoBanner
              tint="brand"
              icon={Leaf}
              dismissible={false}
              title={`${nomsTermines.length} culture${nomsTermines.length > 1 ? 's' : ''} entièrement plantée${nomsTermines.length > 1 ? 's' : ''}`}
              body={nomsTermines.join(', ')}
            />
          )}
          {totalVendus > 0 && (
            <InfoBanner
              tint="amber"
              icon={Sprout}
              dismissible={false}
              title={`${pluriel(totalVendus, 'pied')} vendu${totalVendus > 1 ? 's' : ''} cette saison`}
              body="Ces plants sont sortis de la pépinière autrement que par plantation."
            />
          )}
        </div>
      )}

      {lotOuvert && <DetailModal lot={lotOuvert} onClose={() => setLotOuvert(null)} />}
    </div>
  )
}
