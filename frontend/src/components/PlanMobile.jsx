// [US-329] Le Plan sur mobile : un petit plan pour se repérer, puis le chemin.
//
// M1 barre, M2 mini-plan (le dessin d'US-327 réduit, sans libellés), M3 légende compacte,
// M4 « N à confirmer » / « N à libérer » (US-328), M5 les parcelles dans l'ordre du chemin, une
// ligne de 54 px par culture, M6 les pépinières et leurs lots. Pas de modification ici.
import { useEffect, useRef, useState } from 'react'
import { ChevronRight, Maximize2, Sprout } from 'lucide-react'
import { ParcellePlan } from './PlanDessin.jsx'
import PlanAgrandi from './PlanAgrandi.jsx'
import { LegendeEtapes, LegendeRepliable } from './ui'
import { IconeEtape } from './ui/EtapeCulture.jsx'
import { classesSegment, VARIANTE_PLEIN } from '../lib/etapes.js'
import { boutonsMobile } from '../lib/aujourdhui.js'
import {
  echelleMiniPlan, hauteurMaxMiniPlan, idCarteChemin, TEXTE_LEGENDE_MOBILE, TEXTE_LOTS_PEPINIERE,
} from '../lib/planMobile.js'

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'

/** M5 : une ligne de culture (≥ 54 px), ou un rang libre. */
export function LigneChemin({ ligne, onOuvrir }) {
  if (ligne.libre) {
    return (
      <li className="flex min-h-[54px] items-center gap-3 px-3 text-[13px] text-txt3" aria-label={ligne.nomAccessible}>
        <span className="w-8 shrink-0 text-[12px] font-bold">{ligne.rang}</span>
        <span aria-hidden="true" className="etape-libre h-[26px] w-[26px] shrink-0 rounded-[6px]" />
        <span>{ligne.nom}</span>
      </li>
    )
  }
  const barre = ligne.etape ? classesSegment(ligne.etape, ligne.variante || VARIANTE_PLEIN) : 'bg-card border border-border'
  return (
    <li>
      <button type="button" aria-label={ligne.nomAccessible} onClick={() => onOuvrir?.(ligne.selection)}
        className={`flex w-full min-h-[54px] items-center gap-3 px-3 py-1.5 text-left hover:bg-card-alt ${FOCUS}`}>
        <span className="w-8 shrink-0 text-[12px] font-bold text-txt2">{ligne.rang}</span>
        <span aria-hidden="true" className={`inline-flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-[6px] ${barre}`}>
          <IconeEtape etape={ligne.etape} taille={14} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14px] font-semibold text-txt">
            <span aria-hidden="true" className="mr-1">{ligne.emoji}</span>{ligne.nom}
          </span>
          {ligne.detail && <span className="block truncate text-[12px] text-txt2">{ligne.detail}</span>}
        </span>
        {ligne.aConfirmer && (
          <span aria-hidden="true"
            className="etape-pastille-texte shrink-0 rounded-full border border-dashed border-current px-2 py-0.5 text-[11px] font-bold">
            À confirmer
          </span>
        )}
      </button>
    </li>
  )
}

