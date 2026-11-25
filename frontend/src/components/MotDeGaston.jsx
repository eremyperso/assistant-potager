import { X } from 'lucide-react'
import { VisageGaston } from './Gaston.jsx'
import { GASTON } from '../lib/compagnon.js'
import { momentDeJournee } from '../lib/motDeGaston.js'

/** La première phrase se lit en gras, comme dans la maquette (« Gel annoncé samedi (−2 °C). »). */
function Texte({ texte }) {
  // [US-360 / CA5] Un mot peut marquer lui-même ce qui se lit en gras : « **3 rangs à libérer** : … ».
  if (texte.includes('**')) {
    return texte.split(/\*\*(.+?)\*\*/g).map((morceau, i) => (i % 2 ? <b key={i}>{morceau}</b> : morceau))
  }
  const coupe = texte.search(/[.!?…](\s|$)/)
  if (coupe === -1) return <b>{texte}</b>
  const premiere = texte.slice(0, coupe + 1)
  const reste = texte.slice(coupe + 1)
  return <><b>{premiere}</b>{reste}</>
}

/**
 * Mot de Gaston [US-353 / CA6] : ce que Gaston sait de cet écran, en deux phrases au plus et une à
 * trois actions. Fond `brand-soft`, visage de 40 px, « Gaston · ce matin », actions en pilules de
 * 34 px (la principale en vert plein), × de 30 px.
 *
 * **Sans rien à dire, le bloc n'est pas rendu** : `mot` nul → `null`, jamais un cadre vide ni en
 * attente. `compact` (le contenu a défilé, CA11) : une seule ligne, sans signature ni actions ; un
 * appui dessus remonte en haut (`onRemonter`).
 */
export default function MotDeGaston({ mot, compact = false, onAction, onMasquer, onRemonter }) {
  if (!mot) return null
  const { texte, actions } = mot
  return (
    <section
      aria-label={`Mot de ${GASTON.nom}`}
      data-compact={compact || undefined}
      onClick={compact ? onRemonter : undefined}
      className={`relative grid items-start rounded-2xl border border-[var(--mg-bord)] bg-brand-soft transition-all duration-200 ${
        compact
          ? 'cursor-pointer grid-cols-[26px_1fr] items-center gap-2.5 py-[7px] pl-2.5 pr-9'
          : 'grid-cols-[40px_1fr] gap-2.5 py-3 pl-3 pr-3.5'
      }`}
    >
      <span
        className={`overflow-hidden rounded-full shadow-[0_0_0_2px_var(--surface),0_0_0_3px_var(--brand)] ${compact ? 'h-[26px] w-[26px]' : 'h-10 w-10'}`}
        style={{ background: 'radial-gradient(circle at 50% 40%, var(--gst-visage), var(--gst-visage-2))' }}
        aria-hidden="true"
      >
        <span className="block h-full w-full [&>svg]:block [&>svg]:h-full [&>svg]:w-full"><VisageGaston /></span>
      </span>
      <div className="min-w-0">
        {!compact && (
          <div className="text-[11.5px] font-bold tracking-[.02em] text-brand-text">
            {GASTON.nom} · {momentDeJournee()}
          </div>
        )}
        <p className={`text-txt ${compact ? 'line-clamp-1 text-[13px] leading-[1.45]' : 'mt-px pr-[18px] text-[13.5px] leading-[1.45]'}`}>
          <Texte texte={texte} />
        </p>
        {!compact && actions.length > 0 && (
          <div className="mt-[9px] flex flex-wrap gap-1.5">
            {actions.map((a) => (
              <button
                key={a.libelle} type="button" onClick={() => onAction?.(a)}
                className={`min-h-[34px] rounded-full border px-3 text-[12.5px] font-bold ${
                  a.principale
                    ? 'border-brand bg-brand text-white'
                    : 'border-[var(--mg-action-bord)] bg-surface text-brand-deep'
                }`}
              >
                {a.libelle}
              </button>
            ))}
          </div>
        )}
      </div>
      {!compact && (
        <button
          type="button" onClick={onMasquer} aria-label={`Masquer le mot de ${GASTON.nom}`}
          className="absolute right-1.5 top-1.5 grid h-[30px] w-[30px] place-items-center rounded-full text-txt3"
        >
          <X size={14} aria-hidden="true" />
        </button>
      )}
    </section>
  )
}
