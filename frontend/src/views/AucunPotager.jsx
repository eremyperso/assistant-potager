// [US-046 / CA5] Écran bloquant — le compte connecté n'appartient à aucun potager.
// [US-048 / CA1, CA4, CA7] Complète le parcours self-service : créer un potager
// ou rejoindre un potager existant via un code d'invitation, sans intervention
// d'un administrateur.
import { useState } from 'react'
import { Sprout } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'

export default function AucunPotager() {
  const { logout } = useAuth()
  const { creerPotager, accepterInvitation } = usePotager()

  const [onglet, setOnglet] = useState('creer') // 'creer' | 'rejoindre'
  const [nom, setNom] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleCreer(e) {
    e.preventDefault()
    if (!nom.trim()) return
    setLoading(true)
    setError(null)
    try {
      await creerPotager(nom.trim())
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  async function handleRejoindre(e) {
    e.preventDefault()
    if (!code.trim()) return
    setLoading(true)
    setError(null)
    try {
      await accepterInvitation(code.trim())
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  const inputStyle = {
    width: '100%', background: 'var(--g-sur)', border: '1px solid var(--g-brd)',
    color: 'var(--g-pri)', borderRadius: 10, padding: '8px 12px', fontSize: 14,
  }
  const boutonStyle = {
    marginTop: 12, width: '100%', background: 'var(--g-acc)', color: 'var(--g-card)',
    borderRadius: 12, padding: '8px 0', fontWeight: 600, opacity: loading ? 0.6 : 1,
  }

  return (
    <div
      className="flex flex-col items-center justify-center h-dvh max-w-md mx-auto px-6 text-center"
      style={{ background: 'var(--g-bg)' }}
    >
      <Sprout size={40} color="var(--g-acc)" style={{ marginBottom: 16 }} />
      <h1 style={{ color: 'var(--g-pri)', fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
        Aucun potager pour l'instant
      </h1>
      <p style={{ color: 'var(--g-sec)', fontSize: 14, marginBottom: 20 }}>
        Créez votre potager ou rejoignez-en un existant avec un code d'invitation.
      </p>

      <div className="flex gap-2 mb-4" style={{ width: '100%' }}>
        <button
          onClick={() => setOnglet('creer')}
          style={{
            flex: 1, borderRadius: 10, padding: '6px 0', fontSize: 13, fontWeight: 600,
            background: onglet === 'creer' ? 'var(--g-acc)' : 'var(--g-sur)',
            color: onglet === 'creer' ? 'var(--g-card)' : 'var(--g-sec)',
            border: '1px solid var(--g-brd)',
          }}
        >
          Créer un potager
        </button>
        <button
          onClick={() => setOnglet('rejoindre')}
          style={{
            flex: 1, borderRadius: 10, padding: '6px 0', fontSize: 13, fontWeight: 600,
            background: onglet === 'rejoindre' ? 'var(--g-acc)' : 'var(--g-sur)',
            color: onglet === 'rejoindre' ? 'var(--g-card)' : 'var(--g-sec)',
            border: '1px solid var(--g-brd)',
          }}
        >
          Rejoindre (code)
        </button>
      </div>

      {error && <p style={{ color: 'var(--g-red)', fontSize: 13, marginBottom: 8 }}>{error}</p>}

      {onglet === 'creer' ? (
        <form onSubmit={handleCreer} style={{ width: '100%' }}>
          <input
            type="text"
            placeholder="Nom du potager"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            style={inputStyle}
          />
          <button type="submit" disabled={loading || !nom.trim()} style={boutonStyle}>
            {loading ? '…' : 'Créer'}
          </button>
        </form>
      ) : (
        <form onSubmit={handleRejoindre} style={{ width: '100%' }}>
          <input
            type="text"
            placeholder="Code d'invitation"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            style={{ ...inputStyle, fontFamily: 'monospace', letterSpacing: 2, textAlign: 'center' }}
          />
          <button type="submit" disabled={loading || !code.trim()} style={boutonStyle}>
            {loading ? '…' : 'Rejoindre'}
          </button>
        </form>
      )}

      <button
        onClick={logout}
        style={{
          marginTop: 20,
          background: 'var(--g-sur)', border: '1px solid var(--g-brd)', color: 'var(--g-pri)',
          borderRadius: 12, padding: '8px 16px', fontSize: 13,
        }}
      >
        Se déconnecter
      </button>
    </div>
  )
}
