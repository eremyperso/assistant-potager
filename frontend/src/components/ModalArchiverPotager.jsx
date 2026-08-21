// [US-083 / CA3] Confirmation en deux étapes avant d'archiver un potager — il
// passe en lecture seule (CA4) tant qu'il n'est pas désarchivé (CA8). Double
// confirmation explicite : une simple modale à un bouton suffit à une action
// réversible en un clic (ex. DelierTelegram), mais archiver coupe l'écriture
// de tous les membres d'un potager potentiellement partagé — la conséquence
// mérite d'être lue deux fois avant validation.
import { useState } from 'react'
import { Archive, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api.js'
import { Modal, Btn } from './ui'

export default function ModalArchiverPotager({ potagerId, nom, onClose, onArchive }) {
  const [etape, setEtape] = useState('expliquer') // 'expliquer' | 'confirmer'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function confirmer() {
    setLoading(true)
    setError(null)
    try {
      await api.archiverPotager(potagerId)
      onArchive?.()
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <Modal title="Archiver ce potager" icon={Archive} sub={nom} onClose={onClose} width={440}>
      {etape === 'expliquer' ? (
        <>
          {/* [CA3] Texte imposé par l'US, mot pour mot. */}
          <p className="text-[13.5px] text-txt leading-relaxed mb-4">
            Ce potager passera en lecture seule. Personne ne pourra plus y
            enregistrer d'événement. Tu pourras le désarchiver plus tard.
          </p>
          <div className="flex items-center justify-end gap-2">
            <Btn kind="ghost" onClick={onClose}>Annuler</Btn>
            <Btn kind="soft" className="text-amber border-amber/40" onClick={() => setEtape('confirmer')}>
              Continuer
            </Btn>
          </div>
        </>
      ) : (
        <>
          <p className="flex items-start gap-2 text-[13.5px] text-txt leading-relaxed mb-4">
            <AlertTriangle size={16} className="text-red shrink-0 mt-0.5" />
            Confirme l'archivage de « {nom} ». Tous les membres perdent
            l'écriture immédiatement.
          </p>
          {error && <p className="text-red text-[13px] mb-2">{error}</p>}
          <div className="flex items-center justify-end gap-2">
            <Btn kind="ghost" onClick={onClose} disabled={loading}>Annuler</Btn>
            <Btn kind="soft" className="text-red border-red/40" onClick={confirmer} disabled={loading}>
              {loading ? '…' : 'Oui, archiver ce potager'}
            </Btn>
          </div>
        </>
      )}
    </Modal>
  )
}
