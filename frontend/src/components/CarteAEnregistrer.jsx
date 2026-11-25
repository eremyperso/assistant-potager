// [US-357 / CA5, CA6] La carte « À enregistrer » : tout ce que Gaston a compris dans un même tour,
// en UNE carte à confirmer — bord vert de 1,5 px, titre sur fond `brand-soft`, une ligne par
// proposition (`CarteProposition`), puis **Corriger** et **Confirmer** (40 px).
//
// La carte est une PRÉSENTATION : chaque ligne reste une proposition du serveur. Elle ne confirme
// rien d'elle-même — « Confirmer » appelle `onConfirmer(cartes)`, que l'écran exécute proposition
// par proposition par le chemin existant (`lib/carteAEnregistrer.confirmerEnSerie`). Aucune écriture
// sans ce geste.
import { Check, Pencil } from 'lucide-react'
import CarteProposition from './CarteProposition.jsx'
import { etatCarte } from '../lib/compagnon.js'
import { cartesAConfirmer, carteACorriger, carteEnAttente, TITRE_CARTE } from '../lib/carteAEnregistrer.js'

export default function CarteAEnregistrer({ cartes, occupe = false, onCorriger, onConfirmer, onAbandonner }) {
  const enAttente = carteEnAttente(cartes)
  const aConfirmer = cartesAConfirmer(cartes)
  const aCorriger = carteACorriger(cartes)

  return (
    <section
      className="@container/carte self-stretch overflow-hidden rounded-[14px] border-[1.5px] border-brand bg-card"
      aria-label={TITRE_CARTE}
      data-carte="a-enregistrer"
    >
      <h3 className="bg-brand-soft px-3 py-2 text-[12px] font-bold text-brand-deep">{TITRE_CARTE}</h3>

      <ul className="px-3 py-1.5">
        {cartes.map((carte) => <CarteProposition key={carte.id} carte={carte} />)}
      </ul>

      {enAttente && (
        <div className="flex flex-col gap-2 px-3 pb-3">
          <div className="flex gap-2">
            <button
              type="button"
              disabled={occupe || !aCorriger}
              onClick={() => onCorriger?.(aCorriger)}
              className="inline-flex min-h-[40px] flex-1 items-center justify-center gap-1.5 rounded-full border-[1.5px] border-brand bg-card px-3.5 text-[13px] font-semibold text-brand-text hover:bg-brand-soft disabled:opacity-40"
            >
              <Pencil size={14} aria-hidden="true" />
              Corriger
            </button>
            <button
              type="button"
              disabled={occupe || aConfirmer.length === 0}
              onClick={() => onConfirmer?.(aConfirmer)}
              className="inline-flex min-h-[40px] flex-1 items-center justify-center gap-1.5 rounded-full border-[1.5px] border-brand bg-brand px-3.5 text-[13px] font-semibold text-white hover:opacity-95 disabled:opacity-40 dark:text-bg"
            >
              <Check size={14} aria-hidden="true" />
              Confirmer
            </button>
          </div>
          <button
            type="button"
            disabled={occupe}
            onClick={() => onAbandonner?.(cartes.filter((c) => !etatCarte(c).finale))}
            className="self-center rounded-full px-3 py-1 text-[12px] font-semibold text-txt3 hover:text-txt2 disabled:opacity-40"
          >
            Abandonner
          </button>
        </div>
      )}
    </section>
  )
}
