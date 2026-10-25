// Règle des temps : réglette de timeline qui pilote la date de référence
// (maquette « Curseur de date », projet Claude Design).
//
// Montée UNE fois dans la coquille de l'app (`App.jsx`), elle sert toutes les
// vues qui portent le sélecteur de date : le bouton « Parcourir » de
// `DateRefPicker` l'ouvre, elle écrit dans la même `dateRef` globale.
//
// Deux temps, volontairement : pendant qu'on fait glisser, seule la date
// affichée suit (aucun appel réseau) ; la date de référence n'est écrite qu'une
// fois la réglette posée sur un jour. Les écrans rechargent leurs données à
// chaque changement de `dateRef` — la leur écrire à chaque pixel les noierait.
import { Fragment, memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, RotateCcw, X } from 'lucide-react'
import { useDateRef } from '../context/AppContext.jsx'
import { jourLocal } from '../lib/gestes.js'
import {
  construireRegle, estToucheAujourdhui, graduations, indexDepuisDefilement, indexDuJour,
  jourDeIndex, libelleCourt, libelleLong, mentionDuJour, pasDuClavier, versDateRef,
} from '../lib/regleTemps.js'

/** Pixels par jour : un trait tous les 10 px, au pouce comme à la souris. */
const PPJ = 10
/** Silence de défilement après lequel la réglette se pose sur un jour. */
const DELAI_REPOS = 160
/** Appui de souris plus court que ça (en px) : un clic, pas un glissé. */
const SEUIL_GLISSE = 3

const mouvementReduit = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Les 700 traits ne changent jamais tant que la réglette garde la même étendue :
// `memo` évite de les réconcilier à chaque jour traversé.
const Graduations = memo(function Graduations({ regle }) {
  const traits = useMemo(() => graduations(regle), [regle])
  return (
    <div className="regle-rl">
      {traits.map(({ i, type, etiquette }) => (
        <Fragment key={i}>
          <i className={`regle-trait regle-trait-${type}`} style={{ left: i * PPJ }} />
          {etiquette && <span className="regle-mois" style={{ left: i * PPJ }}>{etiquette}</span>}
        </Fragment>
      ))}
      <span className="regle-auj" style={{ left: (regle.n - 1) * PPJ }} />
    </div>
  )
})

const BoutonPas = ({ sens, onClick, children }) => (
  <button
    type="button" onClick={onClick}
    aria-label={sens < 0 ? 'Jour précédent' : 'Jour suivant'}
    className="hidden @[30rem]/regle:flex items-center justify-center shrink-0 w-[34px] h-[34px] rounded-[10px] border border-border bg-surface text-txt2 hover:border-brand hover:text-brand-text transition-colors"
  >
    {children}
  </button>
)

