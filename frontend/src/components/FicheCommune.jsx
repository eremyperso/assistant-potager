import { useEffect, useRef, useState } from 'react'
import {
  X, Pencil, NotebookText, ShoppingBasket, Sprout, Leaf, Droplet, Euro, Skull, Scissors, Package, MoreHorizontal,
} from 'lucide-react'
import { api } from '../lib/api.js'
import { useDateRef } from '../context/AppContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { useNavigation } from '../context/NavigationContext.jsx'
import { useCoquille } from '../context/CoquilleContext.jsx'
import { peutEnregistrer } from '../lib/gestes.js'
import { ouvrirGastonAvec, ouvrirGastonSur, publierSelection } from '../lib/contexteCompagnon.js'
import { sujetCulture } from '../lib/ouvertureGaston.js'  // [US-358]
import { origine, contexteNoter, nomEvenement, ETAT_A_VENIR } from '../lib/suiviCulture.js'
import {
  ONGLETS, ONGLET_SUIVI, ONGLET_REFERENCE, enteteDeFiche, emplacementDeFiche, etapeDeFiche, libelleDuBoutonNoter,
  friseDeFiche, carnetDeCulture, nombreDeRecoltes, ligneDeRecolte, phraseOrigine, resoudreSelection,
} from '../lib/ficheCommune.js'
import LoadingSkeleton from './LoadingSkeleton.jsx'
import ApiError from './ApiError.jsx'
import ReferenceCulture from './ReferenceCulture.jsx'
import { Frise } from './SuiviCulture.jsx'
import { PuceEtape, PastilleEtape, NoteCarnet, IconeLot } from './ui'

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'
const TITRE_BLOC = 'mb-2 mt-5 text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2'

/** Le pictogramme d'un geste, par `type_action` (les mêmes familles que le filtre du Journal). */
const ICONE_PAR_ACTION = {
  recolte: ShoppingBasket, semis: Sprout, mise_en_godet: Package, deplacement: Package, levee: Sprout,
  plantation: Leaf, repiquage: Leaf, arrosage: Droplet, vendu: Euro, perte: Skull, perte_godet: Skull,
  desherbage: Scissors, paillage: Scissors, fertilisation: Scissors, traitement: Scissors, taille: Scissors, tuteurage: Scissors,
}

/** Les étapes d'une culture sans étape notée : la frise est là, toute grisée (cas « à placer »). */
const ETAPES_SANS_SUIVI = ['plantee', 'croissance', 'en_recolte', 'terminee']
const friseGrisee = () => ETAPES_SANS_SUIVI.map((cle) => ({
  cle, nom: nomEvenement(cle), etat: ETAT_A_VENIR, date: '', variante: 'plein', aConfirmer: false,
}))

/** Une ligne du carnet : la pastille de sa nature à gauche, son titre et sa date, puis son mot s'il en a un. */
function LigneDeCarnet({ l }) {
  if (l.type === 'note') {
    return (
      <li className="grid grid-cols-[30px_1fr] items-start gap-2.5 border-t border-border-soft py-2 first:border-t-0">
        <span aria-hidden="true" className="grid h-[30px] w-[30px] place-items-center rounded-full bg-[var(--paper)] text-[#7B6A3E] shadow-[inset_0_0_0_1px_var(--paper-bd)]">
          <NotebookText size={15} />
        </span>
        <NoteCarnet dicte={null} texte={l.texte} date={l.date} lieu={l.lieu} />
      </li>
    )
  }
  const Icone = ICONE_PAR_ACTION[l.action] ?? MoreHorizontal
  return (
    <li className="grid grid-cols-[30px_1fr] items-start gap-2.5 border-t border-border-soft py-2 first:border-t-0">
      {l.type === 'recolte'
        ? <PastilleEtape etape="en_recolte" petite />
        : (
          <span aria-hidden="true" className={`grid h-[30px] w-[30px] place-items-center rounded-full ${l.perte ? 'bg-red-soft text-red' : 'bg-card-alt text-txt2'}`}>
            <Icone size={15} />
          </span>
        )}
      <span className="min-w-0">
        <b className={`text-[13.5px] font-semibold ${l.perte ? 'text-red' : 'text-txt'}`}>{l.titre}</b>
        <span className="ml-1.5 text-[12px] text-txt2">{l.date}</span>
        {l.detail && <small className="block text-[12px] text-txt2">{l.detail}</small>}
        {l.texte && <span className="note-carnet-texte mt-0.5 block">{l.texte}</span>}
      </span>
    </li>
  )
}

