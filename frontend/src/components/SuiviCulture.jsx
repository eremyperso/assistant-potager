// [US-322] Le suivi d'une culture en place : son histoire, de la graine à la récolte.
//
// Ordinateur : le panneau de droite du plan. Mobile : une feuille basse (S1, S2 + S3,
// S4, S5, S6, Photo, « Fiche », dernière note) ; « Fiche » déplie le suivi complet.
// UNE lecture (`GET /plan/suivi`, CA4) ; la mise en mots vit dans `lib/suiviCulture.js`.
import { useState, useEffect, useRef } from 'react'
import { X, Pencil, Camera, Sprout, ShoppingBag, Bean, Mic, ChevronRight } from 'lucide-react'
import { api } from '../lib/api.js'
import {
  enTete, localisation, lignePlace, etapeCourante, bandeauAConfirmer, libelleNoter,
  texteRecolte, frise, origine, notes, contexteNoter, ETAT_FAITE, ETAT_COURANTE,
} from '../lib/suiviCulture.js'
import { ouvrirGastonAvec, publierSelection } from '../lib/contexteCompagnon.js'
import { peutEnregistrer } from '../lib/gestes.js'
import { classesSegment } from '../lib/etapes.js'
import LoadingSkeleton from './LoadingSkeleton.jsx'
import ApiError from './ApiError.jsx'
import { EtiquetteEtape, IconeEtape } from './ui/EtapeCulture.jsx'

/** [S6, US-323] Ouvre Gaston avec la culture du suivi pour contexte. */
const ouvrirGaston = (contexte) => ouvrirGastonAvec(contexte)

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'
const TITRE_BLOC = 'flex items-center justify-between text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2 mt-5 mb-2'

function Frise({ etapes }) {
  return (
    <ol className="flex flex-col">
      {etapes.map((x, i) => (
        <li key={x.cle} className="relative grid grid-cols-[30px_1fr_auto] items-center gap-2.5 min-h-[38px]">
          {i < etapes.length - 1 && (
            <span aria-hidden="true"
              className={`absolute left-[14px] top-[30px] -bottom-2 w-0.5 ${x.etat === ETAT_FAITE ? 'bg-brand' : 'bg-border'}`} />
          )}
          <span aria-hidden="true"
            className={`relative z-[1] grid place-items-center w-[30px] h-[30px] rounded-full
              ${x.etat === ETAT_FAITE || x.etat === ETAT_COURANTE ? classesSegment(x.cle, x.variante) : 'bg-card text-txt3 ring-[1.5px] ring-inset ring-border'}
              ${x.etat === ETAT_COURANTE ? (x.aConfirmer ? 'ring-2 ring-[color:var(--etape-pastille)]' : 'ring-[2.5px] ring-txt') : ''}`}>
            <IconeEtape etape={x.cle} taille={15} />
          </span>
          <b className={`text-[13px] ${x.etat === ETAT_FAITE || x.etat === ETAT_COURANTE ? 'text-txt' : 'font-medium text-txt2'}`}>
            {x.nom}{x.etat === ETAT_COURANTE && <span className="sr-only"> (étape courante{x.aConfirmer ? ', à confirmer' : ''})</span>}
          </b>
          <time className={`text-[12px] whitespace-nowrap ${x.aConfirmer ? 'font-bold text-[color:var(--etape-pastille)]' : 'text-txt2'}`}>{x.date}</time>
        </li>
      ))}
    </ol>
  )
}

function Origine({ o, onLot }) {
  const Icone = o.type === 'pepiniere' ? Sprout : o.type === 'achat' ? ShoppingBag : Bean
  return (
    <div className="flex gap-2.5 items-start rounded-[10px] border border-border px-3 py-2.5 text-[13px]">
      <span aria-hidden="true" className="grid place-items-center w-[30px] h-[30px] shrink-0 rounded-lg bg-brand-soft text-brand">
        <Icone size={17} />
      </span>
      <div className="min-w-0">
        <b className="block text-txt">{o.titre}</b>
        {o.detail && <small className="text-[12px] text-txt2">{o.detail}</small>}
        {o.numeroLot != null && onLot && (
          <button type="button" onClick={() => onLot(o.numeroLot)}
            className={`block mt-0.5 text-[12.5px] font-semibold text-brand-text hover:underline ${FOCUS}`}>
            Voir le lot →
          </button>
        )}
      </div>
    </div>
  )
}

