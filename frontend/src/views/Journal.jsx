// [US-063] Écran Journal — remplace `Historique.jsx` (renommage §5.4) et porte
// `ScreenJournal` (`web-screens.jsx`, maquette 2026, proposition du 18/08/2026)
// sur la donnée réelle exposée par `GET /historique`.
//
// La maquette compose une phrase par événement (« Récolte de 1,2 kg de
// courgettes ») et l'affiche avec une heure. Le modèle réel n'a ni l'une ni
// l'autre : `Evenement` stocke des champs séparés, et l'heure n'existe nulle part
// — `parse_date()` tronque à `%Y-%m-%d` et `GET /historique` re-tronque via
// `str(e.date)[:10]`. La phrase est donc RECONSTRUITE ici à partir des champs
// réels, selon le patron « <action> de <quantité> <unité> de <culture> <variété> »
// (décision produit du 18/08/2026), et la colonne d'heure est simplement absente
// plutôt que remplie d'une valeur inventée.
//
// Même décision pour les filtres : liste déroulante d'actions, date unique au lieu
// d'une période à deux dates, pas de date de référence sur cet écran, export
// CSV/JSON ajouté. L'API reste paginée à 20 événements/page ; le regroupement par
// jour est un habillage visuel de la page déjà chargée, pas un nouvel appel.
import { useState, useEffect } from 'react'
import {
  Calendar, ChevronLeft, ChevronRight, Clock, X, FileDown, FileJson, Filter,
  ShoppingBasket, Sprout, Leaf, Droplet, Skull, Package, Euro, Scissors,
  NotebookText, MoreHorizontal,
} from 'lucide-react'
import { api } from '../lib/api.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { phraseEvenement, libelleAction, grouperParJour } from '../lib/journal.js'
import CultureFilter from '../components/CultureFilter.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import { Card, IconSelect, Btn, SectionLabel } from '../components/ui'

// [CA2] Classes littérales et non `bg-${tint}-soft` : Tailwind ne génère que les
// classes qu'il lit textuellement dans les sources, et ce projet n'a pas de
// `safelist` — une classe construite dynamiquement n'existe que tant qu'un autre
// fichier l'écrit en toutes lettres. Même table explicite que `Badge`/`CardHead`.
const TINTS = {
  brand:  { bg: 'bg-brand-soft',  fg: 'text-brand'  },
  amber:  { bg: 'bg-amber-soft',  fg: 'text-amber'  },
  blue:   { bg: 'bg-blue-soft',   fg: 'text-blue'   },
  red:    { bg: 'bg-red-soft',    fg: 'text-red'    },
  violet: { bg: 'bg-violet-soft', fg: 'text-violet' },
  neutre: { bg: 'bg-card-alt',    fg: 'text-txt3'   },
}

// ── Catégories de filtre — les 9 de la maquette [CA3] ─────────────────────────
// Une catégorie ne vaut pas un `type_action` : plusieurs en recouvrent
// nettement plus d'un (« Entretien » en couvre six). D'où `valeurs`, envoyé au
// serveur en liste séparée par des virgules — filtrer côté client fausserait la
// pagination, calculée côté serveur.

const CATEGORIES = [
  { label: 'Récoltes',    valeurs: ['recolte'],                 tint: 'amber',  icon: ShoppingBasket },
  { label: 'Semis',       valeurs: ['semis'],                   tint: 'blue',   icon: Sprout },
  { label: 'Lots godet',  valeurs: ['mise_en_godet'],           tint: 'amber',  icon: Package },
  { label: 'Plantations', valeurs: ['plantation', 'repiquage'], tint: 'brand',  icon: Leaf },
  { label: 'Arrosages',   valeurs: ['arrosage'],                tint: 'blue',   icon: Droplet },
  { label: 'Ventes',      valeurs: ['vendu'],                   tint: 'violet', icon: Euro },
  { label: 'Pertes',      valeurs: ['perte', 'perte_godet'],    tint: 'red',    icon: Skull },
  { label: 'Entretien',   tint: 'neutre', icon: Scissors,
    valeurs: ['desherbage', 'paillage', 'fertilisation', 'traitement', 'taille', 'tuteurage'] },
  { label: 'Notes',       valeurs: ['observation'],             tint: 'neutre', icon: NotebookText },
]

const TOUTES_ACTIONS = 'Toutes les actions'
const CATEGORIE_PAR_LABEL = Object.fromEntries(CATEGORIES.map(c => [c.label, c]))

const OPTIONS_FILTRE = [
  { value: TOUTES_ACTIONS, label: TOUTES_ACTIONS, icon: Filter },
  ...CATEGORIES.map(c => ({ value: c.label, label: c.label, icon: c.icon, tint: c.tint })),
]

