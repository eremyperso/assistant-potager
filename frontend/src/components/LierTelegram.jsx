// [US-045 / CA1] Génération d'un code de liaison chat Telegram ⇄ compte web.
// [US-055 / CA2] Habillage aligné sur `ModalTelegram` de la maquette 2026
// (`web-account.jsx`) — même logique (état, TTL, régénération), nouveau rendu.
// [US-091] Reframing éditorial : Telegram n'est plus « un compte à connecter »
// mais « un compagnon de terrain à activer » (CA2). Le geste unique deep-link
// + QR (CA3, CA4) est extrait en un hook + un panneau réutilisables — utilisés
// ici dans la modale du menu Compte, et par `ActivationCompagnon` (écran plein
// écran de fin d'onboarding, CA1).
import { useState, useEffect, useRef } from 'react'
import { Send, Check, Copy, ExternalLink } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../lib/api.js'
import { Modal, Btn, SectionLabel, Badge } from './ui'

function secondesRestantes(expireLe) {
  return Math.max(0, Math.round((new Date(expireLe).getTime() - Date.now()) / 1000))
}

// [US-091] État + logique partagés entre la modale (menu Compte) et l'écran
// plein écran d'onboarding — `botUsername` vient de GET /auth/me, résolu
// côté serveur à partir du token du bot (jamais une variable séparée à
// synchroniser à la main), vide seulement si l'appel Telegram échoue.
export function useCodeLiaison(telegramLie) {
  const [code, setCode] = useState(null)
  const [expireLe, setExpireLe] = useState(null)
  const [restant, setRestant] = useState(0)
  const [dureeTotale, setDureeTotale] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [copie, setCopie] = useState(false)
  const [botUsername, setBotUsername] = useState('')
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

  useEffect(() => { api.moi().then((m) => setBotUsername(m.bot_username || '')).catch(() => {}) }, [])

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
  const deepLink = code && botUsername ? `https://t.me/${botUsername}?start=${code}` : null

  return { code, restant, loading, error, copie, botUsername, deepLink, expire, pctRestant, genererCode, copierCode }
}

// [US-091 / CA3-CA7] Panneau du geste d'activation — bouton deep-link + QR
// visible sans interaction supplémentaire (CA4), repli code en clair + rappel
// `/lier CODE` (CA5), compte à rebours et régénération (CA7).
export function PanneauActivation({ etat, tailleQr = 132 }) {
  const { code, restant, loading, error, copie, deepLink, expire, pctRestant, genererCode, copierCode } = etat

  return (
    <div>
      {error && <p className="text-red text-[13px] mb-2">{error}</p>}

      {code && !loading && (
        <>
          {/* [Fix] Deux chemins clairement nommés par appareil plutôt qu'un QR
              et un bouton empilés sans hiérarchie — l'un lit « ouvrir » sans
              dire sur quel appareil, l'autre affichait la légende du QR APRÈS
              le bouton, dans le désordre. Bouton d'abord (l'action universelle,
              utilisable partout où Telegram est installé), QR ensuite (le
              relais explicite vers un second appareil). */}
          {deepLink && !expire && (
            <div className="mb-3.5">
              <SectionLabel>Sur cet appareil</SectionLabel>
              <div className="bg-card-alt rounded-2xl py-3.5 px-3.5 mb-3">
                {/* target="_blank" : sans lui, un clic remplace l'onglet de
                    l'application par la page Telegram (perte de session PWA)
                    dès que Telegram n'est pas installé pour intercepter le
                    lien — cas systématique sur desktop. Un nouvel onglet garde
                    l'appli vivante pendant l'activation, mobile compris (l'OS
                    intercepte toujours le deep-link vers l'app native le cas
                    échéant). */}
                <Btn
                  href={deepLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  kind="primary"
                  icon={ExternalLink}
                  className="w-full justify-center"
                >
                  Ouvrir mon compagnon
                </Btn>
                <p className="text-[11.5px] text-txt3 text-center leading-relaxed mt-2">
                  Si Telegram est installé ici (téléphone ou ordinateur), ce bouton l'ouvre directement.
                </p>
              </div>

              <SectionLabel>Depuis un autre appareil</SectionLabel>
              <div className="flex flex-col items-center gap-2.5 bg-card-alt rounded-2xl py-4.5 px-3.5">
                <div className="p-2.5 bg-white rounded-xl">
                  <QRCodeSVG value={deepLink} size={tailleQr} />
                </div>
                <p className="text-[11.5px] text-txt3 text-center leading-relaxed">
                  Pas de Telegram sur cet écran ? Scannez ce code avec l'appareil photo de votre téléphone.
                </p>
              </div>
            </div>
          )}

          <SectionLabel>Ou saisissez le code</SectionLabel>
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
        </>
      )}

      {(expire || error) && (
        <Btn kind="primary" onClick={genererCode} disabled={loading} className="w-full mt-3.5">
          {loading ? '…' : code ? 'Générer un nouveau lien' : "Générer un lien d'activation"}
        </Btn>
      )}

      {/* N'a de sens qu'une fois un code affiché — sinon l'instruction renvoie
          à un code qui n'existe pas encore. */}
      {code && !expire && (
        <p className="text-[12.5px] text-txt2 leading-relaxed mt-3.5">
          Ou envoyez ce code au bot Telegram du potager (<code>/lier CODE</code> ou le code seul).
        </p>
      )}
    </div>
  )
}

export default function LierTelegram({ telegramLie = false, onClose }) {
  const etat = useCodeLiaison(telegramLie)

  return (
    <Modal
      title="Activer votre compagnon"
      icon={Send}
      sub="Notes vocales, rappels et alertes depuis le potager"
      onClose={onClose}
      width={430}
      foot="Le lien et le code sont valables 10 minutes et ne servent qu'une fois."
    >
      {/* [CA2] État actuel de la liaison — « actif / à faire ». */}
      {telegramLie && (
        <div className="flex items-center gap-2.5 bg-brand-soft rounded-xl px-3.5 py-3 mb-4">
          <Check size={18} className="text-brand shrink-0" />
          <span className="flex-1 min-w-0 text-[13.5px] font-bold text-brand-text">Compagnon actif</span>
          <Badge tint="brand">actif</Badge>
        </div>
      )}

      {/* [Fix] `users.telegram_chat_id` est une colonne unique : lier un nouveau
          chat remplace silencieusement l'ancien (aucune notion d'appareils
          multiples côté backend, cf. `lier_chat_id`) — le libellé et
          l'avertissement doivent le refléter, pas suggérer un ajout. */}
      <SectionLabel>{telegramLie ? 'Remplacer la liaison' : "Générer un lien d'activation"}</SectionLabel>
      {telegramLie && (
        <p className="text-[12px] text-txt3 leading-relaxed -mt-1 mb-2.5">
          Activer un nouveau chat Telegram remplacera la liaison actuelle — un seul
          chat peut être relié à la fois.
        </p>
      )}

      <PanneauActivation etat={etat} />
    </Modal>
  )
}