function Notes({ liste }) {
  return (
    <ul className="flex flex-col">
      {liste.map((n, i) => (
        <li key={n.id} className={`grid grid-cols-[86px_1fr] gap-2.5 py-2 text-[13px] ${i ? 'border-t border-border' : ''}`}>
          <time className="text-[12px] text-txt2">{n.date}</time>
          <span className="text-txt">
            {n.dictee && <Mic size={13} role="img" aria-label="dictée" className="inline mr-1 -mt-0.5 text-brand" />}
            {n.texte}
          </span>
        </li>
      ))}
    </ul>
  )
}

/**
 * [US-322] Le suivi. `compact` : la feuille basse mobile (CA7), que « Fiche » déplie en
 * suivi complet. `onClose` absent : pas de bouton Fermer (la feuille a déjà le sien).
 */
export default function SuiviCulture({ selection, dateRef, potagerId, role, compact = false, onClose, onParcelle, onLot, donnees }) {
  const [suivi, setSuivi] = useState(donnees || null)
  const [loading, setLoading] = useState(!donnees)
  const [error, setError] = useState(null)
  const [complet, setComplet] = useState(!compact)
  const titre = useRef(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setSuivi(await api.suiviCulture({
        parcelleId: selection.parcelleId, culture: selection.culture, variete: selection.variete, dateRef, potagerId,
      }))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { if (!donnees) load() }, [selection?.parcelleId, selection?.culture, selection?.variete, dateRef, potagerId])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (suivi && !compact) titre.current?.focus() }, [suivi, compact])
  // [US-325 / CA3] Le suivi lu enrichit la sélection du plan (étape, rang touché) : le bouton
  // « Noter » de la barre basse ouvre Gaston avec les mêmes raccourcis que celui du suivi.
  useEffect(() => {
    if (!suivi || donnees || !selection) return
    const contexte = contexteNoter(suivi)
    publierSelection({
      ...contexte, rang: selection.rang ?? contexte.rang, ...(suivi.est_pepiniere && { pepiniere: true }),
    })
  }, [suivi])   // eslint-disable-line react-hooks/exhaustive-deps

  // [CA1] Échap referme le panneau d'ordinateur (la feuille mobile a le sien : Modal).
  useEffect(() => {
    if (compact || !onClose) return undefined
    const surTouche = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [compact, onClose])

  if (loading) return <LoadingSkeleton lines={4} />
  if (error) return <ApiError message={error} onRetry={load} />
  if (!suivi) return null

  const t = enTete(suivi)
  const loc = localisation(suivi)
  const place = lignePlace(suivi)
  const courante = etapeCourante(suivi)
  const bandeau = bandeauAConfirmer(suivi)
  const recolte = texteRecolte(suivi)
  const etapes = frise(suivi)
  const orig = origine(suivi)
  const lesNotes = notes(suivi)
  const ecrire = peutEnregistrer(role)
  const reduit = compact && !complet

  return (
    <article aria-label={`Suivi : ${t.titre}${suivi.variete ? ` ${suivi.variete}` : ''}`} className="text-txt">
      {/* S1 — En-tête */}
      <div className="flex gap-3 items-start">
        <span aria-hidden="true" className="grid place-items-center w-12 h-12 shrink-0 rounded-xl bg-card-alt text-[26px]">{t.emoji}</span>
        <div className="flex-1 min-w-0">
          <h3 ref={titre} tabIndex={-1} className="font-serif text-[19px] font-semibold leading-tight focus:outline-none">{t.titre}</h3>
          {t.sousTitre && <p className="text-[12.5px] text-txt2 mt-0.5">{t.sousTitre}</p>}
        </div>
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Fermer le suivi"
            className={`grid place-items-center w-11 h-11 -mr-2 -mt-2 rounded-lg text-txt2 hover:bg-card-alt ${FOCUS}`}>
            <X size={18} />
          </button>
        )}
      </div>

      {/* S2 + S3 — Localisation et place sur le rang */}
      {loc && (loc.lien && onParcelle ? (
        <button type="button" onClick={onParcelle}
          className={`mt-3.5 w-full min-h-[44px] flex justify-between items-center gap-2 rounded-[10px] bg-card-alt px-3 py-2.5 text-left text-[13px] font-semibold ${FOCUS}`}>
          <span>{loc.texte}</span>
          <span className="text-[12.5px] text-brand-text whitespace-nowrap">Voir la parcelle →</span>
        </button>
      ) : (
        <p className="mt-3.5 rounded-[10px] bg-card-alt px-3 py-2.5 text-[13px] font-semibold">{loc.texte}</p>
      ))}
      {place && (
        <p className="mt-1 text-[12px] text-txt2" aria-label={place.nomAccessible}>
          {place.texte}{place.depassement && <span className="ml-1.5 font-bold text-red">{place.depassement}</span>}
        </p>
      )}

      {/* S4 — Étape courante */}
      {courante && (
        <div className="flex flex-wrap items-center gap-2 mt-3.5 text-[12.5px] text-txt2">
          <EtiquetteEtape etape={courante.cle} prevue={courante.prevue} />
          {courante.texte && <span>{courante.texte}</span>}
        </div>
      )}

      {/* S5 — À confirmer */}
      {bandeau && (
        <p className="mt-3 flex items-center gap-2 rounded-[10px] border px-2.5 py-2 text-[12.5px] font-semibold text-txt"
          style={{ borderColor: 'color-mix(in srgb, var(--etape-pastille) 45%, transparent)', background: 'color-mix(in srgb, var(--etape-pastille) 12%, transparent)' }}>
          <i aria-hidden="true" className="etape-pastille w-[9px] h-[9px] shrink-0 rounded-full" />{bandeau}
        </p>
      )}

      {/* S6 — Une seule action ; [CA6] aucune en lecture seule. [CA5] Photo : bientôt. */}
      <div className="flex flex-wrap gap-2 mt-3.5">
        {ecrire && (
          <button type="button" onClick={() => ouvrirGaston(contexteNoter(suivi))}
            className={`inline-flex items-center gap-1.5 min-h-[44px] rounded-[10px] bg-brand px-4 text-[13.5px] font-semibold text-white hover:opacity-95 ${FOCUS}`}>
            <Pencil size={15} aria-hidden="true" />{libelleNoter(suivi, { compact })}
          </button>
        )}
        <button type="button" disabled aria-disabled="true" aria-label="Photo, bientôt disponible"
          className="inline-flex items-center gap-1.5 min-h-[44px] rounded-[10px] border border-border px-3.5 text-[13px] text-txt3 cursor-not-allowed">
          <Camera size={15} aria-hidden="true" />Photo · bientôt disponible
        </button>
        {reduit && (
          <button type="button" onClick={() => setComplet(true)}
            className={`inline-flex items-center gap-1 min-h-[44px] rounded-[10px] border border-border px-3.5 text-[13px] font-semibold text-txt ${FOCUS}`}>
            Fiche<ChevronRight size={15} aria-hidden="true" />
          </button>
        )}
      </div>

      {reduit ? (
        lesNotes && (
          <section aria-label="Dernière note" className="mt-4">
            <h4 className={TITRE_BLOC}>Dernière note</h4>
            <Notes liste={lesNotes.slice(0, 1)} />
          </section>
        )
      ) : (
        <>
          {/* S7 — Récolté */}
          {recolte && (
            <p className="mt-2.5 rounded-[9px] px-3 py-2 text-[13px] font-semibold etape-recolte">{recolte}</p>
          )}
          {/* S8 — Étapes */}
          {etapes && (
            <section aria-label="Étapes">
              <h4 className={TITRE_BLOC}>Étapes</h4>
              <Frise etapes={etapes} />
            </section>
          )}
          {/* S9 — Origine */}
          {orig && (
            <section aria-label="Origine">
              <h4 className={TITRE_BLOC}>Origine</h4>
              <Origine o={orig} onLot={onLot} />
            </section>
          )}
          {/* S10 — Notes */}
          {lesNotes && (
            <section aria-label="Notes">
              <h4 className={TITRE_BLOC}>Notes</h4>
              <Notes liste={lesNotes} />
            </section>
          )}
        </>
      )}
    </article>
  )
}
