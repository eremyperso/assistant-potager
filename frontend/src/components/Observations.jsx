import { useState } from 'react'
import { Eye, ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZE = 3

/**
 * [US-039] Icône déclencheur d'observations — bouton discret, à placer comme
 * item d'une ligne flex existante (parcelle ou culture). Le parent gère l'état
 * ouvert/fermé et le rendu de <ObservationPanel /> juste en dessous de la ligne.
 * Symbole "œil" repris de la maquette Claude Design (ObsGlyph → IcoEye).
 */
export function ObservationIcon({ onClick, active = false, size = 17 }) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick() }}
      title="Observations"
      aria-label="Observations"
      className="shrink-0 flex items-center justify-center"
      style={{
        background: 'none', border: 'none', cursor: 'pointer',
        // [feedback mobile] zone tactile élargie (padding invisible autour de l'icône)
        padding: 8, margin: -8,
      }}
    >
      <Eye size={size} style={{ color: active ? 'var(--g-acc)' : 'var(--g-sec)' }} />
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
 */
export function ObservationPanel({ items, loading }) {
  const [page, setPage] = useState(0)

  const total = items ? items.length : 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const clampedPage = Math.min(page, pageCount - 1)
  const pageItems = (items || []).slice(clampedPage * PAGE_SIZE, clampedPage * PAGE_SIZE + PAGE_SIZE)

  return (
    <div
      className="rounded-lg px-2 py-2.5 mt-1.5 mb-1 w-full flex flex-col gap-2"
      style={{ background: 'var(--g-sur)' }}
    >
      {loading && (
        <p className="text-[12px]" style={{ color: 'var(--g-sec)' }}>Chargement…</p>
      )}
      {!loading && total === 0 && (
        <p className="text-[12px] italic" style={{ color: 'var(--g-sec)' }}>Aucune observation enregistrée.</p>
      )}
      {!loading && pageItems.map((o, i) => (
        <div key={i} className="flex gap-2">
          <span className="text-[11px] shrink-0 w-7 tabular-nums" style={{ color: 'var(--g-sec)' }}>{o.date}</span>
          <span className="text-[13px] flex-1 leading-snug" style={{ color: 'var(--g-pri)' }}>{o.texte}</span>
        </div>
      ))}
      {!loading && pageCount > 1 && (
        <div
          className="flex items-center justify-between mt-0.5 pt-1.5"
          style={{ borderTop: '1px solid var(--g-brd)' }}
        >
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={clampedPage === 0}
            className="flex items-center"
            style={{
              background: 'none', border: 'none',
              cursor: clampedPage === 0 ? 'default' : 'pointer',
              padding: 2, opacity: clampedPage === 0 ? 0.3 : 1,
            }}
          >
            <ChevronLeft size={14} style={{ color: 'var(--g-sec)' }} />
          </button>
          <span className="text-[11px]" style={{ color: 'var(--g-sec)' }}>{clampedPage + 1} / {pageCount}</span>
          <button
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={clampedPage === pageCount - 1}
            className="flex items-center"
            style={{
              background: 'none', border: 'none',
              cursor: clampedPage === pageCount - 1 ? 'default' : 'pointer',
              padding: 2, opacity: clampedPage === pageCount - 1 ? 0.3 : 1,
            }}
          >
            <ChevronRight size={14} style={{ color: 'var(--g-sec)' }} />
          </button>
        </div>
      )}
    </div>
  )
}
