// [US-271] Une proposition du compagnon, en carte : ce qu'il a compris, et trois boutons.
//
// Dans le langage de la maquette « Compagnon.html » : la carte reprend le gabarit de l'encart du
// support (fond de bulle, bord pointillé vert, titre à la main en Kalam) et ses boutons sont les
// pastilles des suggestions. La maquette ne dessine pas les cartes de proposition : ce gabarit est
// l'extension la plus proche de ce qu'elle montre.
//
// Un geste compris se confirme ICI (levée d'A16) ; une commande se confirme dans Telegram, et la
// carte le dit au lieu de proposer un bouton qui échouerait. La carte ne décide de rien : elle
// montre l'état que le serveur lui donne (`lib/compagnon.etatCarte`) et appelle l'API.
//
// Container queries (frontend/CLAUDE.md) : dans une carte étroite les boutons s'empilent en pleine
// largeur ; dès 20 rem ils se rangent en pastilles côte à côte.
import { Check, Pencil, X, Info } from 'lucide-react'
import { etatCarte, boutonsCarte } from '../lib/compagnon.js'

const ICONES = { confirmer: Check, corriger: Pencil, abandonner: X }

const PASTILLE = {
  primary: 'bg-brand text-white dark:text-bg border-brand',
  ghost: 'bg-[var(--gst-bulle)] text-brand-text border-brand hover:bg-brand-soft',
  quiet: 'bg-transparent text-txt3 border-transparent hover:text-txt2',
}

const ETIQUETTE = {
  brand: 'bg-brand-soft text-brand-text',
  amber: 'bg-amber-soft text-amber',
  red: 'bg-red-soft text-red',
  blue: 'bg-blue-soft text-blue',
}

export default function CarteProposition({ carte, occupe = false, onAction }) {
  const etat = etatCarte(carte)
  const boutons = boutonsCarte(carte, occupe)
  const lignes = carte.lignes?.length ? carte.lignes : [carte.resume]
  const titre = carte.nature === 'geste' ? 'Geste compris' : carte.nature === 'plan' ? 'Plan proposé' : 'Commande proposée'

  return (
    <div
      className={`@container/carte rounded-[12px] bg-[var(--gst-bulle)] px-3 py-2.5 text-[12.5px] text-txt2 border-[1.5px] ${
        etat.finale ? 'border-solid border-[var(--gst-bord)]' : 'border-dashed border-brand'
      }`}
      data-etat={etat.id}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <b className="font-hand text-[17px] leading-none text-txt">{titre}</b>
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${ETIQUETTE[etat.tone]}`}>
          {etat.libelle}
        </span>
      </div>

      <ul className="mt-1.5 space-y-0.5">
        {lignes.map((ligne, i) => (
          <li key={i} className="text-[13.5px] font-semibold text-txt break-words">{ligne}</li>
        ))}
      </ul>

      {(carte.avertissements ?? []).map((a, i) => (
        <p key={i} className="mt-2 rounded-[8px] bg-amber-soft px-2.5 py-1.5 text-amber">{a}</p>
      ))}

      {carte.erreur && (
        <p role="alert" className="mt-2 rounded-[8px] bg-red-soft px-2.5 py-1.5 text-red">{carte.erreur}</p>
      )}

      {carte.note && (
        <p className="mt-2 inline-flex items-start gap-1.5">
          <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
          {carte.note}
        </p>
      )}

      {!etat.finale && !carte.confirmable && carte.motif_non_confirmable && (
        <p className="mt-2">{carte.motif_non_confirmable}</p>
      )}

      {boutons.length > 0 && (
        <div className="mt-2.5 flex flex-col gap-1.5 @[17rem]/carte:flex-row @[17rem]/carte:flex-wrap">
          {boutons.map((b) => {
            const Icone = ICONES[b.id]
            return (
              <button
                key={b.id}
                type="button"
                disabled={!b.actif}
                onClick={() => onAction?.(b.id, carte)}
                className={`inline-flex items-center justify-center gap-1.5 rounded-full border-[1.5px] px-3.5 py-1.5 text-[12.5px] font-semibold transition-colors disabled:opacity-40 ${PASTILLE[b.kind]}`}
              >
                <Icone size={13} aria-hidden="true" />
                {b.libelle}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
