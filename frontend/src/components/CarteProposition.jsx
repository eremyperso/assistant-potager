// [US-271, US-357] Une proposition du compagnon, en LIGNE de la carte « À enregistrer ».
//
// Depuis US-357 il n'y a plus une carte à titre en Kalam et bord pointillé par proposition : les
// propositions d'un même tour vivent dans UNE carte (`CarteAEnregistrer`), et ce composant dessine
// la part de l'une d'elles — une ligne par geste : la pastille d'étape (hachurée si l'événement est
// prévu), « **Levée** · fève · rang 6 · aujourd'hui », et pour une note au carnet sa citation. Il
// dit aussi, sur la ligne, ce qui lui est arrivé : confirmée, échouée (avec la raison), laissée
// tomber, ou « à confirmer dans Telegram » pour une commande que seul le bot exécute.
//
// La ligne ne décide de rien : elle montre l'état que le serveur lui donne (`lib/compagnon.etatCarte`).
// Les boutons, eux, sont ceux de la carte : un seul « Confirmer » pour toutes les lignes.
//
// Container queries (frontend/CLAUDE.md) : la citation d'une note tient sur une ligne dans une carte
// étroite, sur deux dès 20 rem.
import { Check, Info, NotebookPen } from 'lucide-react'
import { etatCarte } from '../lib/compagnon.js'
import { lignesDeCarte } from '../lib/carteAEnregistrer.js'
import { PastilleEtape } from './ui/EtapeCulture.jsx'

const TON_ETAT = {
  brand: 'text-brand-text',
  amber: 'text-amber',
  red: 'text-red',
  blue: 'text-blue',
}

function Pastille({ ligne }) {
  if (ligne.note) {
    return (
      <span
        className="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-[9px] border border-paper-bd bg-paper text-[#7B6A3E]"
        aria-hidden="true"
      >
        <NotebookPen size={16} />
      </span>
    )
  }
  if (ligne.etape) return <PastilleEtape etape={ligne.etape} prevue={ligne.prevue} petite />
  return (
    <span className="grid h-[30px] w-[30px] shrink-0 place-items-center rounded-[9px] bg-card-alt text-txt2" aria-hidden="true">
      <Check size={15} />
    </span>
  )
}

export default function CarteProposition({ carte }) {
  const etat = etatCarte(carte)
  const lignes = lignesDeCarte(carte)
  // Une proposition en attente ne dit rien de son état (la carte porte les boutons) : seul un état
  // final, ou une erreur, se dit sur la ligne.
  const dit = etat.finale || etat.id === 'erreur'
  const confirmee = etat.id === 'confirmee'

  return (
    <>
      {lignes.map((ligne, i) => (
        <li
          key={ligne.cle}
          data-etat={etat.id}
          className="@container/ligne border-t border-border-soft py-1.5 first:border-t-0 text-[13px] text-txt"
        >
          <div className="flex items-center gap-2">
            <Pastille ligne={ligne} />
            <span className={`min-w-0 flex-1 break-words leading-[1.35] ${etat.id === 'abandonnee' || etat.id === 'remplacee' ? 'text-txt3 line-through' : ''}`}>
              {ligne.note ? (
                <>
                  {ligne.titre}
                  {ligne.citation && (
                    <>
                      {' : '}
                      {/* Kalam n'écrit que ce que le jardinier a dit (US-352 / CA6) : la citation de sa note. */}
                      <span className="note-carnet-texte !text-[15px] line-clamp-1 @[20rem]/ligne:line-clamp-2">« {ligne.citation} »</span>
                    </>
                  )}
                </>
              ) : (
                <>
                  {ligne.titre ? <b className="font-bold">{ligne.titre}</b> : null}
                  {ligne.titre && ligne.reste ? ' · ' : null}
                  {ligne.titre ? ligne.reste : <b className="font-semibold">{ligne.reste}</b>}
                </>
              )}
            </span>
            {i === 0 && dit && (
              <span className={`shrink-0 text-[11.5px] font-semibold ${TON_ETAT[etat.tone]}`}>
                {confirmee ? <Check size={14} className="inline" aria-label="Confirmé" /> : etat.libelle}
              </span>
            )}
          </div>

          {/* [US-272 / CA6 / F5] Le potager où elle s'exécute, quand le jardinier en a plusieurs. */}
          {i === 0 && carte.potager && (
            <p className="mt-0.5 pl-[38px] text-[11.5px] font-semibold text-txt3 break-words">🏡 {carte.potager}</p>
          )}

          {i === lignes.length - 1 && (
            <>
              {(carte.avertissements ?? []).map((a, k) => (
                <p key={k} className="mt-1 ml-[38px] rounded-[8px] bg-amber-soft px-2.5 py-1.5 text-[12.5px] text-amber">{a}</p>
              ))}

              {carte.erreur && (
                <p role="alert" className="mt-1 ml-[38px] rounded-[8px] bg-red-soft px-2.5 py-1.5 text-[12.5px] text-red">{carte.erreur}</p>
              )}

              {carte.note && (
                <p className="mt-1 ml-[38px] inline-flex items-start gap-1.5 text-[12.5px] text-txt2">
                  <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                  {carte.note}
                </p>
              )}

              {!etat.finale && !carte.confirmable && carte.motif_non_confirmable && (
                <p className="mt-1 ml-[38px] text-[12.5px] text-txt2">{carte.motif_non_confirmable}</p>
              )}
            </>
          )}
        </li>
      ))}
    </>
  )
}
