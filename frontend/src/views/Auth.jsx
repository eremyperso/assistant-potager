// [US-044] Écran d'inscription / connexion — affiché tant qu'aucune session JWT n'est active.
import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

function IconOeil({ barre }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z" />
      <circle cx="12" cy="12" r="3" />
      {barre && <line x1="2" y1="22" x2="22" y2="2" />}
    </svg>
  )
}

export default function Auth() {
  const { login, register, loading, error, errorCode, resendVerification } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [message, setMessage] = useState(null)
  const [afficherMdp, setAfficherMdp] = useState(false)

  async function handleResend() {
    setMessage(null)
    await resendVerification(email)
    setMessage('Si ce compte existe, un nouvel e-mail de vérification vient d\'être envoyé.')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setMessage(null)

    if (mode === 'login') {
      const ok = await login(email, motDePasse)
      if (!ok) {
        setMotDePasse('')
        setAfficherMdp(false)
      }
    } else {
      const ok = await register(email, motDePasse)
      setMotDePasse('')
      setAfficherMdp(false)
      if (ok) {
        setMessage(
          "Compte créé — un e-mail de vérification vient d'être envoyé à votre adresse. " +
            'Cliquez sur le lien reçu pour activer votre compte avant de vous connecter.'
        )
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
          <div style={{ position: 'relative' }}>
            <input
              type={afficherMdp ? 'text' : 'password'}
              required
              minLength={8}
              placeholder="Mot de passe (8 caractères min.)"
              value={motDePasse}
              onChange={(e) => setMotDePasse(e.target.value)}
              style={{ ...inputStyle, width: '100%', paddingRight: 40 }}
            />
            <button
              type="button"
              onClick={() => setAfficherMdp((v) => !v)}
              aria-label={afficherMdp ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
              title={afficherMdp ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
              style={{
                position: 'absolute',
                right: 10,
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--g-sec)',
                lineHeight: 0,
                padding: 4,
              }}
            >
              <IconOeil barre={afficherMdp} />
            </button>
          </div>

          {error && <p style={{ color: 'var(--g-red)', fontSize: 13 }}>{error}</p>}
          {errorCode === 'EMAIL_NOT_VERIFIED' && (
            <button
              type="button"
              onClick={handleResend}
              disabled={loading}
              style={{ color: 'var(--g-acc)', fontSize: 13, textAlign: 'left' }}
            >
              Renvoyer l'e-mail de vérification
            </button>
          )}
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
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setMessage(null)
            setMotDePasse('')
            setAfficherMdp(false)
          }}
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
