import { ArrowDown, ArrowUp } from 'lucide-react'

const COULEURS = {
  defavorable: 'text-[color:var(--ecart-defavorable)]',
  favorable: 'text-brand-text',
  neutre: 'text-[color:var(--ecart-neutre)]',
  indisponible: 'text-txt3 font-semibold',
}

/** « 2,31 M » → « 2,31 » + « M » : l'unité passe en petit, comme dans la maquette d'US-318. */
function separerUnite(texte) {
  const m = /^(.*) (M|k|%)$/.exec(texte)
  return m ? { nombre: m[1], unite: m[2] } : { nombre: texte, unite: '' }
}

/**
 * Un chiffre clé avec son écart à la période précédente [US-311 / US-312 / CA1].
 * L'écart se lit par une flèche, le texte et — quand il juge — le mot « défavorable » / « favorable » :
 * jamais par la couleur seule. `vide` : période sans appel (« — pas d'appel ») ;
 * `ancien` : dernières valeurs connues, marquées de leur heure (« de 14 h 32 »).
 */
export default function ChiffreCle({ libelle, texte, ecart, periodePrecedente, vide = false, ancien = '' }) {
  const { nombre, unite } = separerUnite(vide ? '0' : texte)
  const Fleche = ecart.delta !== null && ecart.delta < 0 ? ArrowDown : ArrowUp
  return (
    <div className="rounded-2xl border border-border bg-card px-[13px] py-3 shadow-card">
      <div className="text-xs leading-[1.3] text-txt2">{libelle}</div>
      <div className="mt-1 text-[23px] font-bold leading-[1.15] tracking-[-.01em] tabular-nums text-txt">
        {nombre}{unite ? <small className="ml-[3px] text-[12.5px] font-semibold text-txt3">{unite}</small> : null}
      </div>
      {vide ? (
        <span className="mt-[5px] inline-flex items-center gap-1 text-xs font-semibold text-txt3">— pas d'appel</span>
      ) : (
        <span className={`mt-[5px] inline-flex items-center gap-1 text-xs font-bold ${COULEURS[ecart.jugement]}`}>
          {ecart.jugement !== 'indisponible' && ecart.delta !== 0 ? <Fleche size={13} aria-hidden="true" /> : null}
          <span className="tabular-nums">{ecart.texte}</span>
          {ecart.libelle ? <em className="font-semibold not-italic">· {ecart.libelle}</em> : null}
        </span>
      )}
      {ancien ? <div><span className="mt-1 inline-flex items-center gap-1 rounded-full bg-card-alt px-2 py-px text-[11px] font-bold text-txt2">de {ancien}</span></div> : null}
      <p className="sr-only">par rapport à {periodePrecedente}</p>
    </div>
  )
}
