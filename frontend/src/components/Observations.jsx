import { useState } from 'react'
import { MessageCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import { Card } from './ui'

const PAGE_SIZE = 3

/**
 * [US-039] Icône déclencheur d'observations — bouton discret, à placer comme
 * item d'une ligne flex existante (parcelle ou culture). Le parent gère l'état
 * ouvert/fermé et le rendu de <ObservationPanel /> juste en dessous de la ligne.
 * Symbole "bulle de dialogue" repris de la maquette Claude Design à jour
 * (ObsGlyph → IcoChat, remplace l'ancien IcoEye).
 *
 * count : nombre d'observations — affiché en badge superposé façon notification
 * (coin supérieur droit de l'icône), plafonné à "10+" au-delà de 9.
 *
 * [US-059] Volontairement sans `container-type: inline-size`, contrairement au
 * panneau : la propriété implique `contain: inline-size`, qui coupe la largeur
 * intrinsèque — un bouton dimensionné par son contenu s'effondrerait à zéro.
 * L'icône est de taille fixe et n'a donc rien à réagencer.
 */
export function ObservationIcon({ onClick, active = false, size = 17, count = 0 }) {
  const label = count > 9 ? '10+' : String(count)

  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick() }}
      title="Observations"
      aria-label={`Observations (${count})`}
      // [feedback mobile] zone tactile élargie (padding invisible autour de l'icône)
      className="shrink-0 flex items-center justify-center bg-transparent border-none cursor-pointer p-2 -m-2"
    >
      <span className="relative inline-flex items-center justify-center">
        <MessageCircle size={size} className={active ? 'text-brand' : 'text-txt3'} />
        {count > 0 && (
          <span
            className="absolute -top-1.5 -right-[7px] flex items-center justify-center font-bold leading-none
                       min-w-[14px] h-3.5 px-[3px] rounded-full bg-brand text-bg text-[9px]"
          >
            {label}
          </span>
        )}
      </span>
    </button>
  )
}

/**
 * [US-039 / CA7, CA9] Bloc accordéon inline : charge les observations au premier
 * affichage (lazy) puis les garde en mémoire tant que le composant reste monté.
 * items : {date, texte}[] déjà nettoyés du préfixe [Catégorie] par le backend.
 *
 * Pagination par blocs de 3 (repris de la maquette Claude Design, ObsInlineBlock)
 * pour éviter une liste trop longue quand une parcelle/culture a beaucoup de notes.
 *
 * [US-059 CA3] Habillage de carte du design system, en fond `surface` pour se
 * détacher de la carte parente. [CA4] `@container/card` fourni par `Card` : sous
 * 16rem de large, la date passe au-dessus de la note plutôt que de lui disputer
 * la ligne.
 */
export function ObservationPanel({ items, loading }) {
  const [page, setPage] = useState(0)

  const total = items ? items.length : 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const clampedPage = Math.min(page, pageCount - 1)
  const pageItems = (items || []).slice(clampedPage * PAGE_SIZE, clampedPage * PAGE_SIZE + PAGE_SIZE)

  return (
    <Card
      bg="bg-surface"
      pad="px-2.5 py-2.5"
      className="mt-1.5 mb-1 w-full flex flex-col gap-2"
    >
      {loading && <p className="text-[12px] text-txt3">Chargement…</p>}
      {!loading && total === 0 && (
        <p className="text-[12px] italic text-txt3">Aucune observation enregistrée.</p>
      )}
      {!loading && pageItems.map((o, i) => (
        <div key={i} className="flex flex-col gap-0.5 @[16rem]/card:flex-row @[16rem]/card:gap-2">
          <span className="text-[11px] shrink-0 tabular-nums text-txt3 @[16rem]/card:w-7">{o.date}</span>
          <span className="text-[13px] flex-1 leading-snug text-txt">{o.texte}</span>
        </div>
      ))}
      {!loading && pageCount > 1 && (
        <div className="flex items-center justify-between mt-0.5 pt-1.5 border-t border-border">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={clampedPage === 0}
            aria-label="Observations précédentes"
            className="flex items-center p-0.5 bg-transparent border-none disabled:opacity-30 disabled:cursor-default cursor-pointer"
          >
            <ChevronLeft size={14} className="text-txt3" />
          </button>
          <span className="text-[11px] text-txt3">{clampedPage + 1} / {pageCount}</span>
          <button
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={clampedPage === pageCount - 1}
            aria-label="Observations suivantes"
            className="flex items-center p-0.5 bg-transparent border-none disabled:opacity-30 disabled:cursor-default cursor-pointer"
          >
            <ChevronRight size={14} className="text-txt3" />
          </button>
        </div>
      )}
    </Card>
  )
}
