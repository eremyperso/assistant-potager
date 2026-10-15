// [US-216 / CA10, CA11] Un compteur à grosses cibles — réutilisable.
//
// Une saisie debout devant une barquette : un clavier numérique ET des boutons
// « − / + » de 56 px (maquette figée du 14/10/2026). Le composant ne sait rien d'une
// levée, d'un lot ni d'une écriture : il tient un nombre, borné, et le rend. Un champ
// vide est `null` — aucun zéro n'est supposé tant que personne n'a compté.
import { useId } from 'react'
import { Minus, Plus } from 'lucide-react'
import { borner, lireNombre } from '../lib/ficheLot.js'

/**
 * @param valeur    Le nombre courant, ou `null` (champ vide).
 * @param onChange  Appelé avec le nouveau nombre, déjà borné — ou `null` si le champ est vidé.
 * @param max       Borne haute (illimité si absent).
 * @param libelle   Ce qu'on compte — lu par les lecteurs d'écran.
 * @param legende   Sous le champ (« levés sur 48 »).
 */
export default function CompteurNumerique({ valeur, onChange, max = null, libelle = 'Nombre', legende = null }) {
  const id = useId()
  const courant = valeur ?? 0
  const change = (n) => onChange(borner(n, max))
  const bouton = 'w-14 h-14 shrink-0 rounded-[14px] border border-border bg-card-alt text-txt flex items-center justify-center active:scale-95 transition-transform disabled:opacity-40'
  return (
    <div className="flex items-center gap-2.5">
      <button
        type="button" className={bouton} aria-label={`Un de moins — ${libelle}`}
        onClick={() => change(courant - 1)} disabled={courant <= 0}
      >
        <Minus size={22} aria-hidden="true" />
      </button>
      <label htmlFor={id} className="flex-1 min-w-0 flex flex-col items-center gap-0.5">
        <span className="sr-only">{libelle}</span>
        <input
          id={id}
          inputMode="numeric"
          pattern="[0-9]*"
          placeholder="0"
          value={valeur ?? ''}
          onChange={(e) => {
            if (e.target.value === '') { onChange(null); return }
            const n = lireNombre(e.target.value)
            if (n != null) change(n)
          }}
          onFocus={(e) => e.target.select()}
          className="w-full h-14 text-center text-[30px] font-bold tabular-nums text-txt bg-bg border-[1.5px] border-brand rounded-[14px] outline-none"
        />
        {legende && <span className="text-[11.5px] text-txt3">{legende}</span>}
      </label>
      <button
        type="button" className={bouton} aria-label={`Un de plus — ${libelle}`}
        onClick={() => change(courant + 1)} disabled={max != null && courant >= max}
      >
        <Plus size={22} aria-hidden="true" />
      </button>
    </div>
  )
}
