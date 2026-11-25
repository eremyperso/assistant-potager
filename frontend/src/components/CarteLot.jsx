// [US-356 / CA4] La carte d'un lot — la MÊME dans le Parcours et dans le registre des Lots : emoji, nom,
// l'icône du lot et « #57 », « variété · quantité · semé le 20 oct. », la frise des gestes datés, une
// alerte orange quand le lot est à régler, et la note du jardinier — en Kalam, parce que c'est ce qu'il
// a dit (US-352 / CA6). Plus de mention de durée inconnue sur la carte : ce qui manque se règle depuis
// la fiche du lot, qui s'ouvre au toucher.
//
// La carte ne calcule rien : `lib/pepiniereSocle.carteLot` lui donne tout. Elle remplit la case qu'on
// lui donne (container query sur son propre conteneur, jamais de breakpoint d'écran).
import IconeLot from './ui/IconeLot.jsx'

/**
 * La frise des gestes datés : un point par geste, reliés par un trait ; les gestes passés sont évidés,
 * le dernier est plein. Chaque point dit son geste et sa date (infobulle), la frise entière en une phrase.
 */
export function FriseGestes({ gestes = [], className = '' }) {
  const n = gestes.length
  if (!n) return null
  const dit = gestes.map((g) => `${g.titre}${g.date ? ` le ${g.date}` : ''}`).join(', ')
  return (
    <span className={`flex items-center gap-[3px] ${className}`} role="img" aria-label={`${n} geste${n > 1 ? 's' : ''} daté${n > 1 ? 's' : ''} : ${dit}`}>
      {gestes.map((g, i) => (
        <span key={i} className="flex items-center gap-[3px]">
          {i > 0 && <span aria-hidden="true" className="block h-[1.5px] w-[14px] shrink-0 bg-brand opacity-45" />}
          <i
            aria-hidden="true" title={`${g.date ? `${g.date} · ` : ''}${g.titre}`}
            className={`block h-2 w-2 shrink-0 rounded-full ${i === n - 1 ? 'bg-brand' : 'bg-card shadow-[inset_0_0_0_1.5px_var(--brand)]'}`}
          />
        </span>
      ))}
    </span>
  )
}

export default function CarteLot({ carte, choisie = false, onOuvrir }) {
  return (
    <button
      type="button" onClick={onOuvrir} aria-label={carte.nomAccessible} aria-pressed={choisie} data-lot-choisi={choisie ? '' : undefined}
      className={`@container/lot flex w-full min-w-0 flex-col gap-1 rounded-[13px] border bg-card px-3 py-2.5 text-left shadow-card hover:border-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand ${choisie ? 'border-brand ring-2 ring-brand' : 'border-border'}`}
    >
      <span className="flex items-baseline gap-1.5">
        <span aria-hidden="true" className="text-[16px] leading-none">{carte.emoji}</span>
        <b className="min-w-0 flex-1 truncate text-[14px] font-bold text-txt">{carte.nom}</b>
        {carte.numero && (
          <span className="inline-flex shrink-0 items-center gap-[3px] self-center text-[11.5px] font-bold text-txt3">
            <IconeLot />{carte.numero}
          </span>
        )}
      </span>
      {carte.meta && <small className="text-[12px] leading-snug text-txt2">{carte.meta}</small>}
      <FriseGestes gestes={carte.gestes} className="mt-0.5" />
      {carte.alerte && (
        <span className="mt-0.5 inline-flex self-start rounded-full bg-due-bg px-2.5 py-0.5 text-[11.5px] font-bold text-due-tx">
          {carte.alerte}
        </span>
      )}
      {carte.note && <span className="note-carnet-texte mt-0.5 !text-[14.5px] line-clamp-2">{carte.note}</span>}
    </button>
  )
}
