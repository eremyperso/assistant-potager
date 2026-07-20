// [US-045 / CA1] Modal de génération d'un code de liaison chat Telegram ⇄ compte web.
import { useState, useEffect, useRef } from 'react'
import { X, Send } from 'lucide-react'
import { api } from '../lib/api.js'

function secondesRestantes(expireLe) {
  return Math.max(0, Math.round((new Date(expireLe).getTime() - Date.now()) / 1000))
}

export default function LierTelegram({ onClose }) {
  const [code, setCode] = useState(null)
  const [expireLe, setExpireLe] = useState(null)
  const [restant, setRestant] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  async function genererCode() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.genererCodeLiaisonTelegram()
      setCode(res.code)
      setExpireLe(res.expire_le)
      setRestant(secondesRestantes(res.expire_le))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { genererCode() }, [])

  useEffect(() => {
    if (!expireLe) return
    intervalRef.current = setInterval(() => setRestant(secondesRestantes(expireLe)), 1000)
    return () => clearInterval(intervalRef.current)
  }, [expireLe])

  const expire = restant <= 0

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
            <Send size={16} /> Relier Telegram
          </span>
          <button onClick={onClose} aria-label="Fermer" className="text-g-sec hover:text-g-pri">
            <X size={18} />
          </button>
        </div>

        <p style={{ color: 'var(--g-sec)', fontSize: 13, marginBottom: 12 }}>
          Envoyez ce code au bot Telegram (message <code>/lier CODE</code> ou le code seul).
        </p>

        {error && <p style={{ color: 'var(--g-red)', fontSize: 13, marginBottom: 8 }}>{error}</p>}

        {code && !loading && (
          <div className="flex flex-col items-center gap-2">
            <span
              style={{
                fontFamily: 'monospace',
                fontSize: 28,
                fontWeight: 700,
                letterSpacing: 4,
                color: expire ? 'var(--g-red)' : 'var(--g-acc)',
              }}
            >
              {code}
            </span>
            <span style={{ fontSize: 12, color: 'var(--g-sec)' }}>
              {expire ? 'Code expiré' : `Expire dans ${Math.floor(restant / 60)}:${String(restant % 60).padStart(2, '0')}`}
            </span>
          </div>
        )}

        {(expire || error) && (
          <button
            onClick={genererCode}
            disabled={loading}
            style={{
              marginTop: 14, width: '100%', background: 'var(--g-acc)', color: 'var(--g-card)',
              borderRadius: 12, padding: '8px 0', fontWeight: 600,
            }}
          >
            {loading ? '…' : 'Générer un nouveau code'}
          </button>
        )}
      </div>
    </div>
  )
}
