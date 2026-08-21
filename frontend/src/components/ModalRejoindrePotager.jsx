// Modale « Rejoindre un potager » — se résume à la saisie d'un code
// d'invitation, conformément à la maquette 2026 (`ModalRejoindre` de
// `web-account.jsx`) : plus de liste de potagers ni de bascule, uniquement le
// champ code et son bouton, réutilisant `accepterInvitation` (US-048).
//
// Remplace l'usage de `PotagerSelector.jsx` pour ce point d'entrée — ce
// composant hérité (Lot D, cf. index.css) mélangeait la liste des potagers,
// les archivés et le code dans une seule vue.
import { useState, useRef, useEffect } from 'react'
import { KeyRound } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { Modal, Btn } from './ui'

export default function ModalRejoindrePotager({ onClose }) {
  const { accepterInvitation } = usePotager()
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const champCode = useRef(null)

  useEffect(() => {
    champCode.current?.focus()
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    const codeNettoye = code.trim()
    if (loading || !codeNettoye) return
    setLoading(true)
    setError(null)
    try {
      await accepterInvitation(codeNettoye)
      // accepterInvitation() recharge la page en cas de succès.
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <Modal title="Rejoindre un potager" icon={KeyRound} sub="Avec un code d'invitation" onClose={onClose} width={400}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
        <p className="text-[13px] text-txt2 leading-relaxed">
          Saisis le code reçu du propriétaire. C'est lui qui définit le rôle qui te sera attribué.
        </p>
        <input
          ref={champCode}
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="XXXX-XXXX"
          className="h-11 px-3.5 rounded-[10px] border border-border bg-card text-[15px] tracking-[.2em] font-semibold text-txt placeholder:text-txt3 placeholder:tracking-[.2em] focus:outline-none focus:border-brand"
        />
        {error && <p className="text-[13px] text-red">{error}</p>}
        <Btn type="submit" kind="primary" disabled={loading || !code.trim()} className="justify-center">
          {loading ? 'Vérification…' : 'Rejoindre'}
        </Btn>
        <p className="text-[12px] text-txt3">Un code reste valable 7 jours et ne sert qu'une fois.</p>
      </form>
    </Modal>
  )
}
