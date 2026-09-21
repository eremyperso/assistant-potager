// [US-224 / CA18, CA22, CA23] La file de gestes, montrée en permanence.
//
// Trois choses tiennent ici, et une seule d'entre elles est décorative :
//
//   * [CA22] **Le compte.** Combien de gestes attendent d'être confirmés, sur
//     tous les écrans concernés. Une file invisible serait une file oubliée,
//     et un jardinier qui a préparé quatre semis sans les confirmer croira
//     les avoir enregistrés.
//   * [CA23] **Le retrait.** On consulte sa file ici, et on en retire un geste.
//     On ne l'y confirme pas : la confirmation reste au compagnon (A16).
//   * [CA18] **Ce qui a été vidé.** La notification de purge est best-effort et
//     peut se perdre. Ce bandeau est son second porteur — sans quoi un geste
//     préparé et jamais confirmé disparaîtrait sans que personne ne le sache.
//
// Posé une fois dans la coquille, au-dessus du contenu de la vue : aucune vue
// n'a à porter son propre compteur.
import { useState } from 'react'
import { AlertCircle, Clock, Send, Trash2, X } from 'lucide-react'
import { Btn, InfoBanner, Modal, SectionLabel } from './ui'
import { useFileGestes } from '../context/FileGestesContext.jsx'

const LIBELLE_FILIERE = Object.freeze({ pepiniere: 'pépinière', pleine_terre: 'pleine terre' })

/** Une ligne de file : le geste, ce qu'il décrit, où et quand. */
function LigneGeste({ geste, onRetirer, retirable = true }) {
  const [enCours, setEnCours] = useState(false)
  const details = [
    geste.variete,
    geste.parcelle,
    geste.contexte_semis ? LIBELLE_FILIERE[geste.contexte_semis] : null,
    geste.date,
  ].filter(Boolean)

  return (
    <li className="flex items-start gap-2 py-2 border-b border-border last:border-0">
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-semibold text-txt">
          {geste.action}{geste.culture ? ` — ${geste.culture}` : ''}
        </div>
        {details.length > 0 && (
          <div className="text-[11.5px] text-txt3 leading-snug">{details.join(' · ')}</div>
        )}
        {geste.motif_refus && (
          <div className="text-[11.5px] text-amber leading-snug">{geste.motif_refus}</div>
        )}
      </div>
      {retirable && (
        <button
          type="button"
          title="Retirer de la file"
          disabled={enCours}
          onClick={async () => { setEnCours(true); try { await onRetirer(geste.id) } finally { setEnCours(false) } }}
          className="shrink-0 p-1.5 rounded-lg text-txt3 hover:text-red hover:bg-bg2"
        >
          <Trash2 size={15} aria-hidden="true" />
        </button>
      )}
    </li>
  )
}

/** [CA23] La file, en entier — consultable, et dont on peut retirer un geste. */
function ModalFile({ enAttente, relancesActives, onRetirer, onClose }) {
  return (
    <Modal title="Vos gestes en attente" icon={Clock} onClose={onClose}>
      <p className="text-[13px] text-txt2 leading-relaxed mb-3">
        Ces gestes sont <strong>préparés, pas enregistrés</strong>. Votre compagnon
        de terrain vous les fait confirmer un par un — c'est là, et seulement là,
        qu'ils entrent au carnet. Ils sont gardés trois jours.
      </p>
      {!relancesActives && (
        <p className="text-[12px] text-amber leading-relaxed mb-3">
          Vous avez coupé les rappels du compagnon : vos gestes vous attendent
          toujours, mais il ne vous les rappellera plus.
        </p>
      )}
      <SectionLabel>{enAttente.length} en attente</SectionLabel>
      <ul className="mt-1">
        {enAttente.map((geste) => (
          <LigneGeste key={geste.id} geste={geste} onRetirer={onRetirer} />
        ))}
      </ul>
    </Modal>
  )
}

export function BandeauFile() {
  const { enAttente, sortis, nbEnAttente, relancesActives, retirer, acquitterSortis } = useFileGestes()
  const [ouverte, setOuverte] = useState(false)

  // [CA18] Ce qui a été VIDÉ, et rien d'autre : un geste confirmé n'a pas
  // besoin d'être annoncé, il est au Journal. Un geste abandonné l'a été
  // exprès. Seule la purge est subie, et c'est elle qu'il faut dire.
  const vides = sortis.filter((geste) => geste.etat === 'perime')

  if (nbEnAttente === 0 && vides.length === 0) return null

  return (
    <div className="mb-4 flex flex-col gap-3">
      {vides.length > 0 && (
        <InfoBanner
          tint="amber"
          icon={AlertCircle}
          dismissible={false}
          title={`${vides.length} geste${vides.length > 1 ? 's' : ''} préparé${vides.length > 1 ? 's ont' : ' a'} été vidé${vides.length > 1 ? 's' : ''}`}
          body={
            <>
              <span className="block">
                Resté{vides.length > 1 ? 's' : ''} trois jours sans être confirmé
                {vides.length > 1 ? 's' : ''} : <strong>rien n'a été enregistré</strong>.
              </span>
              <span className="block mt-1">
                {vides.map((g) => [g.action, g.culture, g.parcelle].filter(Boolean).join(' — ')).join(' · ')}
              </span>
            </>
          }
          action={<Btn kind="ghost" small icon={X} onClick={acquitterSortis}>J'ai vu</Btn>}
        />
      )}

      {nbEnAttente > 0 && (
        <button
          type="button"
          onClick={() => setOuverte(true)}
          className="@container/file flex items-center gap-3 w-full text-left rounded-2xl px-4 py-3 bg-card border border-border hover:border-brand"
        >
          <span className="w-8 h-8 rounded-[9px] bg-bg2 flex items-center justify-center shrink-0">
            <Send size={16} className="text-brand" aria-hidden="true" />
          </span>
          <span className="flex-1 min-w-0">
            <span className="block text-sm font-bold text-txt">
              {nbEnAttente} geste{nbEnAttente > 1 ? 's' : ''} en attente de confirmation
            </span>
            <span className="block text-[12.5px] text-txt3 leading-snug">
              Préparé{nbEnAttente > 1 ? 's' : ''} ici, à confirmer dans votre compagnon — rien n'est
              encore enregistré.
            </span>
          </span>
          <span className="shrink-0 text-[11.5px] font-semibold text-brand">Voir</span>
        </button>
      )}

      {ouverte && (
        <ModalFile
          enAttente={enAttente}
          relancesActives={relancesActives}
          onRetirer={retirer}
          onClose={() => setOuverte(false)}
        />
      )}
    </div>
  )
}

export default BandeauFile