/** M5 / M6 : la carte d'une parcelle (ou d'une pépinière) dans le chemin. */
function CarteChemin({ parcelle, enEvidence, onOuvrir, onDetail, onLot, onPepiniere }) {
  return (
    <section id={idCarteChemin(parcelle.id)} tabIndex={-1} aria-label={`${parcelle.nom}, ${parcelle.sousTitre}`}
      className={`carte-chemin scroll-mt-3 overflow-hidden rounded-xl border border-border bg-card ${FOCUS}${enEvidence ? ' en-evidence' : ''}`}>
      <header className="flex items-center gap-2 border-b border-border px-3 py-2">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[14.5px] font-bold text-txt">{parcelle.nom}</h3>
          <p className="text-[12px] text-txt2">
            {parcelle.sousTitre}{!parcelle.placee && ' · pas encore sur le plan'}
          </p>
        </div>
        {parcelle.pepiniere ? (
          <button type="button" onClick={() => onPepiniere?.()}
            className={`min-h-[44px] shrink-0 rounded-lg px-2 text-[12.5px] font-semibold text-brand-text hover:underline ${FOCUS}`}>
            Ma pépinière
          </button>
        ) : (
          <button type="button" onClick={() => onDetail?.(parcelle)} aria-label={`Détail de ${parcelle.nom}`}
            className={`inline-flex min-h-[44px] shrink-0 items-center gap-0.5 rounded-lg border border-border px-2.5 text-[12.5px] font-semibold text-txt hover:border-brand ${FOCUS}`}>
            Détail <ChevronRight size={14} aria-hidden="true" />
          </button>
        )}
      </header>
      {parcelle.pepiniere ? (
        <>
          {parcelle.lots.length > 0 ? (
            <ul className="divide-y divide-border">
              {parcelle.lots.map((lot) => (
                <li key={lot.cle}>
                  <button type="button" aria-label={lot.nomAccessible} onClick={() => onLot?.(lot)}
                    className={`flex w-full min-h-[54px] items-center gap-3 px-3 py-1.5 text-left hover:bg-card-alt ${FOCUS}`}>
                    <span className="w-10 shrink-0 text-[12px] font-bold text-txt2">{lot.numero != null ? `#${lot.numero}` : '—'}</span>
                    <span aria-hidden="true" className="text-[18px] leading-none">{lot.emoji}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[14px] font-semibold text-txt">
                        {lot.nom}{lot.variete && <span className="font-normal text-txt2"> {lot.variete}</span>}
                      </span>
                      {lot.detail && <span className="block truncate text-[12px] text-txt2">{lot.detail}</span>}
                    </span>
                    <ChevronRight size={16} aria-hidden="true" className="shrink-0 text-txt3" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-3 text-[12.5px] text-txt3">Aucun lot en cours.</p>
          )}
          <p className="flex items-center gap-1.5 border-t border-border px-3 py-2 text-[12px] text-txt3">
            <Sprout size={13} aria-hidden="true" />{TEXTE_LOTS_PEPINIERE}
          </p>
        </>
      ) : parcelle.lignes.length > 0 ? (
        <ul className="divide-y divide-border">
          {parcelle.lignes.map((l) => <LigneChemin key={l.cle} ligne={l} onOuvrir={onOuvrir} />)}
        </ul>
      ) : (
        <p className="px-3 py-3 text-[12.5px] text-txt3">Rien en place.</p>
      )}
    </section>
  )
}

/**
 * L'écran mobile entier. `formes`/`emprise` : le dessin d'US-327 (mêmes calculs) ;
 * `chemin` : `parcellesDuChemin(plan)` ; `taches` : `tachesDuPlan(plan)`.
 */
export default function PlanMobile({
  entete, formes, emprise, angle = 0, chemin, taches, largeur,
  onOuvrir, onDetail, onLot, onPepiniere, annoncer,
}) {
  const [enEvidence, setEnEvidence] = useState(null)
  const [agrandi, setAgrandi] = useState(false)
  const minuterie = useRef(null)
  const hauteurEcran = typeof window !== 'undefined' ? window.innerHeight : 0
  const u = echelleMiniPlan(emprise, largeur, hauteurMaxMiniPlan(hauteurEcran))
  const boutons = boutonsMobile(taches)

  // [M2, CA5] Toucher une parcelle : défiler jusqu'à sa carte, la mettre en évidence, y porter
  // le focus et l'annoncer aux lecteurs d'écran.
  const allerA = (forme) => {
    const el = typeof document !== 'undefined' ? document.getElementById(idCarteChemin(forme.id)) : null
    if (!el) return
    const reduit = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    el.scrollIntoView?.({ behavior: reduit ? 'auto' : 'smooth', block: 'start' })
    el.focus?.({ preventScroll: true })
    setEnEvidence(forme.id)
    annoncer?.(`${forme.nom} : sa carte est affichée`)
    clearTimeout(minuterie.current)
    minuterie.current = setTimeout(() => setEnEvidence(null), 2500)
  }

  // Depuis le plan agrandi : fermer la fenêtre PUIS défiler. La fenêtre rend le focus au bouton
  // « Agrandir » en se fermant ; sans ce délai, il reprendrait le focus déjà posé sur la carte.
  const choisirDepuisAgrandi = (forme) => {
    setAgrandi(false)
    setTimeout(() => allerA(forme), 0)
  }

  useEffect(() => () => clearTimeout(minuterie.current), [])

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {/* M1 */}
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-serif text-[17px] font-semibold text-txt">{entete.titre}</h2>
          <p className="text-[12px] text-txt2">{[entete.fond, entete.dimension].filter(Boolean).join(' · ')}</p>
        </div>
        {/* Hors du dessin : un bouton posé sur le plan masquerait une parcelle. */}
        {u > 0 && formes.length > 0 && (
          <button type="button" onClick={() => setAgrandi(true)} aria-label="Agrandir le plan"
            className={`inline-flex min-h-[44px] shrink-0 items-center gap-1.5 rounded-full border border-border bg-card px-3.5 text-[13px] font-semibold text-txt ${FOCUS}`}>
            <Maximize2 size={15} aria-hidden="true" />Agrandir
          </button>
        )}
      </div>

      {/* M2 — CA4 : une parcelle non placée n'y figure pas. */}
      {u > 0 && formes.length > 0 && (
        <div className="relative mx-auto" style={{ width: emprise.longueur * u, maxWidth: '100%' }}>
          <div className="plan-cadre relative overflow-hidden rounded-xl"
            style={{ width: '100%', height: emprise.largeur * u }}>
            <div className="absolute inset-0" style={angle ? { transform: `rotate(${angle}deg)` } : undefined}>
              {formes.filter((f) => f.actif).map((forme) => (
                <ParcellePlan key={forme.id} forme={forme} u={u} mini parcelleChoisie={enEvidence}
                  onParcelle={allerA} />
              ))}
            </div>
          </div>
        </div>
      )}
      {agrandi && (
        <PlanAgrandi formes={formes} emprise={emprise} angle={angle}
          onChoisir={choisirDepuisAgrandi} onClose={() => setAgrandi(false)} />
      )}

      {/* M3 */}
      <div className="flex flex-col gap-1">
        <LegendeRepliable>
          <LegendeEtapes compact />
          <p className="text-[12px] text-txt3 mt-1">{TEXTE_LEGENDE_MOBILE}</p>
        </LegendeRepliable>
      </div>

      {/* M4 — US-328 / CA7 : chaque bouton ouvre la première culture de sa liste. */}
      {boutons.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {boutons.map((b) => (
            <button key={b.cle} type="button" onClick={() => onOuvrir?.(b.premiere.selection)}
              className={`min-h-[44px] rounded-full border-[1.5px] border-dashed border-current px-4 text-[13px] font-bold etape-pastille-texte bg-card ${FOCUS}`}>
              {b.texte}
            </button>
          ))}
        </div>
      )}

      {/* M5, M6 */}
      <h3 className="mt-1 text-[11.5px] font-bold uppercase tracking-[.05em] text-txt2">Dans l’ordre du chemin</h3>
      <div className="flex flex-col gap-3">
        {chemin.map((p) => (
          <CarteChemin key={p.id} parcelle={p} enEvidence={enEvidence === p.id}
            onOuvrir={onOuvrir} onDetail={onDetail} onLot={onLot} onPepiniere={onPepiniere} />
        ))}
      </div>
    </div>
  )
}
