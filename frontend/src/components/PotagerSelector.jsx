// [US-046 / CA2] Modal de sélection du potager actif.
// [US-048 / CA4] Complétée avec la saisie d'un code d'invitation — seul
// endroit accessible à tout moment (pas uniquement au premier onboarding,
// cf. AucunPotager.jsx) pour rejoindre un potager supplémentaire.
import { useState, useRef, useEffect } from 'react'
import { X, Sprout, Check } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'

// [US-054 / CA2] `focusCode` : ouverture depuis « Rejoindre un potager » du menu
// déroulant — le champ code prend le focus pour éviter un clic supplémentaire.
export default function PotagerSelector({ onClose, focusCode = false }) {
  const { potagers, activer, accepterInvitation } = usePotager()
  const [enCours, setEnCours] = useState(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState(null)
  const [rejoindre, setRejoindre] = useState(false)
  const champCode = useRef(null)

  useEffect(() => {
    if (focusCode) champCode.current?.focus()
  }, [focusCode])

  async function handleSelect(potagerId) {
    if (enCours) return
    setEnCours(potagerId)
    try {
      await activer(potagerId)
      // activer() recharge la page — pas besoin de fermer la modale manuellement
    } catch {
      setEnCours(null)
    }
  }

  async function handleRejoindre(e) {
    e.preventDefault()
    if (!code.trim() || rejoindre) return
    setRejoindre(true)
    setError(null)
    try {
      await accepterInvitation(code.trim())
      // accepterInvitation() recharge la page en cas de succès
    } catch (err) {
      setError(err.message)
      setRejoindre(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-6"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-xs"
        style={{ background: 'var(--g-card)', border: '1px solid var(--g-brd)', borderRadius: 18, padding: 20 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <span className="flex items-center gap-2 font-semibold text-g-pri">
            <Sprout size={16} /> Vos potagers
          </span>
          <button onClick={onClose} aria-label="Fermer" className="text-g-sec hover:text-g-pri">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col gap-2">
          {potagers.map((p) => (
            <button
              key={p.id}
              onClick={() => handleSelect(p.id)}
              disabled={Boolean(enCours)}
              className="flex items-center justify-between"
              style={{
                background: p.actif ? 'var(--g-acc-dim)' : 'var(--g-sur)',
                border: '1px solid var(--g-brd)',
                borderRadius: 12,
                padding: '10px 12px',
                color: 'var(--g-pri)',
                opacity: enCours && enCours !== p.id ? 0.5 : 1,
              }}
            >
              <span>{p.nom}</span>
              {p.actif && <Check size={16} color="var(--g-acc)" />}
              {enCours === p.id && <span style={{ fontSize: 12, color: 'var(--g-sec)' }}>…</span>}
            </button>
          ))}
        </div>

        <div style={{ borderTop: '1px solid var(--g-brd)', marginTop: 14, paddingTop: 14 }}>
          <p style={{ fontSize: 12, color: 'var(--g-sec)', marginBottom: 8 }}>
            Rejoindre un autre potager avec un code d'invitation
          </p>
          {error && <p style={{ color: 'var(--g-red)', fontSize: 13, marginBottom: 6 }}>{error}</p>}
          <form onSubmit={handleRejoindre} className="flex gap-2">
            <input
              ref={champCode}
              type="text"
              placeholder="Code"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              style={{
                flex: 1, background: 'var(--g-sur)', border: '1px solid var(--g-brd)',
                color: 'var(--g-pri)', borderRadius: 10, padding: '6px 10px', fontSize: 13,
                fontFamily: 'monospace', letterSpacing: 1,
              }}
            />
            <button
              type="submit"
              disabled={rejoindre || !code.trim()}
              style={{
                background: 'var(--g-acc)', color: 'var(--g-card)',
                borderRadius: 10, padding: '6px 14px', fontSize: 13, fontWeight: 600,
                opacity: rejoindre ? 0.6 : 1,
              }}
            >
              {rejoindre ? '…' : 'Rejoindre'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
