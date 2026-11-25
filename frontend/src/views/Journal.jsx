// [US-063] Écran Journal — remplace `Historique.jsx` et porte la donnée réelle de `GET /historique`.
// [US-354 / CA7-CA9] Sur le socle commun : jours en capitales, notes du jour REGROUPÉES (« 3 notes »,
// la première en Kalam, « 1 sans texte », « + 1 autre »), gestes en ligne avec leur pastille (récolte,
// paillage, perte en rouge). La barre d'outils (date, « Culture, parcelle ou mot », Filtrer, ⋯) et le
// Mot de Gaston (le bilan de la semaine, sans action) sont déclarés à la coquille.
//
// La phrase d'un geste est reconstruite des champs réels (`phraseEvenement`) ; l'heure n'existe nulle
// part dans le modèle et n'est donc pas affichée. L'API reste paginée ; le regroupement par jour et
// celui des notes sont un habillage de la page déjà chargée.
import { useState, useEffect, useMemo } from 'react'
import {
  ChevronLeft, ChevronRight, Clock, ShoppingBasket, Sprout, Leaf, Droplet, Skull, Package, Euro, Scissors,
  NotebookText, MoreHorizontal,
} from 'lucide-react'
import { api } from '../lib/api.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { useDateRef } from '../context/AppContext.jsx'
import { useIntention, useEtatEcran, useNavigation } from '../context/NavigationContext.jsx'
import { useDeclarerEcran } from '../context/CoquilleContext.jsx'
import { useFiches } from '../hooks/useFiches.jsx'
import { libelleAction } from '../lib/journal.js'
import {
  joursDuJournal, titreDuGroupe, libelleAutres, libelleSansTexte, repondALaRecherche, motDuJournal, debutDuBilan,
} from '../lib/journalSocle.js'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import ApiError from '../components/ApiError.jsx'
import FeuilleFiltres, { GroupeChoix } from '../components/FeuilleFiltres.jsx'
import { PastilleEtape, IconeLot } from '../components/ui'

// ── Catégories de filtre — les 9 de la maquette (US-063 / CA3) ─────────────────────────────────
// Une catégorie recouvre parfois plusieurs `type_action` : `valeurs` part au serveur en liste séparée
// par des virgules — filtrer côté client fausserait la pagination, calculée côté serveur.
const CATEGORIES = [
  { label: 'Récoltes',    valeurs: ['recolte'],                 icon: ShoppingBasket },
  { label: 'Semis',       valeurs: ['semis'],                   icon: Sprout },
  { label: 'Lots godet',  valeurs: ['mise_en_godet', 'deplacement', 'levee'], icon: Package },
  { label: 'Plantations', valeurs: ['plantation', 'repiquage'], icon: Leaf },
  { label: 'Arrosages',   valeurs: ['arrosage'],                icon: Droplet },
  { label: 'Ventes',      valeurs: ['vendu'],                   icon: Euro },
  { label: 'Pertes',      valeurs: ['perte', 'perte_godet'],    icon: Skull },
  { label: 'Entretien',   icon: Scissors,
    valeurs: ['desherbage', 'paillage', 'fertilisation', 'traitement', 'taille', 'tuteurage'] },
  { label: 'Notes',       valeurs: ['observation'],             icon: NotebookText },
]

const TOUTES_ACTIONS = 'Toutes les actions'
const CATEGORIE_PAR_LABEL = Object.fromEntries(CATEGORIES.map((c) => [c.label, c]))
const OPTIONS_CATEGORIES = [
  { valeur: TOUTES_ACTIONS, libelle: TOUTES_ACTIONS },
  ...CATEGORIES.map((c) => ({ valeur: c.label, libelle: c.label })),
]

// L'icône d'un geste est indexée par `type_action` réel, dérivée des catégories du filtre.
const ICONE_PAR_ACTION = Object.fromEntries(CATEGORIES.flatMap((c) => c.valeurs.map((v) => [v, c.icon])))

const PAGE_SIZE = 30

// ── Export CSV/JSON — page affichée après filtres, jamais tout l'historique ────────────────────

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

