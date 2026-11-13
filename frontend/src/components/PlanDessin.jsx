// [US-327] Les pièces du plan vu du dessus : une parcelle dessinée à l'échelle, ses
// rangs et leurs segments (ou ses lots de pépinière), la rose des vents, l'échelle.
//
// Aucun calcul ici : position, taille, segments, libellés et noms accessibles viennent
// de `lib/planDessus.js` (CA2). Réutilisées par l'écran Plan, la page de contrôle et,
// demain, le plan mobile (US-329) et le détail d'une parcelle (US-330).
import {
  modeLibelle, tailleSegment, lotAvecNom, estEstompe, DIR_V,
  LIBELLE_VERTICAL, LIBELLE_COMPLET, LIBELLE_EMOJI_PICTO, LIBELLE_PICTO,
  MARGE_PARCELLE_PX, ECART_RANGS_PX, LONGUEUR_ECHELLE_M,
} from '../lib/planDessus.js'
import { classesSegment, VARIANTE_A_CONFIRMER, VARIANTE_PLEIN } from '../lib/etapes.js'
import { IconeEtape } from './ui/EtapeCulture.jsx'

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand'

/** [P2, P3, P4] Un segment : une culture sur sa part du rang, ou un morceau libre. */
function Segment({ forme, mesure, segment, filtre, choisi, onSegment, onRangLibre, onDeposer, accueillant, mini }) {
  const { largeur, hauteur } = tailleSegment(mesure.forme, segment, mesure.u)
  const mode = modeLibelle(largeur, hauteur, forme.dir)
  const estompe = estEstompe(filtre, segment) ? ' estompe' : ''
  const style = { flexGrow: segment.part, flexBasis: 0 }
  const vertical = forme.dir === DIR_V
  const base = `segment-plan relative min-w-0 min-h-0 rounded-[4px] overflow-hidden whitespace-nowrap
    text-[11.5px] font-semibold flex items-center gap-1 ${vertical ? 'flex-col justify-center py-1' : 'px-[5px]'} ${FOCUS}`

  // [US-329 / CA2] Le mini-plan : le même dessin, sans libellé ni cible (la parcelle entière en est une).
  if (mini) {
    const fond = segment.libre ? 'etape-libre' : (segment.etape ? classesSegment(segment.etape, segment.variante || VARIANTE_PLEIN) : 'bg-card border border-border')
    return <span aria-hidden="true" style={style} className={`min-w-0 min-h-0 rounded-[2px] ${fond}`} />
  }

  if (segment.libre) {
    // [US-328 / CA4] Un rang libre accueille une carte « À placer » : glissée, ou prise au clavier
    // puis Entrée ici. Rien n'est écrit : le dépôt ouvre Gaston avec la proposition.
    const surDeposer = (e) => { e.preventDefault(); onDeposer?.(forme, segment) }
    return (
      <button type="button" style={style}
        aria-label={accueillant ? `${segment.nomAccessible} — déposer ici la carte en main` : segment.nomAccessible}
        onClick={() => (accueillant ? onDeposer?.(forme, segment) : onRangLibre?.(forme, segment))}
        onDragOver={(e) => { if (onDeposer) { e.preventDefault(); try { e.dataTransfer.dropEffect = 'move' } catch { /* jsdom */ } } }}
        onDrop={surDeposer}
        className={`${base} etape-libre justify-center font-medium${estompe}${accueillant ? ' accueillant' : ''}`}>
        {mode === LIBELLE_COMPLET && (accueillant ? 'déposer ici' : 'libre')}
      </button>
    )
  }
  const classes = segment.etape ? classesSegment(segment.etape, segment.variante || VARIANTE_PLEIN) : 'bg-card text-txt border border-border'
  return (
    <button type="button" style={style} aria-label={segment.nomAccessible}
      aria-pressed={choisi ? 'true' : 'false'}
      onClick={() => onSegment?.(forme, segment)}
      className={`${base} ${classes}${estompe}${choisi ? ' choisi' : ''}`}>
      {mode === LIBELLE_VERTICAL && <>
        <span aria-hidden="true" className="text-[13px] leading-none">{segment.emoji}</span>
        <span aria-hidden="true" className="vertical">{segment.nom}</span>
        <IconeEtape etape={segment.etape} taille={13} />
      </>}
      {mode === LIBELLE_COMPLET && <>
        <span aria-hidden="true" className="text-[13px] leading-none">{segment.emoji}</span>
        <span aria-hidden="true" className="truncate min-w-0">{segment.nom}</span>
        <IconeEtape etape={segment.etape} taille={13} className="ml-auto" />
      </>}
      {mode === LIBELLE_EMOJI_PICTO && <>
        <span aria-hidden="true" className="text-[13px] leading-none">{segment.emoji}</span>
        <IconeEtape etape={segment.etape} taille={13} className="ml-auto" />
      </>}
      {mode === LIBELLE_PICTO && <IconeEtape etape={segment.etape} taille={13} className="mx-auto" />}
      {segment.variante === VARIANTE_A_CONFIRMER && (
        <span aria-hidden="true" className="etape-pastille absolute top-[2px] right-[2px] w-[9px] h-[9px] rounded-full" />
      )}
    </button>
  )
}