// Icône et teinte d'une ligne : indexées par `type_action` réel, dérivées des
// catégories ci-dessus pour que le menu de filtre et les lignes qu'il filtre
// partagent exactement la même grammaire visuelle.
const VISUEL_PAR_ACTION = Object.fromEntries(
  CATEGORIES.flatMap(c => c.valeurs.map(v => [v, { tint: TINTS[c.tint], icon: c.icon }])),
)

function actionVisual(typeAction) {
  return VISUEL_PAR_ACTION[typeAction] ?? { tint: TINTS.neutre, icon: MoreHorizontal }
}

// Libellés au SINGULIER pour la phrase — les libellés de catégorie sont au
// pluriel (« Récoltes »), ce qui ne se dit pas dans une phrase d'événement.
// Couvre les 16 `ACTIONS_VALIDES` de `utils/validation.py`, pas seulement les
// types filtrables : le journal restitue tout ce qui a été enregistré. La table
// des libellés, la composition de la phrase et le regroupement par jour vivent
// dans `lib/journal.js` — testables sans rendu React (`npm test`).

const PAGE_SIZE = 20

// ── Filtre date unique [CA3] ────────────────────────────────────────────────
// Remplace le sélecteur de période à deux dates : une seule date, envoyée au
// serveur à la fois comme `from` et `to`. Habillage repris de `DateRefPicker`
// (bouton + input natif superposé) mais sur un état local à cet écran — pas de
// `useDateRef`, la date de référence globale ne s'applique plus au Journal.

