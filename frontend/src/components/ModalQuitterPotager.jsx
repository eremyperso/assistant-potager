// [US-086 / CA6] Confirmation avant de quitter un potager dont on est membre.
// Une seule étape, contrairement à l'archivage (ModalArchiverPotager) qui coupe
// l'écriture de tous les membres : le départ ne concerne que soi. Il est en
// revanche à sens unique — revenir demande une nouvelle invitation, ce que le
// texte dit noir sur blanc — et ne supprime rien (CA5), ce qu'il dit aussi.
import { useState } from 'react'
import { LogOut, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api.js'
import { Modal, Btn } from './ui'

export default function ModalQuitterPotager({ potagerId, nom, onClose, onQuitte }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function confirmer() {
    setLoading(true)
    setError(null)
    try {
      await api.quitterPotager(potagerId)
      onQuitte?.()
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <Modal title="Quitter ce potager" icon={LogOut} sub={nom} onClose={onClose} width={440}>
      <p className="flex items-start gap-2 text-[13.5px] text-txt leading-relaxed mb-2">
        <AlertTriangle size={16} className="text-red shrink-0 mt-0.5" />
        Tu ne feras plus partie de « {nom} » et tu n'y auras plus accès. Pour y revenir,
        il te faudra une nouvelle invitation.
      </p>
      <p className="text-[13px] text-txt2 leading-relaxed mb-4">
        Tes événements, parcelles et photos restent dans le potager : ils appartiennent au collectif.
      </p>
      {error && <p className="text-red text-[13px] mb-2">{error}</p>}
      <div className="flex items-center justify-end gap-2">
        <Btn kind="ghost" onClick={onClose} disabled={loading}>Annuler</Btn>
        <Btn kind="soft" className="text-red border-red/40" onClick={confirmer} disabled={loading}>
          {loading ? '…' : 'Quitter ce potager'}
        </Btn>
      </div>
    </Modal>
  )
}