// L'export reste tabulaire (un champ par colonne), jamais la phrase reconstruite : une phrase se
// relit, elle ne se retrie ni ne se recalcule dans un tableur.
const EXPORT_HEADERS = ['Date', 'Action', 'Culture', 'Variété', 'Parcelle', 'Quantité', 'Unité', 'Godets']
const ligneExport = (e) => ({
  date: e.date, action: libelleAction(e.type_action), culture: e.culture ?? '', variete: e.variete ?? '',
  parcelle: e.parcelle ?? '', quantite: e.quantite ?? '', unite: e.unite ?? '', godets: e.nb_plants_godets ?? '',
})
const jourFichier = () => new Date().toISOString().slice(0, 10)
const exporterCsv = (rows) => telecharger(
  `journal-${jourFichier()}.csv`,
  `﻿${[EXPORT_HEADERS.join(';'), ...rows.map(ligneExport).map((r) => Object.values(r).map(csvEscape).join(';'))].join('\n')}`,
  'text/csv;charset=utf-8',
)
const exporterJson = (rows) => telecharger(`journal-${jourFichier()}.json`, JSON.stringify(rows.map(ligneExport), null, 2), 'application/json')

// ── Pièces ──────────────────────────────────────────────────────────────────────────────────────

/** Un geste en ligne : pastille de récolte, ou pictogramme de l'action ; une perte est en rouge. */
function LigneGeste({ g, onOuvrir }) {
  const Icone = ICONE_PAR_ACTION[g.type] ?? MoreHorizontal
  const contenu = (
    <>
      {g.recolte
        ? <PastilleEtape etape="en_recolte" className="shrink-0" />
        : (
          <span
            aria-hidden="true"
            className={`grid h-10 w-10 shrink-0 place-items-center rounded-[11px] ${g.perte ? 'bg-red-soft text-red' : 'bg-card-alt text-txt2'}`}
          >
            <Icone size={19} />
          </span>
        )}
      <span className="min-w-0 flex-1">
        <b className={`block text-[14px] font-semibold ${g.perte ? 'text-red' : 'text-txt'}`}>{g.titre}</b>
        {g.detail && (
          <small className="flex items-center gap-[3px] text-[12.5px] text-txt2">{/lot #/.test(g.detail) && <IconeLot />}{g.detail}</small>
        )}
      </span>
      {onOuvrir && <ChevronRight size={16} aria-hidden="true" className="shrink-0 self-center text-txt3" />}
    </>
  )
  const classes = 'flex w-full items-start gap-[11px] border-t border-border-soft px-3 py-2.5 text-left first:border-t-0'
  return onOuvrir
    ? <button type="button" onClick={onOuvrir} className={`${classes} hover:bg-card-alt focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand`}>{contenu}</button>
    : <div className={classes}>{contenu}</div>
}

/** Une note : son texte en Kalam, sa culture et sa parcelle dessous. */
function TexteDeNote({ n }) {
  return (
    <>
      <span className="note-carnet-texte mt-0.5 block">{n.texte}</span>
      {n.ou && <small className="block text-[12.5px] text-txt2">{n.ou}</small>}
    </>
  )
}

/** [CA7] Les notes d'un jour regroupées : « n notes », la première, « n sans texte », « + n autres ». */
function GroupeDeNotes({ notes }) {
  const [deplie, setDeplie] = useState(false)
  return (
    <div className="flex w-full items-start gap-[11px] border-t border-border-soft px-3 py-2.5 first:border-t-0">
      <span
        aria-hidden="true"
        className="grid h-10 w-10 shrink-0 place-items-center rounded-[11px] bg-[var(--paper)] text-[#7B6A3E] shadow-[inset_0_0_0_1px_var(--paper-bd)]"
      >
        <NotebookText size={19} />
      </span>
      <span className="min-w-0 flex-1">
        <b className="block text-[14px] font-semibold text-txt">{titreDuGroupe(notes.total)}</b>
        {notes.premiere && <TexteDeNote n={notes.premiere} />}
        {deplie && notes.autres.map((n) => (
          <span key={n.cle} className="mt-2 block border-t border-border-soft pt-2"><TexteDeNote n={n} /></span>
        ))}
        {notes.sansTexte > 0 && <span className="mt-0.5 block text-[12.5px] text-txt3">{libelleSansTexte(notes.sansTexte)}</span>}
        {notes.autres.length > 0 && (
          <button
            type="button" aria-expanded={deplie} onClick={() => setDeplie((d) => !d)}
            className="mt-1 block text-[12.5px] font-bold text-brand-text hover:underline"
          >
            {deplie ? 'Réduire' : libelleAutres(notes.autres.length)}
          </button>
        )}
      </span>
    </div>
  )
}

// ── Vue principale ────────────────────────────────────────────────────────────────────────────

export default function Journal({ refresh }) {
  const { potagerId } = usePotager()
  const { dateRef } = useDateRef()
  const { annoncer } = useNavigation()
  const { ouvrirCulture } = useFiches()   // [US-355 / CA1] un geste ouvre la fiche commune de sa culture
  const [data, setData] = useState({ total: 0, evenements: [] })
  const [semaine, setSemaine] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filtresOuverts, setFiltresOuverts] = useState(false)
  // [US-195 / CA2] « Journal du jour » ouvre cet écran FILTRÉ sur la date — et sur la culture si le
  // lien la donne. [CA9] Les mêmes filtres font l'état exact de l'écran : la coquille les rend tels
  // quels au retour.
  const intention = useIntention('journal', (recue) => {
    setEtat({
      ...(recue.date ? { date: recue.date } : {}),
      ...(recue.culture ? { q: recue.culture } : {}),
      // [US-232 / CA8] « Tout voir » de la carte « Sol et entretien » : une parcelle, et la liste de
      // gestes que le serveur a servie. Le Journal la reçoit, il ne la connaît pas : elle ne diverge
      // donc pas de celle du domaine.
      ...(recue.parcelle ? { parcelle: recue.parcelle } : {}),
      ...(recue.gestes ? { gestes: recue.gestes } : {}),
    })
    // [CA4] Un filtre posé par un lien se dit : sans cela, le lecteur d'écran annonce une liste plus
    // courte sans jamais expliquer pourquoi.
    annoncer(`Journal filtré${recue.date ? ` sur le ${recue.date.split('-').reverse().join('/')}` : ''}${recue.culture ? ` sur ${recue.culture}` : ''}${recue.parcelle ? ` sur la parcelle ${recue.parcelle}` : ''}${recue.gestes ? ' sur les gestes de sol' : ''}.`)
  })
  // Le filtre porte le LIBELLÉ de catégorie (« Pertes »), pas un `type_action`.
  const [etat, setEtat] = useEtatEcran(
    'journal', { action: TOUTES_ACTIONS, q: '', date: null, parcelle: '', gestes: '' }, intention,
  )
  const [page, setPage] = useState(0)

  async function charger(pg = page) {
    setLoading(true); setError(null)
    try {
      const params = { limit: PAGE_SIZE, offset: pg * PAGE_SIZE }
      const categorie = CATEGORIE_PAR_LABEL[etat.action]
      // [US-232 / CA8] Les gestes reçus du lien priment sur la catégorie du menu : ils SONT le filtre.
      if (etat.gestes) params.action = etat.gestes
      else if (categorie) params.action = categorie.valeurs.join(',')
      if (etat.parcelle) params.parcelle = etat.parcelle
      if (etat.date) { params.from = etat.date; params.to = etat.date }
      // [CA9] Le Journal suit la date de la règle des temps : rien après le jour lu.
      if (dateRef) params.date_ref = dateRef
      // [US-083 / CA7] Si on consulte un potager archivé, passer son ID
      if (potagerId) params.potager_id = potagerId
      setData(await api.historique(params))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Le bilan de la semaine (CA8) : une lecture à part, les 7 jours qui finissent le jour lu, sans filtre.
  async function chargerSemaine(jour) {
    try {
      const r = await api.historique({
        from: debutDuBilan(jour), to: jour, limit: 100, ...(potagerId ? { potager_id: potagerId } : {}),
      })
      setSemaine(r?.evenements ?? [])
    } catch { setSemaine([]) }
  }

  // [CA4] Un changement de filtre transmis au serveur ramène à la première page.
  useEffect(() => { setPage(0); charger(0) }, [refresh, etat.action, etat.date, potagerId, etat.parcelle, etat.gestes, dateRef]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { charger(page) }, [page]) // eslint-disable-line react-hooks/exhaustive-deps
  const jourLu = data.date_ref_effective || dateRef || jourFichier()
  useEffect(() => { chargerSemaine(jourLu) }, [jourLu, potagerId, refresh]) // eslint-disable-line react-hooks/exhaustive-deps

  const total = data.total || 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const evenements = data.evenements || []
  const trouves = useMemo(() => evenements.filter((e) => repondALaRecherche(e, etat.q)), [evenements, etat.q])
  const jours = useMemo(() => joursDuJournal(trouves), [trouves])
  const mot = useMemo(() => motDuJournal(semaine), [semaine])

  const nombreFiltres = (etat.action !== TOUTES_ACTIONS ? 1 : 0) + (etat.date ? 1 : 0)
  const retirerFiltreLien = () => setEtat({ parcelle: '', gestes: '' })

  // [CA7-CA8] La barre et le mot vont à la coquille.
  useDeclarerEcran({
    mot,
    barre: {
      recherche: { placeholder: 'Culture, parcelle ou mot', valeur: etat.q ?? '', onChange: (q) => setEtat({ q }) },
      filtre: { nombre: nombreFiltres, onOuvrir: () => setFiltresOuverts(true) },
      menu: { exporterCsv: () => exporterCsv(trouves), exporterJson: () => exporterJson(trouves) },
    },
  }, [JSON.stringify(mot), etat.q, nombreFiltres, trouves])

  return (
    <div className="flex flex-col gap-3.5">
      {/* [US-232 / CA8] Le filtre posé par « Tout voir » — nommé, et retirable : un journal plus court
          sans rien qui l'explique serait un journal qui ment par omission. */}
      {(etat.parcelle || etat.gestes) && (
        <div className="flex items-center gap-2 rounded-lg bg-card-alt px-3 py-2 text-[12.5px] text-txt2">
          <span>
            Filtré sur{etat.parcelle ? <> la parcelle <strong className="text-txt">{etat.parcelle}</strong></> : null}
            {etat.gestes ? <>{etat.parcelle ? ' et ' : ' '}les gestes de sol et d’entretien</> : null}
          </span>
          <button
            type="button" onClick={retirerFiltreLien}
            className="ml-auto whitespace-nowrap rounded font-semibold underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            Retirer ce filtre
          </button>
        </div>
      )}

      {loading ? (
        <LoadingSkeleton lines={6} />
      ) : error ? (
        <ApiError message={error} onRetry={() => charger(page)} />
      ) : jours.length === 0 ? (
        <div className="mt-12 flex flex-col items-center gap-3 text-txt3">
          <Clock size={36} />
          <p className="text-base">Aucun événement enregistré.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {jours.map((j) => (
            <section key={`${j.iso}-${j.label}`} aria-label={j.label}>
              <h3 className="mx-0.5 mb-1.5 text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">{j.label}</h3>
              <div className="overflow-hidden rounded-[14px] border border-border bg-card">
                {j.gestes.map((g) => (
                  <LigneGeste key={g.cle} g={g} onOuvrir={g.selection ? () => ouvrirCulture(g.selection) : null} />
                ))}
                {j.notes && <GroupeDeNotes notes={j.notes} />}
              </div>
            </section>
          ))}
        </div>
      )}

      {!loading && !error && totalPages > 1 && (
        <div className="mt-1 flex items-center justify-between px-1">
          <button
            type="button" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
            aria-label="Page précédente" className="rounded-xl border border-border p-2 text-txt3 disabled:opacity-30"
          >
            <ChevronLeft size={18} />
          </button>
          <span className="text-sm text-txt3">
            Page {page + 1} / {totalPages}
            <span className="ml-1 text-[12px]">({total} événements)</span>
          </span>
          <button
            type="button" onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
            aria-label="Page suivante" className="rounded-xl border border-border p-2 text-txt3 disabled:opacity-30"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}

      {/* [CA7] « Filtrer » : le type de geste, et un jour précis (US-195). */}
      {filtresOuverts && (
        <FeuilleFiltres
          onFermer={() => setFiltresOuverts(false)} peutEffacer={nombreFiltres > 0}
          onEffacer={() => setEtat({ action: TOUTES_ACTIONS, date: null })}
        >
          <GroupeChoix titre="Type de geste" options={OPTIONS_CATEGORIES} valeur={etat.action} onChoisir={(v) => setEtat({ action: v })} />
          <label className="flex flex-col gap-2 text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">
            Un jour précis
            <input
              type="date" value={etat.date || ''} onChange={(e) => setEtat({ date: e.target.value || null })}
              className="h-10 rounded-xl border border-border bg-surface px-3 text-[13px] font-normal normal-case tracking-normal text-txt"
            />
          </label>
        </FeuilleFiltres>
      )}
    </div>
  )
}
