const SEG = 'flex max-w-full gap-[3px] overflow-x-auto rounded-[10px] bg-card-alt p-[3px]'
const SEG_BTN = (actif) => `min-h-[34px] whitespace-nowrap rounded-lg px-[11px] py-[7px] text-[12.5px] font-semibold ${actif ? 'bg-card text-txt shadow-[0_1px_3px_rgba(0,0,0,.12)]' : 'text-txt2'}`

/** Le sélecteur à segments de la maquette d'US-318 (« Ventiler par »), tel que la vue Consommation le
 *  dessine : un seul choix actif, annoncé par `aria-pressed`. */
export default function Segments({ libelle, choix, valeur, surChoix }) {
  return (
    <div role="group" aria-label={libelle} className={SEG}>
      {choix.map((c) => (
        <button key={c.id || 'defaut'} type="button" aria-pressed={valeur === c.id} onClick={() => surChoix(c.id)} className={SEG_BTN(valeur === c.id)}>
          {c.libelle}
        </button>
      ))}
    </div>
  )
}
