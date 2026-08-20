import { useState } from 'react'
import { Sprout, ChevronDown, Check, KeyRound, ArrowLeftRight, MapPinned } from 'lucide-react'
import { usePotager } from '../context/PotagerContext.jsx'
import { Pop, PopItem, PopHead, PopSep, Badge } from './ui'
import { libelleRole } from '../lib/roles.js'
import PotagerSelector from './PotagerSelector.jsx'
import ModalModifierPotager from './ModalModifierPotager.jsx'

/**
 * Sélecteur de potager [US-054].
 *
 * Remplace le bouton texte qui ouvrait directement une modale : le nom du
 * potager actif ouvre désormais un menu déroulant listant les potagers de
 * l'utilisateur (rôle, parcelles, membres), suivi des deux actions
 * « Rejoindre un potager » et « Tous mes potagers » [CA1, CA2].
 *
 * Aucune logique métier ici : la bascule et l'adhésion restent portées par
 * `PotagerContext` (US-046) et `PotagerSelector` (US-048).
 */
/** « Éditeur · 3 parcelles · 2 membres » — accorde les pluriels. */
function sousTitrePotager({ role, nb_parcelles = 0, nb_membres = 0 }) {
  const parcelles = `${nb_parcelles} parcelle${nb_parcelles > 1 ? 's' : ''}`
  const membres = `${nb_membres} membre${nb_membres > 1 ? 's' : ''}`
  return `${libelleRole(role)} · ${parcelles} · ${membres}`
}

export default function PotagerMenu() {
  const { potagers, potagerActif, activer } = usePotager()
  const [ouvert, setOuvert] = useState(false)
  const [modale, setModale] = useState(null) // null | 'liste' | 'rejoindre'
  const [bascule, setBascule] = useState(null)

  // [CA3] Sans potager actif, rien à afficher : l'utilisateur est alors dirigé
  // vers l'assistant d'onboarding (Onboarding.jsx, US-058) par le PotagerGate d'App.jsx.
  if (!potagerActif) return null

  async function basculerVers(potagerId) {
    if (bascule || potagerId === potagerActif.id) {
      setOuvert(false)
      return
    }
    setBascule(potagerId)
    try {
      // [CA4] `activer()` recharge la page (comportement d'origine US-046 :
      // évite tout état obsolète dans les vues déjà montées).
      await activer(potagerId)
    } catch {
      setBascule(null)
    }
  }

  return (
    <div className="relative min-w-0">
      <button
        onClick={() => setOuvert((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={ouvert}
        aria-label="Changer de potager / rejoindre un potager"
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-[10px] bg-header-glass max-w-[230px] min-w-0"
      >
        <Sprout size={15} className="shrink-0" />
        {/* [CA5] Troncature en ellipse plutôt que débordement du bandeau. */}
        <span className="text-[13px] font-semibold truncate min-w-0">{potagerActif.nom}</span>
        <ChevronDown size={14} className="shrink-0" />
      </button>

      {/* Largeur 320 : laisse tenir « Propriétaire · 12 parcelles · 8 membres »
          à côté du badge « actif » sans troncature. */}
      {ouvert && (
        <Pop width={320} onClose={() => setOuvert(false)}>
          <PopHead>Vos potagers · {potagers.length}</PopHead>

          {potagers.map((p) => (
            <PopItem
              key={p.id}
              icon={p.actif ? Check : Sprout}
              tint={p.actif ? 'brand' : undefined}
              label={p.nom}
              sub={bascule === p.id ? 'Basculement…' : sousTitrePotager(p)}
              onClick={() => basculerVers(p.id)}
              right={p.actif ? <Badge tint="brand">actif</Badge> : null}
            />
          ))}

          <PopSep />

          {/* [CA2] Seul accès permanent au code d'invitation (cf. US-048 / CA4). */}
          <PopItem
            icon={KeyRound}
            label="Rejoindre un potager"
            sub="Avec un code d'invitation"
            onClick={() => {
              setOuvert(false)
              setModale('rejoindre')
            }}
          />
          <PopItem
            icon={ArrowLeftRight}
            label="Tous mes potagers"
            sub="Comparer et basculer"
            onClick={() => {
              setOuvert(false)
              setModale('liste')
            }}
          />

          {/* [US-074 / CA5] Seul moyen de localiser (ou corriger) un potager déjà
              créé — réservé au owner, même garde que la gestion des membres. */}
          {potagerActif.role === 'owner' && (
            <PopItem
              icon={MapPinned}
              label="Modifier le potager"
              sub="Nom, ville"
              onClick={() => {
                setOuvert(false)
                setModale('modifier')
              }}
            />
          )}
        </Pop>
      )}

      {(modale === 'liste' || modale === 'rejoindre') && (
        <PotagerSelector focusCode={modale === 'rejoindre'} onClose={() => setModale(null)} />
      )}
      {modale === 'modifier' && (
        <ModalModifierPotager potager={potagerActif} onClose={() => setModale(null)} />
      )}
    </div>
  )
}