/**
 * [US-355 / CA1, CA2] La fiche commune d'une culture : la même ouverte depuis le Tableau de bord, le Plan, Cultures,
 * les Stocks et le Journal (feuille sur mobile, panneau droit sur ordinateur — le panneau partagé la porte).
 *
 * L'onglet **Suivi** reprend le suivi de culture (US-322) : la frise des étapes, le carnet de la culture
 * (`GET /historique` filtré) et l'origine. L'onglet **Référence** reprend la fiche culture (US-207).
 *
 * `selection` : `{ culture, variete?, parcelleId?, parcelle?, rang?, quantiteTexte?, origineTexte? }`. Sans
 * `parcelleId` la culture n'a pas encore de place : la fiche le dit, sans étape. Une lecture à la fois par onglet,
 * aucune règle recalculée ici : l'étape, « à confirmer » et le cumul récolté viennent du serveur.
 * `publier` : le Plan relaie la culture choisie à la barre basse « Noter » (US-325). `onVoirAuPlan` : le Plan ouvre
 * lui-même la parcelle ; ailleurs, « Voir au plan → » referme la fiche et ouvre le Plan sur la parcelle.
 */
export default function FicheCommune({ selection, onglet: ongletInitial = ONGLET_SUIVI, publier = false, onVoirAuPlan = null, onLot = null, onFermer = null }) {
  const { dateRef } = useDateRef()
  const { potagerId, potagerActif } = usePotager()
  const { aller } = useNavigation()
  const { fermerPanneau } = useCoquille()
  const role = potagerActif?.role

  const [onglet, setOnglet] = useState(ongletInitial)
  const [referenceOuverte, setReferenceOuverte] = useState(ongletInitial === ONGLET_REFERENCE)
  const [suivi, setSuivi] = useState(null)
  const [evenements, setEvenements] = useState(null)
  const [carnetEchoue, setCarnetEchoue] = useState(false)
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState(null)
  const titre = useRef(null)
  // `sel` : la culture une fois sa place résolue. Une fiche ouverte depuis le Journal ou les Stocks ne connaît pas la
  // parcelle (`parcelleId` absent) : on la cherche dans le plan, une lecture ; `null` dit « pas encore placée ».
  const [sel, setSel] = useState(selection)
  const aUnePlace = sel.parcelleId != null

  async function charger() {
    setChargement(true)
    setErreur(null)
    setCarnetEchoue(false)
    let cible = selection
    if (selection.parcelleId === undefined) {
      try {
        const plan = await api.plan(dateRef, potagerId)
        cible = { ...selection, ...(resoudreSelection(plan, selection) || { parcelleId: null }) }
      } catch {
        cible = { ...selection, parcelleId: null }
      }
    }
    setSel(cible)
    const place = cible.parcelleId != null
    const params = {
      culture: cible.culture, limit: 100,
      ...(cible.parcelle && place && { parcelle: cible.parcelle }),
      ...(dateRef && { date_ref: dateRef }), ...(potagerId && { potager_id: potagerId }),
    }
    const [s, h] = await Promise.allSettled([
      place
        ? api.suiviCulture({ parcelleId: cible.parcelleId, culture: cible.culture, variete: cible.variete, dateRef, potagerId })
        : Promise.resolve(null),
      api.historique(params),
    ])
    if (s.status === 'rejected') setErreur(s.reason?.message || 'Lecture impossible')
    setSuivi(s.status === 'fulfilled' ? s.value : null)
    setEvenements(h.status === 'fulfilled' ? (h.value?.evenements || []) : null)
    setCarnetEchoue(h.status === 'rejected')
    setChargement(false)
  }
  useEffect(() => { charger() }, [selection.parcelleId, selection.culture, selection.variete, dateRef, potagerId])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!chargement) titre.current?.focus() }, [chargement])

  // [US-325 / CA3] Le plan relaie la culture lue à la barre basse « Noter ».
  useEffect(() => {
    if (!publier || !suivi) return
    const contexte = contexteNoter(suivi)
    publierSelection({ ...contexte, rang: sel.rang ?? contexte.rang, ...(suivi.est_pepiniere && { pepiniere: true }) })
  }, [suivi])   // eslint-disable-line react-hooks/exhaustive-deps

  if (chargement) return <div className="p-4"><LoadingSkeleton lines={4} /></div>
  if (erreur) return <div className="p-4"><ApiError message={erreur} onRetry={charger} /></div>

  const t = enteteDeFiche(suivi, sel)
  const place = emplacementDeFiche(suivi, sel)
  const courante = etapeDeFiche(suivi)
  const nbRecoltes = nombreDeRecoltes(evenements || [], { variete: sel.variete })
  const recolte = ligneDeRecolte(suivi, nbRecoltes)
  const etapes = suivi ? friseDeFiche(suivi) : friseGrisee()
  const carnet = carnetDeCulture(evenements || [], { variete: sel.variete })
  const orig = suivi ? origine(suivi) : null
  const texteOrigine = orig ? phraseOrigine(orig) : (sel.origineTexte || null)
  const ecrire = peutEnregistrer(role)

  const voirAuPlan = onVoirAuPlan || (() => {
    fermerPanneau()
    aller('plan', aUnePlace ? { parcelle: sel.parcelleId } : undefined)
  })
  const ouvrirLot = onLot || ((numero) => { fermerPanneau(); aller('pepiniere', { onglet: 'parcours', lot: String(numero) }) })
  const voirLeJournal = () => { fermerPanneau(); aller('journal', { culture: sel.culture }) }
  const noter = () => {
    if (suivi) ouvrirGastonAvec({ ...contexteNoter(suivi), rang: sel.rang ?? contexteNoter(suivi).rang })
    else ouvrirGastonSur({ sujet: sujetCulture(sel.culture, sel.variete) })   // [US-358] sans place : la culture, affichée
  }
  const choisir = (id) => {
    setOnglet(id)
    if (id === ONGLET_REFERENCE) setReferenceOuverte(true)
  }

  return (
    <article aria-label={`Fiche : ${t.titre}${sel.variete ? ` ${sel.variete}` : ''}`} className="relative p-4 pb-6 text-txt">
      {onFermer && (
        <button
          type="button" onClick={onFermer} aria-label="Fermer la fiche"
          className={`absolute right-3 top-3 z-10 grid h-9 w-9 place-items-center rounded-full bg-card-alt text-txt2 ${FOCUS}`}
        >
          <X size={16} aria-hidden="true" />
        </button>
      )}
      {/* En-tête : emoji 52 px, nom en Lora 21 px, « variété · quantité » */}
      <div className="flex items-start gap-3 pr-11">
        <span aria-hidden="true" className="grid h-[52px] w-[52px] shrink-0 place-items-center rounded-[14px] bg-card-alt text-[28px]">{t.emoji}</span>
        <div className="min-w-0 flex-1">
          <h2 ref={titre} tabIndex={-1} className="font-serif text-[21px] font-semibold leading-tight focus:outline-none">{t.titre}</h2>
          {t.sousTitre && <p className="mt-0.5 text-[12.5px] text-txt2">{t.sousTitre}</p>}
        </div>
      </div>

      {/* Emplacement : « Planche centrale · rang 3 — Voir au plan → », ou « Pas encore placé » en pointillé */}
      <button
        type="button" onClick={voirAuPlan}
        className={`mt-3 flex min-h-[44px] w-full items-center justify-between gap-2 rounded-[11px] px-3 text-left text-[13px] font-semibold ${FOCUS} ${place.place ? 'bg-card-alt' : 'border-[1.5px] border-dashed border-border bg-transparent'}`}
      >
        <span>{place.texte}</span>
        <span className="whitespace-nowrap text-[12.5px] font-semibold text-brand-text">{place.lien}</span>
      </button>

      {/* Étape courante : la puce et « depuis le 20 octobre » (orange quand elle est due) */}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px] text-txt2">
        {courante.aucune ? (
          <>
            <span className="inline-flex items-center rounded-full bg-card-alt px-2.5 py-0.5 text-[11.5px] font-semibold text-txt2">{courante.texte}</span>
            <span>{courante.precision}</span>
          </>
        ) : (
          <>
            <PuceEtape etape={courante.cle} prevue={courante.prevue} />
            <span className={courante.due ? 'font-semibold text-due-tx' : ''}>{courante.texte}</span>
          </>
        )}
      </div>

      {recolte && <p className="mt-2.5 rounded-[9px] px-3 py-2 text-[13px] font-semibold etape-recolte">{recolte}</p>}

      {/* Noter : ouvre Gaston sur cette culture */}
      {ecrire && (
        <button
          type="button" onClick={noter}
          className={`mt-3 inline-flex min-h-[44px] w-full items-center justify-center gap-1.5 rounded-[10px] bg-brand px-4 text-[13.5px] font-semibold text-white hover:opacity-95 ${FOCUS}`}
        >
          <Pencil size={15} aria-hidden="true" />{libelleDuBoutonNoter(suivi)}
        </button>
      )}

      {/* Les deux onglets */}
      <div role="tablist" aria-label="Fiche" className="mt-3 flex gap-[3px] rounded-xl bg-card-alt p-[3px]">
        {ONGLETS.map((o) => (
          <button
            key={o.id} type="button" role="tab" id={`fiche-onglet-${o.id}`} aria-selected={onglet === o.id}
            aria-controls={`fiche-corps-${o.id}`} onClick={() => choisir(o.id)}
            className={`min-h-[38px] flex-1 rounded-[10px] text-[13px] font-semibold ${FOCUS} ${onglet === o.id ? 'bg-surface text-txt shadow-card' : 'text-txt2'}`}
          >
            {o.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`fiche-corps-${ONGLET_SUIVI}`} aria-labelledby={`fiche-onglet-${ONGLET_SUIVI}`} hidden={onglet !== ONGLET_SUIVI}>
        <h3 className={TITRE_BLOC}>Étapes</h3>
        <Frise etapes={etapes} />

        <h3 className={TITRE_BLOC}>Carnet de la culture</h3>
        {carnetEchoue ? (
          <p className="text-[12.5px] text-txt2">
            Le carnet n’a pas pu être lu.{' '}
            <button type="button" onClick={charger} className={`font-semibold text-brand-text underline ${FOCUS}`}>Réessayer</button>
          </p>
        ) : carnet.length === 0 ? (
          <p className="text-[12.5px] text-txt2">Rien de noté pour l’instant.</p>
        ) : (
          <ul>{carnet.map((l) => <LigneDeCarnet key={l.cle} l={l} />)}</ul>
        )}
        <button
          type="button" onClick={voirLeJournal}
          className={`mt-1.5 min-h-[36px] text-[12.5px] font-bold text-brand-text hover:underline ${FOCUS}`}
        >
          Voir dans le Journal →
        </button>

        {texteOrigine && (
          <>
            <h3 className={TITRE_BLOC}>Origine</h3>
            <p className="flex items-center gap-[3px] text-[13px]">{/lot #/.test(texteOrigine) && <IconeLot />}{texteOrigine}</p>
            {orig?.numeroLot != null && (
              <button type="button" onClick={() => ouvrirLot(orig.numeroLot)} className={`mt-0.5 min-h-[32px] text-[12.5px] font-semibold text-brand-text hover:underline ${FOCUS}`}>
                Voir le lot →
              </button>
            )}
          </>
        )}
      </div>

      {referenceOuverte && (
        <div role="tabpanel" id={`fiche-corps-${ONGLET_REFERENCE}`} aria-labelledby={`fiche-onglet-${ONGLET_REFERENCE}`} hidden={onglet !== ONGLET_REFERENCE} className="mt-4">
          <ReferenceCulture
            culture={sel.culture} dateRef={dateRef} potagerId={potagerId}
            parcelleId={sel.parcelleId ?? null} ecran="cultures"
            onOuvrirLot={ouvrirLot}
          />
        </div>
      )}
    </article>
  )
}
