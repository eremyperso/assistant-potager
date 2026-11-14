// [US-333] « Modifier le plan » — poser, dimensionner, orienter les parcelles, sur ordinateur.
//
// Trois colonnes : à gauche le fond (« Sans fond », US-335), les parcelles « À placer », les quatre formes
// nouvelles et la rose des vents ; au centre le plan, à grille aimantée ; à droite la parcelle choisie.
// Tout se calcule dans `lib/editeurPlan.js` (CA6) ; ici, on dessine l'état et on relaie les gestes.
// Rien n'est écrit avant « Enregistrer » (E5) — en un seul appel, ou rien (CA3). Une forme NOUVELLE
// n'existe qu'après « Confirmer » dans Gaston (E3, US-332).
import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Undo2, Redo2, Copy, Trash2, MoveHorizontal, MoveVertical, MapPin, Plus, GripVertical } from 'lucide-react'
import { api } from '../lib/api.js'
import { Btn } from './ui'
import AssistantMiseEnPlace from './AssistantMiseEnPlace.jsx'  // [US-334]
import { RoseDesVents, EchellePlan } from './PlanDessin.jsx'
import { ouvrirGastonPourPlan } from '../lib/contexteCompagnon.js'
import { ECHELLE_MIN, ECHELLE_MAX } from '../lib/planDessus.js'
import {
  etatInitial, synchroniser, poser, deplacer, decaler, redimensionner, tourner, definirSens, definirRangs,
  retirer, orienter, annuler, refaire, selectionner, alignerFiche, posees, aPlacer, parcelleDe, cotes,
  ecartSurface, erreurRangs, erreurs, modifie, chargeEnregistrement, resumeModifications, demandeDeCreation,
  demandeDeDuplication, directionDuNord, estAlignee, aimanter, aimanterRotation, texteMetres,
  DIRECTIONS, FORMES_NOUVELLES, PAS_AIMANT_M, TEXTE_ABANDON, empriseDe,
} from '../lib/editeurPlan.js'

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'
const MARGE_PLAN_M = 2
const TITRE_COLONNE = 'text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2 mb-2'

function Champ({ id, label, children, aide, erreur }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[12px] font-semibold text-txt2">{label}</label>
      {children}
      {erreur ? <span role="alert" className="text-[12px] text-red">{erreur}</span>
        : aide ? <span className="text-[11.5px] text-txt3">{aide}</span> : null}
    </div>
  )
}

const CLASSE_SAISIE = `min-h-[36px] w-full rounded-lg border border-border bg-card px-2.5 text-[13px] text-txt ${FOCUS}`

/** Une parcelle sur le plan : poignées de redimensionnement (angle bas-droit) et de rotation (au-dessus). */
function ParcelleEditable({ p, u, choisie, onChoisir, onGeste, onTouche }) {
  const w = p.w * u
  const h = p.h * u
  const vertical = p.sens === 'travers'
  const rangs = Math.max(1, Math.min(p.nbRangs || 0, 12)) || 0
  return (
    <div role="button" tabIndex={0} data-parcelle={p.id}
      aria-label={`${p.nom}, ${texteMetres(p.w)} sur ${texteMetres(p.h)} mètres${choisie ? ', sélectionnée' : ''}. Flèches : déplacer de 50 centimètres.`}
      aria-pressed={choisie}
      onPointerDown={(e) => { if (e.target.dataset.poignee) return; onChoisir(p.id); onGeste(e, p, 'deplacer') }}
      onKeyDown={(e) => onTouche(e, p)}
      className={`parcelle-plan forme-${p.forme}${p.estimee ? ' estimee' : ''}${choisie ? ' choisie' : ''} ${FOCUS} cursor-move touch-none select-none`}
      style={{
        position: 'absolute', left: p.x * u, top: p.y * u, width: w, height: h,
        transform: p.rotation ? `rotate(${p.rotation}deg)` : undefined,
      }}>
      {rangs > 0 && (
        <span aria-hidden="true" className={`absolute inset-[3px] flex ${vertical ? 'flex-row' : 'flex-col'} gap-[2px]`}>
          {Array.from({ length: rangs }, (_, i) => (
            <i key={i} className="flex-1 rounded-[3px] bg-[color:var(--parcelle-sol-bd)] opacity-30" />
          ))}
        </span>
      )}
      <span className="absolute left-1.5 top-1 max-w-[calc(100%-12px)] truncate text-[11.5px] font-bold text-txt pointer-events-none">{p.nom}</span>
      {choisie && (
        <>
          <span data-poignee="tourner" role="presentation" title="Tourner"
            onPointerDown={(e) => onGeste(e, p, 'tourner')}
            className="absolute left-1/2 -top-[26px] h-[14px] w-[14px] -translate-x-1/2 cursor-grab rounded-full border-2 border-brand bg-card" />
          <span aria-hidden="true" className="absolute left-1/2 -top-[12px] h-[12px] w-px bg-brand" />
          <span data-poignee="redimensionner" role="presentation" title="Redimensionner"
            onPointerDown={(e) => onGeste(e, p, 'redimensionner')}
            className="absolute -right-[7px] -bottom-[7px] h-[14px] w-[14px] cursor-nwse-resize rounded-[3px] border-2 border-brand bg-card" />
        </>
      )}
    </div>
  )
}

