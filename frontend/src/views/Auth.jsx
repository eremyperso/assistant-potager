// [US-044] Écran d'inscription / connexion — affiché tant qu'aucune session JWT n'est active.
import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

export default function Auth() {
  const { login, register, loading, error } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [message, setMessage] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setMessage(null)

    if (mode === 'login') {
      await login(email, motDePasse)
    } else {
      const ok = await register(email, motDePasse)
      if (ok) {
        setMessage('Compte créé — vous pouvez maintenant vous connecter.')
        setMode('login')
      }
    }
  }

  return (
    <div
      className="flex flex-col items-center justify-center h-dvh max-w-md mx-auto px-6"
      style={{ background: 'var(--g-bg)' }}
    >
      <div
        className="w-full"
        style={{
          background: 'var(--g-card)',
          border: '1px solid var(--g-brd)',
          borderRadius: 18,
          padding: 24,
        }}
      >
        <h1 style={{ color: 'var(--g-pri)', fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
          🌿 Assistant Potager
        </h1>
        <p style={{ color: 'var(--g-sec)', fontSize: 14, marginBottom: 20 }}>
          {mode === 'login' ? 'Connectez-vous à votre potager' : 'Créez votre compte'}
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="email"
            required
            placeholder="E-mail"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={inputStyle}
          />
          <input
            type="password"
            required
            minLength={8}
            placeholder="Mot de passe (8 caractères min.)"
            value={motDePasse}
            onChange={(e) => setMotDePasse(e.target.value)}
            style={inputStyle}
          />

          {error && <p style={{ color: 'var(--g-red)', fontSize: 13 }}>{error}</p>}
          {message && <p style={{ color: 'var(--g-acc)', fontSize: 13 }}>{message}</p>}

          <button
            type="submit"
            disabled={loading}
            style={{
              background: 'var(--g-acc)',
              color: 'var(--g-card)',
              borderRadius: 12,
              padding: '10px 0',
              fontWeight: 600,
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? '…' : mode === 'login' ? 'Se connecter' : "S'inscrire"}
          </button>
        </form>

        <button
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setMessage(null) }}
          style={{ color: 'var(--g-sec)', fontSize: 13, marginTop: 16, width: '100%', textAlign: 'center' }}
        >
          {mode === 'login' ? "Pas encore de compte ? S'inscrire" : 'Déjà un compte ? Se connecter'}
        </button>
      </div>
    </div>
  )
}

const inputStyle = {
  background: 'var(--g-sur)',
  border: '1px solid var(--g-brd)',
  borderRadius: 12,
  padding: '10px 12px',
  color: 'var(--g-pri)',
  fontSize: 14,
}
