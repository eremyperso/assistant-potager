// [US-048 / CA3, CA5] Modal de gestion des membres du potager actif — réservée
// à l'owner : générer une invitation (code + rôle proposé), lister les membres,
// retirer un membre.
import { useState, useEffect } from 'react'
import { X, UserMinus, UserPlus } from 'lucide-react'
import { api } from '../lib/api.js'
import { usePotager } from '../context/PotagerContext.jsx'

export default function GestionMembres({ onClose }) {
  const { potagerActif } = usePotager()
  const [membres, setMembres] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [rolePropose, setRolePropose] = useState('editor')
  const [invitation, setInvitation] = useState(null)

  async function recharger() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.listerMembres(potagerActif.id)
      setMembres(res.membres)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (potagerActif) recharger() }, [potagerActif])

  async function handleInviter() {
    setError(null)
    try {
      const res = await api.creerInvitation(potagerActif.id, rolePropose)
      setInvitation(res)
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleRetirer(membreUserId) {
    setError(null)
    try {
      await api.retirerMembre(potagerActif.id, membreUserId)
      recharger()
    } catch (e) {
      setError(e.message)
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
            <UserPlus size={16} /> Membres du potager
          </span>
          <button onClick={onClose} aria-label="Fermer" className="text-g-sec hover:text-g-pri">
            <X size={18} />
          </button>
        </div>

        {error && <p style={{ color: 'var(--g-red)', fontSize: 13, marginBottom: 8 }}>{error}</p>}

        <div className="flex flex-col gap-2 mb-4">
          {loading && <span style={{ fontSize: 13, color: 'var(--g-sec)' }}>Chargement…</span>}
          {!loading && membres.map((m) => (
            <div key={m.user_id} className="flex items-center justify-between" style={{ fontSize: 13 }}>
              <span style={{ color: 'var(--g-pri)' }}>{m.email || `#${m.user_id}`} · {m.role}</span>
              {m.role !== 'owner' && (
                <button
                  onClick={() => handleRetirer(m.user_id)}
                  aria-label={`Retirer ${m.email || m.user_id}`}
                  className="text-g-red hover:opacity-70"
                >
                  <UserMinus size={15} />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2 mb-2">
          <select
            value={rolePropose}
            onChange={(e) => setRolePropose(e.target.value)}
            style={{
              flex: 1, background: 'var(--g-sur)', border: '1px solid var(--g-brd)',
              color: 'var(--g-pri)', borderRadius: 10, padding: '6px 8px', fontSize: 13,
            }}
          >
            <option value="editor">Editor</option>
            <option value="lecteur">Lecteur</option>
          </select>
          <button
            onClick={handleInviter}
            style={{
              background: 'var(--g-acc)', color: 'var(--g-card)',
              borderRadius: 10, padding: '6px 12px', fontSize: 13, fontWeight: 600,
            }}
          >
            Inviter
          </button>
        </div>

        {invitation && (
          <div className="flex flex-col items-center gap-1" style={{ marginTop: 8 }}>
            <span style={{ fontFamily: 'monospace', fontSize: 22, fontWeight: 700, letterSpacing: 3, color: 'var(--g-acc)' }}>
              {invitation.code}
            </span>
            <span style={{ fontSize: 12, color: 'var(--g-sec)' }}>
              Rôle proposé : {invitation.role_propose} — à partager avec la personne invitée
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