export default function EditeurPlan({
  plan, emprise: empriseEcran, selectionInitiale = null, guide = false, onQuitter, onEnregistre, onCaracteristiques, annoncer = () => {},
}) {
  const [etat, setEtat] = useState(() => etatInitial(plan, selectionInitiale))
  const [geste, setGeste] = useState(null)         // l'aperçu d'un glisser en cours : { id, x, y, w, h, rotation }
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [abandon, setAbandon] = useState(false)
  // [US-334 / M4] La première ouverture déroule l'assistant ; il se ferme, il ne revient pas dans la même séance.
  const [assistant, setAssistant] = useState(guide)
  const cadre = useRef(null)
  const toile = useRef(null)
  // La barre d'actions se déplace : sa position (px dans le cadre) est gardée tant que l'éditeur est ouvert.
  const barre = useRef(null)
  const [posBarre, setPosBarre] = useState(null)    // null = centrée en haut
  const deplacerBarre = (e) => {
    if (!barre.current || !cadre.current) return
    e.preventDefault()
    const rb = barre.current.getBoundingClientRect()
    const rc = cadre.current.getBoundingClientRect()
    const dx = e.clientX - rb.left, dy = e.clientY - rb.top
    const suivre = (ev) => {
      const x = Math.min(Math.max(0, ev.clientX - rc.left - dx), Math.max(0, rc.width - rb.width))
      const y = Math.min(Math.max(0, ev.clientY - rc.top - dy), Math.max(0, rc.height - rb.height))
      setPosBarre({ x, y })
    }
    const fin = () => { window.removeEventListener('pointermove', suivre); window.removeEventListener('pointerup', fin) }
    window.addEventListener('pointermove', suivre)
    window.addEventListener('pointerup', fin)
  }
  const [largeurCadre, setLargeurCadre] = useState(0)

  // Une parcelle confirmée par Gaston (ou supprimée) pendant l'édition rejoint l'éditeur.
  useEffect(() => { setEtat((e) => synchroniser(e, plan)) }, [plan])
  useEffect(() => {
    const el = cadre.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const obs = new ResizeObserver(([e]) => setLargeurCadre(Math.floor(e.contentRect.width)))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const choisie = parcelleDe(etat, etat.selection)
  const sur = posees(etat)
  const libres = aPlacer(etat)
  const nord = directionDuNord(etat)
  const emprise = empriseDe(etat, empriseEcran)   // [US-334] l'emprise posée ici l'emporte sur celle de l'écran
  const changements = modifie(etat)
  const refus = erreurs(etat)

  // Le plan montre au moins l'emprise posée, et laisse 2 m au-delà de la dernière parcelle.
  const dims = useMemo(() => {
    const maxX = Math.max(0, ...sur.map((p) => p.x + p.w))
    const maxY = Math.max(0, ...sur.map((p) => p.y + p.h))
    return {
      longueur: Math.max(emprise?.longueur || 0, Math.ceil(maxX) + MARGE_PLAN_M, 10),
      largeur: Math.max(emprise?.largeur || 0, Math.ceil(maxY) + MARGE_PLAN_M, 6),
    }
  }, [emprise, sur])
  const u = Math.max(ECHELLE_MIN, Math.min(ECHELLE_MAX, Math.floor((largeurCadre || 600) / dims.longueur)))

  const appliquer = useCallback((f) => setEtat((e) => f(e)), [])

  // ── Glisser, redimensionner, tourner (pointeur) ────────────────────────────
  const demarrerGeste = (e, p, mode) => {
    if (e.button != null && e.button !== 0) return
    e.stopPropagation()
    e.preventDefault()
    const rect = toile.current.getBoundingClientRect()
    const depart = { px: e.clientX, py: e.clientY, x: p.x, y: p.y, w: p.w, h: p.h, rect }
    const centre = { x: rect.left + (p.x + p.w / 2) * u, y: rect.top + (p.y + p.h / 2) * u }
    const lire = (ev) => {
      const dx = (ev.clientX - depart.px) / u
      const dy = (ev.clientY - depart.py) / u
      if (mode === 'deplacer') return { id: p.id, x: aimanter(depart.x + dx), y: aimanter(depart.y + dy), w: p.w, h: p.h, rotation: p.rotation }
      if (mode === 'redimensionner') {
        return { id: p.id, x: p.x, y: p.y, w: Math.max(0.5, aimanter(depart.w + dx)), h: Math.max(0.5, aimanter(depart.h + dy)), rotation: p.rotation }
      }
      const deg = (Math.atan2(ev.clientX - centre.x, centre.y - ev.clientY) * 180) / Math.PI
      return { id: p.id, x: p.x, y: p.y, w: p.w, h: p.h, rotation: aimanterRotation(deg) }
    }
    const bouger = (ev) => setGeste({ ...lire(ev), mode })
    const finir = (ev) => {
      window.removeEventListener('pointermove', bouger)
      window.removeEventListener('pointerup', finir)
      window.removeEventListener('pointercancel', finir)
      const f = lire(ev)
      setGeste(null)
      if (mode === 'deplacer') appliquer((s) => deplacer(s, p.id, Math.max(0, f.x), Math.max(0, f.y)))
      else if (mode === 'redimensionner') appliquer((s) => redimensionner(s, p.id, { w: f.w, h: f.h }))
      else appliquer((s) => tourner(s, p.id, f.rotation))
    }
    window.addEventListener('pointermove', bouger)
    window.addEventListener('pointerup', finir)
    window.addEventListener('pointercancel', finir)
    setGeste({ ...lire(e), mode })
  }

  const surTouche = (e, p) => {
    const pas = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key]
    if (pas) { e.preventDefault(); appliquer((s) => decaler(selectionner(s, p.id), p.id, ...pas)); return }
    if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); retirerDuPlan(p) }
  }

  const retirerDuPlan = (p) => { appliquer((s) => retirer(s, p.id)); annoncer(`${p.nom} retirée du plan : elle revient dans « À placer ».`) }

  // Ctrl+Z / Ctrl+Y : annuler et rétablir la dernière action.
  useEffect(() => {
    const surClavier = (e) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const cible = e.target
      if (cible?.tagName === 'INPUT' || cible?.tagName === 'TEXTAREA') return
      const k = e.key.toLowerCase()
      if (k === 'z' && !e.shiftKey) { e.preventDefault(); appliquer(annuler) }
      else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); appliquer(refaire) }
    }
    window.addEventListener('keydown', surClavier)
    return () => window.removeEventListener('keydown', surClavier)
  }, [appliquer])
  // Quitter l'onglet avec des modifications non enregistrées : le navigateur demande confirmation.
  useEffect(() => {
    if (!changements) return undefined
    const avant = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', avant)
    return () => window.removeEventListener('beforeunload', avant)
  }, [changements])

  // ── Déposer sur le plan ────────────────────────────────────────────────────
  const positionSurLePlan = (e) => {
    const rect = toile.current.getBoundingClientRect()
    return { x: (e.clientX - rect.left) / u, y: (e.clientY - rect.top) / u }
  }
  const surDepot = (e) => {
    e.preventDefault()
    const brut = e.dataTransfer.getData('text/plain')
    const { x, y } = positionSurLePlan(e)
    deposer(brut, x, y)
  }
  const deposer = (brut, x, y) => {
    if (brut.startsWith('parcelle:')) {
      const id = Number(brut.slice(9))
      appliquer((s) => poser(s, id, x, y))
      annoncer('Parcelle posée sur le plan, alignée et aimantée à 50 cm.')
    } else if (brut.startsWith('forme:')) {
      demanderCreation(brut.slice(6), x, y)
    }
  }
  const demanderCreation = (forme, x, y, options) => {
    const d = demandeDeCreation(forme, x, y, etat, options)
    ouvrirGastonPourPlan({ phrase: d.phrase, plan: d.plan })
  }
  /** Au clavier : une parcelle « À placer » ou une forme nouvelle se pose au milieu du plan visible. */
  const poserAuCentre = (id) => {
    const p = parcelleDe(etat, id)
    appliquer((s) => poser(s, id, Math.max(0, dims.longueur / 2 - (p?.w || 2) / 2), Math.max(0, dims.largeur / 2 - (p?.h || 1) / 2)))
  }

  // ── Enregistrer, abandonner ────────────────────────────────────────────────
  const enregistrer = async () => {
    const charge = chargeEnregistrement(etat)
    if (!charge || refus.length) return
    setEnCours(true)
    setErreur('')
    try {
      await api.enregistrerPlan(charge)
      annoncer('Plan enregistré.')
      onEnregistre?.()
    } catch (e) {
      // Un échec n'écrit rien : on le dit, et tout reste en place.
      setErreur(e.message || 'Le plan n’a pas pu être enregistré. Rien n’a été modifié.')
    } finally {
      setEnCours(false)
    }
  }
  const quitter = () => { if (changements) setAbandon(true); else onQuitter?.() }
  useEffect(() => {
    const surEchap = (e) => { if (e.key === 'Escape' && !geste) { if (modifie(etat)) setAbandon(true); else onQuitter?.() } }
    window.addEventListener('keydown', surEchap)
    return () => window.removeEventListener('keydown', surEchap)
  }, [etat, geste, onQuitter])

  const apercu = (p) => (geste?.id === p.id ? { ...p, x: geste.x, y: geste.y, w: geste.w, h: geste.h, rotation: geste.rotation } : p)
  const ecart = choisie ? ecartSurface(choisie) : null
  const erreurDesRangs = choisie ? erreurRangs(choisie) : null
  const peutDupliquer = choisie?.placee && demandeDeDuplication(etat, choisie.id)

  return (
    <div className="@container flex flex-col gap-3" data-editeur-plan>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-serif text-[18px] font-semibold text-txt">Modifier le plan</h2>
          <p className="text-[12.5px] text-txt2 mt-0.5">
            Sans fond · grille aimantée tous les {texteMetres(PAS_AIMANT_M * 100)} cm · {resumeModifications(etat)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" aria-label="Annuler la dernière action" disabled={!etat.passe.length}
            onClick={() => appliquer(annuler)}
            className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-txt disabled:opacity-40 ${FOCUS}`}>
            <Undo2 size={16} aria-hidden="true" />
          </button>
          <button type="button" aria-label="Rétablir" disabled={!etat.futur.length} onClick={() => appliquer(refaire)}
            className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-txt disabled:opacity-40 ${FOCUS}`}>
            <Redo2 size={16} aria-hidden="true" />
          </button>
          <Btn small onClick={quitter}>Annuler</Btn>
          <Btn small kind="primary" disabled={!changements || enCours || refus.length > 0} onClick={enregistrer}>
            {enCours ? 'Enregistrement…' : 'Enregistrer'}
          </Btn>
        </div>
      </header>

      {abandon && (
        <div role="alertdialog" aria-label="Abandonner les modifications" className="flex flex-wrap items-center gap-3 rounded-[10px] border border-border bg-card-alt px-3 py-2 text-[13px] text-txt">
          <span>{TEXTE_ABANDON}</span>
          <Btn small onClick={() => setAbandon(false)}>Continuer à modifier</Btn>
          <Btn small kind="primary" onClick={() => onQuitter?.()}>Abandonner</Btn>
        </div>
      )}
      {erreur && <p role="alert" className="rounded-[10px] bg-red-soft px-3 py-2 text-[12.5px] text-red">{erreur}</p>}
      {assistant && (
        <AssistantMiseEnPlace etat={etat} appliquer={appliquer} plan={plan} emprise={emprise} annoncer={annoncer}
          onTerminer={() => setAssistant(false)} />
      )}

      <div className="grid gap-4 @[760px]:grid-cols-[190px_minmax(0,1fr)_230px] @[760px]:items-start">
        {/* Colonne de gauche : fond, À placer, formes nouvelles, orientation */}
        <div className="flex flex-col gap-4 @[760px]:order-1 order-2">
          <section aria-label="Fond du plan">
            <h3 className={TITRE_COLONNE}>Fond du plan</h3>
            <p className="rounded-lg border border-dashed border-border px-2.5 py-2 text-[12.5px] text-txt2">Sans fond</p>
          </section>
          <section aria-label="Parcelles à placer">
            <h3 className={TITRE_COLONNE}>À placer · {libres.length}</h3>
            {libres.length === 0 ? <p className="text-[12.5px] text-txt3">Toutes les parcelles sont posées.</p> : (
              <ul className="flex flex-col gap-1.5">
                {libres.map((p) => (
                  <li key={p.id} draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', `parcelle:${p.id}`)}
                    className="flex items-center gap-1.5 rounded-lg border border-dashed border-border bg-card px-2 py-1.5 text-[12.5px] text-txt">
                    <MapPin size={13} aria-hidden="true" className="text-txt3 shrink-0" />
                    <span className="min-w-0 flex-1 truncate">{p.nom}</span>
                    <button type="button" onClick={() => poserAuCentre(p.id)} aria-label={`Poser ${p.nom} sur le plan`}
                      className={`rounded-md px-1.5 py-0.5 text-[11.5px] font-semibold text-brand-text hover:underline ${FOCUS}`}>Poser</button>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-label="Nouvelle parcelle">
            <h3 className={TITRE_COLONNE}>Nouvelle parcelle</h3>
            <ul className="grid grid-cols-2 gap-1.5">
              {FORMES_NOUVELLES.map((f) => (
                <li key={f.id}>
                  <button type="button" draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', `forme:${f.id}`)}
                    onClick={() => demanderCreation(f.id, Math.max(0, dims.longueur / 2 - f.longueur / 2), Math.max(0, dims.largeur / 2 - f.largeur / 2))}
                    aria-label={`Nouvelle ${f.libelle.toLowerCase()} : Gaston propose de la créer`}
                    className={`flex min-h-[40px] w-full items-center justify-center gap-1 rounded-lg border border-border bg-card px-2 text-[12.5px] font-semibold text-txt hover:border-brand ${FOCUS}`}>
                    <Plus size={13} aria-hidden="true" />{f.libelle}
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-1.5 text-[11.5px] text-txt3">Glissez une forme sur le plan : Gaston la propose, rien n’existe avant « Confirmer ».</p>
          </section>
          <section aria-label="Orientation">
            <h3 className={TITRE_COLONNE}>Orientation</h3>
            <div role="group" aria-label="Direction du nord" className="grid grid-cols-4 gap-1">
              {DIRECTIONS.map((d) => (
                <button key={d.id} type="button" aria-pressed={etat.potager.nord === d.id} title={`Nord ${d.nord}`}
                  onClick={() => appliquer((s) => orienter(s, d.id))}
                  className={`min-h-[34px] rounded-md border text-[12px] font-semibold ${FOCUS}
                    ${etat.potager.nord === d.id ? 'border-brand bg-brand-soft text-brand-text' : 'border-border bg-card text-txt2 hover:text-txt'}`}>
                  {d.id.toUpperCase()}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[12px] text-txt2">{nord ? `Nord ${nord.nord}` : 'Nord non posé'}</p>
          </section>
        </div>

        {/* Centre : le plan */}
        <div className="min-w-0 @[760px]:order-2 order-1">
          <div ref={cadre} className="relative min-w-0">
            {choisie?.placee && (
              <div role="toolbar" aria-label="Actions sur la parcelle" ref={barre}
                className={`absolute z-20 flex items-center gap-1 rounded-full border border-border bg-card px-2 py-1 shadow-md ${posBarre ? '' : 'left-1/2 top-2 -translate-x-1/2'}`}
                style={posBarre ? { left: posBarre.x, top: posBarre.y } : undefined}>
                <span role="button" tabIndex={0} aria-label="Déplacer la barre d’actions (double-clic pour la recentrer)" title="Déplacer la barre"
                  onPointerDown={deplacerBarre} onDoubleClick={() => setPosBarre(null)}
                  onKeyDown={(e) => { if (e.key === 'Enter') setPosBarre(null) }}
                  className={`inline-flex min-h-[32px] cursor-grab touch-none items-center rounded-full px-0.5 text-txt3 active:cursor-grabbing ${FOCUS}`}>
                  <GripVertical size={16} aria-hidden="true" />
                </span>
                <button type="button" aria-pressed={choisie.sens === 'longueur'} onClick={() => appliquer((s) => definirSens(s, choisie.id, 'longueur'))}
                  className={`inline-flex min-h-[32px] items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[12px] font-semibold ${FOCUS} ${choisie.sens === 'longueur' ? 'bg-brand-soft text-brand-text' : 'text-txt2'}`}>
                  <MoveHorizontal size={14} aria-hidden="true" />Rangs ↔
                </button>
                <button type="button" aria-pressed={choisie.sens === 'travers'} onClick={() => appliquer((s) => definirSens(s, choisie.id, 'travers'))}
                  className={`inline-flex min-h-[32px] items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[12px] font-semibold ${FOCUS} ${choisie.sens === 'travers' ? 'bg-brand-soft text-brand-text' : 'text-txt2'}`}>
                  <MoveVertical size={14} aria-hidden="true" />Rangs ↕
                </button>
                <button type="button" disabled={!peutDupliquer} aria-label="Dupliquer : Gaston propose une nouvelle parcelle de mêmes dimensions"
                  onClick={() => { const d = demandeDeDuplication(etat, choisie.id); if (d) ouvrirGastonPourPlan({ phrase: d.phrase, plan: d.plan }) }}
                  className={`inline-flex min-h-[32px] items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[12px] font-semibold text-txt2 hover:text-txt disabled:opacity-40 ${FOCUS}`}>
                  <Copy size={14} aria-hidden="true" />Dupliquer
                </button>
                <button type="button" onClick={() => retirerDuPlan(choisie)}
                  className={`inline-flex min-h-[32px] items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[12px] font-semibold text-red ${FOCUS}`}>
                  <Trash2 size={14} aria-hidden="true" />Retirer du plan
                </button>
              </div>
            )}
            <div className="overflow-auto rounded-xl">
              <div ref={toile} className="plan-cadre plan-grille relative rounded-xl"
                onClick={(e) => { if (e.target === e.currentTarget) appliquer((s) => selectionner(s, null)) }}
                onDragOver={(e) => e.preventDefault()} onDrop={surDepot}
                style={{ width: dims.longueur * u, height: dims.largeur * u, backgroundSize: `${u * PAS_AIMANT_M * 2}px ${u * PAS_AIMANT_M * 2}px` }}>
                {sur.map((p) => {
                  const a = apercu(p)
                  return (
                    <ParcelleEditable key={p.id} p={a} u={u} choisie={etat.selection === p.id}
                      onChoisir={(id) => appliquer((s) => selectionner(s, id))} onGeste={demarrerGeste} onTouche={surTouche} />
                  )
                })}
                {choisie?.placee && (() => {
                  const a = apercu(choisie)
                  const c = cotes(a, etat)
                  return (
                    <>
                      <span aria-hidden="true" className="pointer-events-none absolute z-10 rounded bg-txt px-1.5 py-px text-[11px] font-bold text-card"
                        style={{ left: a.x * u + (a.w * u) / 2, top: a.y * u + a.h * u + 6, transform: 'translateX(-50%)' }}>{c.longueur}</span>
                      <span aria-hidden="true" className="pointer-events-none absolute z-10 rounded bg-txt px-1.5 py-px text-[11px] font-bold text-card"
                        style={{ left: a.x * u + a.w * u + 10, top: a.y * u + (a.h * u) / 2, transform: 'translateY(-50%)' }}>{c.largeur}</span>
                      <span aria-hidden="true" className="pointer-events-none absolute z-10 whitespace-nowrap rounded bg-brand-soft px-1.5 py-px text-[11px] font-bold text-brand-text"
                        style={{ left: a.x * u, top: Math.max(0, a.y * u - 46) }}>{c.angle}</span>
                    </>
                  )
                })()}
                <RoseDesVents rose={nord ? { angle: nord.angle, nomAccessible: `Rose des vents : nord ${nord.nord}` } : null} />
                <EchellePlan u={u} />
              </div>
            </div>
            <p className="sr-only" aria-live="polite">{geste ? `Parcelle à ${texteMetres(geste.x)} ; ${texteMetres(geste.y)} mètres` : ''}</p>
          </div>
        </div>

        {/* Colonne de droite : la parcelle choisie */}
        <aside aria-label="Parcelle sélectionnée" className="flex flex-col gap-3 @[760px]:order-3 order-3">
          {!choisie ? (
            <p className="rounded-lg border border-dashed border-border px-3 py-3 text-[12.5px] text-txt2">
              Choisissez une parcelle sur le plan : sa forme, ses dimensions et ses rangs se règlent ici, au clavier comme à la souris.
            </p>
          ) : (
            <>
              <div>
                <h3 className="font-serif text-[16px] font-semibold text-txt">{choisie.nom}</h3>
                <p className="text-[12.5px] text-txt2">{choisie.forme.charAt(0).toUpperCase() + choisie.forme.slice(1)}{choisie.placee ? '' : ' · pas encore posée'}</p>
              </div>
              {!choisie.placee ? (
                <Btn small kind="primary" onClick={() => poserAuCentre(choisie.id)}>Poser sur le plan</Btn>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <Champ id="ep-longueur" label="Longueur (m)">
                      <input id="ep-longueur" type="number" min="0.5" step="0.5" className={CLASSE_SAISIE} value={choisie.w}
                        onChange={(e) => { const v = parseFloat(e.target.value); if (v > 0) appliquer((s) => redimensionner(s, choisie.id, { w: v })) }} />
                    </Champ>
                    <Champ id="ep-largeur" label="Largeur (m)">
                      <input id="ep-largeur" type="number" min="0.5" step="0.5" className={CLASSE_SAISIE} value={choisie.h}
                        onChange={(e) => { const v = parseFloat(e.target.value); if (v > 0) appliquer((s) => redimensionner(s, choisie.id, { h: v })) }} />
                    </Champ>
                    <Champ id="ep-x" label="Position x (m)">
                      <input id="ep-x" type="number" min="0" step="0.5" className={CLASSE_SAISIE} value={choisie.x}
                        onChange={(e) => { const v = parseFloat(e.target.value); if (v >= 0) appliquer((s) => deplacer(s, choisie.id, v, choisie.y)) }} />
                    </Champ>
                    <Champ id="ep-y" label="Position y (m)">
                      <input id="ep-y" type="number" min="0" step="0.5" className={CLASSE_SAISIE} value={choisie.y}
                        onChange={(e) => { const v = parseFloat(e.target.value); if (v >= 0) appliquer((s) => deplacer(s, choisie.id, choisie.x, v)) }} />
                    </Champ>
                  </div>
                  {ecart && (
                    <div role="status" className="rounded-lg border border-border bg-card-alt px-2.5 py-2 text-[12.5px] text-txt">
                      <p>{ecart.texte}</p>
                      <button type="button" onClick={() => appliquer((s) => alignerFiche(s, choisie.id))}
                        className={`mt-1 text-[12.5px] font-semibold text-brand-text hover:underline ${FOCUS}`}>{ecart.action}</button>
                    </div>
                  )}
                  <Champ id="ep-rangs" label="Nombre de rangs" erreur={erreurDesRangs}
                    aide={choisie.rangsOccupes ? `${choisie.rangsOccupes} occupé${choisie.rangsOccupes > 1 ? 's' : ''}` : undefined}>
                    <input id="ep-rangs" type="number" min="1" step="1" className={CLASSE_SAISIE} value={choisie.nbRangs ?? ''}
                      aria-invalid={Boolean(erreurDesRangs)} onChange={(e) => appliquer((s) => definirRangs(s, choisie.id, e.target.value))} />
                  </Champ>
                  <Champ id="ep-angle" label="Angle" aide={estAlignee(choisie) ? 'Celui du potager' : undefined}>
                    <div className="flex items-center gap-2">
                      <input id="ep-angle" type="number" step="5" className={CLASSE_SAISIE} value={estAlignee(choisie) ? etat.potager.angle : choisie.rotation}
                        disabled={estAlignee(choisie)}
                        onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) appliquer((s) => tourner(s, choisie.id, v)) }} />
                    </div>
                    <label className="mt-1 flex items-center gap-1.5 text-[12px] text-txt2">
                      <input type="checkbox" checked={!estAlignee(choisie)}
                        onChange={(e) => appliquer((s) => tourner(s, choisie.id, e.target.checked ? 15 : 0))} />
                      Parcelle de travers
                    </label>
                  </Champ>
                </>
              )}
              {onCaracteristiques && (
                <button type="button" onClick={() => onCaracteristiques(choisie.id)}
                  className={`self-start text-[12.5px] font-semibold text-brand-text hover:underline ${FOCUS}`}>Caractéristiques →</button>
              )}
            </>
          )}
        </aside>
      </div>
    </div>
  )
}