/** [P6] Les lots d'une pépinière, en vignettes ; toucher l'un ouvre sa fiche. */
function Lots({ forme, mesure, onLot }) {
  const avecNom = lotAvecNom(mesure.forme, mesure.u)
  return (
    <div className="absolute inset-[6px] grid grid-cols-3 gap-1 content-start">
      {forme.lots.map((lot) => (
        <button key={lot.cle} type="button" aria-label={lot.nomAccessible} onClick={() => onLot?.(lot)}
          className={`lot-plan min-w-0 h-7 rounded-[5px] flex items-center justify-center gap-1 px-1
                      text-[11px] font-bold whitespace-nowrap overflow-hidden ${FOCUS}`}>
          <span aria-hidden="true" className="text-[13px]">{lot.emoji}</span>
          {lot.numero != null && <span aria-hidden="true">#{lot.numero}</span>}
          {avecNom && <span aria-hidden="true" className="truncate font-semibold">· {lot.nom}</span>}
        </button>
      ))}
    </div>
  )
}

/**
 * [P1-P7] Une parcelle à sa place, à l'échelle `u` (pixels par mètre). Le nom est un
 * bouton posé sur la parcelle (P5) ; les rangs suivent le sens des rangs (P2).
 * `positionnee={false}` : la parcelle se met dans le flux (plan par zones, P10).
 */
export function ParcellePlan({
  forme, u, filtre, choix, parcelleChoisie, positionnee = true, largeurPx, hauteurPx,
  onSegment, onParcelle, onRangLibre, onLot, onDeposer, accueillant = false, mini = false,
}) {
  const w = largeurPx ?? forme.w * u
  const h = hauteurPx ?? forme.h * u
  const style = positionnee
    ? { position: 'absolute', left: forme.x * u, top: forme.y * u, width: w, height: h, transform: forme.rotation ? `rotate(${forme.rotation}deg)` : undefined }
    : { position: 'relative', width: w, height: h }
  // Un segment se mesure sur la taille DESSINÉE : en zones, la tuile n'est pas à
  // l'échelle, elle se mesure donc en pixels (u = 1).
  const mesure = positionnee ? { forme, u } : { forme: { ...forme, w, h }, u: 1 }
  const nature = forme.pepiniere ? ` · pépinière${forme.typePepiniere ? ` ${forme.typePepiniere}` : ''}` : ''
  const etat = forme.actif ? '' : ' · inactive'
  const classes = `parcelle-plan forme-${forme.forme}${forme.estimee ? ' estimee' : ''}${forme.actif ? '' : ' inactive'}${parcelleChoisie === forme.id ? ' choisie' : ''}`
  const vertical = forme.dir === DIR_V

  if (mini) {
    // [US-329 / M2] Toucher une parcelle du mini-plan fait défiler jusqu'à sa carte.
    return (
      <button type="button" onClick={() => onParcelle?.(forme)} style={style}
        aria-label={`${forme.nom}${nature}${etat} : aller à sa carte`}
        className={`${classes} mini ${FOCUS}`}>
        {forme.rangs.length > 0 && (
          <span aria-hidden="true" className={`absolute inset-[2px] flex ${vertical ? 'flex-row' : 'flex-col'}`} style={{ gap: 1 }}>
            {forme.rangs.map((rang) => (
              <span key={rang.numero} className={`flex flex-1 basis-0 min-w-0 min-h-0 ${vertical ? 'flex-col' : 'flex-row'}`} style={{ gap: 1 }}>
                {rang.segments.map((segment) => (
                  <Segment key={segment.cle} forme={forme} mesure={mesure} segment={segment} filtre={filtre} mini />
                ))}
              </span>
            ))}
          </span>
        )}
      </button>
    )
  }

  return (
    <section aria-label={`Parcelle ${forme.nom}${nature}${etat}`} className={classes} style={style}>
      <button type="button" onClick={() => onParcelle?.(forme)}
        aria-label={`Parcelle ${forme.nom}${nature}${etat} : ouvrir son détail`}
        className={`absolute left-2 -top-[11px] z-[3] max-w-[calc(100%-16px)] truncate rounded-full border border-border
                    bg-card px-[9px] py-px text-[11.5px] font-bold text-txt shadow-sm hover:border-brand ${FOCUS}
                    ${forme.pepiniere ? 'text-[color:var(--parcelle-pep-t)]' : ''}`}>
        {forme.nom}{nature}{etat} <span aria-hidden="true" className="text-txt3">→</span>
      </button>
      {forme.pepiniere && forme.actif && <Lots forme={forme} mesure={mesure} onLot={onLot} />}
      {forme.rangs.length > 0 && (
        <div className={`absolute flex ${vertical ? 'flex-row' : 'flex-col'}`}
          style={{ inset: forme.forme === 'butte' ? `${MARGE_PARCELLE_PX}px 14px` : MARGE_PARCELLE_PX, gap: ECART_RANGS_PX }}>
          {forme.rangs.map((rang) => (
            <div key={rang.numero} className={`flex flex-1 basis-0 min-w-0 min-h-0 ${vertical ? 'flex-col' : 'flex-row'}`}
              style={{ gap: ECART_RANGS_PX }}>
              {rang.segments.map((segment) => (
                <Segment key={segment.cle} forme={forme} mesure={mesure} segment={segment} filtre={filtre}
                  choisi={!segment.libre && choix?.parcelleId === forme.id && choix?.cle === segment.cle}
                  onSegment={onSegment} onRangLibre={onRangLibre} onDeposer={onDeposer} accueillant={accueillant} />
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

/** [P9] La rose des vents, tournée selon le nord du potager. */
export function RoseDesVents({ rose, petite = false }) {
  if (!rose) return null
  const t = petite ? 44 : 64
  const R = (x) => (x * Math.PI) / 180
  const P = (a, r) => `${(Math.sin(R(a)) * r).toFixed(2)} ${(-Math.cos(R(a)) * r).toFixed(2)}`
  const branche = (a, r, l, c1, c2) => (
    <g key={`${a}-${r}`}>
      <path d={`M0 0L${P(a - 90, l)}L${P(a, r)}Z`} fill={c1} />
      <path d={`M0 0L${P(a + 90, l)}L${P(a, r)}Z`} fill={c2} />
    </g>
  )
  return (
    <span role="img" aria-label={rose.nomAccessible}
      className="absolute right-3 bottom-3 z-[6] rounded-full bg-card/80 p-1 shadow-sm"
      style={{ width: t, height: t }}>
      <svg viewBox="-50 -50 100 100" width="100%" height="100%" aria-hidden="true"
        style={{ transform: `rotate(${rose.angle}deg)` }}>
        <circle r="33" fill="none" stroke="#C9B58F" strokeWidth="1" />
        {[45, 135, 225, 315].map((a) => branche(a, 25, 5, '#B8C9A4', '#7E9566'))}
        {[0, 90, 180, 270].map((a) => branche(a, 38, 7, a === 0 ? '#2F5416' : '#56634A', a === 0 ? '#5E9A2E' : '#9AA58F'))}
        <circle r="3" fill="#fff" stroke="#2F5416" strokeWidth="1.2" />
        <text x="0" y="-45" textAnchor="middle" dominantBaseline="central" fontSize="11" fontWeight="700" fill="#2F5416">N</text>
      </svg>
    </span>
  )
}

/** [P9] La barre d'échelle : cinq mètres à l'échelle du plan. */
export function EchellePlan({ u }) {
  return (
    <span aria-hidden="true"
      className="absolute left-3 bottom-2.5 z-[6] flex flex-col gap-0.5 rounded-md bg-card/85 px-1.5 py-[3px] text-[11px] font-bold text-txt">
      {LONGUEUR_ECHELLE_M} m
      <i className="block h-[5px] border-[1.5px] border-t-0 border-txt" style={{ width: LONGUEUR_ECHELLE_M * u }} />
    </span>
  )
}
