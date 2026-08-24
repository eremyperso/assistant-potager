// [US-050 / CA1] Modal de confirmation de dissociation du chat Telegram lié au
// compte web — pendant côté PWA de la commande `/delier` du bot (CA2), pour le
// cas où le chat lié n'est justement plus accessible (téléphone changé, compte
// Telegram perdu, liaison faite sur le mauvais chat).
import { useState } from 'react'
import { Unlink } from 'lucide-react'
import { api } from '../lib/api.js'
import { Modal, Btn } from './ui'

export default function DelierTelegram({ onClose }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function confirmer() {
    setLoading(true)
    setError(null)
    try {
      await api.delierTelegram()
      onClose()
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <Modal
      title="Désactiver votre compagnon"
      icon={Unlink}
      sub="Rompre le lien avec le chat actuellement relié"
      onClose={onClose}
      width={430}
      foot="Vous pourrez le réactiver à tout moment avec un nouveau lien."
    >
      <p className="text-[13.5px] text-txt leading-relaxed mb-2">
        Votre compagnon de terrain ne pourra plus dicter d'actions ni
        interroger vos données, ni vous envoyer de rappels, tant qu'il ne sera
        pas réactivé.
      </p>
      {/* [CA6] Aucune donnée métier n'est touchée par la dissociation — seul le
          lien telegram_chat_id ↔ user_id est rompu. */}
      <p className="text-[12.5px] text-txt3 leading-relaxed mb-4">
        Vos événements, parcelles et l'appartenance à vos potagers restent
        inchangés.
      </p>

      {error && <p className="text-red text-[13px] mb-2">{error}</p>}

      <div className="flex items-center justify-end gap-2">
        <Btn kind="ghost" onClick={onClose} disabled={loading}>
          Annuler
        </Btn>
        <Btn
          kind="soft"
          className="text-red border-red/40"
          onClick={confirmer}
          disabled={loading}
        >
          {loading ? '…' : 'Dissocier'}
        </Btn>
      </div>
    </Modal>
  )
}
