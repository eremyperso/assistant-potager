import { Modal, Btn } from './ui'
import { SlidersHorizontal } from 'lucide-react'

/**
 * [US-354] La feuille « Filtrer » de la barre d'outils : ce que la vue y range (groupes de choix, une
 * date…) tient dans `children`. Une feuille basse sur mobile, une fenêtre centrée au-delà. Le bouton
 * « Effacer » ramène la vue à ses réglages d'origine ; le compteur du bouton Filtrer le dit.
 */
export default function FeuilleFiltres({ titre = 'Filtrer', children, onEffacer, onFermer, peutEffacer = false }) {
  return (
    <Modal
      title={titre} icon={SlidersHorizontal} onClose={onFermer} disposition="basse"
      foot={(
        <div className="flex items-center justify-between gap-2">
          <Btn small kind="ghost" onClick={onEffacer} disabled={!peutEffacer}>Effacer les filtres</Btn>
          <Btn small kind="primary" onClick={onFermer}>Voir</Btn>
        </div>
      )}
    >
      <div className="flex flex-col gap-4">{children}</div>
    </Modal>
  )
}

/** Un groupe de choix exclusifs : « Famille », « Type de geste »… `options` : `[{ valeur, libelle }]`. */
export function GroupeChoix({ titre, options, valeur, onChoisir }) {
  return (
    <fieldset>
      <legend className="mb-2 text-[11.5px] font-bold uppercase tracking-[.06em] text-txt2">{titre}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => {
          const actif = o.valeur === valeur
          return (
            <button
              key={String(o.valeur)} type="button" aria-pressed={actif} onClick={() => onChoisir(o.valeur)}
              className={`inline-flex min-h-[34px] items-center rounded-full border px-3 text-[12.5px] font-semibold ${
                actif ? 'border-brand bg-brand text-white dark:text-bg' : 'border-border bg-card text-txt2'
              }`}
            >
              {o.libelle}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
