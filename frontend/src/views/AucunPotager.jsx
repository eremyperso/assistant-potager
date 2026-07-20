// [US-046 / CA5] Écran bloquant — le compte connecté n'appartient à aucun potager.
import { Sprout } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

export default function AucunPotager() {
  const { logout } = useAuth()

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
        Votre compte n'est encore rattaché à aucun potager. Créez-en un ou demandez à être
        invité·e sur un potager existant pour commencer à l'utiliser ici.
      </p>
      <button
        onClick={logout}
        style={{
          background: 'var(--g-sur)', border: '1px solid var(--g-brd)', color: 'var(--g-pri)',
          borderRadius: 12, padding: '8px 16px', fontSize: 13,
        }}
      >
        Se déconnecter
      </button>
    </div>
  )
}
