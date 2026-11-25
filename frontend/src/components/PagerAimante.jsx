import { useEffect, useRef } from 'react'

/**
 * [US-356 / CA3, CA9] Un pager à défilement horizontal AIMANTÉ : une colonne à la fois, et des points
 * qui suivent le défilement (le courant, allongé, en vert). Toucher un point y va. Le libellé de la
 * colonne courante (« En godet · 4 ») se lit à côté des points.
 *
 * Sert au Parcours (un stade à la fois) et au registre des Lots (un filtre à la fois) sur mobile : « les
 * mêmes points que le Parcours ». `pages` : `[{ cle, libelle, contenu }]`.
 *
 * Structure seulement — aucune donnée, aucune règle. La largeur d'une colonne est celle du pager (un
 * conteneur), jamais celle de l'écran.
 */
export default function PagerAimante({ pages, actif, onChange, etiquette = 'Colonnes', className = '' }) {
  const piste = useRef(null)
  const minuterie = useRef(null)
  const index = Math.max(0, pages.findIndex((p) => p.cle === actif))

  // La colonne choisie ailleurs (un point, un lien) : la piste s'y rend.
  useEffect(() => {
    const el = piste.current
    if (!el || !el.clientWidth) return
    if (Math.abs(el.scrollLeft - index * el.clientWidth) > 4) {
      el.scrollTo?.({ left: index * el.clientWidth, behavior: 'smooth' })
    }
  }, [index])

  useEffect(() => () => clearTimeout(minuterie.current), [])

  // Le doigt (ou la molette) a fait défiler : la colonne la plus proche devient la courante.
  const surDefilement = () => {
    clearTimeout(minuterie.current)
    minuterie.current = setTimeout(() => {
      const el = piste.current
      if (!el || !el.clientWidth) return
      const i = Math.round(el.scrollLeft / el.clientWidth)
      if (i !== index && pages[i]) onChange?.(pages[i].cle)
    }, 80)
  }

  const courante = pages[index]
  return (
    <div className={className}>
      <div className="mb-2 flex items-center gap-2.5">
        <span className="min-w-0 flex-1 truncate text-[12.5px] font-bold text-txt" aria-live="polite">{courante?.libelle}</span>
        <div role="tablist" aria-label={etiquette} className="flex shrink-0 items-center">
          {pages.map((p, i) => (
            <button
              key={p.cle} type="button" role="tab" aria-selected={i === index} aria-label={p.libelle}
              onClick={() => onChange?.(p.cle)}
              className="grid h-6 min-w-[22px] place-items-center"
            >
              <i className={`block h-2 rounded-full transition-all ${i === index ? 'w-[18px] bg-brand' : 'w-2 bg-border'}`} />
            </button>
          ))}
        </div>
      </div>
      <div
        ref={piste} onScroll={surDefilement}
        className="flex snap-x snap-mandatory overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {pages.map((p) => (
          <section
            key={p.cle} role="tabpanel" aria-label={p.libelle} aria-hidden={p.cle !== actif}
            className="w-full shrink-0 snap-center snap-always px-0.5"
          >
            {p.contenu}
          </section>
        ))}
      </div>
    </div>
  )
}
