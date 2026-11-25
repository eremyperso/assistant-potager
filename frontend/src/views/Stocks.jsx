// [US-067] Écran Stocks — les cultures EN TERRE (plantées ou semées en pleine terre), rangées par PARCELLE.
// [US-354 / CA4-CA6] Sur le socle commun : quatre chiffres en Lora 20 px (la tuile des kg est un bouton
// orangé « Comparer les saisons › » qui ouvre « Récoltes par saison » dans le panneau partagé — une
// feuille sur mobile, le panneau droit sur ordinateur), des cartes par parcelle dont chaque ligne porte une
// petite pastille d'étape, sa quantité (plants, ou surface d'un semis en m²) et sa récolte. La recherche,
// Filtrer (famille, lettre, origine) et les exports (⋯) sont déclarés à la coquille ; le Mot de Gaston
// propose de placer les godets qui attendent.
//
// Décision du 25/11 : plus de godets ni de graines en pépinière ici (c'est la Pépinière), et une ligne par
// culture ET par parcelle. Les lignes viennent de `GET /plan` (ce qui est en place, par parcelle) ; la récolte
// de `GET /stats/varietes`. Une récolte en pièces n'est jamais convertie en kg (US-036, INC-008) : les kg de
// la tuile et de la comparaison viennent de `GET /stats/rendement`.
import { useState, useEffect, useMemo, useRef } from 'react'
import { RelectureAuRetourProvider } from '../hooks/useRelectureAuRetour.jsx'
import { Leaf } from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { useCoquille, useDeclarerEcran } from '../context/CoquilleContext.jsx'
import {
  lignesDeStock, groupesParParcelle, quatreChiffres, repondALaRecherche, anneesAChercher, saisonsDepuis, kgEnLettres,
  motDesStocks,
} from '../lib/stocksSocle.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import FeuilleFiltres, { GroupeChoix } from '../components/FeuilleFiltres.jsx'
import RecoltesParSaison from '../components/RecoltesParSaison.jsx'
import { useFiches } from '../hooks/useFiches.jsx'
import { EnTeteSection, ListeSocle, LigneSocle } from '../components/SectionSocle.jsx'

// ── Constantes de référence — mêmes libellés que le calcul serveur (US-072) ────

const ORIGINE_LABELS = {
  'pépinière':          'Pépinière',
  'pied_acheté':        'Pied acheté',
  'semis_pleine_terre': 'Semis pleine terre',
  'non_localisé':       'Non localisé',
}
const ORIGINE_OPTIONS = ['Toutes origines', 'Pépinière', 'Pied acheté', 'Semis pleine terre', 'Non localisé']
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')
const TOUTES = 'Toutes'
const TOUTES_ORIGINES = 'Toutes origines'

function iniOf(nom) {
  const c = (nom || '').normalize('NFD').replace(/\p{Diacritic}/gu, '')[0]
  return c ? c.toUpperCase() : '?'
}

// ── Export CSV/JSON — la liste affichée après filtres ───────────────────────────────────────────

