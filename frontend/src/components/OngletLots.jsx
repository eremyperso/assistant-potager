// [US-242] L'onglet « Lots » de la Pépinière — le journal de saison.
//
// Maquette « Lots - Journal de saison HF » (projet Claude Design, 19/10/2026). Un
// registre SANS geste : chaque lot est une ligne de gestes datés sur une frise ; la
// ligne déplie sa fiche (conteneur large) ou l'ouvre en plein écran (conteneur étroit).
// On agit dans « Ma pépinière » : le seul bouton de la fiche y mène.
//
// Les règles — statut, gestes datés, fenêtre, positions, bilan — vivent dans
// `lib/lotsJournal.js` ; ce composant ne fait que les dessiner.
import { useEffect, useMemo, useRef, useState } from 'react'
import { CalendarDays, ChevronRight, MapPin, Sprout, X } from 'lucide-react'
import { Modal, SearchField } from './ui'
import DateRefPicker from './DateRefPicker.jsx'
import { lireNumeroLot, messageLotInconnu } from '../lib/pepiniere.js'
import { placeEnClair, suggestionsVisibles, tracabilite } from '../lib/ficheLot.js'
import {
  FILTRES, LIBELLE_STATUT, barreDuLot, bilanDesLots, comptesFiltres, echeanceFiche, etatEnUneLigne as etatLigne, fenetre,
  filtreInitial, frise, groupesParMois, identiteFiche, jourDeReference, journalDuLot, lotsVisibles,
  moisDeLaFenetre, quantiteNonDite, statutLot, tauxDuLot,
} from '../lib/lotsJournal.js'
import { dateCourte } from '../lib/parcours.js'

/** Seuil du conteneur (48rem) : frise en tableau et fiche dépliée au-dessus, liste et plein écran en dessous. */
const LARGEUR_TABLEAU = 768

function useLargeur(el) {
  const [largeur, setLargeur] = useState(0)
  useEffect(() => {
    if (!el) return undefined
    const mesurer = () => setLargeur(el.getBoundingClientRect().width)
    mesurer()
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(mesurer)
    ro.observe(el)
    return () => ro.disconnect()
  }, [el])
  return largeur
}

// ── Les pictos de geste (ceux de la maquette) ────────────────────────────────

const TRACES = {
  S: <><path d="M12 3C8 8 6.5 12 6.5 15a5.5 5.5 0 0 0 11 0C17.5 12 16 8 12 3z" /><path d="M12 10v9" /></>,
  L: <><path d="M12 21v-9" /><path d="M12 13C12 9.5 9.5 7 5 7c0 3.5 2.5 6 7 6z" /><path d="M12 11c0-3.5 2.5-6 7-6 0 3.5-2.5 6-7 6z" /><path d="M7 21h10" /></>,
  G: <><path d="M4 11h16" /><path d="M5.5 11 7 21h10l1.5-10" /><path d="M12 11V7" /><path d="M12 8c0-2.5 2-4 4.5-4 0 2.5-2 4-4.5 4z" /></>,
  D: <><path d="M4 8h15" /><path d="m15 4 4 4-4 4" /><path d="M20 16H5" /><path d="m9 12-4 4 4 4" /></>,
  C: <><path d="M5 22V3" /><path d="M5 4h8v4h6v8h-8v-4H5" /></>,
  X: <><path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" /><path d="M3 3v5h5" /><path d="M12 7.5V12l3 2" /></>,
  V: <><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z" /><circle cx="7.5" cy="7.5" r="1" /></>,
  P: <><path d="M18 6 6 18" /><path d="m6 6 12 12" /></>,
  T: <><path d="M12 3v11" /><path d="M8.5 14h7l-1 5.5a2.5 2.5 0 0 1-5 0z" /><path d="M3 21h18" /><path d="M9 3h6" /></>,
}

function Picto({ code, size = 13 }) {
  if (!TRACES[code]) return null
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2.1"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {TRACES[code]}
    </svg>
  )
}

const LEGENDE = [
  ['S', 'semé'], ['L', 'levée notée'], ['G', 'dernière mise en godet'], ['D', 'déplacé de pépinière'],
  ['T', 'mis en terre'], ['V', 'vendu'], ['P', 'perdu en godet'],
  ['C', "clôturé, fin de l'itinéraire"], ['X', 'dernier geste'],
]