function Dock() {
  const { dateRef, setDateRef, setRegleOuverte } = useDateRef()
  const [aujourdhui] = useState(() => jourLocal())
  const regle = useMemo(() => construireRegle(aujourdhui), [aujourdhui])
  const indexCible = indexDuJour(regle, dateRef)

  const [jour, setJour] = useState(indexCible)   // le jour affiché, en cours de défilement compris
  const [survol, setSurvol] = useState(null)     // infobulle de la souris : { x, texte }

  const vue = useRef(null)
  const repos = useRef(0)
  const appui = useRef(null)          // glissé à la souris : { x, gauche, bouge }
  const actif = useRef(false)         // la réglette bouge : la date de référence ne la déplace pas
  const doigt = useRef(false)         // dernier geste au doigt : autorise la vibration
  const indexCibleRef = useRef(indexCible)
  const dernierIndex = useRef(indexCible)
  indexCibleRef.current = indexCible

  const lundis = useMemo(() => new Set(graduations(regle).filter((g) => g.type === 'semaine').map((g) => g.i)), [regle])

  const courant = () => indexDepuisDefilement(regle, vue.current?.scrollLeft ?? 0, PPJ)

  const aller = (i, doux = false) => {
    const v = vue.current
    if (!v) return
    const gauche = Math.max(0, Math.min(regle.n - 1, i)) * PPJ
    if (doux && !mouvementReduit()) v.scrollTo({ left: gauche, behavior: 'smooth' })
    else v.scrollLeft = gauche
  }

  // Pose la réglette sur un jour entier, puis seulement écrit la date de référence.
  const poser = () => {
    const v = vue.current
    if (!v || appui.current) return
    const i = courant()
    if (Math.abs(v.scrollLeft - i * PPJ) > 0.5) {
      aller(i, true)
      return
    }
    actif.current = false
    if (i !== indexCibleRef.current) setDateRef(versDateRef(regle, i))
  }

  const surDefilement = () => {
    const v = vue.current
    if (!v || !v.clientWidth) return
    const i = courant()
    actif.current = true
    if (i !== dernierIndex.current) {
      dernierIndex.current = i
      // Un cran au passage d'un lundi — Android seulement, l'iPhone ignore l'API.
      if (doigt.current && lundis.has(i)) navigator.vibrate?.(5)
      setJour(i)
    }
    clearTimeout(repos.current)
    repos.current = setTimeout(poser, DELAI_REPOS)
  }

  const jourSousLeCurseur = (clientX) => {
    const v = vue.current
    const r = v.getBoundingClientRect()
    return indexDepuisDefilement(regle, clientX - r.left + v.scrollLeft - v.clientWidth / 2, PPJ)
  }

  const surAppui = (e) => {
    if (e.pointerType !== 'mouse') return
    const v = vue.current
    doigt.current = false
    appui.current = { x: e.clientX, gauche: v.scrollLeft, bouge: 0 }
    setSurvol(null)
    v.parentElement.classList.add('regle-glisse')
    v.setPointerCapture(e.pointerId)
    e.preventDefault()
  }

  const surMouvement = (e) => {
    if (e.pointerType !== 'mouse') return
    const a = appui.current
    if (a) {
      const dx = e.clientX - a.x
      a.bouge = Math.max(a.bouge, Math.abs(dx))
      vue.current.scrollLeft = a.gauche - dx
      return
    }
    const r = vue.current.getBoundingClientRect()
    setSurvol({ x: e.clientX - r.left, texte: libelleCourt(jourDeIndex(regle, jourSousLeCurseur(e.clientX))) })
  }

  const surRelache = (e) => {
    const a = appui.current
    if (!a) return
    appui.current = null
    vue.current.parentElement.classList.remove('regle-glisse')
    if (a.bouge < SEUIL_GLISSE) aller(jourSousLeCurseur(e.clientX), true)   // clic sur un jour : on y saute
    else poser()
  }

  const surTouche = (e) => {
    const pas = pasDuClavier(e.key, e.shiftKey)
    doigt.current = false
    if (pas !== null) aller(courant() + pas)
    else if (estToucheAujourdhui(e.key)) aller(regle.n - 1, true)
    else if (e.key === 'Escape') setRegleOuverte(false)
    else return
    e.preventDefault()
  }

  // Molette et pavé tactile : le défilement vertical de la souris fait glisser
  // la réglette. Écouteur natif, `onWheel` de React est passif et ne peut pas
  // empêcher le défilement de la page.
  useEffect(() => {
    const v = vue.current
    if (!v) return undefined
    const roue = (e) => {
      e.preventDefault()
      e.stopPropagation()
      doigt.current = false
      v.scrollLeft += Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY
    }
    v.addEventListener('wheel', roue, { passive: false })
    return () => v.removeEventListener('wheel', roue)
  }, [])

  // À l'ouverture : la réglette se cale sur la date de référence et prend le focus.
  useLayoutEffect(() => {
    aller(indexCible)
    // Le focus sert le clavier : au doigt, il ne ferait qu'allumer l'anneau de focus.
    if (!window.matchMedia?.('(pointer: coarse)').matches) vue.current?.focus({ preventScroll: true })
    return () => clearTimeout(repos.current)
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  // La date de référence a changé ailleurs (calendrier natif, remise à zéro du
  // sélecteur, autre vue) : la réglette suit — sauf si c'est elle qui bouge.
  useEffect(() => {
    const v = vue.current
    if (!v || actif.current) return
    if (Math.abs(v.scrollLeft - indexCible * PPJ) > PPJ / 2) v.scrollLeft = indexCible * PPJ
    dernierIndex.current = indexCible
    setJour(indexCible)
  }, [indexCible])

  const iso = jourDeIndex(regle, jour)
  const mention = mentionDuJour(iso, aujourdhui)
  const enDirect = jour >= regle.n - 1

  return (
    <section
      aria-label="Règle des temps"
      className="@container/regle shrink-0 bg-surface border-t border-border shadow-[0_-6px_20px_rgba(22,33,12,.07)]"
    >
      <div className="max-w-[1320px] mx-auto px-3 nav:px-6 pt-2 pb-2.5 flex flex-col gap-1.5">
        <div className="flex items-center gap-2 min-h-[40px]">
          <span className="font-hand text-[22px] font-bold leading-none text-txt whitespace-nowrap" aria-live="polite">
            <span className="@[30rem]/regle:hidden">{libelleCourt(iso)}</span>
            <span className="hidden @[30rem]/regle:inline">{libelleLong(iso)}</span>
          </span>
          {/* En étroit, la pastille ambre du sélecteur dit déjà qu'on lit le passé. */}
          {mention && (
            <span className="hidden @[30rem]/regle:inline text-[10px] font-bold uppercase tracking-[.05em] px-1.5 py-0.5 rounded-md bg-card-alt text-txt2">
              {mention}
            </span>
          )}
          <span className="flex-1" />
          <button
            type="button" onClick={() => aller(regle.n - 1, true)} tabIndex={enDirect ? -1 : 0}
            className={`inline-flex items-center gap-1.5 min-h-[40px] px-3 rounded-full bg-brand-soft text-brand-text font-bold text-[12.5px] whitespace-nowrap ${enDirect ? 'invisible' : ''}`}
          >
            <RotateCcw size={14} aria-hidden="true" />Aujourd'hui
          </button>
          <button
            type="button" onClick={() => setRegleOuverte(false)} aria-label="Fermer la réglette"
            className="inline-flex items-center justify-center w-10 h-10 rounded-[10px] bg-card-alt text-txt2 hover:text-txt transition-colors"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <BoutonPas sens={-1} onClick={() => aller(courant() - 1)}><ChevronLeft size={16} aria-hidden="true" /></BoutonPas>
          <div className="regle-w">
            <div
              ref={vue} className="regle-vue" tabIndex={0} role="slider"
              aria-label="Date de lecture" aria-valuemin={0} aria-valuemax={regle.n - 1}
              aria-valuenow={jour} aria-valuetext={libelleLong(iso)}
              onScroll={surDefilement}
              onPointerDown={surAppui} onPointerMove={surMouvement}
              onPointerUp={surRelache} onPointerCancel={surRelache}
              onPointerLeave={() => setSurvol(null)}
              onTouchStart={() => { doigt.current = true; appui.current = null; clearTimeout(repos.current) }}
              onTouchEnd={() => { clearTimeout(repos.current); repos.current = setTimeout(poser, DELAI_REPOS) }}
              onKeyDown={surTouche}
            >
              <div className="regle-in" style={{ width: regle.n * PPJ }}>
                <Graduations regle={regle} />
              </div>
            </div>
            <div className="regle-centre" aria-hidden="true" />
            {survol && (
              <div className="regle-tip" style={{ left: survol.x }} aria-hidden="true">{survol.texte}</div>
            )}
          </div>
          <BoutonPas sens={1} onClick={() => aller(courant() + 1)}><ChevronRight size={16} aria-hidden="true" /></BoutonPas>
        </div>

        <p className="hidden @[40rem]/regle:block text-[11px] text-txt3 px-[42px]">
          Glisser, molette ou clic sur un jour · <kbd className="regle-kbd">←</kbd> <kbd className="regle-kbd">→</kbd> un jour,
          {' '}<kbd className="regle-kbd">Maj</kbd> une semaine · <kbd className="regle-kbd">T</kbd> aujourd'hui
        </p>
      </div>
    </section>
  )
}

/** La règle des temps, ouverte depuis le sélecteur de date (bouton « Parcourir »). */
export default function RegleTemps() {
  const { regleOuverte } = useDateRef()
  return regleOuverte ? <Dock /> : null
}