function DateFilter({ value, onChange }) {
  return (
    <div className="flex items-center gap-1">
      <div className="relative inline-flex items-center">
        <div className={`flex items-center gap-1.5 px-3 h-[38px] rounded-[10px] border text-[13.5px] font-medium select-none cursor-pointer transition-colors ${
          value ? 'bg-brand-soft border-brand text-brand-text' : 'bg-card border-border text-txt3'
        }`}>
          <Calendar size={15} aria-hidden="true" />
          <span>{value ? value.split('-').reverse().join('/') : 'Toutes les dates'}</span>
        </div>
        <input
          type="date"
          value={value || ''}
          onChange={e => onChange(e.target.value || null)}
          onClick={e => { try { e.target.showPicker() } catch {} }}
          className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
          aria-label="Filtrer par date"
        />
      </div>
      {value && (
        <button
          onClick={() => onChange(null)}
          title="Effacer la date"
          className="p-1 rounded text-brand-text hover:text-txt transition-colors"
          aria-label="Effacer le filtre de date"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}

// ── Export CSV/JSON [CA8] — page affichée après filtres, jamais tout l'historique ──

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

// L'export reste tabulaire (un champ par colonne), jamais la phrase reconstruite :
// une phrase se relit, elle ne se retrie ni ne se recalcule dans un tableur.
const EXPORT_HEADERS = ['Date', 'Action', 'Culture', 'Variété', 'Parcelle', 'Quantité', 'Unité', 'Godets']

function toExportRow(e) {
  return {
    date: e.date,
    action: libelleAction(e.type_action),
    culture: e.culture ?? '',
    variete: e.variete ?? '',
    parcelle: e.parcelle ?? '',
    quantite: e.quantite ?? '',
    unite: e.unite ?? '',
    godets: e.nb_plants_godets ?? '',
  }
}

function exportCSV(rows) {
  const lignes = rows.map(toExportRow)
  const csv = [
    EXPORT_HEADERS.join(';'),
    ...lignes.map(r => Object.values(r).map(csvEscape).join(';')),
  ].join('\n')
  downloadBlob(`journal-${new Date().toISOString().slice(0, 10)}.csv`, '﻿' + csv, 'text/csv;charset=utf-8')
}

function exportJSON(rows) {
  const json = JSON.stringify(rows.map(toExportRow), null, 2)
  downloadBlob(`journal-${new Date().toISOString().slice(0, 10)}.json`, json, 'application/json')
}

// ── Ligne d'événement ─────────────────────────────────────────────────────────
// Une ligne dans la carte du jour, séparée de la suivante par un filet — pas une
// carte autonome : la maquette montre une LISTE, un bloc par journée, et non une
// grille de vignettes.

function EventRow({ e, last }) {
  const { tint, icon: Icon } = actionVisual(e.type_action)
  return (
    <div className={`flex items-center gap-3 px-4 py-3 ${last ? '' : 'border-b border-border-soft'}`}>
      <span className={`w-9 h-9 rounded-[10px] flex items-center justify-center shrink-0 ${tint.bg}`}>
        <Icon size={17} className={tint.fg} />
      </span>
      {/* [CA5] `@container/card` est fourni par `Card` : au-delà de 34rem de
          largeur de carte, la parcelle rejoint la phrase sur la même ligne, calée
          à droite (la place qu'occupe l'heure dans la maquette) ; en dessous elle
          repasse sous la phrase. Adaptation pilotée par la largeur du conteneur,
          jamais par un breakpoint d'écran (règle non négociable de CLAUDE.md). */}
      <div className="min-w-0 flex-1 @[34rem]/card:flex @[34rem]/card:items-baseline @[34rem]/card:gap-3">
        <p className="text-[14px] text-txt @[34rem]/card:flex-1 @[34rem]/card:min-w-0">
          {phraseEvenement(e)}
        </p>
        {e.parcelle && (
          <p className="text-[11.5px] text-txt3 mt-0.5 @[34rem]/card:mt-0 @[34rem]/card:shrink-0">
            {e.parcelle}
          </p>
        )}
      </div>
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────

export default function Journal({ refresh }) {
  const { potagerId } = usePotager()
  const [data, setData]                 = useState({ total: 0, evenements: [] })
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState(null)
  // Le filtre porte le LIBELLÉ de catégorie (« Pertes »), pas un `type_action` :
  // une catégorie en recouvre parfois plusieurs, détaillés dans `valeurs`.
  const [actionFilter, setActionFilter] = useState(TOUTES_ACTIONS)
  const [cultureFilter, setCulture]     = useState('')
  const [dateFilter, setDateFilter]     = useState(null)
  const [page, setPage]                 = useState(0)

  async function load(pg = page) {
    setLoading(true); setError(null)
    try {
      const params = { limit: PAGE_SIZE, offset: pg * PAGE_SIZE }
      const categorie = CATEGORIE_PAR_LABEL[actionFilter]
      if (categorie) params.action = categorie.valeurs.join(',')
      if (dateFilter) { params.from = dateFilter; params.to = dateFilter }
      // [US-083 / CA7] Si on consulte un potager archivé, passer son ID
      if (potagerId) params.potager_id = potagerId
      setData(await api.historique(params))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // [CA4] Un changement de filtre transmis au serveur ramène à la première page.
  // Le filtre culture reste un filtrage local de la page déjà chargée : il ne
  // recharge rien et ne modifie donc pas la pagination (comme avant la refonte).
  useEffect(() => { setPage(0); load(0) }, [refresh, actionFilter, dateFilter, potagerId])
  useEffect(() => { load(page) }, [page])

  const evenements = data.evenements || []
  const total      = data.total || 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const q = cultureFilter.toLowerCase()
  const filtered = q
    ? evenements.filter(e => (e.culture || '').toLowerCase().includes(q) || (e.variete || '').toLowerCase().includes(q))
    : evenements

  const groupes = grouperParJour(filtered)

  const filtres = (
    <div className="@container/filtres flex items-center gap-2 flex-wrap">
      <CultureFilter
        value={cultureFilter}
        onChange={setCulture}
        className="relative basis-full order-last min-w-0 @[34rem]/filtres:basis-0 @[34rem]/filtres:flex-1 @[34rem]/filtres:order-none"
      />
      <IconSelect
        value={actionFilter}
        options={OPTIONS_FILTRE}
        onChange={setActionFilter}
        aria-label="Filtrer par type d'action"
      />
      <DateFilter value={dateFilter} onChange={setDateFilter} />
      <span className="flex gap-1.5 ml-auto">
        <Btn small icon={FileDown} onClick={() => exportCSV(filtered)} title="Exporter en CSV">CSV</Btn>
        <Btn small icon={FileJson} onClick={() => exportJSON(filtered)} title="Exporter en JSON">JSON</Btn>
      </span>
    </div>
  )

  return (
    <div className="flex flex-col gap-3.5">
      {filtres}

      {loading ? (
        <LoadingSkeleton lines={6} />
      ) : error ? (
        <ApiError message={error} onRetry={() => load(page)} />
      ) : groupes.length === 0 ? (
        <div className="flex flex-col items-center gap-3 mt-12 text-txt3">
          <Clock size={36} />
          <p className="text-base">Aucun événement enregistré.</p>
        </div>
      ) : (
        // [CA1] Une carte par journée, les événements en lignes à l'intérieur —
        // structure de la maquette (`SectionLabel` + `Card pad={0}`).
        <div className="flex flex-col gap-4">
          {groupes.map((g, i) => (
            <div key={i}>
              <SectionLabel>{g.label}</SectionLabel>
              <Card pad="p-0" className="overflow-hidden">
                {g.items.map((e, j) => (
                  <EventRow key={e.id ?? `${i}-${j}`} e={e} last={j === g.items.length - 1} />
                ))}
              </Card>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && totalPages > 1 && (
        <div className="flex items-center justify-between mt-1 px-1">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="p-2 rounded-xl border border-border text-txt3 disabled:opacity-30"
          >
            <ChevronLeft size={18} />
          </button>
          <span className="text-sm text-txt3">
            Page {page + 1} / {totalPages}
            <span className="ml-1 text-[12px]">({total} événements)</span>
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="p-2 rounded-xl border border-border text-txt3 disabled:opacity-30"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}
    </div>
  )
}
