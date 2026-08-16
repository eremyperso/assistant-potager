// [US-045 / CA1] Modal de génération d'un code de liaison chat Telegram ⇄ compte web.
// [US-055 / CA2] Habillage aligné sur `ModalTelegram` de la maquette 2026
// (`web-account.jsx`) — même logique (état, TTL, régénération), nouveau rendu.
import { useState, useEffect, useRef } from 'react'
import { Send, Check, Copy } from 'lucide-react'
import { api } from '../lib/api.js'
import { Modal, Btn, SectionLabel, Badge } from './ui'

function secondesRestantes(expireLe) {
  return Math.max(0, Math.round((new Date(expireLe).getTime() - Date.now()) / 1000))
}

export default function LierTelegram({ telegramLie = false, onClose }) {
  const [code, setCode] = useState(null)
  const [expireLe, setExpireLe] = useState(null)
  const [restant, setRestant] = useState(0)
  const [dureeTotale, setDureeTotale] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [copie, setCopie] = useState(false)
  const intervalRef = useRef(null)

  async function genererCode() {
    setLoading(true)
    setError(null)
    setCopie(false)
    try {
      const res = await api.genererCodeLiaisonTelegram()
      setCode(res.code)
      setExpireLe(res.expire_le)
      const s = secondesRestantes(res.expire_le)
      setRestant(s)
      setDureeTotale(s || 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function copierCode() {
    navigator.clipboard?.writeText(code).then(() => {
      setCopie(true)
      setTimeout(() => setCopie(false), 1500)
    })
  }

  // [Fix] Générer un code n'a de sens que si le compte n'est pas encore relié —
  // sinon la modale affichait un code de liaison actif juste sous le bandeau
  // « Compte relié », comme s'il fallait agir alors que non. Pour un compte
  // déjà relié, la génération devient une action explicite (bouton), réservée
  // au cas « relier un autre appareil ».
  useEffect(() => { if (!telegramLie) genererCode() }, [])

  useEffect(() => {
    if (!expireLe) return
    intervalRef.current = setInterval(() => setRestant(secondesRestantes(expireLe)), 1000)
    return () => clearInterval(intervalRef.current)
  }, [expireLe])

  const expire = restant <= 0
  const pctRestant = Math.round((restant / dureeTotale) * 100)

  return (
    <Modal
      title="Relier Telegram"
      icon={Send}
      sub="Saisir vos actions depuis la conversation Telegram"
      onClose={onClose}
      width={430}
      foot="Le code est valable 10 minutes et ne sert qu'une fois."
    >
      {/* [CA2] État actuel de la liaison — « relié / à faire ». */}
      {telegramLie && (
        <div className="flex items-center gap-2.5 bg-brand-soft rounded-xl px-3.5 py-3 mb-4">
          <Check size={18} className="text-brand shrink-0" />
          <span className="flex-1 min-w-0 text-[13.5px] font-bold text-brand-text">Compte relié</span>
          <Badge tint="brand">actif</Badge>
        </div>
      )}

      {/* [Fix] `users.telegram_chat_id` est une colonne unique : lier un nouveau
          chat remplace silencieusement l'ancien (aucune notion d'appareils
          multiples côté backend, cf. `lier_chat_id`) — le libellé et
          l'avertissement doivent le refléter, pas suggérer un ajout. */}
      <SectionLabel>{telegramLie ? 'Remplacer la liaison' : 'Générer un code'}</SectionLabel>
      {telegramLie && (
        <p className="text-[12px] text-txt3 leading-relaxed -mt-1 mb-2.5">
          Lier un nouveau chat Telegram remplacera la liaison actuelle — un seul
          chat peut être relié à la fois.
        </p>
      )}

      {error && <p className="text-red text-[13px] mb-2">{error}</p>}

      {code && !loading && (
        <div className="text-center bg-card-alt rounded-2xl py-4.5 px-3.5">
          <div className="flex items-center justify-center gap-2.5">
            <span
              className="font-serif text-[30px] font-bold tracking-[.26em] pl-[.26em]"
              style={{ color: expire ? 'var(--red)' : 'var(--txt)' }}
            >
              {code}
            </span>
            {/* Copier un code expiré n'a pas de sens : il ne sera plus accepté. */}
            {!expire && (
              <Btn kind="soft" small icon={Copy} onClick={copierCode}>
                {copie ? 'Copié' : 'Copier'}
              </Btn>
            )}
          </div>
          <div className="text-xs text-txt3 mt-2">
            {expire ? 'Code expiré' : `Expire dans ${Math.floor(restant / 60)}:${String(restant % 60).padStart(2, '0')}`}
          </div>
          <div className="h-[5px] bg-border rounded-full mt-2.5 mx-5 overflow-hidden">
            <div
              className="h-full bg-brand rounded-full transition-[width]"
              style={{ width: `${expire ? 0 : pctRestant}%` }}
            />
          </div>
        </div>
      )}

      {(expire || error) && (
        <Btn kind="primary" onClick={genererCode} disabled={loading} className="w-full mt-3.5">
          {loading ? '…' : code ? 'Générer un nouveau code' : 'Générer un code'}
        </Btn>
      )}

      {/* N'a de sens qu'une fois un code affiché — sinon l'instruction renvoie
          à un code qui n'existe pas encore. */}
      {code && (
        <p className="text-[12.5px] text-txt2 leading-relaxed mt-3.5">
          Envoyez ce code au bot Telegram du potager avec la commande de liaison
          (<code>/lier CODE</code> ou le code seul).
        </p>
      )}
    </Modal>
  )
}
