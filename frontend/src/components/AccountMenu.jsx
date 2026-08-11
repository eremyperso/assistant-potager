import { useState, useEffect, useCallback } from 'react'
import { ChevronDown, RefreshCw, Bell, Send, Unlink, Users, LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { usePotager } from '../context/PotagerContext.jsx'
import { api } from '../lib/api.js'
import { libelleRole, teinteRole } from '../lib/roles.js'
import { initiales, nomAffiche, prenomAffiche } from '../lib/identite.js'
import { Pop, PopItem, PopHead, PopSep, Badge } from './ui'
import LierTelegram from './LierTelegram.jsx'
import DelierTelegram from './DelierTelegram.jsx'
import GestionMembres from './GestionMembres.jsx'

/**
 * Menu Compte [US-055].
 *
 * Regroupe derrière l'avatar ce qui était dispersé en icônes isolées dans le
 * bandeau : identité, rôle sur le potager actif, actualisation des données,
 * liaison Telegram, gestion des membres, déconnexion et version de l'API [CA1].
 * Structure reprise du composant `AccountMenu` de la maquette 2026
 * (`web-account.jsx`).
 *
 * Aucune logique métier ici : les deux modales gardent le comportement de
 * `LierTelegram` (US-045) et `GestionMembres` (US-048) [CA2, CA3] — seul leur
 * habillage a été aligné sur `ModalTelegram`/`ModalMembres` de la maquette.
 */

export default function AccountMenu({ onRefresh, loading }) {
  const { logout } = useAuth()
  const { potagerActif } = usePotager()
  const [ouvert, setOuvert] = useState(false)
  const [modale, setModale] = useState(null) // null | 'telegram' | 'delier' | 'membres'
  const [moi, setMoi] = useState(null)
  const [version, setVersion] = useState(null)

  const chargerIdentite = useCallback(() => {
    api.moi().then(setMoi).catch(() => {})
  }, [])

  useEffect(() => { chargerIdentite() }, [chargerIdentite])

  useEffect(() => {
    api.health().then((h) => setVersion(h?.version)).catch(() => {})
  }, [])

  // L'état de la liaison Telegram peut changer hors de l'application (commandes
  // /lier et /delier côté bot) : on le rafraîchit à chaque ouverture du menu
  // plutôt que de le figer au montage.
  function basculer() {
    setOuvert((o) => {
      if (!o) chargerIdentite()
      return !o
    })
  }

  const role = potagerActif?.role
  const telegramLie = moi?.telegram_lie === true
  const nbMembres = potagerActif?.nb_membres ?? 0

  function ouvrirModale(nom) {
    setOuvert(false)
    setModale(nom)
  }

  return (
    <div className="relative shrink-0">
      <button
        onClick={basculer}
        aria-haspopup="menu"
        aria-expanded={ouvert}
        aria-label="Menu du compte"
        className="flex items-center gap-2 pl-[5px] pr-2.5 py-[5px] rounded-full bg-header-glass"
      >
        <span className="w-7 h-7 rounded-full bg-header-txt text-brand-deep flex items-center justify-center text-[12px] font-bold shrink-0">
          {initiales(moi?.nom, moi?.email)}
        </span>
        {/* [CA4] Sous 900px, seul l'avatar subsiste — le prénom prendrait la
            place dont le sélecteur de potager a besoin. */}
        <span className="text-[13px] font-semibold max-w-[110px] truncate hidden nav:inline">
          {prenomAffiche(moi?.nom, moi?.email)}
        </span>
        <ChevronDown size={14} className="shrink-0" />
      </button>

      {ouvert && (
        <Pop align="right" width={282} onClose={() => setOuvert(false)}>
          {/* Identité [CA1] */}
          <div className="flex items-center gap-2.5 p-3 bg-brand-soft">
            <span className="w-[38px] h-[38px] rounded-full bg-brand text-white dark:text-bg flex items-center justify-center text-[15px] font-bold shrink-0">
              {initiales(moi?.nom, moi?.email)}
            </span>
            <span className="min-w-0">
              <span className="block text-[13.5px] font-bold text-txt truncate">
                {nomAffiche(moi?.nom, moi?.email)}
              </span>
              <span className="block text-[11.5px] text-txt3 truncate">{moi?.email || '—'}</span>
            </span>
          </div>

          {/* Rôle sur le potager actif [CA1] */}
          {role && (
            <div className="flex items-center gap-1.5 px-3 py-2.5 border-b border-border-soft">
              <span className="text-[11.5px] text-txt3">Sur ce potager</span>
              <Badge tint={teinteRole(role)}>{libelleRole(role)}</Badge>
            </div>
          )}

          <PopHead>Compte &amp; liaisons</PopHead>

          {/* [CA4, CA5] L'actualisation reste dans le bandeau en desktop : ici,
              elle ne sert qu'en dessous de 900px, où l'icône disparaît. */}
          <PopItem
            className="nav:hidden"
            icon={RefreshCw}
            label="Actualiser les données"
            sub={loading ? 'Actualisation en cours…' : 'Recharger depuis le serveur'}
            disabled={loading}
            onClick={() => {
              setOuvert(false)
              onRefresh?.()
            }}
          />
          {/* [CA4] Emplacement réservé — la fonctionnalité de notifications
              n'existe pas encore côté application, l'entrée reste inactive.
              Écart assumé avec la maquette, qui la réserve au mobile (`wmob-only`)
              parce qu'une icône cloche la porte en desktop : cette icône n'ayant
              pas de fonction ici, l'entrée reste visible à toutes les tailles
              plutôt que de disparaître au-dessus de 900px. */}
          <PopItem icon={Bell} label="Notifications" sub="Bientôt disponible" disabled />

          <PopSep />

          {/* [CA2] Une seule entrée reflétant l'état de la liaison : non liée,
              elle ouvre l'appairage ; liée, elle ouvre directement la
              dissociation (qui a sa propre confirmation) plutôt que de
              proposer les deux actions en parallèle — un chat ne peut être
              relié qu'à un seul compte à la fois (`telegram_chat_id` est
              unique en base), donc "relier" n'a aucun sens tant qu'un lien
              existe déjà. */}
          <PopItem
            icon={telegramLie ? Unlink : Send}
            label={telegramLie ? 'Compte Telegram' : 'Relier Telegram'}
            sub={telegramLie ? 'Relié — cliquer pour dissocier' : 'Non relié'}
            onClick={() => ouvrirModale(telegramLie ? 'delier' : 'telegram')}
            right={
              telegramLie
                ? <Badge tint="brand">actif</Badge>
                : <Badge tint="amber">à faire</Badge>
            }
          />

          {/* [CA3] Réservé à l'owner du potager actif — non-régression de la
              condition d'affichage actuelle de TopBar. */}
          {role === 'owner' && (
            <PopItem
              icon={Users}
              label="Gérer les membres"
              sub={`${nbMembres} membre${nbMembres > 1 ? 's' : ''} · invitations`}
              onClick={() => ouvrirModale('membres')}
            />
          )}

          <PopSep />

          <PopItem
            icon={LogOut}
            label="Se déconnecter"
            danger
            onClick={() => {
              setOuvert(false)
              logout()
            }}
          />

          {/* [CA1] Version de l'API en pied de menu — elle occupait auparavant
              une place permanente dans le bandeau. */}
          <div className="px-3 pt-2 pb-2.5 border-t border-border-soft text-[10.5px] text-txt3">
            API v{version || '—'}
          </div>
        </Pop>
      )}

      {modale === 'telegram' && (
        <LierTelegram telegramLie={telegramLie} onClose={() => { setModale(null); chargerIdentite() }} />
      )}
      {modale === 'delier' && (
        <DelierTelegram onClose={() => { setModale(null); chargerIdentite() }} />
      )}
      {modale === 'membres' && <GestionMembres moiId={moi?.id} onClose={() => setModale(null)} />}
    </div>
  )
}