const csvEscape = (v) => {
  const s = String(v ?? '')
  return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function telecharger(nom, contenu, mime) {
  const url = URL.createObjectURL(new Blob([contenu], { type: mime }))
  const a = document.createElement('a')
  a.href = url; a.download = nom
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const EXPORT_HEADERS = ['Parcelle', 'Culture', 'Variété', 'Famille', 'Origine', 'Quantité en terre', 'Unité', 'Récolté (kg)']

const ligneExport = (l) => ({
  parcelle: l.parcelle, culture: l.culture, variete: l.variete ?? '', famille: l.famille ?? '',
  origine: ORIGINE_LABELS[l.origine] ?? l.origine ?? '', quantite: l.nbPlants || l.surfaceM2 || '', unite: l.unite ?? '',
  recolte: Math.round((l.recolteKg || 0) * 100) / 100,
})

function exporter(format, rows, jour) {
  if (format === 'csv') {
    const csv = [EXPORT_HEADERS.join(';'), ...rows.map(ligneExport).map((r) => Object.values(r).map(csvEscape).join(';'))].join('\n')
    telecharger(`stocks-${jour}.csv`, `﻿${csv}`, 'text/csv;charset=utf-8')
  } else {
    telecharger(`stocks-${jour}.json`, JSON.stringify({ date_ref: jour, stocks: rows.map(ligneExport) }, null, 2), 'application/json')
  }
}

// ── Les quatre chiffres (CA4) ───────────────────────────────────────────────────────────────

function Chiffre({ valeur, libelle }) {
  return (
    <div className="rounded-[12px] border border-border bg-card px-3 py-2.5 text-left text-[12px] text-txt2">
      <b className="mb-0.5 block font-serif text-[20px] font-bold leading-[1.1] text-txt">{valeur}</b>
      {libelle}
    </div>
  )
}

/** La tuile des kg : un bouton orangé qui ouvre la comparaison des saisons. */
function TuileKg({ valeur, libelle, onOuvrir }) {
  return (
    <button
      type="button" onClick={onOuvrir}
      className="rounded-[12px] border border-[#F3C796] bg-[#FFFAF3] px-3 py-2.5 text-left text-[12px] text-txt2 hover:border-amber focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand dark:border-amber dark:bg-amber-soft"
    >
      <b className="mb-0.5 block font-serif text-[20px] font-bold leading-[1.1] text-txt">{valeur}</b>
      {libelle}
      <span className="mt-1 block font-bold text-brand-text">Comparer les saisons ›</span>
    </button>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────────────────────

export default function Stocks({ refresh }) {
  const { dateRef } = useDateRef()
  const { potagerId } = usePotager()
  const { ouvrirPanneau, fermerPanneau } = useCoquille()
  const [data, setData] = useState(null)
  const [saisons, setSaisons] = useState([])
  const [lots, setLots] = useState([])
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [q, setQ] = useState('')
  const [fam, setFam] = useState(TOUTES)
  const [letter, setLetter] = useState(null)
  const [origineFiltre, setOrigineFiltre] = useState(TOUTES_ORIGINES)
  const [filtresOuverts, setFiltresOuverts] = useState(false)
  const { ouvrirCulture } = useFiches()   // [US-355 / CA1] une ligne ouvre la fiche commune de sa culture
  const panneauOuvertParMoi = useRef(false)

  async function load() {
    setLoading(true); setError(null)
    try {
      const stats = await api.statsVarietes(dateRef, potagerId)
      setData(stats)
      // Ce qui nourrit les kg de l'année, la comparaison des saisons et le mot : leur échec n'ôte rien à
      // l'écran (une tuile à 0 kg, pas de mot).
      const annee = Number((stats?.date_ref_effective || dateRef || new Date().toISOString()).slice(0, 4))
      const [lectures, pep, pl] = await Promise.all([
        Promise.all(anneesAChercher(annee).map((a) => api.rendement(a, dateRef, potagerId).catch(() => null))),
        api.pepiniereLots(dateRef, potagerId).catch(() => null),
        api.plan(dateRef, potagerId).catch(() => null),
      ])
      setSaisons(saisonsDepuis(lectures))
      setLots(pep?.lots ?? [])
      setPlan(pl)
    }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [refresh, dateRef, potagerId]) // eslint-disable-line react-hooks/exhaustive-deps

  // [US-067 / CA5, CA6, CA8] La famille vient du Plan (culture_config → familles_botaniques côté serveur).
  // Les lignes sont ce qui est EN TERRE, une par culture/variété et par parcelle.
  const varietes = useMemo(() => lignesDeStock(plan, data?.varietes ?? []).map((d) => ({ ...d, fam: d.famille || 'Autres' })), [plan, data])
  const fams = useMemo(() => [...new Set(varietes.map((d) => d.fam))].sort((a, b) =>
    a === 'Autres' ? 1 : b === 'Autres' ? -1 : a.localeCompare(b, 'fr')), [varietes])
  const base = useMemo(() => varietes.filter((d) => fam === TOUTES || d.fam === fam), [varietes, fam])
  const activeLetters = useMemo(() => new Set(base.map((d) => iniOf(d.culture))), [base])

  const list = useMemo(() => base.filter((d) => {
    if (!repondALaRecherche(d, q)) return false
    if (letter && iniOf(d.culture) !== letter) return false
    if (origineFiltre !== TOUTES_ORIGINES && (ORIGINE_LABELS[d.origine] ?? d.origine) !== origineFiltre) return false
    return true
  }), [base, q, letter, origineFiltre])

  const jourLu = data?.date_ref_effective || dateRef || new Date().toISOString().slice(0, 10)
  const anneeLue = Number(jourLu.slice(0, 4))
  const kgAnnee = saisons.find((s) => s.annee === anneeLue)?.total ?? 0
  const chiffres = quatreChiffres(varietes, kgAnnee, anneeLue, data?.varietes)
  const groupes = useMemo(() => groupesParParcelle(list), [list])
  const mot = useMemo(() => motDesStocks({ lots, plan, aujourdhui: jourLu }), [lots, plan, jourLu])
  const nombreFiltres = (fam !== TOUTES ? 1 : 0) + (letter ? 1 : 0) + (origineFiltre !== TOUTES_ORIGINES ? 1 : 0)

  // [CA5] « Récoltes par saison » : un occupant du panneau partagé (feuille sur mobile, panneau droit sur ordinateur).
  function ouvrirSaisons() {
    panneauOuvertParMoi.current = true
    ouvrirPanneau({
      cle: 'recoltes', titre: 'Récoltes par saison',
      contenu: <RecoltesParSaison saisons={saisons} jourLu={jourLu} anneeInitiale={anneeLue} />,
    })
  }
  useEffect(() => () => { if (panneauOuvertParMoi.current) fermerPanneau() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // [CA4, CA6] La barre (recherche, Filtrer, exports) et le mot vont à la coquille.
  useDeclarerEcran({
    mot,
    barre: {
      recherche: { placeholder: 'Culture, variété ou parcelle', valeur: q, onChange: setQ },
      filtre: { nombre: nombreFiltres, onOuvrir: () => setFiltresOuverts(true) },
      menu: { exporterCsv: () => exporter('csv', list, jourLu), exporterJson: () => exporter('json', list, jourLu) },
    },
  }, [JSON.stringify(mot), q, nombreFiltres, list, jourLu])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error) return <ApiError message={error} onRetry={load} />

  if (!varietes.length) return (
    <div className="mt-12 flex flex-col items-center gap-2 text-txt3">
      <Leaf size={36} />
      <p className="text-base">Rien n’est en terre pour l’instant.</p>
      <p className="max-w-[34ch] text-center text-[12.5px]">Les stocks comptent les cultures plantées ou semées en pleine terre ; les godets et les semis en pépinière se lisent dans la Pépinière.</p>
    </div>
  )

  return (
    // [US-196 / CA12] Un geste lancé depuis la fiche relit les stocks UNE FOIS au retour sur l'onglet.
    <RelectureAuRetourProvider relire={load}>
    <div className="@container/stocks flex flex-col gap-3.5">
      <section aria-label="Chiffres du potager" className="grid grid-cols-2 gap-2 @[700px]/stocks:grid-cols-4">
        <Chiffre valeur={chiffres.plants} libelle={`plants en terre${chiffres.surface > 0 ? ` · ${String(Math.round(chiffres.surface * 100) / 100).replace('.', ',')} m² semés` : ''}`} />
        <Chiffre valeur={chiffres.cultures} libelle={chiffres.cultures > 1 ? 'cultures en place' : 'culture en place'} />
        <TuileKg valeur={kgEnLettres(chiffres.kg)} libelle={chiffres.kgLibelle} onOuvrir={ouvrirSaisons} />
        <Chiffre valeur={chiffres.perdues} libelle="unités perdues" />
      </section>

      {groupes.length === 0 ? (
        <p className="py-8 text-center text-[13px] text-txt3">Aucune culture pour ce filtre.</p>
      ) : (
        <div className="grid items-start gap-3.5 @[700px]/stocks:grid-cols-2">
          {groupes.map((g) => (
            <section key={g.cle}>
              <EnTeteSection titre={g.titre} />
              <ListeSocle>
                {g.lignes.map((l) => (
                  <LigneSocle
                    key={l.cle} etape={l.etape} emoji={l.emoji} titre={l.titre} variete={l.variete}
                    droite={l.droite} detail={l.detail} nomAccessible={l.nomAccessible}
                    onOuvrir={() => ouvrirCulture(l.selection)}
                  />
                ))}
              </ListeSocle>
            </section>
          ))}
        </div>
      )}

      {/* [CA4] La famille et l'ordre alphabétique sont des filtres dans « Filtrer » (avec l'origine) ; le regroupement est par parcelle. */}
      {filtresOuverts && (
        <FeuilleFiltres
          onFermer={() => setFiltresOuverts(false)} peutEffacer={nombreFiltres > 0}
          onEffacer={() => { setFam(TOUTES); setLetter(null); setOrigineFiltre(TOUTES_ORIGINES) }}
        >
          <GroupeChoix
            titre="Famille botanique"
            options={[TOUTES, ...fams].map((f) => ({ valeur: f, libelle: f }))}
            valeur={fam} onChoisir={(f) => { setFam(f); setLetter(null) }}
          />
          <fieldset>
            <legend className="mb-2 text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">Ordre alphabétique</legend>
            <div className="flex flex-wrap gap-1">
              <button
                type="button" aria-pressed={letter === null} onClick={() => setLetter(null)}
                className={`h-8 min-w-[34px] rounded-md border px-2 text-[12px] font-bold ${letter === null ? 'border-border bg-card text-txt' : 'border-transparent text-txt3'}`}
              >
                Tout
              </button>
              {ALPHABET.map((L) => {
                const active = activeLetters.has(L)
                return (
                  <button
                    key={L} type="button" disabled={!active} aria-pressed={letter === L} onClick={() => setLetter(letter === L ? null : L)}
                    className={`h-8 w-8 rounded-md text-[12.5px] ${letter === L ? 'bg-brand font-bold text-white dark:text-bg' : active ? 'font-bold text-brand-text' : 'text-txt3 opacity-35'}`}
                  >
                    {L}
                  </button>
                )
              })}
            </div>
          </fieldset>
          <GroupeChoix
            titre="Origine" options={ORIGINE_OPTIONS.map((o) => ({ valeur: o, libelle: o }))}
            valeur={origineFiltre} onChoisir={setOrigineFiltre}
          />
        </FeuilleFiltres>
      )}

    </div>
    </RelectureAuRetourProvider>
  )
}
