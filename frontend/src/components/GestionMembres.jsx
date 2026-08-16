// [US-048 / CA3, CA5] Modal de gestion des membres du potager actif — réservée
// à l'owner : générer une invitation (code + rôle proposé), lister les membres,
// retirer un membre.
// [US-055 / CA3] Habillage aligné sur `ModalMembres` de la maquette 2026
// (`web-account.jsx`) — même logique (lister, inviter, retirer), nouveau rendu.
import { useState, useEffect } from 'react'
import { UserMinus, Users, Copy, Key, Pencil, Eye } from 'lucide-react'
import { api } from '../lib/api.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { initiales, nomAffiche } from '../lib/identite.js'
import { libelleRole, teinteRole } from '../lib/roles.js'
import { Modal, Btn, RoleSelect, Badge } from './ui'

// [US-055] Icône + description par rôle invitable — porté depuis `ROLE_OPTS`
// de la maquette (`web-account.jsx`) ; libellé et teinte restent centralisés
// dans `lib/roles.js`, seule source de vérité partagée avec PotagerMenu/AccountMenu.
const ROLES_INVITABLES = [
  { value: 'editor', icon: Pencil, sub: 'Saisit récoltes, semis et cultures' },
  { value: 'lecteur', icon: Eye, sub: 'Consulte sans rien modifier' },
]

/** « expire dans 6 j » / « expire dans moins d'un jour » à partir d'un ISO. */
function expirationLisible(expireLe) {
  const jours = Math.ceil((new Date(expireLe).getTime() - Date.now()) / 86_400_000)
  if (jours <= 0) return "expire dans moins d'un jour"
  return `expire dans ${jours} j`
}

export default function GestionMembres({ moiId, onClose }) {
  const { potagerActif } = usePotager()
  const [membres, setMembres] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [rolePropose, setRolePropose] = useState('editor')
  const [invitation, setInvitation] = useState(null)
  const [copie, setCopie] = useState(false)

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
      setCopie(false)
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

  function copierCode() {
    navigator.clipboard?.writeText(invitation.code).then(() => {
      setCopie(true)
      setTimeout(() => setCopie(false), 1500)
    })
  }

  return (
    <Modal
      title="Membres du potager"
      icon={Users}
      sub={`${potagerActif?.nom || '—'} · ${membres.length} membre${membres.length > 1 ? 's' : ''}`}
      onClose={onClose}
      width={520}
      foot="Seul le propriétaire peut inviter ou retirer un membre."
    >
      {error && <p className="text-red text-[13px] mb-2">{error}</p>}

      <div className="flex flex-col gap-2 mb-4">
        {loading && <span className="text-[13px] text-txt3">Chargement…</span>}
        {!loading && membres.map((m) => (
          <div key={m.user_id} className="flex items-center gap-3 p-3 rounded-xl bg-card-alt">
            <span className="w-[34px] h-[34px] rounded-full bg-brand-soft text-brand-text flex items-center justify-center text-[13px] font-bold shrink-0">
              {initiales(m.nom, m.email)}
            </span>
            <span className="flex-1 min-w-0">
              <span className="flex items-center gap-1.5 text-[13.5px] font-semibold text-txt truncate">
                {nomAffiche(m.nom, m.email)}
                {m.user_id === moiId && <span className="text-[11px] font-medium text-txt3">(vous)</span>}
              </span>
              <span className="block text-[11.5px] text-txt3 truncate mt-px">{m.email}</span>
            </span>
            <Badge tint={teinteRole(m.role)}>{libelleRole(m.role)}</Badge>
            {m.role !== 'owner' && (
              <button
                onClick={() => handleRetirer(m.user_id)}
                aria-label={`Retirer ${m.email || m.user_id}`}
                className="text-red hover:opacity-70 shrink-0"
              >
                <UserMinus size={15} />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="bg-brand-soft rounded-2xl p-3.5">
        <div className="flex items-center gap-1.5 mb-2.5">
          <Key size={16} className="text-brand" />
          <span className="text-[13.5px] font-bold text-brand-text">Inviter un membre</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <RoleSelect value={rolePropose} options={ROLES_INVITABLES} onChange={setRolePropose} />
          <Btn kind="primary" icon={Key} onClick={handleInviter}>Générer un code</Btn>
        </div>

        {invitation && (
          <div className="flex items-center gap-2.5 mt-3 bg-card rounded-[10px] px-3.5 py-2.5">
            <span className="flex-1 text-[17px] font-bold tracking-[.2em] text-txt">{invitation.code}</span>
            <span className="text-[11.5px] text-txt3">{expirationLisible(invitation.expire_le)}</span>
            <Btn kind="soft" small icon={Copy} onClick={copierCode}>
              {copie ? 'Copié' : 'Copier'}
            </Btn>
          </div>
        )}
      </div>
    </Modal>
  )
}