const TON_STATUT = {
  en_cours: 'bg-brand-soft text-brand-text',
  a_regler: 'bg-amber-soft text-amber',
  termine: 'bg-card-alt text-txt2',
}

function PastilleStatut({ lot }) {
  const s = statutLot(lot)
  return (
    <span className={`inline-flex self-start items-center h-[22px] px-[9px] rounded-full text-[11px] font-bold whitespace-nowrap ${TON_STATUT[s]}`}>
      {LIBELLE_STATUT[s]}
    </span>
  )
}

const nomDuLot = (lot) => (
  <>
    <span className="capitalize">{lot.culture}</span>
    {lot.variete && <small className="font-medium text-txt3 text-[12px]"> {lot.variete}</small>}
  </>
)

// ── La barre et sa légende ───────────────────────────────────────────────────

function BarreEmpilee({ segments, hauteur = 'h-[14px]' }) {
  return (
    <>
      <div className={`flex ${hauteur} rounded-full overflow-hidden bg-card-alt`}>
        {segments.map((s) => (
          <i key={s.cle} className={`block h-full part-${s.cle}`} style={{ width: `${s.largeur}%` }} title={`${s.valeur} ${s.libelle}`} />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-txt2 mt-2">
        {segments.map((s) => (
          <span key={s.cle} className="inline-flex items-center gap-[5px]">
            <i className={`inline-block w-2.5 h-2.5 rounded-[3px] part-${s.cle}`} aria-hidden="true" />{s.valeur} {s.libelle}
          </span>
        ))}
      </div>
    </>
  )
}

// ── Le bilan des lots visibles (CA2) ─────────────────────────────────────────

function Bilan({ lots, aujourdhui }) {
  const b = bilanDesLots(lots, aujourdhui)
  const tuiles = [
    ['S', b.semees, `graines semées · ${b.lots} lot${b.lots > 1 ? 's' : ''}`],
    ['L', b.obtenus, 'plants obtenus'],
    ['G', b.go, "en godet aujourd'hui"],
    ['T', b.pl, 'mis en terre'],
  ]
  return (
    <section aria-label="Bilan des lots" className="@container/bilan bg-card border border-border rounded-[18px] shadow-card">
      <div className="flex flex-col gap-2 px-3.5 py-3 @[60rem]/bilan:grid @[60rem]/bilan:grid-cols-[minmax(0,330px)_minmax(0,1fr)] @[60rem]/bilan:gap-7 @[44rem]/bilan:gap-3.5 @[44rem]/bilan:px-[22px] @[44rem]/bilan:py-[18px] @[44rem]/bilan:items-center">
        <div>
          <div className="flex items-baseline gap-2.5">
            <span className="font-hand whitespace-nowrap text-[24px] @[44rem]/bilan:text-[28px] font-bold leading-none text-brand-deep">
              {b.pourcent == null ? '—' : `${b.pourcent} %`}
            </span>
            <span className="text-[12.5px] @[44rem]/bilan:text-[13px] text-txt2 leading-tight">des graines semées ont donné un plant</span>
          </div>
          <p className="mt-2 @[44rem]/bilan:mt-2.5 font-serif text-[14px] @[44rem]/bilan:text-[16px] font-semibold leading-[1.35] text-txt">
            {b.phrase}
            {b.urgence && <> · <em className="not-italic text-frk-d bg-frk-s rounded-[6px] px-[5px]">{b.urgence}</em></>}
          </p>
        </div>
        <div>
          <div className="hidden @[36rem]/bilan:grid grid-cols-2 @[44rem]/bilan:grid-cols-4 gap-2.5 mb-3.5">
            {tuiles.map(([k, v, l]) => (
              <div key={k} className="flex items-center gap-3 border border-border rounded-[16px] px-3.5 py-3 bg-card min-w-0">
                <span className={`w-11 h-11 rounded-[12px] flex items-center justify-center shrink-0 tuile-${k}`}><Picto code={k} size={22} /></span>
                <span className="min-w-0">
                  <b className="block font-hand text-[28px] leading-none text-txt">{v}</b>
                  <small className="block text-[12px] text-txt2 leading-tight">{l}</small>
                </span>
              </div>
            ))}
          </div>
          {b.barre.length > 0 && <BarreEmpilee segments={b.barre} hauteur="h-3 @[44rem]/bilan:h-[18px]" />}
        </div>
      </div>
    </section>
  )
}

// ── La frise d'un lot (CA3) ──────────────────────────────────────────────────

function Frise({ lot, f, aujourdhui, largeur, etroite, mois }) {
  const fr = frise(lot, f, aujourdhui, largeur ? (24 / largeur) * 100 : 3)
  return (
    <div className={`relative ${etroite ? 'frise-etroite min-h-[50px] -mx-0.5' : 'min-h-[68px]'}`}>
      {mois.map((m, i) => (
        <i key={m.date} className={`absolute top-0 bottom-0 w-px ${i === 0 && m.gauche === 0 ? 'bg-border' : 'bg-border-soft'}`} style={{ left: `${m.gauche}%` }} aria-hidden="true" />
      ))}
      {fr.fenetreTerre && (
        <i className="absolute top-[calc(50%-7px)] h-3.5 rounded-[7px] fenetre-terre" style={{ left: `${fr.fenetreTerre.gauche}%`, width: `${fr.fenetreTerre.largeur}%` }}
          title={`mise en terre prévue du ${dateCourte(fr.fenetreTerre.du)} au ${dateCourte(fr.fenetreTerre.au)}`} />
      )}
      {fr.trait && <i className="absolute top-1/2 h-0 border-t-2 border-txt2 z-[1]" style={{ left: `${fr.trait.gauche}%`, width: `${fr.trait.largeur}%` }} aria-hidden="true" />}
      {fr.attente && <i className="absolute top-1/2 h-0 border-t-2 border-dashed border-txt3 z-[1]" style={{ left: `${fr.attente.gauche}%`, width: `${fr.attente.largeur}%` }} aria-hidden="true" />}
      <i className="absolute top-0 bottom-0 w-[2.5px] rounded-sm bg-red z-[3]" style={{ left: `${fr.aujourdhui}%` }} aria-hidden="true" />
      {fr.pastilles.map((p) => (
        <i key={`${p.code}-${p.date}`} className={`geste geste-${p.code}${p.niveau < 0 ? ' haut' : p.niveau > 0 ? ' bas' : ''}`}
          style={{ left: `${p.gauche}%`, ...(p.pale ? { opacity: 0.5 } : {}) }} data-info={p.info} aria-label={p.info}>
          <Picto code={p.code} size={etroite ? 11 : 13} />
        </i>
      ))}
    </div>
  )
}

function EnteteFrise({ f, aujourdhui, mois }) {
  return (
    <span className="relative min-h-[34px] block">
      {mois.map((m) => (
        <span key={m.date} className="absolute top-2.5 translate-x-[5px] text-[10.5px] font-semibold normal-case tracking-normal" style={{ left: `${m.gauche}%` }}>{m.mois}</span>
      ))}
      <b className="absolute top-1.5 -translate-x-1/2 bg-red text-white text-[10px] font-bold px-1.5 py-px rounded-full z-[4] normal-case tracking-normal"
        style={{ left: `${frise({}, f, aujourdhui).aujourdhui}%` }}>{dateCourte(aujourdhui)}</b>
    </span>
  )
}

// ── La fiche, sans geste (CA6, CA7) ──────────────────────────────────────────

const TON_ECHEANCE = {
  fin: 'bg-card-alt',
  pret: 'echeance-pret [&_b]:text-frk-d',
  bien: 'bg-amber-soft [&_b]:text-amber',
  retard: 'bg-amber-soft [&_b]:text-amber',
  na: 'bg-card-alt border-[1.5px] border-dashed border-border',
  info: 'bg-card-alt',
}

const Boite = ({ titre, action, children }) => (
  <section aria-label={titre} className="bg-card border border-border rounded-[14px] px-4 py-3.5 flex flex-col gap-2.5 min-w-0">
    <div className="flex justify-between items-center text-[11px] font-bold uppercase tracking-[.06em] text-txt3">{titre}{action}</div>
    {children}
  </section>
)

function BlocLot({ lot, aujourdhui, onAgir, avecTitre, action }) {
  const id = identiteFiche(lot, aujourdhui)
  const ech = echeanceFiche(lot)
  const ou = lot.ou_mettre && (lot.stock_residuel_godet ?? 0) > 0 ? suggestionsVisibles(lot.ou_mettre) : []
  const termine = statutLot(lot) === 'termine'
  const contenu = (
    <>
      <div className="text-[12.5px] text-txt2 flex flex-col gap-[3px]">
        {!lot.variete && <span className="italic text-txt3">variété non précisée</span>}
        <span className="flex gap-1.5 items-start"><CalendarDays size={15} className="text-txt3 mt-px shrink-0" aria-hidden="true" />{id.semis}</span>
        <span className="flex gap-1.5 items-start">
          <MapPin size={15} className="text-txt3 mt-px shrink-0" aria-hidden="true" />
          <span>{id.lieu}{id.deplace ? ` · ${id.deplace}` : ''}</span>
        </span>
      </div>
      <PastilleStatut lot={lot} />
      {ech && (
        <div className={`rounded-[12px] px-3 py-2.5 flex flex-col gap-0.5 ${TON_ECHEANCE[ech.ton] ?? TON_ECHEANCE.info}`}>
          <b className="text-[14px] text-txt">{ech.titre}</b>
          {ech.detail && <span className="text-[12px] text-txt2">{ech.detail}</span>}
        </div>
      )}
      {ou.length > 0 && (
        <div className="rounded-[10px] border border-border-soft px-2.5 py-2 flex flex-col gap-[3px] text-[12px] text-txt2">
          <span className="text-[10.5px] font-bold uppercase tracking-[.05em] text-txt3">Où les mettre</span>
          {ou.map((s) => (
            <div key={s.parcelle_id}><b className="text-txt">{s.parcelle}</b> · {placeEnClair(s, null)}{s.exposition?.libelle ? ` · ${s.exposition.libelle}` : ''}</div>
          ))}
          {lot.ou_mettre.plants_non_calcules && <div className="text-amber font-semibold">{lot.ou_mettre.plants_non_calcules}</div>}
        </div>
      )}
      {!termine && (
        <button type="button" onClick={() => onAgir(lot)}
          className="flex items-center justify-between min-h-[44px] px-3 rounded-[12px] border border-border text-[13px] font-semibold text-txt hover:border-brand hover:text-brand-text">
          <span className="flex gap-2 items-center"><Sprout size={16} aria-hidden="true" />Agir dans Ma pépinière</span>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
      )}
    </>
  )
  return avecTitre ? <Boite titre="Lot sélectionné" action={action}>{contenu}</Boite> : <section aria-label="Lot" className="bg-card border border-border rounded-[14px] px-4 py-3.5 flex flex-col gap-2.5">{contenu}</section>
}

function BlocBilan({ lot }) {
  const taux = tauxDuLot(lot)
  const barre = barreDuLot(lot)
  const lignes = tracabilite(lot).filter((l) => l.cle !== 'taux_levee')
  return (
    <Boite titre="Bilan">
      {taux && (
        <div className="flex items-baseline gap-2">
          <span className="font-hand text-[34px] font-bold leading-none text-txt">{taux.valeur}&nbsp;%</span>
          <small className="text-[12px] text-txt2">{taux.libelle} · sur {taux.sur} graines</small>
        </div>
      )}
      {quantiteNonDite(lot) ? (
        <>
          <div className="h-3.5 rounded-full border border-dashed border-border bg-[repeating-linear-gradient(90deg,var(--card-alt)_0_6px,var(--card)_6px_10px)]" />
          <div className="text-[11.5px] text-txt2">quantité semée non dite : pas de bilan possible</div>
        </>
      ) : barre.length > 0 && <BarreEmpilee segments={barre} />}
      <dl className="flex flex-col border-t border-border-soft">
        {lignes.map((l) => (
          <div key={l.cle} className="flex items-baseline gap-2.5 py-1.5 border-b border-border-soft">
            <dt className="flex-1 text-[12.5px] text-txt2">{l.libelle}</dt>
            <dd className={`text-[14px] tabular-nums ${l.valeur == null ? 'text-txt3 font-medium' : 'font-bold text-txt'}`}>{l.valeur == null ? '—' : l.valeur}</dd>
          </div>
        ))}
      </dl>
    </Boite>
  )
}

function BlocJournal({ lot, aujourdhui }) {
  const lignes = journalDuLot(lot, aujourdhui)
  return (
    <Boite titre="Journal du lot">
      <ol className="flex flex-col relative journal-trait">
        {lignes.map((g, i) => (
          <li key={i} className="grid [grid-template-columns:38px_22px_minmax(0,1fr)] gap-x-2.5 items-start py-1.5 relative">
            <span className={`font-hand text-[17px] font-bold text-right leading-[22px] ${g.aujourdhui ? 'text-red' : 'text-txt2'}`}>{g.jour ?? ''}</span>
            {g.aujourdhui
              ? <i className="geste statique geste-N m-[5px]" aria-hidden="true" />
              : <i className={`geste statique geste-${g.code}`} aria-hidden="true"><Picto code={g.code} /></i>}
            <div className={`text-[12.5px] leading-[1.35] ${g.nonDate ? 'text-txt3 italic' : 'text-txt'}`}>
              <b className={`block text-[13px] ${g.aujourdhui ? 'text-red' : g.nonDate ? 'text-txt2' : ''}`}>{g.titre}</b>
              {g.nonDate
                ? <>{g.detail} · date non transmise</>
                : <>{g.quand}{g.detail ? <> · <small className="text-txt3 text-[11.5px]">{g.detail}</small></> : null}</>}
            </div>
          </li>
        ))}
      </ol>
    </Boite>
  )
}

function FicheDepliee({ lot, aujourdhui, onAgir, onFermer }) {
  return (
    <div className="deplier border-t border-border bg-[linear-gradient(var(--brand-soft),var(--surface)_46px)] px-4 pt-1.5 pb-[18px] @[56rem]/journal:pl-[92px]">
      <div className="@container/fichej">
        <div className="grid gap-4 grid-cols-1 @[40rem]/fichej:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <BlocLot lot={lot} aujourdhui={aujourdhui} onAgir={onAgir} avecTitre
            action={(
              <button type="button" onClick={onFermer} aria-label="Replier la fiche"
                className="w-[30px] h-[30px] rounded-[9px] bg-card-alt flex items-center justify-center text-txt2">
                <X size={16} />
              </button>
            )} />
          <BlocBilan lot={lot} />
          <BlocJournal lot={lot} aujourdhui={aujourdhui} />
        </div>
      </div>
    </div>
  )
}

function FichePleinEcran({ lot, aujourdhui, onAgir, onFermer }) {
  const titre = `${lot.numero_lot != null ? `#${lot.numero_lot} · ` : ''}${lot.culture}${lot.variete ? ` ${lot.variete}` : ''}`
  return (
    <Modal title={titre} onClose={onFermer} disposition="adaptative" width={460} entete={false} bodyClassName="flex flex-col flex-1 min-h-0 bg-bg">
      <div className="flex items-center gap-1.5 min-h-[56px] pl-1 pr-2.5 py-1 border-b border-border bg-surface">
        <button type="button" onClick={onFermer} aria-label="Fermer la fiche" className="w-12 h-12 rounded-[12px] flex items-center justify-center text-txt">
          <X size={18} />
        </button>
        <b className="flex-1 font-hand text-[21px] font-bold leading-tight text-txt">{titre}</b>
        <PastilleStatut lot={lot} />
      </div>
      <div className="flex-1 overflow-auto p-3.5 flex flex-col gap-3">
        <BlocLot lot={lot} aujourdhui={aujourdhui} onAgir={onAgir} />
        <BlocBilan lot={lot} />
        <BlocJournal lot={lot} aujourdhui={aujourdhui} />
      </div>
    </Modal>
  )
}

// ── L'onglet ─────────────────────────────────────────────────────────────────

/**
 * @param lots     les lots de `GET /pepiniere/lots`
 * @param etat     l'état d'écran (`q`, `filtreLots`, `zoom`, `lotDeplie`) — RT12
 * @param onAgir   ouvre le lot dans « Ma pépinière » (CA7)
 * @param onLotInconnu  un numéro saisi qui n'existe pas (US-209 / CA11)
 */
export default function OngletLots({ lots, dateRef, etat, setEtat, onAgir, onLotInconnu, signaler }) {
  const [racine, setRacine] = useState(null)
  const largeur = useLargeur(racine)
  const large = largeur >= LARGEUR_TABLEAU
  const [axe, setAxe] = useState(null)
  const largeurAxe = useLargeur(axe)
  const [numeroSaisi, setNumeroSaisi] = useState('')
  const lignes = useRef({})

  const aujourdhui = jourDeReference(dateRef, lots)
  const filtre = filtreInitial(etat.filtreLots)
  const zoom = large ? (etat.zoom === 'recent' ? 'recent' : 'saison') : 'recent'
  const f = useMemo(() => fenetre(zoom, aujourdhui), [zoom, aujourdhui])
  const fRecent = useMemo(() => fenetre('recent', aujourdhui), [aujourdhui])
  const mois = useMemo(() => moisDeLaFenetre(f), [f])
  const comptes = useMemo(() => comptesFiltres(lots), [lots])
  const visibles = useMemo(() => lotsVisibles(lots, { filtre, q: etat.q }), [lots, filtre, etat.q])
  const groupes = useMemo(() => groupesParMois(visibles), [visibles])
  const ouvert = etat.lotDeplie != null ? (lots ?? []).find((l) => l.lot_id === etat.lotDeplie) ?? null : null

  const basculer = (lot) => setEtat({ lotDeplie: etat.lotDeplie === lot.lot_id ? null : lot.lot_id })
  const fermer = () => setEtat({ lotDeplie: null })

  function allerAuLot(e) {
    e.preventDefault()
    const numero = lireNumeroLot(numeroSaisi)
    if (numero == null) { signaler?.("Tapez le numéro écrit sur l'étiquette, par exemple 128."); return }
    const cible = (lots ?? []).find((l) => l.numero_lot === numero)
    if (!cible) { signaler?.(messageLotInconnu(numero)); onLotInconnu?.(numero); return }
    setEtat({ filtreLots: 'tous', q: '', lotDeplie: cible.lot_id })
    setNumeroSaisi('')
  }

  // La ligne dépliée par « Aller au lot n° » vient sous les yeux.
  useEffect(() => {
    if (ouvert && large) lignes.current[ouvert.lot_id]?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
  }, [ouvert?.lot_id, large])

  const surTouche = (e, lot) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); basculer(lot) }
  }

  return (
    <div ref={setRacine} className="@container/journal flex flex-col gap-3.5 min-w-0">
      <div className="@container/barre-lots flex flex-col gap-2.5">
        <div className="flex items-center gap-2 flex-wrap">
          <DateRefPicker />
          <SearchField
            value={etat.q} onChange={(v) => setEtat({ q: v })} placeholder="Rechercher un lot, une variété…"
            className="relative basis-full order-last min-w-0 @[30rem]/barre-lots:basis-0 @[30rem]/barre-lots:flex-1 @[30rem]/barre-lots:order-none @[30rem]/barre-lots:max-w-[340px] @[30rem]/barre-lots:ml-auto"
            aria-label="Rechercher un lot"
          />
          {/* [US-209 / CA11] Le numéro écrit au crayon sur l'étiquette déplie la fiche du lot. */}
          <form onSubmit={allerAuLot} className="flex items-center gap-1.5 min-h-[38px] pl-3 pr-1.5 rounded-[10px] border border-border bg-card focus-within:border-brand">
            <label htmlFor="aller-au-lot" className="text-[12.5px] font-semibold text-txt2 whitespace-nowrap">Aller au lot n°</label>
            <input
              id="aller-au-lot" inputMode="numeric" value={numeroSaisi} onChange={(e) => setNumeroSaisi(e.target.value)}
              className="w-[54px] h-7 px-2 rounded-[7px] border border-border bg-card-alt text-[13px] text-txt outline-none" placeholder="128"
            />
          </form>
        </div>
        <div className="flex items-center gap-2.5 flex-wrap">
          <div role="radiogroup" aria-label="Filtrer les lots" className="flex flex-1 @[40rem]/barre-lots:flex-none gap-[3px] bg-card-alt rounded-[10px] p-[3px]">
            {FILTRES.map((x) => (
              <button
                key={x.cle} type="button" role="radio" aria-checked={filtre === x.cle} onClick={() => setEtat({ filtreLots: x.cle, lotDeplie: null })}
                className={`flex-1 @[40rem]/barre-lots:flex-none min-h-[40px] @[40rem]/barre-lots:min-h-[32px] px-[11px] rounded-lg text-[12px] @[40rem]/barre-lots:text-[12.5px] flex flex-col @[40rem]/barre-lots:flex-row items-center justify-center gap-0 @[40rem]/barre-lots:gap-1.5 leading-tight whitespace-nowrap ${filtre === x.cle ? 'bg-card text-txt font-bold shadow-card' : 'text-txt2 font-medium'}`}
              >
                {x.libelle} <b className={`text-[13px] @[40rem]/barre-lots:text-[12px] font-bold ${filtre === x.cle ? 'text-txt' : 'text-txt3'}`}>{comptes[x.cle]}</b>
              </button>
            ))}
          </div>
          {large && (
            <div role="radiogroup" aria-label="Fenêtre de temps" className="flex gap-[3px] bg-card-alt rounded-[10px] p-[3px]">
              {['saison', 'recent'].map((z) => (
                <button key={z} type="button" role="radio" aria-checked={zoom === z} onClick={() => setEtat({ zoom: z })}
                  className={`min-h-[32px] px-[11px] rounded-lg text-[12.5px] whitespace-nowrap ${zoom === z ? 'bg-card text-txt font-bold shadow-card' : 'text-txt2 font-medium'}`}>
                  {z === 'saison' ? 'Saison' : fRecent.libelle}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <Bilan lots={visibles} aujourdhui={aujourdhui} />

      <div className={large ? 'bg-card border border-border rounded-[18px] shadow-card' : 'flex flex-col gap-1.5'}>
        {large && (
          <>
            <div className="flex gap-4 flex-wrap items-center px-4 py-3 border-b border-border text-[12px] text-txt2">
              <span className="font-hand text-[17px] font-bold text-txt">Gestes datés</span>
              {LEGENDE.map(([k, l]) => (
                <span key={k} className="inline-flex gap-1.5 items-center"><i className={`geste statique geste-${k}`} aria-hidden="true"><Picto code={k} /></i>{l}</span>
              ))}
              <span className="inline-flex gap-1.5 items-center"><i className="w-[30px] border-t-2 border-dashed border-txt3" aria-hidden="true" />sans geste depuis</span>
              <span className="inline-flex gap-1.5 items-center"><i className="w-[30px] h-3 rounded-md fenetre-terre" aria-hidden="true" />mise en terre prévue</span>
            </div>
            <div className="grid [grid-template-columns:92px_220px_minmax(0,1fr)_200px] min-h-[34px] text-[10.5px] font-bold uppercase tracking-[.06em] text-txt3 border-b border-border items-center">
              <span className="pl-4">Semés en</span>
              <span className="px-3">Lot</span>
              <span ref={setAxe} className="block"><EnteteFrise f={f} aujourdhui={aujourdhui} mois={mois} /></span>
              <span className="pl-3.5">Où il en est</span>
            </div>
          </>
        )}

        {!visibles.length && <div className="p-7 text-center text-txt3 text-[13px]">Aucun lot ne correspond.</div>}

        {groupes.map((g) => (
          large ? (
            g.lots.map((lot, i) => {
              const estOuvert = ouvert?.lot_id === lot.lot_id
              return (
                <div key={lot.lot_id} ref={(el) => { lignes.current[lot.lot_id] = el }}>
                  <div
                    role="button" tabIndex={0} aria-expanded={estOuvert} onClick={() => basculer(lot)} onKeyDown={(e) => surTouche(e, lot)}
                    aria-label={`Lot ${lot.numero_lot ?? ''} ${lot.culture}${lot.variete ? ` ${lot.variete}` : ''}, ${LIBELLE_STATUT[statutLot(lot)]}`}
                    className={`group grid [grid-template-columns:92px_220px_minmax(0,1fr)_200px] items-stretch min-h-[68px] cursor-pointer transition-colors ${i === 0 ? 'border-t border-border' : 'border-t border-border-soft'} ${estOuvert ? 'bg-brand-soft' : 'hover:bg-card-alt/50'}`}
                  >
                    <span className="font-hand text-[19px] font-bold text-txt2 pt-2.5 pl-4 leading-none">{i === 0 ? g.mois : ''}</span>
                    <span className="flex items-center gap-2 px-3 min-w-0">
                      <b className="font-hand text-[20px] leading-none text-txt min-w-[28px]">{lot.numero_lot != null ? `#${lot.numero_lot}` : ''}</b>
                      <span className="min-w-0 font-bold text-[13.5px] text-txt underline decoration-border group-hover:decoration-brand underline-offset-4 whitespace-nowrap overflow-hidden text-ellipsis">{nomDuLot(lot)}</span>
                      <ChevronRight size={16} aria-hidden="true" className={`ml-auto shrink-0 transition-transform ${estOuvert ? 'rotate-90 text-brand' : 'text-txt3'}`} />
                    </span>
                    <Frise lot={lot} f={f} aujourdhui={aujourdhui} largeur={largeurAxe} mois={mois} />
                    <span className="flex flex-col justify-center gap-0.5 px-3.5 py-1.5">
                      <PastilleStatut lot={lot} />
                      <small className="text-[11.5px] text-txt2 leading-tight">{etatLigne(lot)}</small>
                    </span>
                  </div>
                  {estOuvert && <FicheDepliee lot={lot} aujourdhui={aujourdhui} onAgir={onAgir} onFermer={fermer} />}
                </div>
              )
            })
          ) : (
            <div key={g.cle} className="flex flex-col gap-1.5">
              <div className="font-hand text-[18px] font-bold text-txt2 mt-1.5 -mb-0.5 ml-0.5">{g.mois}</div>
              <div className="bg-card border border-border rounded-[14px] overflow-hidden shadow-card">
                {g.lots.map((lot, i) => (
                  <div
                    key={lot.lot_id} role="button" tabIndex={0} onClick={() => basculer(lot)} onKeyDown={(e) => surTouche(e, lot)}
                    aria-label={`Lot ${lot.numero_lot ?? ''} ${lot.culture}${lot.variete ? ` ${lot.variete}` : ''}, ${LIBELLE_STATUT[statutLot(lot)]}`}
                    className={`flex flex-col gap-1 pt-2 pb-1.5 pl-3 pr-2.5 min-h-[56px] cursor-pointer active:bg-brand-soft ${i > 0 ? 'border-t border-border-soft' : ''}`}
                  >
                    <div className="flex items-center gap-2">
                      <b className="font-hand text-[19px] leading-none text-txt">{lot.numero_lot != null ? `#${lot.numero_lot}` : ''}</b>
                      <span className="flex-1 min-w-0 font-bold text-[13.5px] text-txt whitespace-nowrap overflow-hidden text-ellipsis">{nomDuLot(lot)}</span>
                      <PastilleStatut lot={lot} />
                      <ChevronRight size={16} className="text-txt3 shrink-0" aria-hidden="true" />
                    </div>
                    <Frise lot={lot} f={fRecent} aujourdhui={aujourdhui} largeur={largeur - 24} etroite mois={moisDeLaFenetre(fRecent)} />
                    <small className="text-[11px] text-txt2">{etatLigne(lot)}</small>
                  </div>
                ))}
              </div>
            </div>
          )
        ))}
      </div>

      <p className="text-[11.5px] text-txt3">
        Un geste dont la date n'est pas connue est compté dans la fiche, sans être posé sur la frise.
      </p>

      {ouvert && !large && <FichePleinEcran lot={ouvert} aujourdhui={aujourdhui} onAgir={onAgir} onFermer={fermer} />}
    </div>
  )
}
