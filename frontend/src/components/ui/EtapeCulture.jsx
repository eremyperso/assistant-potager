import {
  etape as lireEtape, classesSegment, libelleAccessible, entreesLegende,
  VARIANTE_PLEIN, VARIANTE_PREVU, VARIANTE_A_CONFIRMER, VARIANTE_A_LIBERER, VARIANTE_LIBRE,
  PICTO_GRAINE, PICTO_LEVEE, PICTO_PLANT, PICTO_TIGE, PICTO_FLEUR, PICTO_PANIER, PICTO_COCHE,
  ETAPE_TERMINEE,
} from '../../lib/etapes.js'

/**
 * Pictogramme d'une étape [US-321 / CA3] : un SVG monochrome teinté par
 * `currentColor`, jamais un emoji. Le pictogramme et le libellé font foi, la
 * couleur aide (V2). L'emoji de culture reste un repère à côté, pas un état.
 */
export function PictoEtape({ picto, taille = 14, className = '' }) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" data-picto-etape={picto} className={`shrink-0 ${className}`}>
      {picto === PICTO_GRAINE && <>
        <path d="M3 20.5h18" />
        <ellipse cx="12" cy="13" rx="3.4" ry="5.4" transform="rotate(-25 12 13)" />
      </>}
      {picto === PICTO_LEVEE && <>
        <path d="M3 20.5h18M12 20.5v-7" />
        <path d="M12 13.5c0-3-2-5-5-5 0 3 2 5 5 5zM12 13.5c0-3 2-5 5-5 0 3-2 5-5 5z" />
      </>}
      {picto === PICTO_PLANT && <>
        <path d="M7 14.5h10l-1.2 6h-7.6zM12 14.5V9" />
        <path d="M12 9c0-3 1.8-4.8 4.8-4.8 0 3-1.8 4.8-4.8 4.8zM12 11.5c0-2.4-1.6-4-4-4 0 2.4 1.6 4 4 4z" />
      </>}
      {picto === PICTO_TIGE && <>
        <path d="M3 20.5h18M12 20.5V4" />
        <path d="M12 16c0-3 2.2-5 5-5 0 3-2.2 5-5 5zM12 11c0-3-2.2-5-5-5 0 3 2.2 5 5 5z" />
      </>}
      {picto === PICTO_FLEUR && <>
        <path d="M12 21v-7.5" />
        <circle cx="12" cy="8.6" r="1.6" />
        <circle cx="12" cy="4.8" r="1.9" />
        <circle cx="12" cy="12.4" r="1.9" />
        <circle cx="8.2" cy="8.6" r="1.9" />
        <circle cx="15.8" cy="8.6" r="1.9" />
      </>}
      {picto === PICTO_PANIER && (
        <path d="M3 10h18l-1.7 9.2a2 2 0 0 1-2 1.6H6.7a2 2 0 0 1-2-1.6zM8 10l3-6.5M16 10l-3-6.5M9 14.5v2.5M15 14.5v2.5" />
      )}
      {picto === PICTO_COCHE && <path d="M4.5 12.5l5 5 10-11" />}
    </svg>
  )
}

/** Pictogramme d'une étape d'après sa clé serveur ; `null` si la clé est inconnue. */
export function IconeEtape({ etape, taille = 14, className = '' }) {
  const e = lireEtape(etape)
  return e ? <PictoEtape picto={e.picto} taille={taille} className={className} /> : null
}

/**
 * Étiquette d'étape [US-321 / CA1] : pictogramme + libellé. `prevue` : variante
 * hachurée « pas encore vue » (V3). Hors rang, elle reste lisible en niveaux de gris
 * parce qu'elle porte son mot.
 */
