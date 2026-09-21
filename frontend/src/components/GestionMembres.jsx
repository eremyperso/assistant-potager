// [US-048 / CA3, CA5] Modal de gestion des membres du potager actif — réservée
// à l'owner : générer une invitation (code + rôle proposé), lister les membres,
// retirer un membre.
// [US-055 / CA3] Habillage aligné sur `ModalMembres` de la maquette 2026
// (`web-account.jsx`) — même logique (lister, inviter, retirer), nouveau rendu.
// [US-082 / CA4] `embedded` : rend le contenu seul, sans le shell `Modal` — pour
// vivre comme section « Membres » de ParametresPotager.jsx, sans dupliquer la
// logique liste/invitation/retrait. `lectureSeule` : masque l'encart d'invitation
// et les boutons de retrait (CA6, membre non-owner sur l'écran Paramètres) —
// AccountMenu, qui n'ouvre cette modale qu'aux owners, n'utilise ni l'un ni l'autre.
// [US-083 / CA7] `potagerId` : cible explicite, par défaut le potager actif —
// nécessaire pour consulter les membres d'un potager archivé consulté
// explicitement (jamais le potager actif, CA6), sans quoi cette modale
// afficherait toujours les membres du potager actif quel que soit l'écran
// Paramètres réellement ouvert.
// [US-085 / CA9] Le badge de rôle devient, pour l'owner, un `RoleSelect` compact :
// corriger un rôle, nommer un autre propriétaire (CA2) ou se rétrograder (CA3),
// à côté du retrait. Nommer un propriétaire — et se rétrograder soi-même — passe
// par une confirmation explicite (CA7) ; le refus « dernier propriétaire » du
// serveur (CA3/CA4) s'affiche tel quel.
import { useState, useEffect } from 'react'
import { UserMinus, Users, Copy, Key, Pencil, Eye, Crown, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api.js'
import { usePotager } from '../context/PotagerContext.jsx'
import { initiales, nomAffiche } from '../lib/identite.js'
import { confirmationChangementRole, libelleRole, teinteRole } from '../lib/roles.js'
import { Modal, Btn, RoleSelect, Badge } from './ui'

// [US-055] Icône + description par rôle invitable — porté depuis `ROLE_OPTS`
// de la maquette (`web-account.jsx`) ; libellé et teinte restent centralisés
// dans `lib/roles.js`, seule source de vérité partagée avec PotagerMenu/AccountMenu.
const ROLES_INVITABLES = [
  { value: 'editor', icon: Pencil, sub: 'Saisit récoltes, semis et cultures' },
  { value: 'lecteur', icon: Eye, sub: 'Consulte sans rien modifier' },
]

// [US-085 / CA1] Un rôle se change vers n'importe lequel des trois, `owner`
// compris — alors qu'une invitation ne propose jamais `owner`.
const ROLES_ATTRIBUABLES = [
  { value: 'owner', icon: Crown, sub: 'Gère le potager et ses membres' },
  ...ROLES_INVITABLES,
]

/** « expire dans 6 j » / « expire dans moins d'un jour » à partir d'un ISO. */
function expirationLisible(expireLe) {
  const jours = Math.ceil((new Date(expireLe).getTime() - Date.now()) / 86_400_000)
  if (jours <= 0) return "expire dans moins d'un jour"
  return `expire dans ${jours} j`
}

export default function GestionMembres({ moiId, onClose, embedded = false, lectureSeule = false, potagerId: potagerIdProp }) {
  const { potagerActif } = usePotager()
  const potagerId = potagerIdProp ?? potagerActif?.id
  const [membres, setMembres] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [rolePropose, setRolePropose] = useState('editor')
  const [invitation, setInvitation] = useState(null)
  const [copie, setCopie] = useState(false)
  // [US-085 / CA7] Changement de rôle en attente de confirmation : { membre, nouveauRole, type }.
  const [changementEnAttente, setChangementEnAttente] = useState(null)
  const [roleEnCours, setRoleEnCours] = useState(null) // user_id dont le rôle est en cours de modification

  async function recharger() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.listerMembres(potagerId)
      setMembres(res.membres)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (potagerId) recharger() }, [potagerId])

  async function handleInviter() {
    setError(null)
    try {
      const res = await api.creerInvitation(potagerId, rolePropose)
      setInvitation(res)
      setCopie(false)
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleRetirer(membreUserId) {
    setError(null)
    try {
      await api.retirerMembre(potagerId, membreUserId)
      recharger()
    } catch (e) {
      setError(e.message)
    }
  }

  // [US-085 / CA7] Nommer un propriétaire ou se rétrograder demande une
  // confirmation ; toute autre correction de rôle s'applique directement.
  function demanderChangementRole(membre, nouveauRole) {
    const type = confirmationChangementRole({
      ancienRole: membre.role,
      nouveauRole,
      estMoi: membre.user_id === moiId,
    })
    if (type) setChangementEnAttente({ membre, nouveauRole, type })
    else if (nouveauRole !== membre.role) appliquerChangementRole(membre, nouveauRole)
  }

  async function appliquerChangementRole(membre, nouveauRole) {
    setError(null)
    setRoleEnCours(membre.user_id)
    try {
      await api.modifierRoleMembre(potagerId, membre.user_id, nouveauRole)
      // [CA6] Son propre rôle vient de changer : bandeau, onglets et actions
      // réservées à l'owner doivent le refléter — rechargement complet, même
      // convention que les actions de cycle de vie (US-083) plutôt qu'une
      // synchronisation manuelle de plusieurs composants.
      if (membre.user_id === moiId) {
        window.location.reload()
        return
      }
      await recharger()
    } catch (e) {
      setError(e.message)
    } finally {
      setRoleEnCours(null)
      setChangementEnAttente(null)
    }
  }

  function copierCode() {
    navigator.clipboard?.writeText(invitation.code).then(() => {
      setCopie(true)
      setTimeout(() => setCopie(false), 1500)
    })
  }

  const contenu = (
    <>
      {error && <p className="text-red text-[13px] mb-2">{error}</p>}

      {/* [US-085 / CA9] Container query : composant réutilisé en modale (menu Compte)
          comme en section de l'écran Paramètres — sous 420 px de large, le sélecteur
          de rôle passe sur sa propre ligne sous le nom, au-delà il reste sur la ligne. */}
      <div className="@container/membres flex flex-col gap-2 mb-4">
        {loading && <span className="text-[13px] text-txt3">Chargement…</span>}
        {!loading && membres.map((m) => (
          <div key={m.user_id} className="flex flex-wrap items-center gap-x-3 gap-y-2 p-3 rounded-xl bg-card-alt">
            <span className="w-[34px] h-[34px] rounded-full bg-brand-soft text-brand-text flex items-center justify-center text-[13px] font-bold shrink-0">
              {initiales(m.nom, m.email)}
            </span>
            <span className="flex-1 min-w-[9rem]">
              <span className="flex items-center gap-1.5 text-[13.5px] font-semibold text-txt truncate">
                {nomAffiche(m.nom, m.email)}
                {m.user_id === moiId && <span className="text-[11px] font-medium text-txt3">(vous)</span>}
              </span>
              <span className="block text-[11.5px] text-txt3 truncate mt-px">{m.email}</span>
            </span>
            {/* [US-085 / CA9] L'owner change le rôle depuis la ligne ; en lecture
                seule (non-owner) le rôle reste un simple badge, comme avant. */}
            {lectureSeule ? (
              <Badge tint={teinteRole(m.role)}>{libelleRole(m.role)}</Badge>
            ) : (
              <RoleSelect
                compact
                placement="below"
                value={m.role}
                options={ROLES_ATTRIBUABLES}
                onChange={(role) => demanderChangementRole(m, role)}
                disabled={roleEnCours === m.user_id}
                ariaLabel={`Rôle de ${nomAffiche(m.nom, m.email)}`}
                className="order-last w-full @[420px]/membres:order-none @[420px]/membres:w-auto"
              />
            )}
            {/* [US-082 / CA6] Retrait masqué en lecture seule — le back refuse déjà
                toute tentative, mais le front ne propose pas une action inutilisable. */}
            {!lectureSeule && m.role !== 'owner' && (
              <button
                onClick={() => handleRetirer(m.user_id)}
                aria-label={`Retirer ${m.email || m.user_id}`}
                className="text-red hover:opacity-70 shrink-0"
              >
                <UserMinus size={15} />
              </button>
            )}
            {/* [US-085 / CA type] Place du bouton de retrait gardée vide sur les lignes
                d'owner (non retirables) : les sélecteurs de rôle restent alignés en colonne. */}
            {!lectureSeule && m.role === 'owner' && (
              <span aria-hidden="true" className="hidden @[420px]/membres:block w-[15px] shrink-0" />
            )}
          </div>
        ))}
      </div>

      {!lectureSeule && (
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
      )}

      {/* [US-085 / CA7] Confirmation explicite avant de nommer un propriétaire (ou de
          se retirer soi-même ce pouvoir) : les conséquences sont dites, pas supposées. */}
      {changementEnAttente && (
        <Modal
          title={changementEnAttente.type === 'promotion' ? 'Nommer un propriétaire' : 'Passer la main'}
          icon={Crown}
          sub={nomAffiche(changementEnAttente.membre.nom, changementEnAttente.membre.email)}
          onClose={() => setChangementEnAttente(null)}
          width={440}
        >
          <p className="flex items-start gap-2 text-[13.5px] text-txt leading-relaxed mb-4">
            <AlertTriangle size={16} className="text-amber shrink-0 mt-0.5" />
            {changementEnAttente.type === 'promotion'
              ? `${nomAffiche(changementEnAttente.membre.nom, changementEnAttente.membre.email)} deviendra propriétaire de ce potager, avec les mêmes droits que toi : archiver ou supprimer le potager, gérer les membres.`
              : `Tu ne seras plus propriétaire de ce potager (rôle : ${libelleRole(changementEnAttente.nouveauRole)}). Tu ne pourras plus l'archiver, le supprimer ni gérer ses membres — seul un autre propriétaire pourra te rendre ce rôle.`}
          </p>
          <div className="flex items-center justify-end gap-2">
            <Btn kind="ghost" onClick={() => setChangementEnAttente(null)} disabled={roleEnCours !== null}>
              Annuler
            </Btn>
            <Btn
              kind="soft"
              className="text-amber border-amber/40"
              onClick={() => appliquerChangementRole(changementEnAttente.membre, changementEnAttente.nouveauRole)}
              disabled={roleEnCours !== null}
            >
              {roleEnCours !== null
                ? '…'
                : changementEnAttente.type === 'promotion' ? 'Nommer propriétaire' : 'Me rétrograder'}
            </Btn>
          </div>
        </Modal>
      )}
    </>
  )

  if (embedded) return contenu

  return (
    <Modal
      title="Membres du potager"
      icon={Users}
      sub={`${potagerActif?.nom || '—'} · ${membres.length} membre${membres.length > 1 ? 's' : ''}`}
      onClose={onClose}
      width={520}
      foot="Seul le propriétaire peut inviter, retirer un membre ou changer son rôle."
    >
      {contenu}
    </Modal>
  )
}
