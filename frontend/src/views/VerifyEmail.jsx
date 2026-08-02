// [US-044 / CA10] Écran affiché quand l'utilisateur clique le lien de vérification
// reçu par e-mail (URL du type /verifier-email?token=...). Indépendant de l'état
// de connexion — un compte pas encore vérifié ne peut pas se connecter (CA11).
import { useEffect, useRef, useState } from 'react'
import { authApi } from '../lib/api.js'

export default function VerifyEmail({ token, onDone }) {
  const [statut, setStatut] = useState('en_cours') // 'en_cours' | 'succes' | 'erreur'
  const [message, setMessage] = useState(null)
  // Le token est à usage unique côté backend : React.StrictMode exécute les
  // effets deux fois en dev pour détecter les effets non idempotents — sans
  // cette garde, le 2e appel retomberait à tort sur "token déjà utilisé".
  const dejaLance = useRef(false)

  useEffect(() => {
    if (dejaLance.current) return
    dejaLance.current = true

    authApi.verifyEmail(token)
      .then(() => setStatut('succes'))
      .catch((e) => {
        setStatut('erreur')
        setMessage(e.message)
      })
  }, [token])

  return (
    <div
      className="flex flex-col items-center justify-center h-dvh max-w-md mx-auto px-6 text-center"
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
        {statut === 'en_cours' && (
          <p style={{ color: 'var(--g-sec)', fontSize: 14 }}>Vérification de votre e-mail…</p>
        )}
        {statut === 'succes' && (
          <>
            <p style={{ color: 'var(--g-pri)', fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
              ✅ E-mail vérifié
            </p>
            <p style={{ color: 'var(--g-sec)', fontSize: 14, marginBottom: 16 }}>
              Vous pouvez maintenant vous connecter.
            </p>
          </>
        )}
        {statut === 'erreur' && (
          <>
            <p style={{ color: 'var(--g-red)', fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
              Lien invalide
            </p>
            <p style={{ color: 'var(--g-sec)', fontSize: 14, marginBottom: 16 }}>
              {message} — vous pouvez redemander un nouveau lien depuis l'écran de connexion.
            </p>
          </>
        )}

        {statut !== 'en_cours' && (
          <button
            onClick={onDone}
            style={{
              background: 'var(--g-acc)',
              color: 'var(--g-card)',
              borderRadius: 12,
              padding: '10px 0',
              fontWeight: 600,
              width: '100%',
            }}
          >
            Aller à la connexion
          </button>
        )}
      </div>
    </div>
  )
}