export function EtiquetteEtape({ etape, prevue = false, small = false, className = '' }) {
  const e = lireEtape(etape)
  if (!e) return null
  const v = prevue ? VARIANTE_PREVU : VARIANTE_PLEIN
  return (
    <span
      data-etape={e.cle} data-variante={v}
      title={libelleAccessible(e.cle, v)}
      className={`inline-flex items-center gap-1.5 rounded-full whitespace-nowrap font-semibold ${small ? 'text-[11px] px-2 py-[1px]' : 'text-[11.5px] px-2.5 py-0.5'} ${classesSegment(e.cle, v)} ${className}`}
    >
      <PictoEtape picto={e.picto} />
      {e.libelle}
      {prevue && <span className="sr-only"> — prévu</span>}
    </span>
  )
}

/**
 * Segment d'étape [US-321 / CA1] : la bande colorée d'un rang ou d'une ligne de
 * suivi. Cinq états (V3-V6) — `plein`, `prevu`, `a_confirmer` (pastille orange),
 * `a_liberer` (gris hachuré), `libre` (contour pointillé) — que le serveur dicte via
 * `variante()` de `lib/etapes.js`.
 *
 * Composant réutilisable : son wrapper est un conteneur de requêtes, le libellé
 * s'écrit « dès qu'il y a la place » (V2) et non selon la taille de l'écran. Le
 * pictogramme, lui, est toujours là. Le nom accessible porte l'état complet.
 */
export function SegmentEtape({ etape, variante = VARIANTE_PLEIN, className = '' }) {
  const libre = variante === VARIANTE_LIBRE
  const e = libre ? null : lireEtape(variante === VARIANTE_A_LIBERER ? ETAPE_TERMINEE : etape)
  if (!libre && !e) return null
  const cle = e?.cle
  const nom = libelleAccessible(cle, variante)
  return (
    <span className={`@container relative block min-w-0 ${className}`}>
      <span
        role="img" aria-label={nom} title={nom}
        data-etape={cle || 'libre'} data-variante={variante}
        className={`flex items-center justify-center gap-1.5 h-7 px-1.5 rounded-md overflow-hidden text-[11.5px] font-semibold whitespace-nowrap ${classesSegment(cle, variante)}`}
      >
        {libre
          ? <span className="hidden @[5.5rem]:inline">Libre</span>
          : <>
              <PictoEtape picto={e.picto} />
              <span className="hidden @[5.5rem]:inline truncate">{e.libelle}</span>
            </>}
      </span>
      {variante === VARIANTE_A_CONFIRMER && (
        <span data-pastille-etape aria-hidden="true"
          className="etape-pastille absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full" />
      )}
    </span>
  )
}

/**
 * Légende réutilisable [US-321 / CA4] : les étapes, puis « hachuré : prévu, à
 * confirmer », « à confirmer aujourd'hui », « rang libre ». `compact` (mobile) : six
 * étapes, Levé et Planté fusionnés. Les mots et les teintes viennent de la lib.
 */
export function LegendeEtapes({ compact = false, className = '' }) {
  return (
    <ul className={`flex flex-wrap gap-x-3 gap-y-1.5 ${className}`} aria-label="Légende des étapes">
      {entreesLegende({ compact }).map((entree) => (
        <li key={entree.type === 'etape' ? entree.cle : entree.type}
          className="flex items-center gap-1.5 text-[11.5px] text-txt2">
          {entree.type === 'etape' && (
            <span className={`inline-flex items-center justify-center w-5 h-5 rounded ${classesSegment(entree.cle, VARIANTE_PLEIN)}`}>
              <PictoEtape picto={entree.picto} taille={13} />
            </span>
          )}
          {entree.type === 'prevu' && (
            <span aria-hidden="true" className="etape-semee etape-prevue inline-block w-5 h-5 rounded" />
          )}
          {entree.type === 'pastille' && (
            <span aria-hidden="true" className="etape-pastille inline-block w-2.5 h-2.5 rounded-full mx-[5px]" />
          )}
          {entree.type === 'libre' && (
            <span aria-hidden="true" className="etape-libre inline-block w-5 h-5 rounded" />
          )}
          {entree.libelle}
        </li>
      ))}
    </ul>
  )
}
